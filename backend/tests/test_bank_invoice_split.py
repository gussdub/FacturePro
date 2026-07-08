"""Tests — split match d'UNE bank_transaction sur PLUSIEURS factures (dépôt qui couvre N factures).

Contrainte v1 : la somme des soldes des N factures doit égaler EXACTEMENT le montant crédité de la
transaction (± 0,01). Sinon 422. Voir `_apply_invoice_split_match` dans backend/server.py.
"""
import os
import sys
import uuid as _uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test")

import pytest  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from backend.server import (  # noqa: E402
    _apply_invoice_split_match,
    _release_bank_transaction,
    db,
)


@pytest.fixture()
def org_scope():
    scope = {"organization_id": f"TESTORG-SPLIT-{_uuid.uuid4()}"}
    yield scope
    db.invoices.delete_many(scope)
    db.bank_transactions.delete_many(scope)


def _mk_invoice(scope, total, **over):
    """Facture minimale 'sent' sans payment. total en CAD. Aucun calcul de taxe : on manipule
    directement `total` pour piloter l'outstanding."""
    doc = {
        "id": str(_uuid.uuid4()),
        "organization_id": scope["organization_id"],
        "created_by_user_id": "u1", "user_id": "u1",
        "invoice_number": f"INV-{_uuid.uuid4().hex[:6]}",
        "client_id": "cli-x", "client_name": "Client X",
        "issue_date": "2099-04-20", "due_date": "2099-05-20",
        "items": [{"description": "S", "quantity": 1, "unit_price": total}],
        "subtotal": total, "total": total,
        "gst_cad": 0, "qst_cad": 0, "hst_cad": 0,
        "status": "sent", "payments": [],
    }
    doc.update(over)
    db.invoices.insert_one(dict(doc))
    return doc


def _mk_tx(scope, amount_cad):
    """Bank tx unmatched. amount_cad positif = crédit (dépôt)."""
    tx = {
        "id": str(_uuid.uuid4()),
        "organization_id": scope["organization_id"],
        "status": "unmatched", "amount_cad": amount_cad,
        "date": "2099-04-21", "description": "DEPOT LEBLEU",
        "match_kind": None, "match_id": None, "invoice_id": None,
    }
    db.bank_transactions.insert_one(dict(tx))
    return tx


def _reload_tx(scope, tx_id):
    return db.bank_transactions.find_one({"id": tx_id, **scope}, {"_id": 0})


def _reload_inv(scope, iid):
    return db.invoices.find_one({"id": iid, **scope}, {"_id": 0})


class TestSplitHappyPath:
    def test_two_invoices_sum_matches_tx(self, org_scope):
        """Sc. réel : dépôt 14808.78 $ couvre facture A (5000) + facture B (9808.78)."""
        a = _mk_invoice(org_scope, 5000.00)
        b = _mk_invoice(org_scope, 9808.78)
        tx = _mk_tx(org_scope, 14808.78)
        result = _apply_invoice_split_match(tx, [a["id"], b["id"]], org_scope)
        assert result["status"] == "matched"
        assert result["match_kind"] == "invoice_split"
        assert set(result["invoice_ids"]) == {a["id"], b["id"]}
        assert len(result["match_ids"]) == 2  # 2 payment ids
        # Chaque facture reçoit un payment == son solde entier + statut paid
        for iid, expected in [(a["id"], 5000.00), (b["id"], 9808.78)]:
            inv = _reload_inv(org_scope, iid)
            assert len(inv["payments"]) == 1
            assert inv["payments"][0]["amount_cad"] == expected
            assert inv["payments"][0]["bank_transaction_id"] == tx["id"]
            assert inv["status"] == "paid"

    def test_three_invoices_sum_matches_tx(self, org_scope):
        """3 factures dont la somme correspond au dépôt."""
        totals = [100.00, 200.00, 350.50]
        invs = [_mk_invoice(org_scope, t) for t in totals]
        tx = _mk_tx(org_scope, sum(totals))
        _apply_invoice_split_match(tx, [i["id"] for i in invs], org_scope)
        for i in invs:
            inv = _reload_inv(org_scope, i["id"])
            assert inv["status"] == "paid"
        assert _reload_tx(org_scope, tx["id"])["match_kind"] == "invoice_split"


class TestSplitRejects:
    def test_sum_mismatch_rejected(self, org_scope):
        a = _mk_invoice(org_scope, 100.00)
        b = _mk_invoice(org_scope, 200.00)
        tx = _mk_tx(org_scope, 500.00)  # Σ soldes = 300 ≠ 500
        with pytest.raises(HTTPException) as exc:
            _apply_invoice_split_match(tx, [a["id"], b["id"]], org_scope)
        assert exc.value.status_code == 422
        # Aucune mutation : les factures restent sans payment
        for i in (a, b):
            assert _reload_inv(org_scope, i["id"])["payments"] == []
        # Note : la tx reste unmatched car _apply_invoice_split_match échoue AVANT toute écriture

    def test_duplicate_target_ids_rejected(self, org_scope):
        a = _mk_invoice(org_scope, 100.00)
        tx = _mk_tx(org_scope, 200.00)
        with pytest.raises(HTTPException) as exc:
            _apply_invoice_split_match(tx, [a["id"], a["id"]], org_scope)
        assert exc.value.status_code == 422

    def test_paid_invoice_in_target_ids_rejected(self, org_scope):
        a = _mk_invoice(org_scope, 100.00, status="paid")
        b = _mk_invoice(org_scope, 200.00)
        tx = _mk_tx(org_scope, 300.00)
        with pytest.raises(HTTPException) as exc:
            _apply_invoice_split_match(tx, [a["id"], b["id"]], org_scope)
        assert exc.value.status_code == 409
        # Rollback implicite : b n'a pas encore été touchée
        assert _reload_inv(org_scope, b["id"])["payments"] == []

    def test_single_target_rejected(self, org_scope):
        """1 seul id → split n'a pas de sens ; l'endpoint route vers _apply_match unitaire."""
        a = _mk_invoice(org_scope, 100.00)
        tx = _mk_tx(org_scope, 100.00)
        with pytest.raises(HTTPException) as exc:
            _apply_invoice_split_match(tx, [a["id"]], org_scope)
        assert exc.value.status_code == 422

    def test_already_matched_tx_rejected(self, org_scope):
        a = _mk_invoice(org_scope, 100.00)
        b = _mk_invoice(org_scope, 200.00)
        tx = _mk_tx(org_scope, 300.00)
        db.bank_transactions.update_one(
            {"id": tx["id"]}, {"$set": {"status": "matched", "match_kind": "expense"}})
        tx_reloaded = _reload_tx(org_scope, tx["id"])
        with pytest.raises(HTTPException) as exc:
            _apply_invoice_split_match(tx_reloaded, [a["id"], b["id"]], org_scope)
        assert exc.value.status_code == 409

    def test_unknown_invoice_id_rejected(self, org_scope):
        a = _mk_invoice(org_scope, 100.00)
        tx = _mk_tx(org_scope, 300.00)
        with pytest.raises(HTTPException) as exc:
            _apply_invoice_split_match(tx, [a["id"], "does-not-exist"], org_scope)
        assert exc.value.status_code == 404


class TestSplitCascadeRelease:
    """Cascade DELETE : si UNE des N factures d'un split est supprimée, `_release_bank_transaction`
    doit défaire tout le split (retirer les payments des autres factures + recomputer leurs statuts)
    pour ne pas laisser d'orphan payments qui pointent vers une tx maintenant unmatched."""

    def test_release_cleans_all_other_invoices(self, org_scope):
        a = _mk_invoice(org_scope, 100.00)
        b = _mk_invoice(org_scope, 200.00)
        tx = _mk_tx(org_scope, 300.00)
        _apply_invoice_split_match(tx, [a["id"], b["id"]], org_scope)
        # Précondition : les deux payments existent
        assert _reload_inv(org_scope, a["id"])["status"] == "paid"
        assert _reload_inv(org_scope, b["id"])["status"] == "paid"
        # Simule le cascade delete de A → release de la tx.
        _release_bank_transaction(tx["id"], org_scope)
        # La tx est unmatched et n'a plus de références de split
        released = _reload_tx(org_scope, tx["id"])
        assert released["status"] == "unmatched"
        assert released["match_kind"] is None
        assert released.get("match_ids") is None
        assert released.get("invoice_ids") is None
        # Facture B (encore présente) — son payment orphelin doit avoir été retiré + status recomputé
        b_after = _reload_inv(org_scope, b["id"])
        assert b_after["payments"] == []
        assert b_after["status"] == "sent"

    def test_release_preserves_concurrent_manual_payment(self, org_scope):
        """Régression revue adverse #4 : le cleanup cascade doit utiliser `$pull` par
        bank_transaction_id, PAS `$set: payments: [...]`. Sinon un payment manuel ajouté
        concurremment (entre find_one et update_one) est écrasé silencieusement.

        Ici on simule le cas en écrivant un payment manuel APRÈS l'apply split mais AVANT le
        release. Puis release. Le payment manuel doit survivre."""
        a = _mk_invoice(org_scope, 100.00)
        b = _mk_invoice(org_scope, 200.00)
        tx = _mk_tx(org_scope, 300.00)
        _apply_invoice_split_match(tx, [a["id"], b["id"]], org_scope)
        # Simule un payment MANUEL du client sur B, entré directement dans la DB (comme si un
        # concurrent POST /api/invoices/B/payments l'ajoutait entre find_one et update_one).
        manual_payment = {
            "id": str(_uuid.uuid4()),
            "amount_cad": 50.00, "method": "cash",
            "date": "2099-04-22", "reference": "Manuel — hors split",
            "bank_transaction_id": None,  # pas lié à cette tx
            "created_at": "2099-04-22T10:00:00Z",
        }
        db.invoices.update_one(
            {"id": b["id"], **org_scope},
            {"$push": {"payments": manual_payment}})
        # Release cascade (ex: user supprime facture A).
        _release_bank_transaction(tx["id"], org_scope)
        # Le payment manuel sur B doit avoir survécu.
        b_after = _reload_inv(org_scope, b["id"])
        payment_ids = [p["id"] for p in b_after["payments"]]
        assert manual_payment["id"] in payment_ids, \
            "le payment manuel a été écrasé par le cascade (bug $set → doit être $pull)"
        # Et le payment du split est bien parti (car son bank_transaction_id == tx.id).
        assert all(p.get("bank_transaction_id") != tx["id"] for p in b_after["payments"])
        # B a maintenant 1 payment (le manuel) → status partial (50 sur 200).
        assert b_after["status"] == "partial"

    def test_release_non_split_tx_still_resets_fields(self, org_scope):
        """Régression : release d'une tx non-split ne doit pas casser (pas de invoice_ids)."""
        tx = _mk_tx(org_scope, 300.00)
        db.bank_transactions.update_one(
            {"id": tx["id"]},
            {"$set": {"status": "matched", "match_kind": "expense", "match_id": "e-1"}})
        _release_bank_transaction(tx["id"], org_scope)
        released = _reload_tx(org_scope, tx["id"])
        assert released["status"] == "unmatched"
        assert released["match_kind"] is None
        assert released["match_id"] is None
