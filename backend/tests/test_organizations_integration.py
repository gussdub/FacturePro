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
