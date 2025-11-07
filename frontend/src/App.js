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

// Login Component (unchanged but improved styling)
const LoginPage = () => {
  const [formData, setFormData] = useState({ email: '', password: '', companyName: '' });
  const [isLogin, setIsLogin] = useState(true);
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
      setError('Erreur de connexion');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: 'Arial, sans-serif',
      padding: '20px'
    }}>
      <div style={{
        background: 'white',
        padding: '40px',
        borderRadius: '12px',
        boxShadow: '0 10px 30px rgba(0,0,0,0.2)',
        width: '100%',
        maxWidth: '420px'
      }}>
        <div style={{ textAlign: 'center', marginBottom: '35px' }}>
          <div style={{
            display: 'inline-block',
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            padding: '15px',
            borderRadius: '12px',
            marginBottom: '15px'
          }}>
            <div style={{ fontSize: '32px' }}>🧾</div>
          </div>
          <h1 style={{
            fontSize: '28px',
            fontWeight: 'bold',
            color: '#333',
            margin: '0'
          }}>
            FacturePro
          </h1>
          <p style={{ color: '#666', margin: '8px 0 0 0' }}>
            {isLogin ? 'Connexion à votre espace' : 'Créez votre compte'}
          </p>
        </div>

        {error && (
          <div style={{
            background: '#fee2e2',
            border: '1px solid #fca5a5',
            color: '#dc2626',
            padding: '12px',
            borderRadius: '6px',
            marginBottom: '25px',
            textAlign: 'center',
            fontSize: '14px'
          }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          {!isLogin && (
            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', fontWeight: '600', color: '#374151', marginBottom: '6px' }}>
                Nom de l'entreprise *
              </label>
              <input
                type="text"
                value={formData.companyName}
                onChange={(e) => setFormData(prev => ({ ...prev, companyName: e.target.value }))}
                required={!isLogin}
                style={{
                  width: '100%',
                  padding: '12px',
                  border: '1px solid #d1d5db',
                  borderRadius: '6px',
                  fontSize: '16px',
                  boxSizing: 'border-box',
                  transition: 'border-color 0.2s'
                }}
                placeholder="Mon Entreprise Inc."
              />
            </div>
          )}

          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', fontWeight: '600', color: '#374151', marginBottom: '6px' }}>
              Adresse email *
            </label>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => setFormData(prev => ({ ...prev, email: e.target.value }))}
              required
              style={{
                width: '100%',
                padding: '12px',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                fontSize: '16px',
                boxSizing: 'border-box'
              }}
              placeholder="votre@email.com"
            />
          </div>

          <div style={{ marginBottom: '30px' }}>
            <label style={{ display: 'block', fontWeight: '600', color: '#374151', marginBottom: '6px' }}>
              Mot de passe *
            </label>
            <input
              type="password"
              value={formData.password}
              onChange={(e) => setFormData(prev => ({ ...prev, password: e.target.value }))}
              required
              style={{
                width: '100%',
                padding: '12px',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                fontSize: '16px',
                boxSizing: 'border-box'
              }}
              placeholder="Mot de passe sécurisé"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              padding: '14px',
              background: loading ? '#9ca3af' : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              fontSize: '16px',
              fontWeight: '600',
              cursor: loading ? 'not-allowed' : 'pointer',
              transition: 'all 0.3s ease'
            }}
          >
            {loading ? '⏳ Connexion...' : (isLogin ? '🔐 Se connecter' : '✨ Créer mon compte')}
          </button>
        </form>

        <div style={{ textAlign: 'center', marginTop: '25px' }}>
          <button
            onClick={() => {
              setIsLogin(!isLogin);
              setError('');
              setFormData({ email: '', password: '', companyName: '' });
            }}
            style={{
              background: 'none',
              border: 'none',
              color: '#667eea',
              cursor: 'pointer',
              textDecoration: 'underline',
              fontSize: '14px'
            }}
          >
            {isLogin ? "Nouveau sur FacturePro ? S'inscrire" : "Déjà client ? Se connecter"}
          </button>
        </div>
      </div>
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
        return <div style={{ padding: '30px' }}><h2>Soumissions - En développement</h2></div>;
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