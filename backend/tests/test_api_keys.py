"""Clés API — étape 2 du lot 0 de l'intégration ProFireManager.

Trois points de sécurité gouvernent ce module, et chacun a son test :

1. La limitation de débit s'applique AVANT la comparaison du hachage. Placée après, elle ne
   protège pas contre l'essai systématique de clés invalides, puisque ces requêtes échouent
   avant d'atteindre le compteur.
2. Les scopes accordables sont une liste blanche. `team:manage` et `billing:manage` ne doivent
   jamais pouvoir être accordés, même demandés explicitement.
3. Une clé ne voit que son organisation. Jamais une valeur venue du corps ou de l'URL.
"""
import hashlib
import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))

import uuid

import pytest
import server as server_module
from fastapi import HTTPException


def _sha(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


class TestGenerationSecret:
    def test_format_du_secret(self):
        secret = server_module._api_key_generate_secret()
        assert secret.startswith("fp_live_")
        # 32 octets en base64url = 43 caractères sans remplissage.
        assert len(secret) >= 8 + 43

    def test_secrets_uniques(self):
        secrets = {server_module._api_key_generate_secret() for _ in range(50)}
        assert len(secrets) == 50

    def test_prefixe_discrimine(self):
        """Le préfixe sert à retrouver la clé en base avant comparaison. S'il valait seulement
        `fp_live_`, il serait identique pour toutes les clés et ne discriminerait rien."""
        a = server_module._api_key_prefix(server_module._api_key_generate_secret())
        b = server_module._api_key_prefix(server_module._api_key_generate_secret())
        assert a != b
        assert a.startswith("fp_live_") and len(a) > len("fp_live_")


class TestListeBlancheScopes:
    def test_scopes_autorises(self):
        assert server_module._API_KEY_ALLOWED_SCOPES == (
            "clients:read", "quotes:read", "quotes:write", "invoices:read")

    @pytest.mark.parametrize("interdit", [
        "team:manage", "billing:manage", "settings:write", "expenses:write", "*", "admin"])
    def test_scope_interdit_rejete(self, interdit):
        """Même demandé explicitement. C'est validé à la création, en 400."""
        with pytest.raises(HTTPException) as exc:
            server_module._api_key_validate_scopes(["clients:read", interdit])
        assert exc.value.status_code == 400

    def test_liste_vide_rejetee(self):
        with pytest.raises(HTTPException) as exc:
            server_module._api_key_validate_scopes([])
        assert exc.value.status_code == 400

    def test_scopes_valides_normalises(self):
        assert server_module._api_key_validate_scopes(
            ["quotes:read", "clients:read", "clients:read"]) == ["clients:read", "quotes:read"]

    def test_team_manage_absent_de_la_liste_blanche(self):
        """Test explicite : ces deux codes sont nommés dans la spec comme interdits."""
        assert "team:manage" not in server_module._API_KEY_ALLOWED_SCOPES
        assert "billing:manage" not in server_module._API_KEY_ALLOWED_SCOPES


class TestLimitationDebit:
    def setup_method(self):
        server_module._API_KEY_RATE.clear()

    def test_sous_la_limite(self):
        for _ in range(server_module._API_KEY_MAX_REQUESTS):
            assert server_module._api_key_rate_limit_ok("1.2.3.4", "fp_live_aaaaaaaa") is True

    def test_au_dessus_de_la_limite(self):
        for _ in range(server_module._API_KEY_MAX_REQUESTS):
            server_module._api_key_rate_limit_ok("1.2.3.4", "fp_live_aaaaaaaa")
        assert server_module._api_key_rate_limit_ok("1.2.3.4", "fp_live_aaaaaaaa") is False

    def test_compteurs_independants_par_ip(self):
        for _ in range(server_module._API_KEY_MAX_REQUESTS):
            server_module._api_key_rate_limit_ok("1.2.3.4", "fp_live_aaaaaaaa")
        assert server_module._api_key_rate_limit_ok("9.9.9.9", "fp_live_aaaaaaaa") is True

    def test_compteurs_independants_par_prefixe(self):
        for _ in range(server_module._API_KEY_MAX_REQUESTS):
            server_module._api_key_rate_limit_ok("1.2.3.4", "fp_live_aaaaaaaa")
        assert server_module._api_key_rate_limit_ok("1.2.3.4", "fp_live_bbbbbbbb") is True


class TestPrincipal:
    """`_api_key_resolve` est le cœur : c'est lui qui décide qui entre."""

    @pytest.fixture
    def cle(self):
        secret = server_module._api_key_generate_secret()
        doc = {
            "id": str(uuid.uuid4()),
            "organization_id": "org-test-api-A",
            "name": "Test PFM",
            "key_prefix": server_module._api_key_prefix(secret),
            "key_hash": _sha(secret),
            "scopes": ["clients:read", "quotes:read"],
            "created_at": "2026-01-01T00:00:00+00:00",
            "created_by_user_id": "u1",
            "last_used_at": None,
            "revoked_at": None,
        }
        server_module.db.api_keys.insert_one(dict(doc))
        yield secret, doc
        server_module.db.api_keys.delete_one({"id": doc["id"]})

    def setup_method(self):
        server_module._API_KEY_RATE.clear()

    def test_cle_valide(self, cle):
        secret, doc = cle
        principal = server_module._api_key_resolve(secret, ip="1.1.1.1")
        assert principal.organization_id == "org-test-api-A"
        assert principal.role == "api"
        assert principal.permissions == ["clients:read", "quotes:read"]
        assert principal.id == doc["id"]

    def test_cle_revoquee_refusee(self, cle):
        secret, doc = cle
        server_module.db.api_keys.update_one(
            {"id": doc["id"]}, {"$set": {"revoked_at": "2026-02-01T00:00:00+00:00"}})
        with pytest.raises(HTTPException) as exc:
            server_module._api_key_resolve(secret, ip="1.1.1.1")
        assert exc.value.status_code == 401

    def test_cle_inconnue_refusee(self):
        with pytest.raises(HTTPException) as exc:
            server_module._api_key_resolve(server_module._api_key_generate_secret(), ip="1.1.1.1")
        assert exc.value.status_code == 401

    def test_mauvais_secret_meme_prefixe_refuse(self, cle):
        """Deux secrets partageant le préfixe : seul le hachage tranche."""
        secret, doc = cle
        faux = secret[:16] + "X" * (len(secret) - 16)
        with pytest.raises(HTTPException) as exc:
            server_module._api_key_resolve(faux, ip="1.1.1.1")
        assert exc.value.status_code == 401

    def test_debit_limite_AVANT_comparaison_de_hachage(self, monkeypatch):
        """LE test de sécurité du lot.

        On rend la comparaison de hachage explosive. Si la limitation venait après, l'essai
        systématique de clés invalides atteindrait la comparaison et le compteur ne
        protégerait rien. Le 429 doit donc arriver sans qu'elle soit jamais appelée.
        """
        appels = []

        def _compare_explosif(*a, **k):
            appels.append(1)
            raise AssertionError("la comparaison de hachage ne doit PAS être atteinte")

        for _ in range(server_module._API_KEY_MAX_REQUESTS):
            try:
                server_module._api_key_resolve("fp_live_zzzzzzzzINVALIDE", ip="7.7.7.7")
            except HTTPException:
                pass
        monkeypatch.setattr(server_module.hmac, "compare_digest", _compare_explosif)
        with pytest.raises(HTTPException) as exc:
            server_module._api_key_resolve("fp_live_zzzzzzzzINVALIDE", ip="7.7.7.7")
        assert exc.value.status_code == 429
        assert not appels, "la comparaison a été atteinte malgré le dépassement"

    def test_derniere_utilisation_horodatee(self, cle):
        secret, doc = cle
        server_module._api_key_resolve(secret, ip="1.1.1.1")
        frais = server_module.db.api_keys.find_one({"id": doc["id"]})
        assert frais["last_used_at"]

    def test_aucune_mfa_invoquee(self, cle, monkeypatch):
        """Une clé API ne passe JAMAIS par _enforce_org_mfa — pas de contournement à écrire.

        Si un jour quelqu'un branche la dépendance des clés sur la chaîne utilisateur, ce test
        tombe et rappelle qu'il faut trancher explicitement plutôt qu'assouplir le garde MFA
        pour tout le monde.
        """
        def _explosif(*a, **k):
            raise AssertionError("_enforce_org_mfa ne doit pas être atteint par une clé API")
        monkeypatch.setattr(server_module, "_enforce_org_mfa", _explosif)
        secret, _ = cle
        assert server_module._api_key_resolve(secret, ip="1.1.1.1").role == "api"


class TestScopeRequis:
    def _principal(self, scopes):
        return server_module.CurrentUser(
            id="k1", email="api-key:fp_live_test", organization_id="org-A",
            role="api", permissions=list(scopes))

    def test_scope_present(self):
        server_module._api_key_require_scope(self._principal(["clients:read"]), "clients:read")

    def test_scope_absent_403(self):
        with pytest.raises(HTTPException) as exc:
            server_module._api_key_require_scope(self._principal(["clients:read"]), "quotes:write")
        assert exc.value.status_code == 403


class TestEndpointsGestion:
    """Création, liste, révocation. Réservés au propriétaire."""

    @pytest.fixture
    def client_api(self):
        from fastapi.testclient import TestClient
        c = TestClient(server_module.app)
        r = c.post("/api/auth/login",
                   json={"email": "gussdub@gmail.com", "password": "testpass123"})
        assert r.status_code == 200, r.text
        return c, {"Authorization": f"Bearer {r.json()['access_token']}"}

    @pytest.fixture(autouse=True)
    def _nettoyage(self):
        yield
        server_module.db.api_keys.delete_many({"name": {"$regex": "^TEST-PFM-"}})

    def test_creation_renvoie_le_secret_une_seule_fois(self, client_api):
        c, h = client_api
        r = c.post("/api/org/api-keys",
                   json={"name": "TEST-PFM-creation", "scopes": ["clients:read"]}, headers=h)
        assert r.status_code == 201, r.text
        corps = r.json()
        assert corps["secret"].startswith("fp_live_")
        assert corps["key_prefix"] == server_module._api_key_prefix(corps["secret"])

        # La liste ne doit JAMAIS le redonner.
        liste = c.get("/api/org/api-keys", headers=h).json()
        ligne = next(k for k in liste["data"] if k["id"] == corps["id"])
        assert "secret" not in ligne
        assert "key_hash" not in ligne

    def test_secret_jamais_stocke_en_clair(self, client_api):
        c, h = client_api
        r = c.post("/api/org/api-keys",
                   json={"name": "TEST-PFM-hash", "scopes": ["clients:read"]}, headers=h)
        secret = r.json()["secret"]
        doc = server_module.db.api_keys.find_one({"id": r.json()["id"]})
        assert secret not in str(doc), "le secret complet ne doit jamais être en base"
        assert doc["key_hash"] == _sha(secret)

    @pytest.mark.parametrize("interdit", ["team:manage", "billing:manage"])
    def test_scope_interdit_refuse_en_400(self, client_api, interdit):
        c, h = client_api
        r = c.post("/api/org/api-keys",
                   json={"name": "TEST-PFM-scope", "scopes": ["clients:read", interdit]},
                   headers=h)
        assert r.status_code == 400, r.text

    def test_revocation(self, client_api):
        c, h = client_api
        r = c.post("/api/org/api-keys",
                   json={"name": "TEST-PFM-revoc", "scopes": ["clients:read"]}, headers=h)
        kid, secret = r.json()["id"], r.json()["secret"]
        server_module._API_KEY_RATE.clear()
        assert server_module._api_key_resolve(secret, ip="1.1.1.1").role == "api"

        assert c.delete(f"/api/org/api-keys/{kid}", headers=h).status_code == 204
        doc = server_module.db.api_keys.find_one({"id": kid})
        assert doc is not None, "une clé révoquée n'est JAMAIS supprimée"
        assert doc["revoked_at"]
        with pytest.raises(HTTPException) as exc:
            server_module._api_key_resolve(secret, ip="1.1.1.1")
        assert exc.value.status_code == 401

    def test_creation_et_revocation_journalisees(self, client_api):
        c, h = client_api
        r = c.post("/api/org/api-keys",
                   json={"name": "TEST-PFM-audit", "scopes": ["clients:read"]}, headers=h)
        kid = r.json()["id"]
        c.delete(f"/api/org/api-keys/{kid}", headers=h)
        actions = {e["action"] for e in server_module.db.audit_logs.find(
            {"target_id": kid}, {"_id": 0, "action": 1})}
        assert "api_key.created" in actions
        assert "api_key.revoked" in actions

    def test_journal_ne_contient_pas_le_secret(self, client_api):
        c, h = client_api
        r = c.post("/api/org/api-keys",
                   json={"name": "TEST-PFM-nosecret", "scopes": ["clients:read"]}, headers=h)
        secret = r.json()["secret"]
        entrees = list(server_module.db.audit_logs.find({"target_id": r.json()["id"]}, {"_id": 0}))
        assert entrees
        assert secret not in str(entrees), "le secret ne doit jamais être journalisé"

    def test_isolation_entre_organisations(self, client_api):
        """Une clé de l'organisation A ne doit pas apparaître dans la liste de B."""
        c, h = client_api
        autre = str(uuid.uuid4())
        server_module.db.api_keys.insert_one({
            "id": autre, "organization_id": "org-etrangere", "name": "TEST-PFM-etrangere",
            "key_prefix": "fp_live_zzzzzzzz", "key_hash": "x", "scopes": ["clients:read"],
            "created_at": "2026-01-01T00:00:00+00:00", "created_by_user_id": "u",
            "last_used_at": None, "revoked_at": None})
        try:
            ids = {k["id"] for k in c.get("/api/org/api-keys", headers=h).json()["data"]}
            assert autre not in ids
            assert c.delete(f"/api/org/api-keys/{autre}", headers=h).status_code == 404
        finally:
            server_module.db.api_keys.delete_one({"id": autre})

    def test_non_proprietaire_refuse(self, client_api):
        """Une clé API contourne l'interface et porte des droits de lecture sur TOUTES les
        données de l'organisation. Sa création est donc réservée au propriétaire.

        On déplace temporairement la propriété de l'organisation plutôt que de créer un second
        compte : le garde réel est ainsi exercé, sans dépendre d'un jeu de données de test.
        """
        c, h = client_api
        me = c.get("/api/auth/me", headers=h).json()
        oid = me["organization_id"]
        org = server_module.db.organizations.find_one({"id": oid}, {"_id": 0, "owner_id": 1})
        vrai_owner = org["owner_id"]
        server_module.db.organizations.update_one(
            {"id": oid}, {"$set": {"owner_id": "un-autre-utilisateur"}})
        try:
            r = c.post("/api/org/api-keys",
                       json={"name": "TEST-PFM-nonowner", "scopes": ["clients:read"]}, headers=h)
            assert r.status_code == 403, r.text
            assert c.get("/api/org/api-keys", headers=h).status_code == 403
            assert c.delete("/api/org/api-keys/nimporte", headers=h).status_code == 403
        finally:
            server_module.db.organizations.update_one(
                {"id": oid}, {"$set": {"owner_id": vrai_owner}})
