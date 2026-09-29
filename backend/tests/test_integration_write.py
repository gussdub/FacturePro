"""Création de soumission en brouillon par l'API — étape 4 du lot 0.

Quatre propriétés :

1. Le statut créé est TOUJOURS `draft`, quoi que demande l'appelant. PFM ne produit que des
   brouillons ; c'est le propriétaire qui ouvre, vérifie et envoie.
2. L'idempotence est obligatoire, pas un confort. PFM réessaiera sur délai dépassé — le réveil
   de Render le garantit — et sans elle chaque réessai créerait une soumission de plus.
3. Le défaut du endpoint public reste `pending`. Le frontend déployé le consomme.
4. `external_ref` est stocké tel quel et relu à l'identique.
"""
import hashlib
import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import server as server_module
from fastapi.testclient import TestClient

ORG_W = "org-ecriture-W"


def _cle(org_id, scopes):
    secret = server_module._api_key_generate_secret()
    kid = str(uuid.uuid4())
    server_module.db.api_keys.insert_one({
        "id": kid, "organization_id": org_id, "name": "TEST-ECRITURE",
        "key_prefix": server_module._api_key_prefix(secret),
        "key_hash": hashlib.sha256(secret.encode()).hexdigest(),
        "scopes": list(scopes), "created_at": "2026-01-01T00:00:00+00:00",
        "created_by_user_id": "u", "last_used_at": None, "revoked_at": None})
    return kid, secret


@pytest.fixture
def ctx():
    server_module._API_KEY_RATE.clear()
    kid_w, sec_w = _cle(ORG_W, ["quotes:write", "quotes:read"])
    kid_r, sec_r = _cle(ORG_W, ["quotes:read"])
    cid = f"test-ecr-cli-{uuid.uuid4().hex[:6]}"
    server_module.db.clients.insert_one({
        "id": cid, "organization_id": ORG_W, "name": "Client écriture",
        "created_at": "2026-01-01T00:00:00+00:00", "updated_at": "2026-01-01T00:00:00+00:00"})
    yield {"ecriture": sec_w, "lecture_seule": sec_r, "client_id": cid}
    server_module.db.quotes.delete_many({"organization_id": ORG_W})
    server_module.db.clients.delete_one({"id": cid})
    server_module.db.api_keys.delete_many({"id": {"$in": [kid_w, kid_r]}})
    server_module.db.api_idempotency.delete_many({"organization_id": ORG_W})


@pytest.fixture
def client():
    return TestClient(server_module.app)


def _corps(client_id, **kw):
    c = {"client_id": client_id,
         "items": [{"description": "Renouvellement 2027", "quantity": 1, "unit_price": 840.0}],
         "valid_until": "2027-01-31",
         "external_ref": {"source": "profiremanager", "tenant_id": "t1", "periode": "2027"}}
    c.update(kw)
    return c


class TestStatutToujoursDraft:
    def test_creation_en_draft(self, client, ctx):
        r = client.post("/api/v1/integration/quotes", json=_corps(ctx["client_id"]),
                        headers={"X-API-Key": ctx["ecriture"]})
        assert r.status_code == 201, r.text
        assert r.json()["status"] == "draft"

    @pytest.mark.parametrize("demande", ["pending", "sent", "accepted", "converted"])
    def test_statut_demande_ignore(self, client, ctx, demande):
        """Quoi que demande l'appelant. Une soumission créée par l'API n'est JAMAIS envoyée
        automatiquement au client final."""
        r = client.post("/api/v1/integration/quotes",
                        json=_corps(ctx["client_id"], status=demande),
                        headers={"X-API-Key": ctx["ecriture"]})
        assert r.status_code == 201, r.text
        assert r.json()["status"] == "draft", f"statut « {demande} » accepté à tort"

    def test_scope_lecture_seule_refuse(self, client, ctx):
        r = client.post("/api/v1/integration/quotes", json=_corps(ctx["client_id"]),
                        headers={"X-API-Key": ctx["lecture_seule"]})
        assert r.status_code == 403


class TestDefautPublicInchange:
    def test_post_api_quotes_reste_pending(self, client):
        """NON-RÉGRESSION. Le frontend déployé consomme ce défaut : le changer casserait
        l'application en production."""
        r = client.post("/api/auth/login",
                        json={"email": "gussdub@gmail.com", "password": "testpass123"})
        h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        cree = client.post("/api/quotes", json={
            "client_id": "x", "items": [{"description": "d", "quantity": 1, "unit_price": 10}],
        }, headers=h)
        assert cree.status_code == 200, cree.text
        qid = cree.json()["id"]
        try:
            assert cree.json()["status"] == "pending"
        finally:
            server_module.db.quotes.delete_one({"id": qid})


class TestIdempotence:
    def test_meme_cle_une_seule_soumission(self, client, ctx):
        """LE test de l'étape. PFM réessaiera sur délai dépassé — Render s'endort après
        15 minutes et le premier appel prend 30 à 60 secondes. Sans idempotence, chaque
        réessai créerait une soumission de plus."""
        cle = f"pfm-{uuid.uuid4().hex}"
        h = {"X-API-Key": ctx["ecriture"], "Idempotency-Key": cle}
        r1 = client.post("/api/v1/integration/quotes", json=_corps(ctx["client_id"]), headers=h)
        r2 = client.post("/api/v1/integration/quotes", json=_corps(ctx["client_id"]), headers=h)
        assert r1.status_code == 201 and r2.status_code == 201
        assert r1.json() == r2.json(), "le rejeu doit rendre la réponse d'ORIGINE"
        assert server_module.db.quotes.count_documents({"organization_id": ORG_W}) == 1

    def test_cles_differentes_deux_soumissions(self, client, ctx):
        for _ in range(2):
            client.post("/api/v1/integration/quotes", json=_corps(ctx["client_id"]),
                        headers={"X-API-Key": ctx["ecriture"],
                                 "Idempotency-Key": f"pfm-{uuid.uuid4().hex}"})
        assert server_module.db.quotes.count_documents({"organization_id": ORG_W}) == 2

    def test_sans_cle_pas_de_deduplication(self, client, ctx):
        """Sans en-tête, chaque appel crée. C'est à PFM de fournir la clé ; on ne devine pas
        une intention de déduplication."""
        for _ in range(2):
            client.post("/api/v1/integration/quotes", json=_corps(ctx["client_id"]),
                        headers={"X-API-Key": ctx["ecriture"]})
        assert server_module.db.quotes.count_documents({"organization_id": ORG_W}) == 2

    def test_cle_cloisonnee_par_organisation(self, client, ctx):
        """La clé composite est (organization_id, idempotency_key). Deux organisations
        utilisant la même chaîne ne doivent pas se voler leurs réponses."""
        autre_kid, autre_sec = _cle("org-ecriture-AUTRE", ["quotes:write"])
        cid2 = f"test-ecr-cli2-{uuid.uuid4().hex[:6]}"
        server_module.db.clients.insert_one({
            "id": cid2, "organization_id": "org-ecriture-AUTRE", "name": "Autre",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00"})
        partagee = "meme-chaine-pour-les-deux"
        try:
            r1 = client.post("/api/v1/integration/quotes", json=_corps(ctx["client_id"]),
                             headers={"X-API-Key": ctx["ecriture"],
                                      "Idempotency-Key": partagee})
            r2 = client.post("/api/v1/integration/quotes", json=_corps(cid2),
                             headers={"X-API-Key": autre_sec, "Idempotency-Key": partagee})
            assert r1.status_code == 201 and r2.status_code == 201
            assert r1.json()["id"] != r2.json()["id"], "réponse volée entre organisations"
        finally:
            server_module.db.quotes.delete_many({"organization_id": "org-ecriture-AUTRE"})
            server_module.db.clients.delete_one({"id": cid2})
            server_module.db.api_keys.delete_one({"id": autre_kid})
            server_module.db.api_idempotency.delete_many(
                {"organization_id": "org-ecriture-AUTRE"})

    def test_purge_des_entrees_anciennes(self, ctx):
        """Les entrées de plus de 7 jours sont nettoyées."""
        vieille = {"organization_id": ORG_W, "idempotency_key": "vieille",
                   "response": {"id": "x"},
                   "created_at": "2020-01-01T00:00:00+00:00"}
        server_module.db.api_idempotency.insert_one(dict(vieille))
        server_module._api_idempotency_purge()
        assert server_module.db.api_idempotency.find_one(
            {"organization_id": ORG_W, "idempotency_key": "vieille"}) is None


class TestExternalRef:
    def test_stocke_et_relu_tel_quel(self, client, ctx):
        ref = {"source": "profiremanager", "tenant_id": "abc", "periode": "2027",
               "imbrique": {"libre": [1, 2, 3]}}
        r = client.post("/api/v1/integration/quotes",
                        json=_corps(ctx["client_id"], external_ref=ref),
                        headers={"X-API-Key": ctx["ecriture"]})
        assert r.status_code == 201, r.text
        qid = r.json()["id"]
        lu = client.get("/api/v1/integration/quotes?limit=500",
                        headers={"X-API-Key": ctx["ecriture"]}).json()["data"]
        doc = next(d for d in lu if d["id"] == qid)
        assert doc["external_ref"] == ref


class TestCalculs:
    def test_totaux_calcules_pas_pris_de_l_appelant(self, client, ctx):
        """Un appelant ne doit pas pouvoir dicter un total : il serait faux vis-à-vis des
        lignes, et c'est FacturePro qui fait foi sur les taxes."""
        r = client.post("/api/v1/integration/quotes",
                        json=_corps(ctx["client_id"], total=1.0, subtotal=1.0, total_tax=0.0),
                        headers={"X-API-Key": ctx["ecriture"]})
        assert r.status_code == 201, r.text
        corps = r.json()
        assert corps["subtotal"] == 840.0
        assert corps["total"] > 840.0, "les taxes doivent être calculées"

    def test_client_inconnu_refuse(self, client, ctx):
        r = client.post("/api/v1/integration/quotes",
                        json=_corps("client-qui-n-existe-pas"),
                        headers={"X-API-Key": ctx["ecriture"]})
        assert r.status_code == 404

    def test_client_d_une_autre_organisation_refuse(self, client, ctx):
        """Le client est résolu dans l'organisation DE LA CLÉ."""
        etranger = f"test-ecr-etr-{uuid.uuid4().hex[:6]}"
        server_module.db.clients.insert_one({
            "id": etranger, "organization_id": "org-tierce", "name": "Étranger",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00"})
        try:
            r = client.post("/api/v1/integration/quotes", json=_corps(etranger),
                            headers={"X-API-Key": ctx["ecriture"]})
            assert r.status_code == 404
        finally:
            server_module.db.clients.delete_one({"id": etranger})

    def test_items_vides_refuses(self, client, ctx):
        r = client.post("/api/v1/integration/quotes",
                        json=_corps(ctx["client_id"], items=[]),
                        headers={"X-API-Key": ctx["ecriture"]})
        assert r.status_code == 422

    def test_numero_unique_sur_creations_successives(self, client, ctx):
        """`quote_number` était dérivé de count_documents() + 1 : après une suppression, le
        compteur recule et le numéro collisionne. Le passage à max + 1 corrige cette
        collision latente, que la création par programme rendrait fréquente."""
        nums = []
        for _ in range(3):
            r = client.post("/api/v1/integration/quotes", json=_corps(ctx["client_id"]),
                            headers={"X-API-Key": ctx["ecriture"]})
            nums.append(r.json()["quote_number"])
        assert len(set(nums)) == 3, f"numéros collisionnés : {nums}"


class TestBrouillonsExclusDuTableauDeBord:
    def test_total_quotes_exclut_les_brouillons(self):
        """Une soumission en brouillon est une proposition en attente de revue, pas une
        soumission remise à un client. Aucune n'existe aujourd'hui (0/138), donc cette
        exclusion ne change rien à l'affichage actuel.

        NOTE : `total_invoices` compte les 104 factures en brouillon. Incohérence
        PRÉÉXISTANTE, délibérément non touchée — le tableau de bord déployé l'affiche ainsi.
        """
        org = f"org-stats-{uuid.uuid4().hex[:6]}"
        ids = []
        for st in ("pending", "draft", "accepted"):
            qid = f"test-stats-{st}-{uuid.uuid4().hex[:6]}"
            ids.append(qid)
            server_module.db.quotes.insert_one({
                "id": qid, "organization_id": org, "status": st, "total": 10.0,
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00"})
        try:
            assert server_module._stats_quote_filter({"organization_id": org}) is not None
            n = server_module.db.quotes.count_documents(
                server_module._stats_quote_filter({"organization_id": org}))
            assert n == 2, f"attendu 2 (pending + accepted), obtenu {n}"
        finally:
            server_module.db.quotes.delete_many({"id": {"$in": ids}})


class TestProvinceEtTaxes:
    """Lot D — questions (b) de PFM sur les taxes.

    Le chemin PUBLIC prend la province du formulaire, par document. Mon endpoint
    d'intégration la prenait des réglages de l'organisation : divergence non documentée, et
    PFM n'avait aucun moyen de la contrôler. La province devient donc un paramètre optionnel
    du corps, avec repli sur les réglages.
    """

    @pytest.fixture
    def ctx_prov(self):
        server_module._API_KEY_RATE.clear()
        kid, sec = _cle(ORG_W, ["quotes:write", "quotes:read"])
        cid = f"test-prov-{uuid.uuid4().hex[:6]}"
        server_module.db.clients.insert_one({
            "id": cid, "organization_id": ORG_W, "name": "Client province",
            "created_at": "2026-01-01T00:00:00+00:00", "updated_at": "2026-01-01T00:00:00+00:00"})
        server_module.db.company_settings.insert_one({
            "id": f"st-{uuid.uuid4().hex[:6]}", "organization_id": ORG_W, "province": "QC"})
        yield sec, cid
        server_module.db.quotes.delete_many({"organization_id": ORG_W})
        server_module.db.clients.delete_one({"id": cid})
        server_module.db.company_settings.delete_many({"organization_id": ORG_W})
        server_module.db.api_keys.delete_one({"id": kid})
        server_module.db.api_idempotency.delete_many({"organization_id": ORG_W})

    def test_total_egale_subtotal_plus_taxes(self, client, ctx_prov):
        sec, cid = ctx_prov
        r = client.post("/api/v1/integration/quotes", json=_corps(cid),
                        headers={"X-API-Key": sec})
        assert r.status_code == 201, r.text
        c = r.json()
        assert c["subtotal"] == 840.0
        assert c["total"] == pytest.approx(c["subtotal"] + c["total_tax"])
        assert c["total_tax"] == pytest.approx(125.79), "QC = 5 % TPS + 9,975 % TVQ"

    def test_province_du_corps_prioritaire(self, client, ctx_prov):
        """PFM doit pouvoir imposer la province, comme le fait le formulaire."""
        sec, cid = ctx_prov
        r = client.post("/api/v1/integration/quotes", json=_corps(cid, province="ON"),
                        headers={"X-API-Key": sec})
        assert r.status_code == 201, r.text
        assert r.json()["total_tax"] == pytest.approx(109.20), "ON = 13 % TVH"

    def test_repli_sur_les_reglages(self, client, ctx_prov):
        sec, cid = ctx_prov
        r = client.post("/api/v1/integration/quotes", json=_corps(cid),
                        headers={"X-API-Key": sec})
        assert r.json()["total_tax"] == pytest.approx(125.79)

    @pytest.mark.parametrize("mauvaise", ["Quebec", "quebec", "QUE", "XX", "Q", "ONT"])
    def test_province_invalide_refusee(self, client, ctx_prov, mauvaise):
        """RÉGRESSION. `calculate_taxes` retombe silencieusement sur 5 % de TPS pour toute
        valeur inconnue : « Quebec » au lieu de « QC » amputerait la taxe des deux tiers,
        sans erreur. Une soumission mal taxée part ensuite au client."""
        sec, cid = ctx_prov
        r = client.post("/api/v1/integration/quotes", json=_corps(cid, province=mauvaise),
                        headers={"X-API-Key": sec})
        assert r.status_code == 422, f"« {mauvaise} » accepté à tort"

    @pytest.mark.parametrize("vide", ["", "   ", None])
    def test_province_vide_retombe_sur_les_reglages(self, client, ctx_prov, vide):
        """Vide ou blanc = « non fournie ». Les deux doivent retomber, pas lever : sans
        rognage préalable, "" retombait mais "  " levait un 422 pour la même intention."""
        sec, cid = ctx_prov
        r = client.post("/api/v1/integration/quotes", json=_corps(cid, province=vide),
                        headers={"X-API-Key": sec})
        assert r.status_code == 201, r.text
        assert r.json()["total_tax"] == pytest.approx(125.79), "repli sur QC des réglages"

    def test_devise_toujours_cad(self, client, ctx_prov):
        """Question (c) de PFM : l'appelant ne peut pas imposer une devise."""
        sec, cid = ctx_prov
        r = client.post("/api/v1/integration/quotes", json=_corps(cid, currency="USD"),
                        headers={"X-API-Key": sec})
        assert r.status_code == 201, r.text
        assert r.json()["currency"] == "CAD"


class TestWebhookReactivation:
    """Lot D §4 — PFM doit poser le secret AVANT que les événements partent, sinon son
    endpoint répond 503 et les réessais abandonnent après ~8 h 45.

    Sans réactivation, désactiver l'endpoint le temps de la bascule était sans retour.
    """

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
        server_module.db.webhook_endpoints.delete_many(
            {"url": {"$regex": "^https://test-reactiv"}})

    def test_reactivation_apres_desactivation(self, cli):
        c, h = cli
        eid = c.post("/api/org/webhooks",
                     json={"url": "https://test-reactiv.example/h",
                           "events": ["client.created"]}, headers=h).json()["id"]
        assert c.delete(f"/api/org/webhooks/{eid}", headers=h).status_code == 204
        assert server_module.db.webhook_endpoints.find_one({"id": eid})["actif"] is False

        r = c.post(f"/api/org/webhooks/{eid}/enable", headers=h)
        assert r.status_code == 200, r.text
        assert server_module.db.webhook_endpoints.find_one({"id": eid})["actif"] is True

    def test_reactivation_efface_la_derniere_erreur(self, cli):
        """Une erreur d'une période où le secret n'était pas encore posé chez le
        destinataire ne doit pas rester affichée après la remise en service."""
        c, h = cli
        eid = c.post("/api/org/webhooks",
                     json={"url": "https://test-reactiv2.example/h",
                           "events": ["client.created"]}, headers=h).json()["id"]
        server_module.db.webhook_endpoints.update_one(
            {"id": eid}, {"$set": {"actif": False, "last_error": "HTTP 503"}})
        c.post(f"/api/org/webhooks/{eid}/enable", headers=h)
        ep = server_module.db.webhook_endpoints.find_one({"id": eid})
        assert ep["actif"] is True
        assert ep["last_error"] is None

    def test_reactivation_autre_organisation_404(self, cli):
        c, h = cli
        etranger = str(uuid.uuid4())
        server_module.db.webhook_endpoints.insert_one({
            "id": etranger, "organization_id": "org-tierce-reactiv",
            "url": "https://test-reactiv-etranger.example/h", "secret": "whsec_x",
            "events": ["client.created"], "actif": False,
            "created_at": "2026-01-01T00:00:00+00:00",
            "last_success_at": None, "last_error": None})
        try:
            assert c.post(f"/api/org/webhooks/{etranger}/enable",
                          headers=h).status_code == 404
        finally:
            server_module.db.webhook_endpoints.delete_one({"id": etranger})


class TestValidUntil:
    """Lot D — question (d) de PFM. `valid_until` n'était pas validée du tout.

    Le vrai danger n'est pas une date malformée, c'est une date PASSÉE : le brouillon arrive
    déjà expiré, Guillaume l'ouvre, l'envoie, et la caserne reçoit une soumission périmée.
    Une création par programme rend ce cas fréquent (décalage de fuseau, période mal calculée).

    Le chemin PUBLIC n'est délibérément PAS touché : un humain qui saisit une date passée peut
    le faire exprès (antidatage), et resserrer un formulaire déployé casserait son usage.
    """

    @pytest.fixture
    def ctx_vu(self):
        server_module._API_KEY_RATE.clear()
        kid, sec = _cle(ORG_W, ["quotes:write", "quotes:read"])
        cid = f"test-vu-{uuid.uuid4().hex[:6]}"
        server_module.db.clients.insert_one({
            "id": cid, "organization_id": ORG_W, "name": "Client valid_until",
            "created_at": "2026-01-01T00:00:00+00:00", "updated_at": "2026-01-01T00:00:00+00:00"})
        yield sec, cid
        server_module.db.quotes.delete_many({"organization_id": ORG_W})
        server_module.db.clients.delete_one({"id": cid})
        server_module.db.api_keys.delete_one({"id": kid})
        server_module.db.api_idempotency.delete_many({"organization_id": ORG_W})

    def _poste(self, client, sec, cid, **kw):
        return client.post("/api/v1/integration/quotes", json=_corps(cid, **kw),
                           headers={"X-API-Key": sec})

    def test_date_future_acceptee(self, client, ctx_vu):
        sec, cid = ctx_vu
        futur = (datetime.now(timezone.utc) + timedelta(days=90)).date().isoformat()
        r = self._poste(client, sec, cid, valid_until=futur)
        assert r.status_code == 201, r.text
        assert r.json()["valid_until"] == futur

    def test_aujourd_hui_accepte(self, client, ctx_vu):
        """Une soumission valide le jour même est légitime — la borne est le passé STRICT."""
        sec, cid = ctx_vu
        r = self._poste(client, sec, cid,
                        valid_until=datetime.now(timezone.utc).date().isoformat())
        assert r.status_code == 201, r.text

    def test_date_passee_refusee(self, client, ctx_vu):
        """LE cas qui compte : un brouillon déjà expiré à la création."""
        sec, cid = ctx_vu
        passe = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
        r = self._poste(client, sec, cid, valid_until=passe)
        assert r.status_code == 422, r.text
        assert "valid_until" in r.text

    @pytest.mark.parametrize("mauvaise", ["31/01/2027", "2027-13-01", "2027-02-30",
                                          "demain", "2027", "janvier"])
    def test_format_invalide_refuse(self, client, ctx_vu, mauvaise):
        sec, cid = ctx_vu
        assert self._poste(client, sec, cid, valid_until=mauvaise).status_code == 422

    def test_forme_compacte_normalisee(self, client, ctx_vu):
        """`date.fromisoformat` accepte « 20270131 » en Python 3.11. Stockée telle quelle, PFM
        relirait un format différent de celui du contrat. On normalise en AAAA-MM-JJ."""
        sec, cid = ctx_vu
        futur = datetime.now(timezone.utc) + timedelta(days=200)
        r = self._poste(client, sec, cid, valid_until=futur.strftime("%Y%m%d"))
        assert r.status_code == 201, r.text
        assert r.json()["valid_until"] == futur.date().isoformat()

    def test_trop_loin_refusee(self, client, ctx_vu):
        """Borne haute contre la faute de frappe d'année (« 20270 »). Une soumission valide
        dix ans n'a pas de sens commercial."""
        sec, cid = ctx_vu
        loin = (datetime.now(timezone.utc) + timedelta(days=365 * 6)).date().isoformat()
        r = self._poste(client, sec, cid, valid_until=loin)
        assert r.status_code == 422, r.text

    @pytest.mark.parametrize("vide", ["", "   ", None])
    def test_omise_reste_acceptee(self, client, ctx_vu, vide):
        """Rétrocompatible : une soumission sans date de validité est légitime (offre
        ouverte). Omise, elle reste vide — pas de 422, pas de défaut inventé."""
        sec, cid = ctx_vu
        r = self._poste(client, sec, cid, valid_until=vide)
        assert r.status_code == 201, r.text
        assert r.json()["valid_until"] == ""

    def test_chemin_public_non_touche(self, client):
        """NON-RÉGRESSION explicite : le formulaire déployé accepte toujours une date passée."""
        r = client.post("/api/auth/login",
                        json={"email": "gussdub@gmail.com", "password": "testpass123"})
        h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        cree = client.post("/api/quotes", json={
            "client_id": "x", "valid_until": "2020-01-01",
            "items": [{"description": "d", "quantity": 1, "unit_price": 10}]}, headers=h)
        assert cree.status_code == 200, cree.text
        try:
            assert cree.json()["valid_until"] == "2020-01-01"
        finally:
            server_module.db.quotes.delete_one({"id": cree.json()["id"]})
