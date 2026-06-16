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
        for key in ["bn_number", "gst_number", "qst_number", "hst_number", "neq_number"]:
            assert key in body["tax_number_warnings"]
            w = body["tax_number_warnings"][key]
            assert "valid" in w
            assert "expected" in w

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
        assert body["bn_number"] == "ABC"
        assert body["tax_number_warnings"]["bn_number"]["valid"] is False

        # Cleanup: restore so subsequent runs aren't polluted
        requests.put(f"{BASE_URL}/api/settings/company", headers=auth,
                     json={"bn_number": ""})
