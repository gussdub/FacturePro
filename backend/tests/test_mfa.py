"""Tests — MFA / double authentification (TOTP), backlog P1 audit Loi 25.

Couvre : setup (secret PENDING), enable (vérif 1er code + codes de secours), login → challenge
(TOTP et code de secours, consommation), disable, exposition dans /api/auth/me.
"""
import os
import sys
import uuid as _uuid

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
def mfa_user():
    """Utilisateur JETABLE (jamais le compte de seed : activer la MFA dessus casserait les autres
    tests). Créé via /register (crée user + org + mot de passe), nettoyé en teardown."""
    email = f"mfa-{_uuid.uuid4().hex[:8]}@ex.com"
    password = "testpass12345"
    r = client.post("/api/auth/register",
                    json={"email": email, "password": password, "company_name": "MFA Test"})
    assert r.status_code == 200, r.text
    uid = r.json()["user"]["id"]
    token = r.json()["access_token"]
    org_id = (db.users.find_one({"id": uid}) or {}).get("organization_id")
    yield {"id": uid, "email": email, "password": password,
           "headers": {"Authorization": f"Bearer {token}"}}
    db.user_mfa.delete_one({"user_id": uid})
    db.users.delete_one({"id": uid})
    db.user_passwords.delete_one({"user_id": uid})
    if org_id:
        db.organizations.delete_one({"id": org_id})


def _enable_mfa(u):
    """Active la MFA pour l'utilisateur et retourne (secret, backup_codes)."""
    r = client.post("/api/auth/mfa/setup", headers=u["headers"])
    assert r.status_code == 200, r.text
    secret = r.json()["secret"]
    code = pyotp.TOTP(secret).now()
    r2 = client.post("/api/auth/mfa/enable", headers=u["headers"], json={"code": code})
    assert r2.status_code == 200, r2.text
    return secret, r2.json()["backup_codes"]


class TestSetupEnable:
    def test_setup_returns_secret_pending(self, mfa_user):
        r = client.post("/api/auth/mfa/setup", headers=mfa_user["headers"])
        assert r.status_code == 200, r.text
        assert r.json()["secret"] and r.json()["otpauth_uri"].startswith("otpauth://totp/")
        doc = db.user_mfa.find_one({"user_id": mfa_user["id"]})
        assert doc and doc["enabled"] is False           # PENDING, pas encore activé

    def test_enable_valid_code_returns_backup_codes(self, mfa_user):
        secret, backups = _enable_mfa(mfa_user)
        assert len(backups) == 8
        doc = db.user_mfa.find_one({"user_id": mfa_user["id"]})
        assert doc["enabled"] is True
        assert len(doc["backup_codes"]) == 8
        assert backups[0] not in doc["backup_codes"]     # stockés HACHÉS, pas en clair

    def test_enable_invalid_code_rejected(self, mfa_user):
        client.post("/api/auth/mfa/setup", headers=mfa_user["headers"])
        r = client.post("/api/auth/mfa/enable", headers=mfa_user["headers"], json={"code": "000000"})
        assert r.status_code == 400


class TestLoginChallenge:
    def test_login_requires_mfa_after_enable(self, mfa_user):
        _enable_mfa(mfa_user)
        r = client.post("/api/auth/login",
                        json={"email": mfa_user["email"], "password": mfa_user["password"]})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("mfa_required") is True
        assert "mfa_token" in body
        assert "access_token" not in body                # le JWT n'est PAS délivré avant le 2e facteur

    def test_challenge_with_totp_issues_token(self, mfa_user):
        secret, _ = _enable_mfa(mfa_user)
        login = client.post("/api/auth/login",
                            json={"email": mfa_user["email"], "password": mfa_user["password"]}).json()
        r = client.post("/api/auth/mfa/challenge",
                        json={"mfa_token": login["mfa_token"], "code": pyotp.TOTP(secret).now()})
        assert r.status_code == 200, r.text
        assert r.json()["access_token"]

    def test_challenge_with_backup_code_consumes_it(self, mfa_user):
        _secret, backups = _enable_mfa(mfa_user)
        login = client.post("/api/auth/login",
                            json={"email": mfa_user["email"], "password": mfa_user["password"]}).json()
        r = client.post("/api/auth/mfa/challenge",
                        json={"mfa_token": login["mfa_token"], "code": backups[0]})
        assert r.status_code == 200, r.text
        assert r.json()["access_token"]
        # le code de secours est CONSOMMÉ → réutilisation refusée
        login2 = client.post("/api/auth/login",
                             json={"email": mfa_user["email"], "password": mfa_user["password"]}).json()
        r2 = client.post("/api/auth/mfa/challenge",
                         json={"mfa_token": login2["mfa_token"], "code": backups[0]})
        assert r2.status_code == 401

    def test_challenge_invalid_code_rejected(self, mfa_user):
        _enable_mfa(mfa_user)
        login = client.post("/api/auth/login",
                            json={"email": mfa_user["email"], "password": mfa_user["password"]}).json()
        r = client.post("/api/auth/mfa/challenge",
                        json={"mfa_token": login["mfa_token"], "code": "000000"})
        assert r.status_code == 401

    def test_pending_token_not_usable_as_access_token(self, mfa_user):
        # [Sécurité] Le jeton pré-auth (mfa_pending) ne doit PAS être accepté comme Bearer d'accès
        # (sinon contournement total du 2e facteur).
        _enable_mfa(mfa_user)
        login = client.post("/api/auth/login",
                            json={"email": mfa_user["email"], "password": mfa_user["password"]}).json()
        r = client.get("/api/auth/me",
                       headers={"Authorization": f"Bearer {login['mfa_token']}"})
        assert r.status_code == 401

    def test_challenge_brute_force_locked(self, mfa_user):
        _enable_mfa(mfa_user)
        login = client.post("/api/auth/login",
                            json={"email": mfa_user["email"], "password": mfa_user["password"]}).json()
        tok = login["mfa_token"]
        try:
            for _ in range(server._LOGIN_MAX_FAILS):
                assert client.post("/api/auth/mfa/challenge",
                                   json={"mfa_token": tok, "code": "000000"}).status_code == 401
            # tentative suivante → verrouillé
            r = client.post("/api/auth/mfa/challenge", json={"mfa_token": tok, "code": "000000"})
            assert r.status_code == 429
        finally:
            db.login_attempts.delete_one(
                {"_id": server._login_attempt_key("mfa:" + mfa_user["id"], "testclient")})


class TestDisableAndMe:
    def test_disable_reverts_to_single_factor(self, mfa_user):
        secret, _ = _enable_mfa(mfa_user)
        r = client.post("/api/auth/mfa/disable", headers=mfa_user["headers"],
                        json={"code": pyotp.TOTP(secret).now()})
        assert r.status_code == 200, r.text
        assert db.user_mfa.find_one({"user_id": mfa_user["id"]}) is None
        # le login redevient direct (JWT immédiat)
        r2 = client.post("/api/auth/login",
                         json={"email": mfa_user["email"], "password": mfa_user["password"]})
        assert "access_token" in r2.json()

    def test_disable_wrong_code_rejected(self, mfa_user):
        _enable_mfa(mfa_user)
        r = client.post("/api/auth/mfa/disable", headers=mfa_user["headers"], json={"code": "000000"})
        assert r.status_code == 400

    def test_me_exposes_mfa_enabled(self, mfa_user):
        before = client.get("/api/auth/me", headers=mfa_user["headers"]).json()
        assert before["mfa_enabled"] is False
        _enable_mfa(mfa_user)
        after = client.get("/api/auth/me", headers=mfa_user["headers"]).json()
        assert after["mfa_enabled"] is True
