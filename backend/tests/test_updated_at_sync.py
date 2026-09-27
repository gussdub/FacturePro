"""`updated_at` sur clients / quotes / invoices — lot 0 de l'intégration ProFireManager.

Sans ce champ, la resynchronisation incrémentale de PFM (« donne-moi ce qui a changé depuis
telle date ») est impossible, et le filet de sécurité prévu côté PFM ne fonctionne pas.

Le test de garde ci-dessous est le cœur du lot : il échoue si QUELQU'UN écrit un jour dans ces
trois collections sans passer par les helpers. Un site oublié ne casse rien visiblement — le
document cesse simplement d'être resynchronisé, en silence. C'est exactement le genre de défaut
qu'un test doit rendre bruyant.
"""
import os as _os
import re as _re
import sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))

from datetime import datetime, timezone

import pytest
import server as server_module

_SERVER_PY = _os.path.join(_os.path.dirname(__file__), "..", "server.py")

# Collections dont `updated_at` doit rester à jour parce qu'elles sont exposées à PFM.
_TRACKED = ("clients", "quotes", "invoices")


def _source():
    with open(_SERVER_PY, encoding="utf-8") as fh:
        return fh.read()


class TestGardeAucuneEcritureDirecte:
    """Aucune écriture brute ne doit subsister : toutes passent par les helpers."""

    def test_aucun_insert_one_direct(self):
        src = _source()
        motif = _re.compile(r"\bdb\.(%s)\.insert_one\(" % "|".join(_TRACKED))
        trouves = [m.group(0) for m in motif.finditer(src)]
        assert not trouves, (
            "Écriture directe trouvée : %s. Utiliser _sync_insert_one(), sinon le document "
            "n'aura pas d'updated_at et cessera d'être resynchronisé vers PFM — en silence."
            % trouves)

    def test_aucun_update_one_direct(self):
        src = _source()
        motif = _re.compile(r"\bdb\.(%s)\.update_one\(" % "|".join(_TRACKED))
        trouves = [m.group(0) for m in motif.finditer(src)]
        assert not trouves, (
            "Écriture directe trouvée : %s. Utiliser _sync_update_one()." % trouves)

    def test_update_one_par_nom_variable_marque(self):
        """`db[nom].update_one(...)` échappe au motif littéral : le nom est une variable, donc
        la collection visée est indécidable statiquement. Ces sites doivent porter un
        `# [sync-ok]`, qui atteste que la question a été tranchée."""
        src = _source().split("\n")
        motif = _re.compile(r"\bdb\[[^\]]+\]\.(insert_one|update_one)\(")
        non_marques = []
        for i, ligne in enumerate(src):
            if not motif.search(ligne):
                continue
            if "[sync-ok]" not in "\n".join(src[max(0, i - 4):i + 1]):
                non_marques.append(f"l.{i + 1}: {ligne.strip()[:70]}")
        assert not non_marques, (
            "Écriture par nom variable sans marqueur [sync-ok] : %s" % non_marques)

    def test_aucune_ecriture_en_masse_non_marquee(self):
        """Les écritures en masse ne passent pas par les helpers. Chacune doit donc porter un
        marqueur `# [sync-ok]` dans les 3 lignes qui la précèdent, attestant qu'elle pose
        `updated_at` elle-même. La migration de remplissage est le seul cas légitime
        aujourd'hui. Le marqueur force quiconque en ajoute une à y réfléchir."""
        src = _source().split("\n")
        # Trois formes doivent etre couvertes :
        #   db.clients.update_many(...)   nom litteral, collection suivie
        #   db[coll].update_many(...)     nom VARIABLE, indecidable statiquement -> exige
        #   coll.update_many(...)         handle obtenu par _sync_collection()
        # La forme entre crochets echappait au motif initial, et SIX sites reels ecrivaient
        # ainsi dans les collections suivies : migrations, auto-ecriture au grand livre,
        # effacement client. Trou trouve a l'etape 4.
        ops = r"(insert_many|update_many|replace_one|bulk_write|find_one_and_update)"
        motifs = [
            _re.compile(r"\bdb\.(%s)\.%s\(" % ("|".join(_TRACKED), ops)),
            _re.compile(r"\bdb\[[^\]]+\]\.%s\(" % ops),
            _re.compile(r"\bcoll\.%s\(" % ops),
        ]
        non_marques = []
        for i, ligne in enumerate(src):
            if not any(m.search(ligne) for m in motifs):
                continue
            contexte = "\n".join(src[max(0, i - 3):i + 1])
            if "[sync-ok]" not in contexte:
                non_marques.append(f"l.{i + 1}: {ligne.strip()[:70]}")
        assert not non_marques, (
            "Écriture en masse sans marqueur [sync-ok] : %s. Elle doit poser updated_at "
            "elle-même, et le déclarer." % non_marques)


class TestHelpers:
    def test_insert_pose_updated_at(self, monkeypatch):
        capture = {}
        monkeypatch.setattr(server_module._sync_collection("clients"), "insert_one",
                            lambda doc, *a, **k: capture.update(doc=doc))
        server_module._sync_insert_one("clients", {"id": "c1", "name": "X"})
        assert capture["doc"]["updated_at"]
        # ISO 8601 UTC avec suffixe Z ou décalage explicite — le contrat PFM exige de l'UTC.
        datetime.fromisoformat(capture["doc"]["updated_at"])

    def test_insert_pose_aussi_created_at_si_absent(self, monkeypatch):
        capture = {}
        monkeypatch.setattr(server_module._sync_collection("clients"), "insert_one",
                            lambda doc, *a, **k: capture.update(doc=doc))
        server_module._sync_insert_one("clients", {"id": "c1"})
        assert capture["doc"]["created_at"] == capture["doc"]["updated_at"]

    def test_insert_ne_met_pas_created_at_existant(self, monkeypatch):
        capture = {}
        monkeypatch.setattr(server_module._sync_collection("clients"), "insert_one",
                            lambda doc, *a, **k: capture.update(doc=doc))
        server_module._sync_insert_one("clients", {"id": "c1", "created_at": "2020-01-01T00:00:00+00:00"})
        assert capture["doc"]["created_at"] == "2020-01-01T00:00:00+00:00"

    def test_insert_ne_mute_pas_l_appelant(self, monkeypatch):
        monkeypatch.setattr(server_module._sync_collection("clients"), "insert_one",
                            lambda doc, *a, **k: None)
        original = {"id": "c1"}
        server_module._sync_insert_one("clients", original)
        assert "updated_at" not in original, "le dict de l'appelant ne doit pas être modifié"

    def test_update_avec_set_ajoute_updated_at(self, monkeypatch):
        capture = {}
        monkeypatch.setattr(server_module._sync_collection("invoices"), "update_one",
                            lambda f, u, *a, **k: capture.update(filtre=f, upd=u))
        server_module._sync_update_one("invoices", {"id": "i1"}, {"$set": {"status": "paid"}})
        assert capture["upd"]["$set"]["status"] == "paid"
        assert capture["upd"]["$set"]["updated_at"]

    def test_update_push_seul_recoit_un_set(self, monkeypatch):
        """4 sites réels poussent dans `payments` SANS $set. Un paiement change l'état payé de
        la facture, donc PFM doit le voir : le helper doit créer le $set au besoin."""
        capture = {}
        monkeypatch.setattr(server_module._sync_collection("invoices"), "update_one",
                            lambda f, u, *a, **k: capture.update(upd=u))
        server_module._sync_update_one("invoices", {"id": "i1"},
                                       {"$push": {"payments": {"amount": 10}}})
        assert capture["upd"]["$push"]["payments"] == {"amount": 10}
        assert capture["upd"]["$set"]["updated_at"], "le $set doit être créé s'il manque"

    def test_update_ne_mute_pas_l_appelant(self, monkeypatch):
        monkeypatch.setattr(server_module._sync_collection("invoices"), "update_one",
                            lambda f, u, *a, **k: None)
        original = {"$set": {"status": "paid"}}
        server_module._sync_update_one("invoices", {"id": "i1"}, original)
        assert "updated_at" not in original["$set"]

    def test_update_renvoie_le_resultat(self, monkeypatch):
        """4 sites lisent `result.matched_count` : le helper doit rendre l'objet tel quel."""
        sentinelle = object()
        monkeypatch.setattr(server_module._sync_collection("invoices"), "update_one",
                            lambda f, u, *a, **k: sentinelle)
        assert server_module._sync_update_one(
            "invoices", {"id": "i1"}, {"$set": {"x": 1}}) is sentinelle

    def test_collection_inconnue_refusee(self):
        """Fail-closed : une faute de frappe sur le nom ne doit pas écrire en silence."""
        with pytest.raises(ValueError):
            server_module._sync_insert_one("cleints", {"id": "c1"})


class TestMigrationRemplissage:
    """La migration remplit les documents antérieurs aux helpers."""

    def _coll(self):
        return server_module._sync_collection("clients")

    def test_remplit_depuis_created_at(self):
        cid = "test-updated-at-" + _os.urandom(6).hex()
        self._coll().insert_one({
            "id": cid, "organization_id": "org-test-ua", "name": "Test",
            "created_at": "2024-03-15T10:00:00+00:00"})
        try:
            server_module.migrate_updated_at_v1()
            doc = self._coll().find_one({"id": cid})
            assert doc["updated_at"] == "2024-03-15T10:00:00+00:00", (
                "updated_at doit valoir created_at, PAS l'heure du boot : dater les documents "
                "existants de « maintenant » les ferait tous ressortir comme modifiés à chaque "
                "resynchronisation suivante")
        finally:
            self._coll().delete_one({"id": cid})

    def test_sans_created_at_recoit_l_epoque_unix(self):
        """Un document sans created_at doit remonter dans la première resynchronisation,
        pas disparaître."""
        cid = "test-updated-at-" + _os.urandom(6).hex()
        self._coll().insert_one({"id": cid, "organization_id": "org-test-ua", "name": "Sans date"})
        try:
            server_module.migrate_updated_at_v1()
            doc = self._coll().find_one({"id": cid})
            assert doc["updated_at"].startswith("1970-01-01")
        finally:
            self._coll().delete_one({"id": cid})

    def test_idempotente_ne_reecrit_pas(self):
        """Rejouée au boot suivant, elle ne doit pas écraser un updated_at déjà posé —
        sinon chaque redémarrage ferait ressortir toute la base comme modifiée."""
        cid = "test-updated-at-" + _os.urandom(6).hex()
        self._coll().insert_one({
            "id": cid, "organization_id": "org-test-ua", "name": "Test",
            "created_at": "2024-03-15T10:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00"})
        try:
            server_module.migrate_updated_at_v1()
            assert self._coll().find_one({"id": cid})["updated_at"] == "2026-01-01T00:00:00+00:00"
        finally:
            self._coll().delete_one({"id": cid})

    def test_index_cree(self):
        """On SUPPRIME l'index avant de relancer la migration.

        Sans cette suppression, le test constate seulement que l'index existe en base — il
        passerait au vert même si la migration ne le créait plus du tout, parce qu'un run
        précédent l'a laissé là. Vérifié par mutation : la version sans suppression survivait
        au retrait de `create_index`.
        """
        cible = ("organization_id", "updated_at")

        def cles_de(name):
            idx = server_module._sync_collection(name).index_information()
            return {nom: tuple(k for k, _ in v["key"]) for nom, v in idx.items()}

        for name in ("clients", "quotes", "invoices"):
            coll = server_module._sync_collection(name)
            for nom, cles in cles_de(name).items():
                if cles == cible:
                    coll.drop_index(nom)
            assert cible not in cles_de(name).values(), f"{name} : index non supprimé"

        server_module.migrate_updated_at_v1()

        for name in ("clients", "quotes", "invoices"):
            assert cible in cles_de(name).values(), (
                f"{name} : la migration n'a pas recréé l'index de la requête updated_since")


class TestBoutEnBout:
    """Preuve que les VRAIS chemins d'écriture posent le champ.

    Le test de garde ne prouve que la forme du code. Celui-ci passe par l'API réelle : c'est lui
    qui tomberait si un helper posait le champ au mauvais endroit, ou pas du tout.
    """

    @pytest.fixture
    def client_api(self):
        from fastapi.testclient import TestClient
        c = TestClient(server_module.app)
        r = c.post("/api/auth/login",
                   json={"email": "gussdub@gmail.com", "password": "testpass123"})
        assert r.status_code == 200, r.text
        return c, {"Authorization": f"Bearer {r.json()['access_token']}"}

    def test_creation_client_pose_updated_at(self, client_api):
        c, h = client_api
        r = c.post("/api/clients", json={"name": "Test updated_at bout en bout"}, headers=h)
        assert r.status_code in (200, 201), r.text
        cid = r.json()["id"]
        try:
            doc = server_module._sync_collection("clients").find_one({"id": cid})
            assert doc["updated_at"], "aucun updated_at posé à la création"
            # Pas une égalité stricte : l'endpoint pose son propre created_at avec son propre
            # appel à now(), le helper pose le sien. Quelques microsecondes les séparent.
            # L'invariant qui compte est l'ordre.
            assert doc["updated_at"] >= doc["created_at"]
        finally:
            server_module._sync_collection("clients").delete_one({"id": cid})

    def test_modification_client_avance_updated_at(self, client_api):
        c, h = client_api
        r = c.post("/api/clients", json={"name": "Test avance"}, headers=h)
        cid = r.json()["id"]
        coll = server_module._sync_collection("clients")
        try:
            avant = coll.find_one({"id": cid})["updated_at"]
            # Forcer un écart lisible : on recule la valeur posée à la création.
            coll.update_one({"id": cid}, {"$set": {"updated_at": "2020-01-01T00:00:00+00:00"}})
            r2 = c.put(f"/api/clients/{cid}", json={"name": "Test avance MODIFIÉ"}, headers=h)
            assert r2.status_code == 200, r2.text
            apres = coll.find_one({"id": cid})["updated_at"]
            assert apres > "2020-01-01T00:00:00+00:00", (
                "updated_at n'a pas avancé lors de la modification — la resynchronisation "
                "incrémentale de PFM manquerait ce changement")
            assert apres >= avant
        finally:
            coll.delete_one({"id": cid})
