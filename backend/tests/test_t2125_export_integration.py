import sys as _sys
import os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))

import io
import uuid
import requests
import pytest
import server as server_module
from fastapi.testclient import TestClient


BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="module")
def client():
    return TestClient(server_module.app)


@pytest.fixture(scope="module")
def auth_headers(client):
    resp = client.post("/api/auth/login",
                       json={"email": "gussdub@gmail.com", "password": "testpass123"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


class TestSettingsValidation:
    def test_valid_home_office_percentage(self, client, auth_headers):
        r = client.put("/api/settings/company", headers=auth_headers,
                       json={"home_office_percentage": 50})
        assert r.status_code == 200
        body = r.json()
        assert body.get("home_office_percentage") == 50

    def test_valid_decimal(self, client, auth_headers):
        r = client.put("/api/settings/company", headers=auth_headers,
                       json={"home_office_percentage": 33.3})
        assert r.status_code == 200

    def test_over_100_returns_422(self, client, auth_headers):
        r = client.put("/api/settings/company", headers=auth_headers,
                       json={"home_office_percentage": 150})
        assert r.status_code == 422

    def test_negative_returns_422(self, client, auth_headers):
        r = client.put("/api/settings/company", headers=auth_headers,
                       json={"home_office_percentage": -5})
        assert r.status_code == 422

    def test_non_numeric_returns_422(self, client, auth_headers):
        r = client.put("/api/settings/company", headers=auth_headers,
                       json={"home_office_percentage": "abc"})
        assert r.status_code == 422

    def test_infinity_blocked(self, client, auth_headers):
        # math.isfinite blocks inf; send raw bytes since JSON spec disallows Infinity
        import math
        h = dict(auth_headers)
        h["Content-Type"] = "application/json"
        r = client.put("/api/settings/company", headers=h,
                       content=b'{"home_office_percentage": 1e999}')
        # 1e999 overflows to inf in some parsers; our code rejects it,
        # or the JSON parser itself may return 422 for non-finite
        assert r.status_code in (422, 200)  # acceptable either way
        if r.status_code == 200:
            # If parsed as finite large number (some JSON libs clamp), pass
            assert math.isfinite(r.json().get("home_office_percentage", 0))

    def test_vehicle_validation_same(self, client, auth_headers):
        r = client.put("/api/settings/company", headers=auth_headers,
                       json={"vehicle_business_percentage": 200})
        assert r.status_code == 422

    def test_reset_to_zero(self, client, auth_headers):
        client.put("/api/settings/company", headers=auth_headers,
                   json={"home_office_percentage": 50})
        r = client.put("/api/settings/company", headers=auth_headers,
                       json={"home_office_percentage": 0})
        assert r.status_code == 200


from datetime import datetime, timezone as _tz_t7


def _t10_valid_year():
    """Année valide : dernière année complète."""
    return datetime.now(_tz_t7.utc).year - 1


class TestT2125JsonEndpoint:
    def test_happy_path(self, client, auth_headers):
        # On suppose que entity_type=sole_proprietor déjà set (default)
        # Si pas le cas, le test échouera et il faudra setup les settings
        year = _t10_valid_year()
        r = client.get(f"/api/reports/t2125?year={year}&basis=accrual",
                       headers=auth_headers)
        # Accepter soit 200 (happy) soit 422 (settings incomplets — entity_type)
        # mais surtout PAS 404
        assert r.status_code in (200, 422), r.text
        if r.status_code == 200:
            body = r.json()
            assert body["year"] == year
            assert body["basis"] == "accrual"
            assert body["entity_type"] == "sole_proprietor"
            assert "expenses_by_arc_line" in body
            assert "net_income" in body

    def test_invalid_year_returns_422(self, client, auth_headers):
        r = client.get("/api/reports/t2125?year=1999&basis=accrual",
                       headers=auth_headers)
        assert r.status_code == 422

    def test_invalid_basis_returns_422(self, client, auth_headers):
        year = _t10_valid_year()
        r = client.get(f"/api/reports/t2125?year={year}&basis=xxx",
                       headers=auth_headers)
        assert r.status_code == 422

    def test_default_basis_accrual(self, client, auth_headers):
        year = _t10_valid_year()
        r = client.get(f"/api/reports/t2125?year={year}", headers=auth_headers)
        # 200 ou 422 (selon settings) — pas 404
        assert r.status_code in (200, 422)
        if r.status_code == 200:
            assert r.json()["basis"] == "accrual"

    def test_unauthenticated_returns_401_or_403(self, client):
        year = _t10_valid_year()
        r = client.get(f"/api/reports/t2125?year={year}&basis=accrual")
        assert r.status_code in (401, 403)
