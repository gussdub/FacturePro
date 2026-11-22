"""Rapport TPS/TVQ : bornes de période tolérantes aux dates ISO datetime.

Régression : `_aggregate_sales_tax` filtrait `issue_date`/`expense_date` par un
`$gte/$lte` de CHAÎNES Mongo. Une facture émise le dernier jour de la période avec
le défaut serveur (`'2026-03-31T15:00:00+00:00'`) était exclue, car
`'2026-03-31T…' > '2026-03-31'` en tri lexical — alors que le grand livre la
poste à `entry_date='2026-03-31'`. Le rapport sous-comptait donc la TPS/TVQ par
rapport aux soldes 2100/2110 pour la même période.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "facturepro_test")

import pytest  # noqa: E402

mongomock = pytest.importorskip("mongomock")
import server as server_module  # noqa: E402

ORG = "TESTORG-ST-BOUNDS"
SCOPE = {"organization_id": ORG}


@pytest.fixture()
def fake_db(monkeypatch):
    db = mongomock.MongoClient()["t"]
    monkeypatch.setattr(server_module, "db", db)
    return db


def _invoice(db, issue_date, gst, qst, status="sent", **extra):
    doc = {
        "id": f"inv-{issue_date}-{status}", "organization_id": ORG,
        "status": status, "issue_date": issue_date, "currency": "CAD",
        "exchange_rate_to_cad": 1.0, "subtotal": 100.0,
        "gst_amount": gst, "pst_amount": qst, "hst_amount": 0.0,
        "province": "QC",
    }
    doc.update(extra)
    db.invoices.insert_one(doc)


def test_facture_iso_datetime_dernier_jour_incluse(fake_db):
    _invoice(fake_db, "2026-03-31T15:00:00+00:00", 5.00, 9.98)
    r = server_module._aggregate_sales_tax(SCOPE, "2026-01-01", "2026-03-31")
    assert r["invoice_count"] == 1
    assert r["summary"]["gst"]["collected"] == pytest.approx(5.00)
    assert r["summary"]["qst"]["collected"] == pytest.approx(9.98)


def test_bornes_inclusives_et_exclusion_hors_periode(fake_db):
    _invoice(fake_db, "2026-01-01", 1.0, 2.0)                       # 1er jour : inclus
    _invoice(fake_db, "2026-03-31T23:59:00", 1.0, 2.0)              # dernier jour : inclus
    _invoice(fake_db, "2026-04-01T00:30:00+00:00", 50.0, 99.0)      # hors période
    _invoice(fake_db, "2025-12-31T23:00:00", 50.0, 99.0)            # hors période
    _invoice(fake_db, "2026-02-10", 50.0, 99.0, status="draft")     # brouillon : exclu
    r = server_module._aggregate_sales_tax(SCOPE, "2026-01-01", "2026-03-31")
    assert r["invoice_count"] == 2
    assert r["summary"]["gst"]["collected"] == pytest.approx(2.0)
    assert r["summary"]["qst"]["collected"] == pytest.approx(4.0)


def test_depense_iso_datetime_dernier_jour_incluse(fake_db):
    fake_db.expenses.insert_one({
        "id": "exp-1", "organization_id": ORG, "category_code": "office_supplies",
        "amount_cad": 114.98, "currency": "CAD",
        "expense_date": "2026-03-31T18:00:00+00:00",
        "gst_paid_cad": 5.00, "qst_paid_cad": 9.98, "hst_paid_cad": 0.0,
    })
    r = server_module._aggregate_sales_tax(SCOPE, "2026-01-01", "2026-03-31")
    assert r["expense_count"] == 1
    assert r["summary"]["gst"]["paid"] == pytest.approx(5.00)
    assert r["summary"]["qst"]["paid"] == pytest.approx(9.98)
