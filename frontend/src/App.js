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
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const initAuth = async () => {
      if (token) {
        try {
          axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
          // Could verify token here if needed
        } catch (error) {
          localStorage.removeItem('token');
          setToken(null);
        }
      }
      setLoading(false);
    };
    initAuth();
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
        error: error.response?.data?.detail || 'Erreur d\'inscription' 
      };
    }
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('token');
    delete axios.defaults.headers.common['Authorization'];
  };

  if (loading) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100vh',
        fontSize: '18px'
      }}>
        Chargement...
      </div>
    );
  }

  return (
    <AuthContext.Provider value={{ user, token, login, register, logout, isAuthenticated: !!token }}>
      {children}
    </AuthContext.Provider>
  );
};

// App Router with routing
function App() {
  const [currentRoute, setCurrentRoute] = useState(
    window.location.pathname === '/' ? '/dashboard' : window.location.pathname
  );
  const { isAuthenticated } = useAuth();

  // Simple router
  useEffect(() => {
    const handlePopState = () => {
      setCurrentRoute(window.location.pathname === '/' ? '/dashboard' : window.location.pathname);
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const navigate = (path) => {
    window.history.pushState({}, '', path);
    setCurrentRoute(path);
  };

  // Show login page if not authenticated
  if (!isAuthenticated) {
    return <LoginPage />;
  }

  // Render protected routes with Layout
  const renderPage = () => {
    switch (currentRoute) {
      case '/clients':
        return <ClientsPage />;
      case '/products':
        return <ProductsPage />;
      case '/invoices':
        return <InvoicesPage />;
      case '/quotes':
        return <QuotesPage />;
      case '/employees':
        return <EmployeesPage />;
      case '/expenses':
        return <ExpensesPage />;
      case '/export':
        return <ExportPage />;
      case '/settings':
        return <SettingsPage />;
      default:
        return <Dashboard />;
    }
  };

  return (
    <div>
      <Layout currentRoute={currentRoute} navigate={navigate}>
        {renderPage()}
      </Layout>
    </div>
  );
}

// Layout Component with Sidebar (ORIGINAL DESIGN)
const Layout = ({ currentRoute, navigate, children }) => {
  const { user, logout } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [settings, setSettings] = useState(null);

  // Load company settings for logo
  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const response = await axios.get(`${BACKEND_URL}/api/settings/company`);
        setSettings(response.data);
      } catch (error) {
        console.error('Error fetching settings:', error);
      }
    };
    fetchSettings();
  }, []);

  const navigation = [
    { name: 'Tableau de bord', href: '/dashboard', icon: '📊', current: currentRoute === '/dashboard' },
    { name: 'Clients', href: '/clients', icon: '👥', current: currentRoute === '/clients' },
    { name: 'Produits', href: '/products', icon: '📦', current: currentRoute === '/products' },
    { name: 'Factures', href: '/invoices', icon: '📄', current: currentRoute === '/invoices' },
    { name: 'Soumissions', href: '/quotes', icon: '📝', current: currentRoute === '/quotes' },
    { name: 'Employés', href: '/employees', icon: '👨‍💼', current: currentRoute === '/employees' },
    { name: 'Dépenses', href: '/expenses', icon: '💳', current: currentRoute === '/expenses' },
    { name: 'Exports', href: '/export', icon: '📊', current: currentRoute === '/export' },
    { name: 'Paramètres', href: '/settings', icon: '⚙️', current: currentRoute === '/settings' },
  ];

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: '#f8fafc' }}>
      {/* Sidebar - DESIGN ORIGINAL */}
      <aside style={{
        width: '280px',
        background: 'linear-gradient(180deg, #1e293b 0%, #334155 100%)',
        boxShadow: '4px 0 6px -1px rgba(0, 0, 0, 0.1)'
      }}>
        {/* Logo Section */}
        <div style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '48px', height: '48px',
              background: 'linear-gradient(135deg, #3b82f6, #1d4ed8)',
              borderRadius: '12px',
              display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}>
              {settings?.logo_url ? (
                <img 
                  src={settings.logo_url} 
                  alt="Logo" 
                  style={{
                    width: '32px', height: '32px',
                    objectFit: 'contain', borderRadius: '6px'
                  }}
                  onError={(e) => {
                    e.target.style.display = 'none';
                    e.target.nextSibling.style.display = 'block';
                  }}
                />
              ) : null}
              <svg 
                width="28" 
                height="28" 
                viewBox="0 0 24 24" 
                fill="none" 
                stroke="white" 
                strokeWidth="2.5"
                style={{ display: settings?.logo_url ? 'none' : 'block' }}
              >
                <path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1-2-1Z"/>
                <path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"/>
                <path d="M12 18V6"/>
              </svg>
            </div>
            <div>
              <div style={{ color: 'white', fontSize: '20px', fontWeight: '800' }}>FacturePro</div>
              <div style={{ color: '#94a3b8', fontSize: '12px' }}>Solution complète</div>
            </div>
          </div>
        </div>

        {/* Navigation Menu */}
        <nav style={{ padding: '0 16px', flex: 1 }}>
          {navigation.map((item) => {
            return (
              <button
                key={item.name}
                onClick={() => navigate(item.href)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  width: '100%',
                  padding: '14px 16px',
                  margin: '4px 0',
                  background: item.current 
                    ? 'rgba(59, 130, 246, 0.2)' 
                    : 'transparent',
                  color: item.current ? '#60a5fa' : '#cbd5e1',
                  border: 'none',
                  borderRadius: '10px',
                  cursor: 'pointer',
                  fontSize: '15px',
                  fontWeight: '600',
                  transition: 'all 0.3s ease',
                  textAlign: 'left'
                }}
                onMouseEnter={(e) => {
                  if (!item.current) {
                    e.target.style.background = 'rgba(255,255,255,0.05)';
                  }
                }}
                onMouseLeave={(e) => {
                  if (!item.current) {
                    e.target.style.background = 'transparent';
                  }
                }}
              >
                <span style={{ 
                  marginRight: '14px', 
                  fontSize: '18px',
                  filter: item.current ? 'none' : 'grayscale(1)'
                }}>
                  {item.icon}
                </span>
                {item.name}
              </button>
            );
          })}
        </nav>

        {/* User Section */}
        <div style={{ padding: '20px', borderTop: '1px solid #334155', marginTop: 'auto' }}>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: '16px' }}>
            <div style={{
              width: '40px', height: '40px',
              background: settings?.logo_url ? 'white' : '#3b82f6',
              borderRadius: '50%',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              marginRight: '12px'
            }}>
              {settings?.logo_url ? (
                <img 
                  src={settings.logo_url} 
                  alt="Logo" 
                  style={{
                    width: '32px', height: '32px',
                    objectFit: 'contain', borderRadius: '50%'
                  }}
                />
              ) : (
                <span style={{
                  color: 'white', fontSize: '16px', fontWeight: '700'
                }}>
                  {user?.company_name?.charAt(0)?.toUpperCase() || 'U'}
                </span>
              )}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ color: 'white', fontSize: '14px', fontWeight: '600' }}>
                {user?.company_name || 'Entreprise'}
              </div>
              <div style={{ color: '#94a3b8', fontSize: '12px' }}>
                {user?.email}
              </div>
            </div>
          </div>
          
          <button
            onClick={logout}
            style={{
              width: '100%',
              padding: '10px 16px',
              background: '#ef4444',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: '600'
            }}
          >
            🚪 Se déconnecter
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {/* Header */}
        <header style={{
          background: 'white',
          padding: '16px 32px',
          borderBottom: '1px solid #e5e7eb',
          boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1)'
        }}>
          <div style={{ display: 'flex', justifyContent: 'between', alignItems: 'center' }}>
            <div style={{ flex: 1 }}>
              <h1 style={{
                fontSize: '28px',
                fontWeight: '800',
                color: '#1f2937',
                margin: 0
              }}>
                {navigation.find(n => n.current)?.name || 'FacturePro'}
              </h1>
            </div>
            
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              {/* Search */}
              <div style={{ position: 'relative' }}>
                <input
                  type="text"
                  placeholder="Rechercher..."
                  style={{
                    paddingLeft: '40px',
                    paddingRight: '16px',
                    paddingTop: '8px',
                    paddingBottom: '8px',
                    border: '1px solid #d1d5db',
                    borderRadius: '8px',
                    fontSize: '14px',
                    width: '200px'
                  }}
                />
                <div style={{
                  position: 'absolute',
                  left: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: '#9ca3af',
                  fontSize: '16px'
                }}>🔍</div>
              </div>

              {/* Notifications */}
              <button style={{
                position: 'relative',
                background: 'none',
                border: 'none',
                padding: '8px',
                borderRadius: '8px',
                cursor: 'pointer',
                color: '#6b7280',
                fontSize: '18px'
              }}>
                🔔
                <span style={{
                  position: 'absolute',
                  top: '6px',
                  right: '6px',
                  width: '8px',
                  height: '8px',
                  background: '#ef4444',
                  borderRadius: '50%'
                }}></span>
              </button>

              {/* User Avatar */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 12px',
                borderRadius: '8px',
                background: '#f8fafc',
                border: '1px solid #e2e8f0'
              }}>
                <div style={{
                  width: '32px', height: '32px',
                  background: settings?.logo_url ? 'white' : '#3b82f6',
                  borderRadius: '50%',
                  display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>
                  {settings?.logo_url ? (
                    <img 
                      src={settings.logo_url} 
                      alt="Logo" 
                      style={{
                        width: '28px', height: '28px',
                        objectFit: 'contain', borderRadius: '50%'
                      }}
                    />
                  ) : (
                    <span style={{
                      color: 'white', fontSize: '14px', fontWeight: '700'
                    }}>
                      {user?.company_name?.charAt(0)?.toUpperCase() || 'U'}
                    </span>
                  )}
                </div>
                <div style={{ fontSize: '14px', fontWeight: '600', color: '#374151' }}>
                  {user?.company_name}
                </div>
              </div>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main style={{ padding: '24px', flex: 1 }}>
          <div style={{ maxWidth: '1400px', margin: '0 auto' }}>
            {children}
          </div>
        </main>
      </div>

      {/* Mobile menu overlay */}
      {sidebarOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.6)',
            zIndex: 50,
            display: window.innerWidth <= 1024 ? 'block' : 'none'
          }}
          onClick={() => setSidebarOpen(false)}
        />
      )}
    </div>
  );
};

// Login Page (DESIGN ORIGINAL COMPLET)
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
      background: 'linear-gradient(to-br, #f1f5f9, #e0e7ff, #c7d2fe)',
      display: 'flex',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
    }}>
      {/* Left Hero Section - DESIGN ORIGINAL */}
      <div style={{
        width: '50%',
        background: 'linear-gradient(135deg, #4338ca, #7c3aed)',
        position: 'relative',
        overflow: 'hidden',
        display: 'flex',
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
          
          {/* Feature highlights - ORIGINAL */}
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

      {/* Right side - Form - DESIGN ORIGINAL */}
      <div style={{
        width: '50%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '40px'
      }}>
        <div style={{ width: '100%', maxWidth: '460px' }}>
          {/* Logo and Title */}
          <div style={{ textAlign: 'center', marginBottom: '40px' }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              width: '88px', height: '88px',
              background: 'linear-gradient(135deg, #4338ca 0%, #7c3aed 100%)',
              borderRadius: '24px', marginBottom: '24px',
              boxShadow: '0 20px 40px rgba(67,56,202,0.4)'
            }}>
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

          {/* Form Card - DESIGN ORIGINAL */}
          <div style={{
            background: 'rgba(255,255,255,0.95)',
            backdropFilter: 'blur(20px)',
            padding: '32px', borderRadius: '24px',
            boxShadow: '0 25px 50px -12px rgba(0,0,0,0.15)',
            border: 'none'
          }}>
            {error && (
              <div style={{
                background: '#fef2f2', border: '1px solid #fecaca',
                borderRadius: '12px', padding: '16px', marginBottom: '24px',
                color: '#b91c1c', fontSize: '14px'
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
                    onChange={handleChange}
                    placeholder="Mon Entreprise"
                    required
                    style={{
                      width: '100%', height: '48px', fontSize: '16px',
                      padding: '12px 16px', border: '1px solid #d1d5db',
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
                  name="email"
                  value={formData.email}
                  onChange={handleChange}
                  placeholder="votre@email.com"
                  required
                  style={{
                    width: '100%', height: '48px', fontSize: '16px',
                    padding: '12px 16px', border: '1px solid #d1d5db',
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
                    name="password"
                    value={formData.password}
                    onChange={handleChange}
                    placeholder="••••••••••"
                    required
                    style={{
                      width: '100%', height: '48px', fontSize: '16px',
                      padding: '12px 52px 12px 16px', border: '1px solid #d1d5db',
                      borderRadius: '12px', boxSizing: 'border-box'
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    style={{
                      position: 'absolute', right: '12px', top: '50%',
                      transform: 'translateY(-50%)', background: 'none',
                      border: 'none', cursor: 'pointer', color: '#6b7280',
                      fontSize: '20px'
                    }}
                  >
                    {showPassword ? (
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/>
                        <path d="m2 2 20 20"/>
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
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
                    : 'linear-gradient(135deg, #4338ca 0%, #7c3aed 100%)',
                  color: 'white', border: 'none', borderRadius: '12px',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  boxShadow: '0 10px 25px rgba(67,56,202,0.4)'
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

            {/* Forgot Password */}
            {isLogin && (
              <div style={{ marginTop: '16px', textAlign: 'center' }}>
                <button
                  type="button"
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

            <div style={{ marginTop: '24px', textAlign: 'center' }}>
              <button
                type="button"
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

          {!isLogin && (
            <div style={{
              marginTop: '24px', textAlign: 'center',
              fontSize: '14px', color: '#64748b'
            }}>
              En créant un compte, vous acceptez nos{' '}
              <a href="#" style={{ color: '#4338ca', textDecoration: 'none' }}>
                conditions d'utilisation
              </a>{' '}
              et notre{' '}
              <a href="#" style={{ color: '#4338ca', textDecoration: 'none' }}>
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
        `}
      </style>
    </div>
  );
};

// Forgot Password Modal (COMPLET)
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
        setSuccess('Code de récupération généré ! Utilisez-le ci-dessous.');
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
        <button
          onClick={onClose}
          style={{
            position: 'absolute', top: '16px', right: '16px',
            background: 'none', border: 'none', fontSize: '24px',
            cursor: 'pointer', color: '#6b7280'
          }}
        >
          ×
        </button>

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

// Dashboard Page (avec vraies stats)
const Dashboard = () => {
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

  if (stats.loading) {
    return (
      <div style={{ textAlign: 'center', padding: '60px' }}>
        <div style={{ fontSize: '48px', marginBottom: '20px' }}>⏳</div>
        <p style={{ fontSize: '18px', color: '#6b7280' }}>Chargement du tableau de bord...</p>
      </div>
    );
  }

  return (
    <div>
      {/* Welcome Banner */}
      <div style={{
        background: 'linear-gradient(135deg, #4338ca, #7c3aed)',
        color: 'white', padding: '32px', borderRadius: '16px',
        marginBottom: '32px', textAlign: 'center'
      }}>
        <h1 style={{ fontSize: '32px', fontWeight: '800', margin: '0 0 8px 0' }}>
          Bienvenue dans FacturePro ! 🎉
        </h1>
        <p style={{ margin: 0, opacity: 0.9, fontSize: '18px' }}>
          Votre tableau de bord est prêt. Gérez votre entreprise en toute simplicité.
        </p>
      </div>

      {/* Stats Cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
        gap: '24px',
        marginBottom: '32px'
      }}>
        <div style={{
          background: 'linear-gradient(135deg, #3b82f6, #1d4ed8)',
          color: 'white', padding: '28px', borderRadius: '16px',
          textAlign: 'center', position: 'relative', overflow: 'hidden'
        }}>
          <div style={{ fontSize: '48px', marginBottom: '12px' }}>👥</div>
          <div style={{ fontSize: '36px', fontWeight: '800', marginBottom: '4px' }}>
            {stats.data?.total_clients || 0}
          </div>
          <div style={{ fontSize: '14px', opacity: 0.9, fontWeight: '600' }}>Clients</div>
        </div>

        <div style={{
          background: 'linear-gradient(135deg, #10b981, #047857)',
          color: 'white', padding: '28px', borderRadius: '16px',
          textAlign: 'center'
        }}>
          <div style={{ fontSize: '48px', marginBottom: '12px' }}>📄</div>
          <div style={{ fontSize: '36px', fontWeight: '800', marginBottom: '4px' }}>
            {stats.data?.total_invoices || 0}
          </div>
          <div style={{ fontSize: '14px', opacity: 0.9, fontWeight: '600' }}>Factures</div>
        </div>

        <div style={{
          background: 'linear-gradient(135deg, #7c3aed, #5b21b6)',
          color: 'white', padding: '28px', borderRadius: '16px',
          textAlign: 'center'
        }}>
          <div style={{ fontSize: '48px', marginBottom: '12px' }}>📝</div>
          <div style={{ fontSize: '36px', fontWeight: '800', marginBottom: '4px' }}>
            {stats.data?.total_quotes || 0}
          </div>
          <div style={{ fontSize: '14px', opacity: 0.9, fontWeight: '600' }}>Soumissions</div>
        </div>

        <div style={{
          background: 'linear-gradient(135deg, #dc2626, #991b1b)',
          color: 'white', padding: '28px', borderRadius: '16px',
          textAlign: 'center'
        }}>
          <div style={{ fontSize: '48px', marginBottom: '12px' }}>💰</div>
          <div style={{ fontSize: '20px', fontWeight: '800', marginBottom: '4px' }}>
            {formatCurrency(stats.data?.total_revenue || 0)}
          </div>
          <div style={{ fontSize: '14px', opacity: 0.9, fontWeight: '600' }}>Revenus</div>
        </div>
      </div>

      {/* Quick Actions */}
      <div style={{
        background: 'white', border: '1px solid #e2e8f0',
        borderRadius: '16px', padding: '32px'
      }}>
        <h3 style={{ margin: '0 0 24px 0', fontSize: '20px', fontWeight: '700', color: '#1f2937' }}>
          🚀 Actions rapides
        </h3>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '16px'
        }}>
          <QuickActionCard
            icon="👥"
            title="Gérer les clients"
            description="Ajouter, modifier vos clients"
            onClick={() => window.history.pushState({}, '', '/clients')}
          />
          <QuickActionCard
            icon="📄"
            title="Créer une facture"
            description="Nouvelle facture client"
            onClick={() => window.history.pushState({}, '', '/invoices')}
          />
          <QuickActionCard
            icon="📦"
            title="Gérer les produits"
            description="Catalogue de services"
            onClick={() => window.history.pushState({}, '', '/products')}
          />
          <QuickActionCard
            icon="📝"
            title="Créer une soumission"
            description="Devis pour prospect"
            onClick={() => window.history.pushState({}, '', '/quotes')}
          />
        </div>
      </div>
    </div>
  );
};

// Quick Action Card Component
const QuickActionCard = ({ icon, title, description, onClick }) => {
  return (
    <button
      onClick={onClick}
      style={{
        background: '#f8fafc', border: '1px solid #e2e8f0',
        padding: '20px', borderRadius: '12px', cursor: 'pointer',
        textAlign: 'center', transition: 'all 0.3s ease',
        width: '100%'
      }}
      onMouseEnter={(e) => {
        e.target.style.background = '#f1f5f9';
        e.target.style.transform = 'translateY(-2px)';
        e.target.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)';
      }}
      onMouseLeave={(e) => {
        e.target.style.background = '#f8fafc';
        e.target.style.transform = 'translateY(0)';
        e.target.style.boxShadow = 'none';
      }}
    >
      <div style={{ fontSize: '32px', marginBottom: '12px' }}>{icon}</div>
      <div style={{ fontWeight: '600', color: '#374151', fontSize: '16px', marginBottom: '4px' }}>
        {title}
      </div>
      <div style={{ fontSize: '14px', color: '#6b7280' }}>
        {description}
      </div>
    </button>
  );
};

// Clients Page (DESIGN ORIGINAL COMPLET)
const ClientsPage = () => {
  const [clients, setClients] = useState([]);
  const [filteredClients, setFilteredClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingClient, setEditingClient] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [formData, setFormData] = useState({
    name: '', email: '', phone: '', address: '', city: '', postal_code: '', country: ''
  });

  useEffect(() => {
    fetchClients();
  }, []);

  useEffect(() => {
    const filtered = clients.filter(client =>
      client.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      client.email.toLowerCase().includes(searchTerm.toLowerCase())
    );
    setFilteredClients(filtered);
  }, [clients, searchTerm]);

  const fetchClients = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/clients`);
      setClients(response.data);
    } catch (error) {
      setError('Erreur lors du chargement des clients');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    try {
      if (editingClient) {
        await axios.put(`${BACKEND_URL}/api/clients/${editingClient.id}`, formData);
        setSuccess('Client modifié avec succès');
      } else {
        await axios.post(`${BACKEND_URL}/api/clients`, formData);
        setSuccess('Client créé avec succès');
      }
      
      setShowForm(false);
      setEditingClient(null);
      setFormData({ name: '', email: '', phone: '', address: '', city: '', postal_code: '', country: '' });
      fetchClients();
    } catch (error) {
      setError(error.response?.data?.detail || 'Erreur lors de la sauvegarde');
    }
  };

  const handleEdit = (client) => {
    setEditingClient(client);
    setFormData({
      name: client.name,
      email: client.email,
      phone: client.phone || '',
      address: client.address || '',
      city: client.city || '',
      postal_code: client.postal_code || '',
      country: client.country || ''
    });
    setShowForm(true);
  };

  const handleDelete = async (clientId) => {
    if (window.confirm('Êtes-vous sûr de vouloir supprimer ce client ?')) {
      try {
        await axios.delete(`${BACKEND_URL}/api/clients/${clientId}`);
        setSuccess('Client supprimé avec succès');
        fetchClients();
      } catch (error) {
        setError('Erreur lors de la suppression');
      }
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '64px' }}>
        <div style={{ fontSize: '48px', marginBottom: '16px' }}>⏳</div>
        <p style={{ fontSize: '18px', color: '#6b7280' }}>Chargement des clients...</p>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <div style={{ fontSize: '32px', marginRight: '12px' }}>👥</div>
          <div>
            <h1 style={{ fontSize: '32px', fontWeight: '800', color: '#1f2937', margin: 0 }}>Clients</h1>
            <p style={{ color: '#6b7280', margin: 0 }}>Gérez vos clients et leurs informations</p>
          </div>
        </div>
        <button
          onClick={() => setShowForm(true)}
          style={{
            background: 'linear-gradient(135deg, #3b82f6, #1d4ed8)',
            color: 'white', border: 'none', padding: '14px 28px',
            borderRadius: '12px', cursor: 'pointer', fontWeight: '700',
            fontSize: '14px', boxShadow: '0 4px 12px rgba(59,130,246,0.4)'
          }}
        >
          ➕ Nouveau Client
        </button>
      </div>

      {/* Messages */}
      {error && (
        <div style={{
          background: '#fef2f2', border: '1px solid #fecaca',
          color: '#b91c1c', padding: '16px', borderRadius: '12px',
          marginBottom: '20px'
        }}>
          {error}
        </div>
      )}

      {success && (
        <div style={{
          background: '#f0fdf4', border: '1px solid #bbf7d0',
          color: '#166534', padding: '16px', borderRadius: '12px',
          marginBottom: '20px'
        }}>
          {success}
        </div>
      )}

      {/* Search and Stats */}
      <div style={{
        background: 'white', border: '1px solid #e2e8f0',
        borderRadius: '12px', padding: '24px', marginBottom: '24px'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ position: 'relative', flex: 1, maxWidth: '320px' }}>
            <input
              type="text"
              placeholder="Rechercher un client..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{
                width: '100%', padding: '12px 12px 12px 44px',
                border: '1px solid #d1d5db', borderRadius: '8px',
                fontSize: '14px', boxSizing: 'border-box'
              }}
            />
            <div style={{
              position: 'absolute', left: '14px', top: '50%',
              transform: 'translateY(-50%)', color: '#9ca3af', fontSize: '16px'
            }}>🔍</div>
          </div>
          <div style={{ fontSize: '14px', color: '#6b7280' }}>
            {filteredClients.length} client{filteredClients.length > 1 ? 's' : ''}
          </div>
        </div>
      </div>

      {/* Clients List */}
      {filteredClients.length === 0 && !searchTerm ? (
        <div style={{
          background: 'white', border: '2px dashed #d1d5db',
          borderRadius: '16px', padding: '64px', textAlign: 'center'
        }}>
          <div style={{ fontSize: '80px', marginBottom: '24px' }}>👥</div>
          <h3 style={{ fontSize: '24px', fontWeight: '700', color: '#374151', margin: '0 0 12px 0' }}>
            Aucun client enregistré
          </h3>
          <p style={{ color: '#6b7280', fontSize: '16px', margin: '0 0 32px 0' }}>
            Commencez par ajouter votre premier client pour créer des factures
          </p>
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
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '20px' }}>
          {filteredClients.map(client => (
            <div key={client.id} style={{
              background: 'white', border: '1px solid #e5e7eb',
              borderRadius: '12px', padding: '24px',
              boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
              transition: 'all 0.3s ease'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '16px' }}>
                <h3 style={{ fontSize: '18px', fontWeight: '700', color: '#1f2937', margin: 0 }}>
                  {client.name}
                </h3>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    onClick={() => handleEdit(client)}
                    style={{
                      background: '#f0f9ff', color: '#0369a1', border: 'none',
                      padding: '6px 10px', borderRadius: '6px', cursor: 'pointer',
                      fontSize: '12px'
                    }}
                  >
                    ✏️ Modifier
                  </button>
                  <button
                    onClick={() => handleDelete(client.id)}
                    style={{
                      background: '#fef2f2', color: '#dc2626', border: 'none',
                      padding: '6px 10px', borderRadius: '6px', cursor: 'pointer',
                      fontSize: '12px'
                    }}
                  >
                    🗑️ Supprimer
                  </button>
                </div>
              </div>
              
              <div style={{ fontSize: '14px', color: '#6b7280', lineHeight: '1.6' }}>
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: '6px' }}>
                  <span style={{ marginRight: '8px' }}>📧</span>
                  {client.email}
                </div>
                {client.phone && (
                  <div style={{ display: 'flex', alignItems: 'center', marginBottom: '6px' }}>
                    <span style={{ marginRight: '8px' }}>📱</span>
                    {client.phone}
                  </div>
                )}
                {client.address && (
                  <div style={{ display: 'flex', alignItems: 'center', marginBottom: '6px' }}>
                    <span style={{ marginRight: '8px' }}>📍</span>
                    {client.address}
                  </div>
                )}
                {client.city && (
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    <span style={{ marginRight: '8px' }}>🏙️</span>
                    {client.city} {client.postal_code}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {filteredClients.length === 0 && searchTerm && (
        <div style={{
          background: 'white', border: '1px solid #e2e8f0',
          borderRadius: '12px', padding: '40px', textAlign: 'center'
        }}>
          <div style={{ fontSize: '64px', marginBottom: '16px' }}>🔍</div>
          <h3 style={{ color: '#374151', margin: '0 0 8px 0' }}>Aucun client trouvé</h3>
          <p style={{ color: '#6b7280', margin: 0 }}>Aucun client ne correspond à votre recherche "{searchTerm}"</p>
        </div>
      )}

      {/* Client Form Modal - DESIGN ORIGINAL */}
      {showForm && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0, 0, 0, 0.6)', display: 'flex', alignItems: 'center',
          justifyContent: 'center', zIndex: 50, padding: '16px'
        }}>
          <div style={{
            background: 'white', borderRadius: '16px',
            maxWidth: '600px', width: '100%', maxHeight: '90vh', overflow: 'auto'
          }}>
            <div style={{
              padding: '24px 24px 0 24px', borderBottom: '1px solid #e5e7eb',
              marginBottom: '24px'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={{
                  fontSize: '20px', fontWeight: '700', color: '#1f2937', margin: 0
                }}>
                  {editingClient ? 'Modifier le client' : 'Nouveau Client'}
                </h3>
                <button
                  onClick={() => {
                    setShowForm(false);
                    setEditingClient(null);
                    setFormData({ name: '', email: '', phone: '', address: '', city: '', postal_code: '', country: '' });
                  }}
                  style={{
                    background: 'none', border: 'none', fontSize: '24px',
                    cursor: 'pointer', color: '#6b7280'
                  }}
                >
                  ✕
                </button>
              </div>
            </div>
            
            <div style={{ padding: '0 24px 24px 24px' }}>
              <form onSubmit={handleSubmit}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: '#374151', marginBottom: '6px' }}>
                      Nom complet *
                    </label>
                    <input
                      type="text"
                      value={formData.name}
                      onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                      placeholder="Jean Dupont"
                      required
                      style={{
                        width: '100%', padding: '12px', border: '1px solid #d1d5db',
                        borderRadius: '8px', fontSize: '16px', boxSizing: 'border-box'
                      }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: '#374151', marginBottom: '6px' }}>
                      Adresse email *
                    </label>
                    <input
                      type="email"
                      value={formData.email}
                      onChange={(e) => setFormData(prev => ({ ...prev, email: e.target.value }))}
                      placeholder="jean@entreprise.com"
                      required
                      style={{
                        width: '100%', padding: '12px', border: '1px solid #d1d5db',
                        borderRadius: '8px', fontSize: '16px', boxSizing: 'border-box'
                      }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: '#374151', marginBottom: '6px' }}>
                      Téléphone
                    </label>
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
                    <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: '#374151', marginBottom: '6px' }}>
                      Ville
                    </label>
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
                </div>
                
                <div style={{ marginBottom: '24px' }}>
                  <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: '#374151', marginBottom: '6px' }}>
                    Adresse complète
                  </label>
                  <input
                    type="text"
                    value={formData.address}
                    onChange={(e) => setFormData(prev => ({ ...prev, address: e.target.value }))}
                    placeholder="123 Rue Example, App 456"
                    style={{
                      width: '100%', padding: '12px', border: '1px solid #d1d5db',
                      borderRadius: '8px', fontSize: '16px', boxSizing: 'border-box'
                    }}
                  />
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', paddingTop: '16px', borderTop: '1px solid #e5e7eb' }}>
                  <button
                    type="button"
                    onClick={() => {
                      setShowForm(false);
                      setEditingClient(null);
                      setFormData({ name: '', email: '', phone: '', address: '', city: '', postal_code: '', country: '' });
                    }}
                    style={{
                      background: 'white', color: '#374151', border: '1px solid #d1d5db',
                      padding: '12px 24px', borderRadius: '8px', cursor: 'pointer',
                      fontSize: '14px', fontWeight: '500'
                    }}
                  >
                    Annuler
                  </button>
                  <button
                    type="submit"
                    style={{
                      background: 'linear-gradient(135deg, #3b82f6, #1d4ed8)', color: 'white',
                      border: 'none', padding: '12px 24px', borderRadius: '8px',
                      cursor: 'pointer', fontWeight: '600', fontSize: '14px'
                    }}
                  >
                    {editingClient ? 'Modifier le client' : 'Créer le client'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// Pages placeholders (seront développées)
// Products Page (FONCTIONNELLE COMPLETE)
const ProductsPage = () => {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [formData, setFormData] = useState({
    name: '', description: '', unit_price: '', unit: 'unité', category: ''
  });

  useEffect(() => {
    fetchProducts();
  }, []);

  const fetchProducts = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/products`);
      setProducts(response.data);
    } catch (error) {
      setError('Erreur lors du chargement des produits');
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(''); setSuccess('');

    try {
      await axios.post(`${BACKEND_URL}/api/products`, {
        ...formData,
        unit_price: parseFloat(formData.unit_price)
      });
      
      setSuccess('Produit créé avec succès');
      setShowForm(false);
      setFormData({ name: '', description: '', unit_price: '', unit: 'unité', category: '' });
      fetchProducts();
    } catch (error) {
      setError('Erreur lors de la création du produit');
    }
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('fr-CA', {
      style: 'currency',
      currency: 'CAD'
    }).format(amount || 0);
  };

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <div style={{ fontSize: '32px', marginRight: '12px' }}>📦</div>
          <div>
            <h1 style={{ fontSize: '32px', fontWeight: '800', color: '#1f2937', margin: 0 }}>Produits & Services</h1>
            <p style={{ color: '#6b7280', margin: 0 }}>Gérez votre catalogue de produits et services</p>
          </div>
        </div>
        <button
          onClick={() => setShowForm(true)}
          style={{
            background: 'linear-gradient(135deg, #10b981, #047857)',
            color: 'white', border: 'none', padding: '14px 28px',
            borderRadius: '12px', cursor: 'pointer', fontWeight: '700',
            fontSize: '14px', boxShadow: '0 4px 12px rgba(16,185,129,0.4)'
          }}
        >
          ➕ Nouveau Produit
        </button>
      </div>

      {/* Messages */}
      {error && (
        <div style={{
          background: '#fef2f2', border: '1px solid #fecaca',
          color: '#b91c1c', padding: '16px', borderRadius: '12px', marginBottom: '20px'
        }}>
          {error}
        </div>
      )}
      {success && (
        <div style={{
          background: '#f0fdf4', border: '1px solid #bbf7d0',
          color: '#166534', padding: '16px', borderRadius: '12px', marginBottom: '20px'
        }}>
          {success}
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px' }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>⏳</div>
          <p>Chargement des produits...</p>
        </div>
      ) : products.length === 0 ? (
        <div style={{
          background: 'white', border: '2px dashed #d1d5db',
          borderRadius: '16px', padding: '64px', textAlign: 'center'
        }}>
          <div style={{ fontSize: '80px', marginBottom: '24px' }}>📦</div>
          <h3 style={{ fontSize: '24px', fontWeight: '700', color: '#374151', margin: '0 0 12px 0' }}>
            Aucun produit créé
          </h3>
          <p style={{ color: '#6b7280', fontSize: '16px', margin: '0 0 32px 0' }}>
            Créez vos produits et services pour faciliter la facturation
          </p>
          <button
            onClick={() => setShowForm(true)}
            style={{
              background: '#10b981', color: 'white', border: 'none',
              padding: '16px 32px', borderRadius: '12px', cursor: 'pointer',
              fontWeight: '700', fontSize: '16px'
            }}
          >
            🚀 Créer mon premier produit
          </button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '20px' }}>
          {products.map(product => (
            <div key={product.id} style={{
              background: 'white', border: '1px solid #e5e7eb',
              borderRadius: '12px', padding: '24px',
              boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
                <h3 style={{ fontSize: '18px', fontWeight: '700', color: '#1f2937', margin: 0 }}>
                  {product.name}
                </h3>
                {product.category && (
                  <span style={{
                    background: '#f3f4f6', color: '#374151',
                    padding: '4px 8px', borderRadius: '6px', fontSize: '12px'
                  }}>
                    {product.category}
                  </span>
                )}
              </div>
              
              <p style={{ color: '#6b7280', fontSize: '14px', marginBottom: '16px' }}>
                {product.description}
              </p>
              
              <div style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                paddingTop: '16px', borderTop: '1px solid #e5e7eb'
              }}>
                <div>
                  <div style={{ fontSize: '20px', fontWeight: '800', color: '#10b981' }}>
                    {formatCurrency(product.unit_price)}
                  </div>
                  <div style={{ fontSize: '12px', color: '#6b7280' }}>
                    par {product.unit}
                  </div>
                </div>
                
                <button
                  onClick={async () => {
                    if (window.confirm('Supprimer ce produit ?')) {
                      try {
                        await axios.delete(`${BACKEND_URL}/api/products/${product.id}`);
                        setSuccess('Produit supprimé');
                        fetchProducts();
                      } catch (error) {
                        setError('Erreur suppression');
                      }
                    }
                  }}
                  style={{
                    background: '#fef2f2', color: '#dc2626', border: 'none',
                    padding: '8px 12px', borderRadius: '6px', cursor: 'pointer',
                    fontSize: '12px'
                  }}
                >
                  🗑️ Supprimer
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Product Form Modal */}
      {showForm && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center',
          justifyContent: 'center', zIndex: 1000, padding: '20px'
        }}>
          <div style={{
            background: 'white', padding: '32px', borderRadius: '16px',
            width: '100%', maxWidth: '500px'
          }}>
            <h3 style={{ margin: '0 0 24px 0', fontSize: '20px', fontWeight: '700' }}>
              📦 Nouveau Produit/Service
            </h3>
            
            <form onSubmit={handleSubmit}>
              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Nom *</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                  required
                  placeholder="Consultation, Kilométrage, Formation..."
                  style={{
                    width: '100%', padding: '12px', border: '1px solid #ddd',
                    borderRadius: '8px', boxSizing: 'border-box'
                  }}
                />
              </div>

              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Description</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                  rows={3}
                  placeholder="Description détaillée du service ou produit..."
                  style={{
                    width: '100%', padding: '12px', border: '1px solid #ddd',
                    borderRadius: '8px', resize: 'vertical', boxSizing: 'border-box'
                  }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px', marginBottom: '24px' }}>
                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Prix (CAD) *</label>
                  <input
                    type="number"
                    step="0.01"
                    value={formData.unit_price}
                    onChange={(e) => setFormData(prev => ({ ...prev, unit_price: e.target.value }))}
                    required
                    style={{
                      width: '100%', padding: '12px', border: '1px solid #ddd',
                      borderRadius: '8px', boxSizing: 'border-box'
                    }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Unité</label>
                  <select
                    value={formData.unit}
                    onChange={(e) => setFormData(prev => ({ ...prev, unit: e.target.value }))}
                    style={{
                      width: '100%', padding: '12px', border: '1px solid #ddd',
                      borderRadius: '8px', boxSizing: 'border-box'
                    }}
                  >
                    <option value="unité">Unité</option>
                    <option value="heure">Heure</option>
                    <option value="km">Kilomètre</option>
                    <option value="jour">Jour</option>
                    <option value="mois">Mois</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Catégorie</label>
                  <input
                    type="text"
                    value={formData.category}
                    onChange={(e) => setFormData(prev => ({ ...prev, category: e.target.value }))}
                    placeholder="Services, Transport..."
                    style={{
                      width: '100%', padding: '12px', border: '1px solid #ddd',
                      borderRadius: '8px', boxSizing: 'border-box'
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
                    background: '#10b981', color: 'white', border: 'none',
                    padding: '12px 24px', borderRadius: '8px', cursor: 'pointer',
                    fontWeight: '600'
                  }}
                >
                  💾 Créer le produit
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

const InvoicesPage = () => (
  <div style={{ textAlign: 'center', padding: '60px' }}>
    <div style={{ fontSize: '80px', marginBottom: '24px' }}>📄</div>
    <h2 style={{ fontSize: '28px', margin: '0 0 16px 0' }}>Factures</h2>
    <p style={{ color: '#6b7280', fontSize: '18px' }}>Créez et gérez vos factures clients</p>
  </div>
);

const QuotesPage = () => (
  <div style={{ textAlign: 'center', padding: '60px' }}>
    <div style={{ fontSize: '80px', marginBottom: '24px' }}>📝</div>
    <h2 style={{ fontSize: '28px', margin: '0 0 16px 0' }}>Soumissions</h2>
    <p style={{ color: '#6b7280', fontSize: '18px' }}>Créez des devis et soumissions</p>
  </div>
);

const EmployeesPage = () => (
  <div style={{ textAlign: 'center', padding: '60px' }}>
    <div style={{ fontSize: '80px', marginBottom: '24px' }}>👨‍💼</div>
    <h2 style={{ fontSize: '28px', margin: '0 0 16px 0' }}>Employés</h2>
    <p style={{ color: '#6b7280', fontSize: '18px' }}>Gérez vos employés et leurs informations</p>
  </div>
);

const ExpensesPage = () => (
  <div style={{ textAlign: 'center', padding: '60px' }}>
    <div style={{ fontSize: '80px', marginBottom: '24px' }}>💳</div>
    <h2 style={{ fontSize: '28px', margin: '0 0 16px 0' }}>Dépenses</h2>
    <p style={{ color: '#6b7280', fontSize: '18px' }}>Système de dépenses et remboursements</p>
  </div>
);

const SettingsPage = () => (
  <div style={{ textAlign: 'center', padding: '60px' }}>
    <div style={{ fontSize: '80px', marginBottom: '24px' }}>⚙️</div>
    <h2 style={{ fontSize: '28px', margin: '0 0 16px 0' }}>Paramètres</h2>
    <p style={{ color: '#6b7280', fontSize: '18px' }}>Configuration de votre entreprise</p>
  </div>
);

const ExportPage = () => (
  <div style={{ textAlign: 'center', padding: '60px' }}>
    <div style={{ fontSize: '80px', marginBottom: '24px' }}>📊</div>
    <h2 style={{ fontSize: '28px', margin: '0 0 16px 0' }}>Exports</h2>
    <p style={{ color: '#6b7280', fontSize: '18px' }}>Exportez vos données en PDF, Excel, CSV</p>
  </div>
);

// Main App with Provider
function AppWithAuth() {
  return (
    <AuthProvider>
      <App />
    </AuthProvider>
  );
}

export default AppWithAuth;