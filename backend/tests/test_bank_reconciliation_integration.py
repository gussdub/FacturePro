import os
import uuid
import requests
import pytest

BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="module")
def auth():
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "gussdub@gmail.com", "password": "testpass123"},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _unique_label():
    return f"TestBank-{uuid.uuid4().hex[:8]}"


class TestMappings:
    _auth = None

    def test_create_mapping(self, auth):
        TestMappings._auth = auth
        payload = {
            "bank_label": _unique_label(),
            "delimiter": ",", "has_header": True,
            "date_column": 0, "date_format": "YYYY-MM-DD",
            "description_column": 1, "amount_mode": "single",
            "amount_column": 2, "sign_convention": "positive_is_credit",
        }
        r = requests.post(f"{BASE_URL}/api/bank/mappings", json=payload, headers=auth)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["id"]
        assert body["bank_label"] == payload["bank_label"]

    def test_list_mappings_includes_created(self, auth):
        payload = {
            "bank_label": _unique_label(), "delimiter": ",", "has_header": True,
            "date_column": 0, "date_format": "YYYY-MM-DD",
            "description_column": 1, "amount_mode": "single",
            "amount_column": 2, "sign_convention": "positive_is_credit",
        }
        created = requests.post(f"{BASE_URL}/api/bank/mappings", json=payload, headers=auth).json()
        r = requests.get(f"{BASE_URL}/api/bank/mappings", headers=auth)
        assert r.status_code == 200
        ids = [m["id"] for m in r.json()]
        assert created["id"] in ids
