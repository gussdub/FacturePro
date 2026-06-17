"""Tests d'intégration HTTP pour les paiements partiels (feature #6)."""
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


def _create_test_invoice(auth, unit_price=574.88):
    """Helper : crée un client + invoice 'sent' et retourne (invoice_id, client_id, total).

    Retourne le total réel (avec taxes QC) pour que les tests puissent calculer
    outstanding_cad correctement sans hardcoder de valeur dépendante du taux de taxe.
    """
    c = requests.post(f"{BASE_URL}/api/clients", headers=auth,
                       json={"name": f"Payment Test {os.urandom(4).hex()}"}).json()
    inv = requests.post(f"{BASE_URL}/api/invoices", headers=auth, json={
        "client_id": c["id"],
        "items": [{"description": "S", "quantity": 1, "unit_price": unit_price}],
        "province": "QC",
        "issue_date": "2099-04-15",
    }).json()
    requests.put(f"{BASE_URL}/api/invoices/{inv['id']}/status",
                 headers=auth, json={"status": "sent"})
    return inv["id"], c["id"], float(inv.get("total", 0))


class TestPostPayment:
    _cleanup = {"clients": set(), "invoices": set()}
    _auth_headers = None

    def test_partial_payment_sets_status_partial(self, auth):
        TestPostPayment._auth_headers = auth
        inv_id, c_id, total = _create_test_invoice(auth)
        TestPostPayment._cleanup["invoices"].add(inv_id)
        TestPostPayment._cleanup["clients"].add(c_id)
        partial_amount = round(total * 0.15, 2)  # 15 % du total réel (taxes incluses)
        resp = requests.post(f"{BASE_URL}/api/invoices/{inv_id}/payments",
                              headers=auth, json={
                                  "date": "2026-04-15", "amount_cad": partial_amount,
                                  "method": "cheque", "reference": "1234"
                              })
        assert resp.status_code in (200, 201), resp.text
        body = resp.json()
        assert body["status"] == "partial"
        assert len(body["payments"]) == 1
        assert body["payments"][0]["amount_cad"] == partial_amount
        assert body["total_paid_cad"] == partial_amount
        assert body["outstanding_cad"] == round(total - partial_amount, 2)

    def test_full_payment_sets_status_paid(self, auth):
        TestPostPayment._auth_headers = auth
        inv_id, c_id, total = _create_test_invoice(auth)
        TestPostPayment._cleanup["invoices"].add(inv_id)
        TestPostPayment._cleanup["clients"].add(c_id)
        resp = requests.post(f"{BASE_URL}/api/invoices/{inv_id}/payments",
                              headers=auth, json={
                                  "date": "2026-04-15", "amount_cad": total,
                                  "method": "transfer"
                              })
        body = resp.json()
        assert body["status"] == "paid"
        assert body["outstanding_cad"] == 0

    def test_second_payment_completes_partial(self, auth):
        TestPostPayment._auth_headers = auth
        inv_id, c_id, _total = _create_test_invoice(auth, unit_price=100)
        TestPostPayment._cleanup["invoices"].add(inv_id)
        TestPostPayment._cleanup["clients"].add(c_id)
        get1 = requests.get(f"{BASE_URL}/api/invoices/{inv_id}", headers=auth).json()
        total = get1["total"]
        requests.post(f"{BASE_URL}/api/invoices/{inv_id}/payments", headers=auth,
                      json={"date": "2026-04-15", "amount_cad": round(total * 0.3, 2),
                            "method": "cheque"})
        get2 = requests.get(f"{BASE_URL}/api/invoices/{inv_id}", headers=auth).json()
        outstanding = get2["outstanding_cad"]
        resp = requests.post(f"{BASE_URL}/api/invoices/{inv_id}/payments", headers=auth,
                              json={"date": "2026-04-30", "amount_cad": outstanding,
                                    "method": "transfer"})
        body = resp.json()
        assert body["status"] == "paid"
        assert body["outstanding_cad"] == 0
        assert len(body["payments"]) == 2

    def test_payment_assigns_id_and_created_at(self, auth):
        TestPostPayment._auth_headers = auth
        inv_id, c_id, _total = _create_test_invoice(auth)
        TestPostPayment._cleanup["invoices"].add(inv_id)
        TestPostPayment._cleanup["clients"].add(c_id)
        resp = requests.post(f"{BASE_URL}/api/invoices/{inv_id}/payments", headers=auth,
                              json={"amount_cad": 50, "method": "cash"})
        body = resp.json()
        p = body["payments"][0]
        assert p["id"]
        assert p["created_at"]

    def test_payment_date_default_today(self, auth):
        TestPostPayment._auth_headers = auth
        inv_id, c_id, _total = _create_test_invoice(auth)
        TestPostPayment._cleanup["invoices"].add(inv_id)
        TestPostPayment._cleanup["clients"].add(c_id)
        resp = requests.post(f"{BASE_URL}/api/invoices/{inv_id}/payments", headers=auth,
                              json={"amount_cad": 50, "method": "cash"})
        body = resp.json()
        p = body["payments"][0]
        assert len(p["date"]) == 10 and p["date"][4] == "-" and p["date"][7] == "-"

    def test_payment_on_unknown_invoice_404(self, auth):
        TestPostPayment._auth_headers = auth
        resp = requests.post(f"{BASE_URL}/api/invoices/does-not-exist/payments",
                              headers=auth, json={"amount_cad": 50, "method": "cash"})
        assert resp.status_code == 404

    @classmethod
    def teardown_class(cls):
        if not cls._auth_headers:
            return
        for iid in cls._cleanup["invoices"]:
            try:
                requests.delete(f"{BASE_URL}/api/invoices/{iid}", headers=cls._auth_headers)
            except Exception:
                pass
        for cid in cls._cleanup["clients"]:
            try:
                requests.delete(f"{BASE_URL}/api/clients/{cid}", headers=cls._auth_headers)
            except Exception:
                pass
        cls._cleanup = {"clients": set(), "invoices": set()}


class TestDeletePayment:
    _cleanup = {"clients": set(), "invoices": set()}
    _auth_headers = None

    def test_delete_payment_recomputes_status(self, auth):
        TestDeletePayment._auth_headers = auth
        inv_id, c_id, _total = _create_test_invoice(auth)
        TestDeletePayment._cleanup["invoices"].add(inv_id)
        TestDeletePayment._cleanup["clients"].add(c_id)
        post = requests.post(f"{BASE_URL}/api/invoices/{inv_id}/payments",
                              headers=auth, json={"amount_cad": 100, "method": "cash"})
        payment_id = post.json()["payments"][0]["id"]
        assert post.json()["status"] == "partial"
        resp = requests.delete(
            f"{BASE_URL}/api/invoices/{inv_id}/payments/{payment_id}", headers=auth)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "sent"
        assert len(body["payments"]) == 0
        assert body["total_paid_cad"] == 0
        assert body["outstanding_cad"] == body["total"]

    def test_delete_one_of_two_payments_keeps_partial(self, auth):
        TestDeletePayment._auth_headers = auth
        inv_id, c_id, _total = _create_test_invoice(auth)
        TestDeletePayment._cleanup["invoices"].add(inv_id)
        TestDeletePayment._cleanup["clients"].add(c_id)
        p1 = requests.post(f"{BASE_URL}/api/invoices/{inv_id}/payments",
                            headers=auth, json={"amount_cad": 100, "method": "cash"})
        requests.post(f"{BASE_URL}/api/invoices/{inv_id}/payments",
                      headers=auth, json={"amount_cad": 200, "method": "transfer"})
        pid = p1.json()["payments"][0]["id"]
        resp = requests.delete(
            f"{BASE_URL}/api/invoices/{inv_id}/payments/{pid}", headers=auth)
        body = resp.json()
        assert body["status"] == "partial"
        assert len(body["payments"]) == 1
        assert body["total_paid_cad"] == 200

    def test_delete_payment_from_paid_invoice_reverts_to_partial(self, auth):
        TestDeletePayment._auth_headers = auth
        inv_id, c_id, _total = _create_test_invoice(auth)
        TestDeletePayment._cleanup["invoices"].add(inv_id)
        TestDeletePayment._cleanup["clients"].add(c_id)
        get = requests.get(f"{BASE_URL}/api/invoices/{inv_id}", headers=auth).json()
        total = get["total"]
        requests.post(f"{BASE_URL}/api/invoices/{inv_id}/payments",
                      headers=auth, json={"amount_cad": round(total * 0.7, 2), "method": "cheque"})
        p2 = requests.post(f"{BASE_URL}/api/invoices/{inv_id}/payments",
                            headers=auth, json={"amount_cad": round(total * 0.3, 2), "method": "transfer"})
        assert p2.json()["status"] == "paid"
        pid = p2.json()["payments"][-1]["id"]
        resp = requests.delete(
            f"{BASE_URL}/api/invoices/{inv_id}/payments/{pid}", headers=auth)
        body = resp.json()
        assert body["status"] == "partial"

    def test_delete_unknown_payment_returns_invoice_unchanged(self, auth):
        TestDeletePayment._auth_headers = auth
        inv_id, c_id, _total = _create_test_invoice(auth)
        TestDeletePayment._cleanup["invoices"].add(inv_id)
        TestDeletePayment._cleanup["clients"].add(c_id)
        resp = requests.delete(
            f"{BASE_URL}/api/invoices/{inv_id}/payments/does-not-exist", headers=auth)
        assert resp.status_code == 200

    def test_delete_on_unknown_invoice_404(self, auth):
        TestDeletePayment._auth_headers = auth
        resp = requests.delete(
            f"{BASE_URL}/api/invoices/no-such/payments/p1", headers=auth)
        assert resp.status_code == 404

    @classmethod
    def teardown_class(cls):
        if not cls._auth_headers:
            return
        for iid in cls._cleanup["invoices"]:
            try:
                requests.delete(f"{BASE_URL}/api/invoices/{iid}", headers=cls._auth_headers)
            except Exception:
                pass
        for cid in cls._cleanup["clients"]:
            try:
                requests.delete(f"{BASE_URL}/api/clients/{cid}", headers=cls._auth_headers)
            except Exception:
                pass
        cls._cleanup = {"clients": set(), "invoices": set()}


class TestGetEnriched:
    _cleanup = {"clients": set(), "invoices": set()}
    _auth_headers = None

    def test_get_invoices_includes_enriched_fields(self, auth):
        TestGetEnriched._auth_headers = auth
        inv_id, c_id, total = _create_test_invoice(auth)
        TestGetEnriched._cleanup["invoices"].add(inv_id)
        TestGetEnriched._cleanup["clients"].add(c_id)
        requests.post(f"{BASE_URL}/api/invoices/{inv_id}/payments",
                      headers=auth, json={"amount_cad": 100, "method": "cash"})
        invoices = requests.get(f"{BASE_URL}/api/invoices", headers=auth).json()
        target = next(i for i in invoices if i["id"] == inv_id)
        assert "total_paid_cad" in target
        assert "outstanding_cad" in target
        assert target["total_paid_cad"] == 100

    def test_get_single_invoice_includes_enriched_fields(self, auth):
        TestGetEnriched._auth_headers = auth
        inv_id, c_id, total = _create_test_invoice(auth)
        TestGetEnriched._cleanup["invoices"].add(inv_id)
        TestGetEnriched._cleanup["clients"].add(c_id)
        requests.post(f"{BASE_URL}/api/invoices/{inv_id}/payments",
                      headers=auth, json={"amount_cad": 200, "method": "cheque"})
        body = requests.get(f"{BASE_URL}/api/invoices/{inv_id}", headers=auth).json()
        assert body["total_paid_cad"] == 200
        assert "outstanding_cad" in body

    @classmethod
    def teardown_class(cls):
        if not cls._auth_headers:
            return
        for iid in cls._cleanup["invoices"]:
            try:
                requests.delete(f"{BASE_URL}/api/invoices/{iid}", headers=cls._auth_headers)
            except Exception:
                pass
        for cid in cls._cleanup["clients"]:
            try:
                requests.delete(f"{BASE_URL}/api/clients/{cid}", headers=cls._auth_headers)
            except Exception:
                pass
        cls._cleanup = {"clients": set(), "invoices": set()}


class TestDashboardOutstanding:
    _cleanup = {"clients": set(), "invoices": set()}
    _auth_headers = None

    def test_outstanding_endpoint_returns_total(self, auth):
        TestDashboardOutstanding._auth_headers = auth
        inv_id, c_id, _total = _create_test_invoice(auth)
        TestDashboardOutstanding._cleanup["invoices"].add(inv_id)
        TestDashboardOutstanding._cleanup["clients"].add(c_id)
        before = requests.get(f"{BASE_URL}/api/dashboard/outstanding", headers=auth).json()
        before_total = before["total_outstanding_cad"]
        requests.post(f"{BASE_URL}/api/invoices/{inv_id}/payments",
                      headers=auth, json={"amount_cad": 100, "method": "cash"})
        after = requests.get(f"{BASE_URL}/api/dashboard/outstanding", headers=auth).json()
        assert round(before_total - after["total_outstanding_cad"], 2) == 100.00

    def test_outstanding_excludes_paid(self, auth):
        TestDashboardOutstanding._auth_headers = auth
        inv_id, c_id, _total = _create_test_invoice(auth)
        TestDashboardOutstanding._cleanup["invoices"].add(inv_id)
        TestDashboardOutstanding._cleanup["clients"].add(c_id)
        get = requests.get(f"{BASE_URL}/api/invoices/{inv_id}", headers=auth).json()
        before = requests.get(f"{BASE_URL}/api/dashboard/outstanding", headers=auth).json()
        requests.post(f"{BASE_URL}/api/invoices/{inv_id}/payments", headers=auth,
                      json={"amount_cad": get["total"], "method": "transfer"})
        after = requests.get(f"{BASE_URL}/api/dashboard/outstanding", headers=auth).json()
        assert before["total_outstanding_cad"] - after["total_outstanding_cad"] >= get["total"] - 0.01

    @classmethod
    def teardown_class(cls):
        if not cls._auth_headers:
            return
        for iid in cls._cleanup["invoices"]:
            try:
                requests.delete(f"{BASE_URL}/api/invoices/{iid}", headers=cls._auth_headers)
            except Exception:
                pass
        for cid in cls._cleanup["clients"]:
            try:
                requests.delete(f"{BASE_URL}/api/clients/{cid}", headers=cls._auth_headers)
            except Exception:
                pass
        cls._cleanup = {"clients": set(), "invoices": set()}


class TestPdfWithPayments:
    _cleanup = {"clients": set(), "invoices": set()}
    _auth_headers = None

    def test_pdf_with_payments_renders(self, auth):
        TestPdfWithPayments._auth_headers = auth
        inv_id, c_id = _create_test_invoice(auth)[:2]
        TestPdfWithPayments._cleanup["invoices"].add(inv_id)
        TestPdfWithPayments._cleanup["clients"].add(c_id)
        requests.post(f"{BASE_URL}/api/invoices/{inv_id}/payments",
                      headers=auth, json={"amount_cad": 100, "method": "cheque",
                                          "reference": "Test1234"})
        resp = requests.get(f"{BASE_URL}/api/invoices/{inv_id}/pdf", headers=auth)
        assert resp.status_code == 200
        assert resp.content[:4] == b"%PDF"
        assert len(resp.content) > 2000

    @classmethod
    def teardown_class(cls):
        if not cls._auth_headers:
            return
        for iid in cls._cleanup["invoices"]:
            try:
                requests.delete(f"{BASE_URL}/api/invoices/{iid}", headers=cls._auth_headers)
            except Exception:
                pass
        for cid in cls._cleanup["clients"]:
            try:
                requests.delete(f"{BASE_URL}/api/clients/{cid}", headers=cls._auth_headers)
            except Exception:
                pass
        cls._cleanup = {"clients": set(), "invoices": set()}
