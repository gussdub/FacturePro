# Tax Registrations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter le support complet des numéros officiels canadiens (BN, TPS, TVQ, TVH, NEQ) côté entreprise et côté client, avec snapshot sur factures/devis, validation souple, et nouveau layout PDF.

**Architecture:** Migration douce d'un champ DB existant (`pst_number` → `qst_number`), ajout de 2 champs côté entreprise et 5 côté client. Snapshot des 10 numéros au moment de la création d'une facture ou d'un devis (immutabilité audit). Validation par regex jamais bloquante. PDF refait : entête épuré, boîte client enrichie, encadré "Numéros d'enregistrement" en bas.

**Tech Stack:** FastAPI (backend), pymongo synchrone, React 18 CRA (frontend), pytest pour tests unitaires + intégration, ReportLab pour PDF.

**Spec source:** [docs/superpowers/specs/2026-06-16-tax-registrations-design.md](../specs/2026-06-16-tax-registrations-design.md)

---

## File Structure

**Created:**
- `backend/tests/test_tax_numbers.py` — tests unitaires des helpers + migration (~120 lignes)
- `backend/tests/test_tax_registrations_integration.py` — tests d'intégration des endpoints + snapshot (~150 lignes)
- `backend/requirements-dev.txt` — pytest comme dev dep (sans alourdir prod)

**Modified:**
- `backend/server.py` — helpers (~30 lignes), migration (~15 lignes), endpoints settings/clients/invoices/quotes (~80 lignes), `generate_document_pdf` (~50 lignes), appel migration au startup (~3 lignes)
- `frontend/src/pages/SettingsPage.js` — nouvelle section "Numéros officiels" (~80 lignes)
- `frontend/src/pages/ClientsPage.js` — section repliable "Numéros officiels" (~80 lignes)

---

## Task 0 : Préparer l'environnement de test

**Files:**
- Create: `backend/requirements-dev.txt`
- Test: lance pytest local

- [ ] **Step 1: Créer `requirements-dev.txt`**

```
pytest>=8.0
pytest-mock>=3.12
```

- [ ] **Step 2: Installer dans le venv**

Run:
```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Expected: `Successfully installed pytest-8.x.x pytest-mock-3.x.x ...`

- [ ] **Step 3: Vérifier que pytest fonctionne**

Run: `pytest --version`
Expected: `pytest 8.x.x` (sans erreur)

- [ ] **Step 4: Commit**

```bash
git add backend/requirements-dev.txt
git commit -m "test: ajout requirements-dev.txt avec pytest"
```

---

## Task 1 : Helpers de validation (TAX_FORMATS, normalize, check)

**Files:**
- Create: `backend/tests/test_tax_numbers.py`
- Modify: `backend/server.py` (ajouter après les imports, avant le client MongoDB ligne ~89)

- [ ] **Step 1: Écrire les tests d'abord**

Créer `backend/tests/test_tax_numbers.py` :

```python
"""Tests unitaires pour les helpers de numéros de taxes."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Charge les helpers en isolation sans démarrer FastAPI
import importlib.util
spec = importlib.util.spec_from_file_location(
    "server_helpers",
    os.path.join(os.path.dirname(__file__), "..", "server.py")
)
# On ne peut pas importer server.py directement sans MONGO_URL.
# À la place, on importe seulement les helpers via copie locale dans ce module de test.
# Pour ce test on duplique les helpers (ou refactor recommandé : extraire en module séparé).

# Pour simplicité du TDD : on importe en se basant sur env vars stub.
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "facturepro_test_unit")
os.environ.setdefault("JWT_SECRET", "test")

from server import normalize_tax_number, check_tax_number, TAX_FORMATS


class TestNormalizeTaxNumber:
    def test_strip_whitespace(self):
        assert normalize_tax_number("  123456789  ") == "123456789"

    def test_remove_internal_spaces(self):
        assert normalize_tax_number("123 456 789") == "123456789"

    def test_remove_dashes(self):
        assert normalize_tax_number("123-456-789-RT-0001") == "123456789RT0001"

    def test_uppercase(self):
        assert normalize_tax_number("123456789rt0001") == "123456789RT0001"

    def test_combined(self):
        assert normalize_tax_number("  123 456 789-rt-0001  ") == "123456789RT0001"

    def test_idempotent(self):
        x = "123456789RT0001"
        assert normalize_tax_number(normalize_tax_number(x)) == x

    def test_none_tolerated(self):
        assert normalize_tax_number(None) == ""

    def test_empty(self):
        assert normalize_tax_number("") == ""


class TestCheckTaxNumber:
    def test_empty_is_valid(self):
        result = check_tax_number("", "bn")
        assert result["valid"] is True
        assert result["expected"] == ""

    def test_bn_valid_9_digits(self):
        result = check_tax_number("123456789", "bn")
        assert result["valid"] is True
        assert result["expected"] == "9 chiffres"

    def test_bn_invalid_too_short(self):
        result = check_tax_number("12345", "bn")
        assert result["valid"] is False
        assert "9 chiffres" in result["expected"]

    def test_gst_valid_with_suffix(self):
        result = check_tax_number("123456789RT0001", "gst")
        assert result["valid"] is True

    def test_gst_invalid_missing_suffix(self):
        result = check_tax_number("123456789", "gst")
        assert result["valid"] is False
        assert "RT0001" in result["expected"]

    def test_qst_valid(self):
        result = check_tax_number("1234567890TQ0001", "qst")
        assert result["valid"] is True

    def test_qst_invalid(self):
        result = check_tax_number("123456789", "qst")
        assert result["valid"] is False

    def test_hst_valid(self):
        result = check_tax_number("123456789RT0001", "hst")
        assert result["valid"] is True

    def test_neq_valid_10_digits(self):
        result = check_tax_number("1234567890", "neq")
        assert result["valid"] is True

    def test_neq_invalid_9_digits(self):
        result = check_tax_number("123456789", "neq")
        assert result["valid"] is False


class TestTaxFormats:
    def test_all_keys_present(self):
        assert set(TAX_FORMATS.keys()) == {"bn", "gst", "qst", "hst", "neq"}

    def test_each_format_is_tuple_of_2(self):
        for kind, (pattern, hint) in TAX_FORMATS.items():
            assert isinstance(pattern, str)
            assert isinstance(hint, str)
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run:
```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
pytest tests/test_tax_numbers.py -v
```

Expected: `ImportError: cannot import name 'normalize_tax_number' from 'server'`

- [ ] **Step 3: Implémenter les helpers dans `server.py`**

Modifier `backend/server.py`, ajouter juste après la ligne `from bson import Binary` (autour de la ligne 44, avant `client = MongoClient(MONGO_URL)`) :

```python
from bson import Binary

# ─── Tax registration helpers (Section 2/3 du spec tax-registrations) ───

TAX_FORMATS = {
    "bn":  (r"^\d{9}$",          "9 chiffres"),
    "gst": (r"^\d{9}RT\d{4}$",   "9 chiffres + RT0001"),
    "qst": (r"^\d{10}TQ\d{4}$",  "10 chiffres + TQ0001"),
    "hst": (r"^\d{9}RT\d{4}$",   "9 chiffres + RT0001"),
    "neq": (r"^\d{10}$",         "10 chiffres"),
}

def normalize_tax_number(value):
    """Normalise un numéro de taxe : strip + uppercase + retire espaces/tirets.
    Idempotent. Tolère None."""
    return (value or "").strip().upper().replace(" ", "").replace("-", "")

def check_tax_number(value, kind):
    """Retourne {'valid': bool, 'expected': str}. Vide considéré valide. Jamais bloquant."""
    import re
    if not value:
        return {"valid": True, "expected": ""}
    pattern, hint = TAX_FORMATS[kind]
    return {"valid": bool(re.match(pattern, value)), "expected": hint}
```

Note : `import re` à l'intérieur de la fonction pour éviter de polluer le scope global (le module `re` n'est pas importé en haut de server.py — vérifier au passage et déplacer en haut si déjà importé ailleurs).

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

Run: `pytest tests/test_tax_numbers.py -v`
Expected: `21 passed` (8 normalize + 11 check + 2 formats).

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_tax_numbers.py backend/server.py
git commit -m "feat(taxes): helpers TAX_FORMATS, normalize_tax_number, check_tax_number"
```

---

## Task 2 : Migration `pst_number` → `qst_number`

**Files:**
- Modify: `backend/server.py` (ajouter fonction migration)
- Modify: `backend/tests/test_tax_numbers.py` (ajouter classe TestMigration)

- [ ] **Step 1: Ajouter la fixture de DB de test dans `test_tax_numbers.py`**

Ajouter en haut du fichier (après les imports existants) :

```python
import pytest
from pymongo import MongoClient

@pytest.fixture
def test_db():
    """Fournit une DB MongoDB de test isolée. Drop à la fin."""
    client = MongoClient("mongodb://localhost:27017")
    db_name = "facturepro_test_migration"
    db = client[db_name]
    yield db
    client.drop_database(db_name)
```

Puis ajouter la classe de test au bas du fichier :

```python
class TestMigration:
    def test_migrates_pst_to_qst(self, test_db):
        from server import migrate_pst_to_qst
        test_db.company_settings.insert_one({"user_id": "u1", "pst_number": "test1"})
        migrate_pst_to_qst(test_db)
        doc = test_db.company_settings.find_one({"user_id": "u1"})
        assert doc["qst_number"] == "test1"
        assert "pst_number" not in doc

    def test_idempotent(self, test_db):
        from server import migrate_pst_to_qst
        test_db.company_settings.insert_one({"user_id": "u1", "pst_number": "x"})
        migrate_pst_to_qst(test_db)
        doc_after_first = test_db.company_settings.find_one({"user_id": "u1"})
        migrate_pst_to_qst(test_db)
        doc_after_second = test_db.company_settings.find_one({"user_id": "u1"})
        assert doc_after_first == doc_after_second

    def test_skips_when_qst_already_exists(self, test_db):
        from server import migrate_pst_to_qst
        # Doc with both: should not overwrite qst
        test_db.company_settings.insert_one({"user_id": "u1", "pst_number": "old", "qst_number": "new"})
        migrate_pst_to_qst(test_db)
        doc = test_db.company_settings.find_one({"user_id": "u1"})
        assert doc["qst_number"] == "new"
        # pst_number left untouched in this corner case
        assert doc.get("pst_number") == "old"

    def test_skips_when_no_pst(self, test_db):
        from server import migrate_pst_to_qst
        test_db.company_settings.insert_one({"user_id": "u1", "qst_number": "x"})
        migrate_pst_to_qst(test_db)
        doc = test_db.company_settings.find_one({"user_id": "u1"})
        assert doc["qst_number"] == "x"
```

- [ ] **Step 2: Lancer pour vérifier que ça échoue**

Run: `pytest tests/test_tax_numbers.py::TestMigration -v`
Expected: `ImportError: cannot import name 'migrate_pst_to_qst' from 'server'`

- [ ] **Step 3: Implémenter `migrate_pst_to_qst` dans `server.py`**

Ajouter juste après les helpers de Task 1 (avant la ligne `client = MongoClient(MONGO_URL)`) :

```python
def migrate_pst_to_qst(database=None):
    """Renomme pst_number en qst_number dans company_settings. Idempotent.
    Si `database` est None, utilise la DB par défaut (`db` global)."""
    target = database if database is not None else db
    result = target.company_settings.update_many(
        {"pst_number": {"$exists": True}, "qst_number": {"$exists": False}},
        [{"$set": {"qst_number": "$pst_number"}}, {"$unset": "pst_number"}]
    )
    if result.modified_count:
        print(f"Migrated {result.modified_count} company_settings: pst_number → qst_number")
    return result.modified_count
```

- [ ] **Step 4: Lancer les tests**

Run: `pytest tests/test_tax_numbers.py::TestMigration -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/server.py backend/tests/test_tax_numbers.py
git commit -m "feat(taxes): migration idempotente pst_number → qst_number"
```

---

## Task 3 : Endpoints settings (GET + PUT)

**Files:**
- Modify: `backend/server.py` (endpoints `/api/settings/company` lignes ~870)
- Create: `backend/tests/test_tax_registrations_integration.py`

- [ ] **Step 1: Repérer le code actuel**

Run:
```bash
grep -n "settings/company" backend/server.py
```
Note les numéros de ligne des endpoints GET et PUT.

- [ ] **Step 2: Écrire les tests d'intégration**

Créer `backend/tests/test_tax_registrations_integration.py` :

```python
"""Tests d'intégration HTTP pour les numéros officiels (settings, clients, invoices)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("FACTUREPRO_BACKEND_URL", "http://localhost:8000").rstrip("/")
TEST_EMAIL = "gussdub@gmail.com"
TEST_PASSWORD = "testpass123"


@pytest.fixture(scope="module")
def auth():
    resp = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


class TestSettingsTaxNumbers:
    def test_get_returns_5_tax_fields(self, auth):
        resp = requests.get(f"{BASE_URL}/api/settings/company", headers=auth)
        assert resp.status_code == 200
        body = resp.json()
        for key in ["bn_number", "gst_number", "qst_number", "hst_number", "neq_number"]:
            assert key in body, f"Missing key {key} in settings response"

    def test_get_returns_tax_warnings(self, auth):
        resp = requests.get(f"{BASE_URL}/api/settings/company", headers=auth)
        body = resp.json()
        assert "tax_number_warnings" in body
        # Object with one key per tax field
        for key in ["bn_number", "gst_number", "qst_number", "hst_number", "neq_number"]:
            assert key in body["tax_number_warnings"]

    def test_put_accepts_all_5_numbers(self, auth):
        payload = {
            "bn_number": "  123 456 789  ",
            "gst_number": "123456789rt0001",
            "qst_number": "1234567890TQ0001",
            "hst_number": "",
            "neq_number": "1234567890",
        }
        resp = requests.put(f"{BASE_URL}/api/settings/company",
                             headers=auth, json=payload)
        assert resp.status_code == 200

        # GET back, values normalized
        get = requests.get(f"{BASE_URL}/api/settings/company", headers=auth)
        body = get.json()
        assert body["bn_number"] == "123456789"
        assert body["gst_number"] == "123456789RT0001"
        assert body["qst_number"] == "1234567890TQ0001"
        assert body["hst_number"] == ""
        assert body["neq_number"] == "1234567890"

    def test_put_accepts_invalid_format_with_warning(self, auth):
        resp = requests.put(f"{BASE_URL}/api/settings/company",
                             headers=auth, json={"bn_number": "abc"})
        assert resp.status_code == 200  # never rejects

        get = requests.get(f"{BASE_URL}/api/settings/company", headers=auth)
        body = get.json()
        # Value stored as-is after normalization (uppercase)
        assert body["bn_number"] == "ABC"
        # Warning surfaced
        assert body["tax_number_warnings"]["bn_number"]["valid"] is False
```

- [ ] **Step 3: Lancer (depuis le venv, backend doit tourner sur :8000)**

Run :
```bash
# Terminal 1 — assure-toi que uvicorn tourne :
pgrep -f "uvicorn server:app" || (cd backend && source .venv/bin/activate && uvicorn server:app --port 8000 &)

# Tests
cd backend && source .venv/bin/activate
pytest tests/test_tax_registrations_integration.py::TestSettingsTaxNumbers -v
```

Expected: 4 tests FAIL — les nouveaux champs ne sont pas encore retournés.

- [ ] **Step 4: Modifier les endpoints settings dans `server.py`**

Trouver le bloc `@app.get("/api/settings/company")` (autour de la ligne 870). Modifier pour ressembler à ceci :

```python
TAX_FIELDS = ["bn_number", "gst_number", "qst_number", "hst_number", "neq_number"]
TAX_FIELD_KINDS = {"bn_number": "bn", "gst_number": "gst", "qst_number": "qst",
                   "hst_number": "hst", "neq_number": "neq"}

def _tax_warnings(doc):
    """Retourne {field: {valid, expected}} pour chaque champ taxe du doc."""
    return {f: check_tax_number(doc.get(f, ""), TAX_FIELD_KINDS[f]) for f in TAX_FIELDS}

@app.get("/api/settings/company")
def get_company_settings(current_user: User = Depends(get_current_user_with_access)):
    settings = db.company_settings.find_one({"user_id": current_user.id}, {"_id": 0})
    if not settings:
        settings = {
            "user_id": current_user.id,
            "company_name": "", "email": "", "phone": "",
            "address": "", "city": "", "postal_code": "", "country": "",
            "default_due_days": 30,
            "bn_number": "", "gst_number": "", "qst_number": "", "hst_number": "", "neq_number": "",
            "logo_url": "",
        }
    # Ensure all 5 tax fields exist in response
    for f in TAX_FIELDS:
        settings.setdefault(f, "")
    settings["tax_number_warnings"] = _tax_warnings(settings)
    return settings

@app.put("/api/settings/company")
def update_company_settings(body: dict, current_user: User = Depends(get_current_user_with_access)):
    update = {k: v for k, v in body.items() if k != "user_id" and k != "tax_number_warnings"}
    # Normalize tax numbers
    for f in TAX_FIELDS:
        if f in update:
            update[f] = normalize_tax_number(update[f])
    db.company_settings.update_one(
        {"user_id": current_user.id},
        {"$set": update},
        upsert=True
    )
    return {"message": "Settings updated"}
```

Important : ne pas casser les champs déjà existants (`company_name`, `address`, etc.). Le PUT doit faire un merge, pas un replace.

- [ ] **Step 5: Redémarrer uvicorn et relancer les tests**

Run :
```bash
lsof -ti:8000 | xargs kill 2>/dev/null
cd backend && source .venv/bin/activate
uvicorn server:app --port 8000 &
sleep 4
pytest tests/test_tax_registrations_integration.py::TestSettingsTaxNumbers -v
```

Expected: 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/server.py backend/tests/test_tax_registrations_integration.py
git commit -m "feat(taxes): endpoints settings GET/PUT supportent 5 numéros officiels"
```

---

## Task 4 : Endpoints clients (POST + PUT + GET)

**Files:**
- Modify: `backend/server.py` (endpoints clients lignes ~309-340)
- Modify: `backend/tests/test_tax_registrations_integration.py`

- [ ] **Step 1: Écrire les tests**

Ajouter dans `test_tax_registrations_integration.py` :

```python
class TestClientTaxNumbers:
    def test_create_client_with_numbers(self, auth):
        payload = {
            "name": "ACME Test Inc.",
            "email": "test@acme.example",
            "bn_number": "987 654 321",
            "gst_number": "987654321RT0001",
            "qst_number": "9876543210TQ0001",
            "hst_number": "",
            "neq_number": "9876543210",
        }
        resp = requests.post(f"{BASE_URL}/api/clients", headers=auth, json=payload)
        assert resp.status_code in (200, 201)
        client_id = resp.json()["id"]

        # Cleanup at end of class
        TestClientTaxNumbers._cleanup_ids.append(client_id)

        get = requests.get(f"{BASE_URL}/api/clients", headers=auth)
        clients = get.json()
        created = next(c for c in clients if c["id"] == client_id)
        assert created["bn_number"] == "987654321"
        assert created["gst_number"] == "987654321RT0001"

    def test_update_client_numbers(self, auth):
        # Create
        create = requests.post(f"{BASE_URL}/api/clients", headers=auth,
                                json={"name": "X Inc."})
        client_id = create.json()["id"]
        TestClientTaxNumbers._cleanup_ids.append(client_id)

        # Update with tax numbers
        upd = requests.put(f"{BASE_URL}/api/clients/{client_id}", headers=auth,
                           json={"bn_number": "111 222 333"})
        assert upd.status_code == 200

        get = requests.get(f"{BASE_URL}/api/clients", headers=auth)
        updated = next(c for c in get.json() if c["id"] == client_id)
        assert updated["bn_number"] == "111222333"

    def test_create_client_without_numbers(self, auth):
        resp = requests.post(f"{BASE_URL}/api/clients", headers=auth,
                              json={"name": "No Tax Inc."})
        assert resp.status_code in (200, 201)
        client_id = resp.json()["id"]
        TestClientTaxNumbers._cleanup_ids.append(client_id)

        get = requests.get(f"{BASE_URL}/api/clients", headers=auth)
        created = next(c for c in get.json() if c["id"] == client_id)
        # All 5 fields default to empty string
        for f in ["bn_number", "gst_number", "qst_number", "hst_number", "neq_number"]:
            assert created.get(f, "") == ""

    _cleanup_ids = []

    @classmethod
    def teardown_class(cls):
        # Best-effort cleanup
        # (auth not available at teardown_class — done via API individually in each test if needed)
        pass
```

- [ ] **Step 2: Lancer pour vérifier qu'ils échouent**

Run: `pytest tests/test_tax_registrations_integration.py::TestClientTaxNumbers -v`
Expected: tous échouent (champs `bn_number` etc. pas retournés).

- [ ] **Step 3: Modifier les endpoints clients dans `server.py`**

Trouver le bloc clients (ligne ~309-340). Modifier la création :

```python
@app.post("/api/clients")
def create_client(client_data: dict, current_user: User = Depends(get_current_user_with_access)):
    # Normalize tax numbers in payload
    for f in TAX_FIELDS:
        if f in client_data:
            client_data[f] = normalize_tax_number(client_data[f])
    new_client = {
        "id": str(uuid.uuid4()),
        "user_id": current_user.id,
        "name": client_data.get("name", ""),
        "email": client_data.get("email", ""),
        "phone": client_data.get("phone", ""),
        "address": client_data.get("address", ""),
        "city": client_data.get("city", ""),
        "postal_code": client_data.get("postal_code", ""),
        "country": client_data.get("country", ""),
        "notes": client_data.get("notes", ""),
        # Tax numbers — default empty
        "bn_number": client_data.get("bn_number", ""),
        "gst_number": client_data.get("gst_number", ""),
        "qst_number": client_data.get("qst_number", ""),
        "hst_number": client_data.get("hst_number", ""),
        "neq_number": client_data.get("neq_number", ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    db.clients.insert_one(new_client)
    new_client.pop("_id", None)
    return new_client

@app.put("/api/clients/{client_id}")
def update_client(client_id: str, updates: dict, current_user: User = Depends(get_current_user_with_access)):
    # Normalize tax numbers in payload
    for f in TAX_FIELDS:
        if f in updates:
            updates[f] = normalize_tax_number(updates[f])
    updates.pop("id", None)
    updates.pop("user_id", None)
    result = db.clients.update_one(
        {"id": client_id, "user_id": current_user.id},
        {"$set": updates}
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Client not found")
    return {"message": "Client updated"}
```

L'endpoint GET liste les clients existants ; il faut juste s'assurer que les anciens clients (sans les nouveaux champs) ne crashent pas. Comme on retourne tels quels les docs Mongo, les champs absents → frontend doit gérer `undefined`. C'est OK.

- [ ] **Step 4: Redémarrer uvicorn + relancer les tests**

Run :
```bash
lsof -ti:8000 | xargs kill 2>/dev/null
cd backend && source .venv/bin/activate
uvicorn server:app --port 8000 &
sleep 4
pytest tests/test_tax_registrations_integration.py::TestClientTaxNumbers -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/server.py backend/tests/test_tax_registrations_integration.py
git commit -m "feat(taxes): endpoints clients supportent 5 numéros officiels B2B"
```

---

## Task 5 : Snapshot `tax_registrations` sur factures + devis

**Files:**
- Modify: `backend/server.py` (POST /api/invoices, POST /api/quotes lignes ~376-410)
- Modify: `backend/tests/test_tax_registrations_integration.py`

- [ ] **Step 1: Écrire le test**

Ajouter dans `test_tax_registrations_integration.py` :

```python
class TestSnapshotOnCreate:
    def test_invoice_snapshots_company_and_client_numbers(self, auth):
        # Pré-condition : configurer settings avec numéros
        requests.put(f"{BASE_URL}/api/settings/company", headers=auth, json={
            "bn_number": "555555555",
            "gst_number": "555555555RT0001",
            "qst_number": "5555555555TQ0001",
        })
        # Pré-condition : créer un client B2B avec numéros
        client_resp = requests.post(f"{BASE_URL}/api/clients", headers=auth, json={
            "name": "Snapshot Test Inc.",
            "bn_number": "111111111",
            "gst_number": "111111111RT0001",
        })
        client_id = client_resp.json()["id"]

        # Créer une facture
        inv_resp = requests.post(f"{BASE_URL}/api/invoices", headers=auth, json={
            "client_id": client_id,
            "items": [{"description": "Snapshot test", "quantity": 1, "unit_price": 100}],
            "province": "QC",
        })
        assert inv_resp.status_code in (200, 201), inv_resp.text
        inv = inv_resp.json()

        # Snapshot stocké et inclut les bons numéros
        assert "tax_registrations" in inv
        assert inv["tax_registrations"]["company"]["bn"] == "555555555"
        assert inv["tax_registrations"]["company"]["gst"] == "555555555RT0001"
        assert inv["tax_registrations"]["client"]["bn"] == "111111111"
        assert inv["tax_registrations"]["client"]["gst"] == "111111111RT0001"

    def test_invoice_snapshot_immutable_after_settings_change(self, auth):
        # Configurer settings initiaux
        requests.put(f"{BASE_URL}/api/settings/company", headers=auth,
                      json={"bn_number": "777777777"})
        client_resp = requests.post(f"{BASE_URL}/api/clients", headers=auth,
                                    json={"name": "Frozen Test"})
        client_id = client_resp.json()["id"]
        inv = requests.post(f"{BASE_URL}/api/invoices", headers=auth, json={
            "client_id": client_id, "items": [{"description": "x", "quantity": 1, "unit_price": 10}],
            "province": "QC",
        }).json()
        inv_id = inv["id"]

        # Modifier les settings APRÈS création
        requests.put(f"{BASE_URL}/api/settings/company", headers=auth,
                      json={"bn_number": "999999999"})

        # Re-fetch la facture
        get = requests.get(f"{BASE_URL}/api/invoices/{inv_id}", headers=auth)
        inv_after = get.json()
        # La facture garde l'ancien numéro (snapshot)
        assert inv_after["tax_registrations"]["company"]["bn"] == "777777777"

    def test_quote_snapshots_too(self, auth):
        requests.put(f"{BASE_URL}/api/settings/company", headers=auth,
                      json={"bn_number": "333333333"})
        client = requests.post(f"{BASE_URL}/api/clients", headers=auth,
                                json={"name": "Quote Test"}).json()
        quote = requests.post(f"{BASE_URL}/api/quotes", headers=auth, json={
            "client_id": client["id"],
            "items": [{"description": "q", "quantity": 1, "unit_price": 50}],
            "province": "QC",
        }).json()
        assert "tax_registrations" in quote
        assert quote["tax_registrations"]["company"]["bn"] == "333333333"
```

- [ ] **Step 2: Lancer pour vérifier qu'ils échouent**

Run: `pytest tests/test_tax_registrations_integration.py::TestSnapshotOnCreate -v`
Expected: tous échouent (pas de `tax_registrations` dans réponse).

- [ ] **Step 3: Ajouter helper snapshot dans `server.py`**

Ajouter après les helpers Task 1 (avant `client = MongoClient...`) :

```python
def _build_tax_registrations(user_id, client_id):
    """Snapshot des 10 numéros : 5 entreprise + 5 client. Champs vides si absents."""
    settings = db.company_settings.find_one({"user_id": user_id}, {"_id": 0}) or {}
    client_doc = db.clients.find_one({"id": client_id, "user_id": user_id}, {"_id": 0}) or {}
    def take(doc, field):
        return doc.get(field, "")
    return {
        "company": {
            "bn":  take(settings, "bn_number"),
            "gst": take(settings, "gst_number"),
            "qst": take(settings, "qst_number"),
            "hst": take(settings, "hst_number"),
            "neq": take(settings, "neq_number"),
        },
        "client": {
            "bn":  take(client_doc, "bn_number"),
            "gst": take(client_doc, "gst_number"),
            "qst": take(client_doc, "qst_number"),
            "hst": take(client_doc, "hst_number"),
            "neq": take(client_doc, "neq_number"),
        },
    }
```

- [ ] **Step 4: Brancher dans POST /api/invoices**

Trouver `@app.post("/api/invoices")` (ligne ~380). Juste avant `db.invoices.insert_one(...)`, ajouter :

```python
    new_invoice["tax_registrations"] = _build_tax_registrations(current_user.id, client_id)
```

Pareil pour `@app.post("/api/quotes")` (chercher avec grep).

- [ ] **Step 5: Lancer les tests**

Run :
```bash
lsof -ti:8000 | xargs kill 2>/dev/null
cd backend && source .venv/bin/activate
uvicorn server:app --port 8000 &
sleep 4
pytest tests/test_tax_registrations_integration.py::TestSnapshotOnCreate -v
```

Expected: 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/server.py backend/tests/test_tax_registrations_integration.py
git commit -m "feat(taxes): snapshot tax_registrations sur création invoice/quote"
```

---

## Task 6 : Convert devis → facture conserve le snapshot

**Files:**
- Modify: `backend/server.py` (endpoint `/api/quotes/{id}/convert`)
- Modify: `backend/tests/test_tax_registrations_integration.py`

- [ ] **Step 1: Écrire le test**

Ajouter à `TestSnapshotOnCreate` :

```python
    def test_convert_carries_snapshot(self, auth):
        requests.put(f"{BASE_URL}/api/settings/company", headers=auth,
                      json={"bn_number": "222222222"})
        client = requests.post(f"{BASE_URL}/api/clients", headers=auth,
                                json={"name": "Convert Test"}).json()
        q = requests.post(f"{BASE_URL}/api/quotes", headers=auth, json={
            "client_id": client["id"],
            "items": [{"description": "convert", "quantity": 1, "unit_price": 30}],
            "province": "QC",
        }).json()
        # Avant de convertir, modifier settings
        requests.put(f"{BASE_URL}/api/settings/company", headers=auth,
                      json={"bn_number": "444444444"})
        # Convert
        conv = requests.post(f"{BASE_URL}/api/quotes/{q['id']}/convert", headers=auth)
        assert conv.status_code in (200, 201), conv.text
        inv = conv.json()
        # La facture doit avoir le snapshot du DEVIS (numéro original 222...)
        assert inv["tax_registrations"]["company"]["bn"] == "222222222"
```

- [ ] **Step 2: Lancer pour échec**

Run: `pytest tests/test_tax_registrations_integration.py::TestSnapshotOnCreate::test_convert_carries_snapshot -v`
Expected: FAIL.

- [ ] **Step 3: Modifier `/api/quotes/{id}/convert` dans `server.py`**

Trouver l'endpoint convert (avec `grep -n "convert" backend/server.py`). Dans le bloc qui construit le nouveau doc facture à partir du devis, ajouter (avant insert) :

```python
    # Carry over the snapshot from the quote — keep the moment-of-quote registrations
    new_invoice["tax_registrations"] = quote.get("tax_registrations") or \
        _build_tax_registrations(current_user.id, quote.get("client_id"))
```

Le fallback `_build_tax_registrations` sert si le devis est antérieur à la migration et n'a pas de snapshot.

- [ ] **Step 4: Lancer**

Run :
```bash
lsof -ti:8000 | xargs kill 2>/dev/null
cd backend && source .venv/bin/activate
uvicorn server:app --port 8000 &
sleep 4
pytest tests/test_tax_registrations_integration.py::TestSnapshotOnCreate::test_convert_carries_snapshot -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/server.py backend/tests/test_tax_registrations_integration.py
git commit -m "feat(taxes): convert quote→invoice conserve tax_registrations"
```

---

## Task 7 : Appel migration au démarrage du backend

**Files:**
- Modify: `backend/server.py` (section startup, autour de la ligne 1626+)

- [ ] **Step 1: Repérer où sont créés les index au startup**

Run: `grep -n "create_index" backend/server.py | head`
Note la position du dernier `create_index`.

- [ ] **Step 2: Ajouter l'appel à `migrate_pst_to_qst()`**

Dans le bloc startup, juste après le dernier `create_index` (et avant le bloc `existing = db.users.find_one(...)`) :

```python
        print("Database indexes created")

        # Migration tax_registrations (Section 2 du spec) — idempotente
        migrate_pst_to_qst()

        existing = db.users.find_one({"email": "gussdub@gmail.com"})
```

- [ ] **Step 3: Vérifier au redémarrage**

Run :
```bash
lsof -ti:8000 | xargs kill 2>/dev/null
cd backend && source .venv/bin/activate
uvicorn server:app --port 8000 2>&1 | head -20
```

Expected: parmi les logs au démarrage, voir soit `Migrated N company_settings: pst_number → qst_number` (si la DB locale avait des docs `pst_number`), soit aucune ligne supplémentaire (si déjà migré). Pas d'erreur.

- [ ] **Step 4: Vérifier idempotence — redémarrer une 2e fois**

Run :
```bash
lsof -ti:8000 | xargs kill 2>/dev/null
cd backend && source .venv/bin/activate
uvicorn server:app --port 8000 2>&1 | head -20
```

Expected: cette fois aucune ligne "Migrated N" (0 documents to migrate).

- [ ] **Step 5: Commit**

```bash
git add backend/server.py
git commit -m "feat(taxes): exécuter migrate_pst_to_qst au démarrage du backend"
```

---

## Task 8 : PDF — entête épuré, boîte client enrichie, encadré bas

**Files:**
- Modify: `backend/server.py` (fonction `generate_document_pdf` lignes 1078-1311)

Cette task touche plusieurs sections de la même fonction. On garde tout dans un seul commit pour cohérence, mais les changements sont segmentés en sous-steps clairs.

- [ ] **Step 1: Repérer les 4 zones de modification**

Run :
```bash
grep -n "gst = company_settings.get\|bill_to.append.*client_email\|elements.append(Spacer(1, 0.5\|terms = document.get" backend/server.py
```

Note les lignes :
- Lignes 1138-1143 : suppression TPS/TVQ dans entête entreprise
- Lignes ~1207-1209 : insertion numéros client dans boîte "Facturer à"
- Lignes ~1305-1307 : insertion encadré "Numéros d'enregistrement" avant footer

- [ ] **Step 2: Étape 2.A — Supprimer les lignes TPS/TVQ de l'entête entreprise**

Remplacer ce bloc (lignes ~1138-1143) :

```python
    gst = company_settings.get('gst_number', '')
    pst = company_settings.get('pst_number', '')
    if gst:
        left_parts.append(Paragraph(f"TPS: {gst}", small_style))
    if pst:
        left_parts.append(Paragraph(f"TVQ: {pst}", small_style))
```

Par (entête plus épuré, plus de numéros sous l'adresse) :

```python
    # Les numéros officiels sont désormais affichés dans l'encadré en bas de page.
```

- [ ] **Step 3: Étape 2.B — Ajouter helper récupération snapshot**

Juste avant l'appel à `generate_document_pdf` (ou en haut de la fonction), ajouter un helper qui choisit snapshot vs fallback :

À l'intérieur de `generate_document_pdf`, juste après la signature et les imports de style, ajouter :

```python
    # Récupère le snapshot des numéros officiels si présent, sinon fallback sur company_settings actuel + client doc
    tax_regs = document.get('tax_registrations') or {
        "company": {
            "bn":  company_settings.get('bn_number', ''),
            "gst": company_settings.get('gst_number', ''),
            "qst": company_settings.get('qst_number', ''),
            "hst": company_settings.get('hst_number', ''),
            "neq": company_settings.get('neq_number', ''),
        },
        "client": {
            "bn":  (client_info or {}).get('bn_number', ''),
            "gst": (client_info or {}).get('gst_number', ''),
            "qst": (client_info or {}).get('qst_number', ''),
            "hst": (client_info or {}).get('hst_number', ''),
            "neq": (client_info or {}).get('neq_number', ''),
        },
    }
```

- [ ] **Step 4: Étape 2.C — Boîte "Facturer à" : ajouter ligne numéros client**

Juste après le bloc qui ajoute l'email du client à `bill_to` (autour ligne 1207-1209) :

```python
    if client_email:
        bill_to.append(Spacer(1, 3))
        bill_to.append(Paragraph(client_email, ParagraphStyle('ClientEmail', parent=small_style, leading=14)))

    # Numéros officiels du client (B2B), affichés en monospace, seulement si renseignés
    client_regs = tax_regs.get('client', {})
    client_num_parts = []
    if client_regs.get('bn'):  client_num_parts.append(f"BN {client_regs['bn']}")
    if client_regs.get('gst'): client_num_parts.append(f"TPS {client_regs['gst']}")
    if client_regs.get('qst'): client_num_parts.append(f"TVQ {client_regs['qst']}")
    if client_regs.get('hst'): client_num_parts.append(f"TVH {client_regs['hst']}")
    if client_regs.get('neq'): client_num_parts.append(f"NEQ {client_regs['neq']}")
    if client_num_parts:
        bill_to.append(Spacer(1, 4))
        client_nums_style = ParagraphStyle('ClientNums', parent=small_style,
                                            fontName='Courier', fontSize=8, leading=11)
        bill_to.append(Paragraph(' &nbsp;·&nbsp; '.join(client_num_parts), client_nums_style))
```

- [ ] **Step 5: Étape 2.D — Encadré "Numéros d'enregistrement" en bas de page**

Juste après le bloc Terms et avant le footer "Merci" (autour ligne 1303-1307) :

```python
    # Terms
    terms = document.get('terms', '')
    if terms:
        elements.append(Spacer(1, 0.3*inch))
        elements.append(Paragraph("<b>Conditions generales:</b>", company_style))
        elements.append(Spacer(1, 4))
        elements.append(Paragraph(terms, terms_style))

    # Encadré "Numéros d'enregistrement" (côté entreprise), si au moins un renseigné
    company_regs = tax_regs.get('company', {})
    company_num_parts = []
    if company_regs.get('bn'):  company_num_parts.append(f"BN {company_regs['bn']}")
    if company_regs.get('gst'): company_num_parts.append(f"TPS {company_regs['gst']}")
    if company_regs.get('qst'): company_num_parts.append(f"TVQ {company_regs['qst']}")
    if company_regs.get('hst'): company_num_parts.append(f"TVH {company_regs['hst']}")
    if company_regs.get('neq'): company_num_parts.append(f"NEQ {company_regs['neq']}")
    if company_num_parts:
        elements.append(Spacer(1, 0.3*inch))
        reg_title_style = ParagraphStyle('RegTitle', parent=small_style,
                                          fontName='Helvetica-Bold', fontSize=8.5, textColor=dark)
        reg_body_style = ParagraphStyle('RegBody', parent=small_style,
                                         fontName='Courier', fontSize=8, leading=11)
        reg_inner = [
            Paragraph("Numeros d'enregistrement", reg_title_style),
            Spacer(1, 3),
            Paragraph(' &nbsp;·&nbsp; '.join(company_num_parts), reg_body_style),
        ]
        reg_table = Table([[reg_inner]], colWidths=[7*inch])
        reg_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), HexColor('#f8fafb')),
            ('BOX', (0, 0), (-1, -1), 0.5, HexColor('#e5e7eb')),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 14),
            ('RIGHTPADDING', (0, 0), (-1, -1), 14),
        ]))
        elements.append(reg_table)

    # Footer
    elements.append(Spacer(1, 0.5*inch))
    elements.append(Paragraph(f"Merci pour votre confiance ! — {comp_name}", ParagraphStyle('Footer', parent=styles['Normal'], fontSize=10, textColor=teal, alignment=TA_CENTER)))
```

- [ ] **Step 6: Tester manuellement la génération PDF**

Run :
```bash
lsof -ti:8000 | xargs kill 2>/dev/null
cd backend && source .venv/bin/activate
uvicorn server:app --port 8000 &
sleep 4

# Trouver un invoice ID existant
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
   -H "Content-Type: application/json" \
   -d '{"email":"gussdub@gmail.com","password":"testpass123"}' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

INVOICE_ID=$(curl -s http://localhost:8000/api/invoices -H "Authorization: Bearer $TOKEN" | python -c "import sys,json;print(json.load(sys.stdin)[0]['id'])")

# Télécharger le PDF
curl -s http://localhost:8000/api/invoices/$INVOICE_ID/pdf \
   -H "Authorization: Bearer $TOKEN" -o /tmp/test-invoice.pdf

# Vérifier que le PDF est valide
file /tmp/test-invoice.pdf
```

Expected:
- `/tmp/test-invoice.pdf: PDF document, version 1.x`
- Ouvrir le PDF (`open /tmp/test-invoice.pdf` sur macOS) :
  - Entête entreprise : pas de ligne "TPS:" ni "TVQ:" sous l'adresse
  - Boîte "Facturer à :" : numéros client en monospace si configurés, sinon rien
  - Bas de page : encadré "Numéros d'enregistrement" avec les numéros entreprise

- [ ] **Step 7: Test fallback sur vieille facture sans snapshot**

Insérer manuellement un doc invoice sans `tax_registrations` :

Run :
```bash
mongosh facturepro --quiet --eval '
  db.invoices.updateOne({}, {$unset: {tax_registrations: ""}})
  print("Snapshot removed from one invoice for fallback test")
'
```

Re-télécharger le PDF de ce invoice : doit afficher les numéros actuels depuis settings (fallback fonctionne).

- [ ] **Step 8: Commit**

```bash
git add backend/server.py
git commit -m "feat(taxes): PDF entête épuré + boîte client enrichie + encadré numéros"
```

---

## Task 9 : Frontend `SettingsPage.js` — section "Numéros officiels"

**Files:**
- Modify: `frontend/src/pages/SettingsPage.js`

- [ ] **Step 1: Repérer la structure actuelle**

Run: `head -80 "frontend/src/pages/SettingsPage.js"` pour comprendre le pattern de champs (state, onChange, etc.).

- [ ] **Step 2: Ajouter les 5 nouveaux champs au state**

Dans le `useState` initial des settings, ajouter `bn_number`, `qst_number`, `neq_number` (`gst_number` et `hst_number` existent déjà) :

```javascript
const [settings, setSettings] = useState({
  // ... champs existants ...
  bn_number: '',
  gst_number: '',
  qst_number: '',
  hst_number: '',
  neq_number: '',
  tax_number_warnings: {},
});
```

S'assurer que le `useEffect` qui charge les settings depuis `/api/settings/company` initialise bien ces 5 champs (`response.data` les contient maintenant grâce à Task 3).

- [ ] **Step 3: Helper de validation côté JS (miroir du backend)**

Ajouter en haut du composant ou dans un fichier helpers :

```javascript
const TAX_FORMATS = {
  bn:  { regex: /^\d{9}$/,          hint: '9 chiffres' },
  gst: { regex: /^\d{9}RT\d{4}$/,   hint: '9 chiffres + RT0001' },
  qst: { regex: /^\d{10}TQ\d{4}$/,  hint: '10 chiffres + TQ0001' },
  hst: { regex: /^\d{9}RT\d{4}$/,   hint: '9 chiffres + RT0001' },
  neq: { regex: /^\d{10}$/,         hint: '10 chiffres' },
};

const TAX_FIELD_KINDS = {
  bn_number: 'bn', gst_number: 'gst', qst_number: 'qst',
  hst_number: 'hst', neq_number: 'neq',
};

const normalizeTaxNumber = (v) => (v || '').trim().toUpperCase().replace(/[\s-]/g, '');

const checkTaxNumber = (value, fieldName) => {
  if (!value) return { valid: true, expected: '' };
  const kind = TAX_FIELD_KINDS[fieldName];
  const { regex, hint } = TAX_FORMATS[kind];
  return { valid: regex.test(value), expected: hint };
};
```

- [ ] **Step 4: Composant `<TaxNumberInput />` réutilisable**

Ajouter dans le même fichier (ou un fichier composant séparé `frontend/src/components/TaxNumberInput.js`) :

```javascript
function TaxNumberInput({ label, fieldName, value, onChange, placeholder, tooltip }) {
  const [touched, setTouched] = React.useState(false);
  const check = checkTaxNumber(value, fieldName);
  const showWarning = touched && value && !check.valid;
  const showOk = touched && value && check.valid;
  const borderColor = showWarning ? '#f59e0b' : showOk ? '#10b981' : '#d1d5db';

  return (
    <div style={{ marginBottom: 14 }}>
      <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 500, color: '#374151', marginBottom: 4 }}>
        {label}
        {tooltip && (
          <span title={tooltip} style={{ cursor: 'help', color: '#6b7280', fontSize: 14 }}>ⓘ</span>
        )}
      </label>
      <input
        type="text"
        value={value || ''}
        placeholder={placeholder}
        onChange={(e) => onChange(normalizeTaxNumber(e.target.value))}
        onBlur={() => setTouched(true)}
        style={{
          width: '100%',
          padding: '8px 10px',
          border: `1.5px solid ${borderColor}`,
          borderRadius: 6,
          fontSize: 13,
          fontFamily: 'monospace',
          outline: 'none',
        }}
      />
      {showWarning && (
        <div style={{ marginTop: 4, fontSize: 12, color: '#b45309' }}>
          ⚠️ Format inhabituel — attendu&nbsp;: {check.expected}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Ajouter la section "Numéros officiels"**

Dans le JSX de SettingsPage, après les champs adresse/téléphone, ajouter :

```jsx
<div style={{ marginTop: 24, padding: 20, background: '#f9fafb', borderRadius: 8 }}>
  <h3 style={{ margin: '0 0 12px', fontSize: 16, color: '#1f2937' }}>Numéros officiels</h3>
  <p style={{ marginTop: 0, fontSize: 13, color: '#6b7280' }}>
    Ces numéros apparaissent dans l'encadré "Numéros d'enregistrement" en bas de tes factures et devis.
  </p>
  <TaxNumberInput
    label="BN — Numéro d'entreprise fédéral"
    fieldName="bn_number"
    value={settings.bn_number}
    onChange={(v) => setSettings({ ...settings, bn_number: v })}
    placeholder="123456789"
    tooltip="9 chiffres attribués par l'ARC"
  />
  <TaxNumberInput
    label="TPS / GST"
    fieldName="gst_number"
    value={settings.gst_number}
    onChange={(v) => setSettings({ ...settings, gst_number: v })}
    placeholder="123456789RT0001"
    tooltip="BN suivi de RT0001"
  />
  <TaxNumberInput
    label="TVQ / QST"
    fieldName="qst_number"
    value={settings.qst_number}
    onChange={(v) => setSettings({ ...settings, qst_number: v })}
    placeholder="1234567890TQ0001"
    tooltip="10 chiffres suivis de TQ0001 (Revenu Québec)"
  />
  <TaxNumberInput
    label="TVH / HST"
    fieldName="hst_number"
    value={settings.hst_number}
    onChange={(v) => setSettings({ ...settings, hst_number: v })}
    placeholder="123456789RT0001"
    tooltip="Pour ON, NB, NS, PE, NL (taxe harmonisée)"
  />
  <TaxNumberInput
    label="NEQ — Numéro d'entreprise Québec"
    fieldName="neq_number"
    value={settings.neq_number}
    onChange={(v) => setSettings({ ...settings, neq_number: v })}
    placeholder="1234567890"
    tooltip="10 chiffres attribués par le REQ (corporations QC)"
  />
</div>
```

- [ ] **Step 6: S'assurer que le PUT envoie ces champs**

Vérifier que le handler de submit envoie bien les 5 nouveaux champs (`bn_number`, `qst_number`, `neq_number`). Normalement, si on POST `settings` au backend, et que `settings` contient ces clés, c'est OK.

- [ ] **Step 7: Test manuel**

Run :
```bash
# Backend doit tourner
lsof -ti:8000 || (cd backend && source .venv/bin/activate && uvicorn server:app --port 8000 &)

# Frontend
cd frontend && npm start
```

Vérifier dans le navigateur (http://localhost:3000) :
- Aller dans Settings
- Section "Numéros officiels" visible
- Saisir BN `123456789` → border verte
- Saisir BN `abc` → border jaune + texte d'aide
- Coller "123 456 789 RT 0001" → normalisé en `123456789RT0001`
- Save → recharger : valeurs persistées normalisées

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/SettingsPage.js
git commit -m "feat(taxes): SettingsPage section 'Numéros officiels' (5 champs + validation souple)"
```

---

## Task 10 : Frontend `ClientsPage.js` — section repliable

**Files:**
- Modify: `frontend/src/pages/ClientsPage.js`

- [ ] **Step 1: Repérer la structure du formulaire client**

Run: `grep -n "name=\|client.name\|address\|email" frontend/src/pages/ClientsPage.js | head -20`

Repérer le formulaire de création/édition de client (probablement un modal ou panneau).

- [ ] **Step 2: Importer le helper `TaxNumberInput`**

Si TaxNumberInput est défini dans SettingsPage, l'extraire dans un fichier commun :

Créer `frontend/src/components/TaxNumberInput.js` (déplacer le composant + helpers depuis Task 9) et l'importer dans les deux pages :

```javascript
// SettingsPage.js et ClientsPage.js
import TaxNumberInput from '../components/TaxNumberInput';
```

- [ ] **Step 3: Ajouter le state des 5 champs au formulaire client**

Le state existant des champs client devrait être étendu :

```javascript
const [form, setForm] = useState({
  // ... champs existants ...
  bn_number: '',
  gst_number: '',
  qst_number: '',
  hst_number: '',
  neq_number: '',
});
```

S'assurer que `useEffect` (ou setForm à l'édition) initialise ces champs depuis le client existant.

- [ ] **Step 4: Ajouter une section repliable**

Ajouter dans le JSX du formulaire, après les champs adresse :

```jsx
const [showTaxNumbers, setShowTaxNumbers] = useState(false);

// ...
<div style={{ marginTop: 16, borderTop: '1px solid #e5e7eb', paddingTop: 12 }}>
  <button
    type="button"
    onClick={() => setShowTaxNumbers(!showTaxNumbers)}
    style={{ background: 'none', border: 0, padding: 0, color: '#00A08C',
              fontSize: 13, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
  >
    <span>{showTaxNumbers ? '▼' : '▶'}</span>
    Numéros officiels (B2B, optionnel)
  </button>

  {showTaxNumbers && (
    <div style={{ marginTop: 12 }}>
      <TaxNumberInput label="BN" fieldName="bn_number"
        value={form.bn_number} placeholder="123456789"
        onChange={(v) => setForm({ ...form, bn_number: v })} />
      <TaxNumberInput label="TPS" fieldName="gst_number"
        value={form.gst_number} placeholder="123456789RT0001"
        onChange={(v) => setForm({ ...form, gst_number: v })} />
      <TaxNumberInput label="TVQ" fieldName="qst_number"
        value={form.qst_number} placeholder="1234567890TQ0001"
        onChange={(v) => setForm({ ...form, qst_number: v })} />
      <TaxNumberInput label="TVH" fieldName="hst_number"
        value={form.hst_number} placeholder="123456789RT0001"
        onChange={(v) => setForm({ ...form, hst_number: v })} />
      <TaxNumberInput label="NEQ" fieldName="neq_number"
        value={form.neq_number} placeholder="1234567890"
        onChange={(v) => setForm({ ...form, neq_number: v })} />
    </div>
  )}
</div>
```

- [ ] **Step 5: S'assurer que le submit envoie les champs**

Le handler POST/PUT doit déjà sérialiser tout `form`. Pas de changement supplémentaire.

- [ ] **Step 6: Test manuel**

Naviguer dans le frontend :
- Clients page → Créer un nouveau client
- Voir le bouton "▶ Numéros officiels (B2B, optionnel)" replié par défaut
- Déplier → 5 champs apparaissent
- Saisir BN `987654321` → border verte
- Save → revenir dans la liste → ré-éditer → les valeurs sont là

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/ClientsPage.js frontend/src/components/TaxNumberInput.js frontend/src/pages/SettingsPage.js
git commit -m "feat(taxes): ClientsPage section repliable 'Numéros officiels' B2B"
```

---

## Task 11 : Tests E2E final + push prod

**Files:** (vérification uniquement)

- [ ] **Step 1: Re-lancer toute la batterie de tests**

Run :
```bash
lsof -ti:8000 | xargs kill 2>/dev/null
cd backend && source .venv/bin/activate
uvicorn server:app --port 8000 &
sleep 4
pytest tests/test_tax_numbers.py tests/test_tax_registrations_integration.py -v
```

Expected: **tous PASS** (helpers + migration + settings + clients + snapshot + convert).

- [ ] **Step 2: Génération PDF e2e — facture B2B complète**

Via UI ou API :
1. Configurer Settings avec BN, TPS, TVQ, NEQ
2. Créer un nouveau client B2B avec BN + TPS
3. Créer une facture pour ce client
4. Télécharger le PDF
5. Ouvrir : vérifier
   - Entête entreprise propre (pas de TPS/TVQ sous adresse)
   - "Facturer à :" : ligne `BN 987... · TPS 987...RT0001`
   - Bas de page : encadré gris pâle "Numéros d'enregistrement" avec BN/TPS/TVQ/NEQ entreprise

- [ ] **Step 3: Vérifier qu'on n'a rien cassé sur les anciennes factures**

Récupérer une facture créée AVANT cette feature (sans `tax_registrations` en DB) :

```bash
mongosh facturepro --quiet --eval 'db.invoices.find({tax_registrations: {$exists: false}}).limit(1)'
```

Si présente, télécharger son PDF — doit afficher les numéros via fallback (lit `company_settings` actuel). Pas de crash.

- [ ] **Step 4: Vérifier en prod (Render + Vercel) après push**

Le push déclenche un redeploy automatique. Attendre ~3 min puis :

```bash
# Vérifier que le backend Render démarre OK (log doit montrer "Database indexes created" puis migration éventuelle)
# Tester via curl
curl -s -m 90 https://facturepro-backend-dkvn.onrender.com/api/health
```

Expected: `{"status":"healthy","database":"connected"}`.

Aller sur https://facturepro.ca, force refresh (Cmd+Shift+R), tester la même e2e qu'en local.

- [ ] **Step 5: Push final vers prod**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git push origin main
```

Expected: `main → main` succès, Render + Vercel déclenchent le redeploy.

- [ ] **Step 6: Update CLAUDE.md avec la nouvelle feature**

Modifier la section "Workflow" de `CLAUDE.md` pour mentionner :

```markdown
## Features livrées

- **2026-06-16** — Numéros officiels canadiens sur PDF (feature #2)
  - 5 champs (BN, TPS, TVQ, TVH, NEQ) côté entreprise et côté client
  - Snapshot sur factures/devis pour immutabilité audit
  - Validation souple, normalisation à la saisie
  - Spec : `docs/superpowers/specs/2026-06-16-tax-registrations-design.md`
  - Plan : `docs/superpowers/plans/2026-06-16-tax-registrations.md`
```

Commit + push :
```bash
git add CLAUDE.md
git commit -m "docs: mise à jour CLAUDE.md avec feature tax-registrations livrée"
git push origin main
```

---

## Récap fichiers touchés

| Fichier | Tâches | Nature |
|---|---|---|
| `backend/server.py` | 1, 2, 3, 4, 5, 6, 7, 8 | Modif (helpers + migration + 6 endpoints + 1 fonction PDF + startup) |
| `backend/requirements-dev.txt` | 0 | Nouveau |
| `backend/tests/test_tax_numbers.py` | 1, 2 | Nouveau |
| `backend/tests/test_tax_registrations_integration.py` | 3, 4, 5, 6 | Nouveau |
| `frontend/src/components/TaxNumberInput.js` | 9, 10 | Nouveau |
| `frontend/src/pages/SettingsPage.js` | 9 | Modif |
| `frontend/src/pages/ClientsPage.js` | 10 | Modif |
| `CLAUDE.md` | 11 | Modif (changelog) |

Commits attendus : **11** (un par task + 1 commit doc final).
