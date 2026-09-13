import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { BACKEND_URL } from '../config';
import { useAuth } from '../context/AuthContext';
import FactureProLogo from '../components/FactureProLogo';

// Messages neutres : on n'indique jamais si un courriel existe ou non au-delà du strict nécessaire.
const ERRORS = {
  refus_fournisseur: "Connexion annulée chez le fournisseur.",
  fournisseur_inconnu: "Ce fournisseur SSO n'est pas configuré.",
  etat_invalide: "Lien de connexion expiré ou déjà utilisé. Réessaie.",
  echange_impossible: "Échec de la communication avec le fournisseur. Réessaie.",
  jeton_invalide: "Réponse du fournisseur invalide.",
  nonce_invalide: "Réponse du fournisseur invalide.",
  courriel_non_verifie:
    "Ton fournisseur n'a pas confirmé ton adresse courriel — connexion refusée par sécurité.",
  compte_inconnu:
    "Aucun compte FacturePro n'est associé à ce courriel. Le SSO relie un compte existant : "
    + "connecte-toi d'abord par mot de passe, ou demande une invitation.",
  navigateur_different:
    "Cette connexion n'a pas été démarrée depuis ce navigateur. Relance depuis la page de connexion.",
  compte_desactive: "Compte désactivé. Contacte le propriétaire de l'organisation.",
};

/**
 * Retour de connexion SSO. L'URL ne porte JAMAIS le jeton : seulement un code d'échange à usage
 * unique (TTL 60 s) qu'on échange ici par POST contre le vrai JWT (ou un défi 2FA).
 */
export default function SsoCallbackPage() {
  const { applyToken, completeMfaChallenge } = useAuth();
  const [error, setError] = useState('');
  const [mfaToken, setMfaToken] = useState(null);
  const [mfaCode, setMfaCode] = useState('');
  const [busy, setBusy] = useState(false);
  const doneRef = useRef(false);        // StrictMode monte 2× en dev : le code est à usage unique

  useEffect(() => {
    if (doneRef.current) return;
    doneRef.current = true;
    const params = new URLSearchParams(window.location.search);
    const err = params.get('error');
    const code = params.get('c');
    // On retire immédiatement le code de l'URL (historique, partage d'écran).
    window.history.replaceState({}, '', '/sso/callback');
    if (err) {
      // Object.prototype : `ERRORS['__proto__']` renverrait un objet (écran blanc).
      const msg = Object.prototype.hasOwnProperty.call(ERRORS, err) ? ERRORS[err] : null;
      setError(msg || 'Connexion SSO impossible.');
      return;
    }
    if (!code) { setError('Lien de connexion incomplet.'); return; }
    (async () => {
      try {
        // withCredentials : le cookie de liaison vit sur le domaine BACKEND, l'appel est cross-site
        const r = await axios.post(`${BACKEND_URL}/api/auth/oidc/exchange`, { code },
                                   { withCredentials: true });
        if (r.data?.mfa_required) { setMfaToken(r.data.mfa_token); return; }
        await applyToken(r.data.access_token);
        window.history.replaceState({}, '', '/dashboard');
        window.location.reload();
      } catch (e) {
        setError(e.response?.data?.detail || 'Connexion SSO impossible.');
      }
    })();
  }, [applyToken]);

  const submitMfa = async (e) => {
    e.preventDefault();
    setBusy(true); setError('');
    try {
      const res = await completeMfaChallenge(mfaToken, mfaCode);
      if (!res?.success) { setError(res?.error || 'Code invalide.'); return; }
      // App.js sert /sso/callback AVANT le test d'authentification : sans navigation explicite,
      // l'utilisateur resterait bloqué sur cette page alors qu'il est connecté.
      window.history.replaceState({}, '', '/dashboard');
      window.location.reload();
    } catch {
      setError('Code invalide.');
    } finally { setBusy(false); }
  };

  const box = {
    background: '#fff', borderRadius: 16, padding: 32, maxWidth: 420, width: '100%',
    boxShadow: '0 10px 30px rgba(0,0,0,0.08)', textAlign: 'center',
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center',
                  justifyContent: 'center', background: '#f8fafc', padding: 16 }}>
      <div style={box} data-testid="sso-callback">
        <div style={{ marginBottom: 16 }}><FactureProLogo /></div>
        {mfaToken ? (
          <form onSubmit={submitMfa}>
            <h3 style={{ margin: '0 0 8px', color: '#1f2937' }}>Vérification en deux étapes</h3>
            <p style={{ color: '#6b7280', fontSize: 14, margin: '0 0 16px' }}>
              Saisis le code de ton application d'authentification (ou un code de secours).
            </p>
            <input value={mfaCode} onChange={e => setMfaCode(e.target.value)} autoFocus
                   data-testid="sso-mfa-input" placeholder="123456"
                   style={{ width: '100%', padding: 12, border: '1px solid #d1d5db',
                            borderRadius: 8, fontSize: 18, textAlign: 'center',
                            letterSpacing: 2, boxSizing: 'border-box', marginBottom: 12 }} />
            <button type="submit" disabled={busy || !mfaCode}
                    style={{ width: '100%', background: '#00A08C', color: '#fff', border: 'none',
                             padding: 12, borderRadius: 8, fontWeight: 700,
                             cursor: busy ? 'wait' : 'pointer' }}>
              {busy ? 'Vérification…' : 'Valider'}
            </button>
          </form>
        ) : error ? (
          <>
            <h3 style={{ margin: '0 0 8px', color: '#b91c1c' }}>Connexion impossible</h3>
            <p style={{ color: '#374151', fontSize: 14, lineHeight: 1.6 }}>{error}</p>
          </>
        ) : (
          <p style={{ color: '#6b7280' }}>Connexion en cours…</p>
        )}
        {(error || mfaToken) && (
          <a href="/" style={{ display: 'inline-block', marginTop: 16, color: '#00A08C',
                               fontSize: 14 }}>← Retour à la connexion</a>
        )}
      </div>
    </div>
  );
}
