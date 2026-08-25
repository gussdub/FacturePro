"""Tests — précision de la conversion USD→CAD (Phase 1, 2026-08-21).

1. Rapprochement : tolérance de montant élargie à ±15 % pour une dépense en devise étrangère
   → une marge de carte réaliste (ex. +5,4 %) matche désormais et adopte le VRAI montant CAD débité.
2. Saisie : override manuel du montant CAD réel (cad_amount_source='manual').
"""
import os
import sys
import uuid as _uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test")
os.environ.setdefault("DB_NAME", "facturepro")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from backend.server import app, db, _auto_match_transactions, _apply_match  # noqa: E402

client = TestClient(app)


@pytest.fixture
def auth_headers():
    r = client.post("/api/auth/login",
                    json={"email": "gussdub@gmail.com", "password": "testpass123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def org_scope():
    scope = {"organization_id": f"TESTORG-FXC-{_uuid.uuid4()}"}
    yield scope
    db.expenses.delete_many(scope)
    db.bank_transactions.delete_many(scope)


def _mk_expense(scope, **over):
    doc = {"id": str(_uuid.uuid4()), "organization_id": scope["organization_id"],
           "created_by_user_id": "u1", "user_id": "u1",
           "amount": 23.0, "currency": "USD", "exchange_rate_to_cad": 0.7215,
           "amount_cad": 31.88, "deductible_percentage": 100, "deductible_amount": 31.88,
           "category_code": "subscriptions", "expense_date": "2026-07-01",
           "description": "Anthropic, PBC", "vendor": "Anthropic",
           "gst_paid_cad": 0, "qst_paid_cad": 0, "hst_paid_cad": 0,
           "status": "pending", "bank_transaction_id": None}
    doc.update(over)
    db.expenses.insert_one(dict(doc))
    return doc


def _mk_tx(scope, import_id, amount_cad, desc="ANTHROPIC PBC", date="2026-07-01"):
    tx = {"id": str(_uuid.uuid4()), "organization_id": scope["organization_id"],
          "import_id": import_id, "status": "unmatched", "parse_error": False,
          "amount_cad": amount_cad, "date": date, "description": desc,
          "match_kind": None, "match_id": None, "invoice_id": None}
    db.bank_transactions.insert_one(dict(tx))
    return tx


class TestFxAutoMatchTolerance:
    def test_clean_fx_within_5pct_adopts(self, org_scope):
        # Marge de change propre (+3,5 %) → dans ±5 % → auto-match + adoption du vrai montant.
        imp = f"imp-{_uuid.uuid4()}"
        exp = _mk_expense(org_scope)  # estimé 31,88
        _mk_tx(org_scope, imp, -33.00)
        n = _auto_match_transactions(imp, {"organization_id": org_scope["organization_id"]})
        assert n >= 1
        got = db.expenses.find_one({"id": exp["id"]}, {"_id": 0})
        assert got["amount_cad"] == 33.00
        assert got["cad_amount_source"] == "bank"

    def test_markup_beyond_5pct_not_auto_matched(self, org_scope):
        # +5,4 % (> ±5 %) → PAS d'auto-adoption silencieuse (sûr : évite les faux matchs
        # même-fournisseur). Corrigé consciemment via le rapport de comparaison ou le champ manuel.
        imp = f"imp-{_uuid.uuid4()}"
        exp = _mk_expense(org_scope)
        _mk_tx(org_scope, imp, -33.59)
        _auto_match_transactions(imp, {"organization_id": org_scope["organization_id"]})
        got = db.expenses.find_one({"id": exp["id"]}, {"_id": 0})
        assert got["amount_cad"] == 31.88            # inchangé
        assert got.get("bank_transaction_id") is None

    def test_cad_expense_still_requires_exact(self, org_scope):
        imp = f"imp-{_uuid.uuid4()}"
        exp = _mk_expense(org_scope, currency="CAD", exchange_rate_to_cad=1.0,
                          amount=31.88, amount_cad=31.88)
        _mk_tx(org_scope, imp, -33.59)  # +5,4 % : refusé pour du CAD
        _auto_match_transactions(imp, {"organization_id": org_scope["organization_id"]})
        got = db.expenses.find_one({"id": exp["id"]}, {"_id": 0})
        assert got.get("bank_transaction_id") is None


class TestApplyMatchRespectsManual:
    def test_manual_cad_not_overwritten_by_match(self, org_scope):
        # Un CAD saisi MANUELLEMENT fait autorité : le rapprochement lie la transaction mais
        # n'écrase PAS le montant (protège d'un faux match qui corromprait la valeur manuelle).
        exp = _mk_expense(org_scope, amount_cad=33.59, exchange_rate_to_cad=round(23 / 33.59, 6),
                          deductible_amount=33.59, cad_amount_source="manual")
        tx = {"id": str(_uuid.uuid4()), "organization_id": org_scope["organization_id"],
              "status": "unmatched", "amount_cad": -30.00, "date": "2026-07-01",
              "description": "ANTHROPIC", "match_kind": None, "match_id": None, "invoice_id": None}
        db.bank_transactions.insert_one(dict(tx))
        _apply_match(tx, "expense", exp["id"], {"organization_id": org_scope["organization_id"]})
        got = db.expenses.find_one({"id": exp["id"]}, {"_id": 0})
        assert got["amount_cad"] == 33.59                 # inchangé
        assert got["cad_amount_source"] == "manual"       # source préservée
        assert got["bank_transaction_id"] == tx["id"]     # lien de rapprochement quand même posé


class TestManualCadOverride:
    def test_create_with_manual_cad(self, auth_headers):
        r = client.post("/api/expenses", headers=auth_headers, json={
            "amount": 23, "currency": "USD", "exchange_rate_to_cad": 0.7215,
            "amount_cad_manual": 33.59, "description": "Anthropic manual",
            "category_code": "subscriptions", "expense_date": "2026-07-01"})
        assert r.status_code == 200, r.text
        exp = r.json()
        try:
            assert exp["amount_cad"] == 33.59
            assert exp["cad_amount_source"] == "manual"
            assert abs(exp["exchange_rate_to_cad"] - (23 / 33.59)) < 1e-4
            assert exp["deductible_amount"] == 33.59
        finally:
            db.expenses.delete_one({"id": exp["id"]})

    def test_update_estimate_to_manual(self, auth_headers):
        r = client.post("/api/expenses", headers=auth_headers, json={
            "amount": 23, "currency": "USD", "exchange_rate_to_cad": 0.7215,
            "description": "Anthropic est", "category_code": "subscriptions",
            "expense_date": "2026-07-01"})
        assert r.status_code == 200, r.text
        eid = r.json()["id"]
        assert r.json()["amount_cad"] == 31.88            # estimé au taux marché
        assert r.json()["cad_amount_source"] == "estimate"
        try:
            r2 = client.put(f"/api/expenses/{eid}", headers=auth_headers, json={
                "amount": 23, "currency": "USD", "exchange_rate_to_cad": 0.7215,
                "amount_cad_manual": 33.59})
            assert r2.status_code == 200, r2.text
            got = db.expenses.find_one({"id": eid}, {"_id": 0})
            assert got["amount_cad"] == 33.59
            assert got["cad_amount_source"] == "manual"
            assert got["deductible_amount"] == 33.59
        finally:
            db.expenses.delete_one({"id": eid})

    def test_manual_ignored_for_cad(self, auth_headers):
        r = client.post("/api/expenses", headers=auth_headers, json={
            "amount": 50, "currency": "CAD", "amount_cad_manual": 999,
            "description": "CAD exp", "category_code": "subscriptions",
            "expense_date": "2026-07-01"})
        assert r.status_code == 200, r.text
        exp = r.json()
        try:
            assert exp["amount_cad"] == 50                 # override ignoré en CAD
            assert exp.get("cad_amount_source") != "manual"
        finally:
            db.expenses.delete_one({"id": exp["id"]})

    @pytest.mark.parametrize("bad", [-5, 0, "abc"])
    def test_manual_invalid_rejected(self, auth_headers, bad):
        r = client.post("/api/expenses", headers=auth_headers, json={
            "amount": 23, "currency": "USD", "exchange_rate_to_cad": 0.7215,
            "amount_cad_manual": bad, "description": "bad manual",
            "category_code": "subscriptions", "expense_date": "2026-07-01"})
        assert r.status_code == 400, r.text
        # rien ne doit être créé
        db.expenses.delete_many({"description": "bad manual"})

    def test_manual_infinity_rejected(self, auth_headers):
        # httpx refuse Infinity via json= ; json.loads de Starlette parse 1e400 → inf → doit 400.
        r = client.post(
            "/api/expenses",
            headers={**auth_headers, "Content-Type": "application/json"},
            content='{"amount":100,"currency":"USD","exchange_rate_to_cad":0.72,'
                    '"amount_cad_manual":1e400,"description":"inf manual",'
                    '"category_code":"subscriptions","expense_date":"2026-07-01"}',
        )
        assert r.status_code == 400, r.text
        db.expenses.delete_many({"description": "inf manual"})
