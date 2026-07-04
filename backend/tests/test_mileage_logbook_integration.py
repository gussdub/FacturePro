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


@pytest.mark.parametrize("bad_date", [
    "abcd-ef-gh",   # 10 char, préfixe non numérique
    "XXXXXXXXXX",   # 10 char, aucun tiret
    "2026/13/99",   # 10 char, mauvais séparateur + valeurs hors plage
    "2026-13-99",   # 10 char, format ok mais mois/jour hors calendrier
    "2026-02-30",   # 10 char, jour inexistant (février)
    "2026-1-5",     # trop court
    "",             # vide
])
def test_create_trip_rejects_invalid_date_before_insert(auth_headers, bad_date):
    # Fix T4 [CALCUL] : le contrat « date pure AAAA-MM-JJ calendaire » est ENFORCÉ
    # avant l'insert (strptime), pas un simple len()==10. Une date non calendaire
    # doit renvoyer 400 SANS persister d'orphelin qui ferait ensuite lever 500
    # _mileage_enrich_trip (int(trip_date[:4])) et empoisonnerait la liste.
    vid = _dedicated_vehicle(auth_headers, f"CALCUL date {bad_date!r}")
    try:
        r = client.post("/api/mileage/trips",
                        json=_new_trip_payload(vid, trip_date=bad_date),
                        headers=auth_headers)
        assert r.status_code == 400, r.text
        # aucun document orphelin n'a été inséré
        assert db.mileage_trips.count_documents({"vehicle_id": vid}) == 0
        # et la liste NON filtrée reste accessible (pas de 500 permanent)
        lst = client.get("/api/mileage/trips", headers=auth_headers)
        assert lst.status_code == 200, lst.text
    finally:
        _cleanup_vehicle(vid)


def test_create_trip_accepts_valid_calendar_date(auth_headers):
    # Complément du fix : une vraie date calendaire limite (29 fév. bissextile) passe.
    # 2028 (année bissextile) n'a pas de taux ARC configuré -> l'enrichissement
    # flague un mileage_rate_reminders '{org}:2028' ; on le nettoie en finally pour
    # ne pas salir le seed org (instruction « ne pas polluer l'org de seed »).
    vid = _dedicated_vehicle(auth_headers, "CALCUL date ok")
    org_id = client.get("/api/org/me", headers=auth_headers).json()["organization"]["id"]
    try:
        r = client.post("/api/mileage/trips",
                        json=_new_trip_payload(vid, trip_date="2028-02-29"),
                        headers=auth_headers)
        assert r.status_code == 200, r.text
        assert r.json()["trip"]["trip_date"] == "2028-02-29"
        # la liste non filtrée se recharge sans 500
        lst = client.get("/api/mileage/trips", headers=auth_headers)
        assert lst.status_code == 200, lst.text
    finally:
        db.mileage_rate_reminders.delete_one({"id": f"{org_id}:2028"})
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


def test_create_trip_rejects_unknown_favorite(auth_headers):
    # Fix T5 [SPEC] : favorite_id est validé appartenir à l'org avant l'insert
    # (plan T5 Step 3). Un id fantôme (ou d'une autre org) → 400 « Favori
    # introuvable », et AUCUN trajet n'est persisté avec une référence croisée.
    vid = _dedicated_vehicle(auth_headers, "T5 favori fantome")
    try:
        r = client.post("/api/mileage/trips",
                        json=_new_trip_payload(vid, favorite_id="does-not-exist"),
                        headers=auth_headers)
        assert r.status_code == 400, r.text
        assert "favori" in r.json()["detail"].lower()
        # aucun orphelin persisté malgré le favorite_id invalide
        assert db.mileage_trips.count_documents({"vehicle_id": vid}) == 0
    finally:
        _cleanup_vehicle(vid)


def test_create_trip_accepts_valid_favorite(auth_headers):
    # Complément du fix : un favorite_id RÉEL de l'org est accepté et tracé sur le
    # trajet. Les endpoints favoris arrivant au Task 7, on insère le doc favori
    # directement (scopé à l'org courante) pour exercer la validation dès T5.
    vid = _dedicated_vehicle(auth_headers, "T5 favori valide")
    org_id = client.get("/api/org/me", headers=auth_headers).json()["organization"]["id"]
    fid = "test-fav-" + org_id
    db.mileage_favorites.insert_one({
        "id": fid,
        "organization_id": org_id,
        "created_by_user_id": "seed",
        "label": "Domicile → Client ABC",
        "origin": "Domicile",
        "destination": "Client ABC, Lévis",
        "purpose": "Rencontre",
        "one_way_km": 45.0,
        "round_trip_default": True,
        "created_at": "2026-01-01T00:00:00+00:00",
    })
    try:
        r = client.post("/api/mileage/trips",
                        json=_new_trip_payload(vid, favorite_id=fid),
                        headers=auth_headers)
        assert r.status_code == 200, r.text
        assert r.json()["trip"]["favorite_id"] == fid
    finally:
        db.mileage_favorites.delete_one({"id": fid})
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


# ─── Task 6 : GET/PUT/DELETE trajets + cumul YTD de bout en bout (bascule 5000 km) ───
#
# Le GET liste et le GET par id existent depuis le T4 ; le T6 ajoute PUT/DELETE et
# PROUVE le CRUD complet + la bascule 5000 km recalculée à la volée après chaque
# mutation. On respecte la discipline d'isolation du fichier : chaque test utilise
# un véhicule DÉDIÉ (cumul YTD par personne+véhicule+année → part de 0) et nettoie
# en `finally` (jamais de trajet laissé dans le seed org).


def _create_trip(auth_headers, vid, **over):
    """Crée un trajet sur le véhicule dédié `vid` et renvoie la réponse enrichie."""
    r = client.post("/api/mileage/trips", json=_new_trip_payload(vid, **over),
                    headers=auth_headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_list_trips_filtered_and_enriched(auth_headers):
    vid = _dedicated_vehicle(auth_headers, "T6 liste enrichie")
    try:
        _create_trip(auth_headers, vid, trip_date="2026-04-01", one_way_km=10,
                     round_trip=False)
        r = client.get(f"/api/mileage/trips?year=2026&month=4&vehicle_id={vid}",
                       headers=auth_headers)
        assert r.status_code == 200, r.text
        rows = r.json()
        assert rows, "au moins un trajet d'avril 2026 attendu"
        assert all(row["trip"]["trip_date"].startswith("2026-04") for row in rows)
        assert "allocation" in rows[0] and "ytd_before" in rows[0]
    finally:
        _cleanup_vehicle(vid)


def test_edit_trip_recalculates_distance(auth_headers):
    vid = _dedicated_vehicle(auth_headers, "T6 edit distance")
    try:
        created = _create_trip(auth_headers, vid, one_way_km=20, round_trip=False)
        tid = created["trip"]["id"]
        assert created["trip"]["distance_km"] == 20.0  # aller simple à la création
        # Passage en aller-retour : distance recalculée backend (valeur figée ignorée).
        r = client.put(f"/api/mileage/trips/{tid}",
                       json=_new_trip_payload(vid, one_way_km=20, round_trip=True),
                       headers=auth_headers)
        assert r.status_code == 200, r.text
        assert r.json()["trip"]["distance_km"] == 40.0
        # L'allocation suit la nouvelle distance (2026, sous 5000 km : 40 × 0,73).
        assert r.json()["allocation"]["amount_cad"] == round(40 * 0.73, 2)
    finally:
        _cleanup_vehicle(vid)


def test_edit_trip_requires_purpose(auth_headers):
    # Invariant ARC préservé au PUT : le motif reste obligatoire (400 si vide).
    vid = _dedicated_vehicle(auth_headers, "T6 edit motif")
    try:
        created = _create_trip(auth_headers, vid, one_way_km=10, round_trip=False)
        tid = created["trip"]["id"]
        r = client.put(f"/api/mileage/trips/{tid}",
                       json=_new_trip_payload(vid, purpose="   "),
                       headers=auth_headers)
        assert r.status_code == 400, r.text
        assert "motif" in r.json()["detail"].lower()
    finally:
        _cleanup_vehicle(vid)


def test_edit_unknown_trip_returns_404(auth_headers):
    r = client.put("/api/mileage/trips/does-not-exist",
                   json={"purpose": "x", "one_way_km": 5}, headers=auth_headers)
    assert r.status_code == 404, r.text


def test_switch_5000km_end_to_end_after_edit(auth_headers):
    # Bascule 5000 km recalculée à la volée : le split au seuil est correct même
    # sur le trajet à cheval, ET le trajet suivant bascule entièrement au taux réduit.
    vid = _dedicated_vehicle(auth_headers, "T6 bascule CRUD")
    try:
        # 49 trajets de 100 km (aller simple) = 4900 km cumulés
        for i in range(49):
            _create_trip(auth_headers, vid, trip_date=f"2026-01-{(i % 28) + 1:02d}",
                         one_way_km=100, round_trip=False)
        # Trajet qui franchit le seuil : ytd 4900 + 200 → 100@0,73 + 100@0,67 = 140,00
        crossing = _create_trip(auth_headers, vid, trip_date="2026-06-15",
                                one_way_km=200, round_trip=False)
        assert crossing["allocation"]["amount_cad"] == 140.00
        assert crossing["allocation"]["breakdown"]["km_full"] == 100.0
        assert crossing["allocation"]["breakdown"]["km_reduced"] == 100.0
        # Trajet suivant : tout au taux réduit
        after = _create_trip(auth_headers, vid, trip_date="2026-07-01",
                             one_way_km=100, round_trip=False)
        assert after["allocation"]["amount_cad"] == round(100 * 0.67, 2)
        # Le GET par id re-calcule identiquement le trajet à cheval (split stable).
        tid = crossing["trip"]["id"]
        got = client.get(f"/api/mileage/trips/{tid}", headers=auth_headers)
        assert got.status_code == 200, got.text
        assert got.json()["allocation"]["amount_cad"] == 140.00
        assert got.json()["running_total_km"] == 5100.0  # cumul ARC après ce trajet
    finally:
        _cleanup_vehicle(vid)


def test_edit_trip_to_missing_rate_year_blocks_allocation(auth_headers):
    # Problème [CALCUL] #2 (couverture) : éditer un trajet VERS une année sans taux
    # (PUT trip_date 2027-*, absente de MILEAGE_RATES) doit re-dériver allocation=None
    # + rate_missing_year — JAMAIS un montant deviné à partir de l'ancien taux 2026.
    # Le chemin est mutualisé avec la création via _mileage_enrich_trip (prouvé à la
    # POST), mais l'invariant « edit → année absente → allocation None » n'était pas
    # vérifié explicitement au PUT. On le prouve ici de bout en bout via HTTP, en
    # nettoyant le rappel écrit pour ne pas salir le seed org.
    vid = _dedicated_vehicle(auth_headers, "T6 edit vers annee sans taux")
    org_id = client.get("/api/org/me", headers=auth_headers).json()["organization"]["id"]
    reminder_id = f"{org_id}:2027"
    db.mileage_rate_reminders.delete_one({"id": reminder_id})  # état propre
    try:
        # Création en 2026 (taux présent) : allocation calculée normalement.
        created = _create_trip(auth_headers, vid, trip_date="2026-05-01",
                               one_way_km=100, round_trip=False)
        tid = created["trip"]["id"]
        assert created["allocation"] is not None
        assert created["allocation"]["amount_cad"] == round(100 * 0.73, 2)
        # Édition VERS 2027 (aucun taux) : allocation re-dérivée à None, aucun montant deviné.
        r = client.put(f"/api/mileage/trips/{tid}",
                       json=_new_trip_payload(vid, trip_date="2027-05-01",
                                              one_way_km=100, round_trip=False),
                       headers=auth_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["trip"]["trip_date"] == "2027-05-01"
        assert body["allocation"] is None          # AUCUN montant deviné après l'edit
        assert body["rate_missing_year"] == 2027
        assert body["running_total_km"] == 100.0   # cumul km toujours tenu
        # Le rappel annuel est réellement écrit pour l'org (enforcement, pas simple flag).
        rem = db.mileage_rate_reminders.find_one({"id": reminder_id})
        assert rem is not None
        assert rem["year"] == 2027
        assert rem["organization_id"] == org_id
        # GET par id : recalcul identique (stable, toujours None — jamais figé sur 2026).
        got = client.get(f"/api/mileage/trips/{tid}", headers=auth_headers)
        assert got.status_code == 200, got.text
        assert got.json()["allocation"] is None
        assert got.json()["rate_missing_year"] == 2027
    finally:
        db.mileage_rate_reminders.delete_one({"id": reminder_id})
        _cleanup_vehicle(vid)


def test_delete_trip(auth_headers):
    vid = _dedicated_vehicle(auth_headers, "T6 delete")
    try:
        created = _create_trip(auth_headers, vid, one_way_km=5, round_trip=False)
        tid = created["trip"]["id"]
        r = client.delete(f"/api/mileage/trips/{tid}", headers=auth_headers)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "deleted"
        # Le trajet n'existe plus (404 au GET par id).
        r2 = client.get(f"/api/mileage/trips/{tid}", headers=auth_headers)
        assert r2.status_code == 404, r2.text
    finally:
        _cleanup_vehicle(vid)


def test_delete_unknown_trip_returns_404(auth_headers):
    r = client.delete("/api/mileage/trips/does-not-exist", headers=auth_headers)
    assert r.status_code == 404, r.text


def test_delete_recomputes_ytd_for_remaining_trips(auth_headers):
    # Après suppression d'un trajet, le cumul YTD (jamais figé) des trajets restants
    # est recalculé : l'allocation d'un trajet postérieur baisse en conséquence.
    vid = _dedicated_vehicle(auth_headers, "T6 delete recompute")
    try:
        first = _create_trip(auth_headers, vid, trip_date="2026-02-01",
                             one_way_km=100, round_trip=False)
        second = _create_trip(auth_headers, vid, trip_date="2026-02-02",
                              one_way_km=100, round_trip=False)
        # Avant suppression : le 2e a un cumul YTD de 100 km avant lui.
        assert second["ytd_before"] == 100.0
        # On supprime le premier ; le 2e voit désormais un cumul de 0.
        assert client.delete(f"/api/mileage/trips/{first['trip']['id']}",
                             headers=auth_headers).status_code == 200
        refetched = client.get(f"/api/mileage/trips/{second['trip']['id']}",
                               headers=auth_headers)
        assert refetched.status_code == 200, refetched.text
        assert refetched.json()["ytd_before"] == 0.0
        assert refetched.json()["running_total_km"] == 100.0
    finally:
        _cleanup_vehicle(vid)


def test_edit_trip_blocked_when_billed(auth_headers):
    # Garde-fou : un trajet déjà rattaché à une dépense (expense_id) ne peut être
    # ni édité ni supprimé directement (400) — il faut d'abord détacher la dépense.
    # La génération de dépense arrive au Task 10 ; on pose ici l'expense_id
    # directement en DB (scopé org) pour exercer le garde-fou dès le T6.
    vid = _dedicated_vehicle(auth_headers, "T6 verrou facture")
    try:
        created = _create_trip(auth_headers, vid, one_way_km=10, round_trip=False)
        tid = created["trip"]["id"]
        db.mileage_trips.update_one({"id": tid}, {"$set": {"expense_id": "exp-lie-123"}})
        r_put = client.put(f"/api/mileage/trips/{tid}",
                           json=_new_trip_payload(vid, one_way_km=99),
                           headers=auth_headers)
        assert r_put.status_code == 400, r_put.text
        r_del = client.delete(f"/api/mileage/trips/{tid}", headers=auth_headers)
        assert r_del.status_code == 400, r_del.text
    finally:
        _cleanup_vehicle(vid)


# ─── Task 7 : Favoris (CRUD) ───
#
# Les favoris sont des GABARITS de trajet (label, départ, arrivée, motif, km,
# aller-retour par défaut) — purement pratiques pour pré-remplir la saisie. Ils
# sont INDÉPENDANTS des trajets : `favorite_id` sur un trajet est traçant, jamais
# liant (spec §3.3). Éditer/supprimer un favori ne DOIT PAS muter les trajets déjà
# saisis. On respecte la discipline d'isolation du fichier : véhicule dédié pour le
# trajet, nettoyage systématique du favori et du véhicule en `finally` (jamais de
# favori/trajet laissé dans le seed org).


def test_favorite_crud_and_trip_independence(auth_headers):
    r = client.post("/api/mileage/favorites", json={
        "label": "Domicile → Client ABC", "origin": "Domicile",
        "destination": "Client ABC, Lévis", "purpose": "Rencontre",
        "one_way_km": 45, "round_trip_default": True,
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    fid = r.json()["id"]

    vid = _dedicated_vehicle(auth_headers, "T7 favori independance")
    try:
        # normalisation : origin/destination trim, one_way_km arrondi en float
        created = r.json()
        assert created["label"] == "Domicile → Client ABC"
        assert created["one_way_km"] == 45.0
        assert created["round_trip_default"] is True
        assert "_id" not in created  # projection Mongo interne masquée

        lst = client.get("/api/mileage/favorites", headers=auth_headers)
        assert lst.status_code == 200, lst.text
        assert any(f["id"] == fid for f in lst.json())

        # trajet créé depuis le favori (favorite_id tracé)
        tr = client.post("/api/mileage/trips",
                         json=_new_trip_payload(vid, favorite_id=fid, one_way_km=45,
                                                round_trip=False),
                         headers=auth_headers)
        assert tr.status_code == 200, tr.text
        tid = tr.json()["trip"]["id"]
        assert tr.json()["trip"]["favorite_id"] == fid
        assert tr.json()["trip"]["one_way_km"] == 45.0

        # éditer le favori n'affecte pas le trajet (snapshot indépendant)
        upd = client.put(f"/api/mileage/favorites/{fid}", json={
            "label": "Modifié", "origin": "X", "destination": "Y",
            "one_way_km": 999, "round_trip_default": False,
        }, headers=auth_headers)
        assert upd.status_code == 200, upd.text
        assert upd.json()["label"] == "Modifié"
        assert upd.json()["one_way_km"] == 999.0
        trip_after = client.get(f"/api/mileage/trips/{tid}", headers=auth_headers).json()
        assert trip_after["trip"]["one_way_km"] == 45.0

        # supprimer le favori n'affecte pas le trajet
        dr = client.delete(f"/api/mileage/favorites/{fid}", headers=auth_headers)
        assert dr.status_code == 200, dr.text
        still = client.get(f"/api/mileage/trips/{tid}", headers=auth_headers)
        assert still.status_code == 200
        assert still.json()["trip"]["favorite_id"] == fid  # référence traçante conservée
    finally:
        db.mileage_favorites.delete_one({"id": fid})
        _cleanup_vehicle(vid)


def test_favorite_requires_label(auth_headers):
    r = client.post("/api/mileage/favorites", json={
        "label": "  ", "origin": "A", "destination": "B", "one_way_km": 10,
    }, headers=auth_headers)
    assert r.status_code == 400, r.text
    assert "nom" in r.json()["detail"].lower() or "favori" in r.json()["detail"].lower()


def test_favorite_requires_positive_distance(auth_headers):
    # La distance est le seul champ numérique d'un gabarit : >0 obligatoire, sinon
    # un trajet pré-rempli depuis ce favori naîtrait avec une distance invalide.
    r = client.post("/api/mileage/favorites", json={
        "label": "Sans distance", "origin": "A", "destination": "B", "one_way_km": 0,
    }, headers=auth_headers)
    assert r.status_code == 400, r.text


def test_update_unknown_favorite_returns_404(auth_headers):
    r = client.put("/api/mileage/favorites/does-not-exist", json={
        "label": "X", "origin": "A", "destination": "B", "one_way_km": 10,
    }, headers=auth_headers)
    assert r.status_code == 404, r.text


def test_delete_unknown_favorite_returns_404(auth_headers):
    r = client.delete("/api/mileage/favorites/does-not-exist", headers=auth_headers)
    assert r.status_code == 404, r.text


# --- Task 8 : GET /api/mileage/rates (+ drapeau annee manquante) --------------

def test_get_rates(auth_headers):
    r = client.get("/api/mileage/rates", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["threshold_km"] == 5000
    # Taux ARC exacts par annee (1er = 5000 premiers km, 2e = au-dela).
    assert body["rates"]["2024"] == {"full": 0.70, "reduced": 0.64}
    assert body["rates"]["2025"] == {"full": 0.72, "reduced": 0.66}
    assert body["rates"]["2026"] == {"full": 0.73, "reduced": 0.67}
    assert "current_year" in body
    assert "current_year_missing" in body
    # Le drapeau reflete exactement l'absence/presence du taux de l'annee courante.
    assert body["current_year_missing"] == (
        _mileage_rate_for_year(body["current_year"]) is None
    )


def test_get_rates_flags_a_missing_year_year(auth_headers):
    # Contrat de garde : une annee sans taux publie ne doit PAS apparaitre dans la
    # table (sinon un fallback silencieux produirait une mauvaise allocation).
    r = client.get("/api/mileage/rates", headers=auth_headers)
    body = r.json()
    assert "2099" not in body["rates"], (
        "Une annee sans taux ARC ne doit jamais etre exposee comme un taux valide"
    )
    # Coherence stricte du drapeau avec le helper source de verite.
    for year_str in body["rates"]:
        assert _mileage_rate_for_year(int(year_str)) is not None
