# Correctif facturation : abonnement mensuel récurrent — design

**Date :** 2026-09-14
**Statut :** design approuvé par le propriétaire, prêt pour le plan d'implémentation

---

## 1. Problème

Les CGU publiées (art. 5, version 2026-09-14) annoncent un **abonnement mensuel de 15 $ CAD renouvelé
automatiquement**. Le code encaisse autre chose.

Constats vérifiés dans `backend/server.py` :

| Fait | Preuve |
|---|---|
| Paiement **unique**, pas un abonnement | `stripe.checkout.Session.create(..., mode="payment")` (l. ~13014) |
| Aucune notion d'abonnement Stripe | **0** occurrence de `stripe.Subscription`, `customer.subscription`, `invoice.payment_succeeded` |
| Le webhook ne traite qu'un seul événement | `if event["type"] == "checkout.session.completed"` |
| `active` ne porte **aucune date d'expiration** | `org_update = {"subscription_status": "active", "subscription_started_at": ...}` |
| La garde ne peut pas expirer un `active` | `_check_subscription_active` (l. ~2278) ne calcule `expired` que pour `sub_status == "trial"` |

**Conséquence :** un abonné paie 15 $ une fois et conserve un accès permanent, sans réfacturation.
Et si un jour un abonnement Stripe était résilié, FacturePro ne l'apprendrait jamais.

### La nature réelle du défaut

Ce n'est pas « Stripe est mal configuré ». C'est que **l'accès ne dépend d'aucune date** :
`subscription_status` est un booléen éternel. Remplacer ce booléen par un autre booléen alimenté
par webhook reproduirait le même défaut dès le premier webhook manqué. Le correctif doit donc
ancrer l'accès sur une **date qui expire d'elle-même**.

### État de la base (mesuré, pas supposé)

```
organisations : 83   (82 « trial », 1 « active »)
utilisateurs  : 77
transactions payment_status="paid" : 0
```

La seule org `active` appartient à `gussdub@gmail.com` (ProFireManager), qui figure dans
`EXEMPT_USERS` — elle n'a ni `stripe_customer_id` ni `subscription_started_at`, donc le webhook ne
l'a jamais touchée.

**Il n'existe aucun client payant.** Aucune migration de droits acquis n'est requise, et le risque
de verrouiller un abonné existant est nul. C'est ce qui rend ce correctif praticable sans phase de
transition.

> Observation hors périmètre, à considérer séparément : 82 essais, 0 conversion, et le chemin de
> paiement n'a donc jamais été exercé en production. Le flux livré ici sera le **premier vrai
> paiement** du produit.

---

## 2. Décisions prises

| Décision | Choix | Motif |
|---|---|---|
| Gestion de l'abonnement par l'abonné | **Portail client Stripe hébergé** | Surface minimale à coder et à maintenir, et seule option couvrant aussi le **changement de carte** et l'**accès aux factures** — qu'un bouton maison ou une résiliation par courriel laisseraient manquants. |
| Modèle de garde d'accès | **Date de fin de période + grâce de 7 jours** | Échoue du côté sûr : un webhook manqué ne redonne pas un accès éternel, il se ferme tout seul. Stripe retente ses webhooks pendant ~3 jours, donc 7 jours couvrent largement une panne sans punir un bon payeur. |

---

## 3. Pièges techniques vérifiés

Ces points ont été vérifiés contre la bibliothèque **réellement installée**, pas de mémoire. Ils
sont la raison principale d'écrire cette spec.

### 3.1 `current_period_end` n'est plus sur l'abonnement

Version installée : **stripe 15.3.0**, version d'API par défaut **`2026-06-24.dahlia`**.

```
grep "current_period_end" stripe/_subscription.py       -> AUCUN RÉSULTAT
grep "current_period_end" stripe/_subscription_item.py  -> current_period_end: int
```

Le champ a **déménagé** de `Subscription` vers `SubscriptionItem`. L'accès correct est
`subscription["items"]["data"][i]["current_period_end"]`.

**Pourquoi c'est critique :** écrire `subscription.current_period_end` — le motif classique que
produit n'importe quel tutoriel — renverrait `None`. L'organisation serait alors `active` **sans
date de fin**, donc **bloquée immédiatement après avoir payé** par la règle §4.3 de ce design.
Le symptôme serait « j'ai payé et je n'ai plus accès », soit le pire cas possible.

**Règle retenue :** prendre le **maximum** des `current_period_end` de tous les items (un
abonnement peut en porter plusieurs), et traiter l'absence de toute valeur comme une **erreur
explicite** — jamais comme un zéro silencieux.

### 3.2 `stripe` n'est pas épinglé dans `requirements.txt`

La ligne 12 est `stripe`, sans version. Or ce correctif **dépend de la version d'API**, comme §3.1
le démontre : un redéploiement qui installerait une version majeure différente pourrait déplacer
à nouveau le champ et casser la facturation en silence.

**Décision :** épingler `stripe` dans ce même commit. Pour du code qui encaisse de l'argent, une
dépendance non épinglée est un risque, pas une commodité.

### 3.3 Les événements d'abonnement ne portent pas les métadonnées du checkout

`checkout.session.completed` transporte `metadata.organization_id` (posé par
`create_subscription_checkout`). Les événements `customer.subscription.*` **ne le transportent
pas** : ils portent les métadonnées de l'**abonnement**, qui est un autre objet.

**Deux mesures, complémentaires :**
1. poser `subscription_data={"metadata": {...}}` à la création du checkout, pour que l'abonnement
   porte lui aussi `organization_id` ;
2. router malgré tout par `stripe_subscription_id` puis `stripe_customer_id` stockés en base — la
   métadonnée sert de filet, pas de mécanisme principal.

### 3.4 `billing_portal` est disponible

`stripe.billing_portal.Session.create` existe dans 15.3.0. Vérifié.

---

## 4. Conception

### 4.1 Checkout

`mode="subscription"`, avec un `price_data` **inline** portant `recurring: {"interval": "month"}`.

Aucun objet `Price` n'est créé dans le tableau de bord Stripe : cela évite une étape manuelle et
une dérive de configuration entre les modes test et production. `SUBSCRIPTION_PRICE_CAD` reste la
source unique du prix (15,00 $ CAD).

Ajouts à la session : `customer_email` (Stripe crée le Customer et pré-remplit le formulaire) et
`subscription_data.metadata` (cf. §3.3).

### 4.2 État persisté sur `db.organizations`

Champs **additifs**. Aucun champ existant ne change de signification, à ceci près que `active`
s'accompagne désormais d'une date d'expiration.

| Champ | Type | Rôle |
|---|---|---|
| `subscription_status` | str | `trial` / `active` / `past_due` / `canceled` / `suspended` |
| `subscription_current_period_end` | str ISO 8601 | **la garde d'accès** |
| `stripe_customer_id` | str | routage des webhooks, ouverture du portail |
| `stripe_subscription_id` | str | routage des webhooks |
| `terminated_at` | str ISO 8601 | fin réelle de l'abonnement — **champ dont la purge de rétention Loi 25 a besoin** |

`subscription_started_at` est conservé tel quel (déjà écrit par le code actuel).

### 4.3 La garde d'accès

`_check_subscription_active(org, user)` est réécrite dans cet ordre strict :

1. **Compte exempté** (`user["email"] in EXEMPT_USERS`) → accès. **En premier et sans condition** :
   le propriétaire ne doit jamais pouvoir se verrouiller hors de son propre produit.
2. `trial` → accès jusqu'à `trial_ends_at` (comportement actuel, inchangé).
3. `active`, `past_due`, `canceled` → accès jusqu'à
   `subscription_current_period_end` **+ 7 jours**.
   - `past_due` conserve l'accès pendant la période déjà payée : Stripe est en train de retenter le
     prélèvement, l'abonné n'est pas fautif.
   - `canceled` conserve l'accès jusqu'à la fin de la période **déjà payée** — c'est ce que la CGU
     art. 10 promet (« la résiliation prend effet à la fin de la période mensuelle en cours »).
4. `suspended` → **aucun accès**, quelle que soit la date de fin. C'est la différence entre
   `suspended` et `canceled` : le second a payé sa période en cours, le premier non.
5. **`active` sans `subscription_current_period_end` → aucun accès (402).**

Le point 5 est l'invariant central de ce design. Un état qui accorde l'accès sans porter de date
ferait revenir le défaut par la porte arrière. Aucune ligne en base n'est dans ce cas aujourd'hui
(le seul `active` est exempté et sort au point 1), donc cette règle ne casse rien et ferme
définitivement la classe de bug.

Tout statut inconnu (valeur future de Stripe, donnée corrompue) → **aucun accès**, et une trace
journalisée. Fail-closed par défaut.

### 4.4 Cartographie des statuts Stripe

Stripe définit **8** statuts. Les cartographier tous est obligatoire : un statut non traité serait
un trou silencieux.

| Statut Stripe | Notre statut | Accès | Motif |
|---|---|---|---|
| `active` | `active` | oui, jusqu'à fin + 7 j | nominal |
| `trialing` | `active` | oui, jusqu'à fin + 7 j | essai géré par Stripe (non utilisé aujourd'hui, mais mappé) |
| `past_due` | `past_due` | oui, jusqu'à fin + 7 j | Stripe retente ; période déjà payée |
| `canceled` | `canceled` + `terminated_at` | oui, jusqu'à fin + 7 j | période déjà payée (CGU art. 10) |
| `incomplete_expired` | `suspended` + `terminated_at` | **non** | premier paiement jamais abouti : aucune période n'a été payée, donc aucun accès à préserver. Mappé sur `suspended` et **non** sur `canceled`, car `canceled` accorde l'accès jusqu'à la fin de la période payée (§4.3 point 3) — ce qui serait faux ici. `terminated_at` est tout de même posé : l'abonnement est terminal, et la purge de rétention doit pouvoir le dater. |
| `incomplete` | `suspended` | **non** | premier paiement jamais abouti |
| `unpaid` | `suspended` | **non** | Stripe a épuisé ses tentatives |
| `paused` | `suspended` | **non** | collecte suspendue, aucun paiement en cours |
| *(valeur future inconnue)* | `suspended` | **non** | fail-closed + log |

### 4.5 Webhooks

Trois handlers s'ajoutent à `checkout.session.completed` dans `POST /api/webhook/stripe`.

| Événement | Effet |
|---|---|
| `checkout.session.completed` | lit `session.subscription`, récupère l'abonnement, applique §4.4 et pose `stripe_customer_id` / `stripe_subscription_id` / la date de fin |
| `customer.subscription.updated` | applique §4.4 et rafraîchit la date de fin — couvre `past_due`, la résiliation programmée (`cancel_at_period_end`) et la réactivation |
| `customer.subscription.deleted` | `canceled` + `terminated_at` |

**Idempotence.** Stripe rejoue ses événements. Les `$set` de statut et de date sont idempotents par
nature. `terminated_at` est en revanche écrit **uniquement s'il est absent** : un `deleted` rejoué
ne doit pas repousser la date, sinon il repousse d'autant la purge de rétention.

**Ordre d'arrivée.** Les webhooks peuvent arriver dans le désordre. La date de fin est donc écrite
sans condition à chaque événement (la valeur la plus récente reçue de Stripe fait autorité), tandis
que `terminated_at` est monotone (première écriture seulement).

### 4.6 Portail client

`POST /api/subscription/portal`, permission `billing:manage` (comme `create-checkout`).

Appelle `stripe.billing_portal.Session.create(customer=<stripe_customer_id>, return_url=...)` et
renvoie l'URL. Renvoie **409** si l'organisation n'a pas encore de `stripe_customer_id` (elle n'a
jamais souscrit) — message explicite, pas une erreur générique.

Côté frontend : un bouton « Gérer mon abonnement » dans `SubscriptionPage`, affiché uniquement
quand un `stripe_customer_id` existe.

---

## 5. Gestion d'erreur

- Secret de webhook absent → **500, fail-closed**. Acquis du correctif P0, conservé tel quel.
- Type d'événement non traité → **200** et ignoré. Renvoyer une erreur ferait retenter Stripe
  indéfiniment.
- Événement concernant un client ou un abonnement introuvable en base → **200** + log, pas de 500,
  pour la même raison.
- Aucun secret, aucune clé d'API, aucun identifiant de carte journalisé. `str(e)` interdit dans les
  logs Stripe (règle déjà en vigueur dans le fichier).
- Échec de `Subscription.retrieve` lors d'un `checkout.session.completed` → l'organisation **n'est
  pas activée**, et l'événement est journalisé. Mieux vaut un abonné qui doit rafraîchir qu'un
  `active` sans date, qui serait de toute façon refusé par §4.3 point 5.

---

## 6. Tests

Suite : `backend/tests/test_subscription_recurring.py`. `stripe.Webhook.construct_event` est
monkeypatché, comme dans `test_security_p0_fixes.py`. Aucun appel réseau à Stripe.

**Garde d'accès — le cœur :**
1. accès **autorisé** à `current_period_end` + 6 jours ;
2. accès **refusé** à `current_period_end` + 8 jours ;
3. `active` **sans** `subscription_current_period_end` → **refusé** (invariant §4.3 point 5) ;
4. compte exempté → accès même avec un statut `suspended` et une date échue ;
5. `trial` non échu → accès (non-régression) ;
6. statut inconnu → refusé.

**Cartographie :** les 8 statuts Stripe produisent le statut interne attendu (test paramétré).

**Webhooks :**
7. `checkout.session.completed` → `active`, date de fin posée, `stripe_customer_id` et
   `stripe_subscription_id` posés ;
8. la date de fin est bien lue depuis **`items.data[].current_period_end`**, et un objet
   d'abonnement de l'**ancienne** forme (champ à la racine) ne doit **pas** produire une date —
   test de non-régression du piège §3.1 ;
9. plusieurs items → le **maximum** est retenu ;
10. `customer.subscription.updated` vers `past_due` → statut mis à jour, accès conservé ;
11. `customer.subscription.deleted` → `canceled` + `terminated_at` ;
12. `deleted` **rejoué** → `terminated_at` **inchangé** ;
13. événement pour un client inconnu → **200**, aucune écriture ;
14. type d'événement inconnu → **200**.

**Checkout et portail :**
15. la session est créée en `mode="subscription"` avec `recurring.interval == "month"` ;
16. `subscription_data.metadata.organization_id` est présent ;
17. portail sans `stripe_customer_id` → **409**.

**Vérification par mutation** (discipline adoptée après les régressions vertes-mais-cassées de
cette série) : retirer la grâce, lire `current_period_end` à la racine de l'abonnement, supprimer
la règle §4.3 point 5, et rendre `terminated_at` non monotone — chacune doit faire échouer au moins
un test.

---

## 7. Hors périmètre

Délibérément exclus de ce commit :

- **La purge de rétention Loi 25** — commit suivant, que `terminated_at` débloque enfin.
- Proraration, paliers tarifaires, facturation annuelle, coupons, taxes automatiques Stripe Tax.
- Courriels de relance en cas d'échec de paiement (« dunning »). La CGU n'en promet aucun ; Stripe
  envoie déjà ses propres avis si l'option est activée dans le tableau de bord.
- Reconquête des 82 essais expirés : décision commerciale, pas un correctif technique.

---

## 8. Ce qui ne peut pas être vérifié depuis le dépôt

La logique est entièrement testable hors ligne, mais **l'aller-retour réel avec Stripe ne l'est
pas**. Devront être exécutés par le propriétaire, en **mode test** :

1. un passage en caisse complet avec la carte de test `4242 4242 4242 4242` ;
2. la réception effective de `checkout.session.completed` par le webhook de production ;
3. une résiliation depuis le portail client, et la réception de `customer.subscription.deleted` ;
4. **l'ajout des trois nouveaux types d'événements à l'endpoint de webhook dans le tableau de bord
   Stripe** — sans cette configuration, les handlers ne seront jamais appelés et l'abonnement
   paraîtra fonctionner tout en ne se résiliant jamais. C'est le point de configuration le plus
   facile à oublier et le plus silencieux.

Une marche à suivre sera fournie au moment de la livraison.

---

## 9. Point de retour arrière

Le changement est additif côté données : aucune donnée métier existante n'est mutée. Un retour
arrière consiste à redéployer le commit précédent ; les champs ajoutés sur `db.organizations`
deviennent alors inertes et sans effet. Aucun point de non-retour.
