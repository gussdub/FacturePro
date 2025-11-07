import React, { useState, createContext, useContext, useEffect } from 'react';
import axios from 'axios';
import ClientsPage from './ClientsPage';
import SettingsPage from './SettingsPage';
import InvoicesPage from './InvoicesPage';
import ProductsPage from './ProductsPage';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'https://facturepro-api.onrender.com';

// Auth Context
const AuthContext = createContext();
export const useAuth = () => useContext(AuthContext);

// Navigation Component
const Navigation = ({ currentPage, onPageChange }) => {
  const { logout } = useAuth();

  const navStyle = {
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    color: 'white',
    padding: '15px 30px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    boxShadow: '0 2px 10px rgba(0,0,0,0.1)'
  };

  const menuStyle = {
    display: 'flex',
    gap: '25px',
    flexWrap: 'wrap'
  };

  const linkStyle = (active) => ({
    background: active ? 'rgba(255,255,255,0.25)' : 'transparent',
    padding: '10px 18px',
    borderRadius: '8px',
    cursor: 'pointer',
    fontWeight: active ? '600' : '400',
    transition: 'all 0.3s ease',
    border: active ? '1px solid rgba(255,255,255,0.3)' : '1px solid transparent',
    fontSize: '14px'
  });

  return (
    <nav style={navStyle}>
      <h1 style={{ margin: 0, fontSize: '26px', fontWeight: 'bold' }}>🧾 FacturePro</h1>
      
      <div style={menuStyle}>
        <div 
          style={linkStyle(currentPage === 'dashboard')}
          onClick={() => onPageChange('dashboard')}
        >
          📊 Dashboard
        </div>
        <div 
          style={linkStyle(currentPage === 'clients')}
          onClick={() => onPageChange('clients')}
        >
          👥 Clients
        </div>
        <div 
          style={linkStyle(currentPage === 'products')}
          onClick={() => onPageChange('products')}
        >
          📦 Produits
        </div>
        <div 
          style={linkStyle(currentPage === 'invoices')}
          onClick={() => onPageChange('invoices')}
        >
          📄 Factures
        </div>
        <div 
          style={linkStyle(currentPage === 'quotes')}
          onClick={() => onPageChange('quotes')}
        >
          📝 Soumissions
        </div>
        <div 
          style={linkStyle(currentPage === 'settings')}
          onClick={() => onPageChange('settings')}
        >
          ⚙️ Paramètres
        </div>
      </div>

      <button
        onClick={logout}
        style={{
          background: '#ef4444',
          color: 'white',
          border: 'none',
          padding: '10px 18px',
          borderRadius: '8px',
          cursor: 'pointer',
          fontWeight: '500'
        }}
      >
        🚪 Déconnexion
      </button>
    </nav>
  );
};

// Enhanced Dashboard with stats
const Dashboard = ({ onPageChange }) => {
  const { user } = useAuth();
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

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('fr-CA', {
      style: 'currency',
      currency: 'CAD'
    }).format(amount || 0);
  };

  return (
    <div style={{ padding: '30px' }}>
      <h2 style={{ marginBottom: '30px', color: '#333' }}>📊 Tableau de bord</h2>
      
      {stats.loading ? (
        <div>Chargement des statistiques...</div>
      ) : stats.error ? (
        <div style={{ color: '#dc2626' }}>Erreur : {stats.error}</div>
      ) : (
        <>
          {/* Stats Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '20px', marginBottom: '30px' }}>
            <div style={{
              background: 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)',
              color: 'white',
              padding: '20px',
              borderRadius: '12px',
              textAlign: 'center'
            }}>
              <div style={{ fontSize: '32px', marginBottom: '8px' }}>👥</div>
              <div style={{ fontSize: '24px', fontWeight: 'bold' }}>{stats.data?.total_clients || 0}</div>
              <div style={{ fontSize: '14px', opacity: 0.9 }}>Clients</div>
            </div>

            <div style={{
              background: 'linear-gradient(135deg, #059669 0%, #047857 100%)',
              color: 'white',
              padding: '20px',
              borderRadius: '12px',
              textAlign: 'center'
            }}>
              <div style={{ fontSize: '32px', marginBottom: '8px' }}>📄</div>
              <div style={{ fontSize: '24px', fontWeight: 'bold' }}>{stats.data?.total_invoices || 0}</div>
              <div style={{ fontSize: '14px', opacity: 0.9 }}>Factures</div>
            </div>

            <div style={{
              background: 'linear-gradient(135deg, #7c3aed 0%, #5b21b6 100%)',
              color: 'white',
              padding: '20px',
              borderRadius: '12px',
              textAlign: 'center'
            }}>
              <div style={{ fontSize: '32px', marginBottom: '8px' }}>📝</div>
              <div style={{ fontSize: '24px', fontWeight: 'bold' }}>{stats.data?.total_quotes || 0}</div>
              <div style={{ fontSize: '14px', opacity: 0.9 }}>Soumissions</div>
            </div>

            <div style={{
              background: 'linear-gradient(135deg, #dc2626 0%, #991b1b 100%)',
              color: 'white',
              padding: '20px',
              borderRadius: '12px',
              textAlign: 'center'
            }}>
              <div style={{ fontSize: '32px', marginBottom: '8px' }}>💰</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold' }}>{formatCurrency(stats.data?.total_revenue || 0)}</div>
              <div style={{ fontSize: '14px', opacity: 0.9 }}>Revenus</div>
            </div>
          </div>

          {/* Quick Actions */}
          <div style={{
            background: 'white',
            border: '1px solid #e2e8f0',
            borderRadius: '12px',
            padding: '25px'
          }}>
            <h3 style={{ marginTop: 0, marginBottom: '20px', color: '#333' }}>🚀 Actions rapides</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '15px' }}>
              <button
                onClick={() => onPageChange('clients')}
                style={{
                  background: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  padding: '15px',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  textAlign: 'center'
                }}
              >
                <div style={{ fontSize: '24px', marginBottom: '8px' }}>👥</div>
                <div style={{ fontWeight: '600', color: '#374151' }}>Gérer les clients</div>
              </button>

              <button
                onClick={() => onPageChange('invoices')}
                style={{
                  background: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  padding: '15px',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  textAlign: 'center'
                }}
              >
                <div style={{ fontSize: '24px', marginBottom: '8px' }}>📄</div>
                <div style={{ fontWeight: '600', color: '#374151' }}>Créer une facture</div>
              </button>

              <button
                onClick={() => onPageChange('products')}
                style={{
                  background: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  padding: '15px',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  textAlign: 'center'
                }}
              >
                <div style={{ fontSize: '24px', marginBottom: '8px' }}>📦</div>
                <div style={{ fontWeight: '600', color: '#374151' }}>Gérer les produits</div>
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

// Forgot Password Modal Component
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
      // Mock password reset - in production, this would call your backend
      await new Promise(resolve => setTimeout(resolve, 1000));
      setMessage('Un email de réinitialisation a été envoyé à votre adresse.');
    } catch (err) {
      setError('Une erreur est survenue. Veuillez réessayer.');
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
          Mot de passe oublié ?
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

// Login Component (restored with original design)
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

  const handleChange = (e) => {
    setFormData(prev => ({
      ...prev,
      [e.target.name]: e.target.value
    }));
  };

  return (
    <div style={{ 
      minHeight: '100vh', 
      background: 'linear-gradient(to-br, #f8fafc, #e0e7ff, #c7d2fe)',
      display: 'flex',
      fontFamily: 'system-ui, -apple-system, sans-serif'
    }}>
      {/* Left side - Hero Section */}
      <div style={{
        display: 'none',
        '@media (min-width: 1024px)': { display: 'flex' },
        width: '50%',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        position: 'relative',
        overflow: 'hidden'
      }} className="hidden lg:flex lg:w-1/2">
        <div style={{
          position: 'absolute',
          top: '80px',
          left: '80px',
          width: '288px',
          height: '288px',
          background: 'rgba(255,255,255,0.1)',
          borderRadius: '50%',
          filter: 'blur(64px)'
        }}></div>
        <div style={{
          position: 'absolute',
          bottom: '80px',
          right: '80px',
          width: '384px',
          height: '384px',
          background: 'rgba(59, 130, 246, 0.2)',
          borderRadius: '50%',
          filter: 'blur(64px)'
        }}></div>
        
        <div style={{
          position: 'relative',
          zIndex: 10,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          padding: '0 48px',
          color: 'white'
        }}>
          <div style={{ marginBottom: '32px' }}>
            <div style={{
              width: '64px',
              height: '64px',
              color: 'rgba(255,255,255,0.9)',
              marginBottom: '24px',
              fontSize: '64px'
            }}>🧾</div>
            <h1 style={{
              fontSize: '48px',
              fontWeight: 'bold',
              marginBottom: '16px',
              lineHeight: '1.2',
              margin: 0
            }}>
              Simplifiez votre
              <span style={{ display: 'block', color: '#bfdbfe' }}>facturation</span>
            </h1>
            <p style={{
              fontSize: '20px',
              color: 'rgba(255,255,255,0.8)',
              lineHeight: '1.6',
              margin: 0
            }}>
              Gérez vos factures, soumissions et clients en toute simplicité avec notre solution complète et intuitive.
            </p>
          </div>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              background: 'rgba(255,255,255,0.1)',
              padding: '12px 20px',
              borderRadius: '8px'
            }}>
              <div style={{ fontSize: '24px', marginRight: '12px' }}>⚡</div>
              <div>
                <div style={{ fontWeight: '600', fontSize: '16px' }}>Facturation instantanée</div>
                <div style={{ fontSize: '14px', opacity: 0.9 }}>Créez et envoyez vos factures en quelques clics</div>
              </div>
            </div>
          </div>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginTop: '20px' }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              background: 'rgba(255,255,255,0.1)',
              padding: '12px 20px',
              borderRadius: '8px'
            }}>
              <div style={{ fontSize: '24px', marginRight: '12px' }}>🔄</div>
              <div>
                <div style={{ fontWeight: '600', fontSize: '16px' }}>Récurrence automatique</div>
                <div style={{ fontSize: '14px', opacity: 0.9 }}>Programmez vos factures récurrentes</div>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginTop: '20px' }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              background: 'rgba(255,255,255,0.1)',
              padding: '12px 20px',
              borderRadius: '8px'
            }}>
              <div style={{ fontSize: '24px', marginRight: '12px' }}>🛡️</div>
              <div>
                <div style={{ fontWeight: '600', fontSize: '16px' }}>Sécurisé et fiable</div>
                <div style={{ fontSize: '14px', opacity: 0.9 }}>Vos données sont protégées et sauvegardées</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Right side - Login Form */}
      <div style={{
        width: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px'
      }}>
        <div style={{ width: '100%', maxWidth: '440px' }}>
          {/* Logo and Title */}
          <div style={{ textAlign: 'center', marginBottom: '32px' }}>
            <div style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '80px',
              height: '80px',
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              borderRadius: '20px',
              marginBottom: '20px',
              boxShadow: '0 10px 25px rgba(102, 126, 234, 0.3)'
            }}>
              <div style={{ fontSize: '36px', color: 'white' }}>🧾</div>
            </div>
            <h1 style={{
              fontSize: '32px',
              fontWeight: 'bold',
              color: '#1f2937',
              margin: '0 0 8px 0'
            }}>
              FacturePro
            </h1>
            <h2 style={{
              fontSize: '24px',
              fontWeight: '600',
              color: '#374151',
              margin: '0 0 8px 0'
            }}>
              {isLogin ? 'Connexion' : 'Créer un compte'}
            </h2>
            <p style={{
              color: '#6b7280',
              margin: 0,
              fontSize: '16px'
            }}>
              {isLogin 
                ? 'Accédez à votre tableau de bord' 
                : 'Démarrez votre essai gratuit aujourd\'hui'
              }
            </p>
          </div>

          <div style={{
            background: 'white',
            padding: '32px',
            borderRadius: '16px',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
            border: 'none'
          }}>
            {error && (
              <div style={{
                background: '#fee2e2',
                border: '1px solid #fecaca',
                borderRadius: '8px',
                padding: '12px',
                marginBottom: '24px'
              }}>
                <div style={{ color: '#b91c1c', fontSize: '14px' }}>
                  {error}
                </div>
              </div>
            )}

            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              {!isLogin && (
                <div>
                  <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: '#374151', marginBottom: '8px' }}>
                    Nom de l'entreprise
                  </label>
                  <input
                    type="text"
                    name="companyName"
                    value={formData.companyName}
                    onChange={handleChange}
                    placeholder="Mon Entreprise"
                    required
                    style={{
                      width: '100%',
                      height: '48px',
                      fontSize: '16px',
                      padding: '12px',
                      border: '1px solid #d1d5db',
                      borderRadius: '8px',
                      transition: 'all 0.2s',
                      boxSizing: 'border-box'
                    }}
                  />
                </div>
              )}

              <div>
                <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: '#374151', marginBottom: '8px' }}>
                  Adresse email
                </label>
                <input
                  type="email"
                  name="email"
                  value={formData.email}
                  onChange={handleChange}
                  placeholder="votre@email.com"
                  required
                  style={{
                    width: '100%',
                    height: '48px',
                    fontSize: '16px',
                    padding: '12px',
                    border: '1px solid #d1d5db',
                    borderRadius: '8px',
                    transition: 'all 0.2s',
                    boxSizing: 'border-box'
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: '#374151', marginBottom: '8px' }}>
                  Mot de passe
                </label>
                <div style={{ position: 'relative' }}>
                  <input
                    type={showPassword ? "text" : "password"}
                    name="password"
                    value={formData.password}
                    onChange={handleChange}
                    placeholder="••••••••"
                    required
                    style={{
                      width: '100%',
                      height: '48px',
                      fontSize: '16px',
                      padding: '12px 48px 12px 12px',
                      border: '1px solid #d1d5db',
                      borderRadius: '8px',
                      transition: 'all 0.2s',
                      boxSizing: 'border-box'
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    style={{
                      position: 'absolute',
                      right: '12px',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      color: '#6b7280',
                      fontSize: '18px'
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
                  width: '100%',
                  height: '48px',
                  fontSize: '16px',
                  fontWeight: '600',
                  background: loading ? '#9ca3af' : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  color: 'white',
                  border: 'none',
                  borderRadius: '8px',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  transform: loading ? 'none' : 'hover:scale-105',
                  transition: 'all 0.3s ease',
                  boxShadow: '0 4px 14px 0 rgba(102, 126, 234, 0.4)'
                }}
              >
                {loading ? (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <div style={{
                      width: '20px',
                      height: '20px',
                      border: '2px solid transparent',
                      borderTop: '2px solid white',
                      borderRadius: '50%',
                      animation: 'spin 1s linear infinite',
                      marginRight: '8px'
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
                    background: 'none',
                    border: 'none',
                    color: '#667eea',
                    fontSize: '14px',
                    cursor: 'pointer',
                    textDecoration: 'underline'
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
                  background: 'none',
                  border: 'none',
                  color: '#667eea',
                  fontSize: '16px',
                  fontWeight: '500',
                  cursor: 'pointer',
                  transition: 'color 0.3s'
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
            <div style={{ marginTop: '24px', textAlign: 'center', fontSize: '14px', color: '#6b7280' }}>
              En créant un compte, vous acceptez nos{' '}
              <a href="#" style={{ color: '#667eea', textDecoration: 'none' }}>
                conditions d'utilisation
              </a>{' '}
              et notre{' '}
              <a href="#" style={{ color: '#667eea', textDecoration: 'none' }}>
                politique de confidentialité
              </a>
            </div>
          )}
        </div>
      </div>

      {/* Forgot Password Modal */}
      {showForgotPassword && <ForgotPasswordModal onClose={() => setShowForgotPassword(false)} />}
    </div>
  );
};

// Main App Content
const AppContent = () => {
  const { user } = useAuth();
  const [currentPage, setCurrentPage] = useState('dashboard');

  const renderPage = () => {
    switch (currentPage) {
      case 'clients':
        return <ClientsPage />;
      case 'products':
        return <ProductsPage />;
      case 'invoices':
        return <InvoicesPage />;
      case 'quotes':
        return <div style={{ padding: '30px', textAlign: 'center' }}>
          <h2>📝 Soumissions</h2>
          <p>En cours de développement...</p>
        </div>;
      case 'settings':
        return <SettingsPage />;
      default:
        return <Dashboard onPageChange={setCurrentPage} />;
    }
  };

  return (
    <div style={{ minHeight: '100vh', background: '#f8fafc' }}>
      <Navigation currentPage={currentPage} onPageChange={setCurrentPage} />
      <main>
        {renderPage()}
      </main>
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
        error: error.response?.data?.detail || 'Erreur de connexion'
      };
    }
  };

  const register = async (email, password, company_name) => {
    try {
      const response = await axios.post(`${BACKEND_URL}/api/auth/register`, {
        email,
        password,
        company_name
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
        error: error.response?.data?.detail || 'Erreur inscription'
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
  return token ? <AppContent /> : <LoginPage />;
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