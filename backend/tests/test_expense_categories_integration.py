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
