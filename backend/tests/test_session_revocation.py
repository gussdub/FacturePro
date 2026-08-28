"""Tests — révocation de session via token_version (backlog P1 audit Loi 25)."""
import os
import sys
import uuid as _uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test")
os.environ.setdefault("DB_NAME", "facturepro")

import jwt as _jwt  # noqa: E402
import pyotp  # noqa: E402
import pytest  # noqa: E402
from datetime import datetime, timezone, timedelta  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from backend import server  # noqa: E402
from backend.server import app, db  # noqa: E402

client = TestClient(app)


@pytest.fixture
def account():
    email = f"rev-{_uuid.uuid4().hex[:8]}@ex.com"
    pw = "revpass12345"
    r = client.post("/api/auth/register",
                    json={"email": email, "password": pw, "company_name": "Rev Test"})
    assert r.status_code == 200, r.text
    uid = r.json()["user"]["id"]
    org_id = (db.users.find_one({"id": uid}) or {}).get("organization_id")
    yield {"id": uid, "email": email, "password": pw, "org_id": org_id,
           "token": r.json()["access_token"]}
    db.user_mfa.delete_one({"user_id": uid})
    db.user_passwords.delete_one({"user_id": uid})
    db.users.delete_one({"id": uid})
    if org_id:
        db.organizations.delete_one({"id": org_id})


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


class TestCoreMechanism:
    def test_bump_invalidates_old_token_both_resolvers(self, account):
        tok = account["token"]
        assert client.get("/api/auth/me", headers=_h(tok)).status_code == 200
        assert client.get("/api/clients", headers=_h(tok)).status_code == 200
        server._revoke_user_sessions(account["id"])   # +1 token_version
        # get_current_user (/, /me) ET get_current_user_with_access (/clients) rejettent
        assert client.get("/api/auth/me", headers=_h(tok)).status_code == 401
        assert client.get("/api/clients", headers=_h(tok)).status_code == 401

    def test_token_without_tv_claim_still_valid(self, account):
        # Graceful : un vieux JWT (émis avant la feature, sans claim tv) reste valide tant qu'aucune
        # révocation n'a eu lieu (tv absent = 0 == token_version absent = 0). Pas de logout de masse.
        legacy = _jwt.encode({"sub": account["id"],
                              "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                             server.JWT_SECRET, algorithm="HS256")
        assert client.get("/api/auth/me", headers=_h(legacy)).status_code == 200
        # après une révocation, même le vieux jeton sans tv est invalidé
        server._revoke_user_sessions(account["id"])
        assert client.get("/api/auth/me", headers=_h(legacy)).status_code == 401

    def test_fresh_token_after_bump_works(self, account):
        server._revoke_user_sessions(account["id"])
        fresh = server.create_token(account["id"])   # lit la nouvelle version
        assert client.get("/api/auth/me", headers=_h(fresh)).status_code == 200


class TestLogoutOthers:
    def test_reissues_current_and_kills_old(self, account):
        old = account["token"]
        r = client.post("/api/auth/logout-others", headers=_h(old))
        assert r.status_code == 200
        fresh = r.json()["access_token"]
        assert fresh and fresh != old
        assert client.get("/api/auth/me", headers=_h(fresh)).status_code == 200   # courante OK
        assert client.get("/api/auth/me", headers=_h(old)).status_code == 401     # ancienne tuée


class TestMfaTriggers:
    def _enable(self, acct):
        r = client.post("/api/auth/mfa/setup", headers=_h(acct["token"]))
        secret = r.json()["secret"]
        code = pyotp.TOTP(secret).now()
        r2 = client.post("/api/auth/mfa/enable", headers=_h(acct["token"]), json={"code": code})
        assert r2.status_code == 200, r2.text
        return secret, r2.json()

    def test_enable_does_not_revoke_by_itself(self, account):
        # L'activation N'AUTO-RÉVOQUE PAS (le front révoque les autres au clic « J'ai noté mes codes »
        # via /logout-others) → pendant l'affichage des codes de secours, le jeton courant reste
        # valide (pas de 401 qui ferait perdre les codes). Pas d'access_token dans la réponse enable.
        old = account["token"]
        _secret, body = self._enable(account)
        assert "access_token" not in body
        assert client.get("/api/auth/me", headers=_h(old)).status_code == 200   # courant toujours valide

    def test_disable_reissues_and_revokes_old(self, account):
        secret, _enable_body = self._enable(account)
        cur = account["token"]                       # toujours valide après enable
        r = client.post("/api/auth/mfa/disable", headers=_h(cur),
                        json={"code": pyotp.TOTP(secret).now()})
        assert r.status_code == 200, r.text
        fresh = r.json().get("access_token")
        assert fresh and fresh != cur
        assert client.get("/api/auth/me", headers=_h(cur)).status_code == 401
        assert client.get("/api/auth/me", headers=_h(fresh)).status_code == 200


class TestAdminTriggers:
    def _member(self, org_id):
        m_email = f"m-{_uuid.uuid4().hex[:8]}@ex.com"
        m_pw, m_uid = "memberpass123", str(_uuid.uuid4())
        db.users.insert_one({"id": m_uid, "email": m_email.lower(), "organization_id": org_id,
                             "role": "accountant", "is_active": True})
        db.user_passwords.insert_one({"user_id": m_uid, "hashed_password": server.hash_password(m_pw)})
        tok = client.post("/api/auth/login", json={"email": m_email, "password": m_pw}).json()["access_token"]
        return m_uid, m_email, tok

    def test_remove_member_revokes_their_sessions(self, account):
        m_uid, m_email, m_tok = self._member(account["org_id"])
        try:
            assert client.get("/api/auth/me", headers=_h(m_tok)).status_code == 200
            r = client.delete(f"/api/org/members/{m_uid}", headers=_h(account["token"]))
            assert r.status_code == 204, r.text
            assert client.get("/api/auth/me", headers=_h(m_tok)).status_code == 401
        finally:
            db.users.delete_one({"id": m_uid})
            db.user_passwords.delete_one({"user_id": m_uid})
            db.login_attempts.delete_one({"_id": server._login_attempt_key(m_email, "testclient")})

    def test_reset_member_mfa_revokes_their_sessions(self, account):
        # propriétaire doit avoir sa propre 2FA pour le bris de glace ? non — reset-mfa n'exige pas
        # require_mfa ; il exige juste owner. On teste la révocation du membre.
        m_uid, m_email, m_tok = self._member(account["org_id"])
        db.user_mfa.insert_one({"user_id": m_uid, "secret": "X", "enabled": True, "backup_codes": []})
        try:
            assert client.get("/api/auth/me", headers=_h(m_tok)).status_code == 200
            r = client.post(f"/api/org/members/{m_uid}/reset-mfa", headers=_h(account["token"]))
            assert r.status_code == 200, r.text
            assert client.get("/api/auth/me", headers=_h(m_tok)).status_code == 401
        finally:
            db.users.delete_one({"id": m_uid})
            db.user_passwords.delete_one({"user_id": m_uid})
            db.user_mfa.delete_one({"user_id": m_uid})
            db.login_attempts.delete_one({"_id": server._login_attempt_key(m_email, "testclient")})


class TestPasswordReset:
    def test_reset_password_revokes_sessions(self, account):
        old = account["token"]
        token_plain = _uuid.uuid4().hex
        db.password_resets.insert_one({
            "token_hash": server._reset_token_hash(token_plain),
            "user_id": account["id"],
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        })
        try:
            r = client.post("/api/auth/reset-password",
                            json={"token": token_plain, "new_password": "brandnewpass123"})
            assert r.status_code == 200, r.text
            assert client.get("/api/auth/me", headers=_h(old)).status_code == 401
        finally:
            db.password_resets.delete_many({"user_id": account["id"]})
