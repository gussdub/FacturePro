"""Tests — journal d'audit (Loi 25 : traçabilité).

Couvre : middleware générique (CRUD données), événements sémantiques (auth/admin), accès
propriétaire seul, isolation cross-org, export CSV/JSON, filtres, forme du helper."""
import os
import sys
import uuid as _uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test")
os.environ.setdefault("DB_NAME", "facturepro")

import time  # noqa: E402
import pytest  # noqa: E402
from datetime import datetime  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from backend import server  # noqa: E402
from backend.server import app, db  # noqa: E402

client = TestClient(app)


def _wait_audit(query, timeout=3.0):
    """Le middleware écrit le journal en FIRE-AND-FORGET (hors chemin de réponse). On attend donc que
    l'entrée apparaisse (le portail bloquant de TestClient fait tourner l'event-loop en continu)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        d = db.audit_logs.find_one(query)
        if d:
            return d
        time.sleep(0.05)
    return None


def _register_owner():
    email = f"audit-{_uuid.uuid4().hex[:8]}@ex.com"
    pw = "auditpass12345"
    r = client.post("/api/auth/register",
                    json={"email": email, "password": pw, "company_name": "Audit Test"})
    assert r.status_code == 200, r.text
    uid = r.json()["user"]["id"]
    org_id = (db.users.find_one({"id": uid}) or {}).get("organization_id")
    return {"id": uid, "email": email, "password": pw, "org_id": org_id,
            "headers": {"Authorization": f"Bearer {r.json()['access_token']}"}}


def _cleanup(org_id, extra_uids=()):
    db.audit_logs.delete_many({"organization_id": org_id})
    for u in db.users.find({"organization_id": org_id}, {"_id": 0, "id": 1}):
        db.user_passwords.delete_one({"user_id": u["id"]})
        db.user_mfa.delete_one({"user_id": u["id"]})
    db.users.delete_many({"organization_id": org_id})
    db.clients.delete_many({"organization_id": org_id})
    db.organizations.delete_one({"id": org_id})
    for uid in extra_uids:
        db.users.delete_one({"id": uid})
        db.user_passwords.delete_one({"user_id": uid})


@pytest.fixture
def owner():
    o = _register_owner()
    yield o
    _cleanup(o["org_id"])


class TestMiddlewareDataAudit:
    def test_data_mutation_is_logged(self, owner):
        # POST /api/clients (mutation métier) → journalisé génériquement par le middleware.
        r = client.post("/api/clients", headers=owner["headers"], json={"name": "Acme"})
        assert r.status_code == 200, r.text
        log = _wait_audit({"organization_id": owner["org_id"], "action": "client.create"})
        assert log is not None
        assert log["category"] == "data"
        assert log["actor_email"] == owner["email"]
        assert log["target_type"] == "client"
        assert log["outcome"] == "success"
        assert isinstance(log["ts"], datetime)          # date BSON (tri + TTL)

    def test_read_is_not_logged(self, owner):
        # Un GET (lecture) ne produit PAS d'entrée (seules les mutations sont journalisées).
        before = db.audit_logs.count_documents({"organization_id": owner["org_id"]})
        client.get("/api/clients", headers=owner["headers"])
        after = db.audit_logs.count_documents({"organization_id": owner["org_id"]})
        assert after == before


class TestSemanticAuthEvents:
    def test_login_success_and_failure_logged(self, owner):
        db.audit_logs.delete_many({"organization_id": owner["org_id"]})
        # mauvais mot de passe → auth.login.failure
        client.post("/api/auth/login", json={"email": owner["email"], "password": "WRONG"})
        fail = db.audit_logs.find_one(
            {"organization_id": owner["org_id"], "action": "auth.login.failure"})
        assert fail is not None and fail["outcome"] == "failure"
        assert fail["metadata"]["reason"] == "bad_password"
        # bon mot de passe → auth.login
        client.post("/api/auth/login",
                    json={"email": owner["email"], "password": owner["password"]})
        ok = db.audit_logs.find_one(
            {"organization_id": owner["org_id"], "action": "auth.login"})
        assert ok is not None and ok["category"] == "auth"
        # purge le verrou anti-force-brute créé par l'échec
        db.login_attempts.delete_one(
            {"_id": server._login_attempt_key(owner["email"], "testclient")})


class TestAccessControl:
    def test_owner_can_read_member_cannot(self, owner):
        # membre non-propriétaire dans l'org
        m_email = f"m-{_uuid.uuid4().hex[:8]}@ex.com"
        m_pw, m_uid = "memberpass123", str(_uuid.uuid4())
        db.users.insert_one({"id": m_uid, "email": m_email, "organization_id": owner["org_id"],
                             "role": "accountant", "is_active": True})
        db.user_passwords.insert_one({"user_id": m_uid, "hashed_password": server.hash_password(m_pw)})
        try:
            m_tok = client.post("/api/auth/login",
                                json={"email": m_email, "password": m_pw}).json()["access_token"]
            mh = {"Authorization": f"Bearer {m_tok}"}
            assert client.get("/api/org/audit-logs", headers=mh).status_code == 403
            assert client.get("/api/org/audit-logs", headers=owner["headers"]).status_code == 200
        finally:
            db.login_attempts.delete_one(
                {"_id": server._login_attempt_key(m_email, "testclient")})

    def test_cross_org_isolation(self, owner):
        client.post("/api/clients", headers=owner["headers"], json={"name": "Secret Corp"})
        other = _register_owner()
        try:
            body = client.get("/api/org/audit-logs", headers=other["headers"]).json()
            assert all(l["organization_id"] == other["org_id"] for l in body["logs"])
            assert not any(l.get("actor_email") == owner["email"] for l in body["logs"])
        finally:
            _cleanup(other["org_id"])


class TestExportAndFilters:
    def test_export_csv_has_bom_and_header(self, owner):
        client.post("/api/clients", headers=owner["headers"], json={"name": "Acme"})
        r = client.get("/api/org/audit-logs/export?format=csv", headers=owner["headers"])
        assert r.status_code == 200
        text = r.content.decode("utf-8-sig")
        assert text.splitlines()[0].startswith("Date (UTC),Acteur,Action")
        assert "client.create" in text

    def test_export_json_is_list(self, owner):
        client.post("/api/clients", headers=owner["headers"], json={"name": "Acme"})
        r = client.get("/api/org/audit-logs/export?format=json", headers=owner["headers"])
        assert r.status_code == 200 and isinstance(r.json(), list)
        assert any(l["action"] == "client.create" for l in r.json())

    def test_filter_by_category(self, owner):
        client.post("/api/clients", headers=owner["headers"], json={"name": "Acme"})  # data
        _wait_audit({"organization_id": owner["org_id"], "action": "client.create"})
        r = client.get("/api/org/audit-logs?category=data", headers=owner["headers"])
        assert r.status_code == 200
        assert all(l["category"] == "data" for l in r.json()["logs"])
        assert r.json()["total"] >= 1


class TestCoverageFixes:
    def test_email_change_logged(self, owner):
        new_email = f"changed-{_uuid.uuid4().hex[:8]}@ex.com"
        r = client.put("/api/auth/me/email", headers=owner["headers"], json={"email": new_email})
        assert r.status_code == 200, r.text
        log = db.audit_logs.find_one(
            {"organization_id": owner["org_id"], "action": "auth.email.changed"})
        assert log is not None and log["target_label"] == new_email
        assert log["metadata"]["old_email"] == owner["email"]

    def test_role_permissions_change_logged(self, owner):
        r = client.put("/api/org/role-permissions", headers=owner["headers"],
                       json={"role": "viewer", "permissions": ["invoices:read"]})
        assert r.status_code == 200, r.text
        log = db.audit_logs.find_one(
            {"organization_id": owner["org_id"], "action": "org.role_permissions.update"})
        assert log is not None and log["category"] == "admin"
        assert log["metadata"]["role"] == "viewer"
        assert log["metadata"]["new"] == ["invoices:read"]

    def test_invitation_revoke_logged(self, owner):
        inv_id = str(_uuid.uuid4())
        db.invitations.insert_one({"id": inv_id, "organization_id": owner["org_id"],
                                   "email": "invitee@ex.com", "role": "viewer",
                                   "token": _uuid.uuid4().hex, "status": "pending"})
        try:
            r = client.delete(f"/api/org/invitations/{inv_id}", headers=owner["headers"])
            assert r.status_code == 204, r.text
            log = db.audit_logs.find_one(
                {"organization_id": owner["org_id"], "action": "org.invitation.revoked"})
            assert log is not None and log["target_label"] == "invitee@ex.com"
        finally:
            db.invitations.delete_one({"id": inv_id})

    def test_file_delete_logged_by_middleware(self, owner):
        # DELETE /api/files/{id} (préfixe ajouté à l'allowlist) → journalisé même sur 404 (échec).
        r = client.delete(f"/api/files/{_uuid.uuid4()}", headers=owner["headers"])
        assert r.status_code == 404
        log = _wait_audit({"organization_id": owner["org_id"], "action": "file.delete"})
        assert log is not None and log["outcome"] == "failure"

    def test_audit_endpoints_require_mfa_when_org_enforces(self, owner):
        # Cohérence : si l'org impose la 2FA et que le propriétaire n'est pas enrôlé, l'accès au
        # journal est bloqué comme le reste (pas d'exemption du gate MFA).
        db.organizations.update_one({"id": owner["org_id"]}, {"$set": {"require_mfa": True}})
        try:
            r = client.get("/api/org/audit-logs", headers=owner["headers"])
            assert r.status_code == 403
            assert r.json().get("detail") == "mfa_enrollment_required"
        finally:
            db.organizations.update_one({"id": owner["org_id"]}, {"$set": {"require_mfa": False}})

    def test_trailing_slash_redirect_not_phantom_logged(self, owner):
        # POST /api/clients/ → 307 → suivi → 200. Le 307 ne doit PAS créer d'entrée fantôme.
        client.post("/api/clients/", headers=owner["headers"], json={"name": "SlashCo"})
        phantom = db.audit_logs.find_one(
            {"organization_id": owner["org_id"], "action": "client.create", "metadata.status": 307})
        assert phantom is None

    def test_export_truncation_header_present(self, owner):
        client.post("/api/clients", headers=owner["headers"], json={"name": "Acme"})
        _wait_audit({"organization_id": owner["org_id"], "action": "client.create"})
        r = client.get("/api/org/audit-logs/export?format=csv", headers=owner["headers"])
        assert r.status_code == 200
        assert r.headers.get("X-Audit-Export-Truncated") == "false"
        assert int(r.headers.get("X-Audit-Export-Returned")) >= 1


class TestHelper:
    def test_audit_helper_shape(self, owner):
        server._audit("test.event", actor_user_id=owner["id"], actor_email=owner["email"],
                      organization_id=owner["org_id"], category="security",
                      metadata={"k": "v"})
        d = db.audit_logs.find_one({"organization_id": owner["org_id"], "action": "test.event"})
        assert d is not None
        assert isinstance(d["ts"], datetime)
        assert d["metadata"] == {"k": "v"}
        # aucun champ secret ne doit exister
        assert "password" not in d and "token" not in d and "code" not in d
