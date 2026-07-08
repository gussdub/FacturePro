"""Test — création à la volée du compte de charge 5xxx d'une catégorie mappée absente du plan.

Bug prod (feature #14) : une org seedée AVANT l'ajout des comptes télécom (5050/5051) voyait ses
dépenses « Télécom — internet » retomber sur 5900 « Dépenses diverses » au lieu de 5051, parce que
la migration qui crée 5050/5051 ne tourne qu'au démarrage du backend. Le fix crée le compte à la
demande au moment du POST. Voir `_resolve_expense_account` / `_ensure_expense_account_for_category`.
"""
import os
import sys
import uuid as _uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test")
os.environ.setdefault("DB_NAME", "facturepro")

import pytest  # noqa: E402
from backend.server import (  # noqa: E402
    _resolve_expense_account,
    _ensure_expense_account_for_category,
    _build_default_accounts,
    db,
)


@pytest.fixture()
def org_scope():
    org_id = f"TESTORG-GLACC-{_uuid.uuid4()}"
    yield org_id
    db.chart_of_accounts.delete_many({"organization_id": org_id})


def _seed_legacy_chart(org_id):
    """Seed un plan comptable COMPLET puis RETIRE 5050/5051 pour simuler une org antérieure à
    la feature #14 (comptes télécom jamais créés)."""
    accounts = _build_default_accounts(org_id, "u1")
    db.chart_of_accounts.insert_many([dict(a) for a in accounts])
    db.chart_of_accounts.delete_many(
        {"organization_id": org_id, "account_number": {"$in": ["5050", "5051"]}})


def _acc(org_id, number):
    return db.chart_of_accounts.find_one(
        {"organization_id": org_id, "account_number": number}, {"_id": 0})


class TestAutoCreate:
    def test_telecom_internet_creates_5051_not_fallback_5900(self, org_scope):
        _seed_legacy_chart(org_scope)
        assert _acc(org_scope, "5051") is None  # précondition : 5051 absent
        acc = _resolve_expense_account(org_scope, "u1", "telecom_internet")
        assert acc["account_number"] == "5051", \
            f"attendu 5051 (créé à la volée), obtenu {acc['account_number']}"
        assert acc["expense_category_code"] == "telecom_internet"
        assert acc["name"] == "Télécom — internet"
        assert acc["account_type"] == "expense"
        assert acc["normal_balance"] == "debit"
        assert acc["is_active"] is True

    def test_telecom_cell_creates_5050(self, org_scope):
        _seed_legacy_chart(org_scope)
        acc = _resolve_expense_account(org_scope, "u1", "telecom_cell")
        assert acc["account_number"] == "5050"
        assert acc["expense_category_code"] == "telecom_cell"

    def test_idempotent_no_duplicate(self, org_scope):
        _seed_legacy_chart(org_scope)
        a1 = _resolve_expense_account(org_scope, "u1", "telecom_internet")
        a2 = _resolve_expense_account(org_scope, "u1", "telecom_internet")
        assert a1["id"] == a2["id"]
        count = db.chart_of_accounts.count_documents(
            {"organization_id": org_scope, "account_number": "5051"})
        assert count == 1, f"attendu 1 compte 5051, obtenu {count} (doublon !)"

    def test_unmapped_category_still_falls_back_to_5900(self, org_scope):
        _seed_legacy_chart(org_scope)
        # "other" et catégorie inconnue ne sont PAS dans EXPENSE_ACCOUNT_NUMBERS → 5900.
        for code in ("other", "zzz_inconnu", ""):
            acc = _resolve_expense_account(org_scope, "u1", code)
            assert acc["account_number"] == "5900", \
                f"code {code!r} devrait retomber sur 5900, obtenu {acc['account_number']}"

    def test_existing_account_returned_as_is(self, org_scope):
        """Plan complet (5051 déjà présent) : lookup normal par catégorie, aucune création."""
        accounts = _build_default_accounts(org_scope, "u1")
        db.chart_of_accounts.insert_many([dict(a) for a in accounts])
        acc = _resolve_expense_account(org_scope, "u1", "telecom_internet")
        assert acc["account_number"] == "5051"
        assert db.chart_of_accounts.count_documents(
            {"organization_id": org_scope, "account_number": "5051"}) == 1

    def test_account_taken_by_other_category_falls_back_to_5900(self, org_scope):
        """Garde revue adverse (finding 2) : si le compte 5051 a été ré-affecté manuellement à
        une AUTRE catégorie, une dépense telecom_internet ne doit PAS s'y poster (compte mal
        étiqueté). Le helper renvoie None → repli propre sur 5900."""
        _seed_legacy_chart(org_scope)
        db.chart_of_accounts.insert_one({
            "id": str(_uuid.uuid4()), "organization_id": org_scope,
            "created_by_user_id": "u1", "account_number": "5051",
            "name": "Réaffecté", "account_type": "expense", "sub_type": "operating_expense",
            "normal_balance": "debit", "is_active": True, "is_system": False,
            "expense_category_code": "advertising",  # catégorie DIFFÉRENTE
            "description": "", "created_at": "2026-01-01T00:00:00Z",
        })
        assert _ensure_expense_account_for_category(org_scope, "u1", "telecom_internet") is None
        acc = _resolve_expense_account(org_scope, "u1", "telecom_internet")
        assert acc["account_number"] == "5900"

    def test_no_duplicate_mapping_when_other_account_has_category(self, org_scope):
        """Garde revue adverse (finding 1) : si un autre compte porte déjà telecom_internet ET
        qu'un 5051 orphelin (code=None) existe, le helper utilise le compte existant SANS
        rattacher le code à 5051 → jamais deux comptes avec la même catégorie."""
        _seed_legacy_chart(org_scope)
        # Compte 5199 déjà porteur de la catégorie telecom_internet.
        db.chart_of_accounts.insert_one({
            "id": str(_uuid.uuid4()), "organization_id": org_scope,
            "created_by_user_id": "u1", "account_number": "5199",
            "name": "Télécom (manuel)", "account_type": "expense", "sub_type": "operating_expense",
            "normal_balance": "debit", "is_active": True, "is_system": False,
            "expense_category_code": "telecom_internet",
            "description": "", "created_at": "2026-01-01T00:00:00Z",
        })
        # 5051 orphelin (code=None).
        db.chart_of_accounts.insert_one({
            "id": str(_uuid.uuid4()), "organization_id": org_scope,
            "created_by_user_id": "u1", "account_number": "5051",
            "name": "Compte 5051", "account_type": "expense", "sub_type": "operating_expense",
            "normal_balance": "debit", "is_active": True, "is_system": True,
            "expense_category_code": None, "description": "", "created_at": "2026-01-01T00:00:00Z",
        })
        acc = _ensure_expense_account_for_category(org_scope, "u1", "telecom_internet")
        assert acc["account_number"] == "5199"  # utilise l'existant
        # 5051 n'a PAS été rattaché → une seule occurrence du mapping
        assert db.chart_of_accounts.count_documents(
            {"organization_id": org_scope, "expense_category_code": "telecom_internet"}) == 1

    def test_backfills_category_on_orphan_number_account(self, org_scope):
        """Compte 5051 présent SANS expense_category_code (créé jadis par numéro) : le helper
        rattache la catégorie pour que les lookups futurs le trouvent directement."""
        _seed_legacy_chart(org_scope)
        # Insère un 5051 orphelin (expense_category_code=None), comme _resolve_ledger_account.
        db.chart_of_accounts.insert_one({
            "id": str(_uuid.uuid4()), "organization_id": org_scope,
            "created_by_user_id": "u1", "account_number": "5051",
            "name": "Compte 5051", "account_type": "expense", "sub_type": "operating_expense",
            "normal_balance": "debit", "is_active": True, "is_system": True,
            "expense_category_code": None, "description": "", "created_at": "2026-01-01T00:00:00Z",
        })
        acc = _ensure_expense_account_for_category(org_scope, "u1", "telecom_internet")
        assert acc["account_number"] == "5051"
        assert acc["expense_category_code"] == "telecom_internet"  # rattaché
        # Lookup par catégorie le trouve maintenant
        found = db.chart_of_accounts.find_one(
            {"organization_id": org_scope, "expense_category_code": "telecom_internet"})
        assert found is not None
        assert db.chart_of_accounts.count_documents(
            {"organization_id": org_scope, "account_number": "5051"}) == 1
