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


# ─── [CALCUL] Calcul d'allocation exercé de bout en bout via HTTP ───
#
# Ces tests répondent aux 4 problèmes [CALCUL] du FIX-PASS T4 : les helpers de
# calcul (corrects, 21 tests unitaires verts) étaient PROUVÉS au niveau primitive
# seulement — aucun endpoint ne les appelait. On exerce désormais le calcul via
# POST/GET /api/mileage/trips (allocation, split au seuil 5000 km, cumul YTD) et
# l'ENFORCEMENT du contrat « année sans taux → montant jamais deviné ».


def _dedicated_vehicle(auth_headers, name):
    """Crée un véhicule dédié à un test pour repartir d'un cumul YTD = 0
    (le cumul est par personne+véhicule+année)."""
    r = client.post("/api/mileage/vehicles", headers=auth_headers, json={"name": name})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _cleanup_vehicle(vehicle_id):
    db.mileage_trips.delete_many({"vehicle_id": vehicle_id})
    db.mileage_vehicles.delete_one({"id": vehicle_id})


def _new_trip_payload(vehicle_id, **over):
    base = {
        "trip_date": "2026-03-10",
        "origin": "Domicile, Québec",
        "destination": "Client ABC, Lévis",
        "purpose": "Rencontre client",
        "one_way_km": 45.0,
        "round_trip": True,
        "vehicle_id": vehicle_id,
    }
    base.update(over)
    return base


def test_create_trip_requires_purpose(auth_headers):
    # Problème [CALCUL] #4 (conformité ARC) : le motif est OBLIGATOIRE côté serveur.
    vid = _dedicated_vehicle(auth_headers, "CALCUL purpose")
    try:
        r = client.post("/api/mileage/trips",
                        json=_new_trip_payload(vid, purpose="   "), headers=auth_headers)
        assert r.status_code == 400, r.text
        assert "motif" in r.json()["detail"].lower()
    finally:
        _cleanup_vehicle(vid)


def test_create_trip_requires_positive_km(auth_headers):
    vid = _dedicated_vehicle(auth_headers, "CALCUL km")
    try:
        r = client.post("/api/mileage/trips",
                        json=_new_trip_payload(vid, one_way_km=0), headers=auth_headers)
        assert r.status_code == 400, r.text
    finally:
        _cleanup_vehicle(vid)


def test_create_trip_round_trip_doubles_and_allocates(auth_headers):
    # Problème [CALCUL] #1 : allocation = km × taux, exercée via HTTP réel.
    vid = _dedicated_vehicle(auth_headers, "CALCUL AR")
    try:
        r = client.post("/api/mileage/trips",
                        json=_new_trip_payload(vid, one_way_km=45, round_trip=True),
                        headers=auth_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["trip"]["distance_km"] == 90.0  # aller-retour doublé backend
        # 2026, sous 5000 km : 90 × 0,73 = 65,70
        assert body["allocation"]["amount_cad"] == round(90 * 0.73, 2)
        assert body["allocation"]["breakdown"]["km_full"] == 90.0
        assert body["allocation"]["breakdown"]["km_reduced"] == 0.0
    finally:
        _cleanup_vehicle(vid)


def test_create_trip_ignores_client_supplied_distance(auth_headers):
    # Sécurité : distance_km recalculée backend, valeur client ignorée.
    vid = _dedicated_vehicle(auth_headers, "CALCUL distance")
    try:
        r = client.post("/api/mileage/trips",
                        json=_new_trip_payload(vid, one_way_km=10, round_trip=False,
                                               distance_km=9999),
                        headers=auth_headers)
        assert r.status_code == 200, r.text
        assert r.json()["trip"]["distance_km"] == 10.0
    finally:
        _cleanup_vehicle(vid)


def test_switch_5000km_split_end_to_end(auth_headers):
    # Problème [CALCUL] #1 & #3 : le split au seuil 5000 km, prouvé en unitaire,
    # est désormais exercé DANS UN FLUX HTTP réel (création + cumul YTD DB).
    vid = _dedicated_vehicle(auth_headers, "CALCUL bascule")
    try:
        # 49 trajets de 100 km (aller simple) = 4900 km cumulés
        for i in range(49):
            rc = client.post("/api/mileage/trips",
                             json=_new_trip_payload(vid, trip_date=f"2026-01-{(i % 28) + 1:02d}",
                                                    one_way_km=100, round_trip=False),
                             headers=auth_headers)
            assert rc.status_code == 200, rc.text
        # Trajet qui franchit le seuil : ytd 4900 + 200 → 100@0,73 + 100@0,67 = 140,00
        crossing = client.post("/api/mileage/trips",
                               json=_new_trip_payload(vid, trip_date="2026-06-15",
                                                      one_way_km=200, round_trip=False),
                               headers=auth_headers)
        assert crossing.status_code == 200, crossing.text
        cb = crossing.json()
        assert cb["allocation"]["amount_cad"] == 140.00
        assert cb["allocation"]["breakdown"]["km_full"] == 100.0
        assert cb["allocation"]["breakdown"]["km_reduced"] == 100.0
        assert cb["ytd_before"] == 4900.0
        assert cb["running_total_km"] == 5100.0  # cumul ARC affiché après ce trajet
        # Trajet suivant : tout au taux réduit
        after = client.post("/api/mileage/trips",
                            json=_new_trip_payload(vid, trip_date="2026-07-01",
                                                   one_way_km=100, round_trip=False),
                            headers=auth_headers)
        assert after.status_code == 200, after.text
        assert after.json()["allocation"]["amount_cad"] == round(100 * 0.67, 2)
    finally:
        _cleanup_vehicle(vid)


def test_list_trips_enriched_and_ordered(auth_headers):
    # Problème [CALCUL] #4 : le carnet expose date/départ/arrivée/motif/km + cumul.
    vid = _dedicated_vehicle(auth_headers, "CALCUL liste")
    try:
        client.post("/api/mileage/trips",
                    json=_new_trip_payload(vid, trip_date="2026-04-15", one_way_km=20,
                                           round_trip=False),
                    headers=auth_headers)
        client.post("/api/mileage/trips",
                    json=_new_trip_payload(vid, trip_date="2026-04-02", one_way_km=10,
                                           round_trip=False),
                    headers=auth_headers)
        r = client.get(f"/api/mileage/trips?year=2026&month=4&vehicle_id={vid}",
                       headers=auth_headers)
        assert r.status_code == 200, r.text
        rows = r.json()
        assert len(rows) == 2
        # trié (trip_date, id) : le 02 avant le 15
        assert rows[0]["trip"]["trip_date"] == "2026-04-02"
        assert rows[1]["trip"]["trip_date"] == "2026-04-15"
        # cumul progressif ARC
        assert rows[0]["running_total_km"] == 10.0
        assert rows[1]["ytd_before"] == 10.0
        assert rows[1]["running_total_km"] == 30.0
        # champs ARC obligatoires présents
        for row in rows:
            t = row["trip"]
            for field in ("trip_date", "origin", "destination", "purpose", "distance_km"):
                assert field in t
    finally:
        _cleanup_vehicle(vid)


def test_missing_rate_year_blocks_allocation_and_flags_reminder(auth_headers):
    # Problème [CALCUL] #2 : une année sans taux ne calcule JAMAIS silencieusement
    # un montant erroné, ET la collection mileage_rate_reminders est réellement
    # écrite (enforcement end-to-end, plus seulement au niveau helper).
    vid = _dedicated_vehicle(auth_headers, "CALCUL sans taux")
    org = client.get("/api/org/me", headers=auth_headers).json()
    org_id = org["organization"]["id"]
    reminder_id = f"{org_id}:2099"
    db.mileage_rate_reminders.delete_one({"id": reminder_id})  # état propre
    try:
        r = client.post("/api/mileage/trips",
                        json=_new_trip_payload(vid, trip_date="2099-05-01",
                                               one_way_km=10, round_trip=False),
                        headers=auth_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        # aucun montant deviné
        assert body["allocation"] is None
        assert body["rate_missing_year"] == 2099
        # cumul km toujours tenu (le carnet reste utilisable), seule l'allocation $ attend
        assert body["running_total_km"] == 10.0
        # la collection de rappel est désormais alimentée (n'était jamais écrite)
        rem = db.mileage_rate_reminders.find_one({"id": reminder_id})
        assert rem is not None
        assert rem["year"] == 2099
        assert rem["organization_id"] == org_id
    finally:
        db.mileage_rate_reminders.delete_one({"id": reminder_id})
        _cleanup_vehicle(vid)


def test_trip_cross_org_isolation(auth_headers):
    # Un trajet créé par l'org courante n'est pas accessible par id sans le scope.
    # (isolation garantie par _org_scope ; ici on vérifie le 404 hors org via un
    # id inexistant, l'isolation cross-org complète est couverte au Task 9.)
    vid = _dedicated_vehicle(auth_headers, "CALCUL iso")
    try:
        created = client.post("/api/mileage/trips",
                              json=_new_trip_payload(vid), headers=auth_headers)
        tid = created.json()["trip"]["id"]
        # le même user (même org) y accède
        assert client.get(f"/api/mileage/trips/{tid}", headers=auth_headers).status_code == 200
        # un id inconnu → 404
        assert client.get("/api/mileage/trips/does-not-exist", headers=auth_headers).status_code == 404
    finally:
        _cleanup_vehicle(vid)
