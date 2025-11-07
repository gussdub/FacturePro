import React, { useState, createContext, useContext, useEffect } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'https://facturepro-api.onrender.com';

// Auth Context
const AuthContext = createContext();
export const useAuth = () => useContext(AuthContext);

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

// Login Page with Original Beautiful Design
const LoginPage = ({ onLogin, onRegister, navigate }) => {
  const [formData, setFormData] = useState({ email: '', password: '', companyName: '' });
  const [isLogin, setIsLogin] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [showForgotPassword, setShowForgotPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      let result;
      if (isLogin) {
        result = await onLogin(formData.email, formData.password);
      } else {
        result = await onRegister(formData.email, formData.password, formData.companyName);
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
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100 flex" style={{
      minHeight: '100vh',
      background: 'linear-gradient(to bottom right, #f8fafc, #dbeafe, #c7d2fe)',
      display: 'flex',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
    }}>
      {/* Left Hero Section */}
      <div style={{
        display: window.innerWidth > 1024 ? 'flex' : 'none',
        width: '50%',
        background: 'linear-gradient(135deg, #4f46e5, #7c3aed)',
        position: 'relative',
        overflow: 'hidden',
        flexDirection: 'column',
        justifyContent: 'center',
        padding: '48px'
      }}>
        {/* Decorative circles */}
        <div style={{
          position: 'absolute', top: '80px', left: '80px',
          width: '288px', height: '288px',
          background: 'rgba(255,255,255,0.1)',
          borderRadius: '50%', filter: 'blur(48px)'
        }}></div>
        <div style={{
          position: 'absolute', bottom: '80px', right: '80px',
          width: '384px', height: '384px',
          background: 'rgba(59,130,246,0.2)',
          borderRadius: '50%', filter: 'blur(48px)'
        }}></div>
        
        <div style={{ position: 'relative', zIndex: 10, color: 'white' }}>
          <div style={{ marginBottom: '32px' }}>
            {/* Beautiful Receipt Icon */}
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginBottom: '24px' }}>
              <path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1-2-1Z"/>
              <path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"/>
              <path d="M12 18V6"/>
            </svg>
            <h1 style={{
              fontSize: '80px', fontWeight: 'bold', marginBottom: '16px',
              lineHeight: '1.1', margin: 0
            }}>
              Simplifiez votre
              <span style={{ display: 'block', color: '#bfdbfe' }}>facturation</span>
            </h1>
            <p style={{
              fontSize: '20px', color: 'rgba(255,255,255,0.8)',
              lineHeight: '1.6', margin: 0
            }}>
              Gérez vos factures, devis et clients en toute simplicité avec notre solution complète et intuitive.
            </p>
          </div>
          
          {/* Feature highlights */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '16px' }}>
            <div style={{
              display: 'flex', alignItems: 'center',
              background: 'rgba(255,255,255,0.1)', padding: '12px 20px',
              borderRadius: '12px', backdropFilter: 'blur(8px)'
            }}>
              <span style={{ fontSize: '24px', marginRight: '12px' }}>⚡</span>
              <div>
                <div style={{ fontWeight: '600', fontSize: '16px' }}>Facturation instantanée</div>
                <div style={{ fontSize: '14px', opacity: 0.9 }}>Créez et envoyez vos factures en quelques clics</div>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '16px' }}>
            <div style={{
              display: 'flex', alignItems: 'center',
              background: 'rgba(255,255,255,0.1)', padding: '12px 20px',
              borderRadius: '12px', backdropFilter: 'blur(8px)'
            }}>
              <span style={{ fontSize: '24px', marginRight: '12px' }}>🔄</span>
              <div>
                <div style={{ fontWeight: '600', fontSize: '16px' }}>Récurrence automatique</div>
                <div style={{ fontSize: '14px', opacity: 0.9 }}>Programmez vos factures récurrentes</div>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div style={{
              display: 'flex', alignItems: 'center',
              background: 'rgba(255,255,255,0.1)', padding: '12px 20px',
              borderRadius: '12px', backdropFilter: 'blur(8px)'
            }}>
              <span style={{ fontSize: '24px', marginRight: '12px' }}>🛡️</span>
              <div>
                <div style={{ fontWeight: '600', fontSize: '16px' }}>Sécurisé et fiable</div>
                <div style={{ fontSize: '14px', opacity: 0.9 }}>Vos données sont protégées et sauvegardées</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Right side - Login/Register Form */}
      <div style={{
        width: window.innerWidth > 1024 ? '50%' : '100%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '40px 20px'
      }}>
        <div style={{ width: '100%', maxWidth: '480px' }}>
          {/* Logo and Title Section */}
          <div style={{ textAlign: 'center', marginBottom: '32px' }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              width: '80px', height: '80px',
              background: 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
              borderRadius: '20px', marginBottom: '20px',
              boxShadow: '0 10px 25px rgba(79, 70, 229, 0.4)'
            }}>
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1-2-1Z"/>
                <path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"/>
                <path d="M12 18V6"/>
              </svg>
            </div>
            <h1 style={{
              fontSize: '32px', fontWeight: '800', color: '#1e293b',
              margin: '0 0 8px 0', letterSpacing: '-0.025em'
            }}>
              FacturePro
            </h1>
            <h2 style={{
              fontSize: '22px', fontWeight: '600', color: '#475569',
              margin: '0 0 8px 0'
            }}>
              {isLogin ? 'Connexion' : 'Créer un compte'}
            </h2>
            <p style={{
              color: '#64748b', margin: 0, fontSize: '16px'
            }}>
              {isLogin 
                ? 'Accédez à votre tableau de bord' 
                : 'Démarrez votre essai gratuit aujourd\'hui'
              }
            </p>
          </div>

          {/* Form Card */}
          <div style={{
            background: 'rgba(255,255,255,0.95)',
            backdropFilter: 'blur(20px)',
            padding: '32px', borderRadius: '20px',
            boxShadow: '0 25px 50px -12px rgba(0,0,0,0.15)',
            border: 'none'
          }}>
            {error && (
              <div style={{
                background: '#fef2f2', border: '1px solid #fecaca',
                borderRadius: '12px', padding: '16px', marginBottom: '24px',
                color: '#b91c1c', fontSize: '14px', textAlign: 'center'
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
                    placeholder="Mon Entreprise"
                    required
                    style={{
                      width: '100%', height: '48px', fontSize: '16px',
                      padding: '12px 16px', border: '1px solid #d1d5db',
                      borderRadius: '12px', boxSizing: 'border-box',
                      transition: 'all 0.2s ease'
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
                    width: '100%', height: '48px', fontSize: '16px',
                    padding: '12px 16px', border: '1px solid #d1d5db',
                    borderRadius: '12px', boxSizing: 'border-box',
                    transition: 'all 0.2s ease'
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
                    placeholder="••••••••"
                    required
                    style={{
                      width: '100%', height: '48px', fontSize: '16px',
                      padding: '12px 52px 12px 16px', border: '1px solid #d1d5db',
                      borderRadius: '12px', boxSizing: 'border-box',
                      transition: 'all 0.2s ease'
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    style={{
                      position: 'absolute', right: '12px', top: '50%',
                      transform: 'translateY(-50%)', background: 'none',
                      border: 'none', cursor: 'pointer', color: '#64748b',
                      fontSize: '20px', padding: '4px'
                    }}
                  >
                    {showPassword ? (
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/>
                        <path d="m15 12 5-5-5-5M9 12l-5 5 5 5"/>
                        <path d="m2 2 20 20"/>
                      </svg>
                    ) : (
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                        <circle cx="12" cy="12" r="3"/>
                      </svg>
                    )}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                style={{
                  width: '100%', height: '48px', fontSize: '16px', fontWeight: '700',
                  background: loading 
                    ? '#94a3b8' 
                    : 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
                  color: 'white', border: 'none', borderRadius: '12px',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  boxShadow: '0 10px 25px rgba(79,70,229,0.4)',
                  transform: 'translateY(0)', transition: 'all 0.3s ease'
                }}
              >
                {loading ? (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
                    <div style={{
                      width: '20px', height: '20px',
                      border: '2px solid transparent', borderTop: '2px solid white',
                      borderRadius: '50%', animation: 'spin 1s linear infinite'
                    }}></div>
                    Chargement...
                  </div>
                ) : (
                  isLogin ? 'Se connecter' : 'Créer mon compte'
                )}
              </button>
            </form>

            {/* Forgot Password Link */}
            {isLogin && (
              <div style={{ marginTop: '16px', textAlign: 'center' }}>
                <button
                  type="button"
                  onClick={() => setShowForgotPassword(true)}
                  style={{
                    background: 'none', border: 'none', color: '#4f46e5',
                    fontSize: '14px', cursor: 'pointer', textDecoration: 'underline'
                  }}
                >
                  Mot de passe oublié ?
                </button>
              </div>
            )}

            <div style={{ marginTop: '24px', textAlign: 'center' }}>
              <button
                type="button"
                onClick={() => {
                  setIsLogin(!isLogin);
                  setError('');
                  setFormData({ email: '', password: '', companyName: '' });
                }}
                style={{
                  background: 'none', border: 'none', color: '#4f46e5',
                  fontSize: '16px', fontWeight: '600', cursor: 'pointer'
                }}
              >
                {isLogin 
                  ? "Pas encore de compte ? S'inscrire" 
                  : "Déjà un compte ? Se connecter"
                }
              </button>
            </div>
          </div>

          {!isLogin && (
            <div style={{
              marginTop: '24px', textAlign: 'center',
              fontSize: '14px', color: '#64748b'
            }}>
              En créant un compte, vous acceptez nos{' '}
              <a href="#" style={{ color: '#4f46e5', textDecoration: 'none' }}>
                conditions d'utilisation
              </a>{' '}
              et notre{' '}
              <a href="#" style={{ color: '#4f46e5', textDecoration: 'none' }}>
                politique de confidentialité
              </a>
            </div>
          )}
        </div>
      </div>

      {/* Forgot Password Modal */}
      {showForgotPassword && <ForgotPasswordModal onClose={() => setShowForgotPassword(false)} />}

      {/* CSS Animations */}
      <style>
        {`
          @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
          
          input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: #4f46e5;
            box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
          }
          
          button:hover:not(:disabled) {
            transform: translateY(-1px);
            box-shadow: 0 12px 28px rgba(79,70,229,0.5);
          }
        `}
      </style>
    </div>
  );
};

// Register Page (if needed separately)
const RegisterPage = ({ onRegister, navigate }) => {
  // Same as login but registration focused
  return navigate('/login'); // Redirect to login with register mode
};

// Forgot Password Modal
const ForgotPasswordModal = ({ onClose }) => {
  const [step, setStep] = useState('email');
  const [email, setEmail] = useState('');
  const [resetData, setResetData] = useState({ token: '', new_password: '', confirm_password: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleSendCode = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(''); setSuccess('');

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

    setLoading(true); setError('');

    try {
      await axios.post(`${BACKEND_URL}/api/auth/reset-password`, {
        token: resetData.token,
        new_password: resetData.new_password
      });

      setSuccess('Mot de passe réinitialisé avec succès ! Vous pouvez maintenant vous connecter.');
      setTimeout(onClose, 2000);
      
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
            background: 'none', border: 'none', fontSize: '24px',
            cursor: 'pointer', color: '#64748b'
          }}
        >
          ×
        </button>

        <div style={{ textAlign: 'center', marginBottom: '24px' }}>
          <div style={{
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            width: '64px', height: '64px',
            background: 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
            borderRadius: '16px', marginBottom: '16px'
          }}>
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
              <circle cx="8" cy="8" r="6"/>
              <path d="m13 13 6 6"/>
              <path d="M13 13v4a2 2 0 0 1-2 2h-3"/>
            </svg>
          </div>
          <h2 style={{ margin: 0, color: '#1f2937', fontSize: '22px', fontWeight: '700' }}>
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
            <p style={{ color: '#64748b', marginBottom: '20px', textAlign: 'center' }}>
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
                  background: loading ? '#9ca3af' : 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
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
                  background: loading ? '#9ca3af' : 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
                  color: 'white', border: 'none', borderRadius: '8px',
                  cursor: loading ? 'not-allowed' : 'pointer'
                }}
              >
                {loading ? 'Réinitialisation...' : 'Réinitialiser'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};

// Modern Dashboard with Beautiful Layout
const Dashboard = ({ navigate, user, logout }) => {
  const [stats, setStats] = useState({ loading: true });

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/dashboard/stats`);
      setStats({ loading: false, data: response.data });
    } catch (error) {
      setStats({ loading: false, error: error.message });
    }
  };

  return (
    <div style={{ minHeight: '100vh', background: '#f8fafc' }}>
      {/* Modern Navigation */}
      <nav style={{
        background: 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
        color: 'white', padding: '16px 32px',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5">
            <path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1-2-1Z"/>
            <path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"/>
            <path d="M12 18V6"/>
          </svg>
          <h1 style={{ margin: 0, fontSize: '28px', fontWeight: '800', letterSpacing: '-0.025em' }}>
            FacturePro
          </h1>
        </div>
        
        <div style={{ display: 'flex', gap: '24px', alignItems: 'center' }}>
          <button
            onClick={() => navigate('/dashboard')}
            style={{
              background: 'rgba(255,255,255,0.2)', color: 'white', border: 'none',
              padding: '10px 18px', borderRadius: '8px', cursor: 'pointer',
              fontWeight: '600', fontSize: '14px'
            }}
          >
            📊 Dashboard
          </button>
          <button
            onClick={() => navigate('/clients')}
            style={{
              background: 'transparent', color: 'rgba(255,255,255,0.8)', border: 'none',
              padding: '10px 18px', borderRadius: '8px', cursor: 'pointer',
              fontWeight: '500', fontSize: '14px'
            }}
          >
            👥 Clients
          </button>
          <button
            onClick={() => navigate('/invoices')}
            style={{
              background: 'transparent', color: 'rgba(255,255,255,0.8)', border: 'none',
              padding: '10px 18px', borderRadius: '8px', cursor: 'pointer',
              fontWeight: '500', fontSize: '14px'
            }}
          >
            📄 Factures
          </button>
        </div>

        <button
          onClick={logout}
          style={{
            background: '#ef4444', color: 'white', border: 'none',
            padding: '10px 18px', borderRadius: '8px', cursor: 'pointer',
            fontWeight: '600'
          }}
        >
          Déconnexion
        </button>
      </nav>

      {/* Dashboard Content */}
      <div style={{ padding: '32px' }}>
        <div style={{ marginBottom: '32px' }}>
          <h2 style={{ fontSize: '32px', fontWeight: '800', color: '#0f172a', margin: '0 0 8px 0' }}>
            Tableau de bord
          </h2>
          <p style={{ color: '#64748b', fontSize: '16px', margin: 0 }}>
            Vue d'ensemble de votre activité
          </p>
        </div>

        {stats.loading ? (
          <div style={{ textAlign: 'center', padding: '40px' }}>
            <div style={{ fontSize: '48px', marginBottom: '16px' }}>⏳</div>
            <p>Chargement des statistiques...</p>
          </div>
        ) : (
          <>
            {/* Stats Cards */}
            <div style={{ 
              display: 'grid', 
              gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', 
              gap: '24px', 
              marginBottom: '32px' 
            }}>
              <div style={{
                background: 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)',
                color: 'white', padding: '28px', borderRadius: '16px',
                textAlign: 'center', position: 'relative', overflow: 'hidden'
              }}>
                <div style={{ fontSize: '48px', marginBottom: '12px' }}>👥</div>
                <div style={{ fontSize: '32px', fontWeight: '800', marginBottom: '4px' }}>
                  {stats.data?.total_clients || 0}
                </div>
                <div style={{ fontSize: '14px', opacity: 0.9 }}>Clients</div>
              </div>

              <div style={{
                background: 'linear-gradient(135deg, #10b981 0%, #047857 100%)',
                color: 'white', padding: '28px', borderRadius: '16px',
                textAlign: 'center'
              }}>
                <div style={{ fontSize: '48px', marginBottom: '12px' }}>📄</div>
                <div style={{ fontSize: '32px', fontWeight: '800', marginBottom: '4px' }}>
                  {stats.data?.total_invoices || 0}
                </div>
                <div style={{ fontSize: '14px', opacity: 0.9 }}>Factures</div>
              </div>

              <div style={{
                background: 'linear-gradient(135deg, #7c3aed 0%, #5b21b6 100%)',
                color: 'white', padding: '28px', borderRadius: '16px',
                textAlign: 'center'
              }}>
                <div style={{ fontSize: '48px', marginBottom: '12px' }}>📝</div>
                <div style={{ fontSize: '32px', fontWeight: '800', marginBottom: '4px' }}>
                  {stats.data?.total_quotes || 0}
                </div>
                <div style={{ fontSize: '14px', opacity: 0.9 }}>Soumissions</div>
              </div>

              <div style={{
                background: 'linear-gradient(135deg, #dc2626 0%, #991b1b 100%)',
                color: 'white', padding: '28px', borderRadius: '16px',
                textAlign: 'center'
              }}>
                <div style={{ fontSize: '48px', marginBottom: '12px' }}>💰</div>
                <div style={{ fontSize: '20px', fontWeight: '800', marginBottom: '4px' }}>
                  {new Intl.NumberFormat('fr-CA', { style: 'currency', currency: 'CAD' }).format(stats.data?.total_revenue || 0)}
                </div>
                <div style={{ fontSize: '14px', opacity: 0.9 }}>Revenus</div>
              </div>
            </div>

            {/* Quick Actions */}
            <div style={{
              background: 'white', border: '1px solid #e2e8f0',
              borderRadius: '16px', padding: '32px'
            }}>
              <h3 style={{ margin: '0 0 24px 0', fontSize: '20px', fontWeight: '700', color: '#0f172a' }}>
                🚀 Actions rapides
              </h3>
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: '16px'
              }}>
                <button
                  onClick={() => navigate('/clients')}
                  style={{
                    background: '#f8fafc', border: '1px solid #e2e8f0',
                    padding: '20px', borderRadius: '12px', cursor: 'pointer',
                    textAlign: 'center', transition: 'all 0.3s ease'
                  }}
                  onMouseEnter={(e) => {
                    e.target.style.background = '#f1f5f9';
                    e.target.style.transform = 'translateY(-2px)';
                  }}
                  onMouseLeave={(e) => {
                    e.target.style.background = '#f8fafc';
                    e.target.style.transform = 'translateY(0)';
                  }}
                >
                  <div style={{ fontSize: '32px', marginBottom: '8px' }}>👥</div>
                  <div style={{ fontWeight: '600', color: '#374151' }}>Gérer les clients</div>
                </button>

                <button
                  onClick={() => navigate('/invoices')}
                  style={{
                    background: '#f8fafc', border: '1px solid #e2e8f0',
                    padding: '20px', borderRadius: '12px', cursor: 'pointer',
                    textAlign: 'center', transition: 'all 0.3s ease'
                  }}
                >
                  <div style={{ fontSize: '32px', marginBottom: '8px' }}>📄</div>
                  <div style={{ fontWeight: '600', color: '#374151' }}>Créer une facture</div>
                </button>

                <button
                  style={{
                    background: '#f8fafc', border: '1px solid #e2e8f0',
                    padding: '20px', borderRadius: '12px', cursor: 'pointer',
                    textAlign: 'center', opacity: 0.6
                  }}
                >
                  <div style={{ fontSize: '32px', marginBottom: '8px' }}>📦</div>
                  <div style={{ fontWeight: '600', color: '#374151' }}>Produits (bientôt)</div>
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

// Clients Page
const ClientsPage = ({ navigate, user, logout }) => {
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({ name: '', email: '', phone: '', address: '', city: '', postal_code: '', country: '' });

  useEffect(() => {
    fetchClients();
  }, []);

  const fetchClients = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/clients`);
      setClients(response.data);
    } catch (error) {
      console.error('Error fetching clients:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', background: '#f8fafc' }}>
      {/* Navigation */}
      <nav style={{
        background: 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
        color: 'white', padding: '16px 32px',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center'
      }}>
        <h1 style={{ margin: 0, fontSize: '24px', fontWeight: 'bold' }}>FacturePro</h1>
        <div style={{ display: 'flex', gap: '20px' }}>
          <button onClick={() => navigate('/dashboard')} style={{ background: 'transparent', color: 'rgba(255,255,255,0.8)', border: 'none', padding: '8px 16px', borderRadius: '6px', cursor: 'pointer' }}>Dashboard</button>
          <button style={{ background: 'rgba(255,255,255,0.2)', color: 'white', border: 'none', padding: '8px 16px', borderRadius: '6px' }}>Clients</button>
          <button onClick={() => navigate('/invoices')} style={{ background: 'transparent', color: 'rgba(255,255,255,0.8)', border: 'none', padding: '8px 16px', borderRadius: '6px', cursor: 'pointer' }}>Factures</button>
        </div>
        <button onClick={logout} style={{ background: '#ef4444', color: 'white', border: 'none', padding: '8px 16px', borderRadius: '6px', cursor: 'pointer' }}>Déconnexion</button>
      </nav>

      <div style={{ padding: '32px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
          <div>
            <h2 style={{ fontSize: '28px', fontWeight: '800', color: '#0f172a', margin: '0 0 8px 0' }}>👥 Clients</h2>
            <p style={{ color: '#64748b', margin: 0 }}>{clients.length} client{clients.length > 1 ? 's' : ''} enregistré{clients.length > 1 ? 's' : ''}</p>
          </div>
          <button
            onClick={() => setShowForm(true)}
            style={{
              background: 'linear-gradient(135deg, #3b82f6, #1d4ed8)',
              color: 'white', border: 'none', padding: '14px 28px',
              borderRadius: '12px', cursor: 'pointer', fontWeight: '700',
              fontSize: '16px', boxShadow: '0 4px 12px rgba(59,130,246,0.4)'
            }}
          >
            ➕ Nouveau Client
          </button>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '60px' }}>
            <div style={{ fontSize: '64px', marginBottom: '20px' }}>⏳</div>
            <p style={{ fontSize: '18px', color: '#64748b' }}>Chargement des clients...</p>
          </div>
        ) : clients.length === 0 ? (
          <div style={{
            background: 'white', border: '2px dashed #d1d5db',
            borderRadius: '16px', padding: '60px', textAlign: 'center'
          }}>
            <div style={{ fontSize: '80px', marginBottom: '24px' }}>👥</div>
            <h3 style={{ fontSize: '24px', fontWeight: '700', color: '#374151', margin: '0 0 12px 0' }}>Aucun client enregistré</h3>
            <p style={{ color: '#6b7280', fontSize: '16px', margin: '0 0 32px 0' }}>Commencez par ajouter votre premier client pour créer des factures</p>
            <button
              onClick={() => setShowForm(true)}
              style={{
                background: '#3b82f6', color: 'white', border: 'none',
                padding: '16px 32px', borderRadius: '12px', cursor: 'pointer',
                fontWeight: '700', fontSize: '16px'
              }}
            >
              🚀 Ajouter mon premier client
            </button>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
            {clients.map(client => (
              <div key={client.id} style={{
                background: 'white', border: '1px solid #e5e7eb',
                borderRadius: '12px', padding: '24px',
                boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                transition: 'all 0.3s ease'
              }}>
                <h3 style={{ fontSize: '20px', fontWeight: '700', color: '#1f2937', margin: '0 0 12px 0' }}>
                  {client.name}
                </h3>
                <div style={{ fontSize: '14px', color: '#6b7280', marginBottom: '8px' }}>📧 {client.email}</div>
                {client.phone && <div style={{ fontSize: '14px', color: '#6b7280', marginBottom: '8px' }}>📱 {client.phone}</div>}
                {client.address && <div style={{ fontSize: '14px', color: '#6b7280', marginBottom: '16px' }}>📍 {client.address}</div>}
                
                <div style={{ textAlign: 'right' }}>
                  <button
                    onClick={async () => {
                      if (window.confirm('Supprimer ce client ?')) {
                        try {
                          await axios.delete(`${BACKEND_URL}/api/clients/${client.id}`);
                          fetchClients();
                        } catch (error) {
                          alert('Erreur lors de la suppression');
                        }
                      }
                    }}
                    style={{
                      background: '#fef2f2', color: '#dc2626', border: '1px solid #fecaca',
                      padding: '8px 12px', borderRadius: '8px', cursor: 'pointer',
                      fontSize: '14px', fontWeight: '500'
                    }}
                  >
                    🗑️ Supprimer
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Client Form Modal */}
      {showForm && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center',
          justifyContent: 'center', zIndex: 1000, padding: '20px'
        }}>
          <div style={{
            background: 'white', padding: '32px', borderRadius: '16px',
            width: '100%', maxWidth: '600px', maxHeight: '90vh', overflow: 'auto'
          }}>
            <h3 style={{ fontSize: '24px', fontWeight: '700', color: '#1f2937', margin: '0 0 24px 0' }}>👥 Nouveau Client</h3>
            
            <form onSubmit={async (e) => {
              e.preventDefault();
              try {
                await axios.post(`${BACKEND_URL}/api/clients`, formData);
                setFormData({ name: '', email: '', phone: '', address: '', city: '', postal_code: '', country: '' });
                setShowForm(false);
                fetchClients();
              } catch (error) {
                alert('Erreur lors de la création du client');
              }
            }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '20px', marginBottom: '24px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '14px', fontWeight: '600', color: '#374151', marginBottom: '8px' }}>Nom complet *</label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                    required
                    placeholder="Jean Dupont"
                    style={{
                      width: '100%', padding: '12px', border: '1px solid #d1d5db',
                      borderRadius: '8px', fontSize: '16px', boxSizing: 'border-box'
                    }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '14px', fontWeight: '600', color: '#374151', marginBottom: '8px' }}>Email *</label>
                  <input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData(prev => ({ ...prev, email: e.target.value }))}
                    required
                    placeholder="jean@entreprise.com"
                    style={{
                      width: '100%', padding: '12px', border: '1px solid #d1d5db',
                      borderRadius: '8px', fontSize: '16px', boxSizing: 'border-box'
                    }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '14px', fontWeight: '600', color: '#374151', marginBottom: '8px' }}>Téléphone</label>
                  <input
                    type="tel"
                    value={formData.phone}
                    onChange={(e) => setFormData(prev => ({ ...prev, phone: e.target.value }))}
                    placeholder="514-123-4567"
                    style={{
                      width: '100%', padding: '12px', border: '1px solid #d1d5db',
                      borderRadius: '8px', fontSize: '16px', boxSizing: 'border-box'
                    }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '14px', fontWeight: '600', color: '#374151', marginBottom: '8px' }}>Adresse</label>
                  <input
                    type="text"
                    value={formData.address}
                    onChange={(e) => setFormData(prev => ({ ...prev, address: e.target.value }))}
                    placeholder="123 Rue Example"
                    style={{
                      width: '100%', padding: '12px', border: '1px solid #d1d5db',
                      borderRadius: '8px', fontSize: '16px', boxSizing: 'border-box'
                    }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '14px', fontWeight: '600', color: '#374151', marginBottom: '8px' }}>Ville</label>
                  <input
                    type="text"
                    value={formData.city}
                    onChange={(e) => setFormData(prev => ({ ...prev, city: e.target.value }))}
                    placeholder="Montréal"
                    style={{
                      width: '100%', padding: '12px', border: '1px solid #d1d5db',
                      borderRadius: '8px', fontSize: '16px', boxSizing: 'border-box'
                    }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '14px', fontWeight: '600', color: '#374151', marginBottom: '8px' }}>Code postal</label>
                  <input
                    type="text"
                    value={formData.postal_code}
                    onChange={(e) => setFormData(prev => ({ ...prev, postal_code: e.target.value }))}
                    placeholder="H1A 1A1"
                    style={{
                      width: '100%', padding: '12px', border: '1px solid #d1d5db',
                      borderRadius: '8px', fontSize: '16px', boxSizing: 'border-box'
                    }}
                  />
                </div>
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
                    cursor: 'pointer', fontWeight: '700'
                  }}
                >
                  💾 Créer le client
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

// Invoices Page
const InvoicesPage = ({ navigate, user, logout }) => {
  return (
    <div style={{ minHeight: '100vh', background: '#f8fafc' }}>
      <nav style={{
        background: 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
        color: 'white', padding: '16px 32px',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center'
      }}>
        <h1 style={{ margin: 0, fontSize: '24px', fontWeight: 'bold' }}>FacturePro</h1>
        <div style={{ display: 'flex', gap: '20px' }}>
          <button onClick={() => navigate('/dashboard')} style={{ background: 'transparent', color: 'rgba(255,255,255,0.8)', border: 'none', padding: '8px 16px', borderRadius: '6px', cursor: 'pointer' }}>Dashboard</button>
          <button onClick={() => navigate('/clients')} style={{ background: 'transparent', color: 'rgba(255,255,255,0.8)', border: 'none', padding: '8px 16px', borderRadius: '6px', cursor: 'pointer' }}>Clients</button>
          <button style={{ background: 'rgba(255,255,255,0.2)', color: 'white', border: 'none', padding: '8px 16px', borderRadius: '6px' }}>Factures</button>
        </div>
        <button onClick={logout} style={{ background: '#ef4444', color: 'white', border: 'none', padding: '8px 16px', borderRadius: '6px', cursor: 'pointer' }}>Déconnexion</button>
      </nav>

      <div style={{ padding: '32px', textAlign: 'center' }}>
        <div style={{ fontSize: '80px', marginBottom: '24px' }}>📄</div>
        <h2 style={{ fontSize: '28px', fontWeight: '800', color: '#1f2937', marginBottom: '16px' }}>Factures</h2>
        <p style={{ color: '#6b7280', fontSize: '18px', marginBottom: '32px' }}>Fonctionnalité en cours de développement...</p>
        
        <div style={{
          background: 'linear-gradient(135deg, #f59e0b, #d97706)',
          color: 'white', padding: '24px', borderRadius: '16px',
          display: 'inline-block'
        }}>
          <div style={{ fontSize: '32px', marginBottom: '8px' }}>🚧</div>
          <div style={{ fontWeight: '700' }}>Bientôt disponible</div>
          <div style={{ fontSize: '14px', opacity: 0.9 }}>Création et gestion de factures</div>
        </div>
      </div>
    </div>
  );
};

// Settings Page
const SettingsPage = ({ navigate, user, logout }) => {
  return (
    <div style={{ minHeight: '100vh', background: '#f8fafc' }}>
      <nav style={{
        background: 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
        color: 'white', padding: '16px 32px',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center'
      }}>
        <h1 style={{ margin: 0, fontSize: '24px', fontWeight: 'bold' }}>FacturePro</h1>
        <div style={{ display: 'flex', gap: '20px' }}>
          <button onClick={() => navigate('/dashboard')} style={{ background: 'transparent', color: 'rgba(255,255,255,0.8)', border: 'none', padding: '8px 16px', borderRadius: '6px', cursor: 'pointer' }}>Dashboard</button>
          <button onClick={() => navigate('/clients')} style={{ background: 'transparent', color: 'rgba(255,255,255,0.8)', border: 'none', padding: '8px 16px', borderRadius: '6px', cursor: 'pointer' }}>Clients</button>
          <button style={{ background: 'rgba(255,255,255,0.2)', color: 'white', border: 'none', padding: '8px 16px', borderRadius: '6px' }}>Paramètres</button>
        </div>
        <button onClick={logout} style={{ background: '#ef4444', color: 'white', border: 'none', padding: '8px 16px', borderRadius: '6px', cursor: 'pointer' }}>Déconnexion</button>
      </nav>

      <div style={{ padding: '32px', textAlign: 'center' }}>
        <div style={{ fontSize: '80px', marginBottom: '24px' }}>⚙️</div>
        <h2 style={{ fontSize: '28px', fontWeight: '800', color: '#1f2937', marginBottom: '16px' }}>Paramètres</h2>
        <p style={{ color: '#6b7280', fontSize: '18px' }}>Configuration de l'entreprise - En développement</p>
      </div>
    </div>
  );
};

// Products Page
const ProductsPage = ({ navigate, user, logout }) => {
  return (
    <div style={{ minHeight: '100vh', background: '#f8fafc' }}>
      <div style={{ padding: '32px', textAlign: 'center' }}>
        <h2>Produits - En développement</h2>
      </div>
    </div>
  );
};

export default App;