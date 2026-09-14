import React from 'react';

// Pages légales PUBLIQUES : /privacy (politique de confidentialité) et /cgu.
// Rendues avant l'authentification (voir App.js). Les liens de consentement (AcceptInvitePage,
// LoginPage) pointent vers ces routes — auparavant morts (gap G3 de l'audit Loi 25).
//
// ⚠️ RÈGLE DE MAINTENANCE — ces deux textes sont OPPOSABLES et lus par la Commission d'accès à
// l'information en cas de plainte. Toute affirmation factuelle ici doit être vraie DANS LE CODE.
// Avant de modifier une fonctionnalité qui touche : un sous-processeur, un transfert hors Québec,
// une durée de conservation, un témoin, une catégorie de renseignements, une mesure de sécurité
// ou le modèle de facturation -> METTRE À JOUR CETTE PAGE DANS LE MÊME COMMIT.
// Les articles cités sont ceux de la Loi sur la protection des renseignements personnels dans le
// secteur privé (RLRQ, c. P-39.1), modernisée en 2021 par la « Loi 25 » — et NON de la Loi 25
// elle-même, qui est la loi modificatrice. Vérifiés sur legisquebec.gouv.qc.ca et contre le guide
// ÉFVP de la CAI. Ne pas citer d'article de mémoire.

const BRAND = '#00A08C';
const LINK = '#00796B';   // teal foncé : 5,32:1 sur blanc (le BRAND ne fait que 3,28:1)

const LegalLayout = ({ title, updated, effective, children }) => (
  <div style={{ minHeight: '100vh', background: '#f8fafb', padding: '40px 20px' }}>
    <div style={{ maxWidth: 820, margin: '0 auto', background: '#fff', borderRadius: 16,
                  boxShadow: '0 1px 3px rgba(0,0,0,0.08)', padding: '40px 44px' }}>
      <a href="/" style={{ color: LINK, fontWeight: 600, textDecoration: 'none', fontSize: 14 }}>← Retour</a>
      <h1 style={{ color: '#1f2937', marginTop: 16, marginBottom: 4 }}>{title}</h1>
      {updated && (
        <p style={{ color: '#6b7280', fontSize: 13, marginTop: 0 }}>
          Version {updated}
          {effective ? ` — en vigueur depuis le ${effective}` : ''}
        </p>
      )}
      <div style={{ color: '#374151', fontSize: 15, lineHeight: 1.7 }}>{children}</div>
      <hr style={{ border: 'none', borderTop: '1px solid #e5e7eb', margin: '32px 0 16px' }} />
      <p style={{ color: '#9ca3af', fontSize: 13 }}>FacturePro inc. — 240, chemin Ostiguy, Shefford (Québec) J2M 2A7</p>
    </div>
  </div>
);

const H = ({ children }) => (
  <h2 style={{ color: '#111827', fontSize: 18, marginTop: 28, marginBottom: 8 }}>{children}</h2>
);

const H3 = ({ children }) => (
  <h3 style={{ color: '#111827', fontSize: 15, marginTop: 18, marginBottom: 6 }}>{children}</h3>
);

const A = ({ href, children, ext }) => (
  <a href={href} style={{ color: LINK }}
     {...(ext ? { target: '_blank', rel: 'noopener noreferrer' } : {})}>{children}</a>
);

const Note = ({ children }) => (
  <p style={{ background: '#f3f4f6', borderLeft: `3px solid ${BRAND}`, borderRadius: 4,
              padding: '10px 14px', fontSize: 14, color: '#374151' }}>{children}</p>
);

const VERSION = '2026-09-14';
const EN_VIGUEUR = '14 septembre 2026';
const RESPONSABLE = 'guillaume.dubeau@facturepro.ca';

export const PrivacyPolicyPage = () => (
  <LegalLayout title="Politique de confidentialité" updated={VERSION} effective={EN_VIGUEUR}>
    <p>
      FacturePro est un logiciel de facturation et de comptabilité offert en mode SaaS par
      {' '}<strong>FacturePro inc.</strong> (« nous », « l'Éditeur »), dont le siège est situé au
      {' '}240, chemin Ostiguy, Shefford (Québec) J2M 2A7, Canada. La présente politique explique quels
      renseignements personnels nous recueillons, pourquoi, avec qui nous les partageons, où ils sont
      traités, combien de temps nous les conservons et quels sont vos droits.
    </p>
    <p>
      Nos traitements sont régis par la <strong>Loi sur la protection des renseignements personnels dans
      le secteur privé</strong> (RLRQ, c. P-39.1), modernisée en 2021 par la loi communément appelée
      {' '}« Loi 25 ». Les articles cités ci-dessous sont ceux de cette loi. À l'égard de nos activités
      au Québec, notre entreprise est soustraite à l'application de la partie 1 de la
      {' '}<em>Loi sur la protection des renseignements personnels et les documents électroniques</em>
      {' '}(LPRPDE) par le décret DORS/2003-374, la loi québécoise ayant été déclarée essentiellement
      similaire; la LPRPDE demeure susceptible de s'appliquer à des renseignements que nous
      communiquons à l'extérieur du Québec dans le cadre d'activités interprovinciales.
    </p>

    <H>Deux rôles distincts — lisez d'abord ceci</H>
    <p>
      Cette politique couvre <strong>deux situations différentes</strong>, et vos droits ne s'exercent pas
      au même endroit selon le cas :
    </p>
    <ul>
      <li>
        <strong>Vos renseignements d'abonné</strong> (vous qui ouvrez un compte) : nous en sommes
        responsables, et vous exercez vos droits directement auprès de nous.
      </li>
      <li>
        <strong>Les renseignements de vos clients et de vos employés</strong>, que vous saisissez dans le
        logiciel : c'est <strong>vous</strong> qui en êtes responsable. Nous agissons pour votre compte,
        sur vos instructions, comme prestataire de services. Si une de ces personnes veut exercer un
        droit, elle doit s'adresser à vous; nous vous assistons, mais nous n'utilisons jamais ces
        renseignements à nos propres fins. Nos engagements à ce titre figurent à l'article 13 de nos
        {' '}<A href="/cgu">conditions générales d'utilisation</A>.
      </li>
    </ul>

    <H>Responsable de la protection des renseignements personnels</H>
    <p>
      La personne ayant la plus haute autorité au sein de l'entreprise est responsable de la protection
      des renseignements personnels (art. 3.1). Cette fonction est exercée par
      {' '}<strong>Guillaume Dubeau</strong> — <A href={`mailto:${RESPONSABLE}`}>{RESPONSABLE}</A>,
      240, chemin Ostiguy, Shefford (Québec) J2M 2A7. Vous pouvez communiquer avec cette personne pour
      toute question, demande d'accès, de rectification, de retrait de consentement ou plainte.
    </p>

    <H>Renseignements que nous recueillons</H>
    <ul>
      <li><strong>Abonnés</strong> : courriel, nom d'entreprise, mot de passe (stocké <strong>haché</strong> avec bcrypt, jamais en clair), rôle dans l'organisation, statut d'abonnement, dates de consentement.</li>
      <li><strong>Vos clients</strong> (saisis par vous) : nom, courriel, téléphone, adresse, numéros fiscaux (BN, TPS, TVQ, TVH, NEQ).</li>
      <li><strong>Vos employés</strong> (saisis par vous) : nom, courriel, téléphone, numéro d'employé, département.</li>
      <li><strong>Documents d'affaires</strong> : factures, devis, dépenses, taxes, et les <strong>images de reçus</strong> que vous téléversez ou numérisez.</li>
      <li><strong>Données bancaires importées</strong> : lorsque vous utilisez le rapprochement bancaire, les opérations de vos relevés (date, description, montant, <strong>nom des contreparties</strong>) ainsi que le <strong>fichier de relevé original</strong> (PDF, CSV ou XLSX) que vous conservez dans l'application.</li>
      <li><strong>Carnet de route</strong> (si vous l'utilisez) : lieu de départ, lieu d'arrivée, motif du déplacement, distance, véhicule et personne concernée — ce sont des renseignements sur vos déplacements.</li>
      <li><strong>Paramètres de sécurité</strong> : si vous activez la double authentification, la clé secrète de votre application d'authentification et vos codes de secours (conservés <strong>hachés</strong>).</li>
      <li><strong>Connexion par Google</strong> (facultative) : lorsque vous choisissez ce mode de connexion, Google nous transmet votre courriel et la confirmation qu'il est vérifié. Nous ne recevons ni votre mot de passe Google, ni vos contacts, ni aucune autre donnée de votre compte Google.</li>
      <li><strong>Journaux de sécurité et d'audit</strong> : courriel, identifiant d'utilisateur, <strong>adresse IP</strong>, agent utilisateur du navigateur, action effectuée, cible de l'action et résultat. Ce journal existe pour détecter les accès non autorisés et répondre à nos obligations de traçabilité.</li>
      <li><strong>Paiement de l'abonnement</strong> : courriel et identifiants de session. <strong>Le numéro de carte ne transite jamais par nos serveurs</strong> : le paiement se déroule entièrement sur une page hébergée par Stripe.</li>
    </ul>
    <Note>
      Nous n'avons pas besoin de renseignements sensibles pour fournir le service. Évitez de téléverser
      des reçus ou des documents contenant des renseignements de santé ou d'autres renseignements
      intimes : notre traitement n'est pas conçu pour ce type de contenu.
    </Note>

    <H3>Comment nous les recueillons</H3>
    <p>
      Par votre saisie directe dans l'application; par le téléversement ou la numérisation de fichiers
      que vous nous confiez; automatiquement par nos serveurs pour les journaux de sécurité (adresse IP,
      agent utilisateur); et par votre fournisseur d'identité si vous choisissez la connexion Google.
      Nous n'achetons aucune donnée et nous n'en recueillons auprès d'aucun courtier.
    </p>

    <H>Finalités</H>
    <p>
      Nous utilisons ces renseignements uniquement pour fournir et sécuriser le service, générer vos
      documents et vos rapports fiscaux, reconnaître le contenu des reçus et des relevés que vous nous
      soumettez, percevoir l'abonnement, vous envoyer les communications liées au service et respecter
      nos obligations légales. <strong>Nous ne faisons aucune publicité, nous ne profilons personne et
      nous ne vendons jamais vos renseignements.</strong>
    </p>

    <H>Qui a accès à vos renseignements</H>
    <ul>
      <li><strong>Chez vous</strong> : les membres de votre organisation, selon le rôle que vous leur attribuez (propriétaire, comptable, lecteur). Les données d'une organisation sont cloisonnées : aucune organisation ne peut voir celles d'une autre.</li>
      <li><strong>Chez nous</strong> : FacturePro inc. est une entreprise à propriétaire unique. Seul son dirigeant, en sa qualité de responsable de la protection des renseignements personnels, peut accéder aux données de production, et uniquement lorsque c'est nécessaire pour assurer le service, corriger une anomalie ou répondre à une demande légale. Aucun autre employé ni sous-traitant humain n'y a accès.</li>
      <li><strong>Nos fournisseurs</strong> : uniquement dans la mesure décrite ci-dessous, et jamais pour leurs propres fins.</li>
    </ul>

    <H>Consentement</H>
    <p>
      Nous demandons un consentement distinct, manifeste, libre, éclairé et daté pour chaque finalité qui
      n'est pas nécessaire au service (art. 14) :
    </p>
    <ul>
      <li><strong>Reconnaissance des reçus par intelligence artificielle</strong> : l'image du reçu est transmise à notre fournisseur Anthropic, aux États-Unis.</li>
      <li><strong>Extraction des relevés bancaires en PDF</strong> : le relevé est transmis au même fournisseur, aux États-Unis. Un relevé bancaire révèle l'ensemble de vos opérations et de vos contreparties — c'est pourquoi ce consentement est demandé séparément de celui des reçus.</li>
      <li><strong>Acceptation d'une invitation d'équipe</strong>, lorsque vous rejoignez l'organisation d'un tiers.</li>
    </ul>
    <p>
      Vous pouvez <strong>retirer votre consentement en tout temps</strong> en écrivant au responsable
      ci-dessus; la fonctionnalité correspondante est alors désactivée pour votre compte. Le retrait n'a
      pas d'effet rétroactif sur les traitements déjà effectués et ne s'étend pas aux renseignements que
      nous devons conserver en vertu de la loi.
    </p>

    <H>Traitement à l'extérieur du Québec</H>
    <p>
      <strong>Nos traitements ont lieu en majeure partie aux États-Unis.</strong> Nous préférons vous le
      dire clairement plutôt que de laisser entendre le contraire. Sont concernés :
    </p>
    <ul>
      <li><strong>MongoDB Atlas</strong> — hébergement de la base de données (chiffrée au repos par l'hébergeur).</li>
      <li><strong>Render</strong> — exécution de l'application et de ses journaux.</li>
      <li><strong>Vercel</strong> — diffusion de l'interface web.</li>
      <li><strong>Stripe</strong> — traitement du paiement de l'abonnement.</li>
      <li><strong>Resend</strong> — acheminement des courriels. Cela inclut les courriels que vous envoyez depuis le logiciel à <strong>vos propres clients</strong> (facture, soumission, rappel de retard), avec leur adresse et le document joint.</li>
      <li><strong>Anthropic</strong> — reconnaissance des reçus <strong>et</strong> extraction des relevés bancaires en PDF.</li>
      <li><strong>Google</strong> — uniquement si vous choisissez la connexion par compte Google.</li>
    </ul>
    <p>
      Avant de communiquer un renseignement personnel à l'extérieur du Québec, ou d'en confier le
      traitement à un tiers qui s'y trouve, la loi nous impose de procéder à une évaluation des facteurs
      relatifs à la vie privée tenant compte de la sensibilité du renseignement, de la finalité de son
      utilisation, des mesures de protection dont il bénéficierait — y compris contractuelles — et du
      régime juridique applicable dans l'État concerné; la communication doit en outre faire l'objet
      d'une entente écrite (art. 17).
    </p>
    <Note>
      <strong>État d'avancement, en toute transparence :</strong> cette évaluation est en cours de
      réalisation et de consignation pour chacun des fournisseurs ci-dessus, et les ententes écrites
      correspondantes sont en cours de conclusion ou de vérification. Nous mettrons cette section à jour
      dès que le dossier sera complet. Nous ne partageons vos renseignements avec aucun autre tiers, sauf
      obligation légale ou à votre demande.
    </Note>

    <H>Durées de conservation</H>
    <ul>
      <li><strong>Compte actif</strong> : vos données sont conservées pendant toute la durée de votre abonnement, puisqu'elles constituent le contenu même du service.</li>
      <li><strong>Journaux de sécurité et d'audit</strong> : 12 mois, puis suppression automatique.</li>
      <li><strong>Jetons temporaires</strong> (réinitialisation de mot de passe, liaison de connexion) : de quelques minutes à une heure, puis suppression automatique.</li>
      <li><strong>Après la fermeture de votre compte</strong> : nous détruisons ou anonymisons les renseignements personnels lorsque les fins pour lesquelles ils ont été recueillis sont accomplies, sous réserve d'un délai de conservation prévu par la loi (art. 23). Écrivez au responsable pour demander la destruction : nous y procédons sur demande.</li>
    </ul>
    <Note>
      <strong>Ce que nous ne faisons pas encore :</strong> la destruction après fermeture de compte n'est
      pas encore automatisée. Tant qu'elle ne l'est pas, elle s'effectue <strong>sur demande</strong>, et
      nous ne vous annonçons pas de délai chiffré que nous ne serions pas en mesure de tenir. Par
      ailleurs, lorsqu'un reçu est retiré d'une dépense, il cesse d'être accessible dans le logiciel mais
      sa copie technique n'est pas encore effacée de notre base; nous corrigeons ce point.
    </Note>
    <p>
      <strong>Obligations fiscales.</strong> Les lois fiscales obligent <strong>l'entreprise</strong> —
      vous — à conserver ses registres et pièces justificatives, généralement pendant six ans suivant la
      fin de la dernière année d'imposition à laquelle ils se rapportent, ce délai pouvant être plus long
      en cas d'opposition ou d'appel. Cette obligation vous incombe, non à nous. C'est pourquoi nous vous
      recommandons d'exporter vos données avant de fermer votre compte : l'outil d'export intégral est à
      votre disposition en tout temps.
    </p>

    <H>Vos droits</H>
    <p>Vous pouvez, à l'égard des renseignements dont nous sommes responsables :</p>
    <ul>
      <li><strong>Y accéder et en obtenir communication</strong> (art. 27). Cet accès est gratuit.</li>
      <li><strong>En recevoir une copie dans un format technologique structuré et couramment utilisé</strong> — la portabilité (art. 27, dernier alinéa). Ce droit porte sur les renseignements que vous nous avez <strong>fournis</strong>, et non sur ceux que nous avons créés ou inférés à partir d'eux; il peut aussi être écarté lorsque son exercice soulève des difficultés pratiques sérieuses. Le propriétaire d'une organisation peut déclencher lui-même un export complet depuis les paramètres.</li>
      <li><strong>Les faire rectifier</strong> s'ils sont inexacts, incomplets ou équivoques, ou si leur collecte, leur communication ou leur conservation n'est pas autorisée par la loi (art. 28).</li>
      <li><strong>Retirer votre consentement</strong> aux traitements facultatifs.</li>
      <li><strong>Demander la cessation de la diffusion</strong> d'un renseignement, ou la désindexation d'un lien y donnant accès, aux conditions prévues par la loi (art. 28.1). En pratique, cela concerne les liens publics de consultation de soumission que vous pouvez émettre depuis le logiciel.</li>
      <li><strong>Demander la destruction ou l'anonymisation</strong> lorsque les fins de la collecte sont accomplies (art. 23).</li>
    </ul>
    <p>
      Pour exercer un droit, écrivez au responsable ci-dessus. Nous répondons par écrit avec diligence et
      au plus tard <strong>30 jours</strong> après la réception de la demande. Le défaut de répondre dans
      ce délai équivaut à un refus. Tout refus sera <strong>motivé</strong>, indiquera la disposition de
      la loi sur laquelle il s'appuie et vous informera de vos recours et du délai pour les exercer.
    </p>

    <H3>Limites de l'effacement — à lire avant de le demander</H3>
    <p>
      Nous appliquons l'effacement à l'intérieur du logiciel de la façon suivante, et nous préférons vous
      en décrire les limites plutôt que de promettre un effacement total :
    </p>
    <ul>
      <li>Les coordonnées d'un client ou d'un employé (courriel, téléphone, adresse, numéros fiscaux, numéro d'employé) sont <strong>effacées</strong>.</li>
      <li><strong>Le nom demeure sur les factures et les soumissions déjà émises.</strong> Une pièce comptable déjà transmise à un tiers ne peut pas être réécrite sans compromettre la valeur probante de vos registres et vos obligations fiscales.</li>
      <li>Les montants, les dates et les écritures comptables sont conservés : ce sont vos registres, et ils ne constituent pas des renseignements personnels une fois les coordonnées retirées.</li>
      <li>Nous employons le mot « effacement » et non « anonymisation » : la loi réserve ce second terme à un procédé irréversible répondant à des critères réglementaires, et nous ne prétendons pas l'atteindre.</li>
    </ul>

    <H>Mesures de sécurité</H>
    <p>Nous prenons les mesures de sécurité propres à assurer la protection de vos renseignements (art. 10) :</p>
    <ul>
      <li>chiffrement de toutes les communications en transit (TLS);</li>
      <li>mots de passe stockés sous forme <strong>hachée</strong> (bcrypt), jamais en clair, jamais consultables par nous;</li>
      <li>chiffrement des données au repos, assuré par notre hébergeur de base de données;</li>
      <li><strong>double authentification</strong> (TOTP) offerte à chaque utilisateur, avec codes de secours;</li>
      <li><strong>révocation des sessions</strong> : un changement de mot de passe ou de facteur invalide les sessions déjà ouvertes;</li>
      <li><strong>cloisonnement par organisation</strong> sur chaque requête, et contrôle d'accès par rôles;</li>
      <li><strong>verrouillage temporaire</strong> après des tentatives de connexion répétées, par couple adresse courriel et adresse IP;</li>
      <li><strong>désactivation immédiate</strong> d'un membre par le propriétaire de l'organisation;</li>
      <li><strong>journal d'audit</strong> de toutes les modifications et de tous les évènements de sécurité, accessible au seul propriétaire et protégé par la double authentification;</li>
      <li><strong>politique de sécurité du contenu</strong> appliquée par le navigateur, et en-têtes de sécurité sur l'ensemble du site.</li>
    </ul>

    <H>Gouvernance, plaintes et incidents</H>
    <H3>Encadrement interne</H3>
    <p>
      La loi nous impose d'établir et de publier des règles encadrant la conservation et la
      destruction des renseignements, la répartition des rôles et des responsabilités tout au long de
      leur cycle de vie, et le traitement des plaintes (art. 3.2). L'entreprise étant à propriétaire
      unique, ces rôles sont réunis chez le responsable désigné ci-dessus, et les durées de
      conservation annoncées plus haut sont appliquées techniquement. La rédaction du document
      détaillé est en cours; écrivez au responsable pour en obtenir l'état à jour.
    </p>
    <H3>Plaintes</H3>
    <p>
      Si vous estimez que nous n'avons pas respecté vos droits, écrivez d'abord au responsable : nous
      accusons réception de votre plainte, l'examinons et vous communiquons notre conclusion motivée.
      Vous pouvez en tout temps vous adresser à la <strong>Commission d'accès à l'information du
      Québec</strong> : <A href="https://www.cai.gouv.qc.ca" ext>www.cai.gouv.qc.ca</A>.
    </p>
    <H3>Incidents de confidentialité</H3>
    <p>
      En cas d'incident de confidentialité, nous prenons les mesures raisonnables pour en diminuer les
      risques et éviter qu'il ne se reproduise. Lorsque l'incident présente un risque qu'un préjudice
      sérieux soit causé, nous en avisons avec diligence la Commission d'accès à l'information et les
      personnes concernées, à moins que cet avis ne risque d'entraver une enquête. Nous tenons un
      registre des incidents, conformément à la loi, et nous en transmettons copie à la Commission
      sur demande. La tenue de ce registre est en cours de mise en place; aucun incident de
      confidentialité ne nous a été signalé à ce jour.
    </p>

    <H>Témoins (cookies)</H>
    <p>
      FacturePro utilise le <strong>stockage local</strong> de votre navigateur pour conserver votre
      session. Un <strong>témoin strictement nécessaire</strong> (nommé <code>fp_oidc_bind</code>, d'une
      durée de dix minutes, HttpOnly et Secure) est déposé <strong>uniquement</strong> lorsque vous
      utilisez la connexion par Google, afin de lier cette connexion au navigateur qui l'a amorcée et
      d'empêcher qu'un tiers ne la détourne. Aucun autre témoin n'est déposé.
      {' '}<strong>Aucun témoin publicitaire, aucun traceur tiers, aucun outil d'analyse d'audience.</strong>
    </p>

    <H>Modifications</H>
    <p>
      Toute modification de la présente politique fait l'objet d'un avis publié sur cette page, et les
      abonnés en sont informés par un moyen raisonnable (art. 8.2). La version et la date d'entrée en
      vigueur figurent en haut de la page.
    </p>

    <H>Nous joindre</H>
    <p>
      FacturePro inc., 240, chemin Ostiguy, Shefford (Québec) J2M 2A7 —
      {' '}<A href={`mailto:${RESPONSABLE}`}>{RESPONSABLE}</A>.
    </p>
  </LegalLayout>
);

export const TermsPage = () => (
  <LegalLayout title="Conditions générales d'utilisation" updated={VERSION} effective={EN_VIGUEUR}>
    <p>
      Les présentes conditions constituent le contrat entre <strong>FacturePro inc.</strong> (« nous »,
      {' '}« l'Éditeur »), société ayant son siège au 240, chemin Ostiguy, Shefford (Québec) J2M 2A7, et
      la personne ou l'entreprise qui souscrit au service (« vous », « l'Abonné »). En créant un compte
      ou en utilisant le service, vous acceptez ces conditions dans leur version {VERSION}.
    </p>

    <H>1. Objet et qualité de l'Abonné</H>
    <p>
      Ces conditions régissent l'utilisation du logiciel FacturePro (le « Service »). Vous déclarez
      souscrire <strong>dans le cadre et pour les fins de votre entreprise ou de votre pratique
      professionnelle</strong>, et non à des fins personnelles, familiales ou domestiques.
    </p>

    <H>2. Description du Service et limites d'usage</H>
    <p>
      FacturePro est un logiciel de facturation et de comptabilité en ligne destiné aux PME et aux
      travailleurs autonomes : facturation, soumissions, dépenses, rapports fiscaux, grand livre,
      rapprochement bancaire et carnet de route. Les fonctionnalités peuvent évoluer.
    </p>
    <p>Les limites suivantes s'appliquent et peuvent être ajustées conformément à l'article 15 :</p>
    <ul>
      <li><strong>400 numérisations par organisation et par mois civil</strong>, partagées entre la reconnaissance de reçus et l'extraction de relevés bancaires en PDF, et partagées entre tous les membres de l'organisation. Le quota se réinitialise au début de chaque mois. Au-delà, la fonction est temporairement refusée; le reste du Service demeure accessible.</li>
      <li>Taille et format des fichiers importés, indiqués dans l'interface au moment de l'import.</li>
    </ul>
    <p>
      Le Service <strong>ne constitue pas un avis comptable, fiscal ou juridique</strong>. Les rapports
      produits (TPS/TVQ, T2125, sommaire GIFI, états financiers) sont des outils de préparation : leur
      exactitude dépend des données que vous saisissez, et leur revue par un professionnel compétent
      demeure votre responsabilité.
    </p>

    <H>3. Compte, organisation et membres</H>
    <p>
      Le Service s'organise autour d'une <strong>organisation</strong>, qui est l'Abonné. La personne qui
      la crée en est le <strong>propriétaire</strong> et déclare avoir le pouvoir d'engager l'Abonné. Le
      propriétaire peut inviter des membres et leur attribuer un rôle (propriétaire, comptable, lecteur).
    </p>
    <p>
      Les actes accomplis par tout membre sont réputés être ceux de l'Abonné. Il appartient au
      propriétaire de gérer les accès et de révoquer sans délai ceux qui ne sont plus nécessaires. Vous
      êtes responsable de l'exactitude des renseignements fournis, de la confidentialité des identifiants
      et de toute activité effectuée sous votre compte, et vous devez nous aviser sans délai de tout
      accès non autorisé.
    </p>

    <H>4. Essai gratuit</H>
    <p>
      Chaque nouvelle organisation bénéficie d'un essai gratuit de <strong>14 jours</strong> à compter de
      la création du compte, <strong>sans carte de crédit</strong>. À l'échéance, l'accès aux
      fonctionnalités est restreint jusqu'à la souscription. Vos données demeurent conservées et
      l'<strong>export intégral demeure accessible</strong> pendant cette période restreinte : vous ne
      perdez jamais l'accès à vos données parce que vous n'avez pas souscrit.
    </p>

    <H>5. Abonnement, prix et paiement</H>
    <p>
      Le Service est offert par abonnement au prix de <strong>15 $ CAD par mois</strong>, taxes en sus le
      cas échéant, par organisation. L'abonnement est payable d'avance, par carte de crédit, au moyen de
      notre prestataire <strong>Stripe</strong>; il se renouvelle automatiquement à chaque période
      mensuelle jusqu'à sa résiliation conformément à l'article 10. Les sommes versées pour une période
      commencée ne sont pas remboursables, sauf disposition légale contraire ou erreur de facturation de
      notre part.
    </p>

    <H>6. Vos obligations</H>
    <p>
      Vous vous engagez à utiliser le Service conformément aux lois applicables, à ne pas y téléverser de
      contenu illicite, à ne pas tenter d'en contourner les mesures de sécurité, d'en extraire
      massivement les données par des moyens automatisés ou d'en perturber le fonctionnement.
    </p>
    <p>
      <strong>Renseignements de tiers.</strong> Vous demeurez responsable des renseignements personnels de
      vos clients et de vos employés que vous saisissez dans le Service : vous devez disposer du droit de
      les recueillir et de nous les confier, et informer ces personnes conformément à la loi. Nos
      engagements comme prestataire figurent à l'article 13.
    </p>

    <H>7. Propriété intellectuelle</H>
    <p>
      Le Service, son code et sa marque demeurent la propriété de FacturePro inc. <strong>Vos données
      demeurent votre propriété</strong>; vous nous accordez la licence limitée, non exclusive et
      révocable nécessaire pour les héberger, les traiter et les afficher aux seules fins de vous fournir
      le Service.
    </p>

    <H>8. Disponibilité, sauvegardes et interruptions</H>
    <p>
      Nous déployons des efforts raisonnables pour maintenir le Service disponible, sans nous engager sur
      un pourcentage de disponibilité. Nous ne garantissons pas l'absence d'interruption : le Service
      repose sur des infrastructures de tiers, et une interruption de leur part se répercute sur lui.
    </p>
    <Note>
      <strong>À savoir, plutôt que de le découvrir à l'usage :</strong> notre palier d'hébergement actuel
      met l'application en veille après une période d'inactivité. La première requête après une veille
      peut prendre de 30 à 60 secondes. Ce n'est pas une panne.
    </Note>
    <p>
      Des sauvegardes de la base de données sont effectuées par notre hébergeur. Elles visent la
      continuité du Service et ne constituent pas un service d'archivage à votre bénéfice :
      <strong> il vous appartient de conserver vos propres copies</strong> au moyen de la fonction
      d'export, notamment avant toute opération importante et avant la fermeture de votre compte.
    </p>

    <H>9. Responsabilité</H>
    <p>
      Le Service est fourni « tel quel ». Dans la mesure permise par la loi, notre responsabilité totale
      envers vous, pour l'ensemble des réclamations relatives au Service, est limitée au plus élevé des
      deux montants suivants : <strong>les sommes que vous nous avez effectivement versées au cours des
      douze mois précédant le fait générateur</strong>, ou <strong>200 $ CAD</strong>.
    </p>
    <p>
      Nous ne sommes pas responsables des dommages indirects, notamment de la perte de profits, de la
      perte de clientèle ou de la perte de données au-delà de ce plafond. Aucune stipulation des
      présentes ne limite notre responsabilité pour un préjudice corporel ou moral, ni en cas de faute
      intentionnelle ou de faute lourde, ni dans la mesure où la loi l'interdit.
    </p>

    <H>10. Durée, résiliation et fermeture du compte</H>
    <p>
      <strong>Par vous.</strong> Vous pouvez résilier en tout temps en écrivant à
      {' '}<A href={`mailto:${RESPONSABLE}`}>{RESPONSABLE}</A> depuis l'adresse du propriétaire de
      l'organisation. La résiliation prend effet à la fin de la période mensuelle en cours, sans
      remboursement de cette période. Nous accusons réception et confirmons la date d'effet.
    </p>
    <p>
      <strong>Par nous.</strong> Nous pouvons suspendre ou résilier votre accès en cas de manquement aux
      présentes, de défaut de paiement ou d'usage portant atteinte à la sécurité ou aux droits d'autrui.
      Sauf urgence ou obligation légale, nous vous en avisons au préalable et vous laissons un délai
      raisonnable pour y remédier.
    </p>

    <H>11. Restitution et exportation de vos données</H>
    <p>
      Le propriétaire de l'organisation peut, <strong>en tout temps et sans frais</strong>, déclencher un
      export intégral de ses données depuis les paramètres du Service. L'export est fourni dans un format
      structuré et couramment utilisé : une archive ZIP contenant vos données tabulaires ainsi que les
      fichiers que vous avez téléversés.
    </p>
    <p>
      Cette fonction demeure accessible pendant toute la durée du contrat, pendant la période d'accès
      restreint suivant l'expiration de l'essai, et <strong>pendant 30 jours après la date d'effet d'une
      résiliation</strong>. Nous vous recommandons fortement de l'utiliser avant de fermer votre compte.
      Au-delà, le sort de vos renseignements suit notre
      {' '}<A href="/privacy">politique de confidentialité</A>.
    </p>

    <H>12. Protection des renseignements personnels</H>
    <p>
      Le traitement des renseignements personnels est décrit dans notre
      {' '}<A href="/privacy">politique de confidentialité</A>, qui fait partie intégrante des présentes.
    </p>

    <H>13. Sous-traitance des renseignements personnels de vos clients et employés</H>
    <p>
      À l'égard des renseignements personnels de vos clients et de vos employés que vous saisissez dans le
      Service, <strong>vous êtes la personne responsable</strong> et nous agissons pour votre compte, sur
      vos instructions. Nous nous engageons à :
    </p>
    <ul>
      <li><strong>en assurer la confidentialité</strong>;</li>
      <li><strong>ne les utiliser que dans l'exercice de nos fonctions</strong> au titre du présent contrat, et à aucune autre fin — nous ne les utilisons ni pour de la publicité, ni pour du profilage, ni pour entraîner des modèles;</li>
      <li><strong>ne pas les conserver après l'expiration du contrat</strong>, sous réserve de ce que la loi nous oblige à conserver;</li>
      <li>vous <strong>aviser sans délai</strong> de toute violation ou tentative de violation de ces obligations, ainsi que de tout incident de confidentialité les concernant, et de vous prêter assistance pour vos propres obligations d'avis;</li>
      <li>vous <strong>assister</strong> lorsqu'une de ces personnes exerce un droit d'accès, de rectification ou de retrait auprès de vous;</li>
      <li>ne recourir qu'aux <strong>sous-traitants énumérés dans la politique de confidentialité</strong>, et vous aviser avant d'en ajouter un nouveau qui traiterait ces renseignements.</li>
    </ul>
    <p>
      Le présent article tient lieu du mandat écrit exigé par la loi. Vous pouvez nous demander tout
      renseignement nécessaire pour vérifier le respect de ces engagements.
    </p>

    <H>14. Indemnisation</H>
    <p>
      Vous nous indemnisez des réclamations de tiers découlant du contenu que vous téléversez ou de votre
      utilisation du Service en contravention des présentes, notamment de l'absence du droit de nous
      confier des renseignements personnels de tiers. Nous vous en avisons sans délai et vous laissons la
      conduite de la défense, à condition de ne conclure aucun règlement nous imposant une obligation
      sans notre accord.
    </p>

    <H>15. Modification des présentes conditions</H>
    <p>
      Nous pouvons modifier les présentes conditions, y compris le prix, les fonctionnalités et les
      limites d'usage prévues à l'article 2. Toute modification vous est communiquée par un
      <strong> avis écrit distinct, au moins 30 jours avant sa date d'effet</strong>. Cet avis présente
      uniquement la clause nouvelle, la clause telle qu'elle se lisait auparavant, la date d'entrée en
      vigueur de la modification et vos droits.
    </p>
    <p>
      <strong>Vous pouvez refuser la modification</strong> et résilier sans frais ni pénalité, en nous
      écrivant au plus tard 30 jours après sa prise d'effet. Une augmentation de prix ne s'applique
      jamais à une période déjà payée.
    </p>

    <H>16. Force majeure</H>
    <p>
      Aucune partie n'est responsable d'un défaut d'exécution causé par une force majeure, notamment une
      défaillance majeure d'un fournisseur d'infrastructure, une interruption des réseaux de
      télécommunication, un sinistre ou une mesure d'autorité publique. Les obligations de paiement
      déjà nées demeurent exigibles.
    </p>

    <H>17. Cession</H>
    <p>
      Vous ne pouvez céder le présent contrat sans notre accord écrit. Nous pouvons le céder dans le cadre
      d'une réorganisation ou d'un transfert d'entreprise, à la condition que le cessionnaire assume les
      présentes obligations, y compris celles de l'article 13; vous en serez avisé.
    </p>

    <H>18. Langue</H>
    <p>
      Les parties reconnaissent avoir exigé que le présent contrat, ainsi que tous les documents qui s'y
      rattachent, soient rédigés en français. Le Service et son soutien sont offerts en français.
    </p>

    <H>19. Règlement des différends et droit applicable</H>
    <p>
      En cas de différend, les parties s'engagent à tenter d'abord de le régler de bonne foi, par écrit,
      dans un délai de 30 jours. Les présentes conditions sont régies par les lois applicables au Québec.
      Tout recours relève des tribunaux du district judiciaire de Bedford, province de Québec, sous
      réserve des règles d'ordre public attribuant compétence à un autre tribunal.
    </p>

    <H>20. Dispositions générales</H>
    <p>
      La nullité d'une clause n'affecte pas les autres. Survivent à la fin du contrat les articles 7, 9,
      11, 13, 14 et 19. Les présentes conditions et la politique de confidentialité constituent
      l'intégralité de l'entente entre les parties relativement au Service et remplacent toute entente
      antérieure. Le fait de ne pas invoquer un droit ne vaut pas renonciation à ce droit.
    </p>

    <H>21. Nous joindre</H>
    <p>
      FacturePro inc., 240, chemin Ostiguy, Shefford (Québec) J2M 2A7 —
      {' '}<A href={`mailto:${RESPONSABLE}`}>{RESPONSABLE}</A>.
    </p>
  </LegalLayout>
);
