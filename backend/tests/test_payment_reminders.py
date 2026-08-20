"""Tests — date convenue pour le solde + rappels « À relancer » (feature #7.15)."""
import os
import sys
import uuid as _uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test")
os.environ.setdefault("DB_NAME", "facturepro")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from backend.server import app, db  # noqa: E402

client = TestClient(app)


@pytest.fixture
def auth_headers():
    r = client.post("/api/auth/login",
                    json={"email": "gussdub@gmail.com", "password": "testpass123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def org_id():
    return db.users.find_one({"email": "gussdub@gmail.com"})["organization_id"]


@pytest.fixture
def temp_data(org_id):
    cid = str(_uuid.uuid4())
    db.clients.insert_one({"id": cid, "organization_id": org_id, "name": "Client Relance Test"})
    made = {"client_id": cid, "invoice_ids": []}

    def inv(num, total, payments, status, bdd):
        iid = str(_uuid.uuid4())
        db.invoices.insert_one({
            "id": iid, "organization_id": org_id, "invoice_number": num, "client_id": cid,
            "total": total, "status": status,
            "issue_date": "2026-01-01", "due_date": "2026-01-31",
            "payments": [{"id": str(_uuid.uuid4()), "amount_cad": p} for p in payments],
            "balance_due_date": bdd,
        })
        made["invoice_ids"].append(iid)
        return iid

    made["past_partial"] = inv("REL-1", 100.0, [50.0], "partial", "2020-01-01")   # à relancer
    made["future"] = inv("REL-2", 100.0, [], "sent", "2099-01-01")                # trop tôt
    made["paid"] = inv("REL-3", 100.0, [100.0], "paid", "2020-01-01")             # payée → non
    made["no_date"] = inv("REL-4", 100.0, [], "sent", None)                       # pas de date → non
    yield made
    db.clients.delete_many({"organization_id": org_id, "id": cid})
    db.invoices.delete_many({"id": {"$in": made["invoice_ids"]}})


class TestReminders:
    def test_endpoint_lists_only_due_with_balance(self, auth_headers, temp_data):
        r = client.get("/api/invoices/payment-reminders", headers=auth_headers)
        assert r.status_code == 200, r.text
        by_id = {x["invoice_id"]: x for x in r.json()["reminders"]}
        assert temp_data["past_partial"] in by_id       # solde 50 + date passée
        assert temp_data["future"] not in by_id         # date trop lointaine
        assert temp_data["paid"] not in by_id           # payée
        assert temp_data["no_date"] not in by_id         # pas de date convenue
        rec = by_id[temp_data["past_partial"]]
        assert rec["outstanding_cad"] == 50.0
        assert rec["days_overdue"] > 0                   # en retard
        assert rec["client_name"] == "Client Relance Test"

    def test_route_not_shadowed_by_invoice_id(self, auth_headers):
        # /payment-reminders ne doit pas être traité comme un {invoice_id} (=> pas de 404).
        r = client.get("/api/invoices/payment-reminders", headers=auth_headers)
        assert r.status_code == 200
        assert "reminders" in r.json() and "count" in r.json()


class TestPaymentStoresBalanceDueDate:
    def _make_invoice(self, org_id, total):
        iid = str(_uuid.uuid4())
        db.invoices.insert_one({
            "id": iid, "organization_id": org_id, "invoice_number": "PAY-" + iid[:6],
            "client_id": None, "total": total, "status": "sent",
            "issue_date": "2026-01-01", "due_date": "2026-01-31", "payments": [],
        })
        return iid

    def test_partial_payment_stores_date(self, auth_headers, org_id):
        iid = self._make_invoice(org_id, 100.0)
        try:
            r = client.post(f"/api/invoices/{iid}/payments", headers=auth_headers,
                            json={"amount_cad": 40, "method": "cheque",
                                  "balance_due_date": "2026-09-15"})
            assert r.status_code == 200, r.text
            inv = db.invoices.find_one({"id": iid}, {"_id": 0})
            assert inv["status"] == "partial"
            assert inv["balance_due_date"] == "2026-09-15"
        finally:
            db.invoices.delete_one({"id": iid})

    def test_full_payment_clears_date(self, auth_headers, org_id):
        iid = self._make_invoice(org_id, 100.0)
        db.invoices.update_one({"id": iid}, {"$set": {"balance_due_date": "2026-09-15"}})
        try:
            r = client.post(f"/api/invoices/{iid}/payments", headers=auth_headers,
                            json={"amount_cad": 100, "method": "cheque"})
            assert r.status_code == 200, r.text
            inv = db.invoices.find_one({"id": iid}, {"_id": 0})
            assert inv["status"] == "paid"
            assert inv.get("balance_due_date") is None
        finally:
            db.invoices.delete_one({"id": iid})

    def test_invalid_date_400(self, auth_headers, org_id):
        iid = self._make_invoice(org_id, 100.0)
        try:
            r = client.post(f"/api/invoices/{iid}/payments", headers=auth_headers,
                            json={"amount_cad": 40, "balance_due_date": "pas-une-date"})
            assert r.status_code == 400
        finally:
            db.invoices.delete_one({"id": iid})

    def test_partial_payment_canonicalizes_date(self, auth_headers, org_id):
        # Py3.11 accepte l'ISO compact « 20260915 » ; il DOIT être stocké canoniquement
        # (« 2026-09-15 ») sinon la query $lte lexicographique des rappels le rate. La date
        # convenue arrivée → la facture doit apparaître dans /payment-reminders.
        iid = self._make_invoice(org_id, 100.0)
        try:
            r = client.post(f"/api/invoices/{iid}/payments", headers=auth_headers,
                            json={"amount_cad": 40, "method": "cheque",
                                  "balance_due_date": "20200115"})
            assert r.status_code == 200, r.text
            inv = db.invoices.find_one({"id": iid}, {"_id": 0})
            assert inv["balance_due_date"] == "2020-01-15"  # canonique, pas « 20200115 »
            rem = client.get("/api/invoices/payment-reminders", headers=auth_headers)
            assert iid in {x["invoice_id"] for x in rem.json()["reminders"]}
        finally:
            db.invoices.delete_one({"id": iid})


class TestSetting:
    def test_lead_days_clamped(self, auth_headers):
        r = client.put("/api/settings/company", headers=auth_headers,
                       json={"payment_reminder_lead_days": 999})
        assert r.status_code == 200, r.text
        assert r.json()["payment_reminder_lead_days"] == 60
        # restaure un défaut raisonnable
        client.put("/api/settings/company", headers=auth_headers,
                   json={"payment_reminder_lead_days": 3})

    def test_lead_days_infinite_rejected(self, auth_headers):
        # JSON Infinity ne doit pas casser int(float('inf')) (OverflowError → 500) : 422 attendu.
        # httpx refuse d'encoder Infinity via json= → on envoie le corps brut (json.loads de
        # Starlette accepte « Infinity » par défaut, exactement comme un vrai client mal élevé).
        r = client.put(
            "/api/settings/company",
            headers={**auth_headers, "Content-Type": "application/json"},
            content='{"payment_reminder_lead_days": Infinity}',
        )
        assert r.status_code == 422, r.text
        # l'org ne doit pas avoir été corrompue : la valeur reste un entier lisible
        chk = client.get("/api/settings/company", headers=auth_headers)
        assert isinstance(chk.json().get("payment_reminder_lead_days"), int)
