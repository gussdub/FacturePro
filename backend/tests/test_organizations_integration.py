import sys as _sys
import os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))

import uuid
from datetime import datetime, timezone, timedelta

import pytest
import server as server_module
from fastapi.testclient import TestClient


BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="module")
def client():
    return TestClient(server_module.app)


@pytest.fixture(scope="module")
def owner_headers(client):
    resp = client.post("/api/auth/login",
                       json={"email": "gussdub@gmail.com", "password": "testpass123"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ─── Regression tests for FIX-PASS Task 2 ───

class TestExpiredUserNotHardGated:
    """Fix 1 (regression): get_current_user_with_access must NOT raise 402.
    An expired user must still reach /api/auth/me, /api/subscription/current,
    and /api/subscription/create-checkout so they can renew."""

    def _make_expired_user(self):
        db = server_module.db
        uid = f"test-expired-{uuid.uuid4().hex[:8]}"
        email = f"{uid}@test.local"
        org_id = str(uuid.uuid4())
        past_iso = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        db.organizations.insert_one({
            "id": org_id,
            "name": "Expired Test Co",
            "owner_id": uid,
            "subscription_status": "trial",
            "trial_ends_at": past_iso,
            "role_permissions": server_module.DEFAULT_ROLE_PERMISSIONS,
            "scan_count_this_month": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        db.users.insert_one({
            "id": uid,
            "email": email,
            "company_name": "Expired Test Co",
            "is_active": True,
            "organization_id": org_id,
            "role": "owner",
            "subscription_status": "trial",
            "trial_end_date": past_iso,
            "scan_count_this_month": 3,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        token = server_module.create_token(uid)
        return uid, org_id, {"Authorization": f"Bearer {token}"}

    def _cleanup(self, uid, org_id):
        db = server_module.db
        db.users.delete_one({"id": uid})
        db.organizations.delete_one({"id": org_id})

    def test_expired_user_can_call_auth_me(self, client):
        """Regression: expired user MUST see /api/auth/me to render renewal screen."""
        uid, org_id, headers = self._make_expired_user()
        try:
            resp = client.get("/api/auth/me", headers=headers)
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["subscription_status"] == "expired"
        finally:
            self._cleanup(uid, org_id)

    def test_expired_user_can_call_subscription_current(self, client):
        """Regression: /api/subscription/current is the endpoint whose purpose
        is showing expired state — it must not itself return 402."""
        uid, org_id, headers = self._make_expired_user()
        try:
            resp = client.get("/api/subscription/current", headers=headers)
            assert resp.status_code == 200, resp.text
        finally:
            self._cleanup(uid, org_id)

    def test_expired_user_can_call_create_checkout(self, client):
        """Regression: expired user must be able to start Stripe checkout to renew.
        We patch STRIPE_API_KEY to empty so the endpoint returns 500 (Stripe non
        configured) instead of hitting the real Stripe API — the point is that
        auth/subscription-gate lets us pass, i.e. NOT 402."""
        uid, org_id, headers = self._make_expired_user()
        original_key = server_module.STRIPE_API_KEY
        server_module.STRIPE_API_KEY = ""
        try:
            resp = client.post(
                "/api/subscription/create-checkout",
                headers=headers,
                json={"origin_url": "http://localhost:3000"},
            )
            # The gate must NOT block us with 402. Endpoint returns 500 because
            # we unset the Stripe key — that's fine, it means we passed the gate.
            assert resp.status_code != 402, resp.text
            assert resp.status_code == 500, resp.text
        finally:
            server_module.STRIPE_API_KEY = original_key
            self._cleanup(uid, org_id)


class TestScanCountReadFromUser:
    """Fix 3 (regression): _check_and_bill_scan writes to db.users, so /api/auth/me
    must read scan_count_this_month from user_doc, not from org (which stays frozen
    at boot value / 0 after register)."""

    def test_scan_count_reflects_user_doc_not_org(self, client):
        db = server_module.db
        uid = f"test-scan-{uuid.uuid4().hex[:8]}"
        email = f"{uid}@test.local"
        org_id = str(uuid.uuid4())
        future_iso = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
        db.organizations.insert_one({
            "id": org_id,
            "name": "Scan Test Co",
            "owner_id": uid,
            "subscription_status": "trial",
            "trial_ends_at": future_iso,
            "role_permissions": server_module.DEFAULT_ROLE_PERMISSIONS,
            # Org has 0 (frozen at register)
            "scan_count_this_month": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        db.users.insert_one({
            "id": uid,
            "email": email,
            "company_name": "Scan Test Co",
            "is_active": True,
            "organization_id": org_id,
            "role": "owner",
            "subscription_status": "trial",
            "trial_end_date": future_iso,
            # User doc has real value from scan writes
            "scan_count_this_month": 7,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        token = server_module.create_token(uid)
        headers = {"Authorization": f"Bearer {token}"}
        try:
            resp = client.get("/api/auth/me", headers=headers)
            assert resp.status_code == 200, resp.text
            body = resp.json()
            # MUST be 7 (from user_doc) not 0 (from org)
            assert body["scan_count_this_month"] == 7, (
                "Fix 3 regression: /api/auth/me must read scan_count_this_month "
                "from user_doc, not from org (org value is frozen)"
            )
        finally:
            db.users.delete_one({"id": uid})
            db.organizations.delete_one({"id": org_id})


class TestStripeWebhookMirrorsOrg:
    """Fix 2 (regression): Stripe webhook writes subscription_status='active' only
    to db.users. Because _check_subscription_active reads from org, the user
    would stay 'trial' on the org side. Webhook must also mirror onto the org."""

    def test_webhook_updates_both_user_and_org(self, client):
        db = server_module.db
        uid = f"test-webhook-{uuid.uuid4().hex[:8]}"
        email = f"{uid}@test.local"
        org_id = str(uuid.uuid4())
        past_iso = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        session_id = f"cs_test_{uuid.uuid4().hex}"
        tx_id = str(uuid.uuid4())
        db.organizations.insert_one({
            "id": org_id,
            "name": "Webhook Test Co",
            "owner_id": uid,
            "subscription_status": "trial",
            "trial_ends_at": past_iso,
            "role_permissions": server_module.DEFAULT_ROLE_PERMISSIONS,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        db.users.insert_one({
            "id": uid,
            "email": email,
            "company_name": "Webhook Test Co",
            "is_active": True,
            "organization_id": org_id,
            "role": "owner",
            "subscription_status": "trial",
            "trial_end_date": past_iso,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        db.payment_transactions.insert_one({
            "id": tx_id,
            "user_id": uid,
            "session_id": session_id,
            "amount": 15.0,
            "currency": "cad",
            "payment_status": "pending",
            "status": "initiated",
            "metadata": {"plan": "facturepro_monthly", "email": email},
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        # Force json path (STRIPE_WEBHOOK_SECRET vide) + STRIPE_API_KEY set pour
        # passer le gate initial du endpoint
        original_key = server_module.STRIPE_API_KEY
        server_module.STRIPE_API_KEY = "sk_test_dummy"
        original_secret = server_module.STRIPE_WEBHOOK_SECRET
        server_module.STRIPE_WEBHOOK_SECRET = ""
        try:
            payload = {
                "type": "checkout.session.completed",
                "data": {"object": {
                    "id": session_id,
                    "payment_status": "paid",
                    "metadata": {"user_id": uid},
                }},
            }
            resp = client.post("/api/webhook/stripe", json=payload)
            assert resp.status_code == 200, resp.text
            # Both user AND org must be flipped to active
            user_after = db.users.find_one({"id": uid})
            org_after = db.organizations.find_one({"id": org_id})
            assert user_after["subscription_status"] == "active"
            assert org_after["subscription_status"] == "active", (
                "Fix 2 regression: webhook must mirror subscription_status onto "
                "the organization, not only onto db.users"
            )
        finally:
            server_module.STRIPE_API_KEY = original_key
            server_module.STRIPE_WEBHOOK_SECRET = original_secret
            db.users.delete_one({"id": uid})
            db.organizations.delete_one({"id": org_id})
            db.payment_transactions.delete_one({"id": tx_id})


# ─── Task 4 : GET /api/org/me + PUT /api/org/role-permissions ───

class TestOrgMeEndpoint:
    def test_owner_gets_full_context(self, client, owner_headers):
        r = client.get("/api/org/me", headers=owner_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "organization" in body
        assert "current_user" in body
        assert "members" in body
        org = body["organization"]
        assert "id" in org
        assert "name" in org
        assert "role_permissions" in org
        cu = body["current_user"]
        assert cu["role"] == "owner"
        # Owner has all permissions (editable + owner-only)
        for code in ["expenses:read", "settings:manage", "team:manage"]:
            assert code in cu["permissions"]
        assert isinstance(body["members"], list)
        assert any(m["id"] == cu["id"] for m in body["members"])

    def test_unauthenticated_returns_401_or_403(self, client):
        r = client.get("/api/org/me")
        assert r.status_code in (401, 403)


class TestRolePermissionsEndpoint:
    def test_owner_can_edit_matrix(self, client, owner_headers):
        r = client.put("/api/org/role-permissions", headers=owner_headers,
                       json={"role": "accountant",
                             "permissions": ["expenses:read", "invoices:read"]})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["role"] == "accountant"
        assert set(body["permissions"]) == {"expenses:read", "invoices:read"}

        # Verify persistence
        r2 = client.get("/api/org/me", headers=owner_headers)
        matrix = r2.json()["organization"]["role_permissions"]
        assert set(matrix["accountant"]) == {"expenses:read", "invoices:read"}

    def test_cannot_edit_owner_role(self, client, owner_headers):
        r = client.put("/api/org/role-permissions", headers=owner_headers,
                       json={"role": "owner", "permissions": ["expenses:read"]})
        assert r.status_code == 400

    def test_cannot_inject_owner_only_code(self, client, owner_headers):
        r = client.put("/api/org/role-permissions", headers=owner_headers,
                       json={"role": "accountant",
                             "permissions": ["expenses:read", "team:manage"]})
        assert r.status_code == 400
        assert "team:manage" in r.json()["detail"]

    def test_cannot_use_unknown_code(self, client, owner_headers):
        r = client.put("/api/org/role-permissions", headers=owner_headers,
                       json={"role": "accountant",
                             "permissions": ["not:a:real:code"]})
        assert r.status_code == 400

    def test_invalid_role_rejected(self, client, owner_headers):
        r = client.put("/api/org/role-permissions", headers=owner_headers,
                       json={"role": "root", "permissions": []})
        assert r.status_code == 400

    def test_reset_matrix_to_defaults(self, client, owner_headers):
        # Restore default accountant permissions (cleanup for other tests)
        r = client.put("/api/org/role-permissions", headers=owner_headers,
                       json={"role": "accountant",
                             "permissions": list(server_module.PERMISSIONS_EDITABLE)})
        assert r.status_code == 200


# ─── Task 5 : Invitations ───

import re


class TestInvitations:
    @pytest.fixture
    def cleanup_invitations(self, client, owner_headers):
        """Cleanup les invitations pending de tests précédents."""
        r = client.get("/api/org/invitations?status=all", headers=owner_headers)
        for inv in r.json():
            if inv.get("email", "").startswith("invite-test-"):
                client.delete(f"/api/org/invitations/{inv['id']}",
                              headers=owner_headers)
        yield

    def _random_email(self):
        return f"invite-test-{uuid.uuid4().hex[:8]}@example.com"

    def test_create_invitation_happy_path(self, client, owner_headers,
                                           cleanup_invitations, monkeypatch):
        # Mock Resend to avoid real emails
        monkeypatch.setattr(server_module, "_send_invitation_email",
                             lambda *a, **kw: True)
        email = self._random_email()
        r = client.post("/api/org/invitations", headers=owner_headers,
                        json={"email": email, "role": "accountant"})
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["email"] == email.lower()
        assert body["role"] == "accountant"
        assert "id" in body
        assert "expires_at" in body

    def test_list_invitations_pending(self, client, owner_headers,
                                        cleanup_invitations, monkeypatch):
        monkeypatch.setattr(server_module, "_send_invitation_email",
                             lambda *a, **kw: True)
        email = self._random_email()
        client.post("/api/org/invitations", headers=owner_headers,
                    json={"email": email, "role": "viewer"})
        r = client.get("/api/org/invitations", headers=owner_headers)
        assert r.status_code == 200
        pending = [i for i in r.json() if i["email"] == email.lower()]
        assert len(pending) == 1
        assert pending[0]["status"] == "pending"

    def test_invalid_role_rejected(self, client, owner_headers):
        r = client.post("/api/org/invitations", headers=owner_headers,
                        json={"email": "x@y.com", "role": "owner"})
        assert r.status_code == 400

    def test_invalid_email_rejected(self, client, owner_headers):
        r = client.post("/api/org/invitations", headers=owner_headers,
                        json={"email": "not-an-email", "role": "viewer"})
        assert r.status_code == 400

    def test_duplicate_pending_rejected(self, client, owner_headers,
                                          cleanup_invitations, monkeypatch):
        monkeypatch.setattr(server_module, "_send_invitation_email",
                             lambda *a, **kw: True)
        email = self._random_email()
        r1 = client.post("/api/org/invitations", headers=owner_headers,
                         json={"email": email, "role": "accountant"})
        assert r1.status_code == 201
        r2 = client.post("/api/org/invitations", headers=owner_headers,
                         json={"email": email, "role": "accountant"})
        assert r2.status_code == 409

    def test_already_member_rejected(self, client, owner_headers, monkeypatch):
        monkeypatch.setattr(server_module, "_send_invitation_email",
                             lambda *a, **kw: True)
        # gussdub@gmail.com is already owner
        r = client.post("/api/org/invitations", headers=owner_headers,
                        json={"email": "gussdub@gmail.com", "role": "accountant"})
        assert r.status_code == 409

    def test_revoke_pending_invitation(self, client, owner_headers,
                                         cleanup_invitations, monkeypatch):
        monkeypatch.setattr(server_module, "_send_invitation_email",
                             lambda *a, **kw: True)
        email = self._random_email()
        r = client.post("/api/org/invitations", headers=owner_headers,
                        json={"email": email, "role": "viewer"})
        inv_id = r.json()["id"]
        r2 = client.delete(f"/api/org/invitations/{inv_id}", headers=owner_headers)
        assert r2.status_code == 204
        # Verify status changed (not hard-deleted)
        r3 = client.get("/api/org/invitations?status=all", headers=owner_headers)
        found = next((i for i in r3.json() if i["id"] == inv_id), None)
        assert found is not None
        assert found["status"] == "revoked"

    def test_revoke_unknown_invitation_returns_404(self, client, owner_headers):
        r = client.delete(f"/api/org/invitations/{uuid.uuid4()}",
                          headers=owner_headers)
        assert r.status_code == 404


class TestAcceptInvite:
    @pytest.fixture(autouse=True)
    def _reset_rate_limit(self):
        # TestClient always presents the same IP ("testclient"), which trips
        # the 5-req/min guard once a few accept-invite tests fire in sequence.
        # Clear the in-memory bucket before each test so we exercise the real
        # handler, not the 429 path (which has its own coverage upstream).
        server_module._ACCEPT_INVITE_RATE.clear()

    def _create_pending_invitation(self, client, owner_headers, email, role,
                                    monkeypatch):
        monkeypatch.setattr(server_module, "_send_invitation_email",
                             lambda *a, **kw: True)
        r = client.post("/api/org/invitations", headers=owner_headers,
                        json={"email": email, "role": role})
        inv_id = r.json()["id"]
        # Fetch the token directly from DB (test-only)
        inv = server_module.db.invitations.find_one({"id": inv_id})
        return inv_id, inv["token"]

    def _cleanup_user(self, email):
        user = server_module.db.users.find_one({"email": email.lower()})
        if user:
            server_module.db.users.delete_one({"id": user["id"]})
            server_module.db.user_passwords.delete_one({"user_id": user["id"]})

    def test_accept_new_user_happy_path(self, client, owner_headers, monkeypatch):
        email = f"accept-new-{uuid.uuid4().hex[:8]}@example.com"
        _, token = self._create_pending_invitation(
            client, owner_headers, email, "accountant", monkeypatch)
        try:
            r = client.post("/api/auth/accept-invite", json={
                "token": token, "password": "newpass123",
                "pipeda_consent": True,
            })
            assert r.status_code == 200, r.text
            body = r.json()
            assert "access_token" in body
            assert body["user"]["email"] == email.lower()
            # Verify user is in the org with correct role
            user = server_module.db.users.find_one({"email": email.lower()})
            assert user is not None
            assert user["role"] == "accountant"
            assert user.get("organization_id") is not None
            assert user.get("pipeda_consent_at") is not None
        finally:
            self._cleanup_user(email)

    def test_missing_pipeda_consent_rejected(self, client, owner_headers,
                                              monkeypatch):
        email = f"accept-nopipeda-{uuid.uuid4().hex[:8]}@example.com"
        _, token = self._create_pending_invitation(
            client, owner_headers, email, "viewer", monkeypatch)
        try:
            r = client.post("/api/auth/accept-invite", json={
                "token": token, "password": "x123456",
                "pipeda_consent": False,
            })
            assert r.status_code == 400
            assert "CGU" in r.json()["detail"] or "PIPEDA" in r.json()["detail"]
        finally:
            self._cleanup_user(email)

    def test_unknown_token_returns_404(self, client):
        r = client.post("/api/auth/accept-invite", json={
            "token": "unknown-token-xxxxxxxxxxxxxxxx", "password": "x123456",
            "pipeda_consent": True,
        })
        assert r.status_code == 404

    def test_revoked_token_returns_410(self, client, owner_headers, monkeypatch):
        email = f"accept-revoked-{uuid.uuid4().hex[:8]}@example.com"
        inv_id, token = self._create_pending_invitation(
            client, owner_headers, email, "viewer", monkeypatch)
        client.delete(f"/api/org/invitations/{inv_id}", headers=owner_headers)
        r = client.post("/api/auth/accept-invite", json={
            "token": token, "password": "x123456", "pipeda_consent": True,
        })
        assert r.status_code == 410

    def test_expired_token_returns_410(self, client, owner_headers, monkeypatch):
        email = f"accept-expired-{uuid.uuid4().hex[:8]}@example.com"
        inv_id, token = self._create_pending_invitation(
            client, owner_headers, email, "viewer", monkeypatch)
        # Manually expire it
        server_module.db.invitations.update_one(
            {"id": inv_id},
            {"$set": {"expires_at": "2020-01-01T00:00:00+00:00"}})
        r = client.post("/api/auth/accept-invite", json={
            "token": token, "password": "x123456", "pipeda_consent": True,
        })
        assert r.status_code == 410

    def test_already_consumed_token_returns_410(self, client, owner_headers,
                                                  monkeypatch):
        email = f"accept-once-{uuid.uuid4().hex[:8]}@example.com"
        _, token = self._create_pending_invitation(
            client, owner_headers, email, "accountant", monkeypatch)
        try:
            r1 = client.post("/api/auth/accept-invite", json={
                "token": token, "password": "x123456", "pipeda_consent": True,
            })
            assert r1.status_code == 200
            # Try to consume the token again
            r2 = client.post("/api/auth/accept-invite", json={
                "token": token, "password": "x123456", "pipeda_consent": True,
            })
            assert r2.status_code == 410
        finally:
            self._cleanup_user(email)

    def test_existing_user_wrong_password_returns_401(self, client, owner_headers,
                                                       monkeypatch):
        # gussdub already exists but is already in an org — test the 409 first
        # Then test wrong-password on a fresh user
        email = f"existing-wrong-{uuid.uuid4().hex[:8]}@example.com"
        # Create the user manually with a known password
        uid = str(uuid.uuid4())
        server_module.db.users.insert_one({
            "id": uid, "email": email, "company_name": "Standalone",
            "is_active": True, "created_at": datetime.now(timezone.utc).isoformat(),
        })
        server_module.db.user_passwords.insert_one({
            "user_id": uid,
            "hashed_password": server_module.hash_password("correct-pass"),
        })
        try:
            _, token = self._create_pending_invitation(
                client, owner_headers, email, "viewer", monkeypatch)
            r = client.post("/api/auth/accept-invite", json={
                "token": token, "password": "WRONG-pass",
                "pipeda_consent": True,
            })
            assert r.status_code == 401
        finally:
            self._cleanup_user(email)

    def test_existing_user_already_in_org_returns_409(self, client, owner_headers,
                                                        monkeypatch):
        # gussdub is already owner of the current org, we invite them elsewhere
        # But since we're testing single test suite = single org, use a manual setup:
        # Create a second org + user
        email = f"already-org-{uuid.uuid4().hex[:8]}@example.com"
        uid = str(uuid.uuid4())
        other_org_id = str(uuid.uuid4())
        server_module.db.organizations.insert_one({
            "id": other_org_id, "name": "OtherOrg",
            "owner_id": uid, "subscription_status": "trial",
            "role_permissions": server_module.DEFAULT_ROLE_PERMISSIONS,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        server_module.db.users.insert_one({
            "id": uid, "email": email, "is_active": True,
            "organization_id": other_org_id, "role": "owner",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        server_module.db.user_passwords.insert_one({
            "user_id": uid,
            "hashed_password": server_module.hash_password("correct-pass"),
        })
        try:
            _, token = self._create_pending_invitation(
                client, owner_headers, email, "viewer", monkeypatch)
            r = client.post("/api/auth/accept-invite", json={
                "token": token, "password": "correct-pass",
                "pipeda_consent": True,
            })
            assert r.status_code == 409
        finally:
            self._cleanup_user(email)
            server_module.db.organizations.delete_one({"id": other_org_id})

    def test_existing_user_mixed_case_email_reuses_account(
            self, client, owner_headers, monkeypatch):
        # Regression: a legacy standalone user with a mixed-case stored email
        # must be matched by accept-invite (which normalizes the invitation
        # email to lowercase). Without the case-insensitive lookup, the code
        # falls through to the New-user path and creates a duplicate user
        # (email unique index is case-sensitive), orphaning the original
        # user's invoices/clients/expenses.
        suffix = uuid.uuid4().hex[:8]
        stored_email = f"John.{suffix}@Example.COM"
        invite_email = stored_email.lower()
        uid = str(uuid.uuid4())
        server_module.db.users.insert_one({
            "id": uid, "email": stored_email, "company_name": "Legacy",
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        server_module.db.user_passwords.insert_one({
            "user_id": uid,
            "hashed_password": server_module.hash_password("legacy-pass"),
        })
        try:
            _, token = self._create_pending_invitation(
                client, owner_headers, invite_email, "accountant", monkeypatch)
            r = client.post("/api/auth/accept-invite", json={
                "token": token, "password": "legacy-pass",
                "pipeda_consent": True,
            })
            assert r.status_code == 200, r.text
            body = r.json()
            # Existing-user path must reuse the legacy user id (no duplicate).
            assert body["user"]["id"] == uid
            # Confirm exactly one user row exists for that email (any casing).
            matches = list(server_module.db.users.find({
                "email": {"$regex": f"^{invite_email}$", "$options": "i"}
            }))
            assert len(matches) == 1
            assert matches[0]["id"] == uid
            assert matches[0].get("organization_id") is not None
            assert matches[0].get("role") == "accountant"
        finally:
            # Cleanup by id (case-insensitive email cleanup helper would work
            # too, but be explicit).
            server_module.db.users.delete_one({"id": uid})
            server_module.db.user_passwords.delete_one({"user_id": uid})


class TestInvitationPreview:
    def test_preview_valid_token(self, client, owner_headers, monkeypatch):
        monkeypatch.setattr(server_module, "_send_invitation_email",
                             lambda *a, **kw: True)
        email = f"preview-{uuid.uuid4().hex[:8]}@example.com"
        r = client.post("/api/org/invitations", headers=owner_headers,
                        json={"email": email, "role": "accountant"})
        inv_id = r.json()["id"]
        token = server_module.db.invitations.find_one({"id": inv_id})["token"]
        r2 = client.get(f"/api/org/invitations/preview?token={token}")
        assert r2.status_code == 200
        body = r2.json()
        assert body["email"] == email.lower()
        assert body["role"] == "accountant"
        assert "org_name" in body

    def test_preview_unknown_token_returns_404(self, client):
        r = client.get("/api/org/invitations/preview?token=unknown-abcdef")
        assert r.status_code == 404


class TestMembers:
    def _accept_invite_setup(self, client, owner_headers, monkeypatch, role):
        """Helper : crée + accepte une invitation, retourne le user_id créé."""
        monkeypatch.setattr(server_module, "_send_invitation_email",
                             lambda *a, **kw: True)
        email = f"member-{uuid.uuid4().hex[:8]}@example.com"
        r = client.post("/api/org/invitations", headers=owner_headers,
                        json={"email": email, "role": role})
        inv_id = r.json()["id"]
        token = server_module.db.invitations.find_one({"id": inv_id})["token"]
        client.post("/api/auth/accept-invite", json={
            "token": token, "password": "memberpass123",
            "pipeda_consent": True,
        })
        user = server_module.db.users.find_one({"email": email})
        return user["id"], email

    def _cleanup_user(self, email):
        user = server_module.db.users.find_one({"email": email.lower()})
        if user:
            server_module.db.users.delete_one({"id": user["id"]})
            server_module.db.user_passwords.delete_one({"user_id": user["id"]})

    def test_change_role_happy_path(self, client, owner_headers, monkeypatch):
        uid, email = self._accept_invite_setup(client, owner_headers,
                                                 monkeypatch, "accountant")
        try:
            r = client.put(f"/api/org/members/{uid}/role", headers=owner_headers,
                           json={"role": "viewer"})
            assert r.status_code == 200, r.text
            assert r.json()["role"] == "viewer"
            assert server_module.db.users.find_one({"id": uid})["role"] == "viewer"
        finally:
            self._cleanup_user(email)

    def test_cannot_change_owner_role(self, client, owner_headers):
        # gussdub is owner
        owner = server_module.db.users.find_one({"email": "gussdub@gmail.com"})
        r = client.put(f"/api/org/members/{owner['id']}/role",
                       headers=owner_headers, json={"role": "viewer"})
        assert r.status_code == 400

    def test_change_role_invalid_role_rejected(self, client, owner_headers,
                                                 monkeypatch):
        uid, email = self._accept_invite_setup(client, owner_headers,
                                                 monkeypatch, "accountant")
        try:
            r = client.put(f"/api/org/members/{uid}/role", headers=owner_headers,
                           json={"role": "owner"})
            assert r.status_code == 400
        finally:
            self._cleanup_user(email)

    def test_change_role_unknown_user_returns_404(self, client, owner_headers):
        r = client.put(f"/api/org/members/{uuid.uuid4()}/role",
                       headers=owner_headers, json={"role": "viewer"})
        assert r.status_code == 404

    def test_remove_member_happy_path(self, client, owner_headers, monkeypatch):
        uid, email = self._accept_invite_setup(client, owner_headers,
                                                 monkeypatch, "viewer")
        try:
            r = client.delete(f"/api/org/members/{uid}", headers=owner_headers)
            assert r.status_code == 204
            user = server_module.db.users.find_one({"id": uid})
            assert user.get("organization_id") is None
            assert user.get("role") is None
        finally:
            self._cleanup_user(email)

    def test_cannot_remove_owner(self, client, owner_headers):
        owner = server_module.db.users.find_one({"email": "gussdub@gmail.com"})
        r = client.delete(f"/api/org/members/{owner['id']}", headers=owner_headers)
        assert r.status_code == 400

    def test_cannot_remove_self_if_owner(self, client, owner_headers):
        # gussdub is BOTH owner AND the current_user — 400
        owner = server_module.db.users.find_one({"email": "gussdub@gmail.com"})
        r = client.delete(f"/api/org/members/{owner['id']}", headers=owner_headers)
        assert r.status_code == 400
