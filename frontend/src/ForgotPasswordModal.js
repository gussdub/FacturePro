import React, { useState } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'https://facturepro-api.onrender.com';

const ForgotPasswordModal = ({ onClose }) => {
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setMessage('');

    try {
      // In production, this would call your password reset endpoint
      await axios.post(`${BACKEND_URL}/api/auth/forgot-password`, { email });
      setMessage('Un email de réinitialisation a été envoyé à votre adresse.');
    } catch (error) {
      setError('Email non trouvé ou erreur du serveur.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0, 0, 0, 0.5)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
      padding: '20px'
    }}>
      <div style={{
        background: 'white',
        borderRadius: '12px',
        padding: '32px',
        maxWidth: '400px',
        width: '100%',
        position: 'relative'
      }}>
        <button
          onClick={onClose}
          style={{
            position: 'absolute',
            top: '16px',
            right: '16px',
            background: 'none',
            border: 'none',
            fontSize: '24px',
            cursor: 'pointer',
            color: '#6b7280'
          }}
        >
          ×
        </button>

        <h2 style={{ marginTop: 0, marginBottom: '8px', color: '#1f2937' }}>
          🔑 Mot de passe oublié ?
        </h2>
        <p style={{ color: '#6b7280', marginBottom: '24px', fontSize: '14px' }}>
          Entrez votre adresse email et nous vous enverrons un lien pour réinitialiser votre mot de passe.
        </p>

        {message && (
          <div style={{
            background: '#d1fae5',
            border: '1px solid #6ee7b7',
            borderRadius: '8px',
            padding: '12px',
            marginBottom: '16px',
            color: '#065f46',
            fontSize: '14px'
          }}>
            {message}
          </div>
        )}

        {error && (
          <div style={{
            background: '#fee2e2',
            border: '1px solid #fecaca',
            borderRadius: '8px',
            padding: '12px',
            marginBottom: '16px',
            color: '#b91c1c',
            fontSize: '14px'
          }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: '#374151', marginBottom: '8px' }}>
              Adresse email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="votre@email.com"
              required
              style={{
                width: '100%',
                height: '48px',
                fontSize: '16px',
                padding: '12px',
                border: '1px solid #d1d5db',
                borderRadius: '8px',
                boxSizing: 'border-box'
              }}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              height: '48px',
              fontSize: '16px',
              fontWeight: '600',
              background: loading ? '#9ca3af' : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              cursor: loading ? 'not-allowed' : 'pointer',
              marginBottom: '12px'
            }}
          >
            {loading ? 'Envoi en cours...' : 'Envoyer le lien'}
          </button>

          <button
            type="button"
            onClick={onClose}
            style={{
              width: '100%',
              height: '48px',
              fontSize: '16px',
              fontWeight: '500',
              background: 'white',
              color: '#374151',
              border: '1px solid #d1d5db',
              borderRadius: '8px',
              cursor: 'pointer'
            }}
          >
            Annuler
          </button>
        </form>
      </div>
    </div>
  );
};

export default ForgotPasswordModal;