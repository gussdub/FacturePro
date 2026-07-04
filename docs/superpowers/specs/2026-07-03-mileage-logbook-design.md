# Carnet de route — kilométrage et allocation véhicule (feature #13) — Design

**Statut :** design approuvé 2026-07-03 (brainstorming session avec gussdub, propriétaire de ProFireManager Inc.)
**Auteur :** Claude (brainstorming + explore-phase sur `backend/server.py`)

## 1. Objectif

FacturePro sait enregistrer une dépense « Frais de véhicule » (catégorie ARC `vehicle_expenses`, ligne 9281, feature #3) sous forme d'un montant en dollars saisi à la main. Mais l'ARC exige, pour justifier une allocation ou une déduction de frais de véhicule, un **carnet de route** (logbook) documentant chaque déplacement d'affaires : date, point de départ, destination, motif, distance parcourue. Sans ce carnet, l'allocation versée est indéfendable en cas de vérification.

Ce module introduit un **carnet de route** : la saisie manuelle de chaque trajet d'affaires, le calcul automatique de l'**allocation** (`km × taux ARC de l'année`, avec bascule au taux réduit après 5 000 km cumulés dans l'année), la génération d'une **dépense** dans « Frais de véhicule (9281) », et l'export d'un **carnet de route PDF conforme ARC**.

**Cas d'usage principal :** ProFireManager Inc. est une **société incorporée** (`entity_type = "corporation"`). Le propriétaire est aussi employé-actionnaire. La société lui verse une **allocation par kilomètre** pour ses déplacements d'affaires avec son véhicule personnel. Cette allocation est **non imposable pour l'employé si elle est raisonnable** — c'est-à-dire calculée au taux prescrit par l'ARC et documentée par un carnet de route. Le carnet documente donc l'allocation versée par la société à l'employé-actionnaire ; la dépense correspondante entre dans les frais de véhicule de la société.

**Contexte codebase :**
- Multi-tenant `organization_id` en place partout (feature #11, cf. `_ORG_SCOPED_COLLECTIONS` `server.py:1369`, helper `_org_scope` `server.py:1356`). Toute nouvelle collection sera scopée org.
- RBAC granulaire en place : `PERMISSIONS_EDITABLE` (`server.py:1220`, contient déjà `expenses:read`/`expenses:write`), `require_permission("code")` (`server.py:1344`). Le carnet **réutilise `expenses:read`/`expenses:write`** — un trajet est conceptuellement une dépense de véhicule.
- Catégories de dépenses ARC en place (feature #3, `EXPENSE_CATEGORIES` `server.py:150`). La catégorie `vehicle_expenses` (`server.py:167`, ligne ARC 9281) est la cible de la dépense générée.
- Création de dépense existante `create_expense` (`server.py:4960`) : construit le doc avec `_build_expense_category_snapshot`, `amount_cad`, `organization_id`, `created_by_user_id`. Le carnet **réutilise ce même chemin** pour matérialiser la dépense d'allocation.
- Pattern PDF FR-CA établi : `_t2125_format_money` (formate `85 000,00 $`), `SimpleDocTemplate` ReportLab, `html.escape` sur strings user-supplied, headers `no-store, no-cache`. Le carnet PDF suit exactement ce pattern.
- **Aucun scheduler in-process** : le seul travail « planifié » existant (`POST /api/subscription/check-trial-expiry` `server.py:6254`) est un **endpoint pingé par un cron externe** (pas d'APScheduler, pas de thread). Le rappel annuel du taux suit ce modèle (§7).
- Migrations idempotentes au boot dans `@app.on_event("startup")` (`server.py:7002`), après `migrate_general_ledger_v1()` (`server.py:7032`).

## 2. Décisions de design (brainstorming — fixes)

| # | Question | Décision | Alternatives rejetées |
|---|----------|----------|------------------------|
| 1 | Saisie de la distance | **Manuelle** : l'utilisateur entre les km lui-même pour chaque trajet. | Calcul auto par géocodage d'adresses (Google Maps Distance Matrix) → dépendance API payante + précision variable + PII adresses ; **noté v2** (§13). |
| 2 | Champs d'un trajet | date, **départ**, **arrivée**, **motif** (obligatoire), **km**, bouton **aller-retour** (double les km). | Motif optionnel → l'ARC **exige** le motif d'affaires ; il est donc requis backend. |
| 3 | Trajets répétitifs | **Trajets favoris** : sauvegarder une route fréquente (domicile→client X, km) et la choisir dans une liste pour pré-remplir un trajet. | Re-taper à chaque fois → friction ; auto-détection des routes fréquentes → sur-ingénierie v1. |
| 4 | Table des taux ARC | **Table par année, dans le code** (constante serveur). Chaque année : taux plein (5 000 premiers km) + taux réduit (au-delà). Le trajet utilise le taux de **l'année de sa date**. | Taux unique codé en dur → faux dès le changement d'année ; taux saisi par l'utilisateur → source d'erreur et de non-conformité. |
| 5 | Bascule au taux réduit | **Automatique à 5 000 km cumulés** dans l'année civile, **par personne+véhicule**. Un trajet à cheval sur le seuil est **scindé** : la portion sous 5 000 km au taux plein, la portion au-delà au taux réduit. | Taux plein sur tout → sur-déclaration ; bascule par simple comparaison sans split → erreur sur le trajet qui franchit le seuil. |
| 6 | Rappel annuel du taux | **Endpoint pingé par cron externe** chaque janvier (`POST /api/mileage/check-rate-update`) : détecte que l'année en cours n'a pas de taux dans la table, notifie l'owner par email pour qu'il **vérifie le taux ARC officiel** et confirme la mise à jour. **Vérification humaine obligatoire** — jamais de mise à jour silencieuse. | Scraping automatique du site ARC → fragile, risque légal si le taux scrapé est faux ; scheduler in-process → l'app n'en a pas (cohérence avec feature #11 trial-expiry). |
| 7 | Produit du carnet | **Deux sorties** : (a) une **dépense** `vehicle_expenses` (9281) = allocation calculée, réutilisant `create_expense` ; (b) un **carnet de route PDF conforme ARC**. | Seulement le PDF → l'allocation n'entre pas dans la compta ; seulement la dépense → pas de justificatif ARC. Il faut les deux. |
| 8 | Un trajet crée-t-il une dépense ? | **Chaque trajet peut générer sa propre dépense** (bouton explicite), ET une **vue carnet mensuelle** agrège tout pour le PDF. Pas de lot mensuel forcé. | Lot mensuel obligatoire → rigide ; dépense auto à chaque trajet → pollue les dépenses avec 40 lignes/mois. On laisse l'utilisateur choisir le grain. |
| 9 | Un ou plusieurs véhicules | **Un véhicule par défaut en v1** (créé au premier accès). Le modèle porte `vehicle_id` dès maintenant pour ne pas casser le multi-véhicule v2. | Multi-véhicule complet dès v1 → UI et cumul plus lourds sans besoin immédiat (ProFireManager = 1 véhicule). **Multi-véhicule noté v2** (§13). |
| 10 | Emplacement UI | **Section dans `ExpensesPage`** : bouton « Carnet de route » qui ouvre la vue trajets/favoris/carnet, à côté de la liste des dépenses. | Page dédiée dans la sidebar → sur-poids pour une fonction proche des dépenses ; le carnet EST une source de dépenses véhicule. |
| 11 | Devise | **CAD uniquement**. Les taux ARC sont en $ CAD/km ; l'allocation est en CAD. | Multi-devise → sans objet (taux fédéral canadien). |
| 12 | Personne du trajet | Champ `employee_id` **optionnel** (réutilise `db.employees`) ; défaut = l'utilisateur courant. Le cumul 5 000 km est calculé **par (employee_id ou user, vehicle_id, année)**. | Ignorer la personne → un ménage à plusieurs conducteurs mélangerait les cumuls, faussant la bascule 5 000 km. |

## 3. Modèle de données

### 3.1 Table des taux ARC (constante serveur, `server.py`)

À côté de `EXPENSE_CATEGORIES`. **Taux officiels ARC** (allocation raisonnable pour frais automobiles) :

```python
# Taux ARC allocation automobile, en $ CAD par km.
# full  = taux pour les 5 000 premiers km de l'année civile
# reduced = taux pour chaque km au-delà de 5 000
MILEAGE_RATES = {
    2024: {"full": 0.70, "reduced": 0.64},
    2025: {"full": 0.72, "reduced": 0.66},
    2026: {"full": 0.73, "reduced": 0.67},
}
MILEAGE_RATE_THRESHOLD_KM = 5000   # bascule full → reduced

def _mileage_rate_for_year(year: int) -> dict | None:
    """Retourne {'full','reduced'} pour l'année, ou None si non renseignée
    (déclenche le rappel annuel §7). Pas de fallback silencieux sur une
    autre année : un taux manquant est une condition à corriger, pas à deviner."""
    return MILEAGE_RATES.get(int(year))
```

> **Remarque de conformité :** les taux ci-dessus **sont confirmés contre canada.ca** (taux raisonnables prescrits, Reg. 7306 ITR). 2024 : 0,70/0,64 ; 2025 : 0,72/0,66 ; **2026 : 0,73/0,67 — confirmé le 2026-07-04** (annonce Finance Canada des plafonds 2026 + guide des allocations automobiles ARC : hausse d'un cent → 73 c/km pour les 5 000 premiers km, 67 c/km au-delà, provinces). Le rappel annuel (§7) garantit qu'ils restent à jour aux années suivantes. Le seuil et les taux territoriaux (+0,04 $/km dans les Territoires) sont notés §13 comme hors scope v1.

### 3.2 Nouvelle collection `mileage_trips`

Un document par trajet, scopé org.

```python
{
  "id": str,                       # uuid
  "organization_id": str,          # scope (feature #11)
  "created_by_user_id": str,       # audit
  "employee_id": str | None,       # FK db.employees ; None => user courant
  "vehicle_id": str,               # FK mileage_vehicles (véhicule par défaut en v1)
  "trip_date": str,                # ISO date "YYYY-MM-DD" PURE (jamais de composante T ni BSON Date) — contrat du cumul YTD §4.1, validé len==10 à l'insert
  "origin": str,                   # point de départ (ex: "Domicile, Québec")
  "destination": str,              # destination (ex: "Client ABC, Lévis")
  "purpose": str,                  # motif d'affaires — OBLIGATOIRE (ARC)
  "one_way_km": float,             # km saisis pour un aller simple (> 0)
  "round_trip": bool,              # true => distance doublée
  "distance_km": float,            # dérivé : one_way_km * (2 if round_trip else 1)
  "favorite_id": str | None,       # trajet favori source (si pré-rempli), pour audit
  "expense_id": str | None,        # dépense générée depuis ce trajet (si générée), pour lien/cascade
  "notes": str | None,
  "created_at": str,               # ISO 8601 UTC
}
```

**Invariants (forcés backend) :**
- `purpose` non vide après `strip()` → sinon 400 (« Le motif du déplacement est obligatoire »).
- `one_way_km > 0` (fini, `math.isfinite`) → sinon 400.
- `distance_km` **toujours recalculé backend** = `round(one_way_km * (2 if round_trip else 1), 2)` (jamais fait confiance à la valeur envoyée).
- `employee_id`, `vehicle_id` référencent des docs de la **même org** (vérifié avant insert).

**Index** : `(organization_id, trip_date)`, `(organization_id, vehicle_id, trip_date)`, `(organization_id, employee_id)`, `(organization_id, expense_id)`.

### 3.3 Nouvelle collection `mileage_favorites`

Un document par route fréquente sauvegardée, scopé org.

```python
{
  "id": str,
  "organization_id": str,
  "created_by_user_id": str,
  "label": str,                    # nom affiché ("Domicile → Client ABC")
  "origin": str,
  "destination": str,
  "purpose": str | None,           # motif par défaut (l'utilisateur peut l'ajuster au trajet)
  "one_way_km": float,             # distance mémorisée pour un aller simple
  "round_trip_default": bool,      # coche aller-retour par défaut à l'application
  "created_at": str,
}
```

**Index** : `(organization_id, label)`.

> Un favori est un **gabarit**, pas un trajet : l'appliquer pré-remplit le formulaire de trajet (origin/destination/purpose/km), l'utilisateur ajuste la date puis enregistre. Modifier ou supprimer un favori **n'affecte jamais** les trajets déjà enregistrés (aucune dénormalisation liante — `favorite_id` sur le trajet est purement traçant).

### 3.4 Nouvelle collection `mileage_vehicles`

```python
{
  "id": str,
  "organization_id": str,
  "created_by_user_id": str,
  "name": str,                     # "Véhicule principal" (défaut)
  "make_model": str | None,        # "Toyota RAV4" (optionnel, utile au carnet ARC)
  "plate": str | None,             # plaque (optionnel)
  "is_default": bool,              # true pour le véhicule seedé v1
  "is_active": bool,
  "created_at": str,
}
```

Un **véhicule par défaut est créé au premier accès** au carnet (`_ensure_default_vehicle(org_id, user_id)`, idempotent : ne crée que si zéro véhicule pour l'org). Ce champ prépare le multi-véhicule v2 sans le livrer.

**Index** : `(organization_id, is_default)`.

### 3.5 Champs ajoutés à `company_settings`

Aucun champ nouveau **requis**. Le rappel annuel du taux (§7) trace son état sur une collection dédiée (§3.6) plutôt que de polluer `company_settings`.

### 3.6 Nouvelle collection `mileage_rate_reminders` (état du rappel annuel)

Empêche le double envoi du rappel (même garantie que `trial_notifications`, `server.py:6281`).

```python
{
  "id": str,                       # "{organization_id}:{year}"
  "organization_id": str,
  "year": int,                     # année dont le taux manque
  "notified_at": str,              # ISO 8601 UTC
}
```

**Index** : `id` unique.

## 4. Calcul de l'allocation (bascule 5 000 km)

Le cœur du module. Deux fonctions serveur.

### 4.1 Cumul annuel avant un trajet

```python
def _mileage_ytd_before(scope, employee_key, vehicle_id, year, before_date, exclude_trip_id=None):
    """Somme des distance_km de la même (personne, véhicule) sur l'année civile,
    pour les trajets DONT la date est < before_date (ou = before_date avec id <).
    Sert à savoir combien de km sont déjà cumulés avant le trajet courant,
    pour appliquer la bascule 5 000 km au bon endroit.
    - employee_key = employee_id ou, si None, 'user:{user_id}' (clé stable par personne)
    - Ne compte que l'année civile de `year`.
    """
    ...
```

Le **cumul est chronologique par date de trajet** : deux trajets sont ordonnés par `(trip_date, id)`. Le YTD « avant » un trajet est la somme des trajets antérieurs de la même personne+véhicule dans l'année.

### 4.2 Allocation d'un trajet (avec split au seuil)

```python
def _mileage_allocation(distance_km, ytd_before, rates, threshold=MILEAGE_RATE_THRESHOLD_KM):
    """Retourne (amount_cad, breakdown).
    Applique le taux plein aux km jusqu'à `threshold` cumulé, le taux réduit au-delà.
    Un trajet à cheval sur le seuil est SCINDÉ.

    Ex: ytd_before=4900, distance=200, threshold=5000, full=0.73, reduced=0.67
        -> 100 km @ 0.73 (jusqu'à 5000) + 100 km @ 0.67 = 73.00 + 67.00 = 140.00
    """
    remaining_full = max(0.0, threshold - ytd_before)
    km_full = min(distance_km, remaining_full)
    km_reduced = distance_km - km_full
    amount = round(km_full * rates["full"] + km_reduced * rates["reduced"], 2)
    return amount, {
        "km_full": round(km_full, 2), "rate_full": rates["full"],
        "km_reduced": round(km_reduced, 2), "rate_reduced": rates["reduced"],
        "ytd_before": round(ytd_before, 2),
    }
```

**Points importants :**
- Le taux vient de `_mileage_rate_for_year(year_of_trip_date)`. Si `None` → l'allocation ne peut être calculée : l'API renvoie une erreur explicite (« Taux ARC {year} non configuré — voir rappel annuel ») **au lieu de deviner**.
- Le cumul, donc la bascule, est **par (personne, véhicule, année)** — cohérent avec la décision #12.
- Le calcul est **recalculé à la volée** à chaque affichage/génération, jamais figé sur le trajet lui-même (sauf snapshot dans la dépense générée, §5). Ainsi, si l'utilisateur insère un trajet antérieur, les allocations suivantes se recalculent correctement.

## 5. Génération de la dépense (produit du carnet, §2 décision #7)

Un bouton « Générer la dépense » sur un trajet (ou sur la vue carnet mensuelle) crée une dépense `vehicle_expenses` via le **chemin existant** `create_expense` (`server.py:4960`), sans réécrire la logique :

- `category_code = "vehicle_expenses"` → `_build_expense_category_snapshot` pose ligne ARC 9281, `deductible_percentage=100`.
- `amount = amount_cad = _mileage_allocation(...)` (CAD, pas de conversion de devise).
- `description` = `"Allocation km — {origin} → {destination} ({distance_km} km)"`.
- `expense_date` = `trip_date` du trajet.
- Champs de traçabilité posés sur la dépense : `mileage_trip_ids: [...]` (un ou plusieurs trajets agrégés) et `mileage_generated: true`.
- Le(s) trajet(s) source(s) reçoivent `expense_id` (lien bidirectionnel pour la cascade).

**Deux modes** (décision #8) :
1. **Par trajet** : `POST /api/mileage/trips/{id}/generate-expense` → une dépense d'un seul trajet.
2. **Lot mensuel** : `POST /api/mileage/generate-expense` avec `{year, month, vehicle_id}` → une **seule** dépense agrégeant tous les trajets non encore facturés du mois (somme des allocations calculées trajet par trajet avec la bascule correcte). Chaque trajet inclus est marqué (`expense_id`).

**Anti-double-comptage :** un trajet qui a déjà un `expense_id` **non nul** est exclu de la génération de lot et son bouton « Générer » individuel est masqué. `DELETE` de la dépense (chemin existant `delete_expense`) **libère** les trajets liés (`_release_mileage_trips(expense_id)` → unset `expense_id` sur les trajets, modèle : `_release_bank_transaction` feature #7). Ainsi supprimer la dépense rend les trajets à nouveau « facturables ».

## 6. API REST

Toutes les routes sous `/api/mileage/*`, scopées org, protégées par `expenses:read` (lecture) ou `expenses:write` (mutation). `_ensure_default_vehicle` appelé au début de chaque endpoint.

### 6.1 Trajets

| Méthode | Route | Perm | Effet |
|---|---|---|---|
| GET | `/api/mileage/trips?year=&month=&vehicle_id=` | `expenses:read` | Liste des trajets filtrés, triés `(trip_date, id)`, chaque trajet **enrichi** de son allocation calculée (avec breakdown §4.2) et de son cumul YTD. |
| POST | `/api/mileage/trips` | `expenses:write` | Crée un trajet. Valide `purpose` non vide, `one_way_km > 0`. Recalcule `distance_km`. Retourne le trajet + allocation. |
| PUT | `/api/mileage/trips/{id}` | `expenses:write` | Édite un trajet. Si un `expense_id` est déjà lié → **400** (« trajet déjà facturé — supprimez d'abord la dépense »). Recalcule `distance_km`. |
| DELETE | `/api/mileage/trips/{id}` | `expenses:write` | Supprime un trajet. Si lié à une dépense → **400** (détacher d'abord). |
| POST | `/api/mileage/trips/{id}/generate-expense` | `expenses:write` | Génère la dépense d'un trajet (§5). 400 si déjà lié. |
| POST | `/api/mileage/generate-expense` | `expenses:write` | Génère la dépense **de lot mensuel** `{year, month, vehicle_id}` (§5). |

### 6.2 Favoris

| Méthode | Route | Perm | Effet |
|---|---|---|---|
| GET | `/api/mileage/favorites` | `expenses:read` | Liste des favoris de l'org. |
| POST | `/api/mileage/favorites` | `expenses:write` | Crée un favori (label, origin, destination, one_way_km, purpose?, round_trip_default?). |
| PUT | `/api/mileage/favorites/{id}` | `expenses:write` | Édite un favori (n'affecte pas les trajets existants). |
| DELETE | `/api/mileage/favorites/{id}` | `expenses:write` | Supprime un favori. |

### 6.3 Véhicules

| Méthode | Route | Perm | Effet |
|---|---|---|---|
| GET | `/api/mileage/vehicles` | `expenses:read` | Liste des véhicules (au moins le défaut, seedé au 1er accès). |
| POST | `/api/mileage/vehicles` | `expenses:write` | Crée un véhicule (préparation v2 ; utilisable mais UI minimale en v1). |

### 6.4 Taux et carnet

| Méthode | Route | Perm | Effet |
|---|---|---|---|
| GET | `/api/mileage/rates` | `expenses:read` | Retourne `MILEAGE_RATES` + `threshold` + année courante + drapeau `current_year_missing` (true si `_mileage_rate_for_year(current_year) is None`). |
| GET | `/api/mileage/logbook?year=&vehicle_id=` | `expenses:read` | JSON du carnet annuel : liste ordonnée des trajets avec **cumul progressif** (running total km) + allocation par trajet + totaux + info véhicule/personne. |
| GET | `/api/mileage/logbook/pdf?year=&vehicle_id=` | `expenses:read` | **Carnet de route PDF conforme ARC** (§8). Headers no-cache. |
| POST | `/api/mileage/check-rate-update` | (aucune — cron externe) | Rappel annuel (§7). Non authentifié comme `check-trial-expiry`. |

## 7. Rappel annuel du taux ARC

**Mécanisme** (aligné sur `POST /api/subscription/check-trial-expiry` `server.py:6254` — endpoint pingé par un cron externe, **pas** de scheduler in-process) :

```python
@app.post("/api/mileage/check-rate-update")
async def check_mileage_rate_update(request: Request):
    """Pingé par un cron externe (ex: Render Cron Job / cron-job.org) chaque
    janvier. Si le taux de l'année courante manque dans MILEAGE_RATES, notifie
    l'owner de chaque org active pour VÉRIFICATION HUMAINE du taux ARC officiel.
    Idempotent : n'envoie qu'une fois par (org, année) via mileage_rate_reminders.
    Ne met JAMAIS à jour le taux automatiquement — la table est dans le code et
    ne change qu'au déploiement, après vérification manuelle."""
    year = datetime.now(timezone.utc).year
    if _mileage_rate_for_year(year) is not None:
        return {"status": "ok", "year": year, "action": "rate_present"}
    # taux manquant -> notifier les owners une seule fois
    ...
```

**Comportement :**
- Le taux vit **dans le code** (`MILEAGE_RATES`). Le rappel ne modifie pas la DB — il **alerte un humain** pour qu'il aille chercher le taux officiel ARC de la nouvelle année et fasse un déploiement (mise à jour de la constante + confirmation).
- L'email (via Resend, pattern `check_trial_expiry`) dit : « Le taux d'allocation automobile ARC {year} n'est pas encore configuré dans FacturePro. Vérifiez le taux officiel sur canada.ca puis mettez à jour. En attendant, le calcul d'allocation {year} est bloqué avec un message explicite. »
- **Gestion de l'indisponibilité** : si `RESEND_API_KEY` absent → l'endpoint log et renvoie `{"status":"skipped","reason":"email_not_configured"}` sans 500. Si un envoi échoue → capturé par org (n'interrompt pas la boucle), à l'image de `check_trial_expiry`. L'état `mileage_rate_reminders` n'est écrit **qu'après** envoi réussi, donc un échec sera retenté au prochain ping cron.
- **UX de blocage :** tant que le taux de l'année courante manque, `GET /api/mileage/rates` renvoie `current_year_missing=true` ; le frontend affiche un bandeau « Taux {year} à confirmer » et **désactive** la génération de dépense pour les trajets de cette année (l'allocation renvoie une erreur 400 explicite, cf. §4.2). Les trajets restent **saisissables** (on n'empêche pas de tenir le carnet) ; seule l'allocation $ attend le taux.

> **Note d'implémentation (planification) :** la mise en place du cron externe (fréquence : 1×/jour en janvier suffit) se fait hors code, dans le tableau de bord Render / un service cron gratuit, en pointant sur `/api/mileage/check-rate-update`. Documenté dans le plan. Aucune dépendance Python de scheduling ajoutée.

## 8. Carnet de route PDF (conformité ARC)

`GET /api/mileage/logbook/pdf?year=&vehicle_id=` — ReportLab `SimpleDocTemplate`, FR-CA, même pattern que le PDF T2125 (`_t2125_format_money`, `html.escape`, no-cache).

**En-tête :**
- Titre « Carnet de route — {année} ».
- Nom de l'entreprise (depuis `company_settings`), véhicule (`name` + `make_model` + `plate` si présents), personne (employé ou owner).
- Mention « Registre des déplacements d'affaires — conforme aux exigences de l'ARC pour l'allocation de frais automobiles ».

**Tableau principal — une ligne par trajet, colonnes exigées par l'ARC :**

| Colonne | Source |
|---|---|
| **Date** | `trip_date` (format `AAAA-MM-JJ`) |
| **Départ** | `origin` (`html.escape`) |
| **Arrivée** | `destination` (`html.escape`) |
| **Motif** | `purpose` (`html.escape`) — **obligatoire ARC** |
| **Km** | `distance_km` (aller-retour déjà appliqué), format FR-CA |
| **Cumul** | running total km depuis le début de l'année (colonne exigée : distance cumulée) |
| **Allocation** | `amount_cad` du trajet, format `140,00 $` |

**Pied de tableau :**
- Total des km de l'année.
- Total de l'allocation de l'année.
- Rappel de la bascule : « Taux plein {full} $/km jusqu'à 5 000 km, puis {reduced} $/km » avec l'année et le taux appliqués.

**Champs obligatoires ARC couverts :** date, point de départ, destination, motif d'affaires, distance parcourue, distance cumulée. (L'odomètre de début/fin d'année n'est pas exigé pour la méthode d'allocation par km ; noté §13 pour la méthode « frais réels » si demandée en v2.)

## 9. Frontend

### 9.1 Emplacement (décision #10)

Dans `ExpensesPage.js`, un bouton « **Carnet de route** » (icône `Car` ou `MapPin` lucide-react) à côté des actions existantes (« Nouvelle dépense », « Scanner reçu »). Il ouvre une vue carnet (modal plein écran ou sous-onglet interne à ExpensesPage — pas de nouvelle route sidebar). Gaté sur `hasPermission("expenses:read")` ; les boutons de mutation sur `expenses:write`.

### 9.2 Vue carnet (onglets internes)

1. **Trajets** — table des trajets du mois/année sélectionné (Date, Départ, Arrivée, Motif, Km, Allocation, badge « facturé » si `expense_id`). Bouton « Nouveau trajet ». Filtre année/mois/véhicule.
   - **Formulaire trajet** : date, **départ**, **arrivée**, **motif** (requis, astérisque), **km (aller simple)**, case **« Aller-retour »** (affiche en direct `km × 2`), sélecteur de favori (« Depuis un favori… » pré-remplit départ/arrivée/motif/km), bouton « Enregistrer et générer la dépense » ou « Enregistrer seulement ».
   - **Allocation live** : sous le champ km, afficher le montant calculé (`X km × taux = Y $`), avec mention si la bascule 5 000 km s'applique (« dont N km au taux réduit »). Calcul frontend indicatif ; backend fait foi.

2. **Favoris** — liste des trajets favoris (label, route, km, aller-retour par défaut). Bouton « Nouveau favori ». Édition/suppression. Bouton « Utiliser » qui bascule vers l'onglet Trajets avec le formulaire pré-rempli.

3. **Carnet** — vue annuelle read-only avec cumul progressif + totaux + bouton « Télécharger le carnet PDF ». Bandeau « Taux {year} à confirmer » si `current_year_missing`.

### 9.3 Génération de dépense

Depuis l'onglet Trajets : bouton par ligne « Générer la dépense » (masqué si `expense_id` déjà posé), et action de barre « Générer la dépense du mois » (lot). Après génération, la dépense apparaît dans la liste des dépenses normale (`vehicle_expenses`) — le carnet et les dépenses restent cohérents.

### 9.4 Composants réutilisés

Format CAD existant, `RouteGuard`/`hasPermission` (feature #11), pattern de téléchargement blob authentifié des PDF (comme T2125). Pas de nouvelle lib, pas de nouvelle route sidebar.

## 10. Sécurité

| Menace | Mitigation |
|---|---|
| **Fuite cross-org** (lecture de trajets d'une autre org) | Tout query filtre `{"organization_id": current_user.organization_id}` via `_org_scope` — jamais d'accès par `id` seul. `employee_id`/`vehicle_id`/`favorite_id` vérifiés appartenir à l'org avant insert. |
| **Motif manquant** (carnet non conforme ARC) | `purpose` validé non vide backend (400) — la validation frontend n'est qu'une commodité. |
| **Distance falsifiée** (`distance_km` envoyé ≠ `one_way_km × facteur`) | `distance_km` **toujours recalculé backend** ; la valeur envoyée est ignorée. |
| **Allocation gonflée** (taux ou bascule contournés) | Taux tiré exclusivement de `MILEAGE_RATES` serveur ; `_mileage_allocation` calculé backend ; le montant frontend est indicatif. Trajet d'une année sans taux → 400, jamais de fallback. |
| **Double comptage** (2 dépenses pour le même trajet) | `expense_id` sur le trajet exclut de la génération ; génération individuelle bloquée si déjà lié (400) ; lot exclut les trajets liés. |
| **Injection HTML dans le PDF** (origin/destination/motif user-supplied) | `html.escape` sur toute string avant ReportLab (pattern `_render_t2125_pdf`). |
| **Cache PDF exposant le carnet** (proxy/CDN) | Headers `no-store, no-cache, must-revalidate` (pattern T2125). |
| **Élévation via `expenses:*`** | Aucun nouveau code de permission ; le carnet réutilise `expenses:read`/`expenses:write` déjà dans `PERMISSIONS_EDITABLE`. Pas de surface RBAC nouvelle. |
| **Endpoint cron ouvert** (`check-rate-update` non authentifié) | Comme `check-trial-expiry` : ne renvoie aucune donnée org sensible (juste un compteur), idempotent par `mileage_rate_reminders`, ne mute aucune donnée métier. Abus = au pire des emails de rappel en double évités par l'index unique. |

## 11. RBAC et migration

### 11.1 Permissions

**Aucun nouveau code de permission.** Le carnet réutilise `expenses:read` / `expenses:write` (déjà `PERMISSIONS_EDITABLE` `server.py:1220`). Un comptable (read+write) et un lecteur (read) héritent automatiquement de l'accès au carnet — cohérent avec le fait qu'un trajet est une dépense de véhicule.

### 11.2 Migration idempotente `migrate_mileage_logbook_v1()`

Ajoutée dans le bloc startup (`server.py:7032`), après `migrate_general_ledger_v1()`.

```python
def migrate_mileage_logbook_v1():
    """Idempotente. Safe à chaque boot. Purement additive :
    crée uniquement les index des nouvelles collections. AUCUNE donnée
    existante touchée. Le véhicule par défaut est seedé LAZY au 1er accès
    (comme le plan comptable feature #12), pas ici, pour ne pas peupler
    des orgs qui n'utiliseront jamais le carnet."""
    db.mileage_trips.create_index([("organization_id", 1), ("trip_date", 1)])
    db.mileage_trips.create_index([("organization_id", 1), ("vehicle_id", 1), ("trip_date", 1)])
    db.mileage_trips.create_index([("organization_id", 1), ("expense_id", 1)])
    db.mileage_favorites.create_index([("organization_id", 1), ("label", 1)])
    db.mileage_vehicles.create_index([("organization_id", 1), ("is_default", 1)])
    db.mileage_rate_reminders.create_index("id", unique=True)
```

Ajouter aussi `_ORG_SCOPED_COLLECTIONS` (`server.py:1369`) les 4 nouvelles collections org-scopées (`mileage_trips`, `mileage_favorites`, `mileage_vehicles`, `mileage_rate_reminders`) pour que tout futur outillage org-scopé (export, suppression d'org) les prenne en compte.

### 11.3 Seed lazy du véhicule par défaut

`_ensure_default_vehicle(org_id, user_id)` appelé au début de chaque endpoint `/api/mileage/*` :
```python
if db.mileage_vehicles.count_documents({"organization_id": org_id}) == 0:
    db.mileage_vehicles.insert_one({... "name": "Véhicule principal",
                                    "is_default": True, "is_active": True, ...})
```
Idempotent (ne seed que si zéro véhicule). Garantit qu'une org accédant au carnet pour la 1re fois a un véhicule cible.

## 12. Tests

### 12.1 Unitaires — `backend/tests/test_mileage_logbook.py`

- `_mileage_rate_for_year` : 2024/2025/2026 retournent les bons taux ; année absente → `None`.
- `distance_km` : aller simple = `one_way_km` ; aller-retour = `2 × one_way_km` ; arrondi 2 décimales.
- `_mileage_allocation` **sans bascule** : `ytd_before=0`, 100 km, 2026 → `100 × 0.73 = 73.00 $`, `km_reduced=0`.
- `_mileage_allocation` **entièrement au taux réduit** : `ytd_before=6000`, 100 km, 2026 → `100 × 0.67 = 67.00 $`.
- `_mileage_allocation` **à cheval sur le seuil** (cas critique) : `ytd_before=4900`, 200 km, 2026 → `100 × 0.73 + 100 × 0.67 = 140.00 $` ; breakdown `km_full=100`, `km_reduced=100`.
- `_mileage_allocation` **exactement au seuil** : `ytd_before=5000`, 100 km → tout au taux réduit ; `ytd_before=4800`, 200 km → `200 × 0.73` (pile sous le seuil, `remaining_full=200`).
- `_mileage_ytd_before` : somme des trajets antérieurs de la même personne+véhicule dans l'année ; ignore une autre personne, un autre véhicule, une autre année ; ordre `(trip_date, id)`.
- Taux manquant : allocation d'un trajet dont l'année n'est pas dans `MILEAGE_RATES` → erreur explicite, pas de calcul silencieux.

### 12.2 Intégration — `backend/tests/test_mileage_logbook_integration.py`

- **Seed lazy véhicule** : 1er GET `/api/mileage/vehicles` d'une org neuve → 1 véhicule par défaut ; 2e appel → pas de doublon.
- **CRUD trajet** : POST sans `purpose` → 400 ; POST `one_way_km=0` → 400 ; POST aller-retour → `distance_km` doublé ; PUT d'un trajet lié à une dépense → 400 ; DELETE d'un trajet lié → 400.
- **Enrichissement** : GET `/api/mileage/trips` retourne allocation + breakdown + YTD par trajet.
- **Bascule 5 000 km end-to-end** : créer des trajets cumulant 4 900 km puis un trajet de 200 km sur 2026 → le dernier a `amount_cad = 140.00` avec split ; un 3e trajet après → tout au taux réduit.
- **Favoris** : POST favori → GET le liste ; appliquer un favori (frontend pré-rempli) puis POST trajet avec `favorite_id` → trajet a `favorite_id` posé ; supprimer le favori n'affecte pas le trajet.
- **Génération dépense par trajet** : POST `/trips/{id}/generate-expense` → une dépense `vehicle_expenses` (ligne 9281) montant = allocation ; trajet a `expense_id` ; 2e appel → 400.
- **Génération lot mensuel** : POST `/generate-expense` `{year, month}` → une seule dépense = somme des allocations du mois ; tous les trajets marqués ; trajets déjà facturés exclus.
- **Cascade** : DELETE de la dépense générée → trajets liés libèrent `expense_id` (re-générables).
- **Carnet PDF** : GET `/logbook/pdf?year=2026` → 200 `application/pdf`, headers no-cache ; colonnes Date/Départ/Arrivée/Motif/Km/Cumul/Allocation présentes.
- **Rappel annuel** : `GET /api/mileage/rates` avec année courante présente → `current_year_missing=false` ; simuler année manquante → `true`. POST `/check-rate-update` année présente → `rate_present` ; année manquante + Resend absent → `skipped` sans 500 ; idempotence via `mileage_rate_reminders`.
- **RBAC** : lecteur GET `/api/mileage/trips` → 200 ; lecteur POST → 403 « expenses:write ».
- **Isolation cross-org** : org A crée un trajet, org B GET `/api/mileage/trips/{id_A}` → 404 ; le carnet de B n'inclut pas les trajets de A.

### 12.3 E2E manuel

- Owner ouvre « Carnet de route » depuis Dépenses → voit le véhicule par défaut.
- Créer un favori « Domicile → Client ABC, 45 km, aller-retour ».
- Saisir un trajet depuis ce favori → 90 km, allocation 90 × 0,73 = 65,70 $ (2026, sous 5 000 km).
- Saisir assez de trajets pour dépasser 5 000 km → vérifier que la bascule s'affiche et que l'allocation baisse au taux réduit sur le trajet qui franchit le seuil (split visible).
- Générer la dépense du mois → une ligne `Frais de véhicule` apparaît dans les dépenses.
- Télécharger le carnet PDF 2026 → colonnes ARC présentes, cumul progressif correct, totaux justes.
- Lecteur invité (feature #11) : accède au carnet en read seul, boutons masqués.

**Cible : ~50 tests** (~20 unitaires + ~25 intégration + ~5 E2E manuels).

## 13. Limites v1 / Hors scope

- **Calcul de distance par adresse** (géocodage/Distance Matrix) — v1 = saisie manuelle des km. **v2 possible** : intégration cartographique pour proposer la distance depuis départ/arrivée.
- **Multi-véhicule** — v1 = un véhicule par défaut par org (le modèle porte `vehicle_id` pour ne pas casser v2). L'UI de gestion multi-véhicule (choisir/renommer/désactiver plusieurs véhicules) est **v2**.
- **Méthode « frais réels »** (allocation calculée sur essence + entretien + DPA au prorata du % d'usage d'affaires, ligne 9281 détaillée) — v1 couvre la **méthode d'allocation par km** (la plus courante pour une société qui rembourse un employé-actionnaire). La méthode frais réels + odomètre début/fin d'année est notée v2.
- **Taux territoriaux** (Territoires du Nord-Ouest / Yukon / Nunavut : +0,04 $/km) — v1 applique le taux fédéral standard. Une org territoriale ajusterait ; noté pour v2.
- **Mise à jour automatique du taux** — v1 = rappel humain (§7). Le scraping/API du taux ARC officiel reste hors scope (fragilité + risque de conformité si erroné).
- **Cumul 5 000 km inter-année / année fiscale décalée** — le cumul et la bascule sont sur l'**année civile** (base de calcul ARC pour les frais automobiles), indépendamment du `fiscal_year_end` de la société (feature #12). C'est correct pour l'allocation ; documenté pour éviter la confusion avec l'exercice financier.
- **Lien carnet ↔ grand livre** (feature #12) — la dépense générée entre dans les rapports (P&L, T2125) comme n'importe quelle dépense ; l'écriture GL automatique arrivera avec l'auto-posting Phase 2 du grand livre.
- **Ne pas cumuler carnet de route ET `vehicle_business_percentage` du T2125** (feature #10) — ⚠️ **incompatibilité de méthode**. La dépense générée par le carnet est déjà l'**allocation déductible** (km × taux ARC de l'année) : elle représente **100 % du montant à déduire**, pas un coût brut de véhicule à proratiser. Or l'export T2125 (feature #10) applique un **mode exclusif** qui, dès que `vehicle_business_percentage > 0` dans Réglages, déplace **tout** le brut de la catégorie `vehicle_expenses` sur la ligne 9281 puis le multiplie par ce pourcentage (`_t2125_compute_vehicle_adjustment`). Une org qui utilise **à la fois** le carnet de route **et** renseigne un `vehicle_business_percentage` verrait donc sa déduction 9281 **réduite deux fois** (allocation déjà proratée × %), sous-déclarant sa déduction véhicule. Ce sont deux **méthodes ARC mutuellement exclusives** : la **méthode allocation par km** (le carnet, ligne 9281 = allocation) et la **méthode frais réels au prorata** (le `vehicle_business_percentage` du T2125, ligne 9281 = coûts réels × % d'usage d'affaires). **Recommandation v1 :** une org qui tient un carnet de route laisse `vehicle_business_percentage = 0` dans Réglages (défaut). Le carnet lui-même EST le justificatif ARC ; le montant généré est déjà la déduction finale. Le double-prorata côté T2125 est **pré-existant** à cette feature (comportement voulu du mode frais réels feature #10) — **ce n'est pas une régression du carnet** : le calcul de génération du carnet est correct et non affecté. Une réconciliation automatique des deux méthodes (détecter des dépenses `mileage_generated=True` et les exclure du prorata T2125) est notée **hors scope v1** — traitable en tâche séparée si les deux méthodes doivent coexister.
- **Devise étrangère** — CAD only (taux fédéral en CAD/km).

## 14. Rollback plan

**Scénarios et procédures :**

1. **Migration `migrate_mileage_logbook_v1` échoue au boot** :
   - Détection : erreur au startup / index non créés.
   - Recovery : la migration ne fait **que** créer des index sur des collections neuves ; elle ne touche aucune donnée existante. Un échec est sans conséquence sur le reste de l'app ; rollback Render à N-1 (« Redeploy previous ») si besoin.

2. **Allocation calculée fausse** (bascule ou taux erroné) :
   - Détection : montant de dépense incohérent, ou carnet PDF avec mauvais total.
   - Le calcul est **recalculé à la volée** (non figé sur le trajet) : corriger `MILEAGE_RATES` ou la logique `_mileage_allocation` + redéployer suffit à corriger tous les affichages. Les **dépenses déjà générées** ont un montant figé (snapshot) ; on les supprime (ce qui libère les trajets) et on régénère.

3. **Le module carnet est totalement problématique** :
   - Feature isolée : cacher le bouton « Carnet de route » dans `ExpensesPage` (hotfix frontend).
   - Backend : les endpoints `/api/mileage/*` peuvent rester en place (inertes sans accès UI). Aucune collection existante (`expenses`, `company_settings`) n'est modifiée — hors la dépense générée, qui est une dépense normale supprimable.
   - Les collections `mileage_trips`, `mileage_favorites`, `mileage_vehicles`, `mileage_rate_reminders` sont **additives** — laissées en place sans impact.

4. **Rollback complet de la feature** :
   - Redéployer la version pré-feature #13 sur Render + Vercel.
   - Les 4 nouvelles collections sont ignorées par l'ancien code.
   - Les dépenses générées (`vehicle_expenses` avec `mileage_generated: true`) restent des dépenses valides — l'ancien code les affiche normalement (champs extra ignorés).
   - Le cron externe pointant sur `/check-rate-update` retournera 404 après rollback — le désactiver dans le tableau de bord cron.

**Point de non-retour** : aucun. Le module est **purement additif** ; il ne migre ni ne mute aucune donnée métier existante (contrairement à la feature #11). La seule écriture dans une collection existante est la **création** d'une dépense (chemin normal, réversible par suppression).

## 15. Impact estimé

- **Backend** : ~14 endpoints `/api/mileage/*` (~400 lignes), table des taux + helpers allocation/cumul (~120 lignes), 1 PDF ReportLab carnet (~180 lignes), endpoint rappel annuel (~60 lignes), 1 migration + seed lazy (~40 lignes). Total : **~800 lignes ajoutées**, ~5 lignes modifiées (`_ORG_SCOPED_COLLECTIONS`, registration migration startup). Réutilise `create_expense`, `_build_expense_category_snapshot`, `_release_*` pattern.
- **Frontend** : vue carnet dans `ExpensesPage` (3 onglets : Trajets, Favoris, Carnet — ~700 lignes), bouton + gating (~15 lignes). Total : **~715 lignes ajoutées**.
- **Tests** : ~50 tests, **~800 lignes**.
- **Nouvelles collections** : `mileage_trips`, `mileage_favorites`, `mileage_vehicles`, `mileage_rate_reminders`.
- **Nouveaux champs** : aucun sur les collections existantes (la dépense générée porte `mileage_trip_ids`/`mileage_generated`, additifs).
- **Nouveaux codes RBAC** : aucun (réutilise `expenses:read`/`expenses:write`).
- **Env vars nouvelles** : aucune (Resend déjà configuré pour le rappel).
- **Infra hors code** : 1 cron externe (Render Cron / cron-job.org) pointant sur `POST /api/mileage/check-rate-update`, 1×/jour en janvier — documenté dans le plan.
