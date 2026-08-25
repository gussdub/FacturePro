import React, { useState } from 'react';
import axios from 'axios';
import { BACKEND_URL } from '../config';
import { useAuth } from '../context/AuthContext';

// Paramètres → Sécurité : activation/désactivation de la double authentification (TOTP).
const TEAL = '#00A08C';
const btn = (disabled) => ({
  background: disabled ? '#9ca3af' : TEAL, color: 'white', border: 'none',
  padding: '10px 18px', borderRadius: 8, cursor: disabled ? 'not-allowed' : 'pointer',
  fontSize: 14, fontWeight: 600,
});
const input = {
  width: '100%', maxWidth: 260, padding: '10px 12px', fontSize: 16, letterSpacing: 1,
  border: '1px solid #d1d5db', borderRadius: 8, boxSizing: 'border-box',
};

const MfaSettings = () => {
  const { user, refreshUser } = useAuth();
  const enabled = !!user?.mfa_enabled;

  const [setupData, setSetupData] = useState(null);   // {secret, otpauth_uri}
  const [code, setCode] = useState('');
  const [backupCodes, setBackupCodes] = useState(null);
  const [disarmCode, setDisarmCode] = useState('');
  const [showDisable, setShowDisable] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const startSetup = async () => {
    setBusy(true); setError(''); setBackupCodes(null);
    try {
      const r = await axios.post(`${BACKEND_URL}/api/auth/mfa/setup`);
      setSetupData(r.data); setCode('');
    } catch (e) { setError(e.response?.data?.detail || 'Erreur'); }
    finally { setBusy(false); }
  };

  const confirmEnable = async (e) => {
    e.preventDefault();
    setBusy(true); setError('');
    try {
      const r = await axios.post(`${BACKEND_URL}/api/auth/mfa/enable`, { code });
      setBackupCodes(r.data.backup_codes);
      setSetupData(null); setCode('');
      await refreshUser();
    } catch (e2) { setError(e2.response?.data?.detail || 'Code invalide'); }
    finally { setBusy(false); }
  };

  const disable = async (e) => {
    e.preventDefault();
    setBusy(true); setError('');
    try {
      await axios.post(`${BACKEND_URL}/api/auth/mfa/disable`, { code: disarmCode });
      setShowDisable(false); setDisarmCode('');
      await refreshUser();
    } catch (e2) { setError(e2.response?.data?.detail || 'Code invalide'); }
    finally { setBusy(false); }
  };

  return (
    <div style={{ maxWidth: 640 }}>
      <h3 style={{ fontSize: 18, color: '#1f2937', margin: '0 0 4px' }}>Double authentification (2FA)</h3>
      <p style={{ color: '#6b7280', fontSize: 14, marginTop: 0 }}>
        Ajoute une étape de vérification à la connexion via une application d'authentification
        (Google Authenticator, Authy, 1Password…). Fortement recommandé pour des données financières.
      </p>

      {error && (
        <div style={{ background: '#fee2e2', border: '1px solid #fecaca', borderRadius: 8,
          padding: '10px 12px', margin: '12px 0', color: '#b91c1c', fontSize: 13 }}>{error}</div>
      )}

      {/* Codes de secours après activation (affichés UNE seule fois) */}
      {backupCodes && (
        <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 10, padding: 16, margin: '12px 0' }}>
          <strong style={{ color: '#065f46' }}>✓ Double authentification activée.</strong>
          <p style={{ fontSize: 13, color: '#374151', margin: '8px 0' }}>
            Conserve ces <strong>codes de secours</strong> en lieu sûr — ils permettent de te connecter
            si tu perds ton téléphone. Chaque code ne sert qu'une fois. <strong>Ils ne seront plus jamais affichés.</strong>
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontFamily: 'monospace', fontSize: 15 }}>
            {backupCodes.map((c) => <span key={c} style={{ background: 'white', border: '1px solid #d1fae5', borderRadius: 6, padding: '6px 10px', textAlign: 'center' }}>{c}</span>)}
          </div>
          <button onClick={() => setBackupCodes(null)} style={{ ...btn(false), marginTop: 12 }}>J'ai noté mes codes</button>
        </div>
      )}

      {/* État activé */}
      {enabled && !backupCodes && (
        <div>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, background: '#ecfdf5',
            border: '1px solid #a7f3d0', borderRadius: 999, padding: '6px 14px', color: '#065f46', fontWeight: 600, fontSize: 14 }}>
            🔒 Activée
          </div>
          {!showDisable ? (
            <div style={{ marginTop: 16 }}>
              <button onClick={() => { setShowDisable(true); setError(''); }}
                style={{ background: '#fff', color: '#b91c1c', border: '1px solid #fecaca', padding: '10px 18px', borderRadius: 8, cursor: 'pointer', fontSize: 14, fontWeight: 600 }}>
                Désactiver la 2FA
              </button>
            </div>
          ) : (
            <form onSubmit={disable} style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
              <label style={{ fontSize: 13, color: '#374151' }}>
                Entre un code de ton application (ou un code de secours) pour confirmer :
              </label>
              <input type="text" inputMode="numeric" value={disarmCode} onChange={(e) => setDisarmCode(e.target.value)}
                placeholder="123 456" data-testid="mfa-disable-code" style={input} />
              <div style={{ display: 'flex', gap: 8 }}>
                <button type="submit" disabled={busy} style={{ background: busy ? '#9ca3af' : '#dc2626', color: 'white', border: 'none', padding: '10px 18px', borderRadius: 8, cursor: 'pointer', fontSize: 14, fontWeight: 600 }}>
                  {busy ? '...' : 'Confirmer la désactivation'}
                </button>
                <button type="button" onClick={() => { setShowDisable(false); setDisarmCode(''); setError(''); }}
                  style={{ background: '#f3f4f6', border: 'none', padding: '10px 18px', borderRadius: 8, cursor: 'pointer' }}>Annuler</button>
              </div>
            </form>
          )}
        </div>
      )}

      {/* Activation : étape 1 (démarrer) */}
      {!enabled && !setupData && !backupCodes && (
        <button onClick={startSetup} disabled={busy} data-testid="mfa-start-setup" style={btn(busy)}>
          {busy ? '...' : 'Activer la double authentification'}
        </button>
      )}

      {/* Activation : étape 2 (scanner/saisir + confirmer) */}
      {!enabled && setupData && (
        <div style={{ marginTop: 12, border: '1px solid #e5e7eb', borderRadius: 10, padding: 16 }}>
          <p style={{ fontSize: 14, color: '#374151', marginTop: 0 }}>
            1. Dans ton application d'authentification, ajoute un compte en saisissant cette clé
            (ou en collant le lien) :
          </p>
          <div style={{ background: '#f8fafb', border: '1px dashed #cbd5e1', borderRadius: 8, padding: 12, marginBottom: 12 }}>
            <div style={{ fontSize: 12, color: '#6b7280' }}>Clé de configuration</div>
            <code style={{ fontSize: 16, letterSpacing: 2, wordBreak: 'break-all', color: '#111827' }}>{setupData.secret}</code>
            <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 8, wordBreak: 'break-all' }}>{setupData.otpauth_uri}</div>
          </div>
          <form onSubmit={confirmEnable} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <label style={{ fontSize: 14, color: '#374151' }}>2. Entre le code à 6 chiffres généré :</label>
            <input type="text" inputMode="numeric" autoComplete="one-time-code" value={code}
              onChange={(e) => setCode(e.target.value)} placeholder="123 456" data-testid="mfa-enable-code" style={input} />
            <div style={{ display: 'flex', gap: 8 }}>
              <button type="submit" disabled={busy} data-testid="mfa-confirm-enable" style={btn(busy)}>
                {busy ? '...' : 'Vérifier et activer'}
              </button>
              <button type="button" onClick={() => { setSetupData(null); setCode(''); setError(''); }}
                style={{ background: '#f3f4f6', border: 'none', padding: '10px 18px', borderRadius: 8, cursor: 'pointer' }}>Annuler</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};

export default MfaSettings;
