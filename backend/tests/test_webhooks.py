"""Webhooks sortants — étape 5 du lot 0 (intégration ProFireManager).

Quatre propriétés :

1. La signature porte sur `<horodatage>.<corps BRUT>`, et le corps signé doit être EXACTEMENT
   celui envoyé. Signer une re-sérialisation rendrait toute vérification impossible chez PFM.
2. La livraison n'est JAMAIS synchrone. Une cible lente ne doit pas faire échouer la création
   du client dans FacturePro.
3. Les réessais sont obligatoires, pas optionnels : PFM est aussi sur Render, donc une cible
   froide échouera au premier appel. Sans réessai, l'intégration perd des événements dès le
   premier jour.
4. Un 4xx définitif n'est pas réessayé — inutile de marteler une cible qui refuse.
"""
import hashlib
import hmac as _hmac
import json
import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import server as server_module

ORG_WH = "org-webhook-T"
SECRET = "whsec_test_abcdef0123456789"


@pytest.fixture
def endpoint():
    eid = str(uuid.uuid4())
    server_module.db.webhook_endpoints.insert_one({
        "id": eid, "organization_id": ORG_WH, "url": "https://pfm.test/hooks/facturepro",
        "secret": SECRET,
        "events": ["client.created", "quote.created"], "actif": True,
        "created_at": "2026-01-01T00:00:00+00:00",
        "last_success_at": None, "last_error": None})
    yield eid
    server_module.db.webhook_endpoints.delete_one({"id": eid})
    server_module.db.webhook_deliveries.delete_many({"endpoint_id": eid})


class TestSignature:
    def test_format_de_l_entete(self):
        entete = server_module._webhook_signature_header("corps brut", SECRET, horodatage=1790000000)
        assert entete.startswith("t=1790000000,v1=")
        assert len(entete.split("v1=")[1]) == 64      # SHA-256 en hexadécimal

    def test_hmac_porte_sur_horodatage_point_corps(self):
        corps = '{"id":"evt_1"}'
        entete = server_module._webhook_signature_header(corps, SECRET, horodatage=1790000000)
        attendu = _hmac.new(SECRET.encode(), f"1790000000.{corps}".encode(),
                            hashlib.sha256).hexdigest()
        assert entete.split("v1=")[1] == attendu

    def test_corps_different_signature_differente(self):
        a = server_module._webhook_signature_header('{"a":1}', SECRET, horodatage=1)
        b = server_module._webhook_signature_header('{"a":2}', SECRET, horodatage=1)
        assert a != b

    def test_secret_different_signature_differente(self):
        a = server_module._webhook_signature_header('{"a":1}', "whsec_un", horodatage=1)
        b = server_module._webhook_signature_header('{"a":1}', "whsec_deux", horodatage=1)
        assert a != b

    def test_verification_rejette_un_horodatage_vieux(self):
        """Sans cette vérification, une requête interceptée pourrait être rejouée
        indéfiniment. Tolérance de 5 minutes."""
        corps = '{"id":"evt_1"}'
        vieux = int((datetime.now(timezone.utc) - timedelta(minutes=10)).timestamp())
        entete = server_module._webhook_signature_header(corps, SECRET, horodatage=vieux)
        assert server_module._webhook_signature_verify(corps, entete, SECRET) is False

    def test_verification_accepte_un_horodatage_frais(self):
        corps = '{"id":"evt_1"}'
        entete = server_module._webhook_signature_header(corps, SECRET)
        assert server_module._webhook_signature_verify(corps, entete, SECRET) is True

    def test_verification_rejette_une_signature_falsifiee(self):
        corps = '{"id":"evt_1"}'
        entete = server_module._webhook_signature_header(corps, SECRET)
        falsifie = entete[:-1] + ("0" if entete[-1] != "0" else "1")
        assert server_module._webhook_signature_verify(corps, falsifie, SECRET) is False

    def test_verification_rejette_un_entete_malforme(self):
        for mauvais in ("", "t=1", "v1=abc", "n'importe quoi", "t=abc,v1=def"):
            assert server_module._webhook_signature_verify('{}', mauvais, SECRET) is False


class TestMiseEnFile:
    def test_evenement_non_abonne_ignore(self, endpoint):
        server_module._webhook_enqueue(ORG_WH, "invoice.paid", {"id": "i1"})
        assert server_module.db.webhook_deliveries.count_documents(
            {"endpoint_id": endpoint}) == 0

    def test_evenement_abonne_mis_en_file(self, endpoint):
        server_module._webhook_enqueue(ORG_WH, "client.created", {"id": "c1"})
        d = server_module.db.webhook_deliveries.find_one({"endpoint_id": endpoint})
        assert d is not None
        assert d["status"] == "pending"
        assert d["attempts"] == 0
        charge = json.loads(d["payload"])
        assert charge["type"] == "client.created"
        assert charge["organization_id"] == ORG_WH
        assert charge["data"] == {"id": "c1"}
        assert charge["id"].startswith("evt_")

    def test_endpoint_inactif_ignore(self, endpoint):
        server_module.db.webhook_endpoints.update_one(
            {"id": endpoint}, {"$set": {"actif": False}})
        server_module._webhook_enqueue(ORG_WH, "client.created", {"id": "c1"})
        assert server_module.db.webhook_deliveries.count_documents(
            {"endpoint_id": endpoint}) == 0

    def test_autre_organisation_ignoree(self, endpoint):
        server_module._webhook_enqueue("org-etrangere", "client.created", {"id": "c1"})
        assert server_module.db.webhook_deliveries.count_documents(
            {"endpoint_id": endpoint}) == 0

    def test_mise_en_file_ne_leve_jamais(self, endpoint, monkeypatch):
        """La mise en file est sur le chemin de requête. Elle ne doit JAMAIS faire échouer la
        création du client, quoi qu'il arrive."""
        def _explose(*a, **k):
            raise RuntimeError("mongo indisponible")
        monkeypatch.setattr(server_module.db.webhook_deliveries, "insert_one", _explose)
        server_module._webhook_enqueue(ORG_WH, "client.created", {"id": "c1"})   # ne lève pas

    def test_aucun_appel_reseau_a_la_mise_en_file(self, endpoint, monkeypatch):
        """§6.5 : jamais de livraison synchrone. Une cible lente ferait échouer la création."""
        def _interdit(*a, **k):
            raise AssertionError("appel réseau sur le chemin de requête")
        monkeypatch.setattr(server_module.httpx, "post", _interdit)
        server_module._webhook_enqueue(ORG_WH, "client.created", {"id": "c1"})


class TestCalendrierDeReessai:
    def test_delais_conformes(self):
        assert server_module._WEBHOOK_RETRY_DELAYS_SEC == (60, 300, 1800, 7200, 21600)

    def test_abandon_apres_la_cinquieme_tentative(self):
        assert server_module._webhook_next_attempt(5) is None

    def test_premier_reessai_a_une_minute(self):
        prochain = server_module._webhook_next_attempt(1)
        assert prochain is not None
        delta = datetime.fromisoformat(prochain) - datetime.now(timezone.utc)
        assert 50 <= delta.total_seconds() <= 70


class TestDecisionDeReessai:
    @pytest.mark.parametrize("code", [200, 201, 202, 204])
    def test_2xx_est_un_succes(self, code):
        assert server_module._webhook_should_retry(code) is False
        assert server_module._webhook_is_success(code) is True

    @pytest.mark.parametrize("code", [408, 429, 500, 502, 503, 504])
    def test_transitoire_est_reessaye(self, code):
        assert server_module._webhook_should_retry(code) is True

    @pytest.mark.parametrize("code", [400, 401, 403, 404, 410, 422])
    def test_4xx_definitif_n_est_pas_reessaye(self, code):
        """Inutile de marteler une cible qui refuse. 408 et 429 sont les seules exceptions."""
        assert server_module._webhook_should_retry(code) is False
        assert server_module._webhook_is_success(code) is False


class TestLivraison:
    def _file(self, endpoint, charge=None):
        did = str(uuid.uuid4())
        server_module.db.webhook_deliveries.insert_one({
            "id": did, "endpoint_id": endpoint, "event_id": "evt_test",
            # SÉPARATEURS COMPACTS, comme `_webhook_enqueue` en production. Avec les
            # séparateurs par défaut, un aller-retour json.loads/json.dumps est neutre et une
            # signature calculée sur une re-sérialisation passerait inaperçue — vérifié par
            # mutation : la fixture d'origine laissait ce défaut invisible.
            "payload": json.dumps(charge or {"id": "evt_test", "type": "client.created"},
                                  separators=(",", ":"), ensure_ascii=False),
            "status": "pending", "attempts": 0,
            "next_attempt_at": datetime.now(timezone.utc).isoformat(),
            "last_status_code": None, "last_error": None})
        return did

    def test_succes_marque_sent(self, endpoint, monkeypatch):
        envois = []

        class Rep:
            status_code = 200

        def _post(url, content=None, headers=None, timeout=None, **k):
            envois.append({"url": url, "content": content, "headers": headers})
            return Rep()
        monkeypatch.setattr(server_module.httpx, "post", _post)
        did = self._file(endpoint)
        server_module._webhook_deliver_due(limite=10)
        d = server_module.db.webhook_deliveries.find_one({"id": did})
        assert d["status"] == "sent"
        assert d["last_status_code"] == 200
        assert len(envois) == 1
        assert envois[0]["url"] == "https://pfm.test/hooks/facturepro"

    def test_le_corps_signe_est_exactement_le_corps_envoye(self, endpoint, monkeypatch):
        """LE test de sécurité. Signer une re-sérialisation rendrait la vérification
        impossible chez PFM : un espace de différence invalide le HMAC."""
        capture = {}

        class Rep:
            status_code = 200

        def _post(url, content=None, headers=None, timeout=None, **k):
            capture["content"] = content
            capture["headers"] = headers
            return Rep()
        monkeypatch.setattr(server_module.httpx, "post", _post)
        self._file(endpoint)
        server_module._webhook_deliver_due(limite=10)
        corps = capture["content"]
        if isinstance(corps, bytes):
            corps = corps.decode()
        entete = capture["headers"]["X-FacturePro-Signature"]
        assert server_module._webhook_signature_verify(corps, entete, SECRET) is True

    def test_500_replanifie_et_incremente(self, endpoint, monkeypatch):
        class Rep:
            status_code = 500
        monkeypatch.setattr(server_module.httpx, "post",
                            lambda *a, **k: Rep())
        did = self._file(endpoint)
        server_module._webhook_deliver_due(limite=10)
        d = server_module.db.webhook_deliveries.find_one({"id": did})
        assert d["status"] == "pending"
        assert d["attempts"] == 1
        assert d["next_attempt_at"] > datetime.now(timezone.utc).isoformat()
        assert d["last_status_code"] == 500

    def test_410_abandonne_immediatement(self, endpoint, monkeypatch):
        class Rep:
            status_code = 410
        monkeypatch.setattr(server_module.httpx, "post", lambda *a, **k: Rep())
        did = self._file(endpoint)
        server_module._webhook_deliver_due(limite=10)
        d = server_module.db.webhook_deliveries.find_one({"id": did})
        assert d["status"] == "failed"
        assert d["attempts"] == 1, "pas de réessai sur un 4xx définitif"

    def test_abandon_apres_cinq_tentatives(self, endpoint, monkeypatch):
        class Rep:
            status_code = 503
        monkeypatch.setattr(server_module.httpx, "post", lambda *a, **k: Rep())
        did = self._file(endpoint)
        server_module.db.webhook_deliveries.update_one(
            {"id": did}, {"$set": {"attempts": 4}})
        server_module._webhook_deliver_due(limite=10)
        d = server_module.db.webhook_deliveries.find_one({"id": did})
        assert d["attempts"] == 5
        assert d["status"] == "failed"
        assert d["last_error"], "l'erreur doit rester visible dans l'interface"

    def test_livraison_non_due_ignoree(self, endpoint, monkeypatch):
        appels = []
        monkeypatch.setattr(server_module.httpx, "post",
                            lambda *a, **k: appels.append(1))
        did = self._file(endpoint)
        futur = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        server_module.db.webhook_deliveries.update_one(
            {"id": did}, {"$set": {"next_attempt_at": futur}})
        server_module._webhook_deliver_due(limite=10)
        assert not appels

    def test_exception_reseau_replanifie(self, endpoint, monkeypatch):
        def _explose(*a, **k):
            raise RuntimeError("connexion refusée")
        monkeypatch.setattr(server_module.httpx, "post", _explose)
        did = self._file(endpoint)
        server_module._webhook_deliver_due(limite=10)
        d = server_module.db.webhook_deliveries.find_one({"id": did})
        assert d["status"] == "pending"
        assert d["attempts"] == 1
        assert d["last_error"]

    def test_le_secret_ne_fuit_jamais_dans_l_erreur(self, endpoint, monkeypatch):
        def _explose(*a, **k):
            raise RuntimeError(f"echec vers une cible avec secret {SECRET}")
        monkeypatch.setattr(server_module.httpx, "post", _explose)
        did = self._file(endpoint)
        server_module._webhook_deliver_due(limite=10)
        d = server_module.db.webhook_deliveries.find_one({"id": did})
        assert SECRET not in str(d), "le secret de l'endpoint ne doit JAMAIS être journalisé"


class TestEndpointsGestion:
    @pytest.fixture
    def cli(self):
        from fastapi.testclient import TestClient
        c = TestClient(server_module.app)
        r = c.post("/api/auth/login",
                   json={"email": "gussdub@gmail.com", "password": "testpass123"})
        assert r.status_code == 200, r.text
        return c, {"Authorization": f"Bearer {r.json()['access_token']}"}

    @pytest.fixture(autouse=True)
    def _menage(self):
        yield
        for ep in server_module.db.webhook_endpoints.find({"url": {"$regex": "^https://test-wh"}}):
            server_module.db.webhook_deliveries.delete_many({"endpoint_id": ep["id"]})
        server_module.db.webhook_endpoints.delete_many({"url": {"$regex": "^https://test-wh"}})

    def test_creation_renvoie_le_secret_une_seule_fois(self, cli):
        c, h = cli
        r = c.post("/api/org/webhooks",
                   json={"url": "https://test-wh.example/hook", "events": ["client.created"]},
                   headers=h)
        assert r.status_code == 201, r.text
        assert r.json()["secret"].startswith("whsec_")
        liste = c.get("/api/org/webhooks", headers=h).json()["data"]
        ligne = next(e for e in liste if e["id"] == r.json()["id"])
        assert "secret" not in ligne, "le secret ne doit JAMAIS ressortir de la liste"

    def test_http_simple_refuse(self, cli):
        """Le corps contient des renseignements de clients. La signature authentifie
        l'expéditeur, elle ne chiffre rien."""
        c, h = cli
        r = c.post("/api/org/webhooks",
                   json={"url": "http://test-wh.example/hook", "events": ["client.created"]},
                   headers=h)
        assert r.status_code == 400

    def test_evenement_inconnu_refuse(self, cli):
        c, h = cli
        r = c.post("/api/org/webhooks",
                   json={"url": "https://test-wh.example/hook",
                         "events": ["client.created", "chose.inventee"]},
                   headers=h)
        assert r.status_code == 400

    def test_ping_met_en_file_sans_envoyer(self, cli, monkeypatch):
        """Même chemin que les vrais événements. Un ping synchrone mentirait sur le
        comportement réel — et resterait bloqué sur une cible froide."""
        def _interdit(*a, **k):
            raise AssertionError("le ping ne doit pas envoyer sur le chemin de requête")
        monkeypatch.setattr(server_module.httpx, "post", _interdit)
        c, h = cli
        eid = c.post("/api/org/webhooks",
                     json={"url": "https://test-wh.example/hook",
                           "events": ["client.created"]}, headers=h).json()["id"]
        r = c.post(f"/api/org/webhooks/{eid}/test", headers=h)
        assert r.status_code == 200, r.text
        d = server_module.db.webhook_deliveries.find_one({"id": r.json()["delivery_id"]})
        assert d["status"] == "pending"
        assert json.loads(d["payload"])["type"] == "ping"

    def test_isolation_entre_organisations(self, cli):
        c, h = cli
        etranger = str(uuid.uuid4())
        server_module.db.webhook_endpoints.insert_one({
            "id": etranger, "organization_id": "org-tierce-wh",
            "url": "https://test-wh-etranger.example/h", "secret": "whsec_x",
            "events": ["client.created"], "actif": True,
            "created_at": "2026-01-01T00:00:00+00:00",
            "last_success_at": None, "last_error": None})
        try:
            ids = {e["id"] for e in c.get("/api/org/webhooks", headers=h).json()["data"]}
            assert etranger not in ids
            assert c.delete(f"/api/org/webhooks/{etranger}", headers=h).status_code == 404
            assert c.post(f"/api/org/webhooks/{etranger}/test", headers=h).status_code == 404
        finally:
            server_module.db.webhook_endpoints.delete_one({"id": etranger})

    def test_non_proprietaire_refuse(self, cli):
        c, h = cli
        me = c.get("/api/auth/me", headers=h).json()
        oid = me["organization_id"]
        org = server_module.db.organizations.find_one({"id": oid}, {"_id": 0, "owner_id": 1})
        vrai = org["owner_id"]
        server_module.db.organizations.update_one({"id": oid}, {"$set": {"owner_id": "autre"}})
        try:
            assert c.get("/api/org/webhooks", headers=h).status_code == 403
            assert c.post("/api/org/webhooks",
                          json={"url": "https://test-wh.example/h",
                                "events": ["client.created"]}, headers=h).status_code == 403
        finally:
            server_module.db.organizations.update_one({"id": oid}, {"$set": {"owner_id": vrai}})


class TestEmissionBoutEnBout:
    """Preuve que les vrais chemins d'écriture émettent. Les tests de la machinerie ne
    prouvent que la machinerie."""

    @pytest.fixture
    def cli_et_endpoint(self):
        from fastapi.testclient import TestClient
        c = TestClient(server_module.app)
        r = c.post("/api/auth/login",
                   json={"email": "gussdub@gmail.com", "password": "testpass123"})
        h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        org = c.get("/api/auth/me", headers=h).json()["organization_id"]
        eid = str(uuid.uuid4())
        server_module.db.webhook_endpoints.insert_one({
            "id": eid, "organization_id": org, "url": "https://test-wh-e2e.example/h",
            "secret": SECRET,
            "events": list(server_module._WEBHOOK_EVENTS), "actif": True,
            "created_at": "2026-01-01T00:00:00+00:00",
            "last_success_at": None, "last_error": None})
        yield c, h, eid
        server_module.db.webhook_deliveries.delete_many({"endpoint_id": eid})
        server_module.db.webhook_endpoints.delete_one({"id": eid})

    def _types(self, eid):
        return [json.loads(d["payload"])["type"]
                for d in server_module.db.webhook_deliveries.find({"endpoint_id": eid})]

    def test_creation_client_emet(self, cli_et_endpoint, monkeypatch):
        monkeypatch.setattr(server_module.httpx, "post",
                            lambda *a, **k: (_ for _ in ()).throw(
                                AssertionError("pas d'envoi synchrone")))
        c, h, eid = cli_et_endpoint
        r = c.post("/api/clients", json={"name": "Client webhook e2e"}, headers=h)
        assert r.status_code in (200, 201), r.text
        cid = r.json()["id"]
        try:
            assert "client.created" in self._types(eid)
            charge = next(json.loads(d["payload"])
                          for d in server_module.db.webhook_deliveries.find({"endpoint_id": eid})
                          if json.loads(d["payload"])["type"] == "client.created")
            # §6.3 : `data` est le MÊME objet que l'endpoint de lecture.
            assert set(charge["data"].keys()) == {
                "id", "name", "email", "phone", "address", "city", "postal_code",
                "province", "created_at", "updated_at"}
            assert charge["data"]["id"] == cid
        finally:
            server_module.db.clients.delete_one({"id": cid})

    def test_modification_client_emet(self, cli_et_endpoint):
        c, h, eid = cli_et_endpoint
        cid = c.post("/api/clients", json={"name": "À modifier"}, headers=h).json()["id"]
        try:
            c.put(f"/api/clients/{cid}", json={"name": "Modifié"}, headers=h)
            assert "client.updated" in self._types(eid)
        finally:
            server_module.db.clients.delete_one({"id": cid})

    def test_creation_echoue_pas_si_le_webhook_casse(self, cli_et_endpoint, monkeypatch):
        """LE test de robustesse. Une cible lente ou une file en panne ne doit JAMAIS faire
        échouer la création du client dans FacturePro."""
        def _explose(*a, **k):
            raise RuntimeError("file indisponible")
        monkeypatch.setattr(server_module.db.webhook_deliveries, "insert_one", _explose)
        c, h, eid = cli_et_endpoint
        r = c.post("/api/clients", json={"name": "Client malgre panne"}, headers=h)
        assert r.status_code in (200, 201), r.text
        try:
            assert server_module.db.clients.find_one({"id": r.json()["id"]}) is not None
        finally:
            server_module.db.clients.delete_one({"id": r.json()["id"]})
