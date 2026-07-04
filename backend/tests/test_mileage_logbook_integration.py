"""Tests d'intégration HTTP — Carnet de route (kilométrage), feature #13.

Task 4 : migration idempotente + seed lazy du véhicule par défaut + org-scoping.

Utilise le TestClient FastAPI (comme test_general_ledger_integration.py) : le
module server.py se connecte à Mongo au chargement, donc DB_NAME doit exister
avant l'import et le paquet `backend` doit être importable depuis la racine.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.server import (  # noqa: E402
    app, db, _mileage_rate_for_year, migrate_mileage_logbook_v1,
)

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _run_mileage_migration():
    """Garantit que la migration du carnet de route a tourné avant les tests.

    En prod la migration s'exécute au startup FastAPI. Ici on l'appelle
    directement (elle est idempotente et purement additive : ne crée que des
    index de collections neuves) plutôt que de dépendre du handler `startup`,
    car ce dernier peut avorter sur un conflit d'index PRÉEXISTANT et sans
    rapport dans la copie-prod locale (ex : `company_settings.user_id` non-unique
    vs `create_index(unique=True)`), ce qui empêcherait toute migration ultérieure
    de tourner. Appeler la migration ciblée rend le test déterministe et fidèle à
    son intention (« la migration crée bien les index attendus »)."""
    migrate_mileage_logbook_v1()
    yield


@pytest.fixture
def auth_headers():
    # Réutilise le compte de seed exempté (voir CLAUDE.md).
    resp = client.post("/api/auth/login", json={
        "email": "gussdub@gmail.com", "password": "testpass123",
    })
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_migration_creates_indexes():
    # La migration a tourné au startup ; les collections existent et sont indexées.
    names = [ix["name"] for ix in db.mileage_trips.list_indexes()]
    assert any("organization_id" in n and "trip_date" in n for n in names)
    reminder_info = db.mileage_rate_reminders.index_information()
    assert any(reminder_info[n].get("unique") for n in reminder_info)


def test_lazy_default_vehicle_created_once(auth_headers):
    # 1er GET seed le véhicule par défaut ; 2e appel ne crée pas de doublon.
    r1 = client.get("/api/mileage/vehicles", headers=auth_headers)
    assert r1.status_code == 200, r1.text
    defaults = [v for v in r1.json() if v["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["name"] == "Véhicule principal"

    r2 = client.get("/api/mileage/vehicles", headers=auth_headers)
    assert len([v for v in r2.json() if v["is_default"]]) == 1


def test_default_vehicle_scoped_to_org(auth_headers):
    # Le véhicule par défaut porte bien l'organization_id du user courant.
    org = client.get("/api/org/me", headers=auth_headers)
    assert org.status_code == 200, org.text
    org_id = org.json()["organization"]["id"]

    r = client.get("/api/mileage/vehicles", headers=auth_headers)
    assert r.status_code == 200, r.text
    # Endpoint filtré par org : le véhicule par défaut appartient à l'org du user.
    default = next(v for v in r.json() if v["is_default"])
    assert "_id" not in default  # projection Mongo interne masquée
    # organization_id n'est pas renvoyé au client sur cet endpoint ; on vérifie
    # côté DB que le doc est bien scopé à l'org courante.
    doc = db.mileage_vehicles.find_one({"id": default["id"]})
    assert doc is not None
    assert doc["organization_id"] == org_id


def test_create_vehicle_requires_name(auth_headers):
    r = client.post("/api/mileage/vehicles", headers=auth_headers, json={})
    assert r.status_code == 400, r.text


def test_create_and_list_vehicle(auth_headers):
    created = client.post("/api/mileage/vehicles", headers=auth_headers, json={
        "name": "Camion T4 test", "make_model": "Ford F-150", "plate": "ABC123",
    })
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["name"] == "Camion T4 test"
    assert body["make_model"] == "Ford F-150"
    assert body["is_default"] is False
    assert "_id" not in body

    listing = client.get("/api/mileage/vehicles", headers=auth_headers)
    ids = [v["id"] for v in listing.json()]
    assert body["id"] in ids

    # Nettoyage : ne pas laisser traîner de véhicule non-défaut dans le seed org.
    db.mileage_vehicles.delete_one({"id": body["id"]})
