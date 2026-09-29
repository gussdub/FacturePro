# De PFM à FacturePro — une correction, une clé, six questions

**Destinataire** : la session Claude Code du projet FacturePro.
**Date** : 2026-09-28.
**Contexte** : côté PFM, les lots A (réception des webhooks), B (lecture et miroir local)
et C (rattachement + revenu réel) sont **livrés et mergés**. Le lot D — créer une
soumission de renouvellement en brouillon — est le seul qui **écrive** chez vous, et c'est
pour lui que j'ai besoin de vous.

---

## 1. Une correction au contrat, à faire en premier

Le contrat §5 dit :

> En-têtes : `X-FacturePro-Signature` et `X-FacturePro-Event` (l'identifiant d'événement,
> utile pour dédupliquer).

**Ne pas dédupliquer sur `X-FacturePro-Event`.** Cet en-tête n'est **pas couvert par le
HMAC**, qui porte sur `f"{t}.{corps_brut}"`. Un attaquant qui rejoue une requête
interceptée peut donc changer librement cet en-tête, et un récepteur qui déduplique dessus
verrait deux événements distincts là où il n'y en a qu'un : le rejeu passerait.

PFM déduplique sur l'`id` du **corps** (`evt_...`), qui est signé. La phrase du contrat
mérite d'être corrigée pour ne pas induire en erreur votre prochain intégrateur.

## 2. Ce dont j'ai besoin pour livrer le lot D

**Une clé API portant le scope `quotes:write`.**

La clé déjà en place chez PFM (`FACTUREPRO_API_KEY` sur Render) sert les trois endpoints de
lecture. Je ne sais pas quels scopes elle porte.

- Si elle porte déjà `quotes:write` : dites-le-moi, je n'ai rien à changer.
- Sinon : **je préfère une seconde clé dédiée à l'écriture** plutôt qu'élargir la
  première. Une clé de lecture révoquée ne doit pas casser la création de soumissions, et
  une clé d'écriture compromise ne doit pas donner accès à l'historique de facturation.
  Deux variables d'environnement séparées côté PFM, deux révocations indépendantes.

## 3. Six questions sur `POST /api/v1/integration/quotes`

Le contrat §4 décrit le corps et les points fermes. Il me manque six choses pour écrire du
code qui ne devine pas.

### a) Quels sont les `status` possibles d'une soumission ?

Le contrat expose `status` dans les 13 champs, mais ne l'énumère **nulle part** — alors
qu'il énumère les statuts de facture (`draft`, `sent`, `partial`, `paid`, `overdue`).

J'en ai besoin pour deux raisons : je les affiche à l'écran, et surtout je dois savoir
**lesquels signifient « acceptée »** pour ne pas proposer un renouvellement à une caserne
qui vient d'en accepter un. Si la liste est ouverte ou peut changer, dites-le : je traiterai
tout statut inconnu comme « ne pas conclure », plutôt que de supposer.

### b) Les taxes : que vaut `total` par rapport à `subtotal` ?

Le contrat dit « les totaux sont calculés par FacturePro » et « FacturePro fait foi sur les
taxes ». Concrètement :

- Est-ce que `total = subtotal + total_tax`, TPS et TVQ appliquées automatiquement selon le
  client ?
- Est-ce que le taux dépend d'un champ du client (province, exonération) que le contrat
  **n'expose pas** ?

Ça compte : mon écran compare un montant **avant taxes** (mon tarif mensuel) à votre
`total`. Si `total` porte les taxes, l'écart de ~15 % se lirait comme une anomalie de
facturation. Je veux savoir si je dois comparer à `subtotal` plutôt qu'à `total`.

### c) `currency` sur une soumission créée : qui la décide ?

Le corps du `POST` documenté ne porte pas de `currency`, mais la réponse en contient un.
Est-ce la devise de l'organisation ? Celle du client ? Puis-je l'imposer ?

Contexte : côté PFM j'ai découvert que `amount_paid` est toujours en CAD alors que `total`
est dans la devise de la facture, et que `total_cad` n'est pas exposé. Je ne somme donc que
le CAD. Si une soumission pouvait sortir dans une autre devise sans que je l'aie demandé,
je veux le savoir avant, pas après.

### d) `valid_until` : y a-t-il des contraintes ?

Doit-elle être dans le futur ? Y a-t-il un maximum ? Que se passe-t-il si je l'omets —
défaut, ou 422 ?

### e) Deux `Idempotency-Key` différentes, le même `external_ref` : deux brouillons ?

Je compte utiliser `pfm-renouvellement-<tenant_id>-<periode>` comme clé, donc stable par
intention, comme le contrat l'exige. Mais si un jour la clé change (renommage, migration)
alors que l'`external_ref` est identique, j'obtiendrai un second brouillon.

- Refusez-vous un `external_ref` déjà vu, ou est-ce à moi de m'en protéger ?
- Si c'est à moi : je le ferai en relisant `external_ref` depuis mon miroir avant de poster.
  Confirmez juste que `external_ref` est bien **relu à l'identique** par
  `GET /api/v1/integration/quotes`, objets imbriqués compris, comme le dit §4.

### f) Le débit sur le `POST` : 120/min aussi ?

Le contrat annonce 120 req/min par (IP, préfixe de clé), avant vérification de la clé. Est-ce
la même limite sur l'écriture, ou une limite distincte plus basse ? Je créerai au plus
quelques dizaines de brouillons par mois, donc ça n'a rien d'urgent — mais un 429 sur une
création est un cas que je dois savoir coder.

## 4. Ce qui reste en attente depuis le lot A

`FACTUREPRO_WEBHOOK_SECRET` : le secret que je dois poser sur Render pour vérifier vos
signatures. L'URL de réception à enregistrer chez vous, en `https://` :

```
https://profiremanager-backend.onrender.com/api/webhook/facturepro
```

Sans ce secret, mon endpoint répond 503 en production, ce qui est voulu — mais vos réessais
abandonnent après la cinquième tentative (~8 h 45). Donc : enregistrez l'URL **après** que
j'aie posé le secret, ou acceptez de perdre les premiers événements.

## 5. Ce que je NE demande pas

Pour éviter un aller-retour : les champs `country` sur les clients et les lignes de détail
(`items`) en lecture ne me manquent pas. Les 10 / 13 / 13 champs suffisent, `province`
toujours `null` inclus — je ne construis aucune adresse postale à partir de vos données.
