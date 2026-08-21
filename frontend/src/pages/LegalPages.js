import React from 'react';

// Pages légales PUBLIQUES (Loi 25) : /privacy (politique de confidentialité) et /cgu.
// Rendues avant l'authentification (voir App.js). Les liens de consentement (AcceptInvitePage,
// LoginPage) pointent vers ces routes — auparavant morts (gap G3 de l'audit Loi 25).

const BRAND = '#00A08C';

const LegalLayout = ({ title, updated, children }) => (
  <div style={{ minHeight: '100vh', background: '#f8fafb', padding: '40px 20px' }}>
    <div style={{ maxWidth: 820, margin: '0 auto', background: '#fff', borderRadius: 16,
                  boxShadow: '0 1px 3px rgba(0,0,0,0.08)', padding: '40px 44px' }}>
      <a href="/" style={{ color: BRAND, fontWeight: 600, textDecoration: 'none', fontSize: 14 }}>← Retour</a>
      <h1 style={{ color: '#1f2937', marginTop: 16, marginBottom: 4 }}>{title}</h1>
      {updated && <p style={{ color: '#6b7280', fontSize: 13, marginTop: 0 }}>Dernière mise à jour : {updated}</p>}
      <div style={{ color: '#374151', fontSize: 15, lineHeight: 1.7 }}>{children}</div>
      <hr style={{ border: 'none', borderTop: '1px solid #e5e7eb', margin: '32px 0 16px' }} />
      <p style={{ color: '#9ca3af', fontSize: 13 }}>FacturePro inc. — 240, chemin Ostiguy, Shefford (Québec) J2M 2A7</p>
    </div>
  </div>
);

const H = ({ children }) => (
  <h2 style={{ color: '#111827', fontSize: 18, marginTop: 28, marginBottom: 8 }}>{children}</h2>
);

export const PrivacyPolicyPage = () => (
  <LegalLayout title="Politique de confidentialité" updated="21 août 2026">
    <p>
      FacturePro est un logiciel de facturation et de comptabilité offert en mode SaaS par
      {' '}<strong>FacturePro inc.</strong> (« nous », « l'Éditeur »), dont le siège est situé au
      {' '}240, chemin Ostiguy, Shefford (Québec) J2M 2A7, Canada. La présente politique explique quels
      renseignements personnels nous recueillons, pourquoi, avec qui nous les partageons, où ils sont
      hébergés, combien de temps nous les conservons et quels sont vos droits, conformément à la Loi 25
      (Québec) et à la PIPEDA.
    </p>

    <H>Responsable de la protection des renseignements personnels</H>
    <p>
      Conformément à l'article 3.1 de la Loi 25, nous avons désigné un responsable de la protection des
      renseignements personnels : <strong>Guillaume Dubeau</strong> —
      {' '}<a href="mailto:guillaume.dubeau@facturepro.ca" style={{ color: BRAND }}>guillaume.dubeau@facturepro.ca</a>,
      240, chemin Ostiguy, Shefford (Québec) J2M 2A7. Vous pouvez communiquer avec cette personne pour
      toute question, demande d'accès, de rectification, de retrait de consentement ou plainte.
    </p>

    <H>Renseignements que nous recueillons</H>
    <ul>
      <li><strong>Utilisateurs</strong> : courriel, nom d'entreprise, mot de passe (stocké <strong>haché</strong>, jamais en clair), rôle, journal de consentement, statut d'abonnement.</li>
      <li><strong>Vos clients</strong> (saisis par vous) : nom, courriel, téléphone, adresse, numéros fiscaux (BN, TPS, TVQ, TVH, NEQ).</li>
      <li><strong>Vos employés</strong> (saisis par vous) : nom, courriel, téléphone, numéro d'employé, département.</li>
      <li><strong>Documents d'affaires</strong> : factures, devis, dépenses, taxes, et images de reçus / relevés que vous téléversez ou numérisez.</li>
      <li><strong>Paiement de l'abonnement</strong> : courriel et identifiants de session (le numéro de carte est traité par Stripe et ne transite jamais par nos serveurs).</li>
      <li><strong>Données techniques</strong> : adresse IP (sécurité) et jeton de session (stocké dans votre navigateur).</li>
    </ul>

    <H>Finalités</H>
    <p>
      Nous utilisons ces renseignements uniquement pour fournir et sécuriser le service, générer vos
      documents et rapports fiscaux, effectuer la reconnaissance de reçus, percevoir l'abonnement, vous
      envoyer des communications liées au service et respecter nos obligations légales. Nous ne faisons
      pas de publicité et nous ne vendons jamais vos renseignements.
    </p>

    <H>Consentement</H>
    <p>
      Certaines fonctionnalités requièrent un consentement spécifique et daté : la <strong>numérisation de
      reçus par IA</strong> (l'image est transmise à notre fournisseur d'IA, Anthropic, aux États-Unis) et
      l'<strong>acceptation d'une invitation d'équipe</strong>. Vous pouvez retirer votre consentement en
      tout temps, sous réserve des renseignements que nous devons conserver pour des raisons légales.
    </p>

    <H>Hébergement et transfert hors du Québec</H>
    <p>
      Notre base de données (MongoDB Atlas) est hébergée <strong>au Canada (Montréal)</strong> et chiffrée
      au repos. Certains traitements sont toutefois effectués par des fournisseurs situés à l'extérieur du
      Canada, principalement aux États-Unis : Render (calcul applicatif), Stripe (paiements), Resend
      (courriels), Anthropic (reconnaissance de reçus) et Vercel (interface web). Conformément à
      l'article 3.3 de la Loi 25, ces transferts font l'objet d'une évaluation des facteurs relatifs à la
      vie privée et sont encadrés par des mesures contractuelles et techniques appropriées. Nous ne
      partageons vos renseignements avec aucun autre tiers, sauf obligation légale ou avec votre consentement.
    </p>

    <H>Durées de conservation</H>
    <ul>
      <li><strong>Compte actif</strong> : pendant toute la durée de votre abonnement.</li>
      <li><strong>Documents fiscaux</strong> : conservés pendant la durée exigée par les lois fiscales (généralement 6 ans, ARC / Revenu Québec).</li>
      <li><strong>Après résiliation</strong> : suppression ou anonymisation dans un délai de 6 mois, sauf obligation légale de conservation.</li>
    </ul>

    <H>Vos droits</H>
    <p>Conformément à la Loi 25, vous pouvez : accéder à vos renseignements et en obtenir une copie (art. 27),
      les recevoir dans un format technologique structuré et couramment utilisé (portabilité), les faire
      rectifier, retirer votre consentement, et demander leur suppression lorsque la loi le permet (art. 28.1).
      Pour exercer un droit, écrivez au responsable ci-dessus; nous répondrons dans un délai maximal de 30 jours.
    </p>

    <H>Plaintes</H>
    <p>
      Si vous estimez que nous n'avons pas respecté vos droits, vous pouvez déposer une plainte auprès de
      notre responsable, puis auprès de la <strong>Commission d'accès à l'information du Québec</strong> :
      {' '}<a href="https://www.cai.gouv.qc.ca" target="_blank" rel="noopener noreferrer" style={{ color: BRAND }}>www.cai.gouv.qc.ca</a>.
    </p>

    <H>Mesures de sécurité</H>
    <p>
      Nous mettons en œuvre des mesures raisonnables : chiffrement des communications en transit (TLS),
      stockage des mots de passe sous forme hachée (bcrypt), chiffrement des données au repos (AES-256,
      base au Canada), cloisonnement des données entre organisations, contrôle d'accès par rôles, et
      protection contre les tentatives de connexion répétées.
    </p>

    <H>Témoins (cookies)</H>
    <p>
      FacturePro utilise le stockage local de votre navigateur pour conserver votre session. Nous
      n'utilisons pas de témoins publicitaires ni de traceurs tiers.
    </p>

    <H>Modifications</H>
    <p>
      Nous pouvons modifier la présente politique; toute modification importante vous sera signalée par un
      moyen raisonnable. La date de dernière mise à jour figure en haut de la page.
    </p>
  </LegalLayout>
);

export const TermsPage = () => (
  <LegalLayout title="Conditions générales d'utilisation" updated="21 août 2026">
    <p style={{ background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 8, padding: '10px 14px', fontSize: 14 }}>
      ⚠️ Modèle de conditions à faire valider par un conseiller juridique avant de s'y fier intégralement.
    </p>

    <H>1. Objet</H>
    <p>Les présentes conditions régissent l'utilisation du logiciel FacturePro (le « Service »), offert par
      FacturePro inc. En créant un compte ou en utilisant le Service, vous acceptez ces conditions.</p>

    <H>2. Description du Service</H>
    <p>FacturePro est un logiciel de facturation et de comptabilité en ligne (SaaS) destiné aux PME et
      travailleurs autonomes. Les fonctionnalités peuvent évoluer.</p>

    <H>3. Compte et accès</H>
    <p>Vous êtes responsable de l'exactitude des renseignements fournis, de la confidentialité de vos
      identifiants et de toute activité effectuée sous votre compte. Vous devez nous aviser sans délai de
      tout accès non autorisé.</p>

    <H>4. Abonnement et paiement</H>
    <p>Le Service est offert par abonnement mensuel (15 $ CAD/mois, sauf indication contraire), facturé via
      notre prestataire de paiement Stripe. Les montants sont payables d'avance et non remboursables, sauf
      disposition légale contraire.</p>

    <H>5. Obligations de l'utilisateur</H>
    <p>Vous vous engagez à utiliser le Service conformément aux lois applicables, à ne pas y téléverser de
      contenu illicite, et à obtenir les consentements requis pour les renseignements de tiers (clients,
      employés) que vous y saisissez.</p>

    <H>6. Propriété intellectuelle</H>
    <p>Le Service, son code et sa marque demeurent la propriété de FacturePro inc. Vos données demeurent
      votre propriété; vous nous accordez la licence limitée nécessaire pour exploiter le Service.</p>

    <H>7. Protection des renseignements personnels</H>
    <p>Le traitement de vos renseignements personnels est décrit dans notre
      {' '}<a href="/privacy" style={{ color: BRAND }}>Politique de confidentialité</a>.</p>

    <H>8. Disponibilité et responsabilité</H>
    <p>Le Service est fourni « tel quel ». Nous déployons des efforts raisonnables pour en assurer la
      disponibilité et la sécurité, sans garantie d'absence d'interruption. Dans la mesure permise par la
      loi, notre responsabilité est limitée. <strong>[À COMPLÉTER : plafond de responsabilité, à valider juridiquement.]</strong></p>

    <H>9. Résiliation</H>
    <p>Vous pouvez résilier votre abonnement en tout temps. Nous pouvons suspendre ou résilier un compte en
      cas de manquement aux présentes conditions. À la résiliation, vos données sont traitées selon la
      Politique de confidentialité.</p>

    <H>10. Modifications</H>
    <p>Nous pouvons modifier ces conditions; les modifications importantes vous seront signalées.</p>

    <H>11. Droit applicable</H>
    <p>Les présentes conditions sont régies par les lois de la province de Québec et les lois du Canada
      applicables. Tout litige relève des tribunaux du district judiciaire compétent au Québec.</p>

    <H>12. Nous joindre</H>
    <p>FacturePro inc. — <a href="mailto:guillaume.dubeau@facturepro.ca" style={{ color: BRAND }}>guillaume.dubeau@facturepro.ca</a></p>
  </LegalLayout>
);
