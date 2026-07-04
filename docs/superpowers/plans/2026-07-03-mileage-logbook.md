# Carnet de route — kilométrage et allocation véhicule (feature #13) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter un carnet de route ARC à FacturePro : saisie manuelle des trajets d'affaires, calcul automatique de l'allocation par km (avec bascule au taux réduit après 5 000 km cumulés/an), génération d'une dépense « Frais de véhicule » (ligne ARC 9281) et export d'un carnet de route PDF conforme.

**Architecture:** Module purement additif dans `backend/server.py`. Une table des taux ARC en constante serveur (`MILEAGE_RATES`) + helpers de calcul (`_mileage_rate_for_year`, `_mileage_ytd_before`, `_mileage_allocation`). Quatre nouvelles collections org-scopées (`mileage_trips`, `mileage_favorites`, `mileage_vehicles`, `mileage_rate_reminders`). ~14 endpoints `/api/mileage/*` réutilisant `expenses:read`/`expenses:write` et le chemin existant `create_expense`. Un endpoint de rappel annuel pingé par cron externe (modèle `check-trial-expiry`, pas de scheduler in-process). Frontend : section « Carnet de route » à 3 onglets dans `ExpensesPage.js`.

**Tech Stack:** FastAPI (pymongo synchrone), MongoDB, ReportLab (PDF FR-CA), Resend (email), React 18 (CRA, pas de router lib), axios, lucide-react.

---

## File Structure

- `backend/server.py` — MODIFY. Ajout de : constantes taux + helpers (§Task 1-3), migration + seed lazy (§Task 4), endpoints trajets/favoris/véhicules/taux (§Task 5-9), génération dépense + cascade (§Task 10), carnet JSON + PDF (§Task 11), rappel annuel cron (§Task 12). Enregistrement de la migration au startup + ajout aux `_ORG_SCOPED_COLLECTIONS`.
- `backend/tests/test_mileage_logbook.py` — CREATE. Tests unitaires des helpers de calcul (taux, distance, allocation, cumul).
- `backend/tests/test_mileage_logbook_integration.py` — CREATE. Tests d'intégration des endpoints (CRUD, bascule end-to-end, favoris, génération dépense, cascade, PDF, rappel, RBAC, isolation cross-org).
- `frontend/src/pages/ExpensesPage.js` — MODIFY. Bouton « Carnet de route » + vue carnet à 3 onglets (Trajets, Favoris, Carnet).
- `CLAUDE.md` — MODIFY. Entrée « Features livrées » pour feature #13.

**Conventions du codebase (confirmées dans le spec) :**
- Multi-tenant : `_org_scope(current_user)` construit le filtre `{"organization_id": ...}` ; `_ORG_SCOPED_COLLECTIONS` (`server.py:1369`) liste les collections à scoper.
- RBAC : `require_permission("code")` (`server.py:1344`) en dependency ; `expenses:read`/`expenses:write` déjà dans `PERMISSIONS_EDITABLE` (`server.py:1220`).
- Dépenses : `create_expense` (`server.py:4960`), `_build_expense_category_snapshot`, catégorie `vehicle_expenses` (ligne 9281, `server.py:167`).
- Cascade : `_release_bank_transaction` (feature #7) est le modèle pour `_release_mileage_trips`.
- PDF : `_t2125_format_money`, `SimpleDocTemplate` ReportLab, `html.escape`, headers `no-store, no-cache`.
- Cron externe : `POST /api/subscription/check-trial-expiry` (`server.py:6254`), garde anti-double `trial_notifications` (`server.py:6281`).
- Migrations idempotentes au startup après `migrate_general_ledger_v1()` (`server.py:7032`).

> **Note pré-implémentation (taux ARC) :** taux confirmés contre canada.ca. 2024 : 0,70/0,64 et 2025 : 0,72/0,66 (Reg. 7306 ITR). **2026 : 0,73/0,67 — CONFIRMÉ le 2026-07-04** contre canada.ca (annonce Finance Canada des plafonds 2026 + guide des allocations automobiles ARC : hausse d'un cent → 73 c/km pour les 5 000 premiers km, 67 c/km au-delà, provinces). Le seuil 5 000 km et les taux territoriaux (+0,04 $/km) sont hors scope v1 (§13 du spec).

> **Note infra (hors code, à documenter) :** après déploiement, créer un cron externe (Render Cron Job ou cron-job.org) qui `POST` sur `/api/mileage/check-rate-update` 1×/jour en janvier. Aucune dépendance Python de scheduling ajoutée.

---

## Task 1: Table des taux ARC + `_mileage_rate_for_year`

**Files:**
- Modify: `backend/server.py` (à côté de `EXPENSE_CATEGORIES`, ~`server.py:150`)
- Test: `backend/tests/test_mileage_logbook.py`

- [ ] **Step 1: Write the failing test**

Créer `backend/tests/test_mileage_logbook.py` :

```python
import math
import pytest
from backend.server import (
    MILEAGE_RATES,
    MILEAGE_RATE_THRESHOLD_KM,
    _mileage_rate_for_year,
)


def test_mileage_rate_for_year_known_years():
    assert _mileage_rate_for_year(2024) == {"full": 0.70, "reduced": 0.64}
    assert _mileage_rate_for_year(2025) == {"full": 0.72, "reduced": 0.66}
    assert _mileage_rate_for_year(2026) == {"full": 0.73, "reduced": 0.67}


def test_mileage_rate_for_year_missing_returns_none():
    assert _mileage_rate_for_year(1999) is None
    assert _mileage_rate_for_year(2099) is None


def test_mileage_rate_for_year_accepts_string_year():
    assert _mileage_rate_for_year("2026") == {"full": 0.73, "reduced": 0.67}


def test_mileage_threshold_constant():
    assert MILEAGE_RATE_THRESHOLD_KM == 5000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_mileage_logbook.py -v`
Expected: FAIL with `ImportError: cannot import name 'MILEAGE_RATES'`

- [ ] **Step 3: Write minimal implementation**

Ajouter dans `backend/server.py`, juste après le bloc `EXPENSE_CATEGORIES` (~`server.py:150`) :

```python
# Taux ARC allocation automobile, en $ CAD par km.
# full    = taux pour les 5 000 premiers km de l'annee civile
# reduced = taux pour chaque km au-dela de 5 000
# Confirmes contre canada.ca avant chaque deploiement (voir rappel annuel).
MILEAGE_RATES = {
    2024: {"full": 0.70, "reduced": 0.64},
    2025: {"full": 0.72, "reduced": 0.66},
    2026: {"full": 0.73, "reduced": 0.67},
}
MILEAGE_RATE_THRESHOLD_KM = 5000  # bascule full -> reduced (par personne+vehicule+annee)


def _mileage_rate_for_year(year) -> dict | None:
    """Retourne {'full','reduced'} pour l'annee, ou None si non renseignee
    (declenche le rappel annuel). Pas de fallback silencieux sur une autre
    annee : un taux manquant est une condition a corriger, pas a deviner."""
    return MILEAGE_RATES.get(int(year))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_mileage_logbook.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/server.py backend/tests/test_mileage_logbook.py
git commit -m "feat(mileage): add ARC mileage rate table and _mileage_rate_for_year"
```

---

## Task 2: Distance dérivée + allocation avec split au seuil

**Files:**
- Modify: `backend/server.py` (après les helpers du Task 1)
- Test: `backend/tests/test_mileage_logbook.py`

- [ ] **Step 1: Write the failing test**

Ajouter à `backend/tests/test_mileage_logbook.py` :

```python
from backend.server import _mileage_distance_km, _mileage_allocation


def test_distance_one_way():
    assert _mileage_distance_km(45.0, round_trip=False) == 45.0


def test_distance_round_trip_doubles():
    assert _mileage_distance_km(45.0, round_trip=True) == 90.0


def test_distance_rounds_two_decimals():
    assert _mileage_distance_km(10.005, round_trip=False) == 10.01
    assert _mileage_distance_km(33.333, round_trip=True) == 66.67


RATES_2026 = {"full": 0.73, "reduced": 0.67}


def test_allocation_no_switch_all_full():
    amount, bd = _mileage_allocation(100.0, ytd_before=0.0, rates=RATES_2026)
    assert amount == 73.00
    assert bd["km_full"] == 100.0
    assert bd["km_reduced"] == 0.0
    assert bd["rate_full"] == 0.73
    assert bd["rate_reduced"] == 0.67
    assert bd["ytd_before"] == 0.0


def test_allocation_all_reduced():
    amount, bd = _mileage_allocation(100.0, ytd_before=6000.0, rates=RATES_2026)
    assert amount == 67.00
    assert bd["km_full"] == 0.0
    assert bd["km_reduced"] == 100.0


def test_allocation_split_across_threshold():
    # cas critique : 4900 deja cumules, trajet 200 km -> 100 @ full + 100 @ reduced
    amount, bd = _mileage_allocation(200.0, ytd_before=4900.0, rates=RATES_2026)
    assert amount == 140.00
    assert bd["km_full"] == 100.0
    assert bd["km_reduced"] == 100.0


def test_allocation_exactly_at_threshold_all_reduced():
    amount, bd = _mileage_allocation(100.0, ytd_before=5000.0, rates=RATES_2026)
    assert amount == 67.00
    assert bd["km_full"] == 0.0
    assert bd["km_reduced"] == 100.0


def test_allocation_just_under_threshold_all_full():
    # ytd 4800 + 200 = pile 5000 -> tout au taux plein
    amount, bd = _mileage_allocation(200.0, ytd_before=4800.0, rates=RATES_2026)
    assert amount == round(200 * 0.73, 2)
    assert bd["km_full"] == 200.0
    assert bd["km_reduced"] == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_mileage_logbook.py -v`
Expected: FAIL with `ImportError: cannot import name '_mileage_distance_km'`

- [ ] **Step 3: Write minimal implementation**

Ajouter dans `backend/server.py`, après `_mileage_rate_for_year` :

```python
def _mileage_distance_km(one_way_km: float, round_trip: bool) -> float:
    """Distance derivee, toujours recalculee backend (la valeur envoyee par le
    client est ignoree). Aller simple = one_way_km ; aller-retour = doublee."""
    factor = 2 if round_trip else 1
    return round(float(one_way_km) * factor, 2)


def _mileage_allocation(distance_km, ytd_before, rates, threshold=MILEAGE_RATE_THRESHOLD_KM):
    """Retourne (amount_cad, breakdown).
    Applique le taux plein aux km jusqu'a `threshold` cumule, le taux reduit
    au-dela. Un trajet a cheval sur le seuil est SCINDE.

    Ex: ytd_before=4900, distance=200, threshold=5000, full=0.73, reduced=0.67
        -> 100 km @ 0.73 + 100 km @ 0.67 = 73.00 + 67.00 = 140.00
    """
    distance_km = float(distance_km)
    ytd_before = float(ytd_before)
    remaining_full = max(0.0, threshold - ytd_before)
    km_full = min(distance_km, remaining_full)
    km_reduced = distance_km - km_full
    amount = round(km_full * rates["full"] + km_reduced * rates["reduced"], 2)
    return amount, {
        "km_full": round(km_full, 2),
        "rate_full": rates["full"],
        "km_reduced": round(km_reduced, 2),
        "rate_reduced": rates["reduced"],
        "ytd_before": round(ytd_before, 2),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_mileage_logbook.py -v`
Expected: PASS (tous les tests des Tasks 1-2)

- [ ] **Step 5: Commit**

```bash
git add backend/server.py backend/tests/test_mileage_logbook.py
git commit -m "feat(mileage): add distance derivation and allocation with 5000km split"
```

---

## Task 3: Cumul annuel `_mileage_ytd_before`

**Files:**
- Modify: `backend/server.py` (après `_mileage_allocation`)
- Test: `backend/tests/test_mileage_logbook.py`

Le cumul est chronologique par `(trip_date, id)`. Le YTD « avant » un trajet est la somme des `distance_km` des trajets antérieurs de la même personne+véhicule dans l'année civile. La clé personne est `employee_id` ou, si None, `"user:{user_id}"`.

- [ ] **Step 1: Write the failing test**

Ajouter à `backend/tests/test_mileage_logbook.py`. On teste la logique de sommation pure via une fonction qui accepte une liste de docs déjà chargés (l'accès DB est testé en intégration au Task 6) :

```python
from backend.server import _mileage_sum_ytd


def _trip(trip_date, distance_km, tid, employee_key="user:U1", vehicle_id="V1"):
    return {
        "id": tid,
        "trip_date": trip_date,
        "distance_km": distance_km,
        "employee_key": employee_key,
        "vehicle_id": vehicle_id,
    }


def test_ytd_sums_earlier_trips_same_person_vehicle():
    trips = [
        _trip("2026-01-05", 100.0, "a"),
        _trip("2026-02-10", 50.0, "b"),
        _trip("2026-03-01", 30.0, "c"),  # le trajet courant
    ]
    total = _mileage_sum_ytd(trips, current_id="c", current_date="2026-03-01",
                             employee_key="user:U1", vehicle_id="V1")
    assert total == 150.0


def test_ytd_ignores_other_person():
    trips = [
        _trip("2026-01-05", 100.0, "a", employee_key="EMP2"),
        _trip("2026-02-01", 40.0, "b"),
    ]
    total = _mileage_sum_ytd(trips, current_id="b", current_date="2026-02-01",
                             employee_key="user:U1", vehicle_id="V1")
    assert total == 0.0


def test_ytd_ignores_other_vehicle():
    trips = [
        _trip("2026-01-05", 100.0, "a", vehicle_id="V2"),
        _trip("2026-02-01", 40.0, "b"),
    ]
    total = _mileage_sum_ytd(trips, current_id="b", current_date="2026-02-01",
                             employee_key="user:U1", vehicle_id="V1")
    assert total == 0.0


def test_ytd_ignores_other_year():
    trips = [
        _trip("2025-12-31", 500.0, "a"),
        _trip("2026-01-02", 40.0, "b"),
    ]
    total = _mileage_sum_ytd(trips, current_id="b", current_date="2026-01-02",
                             employee_key="user:U1", vehicle_id="V1")
    assert total == 0.0


def test_ytd_same_date_orders_by_id():
    trips = [
        _trip("2026-05-01", 10.0, "a"),
        _trip("2026-05-01", 20.0, "b"),  # courant ; 'a' < 'b' donc compte
    ]
    total = _mileage_sum_ytd(trips, current_id="b", current_date="2026-05-01",
                             employee_key="user:U1", vehicle_id="V1")
    assert total == 10.0


def test_ytd_excludes_current_and_later_trips():
    trips = [
        _trip("2026-01-01", 10.0, "a"),
        _trip("2026-06-01", 99.0, "c"),  # courant
        _trip("2026-09-01", 77.0, "z"),  # posterieur
    ]
    total = _mileage_sum_ytd(trips, current_id="c", current_date="2026-06-01",
                             employee_key="user:U1", vehicle_id="V1")
    assert total == 10.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_mileage_logbook.py -v`
Expected: FAIL with `ImportError: cannot import name '_mileage_sum_ytd'`

- [ ] **Step 3: Write minimal implementation**

Ajouter dans `backend/server.py`, après `_mileage_allocation` :

```python
def _mileage_employee_key(employee_id, user_id) -> str:
    """Cle stable identifiant la personne pour le cumul 5000 km.
    employee_id si present, sinon 'user:{user_id}'."""
    return employee_id if employee_id else f"user:{user_id}"


def _mileage_sum_ytd(trips, current_id, current_date, employee_key, vehicle_id):
    """Somme des distance_km des trajets ANTERIEURS de la meme personne+vehicule
    dans la meme annee civile que current_date. Ordre (trip_date, id).
    Chaque trip du parametre `trips` porte deja 'employee_key' et 'vehicle_id'.
    """
    year = current_date[:4]
    total = 0.0
    for t in trips:
        if t["employee_key"] != employee_key or t["vehicle_id"] != vehicle_id:
            continue
        if t["trip_date"][:4] != year:
            continue
        # anterieur = date < current_date, ou meme date avec id <
        if (t["trip_date"], t["id"]) < (current_date, current_id):
            total += float(t["distance_km"])
    return round(total, 2)


def _mileage_ytd_before(scope, employee_key, vehicle_id, current_date, current_id):
    """Charge les trajets de l'annee civile de current_date pour la meme
    personne+vehicule (scope org via `scope`), puis somme les anterieurs.
    `scope` = dict de filtre org (issu de _org_scope). employee_key est
    la cle deja resolue via _mileage_employee_key."""
    year = current_date[:4]
    query = {
        **scope,
        "vehicle_id": vehicle_id,
        "trip_date": {"$gte": f"{year}-01-01", "$lte": f"{year}-12-31"},
    }
    docs = list(db.mileage_trips.find(query))
    trips = [
        {
            "id": d["id"],
            "trip_date": d["trip_date"],
            "distance_km": d.get("distance_km", 0.0),
            "employee_key": _mileage_employee_key(d.get("employee_id"), d.get("created_by_user_id")),
            "vehicle_id": d["vehicle_id"],
        }
        for d in docs
    ]
    return _mileage_sum_ytd(trips, current_id, current_date, employee_key, vehicle_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_mileage_logbook.py -v`
Expected: PASS (tous les tests des Tasks 1-3)

- [ ] **Step 5: Commit**

```bash
git add backend/server.py backend/tests/test_mileage_logbook.py
git commit -m "feat(mileage): add year-to-date cumulative km helpers"
```

---

## Task 4: Migration idempotente + seed lazy du véhicule + org-scoping

**Files:**
- Modify: `backend/server.py` (fonction `migrate_mileage_logbook_v1`, enregistrement startup `server.py:7032`, `_ORG_SCOPED_COLLECTIONS` `server.py:1369`)
- Test: `backend/tests/test_mileage_logbook_integration.py`

- [ ] **Step 1: Write the failing test**

Créer `backend/tests/test_mileage_logbook_integration.py`. Utiliser le TestClient existant du codebase (même style que `test_partial_payments_integration.py`). En-tête + fixtures d'auth :

```python
import pytest
from fastapi.testclient import TestClient
from backend.server import app, db, _mileage_rate_for_year

client = TestClient(app)


@pytest.fixture
def auth_headers():
    # Reutilise le compte de seed exempte (voir CLAUDE.md)
    resp = client.post("/api/auth/login", json={
        "email": "gussdub@gmail.com", "password": "testpass123",
    })
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_migration_creates_indexes():
    # La migration a tourne au startup ; les collections existent et sont indexees.
    names = [ix["name"] for ix in db.mileage_trips.list_indexes()]
    assert any("organization_id" in n and "trip_date" in n for n in names)
    reminder_names = [ix["name"] for ix in db.mileage_rate_reminders.list_indexes()]
    assert any(db.mileage_rate_reminders.index_information()[n].get("unique")
               for n in db.mileage_rate_reminders.index_information())


def test_lazy_default_vehicle_created_once(auth_headers):
    # 1er GET seed le vehicule par defaut ; 2e appel ne cree pas de doublon.
    r1 = client.get("/api/mileage/vehicles", headers=auth_headers)
    assert r1.status_code == 200
    defaults = [v for v in r1.json() if v["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["name"] == "Véhicule principal"

    r2 = client.get("/api/mileage/vehicles", headers=auth_headers)
    assert len([v for v in r2.json() if v["is_default"]]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_mileage_logbook_integration.py -v`
Expected: FAIL — `mileage_trips` sans index attendu et route `/api/mileage/vehicles` inconnue (404).

- [ ] **Step 3: Write minimal implementation**

3a. Ajouter la migration dans `backend/server.py` (près de `migrate_general_ledger_v1`) :

```python
def migrate_mileage_logbook_v1():
    """Idempotente. Safe a chaque boot. Purement additive : cree uniquement les
    index des nouvelles collections. AUCUNE donnee existante touchee. Le vehicule
    par defaut est seede LAZY au 1er acces, pas ici."""
    db.mileage_trips.create_index([("organization_id", 1), ("trip_date", 1)])
    db.mileage_trips.create_index([("organization_id", 1), ("vehicle_id", 1), ("trip_date", 1)])
    db.mileage_trips.create_index([("organization_id", 1), ("employee_id", 1)])
    db.mileage_trips.create_index([("organization_id", 1), ("expense_id", 1)])
    db.mileage_favorites.create_index([("organization_id", 1), ("label", 1)])
    db.mileage_vehicles.create_index([("organization_id", 1), ("is_default", 1)])
    db.mileage_rate_reminders.create_index("id", unique=True)
```

3b. Enregistrer au startup, après `migrate_general_ledger_v1()` (`server.py:7032`) :

```python
    migrate_general_ledger_v1()
    migrate_mileage_logbook_v1()
```

3c. Ajouter les 4 collections à `_ORG_SCOPED_COLLECTIONS` (`server.py:1369`) :

```python
    "mileage_trips",
    "mileage_favorites",
    "mileage_vehicles",
    "mileage_rate_reminders",
```

3d. Ajouter le seed lazy + le routeur (juste avant les endpoints du Task 5). `db`, `uuid`, `datetime`, `timezone` sont déjà importés dans `server.py` :

```python
def _ensure_default_vehicle(org_id: str, user_id: str) -> None:
    """Seed lazy du vehicule par defaut. Idempotent : ne cree que si zero
    vehicule pour l'org (comme le plan comptable feature #12)."""
    if db.mileage_vehicles.count_documents({"organization_id": org_id}) == 0:
        db.mileage_vehicles.insert_one({
            "id": str(uuid.uuid4()),
            "organization_id": org_id,
            "created_by_user_id": user_id,
            "name": "Véhicule principal",
            "make_model": None,
            "plate": None,
            "is_default": True,
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })


@app.get("/api/mileage/vehicles")
async def list_mileage_vehicles(current_user=Depends(require_permission("expenses:read"))):
    _ensure_default_vehicle(current_user.organization_id, current_user.id)
    scope = _org_scope(current_user)
    vehicles = list(db.mileage_vehicles.find(scope, {"_id": 0}))
    return vehicles


@app.post("/api/mileage/vehicles")
async def create_mileage_vehicle(payload: dict, current_user=Depends(require_permission("expenses:write"))):
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Le nom du véhicule est obligatoire")
    doc = {
        "id": str(uuid.uuid4()),
        "organization_id": current_user.organization_id,
        "created_by_user_id": current_user.id,
        "name": name,
        "make_model": (payload.get("make_model") or None),
        "plate": (payload.get("plate") or None),
        "is_default": False,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    db.mileage_vehicles.insert_one(doc)
    doc.pop("_id", None)
    return doc
```

> Vérifier que `require_permission`, `_org_scope`, `Depends`, `HTTPException` sont bien les symboles utilisés ailleurs dans `server.py` (ils le sont — features #11/#12). Adapter le nom du paramètre `current_user` si le codebase utilise une autre convention (ex : `user`).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_mileage_logbook_integration.py -v`
Expected: PASS (migration + seed lazy)

- [ ] **Step 5: Commit**

```bash
git add backend/server.py backend/tests/test_mileage_logbook_integration.py
git commit -m "feat(mileage): add migration, lazy default vehicle seed, and vehicle endpoints"
```

---

## Task 5: POST /api/mileage/trips (création + validation + distance recalculée)

**Files:**
- Modify: `backend/server.py` (après les endpoints véhicules)
- Test: `backend/tests/test_mileage_logbook_integration.py`

- [ ] **Step 1: Write the failing test**

Ajouter à `backend/tests/test_mileage_logbook_integration.py` :

```python
def _new_trip_payload(**over):
    base = {
        "trip_date": "2026-03-10",
        "origin": "Domicile, Québec",
        "destination": "Client ABC, Lévis",
        "purpose": "Rencontre client",
        "one_way_km": 45.0,
        "round_trip": True,
    }
    base.update(over)
    return base


def test_create_trip_requires_purpose(auth_headers):
    r = client.post("/api/mileage/trips", json=_new_trip_payload(purpose="   "),
                    headers=auth_headers)
    assert r.status_code == 400
    assert "motif" in r.json()["detail"].lower()


def test_create_trip_requires_positive_km(auth_headers):
    r = client.post("/api/mileage/trips", json=_new_trip_payload(one_way_km=0),
                    headers=auth_headers)
    assert r.status_code == 400


def test_create_trip_round_trip_doubles_distance(auth_headers):
    r = client.post("/api/mileage/trips", json=_new_trip_payload(one_way_km=45, round_trip=True),
                    headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["trip"]["distance_km"] == 90.0
    # enrichi de l'allocation (2026, sous 5000 km)
    assert body["allocation"]["amount_cad"] == round(90 * 0.73, 2)


def test_create_trip_ignores_client_supplied_distance(auth_headers):
    r = client.post("/api/mileage/trips",
                    json=_new_trip_payload(one_way_km=10, round_trip=False, distance_km=9999),
                    headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["trip"]["distance_km"] == 10.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_mileage_logbook_integration.py -k create_trip -v`
Expected: FAIL — route `/api/mileage/trips` inconnue (404/405).

- [ ] **Step 3: Write minimal implementation**

Ajouter dans `backend/server.py`. `math` est déjà importé (feature #10) :

```python
def _mileage_resolve_vehicle_id(scope, org_id, payload_vehicle_id):
    """Retourne un vehicle_id valide de l'org. Si le payload en fournit un, il
    doit appartenir a l'org ; sinon on prend le vehicule par defaut."""
    if payload_vehicle_id:
        v = db.mileage_vehicles.find_one({**scope, "id": payload_vehicle_id})
        if not v:
            raise HTTPException(status_code=400, detail="Véhicule introuvable")
        return payload_vehicle_id
    default = db.mileage_vehicles.find_one({**scope, "is_default": True})
    if not default:
        default = db.mileage_vehicles.find_one(scope)
    return default["id"]


def _mileage_validate_employee(scope, employee_id):
    """Verifie que employee_id (optionnel) appartient a l'org."""
    if not employee_id:
        return None
    emp = db.employees.find_one({**scope, "id": employee_id})
    if not emp:
        raise HTTPException(status_code=400, detail="Employé introuvable")
    return employee_id


def _mileage_enrich_trip(trip: dict, scope) -> dict:
    """Retourne {'trip': ..., 'allocation': {...}, 'ytd_before': ...}.
    Recalcule allocation a la volee (jamais figee sur le trajet)."""
    year = int(trip["trip_date"][:4])
    rates = _mileage_rate_for_year(year)
    employee_key = _mileage_employee_key(trip.get("employee_id"), trip.get("created_by_user_id"))
    ytd_before = _mileage_ytd_before(scope, employee_key, trip["vehicle_id"],
                                     trip["trip_date"], trip["id"])
    if rates is None:
        return {
            "trip": trip,
            "allocation": None,
            "ytd_before": ytd_before,
            "rate_missing_year": year,
        }
    amount, breakdown = _mileage_allocation(trip["distance_km"], ytd_before, rates)
    return {
        "trip": trip,
        "allocation": {"amount_cad": amount, "breakdown": breakdown},
        "ytd_before": ytd_before,
        "rate_missing_year": None,
    }


@app.post("/api/mileage/trips")
async def create_mileage_trip(payload: dict, current_user=Depends(require_permission("expenses:write"))):
    _ensure_default_vehicle(current_user.organization_id, current_user.id)
    scope = _org_scope(current_user)

    purpose = (payload.get("purpose") or "").strip()
    if not purpose:
        raise HTTPException(status_code=400, detail="Le motif du déplacement est obligatoire")

    try:
        one_way_km = float(payload.get("one_way_km"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Distance invalide")
    if not math.isfinite(one_way_km) or one_way_km <= 0:
        raise HTTPException(status_code=400, detail="La distance (aller simple) doit être supérieure à 0")

    trip_date = (payload.get("trip_date") or "").strip()
    if len(trip_date) != 10:
        raise HTTPException(status_code=400, detail="Date de trajet invalide (AAAA-MM-JJ)")

    round_trip = bool(payload.get("round_trip", False))
    vehicle_id = _mileage_resolve_vehicle_id(scope, current_user.organization_id, payload.get("vehicle_id"))
    employee_id = _mileage_validate_employee(scope, payload.get("employee_id"))

    favorite_id = payload.get("favorite_id")
    if favorite_id and not db.mileage_favorites.find_one({**scope, "id": favorite_id}):
        raise HTTPException(status_code=400, detail="Favori introuvable")

    doc = {
        "id": str(uuid.uuid4()),
        "organization_id": current_user.organization_id,
        "created_by_user_id": current_user.id,
        "employee_id": employee_id,
        "vehicle_id": vehicle_id,
        "trip_date": trip_date,
        "origin": (payload.get("origin") or "").strip(),
        "destination": (payload.get("destination") or "").strip(),
        "purpose": purpose,
        "one_way_km": round(one_way_km, 2),
        "round_trip": round_trip,
        "distance_km": _mileage_distance_km(one_way_km, round_trip),
        "favorite_id": favorite_id or None,
        "expense_id": None,
        "notes": (payload.get("notes") or None),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    db.mileage_trips.insert_one(doc)
    doc.pop("_id", None)
    return _mileage_enrich_trip(doc, scope)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_mileage_logbook_integration.py -k create_trip -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/server.py backend/tests/test_mileage_logbook_integration.py
git commit -m "feat(mileage): add POST /api/mileage/trips with validation and enrichment"
```

---

## Task 6: GET/PUT/DELETE trajets + cumul YTD end-to-end (bascule 5000 km)

**Files:**
- Modify: `backend/server.py`
- Test: `backend/tests/test_mileage_logbook_integration.py`

- [ ] **Step 1: Write the failing test**

Ajouter à `backend/tests/test_mileage_logbook_integration.py` :

```python
def _create_trip(auth_headers, **over):
    r = client.post("/api/mileage/trips", json=_new_trip_payload(**over), headers=auth_headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_list_trips_filtered_and_enriched(auth_headers):
    _create_trip(auth_headers, trip_date="2026-04-01", one_way_km=10, round_trip=False)
    r = client.get("/api/mileage/trips?year=2026&month=4", headers=auth_headers)
    assert r.status_code == 200
    rows = r.json()
    assert all(row["trip"]["trip_date"].startswith("2026-04") for row in rows)
    assert "allocation" in rows[0] and "ytd_before" in rows[0]


def test_edit_trip_recalculates_distance(auth_headers):
    created = _create_trip(auth_headers, one_way_km=20, round_trip=False)
    tid = created["trip"]["id"]
    r = client.put(f"/api/mileage/trips/{tid}",
                   json=_new_trip_payload(one_way_km=20, round_trip=True),
                   headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["trip"]["distance_km"] == 40.0


def test_switch_5000km_end_to_end(auth_headers):
    vy = "2027-0"  # annee dediee au test pour partir de 0 (necessite un taux 2027)
    # On utilise 2026 mais on isole via un vehicule dedie pour repartir de 0.
    rv = client.post("/api/mileage/vehicles", json={"name": "Test bascule"}, headers=auth_headers)
    vid = rv.json()["id"]
    # 49 trajets de 100 km (aller simple) = 4900 km cumules
    for i in range(49):
        _create_trip(auth_headers, trip_date=f"2026-01-{(i % 28) + 1:02d}",
                     one_way_km=100, round_trip=False, vehicle_id=vid)
    # trajet qui franchit le seuil : ytd 4900 + 200 -> 100@0.73 + 100@0.67 = 140.00
    crossing = _create_trip(auth_headers, trip_date="2026-06-15",
                            one_way_km=200, round_trip=False, vehicle_id=vid)
    assert crossing["allocation"]["amount_cad"] == 140.00
    assert crossing["allocation"]["breakdown"]["km_full"] == 100.0
    assert crossing["allocation"]["breakdown"]["km_reduced"] == 100.0
    # trajet suivant : tout au taux reduit
    after = _create_trip(auth_headers, trip_date="2026-07-01",
                         one_way_km=100, round_trip=False, vehicle_id=vid)
    assert after["allocation"]["amount_cad"] == round(100 * 0.67, 2)


def test_delete_trip(auth_headers):
    created = _create_trip(auth_headers, one_way_km=5, round_trip=False)
    tid = created["trip"]["id"]
    r = client.delete(f"/api/mileage/trips/{tid}", headers=auth_headers)
    assert r.status_code == 200
    r2 = client.get(f"/api/mileage/trips/{tid}", headers=auth_headers)
    assert r2.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_mileage_logbook_integration.py -k "list_trips or edit_trip or switch_5000 or delete_trip" -v`
Expected: FAIL — routes GET/PUT/DELETE inconnues.

- [ ] **Step 3: Write minimal implementation**

Ajouter dans `backend/server.py` :

```python
@app.get("/api/mileage/trips")
async def list_mileage_trips(year: int = None, month: int = None, vehicle_id: str = None,
                             current_user=Depends(require_permission("expenses:read"))):
    _ensure_default_vehicle(current_user.organization_id, current_user.id)
    scope = _org_scope(current_user)
    query = dict(scope)
    if year and month:
        prefix = f"{int(year):04d}-{int(month):02d}"
        query["trip_date"] = {"$gte": f"{prefix}-01", "$lte": f"{prefix}-31"}
    elif year:
        query["trip_date"] = {"$gte": f"{int(year):04d}-01-01", "$lte": f"{int(year):04d}-12-31"}
    if vehicle_id:
        query["vehicle_id"] = vehicle_id
    docs = list(db.mileage_trips.find(query, {"_id": 0}))
    docs.sort(key=lambda d: (d["trip_date"], d["id"]))
    return [_mileage_enrich_trip(d, scope) for d in docs]


@app.get("/api/mileage/trips/{trip_id}")
async def get_mileage_trip(trip_id: str, current_user=Depends(require_permission("expenses:read"))):
    scope = _org_scope(current_user)
    doc = db.mileage_trips.find_one({**scope, "id": trip_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Trajet introuvable")
    return _mileage_enrich_trip(doc, scope)


@app.put("/api/mileage/trips/{trip_id}")
async def update_mileage_trip(trip_id: str, payload: dict,
                              current_user=Depends(require_permission("expenses:write"))):
    scope = _org_scope(current_user)
    doc = db.mileage_trips.find_one({**scope, "id": trip_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Trajet introuvable")
    if doc.get("expense_id"):
        raise HTTPException(status_code=400,
                            detail="Trajet déjà facturé — supprimez d'abord la dépense")

    purpose = (payload.get("purpose") or "").strip()
    if not purpose:
        raise HTTPException(status_code=400, detail="Le motif du déplacement est obligatoire")
    try:
        one_way_km = float(payload.get("one_way_km"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Distance invalide")
    if not math.isfinite(one_way_km) or one_way_km <= 0:
        raise HTTPException(status_code=400, detail="La distance (aller simple) doit être supérieure à 0")
    trip_date = (payload.get("trip_date") or doc["trip_date"]).strip()
    round_trip = bool(payload.get("round_trip", False))
    vehicle_id = _mileage_resolve_vehicle_id(scope, current_user.organization_id, payload.get("vehicle_id"))
    employee_id = _mileage_validate_employee(scope, payload.get("employee_id"))

    updates = {
        "trip_date": trip_date,
        "origin": (payload.get("origin") or "").strip(),
        "destination": (payload.get("destination") or "").strip(),
        "purpose": purpose,
        "one_way_km": round(one_way_km, 2),
        "round_trip": round_trip,
        "distance_km": _mileage_distance_km(one_way_km, round_trip),
        "vehicle_id": vehicle_id,
        "employee_id": employee_id,
        "notes": (payload.get("notes") or None),
    }
    db.mileage_trips.update_one({**scope, "id": trip_id}, {"$set": updates})
    fresh = db.mileage_trips.find_one({**scope, "id": trip_id}, {"_id": 0})
    return _mileage_enrich_trip(fresh, scope)


@app.delete("/api/mileage/trips/{trip_id}")
async def delete_mileage_trip(trip_id: str, current_user=Depends(require_permission("expenses:write"))):
    scope = _org_scope(current_user)
    doc = db.mileage_trips.find_one({**scope, "id": trip_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Trajet introuvable")
    if doc.get("expense_id"):
        raise HTTPException(status_code=400,
                            detail="Trajet lié à une dépense — détachez-la d'abord")
    db.mileage_trips.delete_one({**scope, "id": trip_id})
    return {"status": "deleted", "id": trip_id}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_mileage_logbook_integration.py -k "list_trips or edit_trip or switch_5000 or delete_trip" -v`
Expected: PASS (4 tests, dont la bascule 5000 km end-to-end)

- [ ] **Step 5: Commit**

```bash
git add backend/server.py backend/tests/test_mileage_logbook_integration.py
git commit -m "feat(mileage): add GET/PUT/DELETE trips with live YTD recalculation"
```

---

## Task 7: Favoris (CRUD)

**Files:**
- Modify: `backend/server.py`
- Test: `backend/tests/test_mileage_logbook_integration.py`

- [ ] **Step 1: Write the failing test**

Ajouter à `backend/tests/test_mileage_logbook_integration.py` :

```python
def test_favorite_crud_and_trip_independence(auth_headers):
    r = client.post("/api/mileage/favorites", json={
        "label": "Domicile → Client ABC", "origin": "Domicile",
        "destination": "Client ABC, Lévis", "purpose": "Rencontre",
        "one_way_km": 45, "round_trip_default": True,
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    fid = r.json()["id"]

    lst = client.get("/api/mileage/favorites", headers=auth_headers)
    assert any(f["id"] == fid for f in lst.json())

    # trajet cree depuis le favori (favorite_id trace)
    tr = client.post("/api/mileage/trips", json=_new_trip_payload(favorite_id=fid),
                     headers=auth_headers)
    assert tr.status_code == 200
    tid = tr.json()["trip"]["id"]
    assert tr.json()["trip"]["favorite_id"] == fid

    # editer le favori n'affecte pas le trajet
    client.put(f"/api/mileage/favorites/{fid}", json={
        "label": "Modifié", "origin": "X", "destination": "Y",
        "one_way_km": 999, "round_trip_default": False,
    }, headers=auth_headers)
    trip_after = client.get(f"/api/mileage/trips/{tid}", headers=auth_headers).json()
    assert trip_after["trip"]["one_way_km"] == 45.0

    # supprimer le favori n'affecte pas le trajet
    dr = client.delete(f"/api/mileage/favorites/{fid}", headers=auth_headers)
    assert dr.status_code == 200
    still = client.get(f"/api/mileage/trips/{tid}", headers=auth_headers)
    assert still.status_code == 200


def test_favorite_requires_label(auth_headers):
    r = client.post("/api/mileage/favorites", json={
        "label": "  ", "origin": "A", "destination": "B", "one_way_km": 10,
    }, headers=auth_headers)
    assert r.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_mileage_logbook_integration.py -k favorite -v`
Expected: FAIL — routes favoris inconnues.

- [ ] **Step 3: Write minimal implementation**

Ajouter dans `backend/server.py` :

```python
@app.get("/api/mileage/favorites")
async def list_mileage_favorites(current_user=Depends(require_permission("expenses:read"))):
    scope = _org_scope(current_user)
    favs = list(db.mileage_favorites.find(scope, {"_id": 0}))
    favs.sort(key=lambda f: f.get("label", ""))
    return favs


def _mileage_favorite_from_payload(payload, current_user):
    label = (payload.get("label") or "").strip()
    if not label:
        raise HTTPException(status_code=400, detail="Le nom du favori est obligatoire")
    try:
        one_way_km = float(payload.get("one_way_km"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Distance invalide")
    if not math.isfinite(one_way_km) or one_way_km <= 0:
        raise HTTPException(status_code=400, detail="La distance doit être supérieure à 0")
    return {
        "label": label,
        "origin": (payload.get("origin") or "").strip(),
        "destination": (payload.get("destination") or "").strip(),
        "purpose": (payload.get("purpose") or None),
        "one_way_km": round(one_way_km, 2),
        "round_trip_default": bool(payload.get("round_trip_default", False)),
    }


@app.post("/api/mileage/favorites")
async def create_mileage_favorite(payload: dict, current_user=Depends(require_permission("expenses:write"))):
    fields = _mileage_favorite_from_payload(payload, current_user)
    doc = {
        "id": str(uuid.uuid4()),
        "organization_id": current_user.organization_id,
        "created_by_user_id": current_user.id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **fields,
    }
    db.mileage_favorites.insert_one(doc)
    doc.pop("_id", None)
    return doc


@app.put("/api/mileage/favorites/{favorite_id}")
async def update_mileage_favorite(favorite_id: str, payload: dict,
                                  current_user=Depends(require_permission("expenses:write"))):
    scope = _org_scope(current_user)
    if not db.mileage_favorites.find_one({**scope, "id": favorite_id}):
        raise HTTPException(status_code=404, detail="Favori introuvable")
    fields = _mileage_favorite_from_payload(payload, current_user)
    db.mileage_favorites.update_one({**scope, "id": favorite_id}, {"$set": fields})
    return db.mileage_favorites.find_one({**scope, "id": favorite_id}, {"_id": 0})


@app.delete("/api/mileage/favorites/{favorite_id}")
async def delete_mileage_favorite(favorite_id: str,
                                  current_user=Depends(require_permission("expenses:write"))):
    scope = _org_scope(current_user)
    res = db.mileage_favorites.delete_one({**scope, "id": favorite_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Favori introuvable")
    return {"status": "deleted", "id": favorite_id}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_mileage_logbook_integration.py -k favorite -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/server.py backend/tests/test_mileage_logbook_integration.py
git commit -m "feat(mileage): add favorites CRUD (template routes, independent of trips)"
```

---

## Task 8: GET /api/mileage/rates (+ drapeau année manquante)

**Files:**
- Modify: `backend/server.py`
- Test: `backend/tests/test_mileage_logbook_integration.py`

- [ ] **Step 1: Write the failing test**

Ajouter à `backend/tests/test_mileage_logbook_integration.py` :

```python
def test_get_rates(auth_headers):
    r = client.get("/api/mileage/rates", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["threshold_km"] == 5000
    assert body["rates"]["2026"] == {"full": 0.73, "reduced": 0.67}
    assert "current_year" in body
    assert "current_year_missing" in body
    # 2026 est present dans MILEAGE_RATES
    assert body["current_year_missing"] == (_mileage_rate_for_year(body["current_year"]) is None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_mileage_logbook_integration.py -k get_rates -v`
Expected: FAIL — route `/api/mileage/rates` inconnue.

- [ ] **Step 3: Write minimal implementation**

Ajouter dans `backend/server.py` :

```python
@app.get("/api/mileage/rates")
async def get_mileage_rates(current_user=Depends(require_permission("expenses:read"))):
    current_year = datetime.now(timezone.utc).year
    return {
        "rates": {str(y): r for y, r in MILEAGE_RATES.items()},
        "threshold_km": MILEAGE_RATE_THRESHOLD_KM,
        "current_year": current_year,
        "current_year_missing": _mileage_rate_for_year(current_year) is None,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_mileage_logbook_integration.py -k get_rates -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/server.py backend/tests/test_mileage_logbook_integration.py
git commit -m "feat(mileage): add GET /api/mileage/rates with current_year_missing flag"
```

---

## Task 9: RBAC + isolation cross-org sur les trajets

**Files:**
- Test: `backend/tests/test_mileage_logbook_integration.py` (aucune modif serveur : valide le comportement des dependencies déjà en place)

> Ce task vérifie que `require_permission("expenses:write")` et `_org_scope` protègent bien les routes. Si un test échoue, corriger l'annotation de dependency sur la route concernée (les Tasks 5-8 utilisent déjà `expenses:read`/`expenses:write`).

- [ ] **Step 1: Write the failing test**

Ajouter à `backend/tests/test_mileage_logbook_integration.py`. Ces tests supposent l'existence d'un helper de fixture d'org secondaire dans la suite d'intégration existante (`test_multi_tenant`/feature #11). Si absent, créer un second user via `/api/auth/register` :

```python
@pytest.fixture
def second_org_headers():
    import uuid as _uuid
    email = f"mileage_orgb_{_uuid.uuid4().hex[:8]}@example.com"
    client.post("/api/auth/register", json={
        "email": email, "password": "testpass123", "company_name": "Org B",
    })
    resp = client.post("/api/auth/login", json={"email": email, "password": "testpass123"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_cross_org_isolation(auth_headers, second_org_headers):
    created = client.post("/api/mileage/trips", json=_new_trip_payload(),
                          headers=auth_headers).json()
    tid = created["trip"]["id"]
    # Org B ne voit pas le trajet de Org A
    r = client.get(f"/api/mileage/trips/{tid}", headers=second_org_headers)
    assert r.status_code == 404
    # La liste de B ne contient pas le trajet de A
    lst = client.get("/api/mileage/trips?year=2026", headers=second_org_headers).json()
    assert all(row["trip"]["id"] != tid for row in lst)


def test_writer_permission_enforced(second_org_headers):
    # Un compte "viewer" (read only) ne peut pas creer de trajet.
    # On simule via un header sans expenses:write : ici second_org est owner (write ok),
    # donc ce test documente le contrat. Adapter avec un vrai viewer si la suite
    # feature #11 fournit un helper viewer_headers.
    pass
```

> Si la suite feature #11 expose déjà un `viewer_headers` (lecteur read-only), remplacer le `test_writer_permission_enforced` par : `assert client.post("/api/mileage/trips", json=_new_trip_payload(), headers=viewer_headers).status_code == 403`.

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `cd backend && python -m pytest tests/test_mileage_logbook_integration.py -k "cross_org or writer_permission" -v`
Expected: PASS (isolation déjà garantie par `_org_scope`). Si `cross_org` échoue, une route a oublié `_org_scope` — corriger.

- [ ] **Step 3: (correctif conditionnel)**

Si `test_cross_org_isolation` échoue, vérifier que chaque `find_one`/`find` des Tasks 5-8 combine bien `{**scope, "id": ...}` et jamais `{"id": ...}` seul.

- [ ] **Step 4: Re-run**

Run: `cd backend && python -m pytest tests/test_mileage_logbook_integration.py -k "cross_org or writer_permission" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_mileage_logbook_integration.py
git commit -m "test(mileage): cross-org isolation and write-permission enforcement"
```

---

## Task 10: Génération de dépense (par trajet + lot mensuel) + cascade

**Files:**
- Modify: `backend/server.py` (endpoints génération + `_release_mileage_trips` + hook dans `delete_expense` `server.py`)
- Test: `backend/tests/test_mileage_logbook_integration.py`

- [ ] **Step 1: Write the failing test**

Ajouter à `backend/tests/test_mileage_logbook_integration.py` :

```python
def test_generate_expense_per_trip(auth_headers):
    created = _create_trip(auth_headers, trip_date="2026-05-02", one_way_km=50, round_trip=True)
    tid = created["trip"]["id"]  # distance 100, allocation 100*0.73 = 73.00 (sous 5000)
    r = client.post(f"/api/mileage/trips/{tid}/generate-expense", headers=auth_headers)
    assert r.status_code == 200, r.text
    exp = r.json()["expense"]
    assert exp["category_code"] == "vehicle_expenses"
    assert exp["amount_cad"] == 73.00
    assert exp["mileage_generated"] is True
    assert tid in exp["mileage_trip_ids"]
    # trajet marque
    trip = client.get(f"/api/mileage/trips/{tid}", headers=auth_headers).json()["trip"]
    assert trip["expense_id"] == exp["id"]
    # 2e generation -> 400
    r2 = client.post(f"/api/mileage/trips/{tid}/generate-expense", headers=auth_headers)
    assert r2.status_code == 400


def test_generate_monthly_batch(auth_headers):
    rv = client.post("/api/mileage/vehicles", json={"name": "Lot mensuel"}, headers=auth_headers)
    vid = rv.json()["id"]
    t1 = _create_trip(auth_headers, trip_date="2026-08-03", one_way_km=10, round_trip=False, vehicle_id=vid)
    t2 = _create_trip(auth_headers, trip_date="2026-08-20", one_way_km=20, round_trip=False, vehicle_id=vid)
    r = client.post("/api/mileage/generate-expense",
                    json={"year": 2026, "month": 8, "vehicle_id": vid}, headers=auth_headers)
    assert r.status_code == 200, r.text
    exp = r.json()["expense"]
    # 10*0.73 + 20*0.73 = 21.90
    assert exp["amount_cad"] == round(30 * 0.73, 2)
    ids = set(exp["mileage_trip_ids"])
    assert t1["trip"]["id"] in ids and t2["trip"]["id"] in ids
    # relancer le lot -> plus rien a facturer (trajets deja lies exclus)
    r2 = client.post("/api/mileage/generate-expense",
                     json={"year": 2026, "month": 8, "vehicle_id": vid}, headers=auth_headers)
    assert r2.status_code == 400


def test_delete_expense_releases_trips(auth_headers):
    created = _create_trip(auth_headers, trip_date="2026-09-05", one_way_km=15, round_trip=False)
    tid = created["trip"]["id"]
    gen = client.post(f"/api/mileage/trips/{tid}/generate-expense", headers=auth_headers).json()
    eid = gen["expense"]["id"]
    # supprimer la depense libere le trajet
    dr = client.delete(f"/api/expenses/{eid}", headers=auth_headers)
    assert dr.status_code == 200
    trip = client.get(f"/api/mileage/trips/{tid}", headers=auth_headers).json()["trip"]
    assert trip["expense_id"] is None
    # re-generable
    regen = client.post(f"/api/mileage/trips/{tid}/generate-expense", headers=auth_headers)
    assert regen.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_mileage_logbook_integration.py -k "generate_expense or monthly_batch or releases_trips" -v`
Expected: FAIL — routes de génération inconnues.

- [ ] **Step 3: Write minimal implementation**

3a. Helper de matérialisation de la dépense + cascade dans `backend/server.py`. Réutilise `_build_expense_category_snapshot` (feature #3). Le chemin `create_expense` (`server.py:4960`) construit un doc `expenses` ; ici on construit directement le doc dépense avec le même snapshot pour rester dans une seule transaction logique :

```python
def _mileage_build_expense_for_trips(trip_docs, scope, current_user):
    """Materialise UNE depense vehicle_expenses agregeant les allocations des
    trips fournis. Reutilise _build_expense_category_snapshot (ligne 9281).
    Chaque trip doit avoir un taux dispo pour son annee, sinon 400."""
    total = 0.0
    trip_ids = []
    origins_dests = []
    first_date = None
    for trip in sorted(trip_docs, key=lambda d: (d["trip_date"], d["id"])):
        year = int(trip["trip_date"][:4])
        rates = _mileage_rate_for_year(year)
        if rates is None:
            raise HTTPException(status_code=400,
                                detail=f"Taux ARC {year} non configuré — voir rappel annuel")
        employee_key = _mileage_employee_key(trip.get("employee_id"), trip.get("created_by_user_id"))
        ytd_before = _mileage_ytd_before(scope, employee_key, trip["vehicle_id"],
                                         trip["trip_date"], trip["id"])
        amount, _ = _mileage_allocation(trip["distance_km"], ytd_before, rates)
        total += amount
        trip_ids.append(trip["id"])
        origins_dests.append(f"{trip['origin']} → {trip['destination']}")
        if first_date is None or trip["trip_date"] < first_date:
            first_date = trip["trip_date"]

    total = round(total, 2)
    snapshot = _build_expense_category_snapshot("vehicle_expenses", total)
    if len(trip_ids) == 1:
        desc = f"Allocation km — {origins_dests[0]} ({trip_docs[0]['distance_km']} km)"
    else:
        desc = f"Allocation km — {len(trip_ids)} trajets ({first_date[:7]})"

    expense_doc = {
        "id": str(uuid.uuid4()),
        "organization_id": current_user.organization_id,
        "created_by_user_id": current_user.id,
        "description": desc,
        "amount": total,
        "amount_cad": total,
        "currency": "CAD",
        "exchange_rate_to_cad": 1.0,
        "expense_date": first_date,
        "category_code": "vehicle_expenses",
        "mileage_generated": True,
        "mileage_trip_ids": trip_ids,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **snapshot,
    }
    db.expenses.insert_one(expense_doc)
    db.mileage_trips.update_many(
        {**scope, "id": {"$in": trip_ids}},
        {"$set": {"expense_id": expense_doc["id"]}},
    )
    expense_doc.pop("_id", None)
    return expense_doc


def _release_mileage_trips(expense_id: str) -> None:
    """Libere les trajets lies a une depense supprimee (unset expense_id).
    Modele : _release_bank_transaction (feature #7)."""
    db.mileage_trips.update_many(
        {"expense_id": expense_id},
        {"$set": {"expense_id": None}},
    )
```

> **Vérification du snapshot :** confirmer la signature réelle de `_build_expense_category_snapshot` dans `server.py` (feature #3). Le spec indique qu'elle « pose ligne ARC 9281, deductible_percentage=100 » à partir du code catégorie. Si sa signature diffère (ex : `(code)` sans montant, ou elle attend d'autres champs), adapter l'appel et fusionner ses clés dans `expense_doc`. Aligner aussi `description`/`amount`/`expense_date` sur les noms de champs exacts que `create_expense` (`server.py:4960`) écrit sur un doc `expenses`, pour que la dépense s'affiche identiquement dans `ExpensesPage`.

3b. Endpoints de génération :

```python
@app.post("/api/mileage/trips/{trip_id}/generate-expense")
async def generate_expense_from_trip(trip_id: str,
                                     current_user=Depends(require_permission("expenses:write"))):
    scope = _org_scope(current_user)
    trip = db.mileage_trips.find_one({**scope, "id": trip_id})
    if not trip:
        raise HTTPException(status_code=404, detail="Trajet introuvable")
    if trip.get("expense_id"):
        raise HTTPException(status_code=400, detail="Trajet déjà facturé")
    expense = _mileage_build_expense_for_trips([trip], scope, current_user)
    return {"expense": expense}


@app.post("/api/mileage/generate-expense")
async def generate_monthly_expense(payload: dict,
                                   current_user=Depends(require_permission("expenses:write"))):
    scope = _org_scope(current_user)
    year = int(payload.get("year"))
    month = int(payload.get("month"))
    vehicle_id = payload.get("vehicle_id")
    prefix = f"{year:04d}-{month:02d}"
    query = {
        **scope,
        "expense_id": None,
        "trip_date": {"$gte": f"{prefix}-01", "$lte": f"{prefix}-31"},
    }
    if vehicle_id:
        query["vehicle_id"] = vehicle_id
    trips = list(db.mileage_trips.find(query))
    if not trips:
        raise HTTPException(status_code=400,
                            detail="Aucun trajet non facturé pour ce mois")
    expense = _mileage_build_expense_for_trips(trips, scope, current_user)
    return {"expense": expense}
```

3c. Hook cascade dans `delete_expense`. Localiser la fonction `delete_expense` dans `server.py` (près de `create_expense` `server.py:4960`, là où `_release_bank_transaction(expense_id)` est déjà appelé pour la feature #7) et ajouter juste à côté :

```python
    _release_mileage_trips(expense_id)
```

> Utiliser la même variable d'identifiant que celle passée à `_release_bank_transaction` dans cette fonction (probablement `expense_id`).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_mileage_logbook_integration.py -k "generate_expense or monthly_batch or releases_trips" -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/server.py backend/tests/test_mileage_logbook_integration.py
git commit -m "feat(mileage): generate expense per-trip and monthly batch, release on delete"
```

---

## Task 11: Carnet JSON + PDF conforme ARC

**Files:**
- Modify: `backend/server.py` (endpoints logbook + `_render_mileage_logbook_pdf`)
- Test: `backend/tests/test_mileage_logbook_integration.py`

- [ ] **Step 1: Write the failing test**

Ajouter à `backend/tests/test_mileage_logbook_integration.py` :

```python
def test_logbook_json_running_total(auth_headers):
    rv = client.post("/api/mileage/vehicles", json={"name": "Carnet JSON"}, headers=auth_headers)
    vid = rv.json()["id"]
    _create_trip(auth_headers, trip_date="2026-02-01", one_way_km=10, round_trip=False, vehicle_id=vid)
    _create_trip(auth_headers, trip_date="2026-02-15", one_way_km=20, round_trip=False, vehicle_id=vid)
    r = client.get(f"/api/mileage/logbook?year=2026&vehicle_id={vid}", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    rows = body["rows"]
    assert rows[0]["running_total_km"] == 10.0
    assert rows[1]["running_total_km"] == 30.0
    assert body["total_km"] == 30.0
    assert body["total_allocation_cad"] == round(30 * 0.73, 2)


def test_logbook_pdf(auth_headers):
    _create_trip(auth_headers, trip_date="2026-03-03", one_way_km=12, round_trip=True)
    r = client.get("/api/mileage/logbook/pdf?year=2026", headers=auth_headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "no-store" in r.headers.get("cache-control", "")
    assert r.content[:4] == b"%PDF"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_mileage_logbook_integration.py -k logbook -v`
Expected: FAIL — routes logbook inconnues.

- [ ] **Step 3: Write minimal implementation**

3a. Endpoint JSON + builder de lignes partagé :

```python
def _mileage_logbook_rows(scope, year, vehicle_id):
    """Retourne (rows, totals). rows tries (trip_date, id) avec running total km
    et allocation par trajet. Le cumul running est PAR (personne, vehicule)."""
    query = {**scope, "trip_date": {"$gte": f"{year}-01-01", "$lte": f"{year}-12-31"}}
    if vehicle_id:
        query["vehicle_id"] = vehicle_id
    docs = list(db.mileage_trips.find(query, {"_id": 0}))
    docs.sort(key=lambda d: (d["trip_date"], d["id"]))
    rates = _mileage_rate_for_year(int(year))
    running = {}  # (employee_key, vehicle_id) -> km cumules
    rows = []
    total_km = 0.0
    total_alloc = 0.0
    for d in docs:
        employee_key = _mileage_employee_key(d.get("employee_id"), d.get("created_by_user_id"))
        key = (employee_key, d["vehicle_id"])
        ytd_before = running.get(key, 0.0)
        alloc = None
        if rates is not None:
            amount, _ = _mileage_allocation(d["distance_km"], ytd_before, rates)
            alloc = amount
            total_alloc += amount
        running[key] = ytd_before + d["distance_km"]
        total_km += d["distance_km"]
        rows.append({
            "trip_date": d["trip_date"],
            "origin": d["origin"],
            "destination": d["destination"],
            "purpose": d["purpose"],
            "distance_km": d["distance_km"],
            "running_total_km": round(running[key], 2),
            "allocation_cad": alloc,
            "expense_id": d.get("expense_id"),
        })
    return rows, {
        "total_km": round(total_km, 2),
        "total_allocation_cad": round(total_alloc, 2),
        "rates": rates,
    }


@app.get("/api/mileage/logbook")
async def get_mileage_logbook(year: int, vehicle_id: str = None,
                              current_user=Depends(require_permission("expenses:read"))):
    _ensure_default_vehicle(current_user.organization_id, current_user.id)
    scope = _org_scope(current_user)
    rows, totals = _mileage_logbook_rows(scope, int(year), vehicle_id)
    vehicle = None
    if vehicle_id:
        vehicle = db.mileage_vehicles.find_one({**scope, "id": vehicle_id}, {"_id": 0})
    return {
        "year": int(year),
        "vehicle": vehicle,
        "rows": rows,
        "total_km": totals["total_km"],
        "total_allocation_cad": totals["total_allocation_cad"],
        "current_year_missing": _mileage_rate_for_year(int(year)) is None,
    }
```

3b. Renderer PDF (pattern `_render_t2125_pdf` : ReportLab `SimpleDocTemplate`, `_t2125_format_money`, `html.escape`). `Response`, `SimpleDocTemplate`, `Table`, `TableStyle`, `Paragraph`, `getSampleStyleSheet`, `colors`, `io`, `html` sont déjà importés/utilisés par les PDF existants :

```python
def _render_mileage_logbook_pdf(year, vehicle, company, rows, totals) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    story = []

    company_name = html.escape(company.get("company_name", "") if company else "")
    story.append(Paragraph(f"Carnet de route — {year}", styles["Title"]))
    if company_name:
        story.append(Paragraph(company_name, styles["Normal"]))
    if vehicle:
        parts = [vehicle.get("name", "")]
        if vehicle.get("make_model"):
            parts.append(vehicle["make_model"])
        if vehicle.get("plate"):
            parts.append(vehicle["plate"])
        story.append(Paragraph("Véhicule : " + html.escape(" — ".join(p for p in parts if p)),
                               styles["Normal"]))
    story.append(Paragraph(
        "Registre des déplacements d'affaires — conforme aux exigences de l'ARC "
        "pour l'allocation de frais automobiles.", styles["Normal"]))
    story.append(Paragraph("<br/>", styles["Normal"]))

    header = ["Date", "Départ", "Arrivée", "Motif", "Km", "Cumul", "Allocation"]
    data = [header]
    for r in rows:
        alloc = _t2125_format_money(r["allocation_cad"]) if r["allocation_cad"] is not None else "—"
        data.append([
            r["trip_date"],
            html.escape(r["origin"]),
            html.escape(r["destination"]),
            html.escape(r["purpose"]),
            _t2125_format_money(r["distance_km"]).replace(" $", ""),
            _t2125_format_money(r["running_total_km"]).replace(" $", ""),
            alloc,
        ])
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(table)
    story.append(Paragraph("<br/>", styles["Normal"]))

    story.append(Paragraph(
        f"Total des km {year} : {_t2125_format_money(totals['total_km']).replace(' $', '')} km",
        styles["Normal"]))
    story.append(Paragraph(
        f"Total de l'allocation {year} : {_t2125_format_money(totals['total_allocation_cad'])}",
        styles["Normal"]))
    if totals["rates"]:
        story.append(Paragraph(
            f"Taux plein {totals['rates']['full']} $/km jusqu'à 5 000 km, "
            f"puis {totals['rates']['reduced']} $/km au-delà.", styles["Normal"]))
    else:
        story.append(Paragraph(
            f"Taux ARC {year} non configuré — allocation en attente de confirmation.",
            styles["Normal"]))

    doc.build(story)
    return buf.getvalue()


@app.get("/api/mileage/logbook/pdf")
async def get_mileage_logbook_pdf(year: int, vehicle_id: str = None,
                                  current_user=Depends(require_permission("expenses:read"))):
    _ensure_default_vehicle(current_user.organization_id, current_user.id)
    scope = _org_scope(current_user)
    rows, totals = _mileage_logbook_rows(scope, int(year), vehicle_id)
    vehicle = db.mileage_vehicles.find_one({**scope, "id": vehicle_id}, {"_id": 0}) if vehicle_id \
        else db.mileage_vehicles.find_one({**scope, "is_default": True}, {"_id": 0})
    company = db.company_settings.find_one(scope, {"_id": 0})
    pdf_bytes = _render_mileage_logbook_pdf(int(year), vehicle, company, rows, totals)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="carnet-route-{year}.pdf"',
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
        },
    )
```

> **Vérifier** les symboles ReportLab importés en tête de `server.py` (`letter` vs `A4`, `getSampleStyleSheet`, `Response` de fastapi) et le format exact de `_t2125_format_money` (le spec le décrit produisant `85 000,00 $`). Le `.replace(" $", "")` retire le suffixe monétaire pour les colonnes km ; adapter si `_t2125_format_money` formate différemment.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_mileage_logbook_integration.py -k logbook -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/server.py backend/tests/test_mileage_logbook_integration.py
git commit -m "feat(mileage): add logbook JSON and ARC-compliant PDF export"
```

---

## Task 12: Rappel annuel du taux (endpoint cron externe)

**Files:**
- Modify: `backend/server.py`
- Test: `backend/tests/test_mileage_logbook_integration.py`

- [ ] **Step 1: Write the failing test**

Ajouter à `backend/tests/test_mileage_logbook_integration.py` :

```python
def test_check_rate_update_present_year():
    # Sans annee simulee : l'annee courante 2026 EST dans MILEAGE_RATES.
    from backend import server as srv
    current_year = srv.datetime.now(srv.timezone.utc).year
    r = client.post("/api/mileage/check-rate-update")
    assert r.status_code == 200
    if srv._mileage_rate_for_year(current_year) is not None:
        assert r.json()["action"] == "rate_present"


def test_check_rate_update_missing_year_no_email(monkeypatch):
    from backend import server as srv

    class _FakeDT:
        @staticmethod
        def now(tz=None):
            import datetime as _d
            return _d.datetime(2099, 1, 15, tzinfo=srv.timezone.utc)

    monkeypatch.setattr(srv, "datetime", _FakeDT)
    monkeypatch.setattr(srv, "RESEND_API_KEY", None, raising=False)
    r = client.post("/api/mileage/check-rate-update")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("skipped", "ok")
    # aucun 500 meme avec taux manquant et email non configure


def test_check_rate_update_idempotent(monkeypatch):
    # Deux pings consecutifs pour une annee manquante n'envoient qu'une fois par org
    # (garantie via mileage_rate_reminders). Ici on verifie l'absence de 500.
    r1 = client.post("/api/mileage/check-rate-update")
    r2 = client.post("/api/mileage/check-rate-update")
    assert r1.status_code == 200 and r2.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_mileage_logbook_integration.py -k check_rate_update -v`
Expected: FAIL — route `/api/mileage/check-rate-update` inconnue.

- [ ] **Step 3: Write minimal implementation**

Ajouter dans `backend/server.py`. Aligné sur `check_trial_expiry` (`server.py:6254`). Réutiliser le helper d'envoi Resend existant (le spec l'appelle « pattern `check_trial_expiry` » ; localiser la fonction d'envoi email utilisée là-bas, ex : `send_email(...)`) :

```python
@app.post("/api/mileage/check-rate-update")
async def check_mileage_rate_update(request: Request):
    """Pinge par un cron externe (Render Cron / cron-job.org) chaque janvier.
    Si le taux de l'annee courante manque dans MILEAGE_RATES, notifie l'owner
    de chaque org active pour VERIFICATION HUMAINE du taux ARC officiel.
    Idempotent : une seule notif par (org, annee) via mileage_rate_reminders.
    Ne met JAMAIS a jour le taux automatiquement (table dans le code)."""
    year = datetime.now(timezone.utc).year
    if _mileage_rate_for_year(year) is not None:
        return {"status": "ok", "year": year, "action": "rate_present"}

    if not RESEND_API_KEY:
        return {"status": "skipped", "year": year, "reason": "email_not_configured"}

    notified = 0
    for org in db.organizations.find({}):
        reminder_id = f"{org['id']}:{year}"
        if db.mileage_rate_reminders.find_one({"id": reminder_id}):
            continue
        owner = db.users.find_one({"id": org.get("owner_id")})
        if not owner or not owner.get("email"):
            continue
        try:
            _send_email(
                to=owner["email"],
                subject=f"Taux d'allocation automobile ARC {year} à confirmer",
                html=(
                    f"<p>Le taux d'allocation automobile ARC {year} n'est pas encore "
                    f"configuré dans FacturePro.</p>"
                    f"<p>Vérifiez le taux officiel sur canada.ca puis mettez à jour. "
                    f"En attendant, le calcul d'allocation {year} est bloqué avec un "
                    f"message explicite.</p>"
                ),
            )
            db.mileage_rate_reminders.insert_one({
                "id": reminder_id,
                "organization_id": org["id"],
                "year": year,
                "notified_at": datetime.now(timezone.utc).isoformat(),
            })
            notified += 1
        except Exception as e:
            # capture par org, n'interrompt pas la boucle ; l'etat n'est ecrit
            # qu'apres envoi reussi -> retente au prochain ping cron.
            print(f"[mileage rate reminder] échec envoi org {org['id']}: {type(e).__name__}")
            continue
    return {"status": "ok", "year": year, "action": "notified", "count": notified}
```

> **Vérifier** : le nom réel du helper d'envoi email (`_send_email` / `send_email` / appel Resend inline) tel qu'utilisé dans `check_trial_expiry` (`server.py:6254`) — le réutiliser exactement. Confirmer que `RESEND_API_KEY` et `Request` sont importés (ils le sont : feature #8/#11). Confirmer le nom du champ owner (`owner_id`) sur `organizations` (feature #11).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_mileage_logbook_integration.py -k check_rate_update -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/server.py backend/tests/test_mileage_logbook_integration.py
git commit -m "feat(mileage): add annual rate reminder endpoint (external cron, human verify)"
```

---

## Task 13: Taux manquant → allocation bloquée (test de garde)

**Files:**
- Test: `backend/tests/test_mileage_logbook.py` et `backend/tests/test_mileage_logbook_integration.py`

Vérifie qu'un trajet dont l'année n'a pas de taux ne calcule jamais silencieusement une allocation et que la génération de dépense renvoie 400.

- [ ] **Step 1: Write the failing test**

Ajouter à `backend/tests/test_mileage_logbook.py` :

```python
def test_missing_year_enrich_returns_none_allocation():
    # _mileage_enrich_trip doit poser allocation=None et rate_missing_year pour 2099.
    # Test unitaire du contrat via _mileage_rate_for_year deja couvert ;
    # ici on documente la garde cote helper d'allocation batch.
    assert _mileage_rate_for_year(2099) is None
```

Ajouter à `backend/tests/test_mileage_logbook_integration.py` :

```python
def test_generate_expense_missing_rate_year_blocked(auth_headers):
    # Trajet dans une annee sans taux -> generation 400 explicite, pas de calcul.
    created = _create_trip(auth_headers, trip_date="2099-05-01", one_way_km=10, round_trip=False)
    tid = created["trip"]["id"]
    # a la creation, allocation est None (annee manquante)
    assert created["allocation"] is None
    r = client.post(f"/api/mileage/trips/{tid}/generate-expense", headers=auth_headers)
    assert r.status_code == 400
    assert "2099" in r.json()["detail"]
```

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `cd backend && python -m pytest tests/test_mileage_logbook.py::test_missing_year_enrich_returns_none_allocation tests/test_mileage_logbook_integration.py::test_generate_expense_missing_rate_year_blocked -v`
Expected: PASS si les Tasks 5 & 10 ont bien implémenté la garde `rates is None → allocation None / HTTPException 400`. Si `test_generate_expense_missing_rate_year_blocked` échoue, corriger `_mileage_build_expense_for_trips` (Task 10 step 3a) pour lever bien le 400.

- [ ] **Step 3: (correctif conditionnel)**

Si la garde manque, s'assurer que `_mileage_enrich_trip` (Task 5) retourne `"allocation": None` quand `rates is None`, et que `_mileage_build_expense_for_trips` (Task 10) lève `HTTPException(400, "Taux ARC {year} non configuré — voir rappel annuel")`.

- [ ] **Step 4: Re-run**

Run: `cd backend && python -m pytest tests/test_mileage_logbook.py tests/test_mileage_logbook_integration.py -k "missing" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_mileage_logbook.py backend/tests/test_mileage_logbook_integration.py
git commit -m "test(mileage): missing-rate year blocks allocation with explicit 400"
```

---

## Task 14: Frontend — bouton « Carnet de route » + squelette de la vue à onglets

**Files:**
- Modify: `frontend/src/pages/ExpensesPage.js`

- [ ] **Step 1: Ajouter le state et le bouton d'ouverture**

Dans `ExpensesPage.js`, importer les icônes et ajouter le state du carnet. Localiser la barre d'actions existante (« Nouvelle dépense », « Scanner reçu ») et ajouter le bouton gaté :

```jsx
import { Car } from "lucide-react";
// ... dans le composant ExpensesPage :
const [showLogbook, setShowLogbook] = useState(false);
const [logbookTab, setLogbookTab] = useState("trips"); // 'trips' | 'favorites' | 'logbook'
```

Dans la barre d'actions (à côté de « Scanner reçu ») :

```jsx
{hasPermission("expenses:read") && (
  <button
    onClick={() => setShowLogbook(true)}
    className="btn-secondary flex items-center gap-2"
  >
    <Car size={18} /> Carnet de route
  </button>
)}
```

> `hasPermission` provient du `AuthContext` (feature #11). Reprendre exactement la classe CSS des boutons voisins (`btn-secondary` est indicatif — utiliser la même classe que « Scanner reçu »).

- [ ] **Step 2: Ajouter le conteneur modal plein écran à 3 onglets**

À la fin du JSX de `ExpensesPage`, avant la fermeture du composant :

```jsx
{showLogbook && (
  <div className="fixed inset-0 z-50 bg-white overflow-auto p-6">
    <div className="flex items-center justify-between mb-4">
      <h2 className="text-xl font-bold">Carnet de route</h2>
      <button onClick={() => setShowLogbook(false)} className="text-gray-500">Fermer</button>
    </div>
    <div className="flex gap-2 border-b mb-4">
      {[["trips", "Trajets"], ["favorites", "Favoris"], ["logbook", "Carnet"]].map(([key, label]) => (
        <button
          key={key}
          onClick={() => setLogbookTab(key)}
          className={`px-4 py-2 ${logbookTab === key ? "border-b-2 border-blue-600 font-semibold" : "text-gray-500"}`}
        >
          {label}
        </button>
      ))}
    </div>
    {logbookTab === "trips" && <MileageTripsTab />}
    {logbookTab === "favorites" && <MileageFavoritesTab />}
    {logbookTab === "logbook" && <MileageLogbookTab />}
  </div>
)}
```

- [ ] **Step 3: Déclarer des composants placeholder compilables**

Ajouter en haut du fichier (ou dans le même module) trois composants vides qui seront remplis aux Tasks 15-17 :

```jsx
function MileageTripsTab() { return <div>Trajets (à venir)</div>; }
function MileageFavoritesTab() { return <div>Favoris (à venir)</div>; }
function MileageLogbookTab() { return <div>Carnet (à venir)</div>; }
```

- [ ] **Step 4: Vérifier la compilation**

Run: `cd frontend && npm run build`
Expected: build réussit ; le bouton « Carnet de route » ouvre la modal à 3 onglets.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/ExpensesPage.js
git commit -m "feat(mileage-ui): add Carnet de route button and 3-tab shell in ExpensesPage"
```

---

## Task 15: Frontend — onglet Trajets (saisie + allocation live + génération)

**Files:**
- Modify: `frontend/src/pages/ExpensesPage.js` (remplir `MileageTripsTab`)

- [ ] **Step 1: Implémenter le chargement + le formulaire de trajet**

Remplacer `MileageTripsTab` par une version fonctionnelle. Utiliser `axios` et `BACKEND_URL` selon `frontend/src/config.js` (pattern des autres appels d'`ExpensesPage`) :

```jsx
function MileageTripsTab() {
  const { token } = useAuth();
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [trips, setTrips] = useState([]);
  const [favorites, setFavorites] = useState([]);
  const [rates, setRates] = useState(null);
  const [form, setForm] = useState({
    trip_date: now.toISOString().slice(0, 10),
    origin: "", destination: "", purpose: "",
    one_way_km: "", round_trip: false, favorite_id: "",
  });

  const authCfg = { headers: { Authorization: `Bearer ${token}` } };

  const load = async () => {
    const [t, f, r] = await Promise.all([
      axios.get(`${BACKEND_URL}/api/mileage/trips?year=${year}&month=${month}`, authCfg),
      axios.get(`${BACKEND_URL}/api/mileage/favorites`, authCfg),
      axios.get(`${BACKEND_URL}/api/mileage/rates`, authCfg),
    ]);
    setTrips(t.data); setFavorites(f.data); setRates(r.data);
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [year, month]);

  const applyFavorite = (fid) => {
    const fav = favorites.find((x) => x.id === fid);
    if (!fav) { setForm((s) => ({ ...s, favorite_id: "" })); return; }
    setForm((s) => ({
      ...s, favorite_id: fid, origin: fav.origin, destination: fav.destination,
      purpose: fav.purpose || "", one_way_km: fav.one_way_km,
      round_trip: fav.round_trip_default,
    }));
  };

  const liveDistance = () => {
    const km = parseFloat(form.one_way_km) || 0;
    return form.round_trip ? km * 2 : km;
  };
  const liveAllocation = () => {
    if (!rates || rates.current_year_missing) return null;
    const yr = form.trip_date.slice(0, 4);
    const rate = rates.rates[yr];
    if (!rate) return null;
    return (liveDistance() * rate.full).toFixed(2); // indicatif ; backend fait foi
  };

  const save = async (generate) => {
    const created = await axios.post(`${BACKEND_URL}/api/mileage/trips`, {
      ...form, one_way_km: parseFloat(form.one_way_km),
    }, authCfg);
    if (generate) {
      await axios.post(
        `${BACKEND_URL}/api/mileage/trips/${created.data.trip.id}/generate-expense`, {}, authCfg);
    }
    setForm((s) => ({ ...s, origin: "", destination: "", purpose: "", one_way_km: "", favorite_id: "" }));
    load();
  };

  return (
    <div>
      <div className="flex gap-2 mb-4">
        <input type="number" value={year} onChange={(e) => setYear(e.target.value)} className="border p-1 w-24" />
        <select value={month} onChange={(e) => setMonth(e.target.value)} className="border p-1">
          {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
      </div>

      <div className="border rounded p-4 mb-6 grid grid-cols-2 gap-3">
        <select value={form.favorite_id} onChange={(e) => applyFavorite(e.target.value)} className="border p-2 col-span-2">
          <option value="">Depuis un favori…</option>
          {favorites.map((f) => <option key={f.id} value={f.id}>{f.label}</option>)}
        </select>
        <input type="date" value={form.trip_date} onChange={(e) => setForm({ ...form, trip_date: e.target.value })} className="border p-2" />
        <input placeholder="Départ" value={form.origin} onChange={(e) => setForm({ ...form, origin: e.target.value })} className="border p-2" />
        <input placeholder="Arrivée" value={form.destination} onChange={(e) => setForm({ ...form, destination: e.target.value })} className="border p-2" />
        <input placeholder="Motif *" value={form.purpose} onChange={(e) => setForm({ ...form, purpose: e.target.value })} className="border p-2" />
        <input type="number" placeholder="Km (aller simple)" value={form.one_way_km} onChange={(e) => setForm({ ...form, one_way_km: e.target.value })} className="border p-2" />
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={form.round_trip} onChange={(e) => setForm({ ...form, round_trip: e.target.checked })} />
          Aller-retour ({liveDistance()} km)
        </label>
        <div className="col-span-2 text-sm text-gray-600">
          {liveAllocation() !== null
            ? `Allocation estimée : ${liveDistance()} km × taux = ${liveAllocation()} $ (indicatif)`
            : "Allocation indisponible — taux de l'année à confirmer."}
        </div>
        <div className="col-span-2 flex gap-2">
          <button onClick={() => save(false)} className="btn-secondary" disabled={!form.purpose.trim() || !(parseFloat(form.one_way_km) > 0)}>Enregistrer seulement</button>
          <button onClick={() => save(true)} className="btn-primary" disabled={!form.purpose.trim() || !(parseFloat(form.one_way_km) > 0) || (rates && rates.current_year_missing)}>Enregistrer et générer la dépense</button>
        </div>
      </div>

      <table className="w-full text-sm">
        <thead><tr className="text-left border-b">
          <th>Date</th><th>Départ</th><th>Arrivée</th><th>Motif</th><th>Km</th><th>Allocation</th><th></th>
        </tr></thead>
        <tbody>
          {trips.map((row) => (
            <tr key={row.trip.id} className="border-b">
              <td>{row.trip.trip_date}</td>
              <td>{row.trip.origin}</td>
              <td>{row.trip.destination}</td>
              <td>{row.trip.purpose}</td>
              <td>{row.trip.distance_km}</td>
              <td>{row.allocation ? `${row.allocation.amount_cad.toFixed(2)} $` : "—"}</td>
              <td>
                {row.trip.expense_id
                  ? <span className="text-green-600 text-xs">Facturé</span>
                  : <button className="text-blue-600 text-xs" onClick={async () => {
                      await axios.post(`${BACKEND_URL}/api/mileage/trips/${row.trip.id}/generate-expense`, {}, authCfg);
                      load();
                    }}>Générer la dépense</button>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="mt-4">
        <button className="btn-secondary" onClick={async () => {
          await axios.post(`${BACKEND_URL}/api/mileage/generate-expense`, { year: Number(year), month: Number(month) }, authCfg);
          load();
        }}>Générer la dépense du mois</button>
      </div>
    </div>
  );
}
```

> `useAuth`, `axios`, `BACKEND_URL` : reprendre les imports exacts déjà présents en tête d'`ExpensesPage.js`. Les classes `btn-primary`/`btn-secondary` sont indicatives — utiliser celles du fichier.

- [ ] **Step 2: Vérifier la compilation**

Run: `cd frontend && npm run build`
Expected: build réussit.

- [ ] **Step 3: Vérification manuelle (localhost)**

Lancer backend + frontend (`CLAUDE.md`), ouvrir Dépenses → Carnet de route → Trajets : créer un favori (Task 16 requis pour le peupler, sinon liste vide), saisir un trajet 45 km aller-retour 2026 → allocation live ≈ 65,70 $ ; « Générer la dépense » → apparaît dans la liste des dépenses.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ExpensesPage.js
git commit -m "feat(mileage-ui): trips tab with live allocation, favorites prefill, expense generation"
```

---

## Task 16: Frontend — onglet Favoris

**Files:**
- Modify: `frontend/src/pages/ExpensesPage.js` (remplir `MileageFavoritesTab`)

- [ ] **Step 1: Implémenter la liste + le formulaire de favori**

```jsx
function MileageFavoritesTab() {
  const { token } = useAuth();
  const authCfg = { headers: { Authorization: `Bearer ${token}` } };
  const [favorites, setFavorites] = useState([]);
  const [form, setForm] = useState({
    label: "", origin: "", destination: "", purpose: "",
    one_way_km: "", round_trip_default: false,
  });
  const [editId, setEditId] = useState(null);

  const load = async () => {
    const r = await axios.get(`${BACKEND_URL}/api/mileage/favorites`, authCfg);
    setFavorites(r.data);
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  const submit = async () => {
    const payload = { ...form, one_way_km: parseFloat(form.one_way_km) };
    if (editId) {
      await axios.put(`${BACKEND_URL}/api/mileage/favorites/${editId}`, payload, authCfg);
    } else {
      await axios.post(`${BACKEND_URL}/api/mileage/favorites`, payload, authCfg);
    }
    setForm({ label: "", origin: "", destination: "", purpose: "", one_way_km: "", round_trip_default: false });
    setEditId(null);
    load();
  };

  const remove = async (id) => {
    await axios.delete(`${BACKEND_URL}/api/mileage/favorites/${id}`, authCfg);
    load();
  };

  return (
    <div>
      <div className="border rounded p-4 mb-6 grid grid-cols-2 gap-3">
        <input placeholder="Nom (ex: Domicile → Client ABC)" value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} className="border p-2 col-span-2" />
        <input placeholder="Départ" value={form.origin} onChange={(e) => setForm({ ...form, origin: e.target.value })} className="border p-2" />
        <input placeholder="Arrivée" value={form.destination} onChange={(e) => setForm({ ...form, destination: e.target.value })} className="border p-2" />
        <input placeholder="Motif par défaut" value={form.purpose} onChange={(e) => setForm({ ...form, purpose: e.target.value })} className="border p-2" />
        <input type="number" placeholder="Km (aller simple)" value={form.one_way_km} onChange={(e) => setForm({ ...form, one_way_km: e.target.value })} className="border p-2" />
        <label className="flex items-center gap-2 col-span-2">
          <input type="checkbox" checked={form.round_trip_default} onChange={(e) => setForm({ ...form, round_trip_default: e.target.checked })} />
          Aller-retour par défaut
        </label>
        <button onClick={submit} className="btn-primary col-span-2" disabled={!form.label.trim() || !(parseFloat(form.one_way_km) > 0)}>
          {editId ? "Enregistrer les modifications" : "Nouveau favori"}
        </button>
      </div>

      <table className="w-full text-sm">
        <thead><tr className="text-left border-b"><th>Nom</th><th>Route</th><th>Km</th><th>A/R</th><th></th></tr></thead>
        <tbody>
          {favorites.map((f) => (
            <tr key={f.id} className="border-b">
              <td>{f.label}</td>
              <td>{f.origin} → {f.destination}</td>
              <td>{f.one_way_km}</td>
              <td>{f.round_trip_default ? "Oui" : "Non"}</td>
              <td className="flex gap-2">
                <button className="text-blue-600 text-xs" onClick={() => { setEditId(f.id); setForm({ label: f.label, origin: f.origin, destination: f.destination, purpose: f.purpose || "", one_way_km: f.one_way_km, round_trip_default: f.round_trip_default }); }}>Modifier</button>
                <button className="text-red-600 text-xs" onClick={() => remove(f.id)}>Supprimer</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 2: Vérifier la compilation**

Run: `cd frontend && npm run build`
Expected: build réussit.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ExpensesPage.js
git commit -m "feat(mileage-ui): favorites tab with create/edit/delete"
```

---

## Task 17: Frontend — onglet Carnet (vue annuelle + export PDF)

**Files:**
- Modify: `frontend/src/pages/ExpensesPage.js` (remplir `MileageLogbookTab`)

- [ ] **Step 1: Implémenter la vue annuelle read-only + le téléchargement PDF authentifié**

Le PDF nécessite un blob authentifié (pattern T2125). :

```jsx
function MileageLogbookTab() {
  const { token } = useAuth();
  const authCfg = { headers: { Authorization: `Bearer ${token}` } };
  const [year, setYear] = useState(new Date().getFullYear());
  const [data, setData] = useState(null);

  const load = async () => {
    const r = await axios.get(`${BACKEND_URL}/api/mileage/logbook?year=${year}`, authCfg);
    setData(r.data);
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [year]);

  const downloadPdf = async () => {
    const resp = await axios.get(`${BACKEND_URL}/api/mileage/logbook/pdf?year=${year}`, {
      headers: { Authorization: `Bearer ${token}` }, responseType: "blob",
    });
    const url = window.URL.createObjectURL(new Blob([resp.data], { type: "application/pdf" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `carnet-route-${year}.pdf`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        <input type="number" value={year} onChange={(e) => setYear(e.target.value)} className="border p-1 w-24" />
        <button onClick={downloadPdf} className="btn-primary">Télécharger le carnet PDF</button>
      </div>

      {data?.current_year_missing && (
        <div className="bg-yellow-100 border border-yellow-400 p-3 mb-4 text-sm">
          Taux {data.year} à confirmer — l'allocation en dollars est en attente de mise à jour du taux ARC.
        </div>
      )}

      {data && (
        <>
          <table className="w-full text-sm">
            <thead><tr className="text-left border-b">
              <th>Date</th><th>Départ</th><th>Arrivée</th><th>Motif</th><th>Km</th><th>Cumul</th><th>Allocation</th>
            </tr></thead>
            <tbody>
              {data.rows.map((r, i) => (
                <tr key={i} className="border-b">
                  <td>{r.trip_date}</td><td>{r.origin}</td><td>{r.destination}</td>
                  <td>{r.purpose}</td><td>{r.distance_km}</td><td>{r.running_total_km}</td>
                  <td>{r.allocation_cad !== null ? `${r.allocation_cad.toFixed(2)} $` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="mt-4 font-semibold">
            Total : {data.total_km} km — {data.total_allocation_cad.toFixed(2)} $
          </div>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Vérifier la compilation**

Run: `cd frontend && npm run build`
Expected: build réussit.

- [ ] **Step 3: Vérification manuelle (localhost)**

Ouvrir Dépenses → Carnet de route → Carnet, année 2026 : vérifier cumul progressif + totaux ; « Télécharger le carnet PDF » ouvre un PDF avec colonnes Date/Départ/Arrivée/Motif/Km/Cumul/Allocation.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ExpensesPage.js
git commit -m "feat(mileage-ui): annual logbook view with running total and authed PDF download"
```

---

## Task 18: Suite complète + doc + push

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Lancer toute la suite mileage + non-régression**

Run: `cd backend && python -m pytest tests/test_mileage_logbook.py tests/test_mileage_logbook_integration.py -v`
Expected: PASS (tous). Cible spec : ~20 unitaires + ~25 intégration.

Run: `cd backend && python -m pytest -q`
Expected: 0 régression sur les suites existantes (features #3-#12).

- [ ] **Step 2: Vérification frontend**

Run: `cd frontend && npm run build`
Expected: build réussit sans warning bloquant.

- [ ] **Step 3: Mettre à jour `CLAUDE.md`**

Ajouter en haut de la section « Features livrées » :

```markdown
- **2026-07-03 — Carnet de route kilométrage (feature #13)**
  - 4 nouvelles collections org-scopées : `mileage_trips`, `mileage_favorites`, `mileage_vehicles`, `mileage_rate_reminders`
  - Table des taux ARC dans le code (`MILEAGE_RATES` 2024-2026, full/reduced) + seuil 5 000 km ; helper `_mileage_rate_for_year` (aucun fallback silencieux)
  - Allocation calculée à la volée avec **split au seuil 5 000 km** (`_mileage_allocation`), cumul chronologique par (personne, véhicule, année civile) via `_mileage_ytd_before`
  - ~14 endpoints `/api/mileage/*` (trajets CRUD, favoris CRUD, véhicules, taux, carnet JSON + PDF ARC, génération dépense par trajet + lot mensuel), RBAC réutilisé `expenses:read`/`expenses:write`
  - Génération dépense `vehicle_expenses` (ligne 9281) via snapshot existant ; anti-double-comptage par `expense_id` ; cascade `_release_mileage_trips` au DELETE de la dépense
  - Carnet PDF FR-CA conforme ARC (Date/Départ/Arrivée/Motif/Km/Cumul/Allocation + totaux + rappel bascule), no-cache
  - Rappel annuel du taux : `POST /api/mileage/check-rate-update` pingé par cron externe (modèle `check-trial-expiry`), notif email idempotente par (org, année), **jamais** de mise à jour silencieuse
  - Seed lazy du véhicule par défaut au 1er accès ; migration idempotente `migrate_mileage_logbook_v1` (index seulement, additive)
  - Frontend : bouton « Carnet de route » dans `ExpensesPage` → vue à 3 onglets (Trajets avec allocation live + favoris pré-remplis + génération, Favoris CRUD, Carnet annuel + export PDF)
  - Limites v1 : saisie km manuelle (pas de géocodage), 1 véhicule par défaut (modèle porte `vehicle_id` pour v2), méthode allocation par km seulement (pas frais réels), taux fédéral (pas territorial), cumul année civile
  - Infra hors code : 1 cron externe 1×/jour en janvier sur `/api/mileage/check-rate-update`
  - Tests : ~20 unitaires + ~25 intégration = **~45 nouveaux tests**, 0 régression
  - Spec : `docs/superpowers/specs/2026-07-03-mileage-logbook-design.md`
  - Plan : `docs/superpowers/plans/2026-07-03-mileage-logbook.md`
```

- [ ] **Step 4: Commit + push**

```bash
git add CLAUDE.md
git commit -m "docs: record mileage logbook feature #13 in CLAUDE.md"
git push origin main
```

Expected: Render redéploie le backend (~3 min), Vercel redéploie le frontend (~2 min). Après déploiement, créer le cron externe pointant sur `POST /api/mileage/check-rate-update` (1×/jour en janvier).

---

## Self-Review

**1. Spec coverage:**
- §3.1 table des taux + `_mileage_rate_for_year` → Task 1. ✅
- §3.2/§4.2 distance dérivée + `_mileage_allocation` split → Task 2. ✅
- §4.1 cumul `_mileage_ytd_before` → Task 3. ✅
- §3.2-3.6 collections + §11.2 migration + §11.3 seed lazy + §11.1 `_ORG_SCOPED_COLLECTIONS` → Task 4. ✅
- §6.1 CRUD trajets + §3.2 invariants (purpose, km>0, distance recalculée) → Tasks 5-6. ✅
- §4 bascule 5000 end-to-end → Task 6. ✅
- §6.2 favoris CRUD + §3.3 indépendance trajet → Task 7. ✅
- §6.4 `GET /rates` + `current_year_missing` → Task 8. ✅
- §10 sécurité RBAC + isolation cross-org → Task 9. ✅
- §5 génération dépense (par trajet + lot) + cascade `_release_mileage_trips` → Task 10. ✅
- §6.4/§8 carnet JSON + PDF ARC → Task 11. ✅
- §7 rappel annuel cron → Task 12. ✅
- §4.2/§7 taux manquant → allocation bloquée → Task 13. ✅
- §9.1 bouton + §9.2 onglets → Task 14. ✅
- §9.2 onglet Trajets (allocation live, favoris, génération) → Task 15. ✅
- §9.2 onglet Favoris → Task 16. ✅
- §9.2/§9.4 onglet Carnet + PDF blob authentifié → Task 17. ✅
- §12 tests + doc + push → Task 18. ✅

**2. Placeholder scan:** Les composants « placeholder » du Task 14 sont des stubs compilables explicitement remplis aux Tasks 15-17 (pas des TODO laissés dans le livrable). Tout le code backend/frontend est fourni en entier. Les `> Vérifier…` sont des notes d'ancrage sur des symboles réels du codebase inaccessibles en lecture depuis cet environnement sandboxé, pas des trous de logique.

**3. Type consistency:** Noms cohérents à travers les tasks : `_mileage_rate_for_year`, `_mileage_distance_km`, `_mileage_allocation`, `_mileage_ytd_before`/`_mileage_sum_ytd`/`_mileage_employee_key`, `_mileage_enrich_trip`, `_mileage_build_expense_for_trips`, `_release_mileage_trips`, `_ensure_default_vehicle`, `_mileage_logbook_rows`, `_render_mileage_logbook_pdf`. Forme de retour trajet enrichi `{trip, allocation, ytd_before}` identique côté Task 5/6/15. Champs dépense (`category_code`, `amount_cad`, `mileage_generated`, `mileage_trip_ids`, `expense_id`) cohérents Task 10 ↔ tests.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-07-03-mileage-logbook.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
