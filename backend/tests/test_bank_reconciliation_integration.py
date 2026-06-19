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


import json as _json


def _csv_bytes(rows, header=True):
    lines = []
    if header:
        lines.append("Date,Description,Montant")
    for r in rows:
        lines.append(",".join(r))
    return ("\n".join(lines) + "\n").encode("utf-8")


def _basic_mapping():
    return {
        "delimiter": ",", "has_header": True,
        "date_column": 0, "date_format": "YYYY-MM-DD",
        "description_column": 1, "amount_mode": "single",
        "amount_column": 2, "sign_convention": "positive_is_credit",
    }


class TestImportDryRun:
    def test_dry_run_returns_parsed_no_write(self, auth):
        uid = uuid.uuid4().hex[:8]
        csv = _csv_bytes([
            ["2099-03-14", f"Costco-{uid}", "-127.84"],
            ["2099-03-15", f"Client Test-{uid}", "250.00"],
        ])
        files = {"file": ("test.csv", csv, "text/csv")}
        data = {"mapping": _json.dumps(_basic_mapping())}
        r = requests.post(f"{BASE_URL}/api/bank/imports?dry_run=true",
                          files=files, data=data, headers=auth)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "parsed_rows" in body
        assert len(body["parsed_rows"]) == 2
        assert body["parsed_rows"][0]["description"].startswith("Costco")


class TestImportCreate:
    _cleanup_imports = set()
    _auth = None

    def test_creates_import_and_transactions(self, auth):
        TestImportCreate._auth = auth
        uid = uuid.uuid4().hex[:8]
        csv = _csv_bytes([
            ["2099-04-14", f"Costco-{uid}", "-127.84"],
            ["2099-04-15", f"Salary-{uid}", "1500.00"],
        ])
        files = {"file": ("test.csv", csv, "text/csv")}
        data = {"mapping": _json.dumps(_basic_mapping()),
                "bank_label": f"DryRunBank-{uuid.uuid4().hex[:6]}"}
        r = requests.post(f"{BASE_URL}/api/bank/imports",
                          files=files, data=data, headers=auth)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["import"]["row_count"] == 2
        assert len(body["transactions"]) == 2
        TestImportCreate._cleanup_imports.add(body["import"]["id"])

    def test_duplicate_csv_returns_409(self, auth):
        uid = uuid.uuid4().hex[:8]
        csv = _csv_bytes([[f"2099-05-14", f"Unique-{uid}", "-1.00"]])
        files = {"file": ("dup.csv", csv, "text/csv")}
        data = {"mapping": _json.dumps(_basic_mapping())}
        r1 = requests.post(f"{BASE_URL}/api/bank/imports",
                           files=files, data=data, headers=auth)
        assert r1.status_code == 201
        TestImportCreate._cleanup_imports.add(r1.json()["import"]["id"])
        # re-upload même contenu
        files = {"file": ("dup.csv", csv, "text/csv")}
        data = {"mapping": _json.dumps(_basic_mapping())}
        r2 = requests.post(f"{BASE_URL}/api/bank/imports",
                           files=files, data=data, headers=auth)
        assert r2.status_code == 409

    def test_oversize_returns_413(self, auth):
        # 5001 lignes → 413
        rows = [[f"2099-06-{(i%28)+1:02d}", f"Row{i}", "1.00"] for i in range(5001)]
        csv = _csv_bytes(rows)
        files = {"file": ("big.csv", csv, "text/csv")}
        data = {"mapping": _json.dumps(_basic_mapping())}
        r = requests.post(f"{BASE_URL}/api/bank/imports",
                          files=files, data=data, headers=auth)
        assert r.status_code == 413

    @classmethod
    def teardown_class(cls):
        if not cls._auth:
            return
        # Delete endpoint sera implémenté dans T10. Pour l'instant cleanup direct.
        # Si l'endpoint n'existe pas (404), on ignore.
        for iid in cls._cleanup_imports:
            try:
                requests.delete(f"{BASE_URL}/api/bank/imports/{iid}?force=true",
                                headers=cls._auth)
            except Exception:
                pass
