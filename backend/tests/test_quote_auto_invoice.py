"""Facturation planifiée : une soumission portant `auto_invoice_date` est convertie en facture
puis envoyée par courriel au client à cette date."""
import sys as _sys
import os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
import server as server_module
from fastapi.testclient import TestClient
from server import DEFAULT_ROLE_PERMISSIONS, create_token, process_scheduled_quote_invoices

TODAY = server_module._today_local_isodate()
TOMORROW = (date.fromisoformat(TODAY) + timedelta(days=1)).isoformat()
YESTERDAY = (date.fromisoformat(TODAY) - timedelta(days=1)).isoformat()


@pytest.fixture(scope="module")
def client():
    return TestClient(server_module.app)


@pytest.fixture()
def sent(monkeypatch):
    calls = []
    monkeypatch.setattr(server_module, "RESEND_API_KEY", "re_test")
    monkeypatch.setattr(server_module.resend.Emails, "send",
                        lambda params: calls.append(params) or {"id": "em_1"})
    return calls


@pytest.fixture()
def org():
    db = server_module.db
    org_id = str(uuid.uuid4())
    owner_id, emp_id = f"own-{uuid.uuid4().hex[:8]}", f"emp-{uuid.uuid4().hex[:8]}"
    db.organizations.insert_one({
        "id": org_id, "name": "Auto Facture Co", "owner_id": owner_id,
        "subscription_status": "active",
        "role_permissions": {"accountant": DEFAULT_ROLE_PERMISSIONS["accountant"],
                             "viewer": DEFAULT_ROLE_PERMISSIONS["viewer"]},
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    for uid, role in ((owner_id, "owner"), (emp_id, "employee")):
        db.users.insert_one({"id": uid, "email": f"{uid}@test.local", "is_active": True,
                             "organization_id": org_id, "role": role})
    h = lambda uid: {"Authorization": f"Bearer {create_token(uid, 0)}"}
    cid = str(uuid.uuid4())
    db.clients.insert_one({"id": cid, "organization_id": org_id, "name": "Client A",
                           "email": "client@exemple.ca", "created_by_user_id": owner_id})
    yield {"id": org_id, "owner": h(owner_id), "emp": h(emp_id), "owner_id": owner_id,
           "emp_id": emp_id, "client_id": cid}
    db.organizations.delete_many({"id": org_id})
    for coll in ("users", "clients", "quotes", "invoices", "company_settings"):
        db[coll].delete_many({"organization_id": org_id})


def _quote(client, org, headers=None, **extra):
    body = {"client_id": org["client_id"], "province": "QC",
            "items": [{"description": "Inspection", "quantity": 1, "unit_price": 100}], **extra}
    r = client.post("/api/quotes", json=body, headers=headers or org["owner"])
    return r


def _q(qid):
    return server_module.db.quotes.find_one({"id": qid}, {"_id": 0})


class TestScheduling:
    def test_create_with_date_is_scheduled(self, client, org):
        r = _quote(client, org, auto_invoice_date=TOMORROW)
        assert r.status_code == 200, r.text
        assert r.json()["auto_invoice_date"] == TOMORROW
        assert r.json()["auto_invoice_status"] == "scheduled"

    def test_past_date_rejected(self, client, org):
        assert _quote(client, org, auto_invoice_date=YESTERDAY).status_code == 400

    def test_invalid_date_rejected(self, client, org):
        assert _quote(client, org, auto_invoice_date="demain").status_code == 400

    def test_employee_cannot_schedule(self, client, org):
        assert _quote(client, org, headers=org["emp"], auto_invoice_date=TOMORROW).status_code == 403

    def test_employee_can_edit_scheduled_quote_without_touching_date(self, client, org):
        db = server_module.db
        qid = _quote(client, org, headers=org["emp"]).json()["id"]
        db.quotes.update_one({"id": qid}, {"$set": {"auto_invoice_date": TOMORROW,
                                                    "auto_invoice_status": "scheduled"}})
        r = client.put(f"/api/quotes/{qid}", json={"notes": "x", "auto_invoice_date": TOMORROW},
                       headers=org["emp"])
        assert r.status_code == 200, r.text

    def test_client_cannot_forge_status(self, client, org):
        qid = _quote(client, org).json()["id"]
        client.put(f"/api/quotes/{qid}", json={"auto_invoice_status": "scheduled"}, headers=org["owner"])
        assert _q(qid).get("auto_invoice_status") is None

    def test_clear_date(self, client, org):
        qid = _quote(client, org, auto_invoice_date=TOMORROW).json()["id"]
        client.put(f"/api/quotes/{qid}", json={"auto_invoice_date": ""}, headers=org["owner"])
        assert _q(qid)["auto_invoice_status"] is None


class TestProcessing:
    def test_due_quote_converted_and_sent(self, client, org, sent):
        qid = _quote(client, org, auto_invoice_date=TODAY).json()["id"]
        out = process_scheduled_quote_invoices()
        assert out["results"].get("sent", 0) >= 1
        q = _q(qid)
        assert q["status"] == "converted" and q["auto_invoice_status"] == "sent"
        inv = server_module.db.invoices.find_one({"id": q["auto_invoice_invoice_id"]}, {"_id": 0})
        assert inv["status"] == "sent" and inv["auto_from_quote_id"] == qid
        assert inv["due_date"] == (date.fromisoformat(TODAY) + timedelta(days=30)).isoformat()
        assert [p["to"] for p in sent] == [["client@exemple.ca"]]

    def test_runs_only_once(self, client, org, sent):
        _quote(client, org, auto_invoice_date=TODAY)
        process_scheduled_quote_invoices()
        process_scheduled_quote_invoices()
        assert len(sent) == 1
        assert server_module.db.invoices.count_documents({"organization_id": org["id"]}) == 1

    def test_future_quote_untouched(self, client, org, sent):
        qid = _quote(client, org, auto_invoice_date=TOMORROW).json()["id"]
        process_scheduled_quote_invoices()
        assert _q(qid)["auto_invoice_status"] == "scheduled" and not sent

    def test_refused_quote_skipped(self, client, org, sent):
        qid = _quote(client, org, auto_invoice_date=TODAY).json()["id"]
        client.put(f"/api/quotes/{qid}/status", json={"status": "refused"}, headers=org["owner"])
        process_scheduled_quote_invoices()
        assert _q(qid)["auto_invoice_status"] == "skipped" and not sent
        assert server_module.db.invoices.count_documents({"organization_id": org["id"]}) == 0

    def test_send_failure_keeps_invoice_and_shows_error(self, client, org, monkeypatch):
        monkeypatch.setattr(server_module, "RESEND_API_KEY", "re_test")

        def boom(params):
            raise RuntimeError("quota")
        monkeypatch.setattr(server_module.resend.Emails, "send", boom)
        qid = _quote(client, org, auto_invoice_date=TODAY).json()["id"]
        process_scheduled_quote_invoices()
        q = _q(qid)
        assert q["auto_invoice_status"] == "send_failed" and q["auto_invoice_error"]
        inv = server_module.db.invoices.find_one({"id": q["auto_invoice_invoice_id"]}, {"_id": 0})
        assert inv["status"] == "draft" and inv["auto_send_error"]

    def test_scheduler_lost_invoice_right(self, client, org, sent):
        db = server_module.db
        qid = _quote(client, org, auto_invoice_date=TODAY).json()["id"]
        # L'employé est l'auteur ET le planificateur : seul le droit invoices:write lui manque.
        db.quotes.update_one({"id": qid}, {"$set": {"auto_invoice_scheduled_by": org["emp_id"],
                                                    "created_by_user_id": org["emp_id"]}})
        process_scheduled_quote_invoices()
        q = _q(qid)
        assert q["auto_invoice_status"] == "failed" and not sent
        assert "droit de créer des factures" in q["auto_invoice_error"]
        assert db.invoices.count_documents({"organization_id": org["id"]}) == 0

    def test_manual_convert_cancels_schedule(self, client, org, sent):
        qid = _quote(client, org, auto_invoice_date=TOMORROW).json()["id"]
        r = client.post(f"/api/quotes/{qid}/convert", json={}, headers=org["owner"])
        assert r.status_code == 200
        assert _q(qid)["auto_invoice_status"] is None

    def test_cron_endpoint_secret(self, client, org, monkeypatch):
        monkeypatch.setenv("CRON_SECRET", "s3cret")
        assert client.post("/api/quotes/process-scheduled").status_code == 401
        r = client.post("/api/quotes/process-scheduled", headers={"X-Cron-Secret": "s3cret"})
        assert r.status_code == 200 and "processed" in r.json()
