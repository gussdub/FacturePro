# Acomptes et paiements partiels sur factures

**Date** : 2026-06-16
**Statut** : Brouillon, en attente de revue utilisateur
**Feature originale** : #6 dans la roadmap comptable

## Contexte et motivation

Aujourd'hui, FacturePro a un modèle binaire de statut de paiement : une facture est `draft` → `sent` → `paid` (ou `overdue` si due_date dépassée). Aucune trace des paiements eux-mêmes : ni date, ni montant, ni méthode. Pour un travailleur autonome / TPE, la réalité est différente :

- Un client paye souvent en plusieurs versements (acompte au début, solde à la livraison).
- Le comptable veut voir l'historique : qui a payé combien, quand, par quel moyen.
- Le dashboard doit refléter la trésorerie réelle (« combien on me doit encore ») et pas juste « facture payée / pas payée ».
- Une facture partiellement payée doit pouvoir être relancée sans confusion.

L'objectif est d'introduire un suivi des paiements **embarqué dans la facture**, avec un nouveau statut `partial`, une UI dédiée pour enregistrer / supprimer des paiements depuis la liste des factures, un impact sur le PDF (la facture devient un relevé), et 2 mises à jour du dashboard (overdue inclut partial, + carte « Total à recevoir »).

## Scope

**Inclus** :
- Champ `payments` (array) sur les invoices, avec 5 sous-champs par paiement.
- Nouveau statut canonique `partial`.
- Helper backend `_recompute_invoice_status(invoice)` appelé après chaque modification de `payments`.
- 2 nouveaux endpoints : `POST /api/invoices/{id}/payments` et `DELETE /api/invoices/{id}/payments/{payment_id}`.
- Enrichissement de `GET /api/invoices` et `GET /api/invoices/{id}` avec `total_paid_cad` + `outstanding_cad` calculés.
- Mise à jour de `GET /api/dashboard/overdue` (inclut `partial` + `outstanding_cad` par ligne).
- Nouveau endpoint `GET /api/dashboard/outstanding` (somme totale).
- Modal frontend pour enregistrer / supprimer un paiement depuis la liste InvoicesPage.
- Nouvelle colonne "Solde" dans le tableau des factures.
- Section "Paiements" en bas du PDF de facture si `payments` n'est pas vide.
- Nouveau widget "Total à recevoir" sur le Dashboard.

**Exclus** :
- Multi-devise pour les paiements (`amount_cad` uniquement en CAD). Cas rare ; sera v2.
- Validation backend des méthodes de paiement (le front est libre d'envoyer ce qu'il veut). Standardisation purement front.
- Edition de paiement (mise à jour). Supprimer + ré-enregistrer suffit pour v1.
- Audit log / soft-delete des paiements. v1 supprime physiquement.
- Calcul des reçus de paiement individuels (un PDF par paiement). Le sommaire dans la facture suffit.
- Filtre dashboard par méthode de paiement. Différé.

## Décisions de design

| Question | Choix | Raison |
|---|---|---|
| Structure stockage | Tableau embarqué `invoice.payments[]` | Lecture/écriture atomique, simple, pas de jointure |
| Statut | `partial` explicite | UI et reports instantanés sans recalcul |
| Champs paiement | date, amount_cad, method, reference, notes | Couvre 100 % des cas réels TPE |
| UI saisie | Modal depuis la liste | Découvrable, contexte facture évident |
| PDF | Section paiements en bas si non-vide | Facture devient relevé utile pour relance |
| Dashboard | Overdue mis à jour + nouvelle carte | Couvre détail + vue d'ensemble |

## Data model

### `invoices` (collection existante)

Champ ajouté :

| Champ | Type | Sens |
|---|---|---|
| `payments` | `array[dict]` | Historique des paiements. Défaut `[]`. |

Structure d'un élément `payments[i]` :

```json
{
  "id": "uuid",
  "date": "2026-04-15",
  "amount_cad": 200.00,
  "method": "cheque",
  "reference": "Chèque #1234",
  "notes": "",
  "created_at": "2026-04-15T10:00:00+00:00"
}
```

**Méthodes canoniques côté frontend** : `cash | cheque | transfer | card | etransfer | stripe | other`. Le backend stocke la valeur reçue sans validation.

**Statut `partial`** ajouté aux valeurs canoniques. Ensemble complet : `draft | sent | partial | paid | overdue`.

**Aucune migration** : invoices existantes sans `payments` sont traitées comme `[]` partout (`.get("payments", [])`).

## Backend

### Helper (`server.py`)

```python
def _recompute_invoice_status(invoice):
    """Détermine le statut basé sur le total payé vs total. Ne touche pas draft.

    - total_paid >= total et total > 0 → 'paid'
    - 0 < total_paid < total → 'partial'
    - total_paid == 0 → on conserve le statut actuel (sent ou overdue)
    """
    payments = invoice.get("payments", []) or []
    total_paid = sum(float(p.get("amount_cad", 0) or 0) for p in payments)
    total = float(invoice.get("total", 0) or 0)
    if total_paid >= total and total > 0:
        return "paid"
    if total_paid > 0:
        return "partial"
    return invoice.get("status", "sent")


def _enrich_invoice(invoice):
    """Ajoute total_paid_cad et outstanding_cad au doc invoice. Mutation in-place."""
    payments = invoice.get("payments", []) or []
    total_paid = round(sum(float(p.get("amount_cad", 0) or 0) for p in payments), 2)
    total = float(invoice.get("total", 0) or 0)
    invoice["total_paid_cad"] = total_paid
    invoice["outstanding_cad"] = round(max(0, total - total_paid), 2)
    return invoice
```

### Endpoints modifiés

| Endpoint | Changement |
|---|---|
| `GET /api/invoices` | Chaque doc enrichi avec `total_paid_cad` + `outstanding_cad` |
| `GET /api/invoices/{id}` | Même enrichissement |
| `PUT /api/invoices/{id}/status` | Accepte `partial` (permis manuel mais découragé — le helper recompute habituellement) |
| `GET /api/dashboard/overdue` | Filtre `status ∈ {sent, partial, overdue}`, chaque ligne a `outstanding_cad` |

### Nouveaux endpoints

```python
@app.post("/api/invoices/{invoice_id}/payments")
def add_invoice_payment(invoice_id: str, body: dict,
                         current_user: User = Depends(get_current_user_with_access)):
    """Enregistre un paiement. Recalcule le statut."""
    invoice = db.invoices.find_one({"id": invoice_id, "user_id": current_user.id}, {"_id": 0})
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    payment = {
        "id": str(uuid.uuid4()),
        "date": body.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "amount_cad": float(body.get("amount_cad", 0) or 0),
        "method": body.get("method", "other"),
        "reference": body.get("reference", ""),
        "notes": body.get("notes", ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    invoice.setdefault("payments", []).append(payment)
    new_status = _recompute_invoice_status(invoice)
    db.invoices.update_one(
        {"id": invoice_id, "user_id": current_user.id},
        {"$push": {"payments": payment}, "$set": {"status": new_status}}
    )
    fresh = db.invoices.find_one({"id": invoice_id}, {"_id": 0})
    return _enrich_invoice(fresh)


@app.delete("/api/invoices/{invoice_id}/payments/{payment_id}")
def delete_invoice_payment(invoice_id: str, payment_id: str,
                            current_user: User = Depends(get_current_user_with_access)):
    """Supprime un paiement. Recalcule le statut."""
    invoice = db.invoices.find_one({"id": invoice_id, "user_id": current_user.id}, {"_id": 0})
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    payments = [p for p in invoice.get("payments", []) if p.get("id") != payment_id]
    invoice["payments"] = payments
    new_status = _recompute_invoice_status(invoice)
    db.invoices.update_one(
        {"id": invoice_id, "user_id": current_user.id},
        {"$set": {"payments": payments, "status": new_status}}
    )
    fresh = db.invoices.find_one({"id": invoice_id}, {"_id": 0})
    return _enrich_invoice(fresh)


@app.get("/api/dashboard/outstanding")
def get_dashboard_outstanding(current_user: User = Depends(get_current_user_with_access)):
    """Total des soldes restants pour les invoices non-finalisées."""
    invoices = list(db.invoices.find({
        "user_id": current_user.id,
        "status": {"$in": ["sent", "partial", "overdue"]},
    }, {"_id": 0}))
    total = 0.0
    for inv in invoices:
        payments = inv.get("payments", []) or []
        paid = sum(float(p.get("amount_cad", 0) or 0) for p in payments)
        total += max(0, float(inv.get("total", 0) or 0) - paid)
    return {"total_outstanding_cad": round(total, 2), "invoice_count": len(invoices)}
```

### PDF (`generate_document_pdf`)

Avant le footer "Merci…", **si `payments` non-vide** :

```python
payments = document.get("payments", []) or []
if doc_type == "invoice" and payments:
    method_labels = {
        "cash": "Comptant", "cheque": "Chèque", "transfer": "Virement",
        "card": "Carte", "etransfer": "Virement Interac", "stripe": "Stripe",
        "other": "Autre",
    }
    elements.append(Spacer(1, 0.3*inch))
    elements.append(Paragraph("Paiements", bold_style))
    rows = [["Date", "Méthode", "Référence", "Montant"]]
    for p in payments:
        rows.append([
            p.get("date", ""),
            method_labels.get(p.get("method", "other"), p.get("method", "")),
            p.get("reference", ""),
            f"{p.get('amount_cad', 0):,.2f} $".replace(",", " "),
        ])
    total_paid = sum(float(p.get("amount_cad", 0) or 0) for p in payments)
    outstanding = max(0, float(document.get("total", 0)) - total_paid)
    rows.append(["", "", "Total payé", f"{total_paid:,.2f} $".replace(",", " ")])
    rows.append(["", "", "Solde restant", f"{outstanding:,.2f} $".replace(",", " ")])
    # ... assemble Table avec style cohérent
```

## Frontend

### `InvoicesPage.js`

**Nouvelle colonne "Solde"** entre "Total" et "Statut" :

```jsx
<td>{fmt(invoice.outstanding_cad ?? invoice.total)}</td>
```

**Bouton "💰 Paiement"** dans la colonne Actions ouvre `<PaymentModal />`.

**`<PaymentModal invoice onClose onSaved />`** :
- État local : `formDate`, `formAmount`, `formMethod`, `formReference`, `formNotes`.
- À l'ouverture : pré-remplit `formAmount` avec `invoice.outstanding_cad`.
- Liste l'historique `invoice.payments` avec un ⓧ par ligne (DELETE).
- Bouton "Enregistrer" → POST `/api/invoices/{id}/payments` → set local invoice, callback `onSaved(updated)`.
- Statut affiché en haut : Total / Total payé / Solde.

### `Dashboard.js`

Nouveau composant `<OutstandingCard />` :

- Fetch `GET /api/dashboard/outstanding` au mount.
- Carte : titre "Total à recevoir", montant en gros, nombre de factures en bas.
- Clic → navigate('/invoices') (pas critique, peut être skip pour v1).

Placée à côté des cartes KPI existantes du dashboard (ex: Revenus, Dépenses, etc.).

## Tests

### Unitaires (`backend/tests/test_partial_payments.py`)

- `_recompute_invoice_status` : 7 cas (vide, complet, partiel, multi-paiements, sur-paiement, total 0, overdue conservé).
- `_enrich_invoice` : 2 cas (sans paiements → outstanding = total ; avec paiements → outstanding correct).

### Intégration (`backend/tests/test_partial_payments_integration.py`)

- POST paiement partiel → status `partial`, outstanding correct.
- POST paiement soldant → status `paid`, outstanding 0.
- POST 2e paiement après partiel jusqu'à solder → `paid`.
- DELETE paiement → status recalculé.
- DELETE le seul paiement d'une facture partial → revient à `sent`.
- GET `/api/invoices` enrichi (total_paid_cad et outstanding_cad présents).
- GET `/api/dashboard/overdue` inclut partial dépassées.
- GET `/api/dashboard/outstanding` retourne la bonne somme.
- GET PDF avec paiements → 200, content-type PDF, magic bytes.

### Vérifications manuelles UI

| Cas | Attendu |
|---|---|
| Click "💰 Paiement" | Modal ouvert, pré-rempli avec solde |
| Enregistrer paiement partiel | Modal reste, historique mis à jour, statut "Partiel" sur ligne |
| Solder en un paiement | Statut "Payé", solde 0 |
| Click ⓧ sur paiement | Statut recalculé après confirmation |
| Dashboard reload | Carte "Total à recevoir" reflète la somme |
| PDF facture partielle | Section "Paiements" en bas avec total + solde |

## Risques et limites

- **Pas de validation sur `method`** : un frontend bogué pourrait envoyer "foo". Le backend l'accepte, le PDF affichera "foo" tel quel (pas mappé). Trade-off : on évite de hard-coder la liste backend pour faciliter futures évolutions.
- **Pas d'edit de paiement** : pour corriger un montant ou une date, l'utilisateur doit supprimer et ré-enregistrer. Acceptable pour v1.
- **Pas de soft-delete / audit log** : un paiement supprimé est perdu. Acceptable pour TPE sans contrainte audit forte.
- **Sur-paiement** : si la somme dépasse le total, on passe à `paid` (le surplus n'est pas modélisé comme "crédit client"). Acceptable, edge case rare.
- **Multi-devise** : tous les paiements sont en CAD. Si un client paye en USD, l'utilisateur convertit manuellement avant saisie.
- **Outstanding calculé à chaque GET** : pour des milliers d'invoices ce serait un problème. Pour l'échelle TPE (< 1000 invoices/an), c'est trivial.
- **Concurrence** : si deux requêtes POST `/payments` arrivent en simultané sur la même invoice, le `$push` est atomique mais le `_recompute_invoice_status` lit l'état avant l'update. Risque négligeable pour 1 utilisateur, mais notable.

## Métriques de succès

- L'utilisateur peut enregistrer un paiement en moins de 4 clics depuis la liste des factures.
- Le statut d'une facture passe automatiquement à `partial` puis `paid` selon les paiements enregistrés.
- Le dashboard affiche le bon montant total à recevoir.
- Le PDF d'une facture partielle est lisible et utilisable comme relevé.
- Aucune régression sur les invoices déjà existantes (champ absent → considéré comme `[]`).
- > 145 tests cumulés sur le projet.
