# Dépenses télécom à usage mixte (% affaires) — Design

**Date :** 2026-07-05
**Feature :** #14 — Portion affaires des dépenses de télécommunications (cellulaire, internet)
**Statut :** À valider (surtout le volet grand livre, avec la comptable)

## Objectif

Permettre de saisir une facture de **cellulaire** ou d'**internet** à son montant total (celui
qui matche le relevé bancaire) et n'en déduire que la **portion affaires**, selon un pourcentage
défini **dans les Paramètres de l'entreprise** (comme le % bureau à domicile). La portion affaires
alimente les rapports et, en option, l'écriture du grand livre.

## Contexte utilisateur

Société par actions (ProFireManager Inc). Actuellement les factures internet + cellulaire sont au
**nom personnel** ; le cellulaire passera bientôt au **nom de l'entreprise**. L'interrupteur ON/OFF
par type couvre les deux situations (voir §5).

## 1. Catégories de dépenses (2 nouvelles)

Ajout à `EXPENSE_CATEGORIES` (server.py ~ligne 158) :

| code                    | label_fr                       | arc_line | deductible_percentage | group   |
|-------------------------|--------------------------------|----------|-----------------------|---------|
| `telecom_cell`          | Télécom — cellulaire           | 9220     | 100                   | office  |
| `telecom_internet`      | Télécom — internet             | 9220     | 100                   | office  |

`deductible_percentage` reste 100 au niveau catégorie (le repas 50 % est différent : c'est une
règle fiscale fixe). Le % affaires télécom est un **réglage par entreprise**, pas une constante.

## 2. Réglages entreprise (`company_settings`)

Deux blocs (cellulaire, internet), chacun :

```
telecom_cell_mixed_use      : bool  (interrupteur — défaut false)
telecom_cell_business_pct   : int 0–100 (défaut 100 ; utilisé seulement si mixed_use=true)
telecom_internet_mixed_use    : bool  (défaut false)
telecom_internet_business_pct : int 0–100 (défaut 100)
```

Validation au `PUT /api/settings/company` : pct clampé 0–100, entier. Visible **quelle que soit
l'entité** (contrairement au % bureau qui est masqué pour les sociétés par actions).

## 3. Snapshot sur la dépense

Au `POST`/`PUT` d'une dépense dont la catégorie ∈ {telecom_cell, telecom_internet}, on fige un
snapshot (comme les autres snapshots de catégorie) :

```
business_use_pct        : int      (100 si mixed_use=false pour ce type, sinon le pct réglé)
business_use_amount_cad : float    (round(total_amount * pct/100, 2))
personal_use_amount_cad : float    (round(total_amount - business_use_amount_cad, 2))
```

Le **montant total** de la dépense reste inchangé (= la facture = la transaction bancaire).
Le snapshot est recalculé au PUT si le montant ou la catégorie change (jamais rétroactif sur les
autres). Une dépense non-télécom n'a pas ces champs (pct implicite 100).

## 4. Rapports (réduction à la portion affaires)

- **État des résultats (P&L, `_aggregate_pnl`)** : pour une dépense télécom, on additionne
  `business_use_amount_cad` (et non `total_amount`). Une ligne informative « portion personnelle
  exclue : X $ » peut apparaître.
- **T2125** (travailleurs autonomes) : idem, la portion affaires alimente la ligne 9220.
  Pour une société par actions le T2125 est masqué — sans effet, mais cohérent.
- **TPS/TVQ** : la portion de taxe récupérable suit aussi le %. *(À confirmer : par défaut on
  applique le même % aux taxes payées ; la comptable valide.)*

## 5. L'interrupteur ON/OFF ↔ les deux scénarios

| Situation | Réglage | Ce que tu saisis | Grand livre |
|-----------|---------|------------------|-------------|
| **Facture perso, remboursement** (actuel) | mixed_use **OFF** (100 %) | le **montant remboursé** par la société (= la portion affaires) | Dr Télécom (total) / Cr Encaisse — 100 % affaires, pas de portion perso dans les livres de la société |
| **Facture au nom de l'entreprise, 100 % affaires** | mixed_use **OFF** | la facture complète | Dr Télécom (total) / Cr Encaisse |
| **Facture au nom de l'entreprise, usage mixte** | mixed_use **ON** (ex. 85 %) | la facture complète | Dr Télécom (portion affaires) / **Dr Dû par l'actionnaire (portion perso)** / Cr Encaisse (total) |

L'interrupteur = « cette dépense a-t-elle une portion personnelle à sortir ? ». OFF pour les deux
premiers cas, ON pour le troisième.

## 6. Grand livre (auto-posting) — À VALIDER AVEC LA COMPTABLE

Aujourd'hui `_autopost_expense` (server.py ~2423) fait `Dr <compte de charge> / Cr Encaisse` (ou
Comptes fournisseurs) pour le montant total.

Pour une dépense télécom **mixed_use ON** :

```
Dr  5xxx  Charge télécom          business_use_amount_cad
Dr  <compte actionnaire>          personal_use_amount_cad
Cr  1000  Encaisse                total_amount
```

**Décision à trancher (comptable) :** le plan comptable par défaut n'a **aucun compte actionnaire**.
Proposition MVP : ajouter un compte **`1300 — Dû par un actionnaire`** (actif courant) — car la
société a payé une dépense personnelle pour l'actionnaire, qui lui doit donc ce montant. Certains
comptables préfèrent l'imputer en réduction d'un **prêt de l'actionnaire (passif, ex. 2200 « Dû à
un actionnaire »)** ou en **avantage imposable**. Le compte cible sera **configurable** (réglage
`telecom_personal_offset_account`, défaut `1300`) pour que la comptable ajuste sans code.

Contraintes GL habituelles respectées : `_validate_entry_balance` (Dr=Cr), auto-post gated sur
`autopost_enabled`, `_safe_autopost` (n'échoue jamais l'opération métier), idempotence source_type/id.

Pour **mixed_use OFF** : comportement inchangé (Dr charge total / Cr Encaisse).

## 7. Frontend

- **SettingsPage** : nouvelle section « Dépenses télécom (usage mixte) » — 2 lignes (Cellulaire,
  Internet), chacune un interrupteur + un champ % (grisé si OFF). Visible pour les sociétés par
  actions.
- **ExpensesPage** : quand la catégorie est télécom et mixed_use ON, afficher sous le montant :
  « Portion affaires : 68,00 $ (85 %) · perso : 12,00 $ ». Lecture seule (piloté par les réglages).

## 8. Tests

- Helpers : calcul portion affaires/perso (arrondis, 100 %, 0 %, montants limites).
- Snapshot au POST/PUT (recalcul si montant/catégorie change).
- P&L : une dépense télécom mixte compte pour sa portion affaires.
- GL : écriture équilibrée à 3 lignes quand mixed_use ON + compte offset ; 2 lignes quand OFF.
- Réglages : validation pct 0–100, interrupteurs.
- Migration : seed du compte 1300 idempotent.

## 9. Questions ouvertes (comptable)

1. Compte de la portion perso : `1300 Dû par un actionnaire` (actif) vs réduction d'un prêt
   d'actionnaire (passif) vs avantage imposable. → configurable, défaut 1300.
2. TPS/TVQ récupérable : appliquer le % à la taxe payée aussi (recommandé) ?
3. Ligne ARC : 9220 (services publics) convient-elle pour cellulaire/internet, ou préférer 8810 ?

## 10. Découpage (plan d'implémentation)

Phase A (sûre, sans risque comptable) : catégories, réglages, snapshot, P&L, T2125, frontend.
Phase B (grand livre) : compte 1300, écriture à 3 lignes, réglage compte offset — après validation
comptable des questions ouvertes.
