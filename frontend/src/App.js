import React, { useState, createContext, useContext, useEffect } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'https://facturepro-api.onrender.com';

// Auth Context
const AuthContext = createContext();
export const useAuth = () => useContext(AuthContext);

// Forgot Password Modal - Complete workflow
const ForgotPasswordModal = ({ onClose }) => {
  const [step, setStep] = useState('email'); // 'email' or 'reset'
  const [email, setEmail] = useState('');
  const [resetData, setResetData] = useState({
    token: '',
    new_password: '',
    confirm_password: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleSendCode = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');

    try {
      const response = await axios.post(`${BACKEND_URL}/api/auth/forgot-password`, { email });
      
      if (response.data.reset_token) {
        setResetData(prev => ({ ...prev, token: response.data.reset_token }));
        setSuccess('Code de récupération généré ! Utilisez-le ci-dessous.');
        setStep('reset');
      } else {
        setSuccess(response.data.message);
      }
    } catch (error) {
      setError(error.response?.data?.detail || 'Erreur lors de la génération du code');
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

    if (resetData.new_password.length < 6) {
      setError('Le mot de passe doit contenir au moins 6 caractères');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await axios.post(`${BACKEND_URL}/api/auth/reset-password`, {
        token: resetData.token,
        new_password: resetData.new_password
      });

      setSuccess('Mot de passe réinitialisé avec succès ! Vous pouvez maintenant vous connecter.');
      
      // Auto-close after success
      setTimeout(() => {
        onClose();
      }, 2000);
      
    } catch (error) {
      setError(error.response?.data?.detail || 'Erreur lors de la réinitialisation');
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
      <div style={{
        background: 'white', padding: '32px', borderRadius: '16px',
        maxWidth: '480px', width: '100%', position: 'relative'
      }}>
        <button
          onClick={onClose}
          style={{
            position: 'absolute', top: '16px', right: '16px',
            background: 'none', border: 'none', fontSize: '28px',
            cursor: 'pointer', color: '#6b7280'
          }}
        >
          ×
        </button>

        <div style={{ textAlign: 'center', marginBottom: '24px' }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              width: '64px', height: '64px',
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              borderRadius: '16px', marginBottom: '16px'
            }}>
              {/* Key SVG Icon for forgot password */}
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="8" cy="8" r="6"/>
                <path d="m13 13 6 6"/>
                <path d="M13 13v4a2 2 0 0 1-2 2h-3"/>
              </svg>
            </div>
          <h2 style={{ margin: 0, color: '#1f2937', fontSize: '24px' }}>
            {step === 'email' ? 'Récupération de compte' : 'Nouveau mot de passe'}
          </h2>
        </div>

        {success && (
          <div style={{
            background: '#d1fae5', border: '1px solid #6ee7b7',
            borderRadius: '8px', padding: '12px', marginBottom: '20px',
            color: '#065f46', fontSize: '14px', textAlign: 'center'
          }}>
            {success}
          </div>
        )}

        {error && (
          <div style={{
            background: '#fee2e2', border: '1px solid #fecaca',
            borderRadius: '8px', padding: '12px', marginBottom: '20px',
            color: '#b91c1c', fontSize: '14px', textAlign: 'center'
          }}>
            {error}
          </div>
        )}

        {step === 'email' ? (
          <form onSubmit={handleSendCode}>
            <p style={{ color: '#6b7280', marginBottom: '20px', textAlign: 'center' }}>
              Entrez votre adresse email pour recevoir un code de récupération
            </p>
            
            <div style={{ marginBottom: '24px' }}>
              <label style={{
                display: 'block', fontSize: '14px', fontWeight: '600',
                color: '#374151', marginBottom: '8px'
              }}>
                Adresse email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="votre@email.com"
                required
                style={{
                  width: '100%', height: '48px', fontSize: '16px',
                  padding: '12px', border: '1px solid #d1d5db',
                  borderRadius: '8px', boxSizing: 'border-box'
                }}
              />
            </div>

            <div style={{ display: 'flex', gap: '12px' }}>
              <button
                type="button"
                onClick={onClose}
                style={{
                  flex: 1, height: '48px', fontSize: '16px', fontWeight: '500',
                  background: 'white', color: '#374151', border: '1px solid #d1d5db',
                  borderRadius: '8px', cursor: 'pointer'
                }}
              >
                Annuler
              </button>
              <button
                type="submit"
                disabled={loading || !email}
                style={{
                  flex: 1, height: '48px', fontSize: '16px', fontWeight: '600',
                  background: loading ? '#9ca3af' : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  color: 'white', border: 'none', borderRadius: '8px',
                  cursor: loading ? 'not-allowed' : 'pointer'
                }}
              >
                {loading ? 'Génération...' : 'Générer le code'}
              </button>
            </div>
          </form>
        ) : (
          <form onSubmit={handleResetPassword}>
            <div style={{
              background: '#eff6ff', border: '1px solid #3b82f6',
              borderRadius: '8px', padding: '16px', marginBottom: '20px'
            }}>
              <p style={{ margin: '0 0 8px 0', fontSize: '14px', fontWeight: '600', color: '#1e40af' }}>
                Code de récupération :
              </p>
              <div style={{
                background: 'white', border: '1px solid #3b82f6',
                borderRadius: '6px', padding: '12px', fontFamily: 'monospace',
                fontSize: '14px', wordBreak: 'break-all', color: '#1e40af'
              }}>
                {resetData.token}
              </div>
              <p style={{ margin: '8px 0 0 0', fontSize: '12px', color: '#3730a3' }}>
                Copiez ce code et collez-le ci-dessous
              </p>
            </div>

            <div style={{ marginBottom: '20px' }}>
              <label style={{
                display: 'block', fontSize: '14px', fontWeight: '600',
                color: '#374151', marginBottom: '8px'
              }}>
                Code de récupération
              </label>
              <input
                type="text"
                value={resetData.token}
                onChange={(e) => setResetData(prev => ({ ...prev, token: e.target.value }))}
                placeholder="Collez le code ici"
                required
                style={{
                  width: '100%', height: '48px', fontSize: '14px',
                  padding: '12px', border: '1px solid #d1d5db',
                  borderRadius: '8px', fontFamily: 'monospace',
                  boxSizing: 'border-box'
                }}
              />
            </div>

            <div style={{ marginBottom: '20px' }}>
              <label style={{
                display: 'block', fontSize: '14px', fontWeight: '600',
                color: '#374151', marginBottom: '8px'
              }}>
                Nouveau mot de passe
              </label>
              <input
                type="password"
                value={resetData.new_password}
                onChange={(e) => setResetData(prev => ({ ...prev, new_password: e.target.value }))}
                placeholder="Nouveau mot de passe (min. 6 caractères)"
                required
                style={{
                  width: '100%', height: '48px', fontSize: '16px',
                  padding: '12px', border: '1px solid #d1d5db',
                  borderRadius: '8px', boxSizing: 'border-box'
                }}
              />
            </div>

            <div style={{ marginBottom: '24px' }}>
              <label style={{
                display: 'block', fontSize: '14px', fontWeight: '600',
                color: '#374151', marginBottom: '8px'
              }}>
                Confirmer le mot de passe
              </label>
              <input
                type="password"
                value={resetData.confirm_password}
                onChange={(e) => setResetData(prev => ({ ...prev, confirm_password: e.target.value }))}
                placeholder="Confirmez le nouveau mot de passe"
                required
                style={{
                  width: '100%', height: '48px', fontSize: '16px',
                  padding: '12px', border: '1px solid #d1d5db',
                  borderRadius: '8px', boxSizing: 'border-box'
                }}
              />
            </div>

            <div style={{ display: 'flex', gap: '12px' }}>
              <button
                type="button"
                onClick={() => setStep('email')}
                style={{
                  flex: 1, height: '48px', fontSize: '16px', fontWeight: '500',
                  background: 'white', color: '#374151', border: '1px solid #d1d5db',
                  borderRadius: '8px', cursor: 'pointer'
                }}
              >
                ← Retour
              </button>
              <button
                type="submit"
                disabled={loading || !resetData.token || !resetData.new_password || !resetData.confirm_password}
                style={{
                  flex: 1, height: '48px', fontSize: '16px', fontWeight: '600',
                  background: loading ? '#9ca3af' : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  color: 'white', border: 'none', borderRadius: '8px',
                  cursor: loading ? 'not-allowed' : 'pointer'
                }}
              >
                {loading ? 'Réinitialisation...' : 'Changer le mot de passe'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};

// Login Page with Beautiful Design
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
    setLoading(true);
    setError('');

    try {
      let result;
      if (isLogin) {
        result = await login(formData.email, formData.password);
      } else {
        result = await register(formData.email, formData.password, formData.companyName);
      }

      if (!result.success) {
        setError(result.error);
      }
    } catch (err) {
      setError('Une erreur est survenue');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ 
      minHeight: '100vh', 
      background: 'linear-gradient(to-br, #f1f5f9, #e0e7ff, #c7d2fe)',
      display: 'flex',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
    }}>
      {/* Left Hero Section */}
      <div style={{
        width: '50%',
        background: 'linear-gradient(135deg, #4338ca, #7c3aed)',
        position: 'relative',
        overflow: 'hidden',
        display: window.innerWidth > 1024 ? 'flex' : 'none',
        flexDirection: 'column',
        justifyContent: 'center',
        padding: '60px'
      }}>
        {/* Decorative Elements */}
        <div style={{
          position: 'absolute', top: '80px', left: '80px',
          width: '300px', height: '300px',
          background: 'rgba(255,255,255,0.1)',
          borderRadius: '50%', filter: 'blur(60px)'
        }}></div>
        <div style={{
          position: 'absolute', bottom: '80px', right: '80px',
          width: '400px', height: '400px',
          background: 'rgba(124,58,237,0.3)',
          borderRadius: '50%', filter: 'blur(80px)'
        }}></div>

        {/* Content */}
        <div style={{ position: 'relative', zIndex: 10, color: 'white' }}>
          <div style={{ fontSize: '72px', marginBottom: '30px' }}>
          {/* Beautiful Receipt SVG Icon */}
          <svg width="72" height="72" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1-2-1Z"/>
            <path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"/>
            <path d="M12 18V6"/>
          </svg>
        </div>
          
          <h1 style={{
            fontSize: '56px', fontWeight: '800', lineHeight: '1.1',
            margin: '0 0 20px 0'
          }}>
            Simplifiez votre
            <br/>
            <span style={{ color: '#c7d2fe' }}>facturation</span>
          </h1>
          
          <p style={{
            fontSize: '22px', lineHeight: '1.6', margin: '0 0 40px 0',
            color: 'rgba(255,255,255,0.85)', maxWidth: '500px'
          }}>
            Gérez vos factures, soumissions et clients en toute simplicité avec notre solution complète et intuitive.
          </p>

          {/* Feature Cards */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: '16px',
              background: 'rgba(255,255,255,0.15)', padding: '16px 24px',
              borderRadius: '12px', backdropFilter: 'blur(10px)'
            }}>
              <div style={{ fontSize: '28px' }}>⚡</div>
              <div>
                <div style={{ fontWeight: '600', fontSize: '18px' }}>Facturation instantanée</div>
                <div style={{ fontSize: '14px', opacity: 0.9 }}>Créez et envoyez vos factures en quelques clics</div>
              </div>
            </div>

            <div style={{
              display: 'flex', alignItems: 'center', gap: '16px',
              background: 'rgba(255,255,255,0.15)', padding: '16px 24px',
              borderRadius: '12px', backdropFilter: 'blur(10px)'
            }}>
              <div style={{ fontSize: '28px' }}>⏰</div>
              <div>
                <div style={{ fontWeight: '600', fontSize: '18px' }}>Récurrence automatique</div>
                <div style={{ fontSize: '14px', opacity: 0.9 }}>Programmez vos factures récurrentes</div>
              </div>
            </div>

            <div style={{
              display: 'flex', alignItems: 'center', gap: '16px',
              background: 'rgba(255,255,255,0.15)', padding: '16px 24px',
              borderRadius: '12px', backdropFilter: 'blur(10px)'
            }}>
              <div style={{ fontSize: '28px' }}>🛡️</div>
              <div>
                <div style={{ fontWeight: '600', fontSize: '18px' }}>Sécurisé et conforme</div>
                <div style={{ fontSize: '14px', opacity: 0.9 }}>Taxes canadiennes TPS/TVQ automatiques</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Right Login Section */}
      <div style={{
        width: window.innerWidth > 1024 ? '50%' : '100%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '40px'
      }}>
        <div style={{ width: '100%', maxWidth: '460px' }}>
          {/* Header */}
          <div style={{ textAlign: 'center', marginBottom: '40px' }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              width: '88px', height: '88px',
              background: 'linear-gradient(135deg, #4338ca 0%, #7c3aed 100%)',
              borderRadius: '24px', marginBottom: '24px',
              boxShadow: '0 20px 40px rgba(67,56,202,0.4)'
            }}>
              {/* Beautiful Receipt SVG Icon */}
              <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1-2-1Z"/>
                <path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"/>
                <path d="M12 18V6"/>
              </svg>
            </div>

            <h1 style={{
              fontSize: '36px', fontWeight: '800', color: '#1e293b',
              margin: '0 0 8px 0'
            }}>
              FacturePro
            </h1>
            <h2 style={{
              fontSize: '24px', fontWeight: '600', color: '#475569',
              margin: '0 0 8px 0'
            }}>
              {isLogin ? 'Connexion' : 'Créer un compte'}
            </h2>
            <p style={{
              color: '#64748b', margin: 0, fontSize: '16px'
            }}>
              {isLogin 
                ? 'Accédez à votre tableau de bord professionnel' 
                : 'Démarrez votre essai gratuit de 14 jours'
              }
            </p>
          </div>

          {/* Login Form */}
          <div style={{
            background: 'rgba(255,255,255,0.8)',
            backdropFilter: 'blur(20px)',
            padding: '40px', borderRadius: '24px',
            border: 'none',
            boxShadow: '0 25px 50px -12px rgba(0,0,0,0.15)'
          }}>
            {error && (
              <div style={{
                background: '#fef2f2', border: '1px solid #fecaca',
                color: '#b91c1c', padding: '16px', borderRadius: '12px',
                marginBottom: '24px', fontSize: '14px'
              }}>
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              {!isLogin && (
                <div>
                  <label style={{
                    display: 'block', fontSize: '14px', fontWeight: '600',
                    color: '#374151', marginBottom: '8px'
                  }}>
                    Nom de l'entreprise *
                  </label>
                  <input
                    type="text"
                    name="companyName"
                    value={formData.companyName}
                    onChange={(e) => setFormData(prev => ({ ...prev, companyName: e.target.value }))}
                    placeholder="Mon Entreprise Inc."
                    required
                    style={{
                      width: '100%', height: '52px', fontSize: '16px',
                      padding: '16px', border: '1px solid #d1d5db',
                      borderRadius: '12px', boxSizing: 'border-box',
                      transition: 'all 0.3s ease'
                    }}
                  />
                </div>
              )}

              <div>
                <label style={{
                  display: 'block', fontSize: '14px', fontWeight: '600',
                  color: '#374151', marginBottom: '8px'
                }}>
                  Adresse email *
                </label>
                <input
                  type="email"
                  name="email"
                  value={formData.email}
                  onChange={(e) => setFormData(prev => ({ ...prev, email: e.target.value }))}
                  placeholder="votre@email.com"
                  required
                  style={{
                    width: '100%', height: '52px', fontSize: '16px',
                    padding: '16px', border: '1px solid #d1d5db',
                    borderRadius: '12px', boxSizing: 'border-box',
                    transition: 'all 0.3s ease'
                  }}
                />
              </div>

              <div>
                <label style={{
                  display: 'block', fontSize: '14px', fontWeight: '600',
                  color: '#374151', marginBottom: '8px'
                }}>
                  Mot de passe *
                </label>
                <div style={{ position: 'relative' }}>
                  <input
                    type={showPassword ? "text" : "password"}
                    name="password"
                    value={formData.password}
                    onChange={(e) => setFormData(prev => ({ ...prev, password: e.target.value }))}
                    placeholder="••••••••••"
                    required
                    style={{
                      width: '100%', height: '52px', fontSize: '16px',
                      padding: '16px 56px 16px 16px', border: '1px solid #d1d5db',
                      borderRadius: '12px', boxSizing: 'border-box',
                      transition: 'all 0.3s ease'
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    style={{
                      position: 'absolute', right: '16px', top: '50%',
                      transform: 'translateY(-50%)', background: 'none',
                      border: 'none', cursor: 'pointer', fontSize: '20px'
                    }}
                  >
                    {showPassword ? '🙈' : '👁️'}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                style={{
                  width: '100%', height: '52px', fontSize: '16px', fontWeight: '700',
                  background: loading ? '#94a3b8' : 'linear-gradient(135deg, #4338ca 0%, #7c3aed 100%)',
                  color: 'white', border: 'none', borderRadius: '12px',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  boxShadow: '0 10px 25px rgba(67,56,202,0.3)',
                  transform: 'translateY(0)', transition: 'all 0.3s ease'
                }}
                onMouseEnter={(e) => {
                  if (!loading) e.target.style.transform = 'translateY(-2px)';
                }}
                onMouseLeave={(e) => {
                  e.target.style.transform = 'translateY(0)';
                }}
              >
                {loading ? (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
                    <div style={{
                      width: '20px', height: '20px', border: '2px solid transparent',
                      borderTop: '2px solid white', borderRadius: '50%',
                      animation: 'spin 1s linear infinite'
                    }}></div>
                    Connexion...
                  </div>
                ) : (
                  isLogin ? 'Se connecter' : 'Créer mon compte'
                )}
              </button>
            </form>

            {/* Forgot Password */}
            {isLogin && (
              <div style={{ textAlign: 'center', marginTop: '20px' }}>
                <button
                  onClick={() => setShowForgotPassword(true)}
                  style={{
                    background: 'none', border: 'none', color: '#4338ca',
                    fontSize: '14px', cursor: 'pointer', textDecoration: 'underline'
                  }}
                >
                  Mot de passe oublié ?
                </button>
              </div>
            )}

            {/* Toggle */}
            <div style={{ textAlign: 'center', marginTop: '28px' }}>
              <button
                onClick={() => {
                  setIsLogin(!isLogin);
                  setError('');
                  setFormData({ email: '', password: '', companyName: '' });
                }}
                style={{
                  background: 'none', border: 'none', color: '#4338ca',
                  fontSize: '16px', fontWeight: '600', cursor: 'pointer'
                }}
              >
                {isLogin 
                  ? "Nouveau sur FacturePro ? Créer un compte" 
                  : "Déjà client ? Se connecter"
                }
              </button>
            </div>
          </div>

          {/* Terms */}
          {!isLogin && (
            <div style={{ 
              textAlign: 'center', marginTop: '24px', 
              fontSize: '14px', color: '#64748b' 
            }}>
              En créant un compte, vous acceptez nos{' '}
              <a href="#" style={{ color: '#4338ca' }}>conditions d'utilisation</a>{' '}
              et notre{' '}
              <a href="#" style={{ color: '#4338ca' }}>politique de confidentialité</a>
            </div>
          )}
        </div>
      </div>

      {/* Modal */}
      {showForgotPassword && <ForgotPasswordModal onClose={() => setShowForgotPassword(false)} />}

      {/* CSS Animation for spinner */}
      <style>
        {`
          @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
        `}
      </style>
    </div>
  );
};

// Invoices Page Component
const InvoicesPage = () => {
  const [invoices, setInvoices] = useState([]);
  const [clients, setClients] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    client_id: '',
    due_date: new Date(Date.now() + 30*24*60*60*1000).toISOString().split('T')[0], // 30 days from now
    items: [{ description: '', quantity: 1, unit_price: 0 }],
    province: 'QC',
    notes: ''
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [invoicesRes, clientsRes, productsRes] = await Promise.all([
        axios.get(`${BACKEND_URL}/api/invoices`),
        axios.get(`${BACKEND_URL}/api/clients`),
        axios.get(`${BACKEND_URL}/api/dashboard/stats`) // For products, we'll use stats for now
      ]);
      setInvoices(invoicesRes.data);
      setClients(clientsRes.data);
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    try {
      // Calculate totals for each item
      const processedItems = formData.items.map(item => ({
        ...item,
        quantity: parseFloat(item.quantity) || 0,
        unit_price: parseFloat(item.unit_price) || 0,
        total: (parseFloat(item.quantity) || 0) * (parseFloat(item.unit_price) || 0)
      }));

      const invoiceData = {
        ...formData,
        items: processedItems
      };

      await axios.post(`${BACKEND_URL}/api/invoices`, invoiceData);
      
      setShowForm(false);
      setFormData({
        client_id: '',
        due_date: new Date(Date.now() + 30*24*60*60*1000).toISOString().split('T')[0],
        items: [{ description: '', quantity: 1, unit_price: 0 }],
        province: 'QC',
        notes: ''
      });
      fetchData();
    } catch (error) {
      alert('Erreur lors de la création de la facture : ' + (error.response?.data?.detail || error.message));
    }
  };

  const addItem = () => {
    setFormData(prev => ({
      ...prev,
      items: [...prev.items, { description: '', quantity: 1, unit_price: 0 }]
    }));
  };

  const updateItem = (index, field, value) => {
    const newItems = [...formData.items];
    newItems[index] = { ...newItems[index], [field]: value };
    setFormData(prev => ({ ...prev, items: newItems }));
  };

  const removeItem = (index) => {
    if (formData.items.length > 1) {
      setFormData(prev => ({
        ...prev,
        items: prev.items.filter((_, i) => i !== index)
      }));
    }
  };

  const getClientName = (clientId) => {
    const client = clients.find(c => c.id === clientId);
    return client ? client.name : 'Client inconnu';
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('fr-CA', {
      style: 'currency',
      currency: 'CAD'
    }).format(amount || 0);
  };

  const calculateItemSubtotal = () => {
    return formData.items.reduce((sum, item) => {
      return sum + ((parseFloat(item.quantity) || 0) * (parseFloat(item.unit_price) || 0));
    }, 0);
  };

  const getStatusBadge = (status) => {
    const statusConfig = {
      draft: { label: 'Brouillon', bg: '#f3f4f6', color: '#374151' },
      sent: { label: 'Envoyée', bg: '#fef3c7', color: '#92400e' },
      paid: { label: 'Payée', bg: '#dcfce7', color: '#166534' },
      overdue: { label: 'En retard', bg: '#fee2e2', color: '#b91c1c' }
    };
    
    const config = statusConfig[status] || statusConfig.draft;
    return (
      <span style={{
        background: config.bg,
        color: config.color,
        padding: '4px 8px',
        borderRadius: '6px',
        fontSize: '12px',
        fontWeight: '500'
      }}>
        {config.label}
      </span>
    );
  };

  if (loading) {
    return <div style={{ padding: '30px' }}>Chargement des factures...</div>;
  }

  return (
    <div style={{ padding: '30px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px' }}>
        <div>
          <h2 style={{ margin: '0 0 8px 0', color: '#1f2937', fontSize: '28px' }}>📄 Factures</h2>
          <p style={{ margin: 0, color: '#6b7280' }}>{invoices.length} facture{invoices.length > 1 ? 's' : ''} au total</p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          style={{
            background: 'linear-gradient(135deg, #3b82f6, #1d4ed8)',
            color: 'white', border: 'none', padding: '14px 28px',
            borderRadius: '10px', cursor: 'pointer', fontWeight: '600',
            fontSize: '16px', boxShadow: '0 4px 12px rgba(59,130,246,0.3)'
          }}
        >
          ✨ Nouvelle Facture
        </button>
      </div>

      {/* Invoices List */}
      {invoices.length === 0 ? (
        <div style={{
          background: 'white', border: '2px dashed #d1d5db',
          borderRadius: '16px', padding: '60px 40px', textAlign: 'center'
        }}>
          <div style={{ fontSize: '64px', marginBottom: '20px' }}>📄</div>
          <h3 style={{ margin: '0 0 12px 0', color: '#374151', fontSize: '20px' }}>Aucune facture créée</h3>
          <p style={{ margin: '0 0 24px 0', color: '#6b7280' }}>
            Créez votre première facture pour commencer à facturer vos clients
          </p>
          <button
            onClick={() => setShowForm(true)}
            style={{
              background: '#3b82f6', color: 'white', border: 'none',
              padding: '12px 24px', borderRadius: '8px', cursor: 'pointer',
              fontWeight: '600'
            }}
          >
            🚀 Créer ma première facture
          </button>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '16px' }}>
          {invoices.map(invoice => (
            <div key={invoice.id} style={{
              background: 'white', border: '1px solid #e5e7eb',
              borderRadius: '12px', padding: '24px',
              boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
                    <h3 style={{ margin: 0, color: '#1f2937', fontSize: '20px', fontWeight: '700' }}>
                      {invoice.invoice_number}
                    </h3>
                    {getStatusBadge(invoice.status)}
                  </div>
                  
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
                    <div>
                      <div style={{ fontSize: '12px', color: '#6b7280', fontWeight: '600', marginBottom: '4px' }}>CLIENT</div>
                      <div style={{ color: '#374151', fontWeight: '500' }}>{getClientName(invoice.client_id)}</div>
                    </div>
                    
                    <div>
                      <div style={{ fontSize: '12px', color: '#6b7280', fontWeight: '600', marginBottom: '4px' }}>ÉCHÉANCE</div>
                      <div style={{ color: '#374151' }}>{new Date(invoice.due_date).toLocaleDateString('fr-CA')}</div>
                    </div>
                    
                    <div>
                      <div style={{ fontSize: '12px', color: '#6b7280', fontWeight: '600', marginBottom: '4px' }}>PROVINCE</div>
                      <div style={{ color: '#374151' }}>{invoice.province === 'QC' ? 'Québec' : 'Ontario'}</div>
                    </div>
                  </div>

                  {invoice.notes && (
                    <div style={{ marginTop: '12px', padding: '8px', background: '#f8fafc', borderRadius: '6px' }}>
                      <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '4px' }}>NOTES</div>
                      <div style={{ fontSize: '14px', color: '#374151' }}>{invoice.notes}</div>
                    </div>
                  )}
                </div>
                
                <div style={{ textAlign: 'right', marginLeft: '24px' }}>
                  <div style={{ marginBottom: '8px' }}>
                    <div style={{ fontSize: '24px', fontWeight: '700', color: '#1f2937' }}>
                      {formatCurrency(invoice.total)}
                    </div>
                    <div style={{ fontSize: '12px', color: '#6b7280' }}>
                      Sous-total: {formatCurrency(invoice.subtotal)}
                    </div>
                    {invoice.province === 'QC' && (
                      <>
                        <div style={{ fontSize: '12px', color: '#6b7280' }}>
                          TPS: {formatCurrency(invoice.gst_amount)}
                        </div>
                        <div style={{ fontSize: '12px', color: '#6b7280' }}>
                          TVQ: {formatCurrency(invoice.pst_amount)}
                        </div>
                      </>
                    )}
                    {invoice.province === 'ON' && (
                      <div style={{ fontSize: '12px', color: '#6b7280' }}>
                        HST: {formatCurrency(invoice.hst_amount)}
                      </div>
                    )}
                  </div>
                  
                  <button
                    onClick={async () => {
                      if (window.confirm('Supprimer cette facture ?')) {
                        try {
                          await axios.delete(`${BACKEND_URL}/api/invoices/${invoice.id}`);
                          fetchData();
                        } catch (error) {
                          alert('Erreur lors de la suppression');
                        }
                      }
                    }}
                    style={{
                      background: '#ef4444', color: 'white', border: 'none',
                      padding: '6px 12px', borderRadius: '6px', cursor: 'pointer',
                      fontSize: '14px'
                    }}
                  >
                    🗑️ Supprimer
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Invoice Form Modal */}
      {showForm && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center',
          justifyContent: 'center', zIndex: 1000, padding: '20px'
        }}>
          <div style={{
            background: 'white', padding: '32px', borderRadius: '16px',
            width: '95%', maxWidth: '900px', maxHeight: '90vh', overflow: 'auto'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px' }}>
              <h3 style={{ margin: 0, fontSize: '24px', color: '#1f2937' }}>✨ Nouvelle Facture</h3>
              <button
                onClick={() => setShowForm(false)}
                style={{
                  background: '#f3f4f6', border: 'none', padding: '8px',
                  borderRadius: '8px', cursor: 'pointer', fontSize: '20px'
                }}
              >
                ✕
              </button>
            </div>
            
            <form onSubmit={handleSubmit}>
              {/* Header Info */}
              <div style={{ 
                display: 'grid', 
                gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', 
                gap: '20px', 
                marginBottom: '30px',
                padding: '20px',
                background: '#f8fafc',
                borderRadius: '12px'
              }}>
                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', color: '#374151' }}>
                    Client *
                  </label>
                  <select
                    value={formData.client_id}
                    onChange={(e) => setFormData(prev => ({ ...prev, client_id: e.target.value }))}
                    required
                    style={{
                      width: '100%', padding: '12px', border: '1px solid #d1d5db',
                      borderRadius: '8px', fontSize: '14px', boxSizing: 'border-box'
                    }}
                  >
                    <option value="">Sélectionner un client</option>
                    {clients.map(client => (
                      <option key={client.id} value={client.id}>
                        {client.name} ({client.email})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', color: '#374151' }}>
                    Date d'échéance *
                  </label>
                  <input
                    type="date"
                    value={formData.due_date}
                    onChange={(e) => setFormData(prev => ({ ...prev, due_date: e.target.value }))}
                    required
                    style={{
                      width: '100%', padding: '12px', border: '1px solid #d1d5db',
                      borderRadius: '8px', boxSizing: 'border-box'
                    }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600', color: '#374151' }}>
                    Province (taxes)
                  </label>
                  <select
                    value={formData.province}
                    onChange={(e) => setFormData(prev => ({ ...prev, province: e.target.value }))}
                    style={{
                      width: '100%', padding: '12px', border: '1px solid #d1d5db',
                      borderRadius: '8px', boxSizing: 'border-box'
                    }}
                  >
                    <option value="QC">🍁 Québec (TPS 5% + TVQ 9.975%)</option>
                    <option value="ON">🍁 Ontario (HST 13%)</option>
                  </select>
                </div>
              </div>

              {/* Items */}
              <div style={{ marginBottom: '30px' }}>
                <h4 style={{ margin: '0 0 16px 0', color: '#1f2937', fontSize: '18px' }}>
                  📋 Articles et Services
                </h4>
                
                {/* Items Header */}
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: '2fr 100px 120px 120px 60px',
                  gap: '12px',
                  padding: '12px 16px',
                  background: '#f1f5f9',
                  borderRadius: '8px 8px 0 0',
                  fontSize: '12px',
                  fontWeight: '700',
                  color: '#374151',
                  borderBottom: '2px solid #e2e8f0'
                }}>
                  <div>DESCRIPTION</div>
                  <div style={{ textAlign: 'center' }}>QTÉ</div>
                  <div style={{ textAlign: 'center' }}>PRIX UNIT.</div>
                  <div style={{ textAlign: 'center' }}>TOTAL</div>
                  <div></div>
                </div>

                {formData.items.map((item, index) => (
                  <div key={index} style={{
                    display: 'grid',
                    gridTemplateColumns: '2fr 100px 120px 120px 60px',
                    gap: '12px',
                    padding: '16px',
                    background: index % 2 === 0 ? 'white' : '#f8fafc',
                    borderBottom: '1px solid #e5e7eb',
                    alignItems: 'center'
                  }}>
                    <input
                      type="text"
                      value={item.description}
                      onChange={(e) => updateItem(index, 'description', e.target.value)}
                      placeholder="Description du service/produit"
                      required
                      style={{
                        padding: '10px', border: '1px solid #d1d5db',
                        borderRadius: '6px', fontSize: '14px', boxSizing: 'border-box'
                      }}
                    />
                    
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={item.quantity}
                      onChange={(e) => updateItem(index, 'quantity', e.target.value)}
                      style={{
                        padding: '10px', border: '1px solid #d1d5db',
                        borderRadius: '6px', textAlign: 'center', boxSizing: 'border-box'
                      }}
                    />
                    
                    <input
                      type="number"
                      step="0.01" 
                      min="0"
                      value={item.unit_price}
                      onChange={(e) => updateItem(index, 'unit_price', e.target.value)}
                      style={{
                        padding: '10px', border: '1px solid #d1d5db',
                        borderRadius: '6px', textAlign: 'center', boxSizing: 'border-box'
                      }}
                    />
                    
                    <div style={{
                      padding: '10px', background: '#f1f5f9', borderRadius: '6px',
                      textAlign: 'center', fontWeight: '600', color: '#374151'
                    }}>
                      {formatCurrency((parseFloat(item.quantity) || 0) * (parseFloat(item.unit_price) || 0))}
                    </div>
                    
                    <button
                      type="button"
                      onClick={() => removeItem(index)}
                      disabled={formData.items.length === 1}
                      style={{
                        background: formData.items.length === 1 ? '#f3f4f6' : '#ef4444',
                        color: formData.items.length === 1 ? '#9ca3af' : 'white',
                        border: 'none', padding: '8px', borderRadius: '6px',
                        cursor: formData.items.length === 1 ? 'not-allowed' : 'pointer'
                      }}
                    >
                      🗑️
                    </button>
                  </div>
                ))}

                {/* Add Item Button */}
                <div style={{ padding: '16px', textAlign: 'center', borderTop: '2px solid #e2e8f0' }}>
                  <button
                    type="button"
                    onClick={addItem}
                    style={{
                      background: '#10b981', color: 'white', border: 'none',
                      padding: '10px 20px', borderRadius: '8px', cursor: 'pointer',
                      fontWeight: '600'
                    }}
                  >
                    ➕ Ajouter un article
                  </button>
                </div>

                {/* Totals */}
                <div style={{
                  background: '#f8fafc', padding: '20px', borderRadius: '0 0 8px 8px',
                  borderTop: '2px solid #3b82f6'
                }}>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '18px', fontWeight: '700', color: '#1f2937' }}>
                      Sous-total: {formatCurrency(calculateItemSubtotal())}
                    </div>
                    <div style={{ fontSize: '14px', color: '#6b7280', marginTop: '4px' }}>
                      {formData.province === 'QC' ? 'TPS (5%) + TVQ (9.975%) ajoutées automatiquement' : 
                       formData.province === 'ON' ? 'HST (13%) ajoutée automatiquement' : 
                       'Taxes calculées selon la province'}
                    </div>
                  </div>
                </div>
              </div>

              {/* Notes */}
              <div style={{ marginBottom: '30px' }}>
                <label style={{ display: 'block', marginBottom: '8px', fontWeight: '600', color: '#374151' }}>
                  📝 Notes (optionnel)
                </label>
                <textarea
                  value={formData.notes}
                  onChange={(e) => setFormData(prev => ({ ...prev, notes: e.target.value }))}
                  rows={3}
                  placeholder="Conditions de paiement, informations supplémentaires..."
                  style={{
                    width: '100%', padding: '12px', border: '1px solid #d1d5db',
                    borderRadius: '8px', resize: 'vertical', fontSize: '14px',
                    boxSizing: 'border-box'
                  }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  style={{
                    background: 'white', color: '#374151', border: '1px solid #d1d5db',
                    padding: '12px 24px', borderRadius: '8px', cursor: 'pointer'
                  }}
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  style={{
                    background: 'linear-gradient(135deg, #3b82f6, #1d4ed8)', color: 'white',
                    border: 'none', padding: '12px 24px', borderRadius: '8px',
                    cursor: 'pointer', fontWeight: '600'
                  }}
                >
                  💾 Créer la facture
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
const Dashboard = () => {
  const { user, logout } = useAuth();

  return (
    <div style={{ minHeight: '100vh', background: '#f8fafc', fontFamily: 'system-ui' }}>
      <nav style={{
        background: 'linear-gradient(135deg, #4338ca, #7c3aed)',
        color: 'white', padding: '20px 40px',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center'
      }}>
        <h1 style={{ margin: 0, fontSize: '28px', fontWeight: 'bold' }}>🧾 FacturePro</h1>
        <button onClick={logout} style={{
          background: '#ef4444', color: 'white', border: 'none',
          padding: '10px 20px', borderRadius: '8px', cursor: 'pointer'
        }}>
          Déconnexion
        </button>
      </nav>

      <div style={{ padding: '40px' }}>
        <h2 style={{ marginBottom: '30px', color: '#1e293b' }}>Tableau de bord</h2>
        
        <div style={{
          background: 'linear-gradient(135deg, #10b981, #059669)',
          color: 'white', padding: '30px', borderRadius: '16px',
          textAlign: 'center', marginBottom: '30px'
        }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>🎉</div>
          <h3 style={{ margin: '0 0 8px 0', fontSize: '24px' }}>Migration Réussie !</h3>
          <p style={{ margin: 0, fontSize: '16px', opacity: 0.9 }}>
            FacturePro fonctionne maintenant sur Vercel + Render
          </p>
        </div>

        <div style={{
          background: 'white', border: '1px solid #e2e8f0',
          borderRadius: '16px', padding: '30px'
        }}>
          <h3 style={{ margin: '0 0 20px 0', color: '#1e293b' }}>👤 Informations du compte</h3>
          <p style={{ margin: '8px 0', color: '#475569' }}>
            <strong>Entreprise :</strong> {user?.company_name}
          </p>
          <p style={{ margin: '8px 0', color: '#475569' }}>
            <strong>Email :</strong> {user?.email}
          </p>
          
          <div style={{
            background: '#f0f9ff', border: '1px solid #0ea5e9',
            borderRadius: '8px', padding: '16px', marginTop: '20px'
          }}>
            <p style={{ margin: 0, color: '#0c4a6e', fontSize: '14px' }}>
              ✅ Version de base déployée avec succès. Toutes les fonctionnalités avancées seront ajoutées progressivement.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

// Auth Provider
const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token'));

  useEffect(() => {
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    }
  }, [token]);

  const login = async (email, password) => {
    try {
      const response = await axios.post(`${BACKEND_URL}/api/auth/login`, { email, password });
      const { access_token, user: userData } = response.data;
      
      setToken(access_token);
      setUser(userData);
      localStorage.setItem('token', access_token);
      axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
      
      return { success: true };
    } catch (error) {
      return { 
        success: false, 
        error: error.response?.data?.detail || 'Email ou mot de passe incorrect' 
      };
    }
  };

  const register = async (email, password, company_name) => {
    try {
      const response = await axios.post(`${BACKEND_URL}/api/auth/register`, { 
        email, password, company_name 
      });
      const { access_token, user: userData } = response.data;
      
      setToken(access_token);
      setUser(userData);
      localStorage.setItem('token', access_token);
      axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
      
      return { success: true };
    } catch (error) {
      return { 
        success: false, 
        error: error.response?.data?.detail || 'Erreur lors de la création du compte' 
      };
    }
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('token');
    delete axios.defaults.headers.common['Authorization'];
  };

  return (
    <AuthContext.Provider value={{ user, token, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

// Main App
function App() {
  const { token } = useAuth();
  return token ? <Dashboard /> : <LoginPage />;
}

// App with Provider
function AppWithAuth() {
  return (
    <AuthProvider>
      <App />
    </AuthProvider>
  );
}

export default AppWithAuth;