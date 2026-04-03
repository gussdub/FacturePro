import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { BACKEND_URL, FACTUREPRO_LOGO_FILE_ID } from '../config';
import ForgotPasswordModal from '../components/ForgotPasswordModal';
import { Zap, RefreshCw, Shield } from 'lucide-react';

const factureProLogoUrl = `${BACKEND_URL}/api/files/${FACTUREPRO_LOGO_FILE_ID}`;

const LoginPage = () => {
  const [formData, setFormData] = useState({ email: '', password: '', companyName: '' });
  const [isLogin, setIsLogin] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [showForgotPassword, setShowForgotPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login, register } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      let result;
      if (isLogin) {
        result = await login(formData.email, formData.password);
      } else {
        result = await register(formData.email, formData.password, formData.companyName);
      }
      if (!result.success) setError(result.error);
    } catch (err) {
      setError('Une erreur est survenue');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e) => {
    setFormData(prev => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const inputStyle = {
    width: '100%', height: '44px', fontSize: '14px', padding: '10px 14px',
    border: '1px solid #e4e4e7', borderRadius: '6px', boxSizing: 'border-box',
    outline: 'none', transition: 'border-color 0.15s ease',
    fontFamily: "'IBM Plex Sans', sans-serif"
  };

  const features = [
    { icon: Zap, title: 'Facturation instantanee', desc: 'Creez et envoyez vos factures en quelques clics' },
    { icon: RefreshCw, title: 'Recurrence automatique', desc: 'Programmez vos factures recurrentes' },
    { icon: Shield, title: 'Securise et conforme', desc: 'Taxes canadiennes calculees automatiquement' }
  ];

  return (
    <div style={{
      minHeight: '100vh', display: 'flex',
      fontFamily: "'IBM Plex Sans', -apple-system, sans-serif"
    }}>
      {/* Left Panel */}
      <div style={{
        width: '50%', background: '#09090b',
        display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: '60px 64px',
        position: 'relative'
      }}>
        <div style={{ position: 'relative', zIndex: 10 }}>
          <div style={{ marginBottom: '40px' }}>
            <img src={factureProLogoUrl} alt="FacturePro" style={{ width: '48px', height: '48px', objectFit: 'contain', marginBottom: '32px', borderRadius: '8px' }} />
            <h1 style={{ fontSize: '48px', fontWeight: '700', lineHeight: '1.05', margin: '0 0 16px', color: '#ffffff', letterSpacing: '-0.04em' }}>
              Simplifiez votre facturation
            </h1>
            <p style={{ fontSize: '16px', color: '#a1a1aa', lineHeight: '1.7', margin: 0, maxWidth: '440px' }}>
              Gerez vos factures, devis et clients en toute simplicite avec notre solution complete pour entreprises canadiennes.
            </p>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {features.map((feature, i) => {
              const Icon = feature.icon;
              return (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: '14px',
                  background: 'rgba(255,255,255,0.05)', padding: '14px 18px',
                  borderRadius: '6px', border: '1px solid rgba(255,255,255,0.08)'
                }}>
                  <Icon size={20} strokeWidth={1.5} color="#a1a1aa" />
                  <div>
                    <div style={{ fontWeight: '600', fontSize: '14px', color: '#ffffff' }}>{feature.title}</div>
                    <div style={{ fontSize: '12px', color: '#71717a' }}>{feature.desc}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Subtle decoration */}
        <div style={{ position: 'absolute', bottom: '32px', left: '64px', fontSize: '12px', color: '#3f3f46' }}>
          FacturePro &copy; 2026
        </div>
      </div>

      {/* Right Panel - Form */}
      <div style={{ width: '50%', background: '#ffffff', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '40px' }}>
        <div style={{ width: '100%', maxWidth: '400px' }}>
          <div style={{ marginBottom: '32px' }}>
            <h2 style={{ fontSize: '24px', fontWeight: '700', color: '#09090b', margin: '0 0 6px', letterSpacing: '-0.03em' }}>
              {isLogin ? 'Connexion' : 'Creer un compte'}
            </h2>
            <p style={{ color: '#a1a1aa', margin: 0, fontSize: '14px' }}>
              {isLogin ? 'Accedez a votre tableau de bord' : 'Demarrez votre essai gratuit de 14 jours'}
            </p>
          </div>

          {error && (
            <div style={{
              background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '6px',
              padding: '12px 14px', marginBottom: '20px', color: '#dc2626', fontSize: '13px'
            }}>{error}</div>
          )}

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
            {!isLogin && (
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: '#52525b', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Nom de l'entreprise
                </label>
                <input type="text" name="companyName" value={formData.companyName} onChange={handleChange}
                  placeholder="Mon Entreprise" required data-testid="register-company-input"
                  style={inputStyle}
                  onFocus={e => e.target.style.borderColor = '#09090b'}
                  onBlur={e => e.target.style.borderColor = '#e4e4e7'}
                />
              </div>
            )}

            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: '#52525b', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Adresse email
              </label>
              <input type="email" name="email" value={formData.email} onChange={handleChange}
                placeholder="votre@email.com" required data-testid="login-email-input"
                style={inputStyle}
                onFocus={e => e.target.style.borderColor = '#09090b'}
                onBlur={e => e.target.style.borderColor = '#e4e4e7'}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: '#52525b', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Mot de passe
              </label>
              <div style={{ position: 'relative' }}>
                <input type={showPassword ? "text" : "password"} name="password" value={formData.password}
                  onChange={handleChange} placeholder="••••••••" required data-testid="login-password-input"
                  style={{ ...inputStyle, paddingRight: '44px' }}
                  onFocus={e => e.target.style.borderColor = '#09090b'}
                  onBlur={e => e.target.style.borderColor = '#e4e4e7'}
                />
                <button type="button" onClick={() => setShowPassword(!showPassword)} style={{
                  position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)',
                  background: 'none', border: 'none', cursor: 'pointer', color: '#a1a1aa', padding: '4px',
                  display: 'flex', alignItems: 'center'
                }}>
                  {showPassword ? (
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="m2 2 20 20"/>
                      <path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/>
                      <path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/>
                    </svg>
                  ) : (
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/>
                    </svg>
                  )}
                </button>
              </div>
            </div>

            <button type="submit" disabled={loading} data-testid="login-submit-btn" style={{
              width: '100%', height: '44px', fontSize: '14px', fontWeight: '600',
              background: loading ? '#a1a1aa' : '#09090b',
              color: '#ffffff', border: 'none', borderRadius: '6px',
              cursor: loading ? 'not-allowed' : 'pointer',
              transition: 'all 0.15s ease', marginTop: '4px'
            }}
            onMouseEnter={e => { if (!loading) e.target.style.background = '#27272a'; }}
            onMouseLeave={e => { if (!loading) e.target.style.background = '#09090b'; }}
            >
              {loading ? 'Chargement...' : (isLogin ? 'Se connecter' : 'Creer mon compte')}
            </button>
          </form>

          {isLogin && (
            <div style={{ marginTop: '14px', textAlign: 'center' }}>
              <button type="button" onClick={() => setShowForgotPassword(true)} data-testid="forgot-password-btn" style={{
                background: 'none', border: 'none', color: '#a1a1aa', fontSize: '13px', cursor: 'pointer',
                transition: 'color 0.15s'
              }}
              onMouseEnter={e => e.target.style.color = '#09090b'}
              onMouseLeave={e => e.target.style.color = '#a1a1aa'}
              >
                Mot de passe oublie ?
              </button>
            </div>
          )}

          <div style={{ marginTop: '24px', textAlign: 'center', borderTop: '1px solid #e4e4e7', paddingTop: '20px' }}>
            <button type="button" data-testid="toggle-auth-btn" onClick={() => {
              setIsLogin(!isLogin); setError('');
              setFormData({ email: '', password: '', companyName: '' });
            }} style={{ background: 'none', border: 'none', color: '#52525b', fontSize: '13px', cursor: 'pointer' }}>
              {isLogin ? (
                <>Pas encore de compte ? <strong style={{ color: '#09090b' }}>S'inscrire</strong></>
              ) : (
                <>Deja un compte ? <strong style={{ color: '#09090b' }}>Se connecter</strong></>
              )}
            </button>
          </div>
        </div>
      </div>

      {showForgotPassword && <ForgotPasswordModal onClose={() => setShowForgotPassword(false)} />}
    </div>
  );
};

export default LoginPage;
