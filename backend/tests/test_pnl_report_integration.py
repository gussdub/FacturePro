"""Tests d'intégration HTTP pour le rapport P&L (feature #5)."""
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


class TestPnlReport:
    _cleanup = {"clients": [], "invoices": [], "expenses": []}
    _auth_headers = None
    _setup_done = False

    def _setup_data(self, auth):
        """2 invoices paid + 1 sent + 1 draft + 3 expenses dans 3 catégories."""
        if TestPnlReport._setup_done:
            return
        TestPnlReport._auth_headers = auth
        TestPnlReport._setup_done = True
        c = requests.post(f"{BASE_URL}/api/clients", headers=auth,
                          json={"name": "P&L Test"}).json()
        TestPnlReport._cleanup["clients"].append(c["id"])
        for i in range(2):
            inv = requests.post(f"{BASE_URL}/api/invoices", headers=auth, json={
                "client_id": c["id"],
                "items": [{"description": "S", "quantity": 1, "unit_price": 1000}],
                "province": "QC", "issue_date": "2099-04-15",
            }).json()
            TestPnlReport._cleanup["invoices"].append(inv["id"])
            requests.put(f"{BASE_URL}/api/invoices/{inv['id']}/status",
                         headers=auth, json={"status": "paid"})
        s = requests.post(f"{BASE_URL}/api/invoices", headers=auth, json={
            "client_id": c["id"],
            "items": [{"description": "Sent", "quantity": 1, "unit_price": 1000}],
            "province": "QC", "issue_date": "2099-05-10",
        }).json()
        TestPnlReport._cleanup["invoices"].append(s["id"])
        requests.put(f"{BASE_URL}/api/invoices/{s['id']}/status",
                     headers=auth, json={"status": "sent"})
        d = requests.post(f"{BASE_URL}/api/invoices", headers=auth, json={
            "client_id": c["id"],
            "items": [{"description": "Drft", "quantity": 1, "unit_price": 9999}],
            "province": "QC", "issue_date": "2099-04-20",
        }).json()
        TestPnlReport._cleanup["invoices"].append(d["id"])
        for desc, amount, code in [("Bureau", 200, "office_expenses"),
                                    ("Repas", 300, "meals_entertainment"),
                                    ("Loyer", 150, "rent")]:
            e = requests.post(f"{BASE_URL}/api/expenses", headers=auth, json={
                "description": desc, "amount": amount, "currency": "CAD",
                "expense_date": "2099-04-20", "category_code": code,
            }).json()
            TestPnlReport._cleanup["expenses"].append(e["id"])

    def test_accrual_no_compare(self, auth):
        self._setup_data(auth)
        resp = requests.get(f"{BASE_URL}/api/reports/pnl", headers=auth,
                            params={"start": "2099-04-01", "end": "2099-06-30",
                                    "basis": "accrual", "compare": "none"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["basis"] == "accrual"
        assert body["compare"] == "none"
        assert body["period"] == {"start": "2099-04-01", "end": "2099-06-30"}
        # 2 paid + 1 sent = 3000 (draft exclu)
        assert body["revenue"]["current"] == 3000.00
        # Total gross = 200 + 300 + 150 = 650
        assert body["total_expenses"]["current"]["gross"] == 650.00
        # Total deductible = 200 + 150 (50% repas) + 150 = 500
        assert body["total_expenses"]["current"]["deductible"] == 500.00
        # Net management = 3000 - 650 = 2350
        assert body["net_income"]["current"]["management"] == 2350.00
        # Net taxable = 3000 - 500 = 2500
        assert body["net_income"]["current"]["taxable"] == 2500.00
        assert body["invoice_count"] == 3
        assert body["expense_count"] == 3
        assert "compare_period" not in body

    def test_cash_basis(self, auth):
        self._setup_data(auth)
        resp = requests.get(f"{BASE_URL}/api/reports/pnl", headers=auth,
                            params={"start": "2099-04-01", "end": "2099-06-30",
                                    "basis": "cash", "compare": "none"})
        body = resp.json()
        # cash = 2 paid uniquement = 2000
        assert body["revenue"]["current"] == 2000.00
        assert body["invoice_count"] == 2

    def test_compare_previous(self, auth):
        self._setup_data(auth)
        resp = requests.get(f"{BASE_URL}/api/reports/pnl", headers=auth,
                            params={"start": "2099-04-01", "end": "2099-06-30",
                                    "basis": "accrual", "compare": "previous"})
        body = resp.json()
        assert "compare_period" in body
        assert body["compare_period"]["end"] == "2099-03-31"
        assert body["revenue"]["previous"] == 0.0
        assert "delta_pct" in body["revenue"]

    def test_compare_prior_year(self, auth):
        self._setup_data(auth)
        resp = requests.get(f"{BASE_URL}/api/reports/pnl", headers=auth,
                            params={"start": "2099-04-01", "end": "2099-06-30",
                                    "basis": "accrual", "compare": "prior_year"})
        body = resp.json()
        assert body["compare_period"] == {"start": "2098-04-01", "end": "2098-06-30"}

    def test_empty_period(self, auth):
        resp = requests.get(f"{BASE_URL}/api/reports/pnl", headers=auth,
                            params={"start": "2020-01-01", "end": "2020-01-31",
                                    "basis": "accrual", "compare": "none"})
        body = resp.json()
        assert body["revenue"]["current"] == 0
        assert body["total_expenses"]["current"] == {"gross": 0, "deductible": 0}
        assert body["expense_groups"] == []
        assert body["invoice_count"] == 0
        assert body["expense_count"] == 0

    def test_invalid_basis_falls_back_to_accrual(self, auth):
        self._setup_data(auth)
        resp = requests.get(f"{BASE_URL}/api/reports/pnl", headers=auth,
                            params={"start": "2099-04-01", "end": "2099-06-30",
                                    "basis": "garbage", "compare": "none"})
        body = resp.json()
        assert body["basis"] == "accrual"
        assert body["revenue"]["current"] == 3000.00

    def test_invalid_compare_falls_back_to_none(self, auth):
        self._setup_data(auth)
        resp = requests.get(f"{BASE_URL}/api/reports/pnl", headers=auth,
                            params={"start": "2099-04-01", "end": "2099-06-30",
                                    "basis": "accrual", "compare": "weird"})
        body = resp.json()
        assert body["compare"] == "none"
        assert "compare_period" not in body

    def test_pdf_endpoint(self, auth):
        self._setup_data(auth)
        resp = requests.get(f"{BASE_URL}/api/reports/pnl/pdf", headers=auth,
                            params={"start": "2099-04-01", "end": "2099-06-30",
                                    "basis": "accrual", "compare": "none"})
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/pdf")
        assert resp.content[:4] == b"%PDF"
        assert len(resp.content) > 1000

    def test_pdf_with_compare(self, auth):
        self._setup_data(auth)
        resp = requests.get(f"{BASE_URL}/api/reports/pnl/pdf", headers=auth,
                            params={"start": "2099-04-01", "end": "2099-06-30",
                                    "basis": "accrual", "compare": "previous"})
        assert resp.status_code == 200
        assert resp.content[:4] == b"%PDF"

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
