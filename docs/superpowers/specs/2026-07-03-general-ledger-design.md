# Grand livre — comptabilité en partie double (feature #12) — Design

**Statut :** design approuvé 2026-07-03 (brainstorming session avec gussdub, propriétaire de ProFireManager Inc.)
**Auteur :** Claude (brainstorming + explore-phase sur `backend/server.py`)

## 1. Objectif

FacturePro n'a **aucune comptabilité générale** aujourd'hui. Il produit des rapports fiscaux dérivés (P&L feature #5, TPS/TVQ feature #4, T2125 feature #10) par agrégation directe des collections `invoices` et `expenses`, mais il n'existe ni **plan comptable**, ni **grand livre**, ni **balance de vérification**, ni **bilan** (état de la situation financière).

Ce module introduit un **grand livre en partie double** (double-entry ledger) : un plan comptable canadien pré-rempli, un journal d'écritures manuelles équilibrées (débits = crédits), un assistant de bilan d'ouverture, et les trois états financiers de base (grand livre général, balance de vérification, bilan).

**Cas d'usage principal :** ProFireManager Inc. est une **société incorporée** (`entity_type = "corporation"`). Contrairement à un travailleur autonome qui produit un T2125 (couvert par la feature #10), une société doit produire un **T2** avec des **états financiers GIFI** complets — bilan + état des résultats. Sa comptable externe (rôle `accountant`) fournit une **balance de vérification d'ouverture** en début d'exercice, saisit les apports du propriétaire, les amortissements, les ajustements de fin d'exercice, et doit pouvoir produire un bilan à toute date. La feature #10 (T2125) reste destinée aux travailleurs autonomes ; ce module comble le trou côté sociétés.

**Contexte codebase :**
- Multi-tenant `organization_id` en place partout (feature #11, cf. `_ORG_SCOPED_COLLECTIONS` `server.py:1345`). Toute nouvelle collection sera scopée org.
- RBAC granulaire en place : `PERMISSIONS_EDITABLE` / `PERMISSIONS_OWNER_ONLY` (`server.py:1197`), `require_permission("code")` (`server.py:1320`), matrice `role_permissions` par org, résolveur `_resolve_permissions` (`server.py:1225`). On y ajoute `accounting:read` + `accounting:write`.
- Catégories de dépenses ARC en place (feature #3, `EXPENSE_CATEGORIES` `server.py:150`) — 18 catégories avec `arc_line`, `deductible_percentage`, `group`. Le plan comptable mappe ses **comptes de dépenses** sur ces catégories pour permettre l'auto-posting Phase 2.
- P&L existant `_aggregate_pnl` (`server.py:322`) — sert de point de réconciliation Phase 2 (base caisse vs exercice).
- `company_settings` existe (créé au register `server.py:2124`), contient `province`, `entity_type`, `home_office_percentage`. On y **ajoute** les champs d'exercice financier.
- Pattern PDF FR-CA établi : `_t2125_format_money` (`server.py:5352`) formate `85 000,00 $`, `SimpleDocTemplate` ReportLab, `html.escape` sur strings user-supplied, headers `no-store, no-cache` (`server.py:5548`).
- Migrations idempotentes au boot dans `@app.on_event("startup")` (`server.py:5555`), après `migrate_pst_to_qst()` et `migrate_organizations_v1()`.

**Livraison en 2 phases :**
- **Phase 1 (MVP)** — fondation manuelle, livrable seul. Plan comptable, journal manuel, assistant ouverture, apport propriétaire, grand livre, balance de vérification, bilan, PDF. **C'est le périmètre de ce spec + son plan.**
- **Phase 2** — auto-posting depuis factures/dépenses/paiements. Design inclus ici (§10) pour cadrer les décisions Phase 1, mais **plan séparé plus tard**.

## 2. Décisions de design (brainstorming — fixes)

| # | Question | Décision | Alternatives rejetées |
|---|----------|----------|------------------------|
| 1 | Modèle comptable | **Partie double stricte** : chaque écriture a `lines[]` avec somme débits = somme crédits, équilibre **forcé au backend** (rejet 400 si déséquilibre > 0,005 $) | Simple entrée (cash book) → ne produit pas de bilan, inutile pour un T2 société. |
| 2 | Intégration factures/dépenses | **Hybride, en 2 phases**. Phase 1 = journal 100 % manuel. Phase 2 = auto-posting depuis factures/paiements/dépenses + journal manuel pour le reste (apport, amortissement, ajustements). | Auto-posting dès le MVP → couple le GL à 3 workflows existants + idempotence complexe avant d'avoir validé le socle. Manuel seul pour toujours → double saisie insoutenable. |
| 3 | Bilan d'ouverture | **Assistant dédié** : la comptable saisit les soldes d'ouverture par compte à une date de début choisie ; validation Dr = Cr ; génère **une écriture d'ouverture spéciale** (`entry_type = "opening"`) | Champ `opening_balance` sur chaque compte → sort de la partie double, casse la traçabilité, complique la balance. Écriture ordinaire → risque de suppression accidentelle ; on veut un type protégé. |
| 4 | Numérotation des comptes | **Plages canoniques** : 1000-1999 Actif, 2000-2999 Passif, 3000-3999 Capitaux propres, 4000-4999 Revenus, 5000-5999 Dépenses. Type déduit de la plage à la création (validé). | Numérotation libre → perte de la sémantique type↔plage, risque d'incohérence solde normal. |
| 5 | Mutabilité des écritures | **Immuable + contre-passation** (reversing entry). Une écriture postée ne se modifie pas ; on la **contre-passe** (écriture miroir Dr↔Cr, `reverses_entry_id`) puis on en crée une correcte. Les écritures en `status = "draft"` sont éditables/supprimables ; le `post` les fige. | Édition en place → détruit la piste d'audit ARC (6 ans), et casserait l'idempotence de l'auto-posting Phase 2. Suppression physique → idem. |
| 6 | Apport du propriétaire | **Formulaire guidé** qui génère l'écriture `Dr Encaisse (1000) / Cr Apport du propriétaire (3100)`. Wrapper autour du journal manuel, pas un mécanisme séparé. | Endpoint comptable brut → l'owner d'une TPE ne connaît pas le sens débit/crédit ; le formulaire guidé abstrait la partie double. |
| 7 | Où loge l'exercice financier | **Sur `company_settings`** : `fiscal_year_end_month` + `fiscal_year_end_day` (une société peut clôturer ailleurs qu'au 31 déc.). | Collection dédiée `fiscal_years` → sur-ingénierie v1 ; un seul exercice courant suffit pour le bilan à date. |
| 8 | Résultat net dans le bilan | **Dérivé, non stocké** : capitaux propres = capital + apports + bénéfices non répartis d'ouverture + **(revenus − dépenses de l'exercice)**. Pas d'écriture de clôture annuelle en v1. | Écriture de clôture (closing entry) qui vide revenus/dépenses vers bénéfices non répartis → correcte comptablement mais lourde ; le calcul dérivé donne un bilan juste sans clôture manuelle. Noté comme limite v1. |
| 9 | Plan comptable pré-rempli | **Seeded par organisation** au premier accès GL (idempotent), personnalisable ensuite (CRUD complet). Comptes de dépenses **mappés sur `EXPENSE_CATEGORIES`** (feature #3) pour l'auto-posting Phase 2. | Plan hardcodé non éditable → une société a des comptes spécifiques. Plan vide → l'utilisateur doit tout créer, mauvaise UX. |
| 10 | Suppression de compte | **Soft (inactivation)** si le compte a des lignes ; hard-delete seulement si zéro ligne. | Hard-delete inconditionnel → orphelinerait des lignes d'écriture, casserait le grand livre. |
| 11 | Devise dans le GL | **CAD uniquement** dans le grand livre v1. Les montants proviennent déjà convertis (`amount_cad`, `total_cad`, `subtotal` via `exchange_rate_to_cad`). | GL multi-devise (comptes en USD + écart de change) → hors scope, noté §13. |
| 12 | RBAC | **2 nouveaux codes éditables** `accounting:read` + `accounting:write` (dans `PERMISSIONS_EDITABLE`). Défaut : comptable = read+write, lecteur = read. | Owner-only → un comptable externe **doit** pouvoir tenir les livres, c'est son métier. |
| 13 | Numéro d'écriture | **Séquence par org** `JE-0001`, `JE-0002`… (compteur atomique), l'écriture d'ouverture = `OB-0001`. | UUID visible → illisible pour la comptable qui référence des pièces. |

## 3. Modèle de données

### 3.1 Nouvelle collection `chart_of_accounts`

Un document par compte, scopé org.

```python
{
  "id": str,                       # uuid
  "organization_id": str,          # scope (feature #11)
  "created_by_user_id": str,       # audit
  "account_number": str,           # "1000".."5999" — unique par org
  "name": str,                     # "Encaisse", "Revenus de services"…
  "account_type": str,             # "asset"|"liability"|"equity"|"revenue"|"expense"
  "sub_type": str | None,          # "current_asset"|"fixed_asset"|"current_liability"|
                                   #  "long_term_liability"|"share_capital"|"retained_earnings"|
                                   #  "operating_revenue"|"operating_expense"|"tax_payable"|
                                   #  "tax_recoverable" … (libre, guidé par UI)
  "normal_balance": str,           # "debit"|"credit" — dérivé du type, stocké pour lisibilité
  "is_active": bool,               # false = inactif (soft-delete)
  "is_system": bool,               # true = compte par défaut protégé (ne peut être supprimé)
  "expense_category_code": str | None,  # mapping EXPENSE_CATEGORIES (feature #3) pour auto-posting Phase 2
  "description": str,              # optionnel
  "created_at": str,               # ISO 8601 UTC
}
```

**Solde normal par type** (dérivé, validé) :

| `account_type` | Plage numéro | `normal_balance` | Signe augmentation |
|---|---|---|---|
| `asset` | 1000-1999 | `debit` | Débit augmente |
| `liability` | 2000-2999 | `credit` | Crédit augmente |
| `equity` | 3000-3999 | `credit` | Crédit augmente |
| `revenue` | 4000-4999 | `credit` | Crédit augmente |
| `expense` | 5000-5999 | `debit` | Débit augmente |

**Index** : `(organization_id, account_number)` unique, `(organization_id, account_type)`, `(organization_id, is_active)`.

### 3.2 Nouvelle collection `journal_entries`

Un document par écriture, avec les lignes **embarquées** (atomicité : une écriture s'insère/se lit d'un bloc, jamais de ligne orpheline — même choix que `payments[]` embarqué dans `invoices`, feature #6).

```python
{
  "id": str,                       # uuid
  "organization_id": str,          # scope
  "created_by_user_id": str,       # audit
  "entry_number": str,             # "JE-0001" | "OB-0001" (ouverture) — séquence par org
  "entry_date": str,               # ISO date "YYYY-MM-DD" (date comptable de l'écriture)
  "description": str,              # libellé de l'écriture (ex: "Apport du propriétaire")
  "reference": str | None,         # n° pièce / chèque / réf externe
  "entry_type": str,               # "manual"|"opening"|"reversal"|"auto" (auto = Phase 2)
  "status": str,                   # "draft"|"posted" — SEULEMENT. draft = brouillon exclu des soldes,
                                   #  posted = comptabilisé, compté dans les soldes. PAS de statut
                                   #  "reversed" : une écriture contre-passée RESTE "posted" (§5.3).
  "lines": [                       # >= 2 lignes, équilibrées Dr = Cr
    {
      "line_id": str,              # uuid (stable pour référence future)
      "account_id": str,           # FK chart_of_accounts.id (même org)
      "account_number": str,       # snapshot lisible (dénormalisé pour affichage/PDF)
      "account_name": str,         # snapshot lisible
      "debit": float,              # >= 0 (CAD) — exactement un des deux > 0 par ligne
      "credit": float,             # >= 0 (CAD)
      "line_description": str | None,
    },
    ...
  ],
  "total_debit": float,            # somme lines[].debit (dénormalisé, = total_credit)
  "total_credit": float,           # somme lines[].credit
  # Contre-passation (feature décision #5) — champs d'AUDIT/LIEN uniquement.
  # Ils tracent la relation origine↔miroir pour l'UI et la piste d'audit ;
  # ils N'EXCLUENT JAMAIS une écriture du calcul de solde (§5.2 / §5.3).
  "reverses_entry_id": str | None, # si entry_type="reversal" : id de l'écriture contre-passée (le miroir pointe vers l'origine)
  "reversed_by_entry_id": str | None,  # posé sur l'écriture d'origine : id du miroir qui la contre-passe
  # Phase 2 — auto-posting (nul en Phase 1)
  "source_type": str | None,       # "invoice"|"payment"|"expense" (Phase 2)
  "source_id": str | None,         # id du doc source (Phase 2, idempotence)
  "created_at": str,               # ISO 8601 UTC
  "posted_at": str | None,         # ISO 8601 UTC (moment du post)
}
```

**Invariants (forcés backend) :**
- `len(lines) >= 2`
- Chaque ligne : `debit >= 0` et `credit >= 0`, et **exactement un** des deux est `> 0` (jamais les deux, jamais zéro).
- `round(sum(debit), 2) == round(sum(credit), 2)` — tolérance `0.005 $`, sinon 400.
- Tous les `account_id` référencent des comptes **actifs** de la **même org**.
- Une écriture `status="posted"` est **immuable** (PUT/DELETE → 400) : ses `lines`, montants et `status` ne changent jamais. Le chemin de contre-passation **n'altère pas le solde** de l'origine : il crée une écriture miroir et se contente de poser le champ d'audit `reversed_by_entry_id` sur l'origine (qui reste `posted`, cf. §5.3).

**Index** : `(organization_id, entry_date)`, `(organization_id, status)`, `(organization_id, entry_number)` unique, `(organization_id, lines.account_id)`, `(organization_id, source_type, source_id)` (Phase 2, idempotence).

### 3.3 Nouvelle collection `ledger_counters` (séquence de numéros)

```python
{
  "id": str,                       # "{organization_id}:journal_entry"
  "organization_id": str,
  "counter_type": str,             # "journal_entry"
  "value": int,                    # dernier numéro attribué
}
```

Incrément **atomique** via `find_one_and_update({... }, {"$inc": {"value": 1}}, upsert=True, return_document=AFTER)` — zéro race sur l'attribution du `entry_number` (même garantie atomique que le quota scan feature #8).

### 3.4 Champs ajoutés à `company_settings`

```python
"fiscal_year_end_month": int,    # 1-12, défaut 12 (décembre)
"fiscal_year_end_day": int,      # 1-31, défaut 31
"ledger_start_date": str | None, # ISO date — date de début de tenue GL (posée par l'assistant ouverture)
```

Ajoutés par migration idempotente (`setdefault`), et exposés/éditables via `PUT /api/settings/company` (validation `1<=month<=12`, `1<=day<=31`).

## 4. Plan comptable par défaut (seeded par org)

Créé au premier accès GL de l'org (idempotent : ne recrée pas si des comptes existent déjà). **Société canadienne (QC).** Les 12 comptes de base + les comptes de dépenses mappés sur `EXPENSE_CATEGORIES` (feature #3).

### 4.1 Comptes de base (12, `is_system = true`)

| N° | Nom | `account_type` | `sub_type` | `normal_balance` |
|---|---|---|---|---|
| 1000 | Encaisse | asset | current_asset | debit |
| 1100 | Comptes clients | asset | current_asset | debit |
| 1200 | TPS à recouvrer | asset | tax_recoverable | debit |
| 1210 | TVQ à recouvrer | asset | tax_recoverable | debit |
| 2000 | Comptes fournisseurs | liability | current_liability | credit |
| 2100 | TPS à payer | liability | tax_payable | credit |
| 2110 | TVQ à payer | liability | tax_payable | credit |
| 3000 | Capital-actions | equity | share_capital | credit |
| 3100 | Apport du propriétaire | equity | contributed_capital | credit |
| 3200 | Bénéfices non répartis | equity | retained_earnings | credit |
| 4000 | Revenus de services | revenue | operating_revenue | credit |
| 5900 | Dépenses diverses | expense | operating_expense | debit |

### 4.2 Comptes de dépenses mappés sur `EXPENSE_CATEGORIES` (feature #3)

Un compte 5xxx par catégorie ARC canonique (le code `other` est couvert par 5900 « Dépenses diverses » ci-dessus). Chaque compte porte `expense_category_code` = le `code` de la catégorie, ce qui permettra l'auto-posting Phase 2 sans table de mapping supplémentaire.

| N° | Nom | `expense_category_code` | ligne ARC (réf.) |
|---|---|---|---|
| 5000 | Frais de bureau | office_expenses | 8810 |
| 5010 | Fournitures | office_supplies | 8811 |
| 5020 | Honoraires professionnels | professional_fees | 8860 |
| 5030 | Frais bancaires | bank_charges | 8620 |
| 5040 | Abonnements et licences | subscriptions | 8740 |
| 5100 | Publicité et promotion | advertising | 8520 |
| 5110 | Repas et représentation | meals_entertainment | 8523 |
| 5200 | Loyer | rent | 8910 |
| 5210 | Services publics | utilities | 9220 |
| 5220 | Assurances | insurance | 8690 |
| 5230 | Entretien et réparations | repairs_maintenance | 8960 |
| 5300 | Frais de déplacement | travel | 9200 |
| 5310 | Frais de véhicule | vehicle_expenses | 9281 |
| 5320 | Livraison et fret | delivery | 9275 |
| 5400 | Salaires et avantages | salaries | 9060 |
| 5410 | Sous-traitance | subcontracts | 9367 |
| 5420 | Frais de gestion | management_fees | 8871 |

**Total plan par défaut : 29 comptes** (12 de base + 17 comptes de dépenses).

> Note : les comptes de taxes par défaut couvrent TPS/TVQ (QC). Une société hors QC (TVH) ajoutera ses comptes 1220 « TVH à recouvrer » / 2120 « TVH à payer » via le CRUD — noté comme personnalisation, pas seedé par défaut en v1 (le seed reflète le profil QC de ProFireManager).

### 4.3 Génération du plan par défaut

`_default_chart_of_accounts()` retourne la liste ci-dessus (constante serveur, à côté de `EXPENSE_CATEGORIES`). Les comptes de dépenses sont **générés à partir de `EXPENSE_CATEGORIES`** + une table de numérotation `{code: account_number}`, garantissant qu'ils restent synchronisés si une catégorie est ajoutée feature #3.

## 5. Logique partie double

### 5.1 Validation de l'équilibre (backend, forcée)

```python
def _validate_entry_balance(lines: list) -> None:
    if len(lines) < 2:
        raise HTTPException(400, "Une écriture doit avoir au moins 2 lignes")
    total_debit = 0.0
    total_credit = 0.0
    for ln in lines:
        d = round(float(ln.get("debit", 0) or 0), 2)
        c = round(float(ln.get("credit", 0) or 0), 2)
        if d < 0 or c < 0:
            raise HTTPException(400, "Débit et crédit doivent être >= 0")
        if (d > 0) == (c > 0):   # les deux > 0, ou les deux == 0
            raise HTTPException(400, "Chaque ligne doit avoir soit un débit soit un crédit, pas les deux")
        total_debit += d
        total_credit += c
    if abs(round(total_debit, 2) - round(total_credit, 2)) > 0.005:
        raise HTTPException(400,
            f"Écriture déséquilibrée : débits {total_debit:.2f} ≠ crédits {total_credit:.2f}")
```

### 5.2 Calcul du solde d'un compte

Le solde d'un compte à une date donnée est la somme de ses mouvements, **orientée par le solde normal** :

```python
def _account_balance(scope, account_id, normal_balance, as_of_date=None):
    """Solde d'un compte à as_of_date (inclus). Ne compte que status='posted'."""
    match = {**scope, "status": "posted", "lines.account_id": account_id}
    if as_of_date:
        match["entry_date"] = {"$lte": as_of_date}
    total_debit = 0.0
    total_credit = 0.0
    for entry in db.journal_entries.find(match, {"_id": 0, "lines": 1}):
        for ln in entry["lines"]:
            if ln["account_id"] == account_id:
                total_debit += float(ln.get("debit", 0) or 0)
                total_credit += float(ln.get("credit", 0) or 0)
    if normal_balance == "debit":
        return round(total_debit - total_credit, 2)   # actif/dépense : Dr - Cr
    return round(total_credit - total_debit, 2)        # passif/CP/revenu : Cr - Dr
```

- Un solde positif est « normal » (débiteur pour un actif, créditeur pour un passif).
- Un solde négatif signale une anomalie (ex. encaisse négative = découvert) — affiché tel quel, pas masqué.
- **TOUTES les écritures `posted` comptent, sans exception.** `_account_balance` filtre **uniquement** sur `status="posted"` ; il ne regarde JAMAIS `reverses_entry_id` ni `reversed_by_entry_id`. L'écriture d'origine ET son miroir de contre-passation sont tous deux `posted`, donc tous deux comptés — leurs effets s'annulent naturellement au net (cf. §5.3).
- **Seules les écritures `posted` comptent.** Les brouillons (`draft`) n'affectent aucun solde.

> **Invariant de contre-passation :** pour toute écriture et son miroir de contre-passation, `somme(écriture) + somme(miroir) = 0` sur chaque compte touché. C'est **garanti par construction** parce que les deux restent `posted` et que le miroir a exactement les débits/crédits inversés. Il n'existe **aucun statut** qui retire une écriture postée du solde — c'est précisément ce qui évite le double effet (retrait de l'origine + application du miroir) qui donnait un solde faux.

### 5.3 Contre-passation (reversing entry)

```
POST /api/ledger/entries/{id}/reverse
```

**Principe (pratique comptable standard).** On ne supprime **jamais** une écriture et on ne la retire **jamais** du solde. Une contre-passation = une **nouvelle écriture `posted`** qui est le miroir exact de l'origine (débits et crédits inversés). **L'origine reste `posted`. Le miroir est `posted`. Les deux comptent dans le solde → le net s'annule automatiquement à zéro.**

Le endpoint :
1. Vérifie que l'origine est `posted` (sinon 400) et **pas déjà contre-passée** — si `reversed_by_entry_id` est déjà posé → 400 « Écriture déjà contre-passée » (empêche la double contre-passation).
2. Crée une nouvelle écriture `entry_type="reversal"`, `status="posted"`, avec chaque ligne inversée (`debit`↔`credit`), `entry_date` = date fournie (défaut : aujourd'hui), description « Contre-passation de {entry_number} », et `reverses_entry_id = id` (pointe vers l'origine).
3. Pose **uniquement** le champ d'audit `reversed_by_entry_id` sur l'origine (id du miroir). **Le `status` de l'origine ne change pas — elle reste `posted`.**

**Effet sur les soldes.** Comme `_account_balance` (§5.2) compte toutes les écritures `posted` sans jamais consulter `reverses_entry_id`/`reversed_by_entry_id`, l'origine et son miroir sont tous deux inclus. Miroir = origine avec Dr↔Cr inversés ⟹ leur somme est nulle sur chaque compte. **Net = 0, garanti.**

> **Pourquoi PAS de statut `reversed` ?** Un statut qui exclurait l'origine du solde produirait un **double effet** : l'origine serait retirée (via `reversed`) **et** le miroir s'appliquerait → le solde final vaudrait `−montant` au lieu de `0`. Tous les états financiers deviendraient faux après toute contre-passation. On l'évite en gardant l'origine `posted` : un seul effet net (celui du miroir), qui annule exactement l'origine.

L'origine et sa contre-passation restent toutes deux dans le grand livre (piste d'audit ARC intacte, append-only), reliées par les champs `reverses_entry_id`/`reversed_by_entry_id`, et leurs effets s'annulent au net.

## 6. API REST

Tous les endpoints sont préfixés `/api/ledger` (sauf le champ fiscal dans `/api/settings/company` existant), scopés `organization_id`, et protégés par `require_permission("accounting:read")` (lecture) ou `require_permission("accounting:write")` (écriture).

### 6.1 Plan comptable

```
GET  /api/ledger/accounts?type=&active=          accounting:read
     → 200 [{id, account_number, name, account_type, sub_type,
             normal_balance, is_active, is_system, expense_category_code}, ...]
     Trié par account_number. Filtres optionnels type / active.

POST /api/ledger/accounts                         accounting:write
     body: {account_number, name, account_type, sub_type?, description?, expense_category_code?}
     Validation :
       - account_number 4 chiffres, plage cohérente avec account_type (400 sinon)
       - unique dans l'org (409 si doublon)
       - account_type ∈ 5 valeurs ; normal_balance dérivé du type
     → 201 {account}

PUT  /api/ledger/accounts/{id}                    accounting:write
     body: {name?, sub_type?, description?, is_active?, expense_category_code?}
     - account_number et account_type NON modifiables (400 si tentative) — protège la cohérence type↔plage
     - is_system=true : name modifiable, mais is_active forcé true (400 si désactivation)
     → 200 {account}

DELETE /api/ledger/accounts/{id}                  accounting:write
     - is_system=true → 400 "Compte système protégé"
     - compte avec au moins 1 ligne d'écriture → 400 "Compte utilisé, désactivez-le plutôt"
     - sinon hard-delete
     → 204
```

### 6.2 Journal des écritures manuelles

```
GET  /api/ledger/entries?start=&end=&account_id=&status=   accounting:read
     → 200 [{id, entry_number, entry_date, description, reference,
             entry_type, status, total_debit, total_credit, lines[]}, ...]
     Trié entry_date desc, entry_number desc.

GET  /api/ledger/entries/{id}                     accounting:read
     → 200 {entry complet}  / 404

POST /api/ledger/entries                          accounting:write
     body: {entry_date, description, reference?, status?("draft"|"posted"),
            lines: [{account_id, debit, credit, line_description?}, ...]}
     Validation :
       - _validate_entry_balance(lines)  (§5.1)
       - tous account_id actifs + même org (400 sinon)
       - entry_type forcé "manual"
     Actions :
       - snapshot account_number/account_name sur chaque ligne
       - attribue entry_number atomique (JE-XXXX) via ledger_counters
       - si status="posted" : pose posted_at
     → 201 {entry}

PUT  /api/ledger/entries/{id}                     accounting:write
     - status="posted" → 400 "Écriture figée, contre-passez-la"
     - status="draft" : ré-édition complète (re-valide équilibre)
     → 200 {entry}

POST /api/ledger/entries/{id}/post                accounting:write
     - draft → posted (re-valide équilibre, pose posted_at)
     → 200 {entry}   / 400 si déjà posted

POST /api/ledger/entries/{id}/reverse             accounting:write
     body: {entry_date?, description?}
     - source doit être "posted" (400 sinon), pas déjà contre-passée
       (reversed_by_entry_id déjà posé → 400)
     - crée l'écriture miroir POSTED (§5.3), pose reversed_by_entry_id sur
       l'origine ; l'origine RESTE "posted" (jamais de statut "reversed")
     → 201 {reversal_entry}

DELETE /api/ledger/entries/{id}                   accounting:write
     - status="posted" → 400
     - draft uniquement → hard-delete
     → 204
```

### 6.3 Assistant bilan d'ouverture

```
GET  /api/ledger/opening-balance                  accounting:read
     → 200 {
         exists: bool,               # true si une écriture OB existe déjà
         opening_date: str | None,   # = company_settings.ledger_start_date
         entry: {...} | None,        # l'écriture d'ouverture si présente
       }

POST /api/ledger/opening-balance                  accounting:write
     body: {
       opening_date: "YYYY-MM-DD",
       balances: [{account_id, debit, credit}, ...]   # soldes d'ouverture par compte
     }
     Validation :
       - _validate_entry_balance(balances)  → Dr = Cr forcé
       - aucune écriture OB préexistante (409 "Bilan d'ouverture déjà saisi — modifiez-le")
       - tous account_id actifs + même org
     Actions :
       - crée UNE écriture entry_type="opening", entry_number="OB-0001",
         status="posted", entry_date=opening_date
       - pose company_settings.ledger_start_date = opening_date
     → 201 {entry}

PUT  /api/ledger/opening-balance                  accounting:write
     - remplace l'écriture OB (re-valide équilibre). Autorisé car pré-clôture.
     → 200 {entry}
```

### 6.4 Apport du propriétaire (formulaire guidé)

```
POST /api/ledger/owner-contribution               accounting:write
     body: {amount, date, cash_account_id?, equity_account_id?, description?}
     Défauts : cash_account_id = compte 1000 (Encaisse),
               equity_account_id = compte 3100 (Apport du propriétaire)
     Validation : amount > 0
     Actions : crée une écriture manuelle postée
       Dr {cash_account} amount / Cr {equity_account} amount
       description = description ou "Apport du propriétaire"
     → 201 {entry}
```

### 6.5 États financiers

```
GET  /api/ledger/general-ledger?account_id=&start=&end=    accounting:read
     → 200 {
         account: {id, account_number, name, account_type, normal_balance},
         opening_balance: float,        # solde avant `start`
         lines: [{entry_id, entry_number, entry_date, description,
                  reference, debit, credit, running_balance}, ...],
         closing_balance: float,
       }
     running_balance = solde progressif orienté par normal_balance.
     N'inclut que status="posted".

GET  /api/ledger/trial-balance?as_of=YYYY-MM-DD    accounting:read
     → 200 {
         as_of: str,
         accounts: [{account_number, name, account_type,
                     debit_balance: float, credit_balance: float}, ...],
         total_debit: float,
         total_credit: float,
         balanced: bool,   # total_debit == total_credit (doit être true)
       }
     Chaque compte apparaît dans la colonne de son solde net :
       solde net > 0 côté normal_balance ; comptes à solde 0 exclus.

GET  /api/ledger/balance-sheet?as_of=YYYY-MM-DD    accounting:read
     → 200 {
         as_of, fiscal_year_start, fiscal_year_end,
         assets:      {accounts: [...], total: float},
         liabilities: {accounts: [...], total: float},
         equity: {
           accounts: [...],              # comptes 3xxx (capital, apports, BNR d'ouverture)
           net_income_current_year: float,   # revenus - dépenses de l'exercice courant
           total: float,
         },
         total_assets: float,
         total_liabilities_and_equity: float,
         balanced: bool,   # total_assets == total_liabilities_and_equity
       }

GET  /api/ledger/trial-balance/pdf?as_of=          accounting:read  → application/pdf
GET  /api/ledger/balance-sheet/pdf?as_of=          accounting:read  → application/pdf
```

## 7. Calcul du bilan et de la balance de vérification (formules exactes)

### 7.1 Balance de vérification

Pour chaque compte actif de l'org (+ inactifs ayant des lignes) :

```
net = _account_balance(scope, account_id, normal_balance, as_of)
si normal_balance == "debit":
    debit_balance  = net si net >= 0 sinon 0
    credit_balance = -net si net < 0 sinon 0
sinon (normal_balance == "credit"):
    credit_balance = net si net >= 0 sinon 0
    debit_balance  = -net si net < 0 sinon 0
```

`total_debit = Σ debit_balance`, `total_credit = Σ credit_balance`. **Invariant : `total_debit == total_credit`** (garanti par la partie double si toutes les écritures sont équilibrées). Si `abs(total_debit - total_credit) > 0.01`, `balanced = false` → signal d'anomalie (ne devrait jamais arriver ; log + affichage d'alerte).

### 7.2 Bilan (état de la situation financière)

**Exercice courant** dérivé de `company_settings.fiscal_year_end_month/day` et de `as_of` :

```python
def _current_fiscal_year(as_of, fy_end_month, fy_end_day):
    """Retourne (fy_start, fy_end) encadrant as_of."""
    y = as_of.year
    fy_end_this = date(y, fy_end_month, fy_end_day)
    if as_of <= fy_end_this:
        fy_end = fy_end_this
    else:
        fy_end = date(y + 1, fy_end_month, fy_end_day)
    fy_start = fy_end - relativedelta(years=1) + timedelta(days=1)
    return fy_start, fy_end
```

**Actif** : Σ des soldes des comptes `asset` à `as_of` (solde normal débiteur).
**Passif** : Σ des soldes des comptes `liability` à `as_of` (solde normal créditeur).

**Capitaux propres** :
```
equity_accounts_total = Σ soldes des comptes equity (3xxx) à as_of
                        # inclut capital-actions + apports + BNR reportés (ouverture)
net_income_current_year = revenue_total - expense_total
  où revenue_total = Σ soldes comptes revenue (4xxx) sur [fy_start, as_of]
     expense_total = Σ soldes comptes expense (5xxx) sur [fy_start, as_of]
total_equity = equity_accounts_total + net_income_current_year
```

> Le résultat net de l'exercice est **calculé sur la période [début d'exercice, as_of]**, pas cumulé depuis toujours, car les revenus/dépenses des exercices antérieurs sont censés être reportés en Bénéfices non répartis (3200). En v1, sans écriture de clôture automatique, la comptable passe une écriture manuelle de clôture en fin d'exercice (Dr Revenus / Cr Dépenses / Cr ou Dr BNR) — documenté dans l'aide de l'assistant. **Limite v1 assumée** (§13).

**Équation fondamentale** :
```
total_assets == total_liabilities + total_equity   → balanced
```
Si l'écart > 0,01 $, `balanced = false` (affiché en rouge dans l'UI + PDF, avec le montant de l'écart pour diagnostic).

### 7.2.1 Clôture annuelle — ⚠️ AVERTISSEMENT FORT (règle stricte)

Le résultat net est **dérivé** dans le bilan sur `[fy_start, as_of]` : c'est correct **à l'intérieur d'un même exercice**. Mais les comptes de **revenus (4xxx)** et de **dépenses (5xxx)** ne sont **jamais remis à zéro automatiquement** en v1 (pas d'écriture de clôture générée par le système).

> **⚠️ Sans écriture de clôture à la fin de l'exercice, le bilan de l'exercice N+1 sera DÉSÉQUILIBRÉ.** Concrètement : au passage à l'exercice N+1, `net_income_current_year` se recalcule sur `[fy_start(N+1), as_of]` et repart de zéro, **mais** le résultat de l'exercice N n'a jamais été viré en Bénéfices non répartis (3200). Le résultat de l'exercice N disparaît alors des capitaux propres du bilan N+1 → l'équation `Actif = Passif + CP` ne tient plus. C'est un **piège comptable classique** qu'il faut absolument documenter côté UI.

**Règle stricte à respecter :**
1. **La clôture se passe À la fin d'exercice ou APRÈS — JAMAIS en cours d'exercice.** Passer une écriture de clôture au milieu de l'exercice vide prématurément les revenus/dépenses et fausse tous les rapports intermédiaires.
2. À (ou après) la date de fin d'exercice, la comptable passe **une écriture de clôture manuelle** : `Dr Revenus (4xxx) / Cr Dépenses (5xxx) / Cr ou Dr Bénéfices non répartis (3200)` pour le résultat net, datée du dernier jour de l'exercice. Cela ramène 4xxx et 5xxx à zéro et transfère le résultat en 3200.
3. Une fois la clôture passée, le bilan de N+1 est équilibré : le résultat de N vit désormais dans le solde de 3200 (BNR reportés), et `net_income_current_year` de N+1 ne mesure plus que l'exercice courant.

**Limite v1 assumée** (§13) : cette écriture de clôture n'est **pas** automatisée. L'UI (Journal / Bilan) doit afficher un **avertissement visible** rappelant cette règle (cf. §9).

### 7.3 PDF FR-CA

Réutilise le pattern `_t2125_format_money` (`server.py:5352`, `85 000,00 $`) et `_render_t2125_pdf` (`server.py:5362`) : `SimpleDocTemplate` letter, `html.escape` sur `company_name` / noms de comptes, en-tête avec nom de société + date, tableaux ligne-par-ligne, totaux en gras, mention « État non audité — usage interne ». Headers `no-store, no-cache` (`server.py:5548`).

## 8. RBAC et migration

### 8.1 Nouveaux codes de permission

Ajout dans `PERMISSIONS_EDITABLE` (`server.py:1197`) :

```python
PERMISSIONS_EDITABLE = [
    ...
    "settings:read",   "settings:write",
    "accounting:read", "accounting:write",   # feature #12 — grand livre
]
```

Défauts (`DEFAULT_ROLE_PERMISSIONS` `server.py:1215`) :
- `accountant` : reçoit `accounting:read` + `accounting:write` (déjà `list(PERMISSIONS_EDITABLE)` → automatique).
- `viewer` : ajouter `"accounting:read"` à sa liste explicite.
- `owner` : inhérent (résolveur `_resolve_permissions` retourne tout `PERMISSIONS_EDITABLE`).

### 8.2 Migration idempotente `migrate_general_ledger_v1()`

Ajoutée dans le bloc startup (`server.py:5555`), après `migrate_organizations_v1()`.

```python
def migrate_general_ledger_v1():
    """Idempotente. Safe à chaque boot.
    1. Backfill des champs fiscaux sur company_settings.
    2. Backfill accounting:read/write dans role_permissions des orgs existantes.
    3. Indexes des nouvelles collections.
    (Le plan comptable par défaut est seedé au 1er accès GL, PAS ici — lazy,
     pour éviter de peupler des orgs qui n'utiliseront jamais le module.)"""
    # 1. Champs fiscaux (défaut 31 décembre)
    db.company_settings.update_many(
        {"fiscal_year_end_month": {"$exists": False}},
        {"$set": {"fiscal_year_end_month": 12, "fiscal_year_end_day": 31}}
    )
    # 2. Backfill perms : accountant → +read+write ; viewer → +read
    for org in db.organizations.find({}):
        rp = org.get("role_permissions") or {}
        changed = False
        acc = set(rp.get("accountant", []))
        if "accounting:read" not in acc or "accounting:write" not in acc:
            acc.update({"accounting:read", "accounting:write"}); changed = True
        vw = set(rp.get("viewer", []))
        if "accounting:read" not in vw:
            vw.add("accounting:read"); changed = True
        if changed:
            rp["accountant"] = sorted(acc); rp["viewer"] = sorted(vw)
            db.organizations.update_one({"id": org["id"]},
                {"$set": {"role_permissions": rp}})
    # 3. Indexes
    db.chart_of_accounts.create_index([("organization_id", 1), ("account_number", 1)], unique=True)
    db.chart_of_accounts.create_index([("organization_id", 1), ("account_type", 1)])
    db.journal_entries.create_index([("organization_id", 1), ("entry_date", 1)])
    db.journal_entries.create_index([("organization_id", 1), ("entry_number", 1)], unique=True)
    db.journal_entries.create_index([("organization_id", 1), ("status", 1)])
    db.journal_entries.create_index([("organization_id", 1), ("source_type", 1), ("source_id", 1)])
    db.ledger_counters.create_index("id", unique=True)
```

**Note perms** : on **n'écrase pas** une matrice où l'owner aurait volontairement retiré `accounting:*` d'un rôle. On n'ajoute que si absent → mais comme le backfill re-tourne à chaque boot, un owner qui retire la perm la reverrait ajoutée. **Décision** : le backfill ne s'exécute que si l'org **n'a jamais eu** le flag `ledger_perms_backfilled = true` (posé après le 1er passage). Idempotence sans ré-écrasement des choix owner.

### 8.3 Seed lazy du plan comptable

`_ensure_chart_seeded(org_id, user_id)` appelé au début de chaque endpoint `/api/ledger/*` :
```python
if db.chart_of_accounts.count_documents({"organization_id": org_id}) == 0:
    db.chart_of_accounts.insert_many(_build_default_accounts(org_id, user_id))
```
Idempotent (ne seed que si zéro compte). Garantit qu'une org accédant au GL pour la 1re fois a son plan prêt.

## 9. Frontend

### 9.1 Navigation

Nouvelle entrée sidebar « **Grand livre** » (icône `BookOpen` lucide-react), gatée sur `hasPermission("accounting:read")` (pattern feature #11, cf. filtre sidebar par permission). Route `/ledger` protégée par `<RouteGuard permission="accounting:read">`.

### 9.2 Pages (onglets dans `LedgerPage`)

Comme `ReportsPage` (feature #4/#5/#10) : une page avec onglets internes.

1. **Plan comptable** — table triée par n° (Numéro, Nom, Type, Solde normal, Actif). Bouton « Nouveau compte » (modal : numéro + nom + type ; sous-type et mapping catégorie optionnels). Édition inline du nom / activation. Suppression gatée (désactivée si `is_system` ou compte utilisé). Boutons d'écriture cachés si `!hasPermission("accounting:write")`.

2. **Journal** — liste des écritures (n°, date, description, débit total, statut badge). Bouton « Nouvelle écriture » ouvre l'éditeur de lignes : tableau dynamique de lignes (compte via dropdown, débit **ou** crédit), avec **compteur d'équilibre live** en pied (Total Dr / Total Cr / Écart) — bouton « Enregistrer » désactivé tant que Dr ≠ Cr. Bouton « Contre-passer » sur les écritures postées (non déjà contre-passées). Filtre par période / compte / statut.
   - **Bannière / note « Clôture annuelle » (§7.2.1)** : un bandeau informatif rappelle que le système ne clôture PAS l'exercice automatiquement, que la clôture doit être passée **à ou après la fin d'exercice (jamais en cours d'exercice)**, et qu'un **oubli déséquilibre le bilan de l'exercice N+1**. Toujours visible dans l'onglet Journal.

3. **Assistant bilan d'ouverture** — wizard : (a) choisir la date d'ouverture ; (b) grille de comptes avec colonnes Débit / Crédit à remplir (issue de la balance de vérification d'ouverture fournie par la comptable) ; (c) bandeau d'équilibre live Dr = Cr ; (d) récap + confirmation. Bloque la soumission tant que déséquilibré. Message d'aide expliquant qu'on saisit la balance de vérification d'ouverture.

4. **Apport du propriétaire** — mini-formulaire guidé (montant, date, compte encaisse par défaut) → affiche en clair « Cela va enregistrer : Débit Encaisse X $ / Crédit Apport du propriétaire X $ ». Abstrait la partie double.

5. **Grand livre** — sélecteur de compte + période → tableau détaillé avec solde progressif (Date, N° écriture, Description, Débit, Crédit, Solde).

6. **Balance de vérification** — sélecteur de date → tableau (Compte, Débit, Crédit) + ligne de total avec pastille verte/rouge « équilibré ». Bouton « Télécharger PDF ».

7. **Bilan** — sélecteur de date → sections Actif / Passif / Capitaux propres (dont ligne « Résultat net de l'exercice »), totaux, pastille équilibre. Bouton « Télécharger PDF ».
   - **Note « Clôture annuelle » (§7.2.1)** : sous les capitaux propres, un rappel indique que « Résultat net de l'exercice » est **dérivé** de l'exercice courant, que **la clôture annuelle (À/APRÈS la fin d'exercice) doit être passée manuellement**, et qu'un oubli **déséquilibrera le bilan de l'exercice suivant** (le résultat de l'exercice ne migre pas en Bénéfices non répartis 3200). Affiché en évidence si `as_of` est postérieur à une fin d'exercice sans écriture de clôture détectée.

### 9.3 Composants réutilisés

`CurrencySelector`/format CAD existant, `RouteGuard` (feature #11), pattern de téléchargement blob authentifié des PDF (comme T2125). Pas de nouvelle lib.

## 10. Phase 2 — auto-posting (design, plan séparé)

Objectif : éliminer la double saisie en générant automatiquement les écritures depuis les événements financiers existants (cf. contexte d'exploration `financial-events`), tout en gardant le journal manuel pour le reste.

### 10.1 Règles de génération

| Événement (source) | Écriture générée |
|---|---|
| Facture passée à `sent` (`PUT /api/invoices/{id}/status`, `server.py:2380`) | Dr **Comptes clients (1100)** total_cad ; Cr **Revenus (4000)** subtotal ; Cr **TPS à payer (2100)** gst_amount ; Cr **TVQ à payer (2110)** pst_amount ; (Cr TVH si hst_amount, compte à créer) |
| Paiement reçu (`POST /api/invoices/{id}/payments`, `server.py:2387`) | Dr **Encaisse (1000)** amount_cad ; Cr **Comptes clients (1100)** amount_cad |
| Dépense créée (`POST /api/expenses`, `server.py:3524`) | Dr **compte 5xxx** mappé via `expense_category_code` amount_cad ; (Dr **TPS à recouvrer (1200)** gst_paid_cad ; Dr **TVQ à recouvrer (1210)** qst_paid_cad) ; Cr **Encaisse (1000)** si payée OU Cr **Comptes fournisseurs (2000)** si non payée |

Le mapping dépense→compte utilise `chart_of_accounts.expense_category_code == expense.category_code` (§4.2), fallback 5900 (Dépenses diverses) si aucun compte mappé.

### 10.2 Idempotence

Chaque facture/paiement/dépense génère **une** écriture liée, identifiée par `(source_type, source_id)` (index §3.2) :
- **Création** → insert une écriture `entry_type="auto"`, `status="posted"`.
- **Modification** du doc source → **contre-passer** l'ancienne écriture auto + en générer une nouvelle (jamais d'édition en place → piste d'audit). Alternative plus simple si l'écriture n'est jamais réconciliée : delete + recreate, à trancher au plan Phase 2.
- **Suppression** du doc source → contre-passation de l'écriture auto (les cascades existantes de la feature #7 `_release_bank_transaction` serviront de modèle).
- **Écritures auto immuables manuellement** : un utilisateur ne peut pas éditer une écriture `entry_type="auto"` via `PUT /entries/{id}` (400 « écriture générée automatiquement »).

### 10.3 Réconciliation avec le P&L existant (feature #5)

Le P&L `_aggregate_pnl` (`server.py:322`) agrège directement `invoices`/`expenses` ; le GL agrège les écritures. Les deux **doivent** concorder en base **exercice** (`accrual`). Différences attendues et documentées :
- **Base caisse vs exercice** : le P&L cash filtre `status=paid` sur `issue_date` ; le GL enregistre le revenu au `sent`. Écart normal.
- **Brouillons** : le GL ignore les écritures `draft` ; le P&L ignore les factures `draft`. Cohérent.
- Un endpoint `GET /api/ledger/reconciliation?start=&end=` (Phase 2) comparera revenus/dépenses GL vs P&L et listera les écarts — outil de contrôle pour la comptable.

## 11. Sécurité

| Menace | Mitigation |
|---|---|
| **Fuite cross-org** (lecture d'écritures d'une autre org) | Tout query filtre `{"organization_id": current_user.organization_id}` — jamais d'accès par `id` seul. `account_id` d'une ligne vérifié appartenir à l'org avant insert. |
| **Écriture déséquilibrée injectée** (bypass frontend) | `_validate_entry_balance` (§5.1) appliqué **backend** sur POST/PUT/post/opening-balance/owner-contribution. Le frontend qui bloque le bouton n'est qu'une commodité UX. |
| **Altération d'une écriture postée** (destruction de piste d'audit ARC) | `status="posted"` → PUT/DELETE renvoient 400. Le chemin de contre-passation n'altère pas l'origine : il ajoute une écriture miroir (append-only) et pose seulement le champ d'audit `reversed_by_entry_id`. Conservation 6 ans implicite (pas de purge). |
| **Suppression d'un compte utilisé** → lignes orphelines | DELETE bloqué si le compte a ≥ 1 ligne (400) ou `is_system` (400) → inactivation seulement. |
| **Élévation via role_permissions** injectant `accounting:write` chez un viewer par matrice | `accounting:*` sont dans `PERMISSIONS_EDITABLE`, donc légitimement éditables par l'owner ; `_resolve_permissions` filtre déjà aux codes connus. Pas de code owner-only exposé. |
| **Numéros d'écriture dupliqués** (course sur le compteur) | `find_one_and_update` atomique `$inc` sur `ledger_counters` (§3.3) + index unique `(org, entry_number)`. |
| **Injection HTML/CSV dans les PDF** (noms de comptes, description) | `html.escape` sur toute string user-supplied avant ReportLab (pattern `_render_t2125_pdf`). |
| **Manipulation de l'écriture d'ouverture** pour fausser le bilan | `entry_type="opening"` protégé : un seul OB par org (409 sur POST si existe), remplacement via PUT dédié re-validé. Non supprimable via `DELETE /entries`. |
| **Contre-passation en boucle / double** | `reverse` refuse si source non `posted` (400) ou déjà contre-passée — `reversed_by_entry_id` déjà posé → 400. Ainsi une même écriture ne peut être contre-passée deux fois, et le miroir (qui n'a pas de `reversed_by_entry_id`) reste techniquement contre-passable une seule fois s'il le fallait. |
| **Modification des champs fiscaux pour manipuler le bilan** | `fiscal_year_end_month/day` sous `settings:write` (déjà tracé `created_by_user_id`). Changer l'exercice ne modifie pas les écritures, seulement le regroupement d'affichage. |
| **Cache PDF exposant un état financier** (proxy/CDN) | Headers `no-store, no-cache, must-revalidate` (pattern `server.py:5548`). |

## 12. Tests

### 12.1 Unitaires — `backend/tests/test_general_ledger.py`

- `_validate_entry_balance` : équilibrée OK ; Dr ≠ Cr → 400 ; < 2 lignes → 400 ; ligne avec Dr **et** Cr → 400 ; ligne négative → 400 ; tolérance 0,005 $ respectée.
- `_account_balance` : compte débiteur (Dr − Cr) ; compte créditeur (Cr − Dr) ; filtre `as_of` ; ignore les `draft` ; solde négatif retourné tel quel.
- `_build_default_accounts` : 29 comptes ; plages cohérentes ; `normal_balance` correct par type ; `expense_category_code` mappé sur les 17 catégories.
- `normal_balance` dérivé : plage 1xxx→debit, 2/3/4xxx→credit, 5xxx→debit.
- Balance de vérification : total_debit == total_credit sur un jeu d'écritures équilibrées ; comptes à solde nul exclus ; solde négatif basculé dans la colonne opposée.
- Bilan : Actif = Passif + CP ; `net_income_current_year` = revenus − dépenses sur l'exercice ; `_current_fiscal_year` avec fin déc. **et** fin non-déc. (ex. 31 mars).
- Contre-passation : lignes inversées ; totaux préservés ; `reversed_by_entry_id` posé sur l'origine ; **l'origine reste `posted`** (jamais `reversed`) ; le miroir est `posted` ; **solde net des deux = 0 sur chaque compte** (invariant §5.2) ; balance de vérification toujours équilibrée après reversal.
- Compteur atomique : `JE-0001` → `JE-0002` séquentiel.

### 12.2 Intégration — `backend/tests/test_general_ledger_integration.py`

- **Seed lazy** : 1er GET `/api/ledger/accounts` d'une org neuve → 29 comptes ; 2e appel → pas de doublon.
- **CRUD comptes** : POST hors plage → 400 ; POST doublon → 409 ; DELETE compte système → 400 ; DELETE compte utilisé → 400 ; PUT account_number → 400.
- **Journal** : POST équilibrée `status=posted` → 201 + entry_number `JE-0001` ; POST déséquilibrée → 400 ; PUT sur postée → 400 ; DELETE postée → 400 ; POST draft puis `/post` → posted.
- **Assistant ouverture** : POST équilibré → 201 `OB-0001` + `ledger_start_date` posée ; POST déséquilibré → 400 ; 2e POST → 409 ; PUT remplace.
- **Apport** : POST owner-contribution 5000 $ → écriture Dr 1000 / Cr 3100 de 5000 ; montant ≤ 0 → 400.
- **Grand livre** : running_balance progressif correct ; opening_balance = solde avant `start`.
- **Balance de vérification** : `balanced=true` ; total Dr == total Cr après une série d'écritures.
- **Bilan** : `balanced=true` (Actif = Passif + CP) après ouverture + apport + une facture manuelle ; résultat net calculé sur l'exercice.
- **RBAC** : viewer GET `/api/ledger/entries` → 200 ; viewer POST → 403 « accounting:write » ; org sans la perm → 403.
- **Isolation cross-org** : org A crée une écriture, org B GET `/api/ledger/entries/{id_A}` → 404 ; balance de B n'inclut pas les comptes de A.
- **PDF** : GET `/trial-balance/pdf` et `/balance-sheet/pdf` → 200 `application/pdf`, headers no-cache.
- **Migration** : backfill champs fiscaux (défaut 12/31) ; backfill perms accountant/viewer ; re-run = no-op (flag `ledger_perms_backfilled`).

### 12.3 E2E manuel

- Owner ouvre « Grand livre », voit le plan par défaut (29 comptes).
- Assistant ouverture : saisir une balance d'ouverture d'un vrai exercice ProFireManager, valider l'équilibre, générer l'OB.
- Saisir un apport de 10 000 $ → vérifier l'écriture Dr Encaisse / Cr Apport.
- Saisir une écriture manuelle d'amortissement (Dr Amortissement 5xxx / Cr Amortissement cumulé — comptes ajoutés via CRUD).
- Consulter le grand livre du compte Encaisse → solde progressif.
- Générer la balance de vérification à date → équilibrée.
- Générer le bilan → Actif = Passif + CP, télécharger le PDF FR-CA.
- Comptable invité (feature #11) : accède au GL en read+write ; lecteur : read seul, boutons masqués.

**Cible : ~60 tests** (~25 unitaires + ~30 intégration + ~5 E2E manuels).

## 13. Limites v1 / Hors scope

- **Auto-posting** (Phase 2) — non implémenté au MVP ; design cadré §10, plan séparé.
- **Écriture de clôture annuelle automatique** (closing entry vidant revenus/dépenses vers BNR) — v1 : résultat net **dérivé** dans le bilan ; la comptable passe la clôture manuellement à/après la fin d'exercice (documenté dans l'assistant + avertissement UI §9). **⚠️ Règle stricte : la clôture se fait À ou APRÈS la fin d'exercice, jamais en cours d'exercice — sinon les rapports intermédiaires sont faussés. Et si la clôture est OUBLIÉE, le bilan de l'exercice N+1 sera déséquilibré (le résultat de N ne migre pas en BNR 3200). Voir §7.2.1.**
- **États consolidés** (multi-entités) — hors scope, une org = une entité comptable.
- **GL multi-devise** (comptes tenus en USD, écart/gain de change) — v1 CAD only ; les montants entrent déjà convertis via `exchange_rate_to_cad`. Les factures/dépenses en devise étrangère apporteront leur `total_cad`/`amount_cad` en Phase 2. Écart de change non modélisé.
- **État des flux de trésorerie** (cash flow statement) — hors scope v1 (le bilan + balance suffisent au T2 de base ; l'état des résultats est déjà couvert par le P&L feature #5).
- **Grands livres auxiliaires** (subsidiary ledgers clients/fournisseurs détaillés) — les Comptes clients / fournisseurs sont des comptes de contrôle globaux ; le détail par client vit dans `invoices` (feature #6 solde par facture).
- **DPA / amortissement automatique** (CCA) — saisie manuelle uniquement (comme la note T2125 feature #10 ligne 9936).
- **Multi-exercices / verrouillage de période** (period lock empêchant d'écrire dans un exercice clos) — v1 : pas de verrou ; la contre-passation reste toujours possible.
- **Rapprochement bancaire ↔ GL** — la feature #7 (bank reconciliation) reste indépendante ; le lien banque↔écriture arrive avec l'auto-posting Phase 2.
- **Export GIFI** pour le T2 — le bilan produit les chiffres, mais le mapping vers les codes GIFI et le formulaire T2 est hors scope v1 (piste future, comme le T2125 feature #10 pour les autonomes).
- **Numérotation TVH par défaut** — le seed reflète le profil QC (TPS/TVQ) ; une société TVH ajoute ses comptes via CRUD.

## 14. Rollback plan

**Scénarios et procédures :**

1. **Migration `migrate_general_ledger_v1` corrompt `company_settings` ou `role_permissions`** :
   - Détection : erreurs 500 sur `/api/settings/company` ou permissions incohérentes.
   - Action : rollback Render à N-1 (« Redeploy previous »).
   - Recovery : la migration n'ajoute que des champs (`setdefault`-like) et n'écrase pas les valeurs existantes (flag `ledger_perms_backfilled`). Aucune donnée métier existante touchée.

2. **Écriture forçant un déséquilibre passe malgré la validation** :
   - Détection : balance de vérification `balanced=false`.
   - L'UI/PDF l'affiche en rouge avec le montant d'écart → diagnostic. On identifie l'écriture fautive, on la contre-passe. Aucune perte, la piste d'audit reste.

3. **Le module GL est totalement problématique** :
   - Feature isolée : masquer l'entrée sidebar (retirer `accounting:read` des rôles, ou hotfix frontend qui cache l'onglet).
   - Backend : les endpoints `/api/ledger/*` peuvent être laissés en place (inertes sans accès). Aucune collection existante (`invoices`, `expenses`, `company_settings` hors nouveaux champs) n'est modifiée en Phase 1.
   - Les collections `chart_of_accounts`, `journal_entries`, `ledger_counters` sont **additives** — laissées en place sans impact sur le reste de l'app.

4. **Rollback complet de la feature** :
   - Redéployer la version pré-feature #12 sur Render + Vercel.
   - Les 3 nouvelles collections + les champs `fiscal_year_end_*` sur `company_settings` sont ignorés par l'ancien code.
   - `role_permissions` contient `accounting:*` en trop → ignorés (codes inconnus filtrés par `_resolve_permissions`).

**Point de non-retour** : aucun en Phase 1. Le module est purement additif ; il ne migre ni ne mute aucune donnée métier existante (contrairement à la feature #11 qui rebasculait `user_id`→`organization_id`). Phase 2 (auto-posting) introduira un couplage aux workflows factures/dépenses et aura son propre plan de rollback.

## 15. Impact estimé

- **Backend** : ~15 nouveaux endpoints `/api/ledger/*` (~600 lignes), constantes plan par défaut + helpers partie double (~200 lignes), 2 PDF ReportLab (~250 lignes), 1 migration (~60 lignes). Total : **~1100 lignes ajoutées**, ~10 lignes modifiées (`PERMISSIONS_EDITABLE`, `DEFAULT_ROLE_PERMISSIONS`, `PUT /api/settings/company` fiscal, registration migration).
- **Frontend** : 1 nouvelle `LedgerPage` à 7 onglets (~900 lignes), entrée sidebar + route guard (~20 lignes). Total : **~920 lignes ajoutées**.
- **Tests** : ~60 tests, **~1000 lignes**.
- **Nouvelles collections** : `chart_of_accounts`, `journal_entries`, `ledger_counters`.
- **Nouveaux champs** : `company_settings.fiscal_year_end_month/day`, `ledger_start_date`.
- **Env vars nouvelles** : aucune.
- **Coût opérationnel** : négligeable (0 appel externe ; tout en Mongo + ReportLab déjà présents).
