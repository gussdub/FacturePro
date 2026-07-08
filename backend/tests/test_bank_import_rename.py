"""Test — PATCH /api/bank/imports/{id} renomme le libellé d'un import."""
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
    r = client.post("/api/auth/login",
                    json={"email": "gussdub@gmail.com", "password": "testpass123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _create_import(auth_headers, label):
    csv = "Date,Description,Montant\n2099-01-05,DEPOT TEST,10.00\n"
    r = client.post("/api/bank/imports", headers=auth_headers,
                    files={"file": ("r.csv", csv, "text/csv")},
                    data={"mapping": json.dumps(MAP), "bank_label": label})
    assert r.status_code in (200, 201), r.text
    return r.json()["import"]["id"]


def test_rename_import_updates_label(auth_headers):
    imp_id = _create_import(auth_headers, "Relevé Compte courant")
    try:
        r = client.patch(f"/api/bank/imports/{imp_id}", headers=auth_headers,
                         json={"bank_label": "Compte courant — Avril 2026"})
        assert r.status_code == 200, r.text
        assert r.json()["bank_label"] == "Compte courant — Avril 2026"
        # Vérifier persistance
        doc = db.bank_imports.find_one({"id": imp_id}, {"_id": 0})
        assert doc["bank_label"] == "Compte courant — Avril 2026"
    finally:
        client.delete(f"/api/bank/imports/{imp_id}?force=true", headers=auth_headers)


def test_rename_import_rejects_empty_label(auth_headers):
    imp_id = _create_import(auth_headers, "Relevé test")
    try:
        r = client.patch(f"/api/bank/imports/{imp_id}", headers=auth_headers,
                         json={"bank_label": "   "})
        assert r.status_code == 422
    finally:
        client.delete(f"/api/bank/imports/{imp_id}?force=true", headers=auth_headers)


def test_rename_import_rejects_too_long_label(auth_headers):
    imp_id = _create_import(auth_headers, "Relevé test")
    try:
        r = client.patch(f"/api/bank/imports/{imp_id}", headers=auth_headers,
                         json={"bank_label": "x" * 200})
        assert r.status_code == 422
    finally:
        client.delete(f"/api/bank/imports/{imp_id}?force=true", headers=auth_headers)


def test_rename_import_404_on_unknown(auth_headers):
    r = client.patch("/api/bank/imports/does-not-exist-999", headers=auth_headers,
                     json={"bank_label": "X"})
    assert r.status_code == 404
