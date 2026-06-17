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


class TestSalesTaxReport:
    _cleanup = {"clients": [], "invoices": [], "expenses": []}
    _auth_headers = None
    _setup_done = False

    def _setup_data(self, auth):
        """Crée un client, 2 invoices QC payées, 1 invoice draft, 2 expenses avec taxes."""
        if TestSalesTaxReport._setup_done:
            return
        TestSalesTaxReport._setup_done = True
        TestSalesTaxReport._auth_headers = auth
        # Client
        c = requests.post(f"{BASE_URL}/api/clients", headers=auth,
                          json={"name": "Tax Report Test"}).json()
        TestSalesTaxReport._cleanup["clients"].append(c["id"])
        # 2 invoices QC paid (subtotal 1000 each, gst=50, qst=99.75)
        for i in range(2):
            inv = requests.post(f"{BASE_URL}/api/invoices", headers=auth, json={
                "client_id": c["id"],
                "items": [{"description": "S", "quantity": 1, "unit_price": 1000}],
                "province": "QC",
                "issue_date": "2099-04-15",
            }).json()
            TestSalesTaxReport._cleanup["invoices"].append(inv["id"])
            # Mark as paid
            requests.put(f"{BASE_URL}/api/invoices/{inv['id']}/status",
                         headers=auth, json={"status": "paid"})
        # 1 invoice draft (must be excluded)
        d = requests.post(f"{BASE_URL}/api/invoices", headers=auth, json={
            "client_id": c["id"],
            "items": [{"description": "Drafty", "quantity": 1, "unit_price": 500}],
            "province": "QC",
            "issue_date": "2099-04-15",
        }).json()
        TestSalesTaxReport._cleanup["invoices"].append(d["id"])
        # 2 expenses avec taxes payées
        for amount, gst, qst in [(114.975, 5.00, 9.98), (229.95, 10.00, 19.96)]:
            e = requests.post(f"{BASE_URL}/api/expenses", headers=auth, json={
                "description": "Exp",
                "amount": amount,
                "currency": "CAD",
                "expense_date": "2099-04-20",
                "gst_paid_cad": gst,
                "qst_paid_cad": qst,
            }).json()
            TestSalesTaxReport._cleanup["expenses"].append(e["id"])
        return c["id"]

    def test_report_summary(self, auth):
        self._setup_data(auth)
        resp = requests.get(
            f"{BASE_URL}/api/reports/sales-tax",
            headers=auth, params={"start": "2099-04-01", "end": "2099-06-30"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["period"] == {"start": "2099-04-01", "end": "2099-06-30"}
        # 2 paid invoices QC : 50 GST each = 100 total
        assert body["summary"]["gst"]["collected"] == 100.00
        # 99.75 QST each × 2 = 199.50
        assert body["summary"]["qst"]["collected"] == 199.50
        # Expenses: 5 + 10 = 15 GST paid, 9.98 + 19.96 = 29.94 QST paid
        assert body["summary"]["gst"]["paid"] == 15.00
        assert body["summary"]["qst"]["paid"] == 29.94
        # Net = collected - paid
        assert body["summary"]["gst"]["net"] == 85.00
        assert body["summary"]["qst"]["net"] == round(199.50 - 29.94, 2)
        # No HST (no ON invoices)
        assert body["summary"]["hst"] == {"collected": 0, "paid": 0, "net": 0}

    def test_counts(self, auth):
        self._setup_data(auth)
        resp = requests.get(
            f"{BASE_URL}/api/reports/sales-tax",
            headers=auth, params={"start": "2099-04-01", "end": "2099-06-30"})
        body = resp.json()
        # 2 paid invoices, draft excluded
        assert body["invoice_count"] == 2
        # 2 expenses
        assert body["expense_count"] == 2

    def test_cra_detail_lines_present(self, auth):
        self._setup_data(auth)
        resp = requests.get(
            f"{BASE_URL}/api/reports/sales-tax",
            headers=auth, params={"start": "2099-04-01", "end": "2099-06-30"})
        body = resp.json()
        cra = body["cra_detail"]
        for key in ("line_101_sales", "line_103_gst_collected", "line_106_itc_gst",
                    "line_109_net_gst", "line_103_hst_collected", "line_106_itc_hst",
                    "line_109_net_hst"):
            assert key in cra

    def test_rq_detail_lines_present(self, auth):
        self._setup_data(auth)
        resp = requests.get(
            f"{BASE_URL}/api/reports/sales-tax",
            headers=auth, params={"start": "2099-04-01", "end": "2099-06-30"})
        body = resp.json()
        rq = body["rq_detail"]
        for key in ("line_201_taxable_sales_qc", "line_203_qst_collected",
                    "line_205_itr_qst", "line_209_net_qst"):
            assert key in rq

    def test_empty_period(self, auth):
        resp = requests.get(
            f"{BASE_URL}/api/reports/sales-tax",
            headers=auth, params={"start": "2020-01-01", "end": "2020-01-31"})
        body = resp.json()
        assert body["summary"]["gst"] == {"collected": 0, "paid": 0, "net": 0}
        assert body["invoice_count"] == 0
        assert body["expense_count"] == 0

    def test_pdf_endpoint(self, auth):
        self._setup_data(auth)
        resp = requests.get(
            f"{BASE_URL}/api/reports/sales-tax/pdf",
            headers=auth, params={"start": "2099-04-01", "end": "2099-06-30"})
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/pdf")
        # PDF starts with %PDF magic bytes
        assert resp.content[:4] == b"%PDF"
        assert len(resp.content) > 1000  # not empty

    @classmethod
    def teardown_class(cls):
        if not cls._auth_headers:
            return
        for iid in cls._cleanup["invoices"]:
            try:
                requests.delete(f"{BASE_URL}/api/invoices/{iid}", headers=cls._auth_headers)
            except Exception:
                pass
        for eid in cls._cleanup["expenses"]:
            try:
                requests.delete(f"{BASE_URL}/api/expenses/{eid}", headers=cls._auth_headers)
            except Exception:
                pass
        for cid in cls._cleanup["clients"]:
            try:
                requests.delete(f"{BASE_URL}/api/clients/{cid}", headers=cls._auth_headers)
            except Exception:
                pass
        cls._cleanup = {"clients": [], "invoices": [], "expenses": []}
        cls._setup_done = False
