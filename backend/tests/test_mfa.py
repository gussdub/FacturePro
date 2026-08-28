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
    """Active la MFA pour l'utilisateur et retourne (secret, backup_codes).
    [Révocation de session] L'activation N'auto-révoque PAS (la révocation des autres sessions se fait
    au clic « J'ai noté mes codes » côté front, via /logout-others) → le jeton courant reste valide."""
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


class TestQrAndOrgEnforcement:
    def test_setup_returns_qr(self, mfa_user):
        r = client.post("/api/auth/mfa/setup", headers=mfa_user["headers"])
        assert r.status_code == 200, r.text
        assert r.json()["qr_data_uri"].startswith("data:image/png;base64,")

    def test_toggle_require_mfa_needs_owner_own_mfa(self, mfa_user):
        # Le propriétaire ne peut IMPOSER la 2FA sans l'avoir lui-même activée (anti-lockout).
        r = client.post("/api/org/require-mfa", headers=mfa_user["headers"], json={"enabled": True})
        assert r.status_code == 400
        # après activation de SA 2FA, il peut imposer
        _enable_mfa(mfa_user)
        r2 = client.post("/api/org/require-mfa", headers=mfa_user["headers"], json={"enabled": True})
        assert r2.status_code == 200 and r2.json()["require_mfa"] is True

    def test_enforcement_blocks_member_without_mfa(self, mfa_user):
        org_id = (db.users.find_one({"id": mfa_user["id"]}) or {}).get("organization_id")
        _enable_mfa(mfa_user)
        assert client.post("/api/org/require-mfa", headers=mfa_user["headers"],
                           json={"enabled": True}).status_code == 200
        # membre SANS 2FA dans la même org
        m_email = f"member-{_uuid.uuid4().hex[:8]}@ex.com"
        m_pw = "memberpass123"
        m_uid = str(_uuid.uuid4())
        db.users.insert_one({"id": m_uid, "email": m_email.lower(), "organization_id": org_id,
                             "role": "accountant", "is_active": True})
        db.user_passwords.insert_one({"user_id": m_uid, "hashed_password": server.hash_password(m_pw)})
        try:
            m_tok = client.post("/api/auth/login",
                                json={"email": m_email, "password": m_pw}).json()["access_token"]
            mh = {"Authorization": f"Bearer {m_tok}"}
            # endpoint métier bloqué avec le motif d'enrôlement
            r = client.get("/api/clients", headers=mh)
            assert r.status_code == 403
            assert r.json().get("detail") == "mfa_enrollment_required"
            # [Sécurité] un endpoint MUTANT en accès direct (hors require_permission) est AUSSI bloqué —
            # sinon un membre sans 2FA pourrait quand même téléverser des fichiers malgré l'imposition.
            up = client.post("/api/upload", headers=mh,
                             files={"file": ("t.png", b"\x89PNG\r\n\x1a\n", "image/png")})
            assert up.status_code == 403
            assert up.json().get("detail") == "mfa_enrollment_required"
            # idem pour le changement d'email (mutation de compte en accès direct)
            em = client.put("/api/auth/me/email", headers=mh, json={"email": "new@ex.com"})
            assert em.status_code == 403
            assert em.json().get("detail") == "mfa_enrollment_required"
            # /api/auth/me reste accessible (pour pouvoir s'enrôler)
            assert client.get("/api/auth/me", headers=mh).status_code == 200
            # le membre ne peut pas non plus lever l'exigence (réservé au propriétaire)
            assert client.post("/api/org/require-mfa", headers=mh,
                               json={"enabled": False}).status_code == 403
        finally:
            db.users.delete_one({"id": m_uid})
            db.user_passwords.delete_one({"user_id": m_uid})
            db.user_mfa.delete_one({"user_id": m_uid})
            db.login_attempts.delete_one({"_id": server._login_attempt_key(m_email, "testclient")})

    def test_org_me_hides_roster_from_unenrolled_member(self, mfa_user):
        # Un membre non-enrôlé (org impose la 2FA) ne doit PAS voir le trombinoscope ni la matrice RBAC.
        org_id = (db.users.find_one({"id": mfa_user["id"]}) or {}).get("organization_id")
        _enable_mfa(mfa_user)
        assert client.post("/api/org/require-mfa", headers=mfa_user["headers"],
                           json={"enabled": True}).status_code == 200
        m_email = f"member-{_uuid.uuid4().hex[:8]}@ex.com"
        m_pw, m_uid = "memberpass123", str(_uuid.uuid4())
        db.users.insert_one({"id": m_uid, "email": m_email.lower(), "organization_id": org_id,
                             "role": "accountant", "is_active": True})
        db.user_passwords.insert_one({"user_id": m_uid, "hashed_password": server.hash_password(m_pw)})
        try:
            m_tok = client.post("/api/auth/login",
                                json={"email": m_email, "password": m_pw}).json()["access_token"]
            mh = {"Authorization": f"Bearer {m_tok}"}
            body = client.get("/api/org/me", headers=mh).json()
            assert body["members"] == []
            assert body["organization"]["role_permissions"] == {}
            assert body["organization"]["mfa_enrollment_required"] is True
            assert body["current_user"]["role"] == "accountant"   # de quoi amorcer l'enrôlement
        finally:
            db.users.delete_one({"id": m_uid})
            db.user_passwords.delete_one({"user_id": m_uid})
            db.login_attempts.delete_one({"_id": server._login_attempt_key(m_email, "testclient")})

    def test_owner_breakglass_resets_member_mfa(self, mfa_user):
        # Le propriétaire peut réinitialiser la 2FA d'un membre verrouillé (perte authenticator + codes).
        org_id = (db.users.find_one({"id": mfa_user["id"]}) or {}).get("organization_id")
        _enable_mfa(mfa_user)
        m_uid = str(_uuid.uuid4())
        db.users.insert_one({"id": m_uid, "email": f"m-{m_uid[:8]}@ex.com", "organization_id": org_id,
                             "role": "accountant", "is_active": True})
        db.user_mfa.insert_one({"user_id": m_uid, "secret": "X", "enabled": True, "backup_codes": []})
        try:
            # non-propriétaire ne peut pas ; propriétaire oui
            r = client.post(f"/api/org/members/{m_uid}/reset-mfa", headers=mfa_user["headers"])
            assert r.status_code == 200 and r.json()["reset"] is True
            assert db.user_mfa.find_one({"user_id": m_uid}) is None       # 2FA du membre supprimée
            # propriétaire ne peut PAS se réinitialiser lui-même par ce biais (contournerait /disable)
            assert client.post(f"/api/org/members/{mfa_user['id']}/reset-mfa",
                               headers=mfa_user["headers"]).status_code == 400
            # membre inconnu → 404
            assert client.post(f"/api/org/members/{_uuid.uuid4()}/reset-mfa",
                               headers=mfa_user["headers"]).status_code == 404
        finally:
            db.users.delete_one({"id": m_uid})
            db.user_mfa.delete_one({"user_id": m_uid})

    def test_reset_member_mfa_requires_owner(self, mfa_user):
        # Un membre lambda ne peut pas réinitialiser la 2FA d'autrui.
        org_id = (db.users.find_one({"id": mfa_user["id"]}) or {}).get("organization_id")
        m_email = f"member-{_uuid.uuid4().hex[:8]}@ex.com"
        m_pw, m_uid = "memberpass123", str(_uuid.uuid4())
        db.users.insert_one({"id": m_uid, "email": m_email.lower(), "organization_id": org_id,
                             "role": "accountant", "is_active": True})
        db.user_passwords.insert_one({"user_id": m_uid, "hashed_password": server.hash_password(m_pw)})
        try:
            m_tok = client.post("/api/auth/login",
                                json={"email": m_email, "password": m_pw}).json()["access_token"]
            r = client.post(f"/api/org/members/{mfa_user['id']}/reset-mfa",
                            headers={"Authorization": f"Bearer {m_tok}"})
            assert r.status_code == 403
        finally:
            db.users.delete_one({"id": m_uid})
            db.user_passwords.delete_one({"user_id": m_uid})
            db.login_attempts.delete_one({"_id": server._login_attempt_key(m_email, "testclient")})

    def test_require_mfa_rejects_non_boolean(self, mfa_user):
        # bool("false") == True : un 'enabled' non booléen ne doit PAS activer l'imposition par erreur.
        _enable_mfa(mfa_user)
        r = client.post("/api/org/require-mfa", headers=mfa_user["headers"], json={"enabled": "false"})
        assert r.status_code == 400
        # l'imposition n'a pas été activée par la valeur mal typée
        assert client.get("/api/auth/me", headers=mfa_user["headers"]).json()["require_mfa"] is False

    def test_me_exposes_require_mfa(self, mfa_user):
        assert client.get("/api/auth/me", headers=mfa_user["headers"]).json()["require_mfa"] is False
