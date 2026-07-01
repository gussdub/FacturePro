import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { BACKEND_URL } from '../config';
import { useAuth } from '../context/AuthContext';
import FactureProLogo from '../components/FactureProLogo';
import { roleLabel } from '../constants/permissions';


function useQueryToken() {
  const [token, setToken] = useState(null);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setToken(params.get('token'));
  }, []);
  return token;
}


export default function AcceptInvitePage() {
  const token = useQueryToken();
  const { acceptInvite } = useAuth();
  const [preview, setPreview] = useState(null);
  const [previewError, setPreviewError] = useState(null);
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [pipedaConsent, setPipedaConsent] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  useEffect(() => {
    if (!token) return;
    axios.get(`${BACKEND_URL}/api/org/invitations/preview?token=${encodeURIComponent(token)}`)
      .then(r => setPreview(r.data))
      .catch(err => setPreviewError(err.response?.data?.detail || 'Invitation introuvable'));
  }, [token]);

  const submit = async (e) => {
    e.preventDefault();
    setSubmitError(null);
    if (password !== confirmPassword) {
      setSubmitError('Les mots de passe ne correspondent pas');
      return;
    }
    if (password.length < 6) {
      setSubmitError('Mot de passe trop court (min 6 caractères)');
      return;
    }
    if (!pipedaConsent) {
      setSubmitError('Vous devez accepter les CGU et la politique PIPEDA');
      return;
    }
    setSubmitting(true);
    const result = await acceptInvite({ token, password, pipeda_consent: true });
    setSubmitting(false);
    if (result.success) {
      window.history.pushState({}, '', '/dashboard');
      window.dispatchEvent(new Event('popstate'));
    } else {
      setSubmitError(result.error);
    }
  };

  if (!token) {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <h2>Lien d'invitation invalide</h2>
        <p>Le token est absent de l'URL.</p>
      </div>
    );
  }

  if (previewError) {
    return (
      <div style={{ padding: 40, textAlign: 'center', maxWidth: 500, margin: '0 auto' }}>
        <FactureProLogo />
        <h2 style={{ color: '#991b1b', marginTop: 24 }}>Invitation invalide</h2>
        <p style={{ color: '#6b7280' }}>{previewError}</p>
        <p style={{ marginTop: 16, fontSize: 13 }}>
          Demandez au propriétaire de l'organisation de vous envoyer une nouvelle invitation.
        </p>
      </div>
    );
  }

  if (!preview) return <div style={{ padding: 40 }}>Chargement…</div>;

  return (
    <div style={{ padding: 40, maxWidth: 500, margin: '0 auto' }}>
      <div style={{ textAlign: 'center', marginBottom: 32 }}>
        <FactureProLogo />
      </div>
      <h1 style={{ fontSize: 22, marginBottom: 8, textAlign: 'center' }}>Rejoindre {preview.org_name}</h1>
      <p style={{ color: '#6b7280', textAlign: 'center', marginBottom: 24 }}>
        Vous avez été invité(e) en tant que <strong>{roleLabel(preview.role)}</strong>.
      </p>

      <form onSubmit={submit}>
        <div style={{ marginBottom: 16 }}>
          <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
            Email
          </label>
          <input type="email" value={preview.email} readOnly
                 style={{
                   width: '100%', padding: 10, border: '1px solid #d1d5db',
                   borderRadius: 6, fontSize: 14, background: '#f9fafb',
                   boxSizing: 'border-box',
                 }} />
        </div>

        <div style={{ marginBottom: 16 }}>
          <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
            Mot de passe
          </label>
          <input type="password" required autoFocus value={password}
                 onChange={e => setPassword(e.target.value)}
                 placeholder="Min. 6 caractères"
                 style={{
                   width: '100%', padding: 10, border: '1px solid #d1d5db',
                   borderRadius: 6, fontSize: 14, boxSizing: 'border-box',
                 }} />
          <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>
            Si vous avez déjà un compte FacturePro avec cet email, entrez votre mot de passe existant.
          </div>
        </div>

        <div style={{ marginBottom: 16 }}>
          <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
            Confirmer le mot de passe
          </label>
          <input type="password" required value={confirmPassword}
                 onChange={e => setConfirmPassword(e.target.value)}
                 style={{
                   width: '100%', padding: 10, border: '1px solid #d1d5db',
                   borderRadius: 6, fontSize: 14, boxSizing: 'border-box',
                 }} />
        </div>

        <div style={{ marginBottom: 24 }}>
          <label style={{ display: 'flex', gap: 8, alignItems: 'flex-start', fontSize: 13, cursor: 'pointer' }}>
            <input type="checkbox" checked={pipedaConsent}
                   onChange={e => setPipedaConsent(e.target.checked)}
                   style={{ marginTop: 2 }} />
            <span>
              J'accepte les <a href="/cgu" target="_blank" style={{ color: '#00A08C' }}>Conditions générales d'utilisation</a> et la <a href="/privacy" target="_blank" style={{ color: '#00A08C' }}>politique de confidentialité (PIPEDA)</a>.
            </span>
          </label>
        </div>

        {submitError && (
          <div style={{ background: '#fee2e2', color: '#991b1b', padding: 10, borderRadius: 6, marginBottom: 16, fontSize: 13 }}>
            {submitError}
          </div>
        )}

        <button type="submit" disabled={submitting} style={{
          width: '100%', background: '#00A08C', color: '#fff', border: 'none',
          padding: 12, borderRadius: 6, cursor: 'pointer', fontWeight: 600, fontSize: 15,
        }}>
          {submitting ? 'Acceptation en cours…' : 'Accepter l\'invitation'}
        </button>
      </form>
    </div>
  );
}
