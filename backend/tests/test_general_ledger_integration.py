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

    def test_ledger_responses_are_no_store_no_cache(self, client, owner_headers):
        # Tous les GET /api/ledger/* (états financiers, balance, grand livre) doivent
        # renvoyer Cache-Control: no-store, no-cache — jamais de cache sur des chiffres
        # financiers. Invariant sécurité/exactitude. Spec §12.2.
        pytest.fail("À implémenter en T4+ : headers no-store/no-cache sur GET /api/ledger/*")

    def test_cross_org_isolation_at_runtime(self, client, owner_headers):
        # Un membre de l'org A ne doit JAMAIS lire/écrire les comptes ou écritures
        # de l'org B (filtre organization_id à l'exécution, pas seulement à la lecture).
        # 404/403 attendu, jamais de fuite cross-tenant. Spec §12.2.
        pytest.fail("À implémenter en T4+ : isolation cross-org à l'exécution")


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
