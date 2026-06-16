# Expense Categories ARC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter la catégorisation des dépenses sur les lignes ARC officielles (T2125/T2 GIFI) avec snapshot du % déductible, picker UI groupé, et sélecteur d'entité fiscale dans Settings.

**Architecture:** Constante module-level `EXPENSE_CATEGORIES` (~18 catégories en 5 groupes) côté backend, exposée via un endpoint GET public. Chaque dépense capture un snapshot immutable des métadonnées (code, label, ligne ARC, % déductible, montant déductible calculé). PUT recalcule sélectivement selon ce qui a changé. Frontend ExpensesPage utilise un `<select>` natif groupé avec zone d'aide contextuelle pour les catégories partiellement déductibles. SettingsPage gagne un sélecteur d'entité fiscale (T2125 vs T2). Aucune migration de données (0 dépense en prod).

**Tech Stack:** FastAPI Python 3.11 + pymongo, React 18 CRA, pytest, MongoDB Atlas. Pas de nouvelle dépendance.

**Spec source:** [docs/superpowers/specs/2026-06-16-expense-categories-design.md](../specs/2026-06-16-expense-categories-design.md)

---

## File Structure

**Created:**
- `backend/tests/test_expense_categories.py` — tests unitaires des constantes + helpers (~120 lignes)
- `backend/tests/test_expense_categories_integration.py` — tests intégration HTTP des endpoints (~200 lignes)

**Modified:**
- `backend/server.py` — constantes `EXPENSE_CATEGORIES` + `EXPENSE_CATEGORY_GROUPS` (~50 lignes), helpers `_find_category` et `_build_expense_category_snapshot` (~30 lignes), endpoint GET `/api/expense-categories` (~5 lignes), POST/PUT `/api/expenses` (~20 lignes), GET/PUT `/api/settings/company` (~10 lignes)
- `frontend/src/pages/SettingsPage.js` — entity_type select (~25 lignes)
- `frontend/src/pages/ExpensesPage.js` — fetch categories + grouped picker + custom input + helper (~80 lignes)
- `CLAUDE.md` — changelog feature livrée (~10 lignes)

---

## Task 1 — Constantes EXPENSE_CATEGORIES et EXPENSE_CATEGORY_GROUPS + helper `_find_category`

**Files:**
- Create: `backend/tests/test_expense_categories.py`
- Modify: `backend/server.py` (ajouter après les helpers de la feature #2, avant `client = MongoClient(...)`)

- [ ] **Step 1: Écrire les tests unitaires d'abord**

Créer `backend/tests/test_expense_categories.py` :

```python
"""Tests unitaires pour les catégories de dépenses ARC (feature #3)."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "facturepro_test_unit")
os.environ.setdefault("JWT_SECRET", "test")

from server import EXPENSE_CATEGORIES, EXPENSE_CATEGORY_GROUPS, _find_category


class TestExpenseCategoriesConstant:
    def test_has_18_entries(self):
        # 17 canoniques + "other"
        assert len(EXPENSE_CATEGORIES) == 18

    def test_each_entry_has_required_keys(self):
        required = {"code", "label_fr", "label_en", "arc_line", "deductible_percentage", "group"}
        for cat in EXPENSE_CATEGORIES:
            assert required.issubset(cat.keys()), f"Missing keys in {cat['code']}: {required - cat.keys()}"

    def test_each_code_is_unique(self):
        codes = [c["code"] for c in EXPENSE_CATEGORIES]
        assert len(codes) == len(set(codes)), "Duplicate code(s) detected"

    def test_meals_entertainment_is_50_percent(self):
        cat = _find_category("meals_entertainment")
        assert cat is not None
        assert cat["deductible_percentage"] == 50
        assert cat["arc_line"] == "8523"
        assert cat["group"] == "marketing"

    def test_office_expenses_is_100_percent(self):
        cat = _find_category("office_expenses")
        assert cat is not None
        assert cat["deductible_percentage"] == 100
        assert cat["arc_line"] == "8810"

    def test_other_category_present(self):
        cat = _find_category("other")
        assert cat is not None
        assert cat["arc_line"] == ""
        assert cat["deductible_percentage"] == 100
        assert cat["group"] == "other"

    def test_all_non_meals_are_100_percent(self):
        for cat in EXPENSE_CATEGORIES:
            if cat["code"] != "meals_entertainment":
                assert cat["deductible_percentage"] == 100, f"{cat['code']} should be 100%"

    def test_groups_are_known(self):
        valid_groups = set(EXPENSE_CATEGORY_GROUPS.keys())
        for cat in EXPENSE_CATEGORIES:
            assert cat["group"] in valid_groups, f"{cat['code']} has unknown group {cat['group']}"


class TestExpenseCategoryGroups:
    def test_has_6_groups(self):
        assert set(EXPENSE_CATEGORY_GROUPS.keys()) == {
            "office", "marketing", "premises", "travel", "personnel", "other"
        }

    def test_french_labels(self):
        assert EXPENSE_CATEGORY_GROUPS["marketing"] == "Marketing"
        assert EXPENSE_CATEGORY_GROUPS["other"] == "Autre"


class TestFindCategory:
    def test_returns_dict_for_canonical_code(self):
        cat = _find_category("rent")
        assert cat["label_fr"] == "Loyer"
        assert cat["arc_line"] == "8910"

    def test_returns_none_for_unknown(self):
        assert _find_category("definitely_not_a_real_code") is None

    def test_returns_none_for_empty(self):
        assert _find_category("") is None

    def test_returns_none_for_none(self):
        assert _find_category(None) is None
```

- [ ] **Step 2: Lancer pour vérifier que les tests échouent**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
pytest tests/test_expense_categories.py -v 2>&1 | tail -20
```

Expected: `ImportError: cannot import name 'EXPENSE_CATEGORIES' from 'server'`

- [ ] **Step 3: Implémenter les constantes et le helper dans `server.py`**

Dans `backend/server.py`, ajouter ce bloc juste après les helpers de la feature #2 (`_take_regs`, `_build_tax_registrations`, `_reg_label_parts`, autour de la ligne ~125), AVANT la fonction `client = MongoClient(...)` :

```python
# ─── Expense categories ARC (feature #3 du spec expense-categories) ───

EXPENSE_CATEGORY_GROUPS = {
    "office":    "Bureau et administration",
    "marketing": "Marketing",
    "premises":  "Local et services publics",
    "travel":    "Déplacements et véhicule",
    "personnel": "Personnel et services",
    "other":     "Autre",
}

EXPENSE_CATEGORIES = [
    # Bureau et administration
    {"code": "office_expenses",    "label_fr": "Frais de bureau",         "label_en": "Office expenses",         "arc_line": "8810", "deductible_percentage": 100, "group": "office"},
    {"code": "office_supplies",    "label_fr": "Fournitures",             "label_en": "Office supplies",         "arc_line": "8811", "deductible_percentage": 100, "group": "office"},
    {"code": "professional_fees",  "label_fr": "Honoraires professionnels","label_en": "Professional fees",      "arc_line": "8860", "deductible_percentage": 100, "group": "office"},
    {"code": "bank_charges",       "label_fr": "Frais bancaires",         "label_en": "Bank charges",            "arc_line": "8620", "deductible_percentage": 100, "group": "office"},
    {"code": "subscriptions",      "label_fr": "Abonnements et licences", "label_en": "Subscriptions & licences", "arc_line": "8740", "deductible_percentage": 100, "group": "office"},
    # Marketing
    {"code": "advertising",        "label_fr": "Publicité et promotion",  "label_en": "Advertising & promotion", "arc_line": "8520", "deductible_percentage": 100, "group": "marketing"},
    {"code": "meals_entertainment","label_fr": "Repas et représentation", "label_en": "Meals & entertainment",   "arc_line": "8523", "deductible_percentage": 50,  "group": "marketing"},
    # Local et services publics
    {"code": "rent",               "label_fr": "Loyer",                   "label_en": "Rent",                    "arc_line": "8910", "deductible_percentage": 100, "group": "premises"},
    {"code": "utilities",          "label_fr": "Services publics",        "label_en": "Utilities",               "arc_line": "9220", "deductible_percentage": 100, "group": "premises"},
    {"code": "insurance",          "label_fr": "Assurances",              "label_en": "Insurance",               "arc_line": "8690", "deductible_percentage": 100, "group": "premises"},
    {"code": "repairs_maintenance","label_fr": "Entretien et réparations","label_en": "Repairs & maintenance",   "arc_line": "8960", "deductible_percentage": 100, "group": "premises"},
    # Déplacements et véhicule
    {"code": "travel",             "label_fr": "Frais de déplacement",    "label_en": "Travel",                  "arc_line": "9200", "deductible_percentage": 100, "group": "travel"},
    {"code": "vehicle_expenses",   "label_fr": "Frais de véhicule",       "label_en": "Vehicle expenses",        "arc_line": "9281", "deductible_percentage": 100, "group": "travel"},
    {"code": "delivery",           "label_fr": "Livraison et fret",       "label_en": "Delivery & freight",      "arc_line": "9275", "deductible_percentage": 100, "group": "travel"},
    # Personnel et services
    {"code": "salaries",           "label_fr": "Salaires et avantages",   "label_en": "Salaries & benefits",     "arc_line": "9060", "deductible_percentage": 100, "group": "personnel"},
    {"code": "subcontracts",       "label_fr": "Sous-traitance",          "label_en": "Subcontracts",            "arc_line": "9367", "deductible_percentage": 100, "group": "personnel"},
    {"code": "management_fees",    "label_fr": "Frais de gestion",        "label_en": "Management fees",         "arc_line": "8871", "deductible_percentage": 100, "group": "personnel"},
    # Autre
    {"code": "other",              "label_fr": "Autre",                   "label_en": "Other",                   "arc_line": "",     "deductible_percentage": 100, "group": "other"},
]


def _find_category(code):
    """Retourne le dict catalogue correspondant à code, ou None si inconnu/vide/None."""
    if not code:
        return None
    return next((c for c in EXPENSE_CATEGORIES if c["code"] == code), None)
```

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

```bash
pytest tests/test_expense_categories.py -v 2>&1 | tail -15
```

Expected: 14 passed (8 TestExpenseCategoriesConstant + 2 TestExpenseCategoryGroups + 4 TestFindCategory).

Si tu obtiens un autre compte, vérifie ton compte de classes/méthodes en relisant le code du test ci-dessus.

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/tests/test_expense_categories.py backend/server.py
git commit -m "feat(expenses): constantes EXPENSE_CATEGORIES + helper _find_category"
```

---

## Task 2 — Helper `_build_expense_category_snapshot`

**Files:**
- Modify: `backend/server.py` (ajouter le helper juste après `_find_category`)
- Modify: `backend/tests/test_expense_categories.py` (ajouter `TestBuildExpenseCategorySnapshot`)

- [ ] **Step 1: Écrire les tests**

Ajouter à la fin de `backend/tests/test_expense_categories.py` :

```python
from server import _build_expense_category_snapshot


class TestBuildExpenseCategorySnapshot:
    def test_canonical_code_uses_catalog(self):
        snap = _build_expense_category_snapshot(
            {"category_code": "office_expenses"}, amount_cad=100.0
        )
        assert snap["category"] == "Frais de bureau"
        assert snap["category_code"] == "office_expenses"
        assert snap["category_custom_label"] == ""
        assert snap["category_arc_line"] == "8810"
        assert snap["deductible_percentage"] == 100
        assert snap["deductible_amount"] == 100.0

    def test_meals_entertainment_is_50_percent_of_amount_cad(self):
        snap = _build_expense_category_snapshot(
            {"category_code": "meals_entertainment"}, amount_cad=200.0
        )
        assert snap["category"] == "Repas et représentation"
        assert snap["deductible_percentage"] == 50
        assert snap["deductible_amount"] == 100.0

    def test_other_with_custom_label(self):
        snap = _build_expense_category_snapshot(
            {"category_code": "other", "category_custom_label": "Cotisations syndicales"},
            amount_cad=50.0,
        )
        assert snap["category"] == "Cotisations syndicales"
        assert snap["category_code"] == "other"
        assert snap["category_custom_label"] == "Cotisations syndicales"
        assert snap["category_arc_line"] == ""
        assert snap["deductible_percentage"] == 100
        assert snap["deductible_amount"] == 50.0

    def test_other_without_custom_label_defaults_to_autre(self):
        snap = _build_expense_category_snapshot(
            {"category_code": "other"}, amount_cad=50.0
        )
        assert snap["category"] == "Autre"
        assert snap["category_custom_label"] == ""

    def test_unknown_code_graceful_fallback(self):
        snap = _build_expense_category_snapshot(
            {"category_code": "doesnt_exist", "category": "legacy text"},
            amount_cad=30.0,
        )
        # Use legacy "category" text as label, no arc line, 100%
        assert snap["category"] == "legacy text"
        assert snap["category_code"] == "doesnt_exist"
        assert snap["category_arc_line"] == ""
        assert snap["deductible_percentage"] == 100
        assert snap["deductible_amount"] == 30.0

    def test_empty_code_graceful_fallback(self):
        snap = _build_expense_category_snapshot(
            {"category_code": "", "category": "Old way"}, amount_cad=10.0
        )
        assert snap["category"] == "Old way"
        assert snap["category_code"] == ""
        assert snap["deductible_amount"] == 10.0

    def test_custom_label_cleared_for_non_other(self):
        snap = _build_expense_category_snapshot(
            {"category_code": "office_expenses", "category_custom_label": "Stale value"},
            amount_cad=100.0,
        )
        # Custom label is only kept when code == "other"
        assert snap["category_custom_label"] == ""

    def test_deductible_amount_rounded_2_decimals(self):
        # 33.33 * 50 / 100 = 16.665 → 16.67 (rounded half-to-even is 16.66 but Python round() gives 16.66 too)
        # Verify whatever round() does is consistent
        snap = _build_expense_category_snapshot(
            {"category_code": "meals_entertainment"}, amount_cad=33.33
        )
        assert snap["deductible_amount"] == round(33.33 * 50 / 100, 2)
```

- [ ] **Step 2: Lancer pour vérifier qu'ils échouent**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
pytest tests/test_expense_categories.py::TestBuildExpenseCategorySnapshot -v 2>&1 | tail -15
```

Expected: `ImportError: cannot import name '_build_expense_category_snapshot'`

- [ ] **Step 3: Implémenter le helper dans `server.py`**

Ajouter immédiatement après `_find_category` :

```python
def _build_expense_category_snapshot(expense_data, amount_cad):
    """Retourne les 6 champs catégorie à snapshoter dans une dépense.

    Args:
        expense_data: dict envoyé par le frontend (peut contenir category_code,
                      category_custom_label, ou un legacy 'category' libre).
        amount_cad: montant déjà converti en CAD (calcul indépendant de la devise).

    Returns:
        dict avec category, category_code, category_custom_label,
        category_arc_line, deductible_percentage, deductible_amount.

    Comportement :
    - Si category_code est un code canonique → snapshot depuis le catalogue.
    - Si category_code == "other" → utilise category_custom_label (fallback "Autre").
    - Sinon (vide, inconnu) → graceful : reprend le label legacy "category",
      arc_line="", percentage=100.
    """
    code = (expense_data.get("category_code") or "").strip()
    custom_label = expense_data.get("category_custom_label", "").strip()
    cat = _find_category(code)
    if code == "other":
        label = custom_label or "Autre"
        arc_line, percentage = "", 100
    elif cat:
        label = cat["label_fr"]
        arc_line = cat["arc_line"]
        percentage = cat["deductible_percentage"]
    else:
        # Unknown or empty code: graceful — use whatever raw category text was sent.
        label = expense_data.get("category", "")
        arc_line, percentage = "", 100
    deductible = round(amount_cad * percentage / 100, 2)
    return {
        "category": label,
        "category_code": code,
        "category_custom_label": custom_label if code == "other" else "",
        "category_arc_line": arc_line,
        "deductible_percentage": percentage,
        "deductible_amount": deductible,
    }
```

- [ ] **Step 4: Lancer les tests**

```bash
pytest tests/test_expense_categories.py -v 2>&1 | tail -15
```

Expected: 22 passed (14 prior + 8 new snapshot tests).

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_expense_categories.py
git commit -m "feat(expenses): helper _build_expense_category_snapshot"
```

---

## Task 3 — Endpoint `GET /api/expense-categories`

**Files:**
- Modify: `backend/server.py` (ajouter l'endpoint)
- Create: `backend/tests/test_expense_categories_integration.py`

- [ ] **Step 1: Écrire le test d'intégration**

Créer `backend/tests/test_expense_categories_integration.py` :

```python
"""Tests d'intégration HTTP pour les catégories de dépenses (feature #3)."""
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


class TestExpenseCategoriesEndpoint:
    def test_get_returns_200_without_auth(self):
        # Endpoint public — pas besoin de Bearer token
        resp = requests.get(f"{BASE_URL}/api/expense-categories")
        assert resp.status_code == 200

    def test_get_returns_categories_and_groups(self):
        resp = requests.get(f"{BASE_URL}/api/expense-categories")
        body = resp.json()
        assert "categories" in body
        assert "groups" in body
        assert len(body["categories"]) == 18
        assert set(body["groups"].keys()) == {
            "office", "marketing", "premises", "travel", "personnel", "other"
        }

    def test_categories_have_required_keys(self):
        resp = requests.get(f"{BASE_URL}/api/expense-categories")
        body = resp.json()
        required = {"code", "label_fr", "label_en", "arc_line", "deductible_percentage", "group"}
        for cat in body["categories"]:
            assert required.issubset(cat.keys()), f"Missing keys: {required - cat.keys()}"

    def test_meals_50_percent_present_in_response(self):
        resp = requests.get(f"{BASE_URL}/api/expense-categories")
        body = resp.json()
        meals = next((c for c in body["categories"] if c["code"] == "meals_entertainment"), None)
        assert meals is not None
        assert meals["deductible_percentage"] == 50
```

- [ ] **Step 2: Démarrer uvicorn et vérifier que les tests échouent**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
lsof -ti:8000 | xargs kill 2>/dev/null
source .venv/bin/activate
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_expense_categories_integration.py::TestExpenseCategoriesEndpoint -v 2>&1 | tail -15
```

Expected: tests FAIL (404 sur l'endpoint).

- [ ] **Step 3: Ajouter l'endpoint dans `server.py`**

Localiser une bonne place dans server.py (par exemple juste après le bloc des endpoints expenses GET/POST, autour de la ligne 712 ou avant), ajouter :

```python
@app.get("/api/expense-categories")
def get_expense_categories():
    """Liste publique des catégories ARC + groupes (utilisée par le picker frontend)."""
    return {"categories": EXPENSE_CATEGORIES, "groups": EXPENSE_CATEGORY_GROUPS}
```

Note : pas de `Depends(get_current_user_with_access)` — données publiques, non sensibles.

- [ ] **Step 4: Redémarrer uvicorn et relancer**

```bash
lsof -ti:8000 | xargs kill 2>/dev/null
source .venv/bin/activate
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_expense_categories_integration.py -v 2>&1 | tail -10
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_expense_categories_integration.py
git commit -m "feat(expenses): GET /api/expense-categories (liste publique)"
```

---

## Task 4 — Brancher `_build_expense_category_snapshot` dans POST `/api/expenses`

**Files:**
- Modify: `backend/server.py` (endpoint POST `/api/expenses` autour de la ligne 714)
- Modify: `backend/tests/test_expense_categories_integration.py` (ajouter `TestExpenseSnapshotOnCreate`)

- [ ] **Step 1: Écrire les tests**

Ajouter à `test_expense_categories_integration.py` :

```python
class TestExpenseSnapshotOnCreate:
    _cleanup_ids = []
    _auth_headers = None

    def test_canonical_category_snapshot(self, auth):
        TestExpenseSnapshotOnCreate._auth_headers = auth
        payload = {
            "description": "Achat fournitures",
            "amount": 100.0,
            "currency": "CAD",
            "category_code": "office_expenses",
            "expense_date": "2026-06-16",
        }
        resp = requests.post(f"{BASE_URL}/api/expenses", headers=auth, json=payload)
        assert resp.status_code in (200, 201), resp.text
        exp = resp.json()
        TestExpenseSnapshotOnCreate._cleanup_ids.append(exp["id"])
        assert exp["category"] == "Frais de bureau"
        assert exp["category_code"] == "office_expenses"
        assert exp["category_arc_line"] == "8810"
        assert exp["deductible_percentage"] == 100
        assert exp["deductible_amount"] == 100.0

    def test_meals_50_percent_deductible(self, auth):
        TestExpenseSnapshotOnCreate._auth_headers = auth
        payload = {
            "description": "Dîner client",
            "amount": 200.0,
            "currency": "CAD",
            "category_code": "meals_entertainment",
            "expense_date": "2026-06-16",
        }
        resp = requests.post(f"{BASE_URL}/api/expenses", headers=auth, json=payload)
        exp = resp.json()
        TestExpenseSnapshotOnCreate._cleanup_ids.append(exp["id"])
        assert exp["category"] == "Repas et représentation"
        assert exp["deductible_percentage"] == 50
        assert exp["deductible_amount"] == 100.0

    def test_other_custom_label(self, auth):
        TestExpenseSnapshotOnCreate._auth_headers = auth
        payload = {
            "description": "Cotisation pro",
            "amount": 50.0,
            "currency": "CAD",
            "category_code": "other",
            "category_custom_label": "Cotisations syndicales",
            "expense_date": "2026-06-16",
        }
        resp = requests.post(f"{BASE_URL}/api/expenses", headers=auth, json=payload)
        exp = resp.json()
        TestExpenseSnapshotOnCreate._cleanup_ids.append(exp["id"])
        assert exp["category"] == "Cotisations syndicales"
        assert exp["category_code"] == "other"
        assert exp["category_custom_label"] == "Cotisations syndicales"
        assert exp["category_arc_line"] == ""
        assert exp["deductible_percentage"] == 100

    def test_unknown_code_graceful(self, auth):
        TestExpenseSnapshotOnCreate._auth_headers = auth
        payload = {
            "description": "Edge case",
            "amount": 30.0,
            "currency": "CAD",
            "category_code": "definitely_not_real",
            "category": "Fallback label",
            "expense_date": "2026-06-16",
        }
        resp = requests.post(f"{BASE_URL}/api/expenses", headers=auth, json=payload)
        assert resp.status_code in (200, 201)  # graceful, no 4xx
        exp = resp.json()
        TestExpenseSnapshotOnCreate._cleanup_ids.append(exp["id"])
        assert exp["category"] == "Fallback label"
        assert exp["deductible_percentage"] == 100

    def test_legacy_payload_without_category_code(self, auth):
        """Rétrocompat : si frontend envoie l'ancien format (juste 'category' texte)."""
        TestExpenseSnapshotOnCreate._auth_headers = auth
        payload = {
            "description": "Legacy",
            "amount": 25.0,
            "currency": "CAD",
            "category": "Old free text",
            "expense_date": "2026-06-16",
        }
        resp = requests.post(f"{BASE_URL}/api/expenses", headers=auth, json=payload)
        assert resp.status_code in (200, 201)
        exp = resp.json()
        TestExpenseSnapshotOnCreate._cleanup_ids.append(exp["id"])
        assert exp["category"] == "Old free text"
        assert exp["category_code"] == ""
        assert exp["deductible_percentage"] == 100
        assert exp["deductible_amount"] == 25.0

    @classmethod
    def teardown_class(cls):
        if not cls._auth_headers:
            return
        for eid in cls._cleanup_ids:
            try:
                requests.delete(f"{BASE_URL}/api/expenses/{eid}", headers=cls._auth_headers)
            except Exception:
                pass
        cls._cleanup_ids = []
```

- [ ] **Step 2: Vérifier que les tests échouent**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
pytest tests/test_expense_categories_integration.py::TestExpenseSnapshotOnCreate -v 2>&1 | tail -15
```

Expected: tests FAIL — `category_code`/`deductible_amount`/etc. absents de la réponse POST.

- [ ] **Step 3: Modifier l'endpoint POST `/api/expenses` dans `server.py`**

Localiser `@app.post("/api/expenses")` (autour de la ligne 713). Le code actuel ressemble à :

```python
@app.post("/api/expenses")
def create_expense(expense_data: dict, current_user: User = Depends(get_current_user_with_access)):
    amount = float(expense_data.get("amount", 0))
    currency = expense_data.get("currency", "CAD")
    exchange_rate = expense_data.get("exchange_rate_to_cad", 1.0)
    amount_cad = round(amount / exchange_rate, 2) if exchange_rate > 0 and currency != "CAD" else amount
    doc = {
        "id": str(uuid.uuid4()), "user_id": current_user.id,
        "employee_id": expense_data.get("employee_id", ""),
        "description": expense_data.get("description", ""),
        "amount": amount, "currency": currency,
        "exchange_rate_to_cad": exchange_rate, "amount_cad": amount_cad,
        "category": expense_data.get("category", ""),
        "expense_date": expense_data.get("expense_date", datetime.now(timezone.utc).isoformat()),
        "status": "pending", "receipt_url": expense_data.get("receipt_url", ""),
        "notes": expense_data.get("notes", ""), "created_at": datetime.now(timezone.utc).isoformat()
    }
```

Modifier en gardant tout le reste et en branchant le snapshot juste avant `db.expenses.insert_one(doc)`. Remplace la ligne `"category": expense_data.get("category", ""),` du dict literal et ajoute les 5 nouveaux champs en utilisant le helper :

```python
@app.post("/api/expenses")
def create_expense(expense_data: dict, current_user: User = Depends(get_current_user_with_access)):
    amount = float(expense_data.get("amount", 0))
    currency = expense_data.get("currency", "CAD")
    exchange_rate = expense_data.get("exchange_rate_to_cad", 1.0)
    amount_cad = round(amount / exchange_rate, 2) if exchange_rate > 0 and currency != "CAD" else amount
    cat_snapshot = _build_expense_category_snapshot(expense_data, amount_cad)
    doc = {
        "id": str(uuid.uuid4()), "user_id": current_user.id,
        "employee_id": expense_data.get("employee_id", ""),
        "description": expense_data.get("description", ""),
        "amount": amount, "currency": currency,
        "exchange_rate_to_cad": exchange_rate, "amount_cad": amount_cad,
        # Catégorie : snapshot ARC (feature #3)
        **cat_snapshot,
        "expense_date": expense_data.get("expense_date", datetime.now(timezone.utc).isoformat()),
        "status": "pending", "receipt_url": expense_data.get("receipt_url", ""),
        "notes": expense_data.get("notes", ""), "created_at": datetime.now(timezone.utc).isoformat()
    }
    db.expenses.insert_one(doc)
    doc.pop("_id", None)
    return doc
```

(Le code original doit probablement déjà avoir le `insert_one + return doc` — préserve-le tel quel après ajout du snapshot.)

- [ ] **Step 4: Redémarrer uvicorn et relancer**

```bash
lsof -ti:8000 | xargs kill 2>/dev/null
source .venv/bin/activate
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_expense_categories_integration.py -v 2>&1 | tail -15
```

Expected: 9 tests PASS (4 endpoint + 5 snapshot).

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_expense_categories_integration.py
git commit -m "feat(expenses): POST snapshot catégorie ARC à la création"
```

---

## Task 5 — PUT `/api/expenses/{id}` : re-snapshot conditionnel

**Files:**
- Modify: `backend/server.py` (endpoint PUT `/api/expenses/{id}`)
- Modify: `backend/tests/test_expense_categories_integration.py` (ajouter `TestExpenseSnapshotOnUpdate`)

Behaviour:
- Si le body contient `category_code` → re-snapshot des 5 champs catégorie (label, code, custom_label, arc_line, percentage) + recalcule deductible_amount.
- Si seul `amount` change (sans `category_code` dans le body) → recalcule UNIQUEMENT deductible_amount avec le percentage déjà stocké. Les autres champs catégorie restent figés.
- Si ni l'un ni l'autre → aucun re-snapshot.

- [ ] **Step 1: Écrire les tests**

Ajouter à `test_expense_categories_integration.py` :

```python
class TestExpenseSnapshotOnUpdate:
    _cleanup_ids = []
    _auth_headers = None

    def _create(self, auth, code, amount):
        resp = requests.post(f"{BASE_URL}/api/expenses", headers=auth, json={
            "description": "Test update",
            "amount": amount,
            "currency": "CAD",
            "category_code": code,
            "expense_date": "2026-06-16",
        })
        eid = resp.json()["id"]
        TestExpenseSnapshotOnUpdate._cleanup_ids.append(eid)
        TestExpenseSnapshotOnUpdate._auth_headers = auth
        return eid

    def test_change_category_resnapshots_all_5_fields(self, auth):
        eid = self._create(auth, "office_expenses", 100)
        # Change category to meals
        upd = requests.put(f"{BASE_URL}/api/expenses/{eid}", headers=auth,
                            json={"category_code": "meals_entertainment"})
        assert upd.status_code == 200
        exp = upd.json()
        assert exp["category"] == "Repas et représentation"
        assert exp["category_code"] == "meals_entertainment"
        assert exp["category_arc_line"] == "8523"
        assert exp["deductible_percentage"] == 50
        # Amount unchanged (100) but deductible recalculated
        assert exp["deductible_amount"] == 50.0

    def test_change_amount_only_recalculates_deductible_keeps_snapshot(self, auth):
        eid = self._create(auth, "meals_entertainment", 100)
        # Change only the amount, no category_code in body
        upd = requests.put(f"{BASE_URL}/api/expenses/{eid}", headers=auth,
                            json={"amount": 200.0})
        assert upd.status_code == 200
        exp = upd.json()
        # Category snapshot UNCHANGED
        assert exp["category_code"] == "meals_entertainment"
        assert exp["category_arc_line"] == "8523"
        assert exp["deductible_percentage"] == 50
        # Deductible recalculated with new amount
        assert exp["amount"] == 200.0
        assert exp["deductible_amount"] == 100.0

    def test_update_unrelated_field_does_not_recalculate(self, auth):
        eid = self._create(auth, "meals_entertainment", 100)
        initial = requests.get(f"{BASE_URL}/api/expenses", headers=auth).json()
        initial_exp = next(e for e in initial if e["id"] == eid)
        initial_deductible = initial_exp["deductible_amount"]
        # Update only description
        upd = requests.put(f"{BASE_URL}/api/expenses/{eid}", headers=auth,
                            json={"description": "Updated description"})
        assert upd.status_code == 200
        # Deductible unchanged
        get = requests.get(f"{BASE_URL}/api/expenses", headers=auth).json()
        updated_exp = next(e for e in get if e["id"] == eid)
        assert updated_exp["deductible_amount"] == initial_deductible

    def test_change_category_to_other_with_custom_label(self, auth):
        eid = self._create(auth, "office_expenses", 80)
        upd = requests.put(f"{BASE_URL}/api/expenses/{eid}", headers=auth,
                            json={
                                "category_code": "other",
                                "category_custom_label": "Permis spécial",
                            })
        assert upd.status_code == 200
        exp = upd.json()
        assert exp["category"] == "Permis spécial"
        assert exp["category_code"] == "other"
        assert exp["category_custom_label"] == "Permis spécial"
        assert exp["category_arc_line"] == ""

    @classmethod
    def teardown_class(cls):
        if not cls._auth_headers:
            return
        for eid in cls._cleanup_ids:
            try:
                requests.delete(f"{BASE_URL}/api/expenses/{eid}", headers=cls._auth_headers)
            except Exception:
                pass
        cls._cleanup_ids = []
```

- [ ] **Step 2: Vérifier que les tests échouent**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
pytest tests/test_expense_categories_integration.py::TestExpenseSnapshotOnUpdate -v 2>&1 | tail -20
```

Expected: tests FAIL — PUT actuel applique simplement `$set` sans recalcul.

- [ ] **Step 3: Modifier l'endpoint PUT `/api/expenses/{id}` dans `server.py`**

Localiser `@app.put("/api/expenses/{expense_id}")` (autour de la ligne 733). Le code actuel est :

```python
@app.put("/api/expenses/{expense_id}")
def update_expense(expense_id: str, expense_data: dict, current_user: User = Depends(get_current_user_with_access)):
    for k in ("id", "user_id", "_id"):
        expense_data.pop(k, None)
    result = db.expenses.update_one({"id": expense_id, "user_id": current_user.id}, {"$set": expense_data})
    if result.matched_count == 0:
        raise HTTPException(404, "Expense not found")
    return clean_doc(db.expenses.find_one({"id": expense_id}, {"_id": 0}))
```

Remplacer par :

```python
@app.put("/api/expenses/{expense_id}")
def update_expense(expense_id: str, expense_data: dict, current_user: User = Depends(get_current_user_with_access)):
    for k in ("id", "user_id", "_id"):
        expense_data.pop(k, None)
    # Charger l'état actuel pour décider si on doit re-snapshot la catégorie ou recalculer deductible_amount.
    current = db.expenses.find_one({"id": expense_id, "user_id": current_user.id}, {"_id": 0})
    if current is None:
        raise HTTPException(404, "Expense not found")
    # Calculer le nouveau amount_cad si amount change
    new_amount = float(expense_data.get("amount", current.get("amount", 0)))
    new_currency = expense_data.get("currency", current.get("currency", "CAD"))
    new_rate = expense_data.get("exchange_rate_to_cad", current.get("exchange_rate_to_cad", 1.0))
    new_amount_cad = round(new_amount / new_rate, 2) if new_rate > 0 and new_currency != "CAD" else new_amount
    expense_data["amount_cad"] = new_amount_cad
    # Décider: re-snapshot complet, recalc deductible only, ou rien
    if "category_code" in expense_data:
        # Re-snapshot complet des 5 champs catégorie
        cat_snapshot = _build_expense_category_snapshot(expense_data, new_amount_cad)
        expense_data.update(cat_snapshot)
    elif "amount" in expense_data or "currency" in expense_data or "exchange_rate_to_cad" in expense_data:
        # L'amount_cad a possiblement changé : recalcule deductible_amount avec le pct stocké
        stored_pct = current.get("deductible_percentage", 100)
        expense_data["deductible_amount"] = round(new_amount_cad * stored_pct / 100, 2)
    db.expenses.update_one({"id": expense_id, "user_id": current_user.id}, {"$set": expense_data})
    return clean_doc(db.expenses.find_one({"id": expense_id}, {"_id": 0}))
```

- [ ] **Step 4: Redémarrer et relancer**

```bash
lsof -ti:8000 | xargs kill 2>/dev/null
source .venv/bin/activate
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_expense_categories_integration.py -v 2>&1 | tail -15
```

Expected: 13 tests PASS (4 endpoint + 5 create + 4 update).

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_expense_categories_integration.py
git commit -m "feat(expenses): PUT re-snapshot conditionnel selon category_code ou amount"
```

---

## Task 6 — Ajouter `entity_type` à GET/PUT `/api/settings/company`

**Files:**
- Modify: `backend/server.py` (endpoints settings)
- Modify: `backend/tests/test_expense_categories_integration.py` (ajouter `TestSettingsEntityType`)

- [ ] **Step 1: Écrire les tests**

Ajouter :

```python
class TestSettingsEntityType:
    def test_get_returns_default_sole_proprietor(self, auth):
        # Si jamais set, défaut sole_proprietor
        resp = requests.get(f"{BASE_URL}/api/settings/company", headers=auth)
        assert resp.status_code == 200
        body = resp.json()
        assert "entity_type" in body
        # Initial state may be already set from a prior test — both values are acceptable here
        assert body["entity_type"] in ("sole_proprietor", "corporation")

    def test_put_sole_proprietor(self, auth):
        requests.put(f"{BASE_URL}/api/settings/company", headers=auth,
                      json={"entity_type": "sole_proprietor"})
        body = requests.get(f"{BASE_URL}/api/settings/company", headers=auth).json()
        assert body["entity_type"] == "sole_proprietor"

    def test_put_corporation(self, auth):
        requests.put(f"{BASE_URL}/api/settings/company", headers=auth,
                      json={"entity_type": "corporation"})
        body = requests.get(f"{BASE_URL}/api/settings/company", headers=auth).json()
        assert body["entity_type"] == "corporation"
        # Restore
        requests.put(f"{BASE_URL}/api/settings/company", headers=auth,
                      json={"entity_type": "sole_proprietor"})

    def test_put_invalid_value_ignored(self, auth):
        # First set a known good value
        requests.put(f"{BASE_URL}/api/settings/company", headers=auth,
                      json={"entity_type": "sole_proprietor"})
        # Try to set invalid
        requests.put(f"{BASE_URL}/api/settings/company", headers=auth,
                      json={"entity_type": "garbage_value"})
        body = requests.get(f"{BASE_URL}/api/settings/company", headers=auth).json()
        # Should still be sole_proprietor (invalid was ignored)
        assert body["entity_type"] == "sole_proprietor"
```

- [ ] **Step 2: Vérifier que les tests échouent**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
pytest tests/test_expense_categories_integration.py::TestSettingsEntityType -v 2>&1 | tail -15
```

Expected: tests FAIL (entity_type absent).

- [ ] **Step 3: Modifier les endpoints settings dans `server.py`**

Localiser GET et PUT `/api/settings/company` (modifiés dans la feature #2, autour de la ligne 905).

**Pour le GET** : ajouter `setdefault("entity_type", "sole_proprietor")` dans le bloc qui crée le default doc OU dans la boucle qui complète les champs avant retour. Cherche la ligne `for f in TAX_FIELDS: settings.setdefault(f, "")` et ajoute juste après :

```python
    settings.setdefault("entity_type", "sole_proprietor")
```

Aussi dans le default doc (si settings absent), ajouter `"entity_type": "sole_proprietor"` au dict.

**Pour le PUT** : ajouter une validation avant le `update_one`. Localiser le bloc qui filtre `update = {k: v for k, v in body.items() if k not in ("user_id", "tax_number_warnings")}` et juste avant `db.company_settings.update_one(...)`, ajouter :

```python
    # Validation entity_type : seules deux valeurs canoniques acceptées
    if "entity_type" in update and update["entity_type"] not in ("sole_proprietor", "corporation"):
        update.pop("entity_type")
```

- [ ] **Step 4: Redémarrer et relancer**

```bash
lsof -ti:8000 | xargs kill 2>/dev/null
source .venv/bin/activate
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_expense_categories_integration.py -v 2>&1 | tail -15
```

Expected: 17 tests PASS (4 endpoint + 5 create + 4 update + 4 entity_type).

Aussi vérifier que les anciens tests de feature #2 passent toujours :

```bash
pytest tests/test_tax_numbers.py tests/test_tax_registrations_integration.py -v 2>&1 | tail -5
```

Expected: 36 still PASS.

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_expense_categories_integration.py
git commit -m "feat(settings): entity_type (sole_proprietor | corporation) avec défaut + validation"
```

---

## Task 7 — Frontend `SettingsPage` : select `entity_type`

**Files:**
- Modify: `frontend/src/pages/SettingsPage.js`

- [ ] **Step 1: Lire la structure actuelle**

```bash
grep -n "company_name\|entity_type\|Numéros officiels" frontend/src/pages/SettingsPage.js | head
```

Note où ajouter le nouveau champ — idéalement dans la section infos entreprise, AVANT la section "Numéros officiels" (feature #2).

- [ ] **Step 2: Ajouter `entity_type` à `useState`**

Trouver le `useState` du form settings et ajouter `entity_type: 'sole_proprietor'` aux valeurs par défaut. Trouver aussi le `useEffect` qui peuple depuis l'API, et confirmer qu'il fait juste `setSettings(response.data)` ou similaire (donc reprendra `entity_type` automatiquement).

- [ ] **Step 3: Ajouter le bloc JSX**

Insérer dans la section infos entreprise, avant la section Numéros officiels (cherche `<h3` qui contient "Numéros officiels") :

```jsx
<div style={{ marginBottom: 16 }}>
  <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 500, color: '#374151', marginBottom: 4 }}>
    Type d'entité fiscale
    <span
      title="Détermine le formulaire de déclaration fiscale utilisé pour exporter tes dépenses."
      style={{ cursor: 'help', color: '#6b7280', fontSize: 14 }}
    >
      ⓘ
    </span>
  </label>
  <select
    value={settings.entity_type || 'sole_proprietor'}
    onChange={(e) => setSettings({ ...settings, entity_type: e.target.value })}
    style={{
      width: '100%',
      padding: '12px',
      border: '1.5px solid #d1d5db',
      borderRadius: 8,
      fontSize: 14,
      background: 'white',
      boxSizing: 'border-box',
    }}
  >
    <option value="sole_proprietor">Travailleur autonome (T2125)</option>
    <option value="corporation">Société par actions (T2)</option>
  </select>
</div>
```

(Si `setSettings` du fichier n'utilise pas le pattern `setSettings({...settings, ...})` mais plutôt un updater functional `setSettings(prev => ({...prev, ...}))`, adapte.)

- [ ] **Step 4: Build pour vérifier**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/frontend"
npx --no-install react-scripts build 2>&1 | tail -10
```

Expected: Compiled successfully.

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add frontend/src/pages/SettingsPage.js
git commit -m "feat(settings): UI select 'Type d'entité fiscale' (T2125 / T2)"
```

---

## Task 8 — Frontend `ExpensesPage` : picker catégorie groupé + zone d'aide

**Files:**
- Modify: `frontend/src/pages/ExpensesPage.js`

Le picker doit :
- Fetch `/api/expense-categories` au mount, stocker `{categories, groups}` dans state.
- Remplacer le champ catégorie texte libre par un `<select>` avec `<optgroup>` par groupe.
- Si la catégorie sélectionnée est `"other"`, afficher un input "Préciser la catégorie".
- Si la catégorie sélectionnée a `deductible_percentage < 100`, afficher une zone d'aide jaune avec le montant déductible calculé.

- [ ] **Step 1: Lire la structure actuelle**

```bash
grep -n "category\|amount\|description" frontend/src/pages/ExpensesPage.js | head -30
```

Note le nom du state du formulaire (ex: `form`, `expenseData`, etc.) et les lignes existantes qui rendent le champ catégorie.

- [ ] **Step 2: Ajouter le fetch des catégories au mount**

Dans le composant principal de `ExpensesPage.js`, ajouter :

```javascript
const [categoryCatalog, setCategoryCatalog] = useState({ categories: [], groups: {} });

useEffect(() => {
  axios.get(`${BACKEND_URL}/api/expense-categories`)
    .then(resp => setCategoryCatalog(resp.data))
    .catch(err => console.error('Failed to fetch expense categories:', err));
}, []);
```

(Adapter `BACKEND_URL` au pattern utilisé dans le fichier — généralement `process.env.REACT_APP_BACKEND_URL` ou via `config.js`.)

- [ ] **Step 3: Ajouter `category_code` et `category_custom_label` au state du formulaire**

Trouver le `useState` du form (probablement `form` ou `expenseData`). Ajouter aux defaults :

```javascript
category_code: '',
category_custom_label: '',
```

S'assurer que les handlers d'édition (`handleEdit`, `setForm(exp)`) reprennent ces champs (`exp.category_code || ''`, `exp.category_custom_label || ''`).

- [ ] **Step 4: Helper de groupement des catégories**

Ajouter, idéalement en haut du composant ou comme helper :

```javascript
// Regroupe les catégories du catalog par leur clé 'group'
const groupedCategories = categoryCatalog.categories.reduce((acc, cat) => {
  if (!acc[cat.group]) acc[cat.group] = [];
  acc[cat.group].push(cat);
  return acc;
}, {});

const selectedCategory = categoryCatalog.categories.find(
  c => c.code === form.category_code
);
```

(Adapter `form.category_code` au nom de ton state.)

- [ ] **Step 5: Remplacer le champ catégorie libre par le picker**

Trouver le `<input>` existant pour la catégorie. Le remplacer par :

```jsx
<div style={{ marginBottom: 14 }}>
  <label style={{ display: 'block', fontSize: 13, fontWeight: 500, color: '#374151', marginBottom: 4 }}>
    Catégorie ARC
  </label>
  <select
    value={form.category_code}
    onChange={(e) => setForm({ ...form, category_code: e.target.value })}
    style={{
      width: '100%', padding: '12px',
      border: '1.5px solid #d1d5db', borderRadius: 8,
      fontSize: 14, background: 'white', boxSizing: 'border-box',
    }}
  >
    <option value="">— Choisir une catégorie —</option>
    {Object.entries(groupedCategories)
      .filter(([groupKey]) => groupKey !== 'other')
      .map(([groupKey, cats]) => (
        <optgroup key={groupKey} label={categoryCatalog.groups[groupKey] || groupKey}>
          {cats.map(cat => (
            <option key={cat.code} value={cat.code}>
              {cat.label_fr}
              {cat.deductible_percentage < 100 ? ` ${cat.deductible_percentage}%` : ''}
              {cat.arc_line ? ` (${cat.arc_line})` : ''}
            </option>
          ))}
        </optgroup>
      ))
    }
    <optgroup label={categoryCatalog.groups.other || 'Autre'}>
      <option value="other">Autre catégorie…</option>
    </optgroup>
  </select>

  {form.category_code === 'other' && (
    <input
      type="text"
      placeholder="Préciser la catégorie (ex: Cotisations syndicales)"
      value={form.category_custom_label}
      onChange={(e) => setForm({ ...form, category_custom_label: e.target.value })}
      style={{
        width: '100%', padding: '12px', marginTop: 8,
        border: '1.5px dashed #f59e0b', borderRadius: 8,
        fontSize: 14, background: '#fffbeb', boxSizing: 'border-box',
      }}
    />
  )}

  {selectedCategory && selectedCategory.deductible_percentage < 100 && form.amount && (
    <div style={{
      marginTop: 8, padding: '8px 12px',
      background: '#fef3c7', borderRadius: 6,
      fontSize: 12.5, color: '#92400e',
    }}>
      ℹ {selectedCategory.deductible_percentage}% seulement déductible — montant déductible : <strong>
        {(parseFloat(form.amount) * selectedCategory.deductible_percentage / 100).toFixed(2)} $
      </strong> sur {parseFloat(form.amount).toFixed(2)} $
    </div>
  )}
</div>
```

- [ ] **Step 6: Build**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/frontend"
npx --no-install react-scripts build 2>&1 | tail -10
```

Expected: Compiled successfully.

- [ ] **Step 7: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add frontend/src/pages/ExpensesPage.js
git commit -m "feat(expenses): UI picker catégorie groupé + custom label + zone d'aide déductible"
```

---

## Task 9 — Tests E2E + push prod + update CLAUDE.md

- [ ] **Step 1: Toute la batterie de tests**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
lsof -ti:8000 | xargs kill 2>/dev/null
source .venv/bin/activate
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_tax_numbers.py tests/test_tax_registrations_integration.py tests/test_expense_categories.py tests/test_expense_categories_integration.py -v 2>&1 | tail -15
```

Expected: tous PASS (36 feature #2 + ~24 feature #3 = ~60 tests). Note: le compte exact dépend des sous-classes.

- [ ] **Step 2: E2E HTTP avec une vraie facture**

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
   -H "Content-Type: application/json" \
   -d '{"email":"gussdub@gmail.com","password":"testpass123"}' \
   | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

echo "=== Categories endpoint ==="
curl -s http://localhost:8000/api/expense-categories | python -m json.tool | head -10

echo "=== Settings entity_type ==="
curl -s -X PUT http://localhost:8000/api/settings/company \
   -H "Authorization: Bearer $TOKEN" \
   -H "Content-Type: application/json" \
   -d '{"entity_type":"corporation"}' > /dev/null
curl -s http://localhost:8000/api/settings/company -H "Authorization: Bearer $TOKEN" \
   | python -c "import sys,json;print('entity_type:', json.load(sys.stdin).get('entity_type'))"

echo "=== Create expense with meals 50% ==="
RESP=$(curl -s -X POST http://localhost:8000/api/expenses \
   -H "Authorization: Bearer $TOKEN" \
   -H "Content-Type: application/json" \
   -d '{"description":"E2E meal","amount":150,"currency":"CAD","category_code":"meals_entertainment","expense_date":"2026-06-16"}')
EXP_ID=$(echo "$RESP" | python -c "import sys,json;print(json.load(sys.stdin)['id'])")
echo "$RESP" | python -m json.tool | grep -E "category|deductible"
echo "Created: $EXP_ID"

echo "=== Update amount only (should keep snapshot, recalc deductible) ==="
curl -s -X PUT http://localhost:8000/api/expenses/$EXP_ID \
   -H "Authorization: Bearer $TOKEN" \
   -H "Content-Type: application/json" \
   -d '{"amount":300}' | python -m json.tool | grep -E "category|deductible"

# Cleanup
curl -s -X DELETE http://localhost:8000/api/expenses/$EXP_ID -H "Authorization: Bearer $TOKEN" > /dev/null
# Restore settings
curl -s -X PUT http://localhost:8000/api/settings/company \
   -H "Authorization: Bearer $TOKEN" \
   -H "Content-Type: application/json" \
   -d '{"entity_type":"sole_proprietor"}' > /dev/null
echo "Cleanup done"
```

Expected output should show:
- After create: `deductible_percentage: 50, deductible_amount: 75.0`
- After PUT amount only: still `deductible_percentage: 50` but `deductible_amount: 150.0` (recalculated)

- [ ] **Step 3: Stop local backend**

```bash
lsof -ti:8000 | xargs kill 2>/dev/null
```

- [ ] **Step 4: Update CLAUDE.md changelog**

Append à la section "Features livrées" :

```markdown

- **2026-06-16 — Catégories de dépenses ARC (feature #3)**
  - 17 catégories canoniques + "Autre" libre, organisées en 5 groupes (T2125/T2 GIFI)
  - Snapshot sur chaque dépense : code, label, ligne ARC, % déductible, montant déductible calculé
  - Règle 50 % sur les repas appliquée automatiquement (`deductible_amount`)
  - Sélecteur d'entité fiscale (sole_proprietor / corporation) dans Settings — pour la future feature #10 (export T2125/T2)
  - Picker UI groupé natif + zone d'aide jaune pour les catégories partiellement déductibles
  - Endpoint public `GET /api/expense-categories`
  - Spec : `docs/superpowers/specs/2026-06-16-expense-categories-design.md`
  - Plan : `docs/superpowers/plans/2026-06-16-expense-categories.md`
```

- [ ] **Step 5: Push prod**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add CLAUDE.md
git commit -m "docs: changelog feature #3 (catégories dépenses ARC)"
git push origin main 2>&1 | tail -5
```

Expected: push succeeds, Render + Vercel start redeploying.

- [ ] **Step 6: Vérifier prod après deploy (~3 min)**

```bash
sleep 180
echo "=== Backend prod ==="
curl -s -m 90 https://facturepro-backend-dkvn.onrender.com/api/health
echo
echo "=== Categories endpoint prod ==="
curl -s -m 30 https://facturepro-backend-dkvn.onrender.com/api/expense-categories | python -c "import sys,json;data=json.load(sys.stdin);print('categories:', len(data.get('categories', [])), '| groups:', len(data.get('groups', {})))"
echo "=== Frontend prod ==="
curl -sI -m 30 https://facturepro.ca | head -3
```

Expected:
- Backend healthy
- Categories endpoint returns 18 categories + 6 groups
- Frontend responds (308 redirect to www is OK)

---

## Récap fichiers touchés

| Fichier | Tasks | Nature |
|---|---|---|
| `backend/server.py` | 1, 2, 3, 4, 5, 6 | Modif (constantes ~50 lignes, helpers ~30, 5 endpoints) |
| `backend/tests/test_expense_categories.py` | 1, 2 | Nouveau |
| `backend/tests/test_expense_categories_integration.py` | 3, 4, 5, 6 | Nouveau |
| `frontend/src/pages/SettingsPage.js` | 7 | Modif (select entity_type) |
| `frontend/src/pages/ExpensesPage.js` | 8 | Modif (picker complet) |
| `CLAUDE.md` | 9 | Modif (changelog) |

Commits attendus : **9** (un par task + commit doc final).
