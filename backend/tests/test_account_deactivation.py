"""Tests — désactivation / réactivation de compte membre (backlog P1 Loi 25)."""
import os
import sys
import uuid as _uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test")
os.environ.setdefault("DB_NAME", "facturepro")

import pyotp  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from backend import server  # noqa: E402
from backend.server import app, db  # noqa: E402

client = TestClient(app)


@pytest.fixture
def org():
    email = f"own-{_uuid.uuid4().hex[:8]}@ex.com"
    r = client.post("/api/auth/register",
                    json={"email": email, "password": "ownpass12345", "company_name": "Deact Test"})
    assert r.status_code == 200, r.text
    owner_uid = r.json()["user"]["id"]
    org_id = (db.users.find_one({"id": owner_uid}) or {}).get("organization_id")
    owner_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    # membre accountant avec mot de passe
    m_email = f"mem-{_uuid.uuid4().hex[:8]}@ex.com"
    m_pw, m_uid = "memberpass123", str(_uuid.uuid4())
    db.users.insert_one({"id": m_uid, "email": m_email.lower(), "organization_id": org_id,
                         "role": "accountant", "is_active": True})
    db.user_passwords.insert_one({"user_id": m_uid, "hashed_password": server.hash_password(m_pw)})
    yield {"owner_uid": owner_uid, "owner_headers": owner_headers, "org_id": org_id,
           "m_uid": m_uid, "m_email": m_email, "m_pw": m_pw}
    db.users.delete_many({"organization_id": org_id})
    db.user_passwords.delete_one({"user_id": m_uid})
    db.user_passwords.delete_one({"user_id": owner_uid})
    db.organizations.delete_one({"id": org_id})
    db.audit_logs.delete_many({"organization_id": org_id})
    db.login_attempts.delete_one({"_id": server._login_attempt_key(m_email, "testclient")})


def _member_token(m_email, m_pw):
    r = client.post("/api/auth/login", json={"email": m_email, "password": m_pw})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


class TestDeactivation:
    def test_deactivate_sets_flag_and_revokes_and_blocks_login(self, org):
        tok = _member_token(org["m_email"], org["m_pw"])
        # le membre a accès avant
        assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"}).status_code == 200
        r = client.post(f"/api/org/members/{org['m_uid']}/deactivate", headers=org["owner_headers"])
        assert r.status_code == 204, r.text
        assert db.users.find_one({"id": org["m_uid"]})["is_active"] is False
        # jeton existant révoqué (session coupée)
        assert client.get("/api/auth/me",
                          headers={"Authorization": f"Bearer {tok}"}).status_code == 401
        # login refusé (403 compte désactivé)
        lr = client.post("/api/auth/login", json={"email": org["m_email"], "password": org["m_pw"]})
        assert lr.status_code == 403

    def test_reactivate_restores_login(self, org):
        client.post(f"/api/org/members/{org['m_uid']}/deactivate", headers=org["owner_headers"])
        r = client.post(f"/api/org/members/{org['m_uid']}/reactivate", headers=org["owner_headers"])
        assert r.status_code == 204, r.text
        assert db.users.find_one({"id": org["m_uid"]})["is_active"] is True
        # login de nouveau possible
        assert _member_token(org["m_email"], org["m_pw"])

    def test_deactivated_member_visible_in_roster(self, org):
        client.post(f"/api/org/members/{org['m_uid']}/deactivate", headers=org["owner_headers"])
        me = client.get("/api/org/me", headers=org["owner_headers"]).json()
        row = [m for m in me["members"] if m["id"] == org["m_uid"]]
        assert row and row[0]["is_active"] is False

    def test_cannot_deactivate_owner(self, org):
        r = client.post(f"/api/org/members/{org['owner_uid']}/deactivate", headers=org["owner_headers"])
        assert r.status_code == 400

    def test_cannot_deactivate_self(self, org):
        # le propriétaire est aussi "soi-même" ici ; garde explicite anti-lockout
        r = client.post(f"/api/org/members/{org['owner_uid']}/deactivate", headers=org["owner_headers"])
        assert r.status_code == 400

    def test_non_owner_forbidden(self, org):
        tok = _member_token(org["m_email"], org["m_pw"])
        # un accountant n'a pas team:manage → 403
        r = client.post(f"/api/org/members/{org['owner_uid']}/deactivate",
                        headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 403

    def test_unknown_member_404(self, org):
        r = client.post(f"/api/org/members/{_uuid.uuid4()}/deactivate", headers=org["owner_headers"])
        assert r.status_code == 404

    def test_mfa_challenge_rejected_when_deactivated(self, org):
        # Le 2e facteur ne doit pas contourner la désactivation (chemin séparé du login).
        secret = pyotp.random_base32()
        db.user_mfa.insert_one({"user_id": org["m_uid"], "secret": secret,
                                "enabled": True, "backup_codes": []})
        try:
            login = client.post("/api/auth/login",
                                json={"email": org["m_email"], "password": org["m_pw"]}).json()
            assert login.get("mfa_required") and login.get("mfa_token")
            # désactivation APRÈS l'obtention du jeton pré-auth
            client.post(f"/api/org/members/{org['m_uid']}/deactivate", headers=org["owner_headers"])
            r = client.post("/api/auth/mfa/challenge",
                            json={"mfa_token": login["mfa_token"], "code": pyotp.TOTP(secret).now()})
            assert r.status_code == 403, r.text
        finally:
            db.user_mfa.delete_one({"user_id": org["m_uid"]})

    def test_deactivate_idempotent(self, org):
        client.post(f"/api/org/members/{org['m_uid']}/deactivate", headers=org["owner_headers"])
        r = client.post(f"/api/org/members/{org['m_uid']}/deactivate", headers=org["owner_headers"])
        assert r.status_code == 204
        assert db.users.find_one({"id": org["m_uid"]})["is_active"] is False

    def test_cannot_transfer_ownership_to_deactivated_member(self, org):
        # BLOCKING (revue) : jamais de propriétaire is_active=False. Le transfert vers un membre
        # désactivé est refusé, et le propriétaire ne change pas.
        client.post(f"/api/org/members/{org['m_uid']}/deactivate", headers=org["owner_headers"])
        r = client.post("/api/org/transfer-ownership", headers=org["owner_headers"],
                        json={"new_owner_user_id": org["m_uid"]})
        assert r.status_code == 400, r.text
        assert db.organizations.find_one({"id": org["org_id"]})["owner_id"] == org["owner_uid"]

    def test_accept_invite_reactivates_removed_member(self, org):
        # IMPORTANT (revue) : accepter une invitation réactive un compte désactivé (pas de zombie).
        db.users.update_one({"id": org["m_uid"]}, {"$set": {"is_active": False}})
        db.users.update_one({"id": org["m_uid"]}, {"$unset": {"organization_id": "", "role": ""}})
        token = "inv_" + _uuid.uuid4().hex
        db.invitations.insert_one({
            "id": str(_uuid.uuid4()), "organization_id": org["org_id"], "email": org["m_email"].lower(),
            "role": "viewer", "token": token, "status": "pending",
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()})
        try:
            r = client.post("/api/auth/accept-invite",
                            json={"token": token, "password": org["m_pw"], "pipeda_consent": True})
            assert r.status_code == 200, r.text
            u = db.users.find_one({"id": org["m_uid"]})
            assert u["is_active"] is True and u.get("organization_id") == org["org_id"]
        finally:
            db.invitations.delete_many({"organization_id": org["org_id"]})
