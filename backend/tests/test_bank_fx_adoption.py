"""Tests — adoption du montant CAD réel de la banque au rapprochement (devise étrangère).

Quand on associe une transaction Desjardins (le VRAI montant CAD débité, marge de change
incluse) à une dépense en devise étrangère, FacturePro adopte ce montant réel plutôt que
l'estimation par taux de marché, et recalcule le taux + les champs dérivés.
"""
import os
import sys
import uuid as _uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test")

import pytest  # noqa: E402
from backend.server import _apply_match, db  # noqa: E402


@pytest.fixture()
def org_scope():
    scope = {"organization_id": f"TESTORG-FX-{_uuid.uuid4()}"}
    yield scope
    db.expenses.delete_many(scope)
    db.bank_transactions.delete_many(scope)


def _mk_expense(scope, **over):
    doc = {
        "id": str(_uuid.uuid4()), "organization_id": scope["organization_id"],
        "created_by_user_id": "u1", "user_id": "u1",
        "amount": 40.0, "currency": "USD", "exchange_rate_to_cad": 0.7175,
        "amount_cad": 55.75, "deductible_percentage": 100, "deductible_amount": 55.75,
        "category_code": "subscriptions", "expense_date": "2026-06-08",
        "gst_paid_cad": 0, "qst_paid_cad": 0, "hst_paid_cad": 0,
        "status": "pending", "bank_transaction_id": None,
    }
    doc.update(over)
    db.expenses.insert_one(dict(doc))
    return doc


def _mk_tx(scope, amount_cad):
    tx = {"id": str(_uuid.uuid4()), "organization_id": scope["organization_id"],
          "status": "unmatched", "amount_cad": amount_cad, "date": "2026-06-08",
          "description": "VERCEL INC", "match_kind": None, "match_id": None, "invoice_id": None}
    db.bank_transactions.insert_one(dict(tx))
    return tx


class TestFxAdoption:
    def test_foreign_expense_adopts_bank_amount(self, org_scope):
        exp = _mk_expense(org_scope)
        tx = _mk_tx(org_scope, -57.21)  # débit de 57.21 CAD (le vrai montant Desjardins)
        _apply_match(tx, "expense", exp["id"], org_scope)
        got = db.expenses.find_one({"id": exp["id"], **org_scope}, {"_id": 0})
        assert got["amount_cad"] == 57.21
        assert got["cad_amount_source"] == "bank"
        assert got["amount_cad_estimated"] == 55.75
        assert got["deductible_amount"] == 57.21
        assert abs(got["exchange_rate_to_cad"] - (40 / 57.21)) < 1e-4  # taux réel back-calculé
        assert got["bank_transaction_id"] == tx["id"]

    def test_cad_expense_not_adopted(self, org_scope):
        exp = _mk_expense(org_scope, currency="CAD", exchange_rate_to_cad=1.0,
                          amount=55.00, amount_cad=55.00, deductible_amount=55.00)
        tx = _mk_tx(org_scope, -57.21)
        _apply_match(tx, "expense", exp["id"], org_scope)
        got = db.expenses.find_one({"id": exp["id"], **org_scope}, {"_id": 0})
        assert got["amount_cad"] == 55.00               # jamais modifié pour du CAD
        assert got.get("cad_amount_source") != "bank"
        assert got["bank_transaction_id"] == tx["id"]   # mais bien lié

    def test_telecom_foreign_recomputes_personal(self, org_scope):
        exp = _mk_expense(org_scope, category_code="telecom_cell", deductible_percentage=85,
                          deductible_amount=47.39, personal_use_amount_cad=8.36)
        tx = _mk_tx(org_scope, -57.21)
        _apply_match(tx, "expense", exp["id"], org_scope)
        got = db.expenses.find_one({"id": exp["id"], **org_scope}, {"_id": 0})
        assert got["amount_cad"] == 57.21
        assert got["deductible_amount"] == round(57.21 * 0.85, 2)             # 48.63
        assert got["personal_use_amount_cad"] == round(57.21 - round(57.21 * 0.85, 2), 2)
        assert round(got["deductible_amount"] + got["personal_use_amount_cad"], 2) == 57.21

    def test_estimate_equal_to_bank_no_adoption(self, org_scope):
        exp = _mk_expense(org_scope, amount_cad=57.21, deductible_amount=57.21)
        tx = _mk_tx(org_scope, -57.21)
        _apply_match(tx, "expense", exp["id"], org_scope)
        got = db.expenses.find_one({"id": exp["id"], **org_scope}, {"_id": 0})
        assert "cad_amount_source" not in got           # écart < 0.01 → pas d'adoption
        assert got["bank_transaction_id"] == tx["id"]

    def test_double_match_rejected(self, org_scope):
        # Correctif revue : dépense déjà liée à une autre tx → 409 (pas d'écrasement/orphelin).
        from fastapi import HTTPException
        exp = _mk_expense(org_scope, bank_transaction_id="AUTRE-TX")
        tx = _mk_tx(org_scope, -60.00)
        with pytest.raises(HTTPException) as ei:
            _apply_match(tx, "expense", exp["id"], org_scope)
        assert ei.value.status_code == 409


class TestEditPurgesAdoption:
    """Correctif BLOQUANT de la revue : éditer le montant d'une dépense adoptée doit purger
    l'état d'adoption (sinon un unmatch restaurerait une estimation périmée)."""
    def test_edit_amount_purges_bank_source(self):
        from fastapi.testclient import TestClient
        from backend.server import app
        client = TestClient(app)
        r = client.post("/api/auth/login", json={"email": "gussdub@gmail.com", "password": "testpass123"})
        assert r.status_code == 200, r.text
        h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        org = client.get("/api/org/me", headers=h).json()["organization"]["id"]
        eid = str(_uuid.uuid4())
        db.expenses.insert_one({
            "id": eid, "organization_id": org, "created_by_user_id": "x", "user_id": "x",
            "amount": 40.0, "currency": "USD", "exchange_rate_to_cad": 0.6992, "amount_cad": 57.21,
            "deductible_percentage": 100, "deductible_amount": 57.21,
            "cad_amount_source": "bank", "amount_cad_estimated": 55.75,
            "category_code": "subscriptions", "expense_date": "2026-06-08",
            "gst_paid_cad": 0, "qst_paid_cad": 0, "hst_paid_cad": 0,
            "status": "pending", "bank_transaction_id": None,
        })
        try:
            resp = client.put(f"/api/expenses/{eid}", json={"amount": 45}, headers=h)
            assert resp.status_code == 200, resp.text
            got = db.expenses.find_one({"id": eid}, {"_id": 0})
            assert got["cad_amount_source"] == "estimate"      # purgé
            assert got["amount_cad_estimated"] is None          # purgé
            assert got["amount_cad"] == round(45 / 0.6992, 2)   # nouveau montant, pas l'estimation
        finally:
            db.expenses.delete_one({"id": eid})
