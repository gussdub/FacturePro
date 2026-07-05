"""Test — drill-down du P&L : détail des dépenses d'une catégorie.

Vérifie l'invariant clé : la somme du détail (GET /api/reports/pnl/expenses) est ÉGALE au
total « brut » de cette catégorie dans le P&L (GET /api/reports/pnl) sur la même période.
"""
import os
import sys
import uuid as _uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from backend.server import app, db  # noqa: E402

client = TestClient(app)


@pytest.fixture
def auth_headers():
    r = client.post("/api/auth/login", json={"email": "gussdub@gmail.com", "password": "testpass123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_drilldown_sums_to_category_total(auth_headers):
    ids = []
    for amt in (10.00, 20.50, 5.25):
        r = client.post("/api/expenses", headers=auth_headers, json={
            "amount": amt, "currency": "CAD", "category_code": "office_supplies",
            "description": "DRILLTEST", "expense_date": "2099-03-15",
        })
        assert r.status_code in (200, 201), r.text
        ids.append(r.json()["id"])
    try:
        d = client.get("/api/reports/pnl/expenses", headers=auth_headers, params={
            "start": "2099-03-01", "end": "2099-03-31", "category_code": "office_supplies"})
        assert d.status_code == 200, d.text
        data = d.json()
        # mes 3 dépenses de test sont présentes dans le détail
        assert set(ids).issubset({x["id"] for x in data["expenses"]})

        # le total du détail == la catégorie office_supplies du P&L sur la même période
        pnl = client.get("/api/reports/pnl", headers=auth_headers, params={
            "start": "2099-03-01", "end": "2099-03-31", "basis": "accrual", "compare": "none"}).json()
        cat_gross = None
        for g in pnl["expense_groups"]:
            for c in g["categories"]:
                if c["code"] == "office_supplies":
                    cat_gross = c["current"]["gross"]
        assert cat_gross is not None, "catégorie office_supplies absente du P&L"
        assert abs(data["total_gross"] - cat_gross) < 0.01
    finally:
        for i in ids:
            db.expenses.delete_one({"id": i})


def test_drilldown_excludes_other_period(auth_headers):
    # Une dépense hors période ne doit PAS apparaître.
    r = client.post("/api/expenses", headers=auth_headers, json={
        "amount": 99.0, "currency": "CAD", "category_code": "office_supplies",
        "description": "DRILLTEST-OUT", "expense_date": "2099-06-15",
    })
    eid = r.json()["id"]
    try:
        d = client.get("/api/reports/pnl/expenses", headers=auth_headers, params={
            "start": "2099-03-01", "end": "2099-03-31", "category_code": "office_supplies"}).json()
        assert eid not in {x["id"] for x in d["expenses"]}
    finally:
        db.expenses.delete_one({"id": eid})
