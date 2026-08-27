"""Tests — envoi email multi-destinataires + Cc (factures & soumissions)."""
import os
import sys
import uuid as _uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test")
os.environ.setdefault("DB_NAME", "facturepro")

import pytest  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from backend import server  # noqa: E402
from backend.server import app, db, _parse_email_list, _resolve_email_recipients  # noqa: E402

client = TestClient(app)


class TestParseEmailList:
    def test_none_and_empty(self):
        assert _parse_email_list(None) == []
        assert _parse_email_list("") == []
        assert _parse_email_list("   ") == []

    def test_single(self):
        assert _parse_email_list("a@x.com") == ["a@x.com"]

    def test_comma_semicolon_space_separated(self):
        assert _parse_email_list("a@x.com, b@y.com; c@z.com  d@w.com") == \
            ["a@x.com", "b@y.com", "c@z.com", "d@w.com"]

    def test_list_input(self):
        assert _parse_email_list(["a@x.com", "b@y.com,c@z.com"]) == \
            ["a@x.com", "b@y.com", "c@z.com"]

    def test_dedup_case_insensitive_keeps_order(self):
        assert _parse_email_list("A@x.com, a@X.com, b@y.com") == ["A@x.com", "b@y.com"]

    def test_invalid_raises_400(self):
        with pytest.raises(HTTPException) as e:
            _parse_email_list("a@x.com, pas-un-email")
        assert e.value.status_code == 400
        assert "pas-un-email" in e.value.detail


class TestResolveRecipients:
    def test_fallback_to_client_email(self):
        to, cc = _resolve_email_recipients({}, "client@ex.com")
        assert to == ["client@ex.com"] and cc == []

    def test_body_overrides_fallback(self):
        to, cc = _resolve_email_recipients({"to_email": "a@x.com, b@y.com"}, "client@ex.com")
        assert to == ["a@x.com", "b@y.com"]

    def test_no_recipient_raises(self):
        with pytest.raises(HTTPException) as e:
            _resolve_email_recipients({}, None)
        assert e.value.status_code == 400

    def test_cc_never_duplicates_to(self):
        to, cc = _resolve_email_recipients(
            {"to_email": "a@x.com", "cc": "a@x.com, b@y.com"}, None)
        assert to == ["a@x.com"] and cc == ["b@y.com"]

    def test_cap_enforced(self):
        many = ", ".join(f"u{i}@x.com" for i in range(30))
        with pytest.raises(HTTPException) as e:
            _resolve_email_recipients({"to_email": many}, None)
        assert e.value.status_code == 400
        assert str(server._EMAIL_MAX_RECIPIENTS) in e.value.detail


@pytest.fixture
def sent(monkeypatch):
    """Capture les params passés à Resend sans envoyer réellement."""
    captured = {}
    monkeypatch.setattr(server, "RESEND_API_KEY", "re_test")

    class _Emails:
        @staticmethod
        def send(params):
            captured.update(params)
            return {"id": "email_test"}
    monkeypatch.setattr(server.resend, "Emails", _Emails)
    return captured


class TestInvoiceSendWiring:
    def test_multi_to_and_cc_passed_to_resend(self, sent):
        org_id = f"TESTORG-MAIL-{_uuid.uuid4()}"
        # user propriétaire minimal + token
        uid = str(_uuid.uuid4())
        db.users.insert_one({"id": uid, "email": f"o-{uid[:8]}@ex.com",
                             "organization_id": org_id, "role": "owner", "is_active": True})
        db.organizations.insert_one({"id": org_id, "owner_id": uid, "name": "MailCo",
                                     "role_permissions": {}})
        inv_id = str(_uuid.uuid4())
        cli_id = str(_uuid.uuid4())
        db.clients.insert_one({"id": cli_id, "organization_id": org_id, "email": "client@ex.com",
                               "name": "Client"})
        db.invoices.insert_one({"id": inv_id, "organization_id": org_id, "client_id": cli_id,
                                "invoice_number": "INV-TEST", "status": "draft",
                                "items": [], "total": 0})
        tok = server.create_token(uid)
        try:
            r = client.post(f"/api/invoices/{inv_id}/send",
                            headers={"Authorization": f"Bearer {tok}"},
                            json={"to_email": "a@x.com, b@y.com", "cc": "boss@x.com"})
            assert r.status_code == 200, r.text
            assert sent["to"] == ["a@x.com", "b@y.com"]
            assert sent["cc"] == ["boss@x.com"]
            inv = db.invoices.find_one({"id": inv_id}, {"_id": 0})
            assert inv["sent_to"] == "a@x.com, b@y.com"
            assert inv["sent_cc"] == "boss@x.com"
            assert inv["status"] == "sent"
        finally:
            db.users.delete_one({"id": uid})
            db.organizations.delete_one({"id": org_id})
            db.clients.delete_one({"id": cli_id})
            db.invoices.delete_one({"id": inv_id})
            db.audit_logs.delete_many({"organization_id": org_id})

    def test_invalid_recipient_rejected(self, sent):
        org_id = f"TESTORG-MAIL-{_uuid.uuid4()}"
        uid = str(_uuid.uuid4())
        db.users.insert_one({"id": uid, "email": f"o-{uid[:8]}@ex.com",
                             "organization_id": org_id, "role": "owner", "is_active": True})
        db.organizations.insert_one({"id": org_id, "owner_id": uid, "name": "MailCo",
                                     "role_permissions": {}})
        inv_id = str(_uuid.uuid4())
        db.invoices.insert_one({"id": inv_id, "organization_id": org_id, "client_id": "x",
                                "invoice_number": "INV-BAD", "status": "draft", "items": [], "total": 0})
        tok = server.create_token(uid)
        try:
            r = client.post(f"/api/invoices/{inv_id}/send",
                            headers={"Authorization": f"Bearer {tok}"},
                            json={"to_email": "pas-un-email"})
            assert r.status_code == 400
        finally:
            db.users.delete_one({"id": uid})
            db.organizations.delete_one({"id": org_id})
            db.invoices.delete_one({"id": inv_id})
            db.audit_logs.delete_many({"organization_id": org_id})
