import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uuid
import pytest
from datetime import datetime, timezone

from server import (
    ACCOUNT_TYPES,
    ACCOUNT_NUMBER_RANGES,
    DEFAULT_BASE_ACCOUNTS,
    EXPENSE_ACCOUNT_NUMBERS,
    _normal_balance_for_type,
    _account_type_for_number,
    _build_default_accounts,
    EXPENSE_CATEGORIES,
)


class TestAccountConstants:
    def test_five_account_types(self):
        assert set(ACCOUNT_TYPES) == {"asset", "liability", "equity", "revenue", "expense"}

    def test_ranges_cover_five_types(self):
        assert ACCOUNT_NUMBER_RANGES["asset"] == (1000, 1999)
        assert ACCOUNT_NUMBER_RANGES["liability"] == (2000, 2999)
        assert ACCOUNT_NUMBER_RANGES["equity"] == (3000, 3999)
        assert ACCOUNT_NUMBER_RANGES["revenue"] == (4000, 4999)
        assert ACCOUNT_NUMBER_RANGES["expense"] == (5000, 5999)


class TestNormalBalance:
    def test_asset_and_expense_are_debit(self):
        assert _normal_balance_for_type("asset") == "debit"
        assert _normal_balance_for_type("expense") == "debit"

    def test_liability_equity_revenue_are_credit(self):
        for t in ("liability", "equity", "revenue"):
            assert _normal_balance_for_type(t) == "credit"


class TestAccountTypeForNumber:
    def test_ranges(self):
        assert _account_type_for_number("1000") == "asset"
        assert _account_type_for_number("2100") == "liability"
        assert _account_type_for_number("3200") == "equity"
        assert _account_type_for_number("4000") == "revenue"
        assert _account_type_for_number("5900") == "expense"

    def test_out_of_range_returns_none(self):
        assert _account_type_for_number("6000") is None
        assert _account_type_for_number("999") is None
        assert _account_type_for_number("abcd") is None


class TestBuildDefaultAccounts:
    def test_total_29_accounts(self):
        accounts = _build_default_accounts("org-x", "user-x")
        assert len(accounts) == 29  # 12 base + 17 dépenses

    def test_all_scoped_and_system(self):
        accounts = _build_default_accounts("org-x", "user-x")
        for a in accounts:
            assert a["organization_id"] == "org-x"
            assert a["created_by_user_id"] == "user-x"
            assert a["is_system"] is True
            assert a["is_active"] is True

    def test_numbers_unique(self):
        accounts = _build_default_accounts("org-x", "user-x")
        numbers = [a["account_number"] for a in accounts]
        assert len(numbers) == len(set(numbers))

    def test_normal_balance_matches_type(self):
        accounts = _build_default_accounts("org-x", "user-x")
        for a in accounts:
            assert a["normal_balance"] == _normal_balance_for_type(a["account_type"])
            derived = _account_type_for_number(a["account_number"])
            assert a["account_type"] == derived

    def test_expense_accounts_mapped_to_17_categories(self):
        accounts = _build_default_accounts("org-x", "user-x")
        mapped = {a["expense_category_code"] for a in accounts if a.get("expense_category_code")}
        catalogue = {c["code"] for c in EXPENSE_CATEGORIES if c["code"] != "other"}
        assert mapped == catalogue  # les 17 catégories hors "other"

    def test_base_accounts_include_cash_and_owner_contribution(self):
        accounts = _build_default_accounts("org-x", "user-x")
        by_number = {a["account_number"]: a for a in accounts}
        assert by_number["1000"]["name"] == "Encaisse"
        assert by_number["3100"]["name"] == "Apport du propriétaire"
        assert by_number["4000"]["account_type"] == "revenue"


from server import (
    PERMISSIONS_EDITABLE,
    PERMISSIONS_OWNER_ONLY,
    DEFAULT_ROLE_PERMISSIONS,
    _resolve_permissions,
)


class TestAccountingPermissions:
    def test_accounting_codes_editable(self):
        assert "accounting:read" in PERMISSIONS_EDITABLE
        assert "accounting:write" in PERMISSIONS_EDITABLE

    def test_accounting_not_owner_only(self):
        assert "accounting:read" not in PERMISSIONS_OWNER_ONLY
        assert "accounting:write" not in PERMISSIONS_OWNER_ONLY

    def test_accountant_default_has_both(self):
        assert "accounting:read" in DEFAULT_ROLE_PERMISSIONS["accountant"]
        assert "accounting:write" in DEFAULT_ROLE_PERMISSIONS["accountant"]

    def test_viewer_default_read_only(self):
        assert "accounting:read" in DEFAULT_ROLE_PERMISSIONS["viewer"]
        assert "accounting:write" not in DEFAULT_ROLE_PERMISSIONS["viewer"]

    def test_owner_resolves_both(self):
        perms = _resolve_permissions({}, "owner")
        assert "accounting:read" in perms
        assert "accounting:write" in perms

    def test_viewer_can_be_granted_write_by_owner(self):
        # accounting:write est un code EDITABLE (pas owner-only) : l'owner peut
        # l'accorder volontairement à un rôle via la matrice role_permissions.
        # Ici l'owner a coché accounting:write pour le viewer → le résolveur
        # doit le laisser passer (il franchit le filtre PERMISSIONS_EDITABLE).
        org = {"role_permissions": {"viewer": ["accounting:read", "accounting:write"]}}
        perms = _resolve_permissions(org, "viewer")
        assert "accounting:write" in perms


from server import (
    migrate_general_ledger_v1,
    migrate_organizations_v1,
    db as server_db,
)


class TestMigrateGeneralLedgerV1:
    def _make_org_and_settings(self):
        org_id = f"gl-mig-{uuid.uuid4().hex[:8]}"
        server_db.organizations.insert_one({
            "id": org_id, "name": "GL Mig Test", "owner_id": "u-" + org_id,
            "role_permissions": {"accountant": [], "viewer": []},
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        server_db.company_settings.insert_one({
            "id": f"cs-{org_id}", "user_id": "u-" + org_id,
            "organization_id": org_id, "company_name": "GL Mig Test",
        })
        return org_id

    def _cleanup(self, org_id):
        server_db.organizations.delete_one({"id": org_id})
        server_db.company_settings.delete_many({"organization_id": org_id})

    def test_backfills_fiscal_fields_default_dec_31(self):
        org_id = self._make_org_and_settings()
        try:
            migrate_general_ledger_v1()
            cs = server_db.company_settings.find_one({"organization_id": org_id})
            assert cs["fiscal_year_end_month"] == 12
            assert cs["fiscal_year_end_day"] == 31
        finally:
            self._cleanup(org_id)

    def test_backfills_accounting_perms(self):
        org_id = self._make_org_and_settings()
        try:
            migrate_general_ledger_v1()
            org = server_db.organizations.find_one({"id": org_id})
            rp = org["role_permissions"]
            assert "accounting:read" in rp["accountant"]
            assert "accounting:write" in rp["accountant"]
            assert "accounting:read" in rp["viewer"]
            assert "accounting:write" not in rp["viewer"]
        finally:
            self._cleanup(org_id)

    def test_idempotent(self):
        org_id = self._make_org_and_settings()
        try:
            migrate_general_ledger_v1()
            migrate_general_ledger_v1()  # re-run — no crash, no dup
            cs = server_db.company_settings.find_one({"organization_id": org_id})
            assert cs["fiscal_year_end_month"] == 12
        finally:
            self._cleanup(org_id)

    def test_does_not_overwrite_custom_fiscal(self):
        org_id = self._make_org_and_settings()
        server_db.company_settings.update_one(
            {"organization_id": org_id},
            {"$set": {"fiscal_year_end_month": 3, "fiscal_year_end_day": 31}}
        )
        try:
            migrate_general_ledger_v1()
            cs = server_db.company_settings.find_one({"organization_id": org_id})
            assert cs["fiscal_year_end_month"] == 3  # respecté
        finally:
            self._cleanup(org_id)

    def test_sets_one_shot_flag(self):
        # Le 1er passage pose le flag persisté `ledger_perms_backfilled` (spec §8.2).
        org_id = self._make_org_and_settings()
        try:
            migrate_general_ledger_v1()
            org = server_db.organizations.find_one({"id": org_id})
            assert org.get("ledger_perms_backfilled") is True
        finally:
            self._cleanup(org_id)

    def test_owner_removal_not_reimposed_on_reboot(self):
        # Régression : après le 1er backfill, un owner retire volontairement
        # accounting:* d'un rôle. Un boot suivant NE doit PAS le ré-accorder.
        #
        # IMPORTANT : ce test enchaîne migrate_organizations_v1() PUIS
        # migrate_general_ledger_v1() dans l'ordre réel du startup
        # (server.py:5777 puis 5780). C'est indispensable : migrate_organizations_v1
        # tourne EN PREMIER à chaque boot, et un backfill accounting inconditionnel
        # y ré-imposerait la perm en contournant le flag one-shot de
        # migrate_general_ledger_v1. Tester la GL en isolation masquait la régression.
        org_id = self._make_org_and_settings()
        try:
            # 1er boot : les deux migrations tournent, perms ajoutées + flag posé.
            migrate_organizations_v1()
            migrate_general_ledger_v1()
            # L'owner retire volontairement accounting:* du comptable et du lecteur.
            server_db.organizations.update_one(
                {"id": org_id},
                {"$set": {"role_permissions": {"accountant": [], "viewer": []}}},
            )
            # Reboot : ordre réel du seed_data. Ni l'une ni l'autre ne doit
            # ré-imposer accounting:* (flag one-shot déjà posé + plus de backfill
            # accounting inconditionnel dans migrate_organizations_v1).
            migrate_organizations_v1()
            migrate_general_ledger_v1()
            org = server_db.organizations.find_one({"id": org_id})
            rp = org["role_permissions"]
            assert "accounting:read" not in rp["accountant"]
            assert "accounting:write" not in rp["accountant"]
            assert "accounting:read" not in rp["viewer"]
        finally:
            self._cleanup(org_id)

    def test_organizations_migration_does_not_reimpose_accounting_on_reboot(self):
        # Cible directement la cause racine du review : migrate_organizations_v1()
        # (qui tourne en premier au boot) NE doit PAS ré-ajouter accounting:* à une
        # org déjà backfillée dont l'owner a retiré la perm. Sans le fix, ce backfill
        # jumeau inconditionnel réintroduisait accounting:read/write et accounting:read.
        org_id = self._make_org_and_settings()
        try:
            # Org déjà passée par le backfill GL (flag posé), owner a tout retiré.
            server_db.organizations.update_one(
                {"id": org_id},
                {"$set": {
                    "ledger_perms_backfilled": True,
                    "role_permissions": {"accountant": [], "viewer": []},
                }},
            )
            migrate_organizations_v1()  # tourne en premier au boot — ne doit rien re-imposer
            org = server_db.organizations.find_one({"id": org_id})
            rp = org["role_permissions"]
            assert "accounting:read" not in rp["accountant"]
            assert "accounting:write" not in rp["accountant"]
            assert "accounting:read" not in rp["viewer"]
        finally:
            self._cleanup(org_id)

    def test_flag_skips_already_backfilled_org(self):
        # Une org qui a déjà le flag (jamais touchée par le backfill) garde ses
        # perms telles quelles même vides — le backfill la saute entièrement.
        org_id = self._make_org_and_settings()
        server_db.organizations.update_one(
            {"id": org_id}, {"$set": {"ledger_perms_backfilled": True}}
        )
        try:
            migrate_general_ledger_v1()
            org = server_db.organizations.find_one({"id": org_id})
            rp = org["role_permissions"]
            assert rp["accountant"] == []
            assert rp["viewer"] == []
        finally:
            self._cleanup(org_id)


from server import _validate_entry_balance, _account_balance
from server import _require_entry_date, _snapshot_lines
from fastapi import HTTPException as _HTTPExc


class TestRequireEntryDate:
    """entry_date DOIT être une date ISO 'YYYY-MM-DD' valide, exigée et normalisée
    (spec §4 ligne 94). Sans ça, une écriture posted+équilibrée avec entry_date
    None/malformée serait stockée telle quelle : toute requête de solde bornée par
    date ($gte/$lte contre entry_date, ex. trial-balance ?as_of=) l'EXCLURAIT en
    silence → compte sous-estimé → balance de vérification faussement déséquilibrée.
    """

    def test_valid_iso_date_passthrough(self):
        assert _require_entry_date("2026-06-15") == "2026-06-15"

    def test_normalises_datetime_to_date_only(self):
        # Une composante horaire casserait les comparaisons de chaînes $gte/$lte.
        assert _require_entry_date("2026-06-15T10:30:00Z") == "2026-06-15"
        assert _require_entry_date("2026-06-15T10:30:00+00:00") == "2026-06-15"

    def test_none_rejected(self):
        with pytest.raises(_HTTPExc) as e:
            _require_entry_date(None)
        assert e.value.status_code == 400

    def test_empty_string_rejected(self):
        with pytest.raises(_HTTPExc) as e:
            _require_entry_date("")
        assert e.value.status_code == 400

    def test_malformed_string_rejected(self):
        for bad in ("not-a-date", "2026-13-40", "15/06/2026", "2026-06"):
            with pytest.raises(_HTTPExc) as e:
                _require_entry_date(bad)
            assert e.value.status_code == 400, bad

    def test_non_string_rejected_as_400_not_500(self):
        # entry_date: 42 dans le JSON ne doit pas exploser en TypeError (500).
        for bad in (42, 3.14, {}, [], True):
            with pytest.raises(_HTTPExc) as e:
                _require_entry_date(bad)
            assert e.value.status_code == 400, bad


class TestSnapshotLinesActiveGuard:
    """_snapshot_lines refuse un compte inactif/introuvable (spec §4 invariant,
    lignes 132/334). Re-exécuté au POST, il empêche qu'un brouillon créé avec un
    compte actif puis désactivé se fige en référençant un compte inactif."""

    def _org(self):
        return f"gl-snap-{uuid.uuid4().hex[:8]}"

    def _insert_account(self, org_id, account_id, is_active=True, number="1000",
                        name="Encaisse"):
        server_db.chart_of_accounts.insert_one({
            "id": account_id, "organization_id": org_id,
            "account_number": number, "name": name, "is_active": is_active,
        })

    def _cleanup(self, org_id):
        server_db.chart_of_accounts.delete_many({"organization_id": org_id})

    def test_active_account_snapshots_number_and_name(self):
        org_id = self._org()
        cash, rev = "a-cash", "a-rev"
        try:
            self._insert_account(org_id, cash, number="1000", name="Encaisse")
            self._insert_account(org_id, rev, number="4000", name="Ventes")
            enriched = _snapshot_lines(org_id, [
                {"account_id": cash, "debit": 100.0, "credit": 0.0},
                {"account_id": rev, "debit": 0.0, "credit": 100.0},
            ])
            assert enriched[0]["account_number"] == "1000"
            assert enriched[0]["account_name"] == "Encaisse"
            assert enriched[1]["account_number"] == "4000"
        finally:
            self._cleanup(org_id)

    def test_inactive_account_rejected_at_snapshot(self):
        # Simule le POST d'un brouillon dont un compte a été désactivé entre-temps.
        org_id = self._org()
        cash, rev = "a-cash", "a-rev"
        try:
            self._insert_account(org_id, cash, is_active=True, number="1000")
            self._insert_account(org_id, rev, is_active=False,  # désactivé
                                 number="4000", name="Ventes")
            with pytest.raises(_HTTPExc) as e:
                _snapshot_lines(org_id, [
                    {"account_id": cash, "debit": 100.0, "credit": 0.0},
                    {"account_id": rev, "debit": 0.0, "credit": 100.0},
                ])
            assert e.value.status_code == 400
        finally:
            self._cleanup(org_id)


class TestValidateEntryBalance:
    def test_balanced_ok(self):
        lines = [
            {"debit": 100.0, "credit": 0.0},
            {"debit": 0.0, "credit": 100.0},
        ]
        _validate_entry_balance(lines)  # no raise

    def test_less_than_two_lines(self):
        with pytest.raises(_HTTPExc) as e:
            _validate_entry_balance([{"debit": 100.0, "credit": 0.0}])
        assert e.value.status_code == 400

    def test_unbalanced(self):
        with pytest.raises(_HTTPExc) as e:
            _validate_entry_balance([
                {"debit": 100.0, "credit": 0.0},
                {"debit": 0.0, "credit": 90.0},
            ])
        assert e.value.status_code == 400

    def test_line_with_both_debit_and_credit(self):
        with pytest.raises(_HTTPExc) as e:
            _validate_entry_balance([
                {"debit": 50.0, "credit": 50.0},
                {"debit": 0.0, "credit": 0.0},
            ])
        assert e.value.status_code == 400

    def test_negative_line(self):
        with pytest.raises(_HTTPExc) as e:
            _validate_entry_balance([
                {"debit": -100.0, "credit": 0.0},
                {"debit": 0.0, "credit": -100.0},
            ])
        assert e.value.status_code == 400

    def test_tolerance_half_cent(self):
        # écart 0,004 $ < 0,005 → accepté
        _validate_entry_balance([
            {"debit": 100.004, "credit": 0.0},
            {"debit": 0.0, "credit": 100.0},
        ])


class TestAccountBalance:
    """Garde-fou de régression pour _account_balance — la fonction qui alimente
    bilan, balance de vérification et grand livre (§5.2 / §5.3).

    Chaque test insère de vraies écritures `journal_entries` dans la DB, scopées
    sur un org_id de test unique, et nettoie en `finally`. On couvre :
      - orientation par normal_balance (débiteur Dr-Cr, créditeur Cr-Dr) ;
      - exclusion des brouillons (draft) ;
      - INVARIANT §5.3 : origine + miroir tous deux `posted` → net = 0 (la
        contre-passation ne doit JAMAIS être exclue du solde) ;
      - garde anti-régression : une écriture reste comptée même si
        reverses_entry_id / reversed_by_entry_id sont posés (champs d'audit) ;
      - bornes as_of_date / start_date (dates ISO incluses) ;
      - non-fuite cross-org.
    """

    def _org(self):
        return f"gl-bal-{uuid.uuid4().hex[:8]}"

    def _line(self, account_id, debit=0.0, credit=0.0):
        return {
            "line_id": str(uuid.uuid4()),
            "account_id": account_id,
            "account_number": "0000",
            "account_name": "Test",
            "debit": debit,
            "credit": credit,
            "line_description": None,
        }

    def _entry(self, org_id, lines, entry_date="2026-06-15", status="posted",
               entry_type="manual", reverses_entry_id=None,
               reversed_by_entry_id=None):
        entry_id = str(uuid.uuid4())
        server_db.journal_entries.insert_one({
            "id": entry_id,
            "organization_id": org_id,
            "created_by_user_id": "u-" + org_id,
            "entry_number": f"JE-{uuid.uuid4().hex[:6]}",
            "entry_date": entry_date,
            "description": "Test",
            "reference": None,
            "entry_type": entry_type,
            "status": status,
            "lines": lines,
            "total_debit": round(sum(l["debit"] for l in lines), 2),
            "total_credit": round(sum(l["credit"] for l in lines), 2),
            "reverses_entry_id": reverses_entry_id,
            "reversed_by_entry_id": reversed_by_entry_id,
            "source_type": None,
            "source_id": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "posted_at": (datetime.now(timezone.utc).isoformat()
                          if status == "posted" else None),
        })
        return entry_id

    def _cleanup(self, org_id):
        server_db.journal_entries.delete_many({"organization_id": org_id})

    def test_debit_normal_orientation(self):
        # Compte à solde normal débiteur (actif/charge) : solde = Dr - Cr.
        # Encaisse débitée 300, créditée 100 → 200.
        org_id = self._org()
        cash = "acct-cash"
        try:
            self._entry(org_id, [self._line(cash, debit=300.0),
                                 self._line("other", credit=300.0)])
            self._entry(org_id, [self._line(cash, credit=100.0),
                                 self._line("other", debit=100.0)])
            bal = _account_balance(org_id, cash, "debit")
            assert bal == 200.0
        finally:
            self._cleanup(org_id)

    def test_credit_normal_orientation(self):
        # Compte à solde normal créditeur (passif/CP/revenu) : solde = Cr - Dr.
        # Revenu crédité 500, débité 50 → 450.
        org_id = self._org()
        rev = "acct-rev"
        try:
            self._entry(org_id, [self._line(rev, credit=500.0),
                                 self._line("other", debit=500.0)])
            self._entry(org_id, [self._line(rev, debit=50.0),
                                 self._line("other", credit=50.0)])
            bal = _account_balance(org_id, rev, "credit")
            assert bal == 450.0
        finally:
            self._cleanup(org_id)

    def test_draft_excluded(self):
        # Un brouillon (draft) ne doit affecter aucun solde.
        org_id = self._org()
        cash = "acct-cash"
        try:
            self._entry(org_id, [self._line(cash, debit=100.0),
                                 self._line("other", credit=100.0)], status="posted")
            self._entry(org_id, [self._line(cash, debit=999.0),
                                 self._line("other", credit=999.0)], status="draft")
            bal = _account_balance(org_id, cash, "debit")
            assert bal == 100.0  # le draft de 999 est ignoré
        finally:
            self._cleanup(org_id)

    def test_reversal_nets_to_zero(self):
        # INVARIANT §5.3 : origine `posted` + miroir `posted` → net = 0.
        # Les deux restent posted ; le solde s'annule naturellement.
        org_id = self._org()
        cash = "acct-cash"
        try:
            origin = self._entry(org_id, [self._line(cash, debit=333.0),
                                          self._line("other", credit=333.0)])
            # Miroir : Dr↔Cr inversés, entry_type=reversal, reverses_entry_id posé.
            mirror = self._entry(
                org_id,
                [self._line(cash, credit=333.0), self._line("other", debit=333.0)],
                entry_type="reversal", reverses_entry_id=origin)
            # L'origine porte reversed_by_entry_id mais RESTE posted.
            server_db.journal_entries.update_one(
                {"id": origin},
                {"$set": {"reversed_by_entry_id": mirror}})
            bal = _account_balance(org_id, cash, "debit")
            assert bal == 0.0  # net nul : jamais de double effet
        finally:
            self._cleanup(org_id)

    def test_reversed_entries_still_counted_regression_guard(self):
        # GARDE ANTI-RÉGRESSION : même quand reverses_entry_id / reversed_by_entry_id
        # sont posés, les DEUX écritures sont comptées. Si un futur changement
        # ajoutait par erreur un filtre excluant ces champs, le net ne serait plus 0
        # (double effet §5.3) et ce test échouerait. On le vérifie en isolant chaque
        # écriture : chacune, prise seule, doit compter pour ±333.
        org_id = self._org()
        cash = "acct-cash"
        try:
            origin = self._entry(
                org_id, [self._line(cash, debit=333.0),
                         self._line("other", credit=333.0)],
                reversed_by_entry_id="mirror-placeholder")
            # Origine seule (avec reversed_by_entry_id posé) : doit compter +333.
            assert _account_balance(org_id, cash, "debit") == 333.0
            # Ajoute le miroir seul (reverses_entry_id posé) : doit compter -333.
            self._entry(
                org_id, [self._line(cash, credit=333.0),
                         self._line("other", debit=333.0)],
                entry_type="reversal", reverses_entry_id=origin)
            assert _account_balance(org_id, cash, "debit") == 0.0
        finally:
            self._cleanup(org_id)

    def test_as_of_date_upper_bound_inclusive(self):
        # as_of_date borne le solde à cette date (incluse) ; les écritures
        # postérieures sont exclues.
        org_id = self._org()
        cash = "acct-cash"
        try:
            self._entry(org_id, [self._line(cash, debit=100.0),
                                 self._line("other", credit=100.0)],
                        entry_date="2026-06-15")
            self._entry(org_id, [self._line(cash, debit=50.0),
                                 self._line("other", credit=50.0)],
                        entry_date="2026-06-30")
            # as_of 2026-06-15 → seule la 1re écriture compte.
            assert _account_balance(org_id, cash, "debit",
                                    as_of_date="2026-06-15") == 100.0
            # as_of 2026-06-30 → les deux comptent (borne incluse).
            assert _account_balance(org_id, cash, "debit",
                                    as_of_date="2026-06-30") == 150.0
        finally:
            self._cleanup(org_id)

    def test_start_date_lower_bound_inclusive(self):
        # start_date borne le solde à partir de cette date (incluse) ; les
        # écritures antérieures sont exclues. Utile pour les soldes de période.
        org_id = self._org()
        rev = "acct-rev"
        try:
            self._entry(org_id, [self._line(rev, credit=200.0),
                                 self._line("other", debit=200.0)],
                        entry_date="2026-01-10")
            self._entry(org_id, [self._line(rev, credit=300.0),
                                 self._line("other", debit=300.0)],
                        entry_date="2026-06-10")
            # start 2026-06-01 → seule la 2e écriture (juin) compte.
            assert _account_balance(org_id, rev, "credit",
                                    start_date="2026-06-01") == 300.0
            # fenêtre [2026-01-01, 2026-06-30] → les deux comptent.
            assert _account_balance(org_id, rev, "credit",
                                    start_date="2026-01-01",
                                    as_of_date="2026-06-30") == 500.0
        finally:
            self._cleanup(org_id)

    def test_no_cross_org_leak(self):
        # Isolation multi-tenant : le solde d'une org ne doit JAMAIS inclure les
        # écritures d'une autre org, même avec le même account_id.
        org_a = self._org()
        org_b = self._org()
        cash = "acct-cash"  # même account_id dans les deux orgs
        try:
            self._entry(org_a, [self._line(cash, debit=100.0),
                                self._line("other", credit=100.0)])
            self._entry(org_b, [self._line(cash, debit=777.0),
                                self._line("other", credit=777.0)])
            assert _account_balance(org_a, cash, "debit") == 100.0
            assert _account_balance(org_b, cash, "debit") == 777.0
        finally:
            self._cleanup(org_a)
            self._cleanup(org_b)

    def test_empty_account_is_zero(self):
        # Un compte sans aucune écriture postée a un solde nul (pas d'erreur).
        org_id = self._org()
        try:
            assert _account_balance(org_id, "acct-never-used", "debit") == 0.0
            assert _account_balance(org_id, "acct-never-used", "credit") == 0.0
        finally:
            self._cleanup(org_id)
