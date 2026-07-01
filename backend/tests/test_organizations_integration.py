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
