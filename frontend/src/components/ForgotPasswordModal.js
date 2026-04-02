import React, { useState } from 'react';
import axios from 'axios';
import { BACKEND_URL } from '../config';

const ForgotPasswordModal = ({ onClose }) => {
  const [step, setStep] = useState('email');
  const [email, setEmail] = useState('');
  const [resetData, setResetData] = useState({ token: '', new_password: '', confirm_password: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleSendCode = async (e) => {
    e.preventDefault();
    setLoading(true); setError(''); setSuccess('');
    try {
      const response = await axios.post(`${BACKEND_URL}/api/auth/forgot-password`, { email });
      if (response.data.reset_token) {
        setResetData(prev => ({ ...prev, token: response.data.reset_token }));
        setSuccess('Code de recuperation genere ! Utilisez-le ci-dessous.');
        setStep('reset');
      }
    } catch (err) {
      setError('Erreur lors de la generation du code');
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async (e) => {
    e.preventDefault();
    if (resetData.new_password !== resetData.confirm_password) {
      setError('Les mots de passe ne correspondent pas');
      return;
    }
    setLoading(true); setError('');
    try {
      await axios.post(`${BACKEND_URL}/api/auth/reset-password`, {
        token: resetData.token, new_password: resetData.new_password
      });
      setSuccess('Mot de passe reinitialise avec succes !');
      setTimeout(onClose, 2000);
    } catch (err) {
      setError('Erreur lors de la reinitialisation');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center',
      justifyContent: 'center', zIndex: 1000, padding: '20px'
    }}>
      <div style={{ background: 'white', padding: '32px', borderRadius: '16px', maxWidth: '480px', width: '100%', position: 'relative' }}>
        <button onClick={onClose} style={{
          position: 'absolute', top: '16px', right: '16px', background: 'none',
          border: 'none', fontSize: '24px', cursor: 'pointer', color: '#6b7280'
        }}>x</button>

        <h2 style={{ margin: '0 0 20px 0', textAlign: 'center', color: '#1f2937' }}>
          {step === 'email' ? 'Recuperation de compte' : 'Nouveau mot de passe'}
        </h2>

        {success && (
          <div style={{
            background: '#d1fae5', border: '1px solid #6ee7b7', borderRadius: '8px',
            padding: '12px', marginBottom: '20px', color: '#065f46', fontSize: '14px', textAlign: 'center'
          }}>{success}</div>
        )}
        {error && (
          <div style={{
            background: '#fee2e2', border: '1px solid #fecaca', borderRadius: '8px',
            padding: '12px', marginBottom: '20px', color: '#b91c1c', fontSize: '14px', textAlign: 'center'
          }}>{error}</div>
        )}

        {step === 'email' ? (
          <form onSubmit={handleSendCode}>
            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', marginBottom: '8px', fontWeight: '600' }}>Email</label>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required
                style={{ width: '100%', padding: '12px', border: '1px solid #ddd', borderRadius: '8px', boxSizing: 'border-box' }} />
            </div>
            <div style={{ display: 'flex', gap: '12px' }}>
              <button type="button" onClick={onClose} style={{
                flex: 1, padding: '12px', background: '#f3f4f6', border: 'none', borderRadius: '8px', cursor: 'pointer'
              }}>Annuler</button>
              <button type="submit" disabled={loading} style={{
                flex: 1, padding: '12px', background: loading ? '#9ca3af' : '#00A08C',
                color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer'
              }}>{loading ? 'Generation...' : 'Generer code'}</button>
            </div>
          </form>
        ) : (
          <form onSubmit={handleResetPassword}>
            <div style={{ background: '#eff6ff', padding: '16px', borderRadius: '8px', marginBottom: '20px' }}>
              <strong>Code : </strong>
              <span style={{ fontFamily: 'monospace', wordBreak: 'break-all' }}>{resetData.token}</span>
            </div>
            <div style={{ marginBottom: '15px' }}>
              <input type="text" value={resetData.token}
                onChange={(e) => setResetData(prev => ({ ...prev, token: e.target.value }))}
                placeholder="Code de recuperation" required
                style={{ width: '100%', padding: '12px', border: '1px solid #ddd', borderRadius: '8px', fontFamily: 'monospace', boxSizing: 'border-box' }} />
            </div>
            <div style={{ marginBottom: '15px' }}>
              <input type="password" value={resetData.new_password}
                onChange={(e) => setResetData(prev => ({ ...prev, new_password: e.target.value }))}
                placeholder="Nouveau mot de passe" required
                style={{ width: '100%', padding: '12px', border: '1px solid #ddd', borderRadius: '8px', boxSizing: 'border-box' }} />
            </div>
            <div style={{ marginBottom: '20px' }}>
              <input type="password" value={resetData.confirm_password}
                onChange={(e) => setResetData(prev => ({ ...prev, confirm_password: e.target.value }))}
                placeholder="Confirmer mot de passe" required
                style={{ width: '100%', padding: '12px', border: '1px solid #ddd', borderRadius: '8px', boxSizing: 'border-box' }} />
            </div>
            <div style={{ display: 'flex', gap: '12px' }}>
              <button type="button" onClick={() => setStep('email')} style={{
                flex: 1, padding: '12px', background: '#f3f4f6', border: 'none', borderRadius: '8px', cursor: 'pointer'
              }}>Retour</button>
              <button type="submit" disabled={loading} style={{
                flex: 1, padding: '12px', background: loading ? '#9ca3af' : '#00A08C',
                color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer'
              }}>{loading ? 'Reinitialisation...' : 'Reinitialiser'}</button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};

export default ForgotPasswordModal;
