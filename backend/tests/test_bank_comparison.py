"""Tests — rapport de comparaison relevé ↔ dépenses (feature #7.14).

Classe chaque retrait : concordante / écart (conversion) / absente. Lecture seule."""
import os
import sys
import uuid as _uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test")
os.environ.setdefault("DB_NAME", "facturepro")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from backend.server import (  # noqa: E402
    app, db, _reconciliation_comparison, _render_comparison_csv, _render_comparison_pdf,
)

client = TestClient(app)


@pytest.fixture()
def recon_org():
    org_id = f"TESTORG-CMP-{_uuid.uuid4()}"
    import_id = str(_uuid.uuid4())
    scope = {"organization_id": org_id}
    db.bank_imports.insert_one({
        "id": import_id, "organization_id": org_id, "bank_label": "Relevé test",
        "row_count": 4, "imported_at": "2026-08-20T00:00:00Z"})

    def tx(desc, amt, date, ridx, **extra):
        db.bank_transactions.insert_one({
            "id": str(_uuid.uuid4()), "import_id": import_id, "organization_id": org_id,
            "date": date, "description": desc, "amount_cad": amt, "status": "unmatched",
            "match_kind": None, "match_id": None, "row_index": ridx, "parse_error": False,
            **extra})

    def expense(vendor, amount_cad, currency, date, **extra):
        eid = str(_uuid.uuid4())
        db.expenses.insert_one({
            "id": eid, "organization_id": org_id, "vendor": vendor, "description": vendor,
            "amount_cad": amount_cad, "currency": currency, "expense_date": date,
            "bank_transaction_id": None, **extra})
        return eid

    # Débits
    tx("VERCEL.COM PURCHASE", -54.80, "2026-08-08", 1)   # USD → écart vs estimé 56.04
    tx("STAPLES OFFICE 123", -404.70, "2026-08-17", 2)   # CAD → concordante exacte
    tx("UNKNOWN VENDOR ZZZ", -99.99, "2026-08-01", 3)    # aucune dépense → absente
    tx("DEPOT CLIENT ABC", 500.00, "2026-08-05", 4)      # crédit → ignoré
    # Dépenses existantes (non rapprochées)
    expense("Vercel Inc", 56.04, "USD", "2026-08-08")     # estimé ≠ banque
    expense("Staples", 404.70, "CAD", "2026-08-17")       # exact

    yield {"org_id": org_id, "import_id": import_id, "scope": scope}
    db.bank_imports.delete_many({"organization_id": org_id})
    db.bank_transactions.delete_many({"organization_id": org_id})
    db.expenses.delete_many({"organization_id": org_id})


class TestComparison:
    def test_three_states_and_summary(self, recon_org):
        rep = _reconciliation_comparison(recon_org["import_id"], recon_org["scope"])
        s = rep["summary"]
        assert s["concordante"] == 1 and s["ecart"] == 1 and s["absente"] == 1
        assert s["total_debits"] == 3            # le crédit est exclu
        assert s["total_fx_ecart"] == -1.24      # 54.80 - 56.04

    def test_ecart_line(self, recon_org):
        rep = _reconciliation_comparison(recon_org["import_id"], recon_org["scope"])
        vercel = next(l for l in rep["lines"] if "VERCEL" in l["description"])
        assert vercel["status"] == "ecart"
        assert vercel["ecart"] == -1.24
        assert vercel["expense"]["amount_cad"] == 56.04
        assert vercel["expense"]["currency"] == "USD"

    def test_concordante_line(self, recon_org):
        rep = _reconciliation_comparison(recon_org["import_id"], recon_org["scope"])
        staples = next(l for l in rep["lines"] if "STAPLES" in l["description"])
        assert staples["status"] == "concordante" and staples["ecart"] == 0.0

    def test_absente_line(self, recon_org):
        rep = _reconciliation_comparison(recon_org["import_id"], recon_org["scope"])
        unk = next(l for l in rep["lines"] if "UNKNOWN" in l["description"])
        assert unk["status"] == "absente" and unk["expense"] is None

    def test_credit_excluded(self, recon_org):
        rep = _reconciliation_comparison(recon_org["import_id"], recon_org["scope"])
        assert not any("DEPOT" in l["description"] for l in rep["lines"])

    def test_already_matched_is_concordante(self, recon_org):
        # Marque le Staples comme déjà rapproché et vérifie le classement "concordante".
        org_id = recon_org["org_id"]
        exp = db.expenses.find_one({"organization_id": org_id, "vendor": "Staples"}, {"_id": 0})
        tx = db.bank_transactions.find_one(
            {"organization_id": org_id, "description": {"$regex": "STAPLES"}}, {"_id": 0})
        db.bank_transactions.update_one(
            {"id": tx["id"]},
            {"$set": {"status": "matched", "match_kind": "expense", "match_id": exp["id"]}})
        db.expenses.update_one({"id": exp["id"]}, {"$set": {"bank_transaction_id": tx["id"]}})
        rep = _reconciliation_comparison(recon_org["import_id"], recon_org["scope"])
        line = next(l for l in rep["lines"] if "STAPLES" in l["description"])
        assert line["status"] == "concordante" and line.get("already_matched") is True

    def test_csv_sanitizes_and_shape(self, recon_org):
        rep = _reconciliation_comparison(recon_org["import_id"], recon_org["scope"])
        text = _render_comparison_csv(rep).decode("utf-8-sig")
        assert text.startswith("État,Date,Description relevé,Montant banque,Dépense,CAD dépense,Devise,Écart")
        assert "Concordante" in text and "Écart" in text and "Absente" in text

    def test_pdf_renders(self, recon_org):
        rep = _reconciliation_comparison(recon_org["import_id"], recon_org["scope"])
        pdf = _render_comparison_pdf(rep, recon_org["org_id"], "Relevé test")
        assert pdf[:4] == b"%PDF" and len(pdf) > 800

    def test_accents_match_stripped_bank_description(self):
        # Revue #2 : « Épicerie Métro » doit recouper « EPICERIE METRO » (relevé dépouillé).
        from backend.server import _name_match
        assert _name_match("Épicerie Métro", "epicerie metro 4001")
        assert _name_match("Dépanneur Café", "depanneur cafe inc")

    def test_foreign_ecart_can_adopt(self, recon_org):
        rep = _reconciliation_comparison(recon_org["import_id"], recon_org["scope"])
        vercel = next(l for l in rep["lines"] if "VERCEL" in l["description"])
        assert vercel["status"] == "ecart" and vercel["can_adopt"] is True  # USD → adoptable

    def test_cad_ecart_not_adoptable(self, recon_org):
        # Revue #1 (BLOCKING) : écart sur une dépense CAD → ecart mais PAS de bouton adopter (no-op).
        org_id, import_id = recon_org["org_id"], recon_org["import_id"]
        db.expenses.insert_one({"id": str(_uuid.uuid4()), "organization_id": org_id,
            "vendor": "Quincaillerie", "description": "Quincaillerie", "amount_cad": 200.0,
            "currency": "CAD", "expense_date": "2026-08-10", "bank_transaction_id": None})
        db.bank_transactions.insert_one({"id": str(_uuid.uuid4()), "import_id": import_id,
            "organization_id": org_id, "date": "2026-08-10", "description": "QUINCAILLERIE 55",
            "amount_cad": -210.0, "status": "unmatched", "match_kind": None, "match_id": None,
            "row_index": 9, "parse_error": False})
        rep = _reconciliation_comparison(import_id, recon_org["scope"])
        q = next(l for l in rep["lines"] if "QUINCAILLERIE" in l["description"])
        assert q["status"] == "ecart" and q["can_adopt"] is False and q["ecart"] == 10.0

    def test_expense_consumed_second_tx_absente(self, recon_org):
        # Revue #3 : 2 débits même fournisseur, 1 seule dépense → 2e = absente (dépense manquante).
        org_id, import_id = recon_org["org_id"], recon_org["import_id"]
        db.expenses.insert_one({"id": str(_uuid.uuid4()), "organization_id": org_id,
            "vendor": "Netflix", "description": "Netflix", "amount_cad": 16.99,
            "currency": "CAD", "expense_date": "2026-08-15", "bank_transaction_id": None})
        for ridx, d in ((10, "2026-08-15"), (11, "2026-08-18")):
            db.bank_transactions.insert_one({"id": str(_uuid.uuid4()), "import_id": import_id,
                "organization_id": org_id, "date": d, "description": "NETFLIX.COM",
                "amount_cad": -16.99, "status": "unmatched", "match_kind": None,
                "match_id": None, "row_index": ridx, "parse_error": False})
        rep = _reconciliation_comparison(import_id, recon_org["scope"])
        nflx = [l for l in rep["lines"] if "NETFLIX" in l["description"]]
        assert len(nflx) == 2
        assert sorted(l["status"] for l in nflx) == ["absente", "concordante"]


@pytest.fixture
def auth_headers():
    r = client.post("/api/auth/login",
                    json={"email": "gussdub@gmail.com", "password": "testpass123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


class TestEndpoints:
    def test_comparison_404_unknown_import(self, auth_headers):
        r = client.get("/api/bank/imports/does-not-exist/comparison", headers=auth_headers)
        assert r.status_code == 404
        r2 = client.get("/api/bank/imports/nope/comparison/pdf", headers=auth_headers)
        assert r2.status_code == 404
        r3 = client.get("/api/bank/imports/nope/comparison/csv", headers=auth_headers)
        assert r3.status_code == 404
