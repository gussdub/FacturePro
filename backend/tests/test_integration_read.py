"""Endpoints de lecture versionnés — étape 3 du lot 0 (intégration ProFireManager).

Trois propriétés gouvernent ces endpoints :

1. Le scope vient de la CLÉ, jamais du corps ni de l'URL. Une clé de l'organisation A ne doit
   voir aucune donnée de B.
2. La pagination est un keyset, pas un décalage : parcourir un jeu plus grand que `limit` ne
   doit ni sauter ni dupliquer de document, même si la liste bouge pendant le parcours.
3. `items` n'est jamais exposé, et le contrat est une liste FERMÉE de champs — un champ ajouté
   au schéma ne doit pas fuiter dans l'API par accident.
"""
import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))

import hashlib
import uuid

import pytest
import server as server_module
from fastapi.testclient import TestClient

ORG_A = "org-lecture-A"
ORG_B = "org-lecture-B"


def _cree_cle(org_id, scopes):
    secret = server_module._api_key_generate_secret()
    kid = str(uuid.uuid4())
    server_module.db.api_keys.insert_one({
        "id": kid, "organization_id": org_id, "name": "TEST-LECTURE",
        "key_prefix": server_module._api_key_prefix(secret),
        "key_hash": hashlib.sha256(secret.encode()).hexdigest(),
        "scopes": list(scopes), "created_at": "2026-01-01T00:00:00+00:00",
        "created_by_user_id": "u", "last_used_at": None, "revoked_at": None})
    return kid, secret


@pytest.fixture
def jeu():
    """Deux organisations, des clients datés de façon contrôlée, et deux clés."""
    server_module._API_KEY_RATE.clear()
    kid_a, sec_a = _cree_cle(ORG_A, ["clients:read", "quotes:read", "invoices:read"])
    kid_b, sec_b = _cree_cle(ORG_B, ["clients:read"])
    ids_a = []
    for i in range(5):
        cid = f"test-lect-A-{i}-{uuid.uuid4().hex[:6]}"
        ids_a.append(cid)
        server_module.db.clients.insert_one({
            "id": cid, "organization_id": ORG_A, "name": f"Client A{i}",
            "email": f"a{i}@ex.test", "phone": None, "address": None, "city": None,
            "postal_code": None, "country": "CA",
            "created_at": f"2026-0{i + 1}-01T00:00:00+00:00",
            "updated_at": f"2026-0{i + 1}-01T00:00:00+00:00"})
    cid_b = f"test-lect-B-{uuid.uuid4().hex[:6]}"
    server_module.db.clients.insert_one({
        "id": cid_b, "organization_id": ORG_B, "name": "Client B secret",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00"})
    yield {"secret_a": sec_a, "secret_b": sec_b, "ids_a": ids_a, "id_b": cid_b}
    server_module.db.clients.delete_many({"id": {"$in": ids_a + [cid_b]}})
    server_module.db.api_keys.delete_many({"id": {"$in": [kid_a, kid_b]}})


@pytest.fixture
def client():
    return TestClient(server_module.app)


def _h(secret):
    return {"X-API-Key": secret}


class TestAuthentification:
    def test_sans_cle_401(self, client):
        assert client.get("/api/v1/integration/clients").status_code == 401

    def test_cle_invalide_401(self, client, jeu):
        r = client.get("/api/v1/integration/clients",
                       headers=_h("fp_live_inexistanteXXXXXXXX"))
        assert r.status_code == 401

    def test_scope_manquant_403(self, client, jeu):
        """La clé B n'a que clients:read."""
        r = client.get("/api/v1/integration/quotes", headers=_h(jeu["secret_b"]))
        assert r.status_code == 403

    def test_jwt_refuse_sur_endpoint_integration(self, client, jeu):
        """Un JWT ne doit PAS ouvrir la surface d'intégration : en-têtes distincts, chaînes
        distinctes. Sinon un jeton de session vaudrait clé API."""
        r = client.post("/api/auth/login",
                        json={"email": "gussdub@gmail.com", "password": "testpass123"})
        jwt = r.json()["access_token"]
        assert client.get("/api/v1/integration/clients",
                          headers={"Authorization": f"Bearer {jwt}"}).status_code == 401


class TestIsolationOrganisation:
    def test_la_cle_A_ne_voit_pas_B(self, client, jeu):
        r = client.get("/api/v1/integration/clients?limit=500", headers=_h(jeu["secret_a"]))
        assert r.status_code == 200, r.text
        ids = {c["id"] for c in r.json()["data"]}
        assert jeu["id_b"] not in ids
        assert set(jeu["ids_a"]) <= ids

    def test_le_scope_ne_vient_pas_de_l_url(self, client, jeu):
        """Un paramètre organization_id injecté ne doit rien changer."""
        r = client.get(f"/api/v1/integration/clients?organization_id={ORG_B}&limit=500",
                       headers=_h(jeu["secret_a"]))
        assert r.status_code == 200
        assert jeu["id_b"] not in {c["id"] for c in r.json()["data"]}


class TestContratDeChamps:
    def test_client_champs_exacts(self, client, jeu):
        r = client.get("/api/v1/integration/clients?limit=500", headers=_h(jeu["secret_a"]))
        doc = next(c for c in r.json()["data"] if c["id"] == jeu["ids_a"][0])
        assert set(doc.keys()) == {
            "id", "name", "email", "phone", "address", "city", "postal_code", "province",
            "created_at", "updated_at"}
        # §11.4 : le champ n'existe pas au schéma, il est exposé à null plutôt qu'inventé.
        assert doc["province"] is None

    def test_items_jamais_exposes(self, client, jeu):
        for chemin in ("quotes", "invoices"):
            r = client.get(f"/api/v1/integration/{chemin}?limit=5", headers=_h(jeu["secret_a"]))
            assert r.status_code == 200, r.text
            for d in r.json()["data"]:
                assert "items" not in d, f"{chemin} : items ne doit jamais sortir"

    def test_aucun_champ_interne_ne_fuit(self, client, jeu):
        """Le contrat est une liste FERMÉE. Un champ ajouté au schéma ne doit pas apparaître
        ici par accident — c'est ce qui rend la surface stable pour un client déployé."""
        interdits = {"_id", "user_id", "created_by_user_id", "items", "tax_registrations",
                     "notes", "recurrence", "sent_to", "key_hash"}
        for chemin in ("clients", "quotes", "invoices"):
            r = client.get(f"/api/v1/integration/{chemin}?limit=5", headers=_h(jeu["secret_a"]))
            for d in r.json()["data"]:
                fuites = interdits & set(d.keys())
                assert not fuites, f"{chemin} : champs internes exposés {fuites}"

    def test_facture_expose_amount_paid_calcule(self, client, jeu):
        """§11.2 : calculé depuis payments[].amount_cad, jamais persisté."""
        iid = f"test-lect-inv-{uuid.uuid4().hex[:6]}"
        server_module.db.invoices.insert_one({
            "id": iid, "organization_id": ORG_A, "client_id": "x",
            "invoice_number": "INV-T1", "status": "partial", "total": 100.0,
            "subtotal": 100.0, "total_tax": 0.0, "currency": "CAD",
            "payments": [{"amount_cad": 30.0}, {"amount_cad": 12.5}],
            "created_at": "2026-06-01T00:00:00+00:00",
            "updated_at": "2026-06-01T00:00:00+00:00"})
        try:
            r = client.get("/api/v1/integration/invoices?limit=500", headers=_h(jeu["secret_a"]))
            doc = next(d for d in r.json()["data"] if d["id"] == iid)
            assert doc["amount_paid"] == 42.5
            assert "payments" not in doc
        finally:
            server_module.db.invoices.delete_one({"id": iid})


class TestUpdatedSince:
    def test_filtre_sur_updated_at(self, client, jeu):
        r = client.get("/api/v1/integration/clients"
                       "?updated_since=2026-03-01T00:00:00Z&limit=500",
                       headers=_h(jeu["secret_a"]))
        assert r.status_code == 200, r.text
        vus = {c["id"] for c in r.json()["data"]}
        # ids_a[i] est daté 2026-0{i+1}-01 : seuls les indices 2, 3, 4 sont >= mars.
        assert jeu["ids_a"][0] not in vus and jeu["ids_a"][1] not in vus
        assert jeu["ids_a"][2] in vus and jeu["ids_a"][4] in vus

    def test_suffixe_Z_compare_correctement(self, client, jeu):
        """RÉGRESSION. `updated_at` est stocké suffixé « +00:00 », le contrat fait envoyer « Z ».
        Mongo compare ces valeurs comme des CHAÎNES, et « + » (0x2B) < « Z » (0x5A) :

            "2026-03-01T00:00:00+00:00" >= "2026-03-01T00:00:00Z"   ->   False

        Comparer la valeur brute faisait donc RATER des documents, en silence et pile à la
        frontière demandée. Les deux formes doivent rendre le même résultat.
        """
        avec_z = client.get("/api/v1/integration/clients"
                            "?updated_since=2026-03-01T00:00:00Z&limit=500",
                            headers=_h(jeu["secret_a"])).json()["data"]
        avec_offset = client.get("/api/v1/integration/clients"
                                 "?updated_since=2026-03-01T00:00:00%2B00:00&limit=500",
                                 headers=_h(jeu["secret_a"])).json()["data"]
        assert {c["id"] for c in avec_z} == {c["id"] for c in avec_offset}
        assert jeu["ids_a"][2] in {c["id"] for c in avec_z}, (
            "le document daté exactement de la borne doit être inclus ($gte)")

    def test_date_invalide_422(self, client, jeu):
        r = client.get("/api/v1/integration/clients?updated_since=pas-une-date",
                       headers=_h(jeu["secret_a"]))
        assert r.status_code == 422


class TestPagination:
    def test_limite_par_defaut_et_plafond(self, client, jeu):
        r = client.get("/api/v1/integration/clients?limit=9999", headers=_h(jeu["secret_a"]))
        assert r.status_code == 422, "une limite hors plage doit être refusée, pas silencieusement rabotée"

    def test_parcours_complet_sans_saut_ni_doublon(self, client, jeu):
        """LE test de la pagination. On parcourt par pages de 2 et on vérifie que l'ensemble
        obtenu est exactement celui d'une requête unique — ni document perdu, ni compté deux
        fois. C'est ce qu'un décalage numérique ne garantit pas quand la liste bouge."""
        tout = client.get("/api/v1/integration/clients?limit=500",
                          headers=_h(jeu["secret_a"])).json()["data"]
        attendu = [c["id"] for c in tout]

        vus, cursor, tours = [], None, 0
        while True:
            tours += 1
            assert tours < 200, "boucle de pagination non terminante"
            url = "/api/v1/integration/clients?limit=2"
            if cursor:
                url += f"&cursor={cursor}"
            page = client.get(url, headers=_h(jeu["secret_a"])).json()
            vus.extend(c["id"] for c in page["data"])
            cursor = page["next_cursor"]
            if not cursor:
                break
        assert vus == attendu, "ordre ou contenu divergent du parcours en une seule requête"
        assert len(vus) == len(set(vus)), "document dupliqué"

    def test_curseur_stable_malgre_insertion_en_cours(self, client, jeu):
        """Un document inséré entre deux pages ne doit pas décaler le parcours et faire sauter
        un document déjà attendu. C'est le défaut exact d'un décalage numérique."""
        p1 = client.get("/api/v1/integration/clients?limit=2",
                        headers=_h(jeu["secret_a"])).json()
        intrus = f"test-lect-A-intrus-{uuid.uuid4().hex[:6]}"
        server_module.db.clients.insert_one({
            "id": intrus, "organization_id": ORG_A, "name": "Intrus",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00"})   # date ANCIENNE, avant le curseur
        try:
            p2 = client.get(f"/api/v1/integration/clients?limit=2&cursor={p1['next_cursor']}",
                            headers=_h(jeu["secret_a"])).json()
            deja = {c["id"] for c in p1["data"]}
            assert not (deja & {c["id"] for c in p2["data"]}), "document redonné"
        finally:
            server_module.db.clients.delete_one({"id": intrus})

    def test_curseur_illisible_422(self, client, jeu):
        r = client.get("/api/v1/integration/clients?cursor=pas-du-base64!!",
                       headers=_h(jeu["secret_a"]))
        assert r.status_code == 422

    def test_curseur_null_en_fin_de_liste(self, client, jeu):
        r = client.get("/api/v1/integration/clients?limit=500", headers=_h(jeu["secret_a"]))
        assert r.json()["next_cursor"] is None

    def test_enveloppe_data_next_cursor(self, client, jeu):
        r = client.get("/api/v1/integration/clients?limit=2", headers=_h(jeu["secret_a"]))
        assert set(r.json().keys()) == {"data", "next_cursor"}


class TestBackfillOrganizationId:
    def test_backfill_attribue_les_documents_orphelins(self):
        """§11.5 : un document sans organization_id mais rattaché à un utilisateur connu doit
        recevoir l'organisation de cet utilisateur. Sinon il est invisible à une requête
        scopée strictement — celle de l'API."""
        u = server_module.db.users.find_one(
            {"organization_id": {"$ne": None}}, {"_id": 0, "id": 1, "organization_id": 1})
        assert u, "aucun utilisateur avec organisation en base de test"
        cid = f"test-backfill-{uuid.uuid4().hex[:6]}"
        server_module.db.clients.insert_one({
            "id": cid, "user_id": u["id"], "name": "Orphelin",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00"})
        try:
            assert "organization_id" not in server_module.db.clients.find_one({"id": cid})
            server_module.migrate_integration_org_backfill_v1()
            assert server_module.db.clients.find_one({"id": cid})["organization_id"] == \
                u["organization_id"]
        finally:
            server_module.db.clients.delete_one({"id": cid})

    def test_backfill_ne_touche_pas_un_utilisateur_inconnu(self):
        """Un document d'un utilisateur supprimé n'est revendiquable par aucune organisation.
        Le laisser tel quel est le seul choix honnête."""
        cid = f"test-backfill-orph-{uuid.uuid4().hex[:6]}"
        server_module.db.clients.insert_one({
            "id": cid, "user_id": "utilisateur-qui-n-existe-pas", "name": "Vrai orphelin",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00"})
        try:
            server_module.migrate_integration_org_backfill_v1()
            assert "organization_id" not in server_module.db.clients.find_one({"id": cid})
        finally:
            server_module.db.clients.delete_one({"id": cid})

    def test_backfill_n_ecrase_pas_une_organisation_existante(self):
        cid = f"test-backfill-ok-{uuid.uuid4().hex[:6]}"
        server_module.db.clients.insert_one({
            "id": cid, "user_id": "peu-importe", "organization_id": "org-deja-la",
            "name": "Déjà attribué", "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00"})
        try:
            server_module.migrate_integration_org_backfill_v1()
            assert server_module.db.clients.find_one({"id": cid})["organization_id"] == \
                "org-deja-la"
        finally:
            server_module.db.clients.delete_one({"id": cid})


class TestPaginationAvecDatesIdentiques:
    """Le cas qui compte vraiment.

    Le remplissage rétroactif de l'étape 1 a daté 339 documents avec leur `created_at`, et
    plusieurs partagent la même seconde. Sans départage par `id`, une page peut redonner les
    mêmes documents indéfiniment ou en sauter. Les tests à dates distinctes ne détectent PAS ce
    défaut — vérifié par mutation : retirer le départage les laissait tous au vert.
    """

    MEME_DATE = "2026-07-15T12:00:00+00:00"

    @pytest.fixture
    def jeu_ex_aequo(self):
        server_module._API_KEY_RATE.clear()
        kid, secret = _cree_cle(ORG_A, ["clients:read"])
        ids = []
        for i in range(7):
            cid = f"test-exaequo-{i}-{uuid.uuid4().hex[:6]}"
            ids.append(cid)
            server_module.db.clients.insert_one({
                "id": cid, "organization_id": ORG_A, "name": f"Ex aequo {i}",
                "created_at": self.MEME_DATE, "updated_at": self.MEME_DATE})
        yield secret, ids
        server_module.db.clients.delete_many({"id": {"$in": ids}})
        server_module.db.api_keys.delete_one({"id": kid})

    def test_parcours_complet_malgre_dates_identiques(self, client, jeu_ex_aequo):
        secret, ids = jeu_ex_aequo
        vus, cursor, tours = [], None, 0
        while True:
            tours += 1
            assert tours < 50, (
                "boucle de pagination non terminante — le curseur ne progresse pas quand "
                "plusieurs documents partagent la même updated_at")
            url = "/api/v1/integration/clients?limit=2"
            if cursor:
                url += f"&cursor={cursor}"
            page = client.get(url, headers=_h(secret)).json()
            vus.extend(c["id"] for c in page["data"])
            cursor = page["next_cursor"]
            if not cursor:
                break
        nos_ids = [i for i in vus if i.startswith("test-exaequo-")]
        assert len(nos_ids) == len(set(nos_ids)), f"document dupliqué : {nos_ids}"
        assert set(nos_ids) == set(ids), (
            f"documents manquants : {set(ids) - set(nos_ids)}")

    def test_ordre_total_stable(self, client, jeu_ex_aequo):
        """Deux parcours identiques doivent rendre le même ordre. Avec des dates ex aequo,
        seul un tri sur `(updated_at, id)` le garantit."""
        secret, _ = jeu_ex_aequo
        a = [c["id"] for c in client.get(
            "/api/v1/integration/clients?limit=500", headers=_h(secret)).json()["data"]]
        b = [c["id"] for c in client.get(
            "/api/v1/integration/clients?limit=500", headers=_h(secret)).json()["data"]]
        assert a == b


class TestTriCoherentAvecLeCurseur:
    """Le tri de la requête doit correspondre EXACTEMENT à ce que le curseur encode.

    Cas discriminant : des dates croissantes dont les `id` décroissent alphabétiquement. Un tri
    sur `id` seul est alors dans l'ordre INVERSE du filtre de curseur, qui porte d'abord sur
    `updated_at` — le parcours saute des documents.

    Ni les dates distinctes-mais-alignées, ni les dates toutes ex aequo ne détectent ce
    défaut : vérifié par mutation, un tri réduit à `id` survivait aux deux.
    """

    @pytest.fixture
    def jeu_inverse(self):
        server_module._API_KEY_RATE.clear()
        kid, secret = _cree_cle(ORG_A, ["clients:read"])
        # `id` DÉCROISSANT pendant que `updated_at` CROÎT.
        lettres = "zyxwvu"
        ids = []
        for i, lettre in enumerate(lettres):
            cid = f"test-inv-{lettre}-{uuid.uuid4().hex[:4]}"
            ids.append(cid)
            server_module.db.clients.insert_one({
                "id": cid, "organization_id": ORG_A, "name": f"Inverse {i}",
                "created_at": f"2027-0{i + 1}-01T00:00:00+00:00",
                "updated_at": f"2027-0{i + 1}-01T00:00:00+00:00"})
        yield secret, ids
        server_module.db.clients.delete_many({"id": {"$in": ids}})
        server_module.db.api_keys.delete_one({"id": kid})

    def test_parcours_ne_saute_aucun_document(self, client, jeu_inverse):
        secret, ids = jeu_inverse
        vus, cursor, tours = [], None, 0
        while True:
            tours += 1
            assert tours < 50, "boucle de pagination non terminante"
            url = "/api/v1/integration/clients?limit=2"
            if cursor:
                url += f"&cursor={cursor}"
            page = client.get(url, headers=_h(secret)).json()
            vus.extend(c["id"] for c in page["data"])
            cursor = page["next_cursor"]
            if not cursor:
                break
        nos = [i for i in vus if i.startswith("test-inv-")]
        assert set(nos) == set(ids), (
            f"documents sautés : {set(ids) - set(nos)} — le tri de la requête ne correspond "
            f"pas au filtre du curseur")
        assert len(nos) == len(set(nos)), "document dupliqué"

    def test_ordre_suit_updated_at_pas_id(self, client, jeu_inverse):
        secret, ids = jeu_inverse
        data = client.get("/api/v1/integration/clients?limit=500",
                          headers=_h(secret)).json()["data"]
        nos = [c for c in data if c["id"].startswith("test-inv-")]
        dates = [c["updated_at"] for c in nos]
        assert dates == sorted(dates), "l'ordre doit suivre updated_at, pas id"
