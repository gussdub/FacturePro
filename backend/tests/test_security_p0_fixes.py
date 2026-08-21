"""Correctifs de sécurité P0 (audit Loi 25 2026-08-20) :
1. /forgot-password ne renvoie plus le jeton (envoyé par courriel, persisté hashé) + anti-énumération.
2. GET /api/files/{id} ne sert QUE les logos (référencés), jamais les reçus (PII).
3. Anti-force-brute sur /login (verrouillage temporaire par email).
4. Webhook Stripe fail-closed si STRIPE_WEBHOOK_SECRET absent.
"""
import os
import sys
import uuid as _uuid
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test")
os.environ.setdefault("DB_NAME", "facturepro")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from backend import server  # noqa: E402
from backend.server import app, db  # noqa: E402

client = TestClient(app)


def _make_user(email, password):
    uid = str(_uuid.uuid4())
    db.users.insert_one({"id": uid, "email": email.lower(),
                         "organization_id": str(_uuid.uuid4()), "is_active": True})
    db.user_passwords.insert_one({"user_id": uid,
                                  "hashed_password": server.hash_password(password)})
    return uid


# ─────────────────────────── Fix #1 : réinitialisation ───────────────────────────
class TestForgotPasswordNoTokenLeak:
    def test_forgot_password_never_returns_token(self):
        email = f"reset-{_uuid.uuid4().hex[:8]}@ex.com"
        uid = _make_user(email, "originalpass")
        try:
            r = client.post("/api/auth/forgot-password", json={"email": email})
            assert r.status_code == 200, r.text
            assert "reset_token" not in r.json()          # JAMAIS le token dans la réponse
            # le token est persisté HASHÉ en base
            rec = db.password_resets.find_one({"user_id": uid})
            assert rec is not None
            assert "token_hash" in rec and len(rec["token_hash"]) == 64  # sha256 hex
        finally:
            db.users.delete_one({"id": uid})
            db.user_passwords.delete_one({"user_id": uid})
            db.password_resets.delete_many({"user_id": uid})

    def test_unknown_email_generic_response_no_leak(self):
        r = client.post("/api/auth/forgot-password",
                        json={"email": f"nobody-{_uuid.uuid4().hex}@ex.com"})
        assert r.status_code == 200
        assert "reset_token" not in r.json()
        # réponse identique au cas « compte existe » → pas d'oracle d'énumération
        assert "existe" in r.json()["message"].lower()

    def test_forgot_password_case_insensitive(self):
        email = f"Case-{_uuid.uuid4().hex[:8]}@Ex.com"
        uid = _make_user(email, "originalpass")  # stocké en minuscules
        try:
            r = client.post("/api/auth/forgot-password", json={"email": email.upper()})
            assert r.status_code == 200
            assert db.password_resets.find_one({"user_id": uid}) is not None
        finally:
            db.users.delete_one({"id": uid})
            db.user_passwords.delete_one({"user_id": uid})
            db.password_resets.delete_many({"user_id": uid})


class TestResetPassword:
    def test_reset_with_valid_token_changes_password(self):
        email = f"rst-{_uuid.uuid4().hex[:8]}@ex.com"
        uid = _make_user(email, "originalpass")
        token = "known-reset-token-" + _uuid.uuid4().hex
        db.password_resets.insert_one({
            "token_hash": server._reset_token_hash(token), "user_id": uid,
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
            "created_at": datetime.now(timezone.utc), "used": False,
        })
        try:
            r = client.post("/api/auth/reset-password",
                            json={"token": token, "new_password": "brandnewpass9"})
            assert r.status_code == 200, r.text
            pwd = db.user_passwords.find_one({"user_id": uid})
            assert server.verify_password("brandnewpass9", pwd["hashed_password"])
            assert not server.verify_password("originalpass", pwd["hashed_password"])
            # usage unique : le jeton est consommé
            assert db.password_resets.find_one({"user_id": uid}) is None
        finally:
            db.users.delete_one({"id": uid})
            db.user_passwords.delete_one({"user_id": uid})
            db.password_resets.delete_many({"user_id": uid})

    def test_reset_rejects_short_password(self):
        uid = _make_user(f"short-{_uuid.uuid4().hex[:8]}@ex.com", "originalpass")
        token = "tok-" + _uuid.uuid4().hex
        db.password_resets.insert_one({
            "token_hash": server._reset_token_hash(token), "user_id": uid,
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=1), "used": False,
        })
        try:
            r = client.post("/api/auth/reset-password",
                            json={"token": token, "new_password": "abc"})
            assert r.status_code == 400
            # mot de passe inchangé
            assert server.verify_password("originalpass",
                                          db.user_passwords.find_one({"user_id": uid})["hashed_password"])
        finally:
            db.users.delete_one({"id": uid})
            db.user_passwords.delete_one({"user_id": uid})
            db.password_resets.delete_many({"user_id": uid})

    def test_reset_rejects_invalid_token(self):
        r = client.post("/api/auth/reset-password",
                        json={"token": "does-not-exist", "new_password": "brandnewpass9"})
        assert r.status_code == 400

    def test_reset_rejects_expired_token(self):
        uid = _make_user(f"exp-{_uuid.uuid4().hex[:8]}@ex.com", "originalpass")
        token = "exp-" + _uuid.uuid4().hex
        db.password_resets.insert_one({
            "token_hash": server._reset_token_hash(token), "user_id": uid,
            "expires_at": datetime.now(timezone.utc) - timedelta(minutes=1), "used": False,
        })
        try:
            r = client.post("/api/auth/reset-password",
                            json={"token": token, "new_password": "brandnewpass9"})
            assert r.status_code == 400
            assert server.verify_password("originalpass",
                                          db.user_passwords.find_one({"user_id": uid})["hashed_password"])
        finally:
            db.users.delete_one({"id": uid})
            db.user_passwords.delete_one({"user_id": uid})
            db.password_resets.delete_many({"user_id": uid})


# ─────────────────────────── Fix #2 : endpoint fichiers ───────────────────────────
class TestFileEndpointLockdown:
    def _insert_file(self, purpose, owner=None):
        fid = str(_uuid.uuid4())
        db.files.insert_one({"id": fid, "data": b"\x89PNGdata", "purpose": purpose,
                             "user_id": owner, "content_type": "image/png", "is_deleted": False})
        return fid

    def test_logo_referenced_by_its_owner_is_served(self):
        owner = str(_uuid.uuid4())
        fid = self._insert_file("logo", owner=owner)
        db.company_settings.insert_one({"user_id": owner, "logo_url": f"/api/files/{fid}"})
        try:
            r = client.get(f"/api/files/{fid}")          # sans auth (chargé via <img>)
            assert r.status_code == 200
            assert r.content == b"\x89PNGdata"
        finally:
            db.files.delete_one({"id": fid})
            db.company_settings.delete_one({"user_id": owner})

    def test_receipt_not_served_anonymously(self):
        fid = self._insert_file("receipt", owner=str(_uuid.uuid4()))  # non référencé comme logo
        try:
            r = client.get(f"/api/files/{fid}")
            assert r.status_code == 404       # reçu (PII) jamais servi ici
        finally:
            db.files.delete_one({"id": fid})

    def test_file_mislabeled_logo_but_not_referenced_is_blocked(self):
        # purpose='logo' (comme la migration legacy le fait) MAIS non référencé → 404.
        # Prouve qu'on ne fait PAS confiance au champ purpose.
        fid = self._insert_file("logo", owner=str(_uuid.uuid4()))
        try:
            r = client.get(f"/api/files/{fid}")
            assert r.status_code == 404
        finally:
            db.files.delete_one({"id": fid})

    def test_logo_url_hijack_blocked(self):
        # Anti-hijack : un ATTAQUANT pointe SON logo_url vers le fichier (reçu) d'une VICTIME.
        # Le propriétaire du fichier ≠ propriétaire du réglage → 404 (le reçu reste protégé).
        victim = str(_uuid.uuid4())
        attacker = str(_uuid.uuid4())
        fid = self._insert_file("receipt", owner=victim)
        db.company_settings.insert_one({"user_id": attacker, "logo_url": f"/api/files/{fid}"})
        try:
            r = client.get(f"/api/files/{fid}")
            assert r.status_code == 404
        finally:
            db.files.delete_one({"id": fid})
            db.company_settings.delete_one({"user_id": attacker})


# ─────────────────────────── Fix #3 : anti-force-brute login ───────────────────────────
_IP = "testclient"  # host par défaut du TestClient Starlette


class TestLoginBruteForce:
    def test_lockout_after_max_failures(self):
        email = f"bf-{_uuid.uuid4().hex[:8]}@ex.com"  # compte inexistant → aucun user réel touché
        try:
            for _ in range(server._LOGIN_MAX_FAILS):
                r = client.post("/api/auth/login", json={"email": email, "password": "wrong"})
                assert r.status_code == 401
            # tentative suivante → verrouillé
            r = client.post("/api/auth/login", json={"email": email, "password": "wrong"})
            assert r.status_code == 429
            assert "Retry-After" in r.headers
        finally:
            db.login_attempts.delete_one({"_id": server._login_attempt_key(email, _IP)})

    def test_lock_uses_rightmost_xff_not_spoofable_left(self):
        # L'attaquant fait varier la GAUCHE de X-Forwarded-For (usurpable) ; le proxy ajoute la
        # vraie IP à DROITE. Le verrou doit keyer sur la droite → 5 échecs suffisent malgré le spoof.
        email = f"xff-{_uuid.uuid4().hex[:8]}@ex.com"
        real_ip = "203.0.113.77"
        try:
            for i in range(server._LOGIN_MAX_FAILS):
                r = client.post("/api/auth/login", json={"email": email, "password": "wrong"},
                                headers={"X-Forwarded-For": f"9.9.9.{i}, {real_ip}"})
                assert r.status_code == 401
            r = client.post("/api/auth/login", json={"email": email, "password": "wrong"},
                            headers={"X-Forwarded-For": f"1.1.1.1, {real_ip}"})
            assert r.status_code == 429  # verrouillé sur la vraie IP (droite), pas contournable
        finally:
            db.login_attempts.delete_one({"_id": server._login_attempt_key(email, real_ip)})

    def test_success_clears_failures(self):
        email = f"clr-{_uuid.uuid4().hex[:8]}@ex.com"
        uid = _make_user(email, "goodpassword1")
        try:
            for _ in range(2):  # 2 échecs (< seuil)
                assert client.post("/api/auth/login",
                                   json={"email": email, "password": "bad"}).status_code == 401
            r = client.post("/api/auth/login", json={"email": email, "password": "goodpassword1"})
            assert r.status_code == 200, r.text
            # le succès a purgé le compteur d'échecs
            assert db.login_attempts.find_one({"_id": server._login_attempt_key(email, _IP)}) is None
        finally:
            db.users.delete_one({"id": uid})
            db.user_passwords.delete_one({"user_id": uid})
            db.login_attempts.delete_one({"_id": server._login_attempt_key(email, _IP)})


class TestForgotPasswordRateLimit:
    def test_forgot_password_rate_limited(self):
        server._FORGOT_PW_RATE.clear()
        try:
            for _ in range(server._FORGOT_PW_MAX):
                assert client.post("/api/auth/forgot-password",
                                   json={"email": f"x-{_uuid.uuid4().hex}@ex.com"}).status_code == 200
            r = client.post("/api/auth/forgot-password", json={"email": "one-more@ex.com"})
            assert r.status_code == 429
        finally:
            server._FORGOT_PW_RATE.clear()


class TestRegisterPasswordPolicy:
    def test_register_rejects_short_password(self):
        r = client.post("/api/auth/register", json={
            "email": f"reg-{_uuid.uuid4().hex[:8]}@ex.com", "password": "abc", "company_name": "X"})
        assert r.status_code == 400
        assert "8" in r.json().get("detail", "")


@pytest.fixture
def auth_headers():
    r = client.post("/api/auth/login",
                    json={"email": "gussdub@gmail.com", "password": "testpass123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


class TestManualReceiptStillViewable:
    def test_org_receipt_served_via_authenticated_endpoint(self, auth_headers):
        # Après le correctif, un reçu manuel (purpose='receipt' + org) reste visible via la voie
        # AUTHENTIFIÉE /api/receipts/{id} (ce que le frontend appelle désormais via viewReceipt).
        org = db.users.find_one({"email": "gussdub@gmail.com"})["organization_id"]
        fid = str(_uuid.uuid4())
        db.files.insert_one({"id": fid, "data": b"receiptbytes", "purpose": "receipt",
                             "organization_id": org, "content_type": "application/pdf",
                             "is_deleted": False})
        try:
            r = client.get(f"/api/receipts/{fid}", headers=auth_headers)
            assert r.status_code == 200, r.text
            assert r.content == b"receiptbytes"
            # et l'endpoint PUBLIC le refuse toujours
            assert client.get(f"/api/files/{fid}").status_code == 404
        finally:
            db.files.delete_one({"id": fid})


class TestManualReceiptLockdown:
    def test_upload_tags_receipt_and_files_endpoint_blocks_it(self):
        # Un reçu manuel (purpose='receipt', même référencé par erreur comme logo par son
        # propriétaire) NE doit PAS être servi par l'endpoint public /api/files.
        owner = str(_uuid.uuid4())
        fid = str(_uuid.uuid4())
        db.files.insert_one({"id": fid, "data": b"pdfdata", "purpose": "receipt",
                             "user_id": owner, "content_type": "application/pdf", "is_deleted": False})
        db.company_settings.insert_one({"user_id": owner, "logo_url": f"/api/files/{fid}"})
        try:
            r = client.get(f"/api/files/{fid}")
            assert r.status_code == 404  # garde défensive purpose='receipt'
        finally:
            db.files.delete_one({"id": fid})
            db.company_settings.delete_one({"user_id": owner})


# ─────────────────────────── Fix #4 : webhook Stripe fail-closed ───────────────────────────
class TestStripeWebhookFailClosed:
    def test_webhook_rejected_without_secret(self):
        orig_api, orig_secret = server.STRIPE_API_KEY, server.STRIPE_WEBHOOK_SECRET
        server.STRIPE_API_KEY = "sk_test_x"
        server.STRIPE_WEBHOOK_SECRET = ""
        try:
            r = client.post("/api/webhook/stripe", content=b'{"type":"checkout.session.completed"}')
            assert r.status_code == 500
            assert "STRIPE_WEBHOOK_SECRET" in r.text
        finally:
            server.STRIPE_API_KEY = orig_api
            server.STRIPE_WEBHOOK_SECRET = orig_secret
