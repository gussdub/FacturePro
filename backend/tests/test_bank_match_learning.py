"""Tests — mémoire d'apprentissage des rapprochements (feature #7.3).

Après un rapprochement MANUEL (relevé sans mot commun avec le nom de la dépense), le système
mémorise l'association et auto-rapproche les futures occurrences (mêmes garde-fous montant/date).
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
    r = client.post("/api/expenses", headers=auth_headers, json={
        "amount": amount, "currency": "CAD", "category_code": "office_supplies",
        "description": name, "expense_date": date})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _import(auth_headers, csv, label):
    r = client.post("/api/bank/imports", headers=auth_headers,
                    files={"file": ("r.csv", csv, "text/csv")},
                    data={"mapping": json.dumps(MAP), "bank_label": label})
    return r.json()


# ─────────────────────────── UNITAIRE ───────────────────────────

def test_alias_bridges_and_record_skip():
    from backend.server import _alias_bridges, _significant_tokens
    aliases = [{"bank_tokens": ["coffee", "shop"], "vendor_tokens": ["boulangerie", "coin"]}]
    assert _alias_bridges(_significant_tokens("SQ COFFEE SHOP"),
                          _significant_tokens("Ma Boulangerie du Coin"), aliases) is True
    # tokens qui ne recoupent pas l'alias
    assert _alias_bridges(_significant_tokens("AMAZON"),
                          _significant_tokens("Netflix"), aliases) is False
    # pas d'alias -> False
    assert _alias_bridges(_significant_tokens("SQ COFFEE"), _significant_tokens("X"), []) is False


# ─────────────────────────── INTÉGRATION ───────────────────────────

def test_learning_bridges_after_manual_match(auth_headers):
    e1 = _make_expense(auth_headers, 50.00, "Ma Boulangerie du Coin", "2099-05-01")
    imp1 = imp2 = e2 = None
    try:
        # 1) tx sans aucun token commun avec le nom -> pas d'auto-match
        d1 = _import(auth_headers, "Date,Description,Montant\n2099-05-01,SQ COFFEE SHOP,-50.00\n", "L1")
        imp1 = d1["import"]["id"]
        assert d1["auto_matched"] == 0, "aucun token commun -> pas d'auto-match au 1er passage"
        tx1 = d1["transactions"][0]

        # 2) rapprochement MANUEL -> apprend l'alias
        m = client.post(f"/api/bank/transactions/{tx1['id']}/match", headers=auth_headers,
                        json={"kind": "expense", "target_id": e1})
        assert m.status_code == 200, m.text

        # 3) nouvelle dépense (même fournisseur, mois suivant) + nouvelle tx même description
        e2 = _make_expense(auth_headers, 50.00, "Ma Boulangerie du Coin", "2099-06-01")
        d2 = _import(auth_headers, "Date,Description,Montant\n2099-06-01,SQ COFFEE SHOP,-50.00\n", "L2")
        imp2 = d2["import"]["id"]
        assert d2["auto_matched"] >= 1, "l'alias appris devrait auto-rapprocher la récurrence"
        assert d2["transactions"][0]["match_id"] == e2
    finally:
        for imp in (imp1, imp2):
            if imp:
                client.delete(f"/api/bank/imports/{imp}?force=true", headers=auth_headers)
        db.expenses.delete_one({"id": e1})
        if e2:
            db.expenses.delete_one({"id": e2})
        db.bank_match_aliases.delete_many({"bank_tokens": ["coffee", "shop"]})


def test_learning_still_gated_by_amount(auth_headers):
    # L'alias débloque le NOM, pas le montant : une récurrence au montant CAD décalé ne matche pas.
    e1 = _make_expense(auth_headers, 50.00, "Ma Boulangerie du Coin", "2099-05-01")
    imp1 = imp2 = e2 = None
    try:
        d1 = _import(auth_headers, "Date,Description,Montant\n2099-05-01,SQ COFFEE SHOP,-50.00\n", "G1")
        imp1 = d1["import"]["id"]
        tx1 = d1["transactions"][0]
        client.post(f"/api/bank/transactions/{tx1['id']}/match", headers=auth_headers,
                    json={"kind": "expense", "target_id": e1})
        # dépense CAD au montant décalé (55,00) + tx 50,00 : alias OK mais montant CAD non exact -> non
        e2 = _make_expense(auth_headers, 55.00, "Ma Boulangerie du Coin", "2099-06-01")
        d2 = _import(auth_headers, "Date,Description,Montant\n2099-06-01,SQ COFFEE SHOP,-50.00\n", "G2")
        imp2 = d2["import"]["id"]
        assert d2["auto_matched"] == 0, "alias ne doit pas outrepasser la règle de montant CAD exact"
    finally:
        for imp in (imp1, imp2):
            if imp:
                client.delete(f"/api/bank/imports/{imp}?force=true", headers=auth_headers)
        db.expenses.delete_one({"id": e1})
        if e2:
            db.expenses.delete_one({"id": e2})
        db.bank_match_aliases.delete_many({"bank_tokens": ["coffee", "shop"]})
