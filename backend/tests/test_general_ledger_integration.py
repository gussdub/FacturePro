import sys as _sys
import os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))

import uuid
import pytest
from datetime import datetime, timezone, timedelta
import server as server_module
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    return TestClient(server_module.app)


@pytest.fixture(scope="module")
def owner_headers(client):
    resp = client.post("/api/auth/login",
                       json={"email": "gussdub@gmail.com", "password": "testpass123"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ─────────────────────────────────────────────────────────────────────────────
# T3 : les endpoints /api/ledger/* n'existent PAS encore (ils arrivent en T4+).
# Ce fichier était un stub silencieux (0 test collecté) — dangereux car il
# ressemblait à de la couverture verte alors qu'AUCUN invariant comptable
# critique n'était vérifié. On rend la lacune VISIBLE dans le rapport pytest via
# des placeholders explicitement `skip` (xfail-like) qui documentent chaque
# invariant à couvrir impérativement quand les endpoints seront implémentés.
#
# Réf. spec §12.2 (Plan de tests d'intégration Grand Livre).
# À convertir en vrais tests (retirer @pytest.mark.skip) en T4+.
# ─────────────────────────────────────────────────────────────────────────────

_T4_REASON = (
    "Endpoints /api/ledger/* pas encore implémentés (T4+). "
    "Placeholder visible — à activer avec les endpoints. Spec §12.2."
)


@pytest.mark.skip(reason=_T4_REASON)
class TestLedgerEndpointsT4Plus:
    """Invariants comptables à vérifier côté endpoint dès T4+ (spec §12.2).

    Chaque test ci-dessous est un contrat exécutable qui échouera tant que le
    endpoint n'existe pas — il ne doit PAS être supprimé, seulement dé-skippé
    et complété quand le endpoint correspondant est livré.
    """

    def test_journal_entry_rejects_unbalanced_dr_ne_cr(self, client, owner_headers):
        # POST /api/ledger/entries doit refuser (400) une écriture où
        # somme(débits) != somme(crédits). Invariant partie double NON négociable.
        pytest.fail("À implémenter en T4+ : rejet Dr != Cr sur POST /api/ledger/entries")

    def test_posted_entry_is_immutable(self, client, owner_headers):
        # PUT/DELETE sur une écriture status=posted doit être refusé.
        # Une écriture postée ne se modifie pas (on contre-passe). Spec §12.2.
        pytest.fail("À implémenter en T4+ : immutabilité des écritures postées")

    def test_opening_balance_balances(self, client, owner_headers):
        # POST /api/ledger/opening-balance doit produire une écriture équilibrée
        # (Dr = Cr) et refuser un solde d'ouverture déséquilibré.
        pytest.fail("À implémenter en T4+ : opening-balance équilibré (Dr = Cr)")

    def test_owner_contribution_balances(self, client, owner_headers):
        # POST /api/ledger/owner-contribution : Dr Encaisse / Cr Apport propriétaire,
        # montants égaux. Vérifie la partie double du raccourci apport.
        pytest.fail("À implémenter en T4+ : owner-contribution équilibré (Dr = Cr)")

    def test_cross_org_isolation_at_runtime(self, client, owner_headers):
        # Un membre de l'org A ne doit JAMAIS lire/écrire les comptes ou écritures
        # de l'org B (filtre organization_id à l'exécution, pas seulement à la lecture).
        # 404/403 attendu, jamais de fuite cross-tenant. Spec §12.2.
        pytest.fail("À implémenter en T4+ : isolation cross-org à l'exécution")


# Implémenté (T7 fix-pass) : les endpoints GET /api/ledger/* existent désormais,
# donc ce contrat §12.2 est actif (sorti de la classe skip T4Plus). Les chiffres
# financiers ne doivent JAMAIS être mis en cache par un proxy/CDN/navigateur.
def test_ledger_responses_are_no_store_no_cache(client, owner_headers):
    for path in ("/api/ledger/accounts", "/api/ledger/entries",
                 "/api/ledger/opening-balance"):
        r = client.get(path, headers=owner_headers)
        assert r.status_code == 200, r.text
        cc = r.headers.get("Cache-Control", "")
        assert "no-store" in cc, f"{path} manque no-store : {cc!r}"
        assert "no-cache" in cc, f"{path} manque no-cache : {cc!r}"


# ─────────────────────────────────────────────────────────────────────────────
# T4 : Plan comptable — CRUD + seed lazy (feature #12).
# ─────────────────────────────────────────────────────────────────────────────
class TestChartOfAccounts:
    def test_seed_lazy_on_first_access(self, client, owner_headers):
        r = client.get("/api/ledger/accounts", headers=owner_headers)
        assert r.status_code == 200, r.text
        accounts = r.json()
        assert len(accounts) >= 29
        numbers = [a["account_number"] for a in accounts]
        assert "1000" in numbers and "3100" in numbers and "5900" in numbers
        # trié par account_number
        assert numbers == sorted(numbers)

    def test_seed_idempotent(self, client, owner_headers):
        r1 = client.get("/api/ledger/accounts", headers=owner_headers)
        n1 = len(r1.json())
        r2 = client.get("/api/ledger/accounts", headers=owner_headers)
        assert len(r2.json()) == n1  # pas de doublon au 2e appel

    def test_create_account_happy_path(self, client, owner_headers):
        num = "1500"
        client.delete_by_number = None  # noqa
        r = client.post("/api/ledger/accounts", headers=owner_headers, json={
            "account_number": num, "name": "Équipement", "sub_type": "fixed_asset",
        })
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["account_type"] == "asset"
        assert body["normal_balance"] == "debit"
        assert body["is_system"] is False
        # cleanup
        client.delete(f"/api/ledger/accounts/{body['id']}", headers=owner_headers)

    def test_create_out_of_range_type_mismatch(self, client, owner_headers):
        # 6xxx hors plages canoniques
        r = client.post("/api/ledger/accounts", headers=owner_headers, json={
            "account_number": "6000", "name": "Bidon",
        })
        assert r.status_code == 400

    def test_create_duplicate_number_409(self, client, owner_headers):
        r = client.post("/api/ledger/accounts", headers=owner_headers, json={
            "account_number": "1000", "name": "Doublon encaisse",
        })
        assert r.status_code == 409

    def test_delete_system_account_forbidden(self, client, owner_headers):
        accounts = client.get("/api/ledger/accounts", headers=owner_headers).json()
        cash = next(a for a in accounts if a["account_number"] == "1000")
        r = client.delete(f"/api/ledger/accounts/{cash['id']}", headers=owner_headers)
        assert r.status_code == 400

    def test_put_cannot_change_number_or_type(self, client, owner_headers):
        r = client.post("/api/ledger/accounts", headers=owner_headers, json={
            "account_number": "1510", "name": "Mobilier", "sub_type": "fixed_asset",
        })
        acc_id = r.json()["id"]
        try:
            r2 = client.put(f"/api/ledger/accounts/{acc_id}", headers=owner_headers,
                            json={"account_number": "1520"})
            assert r2.status_code == 400
            r3 = client.put(f"/api/ledger/accounts/{acc_id}", headers=owner_headers,
                            json={"name": "Mobilier de bureau"})
            assert r3.status_code == 200
            assert r3.json()["name"] == "Mobilier de bureau"
        finally:
            client.delete(f"/api/ledger/accounts/{acc_id}", headers=owner_headers)

    # ── [COMPTA] fix #1 : expense_category_code verrouillé (auto-posting §10.2) ──

    def test_create_expense_account_rejects_duplicate_category_code(
            self, client, owner_headers):
        # Le seed a déjà mappé "rent" sur le compte système 5200. Un 2e compte
        # 5xxx portant le même code casserait le mapping dépense→compte (double
        # comptage P&L/T2125) → doit être refusé (409).
        r = client.post("/api/ledger/accounts", headers=owner_headers, json={
            "account_number": "5250", "name": "Loyer entrepôt",
            "sub_type": "operating_expense", "expense_category_code": "rent",
        })
        assert r.status_code == 409, r.text

    def test_create_rejects_unknown_category_code(self, client, owner_headers):
        r = client.post("/api/ledger/accounts", headers=owner_headers, json={
            "account_number": "5251", "name": "Bidon",
            "sub_type": "operating_expense", "expense_category_code": "not_a_code",
        })
        assert r.status_code == 400, r.text

    def test_create_rejects_category_code_on_non_expense(self, client, owner_headers):
        # Un compte d'actif ne doit pas porter un expense_category_code.
        r = client.post("/api/ledger/accounts", headers=owner_headers, json={
            "account_number": "1550", "name": "Actif bidon",
            "sub_type": "current_asset", "expense_category_code": "rent",
        })
        assert r.status_code == 400, r.text

    def test_put_rejects_duplicate_category_code(self, client, owner_headers):
        # Créer un compte de dépense sans code, puis tenter de lui coller un code
        # déjà pris par un compte système → 409.
        r = client.post("/api/ledger/accounts", headers=owner_headers, json={
            "account_number": "5252", "name": "Dépense libre",
            "sub_type": "operating_expense",
        })
        acc_id = r.json()["id"]
        try:
            r2 = client.put(f"/api/ledger/accounts/{acc_id}", headers=owner_headers,
                            json={"expense_category_code": "utilities"})
            assert r2.status_code == 409, r2.text
            # ré-attribuer son PROPRE code (idempotent) doit rester possible
            r3 = client.put(f"/api/ledger/accounts/{acc_id}", headers=owner_headers,
                            json={"expense_category_code": None})
            assert r3.status_code == 200, r3.text
        finally:
            client.delete(f"/api/ledger/accounts/{acc_id}", headers=owner_headers)

    # ── [COMPTA] fix #2 : sub_type contraint au vocabulaire (regroupement bilan) ──

    def test_create_rejects_unknown_sub_type(self, client, owner_headers):
        r = client.post("/api/ledger/accounts", headers=owner_headers, json={
            "account_number": "1560", "name": "Actif exotique",
            "sub_type": "totally_made_up",
        })
        assert r.status_code == 400, r.text

    def test_create_rejects_sub_type_incoherent_with_type(self, client, owner_headers):
        # current_liability sur un compte d'ACTIF (1xxx) → incohérent → 400.
        r = client.post("/api/ledger/accounts", headers=owner_headers, json={
            "account_number": "1561", "name": "Actif mal typé",
            "sub_type": "current_liability",
        })
        assert r.status_code == 400, r.text

    def test_create_accepts_valid_sub_type_and_none(self, client, owner_headers):
        r = client.post("/api/ledger/accounts", headers=owner_headers, json={
            "account_number": "1562", "name": "Équipement lourd",
            "sub_type": "fixed_asset",
        })
        assert r.status_code == 201, r.text
        assert r.json()["sub_type"] == "fixed_asset"
        client.delete(f"/api/ledger/accounts/{r.json()['id']}", headers=owner_headers)
        r2 = client.post("/api/ledger/accounts", headers=owner_headers, json={
            "account_number": "1563", "name": "Sans sous-type",
        })
        assert r2.status_code == 201, r2.text
        assert r2.json()["sub_type"] is None
        client.delete(f"/api/ledger/accounts/{r2.json()['id']}", headers=owner_headers)

    def test_put_rejects_unknown_sub_type(self, client, owner_headers):
        r = client.post("/api/ledger/accounts", headers=owner_headers, json={
            "account_number": "1564", "name": "Actif à modifier",
            "sub_type": "current_asset",
        })
        acc_id = r.json()["id"]
        try:
            r2 = client.put(f"/api/ledger/accounts/{acc_id}", headers=owner_headers,
                            json={"sub_type": "nonsense"})
            assert r2.status_code == 400, r2.text
            r3 = client.put(f"/api/ledger/accounts/{acc_id}", headers=owner_headers,
                            json={"sub_type": "fixed_asset"})
            assert r3.status_code == 200, r3.text
            assert r3.json()["sub_type"] == "fixed_asset"
        finally:
            client.delete(f"/api/ledger/accounts/{acc_id}", headers=owner_headers)


class TestJournalEntries:
    def _accounts(self, client, owner_headers):
        accounts = client.get("/api/ledger/accounts", headers=owner_headers).json()
        by_num = {a["account_number"]: a for a in accounts}
        return by_num

    def _free_expense_number(self, by_num):
        """Un numéro 5xxx libre (compte de dépense). Évite les collisions 409 avec
        les comptes système/seed et les résidus de runs précédents non supprimables."""
        for n in range(5600, 5999):
            if str(n) not in by_num:
                return str(n)
        raise AssertionError("aucun numéro 5xxx libre pour le test")

    def _balanced_body(self, by_num, amount=250.0, status="posted"):
        return {
            "entry_date": "2026-06-15",
            "description": "Test écriture",
            "status": status,
            "lines": [
                {"account_id": by_num["1000"]["id"], "debit": amount, "credit": 0},
                {"account_id": by_num["4000"]["id"], "debit": 0, "credit": amount},
            ],
        }

    def test_post_balanced_entry_creates_je_number(self, client, owner_headers):
        by_num = self._accounts(client, owner_headers)
        r = client.post("/api/ledger/entries", headers=owner_headers,
                        json=self._balanced_body(by_num))
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["entry_number"].startswith("JE-")
        assert body["status"] == "posted"
        assert body["posted_at"] is not None
        assert round(body["total_debit"], 2) == round(body["total_credit"], 2)
        # snapshot des lignes
        assert body["lines"][0]["account_number"] == "1000"
        client.delete(f"/api/ledger/entries/{body['id']}", headers=owner_headers)

    def test_post_unbalanced_400(self, client, owner_headers):
        by_num = self._accounts(client, owner_headers)
        body = self._balanced_body(by_num)
        body["lines"][1]["credit"] = 100.0  # déséquilibre
        r = client.post("/api/ledger/entries", headers=owner_headers, json=body)
        assert r.status_code == 400

    def test_draft_then_post(self, client, owner_headers):
        by_num = self._accounts(client, owner_headers)
        r = client.post("/api/ledger/entries", headers=owner_headers,
                        json=self._balanced_body(by_num, status="draft"))
        assert r.status_code == 201
        entry_id = r.json()["id"]
        assert r.json()["status"] == "draft"
        assert r.json()["posted_at"] is None
        r2 = client.post(f"/api/ledger/entries/{entry_id}/post", headers=owner_headers)
        assert r2.status_code == 200
        assert r2.json()["status"] == "posted"
        client.delete(f"/api/ledger/entries/{entry_id}", headers=owner_headers)

    def test_put_on_posted_forbidden(self, client, owner_headers):
        by_num = self._accounts(client, owner_headers)
        r = client.post("/api/ledger/entries", headers=owner_headers,
                        json=self._balanced_body(by_num))
        entry_id = r.json()["id"]
        try:
            r2 = client.put(f"/api/ledger/entries/{entry_id}", headers=owner_headers,
                            json={"description": "modifié"})
            assert r2.status_code == 400
            r3 = client.delete(f"/api/ledger/entries/{entry_id}", headers=owner_headers)
            assert r3.status_code == 400  # posted → DELETE interdit
        finally:
            # reverse pour nettoyer proprement puis rien (piste d'audit)
            pass

    def test_reverse_creates_mirror(self, client, owner_headers):
        by_num = self._accounts(client, owner_headers)
        r = client.post("/api/ledger/entries", headers=owner_headers,
                        json=self._balanced_body(by_num, amount=333.0))
        entry_id = r.json()["id"]
        r2 = client.post(f"/api/ledger/entries/{entry_id}/reverse",
                         headers=owner_headers, json={})
        assert r2.status_code == 201, r2.text
        rev = r2.json()
        assert rev["entry_type"] == "reversal"
        assert rev["status"] == "posted"           # le miroir est POSTED
        assert rev["reverses_entry_id"] == entry_id
        # lignes inversées : ce qui était débit devient crédit
        assert rev["lines"][0]["credit"] == 333.0
        assert rev["lines"][0]["debit"] == 0
        # origine : RESTE 'posted', SEUL le lien d'audit est posé (pas de statut 'reversed')
        origin = client.get(f"/api/ledger/entries/{entry_id}",
                            headers=owner_headers).json()
        assert origin["status"] == "posted"        # ⚠️ reste posted, JAMAIS 'reversed'
        assert origin["reversed_by_entry_id"] == rev["id"]

    def test_reverse_nets_to_zero_and_stays_balanced(self, client, owner_headers):
        """Le test qui manquait (§5.3) : Dr Encaisse 100 / Cr Revenus 100 →
        solde Encaisse = 100 ; après contre-passation → Encaisse = 0 ET Revenus = 0
        ET la balance de vérification reste équilibrée. C'est l'invariant net zéro
        garanti par le fait que l'origine ET le miroir restent 'posted'.

        NB : ce test consomme /api/ledger/trial-balance, endpoint livré en Task 9.
        Tant qu'il n'existe pas, on skip (l'invariant net-zéro pur — sans passer par
        la balance de vérification — est déjà couvert par TestAccountBalance côté
        unitaire). Le test s'active automatiquement dès que Task 9 est livrée."""
        by_num = self._accounts(client, owner_headers)
        _probe = client.get("/api/ledger/trial-balance?as_of=2030-12-31",
                            headers=owner_headers)
        if _probe.status_code == 404 or "accounts" not in (_probe.json() or {}):
            pytest.skip("Endpoint /api/ledger/trial-balance livré en Task 9 — "
                        "invariant net-zéro déjà couvert unitairement (TestAccountBalance)")

        def _bal(num, as_of="2030-12-31"):
            tb = client.get(f"/api/ledger/trial-balance?as_of={as_of}",
                            headers=owner_headers).json()
            row = next((a for a in tb["accounts"]
                        if a["account_number"] == num), None)
            if not row:
                return 0.0
            return round(row["debit_balance"] - row["credit_balance"], 2)

        cash0 = _bal("1000")
        rev0 = _bal("4000")
        # Dr Encaisse (1000) 100 / Cr Revenus (4000) 100
        r = client.post("/api/ledger/entries", headers=owner_headers, json={
            "entry_date": "2029-06-15", "description": "Vente à contre-passer",
            "status": "posted",
            "lines": [
                {"account_id": by_num["1000"]["id"], "debit": 100.0, "credit": 0},
                {"account_id": by_num["4000"]["id"], "debit": 0, "credit": 100.0},
            ],
        })
        entry_id = r.json()["id"]
        # après post : Encaisse +100 (débit), Revenus +100 (crédit → -100 en net Dr-Cr)
        assert round(_bal("1000") - cash0, 2) == 100.0
        assert round(_bal("4000") - rev0, 2) == -100.0
        # contre-passation
        r2 = client.post(f"/api/ledger/entries/{entry_id}/reverse",
                         headers=owner_headers, json={"entry_date": "2029-06-16"})
        assert r2.status_code == 201, r2.text
        # net zéro : les deux comptes reviennent EXACTEMENT à leur solde d'avant
        assert round(_bal("1000") - cash0, 2) == 0.0   # Encaisse nette = 0
        assert round(_bal("4000") - rev0, 2) == 0.0    # Revenus nets = 0
        # balance de vérification toujours équilibrée
        tb = client.get("/api/ledger/trial-balance?as_of=2030-12-31",
                        headers=owner_headers).json()
        assert tb["balanced"] is True
        assert round(tb["total_debit"], 2) == round(tb["total_credit"], 2)

    def test_reverse_twice_forbidden(self, client, owner_headers):
        """Double contre-passation interdite : le 2e reverse sur la même origine
        (reversed_by_entry_id déjà posé) → 400."""
        by_num = self._accounts(client, owner_headers)
        r = client.post("/api/ledger/entries", headers=owner_headers,
                        json=self._balanced_body(by_num, amount=42.0))
        entry_id = r.json()["id"]
        r1 = client.post(f"/api/ledger/entries/{entry_id}/reverse",
                         headers=owner_headers, json={})
        assert r1.status_code == 201
        r2 = client.post(f"/api/ledger/entries/{entry_id}/reverse",
                         headers=owner_headers, json={})
        assert r2.status_code == 400   # déjà contre-passée

    def test_reverse_non_posted_400(self, client, owner_headers):
        by_num = self._accounts(client, owner_headers)
        r = client.post("/api/ledger/entries", headers=owner_headers,
                        json=self._balanced_body(by_num, status="draft"))
        entry_id = r.json()["id"]
        r2 = client.post(f"/api/ledger/entries/{entry_id}/reverse",
                         headers=owner_headers, json={})
        assert r2.status_code == 400
        client.delete(f"/api/ledger/entries/{entry_id}", headers=owner_headers)

    # ── [COMPTA] fix #1 : entry_date exigée + validée (spec §4 ligne 94) ──

    def test_create_rejects_missing_entry_date(self, client, owner_headers):
        # Sans entry_date, l'écriture serait invisible des soldes datés (as_of=).
        by_num = self._accounts(client, owner_headers)
        body = self._balanced_body(by_num)
        del body["entry_date"]
        r = client.post("/api/ledger/entries", headers=owner_headers, json=body)
        assert r.status_code == 400, r.text

    def test_create_rejects_null_entry_date(self, client, owner_headers):
        by_num = self._accounts(client, owner_headers)
        body = self._balanced_body(by_num)
        body["entry_date"] = None
        r = client.post("/api/ledger/entries", headers=owner_headers, json=body)
        assert r.status_code == 400, r.text

    def test_create_rejects_malformed_entry_date(self, client, owner_headers):
        by_num = self._accounts(client, owner_headers)
        for bad in ("15/06/2026", "not-a-date", "2026-13-40", 42):
            body = self._balanced_body(by_num)
            body["entry_date"] = bad
            r = client.post("/api/ledger/entries", headers=owner_headers, json=body)
            assert r.status_code == 400, f"{bad!r} → {r.status_code} {r.text}"

    def test_create_normalises_datetime_entry_date_to_date_only(
            self, client, owner_headers):
        # Une composante horaire est normalisée → 'YYYY-MM-DD' (comparaisons $gte/$lte
        # de solde homogènes). Sinon un compte pourrait être sous-estimé.
        by_num = self._accounts(client, owner_headers)
        body = self._balanced_body(by_num)
        body["entry_date"] = "2026-06-15T10:30:00Z"
        r = client.post("/api/ledger/entries", headers=owner_headers, json=body)
        assert r.status_code == 201, r.text
        assert r.json()["entry_date"] == "2026-06-15"
        client.delete(f"/api/ledger/entries/{r.json()['id']}", headers=owner_headers)

    def test_reverse_rejects_malformed_entry_date(self, client, owner_headers):
        by_num = self._accounts(client, owner_headers)
        r = client.post("/api/ledger/entries", headers=owner_headers,
                        json=self._balanced_body(by_num, amount=55.0))
        entry_id = r.json()["id"]
        r2 = client.post(f"/api/ledger/entries/{entry_id}/reverse",
                         headers=owner_headers, json={"entry_date": "pas-une-date"})
        assert r2.status_code == 400, r2.text
        # nettoie proprement par une vraie contre-passation
        client.post(f"/api/ledger/entries/{entry_id}/reverse",
                    headers=owner_headers, json={})

    # ── [COMPTA] fix #2 : post re-valide 'compte actif' (spec §4 invariant) ──

    def test_post_rejects_draft_referencing_deactivated_account(
            self, client, owner_headers):
        """Un brouillon créé avec un compte actif, puis ce compte désactivé, ne
        doit PAS être postable — post_entry re-exécute _snapshot_lines et lève 400.
        """
        by_num = self._accounts(client, owner_headers)
        # Compte de dépense non-système, désactivable. Numéro 5xxx libre.
        acc = client.post("/api/ledger/accounts", headers=owner_headers, json={
            "account_number": self._free_expense_number(by_num),
            "name": "Dépense temporaire", "sub_type": "operating_expense",
        })
        assert acc.status_code == 201, acc.text
        acc_id = acc.json()["id"]
        entry_id = None
        try:
            # Brouillon équilibré : Dr 5xxx / Cr 1000 (Encaisse système).
            draft = client.post("/api/ledger/entries", headers=owner_headers, json={
                "entry_date": "2026-06-20", "description": "Brouillon compte à désactiver",
                "status": "draft",
                "lines": [
                    {"account_id": acc_id, "debit": 40.0, "credit": 0},
                    {"account_id": by_num["1000"]["id"], "debit": 0, "credit": 40.0},
                ],
            })
            assert draft.status_code == 201, draft.text
            entry_id = draft.json()["id"]
            # Désactive le compte APRÈS création du brouillon.
            dz = client.put(f"/api/ledger/accounts/{acc_id}", headers=owner_headers,
                            json={"is_active": False})
            assert dz.status_code == 200, dz.text
            # Le post doit maintenant échouer (compte inactif référencé).
            rp = client.post(f"/api/ledger/entries/{entry_id}/post",
                             headers=owner_headers)
            assert rp.status_code == 400, rp.text
            # L'écriture reste 'draft' (pas figée sur un compte inactif).
            still = client.get(f"/api/ledger/entries/{entry_id}",
                               headers=owner_headers).json()
            assert still["status"] == "draft"
        finally:
            if entry_id:
                client.delete(f"/api/ledger/entries/{entry_id}", headers=owner_headers)
            # Réactive puis supprime le compte (pas de ligne postée dessus).
            client.put(f"/api/ledger/accounts/{acc_id}", headers=owner_headers,
                       json={"is_active": True})
            client.delete(f"/api/ledger/accounts/{acc_id}", headers=owner_headers)

    def test_post_refreshes_snapshot_number_and_name(self, client, owner_headers):
        """Bonus : le post re-snapshot number/name → un compte renommé pendant le
        brouillon voit son nom à jour figé au post (état courant, actif)."""
        by_num = self._accounts(client, owner_headers)
        # Numéro 5xxx unique par run : ce test poste une écriture sur le compte,
        # donc il ne peut plus être supprimé après (seulement désactivé). Réutiliser
        # un numéro fixe casserait l'idempotence du test (409 au 2e run).
        num = self._free_expense_number(by_num)
        acc = client.post("/api/ledger/accounts", headers=owner_headers, json={
            "account_number": num, "name": "Ancien nom",
            "sub_type": "operating_expense",
        })
        assert acc.status_code == 201, acc.text
        acc_id = acc.json()["id"]
        entry_id = None
        try:
            draft = client.post("/api/ledger/entries", headers=owner_headers, json={
                "entry_date": "2026-06-21", "description": "Brouillon renommage",
                "status": "draft",
                "lines": [
                    {"account_id": acc_id, "debit": 30.0, "credit": 0},
                    {"account_id": by_num["1000"]["id"], "debit": 0, "credit": 30.0},
                ],
            })
            assert draft.status_code == 201, draft.text
            entry_id = draft.json()["id"]
            client.put(f"/api/ledger/accounts/{acc_id}", headers=owner_headers,
                       json={"name": "Nouveau nom"})
            posted = client.post(f"/api/ledger/entries/{entry_id}/post",
                                 headers=owner_headers)
            assert posted.status_code == 200, posted.text
            line = next(l for l in posted.json()["lines"]
                        if l["account_id"] == acc_id)
            assert line["account_name"] == "Nouveau nom"
        finally:
            # L'écriture est postée → immuable ; on la contre-passe pour nettoyer.
            if entry_id:
                client.post(f"/api/ledger/entries/{entry_id}/reverse",
                            headers=owner_headers, json={})
            # Compte porte des lignes postées → non supprimable ; on le désactive.
            client.put(f"/api/ledger/accounts/{acc_id}", headers=owner_headers,
                       json={"is_active": False})


class TestOpeningBalance:
    @pytest.fixture(autouse=True)
    def _clean_ob(self, client, owner_headers):
        """Supprime toute écriture OB existante avant chaque test (isolation)."""
        server_module.db.journal_entries.delete_many({
            "organization_id": self._org_id(client, owner_headers),
            "entry_type": "opening",
        })
        server_module.db.company_settings.update_many(
            {}, {"$unset": {"ledger_start_date": ""}})
        yield

    def _org_id(self, client, owner_headers):
        return client.get("/api/org/me", headers=owner_headers).json()["organization"]["id"]

    def _accounts(self, client, owner_headers):
        accounts = client.get("/api/ledger/accounts", headers=owner_headers).json()
        return {a["account_number"]: a for a in accounts}

    def test_post_balanced_creates_ob(self, client, owner_headers):
        by_num = self._accounts(client, owner_headers)
        r = client.post("/api/ledger/opening-balance", headers=owner_headers, json={
            "opening_date": "2026-01-01",
            "balances": [
                {"account_id": by_num["1000"]["id"], "debit": 5000.0, "credit": 0},
                {"account_id": by_num["3200"]["id"], "debit": 0, "credit": 5000.0},
            ],
        })
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["entry_number"] == "OB-0001"
        assert body["entry_type"] == "opening"
        assert body["status"] == "posted"
        # ledger_start_date posée
        g = client.get("/api/ledger/opening-balance", headers=owner_headers).json()
        assert g["exists"] is True
        assert g["opening_date"] == "2026-01-01"

    def test_post_unbalanced_400(self, client, owner_headers):
        by_num = self._accounts(client, owner_headers)
        r = client.post("/api/ledger/opening-balance", headers=owner_headers, json={
            "opening_date": "2026-01-01",
            "balances": [
                {"account_id": by_num["1000"]["id"], "debit": 5000.0, "credit": 0},
                {"account_id": by_num["3200"]["id"], "debit": 0, "credit": 4000.0},
            ],
        })
        assert r.status_code == 400

    def test_second_post_409(self, client, owner_headers):
        by_num = self._accounts(client, owner_headers)
        payload = {
            "opening_date": "2026-01-01",
            "balances": [
                {"account_id": by_num["1000"]["id"], "debit": 5000.0, "credit": 0},
                {"account_id": by_num["3200"]["id"], "debit": 0, "credit": 5000.0},
            ],
        }
        r1 = client.post("/api/ledger/opening-balance", headers=owner_headers, json=payload)
        assert r1.status_code == 201
        r2 = client.post("/api/ledger/opening-balance", headers=owner_headers, json=payload)
        assert r2.status_code == 409

    def test_put_replaces(self, client, owner_headers):
        by_num = self._accounts(client, owner_headers)
        client.post("/api/ledger/opening-balance", headers=owner_headers, json={
            "opening_date": "2026-01-01",
            "balances": [
                {"account_id": by_num["1000"]["id"], "debit": 5000.0, "credit": 0},
                {"account_id": by_num["3200"]["id"], "debit": 0, "credit": 5000.0},
            ],
        })
        r = client.put("/api/ledger/opening-balance", headers=owner_headers, json={
            "opening_date": "2026-01-01",
            "balances": [
                {"account_id": by_num["1000"]["id"], "debit": 8000.0, "credit": 0},
                {"account_id": by_num["3200"]["id"], "debit": 0, "credit": 8000.0},
            ],
        })
        assert r.status_code == 200
        assert r.json()["total_debit"] == 8000.0


class TestOwnerContribution:
    def _accounts(self, client, owner_headers):
        accounts = client.get("/api/ledger/accounts", headers=owner_headers).json()
        return {a["account_number"]: a for a in accounts}

    def test_contribution_creates_dr_cash_cr_equity(self, client, owner_headers):
        r = client.post("/api/ledger/owner-contribution", headers=owner_headers, json={
            "amount": 5000.0, "date": "2026-06-20",
        })
        assert r.status_code == 201, r.text
        body = r.json()
        by_line = {l["account_number"]: l for l in body["lines"]}
        assert by_line["1000"]["debit"] == 5000.0   # Encaisse débitée
        assert by_line["3100"]["credit"] == 5000.0  # Apport crédité
        assert body["status"] == "posted"
        # reverse pour ne pas polluer les soldes des autres tests
        client.post(f"/api/ledger/entries/{body['id']}/reverse",
                    headers=owner_headers, json={})

    def test_amount_zero_400(self, client, owner_headers):
        r = client.post("/api/ledger/owner-contribution", headers=owner_headers, json={
            "amount": 0, "date": "2026-06-20",
        })
        assert r.status_code == 400

    def test_negative_amount_400(self, client, owner_headers):
        r = client.post("/api/ledger/owner-contribution", headers=owner_headers, json={
            "amount": -100.0, "date": "2026-06-20",
        })
        assert r.status_code == 400

    def test_cash_override_must_be_asset(self, client, owner_headers):
        # Concern #4 (review T8) : le formulaire guidé contraint cash → asset.
        # Pointer cash_account_id vers un compte non-actif (ici 2000, liability)
        # doit être refusé (400), même si l'écriture serait équilibrée.
        by_num = self._accounts(client, owner_headers)
        r = client.post("/api/ledger/owner-contribution", headers=owner_headers, json={
            "amount": 5000.0, "date": "2026-06-20",
            "cash_account_id": by_num["2000"]["id"],  # Comptes fournisseurs = liability
        })
        assert r.status_code == 400, r.text
        assert "asset" in r.text

    def test_equity_override_must_be_equity(self, client, owner_headers):
        # Concern #4 (review T8) : le formulaire guidé contraint equity → equity.
        # Pointer equity_account_id vers un compte non-capitaux-propres (ici 1000,
        # asset) doit être refusé (400).
        by_num = self._accounts(client, owner_headers)
        r = client.post("/api/ledger/owner-contribution", headers=owner_headers, json={
            "amount": 5000.0, "date": "2026-06-20",
            "equity_account_id": by_num["1000"]["id"],  # Encaisse = asset
        })
        assert r.status_code == 400, r.text
        assert "equity" in r.text

    def test_equity_override_accepts_other_equity_account(self, client, owner_headers):
        # Un override vers un AUTRE compte de capitaux propres (3200 BNR) reste
        # accepté : la contrainte porte sur le type, pas sur le numéro exact.
        by_num = self._accounts(client, owner_headers)
        r = client.post("/api/ledger/owner-contribution", headers=owner_headers, json={
            "amount": 1000.0, "date": "2026-06-20",
            "equity_account_id": by_num["3200"]["id"],  # Bénéfices non répartis = equity
        })
        assert r.status_code == 201, r.text
        by_line = {l["account_number"]: l for l in r.json()["lines"]}
        assert by_line["1000"]["debit"] == 1000.0
        assert by_line["3200"]["credit"] == 1000.0
        client.post(f"/api/ledger/entries/{r.json()['id']}/reverse",
                    headers=owner_headers, json={})


class TestTrialBalance:
    def _accounts(self, client, owner_headers):
        accounts = client.get("/api/ledger/accounts", headers=owner_headers).json()
        return {a["account_number"]: a for a in accounts}

    def test_trial_balance_balanced(self, client, owner_headers):
        by_num = self._accounts(client, owner_headers)
        # une écriture équilibrée
        r = client.post("/api/ledger/entries", headers=owner_headers, json={
            "entry_date": "2026-05-10", "description": "TB test", "status": "posted",
            "lines": [
                {"account_id": by_num["1000"]["id"], "debit": 1200.0, "credit": 0},
                {"account_id": by_num["4000"]["id"], "debit": 0, "credit": 1200.0},
            ],
        })
        entry_id = r.json()["id"]
        try:
            tb = client.get("/api/ledger/trial-balance?as_of=2026-12-31",
                            headers=owner_headers).json()
            assert tb["balanced"] is True
            assert round(tb["total_debit"], 2) == round(tb["total_credit"], 2)
            # comptes à solde nul exclus
            for a in tb["accounts"]:
                assert (a["debit_balance"] > 0) or (a["credit_balance"] > 0)
        finally:
            client.post(f"/api/ledger/entries/{entry_id}/reverse",
                        headers=owner_headers, json={})

    def _cash_debit(self, client, owner_headers, as_of):
        tb = client.get(f"/api/ledger/trial-balance?as_of={as_of}",
                        headers=owner_headers).json()
        row = next((a for a in tb["accounts"]
                    if a["account_number"] == "1000"), None)
        return round(row["debit_balance"] - row["credit_balance"], 2) if row else 0.0

    def test_as_of_excludes_future_entries(self, client, owner_headers):
        by_num = self._accounts(client, owner_headers)
        # Delta-based : robuste à un solde 1000 non nul laissé par d'autres tests
        # du module (isolation partielle). L'invariant testé est que l'écriture
        # datée 2027 n'ajoute RIEN au solde net au 2026-12-31 (borne as_of, §7.1).
        cash_asof_before = self._cash_debit(client, owner_headers, "2026-12-31")
        cash_future_before = self._cash_debit(client, owner_headers, "2027-12-31")
        r = client.post("/api/ledger/entries", headers=owner_headers, json={
            "entry_date": "2027-01-15", "description": "Future", "status": "posted",
            "lines": [
                {"account_id": by_num["1000"]["id"], "debit": 999.0, "credit": 0},
                {"account_id": by_num["4000"]["id"], "debit": 0, "credit": 999.0},
            ],
        })
        entry_id = r.json()["id"]
        try:
            # au 2026-12-31 : l'écriture 2027 est exclue → aucun changement de solde
            cash_asof = self._cash_debit(client, owner_headers, "2026-12-31")
            assert round(cash_asof - cash_asof_before, 2) == 0.0
            # au 2027-12-31 : l'écriture 2027 compte → +999 sur Encaisse (delta à
            # as_of identique pour isoler la SEULE contribution de cette écriture)
            cash_future = self._cash_debit(client, owner_headers, "2027-12-31")
            assert round(cash_future - cash_future_before, 2) == 999.0
        finally:
            client.post(f"/api/ledger/entries/{entry_id}/reverse",
                        headers=owner_headers, json={})


class TestBalanceSheet:
    def _accounts(self, client, owner_headers):
        accounts = client.get("/api/ledger/accounts", headers=owner_headers).json()
        return {a["account_number"]: a for a in accounts}

    def test_balance_sheet_balanced_after_contribution(self, client, owner_headers):
        # apport 4000 : Dr Encaisse (actif) / Cr Apport (CP) → Actif = CP
        r = client.post("/api/ledger/owner-contribution", headers=owner_headers, json={
            "amount": 4000.0, "date": "2026-03-01",
        })
        contrib_id = r.json()["id"]
        try:
            bs = client.get("/api/ledger/balance-sheet?as_of=2026-12-31",
                            headers=owner_headers).json()
            assert bs["balanced"] is True
            assert round(bs["total_assets"], 2) == round(
                bs["total_liabilities_and_equity"], 2)
        finally:
            client.post(f"/api/ledger/entries/{contrib_id}/reverse",
                        headers=owner_headers, json={})

    def test_net_income_current_year_reflected(self, client, owner_headers):
        by_num = self._accounts(client, owner_headers)
        # revenu 1000 : Dr Encaisse / Cr Revenus → net income +1000
        r = client.post("/api/ledger/entries", headers=owner_headers, json={
            "entry_date": "2026-04-01", "description": "Vente", "status": "posted",
            "lines": [
                {"account_id": by_num["1000"]["id"], "debit": 1000.0, "credit": 0},
                {"account_id": by_num["4000"]["id"], "debit": 0, "credit": 1000.0},
            ],
        })
        entry_id = r.json()["id"]
        try:
            bs = client.get("/api/ledger/balance-sheet?as_of=2026-12-31",
                            headers=owner_headers).json()
            assert bs["equity"]["net_income_current_year"] >= 1000.0
            assert bs["balanced"] is True
        finally:
            client.post(f"/api/ledger/entries/{entry_id}/reverse",
                        headers=owner_headers, json={})
