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


class TestScanCountReadFromOrg:
    """Task 8: _check_and_bill_scan writes to db.organizations (source of truth
    multi-tenant), so /api/auth/me must read scan_count_this_month from the
    org, not from user_doc. Falls back to user_doc if the org has no value
    (pre-migration edge case)."""

    def test_scan_count_reflects_org_not_user_doc(self, client):
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
            # Org is now the source of truth (Task 8)
            "scan_count_this_month": 12,
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
            # Stale user_doc value should be ignored
            "scan_count_this_month": 7,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        token = server_module.create_token(uid)
        headers = {"Authorization": f"Bearer {token}"}
        try:
            resp = client.get("/api/auth/me", headers=headers)
            assert resp.status_code == 200, resp.text
            body = resp.json()
            # MUST be 12 (from org) not 7 (stale user_doc)
            assert body["scan_count_this_month"] == 12, (
                "Task 8: /api/auth/me must read scan_count_this_month from "
                "the organization (source of truth), not user_doc"
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


# ─── Task 8 : Move Stripe subscription + scan quota to org ───

class TestSubscriptionOnOrg:
    """Task 8: subscription_status / trial_ends_at / stripe_customer_id and
    scan_count_this_month are now stored on the organization (source of vérité
    multi-tenant). /api/org/me exposes them; _check_and_bill_scan writes to
    db.organizations; the Stripe webhook routes to the correct org via
    metadata.organization_id."""

    def test_org_me_exposes_subscription(self, client, owner_headers):
        r = client.get("/api/org/me", headers=owner_headers)
        assert r.status_code == 200, r.text
        org = r.json()["organization"]
        assert "subscription_status" in org
        assert "trial_ends_at" in org

    def test_scan_quota_shared_across_org(self, client, owner_headers):
        # Owner scan_count is stored on org, not user (shared across members).
        r = client.get("/api/org/me", headers=owner_headers)
        assert r.status_code == 200, r.text
        org = r.json()["organization"]
        assert "scan_count_this_month" in org

    def test_check_and_bill_scan_writes_to_org(self):
        """Direct unit-ish call: _check_and_bill_scan must operate on
        db.organizations, not db.users."""
        db = server_module.db
        uid = f"test-cbs-{uuid.uuid4().hex[:8]}"
        org_id = str(uuid.uuid4())
        db.organizations.insert_one({
            "id": org_id,
            "name": "CBS Test Co",
            "owner_id": uid,
            "subscription_status": "trial",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        db.users.insert_one({
            "id": uid,
            "email": f"{uid}@test.local",
            "company_name": "CBS Test Co",
            "is_active": True,
            "organization_id": org_id,
            "role": "owner",
            "scan_count_this_month": 999,  # sentinel — must NOT be touched
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        try:
            n1 = server_module._check_and_bill_scan(org_id)
            n2 = server_module._check_and_bill_scan(org_id)
            org_after = db.organizations.find_one({"id": org_id})
            user_after = db.users.find_one({"id": uid})
            assert n1 == 1 and n2 == 2
            assert org_after["scan_count_this_month"] == 2
            # User doc sentinel is untouched — writes go to org only
            assert user_after["scan_count_this_month"] == 999
        finally:
            db.users.delete_one({"id": uid})
            db.organizations.delete_one({"id": org_id})

    def test_webhook_routes_by_organization_id_in_metadata(self, client):
        """Webhook uses metadata.organization_id to route paid status to the
        correct org — not the owner_id fallback (which breaks for multi-user
        orgs where the paying user isn't the owner)."""
        db = server_module.db
        uid = f"test-wh-org-{uuid.uuid4().hex[:8]}"
        org_id = str(uuid.uuid4())
        past_iso = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        session_id = f"cs_test_{uuid.uuid4().hex}"
        tx_id = str(uuid.uuid4())
        db.organizations.insert_one({
            "id": org_id,
            "name": "Webhook Metadata Test Co",
            # Deliberately different owner_id from uid to prove routing goes
            # by metadata.organization_id, not owner_id lookup.
            "owner_id": f"other-owner-{uuid.uuid4().hex[:6]}",
            "subscription_status": "trial",
            "trial_ends_at": past_iso,
            "role_permissions": server_module.DEFAULT_ROLE_PERMISSIONS,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        db.users.insert_one({
            "id": uid,
            "email": f"{uid}@test.local",
            "company_name": "Webhook Metadata Test Co",
            "is_active": True,
            "organization_id": org_id,
            "role": "accountant",
            "subscription_status": "trial",
            "trial_end_date": past_iso,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        db.payment_transactions.insert_one({
            "id": tx_id,
            "user_id": uid,
            "organization_id": org_id,
            "session_id": session_id,
            "amount": 15.0,
            "currency": "cad",
            "payment_status": "pending",
            "status": "initiated",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
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
                    "customer": "cus_test_dummy_123",
                    "metadata": {"user_id": uid, "organization_id": org_id},
                }},
            }
            resp = client.post("/api/webhook/stripe", json=payload)
            assert resp.status_code == 200, resp.text
            org_after = db.organizations.find_one({"id": org_id})
            assert org_after["subscription_status"] == "active"
            # stripe_customer_id persisted for future customer portal usage
            assert org_after.get("stripe_customer_id") == "cus_test_dummy_123"
        finally:
            server_module.STRIPE_API_KEY = original_key
            server_module.STRIPE_WEBHOOK_SECRET = original_secret
            db.users.delete_one({"id": uid})
            db.organizations.delete_one({"id": org_id})
            db.payment_transactions.delete_one({"id": tx_id})


# ─── Task 10 FIX-PASS : Multi-member internal-helper regression tests ──────
#
# These tests specifically prove that the four internal helpers (_apply_match,
# _release_bank_transaction, _auto_match_transactions, _build_tax_registrations)
# use an ORG-SCOPED filter instead of `{"user_id": current_user.id}`. Before
# the fix, a non-owner accountant would :
#   (1) get an EMPTY tax_registrations snapshot on invoices/quotes they create,
#   (2) get 404 when matching a bank tx to an owner-created invoice,
#   (3) leave orphaned matched bank_transactions when deleting owner docs,
#   (4) get zero auto-matches on CSV import.
# All four scenarios below would have caught the reviewer-identified bugs.

class TestTask10MultiMemberHelpers:
    """FIX-PASS T10: prove internal helpers scope by org, not user_id."""

    def _make_accountant_in_gussdub_org(self):
        """Create an accountant member inside gussdub's org, return token+id.

        Returns (uid, email, headers). Cleanup by caller via _cleanup_user."""
        db = server_module.db
        owner = db.users.find_one({"email": "gussdub@gmail.com"})
        org_id = owner["organization_id"]
        uid = f"test-t10-acc-{uuid.uuid4().hex[:8]}"
        email = f"{uid}@test.local"
        db.users.insert_one({
            "id": uid,
            "email": email,
            "company_name": owner.get("company_name", ""),
            "is_active": True,
            "organization_id": org_id,
            "role": "accountant",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        token = server_module.create_token(uid)
        return uid, email, {"Authorization": f"Bearer {token}"}

    def _cleanup_user(self, uid):
        server_module.db.users.delete_one({"id": uid})
        server_module.db.user_passwords.delete_one({"user_id": uid})

    # ── Scenario 1 : tax_registrations snapshot uses OWNER's company_settings ──
    def test_accountant_creating_invoice_gets_owner_tax_registrations_snapshot(
        self, client, owner_headers
    ):
        """T10 FIX-PASS #4: _build_tax_registrations must use org scope so that
        a non-owner member's invoice inherits the OWNER's company_settings +
        client tax numbers, not an empty snapshot."""
        db = server_module.db
        owner = db.users.find_one({"email": "gussdub@gmail.com"})
        org_id = owner["organization_id"]

        # Seed / upsert company_settings with a distinctive BN so we can prove
        # snapshot came from the org, not the accountant's user_id.
        settings_marker = f"111111{uuid.uuid4().hex[:3].upper()}"[:9]
        original_settings = db.company_settings.find_one({"organization_id": org_id})
        settings_id = None
        if not original_settings:
            settings_id = str(uuid.uuid4())
            db.company_settings.insert_one({
                "id": settings_id,
                "organization_id": org_id,
                "user_id": owner["id"],
                "bn_number": settings_marker,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        else:
            db.company_settings.update_one(
                {"id": original_settings["id"]},
                {"$set": {"bn_number": settings_marker}},
            )

        uid, email, acc_headers = self._make_accountant_in_gussdub_org()
        created_client_id = None
        created_invoice_id = None
        try:
            # Owner creates a client with a distinctive GST number
            client_gst = f"222222{uuid.uuid4().hex[:3].upper()}"[:9] + "RT0001"
            r = client.post(
                "/api/clients",
                headers=owner_headers,
                json={"name": "T10 Client", "email": "t10@example.com",
                      "gst_number": client_gst},
            )
            assert r.status_code == 200, r.text
            created_client_id = r.json()["id"]

            # Accountant (non-owner) creates an invoice for the owner's client.
            r = client.post(
                "/api/invoices",
                headers=acc_headers,
                json={"client_id": created_client_id,
                      "items": [{"description": "Test", "quantity": 1,
                                 "unit_price": 100.0}]},
            )
            assert r.status_code == 200, r.text
            body = r.json()
            created_invoice_id = body["id"]

            regs = body.get("tax_registrations") or {}
            company = regs.get("company") or {}
            client_regs = regs.get("client") or {}

            # THE bug: pre-fix, both company & client would be EMPTY because
            # _build_tax_registrations filtered by accountant's user_id.
            assert company.get("bn") == settings_marker, (
                "T10 FIX-PASS #4: accountant-created invoice must snapshot the "
                "OWNER's company_settings.bn_number (org scope). "
                f"Got: {company!r}"
            )
            assert client_regs.get("gst") == client_gst, (
                "T10 FIX-PASS #4: accountant-created invoice must snapshot the "
                "OWNER's client tax fields (org scope). "
                f"Got: {client_regs!r}"
            )
        finally:
            if created_invoice_id:
                db.invoices.delete_one({"id": created_invoice_id})
            if created_client_id:
                db.clients.delete_one({"id": created_client_id})
            if settings_id:
                db.company_settings.delete_one({"id": settings_id})
            self._cleanup_user(uid)

    # ── Scenario 2 : accountant matches bank tx to owner-created invoice ──
    def test_accountant_can_match_bank_tx_to_owner_created_invoice(
        self, client, owner_headers
    ):
        """T10 FIX-PASS #1: _apply_match must use org scope so an accountant
        can match a bank_transaction to an invoice created by the owner."""
        db = server_module.db
        owner = db.users.find_one({"email": "gussdub@gmail.com"})
        org_id = owner["organization_id"]

        uid, email, acc_headers = self._make_accountant_in_gussdub_org()
        created_invoice_id = None
        tx_id = str(uuid.uuid4())
        import_id = str(uuid.uuid4())
        try:
            # OWNER creates an unpaid invoice.
            r = client.post(
                "/api/invoices",
                headers=owner_headers,
                json={"items": [{"description": "T10", "quantity": 1,
                                 "unit_price": 100.0}]},
            )
            assert r.status_code == 200, r.text
            inv = r.json()
            created_invoice_id = inv["id"]
            # Bump to `sent` so the invoice is matchable.
            client.put(
                f"/api/invoices/{created_invoice_id}/status",
                headers=owner_headers,
                json={"status": "sent"},
            )
            total = float(inv["total"])

            # Seed a bank_transaction (org-scoped) matching that invoice amount.
            now = datetime.now(timezone.utc).isoformat()
            db.bank_imports.insert_one({
                "id": import_id,
                "organization_id": org_id,
                "user_id": owner["id"],
                "file_hash": f"h-{uuid.uuid4().hex}",
                "imported_at": now,
                "closed_at": None,
            })
            db.bank_transactions.insert_one({
                "id": tx_id,
                "organization_id": org_id,
                # Note: created_by_user_id = owner, not accountant.
                "created_by_user_id": owner["id"],
                "user_id": owner["id"],
                "import_id": import_id,
                "date": now[:10],
                "description": "T10 payment",
                "amount_cad": total,
                "parse_error": False,
                "status": "unmatched",
                "match_kind": None,
                "match_id": None,
                "invoice_id": None,
                "matched_at": None,
            })

            # ACCOUNTANT (non-owner) matches the tx to the owner's invoice.
            r = client.post(
                f"/api/bank/transactions/{tx_id}/match",
                headers=acc_headers,
                json={"kind": "invoice_payment", "target_id": created_invoice_id},
            )
            # Pre-fix: 404 (invoice lookup filtered by accountant's user_id).
            assert r.status_code == 200, (
                f"T10 FIX-PASS #1: accountant must be able to match a bank tx "
                f"to an owner-created invoice. Got {r.status_code}: {r.text}"
            )
            body = r.json()
            assert body["status"] == "matched"
            assert body["match_kind"] == "invoice_payment"

            # Confirm payment appears on the owner's invoice.
            fresh = db.invoices.find_one({"id": created_invoice_id})
            assert any(p.get("bank_transaction_id") == tx_id
                       for p in (fresh.get("payments") or []))
        finally:
            db.bank_transactions.delete_one({"id": tx_id})
            db.bank_imports.delete_one({"id": import_id})
            if created_invoice_id:
                db.invoices.delete_one({"id": created_invoice_id})
            self._cleanup_user(uid)

    # ── Scenario 3 : accountant deletes owner-created invoice → tx released ──
    def test_accountant_deleting_invoice_releases_matched_bank_transaction(
        self, client, owner_headers
    ):
        """T10 FIX-PASS #2: _release_bank_transaction must use org scope so
        cascades from non-owner DELETE reset the bank_transaction. Otherwise
        the tx stays `status=matched` with a dangling invoice_id — an
        orphaned reference that violates the invariant."""
        db = server_module.db
        owner = db.users.find_one({"email": "gussdub@gmail.com"})
        org_id = owner["organization_id"]

        uid, email, acc_headers = self._make_accountant_in_gussdub_org()
        created_invoice_id = None
        tx_id = str(uuid.uuid4())
        import_id = str(uuid.uuid4())
        try:
            # OWNER creates invoice + adds payment referencing a bank tx.
            r = client.post(
                "/api/invoices",
                headers=owner_headers,
                json={"items": [{"description": "T10", "quantity": 1,
                                 "unit_price": 50.0}]},
            )
            assert r.status_code == 200, r.text
            inv = r.json()
            created_invoice_id = inv["id"]
            client.put(
                f"/api/invoices/{created_invoice_id}/status",
                headers=owner_headers,
                json={"status": "sent"},
            )

            now = datetime.now(timezone.utc).isoformat()
            db.bank_imports.insert_one({
                "id": import_id,
                "organization_id": org_id,
                "user_id": owner["id"],
                "file_hash": f"h-{uuid.uuid4().hex}",
                "imported_at": now,
                "closed_at": None,
            })
            db.bank_transactions.insert_one({
                "id": tx_id,
                "organization_id": org_id,
                "created_by_user_id": owner["id"],
                "user_id": owner["id"],
                "import_id": import_id,
                "date": now[:10],
                "description": "T10 tx",
                "amount_cad": float(inv["total"]),
                "parse_error": False,
                "status": "matched",
                "match_kind": "invoice_payment",
                "match_id": "pay-abc",
                "invoice_id": created_invoice_id,
                "matched_at": now,
            })
            # Add a payment referencing the bank tx directly on the invoice.
            db.invoices.update_one(
                {"id": created_invoice_id},
                {"$push": {"payments": {
                    "id": "pay-abc",
                    "amount_cad": float(inv["total"]),
                    "method": "transfer",
                    "date": now[:10],
                    "reference": "T10",
                    "bank_transaction_id": tx_id,
                    "created_at": now,
                }}},
            )

            # ACCOUNTANT (non-owner) DELETES the owner-created invoice.
            r = client.delete(
                f"/api/invoices/{created_invoice_id}",
                headers=acc_headers,
            )
            assert r.status_code == 200, r.text
            created_invoice_id = None  # deleted

            # Bank tx must be released back to unmatched — no orphan.
            tx_after = db.bank_transactions.find_one({"id": tx_id})
            assert tx_after["status"] == "unmatched", (
                "T10 FIX-PASS #2: cascade from non-owner DELETE must release "
                "the bank_transaction (org scope). "
                f"Actual status: {tx_after['status']!r}"
            )
            assert tx_after["match_kind"] is None
            assert tx_after["match_id"] is None
            assert tx_after["invoice_id"] is None
        finally:
            db.bank_transactions.delete_one({"id": tx_id})
            db.bank_imports.delete_one({"id": import_id})
            if created_invoice_id:
                db.invoices.delete_one({"id": created_invoice_id})
            self._cleanup_user(uid)

    # ── Scenario 4 : accountant CSV import auto-matches owner's invoices ──
    def test_accountant_csv_import_auto_matches_owner_created_invoice(
        self, client, owner_headers
    ):
        """T10 FIX-PASS #3: _auto_match_transactions must use org scope so
        an accountant importing a CSV can auto-match against the OWNER's
        open invoices."""
        db = server_module.db
        owner = db.users.find_one({"email": "gussdub@gmail.com"})
        org_id = owner["organization_id"]

        uid, email, acc_headers = self._make_accountant_in_gussdub_org()
        created_invoice_id = None
        created_client_id = None
        try:
            # OWNER creates a distinctively-named client (auto-match score +1
            # if the client name appears in the tx description).
            client_name = f"T10AutoClient{uuid.uuid4().hex[:6]}"
            r = client.post(
                "/api/clients",
                headers=owner_headers,
                json={"name": client_name},
            )
            assert r.status_code == 200, r.text
            created_client_id = r.json()["id"]

            # OWNER creates + sends an invoice; capture actual TOTAL (incl. tax).
            r = client.post(
                "/api/invoices",
                headers=owner_headers,
                json={"client_id": created_client_id,
                      "province": "AB",
                      "items": [{"description": "T10auto", "quantity": 1,
                                 "unit_price": 200.0}]},
            )
            assert r.status_code == 200, r.text
            inv = r.json()
            created_invoice_id = inv["id"]
            client.put(
                f"/api/invoices/{created_invoice_id}/status",
                headers=owner_headers,
                json={"status": "sent"},
            )
            amount = float(inv["total"])
            issue_date = (inv.get("issue_date") or "")[:10]
            assert issue_date

            # ACCOUNTANT imports a CSV with a single credit matching the invoice.
            # Description contains client name → score 3 → auto-match.
            # unique payload → unique file_hash → skip duplicate-detect (409)
            csv_body = (
                "Date,Description,Amount\n"
                f"{issue_date},Payment from {client_name} {uuid.uuid4().hex},{amount}\n"
            )
            mapping = {
                "delimiter": ",",
                "has_header": True,
                "date_column": 0,
                "description_column": 1,
                "date_format": "YYYY-MM-DD",
                "amount_mode": "single",
                "amount_column": 2,
                "sign_convention": "positive_is_credit",
            }
            import json as _json
            files = {"file": ("t10.csv", csv_body.encode(), "text/csv")}
            data = {"mapping": _json.dumps(mapping), "bank_label": "T10 Bank"}
            r = client.post("/api/bank/imports", headers=acc_headers,
                            files=files, data=data)
            assert r.status_code == 201, r.text
            body = r.json()
            # Pre-fix: auto_matched = 0 (open_invoices lookup filtered by
            # accountant's user_id, so nothing found).
            assert body["auto_matched"] == 1, (
                "T10 FIX-PASS #3: accountant CSV import must auto-match "
                "against OWNER's open invoices (org scope). "
                f"Got auto_matched={body['auto_matched']}, transactions="
                f"{body.get('transactions')!r}"
            )
            # Cleanup: delete the import + txs.
            import_id = body["import"]["id"]
            db.bank_transactions.delete_many({"import_id": import_id})
            db.bank_imports.delete_one({"id": import_id})
        finally:
            if created_invoice_id:
                db.invoices.delete_one({"id": created_invoice_id})
            if created_client_id:
                db.clients.delete_one({"id": created_client_id})
            self._cleanup_user(uid)
