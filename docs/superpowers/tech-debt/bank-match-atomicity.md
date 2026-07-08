# Dette technique — atomicité du rapprochement bancaire

**Date** : 2026-07-08
**Sévérité** : IMPORTANT (pas BLOCKING en solo dev à faible trafic ; devient BLOCKING dès que
plusieurs utilisateurs concurrents ou trafic élevé)
**Contexte** : identifiée pendant la revue adversariale du F-split (workflow 32 agents, 5 lentilles
× 3 juges). 4 findings BLOCKING confirmés 3/3, mais **existent tous aussi dans `_apply_match`
single** — le split les aggrave (fenêtre plus large) mais ne les crée pas.

## Résumé

Le rapprochement bancaire n'a **aucun mécanisme d'atomicité** entre lecture et écriture Mongo :
- `_apply_match(tx, kind, target_id)` (~ligne 1177) : read tx → check status → push payment → set status
- `_apply_invoice_split_match(tx, target_ids)` (~ligne 1270) : idem sur N invoices en séquence
- `_release_bank_transaction(tx_id)` (~ligne 1099) : idem en cascade sur N invoices

Aucune transaction MongoDB, aucun lock optimiste, aucun compare-and-swap sur `tx.status`.

## Findings différés (revue adverse 2026-07-08)

### #1 — Rollback partiel non-atomique (`_apply_invoice_split_match`, ~ligne 1314)

Loop N-invoices sans wrapper. Si Mongo primary step down au milieu :
- Invoices 1..k ont un payment lié à tx.id, status=paid
- Invoices k+1..N intactes
- `tx.status` reste `unmatched` (dernier `$set` jamais atteint)
- Retry du même split → 409 « outstanding must be > 0 » sur invoice 1 (déjà payée) → recovery
  impossible sans intervention manuelle DB.

**Fix propre** : `client.start_session()` + `session.start_transaction()` autour du loop et du
`$set` final de tx. Requiert un replica set (Atlas OK).

**Fallback sans transaction** : marquer tx en `pending_split_apply=true` AVANT le loop ; endpoint
de repair au startup qui scanne les tx `pending_split_apply` et roll-forward ou roll-back en
inspectant `payments[].bank_transaction_id`.

### #2 — TOCTOU sur `tx.status` (double-clic / retry / deux onglets)

Deux POST /match simultanés sur la même tx passent tous deux le check `tx.get("status") !=
"unmatched"` (snapshot mémoire), et pushent chacun N payments → chaque facture reçoit 2× son
solde.

**Fix propre** : remplacer le check en mémoire par un compare-and-swap Mongo en tête de
`_apply_match` et `_apply_invoice_split_match` :

```python
res = db.bank_transactions.update_one(
    {"id": tx["id"], "status": "unmatched", **scope},
    {"$set": {"status": "matching", "matching_started_at": now}})
if res.modified_count == 0:
    raise HTTPException(409, "Transaction already matched or being matched")
```

Puis à la fin : flip `matching` → `matched`. En cas d'erreur : rollback vers `unmatched`.

### #3 — Overshoot sur splits concurrents avec facture commune

Split X sur (A,B) + split Y sur (B,C) simultanés → B collecte 2× son solde en payments.

**Fix propre** : `updateOne` conditionnel par facture qui vérifie l'invariant sum(payments) + new
≤ total en une seule opération :

```python
res = db.invoices.update_one(
    {"id": iid, **scope, "status": {"$ne": "paid"},
     "$expr": {"$lte": [{"$add": [{"$sum": "$payments.amount_cad"}, payment_amt]}, "$total"]}},
    {"$push": {"payments": payment}})
if res.modified_count == 0:
    # rollback des payments déjà pushés dans le split
    ...
    raise HTTPException(409, "Concurrent modification, please retry")
```

### #6 — Race read/write outstanding entre split et `POST /payments`

Split lit outstanding de B, un `POST /api/invoices/{B}/payments` concurrent ajoute un payment,
split pushe son propre payment → over-payment. Même fix que #3.

### #7 — Partial failure sur `unmatch_bank_transaction` (~ligne 6965)

Si Mongo drop au milieu du loop unmatch, invoices 1..k avec payments retirés, invoices k+1..N
avec payments encore là, tx encore `matched`. Fix : transaction Mongo OU flip tx.status en
`unmatching` avant le loop.

## Fix appliqué en préalable (dans le PR F-split)

**#4 (cascade `$set` écrase concurrent)** : corrigé en utilisant `$pull` par
`bank_transaction_id` au lieu de `$set: payments: [...]`. Voir `_release_bank_transaction` (~ligne
1099) et branche `invoice_split` de `unmatch_bank_transaction` (~ligne 6965). Test de régression
`test_release_preserves_concurrent_manual_payment`.

**#5 (régression paiement partiel)** : corrigé — le bouton "Rapprocher cette facture" est ré-actif
quand nSel=1 sans exigence de somme exacte. Le libellé change en "Rapprocher (paiement partiel)"
quand `selectedSum ≠ txAmt`. Cf. `frontend/src/components/BankManualSearchModal.js`.

## Priorité de traitement

- **Solo dev / faible trafic** : le risque est théorique (aucune concurrence réelle sur une
  organisation à 1 comptable). Documenté ici, à traiter quand FacturePro atteint 5+ comptables
  simultanés dans une même organisation OU quand un client rapporte un incident concret.
- **Traitement recommandé** : un PR dédié qui refactore ATOMIQUEMENT `_apply_match`,
  `_apply_invoice_split_match`, `_release_bank_transaction`, `unmatch_bank_transaction`,
  `POST /api/invoices/{id}/payments`, `DELETE /api/invoices/{id}/payments/{pid}` avec le pattern
  CAS Mongo + transaction. Requiert probablement un replica set (déjà OK sur Atlas prod).
