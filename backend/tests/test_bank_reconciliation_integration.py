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


def _create_invoice_for_match(auth, subtotal, issue_date, client_name=None):
    """Crée client + invoice statut sent (province AB → +5% taxes seulement).
    Retourne (invoice_id, client_id, total)."""
    cname = client_name or f"Auto-{uuid.uuid4().hex[:6]}"
    c = requests.post(f"{BASE_URL}/api/clients", headers=auth, json={
        "name": cname, "email": f"{cname.lower().replace(' ', '')}@x.test"}).json()
    inv = requests.post(f"{BASE_URL}/api/invoices", headers=auth, json={
        "client_id": c["id"],
        "issue_date": issue_date,
        "due_date": issue_date,
        "items": [{"description": "X", "quantity": 1, "unit_price": subtotal}],
        "province": "AB",
        "currency": "CAD",
        "status": "sent",
    }).json()
    return inv["id"], c["id"], inv["total"]


class TestAutoMatch:
    _cleanup = {"imports": set(), "invoices": set(), "clients": set()}
    _auth = None

    def test_credit_matches_existing_invoice(self, auth):
        TestAutoMatch._auth = auth
        # facture subtotal 100 → total 105 (province AB), nom client distinctif
        client_name = f"BANKMATCH{uuid.uuid4().hex[:6].upper()}"
        inv_id, c_id, total = _create_invoice_for_match(auth, 100, "2099-07-10", client_name)
        TestAutoMatch._cleanup["invoices"].add(inv_id)
        TestAutoMatch._cleanup["clients"].add(c_id)
        # CSV avec crédit de 105.00 $ le 2099-07-12 (dans la fenêtre ±3j),
        # description contenant le nom du client → score parfait → auto-match
        csv = _csv_bytes([
            ["2099-07-12", f"VIREMENT {client_name} REF12345", f"{total:.2f}"],
        ])
        files = {"file": ("am.csv", csv, "text/csv")}
        data = {"mapping": _json.dumps(_basic_mapping())}
        r = requests.post(f"{BASE_URL}/api/bank/imports",
                          files=files, data=data, headers=auth)
        assert r.status_code == 201, r.text
        body = r.json()
        TestAutoMatch._cleanup["imports"].add(body["import"]["id"])
        tx = body["transactions"][0]
        assert tx["status"] == "matched", f"Expected matched, got {tx['status']}"
        assert tx["match_kind"] == "invoice_payment"
        # vérifier que la facture a maintenant un payment
        inv_after = requests.get(f"{BASE_URL}/api/invoices/{inv_id}", headers=auth).json()
        assert len(inv_after["payments"]) == 1
        assert inv_after["status"] == "paid"

    def test_credit_no_match_when_amount_off(self, auth):
        uid = uuid.uuid4().hex[:8]
        csv = _csv_bytes([
            ["2099-08-10", f"Quelque chose unique {uid}", "999999.00"],  # montant improbable
        ])
        files = {"file": ("nm.csv", csv, "text/csv")}
        data = {"mapping": _json.dumps(_basic_mapping())}
        r = requests.post(f"{BASE_URL}/api/bank/imports",
                          files=files, data=data, headers=auth)
        assert r.status_code == 201
        body = r.json()
        TestAutoMatch._cleanup["imports"].add(body["import"]["id"])
        assert body["transactions"][0]["status"] == "unmatched"

    @classmethod
    def teardown_class(cls):
        if not cls._auth:
            return
        for iid in cls._cleanup["imports"]:
            try: requests.delete(f"{BASE_URL}/api/bank/imports/{iid}?force=true", headers=cls._auth)
            except: pass
        for invid in cls._cleanup["invoices"]:
            try: requests.delete(f"{BASE_URL}/api/invoices/{invid}", headers=cls._auth)
            except: pass
        for cid in cls._cleanup["clients"]:
            try: requests.delete(f"{BASE_URL}/api/clients/{cid}", headers=cls._auth)
            except: pass


class TestImportsList:
    _cleanup = set()
    _auth = None

    def test_list_returns_recent_imports_with_counts(self, auth):
        TestImportsList._auth = auth
        # crée un import unique
        suffix = uuid.uuid4().hex[:6]
        csv = _csv_bytes([[f"2099-09-{suffix[0:2]}", f"X-{suffix}", "1.00"]])
        files = {"file": ("a.csv", csv, "text/csv")}
        data = {"mapping": _json.dumps(_basic_mapping())}
        body = requests.post(f"{BASE_URL}/api/bank/imports",
                             files=files, data=data, headers=auth).json()
        TestImportsList._cleanup.add(body["import"]["id"])

        r = requests.get(f"{BASE_URL}/api/bank/imports", headers=auth)
        assert r.status_code == 200
        items = r.json()
        assert len(items) > 0
        first = items[0]
        assert "matched_count" in first
        assert "ignored_count" in first
        assert "unmatched_count" in first

    def test_get_detail_returns_transactions(self, auth):
        suffix = uuid.uuid4().hex[:6]
        csv = _csv_bytes([
            ["2099-09-11", f"A-{suffix}", "1.00"],
            ["2099-09-12", f"B-{suffix}", "2.00"],
        ])
        files = {"file": ("b.csv", csv, "text/csv")}
        data = {"mapping": _json.dumps(_basic_mapping())}
        body = requests.post(f"{BASE_URL}/api/bank/imports",
                             files=files, data=data, headers=auth).json()
        TestImportsList._cleanup.add(body["import"]["id"])

        r = requests.get(f"{BASE_URL}/api/bank/imports/{body['import']['id']}",
                          headers=auth)
        assert r.status_code == 200
        d = r.json()
        assert d["import"]["id"] == body["import"]["id"]
        assert len(d["transactions"]) == 2
        assert d["total_count"] == 2

    def test_get_detail_unknown_returns_404(self, auth):
        r = requests.get(f"{BASE_URL}/api/bank/imports/non-existent-id",
                          headers=auth)
        assert r.status_code == 404

    @classmethod
    def teardown_class(cls):
        if not cls._auth:
            return
        for iid in cls._cleanup:
            try: requests.delete(f"{BASE_URL}/api/bank/imports/{iid}?force=true", headers=cls._auth)
            except: pass
