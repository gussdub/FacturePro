"""Tests — SSO / OIDC (liaison de compte uniquement).

On ne teste PAS l'aller-retour réel chez Google : on cible les propriétés de SÉCURITÉ qui sont
vérifiables en local — usage unique de l'état CSRF et du code d'échange, non-contournement de la
2FA, refus d'un compte désactivé, et le fait que le JWT ne soit forgé qu'à l'échange.
"""
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
def user():
    email = f"sso-{_uuid.uuid4().hex[:8]}@ex.com"
    r = client.post("/api/auth/register",
                    json={"email": email, "password": "ssopass12345", "company_name": "SSO Test"})
    assert r.status_code == 200, r.text
    uid = r.json()["user"]["id"]
    org_id = (db.users.find_one({"id": uid}) or {}).get("organization_id")
    yield {"id": uid, "email": email, "org_id": org_id}
    db.users.delete_many({"organization_id": org_id})
    db.user_passwords.delete_one({"user_id": uid})
    db.user_mfa.delete_one({"user_id": uid})
    db.organizations.delete_one({"id": org_id})
    db.audit_logs.delete_many({"organization_id": org_id})
    db.oidc_exchanges.delete_many({"user_id": uid})


BIND = "bind-de-test"          # valeur du cookie de liaison navigateur


def _seed_exchange(user_id, ttl=60, provider="google"):
    code = "x_" + _uuid.uuid4().hex
    db.oidc_exchanges.insert_one({
        "code": code, "user_id": user_id, "provider": provider,
        "bind_hash": server._oidc_bind_hash(BIND),
        "expires_at": datetime.now(timezone.utc) + timedelta(seconds=ttl)})
    return code


def _exchange(code, bind=BIND):
    """POST /exchange en présentant (ou non) le cookie de liaison."""
    cookies = {server._OIDC_BIND_COOKIE: bind} if bind else {}
    return client.post("/api/auth/oidc/exchange", json={"code": code}, cookies=cookies)


class TestProviderGating:
    def test_providers_lists_only_configured(self):
        r = client.get("/api/auth/oidc/providers")
        assert r.status_code == 200
        # Sans variables d'environnement, AUCUN fournisseur ne doit être annoncé.
        for p in r.json()["providers"]:
            cfg = server._OIDC_PROVIDERS[p["id"]]
            assert cfg["client_id"] and cfg["client_secret"]

    def test_start_unconfigured_provider_404(self):
        assert client.get("/api/auth/oidc/google/start", follow_redirects=False).status_code == 404
        assert client.get("/api/auth/oidc/inconnu/start", follow_redirects=False).status_code == 404


class TestCallbackState:
    def test_unknown_state_is_rejected(self):
        r = client.get("/api/auth/oidc/google/callback?code=abc&state=jamais_vu",
                       follow_redirects=False)
        assert r.status_code == 302
        assert "error=" in r.headers["location"]

    def test_state_is_single_use(self, monkeypatch):
        """Un state valide est consommé ATOMIQUEMENT dès qu'il est présenté — même si la suite
        échoue — pour qu'un code intercepté ne puisse pas être rejoué. On active un fournisseur
        factice et on neutralise la découverte (aucun appel réseau en test)."""
        monkeypatch.setitem(server._OIDC_PROVIDERS, "google", {
            "label": "Google", "discovery": "http://127.0.0.1:1/none",
            "client_id": "cid-test", "client_secret": "sec-test"})
        monkeypatch.setattr(server, "_oidc_discovery",
                            lambda p: (_ for _ in ()).throw(RuntimeError("pas de reseau")))
        st = "s_" + _uuid.uuid4().hex
        db.oidc_states.insert_one({
            "state": st, "nonce": "n", "provider": "google",
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=600)})
        try:
            r = client.get(f"/api/auth/oidc/google/callback?code=abc&state={st}",
                           follow_redirects=False)
            assert r.status_code == 302
            assert db.oidc_states.find_one({"state": st}) is None, "state non consommé → rejouable"
        finally:
            db.oidc_states.delete_one({"state": st})

    def test_unconfigured_provider_does_not_consume_state(self):
        """Symétrique : si le fournisseur n'est pas configuré, on sort AVANT de toucher à l'état."""
        st = "s_" + _uuid.uuid4().hex
        db.oidc_states.insert_one({
            "state": st, "nonce": "n", "provider": "google",
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=600)})
        try:
            r = client.get(f"/api/auth/oidc/google/callback?code=abc&state={st}",
                           follow_redirects=False)
            assert "error=fournisseur_inconnu" in r.headers["location"]
            assert db.oidc_states.find_one({"state": st}) is not None
        finally:
            db.oidc_states.delete_one({"state": st})

    def test_provider_error_redirects_without_crash(self):
        r = client.get("/api/auth/oidc/google/callback?error=access_denied",
                       follow_redirects=False)
        assert r.status_code == 302 and "error=refus_fournisseur" in r.headers["location"]


class TestExchange:
    def test_happy_path_issues_token(self, user):
        code = _seed_exchange(user["id"])
        r = _exchange(code)
        assert r.status_code == 200, r.text
        assert r.json()["access_token"]
        # le jeton fonctionne réellement
        tok = r.json()["access_token"]
        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"})
        assert me.status_code == 200 and me.json()["email"] == user["email"].lower()

    def test_code_is_single_use(self, user):
        code = _seed_exchange(user["id"])
        assert _exchange(code).status_code == 200
        assert _exchange(code).status_code == 400

    def test_expired_code_rejected(self, user):
        code = _seed_exchange(user["id"], ttl=-5)
        assert _exchange(code).status_code == 400

    def test_unknown_code_rejected(self):
        assert _exchange("nawak").status_code == 400
        assert client.post("/api/auth/oidc/exchange", json={}, cookies={server._OIDC_BIND_COOKIE: BIND}).status_code == 400

    def test_sso_does_not_bypass_mfa(self, user):
        """CRITIQUE : si la 2FA est active, le SSO doit exiger le second facteur, pas le sauter."""
        db.user_mfa.insert_one({"user_id": user["id"], "secret": pyotp.random_base32(),
                                "enabled": True, "backup_codes": []})
        code = _seed_exchange(user["id"])
        r = _exchange(code)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("mfa_required") is True and body.get("mfa_token")
        assert "access_token" not in body, "le SSO a délivré un jeton en sautant la 2FA"

    def test_deactivated_account_refused(self, user):
        db.users.update_one({"id": user["id"]}, {"$set": {"is_active": False}})
        code = _seed_exchange(user["id"])
        assert _exchange(code).status_code == 403

    def test_token_carries_current_token_version(self, user):
        """Le jeton est forgé À L'ÉCHANGE : une révocation antérieure doit être prise en compte."""
        server._revoke_user_sessions(user["id"])     # bump token_version
        code = _seed_exchange(user["id"])
        r = _exchange(code)
        assert r.status_code == 200
        tok = r.json()["access_token"]
        assert client.get("/api/auth/me",
                          headers={"Authorization": f"Bearer {tok}"}).status_code == 200


class TestBrowserBinding:
    """Le `state` et le code d'échange sont liés au NAVIGATEUR initiateur (cookie HttpOnly) :
    sans ça, un code capté (historique, Referer, extension) serait rejouable par un tiers, et un
    attaquant pourrait faire consommer SON callback dans le navigateur de la victime."""

    def test_exchange_without_cookie_refused(self, user):
        code = _seed_exchange(user["id"])
        assert _exchange(code, bind=None).status_code == 400

    def test_exchange_with_wrong_cookie_refused(self, user):
        code = _seed_exchange(user["id"])
        assert _exchange(code, bind="autre-navigateur").status_code == 400

    def test_callback_without_cookie_refused(self, monkeypatch):
        monkeypatch.setitem(server._OIDC_PROVIDERS, "google", {
            "label": "Google", "discovery": "x", "client_id": "cid", "client_secret": "sec"})
        st = "s_" + _uuid.uuid4().hex
        db.oidc_states.insert_one({
            "state": st, "nonce": "n", "provider": "google",
            "bind_hash": server._oidc_bind_hash(BIND),
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=600)})
        try:
            r = client.get(f"/api/auth/oidc/google/callback?code=abc&state={st}",
                           follow_redirects=False)
            assert "error=navigateur_different" in r.headers["location"]
        finally:
            db.oidc_states.delete_one({"state": st})


class TestIdTokenRs256:
    """Exerce RÉELLEMENT la validation cryptographique de l'ID token (RS256 + JWKS).

    C'est le chemin que les autres tests court-circuitaient : il dépend de `cryptography`, dont
    l'absence dans requirements.txt aurait fait échouer 100 % des connexions SSO en production.
    """

    def _keypair(self):
        from cryptography.hazmat.primitives.asymmetric import rsa
        return rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def _run_callback(self, monkeypatch, user_email, claims_extra=None):
        import jwt as _jwt
        key = self._keypair()
        issuer, client_id = "https://idp.test", "cid-test"
        monkeypatch.setitem(server._OIDC_PROVIDERS, "google", {
            "label": "Google", "discovery": "x", "client_id": client_id, "client_secret": "sec"})
        monkeypatch.setattr(server, "_oidc_discovery", lambda p: {
            "issuer": issuer, "token_endpoint": "https://idp.test/token",
            "jwks_uri": "https://idp.test/jwks", "authorization_endpoint": "https://idp.test/auth"})
        st = "s_" + _uuid.uuid4().hex
        db.oidc_states.insert_one({
            "state": st, "nonce": "N1", "provider": "google",
            "bind_hash": server._oidc_bind_hash(BIND),
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=600)})
        now = datetime.now(timezone.utc)
        claims = {"iss": issuer, "aud": client_id, "sub": "idp-user-1", "nonce": "N1",
                  "email": user_email, "email_verified": True,
                  "iat": now, "exp": now + timedelta(minutes=5)}
        claims.update(claims_extra or {})
        id_token = _jwt.encode(claims, key, algorithm="RS256")

        class _Resp:
            def raise_for_status(self): pass
            def json(self): return {"id_token": id_token}

        class _SigningKey:
            def __init__(self, k): self.key = k

        class _Jwks:
            def get_signing_key_from_jwt(self, _t): return _SigningKey(key.public_key())

        monkeypatch.setattr(server.httpx, "post", lambda *a, **k: _Resp())
        monkeypatch.setattr(server, "_oidc_jwks", lambda p, u: _Jwks())
        try:
            return client.get(f"/api/auth/oidc/google/callback?code=abc&state={st}",
                              cookies={server._OIDC_BIND_COOKIE: BIND}, follow_redirects=False)
        finally:
            db.oidc_states.delete_one({"state": st})

    def test_valid_id_token_yields_exchange_code_then_token(self, user, monkeypatch):
        r = self._run_callback(monkeypatch, user["email"])
        assert r.status_code == 302, r.text
        loc = r.headers["location"]
        assert "/sso/callback?c=" in loc and "error" not in loc
        xcode = loc.split("c=", 1)[1]
        ex = _exchange(xcode)
        assert ex.status_code == 200, ex.text
        assert ex.json()["access_token"]

    def test_unverified_email_is_refused(self, user, monkeypatch):
        r = self._run_callback(monkeypatch, user["email"], {"email_verified": False})
        assert "error=courriel_non_verifie" in r.headers["location"]

    def test_wrong_nonce_is_refused(self, user, monkeypatch):
        r = self._run_callback(monkeypatch, user["email"], {"nonce": "AUTRE"})
        assert "error=nonce_invalide" in r.headers["location"]

    def test_unknown_email_is_refused(self, monkeypatch):
        r = self._run_callback(monkeypatch, f"inconnu-{_uuid.uuid4().hex[:8]}@ex.com")
        assert "error=compte_inconnu" in r.headers["location"]
