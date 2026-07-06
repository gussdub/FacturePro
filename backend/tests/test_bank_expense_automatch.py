"""Test — l'auto-match des DÉPENSES lit le bon champ date (`expense_date`).

Régression : le matcheur lisait `exp.get("date")` (toujours None) au lieu de `expense_date`,
donc aucune dépense normalement saisie ne pouvait atteindre le score 3 requis -> jamais
d'auto-rapprochement (« trop strict »). Vérifie qu'une dépense exacte (montant+date+fournisseur)
est bien rapprochée automatiquement, + l'endpoint de re-match.
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


def _make_expense(auth_headers, amount, name, date):
    # Le nom du fournisseur va dans la description (l'API ne stocke pas de vendor en saisie
    # manuelle ; le matcheur s'appuie donc sur description OU vendor).
    r = client.post("/api/expenses", headers=auth_headers, json={
        "amount": amount, "currency": "CAD", "category_code": "office_supplies",
        "description": name, "expense_date": date})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def test_expense_automatch_uses_expense_date(auth_headers):
    exp_id = _make_expense(auth_headers, 37.30, "Genspark.ai", "2099-09-12")
    import_id = None
    try:
        csv = "Date,Description,Montant\n2099-09-12,Genspark.ai,-37.30\n"
        r = client.post("/api/bank/imports", headers=auth_headers,
                        files={"file": ("r.csv", csv, "text/csv")},
                        data={"mapping": json.dumps(MAP), "bank_label": "AMATCH"})
        assert r.status_code in (200, 201), r.text
        data = r.json()
        import_id = data["import"]["id"]
        assert data["auto_matched"] >= 1, "la dépense exacte aurait dû s'auto-rapprocher"
        tx = data["transactions"][0]
        assert tx["status"] == "matched"
        assert tx["match_kind"] == "expense" and tx["match_id"] == exp_id
        assert db.expenses.find_one({"id": exp_id}).get("bank_transaction_id") is not None
    finally:
        if import_id:
            client.delete(f"/api/bank/imports/{import_id}?force=true", headers=auth_headers)
        db.expenses.delete_one({"id": exp_id})


def test_name_match_helper_permissive_but_anchored():
    from backend.server import _name_match
    assert _name_match("Genspark.ai", "genspark.ai 877-4612631 pa") is True
    assert _name_match("Render Services Inc", "render.com ca") is True   # token « render »
    assert _name_match("Anthropic, PBC", "anthropic claude sub") is True  # token « anthropic »
    # mots génériques seuls ne matchent PAS (sinon faux rapprochements)
    assert _name_match("Paiement Hydro", "paiement bell") is False
    assert _name_match("Services ABC", "services xyz") is False


def test_automatch_tolerates_date_drift(auth_headers):
    # Dépense saisie le 08, débit bancaire le 12 (4 jours) : montant + nom -> auto-match quand même.
    exp_id = _make_expense(auth_headers, 44.44, "DriftVendorXZ", "2099-09-08")
    import_id = None
    try:
        csv = "Date,Description,Montant\n2099-09-12,DriftVendorXZ paiement,-44.44\n"
        r = client.post("/api/bank/imports", headers=auth_headers,
                        files={"file": ("r.csv", csv, "text/csv")},
                        data={"mapping": json.dumps(MAP), "bank_label": "DRIFT"})
        data = r.json()
        import_id = data["import"]["id"]
        assert data["auto_matched"] >= 1, "montant + nom devraient suffire malgré 4j d'écart"
        assert data["transactions"][0]["match_id"] == exp_id
    finally:
        if import_id:
            client.delete(f"/api/bank/imports/{import_id}?force=true", headers=auth_headers)
        db.expenses.delete_one({"id": exp_id})


def test_automatch_ambiguous_two_identical_not_matched(auth_headers):
    # Deux dépenses même montant + même nom dans la fenêtre -> ambigu -> PAS d'auto-match.
    e1 = _make_expense(auth_headers, 55.55, "AmbiguVendorQ", "2099-10-01")
    e2 = _make_expense(auth_headers, 55.55, "AmbiguVendorQ", "2099-10-02")
    import_id = None
    try:
        csv = "Date,Description,Montant\n2099-10-01,AmbiguVendorQ,-55.55\n"
        r = client.post("/api/bank/imports", headers=auth_headers,
                        files={"file": ("r.csv", csv, "text/csv")},
                        data={"mapping": json.dumps(MAP), "bank_label": "AMBIG"})
        data = r.json()
        import_id = data["import"]["id"]
        assert data["auto_matched"] == 0, "deux candidats identiques ne doivent pas s'auto-rapprocher"
    finally:
        if import_id:
            client.delete(f"/api/bank/imports/{import_id}?force=true", headers=auth_headers)
        db.expenses.delete_one({"id": e1})
        db.expenses.delete_one({"id": e2})


def test_automatch_token_name_with_fx_gap_usd_marked(auth_headers):
    # Relevé « Genspark.ai » 29.64 vs dépense « MainFunc PTE. LTD. (Genspark) » 29.01 en USD :
    # token « genspark » + montant à ~2 % (tolérance change) + date 1j -> auto-match.
    exp_id = _make_expense(auth_headers, 29.01, "MainFunc PTE. LTD. (Genspark)", "2099-09-19")
    db.expenses.update_one({"id": exp_id}, {"$set": {"currency": "USD"}})
    import_id = None
    try:
        csv = "Date,Description,Montant\n2099-09-18,Genspark.ai,-29.64\n"
        r = client.post("/api/bank/imports", headers=auth_headers,
                        files={"file": ("r.csv", csv, "text/csv")},
                        data={"mapping": json.dumps(MAP), "bank_label": "TOK"})
        data = r.json()
        import_id = data["import"]["id"]
        assert data["auto_matched"] >= 1, "USD marqué : token + montant ~2 % + date devraient matcher"
        assert data["transactions"][0]["match_id"] == exp_id
    finally:
        if import_id:
            client.delete(f"/api/bank/imports/{import_id}?force=true", headers=auth_headers)
        db.expenses.delete_one({"id": exp_id})


def test_cad_nonexact_amount_not_matched(auth_headers):
    # SÉCURITÉ (revue) : dépense CAD au montant décalé (une AUTRE facture Bell, écart ~5 %) NE
    # doit PAS s'auto-rapprocher — sans marquage devise, un écart de montant sur CAD est suspect.
    exp_id = _make_expense(auth_headers, 100.00, "Bell Mobilite", "2099-03-08")  # CAD
    import_id = None
    try:
        csv = "Date,Description,Montant\n2099-03-10,PAIEMENT BELL CANADA,-105.00\n"
        r = client.post("/api/bank/imports", headers=auth_headers,
                        files={"file": ("r.csv", csv, "text/csv")},
                        data={"mapping": json.dumps(MAP), "bank_label": "BELL"})
        data = r.json()
        import_id = data["import"]["id"]
        assert data["auto_matched"] == 0, "CAD au montant décalé de 5 % ne doit pas matcher"
    finally:
        if import_id:
            client.delete(f"/api/bank/imports/{import_id}?force=true", headers=auth_headers)
        db.expenses.delete_one({"id": exp_id})


def test_numeric_token_is_not_a_name_anchor(auth_headers):
    from backend.server import _name_match
    assert _name_match("Uber 2026", "lyft 2026 frais") is False   # « 2026 » n'ancre pas
    assert _name_match("Depanneur 123", "restaurant 123") is False
    assert _name_match("Genspark.ai", "genspark.ai 877 4612631") is True  # token alpha OK


def test_amount_close_without_name_not_matched(auth_headers):
    # Montant dans la fourchette ±5 % MAIS aucun nom qui recoupe -> PAS d'auto-match (nom requis).
    exp_id = _make_expense(auth_headers, 200.00, "Totalement Autre Chose", "2099-12-01")
    import_id = None
    try:
        csv = "Date,Description,Montant\n2099-12-01,MYSTERY VENDOR XYZ,-198.00\n"
        r = client.post("/api/bank/imports", headers=auth_headers,
                        files={"file": ("r.csv", csv, "text/csv")},
                        data={"mapping": json.dumps(MAP), "bank_label": "NONAME"})
        data = r.json()
        import_id = data["import"]["id"]
        assert data["auto_matched"] == 0, "montant proche sans nom qui recoupe ne doit pas matcher"
    finally:
        if import_id:
            client.delete(f"/api/bank/imports/{import_id}?force=true", headers=auth_headers)
        db.expenses.delete_one({"id": exp_id})


def test_foreign_currency_amount_tolerance(auth_headers):
    # Dépense USD : CAD estimé 13.07, mais débit réel 13.50 (frais de change) -> doit matcher
    # grâce à la tolérance ±5 % (0.43 <= 0.65), puis _apply_match adopte le montant exact.
    exp_id = _make_expense(auth_headers, 13.07, "FxVendorZZ", "2099-11-01")
    db.expenses.update_one({"id": exp_id}, {"$set": {"currency": "USD"}})  # devient étrangère
    import_id = None
    try:
        csv = "Date,Description,Montant\n2099-11-02,FxVendorZZ,-13.50\n"
        r = client.post("/api/bank/imports", headers=auth_headers,
                        files={"file": ("r.csv", csv, "text/csv")},
                        data={"mapping": json.dumps(MAP), "bank_label": "FX"})
        data = r.json()
        import_id = data["import"]["id"]
        assert data["auto_matched"] >= 1, "l'écart de change (~3 %) devrait être toléré"
        assert data["transactions"][0]["match_id"] == exp_id
        # _apply_match a adopté le montant exact du relevé
        exp = db.expenses.find_one({"id": exp_id})
        assert abs(float(exp["amount_cad"]) - 13.50) < 0.01
    finally:
        if import_id:
            client.delete(f"/api/bank/imports/{import_id}?force=true", headers=auth_headers)
        db.expenses.delete_one({"id": exp_id})


def test_foreign_currency_tolerance_bounded(auth_headers):
    # La tolérance de change n'est PAS illimitée : un écart de ~22 % ne doit pas matcher.
    exp_id = _make_expense(auth_headers, 13.07, "FxVendorBoundQ", "2099-11-01")
    db.expenses.update_one({"id": exp_id}, {"$set": {"currency": "USD"}})
    import_id = None
    try:
        csv = "Date,Description,Montant\n2099-11-02,FxVendorBoundQ,-16.00\n"
        r = client.post("/api/bank/imports", headers=auth_headers,
                        files={"file": ("r.csv", csv, "text/csv")},
                        data={"mapping": json.dumps(MAP), "bank_label": "FXB"})
        data = r.json()
        import_id = data["import"]["id"]
        assert data["auto_matched"] == 0, "16.00 vs 13.07 (~22 %) dépasse la tolérance ±5 %"
    finally:
        if import_id:
            client.delete(f"/api/bank/imports/{import_id}?force=true", headers=auth_headers)
        db.expenses.delete_one({"id": exp_id})


def test_rematch_endpoint_matches_after_expense_created(auth_headers):
    # Importe d'abord (aucune dépense -> aucun match), puis crée la dépense, puis re-match.
    import_id = None
    exp_id = None
    try:
        csv = "Date,Description,Montant\n2099-08-05,Acme Reload,-88.88\n"
        r = client.post("/api/bank/imports", headers=auth_headers,
                        files={"file": ("r.csv", csv, "text/csv")},
                        data={"mapping": json.dumps(MAP), "bank_label": "REMATCH"})
        data = r.json()
        import_id = data["import"]["id"]
        assert data["auto_matched"] == 0
        exp_id = _make_expense(auth_headers, 88.88, "Acme Reload", "2099-08-05")
        r2 = client.post(f"/api/bank/imports/{import_id}/rematch", headers=auth_headers)
        assert r2.status_code == 200, r2.text
        assert r2.json()["auto_matched"] >= 1
    finally:
        if import_id:
            client.delete(f"/api/bank/imports/{import_id}?force=true", headers=auth_headers)
        if exp_id:
            db.expenses.delete_one({"id": exp_id})
