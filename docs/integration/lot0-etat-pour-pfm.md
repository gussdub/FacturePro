# Lot 0 — l'API FacturePro est en ligne. État et contrat pour PFM.

**Destinataire** : la session Claude Code du projet ProFireManager.
**Date** : 2026-09-27.
**Statut** : les cinq étapes du lot 0 sont livrées et déployées en production.

---

## 1. Ce qui est disponible

Base : `https://facturepro-backend-dkvn.onrender.com`

| Endpoint | Méthode | Scope requis |
|---|---|---|
| `/api/v1/integration/clients` | GET | `clients:read` |
| `/api/v1/integration/quotes` | GET | `quotes:read` |
| `/api/v1/integration/invoices` | GET | `invoices:read` |
| `/api/v1/integration/quotes` | POST | `quotes:write` |

Les webhooks sortants sont fonctionnels. Il manque uniquement **l'URL de réception côté PFM**,
qui se configure dans Réglages → Intégrations de FacturePro quand tu l'auras.

---

## 2. Authentification

En-tête dédié, **jamais** `Authorization: Bearer` :

```
X-API-Key: fp_live_...
```

Un JWT est explicitement refusé sur cette surface, et une clé API est refusée sur les endpoints
de session. Les deux chaînes sont séparées.

**Limitation de débit : 120 requêtes par minute**, comptée par (IP, préfixe de clé). Au-delà,
429. Elle s'applique **avant** la vérification de la clé, donc une clé invalide est aussi
limitée.

Codes : `401` clé absente, invalide ou révoquée · `403` scope manquant · `429` débit dépassé.

---

## 3. Lecture

Paramètres communs aux trois endpoints GET :

| Paramètre | Défaut | Note |
|---|---|---|
| `updated_since` | aucun | ISO 8601. Le suffixe `Z` **et** `+00:00` sont acceptés. Comparaison `>=`. |
| `limit` | 100 | Entre 1 et 500. Hors plage → `422`, jamais raboté en silence. |
| `cursor` | aucun | Opaque. À renvoyer tel quel. |

Réponse :

```json
{ "data": [ ... ], "next_cursor": "eyJ1IjoiMjAy..." }
```

`next_cursor` vaut `null` quand tu es au bout. **Algorithme de parcours** : appelle sans
`cursor`, traite `data`, réappelle avec le `next_cursor` reçu, jusqu'à ce qu'il soit `null`.

Le curseur est un *keyset* sur `(updated_at, id)`, pas un décalage numérique. Conséquence
utile pour toi : le parcours est **stable même si des documents sont modifiés pendant que tu
pagines**. Ni saut ni doublon. Ne fabrique pas de curseur toi-même, son contenu peut changer.

### Champs exposés

**client** — 10 champs
```
id, name, email, phone, address, city, postal_code, province, created_at, updated_at
```

**soumission** — 13 champs
```
id, client_id, quote_number, status, issue_date, valid_until,
subtotal, total_tax, total, currency, created_at, updated_at, external_ref
```

**facture** — 13 champs
```
id, client_id, invoice_number, status, issue_date, due_date,
subtotal, total_tax, total, currency, amount_paid, created_at, updated_at
```

Le contrat est une **liste fermée**. Aucun autre champ ne sortira, même si le schéma interne
de FacturePro en gagne. Tu peux t'appuyer dessus.

### Trois choses à savoir sur ces champs

1. **`province` est toujours `null` sur les clients.** Le champ n'existe sur aucun des 71
   clients en base — FacturePro ne le collecte pas au formulaire client. Il est exposé pour que
   le contrat soit stable si le champ arrive un jour. **Ne construis pas d'adresse postale
   complète en te fiant dessus.** Les clients portent un pays, non exposé pour l'instant : dis-le
   si tu en as besoin.
2. **`amount_paid` est calculé**, pas stocké. Il vaut la somme des paiements enregistrés. Il vaut
   `0` aujourd'hui pour toutes les factures, aucun paiement n'étant encore enregistré.
3. **Les lignes de détail (`items`) ne sont pas exposées**, par décision : tu n'as besoin que des
   totaux. Dis-le si ça change.

---

## 4. Création d'une soumission en brouillon

```
POST /api/v1/integration/quotes
X-API-Key: fp_live_...
Idempotency-Key: <une chaîne unique par tentative logique>
Content-Type: application/json
```

```json
{
  "client_id": "...",
  "items": [ { "description": "Renouvellement 2027", "quantity": 1, "unit_price": 840.00 } ],
  "valid_until": "2027-01-31",
  "notes": "...",
  "external_ref": { "source": "profiremanager", "tenant_id": "...", "periode": "2027" }
}
```

Réponse `201`, au format d'une soumission lue (les 13 champs ci-dessus).

**Points fermes :**

- Le statut créé est **toujours `draft`**. Si tu envoies `"status": "pending"`, il est ignoré.
  Une soumission créée par l'API n'est **jamais** envoyée au client final : c'est Guillaume qui
  l'ouvre, la vérifie et l'envoie depuis FacturePro.
- **Les totaux sont calculés par FacturePro** depuis tes `items`. Si tu envoies un `total`, il est
  ignoré. FacturePro fait foi sur les taxes.
- `client_id` doit exister **dans l'organisation de la clé**, sinon `404`. Tu ne peux pas créer de
  client : la circulation est à sens unique.
- `items` vide → `422`.
- `external_ref` est **libre**. Stocké tel quel, relu à l'identique, y compris les objets
  imbriqués. Sers-t'en pour reconnaître tes propres soumissions et ne pas en produire deux pour la
  même période.

### L'idempotence n'est pas optionnelle

**Envoie toujours `Idempotency-Key`.** Ce n'est pas une précaution théorique : le backend
FacturePro dort après 15 minutes d'inactivité et le premier appel prend **30 à 60 secondes**. Tu
vas dépasser ton délai d'attente et réessayer. Sans cette en-tête, chaque réessai crée une
soumission de plus, et Guillaume trouve trois brouillons identiques à trier.

Un rejeu dans les **24 heures** avec la même clé renvoie la réponse d'origine **sans rien créer**.
La clé est cloisonnée par organisation.

Utilise une clé stable par intention métier — par exemple
`pfm-renouvellement-<tenant_id>-<periode>` — et non un UUID tiré à chaque appel, sinon un réessai
n'est pas reconnu comme tel.

---

## 5. Webhooks

FacturePro pousse vers l'URL que tu fourniras. Événements disponibles :

```
client.created      client.updated
quote.created       quote.status_changed
invoice.created     invoice.status_changed     invoice.paid
```

`invoice.paid` est émis **en plus** de `invoice.status_changed` : tu peux t'abonner au seul cas
qui t'intéresse.

Charge utile :

```json
{
  "id": "evt_...",
  "type": "client.created",
  "created_at": "2026-09-27T14:03:11.123456+00:00",
  "organization_id": "...",
  "data": { ... }
}
```

`data` est **exactement** l'objet que renvoie l'endpoint de lecture correspondant. Tu peux donc
réutiliser le même code de désérialisation pour les deux chemins.

En-têtes : `X-FacturePro-Signature` et `X-FacturePro-Event` (l'identifiant d'événement, utile pour
dédupliquer).

### Vérification de la signature — à implémenter exactement ainsi

```
X-FacturePro-Signature: t=1790000000,v1=<hmac hex 64 caractères>
```

1. Découpe l'en-tête sur `,` puis sur `=` pour obtenir `t` et `v1`.
2. Recalcule : `HMAC-SHA256(secret, f"{t}.{corps_brut}")` en hexadécimal.
3. Compare à `v1` **en temps constant** (`hmac.compare_digest` en Python,
   `crypto.timingSafeEqual` en Node).
4. **Rejette si `|maintenant - t| > 300 secondes.** Sans cette vérification, une requête
   interceptée peut être rejouée indéfiniment.

⚠️ Le HMAC porte sur le **corps brut reçu**, octet pour octet. Ne le désérialise pas puis ne le
re-sérialise pas avant de vérifier : un seul espace de différence invalide la signature. En
Express, lis le corps avec `express.raw()` ou conserve le buffer brut avant `JSON.parse`.

### Réessais — et une limite d'hébergement à connaître

Calendrier : **1 min, 5 min, 30 min, 2 h, 6 h**. Abandon après la cinquième tentative.

- Toute réponse **2xx** vaut succès.
- **408 et 429** sont réessayés.
- Tout autre **4xx est définitif** : FacturePro abandonne immédiatement. Ne renvoie donc pas 400
  ou 422 pour une erreur transitoire de ton côté — renvoie 500 si tu veux être réessayé.
- Absence de réponse, timeout, 5xx : réessayé.

⚠️ **Ces délais sont des planchers, pas des garanties.** La boucle d'envoi de FacturePro ne tourne
que pendant que son instance Render est éveillée, et elle s'endort après 15 minutes. Un réessai
planifié à +30 min peut donc partir bien plus tard.

**Conséquence pour ta conception : garde le bouton de resynchronisation manuelle prévu.** Il n'est
pas un filet de sécurité théorique, c'est le mécanisme de rattrapage réel. Une resynchronisation
avec `updated_since` est idempotente de ton côté et rattrape tout événement perdu.

### Ton endpoint doit être idempotent

Le même événement peut arriver deux fois : un réessai part dès que FacturePro n'a pas lu de 2xx,
même si tu avais bien traité la requête. Déduplique sur `id` (`evt_...`), pas sur le contenu.

---

## 6. Ce que FacturePro ne fera pas

- **N'envoie rien au client final** à ta demande. Tu ne produis que des brouillons.
- **N'accepte ni création ni modification de client.** Sens unique.
- **N'expose pas les lignes de détail.**
- Les endpoints existants (`/api/clients`, `/api/quotes`, `/api/invoices`) **ne sont pas** ton
  contrat. Ils servent le frontend de FacturePro et leur forme peut changer sans préavis. Utilise
  exclusivement `/api/v1/integration/`.

---

## 7. Deux pièges d'intégration à traiter dès ta première ligne de code

1. **Délai d'attente généreux.** 60 secondes minimum sur le premier appel d'une série.
   Render dort. Un timeout de 10 secondes échouera systématiquement après une période
   d'inactivité.
2. **Dates en UTC.** Tout ce que FacturePro renvoie est en UTC, suffixé `+00:00`. Convertis pour
   l'affichage, ne suppose pas le fuseau local. En envoi, `Z` et `+00:00` sont tous deux acceptés.

---

## 8. Ce dont j'ai besoin de toi

1. **L'URL de ton endpoint de réception**, en `https://` — le `http://` simple est refusé à la
   configuration, le corps contenant des renseignements de clients.
2. **Confirmer que les 10 / 13 / 13 champs te suffisent.** Si tu as besoin de `country` sur les
   clients ou des lignes de détail, dis-le maintenant : ajouter un champ est additif et sans
   risque, en retirer un casserait ton client déjà déployé.
3. **Me dire si `province` te manque vraiment.** Si oui, c'est un changement de produit dans
   FacturePro — ajouter le champ au formulaire client — pas un changement d'API.
