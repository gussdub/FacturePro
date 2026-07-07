# Codes fiscaux adaptés au type d'entité (feature #7.6) — spec

**Statut** : à approuver
**Date** : 2026-07-06
**Auteur** : gussdub + Claude
**Feature #** : 7.6

## Contexte

Aujourd'hui chaque catégorie de dépense porte un unique champ `arc_line` (ex. 8740 pour
« Abonnements et licences ») affiché dans le picker à côté du libellé. Deux problèmes :

1. **Codes erronés** — audit par recherche multi-sources CRA (RC4088, T2125 fr,
   T2SCH125, canada.ca) : `bank_charges` 8620, `subscriptions` 8740, `subcontracts` 9367
   n'existent pas dans le référentiel officiel ARC. `advertising` porte 8520 mais le
   T2125 utilise 8521 (le 8520 est le code GIFI de la société — c'est deux référentiels
   différents).
2. **Un seul référentiel** — l'utilisateur est soit un travailleur autonome (déclare
   avec le **T2125**), soit une société par actions (déclare avec la **T2** qui utilise
   les codes **GIFI**, repris aussi par le **CO-17** québécois). Ces deux référentiels
   se ressemblent mais divergent sur certains codes. FacturePro connaît déjà
   `entity_type` (`sole_proprietor` / `corporation`) mais utilise le même arc_line pour
   les deux, ce qui affiche un code potentiellement inapproprié pour une société.

Résultat visible : la même dépense « Abonnements et licences » affiche « 8740 » (mauvais
code, ni T2125 ni GIFI) alors qu'elle apparaît aussi au compte GL 5040 (correct). Le
picker crée de la confusion et — surtout — les rapports fiscaux ne reflètent pas
fidèlement le référentiel du type d'entité.

## Objectifs

- Corriger les codes ARC erronés (bank, subscriptions, subcontracts, advertising).
- Ajouter le référentiel **GIFI** en parallèle du référentiel **T2125**, avec choix
  automatique selon `entity_type`.
- Afficher le code **étiqueté** dans le picker (« T2125 ligne 8760 » / « GIFI 8523 »)
  pour lever la confusion avec le compte GL (`5040`).
- Livrer un nouveau rapport **Sommaire GIFI** pour les sociétés (le T2125 est masqué
  pour une société aujourd'hui, elle n'a donc aucun rapport de lignes fiscales).
- Ne pas casser les dépenses existantes : migration idempotente qui ré-annote les
  snapshots historiques avec les deux codes + corrige les codes erronés.

Hors périmètre : TP-80 québécois pour le travailleur autonome (le CO-17 des sociétés
est déjà couvert car il utilise le GIFI). À réaliser plus tard si besoin.

## Table de correspondance (verrouillée par recherche adversariale, sources ARC)

Chaque catégorie porte deux codes distincts. Pour les catégories sans ligne T2125
dédiée (bank, telecom, SaaS), on retient la **convention pratique** (celle utilisée par
Wave/QuickBooks) plutôt qu'un fallback systématique vers 9270.

| # | code | T2125 line | T2125 label_fr | GIFI code | GIFI label_en | Confiance | Ambiguïté |
|---|---|---|---|---|---|---|---|
| 1 | office_expenses | 8810 | Frais de bureau | 8810 | Office expenses | HIGH | — |
| 2 | office_supplies | 8811 | Papeterie et fournitures de bureau | 8811 | Office stationery and supplies | HIGH | — |
| 3 | professional_fees | 8860 | Honoraires professionnels | 8860 | Professional fees | HIGH | GIFI peut se raffiner en 8861/8862 (juridique/comptable) — non retenu v1 |
| 4 | bank_charges | 8710 | Intérêts et frais bancaires | 8715 | Bank charges | HIGH | T2125 combiné avec intérêts (pas de ligne dédiée) |
| 5 | subscriptions | 8760 | Taxes d'affaires, droits d'adhésion et licences | 8810 | Office expenses | MEDIUM | Aucun code dédié SaaS — convention pratique |
| 6 | telecom_cell | 9220 | Services publics | 9225 | Telephone and telecommunications | MEDIUM | T2125 pas de ligne dédiée — convention |
| 7 | telecom_internet | 9220 | Services publics | 9152 | Internet | MEDIUM | T2125 pas de ligne dédiée — convention |
| 8 | advertising | 8521 | Publicité | 8520 | Advertising and promotion | HIGH | T2125 ≠ GIFI (1 chiffre d'écart) |
| 9 | meals_entertainment | 8523 | Repas et frais de représentation | 8523 | Meals and entertainment | HIGH | 50 % appliqué au niveau du montant (feature #3), pas au code |
| 10 | rent | 8910 | Loyer | 8910 | Rental | HIGH | — |
| 11 | utilities | 9220 | Services publics | 9220 | Utilities | HIGH | — |
| 12 | insurance | 8690 | Assurances | 8690 | Insurance | HIGH | — |
| 13 | repairs_maintenance | 8960 | Entretien et réparations | 8960 | Repairs and maintenance | HIGH | — |
| 14 | travel | 9200 | Frais de déplacement | 9200 | Travel expenses | HIGH | — |
| 15 | vehicle_expenses | 9281 | Frais de véhicule à moteur | 9281 | Vehicle expenses | HIGH | — |
| 16 | delivery | 9275 | Livraison, transport et messagerie | 9275 | Delivery, freight and express | HIGH | — |
| 17 | salaries | 9060 | Salaires, traitements et avantages | 9060 | Salaries and wages | HIGH | — |
| 18 | subcontracts | 9060 | Salaires, traitements et avantages | 9110 | Sub-contracts | MEDIUM | T2125 pas de ligne dédiée (services hors production) |
| 19 | management_fees | 8871 | Frais de gestion et d'administration | 8871 | Management and administration fees | HIGH | — |
| 20 | other | 9270 | Autres dépenses | 9270 | Other expenses | HIGH | — |

**Sources ARC** (verrouillées, revue adversariale) :
- RC4088 (GIFI complet) : <https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/rc4088.html>
- T2 Schedule 125 : <https://www.cchwebsites.com/content/pdf/tax_forms/ca/en/t2sch125_en.pdf>
- T2125 (fr) pages canada.ca par ligne (8521, 8523, 8690, 8710, 8760, 8810, 8811, 8860, 8871, 8910, 8960, 9060, 9200, 9220, 9270, 9275, 9281).

## Architecture

### Backend

**Modèle de données — `EXPENSE_CATEGORIES` (server.py ~L156)**

Chaque entrée passe de :
```py
{"code": "subscriptions", "label_fr": "Abonnements et licences", "arc_line": "8740", ...}
```

à :
```py
{"code": "subscriptions", "label_fr": "Abonnements et licences",
 "t2125_line": "8760", "t2125_label_fr": "Taxes d'affaires, droits d'adhésion et licences",
 "gifi_code":  "8810", "gifi_label_en": "Office expenses",
 "deductible_percentage": 100, "group": "office"}
```

`arc_line` disparaît du modèle canonique. Un shim (§ Rétrocompat) le calcule à la
volée pour les lecteurs legacy le temps de la migration.

**Snapshot figé sur la dépense — `_build_expense_category_snapshot`**

Le snapshot inclut désormais **les deux codes** (indépendamment de `entity_type`) :

```py
snapshot = {
    "category": label,
    "category_code": code,
    "category_custom_label": "",
    "category_t2125_line": t2125_line,     # nouveau
    "category_t2125_label_fr": t2125_label, # nouveau
    "category_gifi_code": gifi_code,        # nouveau
    "category_gifi_label_en": gifi_label,   # nouveau
    "category_arc_line": t2125_line,        # LEGACY = t2125_line, kept temporarily
    "deductible_percentage": ...,
    "deductible_amount": ...,
}
```

**Pourquoi les deux codes** : si l'utilisateur passe de `sole_proprietor` à
`corporation` (ou l'inverse), ses dépenses historiques portent déjà le bon code pour
le nouveau régime — pas de recalcul, pas de migration à re-lancer.

**Endpoint `GET /api/expense-categories`**

Retourne désormais `t2125_line` + `gifi_code` sur chaque catégorie. La page paramètres
frontend continue de fonctionner (elle lit `code` + `label_fr` uniquement).

**Rapport GIFI — nouveau endpoint `GET /api/reports/gifi`**

Miroir du rapport T2125 existant (`_build_t2125_report`) mais agrège par
`category_gifi_code`. Réutilise le maximum de code (partager `_t2125_flatten_pnl_expenses`
via renommage `_flatten_pnl_expenses`, et écrire `_gifi_group_by_code` en parallèle de
`_t2125_group_by_arc_line`).

Format de retour identique au T2125 : `{lines: [{code, label, amount}], total}`.

Endpoints associés :
- `GET /api/reports/gifi` — JSON
- `GET /api/reports/gifi/csv` — export CSV
- `GET /api/reports/gifi/pdf` — PDF (réutilise `_render_t2125_pdf` renommé
  `_render_tax_summary_pdf(kind="gifi"|"t2125")`)

**Migration idempotente au startup — `migrate_expense_tax_codes_v1`**

Sélectionne toutes les dépenses dont `category_code` est présent MAIS `category_gifi_code`
absent (ou `category_arc_line ∈ {8620, 8740, 9367, 8520}` — codes erronés à corriger).
Pour chacune : recharge la catégorie via `_find_category`, ré-écrit `category_t2125_line`,
`category_t2125_label_fr`, `category_gifi_code`, `category_gifi_label_en`,
`category_arc_line` (aligné sur `t2125_line`). **Aucun montant ni % déductible touché** —
c'est purement une ré-annotation des snapshots historiques.

Idempotente par construction : au 2e passage, la clause `category_gifi_code absent` est
fausse, la migration ne fait rien.

**Rétrocompat `arc_line`**

Deux consommateurs actuels lisent `category_arc_line` : le rapport T2125
(`_t2125_group_by_arc_line`) et l'export CSV des dépenses. On garde `category_arc_line`
snapshoté sur la dépense (= `category_t2125_line`) — aucun changement de comportement
pour T2125 tant qu'aucun code n'est modifié. Une fois la migration passée, la valeur
sera corrigée pour bank/subscriptions/subcontracts/advertising ; les rapports T2125
existants deviennent automatiquement plus exacts.

### Frontend

**Picker de catégorie (`ExpensesPage.js`, `BankCreateExpenseModal.js`, etc.)**

L'API `GET /api/expense-categories` retourne les deux codes ; le frontend lit
`entity_type` depuis `GET /api/settings/company` et affiche :

- `sole_proprietor` → « Abonnements et licences — T2125 ligne 8760 »
- `corporation` → « Abonnements et licences — GIFI 8810 »

Icône ⓘ à côté du code pour les 3 catégories marquées MEDIUM (bank, telecom, SaaS)
avec tooltip : « Aucune ligne T2125 dédiée — convention utilisée : ligne 8710 »
(ou équivalent).

**Page Rapports (`ReportsPage.js`)**

L'onglet « T2125 » reste affiché si `entity_type == "sole_proprietor"` (déjà en place
via `T2125ReportSection.js:64`).

Nouveau onglet « **Sommaire GIFI** » (composant `GifiReportSection.js`), affiché si
`entity_type == "corporation"`. Réutilise le layout de `T2125ReportSection` (période,
tableau lignes, total, boutons PDF/CSV). Aucune configuration spécifique (pas
d'ajustements home/vehicle comme sur T2125 — le GIFI est agrégé brut).

### Cas ambigus — convention retenue

Décision utilisateur : **convention pratique** (Wave/QuickBooks) plutôt que fallback
systématique vers 9270. Trois catégories sont concernées :

1. **bank_charges** — T2125 8710 (combiné avec intérêts), GIFI 8715 (séparé).
2. **telecom_cell / telecom_internet** — T2125 9220 (Services publics), GIFI 9225 /
   9152 (dédiés).
3. **subscriptions (SaaS)** — T2125 8760 (Taxes/cotisations), GIFI 8810 (Office).

Tooltip visible dans le picker + rapports pour ces trois catégories : « Aucune ligne
T2125 dédiée pour ce type de dépense — convention. »

## Testing

Nouveaux tests dans `backend/tests/test_expense_tax_codes.py` :

1. **Snapshot** — créer une dépense pour chacun des 20 codes, vérifier
   `category_t2125_line` + `category_gifi_code` corrects.
2. **Erreurs corrigées** — insérer une dépense legacy avec `category_arc_line = "8740"`,
   lancer la migration, vérifier `category_t2125_line = "8760"` et
   `category_gifi_code = "8810"`.
3. **Idempotence migration** — lancer la migration deux fois, vérifier qu'aucun
   `updated_count` au 2e passage.
4. **Rapport GIFI** — 3 dépenses (repas, loyer, autre), vérifier l'agrégation par
   `gifi_code` (8523 / 8910 / 9270).
5. **Rétrocompat T2125** — les tests existants `test_t2125_report.py` doivent passer
   sans modification (car `category_arc_line = category_t2125_line`).
6. **Séparation T2125/GIFI** — vérifier que `advertising` snapshote `t2125_line=8521`
   ET `gifi_code=8520` (deux valeurs distinctes).

Aucune revue adversariale supplémentaire prévue — la table de correspondance a déjà
été verrouillée par 2 rondes de recherche multi-sources CRA + revue adversariale
(15 claims 3/3, sources canada.ca directes).

## Rollout

Un seul commit backend + frontend, push prod normal. La migration s'exécute au
redémarrage de Render (idempotente, ~secondes sur la base actuelle). Aucun risque
data : montants, dates, catégories inchangés — seuls les snapshots de code fiscal
sont ré-annotés.

## Files

**Backend**
- `backend/server.py` — `EXPENSE_CATEGORIES` (modif in-place),
  `_build_expense_category_snapshot` (2 nouveaux champs),
  `_flatten_pnl_expenses` + `_gifi_group_by_code` (nouveau),
  `_render_tax_summary_pdf(kind)` (renommage + généralisation),
  3 endpoints `/api/reports/gifi(/csv|/pdf)`,
  `migrate_expense_tax_codes_v1()` (nouveau, appelé au startup).
- `backend/tests/test_expense_tax_codes.py` — nouveau fichier de tests.

**Frontend**
- `frontend/src/pages/ExpensesPage.js` — picker : label enrichi selon `entity_type`.
- `frontend/src/components/BankCreateExpenseModal.js` — idem.
- `frontend/src/pages/ReportsPage.js` — onglet GIFI conditionnel.
- `frontend/src/components/GifiReportSection.js` — nouveau composant.

**Docs**
- `CLAUDE.md` — entrée changelog feature #7.6.

## Rejected options

- **Tout renvoyer vers 9270 (Autres) pour les cas ambigus** — plus conservateur mais
  rend le T2125 moins détaillé. Wave/QuickBooks utilisent la convention pratique.
- **Réglage par catégorie dans les paramètres** — trop de configuration pour un
  cas marginal (3 catégories sur 20).
- **Ne stocker QUE le code du régime actuel** — casserait les dépenses si l'utilisateur
  change de type d'entité (autonome → société par actions). Snapshoter les deux est
  gratuit et rétrocompatible.
