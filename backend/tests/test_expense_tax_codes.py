"""Tests — codes fiscaux adaptés au type d'entité (feature #7.6).

Vérifie que :
- EXPENSE_CATEGORIES porte les 4 nouveaux champs (t2125_line, gifi_code, etc.).
- Le snapshot de dépense fige les deux codes + garde category_arc_line legacy.
- La migration migrate_expense_tax_codes_v1 corrige les codes ARC erronés + ajoute
  les nouveaux champs sur les dépenses historiques.
- Le rapport GIFI agrège par category_gifi_code.
- Le rapport T2125 continue de fonctionner (rétrocompat via category_arc_line).
"""
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


@pytest.fixture
def auth_headers():
    r = client.post("/api/auth/login", json={"email": "gussdub@gmail.com", "password": "testpass123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_expense_categories_have_dual_codes():
    """Chaque catégorie porte les 4 nouveaux champs (t2125_line + t2125_label_fr +
    gifi_code + gifi_label_en) et n'a PLUS de arc_line."""
    from backend.server import EXPENSE_CATEGORIES
    required = {"code", "label_fr", "label_en", "t2125_line", "t2125_label_fr",
                "gifi_code", "gifi_label_en", "deductible_percentage", "group"}
    for cat in EXPENSE_CATEGORIES:
        missing = required - set(cat.keys())
        assert not missing, f"{cat['code']} manque {missing}"
        assert "arc_line" not in cat, f"{cat['code']} porte encore l'ancien arc_line"


def test_expense_categories_correct_codes():
    """Codes fiscaux corrigés par la revue adversariale multi-sources CRA."""
    from backend.server import EXPENSE_CATEGORIES
    by = {c["code"]: c for c in EXPENSE_CATEGORIES}
    # Corrections dues aux erreurs historiques
    assert by["bank_charges"]["t2125_line"] == "8710"
    assert by["bank_charges"]["gifi_code"] == "8715"
    assert by["subscriptions"]["t2125_line"] == "8760"
    assert by["subscriptions"]["gifi_code"] == "8810"
    assert by["subcontracts"]["t2125_line"] == "9060"  # pas de ligne T2125 dédiée
    assert by["subcontracts"]["gifi_code"] == "9110"
    # T2125 8521 ≠ GIFI 8520 pour la pub (à 1 chiffre d'écart)
    assert by["advertising"]["t2125_line"] == "8521"
    assert by["advertising"]["gifi_code"] == "8520"
    # Télécom : T2125 pas de ligne dédiée (convention 9220), GIFI granulaire
    assert by["telecom_cell"]["gifi_code"] == "9225"
    assert by["telecom_internet"]["gifi_code"] == "9152"


def test_snapshot_writes_dual_codes():
    """Le snapshot fige category_t2125_line + category_gifi_code + garde
    category_arc_line pour la rétrocompat du rapport T2125."""
    from backend.server import _build_expense_category_snapshot
    snap = _build_expense_category_snapshot({"category_code": "subscriptions"}, 100.0)
    assert snap["category_t2125_line"] == "8760"
    assert snap["category_t2125_label_fr"] == "Taxes d'affaires, droits d'adhésion et licences"
    assert snap["category_gifi_code"] == "8810"
    assert snap["category_gifi_label_en"] == "Office expenses"
    # Rétrocompat : category_arc_line = category_t2125_line
    assert snap["category_arc_line"] == "8760"


def test_snapshot_other_code_empty_gifi_ok():
    """Le code 'other' a un gifi/t2125 dédiés (9270) — pas de champ vide."""
    from backend.server import _build_expense_category_snapshot
    snap = _build_expense_category_snapshot({"category_code": "other"}, 50.0)
    assert snap["category_t2125_line"] == "9270"
    assert snap["category_gifi_code"] == "9270"


def test_snapshot_unknown_code_graceful():
    """Un code inconnu → snapshot avec champs vides (comportement legacy conservé)."""
    from backend.server import _build_expense_category_snapshot
    snap = _build_expense_category_snapshot(
        {"category_code": "totally_made_up", "category": "Mon label libre"}, 10.0)
    assert snap["category_t2125_line"] == ""
    assert snap["category_gifi_code"] == ""
    assert snap["category_arc_line"] == ""


def test_categories_endpoint_returns_dual_codes(auth_headers):
    """GET /api/expense-categories retourne les 4 nouveaux champs par catégorie.

    L'endpoint expose une enveloppe {"categories": [...], "groups": {...}} —
    contrat inchangé (ExpensesPage.js le consomme tel quel)."""
    r = client.get("/api/expense-categories", headers=auth_headers)
    assert r.status_code == 200, r.text
    payload = r.json()
    assert "categories" in payload and "groups" in payload
    cats = payload["categories"]
    assert isinstance(cats, list) and len(cats) >= 20
    by = {c["code"]: c for c in cats}
    subs = by["subscriptions"]
    assert subs["t2125_line"] == "8760"
    assert subs["t2125_label_fr"] == "Taxes d'affaires, droits d'adhésion et licences"
    assert subs["gifi_code"] == "8810"
    assert subs["gifi_label_en"] == "Office expenses"
    # arc_line n'est plus dans le modèle canonique (T1)
    assert "arc_line" not in subs, "arc_line ne doit plus être présent sur la catégorie"


def test_migration_backfills_dual_codes(auth_headers):
    """Une dépense legacy (uniquement category_arc_line + arc_line erroné) reçoit
    les 4 nouveaux champs + un category_arc_line corrigé après migration."""
    from backend.server import migrate_expense_tax_codes_v1
    # Créer une dépense legacy manuellement en DB (schéma pré-migration)
    org_id = _probe_org_id(auth_headers)
    if not org_id:
        pytest.skip("org_id indisponible")
    from backend import server
    legacy_id = "test_legacy_migr_" + os.urandom(4).hex()
    server.db.expenses.insert_one({
        "id": legacy_id, "organization_id": org_id, "user_id": "test",
        "amount": 100.0, "amount_cad": 100.0, "currency": "CAD",
        "category_code": "subscriptions", "category": "Abonnements et licences",
        "category_arc_line": "8740",  # ancien code erroné
        "deductible_percentage": 100, "deductible_amount": 100.0,
        "expense_date": "2099-01-15",
    })
    try:
        stats = migrate_expense_tax_codes_v1()
        assert stats["updated"] >= 1
        migrated = server.db.expenses.find_one({"id": legacy_id}, {"_id": 0})
        assert migrated["category_t2125_line"] == "8760"
        assert migrated["category_gifi_code"] == "8810"
        assert migrated["category_arc_line"] == "8760", "arc_line legacy corrigé"
        # 2e passage : rien à faire (idempotent)
        stats2 = migrate_expense_tax_codes_v1()
        assert legacy_id not in stats2.get("touched_ids", []), \
            "migration doit être idempotente sur cette dépense"
    finally:
        server.db.expenses.delete_one({"id": legacy_id})


def _probe_org_id(auth_headers):
    """Récupère l'org_id du user de test via une dépense sonde."""
    r = client.post("/api/expenses", headers=auth_headers, json={
        "amount": 1.00, "currency": "CAD", "category_code": "office_supplies",
        "description": "PROBE", "expense_date": "2099-01-01"})
    if r.status_code not in (200, 201):
        return None
    exp_id = r.json()["id"]
    from backend import server
    doc = server.db.expenses.find_one({"id": exp_id}, {"_id": 0})
    server.db.expenses.delete_one({"id": exp_id})
    return doc.get("organization_id") if doc else None


def test_gifi_group_by_code_aggregates_correctly():
    """_gifi_group_by_code agrège les dépenses par category_gifi_code + attache le label."""
    from backend.server import _gifi_group_by_code
    flat = {
        "meals_entertainment": {"gross": 200.0, "deductible": 100.0,
                                 "t2125_line": "8523", "gifi_code": "8523"},
        "rent": {"gross": 1000.0, "deductible": 1000.0,
                 "t2125_line": "8910", "gifi_code": "8910"},
        "subscriptions": {"gross": 50.0, "deductible": 50.0,
                          "t2125_line": "8760", "gifi_code": "8810"},
    }
    grouped = _gifi_group_by_code(flat)
    by_code = {g["code"]: g for g in grouped}
    assert by_code["8523"]["amount"] == 100.0  # déductible
    assert by_code["8523"]["label"] == "Meals and entertainment"
    assert by_code["8910"]["amount"] == 1000.0
    # subscriptions → 8810 GIFI (pas 8760 T2125)
    assert by_code["8810"]["amount"] == 50.0
    assert by_code["8810"]["label"] == "Office expenses"


def test_flatten_reads_both_codes():
    """_flatten_pnl_expenses attache t2125_line ET gifi_code sur chaque catégorie.

    Shape fidèle à _aggregate_pnl: expense_groups[].categories[] avec "code"
    (pas "expenses[].category_code" — ancienne forme incorrecte)."""
    from backend.server import _flatten_pnl_expenses
    groups = [{
        "categories": [
            {"code": "subscriptions", "gross": 50.0, "deductible": 50.0},
        ],
    }]
    flat = _flatten_pnl_expenses(groups)
    assert "subscriptions" in flat
    assert flat["subscriptions"]["t2125_line"] == "8760"
    assert flat["subscriptions"]["gifi_code"] == "8810"


def test_gifi_report_endpoint(auth_headers):
    """GET /api/reports/gifi?year=YYYY&basis=cash retourne l'agrégation par gifi_code."""
    # Créer deux dépenses dans deux catégories distinctes
    e1 = client.post("/api/expenses", headers=auth_headers, json={
        "amount": 100.0, "currency": "CAD", "category_code": "meals_entertainment",
        "description": "Diner client", "expense_date": "2099-04-10"}).json()["id"]
    e2 = client.post("/api/expenses", headers=auth_headers, json={
        "amount": 500.0, "currency": "CAD", "category_code": "rent",
        "description": "Loyer avril", "expense_date": "2099-04-01"}).json()["id"]
    try:
        r = client.get("/api/reports/gifi?year=2099&basis=cash", headers=auth_headers)
        assert r.status_code == 200, r.text
        report = r.json()
        assert "lines" in report and "total" in report
        by = {ln["code"]: ln for ln in report["lines"]}
        assert "8523" in by  # meals GIFI
        assert "8910" in by  # rent GIFI
        # Meals 50% déductible → 50.0
        assert by["8523"]["amount"] == 50.0
        assert by["8523"]["label"] == "Meals and entertainment"
        assert by["8910"]["amount"] == 500.0
    finally:
        from backend import server
        for eid in (e1, e2):
            server.db.expenses.delete_one({"id": eid})


def test_gifi_report_csv(auth_headers):
    e = client.post("/api/expenses", headers=auth_headers, json={
        "amount": 100.0, "currency": "CAD", "category_code": "advertising",
        "description": "Facebook ads", "expense_date": "2099-05-01"}).json()["id"]
    try:
        r = client.get("/api/reports/gifi/csv?year=2099&basis=cash", headers=auth_headers)
        assert r.status_code == 200
        body = r.text
        assert "Code GIFI" in body or "GIFI" in body
        assert "8520" in body  # advertising GIFI
        assert "Advertising and promotion" in body
        assert "100" in body
    finally:
        from backend import server
        server.db.expenses.delete_one({"id": e})


def test_gifi_report_pdf(auth_headers):
    e = client.post("/api/expenses", headers=auth_headers, json={
        "amount": 200.0, "currency": "CAD", "category_code": "professional_fees",
        "description": "Comptable", "expense_date": "2099-06-01"}).json()["id"]
    try:
        r = client.get("/api/reports/gifi/pdf?year=2099&basis=cash", headers=auth_headers)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/pdf")
        assert r.content[:4] == b"%PDF", "doit être un PDF valide"
        assert len(r.content) > 500  # taille raisonnable pour un PDF avec au moins une ligne
    finally:
        from backend import server
        server.db.expenses.delete_one({"id": e})
