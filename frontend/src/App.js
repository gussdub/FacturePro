import React, { useState, createContext, useContext, useEffect } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'https://facturepro-api.onrender.com';

// Auth Context
const AuthContext = createContext();
export const useAuth = () => useContext(AuthContext);

// Simple Login/Register Page
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

  const containerStyle = {
    minHeight: '100vh',
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: 'Arial, sans-serif',
    padding: '20px'
  };

  const formStyle = {
    background: 'white',
    padding: '40px',
    borderRadius: '12px',
    boxShadow: '0 10px 30px rgba(0,0,0,0.2)',
    width: '100%',
    maxWidth: '400px'
  };

  const inputStyle = {
    width: '100%',
    padding: '12px',
    border: '1px solid #ddd',
    borderRadius: '6px',
    fontSize: '16px',
    marginTop: '5px',
    boxSizing: 'border-box'
  };

  const buttonStyle = {
    width: '100%',
    padding: '14px',
    background: loading ? '#999' : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    color: 'white',
    border: 'none',
    borderRadius: '6px',
    fontSize: '16px',
    fontWeight: '600',
    cursor: loading ? 'not-allowed' : 'pointer',
    transition: 'all 0.3s ease'
  };

  return (
    <div style={containerStyle}>
      <div style={formStyle}>
        <div style={{ textAlign: 'center', marginBottom: '30px' }}>
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
          <p style={{ color: '#666', margin: '5px 0 0 0' }}>
            {isLogin ? 'Connexion à votre tableau de bord' : 'Créez votre compte gratuit'}
          </p>
        </div>

        {error && (
          <div style={{
            background: '#fee2e2',
            border: '1px solid #fca5a5',
            color: '#dc2626',
            padding: '12px',
            borderRadius: '6px',
            marginBottom: '20px',
            textAlign: 'center'
          }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          {!isLogin && (
            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', fontWeight: '600', color: '#374151', marginBottom: '5px' }}>
                Nom de l'entreprise
              </label>
              <input
                type="text"
                value={formData.companyName}
                onChange={(e) => setFormData(prev => ({ ...prev, companyName: e.target.value }))}
                required={!isLogin}
                style={inputStyle}
                placeholder="Mon Entreprise Inc."
              />
            </div>
          )}

          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', fontWeight: '600', color: '#374151', marginBottom: '5px' }}>
              Adresse email
            </label>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => setFormData(prev => ({ ...prev, email: e.target.value }))}
              required
              style={inputStyle}
              placeholder="votre@email.com"
            />
          </div>

          <div style={{ marginBottom: '30px' }}>
            <label style={{ display: 'block', fontWeight: '600', color: '#374151', marginBottom: '5px' }}>
              Mot de passe
            </label>
            <input
              type="password"
              value={formData.password}
              onChange={(e) => setFormData(prev => ({ ...prev, password: e.target.value }))}
              required
              style={inputStyle}
              placeholder="Votre mot de passe sécurisé"
            />
          </div>

          <button type="submit" disabled={loading} style={buttonStyle}>
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
            {isLogin ? "Pas encore de compte ? S'inscrire" : "Déjà un compte ? Se connecter"}
          </button>
        </div>
      </div>
    </div>
  );
};

// Dashboard
const Dashboard = () => {
  const { user, logout } = useAuth();
  const [stats, setStats] = useState({ message: 'Chargement...' });

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/health`);
      setStats(response.data);
    } catch (error) {
      setStats({ message: 'Erreur de connexion API' });
    }
  };

  const dashboardStyle = {
    minHeight: '100vh',
    background: 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)',
    padding: '20px',
    fontFamily: 'Arial, sans-serif'
  };

  const cardStyle = {
    background: 'white',
    padding: '30px',
    borderRadius: '12px',
    boxShadow: '0 4px 20px rgba(0,0,0,0.1)',
    maxWidth: '800px',
    margin: '0 auto'
  };

  const headerStyle = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '30px',
    paddingBottom: '20px',
    borderBottom: '2px solid #e5e7eb'
  };

  return (
    <div style={dashboardStyle}>
      <div style={cardStyle}>
        <div style={headerStyle}>
          <div>
            <h1 style={{ margin: 0, color: '#1f2937', fontSize: '24px' }}>
              🎉 FacturePro
            </h1>
            <p style={{ margin: '5px 0 0 0', color: '#6b7280' }}>
              Bienvenue, {user?.company_name || user?.email}
            </p>
          </div>
          <button
            onClick={logout}
            style={{
              padding: '10px 20px',
              background: '#ef4444',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontWeight: '500'
            }}
          >
            🚪 Déconnexion
          </button>
        </div>

        <div style={{ textAlign: 'center' }}>
          <div style={{ 
            background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
            color: 'white',
            padding: '20px',
            borderRadius: '8px',
            marginBottom: '20px'
          }}>
            <h2 style={{ margin: '0 0 10px 0' }}>✅ Migration Réussie !</h2>
            <p style={{ margin: 0 }}>FacturePro fonctionne maintenant sur Vercel + Render</p>
          </div>

          <div style={{ 
            background: '#f3f4f6',
            padding: '20px',
            borderRadius: '8px',
            textAlign: 'left'
          }}>
            <h3 style={{ margin: '0 0 15px 0', color: '#374151' }}>📊 Status API :</h3>
            <pre style={{ 
              background: '#1f2937',
              color: '#10b981',
              padding: '15px',
              borderRadius: '6px',
              overflow: 'auto',
              fontSize: '14px',
              margin: 0
            }}>
              {JSON.stringify(stats, null, 2)}
            </pre>
          </div>

          <p style={{ color: '#6b7280', marginTop: '20px', fontSize: '14px' }}>
            🚀 Version de base déployée. Toutes les fonctionnalités seront ajoutées progressivement.
          </p>
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

// Main App Component
function App() {
  const { token } = useAuth();

  return (
    <div>
      {token ? <Dashboard /> : <LoginPage />}
    </div>
  );
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