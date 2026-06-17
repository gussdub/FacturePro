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


class TestExpenseTaxesPaid:
    _cleanup_ids = []
    _auth_headers = None

    def test_create_with_taxes_paid(self, auth):
        TestExpenseTaxesPaid._auth_headers = auth
        payload = {
            "description": "Achat fournitures",
            "amount": 114.975,
            "currency": "CAD",
            "category_code": "office_expenses",
            "expense_date": "2026-06-16",
            "gst_paid_cad": 5.00,
            "qst_paid_cad": 9.98,
            "hst_paid_cad": 0,
            "taxes_auto_computed": True,
        }
        resp = requests.post(f"{BASE_URL}/api/expenses", headers=auth, json=payload)
        assert resp.status_code in (200, 201)
        exp = resp.json()
        TestExpenseTaxesPaid._cleanup_ids.append(exp["id"])
        assert exp["gst_paid_cad"] == 5.00
        assert exp["qst_paid_cad"] == 9.98
        assert exp["hst_paid_cad"] == 0
        assert exp["taxes_auto_computed"] is True

    def test_create_without_taxes_paid_defaults(self, auth):
        TestExpenseTaxesPaid._auth_headers = auth
        payload = {
            "description": "Plain expense",
            "amount": 100,
            "currency": "CAD",
            "expense_date": "2026-06-16",
        }
        resp = requests.post(f"{BASE_URL}/api/expenses", headers=auth, json=payload)
        exp = resp.json()
        TestExpenseTaxesPaid._cleanup_ids.append(exp["id"])
        assert exp["gst_paid_cad"] == 0
        assert exp["qst_paid_cad"] == 0
        assert exp["hst_paid_cad"] == 0
        assert exp["taxes_auto_computed"] is False

    def test_update_taxes_paid(self, auth):
        TestExpenseTaxesPaid._auth_headers = auth
        resp = requests.post(f"{BASE_URL}/api/expenses", headers=auth, json={
            "description": "To update",
            "amount": 113,
            "currency": "CAD",
            "expense_date": "2026-06-16",
        })
        eid = resp.json()["id"]
        TestExpenseTaxesPaid._cleanup_ids.append(eid)
        upd = requests.put(f"{BASE_URL}/api/expenses/{eid}", headers=auth,
                            json={"hst_paid_cad": 13.00, "taxes_auto_computed": True})
        assert upd.status_code == 200
        exp = upd.json()
        assert exp["hst_paid_cad"] == 13.00
        assert exp["taxes_auto_computed"] is True

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
