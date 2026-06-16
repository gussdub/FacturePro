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
        assert resp.status_code in (200, 201)
        exp = resp.json()
        TestExpenseSnapshotOnCreate._cleanup_ids.append(exp["id"])
        assert exp["category"] == "Fallback label"
        assert exp["deductible_percentage"] == 100

    def test_legacy_payload_without_category_code(self, auth):
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
        upd = requests.put(f"{BASE_URL}/api/expenses/{eid}", headers=auth,
                            json={"description": "Updated description"})
        assert upd.status_code == 200
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


class TestSettingsEntityType:
    def test_get_returns_default_sole_proprietor(self, auth):
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
