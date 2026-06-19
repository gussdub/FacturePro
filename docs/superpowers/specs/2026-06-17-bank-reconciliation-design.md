# Rapprochement bancaire (feature #7) — Design

**Statut :** design approuvé 2026-06-17 (révisé après critique multi-angles)
**Auteur :** Claude (brainstorming session avec gussdub)

## 1. Objectif

Permettre à un utilisateur d'importer un relevé bancaire CSV et de rapprocher chaque ligne avec ses factures (via création automatique d'un paiement de la feature #6) ou ses dépenses existantes. Couvre revenus ET dépenses sur le même écran.

Cas d'usage principal : à la fin de chaque mois, l'utilisateur exporte son CSV depuis le portail de sa banque (Desjardins, RBC, BMO, etc.), l'importe dans FacturePro, valide les matchs auto-proposés et règle manuellement le reste. Une fois fini, ses statuts de factures et la base de dépenses reflètent la réalité bancaire.

## 2. Décisions de design (brainstorming)

| # | Question | Décision |
|---|----------|----------|
| 1 | Portée du rapprochement | **Revenus + dépenses** sur un seul écran. |
| 2 | Stratégie match auto | **Tolérant** : montant ±0,01 $, date ±3 jours. Auto-match seulement si candidat unique avec score parfait. |
| 3 | Format CSV | **Mapping configurable** par l'utilisateur, sauvegardable par banque. |
| 4 | Résultat d'un match (facture) | **Création automatique du paiement** (feature #6). |
| 5 | Lignes orphelines | **Création rapide** d'une dépense ou facture depuis la ligne CSV. |
| 6 | Persistance | **Tout est persisté** (collections `bank_imports`, `bank_transactions`, `bank_mappings`). |
| 7 | Emplacement UI | **Page dédiée** dans la sidebar. |

## 3. Architecture & modèle de données

Trois nouvelles collections MongoDB.

### 3.1 `bank_mappings`

Mapping de colonnes par banque, réutilisable.

```python
{
  "id": str,                          # uuid
  "user_id": str,
  "bank_label": str,                  # libre, ex: "Desjardins perso", "RBC business"
  "delimiter": str,                   # "," | ";" | "\t"
  "has_header": bool,
  "date_column": int,                 # index 0-based
  "date_format": str,                 # "YYYY-MM-DD" | "DD/MM/YYYY" | "MM/DD/YYYY"
  "description_column": int,
  "amount_mode": str,                 # "single" | "debit_credit"
  "amount_column": int | None,
  "debit_column": int | None,
  "credit_column": int | None,
  "sign_convention": str,             # "positive_is_credit" | "positive_is_debit"
  "created_at": str,                  # ISO datetime
  "last_used_at": str
}
```

Index : `(user_id, bank_label)` (non-unique — label libre, l'utilisateur peut avoir « Desjardins perso » et « Desjardins entreprise »).

**Limite** : max 20 mappings par user (POST renvoie 409 au-delà). Couvre toutes les banques réalistes pour une TPE.

### 3.2 `bank_imports`

Métadonnée d'un upload.

```python
{
  "id": str,
  "user_id": str,
  "mapping_id": str | None,           # None si mapping inline non sauvegardé
  "bank_label": str,                  # snapshot au moment de l'import
  "filename": str,
  "file_hash": str,                   # sha256 du contenu — anti-duplicata par user
  "row_count": int,                   # nb de lignes parsées (hors header)
  "skipped_rows": int,                # lignes vides / illisibles
  "imported_at": str,
  "closed_at": str | None             # null tant que la session est ouverte
}
```

**Pas de compteurs `matched_count` / `ignored_count`** — calculés live via `db.bank_transactions.count_documents(...)` au moment du GET. Évite tout risque de drift.

Index :
- `(user_id, file_hash)` **UNIQUE** — anti-duplicata par user (un autre user peut importer le même CSV).
- `(user_id, imported_at)` — liste triée.

### 3.3 `bank_transactions`

Une ligne CSV = un document.

```python
{
  "id": str,
  "user_id": str,
  "import_id": str,
  "row_index": int,                   # 0-based dans le CSV
  "date": str | None,                 # YYYY-MM-DD, null si parse_error
  "description": str,                 # libellé brut sanitisé (cf. 4.2 CSV injection)
  "amount_cad": float | None,         # >0=crédit, <0=débit, None si parse_error
  "parse_error": bool,
  "raw_line": str | None,             # ligne CSV originale tronquée à 500 char,
                                      # set UNIQUEMENT si parse_error=True
  "status": str,                      # "unmatched" | "matched" | "ignored"
  "match_kind": str | None,           # None | "invoice_payment" | "expense"
  "match_id": str | None,             # id du payment OU id de l'expense
  "invoice_id": str | None,           # set seulement si match_kind="invoice_payment"
                                      # (redondant avec lookup, mais accélère la cascade)
  "matched_at": str | None
}
```

Index :
- `(user_id, import_id, status)` — filtre principal de l'écran de matching.
- `(user_id, status)` — vues globales (optionnel v2).

### 3.4 Liens retour

Ajout de champs optionnels sur collections existantes :
- `invoice.payments[i].bank_transaction_id: str | None` (set quand le payment est créé via rapprochement)
- `expense.bank_transaction_id: str | None` (set quand l'expense est liée)

### 3.5 Cascade & cleanup (CRITIQUE)

Trois modifications obligatoires d'endpoints existants :

**`DELETE /api/invoices/{invoice_id}`** — avant la suppression :
```python
for payment in invoice.get("payments", []):
    btx_id = payment.get("bank_transaction_id")
    if btx_id:
        db.bank_transactions.update_one(
            {"id": btx_id, "user_id": current_user.id},
            {"$set": {"status": "unmatched", "match_kind": None,
                      "match_id": None, "invoice_id": None, "matched_at": None}},
        )
```

**`DELETE /api/invoices/{invoice_id}/payments/{payment_id}`** (feature #6) — symétrique :
```python
# avant de pull le payment, récupérer son bank_transaction_id
payment = next((p for p in invoice["payments"] if p["id"] == payment_id), None)
if payment and payment.get("bank_transaction_id"):
    db.bank_transactions.update_one(
        {"id": payment["bank_transaction_id"], "user_id": current_user.id},
        {"$set": {"status": "unmatched", "match_kind": None,
                  "match_id": None, "invoice_id": None, "matched_at": None}},
    )
```

**`DELETE /api/expenses/{expense_id}`** :
```python
expense = db.expenses.find_one({"id": expense_id, "user_id": current_user.id})
if expense and expense.get("bank_transaction_id"):
    db.bank_transactions.update_one(
        {"id": expense["bank_transaction_id"], "user_id": current_user.id},
        {"$set": {"status": "unmatched", "match_kind": None,
                  "match_id": None, "matched_at": None}},
    )
```

Tous les filtres incluent `user_id` — pas de cross-tenant possible.

### 3.6 Cardinalité

5 ans × 4 imports/mois × ~100 lignes ≈ 24 000 docs/user. Collection séparée justifiée (au-delà du seuil d'embarquement). Les requêtes UI restent rapides avec les index ci-dessus.

## 4. API REST

Toutes routes sous `/api/bank/`, auth requise. **TOUS les endpoints qui prennent un `{id}` en path** (mapping, import, transaction) doivent résoudre l'objet avec un filtre `{"id": <id>, "user_id": current_user.id}` et renvoyer 404 si non trouvé. Pas d'exception.

### 4.1 Mappings (CRUD partiel v1)

```
GET    /api/bank/mappings              → [bank_mapping, ...]
POST   /api/bank/mappings              body: bank_mapping (sans id)        → bank_mapping (201)
                                       409 si l'utilisateur a déjà 20 mappings
```

**Pas de PUT ni DELETE en v1** — un mapping erroné est simplement non-réutilisé, l'utilisateur crée un nouveau avec un label différent. Reporté en v2 quand une page « Settings > Mappings » sera scopée.

### 4.2 Imports

```
POST   /api/bank/imports               multipart: file=CSV, mapping_id=str OU mapping=JSON
                                       query: dry_run=bool (default false)
                                       → si dry_run=true : {parsed_rows: [...10 premières], errors: [...]}
                                                            (n'écrit RIEN en base)
                                       → si dry_run=false : {import: {...}, transactions: [...]}
                                                            (lance aussi le match auto)

GET    /api/bank/imports               query: limit=50 (default, max 50)
                                       → [bank_import_with_counts, ...] (tri imported_at desc)
                                       counts calculés live : matched_count, ignored_count, unmatched_count

GET    /api/bank/imports/{id}          query: page=1, per_page=100 (max 500)
                                       → {import, transactions: [...], total_count, page, per_page}

POST   /api/bank/imports/{id}/close                                         → 204
DELETE /api/bank/imports/{id}          query: force=true si closed_at set
                                       → 204 (cascade décrit en 7)
                                       409 si fermé et pas de force=true
```

**Validations à l'entrée de POST /api/bank/imports** (dans l'ordre, AVANT toute autre logique) :
1. `Content-Length > 5 242 880 (5 MB)` → **413 Payload Too Large**.
2. Lecture streamée du body. Si le total réel dépasse 5 MB → 413.
3. `row_count > 5 000` (counting via générateur, early-exit après 5 001ᵉ ligne) → **413** avec `{detail: "File exceeds row limit: 5000"}`.
4. Calcul `file_hash` (sha256) — seulement après les checks de taille.
5. Lookup `{user_id, file_hash}` → si existe → **409 Conflict** `{detail: "Duplicate import", import_id: <existing>}`.
6. Parser CSV → si moins de 2 colonnes assignables → **422**.

**Sanitisation des cellules CSV** (toutes les colonnes, avant stockage) :
```python
def _sanitize_cell(value: str) -> str:
    if not value: return ""
    # Protection CSV-injection (formula): strip si commence par = + - @
    stripped = value.lstrip()
    if stripped and stripped[0] in ("=", "+", "-", "@", "\t"):
        return stripped[1:]
    return value
```

### 4.3 Matching

**Convention vocabulaire** (CRITIQUE) :
- Body API : `kind = "invoice_payment" | "expense"` (identique au champ DB `match_kind`).
- UI/copy : « rapprochement » / « rapprocher » (français).
- Code Python/JS : `match`, `matched`, `unmatched` (anglais).

```
GET    /api/bank/transactions/{tx_id}/suggestions    → {invoices: [...max 3], expenses: [...max 3]}
                                                     (calculé à chaque appel, non persisté)

POST   /api/bank/transactions/{tx_id}/match          body: {kind, target_id}
                                                     → bank_transaction (mise à jour)
                                                     Comportement détaillé ci-dessous.

POST   /api/bank/transactions/{tx_id}/unmatch        → bank_transaction (status=unmatched)

POST   /api/bank/transactions/{tx_id}/ignore         → bank_transaction (status=ignored)
POST   /api/bank/transactions/{tx_id}/unignore       → bank_transaction (status=unmatched)
```

**Comportement de POST /match (handler partagé `_apply_match(tx, kind, target_id, user_id)`)** :

```python
# Pre-conditions
target = db[collection].find_one({"id": target_id, "user_id": user_id})
if not target: raise 404
if tx.status != "unmatched": raise 409 "Transaction already matched or ignored"

if kind == "invoice_payment":
    if target["status"] == "paid":
        raise 409 "Invoice already fully paid"
    # crée un payment
    payment = {
        "id": str(uuid.uuid4()),
        "amount_cad": abs(tx.amount_cad),
        "method": "transfer",           # hardcoded v1 — éditable après via UI feature #6
        "date": tx.date,
        "reference": tx.description[:200],
        "bank_transaction_id": tx.id,
        "created_at": now_iso(),
    }
    db.invoices.update_one(
        {"id": target_id, "user_id": user_id},
        {"$push": {"payments": payment}}
    )
    # recalcule statut via _recompute_invoice_status (helper feature #6)
    db.invoices.update_one({"id": target_id, "user_id": user_id},
                           {"$set": {"status": _recompute_invoice_status(...)}})
    match_kind = "invoice_payment"
    match_id = payment["id"]
    invoice_id = target_id

elif kind == "expense":
    db.expenses.update_one(
        {"id": target_id, "user_id": user_id},
        {"$set": {"bank_transaction_id": tx.id}}
    )
    match_kind = "expense"
    match_id = target_id
    invoice_id = None

else:
    raise 422 "Invalid kind"

# update transaction
db.bank_transactions.update_one(
    {"id": tx.id, "user_id": user_id},
    {"$set": {"status": "matched", "match_kind": match_kind,
              "match_id": match_id, "invoice_id": invoice_id,
              "matched_at": now_iso()}}
)
```

**Note : pas de validation directionnelle.** Un crédit peut être manuellement matché à une expense (cas de remboursement), un débit à une invoice (renvoi). L'UI affichera un warning visuel mais ne bloquera pas. L'auto-match (section 5), lui, respecte la direction.

**POST /unmatch** doit miroir `DELETE /api/invoices/{id}/payments/{pid}` (feature #6) : reset status à `"sent"` avant `_recompute_invoice_status` pour gérer correctement le cas où le payment ramenait l'invoice à `paid` depuis `overdue`.

### 4.4 Création depuis transaction

```
POST   /api/bank/transactions/{tx_id}/create-expense  body: {category_code, vendor?, taxes_paid?}
                                                      → {expense, transaction}

POST   /api/bank/transactions/{tx_id}/create-invoice  body: {client_id, item_description?}
                                                      → {invoice, transaction}
```

**`create-expense`** : montant = `abs(tx.amount_cad)`, date = `tx.date`, vendor = body.vendor ou `tx.description` tronqué 60 char, currency = "CAD". Catégorie obligatoire (sélecteur ARC). Snapshots feature #3 appliqués. `taxes_paid` (TPS/TVQ/TVH) restent à 0 par défaut (modifiables après via ExpensesPage — pas d'edge case TVH/TPS au moment du rapprochement rapide). `bank_transaction_id = tx.id` set sur l'expense créée.

**`create-invoice`** (SIMPLIFIÉ par rapport au brainstorming) : pour éviter la complexité du back-calcul de taxes :
- `client_id` obligatoire.
- Un seul article : `description = body.item_description ou "Encaissement bancaire — " + tx.description[:60]`, `quantity=1`, `unit_price = abs(tx.amount_cad)`.
- `subtotal = abs(tx.amount_cad)` — **pas de taxes ajoutées**. La logique : si l'argent reçu en banque inclut des taxes, le sous-total + le total seront identiques (au mieux trompeur sur le PDF). L'utilisateur doit corriger après via l'UI standard si nécessaire.
- `status = "paid"`, un `payment` auto-inséré avec `amount_cad = total`, `method="transfer"`, `bank_transaction_id = tx.id`.
- Snapshots `tax_registrations` feature #2 appliqués.
- Documenter en commentaire UI : « Cette facture est créée sans taxes — édite-la après si nécessaire. »

## 5. Algorithme de match auto

Exécuté en boucle dans `POST /api/bank/imports` (`dry_run=false`) sur les transactions fraîchement créées avec `status="unmatched"` ET `parse_error=False`. Code dans `_auto_match_transactions(import_id, user_id)`.

**Optimisation N+1 → O(1)** : avant la boucle, charger en mémoire toutes les candidates :
- `open_invoices = list(db.invoices.find({"user_id": user_id, "status": {"$in": ["sent", "partial", "overdue"]}}))` puis enrich Python (`_enrich_invoice` ajoute `outstanding_cad`).
- `open_expenses = list(db.expenses.find({"user_id": user_id, "bank_transaction_id": None}))`.
- Cache une `dict[client_id → client.name]` et `dict[expense_id → vendor.lower()]` pour les checks textuels.

Puis pour chaque transaction :

```python
def _auto_match_transaction(tx, open_invoices, open_expenses, clients_by_id, user_id):
    if tx.date is None or tx.amount_cad is None:
        return None  # parse_error — pas de match auto, l'UI affichera "Chercher manuellement"

    target = abs(tx.amount_cad)
    desc_lower = tx.description.lower()
    candidates = []

    if tx.amount_cad > 0:  # CRÉDIT — match sur factures
        for inv in open_invoices:
            outstanding = inv["outstanding_cad"]   # enrichi en Python
            if abs(outstanding - target) > 0.01:
                continue
            # fenêtre : lookback 90j (factures émises il y a longtemps acceptées),
            #          lookahead 3j (encaissements parfois pré-datent l'émission)
            issue = parse_date(inv["issue_date"])
            if not (tx.date - timedelta(days=90) <= issue <= tx.date + timedelta(days=3)):
                continue
            # scoring (max 3) :
            #   +1 montant exact  (toujours vrai pour les candidats — c'est le filtre lui-même)
            #   +1 date proche selon due_date OU issue_date (peu importe lequel matche)
            #   +1 nom client présent dans description
            due = parse_date(inv.get("due_date") or inv["issue_date"])
            client_name = (clients_by_id.get(inv["client_id"]) or "").lower()
            score = 1
            if abs((tx.date - due).days) <= 3 or abs((tx.date - issue).days) <= 3:
                score += 1
            if client_name and len(client_name) >= 3 and client_name in desc_lower:
                score += 1
            candidates.append({"kind": "invoice_payment", "target": inv,
                               "score": score,
                               "date_diff": min(abs((tx.date - due).days), abs((tx.date - issue).days)),
                               "amount_diff": abs(outstanding - target)})

    elif tx.amount_cad < 0:  # DÉBIT — match sur dépenses
        for exp in open_expenses:
            if abs(exp["amount_cad"] - target) > 0.01:
                continue
            exp_date = parse_date(exp["date"])
            if abs((tx.date - exp_date).days) > 3:
                continue
            vendor = (exp.get("vendor") or "").lower()
            score = 1
            if abs((tx.date - exp_date).days) <= 1:
                score += 1
            if vendor and len(vendor) >= 3 and vendor in desc_lower:
                score += 1
            candidates.append({"kind": "expense", "target": exp,
                               "score": score,
                               "date_diff": abs((tx.date - exp_date).days),
                               "amount_diff": abs(exp["amount_cad"] - target)})

    if not candidates:
        return None

    # Tri : score desc, puis date_diff asc, puis amount_diff asc (tie-breaker déterministe).
    candidates.sort(key=lambda c: (-c["score"], c["date_diff"], c["amount_diff"]))

    top = candidates[0]
    if top["score"] == 3 and (len(candidates) == 1 or candidates[1]["score"] < 3):
        # auto-match : unique candidat parfait
        _apply_match(tx, kind=top["kind"], target_id=top["target"]["id"], user_id=user_id)
        return top

    return None  # suggestions seront servies via GET /suggestions
```

**Max effectif du score = 3** (montant exact + date proche + nom trouvé). Si le nom client/vendor n'est pas dans la description, max = 2 → pas d'auto-match → suggestion seulement. C'est intentionnel : on évite les faux positifs sur des montants ronds (ex: deux factures de 250 $ le même jour).

**Suggestions à la demande** (GET /suggestions) : applique la même logique mais sans appliquer le match. Retourne top 3 invoices + top 3 expenses, déjà triées. Filtre identique (paid/linked exclus).

## 6. Flow UI

Nouvelle page `BankReconciliationPage.js`, accessible via le path géré côté frontend (label sidebar « Rapprochement », icône `GitMerge` lucide-react).

### 6.1 Vue par défaut — liste des imports

Tableau : Date / Banque / Lignes / Matchées (live count) / Solde % / État (Ouvert/Fermé). Bouton « + Nouvel import ». Clic sur ligne → écran de matching (6.3).

**Limite v1** : affichage des 50 imports les plus récents (champ `limit=50` côté backend). Plus tard, ajouter une pagination si besoin.

**Empty state** (zéro import) : illustration + CTA primaire « Importer votre premier relevé ».

### 6.2 Wizard nouvel import (3 étapes plein écran)

**Étape 1 — Upload.** Champ « Banque » (libre, autocomplete sur `bank_mappings` filtrés case-insensitive trimmed). Drop-zone CSV (drag-drop ou clic, max 5 MB). Si un mapping existe pour le label saisi (match case-insensitive trimmed) → étape 2 pré-remplie (l'utilisateur ne saute PAS l'étape 2 — il doit cliquer « Suivant » pour confirmer que le mapping reste valide ; les banques changent parfois leur format).

**Étape 2 — Mapping colonnes.** Tableau aperçu (10 premières lignes via POST /imports avec `dry_run=true`). Au-dessus de chaque colonne : select (« — ignorer — », Date, Description, Montant, Débit, Crédit). En bas : format date (3 choix), délimiteur (auto-détecté, modifiable), checkbox « 1ère ligne = en-têtes » (auto-cochée si la 1re ligne ne se parse pas en date).

Bouton « Vérifier » désactivé tant que :
- Au moins une colonne assignée à Date.
- Au moins une à Description.
- Soit Montant assigné, soit Débit ET Crédit assignés.

Sur clic « Vérifier » → POST /imports `dry_run=true` → succès rend « Importer » actif et affiche les 10 lignes parsées. Erreurs → liste warnings dismissibles sous la table.

Checkbox « Sauvegarder ce mapping ».

**Loading state** : spinner « Vérification du fichier… ». POST /imports (dry_run=false) → spinner plein écran « Import et rapprochement en cours… » (avec message « cela peut prendre 5 à 30 secondes pour un gros relevé » après 3 s).

**Navigation away** étapes 1-2 : l'état est perdu, pas de beforeunload. C'est volontaire — l'utilisateur n'a rien sauvegardé. Une fois en étape 3 l'import est persisté donc safe.

### 6.3 Écran de matching

Liste verticale des transactions. Cinq états visuels :

| Icône | DB state | Affichage |
|-------|----------|-----------|
| ● ambre | `unmatched` + suggestions | montre top candidat, boutons « Confirmer / Voir autres / Ignorer » |
| ? rouge | `unmatched` sans suggestion ET `parse_error=false` | boutons « Chercher manuellement / Créer facture ou dépense / Ignorer » |
| 🟥 rouge bordure | `parse_error=true` | bandeau « Ligne illisible (date ou montant) » + boutons « Voir ligne brute / Ignorer » |
| ✓ vert | `matched` | montre la cible matchée, bouton « Défaire » |
| ✗ gris | `ignored` | bouton « Annuler ignorer » |

Filtres : Tout / Non rapprochées / Matchées / Ignorées + recherche texte sur description.

Barre de progression : **`(matched_count + ignored_count) / (row_count - skipped_rows)` × 100 %** — compteurs calculés live côté backend dans `GET /api/bank/imports/{id}`. À 100 %, le bouton « Fermer cet import » apparaît (banner explicatif « Toutes les transactions sont rapprochées ou ignorées »).

**Modal « Chercher manuellement »** : recherche live. Pool restreint pour éviter erreurs :
- Crédit : invoices `status IN ("sent", "partial", "overdue")` du user.
- Débit : expenses où `bank_transaction_id IS NULL` du user.

**Modal « Créer dépense »** : prérempli date / montant / vendor (description tronquée 60 char). Sélecteur catégorie ARC obligatoire (composant feature #3 — l'extraire dans `ExpenseCategoryPicker` si pas déjà fait). Champs `taxes_paid` cachés (= 0 par défaut, éditables plus tard dans ExpensesPage).

**Modal « Créer facture »** (lignes positives) : sélecteur client obligatoire. Item unique avec description éditable. Note explicite : « Cette facture est créée sans taxes — modifie-la après si nécessaire. »

### 6.4 Empty states (récap)

- Aucun import → CTA « Importer votre premier relevé ».
- Import 100 % réglé → banner « Toutes les transactions sont rapprochées » + bouton « Fermer cet import ».
- GET /suggestions vide → la ligne s'affiche immédiatement en état `? rouge` (pas de spinner intermédiaire).

### 6.5 Erreurs (récap)

Toasts pour :
- 409 duplicate CSV → toast avec lien « Voir l'import existant ».
- 422 mapping invalide → message inline sous le bouton « Vérifier ».
- 413 fichier trop gros → toast « Fichier trop volumineux (max 5 MB / 5 000 lignes) ».
- 409 match sur invoice paid → toast « Cette facture est déjà entièrement payée ».
- Erreur réseau (match/unmatch/etc.) → toast « Erreur réseau, réessayer ».

Le pattern toast réutilise celui des features #2-#6 (à confirmer en lisant `frontend/src/App.js` ou `Layout.js`).

### 6.6 Mobile / Responsive

**Hors scope v1.** L'écran de matching est dense et destiné au desktop. Sur mobile, on tolère le scroll horizontal — pas de layout adaptatif spécifique. Si demande post-launch, on collapsera en card-per-transaction à <768px (v2).

## 7. Edge cases

| Cas | Comportement |
|-----|--------------|
| Re-import du même CSV (`(user_id, file_hash)` identique) | 409 Conflict + `import_id` existant dans le body. |
| Re-import du même CSV par un AUTRE user | OK — aucun lien, hash unique par user. |
| Ligne CSV vide / colonnes manquantes | Skip, comptée dans `skipped_rows`. |
| Date illisible / montant illisible | `parse_error=true`, `date/amount_cad=None`, `raw_line` stockée. État visuel `🟥` dans l'UI. Auto-match skip. |
| Notation européenne (`1 234,56`) | Parseur essaie `,` puis `.` comme séparateur décimal, supprime les espaces non-cassants. |
| Sign convention `positive_is_debit` | Applique `amount_cad = -raw_amount` après parsing. En mode `debit_credit`, `sign_convention` est ignoré (sign inféré de la colonne remplie). |
| Mode `debit_credit`, les 2 colonnes > 0 | `amount_cad = credit - debit` (résultat signé). Si valeur négative dans une colonne → prend l'absolu d'abord. |
| Mode `debit_credit`, les 2 colonnes vides ou 0 | `amount_cad = 0` (la ligne existe, ne match rien, peut être ignorée manuellement). |
| Cellule commençant par `= + - @` | Premier caractère strippé (CSV injection protection). |
| Paiement Interac sur 2 lignes (montant + frais) | Pas de gestion spéciale ; les frais (< 5 $) sont typiquement ignorés. |
| Facture en USD payée en CAD | Compare `outstanding_cad` (déjà converti via `exchange_rate_to_cad`) au `tx.amount_cad`. |
| Plusieurs candidates avec même score | Tri tie-breaker déterministe (date_diff asc, puis amount_diff asc). Auto-match seulement si UN unique candidat score=3 ET le 2e a score<3. |
| POST /match sur invoice déjà `paid` | 409 Conflict. |
| POST /match avec target_id d'un AUTRE user | 404 Not Found (filtre `user_id` au lookup). |
| POST /match dans direction inverse (crédit→expense ou débit→invoice) | Pas bloqué (cas refunds/corrections). L'UI affichera un warning visuel. |
| DELETE expense liée | Cascade définie en 3.5 : libère la `bank_transaction`. |
| DELETE invoice liée | Cascade définie en 3.5 : pour chaque payment avec `bank_transaction_id`, libère la `bank_transaction`. |
| DELETE payment via `/api/invoices/{id}/payments/{pid}` (feature #6) | Cascade définie en 3.5 : libère la `bank_transaction` du payment. |
| DELETE bank_import non-fermé | OK, cascade sur transactions + libère payments créés (algo en 4.2). |
| DELETE bank_import fermé | Requiert `force=true`. UI affiche modal de confirmation listant : N transactions, M payments removed, K invoices status reverted. Log structuré à l'INFO. |
| EDIT expense liée à une bank_transaction | Le lien persiste sans re-validation (montant ou date modifié → user doit unmatch + re-match si besoin). Documenté comme limite v1. |
| Mapping introuvable au POST /imports | 404. |
| POST /mappings au-delà de 20 | 409 « Limite de 20 mappings atteinte ». |

## 8. Limites v1 (hors scope)

- **CAD uniquement.** Pas de compte multidevise.
- **Pas de comptes bancaires persistants.** `bank_label` est libre et descriptif.
- **Pas de réconciliation cumulative** (pas de solde fin de période).
- **Pas d'import OFX/QFX.** CSV seulement.
- **Pas de règles automatiques personnalisées.**
- **Pas de split de transaction** (1 ligne CSV → 2 dépenses).
- **Pas de PUT / DELETE sur mappings.** Création seule en v1.
- **Pas de POST /preview séparé.** Le `dry_run=true` sur POST /imports remplit le rôle.
- **Pas de back-calcul de taxes** sur create-invoice. Subtotal = total (sans taxes).
- **Pas de mobile responsive.**
- **Taille max CSV : 5 MB / 5 000 lignes.**
- **Max 20 mappings par user.**

## 9. Tests

### 9.1 Unitaires — `backend/tests/test_bank_reconciliation.py`

**Parsing** :
- `_parse_date` : 3 formats × cas valides + invalides → renvoie None si invalide.
- `_normalize_amount` : notation US (1,234.56), EU (1 234,56), espaces non-cassants, négatifs.
- `_sanitize_cell` : `=cmd`, `+att`, `-1`, `@me`, valeur normale.
- `_compute_file_hash` : reproductibilité, indépendant des sauts de ligne (CRLF vs LF).

**Algorithme de match** (sans MongoDB — fixtures Python pures) :
- Match parfait (amount exact, date dans ±3j, nom client trouvé) → score 3, auto-match.
- Pas de nom dans description → score 2, suggestion seulement.
- Hors fenêtre date → pas de candidat.
- Plusieurs candidats à score 3 → aucun auto-match (le 2ᵉ a score=3 aussi).
- Tx parse_error → return None directement.
- Tx direction crédit ne match jamais expenses.
- Tx direction débit ne match jamais invoices.
- Tie-breaker déterministe : 2 candidats score 2 → tri date_diff puis amount_diff.

### 9.2 Intégration — `backend/tests/test_bank_reconciliation_integration.py`

Utilise fixture `auth` et helpers comme `test_partial_payments_integration.py`. Cleanup via `teardown_class`. Dates futures (2099) pour éviter collisions.

- POST /mappings → 201, lookup par GET, max 20 enforcé.
- POST /imports `dry_run=true` → preview, aucune transaction persistée.
- POST /imports `dry_run=false` avec CSV synthétique (style Desjardins) → import + transactions créés.
- Auto-match : facture créée avec subtotal+taxes matchant un crédit → transaction passe `matched`, payment apparaît dans `invoice.payments[]`, status invoice recalculé.
- Re-import même CSV (même user) → 409.
- Re-import même CSV par user B → succès (no leak).
- POST /match avec `target_id` d'un autre user → 404.
- POST /match sur invoice `paid` → 409.
- POST /match direction crédit → expense → 200 (permis manuellement).
- POST /unmatch après match invoice → payment supprimé, status invoice retombe correctement (depuis `paid` à `sent`).
- POST /ignore puis /unignore → status flip-flop.
- POST /create-expense → expense créée avec snapshots ARC + `bank_transaction_id` set.
- POST /create-invoice → invoice `paid` créée avec un payment et `subtotal=total`.
- DELETE expense liée → tx repasse `unmatched`.
- DELETE invoice liée → tx repasse `unmatched`.
- DELETE payment de invoice (feature #6 endpoint) → tx repasse `unmatched`.
- DELETE bank_import non-fermé → cascade nette (transactions supprimées, payments retirés, invoice statuses recalculés).
- DELETE bank_import fermé sans `force` → 409.
- Fichier > 5 MB → 413 avant hash.
- CSV avec 5 001 lignes → 413.
- CSV avec cellule `=cmd()` → cellule stockée sans le `=`.

Cible : ~30 tests intégration + ~10 tests unitaires = **~40 nouveaux tests**.

### 9.3 E2E

Pas d'E2E browser automatisé — testé manuellement sur facturepro.ca après le push.

## 10. Observabilité

Logs Python `print()` (Render log streaming les capture). Niveaux logiques :

- `POST /imports` : `INFO bank.import.start user=<id> rows=<n>`, `INFO bank.import.done user=<id> rows=<n> auto_matched=<k> duration_ms=<t>`.
- `_apply_match` : `INFO bank.match user=<id> tx=<id> kind=<k> target=<id>`.
- `_unmatch` : `INFO bank.unmatch user=<id> tx=<id>`.
- `DELETE /imports/{id}` cascade : `INFO bank.import.delete user=<id> import=<id> txs=<n> payments_removed=<m> invoices_affected=<k>`.
- Toute exception capturée : `ERROR bank.<route> user=<id> error=<msg>` (sans stack trace en prod).

Pas d'infra externe (pas de Datadog/Sentry en v1). Render streaming suffit pour debug.

## 11. Performance

Budget : POST /imports avec **500 lignes** complète en **< 5 secondes** sur Render free tier (single-thread shared CPU).

Garanti par :
- Batch-load des candidates (1 query invoices + 1 query expenses) avant la boucle, plutôt que N×2 queries.
- Pas d'index miss : `(user_id, status)` sur invoices, `(user_id, bank_transaction_id)` sur expenses (à ajouter si absent).
- Tri/scoring entièrement en Python en mémoire.

Si dépassement constaté → option future : background task via FastAPI BackgroundTasks + polling côté frontend. Hors scope v1.

## 12. Rollout

Push direct sur main, déploiement automatique Render + Vercel. Pas de feature flag (cohérent avec features #2-#6). Mitigation en cas de bug critique : retirer le lien sidebar dans un hotfix Vercel (~2 min). Les collections `bank_*` restent en MongoDB mais inaccessibles depuis l'UI.

## 13. Dépendances

Backend : déjà couvertes (pymongo, fastapi). Module standard `csv` Python suffit. `hashlib.sha256`.

Frontend : déjà couvertes (axios, lucide-react). Drag-drop via `<input type="file">` natif.

## 14. Migration

Aucune migration de données. Les 3 nouvelles collections sont créées à la volée. Les champs optionnels `invoice.payments[i].bank_transaction_id` et `expense.bank_transaction_id` apparaissent en écriture sans backfill.
