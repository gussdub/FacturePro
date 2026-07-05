"""Tests d'intégration — CRUD véhicules du carnet (feature #13).

Ajoute/modifie/supprime un véhicule + choix du véhicule par défaut. Même harnais que
test_mileage_places_integration.py (TestClient in-process + login du compte de seed).
Les véhicules de test sont préfixés TESTVEH et nettoyés ; le véhicule par défaut d'origine
est restauré après les tests qui le déplacent.
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
    migrate_mileage_logbook_v1()
    yield


@pytest.fixture
def auth_headers():
    r = client.post("/api/auth/login", json={"email": "gussdub@gmail.com", "password": "testpass123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


class TestMileageVehicles:
    def test_create_requires_name(self, auth_headers):
        r = client.post("/api/mileage/vehicles", headers=auth_headers, json={"make_model": "x"})
        assert r.status_code == 400

    def test_create_update_delete(self, auth_headers):
        r = client.post("/api/mileage/vehicles", headers=auth_headers,
                        json={"name": "TESTVEH Honda", "make_model": "Civic 2022", "plate": "ABC 123"})
        assert r.status_code == 200, r.text
        v = r.json()
        vid = v["id"]
        try:
            assert v["name"] == "TESTVEH Honda"
            assert v["is_default"] is False and v["is_active"] is True
            assert any(x["id"] == vid for x in client.get("/api/mileage/vehicles", headers=auth_headers).json())

            up = client.put(f"/api/mileage/vehicles/{vid}", headers=auth_headers,
                            json={"name": "TESTVEH Toyota", "make_model": "Corolla", "plate": "XYZ 789"})
            assert up.status_code == 200 and up.json()["name"] == "TESTVEH Toyota"
            assert up.json()["plate"] == "XYZ 789"

            dl = client.delete(f"/api/mileage/vehicles/{vid}", headers=auth_headers)
            assert dl.status_code == 200
            assert not any(x["id"] == vid for x in client.get("/api/mileage/vehicles", headers=auth_headers).json())
        finally:
            db.mileage_vehicles.delete_one({"id": vid})

    def test_set_default_keeps_single_default(self, auth_headers):
        orig = client.get("/api/mileage/vehicles", headers=auth_headers).json()
        orig_default = next((x["id"] for x in orig if x.get("is_default")), None)
        vid = client.post("/api/mileage/vehicles", headers=auth_headers,
                          json={"name": "TESTVEH Défaut"}).json()["id"]
        try:
            sd = client.post(f"/api/mileage/vehicles/{vid}/set-default", headers=auth_headers)
            assert sd.status_code == 200 and sd.json()["is_default"] is True
            lst = client.get("/api/mileage/vehicles", headers=auth_headers).json()
            assert sum(1 for x in lst if x.get("is_default")) == 1   # un seul défaut
            assert next(x for x in lst if x["id"] == vid)["is_default"] is True
        finally:
            # restaure le défaut d'origine puis supprime le véhicule de test
            if orig_default:
                client.post(f"/api/mileage/vehicles/{orig_default}/set-default", headers=auth_headers)
            db.mileage_vehicles.delete_one({"id": vid})

    def test_delete_unknown_404(self, auth_headers):
        r = client.delete(f"/api/mileage/vehicles/{_uuid.uuid4()}", headers=auth_headers)
        assert r.status_code == 404
