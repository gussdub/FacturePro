"""Tests unitaires — Grand livre Phase 2 : auto-posting (feature #12).

TDD. Chaque test crée ses données dans une org JETABLE (jamais le seed org
gussdub) et se nettoie en finally, pour ne pas salir la copie-prod locale
(pattern _setup_org/_cleanup de TestLedgerCrossOrgIsolation).

Backend requis : MongoDB local (MONGO_URL/.env). Le plan comptable est seedé
via _ensure_chart_seeded pour que _snapshot_lines résolve les account_id.
"""
import sys as _sys
import os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))

import uuid
import pytest
import pymongo

import server as server_module


def _make_org():
    """Crée une org jetable + seed du plan comptable. Renvoie (org_id, user_id)."""
    org_id = str(uuid.uuid4())
    user_id = f"ap-{uuid.uuid4().hex[:8]}"
    server_module._ensure_chart_seeded(org_id, user_id)
    return org_id, user_id


def _cleanup_org(org_id):
    server_module.db.chart_of_accounts.delete_many({"organization_id": org_id})
    server_module.db.journal_entries.delete_many({"organization_id": org_id})
    server_module.db.ledger_counters.delete_many({"organization_id": org_id})
    server_module.db.company_settings.delete_many({"organization_id": org_id})


def _account_id(org_id, account_number):
    acc = server_module.db.chart_of_accounts.find_one(
        {"organization_id": org_id, "account_number": account_number}, {"id": 1})
    assert acc, f"compte {account_number} non seedé pour {org_id}"
    return acc["id"]


class TestCreateJournalEntryThreadsSource:
    """Tâche 1 — _create_journal_entry doit threader source_type/source_id."""

    def test_create_journal_entry_threads_source(self):
        org_id, user_id = _make_org()
        try:
            lines = [
                {"account_id": _account_id(org_id, "1000"), "debit": 100, "credit": 0},
                {"account_id": _account_id(org_id, "4000"), "debit": 0, "credit": 100},
            ]
            entry = server_module._create_journal_entry(
                org_id, user_id, entry_date="2026-07-01", description="x",
                lines=lines, status="posted", entry_type="auto",
                source_type="invoice", source_id="inv-1",
            )
            # Retour de la factory
            assert entry["source_type"] == "invoice"
            assert entry["source_id"] == "inv-1"
            # Document réellement inséré dans journal_entries
            doc = server_module.db.journal_entries.find_one(
                {"id": entry["id"], "organization_id": org_id}, {"_id": 0})
            assert doc is not None
            assert doc["source_type"] == "invoice"
            assert doc["source_id"] == "inv-1"
            assert doc["entry_type"] == "auto"
        finally:
            _cleanup_org(org_id)

    def test_create_journal_entry_source_defaults_none(self):
        # Non-régression Phase 1 : sans passer les params, source_type/id = None.
        org_id, user_id = _make_org()
        try:
            lines = [
                {"account_id": _account_id(org_id, "1000"), "debit": 50, "credit": 0},
                {"account_id": _account_id(org_id, "4000"), "debit": 0, "credit": 50},
            ]
            entry = server_module._create_journal_entry(
                org_id, user_id, entry_date="2026-07-01", description="manuelle",
                lines=lines, status="posted",
            )
            assert entry["source_type"] is None
            assert entry["source_id"] is None
            doc = server_module.db.journal_entries.find_one(
                {"id": entry["id"], "organization_id": org_id}, {"_id": 0})
            assert doc["source_type"] is None
            assert doc["source_id"] is None
        finally:
            _cleanup_org(org_id)


class TestAutopostMigration:
    """Tâche 2 — migrate_general_ledger_autopost_v1 : flags org + index partiel."""

    def test_migration_seeds_autopost_settings(self):
        # Org SANS les champs → gagne les défauts (setdefault, pas d'écrasement).
        org_missing = str(uuid.uuid4())
        # Org qui a DÉJÀ autopost_enabled=True → NON écrasée (idempotence).
        org_preset = str(uuid.uuid4())
        try:
            server_module.db.company_settings.insert_one({
                "id": str(uuid.uuid4()),
                "organization_id": org_missing,
                "company_name": "Missing Co",
            })
            server_module.db.company_settings.insert_one({
                "id": str(uuid.uuid4()),
                "organization_id": org_preset,
                "company_name": "Preset Co",
                "autopost_enabled": True,
                "expense_default_credit_account": "2000",
            })

            server_module.migrate_general_ledger_autopost_v1(server_module.db)

            seeded = server_module.db.company_settings.find_one(
                {"organization_id": org_missing}, {"_id": 0})
            assert seeded["autopost_enabled"] is False
            assert seeded["expense_default_credit_account"] == "1000"

            preset = server_module.db.company_settings.find_one(
                {"organization_id": org_preset}, {"_id": 0})
            # Valeurs pré-existantes préservées — jamais écrasées.
            assert preset["autopost_enabled"] is True
            assert preset["expense_default_credit_account"] == "2000"
        finally:
            server_module.db.company_settings.delete_many(
                {"organization_id": {"$in": [org_missing, org_preset]}})

    def test_migration_rejouable(self):
        # Rejouer la migration deux fois ne change rien la 2e fois (idempotence).
        org_id = str(uuid.uuid4())
        try:
            server_module.db.company_settings.insert_one({
                "id": str(uuid.uuid4()),
                "organization_id": org_id,
                "company_name": "Replay Co",
            })
            server_module.migrate_general_ledger_autopost_v1(server_module.db)
            first = server_module.db.company_settings.find_one(
                {"organization_id": org_id}, {"_id": 0})
            # L'utilisateur bascule le flag après la 1re migration.
            server_module.db.company_settings.update_one(
                {"organization_id": org_id},
                {"$set": {"autopost_enabled": True}})
            server_module.migrate_general_ledger_autopost_v1(server_module.db)
            second = server_module.db.company_settings.find_one(
                {"organization_id": org_id}, {"_id": 0})
            assert first["autopost_enabled"] is False
            # 2e passage NE ré-écrase PAS le choix utilisateur.
            assert second["autopost_enabled"] is True
            assert second["expense_default_credit_account"] == "1000"
        finally:
            server_module.db.company_settings.delete_many({"organization_id": org_id})

    def test_autopost_unique_partial_index(self):
        # L'index unique partiel bloque un 2e post AUTO vivant même (org, source),
        # mais laisse passer un miroir reversal (hors du partialFilterExpression).
        org_id, user_id = _make_org()
        # S'assure que l'index existe (créé par la migration au boot ou ci-dessous).
        server_module.migrate_general_ledger_autopost_v1(server_module.db)
        try:
            base = {
                "organization_id": org_id,
                "source_type": "invoice",
                "source_id": "inv-dup",
                "entry_type": "auto",
                "reverses_entry_id": None,
                "reversed_by_entry_id": None,
            }
            server_module.db.journal_entries.insert_one(
                {**base, "id": str(uuid.uuid4()), "entry_number": "JE-D1"})
            # 2e écriture auto vivante, mêmes clés → DuplicateKeyError.
            with pytest.raises(pymongo.errors.DuplicateKeyError):
                server_module.db.journal_entries.insert_one(
                    {**base, "id": str(uuid.uuid4()), "entry_number": "JE-D2"})
            # Un miroir reversal avec les mêmes (org, source) est ACCEPTÉ
            # (entry_type != "auto" → hors du filtre partiel).
            mirror = {
                **base,
                "id": str(uuid.uuid4()),
                "entry_number": "JE-D3",
                "entry_type": "reversal",
                "reverses_entry_id": "some-live-id",
            }
            server_module.db.journal_entries.insert_one(mirror)
            count = server_module.db.journal_entries.count_documents(
                {"organization_id": org_id, "source_id": "inv-dup"})
            assert count == 2  # 1 auto vivant + 1 miroir reversal
        finally:
            _cleanup_org(org_id)

    def test_autopost_null_source_does_not_collide(self):
        # RÉGRESSION (problème #4) : deux écritures auto vivantes SANS source
        # réelle (source_type/source_id = None) NE doivent PAS entrer en collision
        # sur l'index partiel. L'ancien filtre {entry_type:auto, reverses_entry_id:
        # None} matchait la clé (org, null, null) et levait DuplicateKeyError dès le
        # 2e post auto à source nulle, cassant toute opération métier future qui
        # poste une écriture auto sans (source_type, source_id). Le filtre durci
        # (source_type/source_id de type string) les exclut de la contrainte.
        org_id, user_id = _make_org()
        server_module.migrate_general_ledger_autopost_v1(server_module.db)
        try:
            base = {
                "organization_id": org_id,
                "source_type": None,
                "source_id": None,
                "entry_type": "auto",
                "reverses_entry_id": None,
                "reversed_by_entry_id": None,
            }
            server_module.db.journal_entries.insert_one(
                {**base, "id": str(uuid.uuid4()), "entry_number": "JE-N1"})
            # 2e écriture auto à source nulle : ACCEPTÉE (hors du filtre partiel).
            server_module.db.journal_entries.insert_one(
                {**base, "id": str(uuid.uuid4()), "entry_number": "JE-N2"})
            count = server_module.db.journal_entries.count_documents(
                {"organization_id": org_id, "entry_type": "auto",
                 "source_type": None})
            assert count == 2  # aucune collision sur les auto à source nulle
        finally:
            _cleanup_org(org_id)

    def test_autopost_index_reconciles_stale_filter(self):
        # RÉGRESSION : si un index homonyme préexiste avec l'ANCIEN filtre partiel
        # (sans les gardes $type), la migration doit le réconcilier (drop+recreate)
        # au lieu de le laisser en place. Après migration, deux auto à source nulle
        # passent (preuve que le nouveau filtre est bien actif).
        stale_org = str(uuid.uuid4())
        try:
            # Force l'ancien index (spec obsolète) directement.
            try:
                server_module.db.journal_entries.drop_index("uniq_live_auto_source")
            except pymongo.errors.OperationFailure:
                pass
            server_module.db.journal_entries.create_index(
                [("organization_id", 1), ("source_type", 1), ("source_id", 1)],
                unique=True,
                partialFilterExpression={
                    "entry_type": "auto", "reverses_entry_id": None},
                name="uniq_live_auto_source",
            )
            # La migration doit détecter la spec obsolète et la remplacer.
            server_module.migrate_general_ledger_autopost_v1(server_module.db)
            info = server_module.db.journal_entries.index_information()
            pfe = dict(info["uniq_live_auto_source"]["partialFilterExpression"])
            assert pfe.get("source_type") == {"$type": "string"}
            assert pfe.get("source_id") == {"$type": "string"}
            # Et fonctionnellement : deux auto à source nulle ne collisionnent plus.
            base = {
                "organization_id": stale_org, "source_type": None,
                "source_id": None, "entry_type": "auto",
                "reverses_entry_id": None, "reversed_by_entry_id": None,
            }
            server_module.db.journal_entries.insert_one(
                {**base, "id": str(uuid.uuid4()), "entry_number": "JE-S1"})
            server_module.db.journal_entries.insert_one(
                {**base, "id": str(uuid.uuid4()), "entry_number": "JE-S2"})
        finally:
            server_module.db.journal_entries.delete_many(
                {"organization_id": stale_org})


class TestSourceEntryPrimitives:
    """Tâche 3 — _find_live_source_entry / _post_source_entry / _unpost_source_entry.

    La couche idempotente partagée (§6.1 du spec) : un doc source = une écriture
    auto vivante ; régénération = contre-passer + reposter. La contre-passation
    auto emprunte EXACTEMENT le même chemin que la manuelle (_reverse_entry_internal).
    """

    def _rev_lines(self, org_id):
        """Dr 1000 100 / Cr 4000 100 — écriture auto de test équilibrée."""
        return [
            {"account_id": _account_id(org_id, "1000"), "debit": 100, "credit": 0},
            {"account_id": _account_id(org_id, "4000"), "debit": 0, "credit": 100},
        ]

    def test_find_live_ignores_reversed(self):
        # Pose une écriture auto, contre-passe-la via _unpost_source_entry :
        # _find_live_source_entry retourne None. Après un nouveau _post_source_entry,
        # il retourne l'unique post vivant.
        org_id, user_id = _make_org()
        try:
            posted = server_module._post_source_entry(
                org_id, user_id, "invoice", "inv-flr",
                entry_date="2026-07-01", description="Facture flr",
                lines=self._rev_lines(org_id))
            assert posted is not None
            live = server_module._find_live_source_entry(org_id, "invoice", "inv-flr")
            assert live is not None
            assert live["id"] == posted["id"]

            # Contre-passe : plus aucune vivante.
            server_module._unpost_source_entry(org_id, user_id, "invoice", "inv-flr")
            assert server_module._find_live_source_entry(
                org_id, "invoice", "inv-flr") is None

            # Re-poste : nouvelle unique vivante, différente de l'ancienne.
            reposted = server_module._post_source_entry(
                org_id, user_id, "invoice", "inv-flr",
                entry_date="2026-07-02", description="Facture flr v2",
                lines=self._rev_lines(org_id))
            assert reposted is not None
            live2 = server_module._find_live_source_entry(
                org_id, "invoice", "inv-flr")
            assert live2 is not None
            assert live2["id"] == reposted["id"]
            assert live2["id"] != posted["id"]
            # Une seule vivante à la fois (index partiel + filtre).
            n_live = server_module.db.journal_entries.count_documents({
                "organization_id": org_id, "source_type": "invoice",
                "source_id": "inv-flr", "entry_type": "auto",
                "reversed_by_entry_id": None})
            assert n_live == 1
        finally:
            _cleanup_org(org_id)

    def test_post_source_entry_idempotent(self):
        # Deux appels _post_source_entry avec les mêmes (source_type, source_id) →
        # 1 seule écriture en base ; le 2e appel retourne None (no-op).
        org_id, user_id = _make_org()
        try:
            first = server_module._post_source_entry(
                org_id, user_id, "invoice", "inv-idem",
                entry_date="2026-07-01", description="Facture idem",
                lines=self._rev_lines(org_id))
            assert first is not None
            second = server_module._post_source_entry(
                org_id, user_id, "invoice", "inv-idem",
                entry_date="2026-07-01", description="Facture idem",
                lines=self._rev_lines(org_id))
            assert second is None  # no-op : une vivante existe déjà
            count = server_module.db.journal_entries.count_documents({
                "organization_id": org_id, "source_type": "invoice",
                "source_id": "inv-idem"})
            assert count == 1
        finally:
            _cleanup_org(org_id)

    def test_unpost_creates_mirror_net_zero(self):
        # Pose Dr 1000 100 / Cr 4000 100, contre-passe ; vérifie qu'un miroir
        # entry_type="reversal", reverses_entry_id == live["id"], source_type/
        # source_id conservés est créé ; que `live` gagne reversed_by_entry_id ;
        # et que _account_balance de 1000 et 4000 revient à 0.
        org_id, user_id = _make_org()
        try:
            live = server_module._post_source_entry(
                org_id, user_id, "invoice", "inv-nz",
                entry_date="2026-07-01", description="Facture nz",
                lines=self._rev_lines(org_id))
            assert live is not None
            acc_1000 = _account_id(org_id, "1000")
            acc_4000 = _account_id(org_id, "4000")
            # Après le post : 1000 (débit normal) = +100, 4000 (crédit normal) = +100.
            assert server_module._account_balance(org_id, acc_1000, "debit") == 100
            assert server_module._account_balance(org_id, acc_4000, "credit") == 100

            mirror = server_module._unpost_source_entry(
                org_id, user_id, "invoice", "inv-nz")
            assert mirror is not None
            assert mirror["entry_type"] == "reversal"
            assert mirror["reverses_entry_id"] == live["id"]
            # Le miroir conserve la traçabilité source.
            assert mirror["source_type"] == "invoice"
            assert mirror["source_id"] == "inv-nz"

            # L'origine reste posted mais gagne reversed_by_entry_id.
            origin = server_module.db.journal_entries.find_one(
                {"id": live["id"], "organization_id": org_id}, {"_id": 0})
            assert origin["status"] == "posted"
            assert origin["reversed_by_entry_id"] == mirror["id"]

            # Net zéro sur les deux comptes (les deux écritures comptent).
            assert server_module._account_balance(org_id, acc_1000, "debit") == 0
            assert server_module._account_balance(org_id, acc_4000, "credit") == 0
        finally:
            _cleanup_org(org_id)

    def test_unpost_noop_when_nothing(self):
        # _unpost_source_entry sur un source inexistant retourne None sans lever.
        org_id, user_id = _make_org()
        try:
            result = server_module._unpost_source_entry(
                org_id, user_id, "invoice", "inconnu-xyz")
            assert result is None
        finally:
            _cleanup_org(org_id)

    def test_unpost_no_double_mirror(self):
        # Contre-passer deux fois de suite → un seul miroir (2e appel no-op car
        # la vivante n'existe plus, déjà reversed_by_entry_id posé).
        org_id, user_id = _make_org()
        try:
            server_module._post_source_entry(
                org_id, user_id, "invoice", "inv-dbl",
                entry_date="2026-07-01", description="Facture dbl",
                lines=self._rev_lines(org_id))
            first_mirror = server_module._unpost_source_entry(
                org_id, user_id, "invoice", "inv-dbl")
            assert first_mirror is not None
            second_mirror = server_module._unpost_source_entry(
                org_id, user_id, "invoice", "inv-dbl")
            assert second_mirror is None  # no-op : plus de vivante à défaire
            n_reversal = server_module.db.journal_entries.count_documents({
                "organization_id": org_id, "source_type": "invoice",
                "source_id": "inv-dbl", "entry_type": "reversal"})
            assert n_reversal == 1  # un seul miroir
        finally:
            _cleanup_org(org_id)

    def test_unpost_isolated_by_org(self):
        # Isolation multi-tenant : une org B ne peut pas contre-passer l'écriture
        # auto d'une org A (même source_id). _find_live_source_entry filtre l'org.
        org_a, user_a = _make_org()
        org_b, user_b = _make_org()
        try:
            server_module._post_source_entry(
                org_a, user_a, "invoice", "inv-shared",
                entry_date="2026-07-01", description="Facture A",
                lines=self._rev_lines(org_a))
            # Org B tente de défaire le même source_id : rien à faire chez elle.
            assert server_module._unpost_source_entry(
                org_b, user_b, "invoice", "inv-shared") is None
            # L'écriture de A est intacte (toujours vivante).
            assert server_module._find_live_source_entry(
                org_a, "invoice", "inv-shared") is not None
        finally:
            _cleanup_org(org_a)
            _cleanup_org(org_b)


class TestSafeAutopost:
    """Tâche 4 — _safe_autopost : garde-fou robustesse (décision #6).

    L'auto-posting ne fait JAMAIS échouer l'opération métier : toute exception
    est avalée, un `autopost_error` GÉNÉRIQUE horodaté est posé sur le doc source
    (jamais `str(e)` — pattern anti-leak feature #8). Au succès, le champ est
    effacé. Le scope org est toujours appliqué à l'update.
    """

    def _make_source_doc(self, org_id, extra=None):
        """Insère un doc jetable dans `invoices` (collection source réelle)."""
        doc = {"id": f"inv-{uuid.uuid4().hex[:8]}", "organization_id": org_id}
        if extra:
            doc.update(extra)
        server_module.db.invoices.insert_one(dict(doc))
        return doc["id"]

    def test_safe_autopost_swallows_and_records(self):
        org_id = str(uuid.uuid4())
        inv_id = self._make_source_doc(org_id)
        try:
            # fn qui lève : _safe_autopost NE DOIT PAS propager.
            def _boom():
                raise RuntimeError("boom")

            # Ne lève pas.
            server_module._safe_autopost(
                _boom, "invoices", inv_id, {"organization_id": org_id})

            doc = server_module.db.invoices.find_one(
                {"id": inv_id, "organization_id": org_id}, {"_id": 0})
            assert doc is not None
            err = doc.get("autopost_error")
            assert isinstance(err, str) and err
            # Message générique horodaté : NE contient PAS le détail de l'exception.
            assert "boom" not in err
            assert "RuntimeError" not in err
        finally:
            server_module.db.invoices.delete_many({"organization_id": org_id})

    def test_safe_autopost_clears_on_success(self):
        org_id = str(uuid.uuid4())
        # Doc qui porte DÉJÀ un autopost_error d'un échec antérieur.
        inv_id = self._make_source_doc(
            org_id, extra={"autopost_error": "2026-01-01T00:00:00+00:00 — échec"})
        try:
            calls = {"n": 0}

            def _ok():
                calls["n"] += 1

            server_module._safe_autopost(
                _ok, "invoices", inv_id, {"organization_id": org_id})

            assert calls["n"] == 1  # fn a bien été exécutée
            doc = server_module.db.invoices.find_one(
                {"id": inv_id, "organization_id": org_id}, {"_id": 0})
            # $unset : le champ a disparu.
            assert "autopost_error" not in doc
        finally:
            server_module.db.invoices.delete_many({"organization_id": org_id})

    def test_safe_autopost_scoped_by_org(self):
        # Le doc d'une AUTRE org portant le même id n'est jamais touché
        # (org_scope appliqué à l'update).
        org_a = str(uuid.uuid4())
        org_b = str(uuid.uuid4())
        shared_id = f"inv-{uuid.uuid4().hex[:8]}"
        try:
            server_module.db.invoices.insert_one(
                {"id": shared_id, "organization_id": org_a})
            server_module.db.invoices.insert_one(
                {"id": shared_id, "organization_id": org_b})

            def _boom():
                raise RuntimeError("x")

            server_module._safe_autopost(
                _boom, "invoices", shared_id, {"organization_id": org_a})

            doc_a = server_module.db.invoices.find_one(
                {"id": shared_id, "organization_id": org_a}, {"_id": 0})
            doc_b = server_module.db.invoices.find_one(
                {"id": shared_id, "organization_id": org_b}, {"_id": 0})
            assert doc_a.get("autopost_error")           # org A marquée
            assert "autopost_error" not in doc_b         # org B intacte
        finally:
            server_module.db.invoices.delete_many(
                {"organization_id": {"$in": [org_a, org_b]}})


class TestResolveLedgerAccount:
    """Tâche 4 — _resolve_ledger_account : résolution de compte par numéro
    canonique avec seed lazy déclenché + création à la volée idempotente.
    """

    def test_resolve_ledger_account_seeds_and_finds(self):
        # Org qui n'a JAMAIS ouvert le GL (aucun compte) → _resolve_ledger_account
        # déclenche _ensure_chart_seeded puis retourne le compte 4000.
        org_id = str(uuid.uuid4())
        user_id = f"ap-{uuid.uuid4().hex[:8]}"
        try:
            assert server_module.db.chart_of_accounts.count_documents(
                {"organization_id": org_id}) == 0
            acc = server_module._resolve_ledger_account(org_id, user_id, "4000")
            assert acc is not None
            assert acc["account_number"] == "4000"
            assert acc["organization_id"] == org_id
            # Le plan a bien été seedé (lazy).
            assert server_module.db.chart_of_accounts.count_documents(
                {"organization_id": org_id}) > 0
        finally:
            _cleanup_org(org_id)

    def test_resolve_ledger_account_missing_returns_none(self):
        # Compte absent, sans create_if_missing → None (pas d'exception).
        org_id, user_id = _make_org()
        try:
            assert server_module._resolve_ledger_account(
                org_id, user_id, "9999") is None
        finally:
            _cleanup_org(org_id)

    def test_resolve_ledger_account_creates_on_the_fly(self):
        # 2120 absent du plan par défaut → créé à la volée (compte système).
        # Idempotent : un 2e appel ne duplique pas.
        org_id, user_id = _make_org()
        try:
            assert server_module.db.chart_of_accounts.find_one(
                {"organization_id": org_id, "account_number": "2120"}) is None

            acc = server_module._resolve_ledger_account(
                org_id, user_id, "2120", create_if_missing=True,
                kind="liability", name="TVH à payer")
            assert acc is not None
            assert acc["account_number"] == "2120"
            assert acc["account_type"] == "liability"
            assert acc["name"] == "TVH à payer"
            assert acc["is_system"] is True
            assert acc["normal_balance"] == "credit"

            # 2e appel : idempotent, retourne le MÊME compte, aucun doublon.
            acc2 = server_module._resolve_ledger_account(
                org_id, user_id, "2120", create_if_missing=True,
                kind="liability", name="TVH à payer")
            assert acc2["id"] == acc["id"]
            assert server_module.db.chart_of_accounts.count_documents(
                {"organization_id": org_id, "account_number": "2120"}) == 1
        finally:
            _cleanup_org(org_id)

    def test_resolve_ledger_account_create_isolated_by_org(self):
        # Isolation : créer 2120 dans org A ne le crée pas dans org B.
        org_a, user_a = _make_org()
        org_b, user_b = _make_org()
        try:
            server_module._resolve_ledger_account(
                org_a, user_a, "2120", create_if_missing=True,
                kind="liability", name="TVH à payer")
            assert server_module.db.chart_of_accounts.find_one(
                {"organization_id": org_b, "account_number": "2120"}) is None
            # org B ne le résout pas non plus (sans create).
            assert server_module._resolve_ledger_account(
                org_b, user_b, "2120") is None
        finally:
            _cleanup_org(org_a)
            _cleanup_org(org_b)
