# Grand livre — Phase 2 : auto-posting depuis factures/paiements/dépenses (feature #12) — Design

**Statut :** design proposé 2026-07-03 (à réviser par gussdub, propriétaire de ProFireManager Inc., société incorporée). **Points ouverts §3 à trancher avant le plan.**
**Auteur :** Claude (explore-phase sur `backend/server.py`, suite du spec Phase 1 `2026-07-03-general-ledger-design.md`)
**Prérequis :** Grand livre Phase 1 **livré** (2026-07-03) — partie double, plan comptable, journal manuel, balance de vérification, bilan. Ce spec s'appuie sur ses collections et helpers existants.

## 1. Objectif

La Phase 1 a posé le socle : un grand livre en partie double **alimenté 100 % à la main**. Chaque facture, chaque paiement, chaque dépense saisie dans FacturePro doit aujourd'hui être **re-saisie manuellement** comme écriture de journal pour que la comptabilité se tienne. Double saisie insoutenable en pratique.

La Phase 2 **génère automatiquement les écritures comptables** à partir des événements financiers qui existent déjà dans l'app :

- une **facture** passée à `sent` → écriture de revenu (base exercice / accrual) ;
- un **paiement** encaissé → écriture d'encaissement ;
- une **dépense** créée → écriture de dépense.

Objectif : **la comptabilité se tient toute seule.** Le journal manuel (Phase 1) reste pour ce qui n'a pas de document source — apport du propriétaire, amortissement, écriture de clôture annuelle, ajustements de fin d'exercice.

**Cas d'usage principal :** ProFireManager Inc. facture ses clients, encaisse des paiements, enregistre ses dépenses via FacturePro. Sa comptable externe (rôle `accountant`) veut ouvrir le grand livre en fin de trimestre et **y trouver les écritures déjà passées**, réconciliées avec le P&L (feature #5), plutôt que de tout ressaisir. Elle garde la main pour les ajustements via le journal manuel.

**Contexte codebase (déjà en place, Phase 1) :**
- **`_create_journal_entry(...)`** (`server.py:1675`) — factory interne d'écriture, valide l'équilibre, snapshot les lignes, attribue le numéro atomique. **Elle écrit déjà les champs `source_type`/`source_id`** (hardcodés `None` en Phase 1, `server.py:1704`). Phase 2 = les **threader** via un nouveau paramètre, sans changer la structure du document.
- **Champs `source_type`/`source_id`** déjà présents sur chaque `journal_entries` + **index** `(organization_id, source_type, source_id)` déjà créé (`server.py:1850`). L'idempotence est **prévue par le modèle Phase 1** — rien à migrer côté schéma.
- **`entry_type`** accepte déjà `"auto"` (documenté §3.2 du spec Phase 1) à côté de `manual`/`opening`/`reversal`.
- **`_account_balance`** (`server.py:1605`) compte **toutes** les écritures `posted` sans jamais regarder `reverses_entry_id`/`reversed_by_entry_id` → la contre-passation d'une écriture auto donne un net zéro **garanti par construction** (invariant Phase 1 §5.2). Phase 2 réutilise ce mécanisme tel quel.
- **`reverse_entry`** (`server.py:2870`) — endpoint + logique de contre-passation par miroir POSTED. Phase 2 réutilise la **même primitive interne** pour contre-passer les écritures auto (pas un mécanisme parallèle).
- **`_ensure_chart_seeded(org_id, user_id)`** (`server.py:2483`) — seed lazy du plan comptable. L'auto-posting doit le déclencher avant de résoudre un compte (une org peut n'avoir jamais ouvert le module GL).
- **Comptes de dépenses mappés `expense_category_code`** (`_build_default_accounts` `server.py:1534`, verrou `_validate_expense_category_code` `server.py:1443`) → mapping dépense→compte 5xxx **déjà garanti unique par org**, sans table supplémentaire.
- **Endpoints sources** : `PUT /api/invoices/{id}/status` (`server.py:3815`), `POST /api/invoices/{id}/payments` (`server.py:3822`), `DELETE /api/invoices/{id}/payments/{pid}` (`server.py:3847`), `DELETE /api/invoices/{id}` (`server.py:3876`), `POST /api/expenses` (`server.py:4959`), `PUT /api/expenses/{id}` (`server.py:4988`), `DELETE /api/expenses/{id}` (`server.py:5037`).
- **Modèle de contre-passation en cascade** : `_release_bank_transaction(tx_id, scope)` (`server.py:629`) sert de patron pour « défaire proprement l'effet d'un doc supprimé ».
- **Réconciliation** : `_aggregate_pnl(scope, start, end, basis)` (`server.py:322`) — le P&L existant, point de contrôle en base exercice.

**Ce spec ne code rien.** Il documente les décisions (avec recommandations sur les points ouverts, à réviser par le propriétaire) et cadre le plan d'implémentation séparé.

## 2. Décisions de design (fixes)

| # | Question | Décision | Alternatives rejetées |
|---|----------|----------|------------------------|
| 1 | Base comptable des écritures auto | **Exercice (accrual)** : le revenu est comptabilisé au passage à `sent`, pas à l'encaissement. Le paiement ne fait que déplacer A/R → Encaisse. | Base caisse (revenu au paiement) → produit un bilan sans Comptes clients, incohérent avec un T2 société. |
| 2 | Idempotence | **Un doc source = une écriture auto vivante**, liée par `(source_type, source_id)`. Jamais de doublon. Un `find_one` sur l'index avant tout post. | Recréer sans vérifier → doublons à chaque re-sauvegarde. Compter les écritures → race. |
| 3 | Régénération sur modif | **Contre-passer l'ancienne (miroir POSTED) + poster la nouvelle.** L'origine reste `posted` (invariant Phase 1). La piste d'audit ARC est préservée (append-only). | Éditer l'écriture en place → détruit la piste d'audit + casse l'immuabilité `posted` de la Phase 1. Delete+recreate → perd la traçabilité de ce qui a été comptabilisé puis annulé. |
| 4 | Écritures auto vs manuel | **Verrouillées** : une écriture `entry_type="auto"` **ne peut pas** être éditée/postée/contre-passée/supprimée via les endpoints `/api/ledger/entries/*` manuels (400). Elle ne change **qu'en réaction** au document source. | Auto éditables à la main → l'utilisateur casse le lien source↔écriture, l'idempotence diverge, la réconciliation P&L saute. |
| 5 | Où vit la logique de post | **Fonctions internes `_autopost_*` appelées en fin des endpoints sources existants** (hooks), + un **service `_post_source_entry` / `_unpost_source_entry`** partagé. Pas de queue asynchrone. | Listeners/change-streams Mongo → complexité opérationnelle, pas de transaction avec l'écriture source. Cron de rattrapage → latence, incohérence transitoire. |
| 6 | Robustesse si le post échoue | **L'auto-posting ne doit JAMAIS faire échouer l'opération métier.** Le doc source (facture/paiement/dépense) est la source de vérité ; l'écriture est dérivée. Un échec de post est **capté, loggé, et signalé** (champ `autopost_error` sur le doc source + endpoint de diagnostic), mais l'opération métier réussit (200/201). Un endpoint de **réparation** re-tente. | Rollback de la facture si l'écriture échoue → un bug comptable empêcherait de facturer, inacceptable. Ignorer silencieusement → écarts invisibles. |
| 7 | Devise du GL | **CAD only** (invariant Phase 1). On utilise `total_cad` (factures) et `amount_cad`/`*_paid_cad` (dépenses). **⚠️ Le détail de taxes des factures (`subtotal`, `gst_amount`, `pst_amount`, `hst_amount`) est en devise de FACTURE, pas en CAD** (`create_invoice` `server.py:3773`) → il faut le **reconvertir** au taux `exchange_rate_to_cad` avant de poster (§5.1). | Poster les montants de taxe bruts → écriture déséquilibrée dès qu'une facture est en devise étrangère (Dr total_cad ≠ Cr subtotal+taxes non convertis). |
| 8 | Backfill historique | **Endpoint on-demand déclenché par l'utilisateur**, avec **aperçu (dry-run) avant application**. **Pas** de backfill automatique au déploiement. | Backfill auto au boot → poste des centaines d'écritures sans consentement, risque de doublon avec des écritures manuelles déjà passées pour les mêmes factures. |
| 9 | Compte de crédit des dépenses | **Encaisse (1000) par défaut** (dépense réputée payée comptant), **configurable** par un flag org `expense_default_credit_account` (Encaisse vs Comptes fournisseurs 2000). **Point ouvert #1 §3.** | Toujours A/P (2000) → suppose un cycle fournisseur inexistant dans l'app. Deviner via `bank_transaction_id`/`status` → fragile, `status` = `pending` n'indique pas « impayé ». |
| 10 | Activation | **Opt-in par org** via un flag `autopost_enabled` sur `company_settings` (défaut **false**). Tant que désactivé, aucun hook ne poste (comportement Phase 1 pur). | Actif d'office → surprend les orgs qui tenaient déjà le journal à la main pour les mêmes docs → doublons. |

## 3. Points OUVERTS — recommandations à réviser (société incorporée)

> Ces 4 points ont un **impact comptable réel** pour une société. Recommandations ci-dessous ; le propriétaire tranche avant le plan.

**Point ouvert #1 — Compte de crédit des dépenses : Encaisse (payé comptant) vs Comptes fournisseurs (à payer) ?**
Les dépenses de l'app **n'ont pas de statut payé/impayé clair** : `create_expense` pose `status="pending"` (`server.py:4981`), qui ne signifie pas « impayé » au sens comptable, et le seul lien de règlement est `bank_transaction_id` (rapprochement bancaire, feature #7), optionnel.
- **RECO : Encaisse (1000) par défaut**, avec flag org `expense_default_credit_account` pour basculer vers Comptes fournisseurs (2000) plus tard si un vrai cycle fournisseur apparaît. Simple, juste dans le cas dominant (TPE qui paie ses dépenses par carte/compte courant), et n'immobilise pas un A/P fantôme au bilan.
- **Conséquence si Encaisse :** l'Encaisse du GL suivra les dépenses au fil de l'eau ; le rapprochement bancaire (feature #7) reste l'outil pour valider le solde réel de banque. À documenter comme limite (§13).

**Point ouvert #2 — Backfill historique : générer les écritures pour les docs DÉJÀ existants ?**
- **RECO : oui, mais on-demand + aperçu.** Endpoint `POST /api/ledger/autopost/backfill?dry_run=true` qui liste **combien** d'écritures seraient créées (par type, par période) **sans rien écrire** ; puis `dry_run=false` applique. **Idempotent** : ne crée une écriture que si `(source_type, source_id)` n'en a pas déjà une (§4.2). Jamais automatique au déploiement (décision #8). Permet à la comptable de choisir la période de départ (ex. début de l'exercice courant) et d'éviter les doublons avec d'éventuelles écritures manuelles déjà passées.

**Point ouvert #3 — Écritures auto : éditables manuellement ou verrouillées ?**
- **RECO : verrouillées** (décision #4). Une écriture `auto` est le reflet fidèle d'un document ; on ajuste **le document source**, pas l'écriture. Toute tentative d'éditer/poster/contre-passer/supprimer une `auto` via les endpoints manuels → 400 « écriture générée automatiquement, modifiez le document source ». Si un ajustement purement comptable est nécessaire (rare), la comptable passe une **écriture manuelle distincte** (ex. reclassement), ce qui laisse la piste d'audit intacte.

**Point ouvert #4 — Multi-devise : GL en CAD via `total_cad`/`amount_cad` ?**
- **RECO : oui.** Le GL est CAD only (invariant Phase 1 §11). On poste `total_cad` (factures) et `amount_cad` + `*_paid_cad` (dépenses). **Piège documenté (décision #7) :** le détail de taxes des factures est en devise de facture ; on le **reconvertit** au taux snapshoté avant de poster, et on **force l'équilibre** en calculant la ligne de revenu par **différence** (`total_cad − Σ taxes_cad`) pour absorber tout arrondi (§5.1). Ainsi l'écriture est **toujours** équilibrée, même sur facture en USD.

## 4. Modèle de données

**Aucune nouvelle collection.** La Phase 2 réutilise les collections Phase 1 et ajoute quelques champs.

### 4.1 `journal_entries` — champs déjà présents, désormais renseignés

Ces champs existent depuis la Phase 1 (`server.py:1704`) ; la Phase 2 les **remplit** pour les écritures auto :

```python
"entry_type": "auto",            # au lieu de manual/opening/reversal
"source_type": str,              # "invoice" | "invoice_payment" | "expense"
"source_id": str,                # id du doc source (facture, paiement, dépense)
```

> `source_type = "invoice_payment"` (et non `"payment"`) car un paiement est **embarqué** dans `invoices.payments[]` (feature #6) et son `source_id` est le `payment.id` (uuid unique de la sous-entrée). Cela évite toute collision avec `source_type="invoice"` (revenu) qui porte le `source_id` = id de la facture.

**Idempotence par l'index existant** `(organization_id, source_type, source_id)` (`server.py:1850`). Aucune migration d'index nécessaire. On ajoute un index d'unicité **partiel** pour durcir (§11) :

```python
db.journal_entries.create_index(
    [("organization_id", 1), ("source_type", 1), ("source_id", 1)],
    unique=True,
    partialFilterExpression={
        "entry_type": "auto",
        "reverses_entry_id": None,   # seul le post "vivant" est unique ; les miroirs de contre-passation partagent source_type/source_id
    })
```

> **Subtilité :** l'écriture auto d'origine ET son miroir de contre-passation portent le même `(source_type, source_id)` (le miroir doit être retrouvable par source pour la traçabilité). L'unicité ne s'applique donc qu'au post **vivant** (`entry_type="auto"` **non-reversal**, `reverses_entry_id=None`). Le miroir est `entry_type="reversal"` → hors du filtre partiel. Après une régénération, l'ancien post reste `auto` mais est **marqué contre-passé** (`reversed_by_entry_id` posé) : voir §4.1bis pour distinguer « auto vivant » de « auto contre-passé ».

### 4.1bis Distinguer l'écriture auto « vivante » de l'écriture auto contre-passée

Une facture régénérée 3 fois laisse : 1 post vivant + 2 anciens posts (chacun contre-passé par son miroir). Tous ont `(source_type, source_id)` identiques. **Le post vivant est celui qui a `entry_type="auto"` ET `reversed_by_entry_id IS None`.** C'est la clé de recherche de `_find_live_source_entry` (§5). L'index partiel ci-dessus garantit qu'il n'en existe **jamais deux** simultanément.

### 4.2 `company_settings` — nouveaux champs (migration idempotente)

```python
"autopost_enabled": bool,                    # défaut False — opt-in par org (décision #10)
"expense_default_credit_account": str,       # "1000" (Encaisse) | "2000" (A/P) — défaut "1000" (point ouvert #1)
```

Ajoutés par `setdefault` dans une migration idempotente (`migrate_general_ledger_autopost_v1`, §8), exposés/éditables via `PUT /api/settings/company` (validation : `expense_default_credit_account ∈ {"1000","2000"}`).

### 4.3 Documents sources — champ de diagnostic (décision #6)

Sur `invoices` et `expenses`, champ optionnel posé **uniquement** en cas d'échec de post :

```python
"autopost_error": str | None,     # message + timestamp du dernier échec ; None = OK
```

Jamais bloquant. Un endpoint de réparation (§6.3) re-tente et efface le champ au succès. Aucun autre champ n'est ajouté aux docs métier (le lien inverse écriture→source vit déjà dans `journal_entries.source_id`).

## 5. Mapping événement → écriture (table Dr/Cr détaillée)

Tous les montants sont en **CAD**. Résolution des comptes par **numéro canonique** via un nouveau helper `_resolve_ledger_account(org_id, account_number)` (le plan comptable étant seedé, §4 Phase 1). Le seed lazy `_ensure_chart_seeded` est appelé **avant** toute résolution.

### 5.1 Facture passée à `sent` → écriture de revenu (accrual)

Déclencheur : `PUT /api/invoices/{id}/status` (`server.py:3815`) quand **le nouveau statut est dans `{sent, partial, paid, overdue}` ET l'ancien était `draft`** (première comptabilisation). Voir §5.5 pour les transitions retour.

Conversion CAD (décision #7, §3 point #4) : les taxes sont en devise de facture → on divise par le taux.

```python
rate = inv["exchange_rate_to_cad"] or 1.0
def _cad(x):  # même logique que _aggregate_pnl server.py:344
    return round((x / rate), 2) if inv["currency"] != "CAD" and rate > 0 else round(x, 2)

gst_cad = _cad(inv["gst_amount"])
qst_cad = _cad(inv["pst_amount"])     # pst_amount = TVQ au QC
hst_cad = _cad(inv["hst_amount"])
ar_cad  = round(inv["total_cad"], 2)  # déjà en CAD, source de vérité du total
# Revenu par DIFFÉRENCE pour absorber l'arrondi de conversion → équilibre garanti :
revenue_cad = round(ar_cad - gst_cad - qst_cad - hst_cad, 2)
```

| Compte | N° | Débit | Crédit |
|---|---|---|---|
| Comptes clients (A/R) | 1100 | `ar_cad` | |
| Revenus de services | 4000 | | `revenue_cad` |
| TPS à payer | 2100 | | `gst_cad` (si > 0) |
| TVQ à payer | 2110 | | `qst_cad` (si > 0) |
| TVH à payer | 2120¹ | | `hst_cad` (si > 0) |

¹ Compte 2120 « TVH à payer » **non seedé par défaut** (le seed reflète le profil QC, spec Phase 1 §4.2). Si `hst_cad > 0` et 2120 absent → on le **crée à la volée** (asset/liability système) OU on échoue proprement avec `autopost_error` explicite. **RECO : créer 2120 à la volée** (idempotent) pour ne pas bloquer une facture ON.

`source_type="invoice"`, `source_id=inv["id"]`, `entry_date = inv["issue_date"][:10]`, `description = f"Facture {inv['invoice_number']}"`, `reference = inv['invoice_number']`.

### 5.2 Paiement reçu → écriture d'encaissement

Déclencheur : `POST /api/invoices/{id}/payments` (`server.py:3822`), après insertion du paiement.

| Compte | N° | Débit | Crédit |
|---|---|---|---|
| Encaisse | 1000 | `payment["amount_cad"]` | |
| Comptes clients (A/R) | 1100 | | `payment["amount_cad"]` |

`source_type="invoice_payment"`, `source_id=payment["id"]`, `entry_date = payment["date"]`, `description = f"Paiement facture {inv['invoice_number']}"`, `reference = payment.get("reference")`.

> `amount_cad` est déjà en CAD sur le paiement (`server.py:3832`). Pas de reconversion.

### 5.3 Paiement supprimé → contre-passation

Déclencheur : `DELETE /api/invoices/{id}/payments/{pid}` (`server.py:3847`).
Action : `_unpost_source_entry("invoice_payment", pid)` → contre-passe l'écriture d'encaissement vivante (miroir POSTED, §5 primitive). Net zéro sur Encaisse et A/R.

### 5.4 Facture repassée en `draft` ou supprimée → contre-passation du revenu

- `PUT /api/invoices/{id}/status` vers `draft` (retour brouillon) → `_unpost_source_entry("invoice", inv_id)` (contre-passe le revenu).
- `DELETE /api/invoices/{id}` (`server.py:3876`) → contre-passe le revenu **et** tous les encaissements liés (`invoice_payment` de chaque `payment.id`). Modèle : la cascade `_release_bank_transaction` déjà appelée dans `delete_invoice` (`server.py:3880`).

> **Cohérence :** on ne supprime jamais physiquement une écriture auto postée (immuabilité Phase 1). On contre-passe. L'origine et son miroir restent au grand livre, net zéro.

### 5.5 Transitions de statut de facture — table de vérité

`update_invoice_status` (`server.py:3815`) est aujourd'hui un `update_one` nu **sans conscience de l'ancien statut**. Le hook doit **lire l'ancien statut avant l'update** puis décider :

| Ancien statut | Nouveau statut | Action auto-posting |
|---|---|---|
| `draft` | `sent`/`partial`/`paid`/`overdue` | **Poster** le revenu (§5.1) s'il n'existe pas déjà |
| `sent`/`overdue`/… | `draft` | **Contre-passer** le revenu (§5.4) |
| `sent` | `overdue` (et inverses non-draft) | **Rien** (le revenu reste comptabilisé — accrual) |
| `sent`/`partial` | `paid` | **Rien** au titre du revenu (l'encaissement est géré par §5.2 via les paiements, pas par le statut) |

> **Note :** `status` peut aussi passer à `partial`/`paid` **automatiquement** via `_recompute_invoice_status` lors de l'ajout d'un paiement (`server.py:3839`). Ce recalcul **ne doit PAS** re-déclencher un post de revenu : le revenu est déjà comptabilisé depuis `sent`. Seul le **paiement** (§5.2) poste, via le hook de `add_invoice_payment`. Le hook de `update_invoice_status` ne poste le revenu que sur la transition `draft → non-draft`.

### 5.6 Dépense créée → écriture de dépense

Déclencheur : `POST /api/expenses` (`server.py:4959`).
Compte de dépense : `_resolve_expense_account(org_id, expense["category_code"])` → compte 5xxx dont `expense_category_code == category_code`, **fallback 5900** (Dépenses diverses) si aucun mappé (§4.2/§10.1 Phase 1).
Compte de crédit : `company_settings.expense_default_credit_account` (défaut 1000 Encaisse — point ouvert #1).

```python
amount_cad = expense["amount_cad"]                 # net de taxes ? NON — voir ci-dessous
gst_cad = expense["gst_paid_cad"]                  # déjà CAD (server.py:4976)
qst_cad = expense["qst_paid_cad"]
hst_cad = expense["hst_paid_cad"]
```

> **⚠️ Sémantique de `amount` sur les dépenses.** `create_expense` calcule `amount_cad` à partir de `amount` (`server.py:4964`) : c'est le **montant total** saisi, taxes **incluses** (le reçu affiche un total TTC). Les champs `*_paid_cad` sont la **part de taxe récupérable extraite de ce total**. Donc la ligne de dépense (charge nette) = `amount_cad − gst_cad − qst_cad − hst_cad`, et le crédit = `amount_cad` (le décaissement total). **Point à confirmer** avec la comptable (est-ce que `amount` est TTC ou HT dans l'usage réel de ProFireManager). **RECO : traiter `amount` comme TTC** (cohérent avec un reçu scanné, feature #8) → charge nette par différence, comme pour le revenu. À valider au plan.

| Compte | N° | Débit | Crédit |
|---|---|---|---|
| Dépense (par catégorie) | 5xxx (fallback 5900) | `expense_net_cad`² | |
| TPS à recouvrer | 1200 | `gst_cad` (si > 0) | |
| TVQ à recouvrer | 1210 | `qst_cad` (si > 0) | |
| TVH à recouvrer | 1220³ | `hst_cad` (si > 0) | |
| Encaisse **ou** Comptes fournisseurs | 1000 **ou** 2000 | | `amount_cad` |

² `expense_net_cad = round(amount_cad − gst_cad − qst_cad − hst_cad, 2)` — calculé **par différence** → équilibre garanti (Dr net + Dr taxes = Cr total).
³ 1220 « TVH à recouvrer » non seedé (profil QC) → créé à la volée si `hst_cad > 0` (comme 2120, §5.1).

`source_type="expense"`, `source_id=expense["id"]`, `entry_date = expense["expense_date"][:10]`, `description = expense.get("description") or expense.get("category")`, `reference = None`.

### 5.7 Dépense modifiée → régénération ; dépense supprimée → contre-passation

- `PUT /api/expenses/{id}` (`server.py:4988`) → **régénérer** : `_unpost_source_entry("expense", id)` (contre-passe l'ancienne) puis `_post_expense_entry(...)` (poste la nouvelle avec les valeurs à jour). Idempotent : si aucun montant comptable n'a changé, on peut court-circuiter (optimisation optionnelle, à trancher au plan — le plus simple/sûr est de toujours régénérer).
- `DELETE /api/expenses/{id}` (`server.py:5037`) → `_unpost_source_entry("expense", id)` (contre-passe). Modèle : la cascade `_release_bank_transaction` déjà présente (`server.py:5040`).

## 6. Idempotence, régénération, contre-passation (logique interne)

### 6.1 Primitives partagées

```python
def _find_live_source_entry(org_id, source_type, source_id):
    """L'écriture auto VIVANTE d'un doc source, ou None.
    Vivante = entry_type 'auto', posted, non contre-passée."""
    return db.journal_entries.find_one({
        "organization_id": org_id, "source_type": source_type,
        "source_id": source_id, "entry_type": "auto",
        "reversed_by_entry_id": None,
    }, {"_id": 0})

def _post_source_entry(org_id, user_id, source_type, source_id, entry_date,
                       description, lines, reference=None):
    """Poste UNE écriture auto pour un doc source, si aucune vivante n'existe (idempotent).
    Réutilise _create_journal_entry (Phase 1) en threadant source_type/source_id."""
    if _find_live_source_entry(org_id, source_type, source_id):
        return None  # déjà posté — no-op (garantit l'idempotence, décision #2)
    return _create_journal_entry(
        org_id, user_id, entry_date=entry_date, description=description,
        lines=lines, status="posted", entry_type="auto", reference=reference,
        source_type=source_type, source_id=source_id)   # ← nouveaux params threadés

def _unpost_source_entry(org_id, user_id, source_type, source_id, rev_date=None):
    """Contre-passe l'écriture auto vivante d'un doc source (miroir POSTED).
    Réutilise EXACTEMENT la logique de reverse_entry (server.py:2870). No-op si rien à défaire."""
    live = _find_live_source_entry(org_id, source_type, source_id)
    if not live:
        return None
    # ... crée le miroir via _create_journal_entry(entry_type="reversal",
    #     reverses_entry_id=live["id"], source_type/source_id conservés),
    #     puis pose reversed_by_entry_id sur `live`. Net zéro garanti (§5.2 Phase 1).
```

### 6.2 Modification threadée dans `_create_journal_entry`

`_create_journal_entry` (`server.py:1675`) gagne deux paramètres `source_type=None, source_id=None` et les écrit dans le doc (aujourd'hui hardcodés `None` `server.py:1704`). **Seul changement de signature de la Phase 1** — rétrocompatible (défauts `None` → comportement manuel inchangé).

### 6.3 Garde-fou robustesse (décision #6)

Chaque hook enveloppe l'appel de post :

```python
def _safe_autopost(fn, source_doc_collection, source_doc_id, org_scope):
    try:
        fn()
        db[source_doc_collection].update_one({"id": source_doc_id, **org_scope},
            {"$unset": {"autopost_error": ""}})
    except Exception as e:
        # NE JAMAIS propager : l'opération métier a déjà réussi.
        logger.warning("autopost failed for %s: %s", source_doc_id, type(e).__name__)
        db[source_doc_collection].update_one({"id": source_doc_id, **org_scope},
            {"$set": {"autopost_error": f"{datetime.now(timezone.utc).isoformat()} — échec auto-posting"}})
```

> **Pas de `str(e)` dans le message stocké** si l'exception peut contenir des données sensibles — on stocke un message générique horodaté (pattern anti-leak feature #8). Le détail va au log serveur.

L'endpoint de réparation (§6.4) rejoue les posts manquants et efface `autopost_error`.

## 7. Backfill (point ouvert #2)

```
POST /api/ledger/autopost/backfill?dry_run=true|false&start=&end=   accounting:write
```

- **Dry-run (défaut true)** : parcourt factures (`status != draft`), leurs paiements, et dépenses de la période `[start, end]` (défaut : exercice courant via `_current_fiscal_year`, `server.py:2591`), et **compte** combien d'écritures seraient créées, **par type**, **sans rien écrire**. Ignore les docs qui ont déjà une écriture vivante (idempotent).
  → `200 {would_create: {invoice: N, invoice_payment: M, expense: K}, skipped_existing: X, period: {start, end}}`
- **Application (`dry_run=false`)** : poste réellement, dans l'ordre **facture (revenu) → paiements → dépenses**, chaque post protégé par `_safe_autopost`. Réponse : décompte réel + liste des `autopost_error` éventuels.
  → `200 {created: {...}, failed: [{source_type, source_id, error}], period}`
  Chaque item de `failed` est un **objet** `{source_type, source_id, error}` (jamais un ID brut). Le champ `error` est le **libellé générique** (`AUTOPOST_ERROR_MESSAGE`), identique à celui posé dans `autopost_error` sur le doc source — **jamais `str(e)`** (le type d'exception ne va qu'au log serveur, pattern anti-leak feature #8). Diagnostic corrélé : `failed[].error` et le champ `autopost_error` du doc concordent.

**Idempotent et rejouable** : relancer le backfill ne double rien (chaque post vérifie `_find_live_source_entry`). Active implicitement rien : `autopost_enabled` reste indépendant (le backfill est une action explicite one-shot ; l'activation du flag gère le **flux continu** futur).

> **Divergence assumée — paiements sur facture `draft` (non corrigée, la plus sûre).** Le backfill exclut **toute** facture `draft` (`status != draft`), donc **n'inclut jamais** les paiements enregistrés sur une draft — alors que le hook live `add_invoice_payment` les posterait (gaté sur `autopost_enabled` seul, pas sur le statut). C'est délibéré : une draft n'a ni revenu ni compte-client comptabilisés, donc un `Dr 1000 / Cr 1100` d'encaissement y créerait un **A/R fantôme négatif**. En pratique le bouton paiement est masqué sur les drafts dans l'UI (feature #6), donc ce cas n'apparaît normalement pas. Couvert par `test_draft_invoice_payment_not_backfilled`.

## 8. API — nouveaux endpoints + hooks sur endpoints existants

### 8.1 Nouveaux endpoints `/api/ledger/autopost/*`

```
GET  /api/ledger/autopost/status                  accounting:read
     → 200 { enabled: bool, expense_default_credit_account: "1000"|"2000",
             pending_errors: int,          # docs avec autopost_error posé
             coverage: { invoices_posted: N, invoices_total_postable: M,
                         expenses_posted: K, expenses_total: L } }

POST /api/ledger/autopost/backfill?dry_run=&start=&end=   accounting:write   (§7)

POST /api/ledger/autopost/repair                  accounting:write
     → rejoue les posts des docs ayant autopost_error ; efface au succès.
       200 { repaired: N, still_failing: [...] }
```

`autopost_enabled` et `expense_default_credit_account` s'éditent via le `PUT /api/settings/company` **existant** (validation ajoutée), pas un endpoint dédié.

### 8.2 Hooks sur endpoints existants (modifications minimales)

| Endpoint | Ligne | Hook ajouté (gardé par `autopost_enabled`) |
|---|---|---|
| `PUT /api/invoices/{id}/status` | `server.py:3815` | **Lire l'ancien statut avant l'update** ; puis `_autopost_invoice_status_transition(old, new, inv)` (§5.5) |
| `POST /api/invoices/{id}/payments` | `server.py:3822` | `_post_source_entry("invoice_payment", payment.id, …)` (§5.2) |
| `DELETE /api/invoices/{id}/payments/{pid}` | `server.py:3847` | `_unpost_source_entry("invoice_payment", pid)` (§5.3) |
| `DELETE /api/invoices/{id}` | `server.py:3876` | contre-passe revenu + chaque paiement (§5.4) |
| `POST /api/expenses` | `server.py:4959` | `_post_expense_entry(expense)` (§5.6) |
| `PUT /api/expenses/{id}` | `server.py:4988` | régénère : unpost + repost (§5.7) |
| `DELETE /api/expenses/{id}` | `server.py:5037` | `_unpost_source_entry("expense", id)` (§5.7) |

Chaque hook : (1) **early-return si `not company_settings.autopost_enabled`** (décision #10) ; (2) `_ensure_chart_seeded` ; (3) `_safe_autopost(...)`. **Aucun hook ne peut faire échouer l'opération métier** (décision #6).

### 8.3 Verrou sur les endpoints manuels (décision #4)

Ajout d'un garde dans `PUT /api/ledger/entries/{id}`, `POST .../post`, `POST .../reverse`, `DELETE .../entries/{id}` :

```python
if entry.get("entry_type") == "auto":
    raise HTTPException(400, "Écriture générée automatiquement — modifiez le document source")
```

> Note : `reverse` d'une auto est bloqué **côté manuel**, mais la contre-passation **interne** (`_unpost_source_entry`) reste possible (elle passe par la primitive, pas par l'endpoint public). C'est voulu : seul le système contre-passe les écritures auto.

## 9. Réconciliation avec le P&L (feature #5)

Le P&L `_aggregate_pnl` (`server.py:322`) agrège **directement** `invoices`/`expenses` ; le GL agrège les **écritures**. En **base exercice**, les deux doivent concorder.

### 9.1 Correspondances attendues

| Grandeur | P&L (accrual) | GL (écritures auto) | Doit concorder ? |
|---|---|---|---|
| Revenus | Σ `subtotal` (converti CAD) des factures `status ∈ {sent,paid,overdue}` sur `issue_date ∈ [start,end]` | Σ crédits compte 4000 sur `entry_date ∈ [start,end]` | **Oui** (à l'arrondi de conversion près, §5.1) |
| Dépenses (brut) | Σ `amount_cad` par catégorie sur `expense_date` | Σ débits comptes 5xxx sur `entry_date` | **Oui**, si `expense_net` = amount − taxes (§5.6). **Écart attendu = les taxes récupérables** (le GL isole la TPS/TVQ à recouvrer en 12xx, le P&L garde le brut). **À documenter.** |

> **⚠️ Écart structurel dépenses :** le P&L compte `amount_cad` (TTC) comme charge ; le GL comptabilise la charge **nette de taxes récupérables** (5xxx) + les taxes en actifs (12xx). Donc `Σ 5xxx (GL) = Σ dépenses P&L − Σ taxes récupérables`. Ce n'est **pas** un bug : c'est la différence entre « vue gestion » (P&L brut) et « vue comptable » (charge nette). L'endpoint de réconciliation l'affiche explicitement.

### 9.2 Endpoint de réconciliation

```
GET  /api/ledger/reconciliation?start=&end=       accounting:read
     → 200 {
         revenue:  { pnl: float, gl: float, diff: float },
         expenses: { pnl_gross: float, gl_net: float,
                     recoverable_taxes: float, diff: float },  # diff attendu ≈ 0 après ajout des taxes
         balanced: bool,        # |diff| < 0.02 sur revenus ET (gl_net + taxes − pnl_gross) < 0.02
       }
```

Outil de contrôle pour la comptable : un `balanced=false` signale une écriture manquante (facture non postée → `autopost_error`, ou backfill partiel).

### 9.3 Comment vérifier (procédure documentée)

1. Activer `autopost_enabled`, lancer le backfill sur l'exercice courant.
2. `GET /api/ledger/reconciliation?start=<fy_start>&end=<today>` → `revenue.diff ≈ 0`.
3. Comparer `GET /api/reports/pnl` (accrual) et `GET /api/ledger/general-ledger?account_id=<4000>` → mêmes totaux revenus.
4. Toute divergence > 0,02 $ → `GET /api/ledger/autopost/status` (`pending_errors`) → `POST /api/ledger/autopost/repair`.

## 10. Sécurité / robustesse

| Menace | Mitigation |
|---|---|
| **Écriture auto déséquilibrée** (arrondi de conversion) | Ligne de revenu/charge calculée **par différence** (`total_cad − Σ taxes`) → `_validate_entry_balance` (Phase 1 §5.1) passe toujours. Jamais d'écriture déséquilibrée postée. |
| **Doublon d'écriture auto** (double POST, retry réseau, backfill relancé) | `_find_live_source_entry` avant chaque post (§6.1) **+ index unique partiel** `(org, source_type, source_id)` sur les auto vivants (§4.1). Le second insert lève `DuplicateKeyError` → capté par `_safe_autopost`, no-op. |
| **Auto-posting qui casse une opération métier** | `_safe_autopost` capte toute exception ; l'op métier réussit (décision #6). Le doc source reste la vérité. `autopost_error` + endpoint repair pour rattraper. |
| **Fuite cross-org** | Tous les helpers `_*_source_entry` filtrent `organization_id` explicitement (jamais par `source_id` seul). Cohérent avec `reverse_entry` (`server.py:2876`). Les hooks passent l'org du `current_user`. |
| **Édition manuelle d'une écriture auto** (divergence source↔écriture) | Verrou `entry_type=="auto"` → 400 sur tous les endpoints manuels (§8.3). |
| **Activation surprise → doublons** avec écritures manuelles préexistantes | Opt-in `autopost_enabled` défaut false (décision #10) ; backfill on-demand + dry-run (§7) ; idempotence par source. |
| **Compte de taxe manquant** (facture ON, TVH) | Création à la volée de 2120/1220 (idempotente) OU `autopost_error` explicite — jamais un post déséquilibré (§5.1/§5.6). |
| **Race sur le numéro d'écriture** (posts concurrents) | `_next_entry_number` atomique `$inc` (Phase 1 §3.3) inchangé. |
| **Contre-passation en boucle** | `_unpost_source_entry` no-op si l'écriture est déjà contre-passée (`reversed_by_entry_id` posé) — pas de double miroir. |
| **Transactionnalité** | Idéal : session Mongo multi-doc (op métier + écriture dans une transaction). **MongoDB Atlas (replica set) supporte les transactions.** RECO : envelopper op-source + post dans une transaction **quand la topologie le permet** ; sinon, l'ordre « op métier d'abord, post ensuite (best-effort) » + `autopost_error` + repair garantit la cohérence éventuelle. À trancher au plan selon la version Mongo de prod. |

## 11. Tests

### 11.1 Unitaires — `backend/tests/test_autoposting.py`

- **Mapping facture** : QC (Dr 1100 / Cr 4000+2100+2110) équilibré ; ON (Cr 2120 TVH) ; facture USD → montants reconvertis, revenu par différence, équilibre exact ; facture sans taxes → 2 lignes.
- **Mapping paiement** : Dr 1000 / Cr 1100 = amount_cad.
- **Mapping dépense** : compte 5xxx résolu par `category_code` ; fallback 5900 ; taxes en 12xx ; charge nette par différence ; crédit Encaisse (défaut) vs A/P (flag) ; dépense sans taxe.
- **Idempotence** : `_post_source_entry` deux fois → 1 seule écriture (2e = no-op) ; index unique partiel lève sur insert concurrent simulé.
- **`_find_live_source_entry`** : ignore les auto contre-passées ; retourne le post vivant unique après N régénérations.
- **Conversion CAD** : `_cad` cohérent avec `_aggregate_pnl` (server.py:344) ; arrondi absorbé par la ligne de différence.
- **Transitions de statut** (§5.5) : draft→sent poste ; sent→overdue no-op ; sent→draft contre-passe ; recompute partial/paid ne re-poste pas le revenu.
- **`_safe_autopost`** : exception → `autopost_error` posé, pas de propagation ; succès → champ effacé.

### 11.2 Intégration — `backend/tests/test_autoposting_integration.py`

- **Opt-in** : `autopost_enabled=false` → aucune écriture créée sur POST facture/dépense ; `true` → écritures créées.
- **Cycle facture** : POST facture draft (rien) → status sent (revenu posté, JE auto) → paiement (encaissement posté) → balance de vérification équilibrée → suppression paiement (contre-passé, net zéro) → retour draft (revenu contre-passé, net zéro).
- **Cycle dépense** : POST (posté) → PUT montant changé (régénéré : ancien contre-passé + nouveau posté, 1 seul vivant) → DELETE (contre-passé).
- **Suppression facture** : contre-passe revenu **et** tous les paiements (cascade §5.4).
- **Backfill** : dry-run compte sans écrire ; apply crée ; relance = idempotente (0 nouveau) ; skipped_existing correct.
- **Réconciliation** : après backfill, `revenue.diff ≈ 0` vs P&L accrual ; écart dépenses = taxes récupérables, `balanced=true`.
- **Robustesse** : compte 4000 supprimé/inactif → POST facture réussit (201) + `autopost_error` posé + `repair` rejoue après recréation du compte.
- **Verrou auto** : PUT/post/reverse/DELETE sur une écriture `entry_type=auto` → 400.
- **Isolation cross-org** : org A poste, org B ne voit pas l'écriture ; backfill de B n'inclut pas les docs de A.
- **Multi-devise** : facture USD → écriture équilibrée, total = `total_cad`.
- **Non-régression Phase 1** : journal manuel, ouverture, apport, balance, bilan inchangés ; les écritures manuelles ne sont jamais touchées par l'auto-posting.

### 11.3 E2E manuel

- Activer l'auto-posting dans Paramètres, lancer le backfill de l'exercice ProFireManager (dry-run puis apply), vérifier la réconciliation P&L, consulter le grand livre 4000/1100/1000, télécharger le bilan (équilibré).

**Cible : ~50 tests** (~22 unitaires + ~26 intégration + ~2 E2E manuels).

## 12. Frontend

- **Onglet « Auto-posting »** dans `LedgerPage` (feature #12), gaté `accounting:read` : toggle d'activation (`autopost_enabled`, `accounting:write`), sélecteur du compte de crédit des dépenses, carte de **couverture** (X/Y factures postées), badge `pending_errors` en rouge avec bouton **« Réparer »**, et **assistant de backfill** (choix période → dry-run affichant « N écritures seront créées » → confirmation).
- **Badge sur les écritures auto** dans l'onglet Journal : `entry_type="auto"` → pastille « Auto » + lien vers le document source ; boutons d'édition/contre-passation **masqués** (verrou §8.3).
- **Indicateur `autopost_error`** sur les listes Factures/Dépenses (petite icône d'alerte) renvoyant vers l'onglet Auto-posting.
- Réutilise `RouteGuard`, `hasPermission`, format CAD existants. Pas de nouvelle lib.

## 13. Limites / hors scope Phase 2

- **Compte de crédit des dépenses = Encaisse par défaut** (point ouvert #1) — un vrai cycle fournisseur (A/P avec paiement séparé, échéancier) est hors scope ; le flag `expense_default_credit_account` permet A/P global mais sans suivi par facture fournisseur.
- **`amount` des dépenses supposé TTC** (§5.6) — à confirmer ; si l'usage réel est HT, le mapping change (charge = amount_cad, taxes en sus) — à trancher au plan.
- **Devises** : GL CAD only (invariant Phase 1). Écart/gain de change non modélisé ; on poste au taux snapshoté de chaque doc, sans réévaluation.
- **Pas de transaction Mongo garantie** si la topologie de prod ne la supporte pas → cohérence **éventuelle** via `autopost_error` + repair (§10), pas atomique stricte.
- **Écriture de clôture annuelle** toujours **manuelle** (limite Phase 1 §7.2.1 inchangée) — l'auto-posting ne clôture pas l'exercice.
- **Devis** (`quotes`) non comptabilisés (pas un événement financier — cohérent avec le P&L).
- **Recouvrement/créances douteuses**, provisions, écritures de régularisation (charges à payer, produits constatés d'avance) → journal manuel.
- **Pas de re-post rétroactif** si le plan comptable change (ex. on remappe une catégorie sur un autre compte 5xxx) : les écritures déjà postées gardent leur compte ; il faut régénérer via PUT du doc source ou un backfill ciblé.
- **Taux de change** figé au snapshot du doc ; pas de réévaluation A/R en devise à la date de bilan.

## 14. Rollback plan

1. **L'auto-posting produit des écritures erronées** : passer `autopost_enabled=false` (opt-out immédiat, aucun nouveau post) ; les écritures auto déjà postées se **contre-passent** en masse via un utilitaire (ou individuellement — elles restent des écritures `posted` normales, net-zérobables). Le journal manuel et les états financiers Phase 1 restent intacts.
2. **Un hook casse un endpoint métier** : `_safe_autopost` empêche déjà toute propagation (décision #6). Si un bug contourne le garde, **retirer le hook** (les hooks sont additifs en fin d'endpoint) et redéployer — les endpoints sources retrouvent leur comportement Phase 1 exact.
3. **Doublons détectés** : l'index unique partiel (§4.1) les empêche à l'insert ; s'il faut nettoyer un état antérieur, un script one-shot contre-passe les auto en trop (jamais de delete physique).
4. **Rollback complet de la Phase 2** : redéployer la version pré-Phase-2. Les champs `autopost_enabled`/`expense_default_credit_account` sur `company_settings` et `autopost_error` sur les docs sont **ignorés** par l'ancien code. Les écritures `entry_type="auto"` déjà présentes restent des écritures `posted` valides dans le grand livre Phase 1 (l'ancien code les lit sans problème — elles sont équilibrées). **Aucune donnée métier existante n'est mutée** par la Phase 2 (seulement des champs additifs + des écritures additives).

**Point de non-retour :** aucun. La Phase 2 est **purement additive et opt-in**. Elle ne modifie ni ne migre aucune donnée métier existante ; elle ajoute des champs à défaut sûr et des écritures dérivées contre-passables. La seule modification de code Phase 1 est l'ajout de deux paramètres à défaut `None` sur `_create_journal_entry` (rétrocompatible §6.2).

## 15. Impact estimé

- **Backend** : ~3 nouveaux endpoints `/api/ledger/autopost/*` + 1 réconciliation (~150 lignes), 3 fonctions de mapping `_autopost_invoice/_post_expense_entry/…` + primitives `_post/_unpost_source_entry`/`_safe_autopost`/`_resolve_ledger_account` (~350 lignes), hooks sur 7 endpoints existants (~120 lignes modifiées), verrou auto sur 4 endpoints manuels (~15 lignes), migration idempotente (~40 lignes), 2 params sur `_create_journal_entry` (~5 lignes). Total : **~700 lignes ajoutées**, ~140 modifiées.
- **Frontend** : 1 onglet « Auto-posting » dans `LedgerPage` + badges auto + indicateurs d'erreur (~350 lignes).
- **Tests** : ~50 tests, **~800 lignes**.
- **Nouvelles collections** : aucune (réutilise Phase 1).
- **Nouveaux champs** : `company_settings.autopost_enabled` + `expense_default_credit_account` ; `invoices/expenses.autopost_error` ; `journal_entries.source_type/source_id` désormais renseignés (déjà au schéma).
- **Nouveaux index** : 1 index unique partiel sur `(org, source_type, source_id)` pour les auto vivants.
- **Env vars nouvelles** : aucune.
- **Coût opérationnel** : négligeable (0 appel externe ; écritures Mongo dérivées des ops déjà en place).
