"""Tests d'intégration HTTP pour le rapport TPS/TVQ (feature #4)."""
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


class TestSettingsProvince:
    def test_get_returns_province_field(self, auth):
        resp = requests.get(f"{BASE_URL}/api/settings/company", headers=auth)
        assert resp.status_code == 200
        body = resp.json()
        assert "province" in body
        assert body["province"] in (
            "QC", "ON", "BC", "AB", "SK", "MB",
            "NB", "NS", "PE", "NL", "YT", "NU", "NT",
        )

    def test_put_qc(self, auth):
        requests.put(f"{BASE_URL}/api/settings/company", headers=auth,
                      json={"province": "QC"})
        body = requests.get(f"{BASE_URL}/api/settings/company", headers=auth).json()
        assert body["province"] == "QC"

    def test_put_on(self, auth):
        requests.put(f"{BASE_URL}/api/settings/company", headers=auth,
                      json={"province": "ON"})
        body = requests.get(f"{BASE_URL}/api/settings/company", headers=auth).json()
        assert body["province"] == "ON"
        # Restore
        requests.put(f"{BASE_URL}/api/settings/company", headers=auth,
                      json={"province": "QC"})

    def test_put_invalid_value_ignored(self, auth):
        requests.put(f"{BASE_URL}/api/settings/company", headers=auth,
                      json={"province": "QC"})
        requests.put(f"{BASE_URL}/api/settings/company", headers=auth,
                      json={"province": "XX"})
        body = requests.get(f"{BASE_URL}/api/settings/company", headers=auth).json()
        assert body["province"] == "QC"
