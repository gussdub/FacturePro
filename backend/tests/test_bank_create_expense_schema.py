"""Tests — une dépense créée depuis une transaction bancaire utilise le schéma CANONIQUE.

Régression (revue) : `create_expense_from_tx` stockait un schéma divergent — `date` au lieu de
`expense_date`, catégorie NICHÉE sous un dict `category`, taxes sous `tps_paid`/`tvq_paid` au lieu
de `gst_paid_cad`/`qst_paid_cad`. Conséquence : les lecteurs comptables (P&L, T2125, rapport taxes,
grand livre) filtrent/lisent par `expense_date` + `category_code`/`deductible_amount`/`gst_paid_cad`
TOP-LEVEL → la dépense était ENTIÈREMENT exclue du P&L, du rapport taxes et du grand livre.

Ce fichier vérifie (a) le schéma à la création, (b) l'apparition dans le P&L, (c) la migration
idempotente des dépenses historiques déjà en base.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test")
os.environ.setdefault("DB_NAME", "facturepro")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from backend.server import app, db  # noqa: E402

client = TestClient(app)

MAP = {
    "delimiter": ",", "has_header": True, "date_column": 0, "date_format": "YYYY-MM-DD",
    "description_column": 1, "amount_mode": "single", "amount_column": 2,
    "sign_convention": "positive_is_credit",
}


@pytest.fixture
def auth_headers():
    r = client.post("/api/auth/login", json={"email": "gussdub@gmail.com", "password": "testpass123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _import_one_debit(auth_headers, date, desc, amount, label):
    csv = f"Date,Description,Montant\n{date},{desc},{amount}\n"
    r = client.post("/api/bank/imports", headers=auth_headers,
                    files={"file": ("r.csv", csv, "text/csv")},
                    data={"mapping": json.dumps(MAP), "bank_label": label})
    assert r.status_code in (200, 201), r.text
    return r.json()


def test_create_from_tx_expense_uses_canonical_schema(auth_headers):
    d = _import_one_debit(auth_headers, "2099-05-15", "STAPLES ACHAT", "-50.00", "SCHEMA")
    import_id = d["import"]["id"]
    tx = d["transactions"][0]
    exp_id = None
    try:
        r = client.post(f"/api/bank/transactions/{tx['id']}/create-expense", headers=auth_headers,
                        json={"category_code": "office_supplies"})
        assert r.status_code in (200, 201), r.text
        exp_id = r.json()["expense"]["id"]
        exp = db.expenses.find_one({"id": exp_id}, {"_id": 0})

        # Date : canonique `expense_date` présente (les rapports filtrent dessus)
        assert exp.get("expense_date") == "2099-05-15", "expense_date canonique requis (pas seulement date)"
        # Catégorie : À PLAT, pas nichée sous un dict
        assert exp.get("category_code") == "office_supplies", "category_code doit être top-level"
        assert not isinstance(exp.get("category"), dict), "category ne doit PAS être un dict niché"
        assert exp.get("deductible_amount") is not None, "deductible_amount top-level requis (P&L/T2125)"
        # Taxes : noms canoniques présents (le grand livre + le rapport taxes les lisent)
        assert "gst_paid_cad" in exp and "qst_paid_cad" in exp and "hst_paid_cad" in exp
        # Champs d'affichage/filtre canoniques
        assert "amount" in exp and "status" in exp
    finally:
        if import_id:
            client.delete(f"/api/bank/imports/{import_id}?force=true", headers=auth_headers)
        if exp_id:
            db.expenses.delete_one({"id": exp_id})


def test_create_from_tx_expense_appears_in_pnl(auth_headers):
    d = _import_one_debit(auth_headers, "2099-05-15", "STAPLES ACHAT", "-50.00", "PNL")
    import_id = d["import"]["id"]
    tx = d["transactions"][0]
    exp_id = None
    try:
        r = client.post(f"/api/bank/transactions/{tx['id']}/create-expense", headers=auth_headers,
                        json={"category_code": "office_supplies"})
        exp_id = r.json()["expense"]["id"]
        rp = client.get("/api/reports/pnl?start=2099-05-01&end=2099-05-31&basis=accrual",
                        headers=auth_headers)
        assert rp.status_code == 200, rp.text
        body = rp.json()
        # La dépense doit apparaître dans une catégorie du P&L — office_supplies, PAS "other"
        found = None
        for grp in body["expense_groups"]:
            for cat in grp["categories"]:
                if cat["code"] == "office_supplies":
                    found = cat
        assert found is not None, "la dépense create-from-tx doit apparaître dans le P&L (office_supplies)"
        assert found["current"]["gross"] >= 50.0, "le montant de la dépense doit être comptabilisé"
    finally:
        if import_id:
            client.delete(f"/api/bank/imports/{import_id}?force=true", headers=auth_headers)
        if exp_id:
            db.expenses.delete_one({"id": exp_id})


def test_create_from_tx_telecom_applies_business_pct(auth_headers):
    # Feature #14 (revue) : une dépense TÉLÉCOM créée depuis la banque doit appliquer le % affaires
    # usage mixte de l'org (parité avec la saisie manuelle) — sinon déductible 100 % = sur-déduction
    # + sur-réclamation du CTI. On configure 60 % puis on vérifie déductible 60 / perso 40 sur 100 $.
    # Découvre l'org via une dépense sonde (l'org_id = organization_id de la dépense créée).
    d0 = _import_one_debit(auth_headers, "2099-03-01", "PROBE ORG", "-1.00", "PROBE")
    r0 = client.post(f"/api/bank/transactions/{d0['transactions'][0]['id']}/create-expense",
                     headers=auth_headers, json={"category_code": "office_supplies"})
    probe = db.expenses.find_one({"id": r0.json()["expense"]["id"]}, {"_id": 0})
    org_id = probe.get("organization_id")
    client.delete(f"/api/bank/imports/{d0['import']['id']}?force=true", headers=auth_headers)
    db.expenses.delete_one({"id": probe["id"]})
    if not org_id:
        pytest.skip("org_id indisponible (utilisateur legacy)")

    prev = db.company_settings.find_one({"organization_id": org_id}, {"_id": 0}) or {}
    db.company_settings.update_one(
        {"organization_id": org_id},
        {"$set": {"telecom_cell_mixed_use": True, "telecom_cell_business_pct": 60}}, upsert=True)
    d = _import_one_debit(auth_headers, "2099-03-15", "TELUS MOBILITE", "-100.00", "TELE")
    import_id = d["import"]["id"]
    exp_id = None
    try:
        r = client.post(f"/api/bank/transactions/{d['transactions'][0]['id']}/create-expense",
                        headers=auth_headers, json={"category_code": "telecom_cell"})
        assert r.status_code in (200, 201), r.text
        exp_id = r.json()["expense"]["id"]
        exp = db.expenses.find_one({"id": exp_id}, {"_id": 0})
        assert exp["deductible_percentage"] == 60, "le % affaires télécom doit s'appliquer"
        assert exp["deductible_amount"] == 60.0, "déductible = 60 % de 100 $"
        assert exp["personal_use_amount_cad"] == 40.0, "portion perso figée (P&L/GL)"
    finally:
        if import_id:
            client.delete(f"/api/bank/imports/{import_id}?force=true", headers=auth_headers)
        if exp_id:
            db.expenses.delete_one({"id": exp_id})
        # Restaure exactement les réglages télécom d'origine (set si présent, unset sinon)
        op = {}
        for k in ("telecom_cell_mixed_use", "telecom_cell_business_pct"):
            if k in prev:
                op.setdefault("$set", {})[k] = prev[k]
            else:
                op.setdefault("$unset", {})[k] = ""
        if op:
            db.company_settings.update_one({"organization_id": org_id}, op)


def test_migration_normalizes_legacy_bank_expense():
    # Insère une dépense au SCHÉMA HISTORIQUE divergent (comme l'ancien create_expense_from_tx),
    # lance la migration idempotente, et vérifie qu'elle est normalisée + ré-exécutable sans effet.
    from backend.server import migrate_bank_created_expenses_v1
    legacy_id = "test-legacy-bank-exp-0001"
    db.expenses.delete_one({"id": legacy_id})
    db.expenses.insert_one({
        "id": legacy_id,
        "organization_id": "test-org-legacy",
        "user_id": "test-user-legacy",
        "date": "2099-04-10",                     # <- pas d'expense_date
        "amount_cad": 80.0,
        "currency": "CAD",
        "exchange_rate_to_cad": 1.0,
        "vendor": "Legacy Vendor",
        "description": "LEGACY BANK EXPENSE",
        "bank_transaction_id": "some-tx-id",
        "category": {"category": "Fournitures de bureau", "category_code": "office_supplies",
                     "category_arc_line": "9270", "deductible_percentage": 100,
                     "deductible_amount": 80.0},  # <- catégorie NICHÉE
        "tps_paid": 0.0, "tvq_paid": 0.0, "tvh_paid": 0.0, "tps_paid_cad": 0.0,
        "created_at": "2099-04-10T00:00:00+00:00",
    })
    try:
        migrate_bank_created_expenses_v1()
        exp = db.expenses.find_one({"id": legacy_id}, {"_id": 0})
        assert exp.get("expense_date") == "2099-04-10", "date -> expense_date"
        assert exp.get("category_code") == "office_supplies", "catégorie aplatie"
        assert not isinstance(exp.get("category"), dict), "plus de dict niché"
        assert exp.get("deductible_amount") == 80.0
        assert exp.get("gst_paid_cad") == 0.0 and "qst_paid_cad" in exp
        # Idempotence : relancer ne change plus rien (aucun dict niché à retraiter)
        migrate_bank_created_expenses_v1()
        exp2 = db.expenses.find_one({"id": legacy_id}, {"_id": 0})
        assert exp2 == exp, "la migration doit être idempotente"
    finally:
        db.expenses.delete_one({"id": legacy_id})
