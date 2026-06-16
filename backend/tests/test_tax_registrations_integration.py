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


class TestClientTaxNumbers:
    _cleanup_ids = []
    _auth_headers = None

    def test_create_client_with_numbers(self, auth):
        # Capture auth on first run for teardown
        TestClientTaxNumbers._auth_headers = auth
        payload = {
            "name": "ACME Test Inc.",
            "email": "test@acme.example",
            "bn_number": "987 654 321",
            "gst_number": "987654321RT0001",
            "qst_number": "9876543210TQ0001",
            "hst_number": "",
            "neq_number": "9876543210",
        }
        resp = requests.post(f"{BASE_URL}/api/clients", headers=auth, json=payload)
        assert resp.status_code in (200, 201), resp.text
        client_id = resp.json()["id"]
        TestClientTaxNumbers._cleanup_ids.append(client_id)

        get = requests.get(f"{BASE_URL}/api/clients", headers=auth)
        clients = get.json()
        created = next(c for c in clients if c["id"] == client_id)
        assert created["bn_number"] == "987654321"
        assert created["gst_number"] == "987654321RT0001"
        assert created["qst_number"] == "9876543210TQ0001"
        assert created["hst_number"] == ""
        assert created["neq_number"] == "9876543210"

    def test_update_client_numbers(self, auth):
        TestClientTaxNumbers._auth_headers = auth
        create = requests.post(f"{BASE_URL}/api/clients", headers=auth,
                                json={"name": "Update Test Inc."})
        client_id = create.json()["id"]
        TestClientTaxNumbers._cleanup_ids.append(client_id)

        upd = requests.put(f"{BASE_URL}/api/clients/{client_id}", headers=auth,
                           json={"bn_number": "111 222 333"})
        assert upd.status_code == 200

        get = requests.get(f"{BASE_URL}/api/clients", headers=auth)
        updated = next(c for c in get.json() if c["id"] == client_id)
        assert updated["bn_number"] == "111222333"

    def test_create_client_without_numbers(self, auth):
        TestClientTaxNumbers._auth_headers = auth
        resp = requests.post(f"{BASE_URL}/api/clients", headers=auth,
                              json={"name": "No Tax Inc."})
        assert resp.status_code in (200, 201)
        client_id = resp.json()["id"]
        TestClientTaxNumbers._cleanup_ids.append(client_id)

        get = requests.get(f"{BASE_URL}/api/clients", headers=auth)
        created = next(c for c in get.json() if c["id"] == client_id)
        for f in ["bn_number", "gst_number", "qst_number", "hst_number", "neq_number"]:
            assert created.get(f, "") == ""

    @classmethod
    def teardown_class(cls):
        if not cls._auth_headers:
            return
        for cid in cls._cleanup_ids:
            try:
                requests.delete(f"{BASE_URL}/api/clients/{cid}", headers=cls._auth_headers)
            except Exception:
                pass  # best-effort
        cls._cleanup_ids = []


class TestSnapshotOnCreate:
    _cleanup = {"clients": [], "invoices": [], "quotes": []}
    _auth_headers = None

    def test_invoice_snapshots_company_and_client_numbers(self, auth):
        TestSnapshotOnCreate._auth_headers = auth
        # Pré-condition: configurer settings avec numéros
        requests.put(f"{BASE_URL}/api/settings/company", headers=auth, json={
            "bn_number": "555555555",
            "gst_number": "555555555RT0001",
            "qst_number": "5555555555TQ0001",
        })
        # Pré-condition: créer un client B2B avec numéros
        client_resp = requests.post(f"{BASE_URL}/api/clients", headers=auth, json={
            "name": "Snapshot Test Inc.",
            "bn_number": "111111111",
            "gst_number": "111111111RT0001",
        })
        client_id = client_resp.json()["id"]
        TestSnapshotOnCreate._cleanup["clients"].append(client_id)

        # Créer une facture
        inv_resp = requests.post(f"{BASE_URL}/api/invoices", headers=auth, json={
            "client_id": client_id,
            "items": [{"description": "Snapshot test", "quantity": 1, "unit_price": 100}],
            "province": "QC",
        })
        assert inv_resp.status_code in (200, 201), inv_resp.text
        inv = inv_resp.json()
        TestSnapshotOnCreate._cleanup["invoices"].append(inv["id"])

        assert "tax_registrations" in inv
        assert inv["tax_registrations"]["company"]["bn"] == "555555555"
        assert inv["tax_registrations"]["company"]["gst"] == "555555555RT0001"
        assert inv["tax_registrations"]["client"]["bn"] == "111111111"
        assert inv["tax_registrations"]["client"]["gst"] == "111111111RT0001"

    def test_invoice_snapshot_immutable_after_settings_change(self, auth):
        TestSnapshotOnCreate._auth_headers = auth
        requests.put(f"{BASE_URL}/api/settings/company", headers=auth,
                      json={"bn_number": "777777777"})
        client_resp = requests.post(f"{BASE_URL}/api/clients", headers=auth,
                                    json={"name": "Frozen Test"})
        client_id = client_resp.json()["id"]
        TestSnapshotOnCreate._cleanup["clients"].append(client_id)

        inv = requests.post(f"{BASE_URL}/api/invoices", headers=auth, json={
            "client_id": client_id,
            "items": [{"description": "x", "quantity": 1, "unit_price": 10}],
            "province": "QC",
        }).json()
        inv_id = inv["id"]
        TestSnapshotOnCreate._cleanup["invoices"].append(inv_id)

        # Modifier les settings APRÈS création
        requests.put(f"{BASE_URL}/api/settings/company", headers=auth,
                      json={"bn_number": "999999999"})

        # Re-fetch
        get = requests.get(f"{BASE_URL}/api/invoices/{inv_id}", headers=auth)
        assert get.status_code == 200
        inv_after = get.json()
        assert inv_after["tax_registrations"]["company"]["bn"] == "777777777"

    def test_quote_snapshots_too(self, auth):
        TestSnapshotOnCreate._auth_headers = auth
        requests.put(f"{BASE_URL}/api/settings/company", headers=auth,
                      json={"bn_number": "333333333"})
        client = requests.post(f"{BASE_URL}/api/clients", headers=auth,
                                json={"name": "Quote Test"}).json()
        client_id = client["id"]
        TestSnapshotOnCreate._cleanup["clients"].append(client_id)

        quote = requests.post(f"{BASE_URL}/api/quotes", headers=auth, json={
            "client_id": client_id,
            "items": [{"description": "q", "quantity": 1, "unit_price": 50}],
            "province": "QC",
        }).json()
        TestSnapshotOnCreate._cleanup["quotes"].append(quote["id"])

        assert "tax_registrations" in quote
        assert quote["tax_registrations"]["company"]["bn"] == "333333333"
        # Client created without tax numbers → all empty
        assert quote["tax_registrations"]["client"]["bn"] == ""
        assert quote["tax_registrations"]["client"]["gst"] == ""

    @classmethod
    def teardown_class(cls):
        if not cls._auth_headers:
            return
        for cid in cls._cleanup["clients"]:
            try:
                requests.delete(f"{BASE_URL}/api/clients/{cid}", headers=cls._auth_headers)
            except Exception:
                pass
        for iid in cls._cleanup["invoices"]:
            try:
                requests.delete(f"{BASE_URL}/api/invoices/{iid}", headers=cls._auth_headers)
            except Exception:
                pass
        for qid in cls._cleanup["quotes"]:
            try:
                requests.delete(f"{BASE_URL}/api/quotes/{qid}", headers=cls._auth_headers)
            except Exception:
                pass
        # Restore settings to neutral state
        try:
            requests.put(f"{BASE_URL}/api/settings/company", headers=cls._auth_headers,
                          json={"bn_number": ""})
        except Exception:
            pass
        cls._cleanup = {"clients": [], "invoices": [], "quotes": []}
