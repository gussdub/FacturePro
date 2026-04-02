import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import ForgotPasswordModal from '../components/ForgotPasswordModal';
import FactureProLogo from '../components/FactureProLogo';

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

  return (
    <div style={{
      minHeight: '100vh', background: 'linear-gradient(to-br, #f0fdfa, #ccfbf1, #d1fae5)',
      display: 'flex', fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
    }}>
      {/* Left Hero Section */}
      <div style={{
        width: '50%', background: 'linear-gradient(135deg, #00A08C, #47D2A7)',
        position: 'relative', overflow: 'hidden', display: 'flex',
        flexDirection: 'column', justifyContent: 'center', padding: '60px'
      }}>
        <div style={{ position: 'absolute', top: '80px', left: '80px', width: '288px', height: '288px', background: 'rgba(255,255,255,0.1)', borderRadius: '50%', filter: 'blur(48px)' }} />
        <div style={{ position: 'absolute', bottom: '80px', right: '80px', width: '384px', height: '384px', background: 'rgba(71,210,167,0.2)', borderRadius: '50%', filter: 'blur(48px)' }} />

        <div style={{ position: 'relative', zIndex: 10, color: 'white' }}>
          <div style={{ marginBottom: '32px' }}>
            <FactureProLogo size={64} />
            <h1 style={{ fontSize: '80px', fontWeight: 'bold', lineHeight: '1.1', margin: 0 }}>
              Simplifiez votre
              <span style={{ display: 'block', color: '#a7f3d0' }}>facturation</span>
            </h1>
            <p style={{ fontSize: '20px', color: 'rgba(255,255,255,0.8)', lineHeight: '1.6', margin: 0 }}>
              Gerez vos factures, devis et clients en toute simplicite avec notre solution complete et intuitive.
            </p>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {[
              { icon: '⚡', title: 'Facturation instantanee', desc: 'Creez et envoyez vos factures en quelques clics' },
              { icon: '🔄', title: 'Recurrence automatique', desc: 'Programmez vos factures recurrentes' },
              { icon: '🛡️', title: 'Securise et conforme', desc: 'Taxes canadiennes calculees automatiquement' }
            ].map((feature, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: '16px',
                background: 'rgba(255,255,255,0.15)', padding: '16px 24px',
                borderRadius: '12px', backdropFilter: 'blur(10px)'
              }}>
                <div style={{ fontSize: '28px' }}>{feature.icon}</div>
                <div>
                  <div style={{ fontWeight: '600', fontSize: '18px' }}>{feature.title}</div>
                  <div style={{ fontSize: '14px', opacity: 0.9 }}>{feature.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right side - Form */}
      <div style={{ width: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '40px' }}>
        <div style={{ width: '100%', maxWidth: '460px' }}>
          <div style={{ textAlign: 'center', marginBottom: '40px' }}>
            <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: '88px', height: '88px', borderRadius: '24px', marginBottom: '24px', overflow: 'hidden' }}>
              <FactureProLogo size={88} />
            </div>
            <h1 style={{ fontSize: '36px', fontWeight: '800', color: '#1e293b', margin: '0 0 8px 0' }}>FacturePro</h1>
            <h2 style={{ fontSize: '22px', fontWeight: '600', color: '#475569', margin: '0 0 8px 0' }}>
              {isLogin ? 'Connexion' : 'Creer un compte'}
            </h2>
            <p style={{ color: '#64748b', margin: 0, fontSize: '16px' }}>
              {isLogin ? 'Accedez a votre tableau de bord' : 'Demarrez votre essai gratuit aujourd\'hui'}
            </p>
          </div>

          <div style={{
            background: 'rgba(255,255,255,0.95)', backdropFilter: 'blur(20px)',
            padding: '32px', borderRadius: '24px', boxShadow: '0 25px 50px -12px rgba(0,0,0,0.15)', border: 'none'
          }}>
            {error && (
              <div style={{
                background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '12px',
                padding: '16px', marginBottom: '24px', color: '#b91c1c', fontSize: '14px'
              }}>{error}</div>
            )}

            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              {!isLogin && (
                <div>
                  <label style={{ display: 'block', fontSize: '14px', fontWeight: '600', color: '#374151', marginBottom: '8px' }}>
                    Nom de l'entreprise *
                  </label>
                  <input type="text" name="companyName" value={formData.companyName} onChange={handleChange}
                    placeholder="Mon Entreprise" required data-testid="register-company-input"
                    style={{ width: '100%', height: '48px', fontSize: '16px', padding: '12px 16px', border: '1px solid #d1d5db', borderRadius: '12px', boxSizing: 'border-box' }} />
                </div>
              )}

              <div>
                <label style={{ display: 'block', fontSize: '14px', fontWeight: '600', color: '#374151', marginBottom: '8px' }}>Adresse email *</label>
                <input type="email" name="email" value={formData.email} onChange={handleChange}
                  placeholder="votre@email.com" required data-testid="login-email-input"
                  style={{ width: '100%', height: '48px', fontSize: '16px', padding: '12px 16px', border: '1px solid #d1d5db', borderRadius: '12px', boxSizing: 'border-box' }} />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '14px', fontWeight: '600', color: '#374151', marginBottom: '8px' }}>Mot de passe *</label>
                <div style={{ position: 'relative' }}>
                  <input type={showPassword ? "text" : "password"} name="password" value={formData.password}
                    onChange={handleChange} placeholder="••••••••••" required data-testid="login-password-input"
                    style={{ width: '100%', height: '48px', fontSize: '16px', padding: '12px 52px 12px 16px', border: '1px solid #d1d5db', borderRadius: '12px', boxSizing: 'border-box' }} />
                  <button type="button" onClick={() => setShowPassword(!showPassword)} style={{
                    position: 'absolute', right: '12px', top: '50%', transform: 'translateY(-50%)',
                    background: 'none', border: 'none', cursor: 'pointer', color: '#6b7280', fontSize: '20px'
                  }}>
                    {showPassword ? (
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="m2 2 20 20"/>
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                      </svg>
                    ) : (
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
                      </svg>
                    )}
                  </button>
                </div>
              </div>

              <button type="submit" disabled={loading} data-testid="login-submit-btn" style={{
                width: '100%', height: '48px', fontSize: '16px', fontWeight: '700',
                background: loading ? '#94a3b8' : 'linear-gradient(135deg, #00A08C 0%, #47D2A7 100%)',
                color: 'white', border: 'none', borderRadius: '12px',
                cursor: loading ? 'not-allowed' : 'pointer', boxShadow: '0 10px 25px rgba(0,160,140,0.4)'
              }}>
                {loading ? 'Chargement...' : (isLogin ? 'Se connecter' : 'Creer mon compte')}
              </button>
            </form>

            {isLogin && (
              <div style={{ marginTop: '16px', textAlign: 'center' }}>
                <button type="button" onClick={() => setShowForgotPassword(true)} data-testid="forgot-password-btn" style={{
                  background: 'none', border: 'none', color: '#00A08C', fontSize: '14px', cursor: 'pointer', textDecoration: 'underline'
                }}>
                  Mot de passe oublie ?
                </button>
              </div>
            )}

            <div style={{ marginTop: '24px', textAlign: 'center' }}>
              <button type="button" data-testid="toggle-auth-btn" onClick={() => {
                setIsLogin(!isLogin); setError('');
                setFormData({ email: '', password: '', companyName: '' });
              }} style={{ background: 'none', border: 'none', color: '#00A08C', fontSize: '16px', fontWeight: '600', cursor: 'pointer' }}>
                {isLogin ? "Pas encore de compte ? S'inscrire" : "Deja un compte ? Se connecter"}
              </button>
            </div>
          </div>

          {!isLogin && (
            <div style={{ marginTop: '24px', textAlign: 'center', fontSize: '14px', color: '#64748b' }}>
              En creant un compte, vous acceptez nos{' '}
              <a href="#terms" style={{ color: '#00A08C', textDecoration: 'none' }}>conditions d'utilisation</a>{' '}
              et notre{' '}
              <a href="#privacy" style={{ color: '#00A08C', textDecoration: 'none' }}>politique de confidentialite</a>
            </div>
          )}
        </div>
      </div>

      {showForgotPassword && <ForgotPasswordModal onClose={() => setShowForgotPassword(false)} />}

      <style>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
    </div>
  );
};

export default LoginPage;
