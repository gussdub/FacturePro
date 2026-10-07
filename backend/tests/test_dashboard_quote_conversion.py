"""Taux de conversion soumissions → factures exposé par /api/dashboard/stats."""
import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))

import mongomock
import pytest
import server as server_module

ORG = "org-conv"
SCOPE = {"organization_id": ORG}


@pytest.fixture
def fake_db(monkeypatch):
    fake = mongomock.MongoClient().db
    monkeypatch.setattr(server_module, "db", fake)
    return fake


def _q(fake, status, client_id, org=ORG):
    fake.quotes.insert_one({"organization_id": org, "status": status, "client_id": client_id})


def test_taux_et_clients_convertis(fake_db):
    _q(fake_db, "converted", "A")
    _q(fake_db, "converted", "A")
    _q(fake_db, "converted", "B")
    _q(fake_db, "sent", "C")
    _q(fake_db, "pending", "C")
    _q(fake_db, "draft", "D")          # brouillon : hors dénominateur
    _q(fake_db, "converted", "Z", org="autre-org")  # autre org : ignorée
    r = server_module._quote_conversion_stats(SCOPE)
    assert r["quotes_converted"] == 3
    assert r["quote_conversion_rate"] == 60.0   # 3 / 5
    assert r["clients_converted"] == 2           # A, B (distincts)
    assert r["clients_quoted"] == 3              # A, B, C (D est en brouillon)


def test_aucune_soumission_pas_de_division_par_zero(fake_db):
    r = server_module._quote_conversion_stats(SCOPE)
    assert r == {"quotes_converted": 0, "quote_conversion_rate": 0.0,
                 "clients_converted": 0, "clients_quoted": 0}


def test_client_absent_non_compte(fake_db):
    _q(fake_db, "converted", None)
    _q(fake_db, "converted", "")
    r = server_module._quote_conversion_stats(SCOPE)
    assert r["quotes_converted"] == 2
    assert r["clients_converted"] == 0


def test_expose_par_dashboard_stats(fake_db):
    _q(fake_db, "converted", "A")
    _q(fake_db, "sent", "B")
    fake_db.quotes.insert_one({"user_id": "u-legacy", "status": "converted", "client_id": "L"})
    user = server_module.CurrentUser(id="u-legacy", email="x@y.z", organization_id=ORG,
                                     role="owner", permissions=["reports:read"])
    r = server_module.get_stats(current_user=user)
    assert r["total_quotes"] == 3
    assert r["quotes_converted"] == 2
    assert r["quote_conversion_rate"] == 66.7
    assert r["clients_converted"] == 2
