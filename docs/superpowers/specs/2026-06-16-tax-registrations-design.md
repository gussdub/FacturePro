# Tax Registrations — Numéros officiels sur PDF

**Date** : 2026-06-16
**Statut** : Brouillon, en attente de revue utilisateur
**Feature originale** : #2 dans la roadmap comptable (sortie du backlog QuickBooks-comparison)

## Contexte et motivation

FacturePro affiche actuellement seulement deux numéros (TPS, TVQ) dans l'entête du PDF, et seulement côté entreprise. Les manques :

- **TVH (HST)** côté entreprise jamais affiché, même si renseigné dans Settings.
- **NEQ** (Numéro Entreprise Québec) non géré du tout — obligatoire pour les corporations québécoises.
- **BN** (Business Number fédéral) non géré comme champ distinct.
- **Côté client** : aucun numéro stocké ni affiché, alors qu'en B2B certains clients exigent que leur propre TPS/TVQ apparaisse sur la facture.
- **Pas de validation de format** à la saisie : faute de frappe possible, rejet potentiel en fin d'année.
- **Pas de snapshot** sur les factures : si l'entreprise change son BN dans 6 mois, les anciennes factures affichent rétroactivement le nouveau, ce qui casse la conformité audit.

L'objectif est d'atteindre la **conformité ARC complète** côté entreprise et côté client, sur les factures et les devis, tout en gardant l'UX simple pour les utilisateurs B2C qui n'utiliseront pas ces champs.

## Scope

**Inclus** :
- Ajout/renommage de champs dans `company_settings` et `clients` (5 champs côté entreprise, 5 côté client).
- Migration douce `pst_number` → `qst_number` dans `company_settings`.
- Snapshot des 10 numéros (entreprise + client) au moment de la création d'une facture ou d'un devis.
- Validation de format souple côté backend et côté frontend (avertissement, jamais blocant).
- Modification du PDF : entête épuré, boîte "Facturer à" enrichie, encadré "Numéros d'enregistrement" en bas de page.
- Labels en français : TPS, TVQ, TVH.

**Exclus** :
- Compléter les provinces fiscales manquantes (BC, AB, SK, MB, Maritimes) — sera la feature #1 séparée plus tard.
- Affichage des numéros à côté des montants individuels de taxes dans le tableau totaux (option C choisie : encadré séparé seulement).
- Renommage de `pst_amount` en `qst_amount` dans les documents `invoices` et `quotes` (cosmétique uniquement, change rien à la conformité).
- Validation arithmétique (check digit ARC) — uniquement validation de format (longueur + caractères).

## Décisions de design

| Question | Choix | Raison |
|---|---|---|
| Scope global | C — Conformité ARC entreprise + client B2B | Maximum, demandé par l'utilisateur ("corrige tout") |
| Numéros entreprise | 5 (BN, TPS, TVQ, TVH, NEQ) | Couvre tous les cas Canada + corporations QC |
| Numéros client | 5 (mêmes que entreprise) | Symétrie complète |
| Layout entreprise sur PDF | Entête épuré + encadré bas | Plus propre, pas de répétition dans tableau totaux |
| Layout client sur PDF | Dans boîte "Facturer à", champs renseignés seulement | Cohérent, pas surchargé si pas renseigné |
| Validation à la saisie | Souple avec aide visuelle | Évite faute de frappe sans bloquer cas non standards |
| Renommer pst_number → qst_number | Oui, dans `company_settings` uniquement | Cohérence nominale |

## Data model

### `company_settings` (collection existante, un doc par user)

Renommer un champ et en ajouter deux :

| Champ | Type | Format | Status |
|---|---|---|---|
| `bn_number` | str | `^\d{9}$` | **Nouveau** |
| `gst_number` | str | `^\d{9}RT\d{4}$` | Inchangé |
| `qst_number` | str | `^\d{10}TQ\d{4}$` | **Renommé** depuis `pst_number` |
| `hst_number` | str | `^\d{9}RT\d{4}$` | Inchangé |
| `neq_number` | str | `^\d{10}$` | **Nouveau** |

Default pour les nouveaux : chaîne vide (`""`), jamais `None`.

### `clients` (collection existante, un doc par client)

Cinq champs ajoutés, tous optionnels et tous initialisés à `""` :

```
bn_number, gst_number, qst_number, hst_number, neq_number
```

### `invoices` et `quotes` — snapshot au create

Au moment de `POST /api/invoices` ou `POST /api/quotes`, on ajoute au document :

```python
"tax_registrations": {
    "company": {"bn": str, "gst": str, "qst": str, "hst": str, "neq": str},
    "client":  {"bn": str, "gst": str, "qst": str, "hst": str, "neq": str}
}
```

Le snapshot est figé. Modifier `company_settings` ou `clients` après création n'affecte pas les vieux documents.

Pour `POST /api/quotes/{id}/convert` (devis → facture), le snapshot du devis est recopié tel quel dans la facture.

## Migration

Une seule migration : `pst_number` → `qst_number` dans `company_settings`. Tous les autres champs sont nouveaux et n'ont rien à migrer.

```python
def migrate_pst_to_qst():
    """Idempotent. Renomme pst_number en qst_number dans company_settings."""
    result = db.company_settings.update_many(
        {"pst_number": {"$exists": True}, "qst_number": {"$exists": False}},
        [{"$set": {"qst_number": "$pst_number"}}, {"$unset": "pst_number"}]
    )
    if result.modified_count:
        print(f"Migrated {result.modified_count} company_settings: pst_number → qst_number")
```

Exécutée au démarrage du backend, juste après la création des index existants. Idempotente : run au démarrage suivant ne modifie aucun document.

**Hors scope** : les champs `pst_amount` dans `invoices` / `quotes` restent tels quels (juste un nombre, le label PDF affiche déjà "TVQ").

## Backend

### Validation helper (`server.py`)

```python
import re

TAX_FORMATS = {
    "bn":  (r"^\d{9}$",          "9 chiffres"),
    "gst": (r"^\d{9}RT\d{4}$",   "9 chiffres + RT0001"),
    "qst": (r"^\d{10}TQ\d{4}$",  "10 chiffres + TQ0001"),
    "hst": (r"^\d{9}RT\d{4}$",   "9 chiffres + RT0001"),
    "neq": (r"^\d{10}$",         "10 chiffres"),
}

def normalize_tax_number(value: str) -> str:
    """Strip whitespace, retirer tirets, uppercase. Idempotent. Tolère None."""
    return (value or "").strip().upper().replace(" ", "").replace("-", "")

def check_tax_number(value: str, kind: str) -> dict:
    """Retourne {'valid': bool, 'expected': str}. Jamais bloquant. Vide = valide."""
    if not value:
        return {"valid": True, "expected": ""}
    pattern, hint = TAX_FORMATS[kind]
    return {"valid": bool(re.match(pattern, value)), "expected": hint}
```

### Endpoints modifiés

| Endpoint | Changement |
|---|---|
| `GET /api/settings/company` | Retourne aussi `bn_number`, `qst_number`, `neq_number`, plus un objet `tax_number_warnings: {<champ>: {valid, expected}}` |
| `PUT /api/settings/company` | Accepte + normalise les 5 numéros. Stocke normalisé. Jamais 4xx pour format. |
| `GET /api/clients`, `GET /api/clients/{id}` | Retournent les 5 champs (`""` si non renseignés) + `tax_number_warnings` |
| `POST /api/clients`, `PUT /api/clients/{id}` | Acceptent + normalisent + valident les 5 numéros |
| `POST /api/invoices`, `POST /api/quotes` | Calculent et stockent `tax_registrations` (snapshot des 10 numéros) |
| `POST /api/quotes/{id}/convert` | Recopie `tax_registrations` du devis vers la facture |

### `generate_document_pdf` (lignes 1078-1311)

- Supprime lignes 1138-1143 (TPS et TVQ sous l'adresse entreprise).
- Boîte client : ajoute ligne monospace avec numéros renseignés seulement, après l'email.
- Tableau totaux : inchangé.
- Nouveau bloc : encadré "Numéros d'enregistrement" inséré entre les terms et le footer "Merci".
- Source des données : `document['tax_registrations']` en priorité, fallback sur `company_settings` actuel pour vieux documents sans snapshot.

## Frontend

### `SettingsPage.js`

Nouvelle section "Numéros officiels" après le bloc adresse :

```
┌─ Numéros officiels ────────────────────────────┐
│ BN (Numéro d'entreprise)    [ 123456789      ] │
│ TPS / GST                   [ 123456789RT0001] │
│ TVQ / QST                   [ 1234567890TQ00..] │
│ TVH / HST                   [                ] │
│ NEQ                         [ 1234567890     ] │
└────────────────────────────────────────────────┘
```

- Placeholder = format attendu.
- Tooltip `?` à côté du label.
- Normalisation à la volée (retirer espaces/tirets, uppercase).
- Validation `onBlur` avec regex JS (même que backend) :
  - Vide ou conforme : border neutre/verte.
  - Inhabituel : border jaune + texte "Format inhabituel — attendu : <expected>".
- Le bouton "Enregistrer" n'est jamais bloqué par les warnings.

### `ClientsPage.js`

Section repliable "Numéros officiels (B2B, optionnel)" — fermée par défaut. Mêmes 5 champs avec mêmes comportements.

### `InvoicesPage.js`, `QuotesPage.js`

Aucun changement UI. Les numéros sont snapshotés côté backend à la création.

## Tests

### Tests unitaires (backend)

`backend/tests/test_tax_numbers.py` :

- `test_normalize_idempotent` : `normalize(normalize(x)) == normalize(x)`, gère espaces/tirets/casse.
- `test_check_tax_number_formats` : chaque type valide passe, format incorrect détecté, vide considéré valide.
- `test_migration_idempotent` : run 2x ne change rien au second run, ne touche pas les docs déjà migrés.

### Tests d'intégration

- `PUT /api/settings/company` avec les 5 numéros → `GET` retourne identique.
- `POST /api/clients` avec numéros → `GET` retourne ces numéros.
- `POST /api/invoices` → vérifier présence et valeurs de `tax_registrations.company` et `tax_registrations.client`.
- Modifier `company_settings` ou `clients` après création → facture conserve ses snapshots.

### Vérifications manuelles

| Cas | Attendu |
|---|---|
| Saisie BN `123456789` | Border verte |
| Saisie BN `abc` | Border jaune + hint |
| Copier-coller `123 456 789 RT 0001` | Normalisé en `123456789RT0001` |
| PDF facture, entreprise avec ≥1 numéro | Encadré bas visible |
| PDF facture, entreprise sans aucun numéro | Encadré bas absent |
| PDF facture, client B2B avec TPS+TVQ | Ligne discrète dans "Facturer à" |
| PDF facture, client sans numéros | Boîte "Facturer à" propre |
| Vieille facture pré-snapshot | PDF lit `company_settings` actuel (fallback) |

## Risques et limites

- **Vieilles factures pré-migration** : pas de `tax_registrations` stocké. Le fallback sur `company_settings` actuel signifie que si l'utilisateur change son BN avant de re-télécharger une vieille facture, le nouveau BN apparaît. Acceptable car cas marginal.
- **Validation de format souple** : un utilisateur peut sauvegarder un BN incorrect malgré le warning. Volontaire. Trade-off : flexibilité > conformité automatique.
- **NEQ** : on stocke 10 chiffres exactement. Si REQ change le format un jour, breaking change.
- **Aucune vérification "check digit"** ARC. Un numéro de la bonne longueur mais inventé passe la validation de format. Out of scope.

## Métriques de succès

- Utilisateur peut enregistrer ses 5 numéros officiels dans Settings sans friction.
- Utilisateur peut renseigner les numéros B2B d'un client.
- Toute nouvelle facture/devis a son `tax_registrations` snapshoté.
- PDF d'une facture entreprise enregistrée affiche l'encadré "Numéros d'enregistrement".
- PDF d'une facture B2B affiche les numéros client dans "Facturer à".
- Aucune régression sur les vieilles factures (fallback fonctionne).
- Migration `pst_number → qst_number` se fait sans intervention manuelle au prochain redéploiement Render.
