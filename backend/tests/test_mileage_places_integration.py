"""Tests d'intégration HTTP — Lieux enregistrés du carnet (feature #13).

Adresses réutilisables (domicile, bureau, clients fréquents) pour pré-remplir
Départ/Arrivée en un clic. CRUD org-scopé, mirroir des favoris.

Même harnais que test_mileage_logbook_integration.py : TestClient FastAPI in-process
+ login du compte de seed exempté. Les lieux créés sont préfixés PLACE_TEST et
supprimés en `finally` (la DB locale est une copie-prod).
"""
import os
import sys
import uuid as _uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.server import app, db, migrate_mileage_logbook_v1  # noqa: E402

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _run_migration():
    migrate_mileage_logbook_v1()  # idempotente, additive (crée l'index mileage_places)
    yield


@pytest.fixture
def auth_headers():
    resp = client.post("/api/auth/login", json={
        "email": "gussdub@gmail.com", "password": "testpass123",
    })
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _cleanup(place_id):
    db.mileage_places.delete_one({"id": place_id})


class TestMileagePlaces:
    def test_create_requires_name(self, auth_headers):
        r = client.post("/api/mileage/places", headers=auth_headers, json={"address": "1 rue X"})
        assert r.status_code == 400

    def test_create_requires_address(self, auth_headers):
        r = client.post("/api/mileage/places", headers=auth_headers, json={"name": "Domicile"})
        assert r.status_code == 400

    def test_create_list_update_delete(self, auth_headers):
        r = client.post("/api/mileage/places", headers=auth_headers, json={
            "name": "PLACE_TEST Domicile",
            "address": "351 rue Jean-Louis Boudreau, J2H0A3, Granby",
        })
        assert r.status_code == 200, r.text
        place = r.json()
        pid = place["id"]
        try:
            assert place["name"] == "PLACE_TEST Domicile"
            assert place["address"].startswith("351 rue")
            assert "_id" not in place

            lst = client.get("/api/mileage/places", headers=auth_headers)
            assert lst.status_code == 200
            assert any(p["id"] == pid for p in lst.json())
            assert all("_id" not in p for p in lst.json())

            up = client.put(f"/api/mileage/places/{pid}", headers=auth_headers, json={
                "name": "PLACE_TEST Bureau", "address": "22 av. Test, Granby",
            })
            assert up.status_code == 200
            assert up.json()["name"] == "PLACE_TEST Bureau"
            assert up.json()["address"].startswith("22 av")

            dl = client.delete(f"/api/mileage/places/{pid}", headers=auth_headers)
            assert dl.status_code == 200

            lst2 = client.get("/api/mileage/places", headers=auth_headers)
            assert not any(p["id"] == pid for p in lst2.json())
        finally:
            _cleanup(pid)

    def test_name_and_address_trimmed_and_truncated(self, auth_headers):
        r = client.post("/api/mileage/places", headers=auth_headers, json={
            "name": "  PLACE_TEST " + "N" * 200, "address": "  1 rue " + "A" * 400 + "  ",
        })
        assert r.status_code == 200
        pid = r.json()["id"]
        try:
            assert len(r.json()["name"]) <= 80
            assert len(r.json()["address"]) <= 250
            assert not r.json()["address"].endswith(" ")   # trim
        finally:
            _cleanup(pid)

    def test_delete_unknown_returns_404(self, auth_headers):
        r = client.delete(f"/api/mileage/places/{_uuid.uuid4()}", headers=auth_headers)
        assert r.status_code == 404

    def test_update_unknown_returns_404(self, auth_headers):
        r = client.put(f"/api/mileage/places/{_uuid.uuid4()}", headers=auth_headers,
                       json={"name": "X", "address": "Y"})
        assert r.status_code == 404
