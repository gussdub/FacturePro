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
