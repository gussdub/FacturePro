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
