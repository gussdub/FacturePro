# ÉFVP — Communication de renseignements personnels à l'extérieur du Québec

**FacturePro inc.** — 240, chemin Ostiguy, Shefford (Québec) J2M 2A7
**Responsable de la protection des renseignements personnels :** Guillaume Dubeau
**Version :** 2026-09-14 · **Statut : CANEVAS À COMPLÉTER ET À VALIDER**

> **Ce document est interne.** Il ne doit pas être publié. Il est destiné à être conservé et
> produit sur demande de la Commission d'accès à l'information (CAI) ou d'un abonné.

---

## 0. Ce qu'il reste à faire (à remplir par le responsable)

Ce canevas est prérempli avec ce qui est **vérifiable dans le code**. Les cases ci-dessous exigent
une information ou une décision que seul le responsable détient. **Tant qu'elles ne sont pas
remplies, l'ÉFVP n'est pas réalisée**, et la politique de confidentialité ne doit pas affirmer
qu'elle l'est (elle dit actuellement « en cours de réalisation », ce qui est exact).

- [ ] **Région exacte du cluster MongoDB Atlas** `facturepro-production` (console Atlas → Project →
      Cluster → Configuration). Joindre une capture. *Hypothèse de travail retenue : États-Unis.*
- [ ] **Palier de chiffrement au repos** confirmé chez Atlas (et chez Render pour les journaux).
- [ ] **Entente écrite / DPA** obtenue et archivée pour chacun des 7 destinataires du tableau §3
      (art. 17 al. 2 : la communication « doit faire l'objet d'une entente écrite »).
- [ ] **Rétention zéro (ZDR) activée chez Anthropic.** Sans ZDR, les images de reçus **et les
      relevés bancaires** peuvent être conservés par le fournisseur — ce qui change l'évaluation
      du risque au §3.6.
- [ ] **Conclusion signée et datée** pour chaque destinataire (§4).
- [ ] **Révision par un conseiller juridique du Québec** (voir l'avertissement au §6).

---

## 1. Fondement légal

L'art. 17 de la *Loi sur la protection des renseignements personnels dans le secteur privé*
(RLRQ, c. P-39.1) prévoit :

> Avant de communiquer à l'extérieur du Québec un renseignement personnel, la personne qui exploite
> une entreprise doit procéder à une évaluation des facteurs relatifs à la vie privée. Elle doit
> notamment tenir compte des éléments suivants : 1° la sensibilité du renseignement; 2° la finalité
> de son utilisation; 3° les mesures de protection, y compris celles qui sont contractuelles, dont
> le renseignement bénéficierait; 4° le régime juridique applicable dans l'État où ce renseignement
> serait communiqué, notamment les principes de protection des renseignements personnels qui y sont
> applicables.

L'alinéa 2 ajoute que la communication ne peut s'effectuer que si l'évaluation démontre une
protection adéquate, et qu'elle **doit faire l'objet d'une entente écrite**. L'alinéa 3 étend
expressément l'obligation au cas de FacturePro :

> Il en est de même lorsque la personne qui exploite une entreprise confie à une personne ou à un
> organisme à l'extérieur du Québec la tâche de recueillir, d'utiliser, de communiquer ou de
> conserver pour son compte un tel renseignement.

**Attention à la confusion de citation.** L'art. 3.3 de la même loi impose une ÉFVP distincte pour
tout *projet d'acquisition, de développement ou de refonte d'un système d'information ou de
prestation électronique de services*. Il s'applique aussi à FacturePro, mais comme obligation
**séparée** — ce n'est pas le fondement du transfert hors Québec. Le guide ÉFVP de la CAI
distingue explicitement les deux (sections 7.1 pour l'art. 17, 7.2 pour l'art. 3.3). La politique
de confidentialité citait l'art. 3.3 à tort; corrigé le 2026-09-14.

**Sources :** texte officiel de P-39.1 sur `legisquebec.gouv.qc.ca` ; guide ÉFVP de la CAI
(`cai.gouv.qc.ca`), sections 7.1 et 7.2.

---

## 2. Catégories de renseignements personnels en jeu

| Catégorie | Contenu | Personne concernée | Sensibilité (app.) |
|---|---|---|---|
| Identité d'abonné | courriel, nom d'entreprise, rôle | l'abonné | Faible |
| Authentification | mot de passe **haché** (bcrypt), secret TOTP, codes de secours **hachés** | l'abonné | **Élevée** (secret TOTP en clair au repos — cf. §5) |
| Clients de l'abonné | nom, courriel, téléphone, adresse, numéros fiscaux | **tiers** | Moyenne |
| Employés de l'abonné | nom, courriel, téléphone, n° d'employé, département | **tiers** | Moyenne |
| Documents d'affaires | factures, devis, dépenses, taxes | abonné + tiers | Moyenne |
| Images de reçus | photo/PDF d'un reçu, possiblement un nom de commerce et un lieu | abonné + tiers | Moyenne |
| **Relevés bancaires** | **ensemble des opérations, montants, contreparties, soldes** | abonné + tiers | **Élevée** |
| Carnet de route | lieu de départ, lieu d'arrivée, motif, distance, personne | abonné/employé | **Élevée** (données de déplacement) |
| Journaux d'audit | courriel, id, **adresse IP**, agent utilisateur, action, cible | l'abonné | Moyenne |
| Paiement | courriel, id de session Stripe — **jamais le numéro de carte** | l'abonné | Faible |

---

## 3. Évaluation par destinataire

Pour chacun : nature des RP communiqués, finalité, mesures de protection, régime juridique,
risque résiduel. Le régime juridique est le même pour les sept (États-Unis, absence de loi
fédérale générale de protection des RP, possibilité d'accès gouvernemental notamment sous le
*CLOUD Act* et la section 702 FISA) — il est donc traité une fois au §3.0 et non répété.

### 3.0 Régime juridique commun (États-Unis) — facteur 4°

Les États-Unis ne disposent pas d'une loi fédérale générale de protection des renseignements
personnels équivalente à P-39.1. Les autorités américaines peuvent, dans certaines conditions,
exiger la communication de données détenues par une entreprise américaine, y compris lorsqu'elles
sont stockées à l'étranger (*CLOUD Act*). Le Québec n'exige pas une équivalence formelle, mais
une **protection adéquate** établie en tenant compte des quatre facteurs. L'atténuation repose
donc principalement sur les facteurs 1° (sensibilité, minimisation) et 3° (mesures techniques et
contractuelles).

*À compléter : décision motivée du responsable sur le caractère adéquat, par destinataire, au §4.*

### 3.1 MongoDB Atlas — hébergement de la base de données

- **RP communiqués :** l'intégralité des catégories du §2.
- **Finalité :** hébergement et persistance des données du service.
- **Mesures techniques :** chiffrement en transit (TLS) et au repos (fourni par l'hébergeur,
  palier **à confirmer**); accès réseau restreint; mots de passe applicatifs hachés bcrypt;
  cloisonnement logique par `organization_id` appliqué à chaque requête.
- **Point d'attention :** c'est le destinataire le plus critique, car il détient **tout**. La
  région exacte est **à confirmer** — hypothèse retenue : États-Unis.
- **Entente écrite :** ☐ à obtenir et archiver.

### 3.2 Render — exécution de l'application

- **RP communiqués :** tous, en transit lors du traitement; journaux applicatifs (adresse IP).
- **Finalité :** exécution du backend FastAPI.
- **Mesures :** aucun secret ni jeton journalisé (règle appliquée dans le code); les journaux ne
  contiennent pas de corps de requête. Variables d'environnement chiffrées côté Render.
- **Entente écrite :** ☐ à obtenir et archiver.

### 3.3 Vercel — diffusion de l'interface web

- **RP communiqués :** essentiellement aucun au repos; métadonnées de requête (IP) en transit.
- **Finalité :** diffusion des fichiers statiques du frontend.
- **Mesures :** en-têtes de sécurité et politique de sécurité du contenu (CSP) appliquée.
- **Entente écrite :** ☐ à obtenir et archiver.

### 3.4 Stripe — paiement de l'abonnement

- **RP communiqués :** courriel, identifiant interne d'utilisateur (métadonnée de session).
- **Finalité :** encaissement de l'abonnement.
- **Mesures :** page de paiement **hébergée par Stripe** — le numéro de carte ne transite jamais
  par nos serveurs (vérifié : `stripe.checkout.Session.create`, aucun champ de carte côté
  serveur); signature du webhook vérifiée et **fail-closed** si le secret est absent.
- **Risque résiduel :** faible (donnée minimale, prestataire certifié PCI-DSS).
- **Entente écrite :** ☐ à obtenir et archiver.

### 3.5 Resend — acheminement des courriels

- **RP communiqués :** l'adresse de l'abonné pour les courriels transactionnels **et l'adresse des
  clients de l'abonné** pour l'envoi de factures, soumissions et rappels de retard, **avec le
  document PDF en pièce jointe** (donc nom, adresse et montants du client).
- **Finalité :** acheminement du courriel.
- **Point d'attention :** ce destinataire reçoit des RP de **tiers** (les clients de l'abonné),
  ce qui engage la qualité de prestataire de FacturePro au sens de l'art. 18.3. Ne pas
  sous-estimer ce flux : il était décrit en un seul mot (« courriels ») dans la politique avant
  le 2026-09-14.
- **Entente écrite :** ☐ à obtenir et archiver.

### 3.6 Anthropic — reconnaissance de reçus ET extraction de relevés bancaires

- **RP communiqués :** (a) l'**image du reçu**; (b) le **relevé bancaire PDF complet** —
  l'ensemble des opérations, montants et contreparties de l'abonné.
- **Finalité :** extraction structurée des données, pour éviter la ressaisie manuelle.
- **Mesures :** consentement **distinct** requis pour chaque flux (le flux relevé doit faire
  l'objet de son propre consentement — cf. §5, écart ouvert); instruction système explicite
  d'ignorer toute instruction contenue dans le document; aucun `str(e)` journalisé (anti-fuite de
  clé); quota de 400 numérisations par organisation et par mois.
- **Point d'attention majeur :** ☐ **rétention zéro (ZDR) à activer**. Sans ZDR, le fournisseur
  peut conserver le contenu soumis. Pour un **relevé bancaire**, c'est le risque le plus élevé de
  tout le dossier. Tant que le ZDR n'est pas confirmé, envisager de suspendre le flux relevé ou
  d'en avertir explicitement l'abonné au moment du consentement.
- **Entente écrite :** ☐ à obtenir et archiver.

### 3.7 Google — connexion facultative par compte Google (OIDC)

- **RP communiqués :** l'adresse courriel et l'état de vérification, reçus **de** Google.
  FacturePro ne transmet aucune donnée d'abonné à Google au-delà de la requête d'authentification.
- **Finalité :** authentification facultative; **liaison à un compte existant seulement** — un
  courriel inconnu est refusé, aucun compte n'est créé par ce chemin.
- **Mesures :** validation JWKS RS256 de l'identité; `state` et `nonce`; code d'échange à usage
  unique (le jeton ne transite jamais par une URL); témoin de liaison HttpOnly/Secure.
- **⚠️ Ordre des opérations :** cette évaluation doit être **complétée avant** de poser les
  variables `GOOGLE_OIDC_CLIENT_ID` / `GOOGLE_OIDC_CLIENT_SECRET` sur Render. Aujourd'hui la
  fonctionnalité est **inerte** faute de ces variables — c'est la fenêtre pour faire les choses
  dans le bon ordre. Même exigence si la liaison Microsoft `(iss, sub)` est un jour réactivée.
- **Entente écrite :** ☐ à obtenir et archiver (conditions Google Cloud / OAuth).

---

## 4. Conclusion par destinataire (à remplir et à signer)

| Destinataire | Protection jugée adéquate ? | Motifs | Entente écrite | Date | Responsable |
|---|---|---|---|---|---|
| MongoDB Atlas | ☐ | | ☐ | | |
| Render | ☐ | | ☐ | | |
| Vercel | ☐ | | ☐ | | |
| Stripe | ☐ | | ☐ | | |
| Resend | ☐ | | ☐ | | |
| Anthropic | ☐ | | ☐ | | |
| Google | ☐ | | ☐ | | |

---

## 5. Écarts ouverts relevés lors de cette évaluation

Ces points ont été constatés **dans le code** pendant la préparation du dossier. Ils sont
consignés ici parce qu'une ÉFVP honnête doit nommer ses faiblesses.

1. **Consentement du flux « relevé bancaire »** — le consentement existant porte sur la
   numérisation de reçus. Un relevé bancaire n'est pas un reçu : l'art. 14 exige un consentement
   *manifeste, libre, éclairé et donné à des fins spécifiques*. Un consentement distinct est à
   recueillir avant l'envoi d'un relevé à Anthropic.
2. **Retrait du consentement** — aucun mécanisme en libre-service; le retrait s'effectue
   aujourd'hui par écrit au responsable. À outiller.
3. **Suppression physique des fichiers** — toutes les suppressions de `db.files` sont des
   suppressions **logiques** (`is_deleted: true`). Il n'existe aucun `$unset` du champ `data` ni
   de `delete_one`. Le binaire d'un reçu reste donc en base après retrait. **La modale de
   consentement OCR affirme le contraire** — représentation à corriger en priorité, puisque le
   consentement a été obtenu en partie sur cette base.
4. **Destruction après fermeture de compte** — non automatisée; aucun état « résilié » ni date de
   résiliation dans le modèle de données. La politique n'annonce donc plus de délai chiffré.
5. **Secret TOTP en clair au repos** — la clé de double authentification est stockée non chiffrée
   (limite déjà documentée dans CLAUDE.md). À chiffrer au repos.
6. **Registre des incidents de confidentialité** (art. 3.8) — non encore constitué.
7. **Consentement aux CGU et à la politique non enregistré à l'inscription** — l'acceptation est
   affirmée dans les CGU mais n'est journalisée nulle part pour le propriétaire qui s'inscrit
   (elle l'est pour une invitation acceptée). Aucune preuve opposable.

---

## 6. Portée et limites de ce document

Ce canevas a été préparé à partir du **code source réel** et du texte officiel de la loi. Il
établit les faits techniques de façon vérifiable, et il identifie les décisions à prendre.

**Il ne constitue pas un avis juridique.** L'appréciation du caractère « adéquat » de la
protection au sens de l'art. 17 al. 2, la rédaction des ententes écrites et l'arbitrage du risque
résiduel relèvent d'un conseiller juridique du Québec. Faire réviser ce dossier, ainsi que la
politique de confidentialité et les conditions générales, avant de s'y fier intégralement.
