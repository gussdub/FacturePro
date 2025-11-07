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

// Login Page (DESIGN ORIGINAL FACTUREPRO)
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
      background: 'linear-gradient(to-br, #f1f5f9, #dbeafe, #c7d2fe)',
      display: 'flex',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
    }}>
      {/* Left Hero Section - ORIGINAL DESIGN */}
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
            {/* Beautiful Receipt Icon - ORIGINAL */}
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
          
          {/* Feature Cards - ORIGINAL */}
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
              <div style={{ fontSize: '28px' }}>🔄</div>
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
                <div style={{ fontSize: '14px', opacity: 0.9 }}>Taxes canadiennes calculées automatiquement</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Right Login Form - ORIGINAL DESIGN */}
      <div style={{
        width: window.innerWidth > 1024 ? '50%' : '100%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '40px'
      }}>
        <div style={{ width: '100%', maxWidth: '460px' }}>
          {/* Logo and Title - ORIGINAL */}
          <div style={{ textAlign: 'center', marginBottom: '40px' }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              width: '88px', height: '88px',
              background: 'linear-gradient(135deg, #4338ca 0%, #7c3aed 100%)',
              borderRadius: '24px', marginBottom: '24px',
              boxShadow: '0 20px 40px rgba(67,56,202,0.4)'
            }}>
              <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5">
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
                ? 'Accédez à votre tableau de bord' 
                : 'Démarrez votre essai gratuit aujourd\'hui'
              }
            </p>
          </div>

          {/* Form Card - ORIGINAL DESIGN */}
          <div style={{
            background: 'rgba(255,255,255,0.9)',
            backdropFilter: 'blur(20px)',
            padding: '32px', borderRadius: '24px',
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
                    value={formData.companyName}
                    onChange={(e) => setFormData(prev => ({ ...prev, companyName: e.target.value }))}
                    placeholder="Mon Entreprise"
                    required
                    style={{
                      width: '100%', height: '52px', fontSize: '16px',
                      padding: '16px', border: '1px solid #d1d5db',
                      borderRadius: '12px', boxSizing: 'border-box'
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
                  value={formData.email}
                  onChange={(e) => setFormData(prev => ({ ...prev, email: e.target.value }))}
                  placeholder="votre@email.com"
                  required
                  style={{
                    width: '100%', height: '52px', fontSize: '16px',
                    padding: '16px', border: '1px solid #d1d5db',
                    borderRadius: '12px', boxSizing: 'border-box'
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
                    value={formData.password}
                    onChange={(e) => setFormData(prev => ({ ...prev, password: e.target.value }))}
                    placeholder="••••••••••"
                    required
                    style={{
                      width: '100%', height: '52px', fontSize: '16px',
                      padding: '16px 56px 16px 16px', border: '1px solid #d1d5db',
                      borderRadius: '12px', boxSizing: 'border-box'
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    style={{
                      position: 'absolute', right: '16px', top: '50%',
                      transform: 'translateY(-50%)', background: 'none',
                      border: 'none', cursor: 'pointer', color: '#6b7280',
                      fontSize: '20px'
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
                  background: loading 
                    ? '#94a3b8' 
                    : 'linear-gradient(135deg, #4338ca 0%, #7c3aed 100%)',
                  color: 'white', border: 'none', borderRadius: '12px',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  boxShadow: '0 10px 25px rgba(67,56,202,0.4)'
                }}
              >
                {loading ? 'Chargement...' : (isLogin ? 'Se connecter' : 'Créer mon compte')}
              </button>
            </form>

            {/* Forgot Password - ORIGINAL */}
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

            {/* Toggle Login/Register */}
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
                  ? "Pas encore de compte ? S'inscrire" 
                  : "Déjà un compte ? Se connecter"
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
              <a href="#" style={{ color: '#4338ca' }}>conditions d'utilisation</a>
            </div>
          )}
        </div>
      </div>

      {/* Forgot Password Modal */}
      {showForgotPassword && <ForgotPasswordModal onClose={() => setShowForgotPassword(false)} />}
    </div>
  );
};

// Simple Dashboard (will be expanded)
const Dashboard = () => {
  const { user, logout } = useAuth();

  return (
    <div style={{ minHeight: '100vh', background: '#f8fafc' }}>
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

      <div style={{ padding: '40px', textAlign: 'center' }}>
        <h2 style={{ marginBottom: '20px', color: '#1e293b' }}>Tableau de bord</h2>
        
        <div style={{
          background: 'linear-gradient(135deg, #10b981, #059669)',
          color: 'white', padding: '30px', borderRadius: '16px',
          marginBottom: '30px'
        }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>🎉</div>
          <h3 style={{ margin: '0 0 8px 0', fontSize: '24px' }}>FacturePro Restauré !</h3>
          <p style={{ margin: 0, fontSize: '16px', opacity: 0.9 }}>
            Toutes les fonctionnalités seront ajoutées progressivement
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
        </div>
      </div>
    </div>
  );
};

// Forgot Password Modal (Complete)
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
        setSuccess('Code de récupération généré !');
        setStep('reset');
      }
    } catch (error) {
      setError('Erreur lors de la génération du code');
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
        token: resetData.token,
        new_password: resetData.new_password
      });

      setSuccess('Mot de passe réinitialisé avec succès !');
      setTimeout(onClose, 2000);
    } catch (error) {
      setError('Erreur lors de la réinitialisation');
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
        maxWidth: '480px', width: '100%'
      }}>
        <h2 style={{ margin: '0 0 20px 0', textAlign: 'center', color: '#1f2937' }}>
          🔑 {step === 'email' ? 'Récupération de compte' : 'Nouveau mot de passe'}
        </h2>

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
            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', marginBottom: '8px', fontWeight: '600' }}>Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                style={{
                  width: '100%', padding: '12px', border: '1px solid #ddd',
                  borderRadius: '8px', boxSizing: 'border-box'
                }}
              />
            </div>
            <div style={{ display: 'flex', gap: '12px' }}>
              <button type="button" onClick={onClose} style={{
                flex: 1, padding: '12px', background: '#f3f4f6', border: 'none',
                borderRadius: '8px', cursor: 'pointer'
              }}>Annuler</button>
              <button type="submit" disabled={loading} style={{
                flex: 1, padding: '12px', background: loading ? '#9ca3af' : '#4338ca',
                color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer'
              }}>{loading ? 'Génération...' : 'Générer code'}</button>
            </div>
          </form>
        ) : (
          <form onSubmit={handleResetPassword}>
            <div style={{ background: '#eff6ff', padding: '16px', borderRadius: '8px', marginBottom: '20px' }}>
              <strong>Code : </strong>
              <span style={{ fontFamily: 'monospace', wordBreak: 'break-all' }}>{resetData.token}</span>
            </div>
            
            <div style={{ marginBottom: '15px' }}>
              <input
                type="text"
                value={resetData.token}
                onChange={(e) => setResetData(prev => ({ ...prev, token: e.target.value }))}
                placeholder="Code de récupération"
                required
                style={{
                  width: '100%', padding: '12px', border: '1px solid #ddd',
                  borderRadius: '8px', fontFamily: 'monospace', boxSizing: 'border-box'
                }}
              />
            </div>
            
            <div style={{ marginBottom: '15px' }}>
              <input
                type="password"
                value={resetData.new_password}
                onChange={(e) => setResetData(prev => ({ ...prev, new_password: e.target.value }))}
                placeholder="Nouveau mot de passe"
                required
                style={{
                  width: '100%', padding: '12px', border: '1px solid #ddd',
                  borderRadius: '8px', boxSizing: 'border-box'
                }}
              />
            </div>
            
            <div style={{ marginBottom: '20px' }}>
              <input
                type="password"
                value={resetData.confirm_password}
                onChange={(e) => setResetData(prev => ({ ...prev, confirm_password: e.target.value }))}
                placeholder="Confirmer mot de passe"
                required
                style={{
                  width: '100%', padding: '12px', border: '1px solid #ddd',
                  borderRadius: '8px', boxSizing: 'border-box'
                }}
              />
            </div>
            
            <div style={{ display: 'flex', gap: '12px' }}>
              <button type="button" onClick={() => setStep('email')} style={{
                flex: 1, padding: '12px', background: '#f3f4f6', border: 'none',
                borderRadius: '8px', cursor: 'pointer'
              }}>← Retour</button>
              <button type="submit" disabled={loading} style={{
                flex: 1, padding: '12px', background: loading ? '#9ca3af' : '#4338ca',
                color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer'
              }}>{loading ? 'Réinitialisation...' : 'Réinitialiser'}</button>
            </div>
          </form>
        )}
      </div>
    </div>
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
