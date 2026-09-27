# Lot 0 — API d'intégration FacturePro ↔ ProFireManager

**Destinataire** : la session Claude Code du projet FacturePro.
**Statut** : spécification d'intention, à valider avant implémentation.
**Rédigé le** : 2026-09-26.

---

## 1. Contexte

ProFireManager (PFM) est l'autre produit du même propriétaire : un logiciel de
gestion pour services d'incendie, vendu en abonnement à des municipalités. PFM
construit actuellement un CRM dans son panneau super-admin (`/admin`) pour
suivre ses prospects et ses clients.

Décision d'architecture déjà prise du côté PFM :

- **FacturePro est la source de vérité** pour les clients, les soumissions et
  les factures. Le module Stripe présent dans PFM reste dormant.
- La circulation des données est **à sens unique, FacturePro → PFM**, à une
  seule exception près : PFM crée des soumissions de renouvellement **en
  brouillon** dans FacturePro. PFM n'envoie jamais rien au client final.
- PFM est notifié par **webhook** (FacturePro pousse), avec un bouton de
  resynchronisation manuelle côté PFM comme filet de sécurité.
- L'intégration doit être **généralisable** : PFM définit une interface
  « fournisseur de facturation » dont FacturePro est la première
  implémentation. Cela n'impose rien à FacturePro, mais explique pourquoi la
  surface d'API doit être stable et versionnée.

FacturePro doit donc livrer quatre choses : une authentification machine à
machine, des endpoints de lecture, la création d'une soumission en brouillon,
et des webhooks sortants signés.

---

## 2. Prérequis découvert dans le code actuel

Ces points bloquent l'intégration et doivent être traités en premier.

### 2.1 Aucun champ `updated_at`

Les documents de `clients`, `quotes` et `invoices` portent `created_at` mais
pas `updated_at`. Sans ce champ, la resynchronisation incrémentale côté PFM
(« donne-moi ce qui a changé depuis telle date ») est impossible, et le filet
de sécurité prévu ne fonctionne pas.

À faire : écrire `updated_at` à chaque écriture sur ces trois collections
(création et modification), puis remplir rétroactivement les documents
existants avec la valeur de `created_at`.

### 2.2 Les soumissions n'ont pas de statut brouillon

`POST /api/quotes` force `"status": "pending"` (backend/server.py, autour de la
ligne 10800). Les factures connaissent `draft`, pas les soumissions.

À faire : accepter un statut `draft` pour les soumissions. Le défaut du
endpoint public existant **reste `pending`** — ne pas changer le comportement
actuel, qui est consommé par le frontend déployé. Vérifier ensuite que les
soumissions en `draft` sont exclues des tableaux de bord et des rapports, comme
le sont les factures en brouillon.

### 2.3 Les endpoints de lecture ne paginent pas

`GET /api/clients`, `/api/quotes` et `/api/invoices` retournent la collection
entière. Acceptable pour un frontend, pas pour une intégration qui grandira.

### 2.4 Render dort

Le backend FacturePro est sur le palier gratuit de Render : il s'endort après
15 minutes et le premier appel prend 30 à 60 secondes. Deux conséquences :

- PFM devra utiliser un délai d'attente généreux en appelant FacturePro.
- À l'inverse, PFM est aussi sur Render. Une livraison de webhook peut donc
  échouer simplement parce que la cible est froide. **Les tentatives répétées
  ne sont pas une amélioration optionnelle : sans elles, l'intégration perdra
  des événements dès le premier jour.**

---

## 3. Authentification par clé API

### 3.1 Modèle

Nouvelle collection `api_keys` :

| Champ | Type | Note |
|---|---|---|
| `id` | str (uuid4) | |
| `organization_id` | str | portée de la clé |
| `name` | str | libellé lisible, ex. « ProFireManager CRM » |
| `key_prefix` | str | 8 premiers caractères, affichés dans l'interface |
| `key_hash` | str | SHA-256 du secret complet |
| `scopes` | list[str] | codes de permission, voir 3.3 |
| `created_at` | str ISO | |
| `created_by_user_id` | str | |
| `last_used_at` | str ISO ou None | |
| `revoked_at` | str ISO ou None | une clé révoquée n'est jamais supprimée |

Format du secret : `fp_live_` suivi de 32 octets aléatoires en base64url. Le
secret complet n'est affiché **qu'une seule fois**, à la création. Seul le
hachage est stocké.

SHA-256 suffit ici, contrairement à un mot de passe : le secret a 256 bits
d'entropie, une fonction lente comme bcrypt n'apporte rien et coûterait à
chaque requête. En revanche, la comparaison doit être faite en temps constant
(`hmac.compare_digest`).

### 3.2 Transport

En-tête dédié : `X-API-Key: fp_live_...`

Ne pas réutiliser `Authorization: Bearer`, déjà utilisé par les JWT. Un en-tête
distinct évite toute ambiguïté dans `get_current_user` et rend impossible
qu'une clé API soit acceptée par erreur là où un JWT est attendu.

### 3.3 Principal et portée

Nouvelle dépendance FastAPI `get_api_principal`, **indépendante** de
`get_current_user`. Elle construit un objet de la même forme que `CurrentUser` :

- `organization_id` : celui de la clé
- `role` : `"api"`
- `permissions` : les `scopes` de la clé
- `id` : l'identifiant de la clé, pour la traçabilité

Scopes autorisés, et eux seuls :

```
clients:read    quotes:read    quotes:write    invoices:read
```

`team:manage`, `billing:manage`, `settings:write` et tout autre code ne doivent
**jamais** pouvoir être accordés à une clé API, même si l'appelant les demande
explicitement. Valider la liste à la création, en 400.

### 3.4 Point d'attention : la 2FA

`_enforce_org_mfa` bloque tout accès si l'organisation impose la 2FA et que
l'utilisateur ne l'a pas activée. Une clé API n'a pas de 2FA et serait donc
bloquée dès que cette option est activée.

Le contournement doit être **explicite et limité aux principals de type clé
API** — surtout pas un assouplissement général de `_enforce_org_mfa`, qui
ouvrirait un trou pour les vrais utilisateurs. Une clé API est un secret
long et révocable ; c'est son propre facteur d'authentification.

### 3.5 Limitation de débit

Appliquer une limitation de débit par clé **avant** la vérification du hachage,
pas après. Une limitation placée après l'authentification ne protège pas contre
l'essai systématique de clés invalides, puisque ces requêtes échouent avant
d'atteindre le compteur.

Ordre correct : identifier l'appelant par IP et par préfixe de clé → compter →
refuser en 429 si dépassement → seulement ensuite comparer le hachage.

### 3.6 Interface

Dans la page Réglages, une section « Clés API » réservée au rôle `owner` :
créer une clé (nom + cases à cocher pour les scopes), afficher le secret une
seule fois avec un avertissement clair, lister les clés existantes (préfixe,
scopes, dernière utilisation), révoquer.

Chaque création et chaque révocation doivent être écrites dans le journal
d'audit d'organisation existant (`/api/org/audit-logs`).

---

## 4. Endpoints de lecture

Nouveau préfixe versionné : `/api/v1/integration/`.

Ne pas exposer directement les endpoints existants. La forme de leur réponse
doit rester libre d'évoluer pour le frontend de FacturePro ; la surface
d'intégration, elle, est un contrat figé avec un client déployé qu'on ne
redéploie pas en même temps.

```
GET /api/v1/integration/clients
GET /api/v1/integration/quotes
GET /api/v1/integration/invoices
```

Paramètres communs :

| Paramètre | Défaut | Note |
|---|---|---|
| `updated_since` | aucun | date ISO 8601 ; filtre sur `updated_at` |
| `limit` | 100 | maximum 500 |
| `cursor` | aucun | pagination par curseur opaque |

Forme de réponse :

```json
{
  "data": [ { ... } ],
  "next_cursor": "..." ou null
}
```

L'enveloppe `{data, next_cursor}` est délibérée : elle permet d'ajouter des
métadonnées plus tard sans changer la forme de la réponse.

Champs à exposer, au minimum :

- **client** : `id`, `name`, `email`, `phone`, `address`, `city`,
  `postal_code`, `province`, `created_at`, `updated_at`
- **soumission** : `id`, `client_id`, `quote_number`, `status`, `issue_date`,
  `valid_until`, `subtotal`, `total_tax`, `total`, `currency`, `created_at`,
  `updated_at`, `external_ref`
- **facture** : `id`, `client_id`, `invoice_number`, `status`, `issue_date`,
  `due_date`, `subtotal`, `total_tax`, `total`, `currency`, `amount_paid`,
  `created_at`, `updated_at`

Ne pas exposer les lignes de détail (`items`) dans un premier temps : PFM n'en
a pas besoin et elles alourdissent le contrat.

Toute requête est scopée par l'`organization_id` **de la clé**, jamais par une
valeur venue du corps ou de l'URL de la requête.

---

## 5. Création d'une soumission en brouillon

```
POST /api/v1/integration/quotes
```

Scope requis : `quotes:write`.

Corps attendu :

```json
{
  "client_id": "...",
  "items": [ { "description": "...", "quantity": 1, "unit_price": 840.00 } ],
  "valid_until": "2027-01-31",
  "notes": "...",
  "external_ref": {
    "source": "profiremanager",
    "tenant_id": "...",
    "periode": "2027"
  }
}
```

Le statut créé est **toujours `draft`**, quoi que demande l'appelant. Une
soumission créée par l'API n'est jamais envoyée automatiquement : c'est
Guillaume qui l'ouvre, la vérifie et l'envoie depuis FacturePro.

### 5.1 Idempotence

PFM réessaiera en cas de délai d'attente dépassé — ce qui arrivera, vu le
réveil de Render. Sans idempotence, chaque réessai créerait une soumission de
plus.

Accepter un en-tête `Idempotency-Key`. Stocker dans une collection
`api_idempotency` la clé composite `(organization_id, idempotency_key)` avec la
réponse produite et un horodatage. Un rejeu dans les 24 heures retourne la
réponse d'origine sans rien créer. Nettoyer les entrées de plus de 7 jours.

### 5.2 `external_ref`

Ce champ est libre côté FacturePro : il est stocké tel quel et renvoyé dans les
lectures. Il permet à PFM de reconnaître ses propres soumissions et de ne pas
en produire deux pour la même période.

---

## 6. Webhooks sortants

### 6.1 Configuration

Collection `webhook_endpoints` : `id`, `organization_id`, `url`, `secret`,
`events` (liste), `actif`, `created_at`, `last_success_at`, `last_error`.

Configurable depuis la page Réglages : ajouter une URL, choisir les événements,
voir les dernières livraisons, en rejouer une.

### 6.2 Événements

```
client.created          client.updated
quote.created           quote.status_changed
invoice.created         invoice.status_changed        invoice.paid
```

### 6.3 Charge utile

```json
{
  "id": "evt_...",
  "type": "client.created",
  "created_at": "2026-09-26T14:03:11Z",
  "organization_id": "...",
  "data": { ... }
}
```

`data` contient le même objet que celui renvoyé par l'endpoint de lecture
correspondant. Cette symétrie évite à PFM d'avoir deux façons de lire la même
entité.

### 6.4 Signature

En-tête `X-FacturePro-Signature: t=<horodatage unix>,v1=<hmac hex>`.

Le HMAC-SHA256 porte sur la chaîne `<horodatage>.<corps brut>`, avec le
`secret` de l'endpoint comme clé. Le récepteur recalcule et compare en temps
constant, puis rejette si l'horodatage s'écarte de plus de 5 minutes de
l'heure courante — sans cette vérification, une requête interceptée pourrait
être rejouée indéfiniment.

### 6.5 Livraison et réessais

Ne jamais livrer de façon synchrone dans le gestionnaire de requête : une
cible lente ferait échouer la création du client dans FacturePro.

Collection `webhook_deliveries` : `id`, `endpoint_id`, `event_id`,
`payload`, `status` (`pending` / `sent` / `failed`), `attempts`,
`next_attempt_at`, `last_status_code`, `last_error`.

Le gestionnaire de requête se contente d'insérer une ligne `pending`. Un
processus d'arrière-plan reprend les livraisons dues. FacturePro n'a pas de
file de tâches aujourd'hui ; un fil d'arrière-plan simple ou APScheduler suffit
à ce volume.

Réessais : 1 min, 5 min, 30 min, 2 h, 6 h. Abandon après la cinquième
tentative, avec l'erreur conservée et visible dans l'interface.

Une livraison est considérée réussie sur toute réponse 2xx. Un 4xx autre que
408 et 429 est définitif : inutile de réessayer.

### 6.6 Test

```
POST /api/v1/integration/webhooks/{endpoint_id}/test
```

Envoie un événement `ping` signé. Indispensable pour diagnostiquer sans
attendre qu'un vrai client soit créé.

---

## 7. Ce que FacturePro ne doit pas faire

- **Ne pas envoyer** de soumission ni de facture au client final à la demande
  de PFM. PFM ne produit que des brouillons.
- **Ne pas modifier** le comportement des endpoints existants
  (`/api/clients`, `/api/quotes`, `/api/invoices`) : le frontend déployé les
  consomme. Les nouveautés vivent sous `/api/v1/integration/`.
- **Ne pas accepter** la création ou la modification de clients depuis PFM. La
  circulation est à sens unique.
- **Ne jamais journaliser** le secret complet d'une clé API ni le secret d'un
  endpoint de webhook.

---

## 8. Tests attendus

Fonctionnels :

- Clé valide, scope correct → 200.
- Clé révoquée → 401.
- Clé sans le scope demandé → 403.
- Clé de l'organisation A → ne voit aucune donnée de l'organisation B.
- Tentative d'accorder `team:manage` à une clé → 400.
- `updated_since` ne retourne que les documents modifiés après la date.
- Pagination : parcourir un jeu de données plus grand que `limit` ne saute ni
  ne duplique de document.
- `POST` de soumission avec le même `Idempotency-Key` deux fois → une seule
  soumission, réponses identiques.
- La soumission créée est en `draft` même si l'appelant demande `pending`.

Sécurité :

- Signature de webhook invalide → rejetée.
- Horodatage vieux de 10 minutes → rejeté.
- Limitation de débit atteinte avec une clé invalide → 429 avant toute
  comparaison de hachage.

Robustesse :

- Cible de webhook qui retourne 500 → livraison replanifiée, compteur de
  tentatives incrémenté.
- Cible qui retourne 410 → abandon immédiat, pas de réessai.

---

## 9. Découpage suggéré

Chaque étape est livrable et testable seule.

1. `updated_at` sur `clients`, `quotes`, `invoices` + remplissage rétroactif.
2. Clés API : modèle, dépendance, interface dans Réglages, audit.
3. Endpoints de lecture versionnés avec pagination et `updated_since`.
4. Statut `draft` pour les soumissions + création idempotente par l'API.
5. Webhooks : modèle, signature, file de livraison, réessais, interface.

Les étapes 1 à 3 débloquent déjà la lecture côté PFM. Les étapes 4 et 5 ne
sont nécessaires que pour les lots PFM ultérieurs.

---

## 10. À confirmer avec PFM avant de commencer

- L'URL exacte de l'endpoint de réception des webhooks côté PFM.
- Le fuseau et le format retenus pour les dates dans le contrat (proposition :
  ISO 8601 en UTC avec suffixe `Z`, PFM convertit pour l'affichage).
- Si PFM a besoin des lignes de détail (`items`) des soumissions et des
  factures, ou seulement des totaux.

---

## 11. Décisions prises (2026-09-27)

Les questions ouvertes du §10 sont tranchées. Cette section est la référence : en cas de
divergence avec les sections antérieures, c'est elle qui vaut.

### 11.1 Réponses du propriétaire

- **Format des dates** : ISO 8601 en UTC. PFM convertit pour l'affichage.
- **Lignes de détail (`items`)** : non exposées. PFM n'a besoin que des totaux.
- **URL du webhook côté PFM** : inconnue, elle arrive avec le lot 2 de PFM. Non bloquant,
  puisque l'URL vit dans `webhook_endpoints`.

### 11.2 `amount_paid` est CALCULÉ, non persisté

Constat : ce champ n'existe sur aucune facture, et le code dérive déjà le montant payé —
`_enrich_invoice` calcule `total_paid_cad = sum(payments[].amount_cad)`.

Décision : l'API le calcule avec la même formule. Le persister créerait une seconde source de
vérité pouvant diverger de `payments`, sans rien apporter : aucune facture ne porte de paiement
aujourd'hui, donc il n'y a même pas de coût de calcul à l'échelle actuelle.

### 11.3 Le curseur est un keyset `(updated_at, id)`, pas un décalage

Encodage : base64url d'un JSON `{"u": <updated_at>, "i": <id>}`. Opaque pour PFM, qui le renvoie
tel quel.

Pourquoi pas un décalage numérique : la liste bouge pendant le parcours. Un document modifié
entre deux pages change de position dans un tri par `updated_at`, ce qui fait **sauter** ou
**dupliquer** des documents avec un décalage. Un keyset est stable — il demande « ce qui vient
après cette position », pas « à partir du 200ᵉ ».

`id` départage les documents partageant la même `updated_at`, ce qui arrive : le remplissage
rétroactif de l'étape 1 a daté 339 documents avec leur `created_at`, et plusieurs partagent la
même seconde.

### 11.4 `province` n'existe pas sur les clients

Le §4 demande `province` pour les clients. Recensement des 71 documents : le champ est **absent
partout**. Les clients portent `country`, pas `province`.

Décision : `province` est exposé à `null`, pour que le contrat reste celui annoncé à PFM sans
inventer de donnée. Si PFM en a besoin, il faut d'abord ajouter le champ au formulaire client —
c'est un changement de produit, pas d'API.

### 11.5 Les 35 documents sans `organization_id`

Recensement : 7 clients, 14 soumissions, 14 factures n'ont pas de champ `organization_id`.
`migrate_organizations_v1` les a manqués.

Ils se répartissent en deux groupes :

| Groupe | Nombre | Utilisateur | Visible dans l'interface aujourd'hui |
|---|---|---|---|
| Attribuables | 30 | existe, org `a0dba47b…` | **oui**, via le repli `user_id` de `_org_scope` |
| Orphelins | 5 | supprimé, introuvable | non |

Décision : `migrate_integration_org_backfill_v1` pose `organization_id` sur les 30 attribuables,
en le lisant sur leur utilisateur. Les 5 orphelins ne sont pas touchés — aucune organisation ne
peut les revendiquer.

**Aucun changement de visibilité** : les 30 étaient déjà visibles par le repli `user_id`, ils le
resteront par le champ direct. Ce qui change, c'est qu'ils deviennent visibles à une requête
scopée strictement par `organization_id` — celle de l'API.

Pourquoi ne pas simplement reproduire le repli `user_id` dans l'API : pour une clé API,
`principal.id` est l'identifiant **de la clé**, pas d'un utilisateur. Le repli de `_org_scope`
matcherait donc zéro document. Corriger la donnée est plus sûr que contourner ce piège à chaque
requête.
