import React, { useState, createContext, useContext, useEffect } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'https://facturepro-api.onrender.com';

// Configure axios to always send token
axios.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

//Auth Context
const AuthContext = createContext();
export const useAuth = () => useContext(AuthContext);

// Notifications Dropdown Component
const NotificationsDropdown = ({ isOpen, onClose }) => {
  const notifications = [
    { id: 1, type: 'info', message: 'Bienvenue dans FacturePro !', time: 'Il y a 2 minutes' },
    { id: 2, type: 'success', message: 'Application déployée avec succès', time: 'Il y a 1 heure' },
    { id: 3, type: 'warning', message: 'Pensez à configurer vos numéros de taxes', time: 'Il y a 2 heures' }
  ];

  if (!isOpen) return null;

  return (
    <div style={{
      position: 'absolute',
      top: '100%',
      right: 0,
      background: 'white',
      border: '1px solid #e5e7eb',
      borderRadius: '12px',
      boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)',
      width: '320px',
      zIndex: 50,
      marginTop: '8px'
    }}>
      <div style={{
        padding: '16px',
        borderBottom: '1px solid #e5e7eb'
      }}>
        <h3 style={{
          fontSize: '16px',
          fontWeight: '700',
          color: '#1f2937',
          margin: 0
        }}>
          🔔 Notifications
        </h3>
      </div>
      
      <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
        {notifications.map(notification => (
          <div key={notification.id} style={{
            padding: '16px',
            borderBottom: '1px solid #f3f4f6'
          }}>
            <div style={{
              display: 'flex',
              alignItems: 'start',
              gap: '12px'
            }}>
              <div style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                background: notification.type === 'success' ? '#10b981' : 
                          notification.type === 'warning' ? '#f59e0b' : '#3b82f6',
                marginTop: '6px'
              }}></div>
              <div style={{ flex: 1 }}>
                <p style={{
                  fontSize: '14px',
                  color: '#374151',
                  margin: '0 0 4px 0',
                  fontWeight: '500'
                }}>
                  {notification.message}
                </p>
                <p style={{
                  fontSize: '12px',
                  color: '#6b7280',
                  margin: 0
                }}>
                  {notification.time}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>
      
      <div style={{
        padding: '12px 16px',
        textAlign: 'center',
        borderTop: '1px solid #e5e7eb'
      }}>
        <button
          onClick={onClose}
          style={{
            background: 'none',
            border: 'none',
            color: '#6b7280',
            fontSize: '14px',
            cursor: 'pointer'
          }}
        >
          Fermer
        </button>
      </div>
    </div>
  );
};

// Auth Provider
const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(() => {
    const savedUser = localStorage.getItem('user');
    return savedUser ? JSON.parse(savedUser) : null;
  });
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const initAuth = async () => {
      if (token) {
        try {
          axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
          // Load user from localStorage if not loaded
          if (!user) {
            const savedUser = localStorage.getItem('user');
            if (savedUser) {
              setUser(JSON.parse(savedUser));
            }
          }
        } catch (error) {
          localStorage.removeItem('token');
          localStorage.removeItem('user');
          setToken(null);
          setUser(null);
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
      localStorage.setItem('user', JSON.stringify(userData));
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
      localStorage.setItem('user', JSON.stringify(userData));
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
    localStorage.removeItem('user');
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

// Public Quote Acceptance Page
const AcceptQuotePage = ({ token }) => {
  const [loading, setLoading] = useState(true);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');
  const [quoteData, setQuoteData] = useState(null);

  useEffect(() => {
    acceptQuote();
  }, [token]);

  const acceptQuote = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/quotes/accept/${token}`);
      setQuoteData(response.data);
      setSuccess(true);
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur lors de l\'acceptation de la soumission');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(to-br, #f0fdfa, #ccfbf1, #99f6e4)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '20px',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
    }}>
      <div style={{
        background: 'white',
        borderRadius: '16px',
        boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25)',
        maxWidth: '600px',
        width: '100%',
        overflow: 'hidden'
      }}>
        {loading ? (
          <div style={{ padding: '60px', textAlign: 'center' }}>
            <div style={{
              width: '60px',
              height: '60px',
              border: '4px solid #e5e7eb',
              borderTop: '4px solid #0d9488',
              borderRadius: '50%',
              animation: 'spin 1s linear infinite',
              margin: '0 auto 20px'
            }}></div>
            <p style={{ color: '#6b7280', fontSize: '16px' }}>Traitement en cours...</p>
          </div>
        ) : success ? (
          <>
            <div style={{
              background: 'linear-gradient(135deg, #10b981, #059669)',
              padding: '40px',
              textAlign: 'center'
            }}>
              <div style={{
                width: '80px',
                height: '80px',
                background: 'white',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 20px',
                fontSize: '40px'
              }}>
                ✅
              </div>
              <h1 style={{ color: 'white', margin: '0 0 10px 0', fontSize: '28px' }}>
                Soumission Acceptée !
              </h1>
              <p style={{ color: 'rgba(255,255,255,0.9)', margin: 0, fontSize: '16px' }}>
                Merci pour votre confirmation
              </p>
            </div>
            <div style={{ padding: '40px' }}>
              <div style={{
                background: '#f0fdf4',
                border: '2px solid #10b981',
                borderRadius: '12px',
                padding: '24px',
                marginBottom: '24px'
              }}>
                <p style={{ margin: '0 0 12px 0', color: '#166534', fontWeight: '600', fontSize: '16px' }}>
                  Détails de la soumission :
                </p>
                <p style={{ margin: '8px 0', color: '#374151' }}>
                  <strong>Numéro:</strong> {quoteData?.quote_number}
                </p>
                <p style={{ margin: '8px 0', color: '#374151' }}>
                  <strong>Client:</strong> {quoteData?.client_name}
                </p>
              </div>
              <p style={{ color: '#6b7280', fontSize: '14px', lineHeight: '1.6', marginBottom: '24px' }}>
                Un email de confirmation a été envoyé à l'entreprise. Vous serez contacté prochainement pour les prochaines étapes.
              </p>
              <div style={{
                padding: '16px',
                background: '#f0fdfa',
                borderRadius: '8px',
                border: '1px solid #5eead4'
              }}>
                <p style={{ margin: 0, color: '#0f766e', fontSize: '14px' }}>
                  💡 Vous pouvez fermer cette page en toute sécurité.
                </p>
              </div>
            </div>
          </>
        ) : (
          <>
            <div style={{
              background: 'linear-gradient(135deg, #ef4444, #dc2626)',
              padding: '40px',
              textAlign: 'center'
            }}>
              <div style={{
                width: '80px',
                height: '80px',
                background: 'white',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 20px',
                fontSize: '40px'
              }}>
                ❌
              </div>
              <h1 style={{ color: 'white', margin: '0 0 10px 0', fontSize: '28px' }}>
                Erreur
              </h1>
            </div>
            <div style={{ padding: '40px' }}>
              <div style={{
                background: '#fef2f2',
                border: '2px solid #ef4444',
                borderRadius: '12px',
                padding: '24px',
                marginBottom: '24px'
              }}>
                <p style={{ margin: 0, color: '#991b1b', fontSize: '16px' }}>
                  {error}
                </p>
              </div>
              <p style={{ color: '#6b7280', fontSize: '14px' }}>
                Si le problème persiste, veuillez contacter l'entreprise directement.
              </p>
            </div>
          </>
        )}
      </div>
      
      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
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

  // Handle public routes (no authentication required)
  if (currentRoute.startsWith('/accept-quote/')) {
    const token = currentRoute.split('/accept-quote/')[1];
    return <AcceptQuotePage token={token} />;
  }

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
      case '/change-password':
        return <ChangePasswordPage />;
      case '/billing':
        return <BillingPage />;
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
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
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
        background: 'linear-gradient(180deg, #0f766e 0%, #0d9488 100%)',
        boxShadow: '4px 0 6px -1px rgba(0, 0, 0, 0.1)'
      }}>
        {/* Logo Section */}
        <div style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '48px', height: '48px',
              background: 'transparent',
              borderRadius: '12px',
              display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}>
              <img 
                src="https://customer-assets.emergentagent.com/job_62508191-52e7-42df-afe2-c04e90de23a9/artifacts/ey3nqz8l_2c256145-633e-411d-9781-dce2201c8da3_wm.jpeg" 
                alt="FacturePro Logo" 
                style={{
                  width: '48px', height: '48px',
                  objectFit: 'contain', borderRadius: '12px'
                }}
              />
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
                    ? 'rgba(20, 184, 166, 0.25)' 
                    : 'transparent',
                  color: item.current ? '#5eead4' : '#cbd5e1',
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
              <div style={{ position: 'relative' }}>
                <button 
                  onClick={() => setNotificationsOpen(!notificationsOpen)}
                  style={{
                    position: 'relative',
                    background: 'none',
                    border: 'none',
                    padding: '8px',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    color: '#6b7280',
                    fontSize: '18px'
                  }}
                >
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

                <NotificationsDropdown
                  isOpen={notificationsOpen}
                  onClose={() => setNotificationsOpen(false)}
                />
              </div>

              {/* User Avatar with Dropdown */}
              <div style={{ position: 'relative' }}>
                <button
                  onClick={() => setUserMenuOpen(!userMenuOpen)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '8px 12px',
                    borderRadius: '8px',
                    background: '#f8fafc',
                    border: '1px solid #e2e8f0',
                    cursor: 'pointer'
                  }}
                >
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
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6b7280" strokeWidth="2">
                    <polyline points="6 9 12 15 18 9"></polyline>
                  </svg>
                </button>

                {/* Dropdown Menu */}
                {userMenuOpen && (
                  <div style={{
                    position: 'absolute',
                    top: '100%',
                    right: 0,
                    marginTop: '8px',
                    width: '220px',
                    background: 'white',
                    border: '1px solid #e2e8f0',
                    borderRadius: '8px',
                    boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
                    zIndex: 50
                  }}>
                    <button
                      onClick={() => {
                        setUserMenuOpen(false);
                        navigate('/change-password');
                      }}
                      style={{
                        width: '100%',
                        padding: '12px 16px',
                        textAlign: 'left',
                        background: 'white',
                        border: 'none',
                        borderBottom: '1px solid #e2e8f0',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px'
                      }}
                      onMouseOver={(e) => e.currentTarget.style.background = '#f9fafb'}
                      onMouseOut={(e) => e.currentTarget.style.background = 'white'}
                    >
                      🔒 Changer le mot de passe
                    </button>
                    <button
                      onClick={() => {
                        setUserMenuOpen(false);
                        navigate('/billing');
                      }}
                      style={{
                        width: '100%',
                        padding: '12px 16px',
                        textAlign: 'left',
                        background: 'white',
                        border: 'none',
                        borderBottom: '1px solid #e2e8f0',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px'
                      }}
                      onMouseOver={(e) => e.currentTarget.style.background = '#f9fafb'}
                      onMouseOut={(e) => e.currentTarget.style.background = 'white'}
                    >
                      💳 Facturation
                    </button>
                    <button
                      onClick={() => {
                        setUserMenuOpen(false);
                        logout();
                      }}
                      style={{
                        width: '100%',
                        padding: '12px 16px',
                        textAlign: 'left',
                        background: 'white',
                        border: 'none',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px',
                        color: '#ef4444',
                        borderRadius: '0 0 8px 8px'
                      }}
                      onMouseOver={(e) => e.currentTarget.style.background = '#fef2f2'}
                      onMouseOut={(e) => e.currentTarget.style.background = 'white'}
                    >
                      🚪 Déconnexion
                    </button>
                  </div>
                )}
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
      background: 'linear-gradient(to-br, #f0fdfa, #ccfbf1, #99f6e4)',
      display: 'flex',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
    }}>
      {/* Left Hero Section - DESIGN ORIGINAL */}
      <div style={{
        width: '50%',
        background: 'linear-gradient(135deg, #0d9488, #06b6d4)',
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
          background: 'rgba(34,211,238,0.2)',
          borderRadius: '50%', filter: 'blur(48px)'
        }}></div>
        
        <div style={{ position: 'relative', zIndex: 10, color: 'white' }}>
          <div style={{ marginBottom: '32px' }}>
            {/* FacturePro Logo */}
            <img 
              src="https://customer-assets.emergentagent.com/job_62508191-52e7-42df-afe2-c04e90de23a9/artifacts/ey3nqz8l_2c256145-633e-411d-9781-dce2201c8da3_wm.jpeg"
              alt="FacturePro Logo"
              style={{
                width: '64px',
                height: '64px',
                marginBottom: '24px',
                borderRadius: '12px'
              }}
            />
            <h1 style={{
              fontSize: '80px', fontWeight: 'bold', marginBottom: '16px',
              lineHeight: '1.1', margin: 0
            }}>
              Simplifiez votre
              <span style={{ display: 'block', color: '#a5f3fc' }}>facturation</span>
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
              background: 'linear-gradient(135deg, #14b8a6 0%, #06b6d4 100%)',
              borderRadius: '24px', marginBottom: '24px',
              boxShadow: '0 20px 40px rgba(20, 184, 166, 0.4)'
            }}>
              <img 
                src="https://customer-assets.emergentagent.com/job_62508191-52e7-42df-afe2-c04e90de23a9/artifacts/ey3nqz8l_2c256145-633e-411d-9781-dce2201c8da3_wm.jpeg"
                alt="FacturePro Logo"
                style={{
                  width: '56px',
                  height: '56px',
                  borderRadius: '12px'
                }}
              />
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
                    : 'linear-gradient(135deg, #0d9488 0%, #06b6d4 100%)',
                  color: 'white', border: 'none', borderRadius: '12px',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  boxShadow: '0 10px 25px rgba(13,148,136,0.4)'
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
                    background: 'none', border: 'none', color: '#0d9488',
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
                  background: 'none', border: 'none', color: '#0d9488',
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
              <a href="#" style={{ color: '#0d9488', textDecoration: 'none' }}>
                conditions d'utilisation
              </a>{' '}
              et notre{' '}
              <a href="#" style={{ color: '#0d9488', textDecoration: 'none' }}>
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
  const [editingProduct, setEditingProduct] = useState(null);
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
      if (editingProduct) {
        // Update existing product
        await axios.put(`${BACKEND_URL}/api/products/${editingProduct.id}`, {
          ...formData,
          unit_price: parseFloat(formData.unit_price)
        });
        setSuccess('Produit modifié avec succès');
      } else {
        // Create new product
        await axios.post(`${BACKEND_URL}/api/products`, {
          ...formData,
          unit_price: parseFloat(formData.unit_price)
        });
        setSuccess('Produit créé avec succès');
      }
      
      setShowForm(false);
      setEditingProduct(null);
      setFormData({ name: '', description: '', unit_price: '', unit: 'unité', category: '' });
      fetchProducts();
    } catch (error) {
      setError(editingProduct ? 'Erreur lors de la modification' : 'Erreur lors de la création du produit');
    }
  };

  const handleEdit = (product) => {
    setEditingProduct(product);
    setFormData({
      name: product.name,
      description: product.description || '',
      unit_price: product.unit_price,
      unit: product.unit,
      category: product.category || ''
    });
    setShowForm(true);
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
                
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    onClick={() => handleEdit(product)}
                    style={{
                      background: '#ede9fe', color: '#7c3aed', border: 'none',
                      padding: '8px 12px', borderRadius: '6px', cursor: 'pointer',
                      fontSize: '12px', fontWeight: '600'
                    }}
                  >
                    ✏️ Modifier
                  </button>
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
                      fontSize: '12px', fontWeight: '600'
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
              {editingProduct ? '✏️ Modifier Produit/Service' : '📦 Nouveau Produit/Service'}
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

const InvoicesPage = () => {
  const [invoices, setInvoices] = useState([]);
  const [clients, setClients] = useState([]);
  const [products, setProducts] = useState([]);
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingInvoice, setEditingInvoice] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  const [formData, setFormData] = useState({
    client_id: '',
    issue_date: new Date().toISOString().split('T')[0],
    due_date: new Date(Date.now() + 30*24*60*60*1000).toISOString().split('T')[0],
    items: [{ product_id: '', description: '', quantity: 1, unit_price: 0, tax_rate: 14.975 }],
    tax_type: 'TPSTVQ', // TPSTVQ or HST
    discount: 0,
    notes: 'Paiement dû à réception de la facture.\nMerci de votre confiance !',
    primary_color: '#3b82f6'
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [invoicesRes, clientsRes, productsRes, settingsRes] = await Promise.all([
        axios.get(`${BACKEND_URL}/api/invoices`),
        axios.get(`${BACKEND_URL}/api/clients`),
        axios.get(`${BACKEND_URL}/api/products`),
        axios.get(`${BACKEND_URL}/api/settings/company`)
      ]);
      setInvoices(invoicesRes.data);
      setClients(clientsRes.data);
      setProducts(productsRes.data);
      setSettings(settingsRes.data);
      
      // Set default color from settings
      if (settingsRes.data?.primary_color) {
        setFormData(prev => ({ ...prev, primary_color: settingsRes.data.primary_color }));
      }
    } catch (error) {
      console.error('Error fetching data:', error);
      setError('Erreur lors du chargement des données');
    } finally {
      setLoading(false);
    }
  };

  const openModal = (invoice = null) => {
    if (invoice) {
      setEditingInvoice(invoice);
      setFormData({
        client_id: invoice.client_id,
        issue_date: invoice.issue_date?.split('T')[0] || new Date().toISOString().split('T')[0],
        due_date: invoice.due_date?.split('T')[0] || new Date(Date.now() + 30*24*60*60*1000).toISOString().split('T')[0],
        items: invoice.items,
        tax_type: invoice.tax_type || 'TPSTVQ',
        discount: invoice.discount || 0,
        notes: invoice.notes || '',
        primary_color: invoice.primary_color || settings?.primary_color || '#3b82f6'
      });
    } else {
      setEditingInvoice(null);
      setFormData({
        client_id: '',
        issue_date: new Date().toISOString().split('T')[0],
        due_date: new Date(Date.now() + 30*24*60*60*1000).toISOString().split('T')[0],
        items: [{ product_id: '', description: '', quantity: 1, unit_price: 0, tax_rate: 14.975 }],
        tax_type: 'TPSTVQ',
        discount: 0,
        notes: 'Paiement dû à réception de la facture.\nMerci de votre confiance !',
        primary_color: settings?.primary_color || '#3b82f6'
      });
    }
    setShowModal(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    try {
      const selectedClient = clients.find(c => c.id === formData.client_id);
      if (!selectedClient) {
        setError('Veuillez sélectionner un client');
        return;
      }

      const invoiceData = {
        ...formData,
        client_name: selectedClient.name,
        client_email: selectedClient.email,
        client_address: `${selectedClient.address || ''}, ${selectedClient.city || ''} ${selectedClient.postal_code || ''}`.trim()
      };

      if (editingInvoice) {
        await axios.put(`${BACKEND_URL}/api/invoices/${editingInvoice.id}`, invoiceData);
        setSuccess('Facture modifiée avec succès');
      } else {
        await axios.post(`${BACKEND_URL}/api/invoices`, invoiceData);
        setSuccess('Facture créée avec succès');
      }
      
      setShowModal(false);
      fetchData();
    } catch (error) {
      console.error('Error saving invoice:', error);
      setError(error.response?.data?.detail || 'Erreur lors de la sauvegarde');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Êtes-vous sûr de vouloir supprimer cette facture ?')) return;
    
    try {
      await axios.delete(`${BACKEND_URL}/api/invoices/${id}`);
      setSuccess('Facture supprimée');
      fetchData();
    } catch (error) {
      setError('Erreur lors de la suppression');
    }
  };

  const handleSendEmail = async (id) => {
    try {
      await axios.post(`${BACKEND_URL}/api/invoices/${id}/send-email`);
      setSuccess('Facture envoyée par email');
      fetchData();
    } catch (error) {
      setError('Erreur lors de l\'envoi de l\'email');
    }
  };

  const addItem = () => {
    setFormData(prev => ({
      ...prev,
      items: [...prev.items, { product_id: '', description: '', quantity: 1, unit_price: 0, tax_rate: prev.tax_type === 'TPSTVQ' ? 14.975 : 13 }]
    }));
  };

  const removeItem = (index) => {
    if (formData.items.length > 1) {
      setFormData(prev => ({
        ...prev,
        items: prev.items.filter((_, i) => i !== index)
      }));
    }
  };

  const updateItem = (index, field, value) => {
    const newItems = [...formData.items];
    
    if (field === 'product_id' && value) {
      const product = products.find(p => p.id === value);
      if (product) {
        newItems[index] = {
          ...newItems[index],
          product_id: value,
          description: product.name,
          unit_price: product.price
        };
      }
    } else {
      newItems[index] = { ...newItems[index], [field]: value };
    }
    
    setFormData(prev => ({ ...prev, items: newItems }));
  };

  const updateTaxType = (type) => {
    const rate = type === 'TPSTVQ' ? 14.975 : 13;
    setFormData(prev => ({
      ...prev,
      tax_type: type,
      items: prev.items.map(item => ({ ...item, tax_rate: rate }))
    }));
  };

  const calculateTotals = () => {
    const subtotal = formData.items.reduce((sum, item) => sum + (item.quantity * item.unit_price), 0);
    const taxTotal = formData.items.reduce((sum, item) => sum + (item.quantity * item.unit_price * item.tax_rate / 100), 0);
    const total = subtotal + taxTotal - (formData.discount || 0);
    return { subtotal, taxTotal, total };
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('fr-CA', { style: 'currency', currency: 'CAD' }).format(amount || 0);
  };

  const getStatusBadge = (status) => {
    const styles = {
      draft: { bg: '#f3f4f6', color: '#374151', text: 'Brouillon' },
      sent: { bg: '#dbeafe', color: '#1e40af', text: 'Envoyée' },
      paid: { bg: '#dcfce7', color: '#166534', text: 'Payée' },
      overdue: { bg: '#fee2e2', color: '#991b1b', text: 'En retard' }
    };
    const s = styles[status] || styles.draft;
    return (
      <span style={{ background: s.bg, color: s.color, padding: '4px 12px', borderRadius: '12px', fontSize: '12px', fontWeight: '600' }}>
        {s.text}
      </span>
    );
  };

  const { subtotal, taxTotal, total } = calculateTotals();
  const selectedClient = clients.find(c => c.id === formData.client_id);

  if (loading) return <div style={{ textAlign: 'center', padding: '60px' }}>Chargement...</div>;

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
        <div>
          <h1 style={{ fontSize: '32px', fontWeight: '800', margin: '0 0 8px 0' }}>📄 Factures</h1>
          <p style={{ color: '#6b7280', margin: 0 }}>Créez et gérez vos factures professionnelles</p>
        </div>
        <button
          onClick={() => openModal()}
          style={{
            background: 'linear-gradient(135deg, #3b82f6, #1d4ed8)',
            color: 'white',
            border: 'none',
            padding: '14px 28px',
            borderRadius: '12px',
            cursor: 'pointer',
            fontWeight: '700',
            fontSize: '15px',
            boxShadow: '0 4px 12px rgba(59,130,246,0.4)'
          }}
        >
          ✨ Nouvelle Facture
        </button>
      </div>

      {/* Messages */}
      {error && (
        <div style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#991b1b', padding: '16px', borderRadius: '8px', marginBottom: '20px' }}>
          {error}
        </div>
      )}
      {success && (
        <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', color: '#166534', padding: '16px', borderRadius: '8px', marginBottom: '20px' }}>
          {success}
        </div>
      )}

      {/* Invoices List */}
      <div style={{ background: 'white', border: '1px solid #e2e8f0', borderRadius: '12px', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead style={{ background: '#f8fafc' }}>
            <tr>
              <th style={{ padding: '16px', textAlign: 'left', fontWeight: '600', color: '#374151' }}>Numéro</th>
              <th style={{ padding: '16px', textAlign: 'left', fontWeight: '600', color: '#374151' }}>Client</th>
              <th style={{ padding: '16px', textAlign: 'left', fontWeight: '600', color: '#374151' }}>Date</th>
              <th style={{ padding: '16px', textAlign: 'left', fontWeight: '600', color: '#374151' }}>Montant</th>
              <th style={{ padding: '16px', textAlign: 'left', fontWeight: '600', color: '#374151' }}>Statut</th>
              <th style={{ padding: '16px', textAlign: 'center', fontWeight: '600', color: '#374151' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {invoices.length === 0 ? (
              <tr>
                <td colSpan="6" style={{ padding: '40px', textAlign: 'center', color: '#9ca3af' }}>
                  Aucune facture. Créez-en une pour commencer !
                </td>
              </tr>
            ) : (
              invoices.map(invoice => (
                <tr key={invoice.id} style={{ borderTop: '1px solid #e5e7eb' }}>
                  <td style={{ padding: '16px', fontWeight: '600' }}>{invoice.invoice_number}</td>
                  <td style={{ padding: '16px' }}>{invoice.client_name}</td>
                  <td style={{ padding: '16px', color: '#6b7280' }}>
                    {new Date(invoice.issue_date).toLocaleDateString('fr-FR')}
                  </td>
                  <td style={{ padding: '16px', fontWeight: '600', color: '#059669' }}>
                    {formatCurrency(invoice.total)}
                  </td>
                  <td style={{ padding: '16px' }}>{getStatusBadge(invoice.status)}</td>
                  <td style={{ padding: '16px', textAlign: 'center' }}>
                    <button
                      onClick={() => openModal(invoice)}
                      style={{ background: '#3b82f6', color: 'white', border: 'none', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer', marginRight: '8px' }}
                      title="Modifier"
                    >
                      ✏️
                    </button>
                    <button
                      onClick={() => handleSendEmail(invoice.id)}
                      style={{ background: '#10b981', color: 'white', border: 'none', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer', marginRight: '8px' }}
                      title="Envoyer par email"
                    >
                      📧
                    </button>
                    <button
                      onClick={() => handleDelete(invoice.id)}
                      style={{ background: '#ef4444', color: 'white', border: 'none', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer' }}
                      title="Supprimer"
                    >
                      🗑️
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Modal */}
      {showModal && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0, 0, 0, 0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: '20px'
        }} onClick={() => setShowModal(false)}>
          <div
            style={{
              background: 'white',
              borderRadius: '16px',
              width: '100%',
              maxWidth: '1400px',
              maxHeight: '90vh',
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div style={{
              padding: '24px',
              borderBottom: '1px solid #e2e8f0',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}>
              <h2 style={{ margin: 0, fontSize: '24px', fontWeight: '700' }}>
                {editingInvoice ? '✏️ Modifier la facture' : '✨ Nouvelle facture'}
              </h2>
              <button
                onClick={() => setShowModal(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  fontSize: '24px',
                  cursor: 'pointer',
                  color: '#9ca3af'
                }}
              >
                ✕
              </button>
            </div>

            {/* Modal Body - 2 Columns */}
            <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
              {/* Left: Form */}
              <div style={{ flex: 1, padding: '24px', overflowY: 'auto', borderRight: '1px solid #e2e8f0' }}>
                <form onSubmit={handleSubmit}>
                  {/* Client Selection */}
                  <div style={{ marginBottom: '20px' }}>
                    <label style={{ display: 'block', marginBottom: '8px', fontWeight: '600' }}>Client *</label>
                    <select
                      value={formData.client_id}
                      onChange={(e) => setFormData(prev => ({ ...prev, client_id: e.target.value }))}
                      required
                      style={{
                        width: '100%',
                        padding: '12px',
                        border: '1px solid #d1d5db',
                        borderRadius: '8px',
                        fontSize: '14px'
                      }}
                    >
                      <option value="">Sélectionner un client</option>
                      {clients.map(client => (
                        <option key={client.id} value={client.id}>{client.name}</option>
                      ))}
                    </select>
                  </div>

                  {/* Dates */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '20px' }}>
                    <div>
                      <label style={{ display: 'block', marginBottom: '8px', fontWeight: '600' }}>Date d'émission</label>
                      <input
                        type="date"
                        value={formData.issue_date}
                        onChange={(e) => setFormData(prev => ({ ...prev, issue_date: e.target.value }))}
                        style={{ width: '100%', padding: '12px', border: '1px solid #d1d5db', borderRadius: '8px' }}
                      />
                    </div>
                    <div>
                      <label style={{ display: 'block', marginBottom: '8px', fontWeight: '600' }}>Date d'échéance</label>
                      <input
                        type="date"
                        value={formData.due_date}
                        onChange={(e) => setFormData(prev => ({ ...prev, due_date: e.target.value }))}
                        style={{ width: '100%', padding: '12px', border: '1px solid #d1d5db', borderRadius: '8px' }}
                      />
                    </div>
                  </div>

                  {/* Tax Type */}
                  <div style={{ marginBottom: '20px' }}>
                    <label style={{ display: 'block', marginBottom: '8px', fontWeight: '600' }}>Type de taxes</label>
                    <div style={{ display: 'flex', gap: '12px' }}>
                      <button
                        type="button"
                        onClick={() => updateTaxType('TPSTVQ')}
                        style={{
                          flex: 1,
                          padding: '12px',
                          border: formData.tax_type === 'TPSTVQ' ? '2px solid #3b82f6' : '1px solid #d1d5db',
                          background: formData.tax_type === 'TPSTVQ' ? '#eff6ff' : 'white',
                          borderRadius: '8px',
                          cursor: 'pointer',
                          fontWeight: '600'
                        }}
                      >
                        TPS + TVQ (14.975%)
                      </button>
                      <button
                        type="button"
                        onClick={() => updateTaxType('HST')}
                        style={{
                          flex: 1,
                          padding: '12px',
                          border: formData.tax_type === 'HST' ? '2px solid #3b82f6' : '1px solid #d1d5db',
                          background: formData.tax_type === 'HST' ? '#eff6ff' : 'white',
                          borderRadius: '8px',
                          cursor: 'pointer',
                          fontWeight: '600'
                        }}
                      >
                        HST (13%)
                      </button>
                    </div>
                  </div>

                  {/* Items */}
                  <div style={{ marginBottom: '20px' }}>
                    <label style={{ display: 'block', marginBottom: '8px', fontWeight: '600' }}>Produits/Services</label>
                    {formData.items.map((item, index) => (
                      <div key={index} style={{
                        background: '#f9fafb',
                        border: '1px solid #e2e8f0',
                        borderRadius: '8px',
                        padding: '16px',
                        marginBottom: '12px'
                      }}>
                        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: '12px', marginBottom: '12px' }}>
                          <div>
                            <label style={{ display: 'block', marginBottom: '4px', fontSize: '12px', fontWeight: '600' }}>Produit</label>
                            <select
                              value={item.product_id}
                              onChange={(e) => updateItem(index, 'product_id', e.target.value)}
                              style={{ width: '100%', padding: '8px', border: '1px solid #d1d5db', borderRadius: '6px', fontSize: '14px' }}
                            >
                              <option value="">Personnalisé</option>
                              {products.map(product => (
                                <option key={product.id} value={product.id}>{product.name}</option>
                              ))}
                            </select>
                          </div>
                          <div>
                            <label style={{ display: 'block', marginBottom: '4px', fontSize: '12px', fontWeight: '600' }}>Quantité</label>
                            <input
                              type="number"
                              value={item.quantity}
                              onChange={(e) => updateItem(index, 'quantity', parseFloat(e.target.value) || 0)}
                              min="0"
                              step="0.01"
                              style={{ width: '100%', padding: '8px', border: '1px solid #d1d5db', borderRadius: '6px' }}
                            />
                          </div>
                          <div>
                            <label style={{ display: 'block', marginBottom: '4px', fontSize: '12px', fontWeight: '600' }}>Prix unitaire</label>
                            <input
                              type="number"
                              value={item.unit_price}
                              onChange={(e) => updateItem(index, 'unit_price', parseFloat(e.target.value) || 0)}
                              min="0"
                              step="0.01"
                              style={{ width: '100%', padding: '8px', border: '1px solid #d1d5db', borderRadius: '6px' }}
                            />
                          </div>
                        </div>
                        <div style={{ display: 'flex', gap: '12px' }}>
                          <input
                            type="text"
                            placeholder="Description"
                            value={item.description}
                            onChange={(e) => updateItem(index, 'description', e.target.value)}
                            style={{ flex: 1, padding: '8px', border: '1px solid #d1d5db', borderRadius: '6px' }}
                          />
                          {formData.items.length > 1 && (
                            <button
                              type="button"
                              onClick={() => removeItem(index)}
                              style={{
                                background: '#ef4444',
                                color: 'white',
                                border: 'none',
                                padding: '8px 16px',
                                borderRadius: '6px',
                                cursor: 'pointer'
                              }}
                            >
                              🗑️
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                    <button
                      type="button"
                      onClick={addItem}
                      style={{
                        width: '100%',
                        padding: '12px',
                        background: '#f3f4f6',
                        border: '2px dashed #d1d5db',
                        borderRadius: '8px',
                        cursor: 'pointer',
                        fontWeight: '600',
                        color: '#374151'
                      }}
                    >
                      ➕ Ajouter une ligne
                    </button>
                  </div>

                  {/* Discount */}
                  <div style={{ marginBottom: '20px' }}>
                    <label style={{ display: 'block', marginBottom: '8px', fontWeight: '600' }}>Escompte</label>
                    <input
                      type="number"
                      value={formData.discount}
                      onChange={(e) => setFormData(prev => ({ ...prev, discount: parseFloat(e.target.value) || 0 }))}
                      min="0"
                      step="0.01"
                      style={{ width: '100%', padding: '12px', border: '1px solid #d1d5db', borderRadius: '8px' }}
                    />
                  </div>

                  {/* Notes */}
                  <div style={{ marginBottom: '20px' }}>
                    <label style={{ display: 'block', marginBottom: '8px', fontWeight: '600' }}>Notes/Conditions</label>
                    <textarea
                      value={formData.notes}
                      onChange={(e) => setFormData(prev => ({ ...prev, notes: e.target.value }))}
                      rows="3"
                      style={{
                        width: '100%',
                        padding: '12px',
                        border: '1px solid #d1d5db',
                        borderRadius: '8px',
                        resize: 'vertical',
                        fontFamily: 'inherit'
                      }}
                    />
                  </div>

                  {/* Submit Button */}
                  <button
                    type="submit"
                    style={{
                      width: '100%',
                      background: 'linear-gradient(135deg, #10b981, #059669)',
                      color: 'white',
                      border: 'none',
                      padding: '16px',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      fontWeight: '700',
                      fontSize: '16px'
                    }}
                  >
                    {editingInvoice ? '💾 Enregistrer les modifications' : '✨ Créer la facture'}
                  </button>
                </form>
              </div>

              {/* Right: Preview */}
              <div style={{ flex: 1, padding: '24px', overflowY: 'auto', background: '#f9fafb' }}>
                <div style={{
                  background: 'white',
                  padding: '40px',
                  boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
                  borderRadius: '8px',
                  fontFamily: 'Arial, sans-serif'
                }}>
                  {/* Header */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '32px', paddingBottom: '24px', borderBottom: `3px solid ${formData.primary_color}` }}>
                    <div>
                      {settings?.logo_url && (
                        <img src={settings.logo_url} alt="Logo" style={{ height: '60px', marginBottom: '12px' }} />
                      )}
                      <h1 style={{ fontSize: '28px', fontWeight: '800', color: formData.primary_color, margin: '0 0 8px 0' }}>
                        {settings?.company_name || 'Votre Entreprise'}
                      </h1>
                      <p style={{ margin: 0, color: '#6b7280', fontSize: '14px' }}>
                        {settings?.address && `${settings.address}, `}
                        {settings?.city && `${settings.city} `}
                        {settings?.postal_code}
                      </p>
                      <p style={{ margin: '4px 0 0 0', color: '#6b7280', fontSize: '14px' }}>
                        {settings?.email} • {settings?.phone}
                      </p>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <h2 style={{ fontSize: '32px', fontWeight: '800', color: formData.primary_color, margin: '0 0 16px 0' }}>
                        FACTURE
                      </h2>
                      <p style={{ margin: '4px 0', fontSize: '14px' }}><strong>Date:</strong> {new Date(formData.issue_date).toLocaleDateString('fr-FR')}</p>
                      <p style={{ margin: '4px 0', fontSize: '14px' }}><strong>Échéance:</strong> {new Date(formData.due_date).toLocaleDateString('fr-FR')}</p>
                    </div>
                  </div>

                  {/* Client Info */}
                  {selectedClient && (
                    <div style={{ marginBottom: '32px', padding: '16px', background: '#f9fafb', borderRadius: '8px' }}>
                      <p style={{ margin: '0 0 4px 0', fontSize: '12px', color: '#6b7280', fontWeight: '600' }}>FACTURER À</p>
                      <p style={{ margin: '4px 0', fontSize: '16px', fontWeight: '700' }}>{selectedClient.name}</p>
                      <p style={{ margin: '2px 0', fontSize: '14px', color: '#6b7280' }}>
                        {selectedClient.address && `${selectedClient.address}, `}
                        {selectedClient.city && `${selectedClient.city} `}
                        {selectedClient.postal_code}
                      </p>
                      <p style={{ margin: '2px 0', fontSize: '14px', color: '#6b7280' }}>{selectedClient.email}</p>
                    </div>
                  )}

                  {/* Items Table */}
                  <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '24px' }}>
                    <thead>
                      <tr style={{ background: formData.primary_color, color: 'white' }}>
                        <th style={{ padding: '12px', textAlign: 'left', fontSize: '14px' }}>Description</th>
                        <th style={{ padding: '12px', textAlign: 'center', fontSize: '14px' }}>Qté</th>
                        <th style={{ padding: '12px', textAlign: 'right', fontSize: '14px' }}>Prix unit.</th>
                        <th style={{ padding: '12px', textAlign: 'right', fontSize: '14px' }}>Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {formData.items.map((item, index) => (
                        <tr key={index} style={{ borderBottom: '1px solid #e5e7eb' }}>
                          <td style={{ padding: '12px', fontSize: '14px' }}>{item.description || '(Vide)'}</td>
                          <td style={{ padding: '12px', textAlign: 'center', fontSize: '14px' }}>{item.quantity}</td>
                          <td style={{ padding: '12px', textAlign: 'right', fontSize: '14px' }}>{formatCurrency(item.unit_price)}</td>
                          <td style={{ padding: '12px', textAlign: 'right', fontSize: '14px', fontWeight: '600' }}>
                            {formatCurrency(item.quantity * item.unit_price)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>

                  {/* Totals */}
                  <div style={{ marginLeft: 'auto', width: '300px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', fontSize: '14px' }}>
                      <span>Sous-total:</span>
                      <span style={{ fontWeight: '600' }}>{formatCurrency(subtotal)}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', fontSize: '14px' }}>
                      <span>{formData.tax_type === 'TPSTVQ' ? 'TPS + TVQ' : 'HST'} ({formData.tax_type === 'TPSTVQ' ? '14.975' : '13'}%):</span>
                      <span style={{ fontWeight: '600' }}>{formatCurrency(taxTotal)}</span>
                    </div>
                    {formData.discount > 0 && (
                      <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', fontSize: '14px', color: '#ef4444' }}>
                        <span>Escompte:</span>
                        <span style={{ fontWeight: '600' }}>-{formatCurrency(formData.discount)}</span>
                      </div>
                    )}
                    <div style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      padding: '16px',
                      background: formData.primary_color,
                      color: 'white',
                      borderRadius: '8px',
                      marginTop: '8px'
                    }}>
                      <span style={{ fontSize: '18px', fontWeight: '700' }}>TOTAL:</span>
                      <span style={{ fontSize: '24px', fontWeight: '800' }}>{formatCurrency(total)}</span>
                    </div>
                  </div>

                  {/* Tax Numbers */}
                  {(settings?.gst_number || settings?.pst_number || settings?.hst_number) && (
                    <div style={{ marginTop: '32px', padding: '16px', background: '#f9fafb', borderRadius: '8px', fontSize: '12px', color: '#6b7280' }}>
                      {settings.gst_number && <p style={{ margin: '2px 0' }}>TPS: {settings.gst_number}</p>}
                      {settings.pst_number && <p style={{ margin: '2px 0' }}>TVQ: {settings.pst_number}</p>}
                      {settings.hst_number && <p style={{ margin: '2px 0' }}>HST: {settings.hst_number}</p>}
                    </div>
                  )}

                  {/* Notes */}
                  {formData.notes && (
                    <div style={{ marginTop: '24px', paddingTop: '24px', borderTop: '1px solid #e5e7eb' }}>
                      <p style={{ fontSize: '12px', fontWeight: '600', color: '#374151', margin: '0 0 8px 0' }}>NOTES:</p>
                      <p style={{ fontSize: '13px', color: '#6b7280', margin: 0, whiteSpace: 'pre-wrap' }}>{formData.notes}</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const QuotesPage = () => {
  const [quotes, setQuotes] = useState([]);
  const [clients, setClients] = useState([]);
  const [products, setProducts] = useState([]);
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingQuote, setEditingQuote] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  const [formData, setFormData] = useState({
    client_id: '',
    valid_until: new Date(Date.now() + 30*24*60*60*1000).toISOString().split('T')[0],
    items: [{ product_id: '', description: '', quantity: 1, unit_price: 0, tax_rate: 14.975 }],
    tax_type: 'TPSTVQ',
    discount: 0,
    notes: 'Cette soumission est valide pour 30 jours.\nMerci de votre confiance !',
    primary_color: '#3b82f6'
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [quotesRes, clientsRes, productsRes, settingsRes] = await Promise.all([
        axios.get(`${BACKEND_URL}/api/quotes`),
        axios.get(`${BACKEND_URL}/api/clients`),
        axios.get(`${BACKEND_URL}/api/products`),
        axios.get(`${BACKEND_URL}/api/settings/company`)
      ]);
      setQuotes(quotesRes.data);
      setClients(clientsRes.data);
      setProducts(productsRes.data);
      setSettings(settingsRes.data);
      
      if (settingsRes.data?.primary_color) {
        setFormData(prev => ({ ...prev, primary_color: settingsRes.data.primary_color }));
      }
    } catch (error) {
      console.error('Error fetching data:', error);
      setError('Erreur lors du chargement des données');
    } finally {
      setLoading(false);
    }
  };

  const openModal = (quote = null) => {
    if (quote) {
      setEditingQuote(quote);
      setFormData({
        client_id: quote.client_id,
        valid_until: quote.valid_until?.split('T')[0] || new Date(Date.now() + 30*24*60*60*1000).toISOString().split('T')[0],
        items: quote.items,
        tax_type: quote.tax_type || 'TPSTVQ',
        discount: quote.discount || 0,
        notes: quote.notes || '',
        primary_color: quote.primary_color || settings?.primary_color || '#3b82f6'
      });
    } else {
      setEditingQuote(null);
      setFormData({
        client_id: '',
        valid_until: new Date(Date.now() + 30*24*60*60*1000).toISOString().split('T')[0],
        items: [{ product_id: '', description: '', quantity: 1, unit_price: 0, tax_rate: 14.975 }],
        tax_type: 'TPSTVQ',
        discount: 0,
        notes: 'Cette soumission est valide pour 30 jours.\nMerci de votre confiance !',
        primary_color: settings?.primary_color || '#3b82f6'
      });
    }
    setShowModal(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    try {
      const selectedClient = clients.find(c => c.id === formData.client_id);
      if (!selectedClient) {
        setError('Veuillez sélectionner un client');
        return;
      }

      const quoteData = {
        ...formData,
        client_name: selectedClient.name,
        client_email: selectedClient.email,
        client_address: `${selectedClient.address || ''}, ${selectedClient.city || ''} ${selectedClient.postal_code || ''}`.trim()
      };

      if (editingQuote) {
        await axios.put(`${BACKEND_URL}/api/quotes/${editingQuote.id}`, quoteData);
        setSuccess('Soumission modifiée avec succès');
      } else {
        await axios.post(`${BACKEND_URL}/api/quotes`, quoteData);
        setSuccess('Soumission créée avec succès');
      }
      
      setShowModal(false);
      fetchData();
    } catch (error) {
      console.error('Error saving quote:', error);
      setError(error.response?.data?.detail || 'Erreur lors de la sauvegarde');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Êtes-vous sûr de vouloir supprimer cette soumission ?')) return;
    
    try {
      await axios.delete(`${BACKEND_URL}/api/quotes/${id}`);
      setSuccess('Soumission supprimée');
      fetchData();
    } catch (error) {
      setError('Erreur lors de la suppression');
    }
  };

  const addItem = () => {
    setFormData(prev => ({
      ...prev,
      items: [...prev.items, { product_id: '', description: '', quantity: 1, unit_price: 0, tax_rate: prev.tax_type === 'TPSTVQ' ? 14.975 : 13 }]
    }));
  };

  const removeItem = (index) => {
    if (formData.items.length > 1) {
      setFormData(prev => ({
        ...prev,
        items: prev.items.filter((_, i) => i !== index)
      }));
    }
  };

  const updateItem = (index, field, value) => {
    const newItems = [...formData.items];
    
    if (field === 'product_id' && value) {
      const product = products.find(p => p.id === value);
      if (product) {
        newItems[index] = {
          ...newItems[index],
          product_id: value,
          description: product.name,
          unit_price: product.price
        };
      }
    } else {
      newItems[index] = { ...newItems[index], [field]: value };
    }
    
    setFormData(prev => ({ ...prev, items: newItems }));
  };

  const updateTaxType = (type) => {
    const rate = type === 'TPSTVQ' ? 14.975 : 13;
    setFormData(prev => ({
      ...prev,
      tax_type: type,
      items: prev.items.map(item => ({ ...item, tax_rate: rate }))
    }));
  };

  const calculateTotals = () => {
    const subtotal = formData.items.reduce((sum, item) => sum + (item.quantity * item.unit_price), 0);
    const taxTotal = formData.items.reduce((sum, item) => sum + (item.quantity * item.unit_price * item.tax_rate / 100), 0);
    const total = subtotal + taxTotal - (formData.discount || 0);
    return { subtotal, taxTotal, total };
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('fr-CA', { style: 'currency', currency: 'CAD' }).format(amount || 0);
  };

  const getStatusBadge = (status) => {
    const styles = {
      draft: { bg: '#f3f4f6', color: '#374151', text: 'Brouillon' },
      sent: { bg: '#dbeafe', color: '#1e40af', text: 'Envoyée' },
      accepted: { bg: '#dcfce7', color: '#166534', text: 'Acceptée' },
      rejected: { bg: '#fee2e2', color: '#991b1b', text: 'Refusée' }
    };
    const s = styles[status] || styles.draft;
    return (
      <span style={{ background: s.bg, color: s.color, padding: '4px 12px', borderRadius: '12px', fontSize: '12px', fontWeight: '600' }}>
        {s.text}
      </span>
    );
  };

  const { subtotal, taxTotal, total } = calculateTotals();
  const selectedClient = clients.find(c => c.id === formData.client_id);

  if (loading) return <div style={{ textAlign: 'center', padding: '60px' }}>Chargement...</div>;

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
        <div>
          <h1 style={{ fontSize: '32px', fontWeight: '800', margin: '0 0 8px 0' }}>📝 Soumissions</h1>
          <p style={{ color: '#6b7280', margin: 0 }}>Créez et gérez vos soumissions clients</p>
        </div>
        <button
          onClick={() => openModal()}
          style={{
            background: 'linear-gradient(135deg, #8b5cf6, #6d28d9)',
            color: 'white',
            border: 'none',
            padding: '14px 28px',
            borderRadius: '12px',
            cursor: 'pointer',
            fontWeight: '700',
            fontSize: '15px',
            boxShadow: '0 4px 12px rgba(139,92,246,0.4)'
          }}
        >
          ✨ Nouvelle Soumission
        </button>
      </div>

      {/* Messages */}
      {error && (
        <div style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#991b1b', padding: '16px', borderRadius: '8px', marginBottom: '20px' }}>
          {error}
        </div>
      )}
      {success && (
        <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', color: '#166534', padding: '16px', borderRadius: '8px', marginBottom: '20px' }}>
          {success}
        </div>
      )}

      {/* Quotes List */}
      <div style={{ background: 'white', border: '1px solid #e2e8f0', borderRadius: '12px', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead style={{ background: '#f8fafc' }}>
            <tr>
              <th style={{ padding: '16px', textAlign: 'left', fontWeight: '600', color: '#374151' }}>Numéro</th>
              <th style={{ padding: '16px', textAlign: 'left', fontWeight: '600', color: '#374151' }}>Client</th>
              <th style={{ padding: '16px', textAlign: 'left', fontWeight: '600', color: '#374151' }}>Valide jusqu'au</th>
              <th style={{ padding: '16px', textAlign: 'left', fontWeight: '600', color: '#374151' }}>Montant</th>
              <th style={{ padding: '16px', textAlign: 'left', fontWeight: '600', color: '#374151' }}>Statut</th>
              <th style={{ padding: '16px', textAlign: 'center', fontWeight: '600', color: '#374151' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {quotes.length === 0 ? (
              <tr>
                <td colSpan="6" style={{ padding: '40px', textAlign: 'center', color: '#9ca3af' }}>
                  Aucune soumission. Créez-en une pour commencer !
                </td>
              </tr>
            ) : (
              quotes.map(quote => (
                <tr key={quote.id} style={{ borderTop: '1px solid #e5e7eb' }}>
                  <td style={{ padding: '16px', fontWeight: '600' }}>{quote.quote_number}</td>
                  <td style={{ padding: '16px' }}>{quote.client_name}</td>
                  <td style={{ padding: '16px', color: '#6b7280' }}>
                    {new Date(quote.valid_until).toLocaleDateString('fr-FR')}
                  </td>
                  <td style={{ padding: '16px', fontWeight: '600', color: '#8b5cf6' }}>
                    {formatCurrency(quote.total)}
                  </td>
                  <td style={{ padding: '16px' }}>{getStatusBadge(quote.status)}</td>
                  <td style={{ padding: '16px', textAlign: 'center' }}>
                    <div style={{ display: 'flex', gap: '8px', justifyContent: 'center', flexWrap: 'wrap' }}>
                      <button
                        onClick={() => openModal(quote)}
                        style={{ background: '#8b5cf6', color: 'white', border: 'none', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer' }}
                        title="Modifier"
                      >
                        ✏️
                      </button>
                      <button
                        onClick={async () => {
                          if (window.confirm('Envoyer cette soumission au client par email ?')) {
                            try {
                              await axios.post(`${BACKEND_URL}/api/quotes/${quote.id}/send-email`);
                              setSuccess('Soumission envoyée au client !');
                              fetchData();
                            } catch (error) {
                              setError('Erreur lors de l\'envoi de la soumission');
                            }
                          }
                        }}
                        style={{ background: '#0d9488', color: 'white', border: 'none', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer' }}
                        title="Envoyer au client"
                      >
                        📧
                      </button>
                      {quote.status !== 'rejected' && (
                        <button
                          onClick={async () => {
                            if (window.confirm('Convertir cette soumission en facture ?')) {
                              try {
                                await axios.post(`${BACKEND_URL}/api/quotes/${quote.id}/convert-to-invoice`);
                                setSuccess('Soumission convertie en facture avec succès !');
                                fetchData();
                              } catch (error) {
                                setError('Erreur lors de la conversion');
                              }
                            }
                          }}
                          style={{ background: '#10b981', color: 'white', border: 'none', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer' }}
                          title="Convertir en facture"
                        >
                          💼
                        </button>
                      )}
                      <button
                        onClick={() => handleDelete(quote.id)}
                        style={{ background: '#ef4444', color: 'white', border: 'none', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer' }}
                        title="Supprimer"
                      >
                        🗑️
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Modal - Similar structure to InvoicesPage but adapted for quotes */}
      {showModal && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0, 0, 0, 0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: '20px'
        }} onClick={() => setShowModal(false)}>
          <div
            style={{
              background: 'white',
              borderRadius: '16px',
              width: '100%',
              maxWidth: '1400px',
              maxHeight: '90vh',
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div style={{
              padding: '24px',
              borderBottom: '1px solid #e2e8f0',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}>
              <h2 style={{ margin: 0, fontSize: '24px', fontWeight: '700' }}>
                {editingQuote ? '✏️ Modifier la soumission' : '✨ Nouvelle soumission'}
              </h2>
              <button
                onClick={() => setShowModal(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  fontSize: '24px',
                  cursor: 'pointer',
                  color: '#9ca3af'
                }}
              >
                ✕
              </button>
            </div>

            {/* Modal Body - 2 Columns */}
            <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
              {/* Left: Form */}
              <div style={{ flex: 1, padding: '24px', overflowY: 'auto', borderRight: '1px solid #e2e8f0' }}>
                <form onSubmit={handleSubmit}>
                  {/* Client Selection */}
                  <div style={{ marginBottom: '20px' }}>
                    <label style={{ display: 'block', marginBottom: '8px', fontWeight: '600' }}>Client *</label>
                    <select
                      value={formData.client_id}
                      onChange={(e) => setFormData(prev => ({ ...prev, client_id: e.target.value }))}
                      required
                      style={{
                        width: '100%',
                        padding: '12px',
                        border: '1px solid #d1d5db',
                        borderRadius: '8px',
                        fontSize: '14px'
                      }}
                    >
                      <option value="">Sélectionner un client</option>
                      {clients.map(client => (
                        <option key={client.id} value={client.id}>{client.name}</option>
                      ))}
                    </select>
                  </div>

                  {/* Valid Until */}
                  <div style={{ marginBottom: '20px' }}>
                    <label style={{ display: 'block', marginBottom: '8px', fontWeight: '600' }}>Valide jusqu'au</label>
                    <input
                      type="date"
                      value={formData.valid_until}
                      onChange={(e) => setFormData(prev => ({ ...prev, valid_until: e.target.value }))}
                      style={{ width: '100%', padding: '12px', border: '1px solid #d1d5db', borderRadius: '8px' }}
                    />
                  </div>

                  {/* Tax Type */}
                  <div style={{ marginBottom: '20px' }}>
                    <label style={{ display: 'block', marginBottom: '8px', fontWeight: '600' }}>Type de taxes</label>
                    <div style={{ display: 'flex', gap: '12px' }}>
                      <button
                        type="button"
                        onClick={() => updateTaxType('TPSTVQ')}
                        style={{
                          flex: 1,
                          padding: '12px',
                          border: formData.tax_type === 'TPSTVQ' ? '2px solid #8b5cf6' : '1px solid #d1d5db',
                          background: formData.tax_type === 'TPSTVQ' ? '#f5f3ff' : 'white',
                          borderRadius: '8px',
                          cursor: 'pointer',
                          fontWeight: '600'
                        }}
                      >
                        TPS + TVQ (14.975%)
                      </button>
                      <button
                        type="button"
                        onClick={() => updateTaxType('HST')}
                        style={{
                          flex: 1,
                          padding: '12px',
                          border: formData.tax_type === 'HST' ? '2px solid #8b5cf6' : '1px solid #d1d5db',
                          background: formData.tax_type === 'HST' ? '#f5f3ff' : 'white',
                          borderRadius: '8px',
                          cursor: 'pointer',
                          fontWeight: '600'
                        }}
                      >
                        HST (13%)
                      </button>
                    </div>
                  </div>

                  {/* Items */}
                  <div style={{ marginBottom: '20px' }}>
                    <label style={{ display: 'block', marginBottom: '8px', fontWeight: '600' }}>Produits/Services</label>
                    {formData.items.map((item, index) => (
                      <div key={index} style={{
                        background: '#f9fafb',
                        border: '1px solid #e2e8f0',
                        borderRadius: '8px',
                        padding: '16px',
                        marginBottom: '12px'
                      }}>
                        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: '12px', marginBottom: '12px' }}>
                          <div>
                            <label style={{ display: 'block', marginBottom: '4px', fontSize: '12px', fontWeight: '600' }}>Produit</label>
                            <select
                              value={item.product_id}
                              onChange={(e) => updateItem(index, 'product_id', e.target.value)}
                              style={{ width: '100%', padding: '8px', border: '1px solid #d1d5db', borderRadius: '6px', fontSize: '14px' }}
                            >
                              <option value="">Personnalisé</option>
                              {products.map(product => (
                                <option key={product.id} value={product.id}>{product.name}</option>
                              ))}
                            </select>
                          </div>
                          <div>
                            <label style={{ display: 'block', marginBottom: '4px', fontSize: '12px', fontWeight: '600' }}>Quantité</label>
                            <input
                              type="number"
                              value={item.quantity}
                              onChange={(e) => updateItem(index, 'quantity', parseFloat(e.target.value) || 0)}
                              min="0"
                              step="0.01"
                              style={{ width: '100%', padding: '8px', border: '1px solid #d1d5db', borderRadius: '6px' }}
                            />
                          </div>
                          <div>
                            <label style={{ display: 'block', marginBottom: '4px', fontSize: '12px', fontWeight: '600' }}>Prix unitaire</label>
                            <input
                              type="number"
                              value={item.unit_price}
                              onChange={(e) => updateItem(index, 'unit_price', parseFloat(e.target.value) || 0)}
                              min="0"
                              step="0.01"
                              style={{ width: '100%', padding: '8px', border: '1px solid #d1d5db', borderRadius: '6px' }}
                            />
                          </div>
                        </div>
                        <div style={{ display: 'flex', gap: '12px' }}>
                          <input
                            type="text"
                            placeholder="Description"
                            value={item.description}
                            onChange={(e) => updateItem(index, 'description', e.target.value)}
                            style={{ flex: 1, padding: '8px', border: '1px solid #d1d5db', borderRadius: '6px' }}
                          />
                          {formData.items.length > 1 && (
                            <button
                              type="button"
                              onClick={() => removeItem(index)}
                              style={{
                                background: '#ef4444',
                                color: 'white',
                                border: 'none',
                                padding: '8px 16px',
                                borderRadius: '6px',
                                cursor: 'pointer'
                              }}
                            >
                              🗑️
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                    <button
                      type="button"
                      onClick={addItem}
                      style={{
                        width: '100%',
                        padding: '12px',
                        background: '#f3f4f6',
                        border: '2px dashed #d1d5db',
                        borderRadius: '8px',
                        cursor: 'pointer',
                        fontWeight: '600',
                        color: '#374151'
                      }}
                    >
                      ➕ Ajouter une ligne
                    </button>
                  </div>

                  {/* Discount */}
                  <div style={{ marginBottom: '20px' }}>
                    <label style={{ display: 'block', marginBottom: '8px', fontWeight: '600' }}>Escompte</label>
                    <input
                      type="number"
                      value={formData.discount}
                      onChange={(e) => setFormData(prev => ({ ...prev, discount: parseFloat(e.target.value) || 0 }))}
                      min="0"
                      step="0.01"
                      style={{ width: '100%', padding: '12px', border: '1px solid #d1d5db', borderRadius: '8px' }}
                    />
                  </div>

                  {/* Notes */}
                  <div style={{ marginBottom: '20px' }}>
                    <label style={{ display: 'block', marginBottom: '8px', fontWeight: '600' }}>Notes/Conditions</label>
                    <textarea
                      value={formData.notes}
                      onChange={(e) => setFormData(prev => ({ ...prev, notes: e.target.value }))}
                      rows="3"
                      style={{
                        width: '100%',
                        padding: '12px',
                        border: '1px solid #d1d5db',
                        borderRadius: '8px',
                        resize: 'vertical',
                        fontFamily: 'inherit'
                      }}
                    />
                  </div>

                  {/* Submit Button */}
                  <button
                    type="submit"
                    style={{
                      width: '100%',
                      background: 'linear-gradient(135deg, #8b5cf6, #6d28d9)',
                      color: 'white',
                      border: 'none',
                      padding: '16px',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      fontWeight: '700',
                      fontSize: '16px'
                    }}
                  >
                    {editingQuote ? '💾 Enregistrer les modifications' : '✨ Créer la soumission'}
                  </button>
                </form>
              </div>

              {/* Right: Preview */}
              <div style={{ flex: 1, padding: '24px', overflowY: 'auto', background: '#f9fafb' }}>
                <div style={{
                  background: 'white',
                  padding: '40px',
                  boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
                  borderRadius: '8px',
                  fontFamily: 'Arial, sans-serif'
                }}>
                  {/* Header */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '32px', paddingBottom: '24px', borderBottom: `3px solid ${formData.primary_color}` }}>
                    <div>
                      {settings?.logo_url && (
                        <img src={settings.logo_url} alt="Logo" style={{ height: '60px', marginBottom: '12px' }} />
                      )}
                      <h1 style={{ fontSize: '28px', fontWeight: '800', color: formData.primary_color, margin: '0 0 8px 0' }}>
                        {settings?.company_name || 'Votre Entreprise'}
                      </h1>
                      <p style={{ margin: 0, color: '#6b7280', fontSize: '14px' }}>
                        {settings?.address && `${settings.address}, `}
                        {settings?.city && `${settings.city} `}
                        {settings?.postal_code}
                      </p>
                      <p style={{ margin: '4px 0 0 0', color: '#6b7280', fontSize: '14px' }}>
                        {settings?.email} • {settings?.phone}
                      </p>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <h2 style={{ fontSize: '32px', fontWeight: '800', color: formData.primary_color, margin: '0 0 16px 0' }}>
                        SOUMISSION
                      </h2>
                      <p style={{ margin: '4px 0', fontSize: '14px' }}><strong>Valide jusqu'au:</strong> {new Date(formData.valid_until).toLocaleDateString('fr-FR')}</p>
                    </div>
                  </div>

                  {/* Client Info */}
                  {selectedClient && (
                    <div style={{ marginBottom: '32px', padding: '16px', background: '#f9fafb', borderRadius: '8px' }}>
                      <p style={{ margin: '0 0 4px 0', fontSize: '12px', color: '#6b7280', fontWeight: '600' }}>SOUMISSION POUR</p>
                      <p style={{ margin: '4px 0', fontSize: '16px', fontWeight: '700' }}>{selectedClient.name}</p>
                      <p style={{ margin: '2px 0', fontSize: '14px', color: '#6b7280' }}>
                        {selectedClient.address && `${selectedClient.address}, `}
                        {selectedClient.city && `${selectedClient.city} `}
                        {selectedClient.postal_code}
                      </p>
                      <p style={{ margin: '2px 0', fontSize: '14px', color: '#6b7280' }}>{selectedClient.email}</p>
                    </div>
                  )}

                  {/* Items Table */}
                  <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '24px' }}>
                    <thead>
                      <tr style={{ background: formData.primary_color, color: 'white' }}>
                        <th style={{ padding: '12px', textAlign: 'left', fontSize: '14px' }}>Description</th>
                        <th style={{ padding: '12px', textAlign: 'center', fontSize: '14px' }}>Qté</th>
                        <th style={{ padding: '12px', textAlign: 'right', fontSize: '14px' }}>Prix unit.</th>
                        <th style={{ padding: '12px', textAlign: 'right', fontSize: '14px' }}>Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {formData.items.map((item, index) => (
                        <tr key={index} style={{ borderBottom: '1px solid #e5e7eb' }}>
                          <td style={{ padding: '12px', fontSize: '14px' }}>{item.description || '(Vide)'}</td>
                          <td style={{ padding: '12px', textAlign: 'center', fontSize: '14px' }}>{item.quantity}</td>
                          <td style={{ padding: '12px', textAlign: 'right', fontSize: '14px' }}>{formatCurrency(item.unit_price)}</td>
                          <td style={{ padding: '12px', textAlign: 'right', fontSize: '14px', fontWeight: '600' }}>
                            {formatCurrency(item.quantity * item.unit_price)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>

                  {/* Totals */}
                  <div style={{ marginLeft: 'auto', width: '300px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', fontSize: '14px' }}>
                      <span>Sous-total:</span>
                      <span style={{ fontWeight: '600' }}>{formatCurrency(subtotal)}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', fontSize: '14px' }}>
                      <span>{formData.tax_type === 'TPSTVQ' ? 'TPS + TVQ' : 'HST'} ({formData.tax_type === 'TPSTVQ' ? '14.975' : '13'}%):</span>
                      <span style={{ fontWeight: '600' }}>{formatCurrency(taxTotal)}</span>
                    </div>
                    {formData.discount > 0 && (
                      <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', fontSize: '14px', color: '#ef4444' }}>
                        <span>Escompte:</span>
                        <span style={{ fontWeight: '600' }}>-{formatCurrency(formData.discount)}</span>
                      </div>
                    )}
                    <div style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      padding: '16px',
                      background: formData.primary_color,
                      color: 'white',
                      borderRadius: '8px',
                      marginTop: '8px'
                    }}>
                      <span style={{ fontSize: '18px', fontWeight: '700' }}>TOTAL:</span>
                      <span style={{ fontSize: '24px', fontWeight: '800' }}>{formatCurrency(total)}</span>
                    </div>
                  </div>

                  {/* Tax Numbers */}
                  {(settings?.gst_number || settings?.pst_number || settings?.hst_number) && (
                    <div style={{ marginTop: '32px', padding: '16px', background: '#f9fafb', borderRadius: '8px', fontSize: '12px', color: '#6b7280' }}>
                      {settings.gst_number && <p style={{ margin: '2px 0' }}>TPS: {settings.gst_number}</p>}
                      {settings.pst_number && <p style={{ margin: '2px 0' }}>TVQ: {settings.pst_number}</p>}
                      {settings.hst_number && <p style={{ margin: '2px 0' }}>HST: {settings.hst_number}</p>}
                    </div>
                  )}

                  {/* Notes */}
                  {formData.notes && (
                    <div style={{ marginTop: '24px', paddingTop: '24px', borderTop: '1px solid #e5e7eb' }}>
                      <p style={{ fontSize: '12px', fontWeight: '600', color: '#374151', margin: '0 0 8px 0' }}>NOTES:</p>
                      <p style={{ fontSize: '13px', color: '#6b7280', margin: 0, whiteSpace: 'pre-wrap' }}>{formData.notes}</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
const EmployeesPage = () => {
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingEmployee, setEditingEmployee] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    position: '',
    salary: '',
    hire_date: new Date().toISOString().split('T')[0]
  });

  useEffect(() => {
    fetchEmployees();
  }, []);

  const fetchEmployees = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/employees`);
      setEmployees(response.data);
    } catch (error) {
      setError('Erreur lors du chargement des employés');
    } finally {
      setLoading(false);
    }
  };

  const openModal = (employee = null) => {
    if (employee) {
      setEditingEmployee(employee);
      setFormData({
        first_name: employee.first_name,
        last_name: employee.last_name,
        email: employee.email,
        phone: employee.phone || '',
        position: employee.position || '',
        salary: employee.salary || '',
        hire_date: employee.hire_date?.split('T')[0] || new Date().toISOString().split('T')[0]
      });
    } else {
      setEditingEmployee(null);
      setFormData({
        first_name: '',
        last_name: '',
        email: '',
        phone: '',
        position: '',
        salary: '',
        hire_date: new Date().toISOString().split('T')[0]
      });
    }
    setShowModal(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    try {
      if (editingEmployee) {
        await axios.put(`${BACKEND_URL}/api/employees/${editingEmployee.id}`, formData);
        setSuccess('Employé modifié avec succès');
      } else {
        await axios.post(`${BACKEND_URL}/api/employees`, formData);
        setSuccess('Employé ajouté avec succès');
      }
      setShowModal(false);
      fetchEmployees();
    } catch (error) {
      setError(error.response?.data?.detail || 'Erreur lors de la sauvegarde');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Êtes-vous sûr de vouloir supprimer cet employé ?')) return;
    try {
      await axios.delete(`${BACKEND_URL}/api/employees/${id}`);
      setSuccess('Employé supprimé');
      fetchEmployees();
    } catch (error) {
      setError('Erreur lors de la suppression');
    }
  };

  if (loading) return <div style={{ textAlign: 'center', padding: '60px' }}>Chargement...</div>;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
        <div>
          <h1 style={{ fontSize: '32px', fontWeight: '800', margin: '0 0 8px 0' }}>👨‍💼 Employés</h1>
          <p style={{ color: '#6b7280', margin: 0 }}>Gérez vos employés et leurs informations</p>
        </div>
        <button
          onClick={() => openModal()}
          style={{
            background: 'linear-gradient(135deg, #f59e0b, #d97706)',
            color: 'white',
            border: 'none',
            padding: '14px 28px',
            borderRadius: '12px',
            cursor: 'pointer',
            fontWeight: '700',
            fontSize: '15px',
            boxShadow: '0 4px 12px rgba(245,158,11,0.4)'
          }}
        >
          ➕ Nouvel Employé
        </button>
      </div>

      {error && (
        <div style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#991b1b', padding: '16px', borderRadius: '8px', marginBottom: '20px' }}>
          {error}
        </div>
      )}
      {success && (
        <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', color: '#166534', padding: '16px', borderRadius: '8px', marginBottom: '20px' }}>
          {success}
        </div>
      )}

      <div style={{ background: 'white', border: '1px solid #e2e8f0', borderRadius: '12px', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead style={{ background: '#f8fafc' }}>
            <tr>
              <th style={{ padding: '16px', textAlign: 'left', fontWeight: '600', color: '#374151' }}>Nom</th>
              <th style={{ padding: '16px', textAlign: 'left', fontWeight: '600', color: '#374151' }}>Email</th>
              <th style={{ padding: '16px', textAlign: 'left', fontWeight: '600', color: '#374151' }}>Poste</th>
              <th style={{ padding: '16px', textAlign: 'left', fontWeight: '600', color: '#374151' }}>Téléphone</th>
              <th style={{ padding: '16px', textAlign: 'center', fontWeight: '600', color: '#374151' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {employees.length === 0 ? (
              <tr>
                <td colSpan="5" style={{ padding: '40px', textAlign: 'center', color: '#9ca3af' }}>
                  Aucun employé. Ajoutez-en un pour commencer !
                </td>
              </tr>
            ) : (
              employees.map(employee => (
                <tr key={employee.id} style={{ borderTop: '1px solid #e5e7eb' }}>
                  <td style={{ padding: '16px', fontWeight: '600' }}>{employee.first_name} {employee.last_name}</td>
                  <td style={{ padding: '16px' }}>{employee.email}</td>
                  <td style={{ padding: '16px', color: '#6b7280' }}>{employee.position || '-'}</td>
                  <td style={{ padding: '16px', color: '#6b7280' }}>{employee.phone || '-'}</td>
                  <td style={{ padding: '16px', textAlign: 'center' }}>
                    <button
                      onClick={() => openModal(employee)}
                      style={{ background: '#f59e0b', color: 'white', border: 'none', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer', marginRight: '8px' }}
                    >
                      ✏️
                    </button>
                    <button
                      onClick={() => handleDelete(employee.id)}
                      style={{ background: '#ef4444', color: 'white', border: 'none', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer' }}
                    >
                      🗑️
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0, 0, 0, 0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }} onClick={() => setShowModal(false)}>
          <div
            style={{
              background: 'white',
              borderRadius: '16px',
              width: '100%',
              maxWidth: '600px',
              padding: '32px'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h2 style={{ margin: '0 0 24px 0', fontSize: '24px', fontWeight: '700' }}>
              {editingEmployee ? '✏️ Modifier l\'employé' : '➕ Nouvel employé'}
            </h2>

            <form onSubmit={handleSubmit}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Prénom *</label>
                  <input
                    type="text"
                    value={formData.first_name}
                    onChange={(e) => setFormData(prev => ({ ...prev, first_name: e.target.value }))}
                    required
                    style={{ width: '100%', padding: '12px', border: '1px solid #d1d5db', borderRadius: '8px', boxSizing: 'border-box' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Nom *</label>
                  <input
                    type="text"
                    value={formData.last_name}
                    onChange={(e) => setFormData(prev => ({ ...prev, last_name: e.target.value }))}
                    required
                    style={{ width: '100%', padding: '12px', border: '1px solid #d1d5db', borderRadius: '8px', boxSizing: 'border-box' }}
                  />
                </div>
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Email *</label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData(prev => ({ ...prev, email: e.target.value }))}
                  required
                  style={{ width: '100%', padding: '12px', border: '1px solid #d1d5db', borderRadius: '8px', boxSizing: 'border-box' }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Téléphone</label>
                  <input
                    type="tel"
                    value={formData.phone}
                    onChange={(e) => setFormData(prev => ({ ...prev, phone: e.target.value }))}
                    style={{ width: '100%', padding: '12px', border: '1px solid #d1d5db', borderRadius: '8px', boxSizing: 'border-box' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Poste</label>
                  <input
                    type="text"
                    value={formData.position}
                    onChange={(e) => setFormData(prev => ({ ...prev, position: e.target.value }))}
                    style={{ width: '100%', padding: '12px', border: '1px solid #d1d5db', borderRadius: '8px', boxSizing: 'border-box' }}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '24px' }}>
                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Salaire annuel</label>
                  <input
                    type="number"
                    value={formData.salary}
                    onChange={(e) => setFormData(prev => ({ ...prev, salary: e.target.value }))}
                    min="0"
                    step="1000"
                    style={{ width: '100%', padding: '12px', border: '1px solid #d1d5db', borderRadius: '8px', boxSizing: 'border-box' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Date d'embauche</label>
                  <input
                    type="date"
                    value={formData.hire_date}
                    onChange={(e) => setFormData(prev => ({ ...prev, hire_date: e.target.value }))}
                    style={{ width: '100%', padding: '12px', border: '1px solid #d1d5db', borderRadius: '8px', boxSizing: 'border-box' }}
                  />
                </div>
              </div>

              <div style={{ display: 'flex', gap: '12px' }}>
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  style={{
                    flex: 1,
                    background: '#f3f4f6',
                    color: '#374151',
                    border: 'none',
                    padding: '14px',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    fontWeight: '600'
                  }}
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  style={{
                    flex: 1,
                    background: 'linear-gradient(135deg, #f59e0b, #d97706)',
                    color: 'white',
                    border: 'none',
                    padding: '14px',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    fontWeight: '700'
                  }}
                >
                  {editingEmployee ? '💾 Enregistrer' : '➕ Ajouter'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

const ExpensesPage = () => {
  const [expenses, setExpenses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingExpense, setEditingExpense] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [formData, setFormData] = useState({
    category: '',
    amount: '',
    description: '',
    date: new Date().toISOString().split('T')[0],
    receipt_url: ''
  });

  useEffect(() => {
    fetchExpenses();
  }, []);

  const fetchExpenses = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/expenses`);
      setExpenses(response.data);
    } catch (error) {
      setError('Erreur lors du chargement des dépenses');
    } finally {
      setLoading(false);
    }
  };

  const openModal = (expense = null) => {
    if (expense) {
      setEditingExpense(expense);
      setFormData({
        category: expense.category,
        amount: expense.amount,
        description: expense.description,
        date: expense.date?.split('T')[0] || new Date().toISOString().split('T')[0],
        receipt_url: expense.receipt_url || ''
      });
    } else {
      setEditingExpense(null);
      setFormData({
        category: '',
        amount: '',
        description: '',
        date: new Date().toISOString().split('T')[0],
        receipt_url: ''
      });
    }
    setShowModal(true);
  };

  const handleFileUpload = (file) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      setFormData(prev => ({ ...prev, receipt_url: e.target.result }));
    };
    reader.readAsDataURL(file);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    try {
      if (editingExpense) {
        await axios.put(`${BACKEND_URL}/api/expenses/${editingExpense.id}`, formData);
        setSuccess('Dépense modifiée avec succès');
      } else {
        await axios.post(`${BACKEND_URL}/api/expenses`, formData);
        setSuccess('Dépense ajoutée avec succès');
      }
      setShowModal(false);
      fetchExpenses();
    } catch (error) {
      setError(error.response?.data?.detail || 'Erreur lors de la sauvegarde');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Êtes-vous sûr de vouloir supprimer cette dépense ?')) return;
    try {
      await axios.delete(`${BACKEND_URL}/api/expenses/${id}`);
      setSuccess('Dépense supprimée');
      fetchExpenses();
    } catch (error) {
      setError('Erreur lors de la suppression');
    }
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('fr-CA', { style: 'currency', currency: 'CAD' }).format(amount || 0);
  };

  if (loading) return <div style={{ textAlign: 'center', padding: '60px' }}>Chargement...</div>;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
        <div>
          <h1 style={{ fontSize: '32px', fontWeight: '800', margin: '0 0 8px 0' }}>💳 Dépenses</h1>
          <p style={{ color: '#6b7280', margin: 0 }}>Gérez vos dépenses professionnelles</p>
        </div>
        <button
          onClick={() => openModal()}
          style={{
            background: 'linear-gradient(135deg, #ec4899, #be185d)',
            color: 'white',
            border: 'none',
            padding: '14px 28px',
            borderRadius: '12px',
            cursor: 'pointer',
            fontWeight: '700',
            fontSize: '15px',
            boxShadow: '0 4px 12px rgba(236,72,153,0.4)'
          }}
        >
          ➕ Nouvelle Dépense
        </button>
      </div>

      {error && (
        <div style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#991b1b', padding: '16px', borderRadius: '8px', marginBottom: '20px' }}>
          {error}
        </div>
      )}
      {success && (
        <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', color: '#166534', padding: '16px', borderRadius: '8px', marginBottom: '20px' }}>
          {success}
        </div>
      )}

      <div style={{ background: 'white', border: '1px solid #e2e8f0', borderRadius: '12px', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead style={{ background: '#f8fafc' }}>
            <tr>
              <th style={{ padding: '16px', textAlign: 'left', fontWeight: '600', color: '#374151' }}>Date</th>
              <th style={{ padding: '16px', textAlign: 'left', fontWeight: '600', color: '#374151' }}>Catégorie</th>
              <th style={{ padding: '16px', textAlign: 'left', fontWeight: '600', color: '#374151' }}>Description</th>
              <th style={{ padding: '16px', textAlign: 'right', fontWeight: '600', color: '#374151' }}>Montant</th>
              <th style={{ padding: '16px', textAlign: 'center', fontWeight: '600', color: '#374151' }}>Justificatif</th>
              <th style={{ padding: '16px', textAlign: 'center', fontWeight: '600', color: '#374151' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {expenses.length === 0 ? (
              <tr>
                <td colSpan="6" style={{ padding: '40px', textAlign: 'center', color: '#9ca3af' }}>
                  Aucune dépense. Ajoutez-en une pour commencer !
                </td>
              </tr>
            ) : (
              expenses.map(expense => (
                <tr key={expense.id} style={{ borderTop: '1px solid #e5e7eb' }}>
                  <td style={{ padding: '16px' }}>{new Date(expense.date).toLocaleDateString('fr-FR')}</td>
                  <td style={{ padding: '16px', fontWeight: '600' }}>{expense.category}</td>
                  <td style={{ padding: '16px', color: '#6b7280' }}>{expense.description}</td>
                  <td style={{ padding: '16px', textAlign: 'right', fontWeight: '600', color: '#ef4444' }}>
                    {formatCurrency(expense.amount)}
                  </td>
                  <td style={{ padding: '16px', textAlign: 'center' }}>
                    {expense.receipt_url ? (
                      <a href={expense.receipt_url} target="_blank" rel="noopener noreferrer" style={{ color: '#3b82f6' }}>
                        📎 Voir
                      </a>
                    ) : (
                      <span style={{ color: '#9ca3af' }}>-</span>
                    )}
                  </td>
                  <td style={{ padding: '16px', textAlign: 'center' }}>
                    <button
                      onClick={() => openModal(expense)}
                      style={{ background: '#ec4899', color: 'white', border: 'none', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer', marginRight: '8px' }}
                    >
                      ✏️
                    </button>
                    <button
                      onClick={() => handleDelete(expense.id)}
                      style={{ background: '#ef4444', color: 'white', border: 'none', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer' }}
                    >
                      🗑️
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0, 0, 0, 0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }} onClick={() => setShowModal(false)}>
          <div
            style={{
              background: 'white',
              borderRadius: '16px',
              width: '100%',
              maxWidth: '600px',
              padding: '32px'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h2 style={{ margin: '0 0 24px 0', fontSize: '24px', fontWeight: '700' }}>
              {editingExpense ? '✏️ Modifier la dépense' : '➕ Nouvelle dépense'}
            </h2>

            <form onSubmit={handleSubmit}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Catégorie *</label>
                  <select
                    value={formData.category}
                    onChange={(e) => setFormData(prev => ({ ...prev, category: e.target.value }))}
                    required
                    style={{ width: '100%', padding: '12px', border: '1px solid #d1d5db', borderRadius: '8px', boxSizing: 'border-box' }}
                  >
                    <option value="">Sélectionner</option>
                    <option value="Bureau">Bureau</option>
                    <option value="Déplacement">Déplacement</option>
                    <option value="Repas">Repas</option>
                    <option value="Matériel">Matériel</option>
                    <option value="Logiciel">Logiciel</option>
                    <option value="Formation">Formation</option>
                    <option value="Autre">Autre</option>
                  </select>
                </div>
                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Montant *</label>
                  <input
                    type="number"
                    value={formData.amount}
                    onChange={(e) => setFormData(prev => ({ ...prev, amount: e.target.value }))}
                    required
                    min="0"
                    step="0.01"
                    style={{ width: '100%', padding: '12px', border: '1px solid #d1d5db', borderRadius: '8px', boxSizing: 'border-box' }}
                  />
                </div>
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Date *</label>
                <input
                  type="date"
                  value={formData.date}
                  onChange={(e) => setFormData(prev => ({ ...prev, date: e.target.value }))}
                  required
                  style={{ width: '100%', padding: '12px', border: '1px solid #d1d5db', borderRadius: '8px', boxSizing: 'border-box' }}
                />
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Description *</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                  required
                  rows="3"
                  style={{ width: '100%', padding: '12px', border: '1px solid #d1d5db', borderRadius: '8px', resize: 'vertical', fontFamily: 'inherit', boxSizing: 'border-box' }}
                />
              </div>

              <div style={{ marginBottom: '24px' }}>
                <label style={{ display: 'block', marginBottom: '8px', fontWeight: '600' }}>Justificatif (reçu, facture)</label>
                <div
                  onDragOver={(e) => {
                    e.preventDefault();
                    e.currentTarget.style.borderColor = '#ec4899';
                    e.currentTarget.style.background = '#fdf2f8';
                  }}
                  onDragLeave={(e) => {
                    e.currentTarget.style.borderColor = '#d1d5db';
                    e.currentTarget.style.background = '#f9fafb';
                  }}
                  onDrop={(e) => {
                    e.preventDefault();
                    e.currentTarget.style.borderColor = '#d1d5db';
                    e.currentTarget.style.background = '#f9fafb';
                    const file = e.dataTransfer.files[0];
                    if (file && (file.type.startsWith('image/') || file.type === 'application/pdf')) {
                      handleFileUpload(file);
                    }
                  }}
                  style={{
                    border: '2px dashed #d1d5db',
                    borderRadius: '8px',
                    padding: '24px',
                    textAlign: 'center',
                    background: '#f9fafb',
                    cursor: 'pointer'
                  }}
                >
                  <input
                    type="file"
                    accept="image/*,application/pdf"
                    onChange={(e) => {
                      const file = e.target.files[0];
                      if (file) handleFileUpload(file);
                    }}
                    style={{ display: 'none' }}
                    id="receipt-upload"
                  />
                  
                  {!formData.receipt_url ? (
                    <label htmlFor="receipt-upload" style={{ cursor: 'pointer', display: 'block' }}>
                      <div style={{ fontSize: '32px', marginBottom: '8px' }}>📎</div>
                      <div style={{ fontSize: '14px', fontWeight: '600', color: '#374151' }}>
                        Glissez-déposez ou cliquez pour sélectionner
                      </div>
                      <div style={{ fontSize: '12px', color: '#6b7280', marginTop: '4px' }}>
                        PNG, JPG, PDF (max 5MB)
                      </div>
                    </label>
                  ) : (
                    <div>
                      <div style={{ fontSize: '32px', marginBottom: '8px' }}>✅</div>
                      <div style={{ fontSize: '14px', fontWeight: '600', color: '#10b981' }}>
                        Justificatif ajouté
                      </div>
                      <button
                        type="button"
                        onClick={() => setFormData(prev => ({ ...prev, receipt_url: '' }))}
                        style={{
                          background: '#ef4444',
                          color: 'white',
                          border: 'none',
                          padding: '6px 16px',
                          borderRadius: '6px',
                          cursor: 'pointer',
                          marginTop: '8px',
                          fontSize: '12px'
                        }}
                      >
                        🗑️ Retirer
                      </button>
                    </div>
                  )}
                </div>
              </div>

              <div style={{ display: 'flex', gap: '12px' }}>
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  style={{
                    flex: 1,
                    background: '#f3f4f6',
                    color: '#374151',
                    border: 'none',
                    padding: '14px',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    fontWeight: '600'
                  }}
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  style={{
                    flex: 1,
                    background: 'linear-gradient(135deg, #ec4899, #be185d)',
                    color: 'white',
                    border: 'none',
                    padding: '14px',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    fontWeight: '700'
                  }}
                >
                  {editingExpense ? '💾 Enregistrer' : '➕ Ajouter'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
const SettingsPage = () => {
  const [settings, setSettings] = useState({
    company_name: '', email: '', phone: '', address: '', city: '', postal_code: '', country: '',
    logo_url: '', primary_color: '#3B82F6', secondary_color: '#1F2937',
    gst_number: '', pst_number: '', hst_number: '', default_due_days: 30
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/settings/company`);
      setSettings({ ...settings, ...response.data });
    } catch (error) {
      setError('Erreur lors du chargement des paramètres');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError(''); setSuccess('');

    try {
      await axios.put(`${BACKEND_URL}/api/settings/company`, settings);
      setSuccess('Paramètres sauvegardés avec succès');
    } catch (error) {
      setError('Erreur lors de la sauvegarde');
    } finally {
      setSaving(false);
    }
  };

  const handleLogoSave = async () => {
    if (!settings.logo_url) {
      setError('Veuillez entrer une URL de logo');
      return;
    }

    try {
      await axios.post(`${BACKEND_URL}/api/settings/company/upload-logo`, {
        logo_url: settings.logo_url
      });
      setSuccess('Logo sauvegardé avec succès');
    } catch (error) {
      setError('Erreur lors de la sauvegarde du logo');
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '60px' }}>
        <div style={{ fontSize: '48px', marginBottom: '16px' }}>⏳</div>
        <p>Chargement des paramètres...</p>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
          <div style={{ fontSize: '32px', marginRight: '12px' }}>⚙️</div>
          <h1 style={{ fontSize: '32px', fontWeight: '800', color: '#1f2937', margin: 0 }}>Paramètres</h1>
        </div>
        <p style={{ color: '#6b7280', margin: 0 }}>Configuration de votre entreprise</p>
      </div>

      {/* Messages */}
      {error && (
        <div style={{
          background: '#fef2f2', border: '1px solid #fecaca',
          color: '#b91c1c', padding: '16px', borderRadius: '12px', marginBottom: '20px'
        }}>{error}</div>
      )}
      {success && (
        <div style={{
          background: '#f0fdf4', border: '1px solid #bbf7d0',
          color: '#166534', padding: '16px', borderRadius: '12px', marginBottom: '20px'
        }}>{success}</div>
      )}

      <form onSubmit={handleSubmit}>
        {/* Logo Section */}
        <div style={{
          background: 'white', border: '1px solid #e2e8f0',
          borderRadius: '12px', padding: '24px', marginBottom: '24px'
        }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: '700' }}>🖼️ Logo de l'entreprise</h3>
          
          <div
            onDragOver={(e) => {
              e.preventDefault();
              e.currentTarget.style.borderColor = '#3b82f6';
              e.currentTarget.style.background = '#eff6ff';
            }}
            onDragLeave={(e) => {
              e.currentTarget.style.borderColor = '#d1d5db';
              e.currentTarget.style.background = '#f9fafb';
            }}
            onDrop={async (e) => {
              e.preventDefault();
              e.currentTarget.style.borderColor = '#d1d5db';
              e.currentTarget.style.background = '#f9fafb';
              
              const file = e.dataTransfer.files[0];
              if (file && file.type.startsWith('image/')) {
                const reader = new FileReader();
                reader.onload = async (event) => {
                  const base64Logo = event.target.result;
                  setSettings(prev => ({ ...prev, logo_url: base64Logo }));
                  // Auto-save after upload
                  try {
                    await axios.post(`${BACKEND_URL}/api/settings/company/upload-logo`, {
                      logo_url: base64Logo
                    });
                    setSuccess('Logo téléchargé avec succès !');
                    setTimeout(() => setSuccess(''), 3000);
                  } catch (error) {
                    setError('Erreur lors du téléchargement du logo');
                  }
                };
                reader.readAsDataURL(file);
              }
            }}
            style={{
              border: '2px dashed #d1d5db',
              borderRadius: '12px',
              padding: '32px',
              textAlign: 'center',
              background: '#f9fafb',
              cursor: 'pointer',
              transition: 'all 0.2s',
              position: 'relative'
            }}
          >
            <input
              type="file"
              accept="image/*"
              onChange={async (e) => {
                const file = e.target.files[0];
                if (file) {
                  const reader = new FileReader();
                  reader.onload = async (event) => {
                    const base64Logo = event.target.result;
                    setSettings(prev => ({ ...prev, logo_url: base64Logo }));
                    // Auto-save after upload
                    try {
                      await axios.post(`${BACKEND_URL}/api/settings/company/upload-logo`, {
                        logo_url: base64Logo
                      });
                      setSuccess('Logo téléchargé avec succès !');
                      setTimeout(() => setSuccess(''), 3000);
                    } catch (error) {
                      setError('Erreur lors du téléchargement du logo');
                    }
                  };
                  reader.readAsDataURL(file);
                }
              }}
              style={{ display: 'none' }}
              id="logo-upload"
            />
            
            {!settings.logo_url ? (
              <label htmlFor="logo-upload" style={{ cursor: 'pointer', display: 'block' }}>
                <div style={{ fontSize: '48px', marginBottom: '12px' }}>📤</div>
                <div style={{ fontSize: '16px', fontWeight: '600', color: '#374151', marginBottom: '8px' }}>
                  Glissez-déposez votre logo ici
                </div>
                <div style={{ fontSize: '14px', color: '#6b7280' }}>
                  ou cliquez pour sélectionner un fichier
                </div>
                <div style={{ fontSize: '12px', color: '#9ca3af', marginTop: '8px' }}>
                  PNG, JPG, SVG (max 2MB)
                </div>
              </label>
            ) : (
              <div>
                <img
                  src={settings.logo_url}
                  alt="Logo"
                  style={{
                    maxWidth: '200px',
                    maxHeight: '120px',
                    objectFit: 'contain',
                    border: '1px solid #e5e7eb',
                    borderRadius: '8px',
                    marginBottom: '16px'
                  }}
                  onError={() => setError('Impossible de charger l\'image à cette URL')}
                />
                <br />
                <label htmlFor="logo-upload" style={{
                  display: 'inline-block',
                  background: '#3b82f6',
                  color: 'white',
                  padding: '10px 20px',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  fontWeight: '600',
                  fontSize: '14px'
                }}>
                  🔄 Changer le logo
                </label>
                <button
                  type="button"
                  onClick={() => {
                    setSettings(prev => ({ ...prev, logo_url: '' }));
                    axios.post(`${BACKEND_URL}/api/settings/company/upload-logo`, { logo_url: '' });
                  }}
                  style={{
                    background: '#ef4444',
                    color: 'white',
                    border: 'none',
                    padding: '10px 20px',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    fontWeight: '600',
                    fontSize: '14px',
                    marginLeft: '12px'
                  }}
                >
                  🗑️ Supprimer
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Company Info */}
        <div style={{
          background: 'white', border: '1px solid #e2e8f0',
          borderRadius: '12px', padding: '24px', marginBottom: '24px'
        }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: '700' }}>🏢 Informations de l'entreprise</h3>
          
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Nom de l'entreprise *</label>
              <input
                type="text"
                value={settings.company_name}
                onChange={(e) => setSettings(prev => ({ ...prev, company_name: e.target.value }))}
                required
                style={{
                  width: '100%', padding: '12px', border: '1px solid #d1d5db',
                  borderRadius: '8px', boxSizing: 'border-box'
                }}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Email *</label>
              <input
                type="email"
                value={settings.email}
                onChange={(e) => setSettings(prev => ({ ...prev, email: e.target.value }))}
                required
                style={{
                  width: '100%', padding: '12px', border: '1px solid #d1d5db',
                  borderRadius: '8px', boxSizing: 'border-box'
                }}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Téléphone</label>
              <input
                type="tel"
                value={settings.phone || ''}
                onChange={(e) => setSettings(prev => ({ ...prev, phone: e.target.value }))}
                placeholder="(514) 555-1234"
                style={{
                  width: '100%', padding: '12px', border: '1px solid #d1d5db',
                  borderRadius: '8px', boxSizing: 'border-box'
                }}
              />
            </div>
            <div style={{ gridColumn: '1 / -1' }}>
              <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Adresse complète</label>
              <input
                type="text"
                value={settings.address || ''}
                onChange={(e) => setSettings(prev => ({ ...prev, address: e.target.value }))}
                placeholder="123 Rue Principale"
                style={{
                  width: '100%', padding: '12px', border: '1px solid #d1d5db',
                  borderRadius: '8px', boxSizing: 'border-box'
                }}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Ville</label>
              <input
                type="text"
                value={settings.city || ''}
                onChange={(e) => setSettings(prev => ({ ...prev, city: e.target.value }))}
                placeholder="Montréal"
                style={{
                  width: '100%', padding: '12px', border: '1px solid #d1d5db',
                  borderRadius: '8px', boxSizing: 'border-box'
                }}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Code postal</label>
              <input
                type="text"
                value={settings.postal_code || ''}
                onChange={(e) => setSettings(prev => ({ ...prev, postal_code: e.target.value }))}
                placeholder="H1A 1A1"
                style={{
                  width: '100%', padding: '12px', border: '1px solid #d1d5db',
                  borderRadius: '8px', boxSizing: 'border-box'
                }}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Pays</label>
              <input
                type="text"
                value={settings.country || ''}
                onChange={(e) => setSettings(prev => ({ ...prev, country: e.target.value }))}
                placeholder="Canada"
                style={{
                  width: '100%', padding: '12px', border: '1px solid #d1d5db',
                  borderRadius: '8px', boxSizing: 'border-box'
                }}
              />
            </div>
          </div>
        </div>

        {/* Tax Numbers */}
        <div style={{
          background: 'white', border: '1px solid #e2e8f0',
          borderRadius: '12px', padding: '24px', marginBottom: '24px'
        }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: '700' }}>📊 Numéros de taxes canadiens</h3>
          
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '16px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>TPS (Fédéral)</label>
              <input
                type="text"
                value={settings.gst_number || ''}
                onChange={(e) => setSettings(prev => ({ ...prev, gst_number: e.target.value }))}
                placeholder="123456789 RT0001"
                style={{
                  width: '100%', padding: '12px', border: '1px solid #d1d5db',
                  borderRadius: '8px', boxSizing: 'border-box'
                }}
              />
              <p style={{ fontSize: '12px', color: '#6b7280', marginTop: '4px' }}>
                Ex: 123456789 RT0001
              </p>
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>TVQ (Québec)</label>
              <input
                type="text"
                value={settings.pst_number || ''}
                onChange={(e) => setSettings(prev => ({ ...prev, pst_number: e.target.value }))}
                placeholder="1234567890 TQ0001"
                style={{
                  width: '100%', padding: '12px', border: '1px solid #d1d5db',
                  borderRadius: '8px', boxSizing: 'border-box'
                }}
              />
              <p style={{ fontSize: '12px', color: '#6b7280', marginTop: '4px' }}>
                Ex: 1234567890 TQ0001
              </p>
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>HST (Ontario)</label>
              <input
                type="text"
                value={settings.hst_number || ''}
                onChange={(e) => setSettings(prev => ({ ...prev, hst_number: e.target.value }))}
                placeholder="123456789 RT0001"
                style={{
                  width: '100%', padding: '12px', border: '1px solid #d1d5db',
                  borderRadius: '8px', boxSizing: 'border-box'
                }}
              />
              <p style={{ fontSize: '12px', color: '#6b7280', marginTop: '4px' }}>
                Ex: 123456789 RT0001
              </p>
            </div>
          </div>
        </div>

        {/* Brand Colors */}
        <div style={{
          background: 'white', border: '1px solid #e2e8f0',
          borderRadius: '12px', padding: '24px', marginBottom: '24px'
        }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: '700' }}>🎨 Couleurs de marque</h3>
          
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Couleur principale</label>
              <p style={{ fontSize: '12px', color: '#6b7280', marginBottom: '8px' }}>
                Utilisée dans les factures et soumissions
              </p>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <input
                  type="color"
                  value={settings.primary_color || '#3B82F6'}
                  onChange={(e) => setSettings(prev => ({ ...prev, primary_color: e.target.value }))}
                  style={{
                    width: '80px',
                    height: '50px',
                    border: '2px solid #e2e8f0',
                    borderRadius: '8px',
                    cursor: 'pointer'
                  }}
                />
                <div>
                  <p style={{ margin: 0, fontWeight: '600', color: settings.primary_color || '#3B82F6' }}>
                    {settings.primary_color || '#3B82F6'}
                  </p>
                  <p style={{ margin: 0, fontSize: '12px', color: '#6b7280' }}>
                    Factures & Soumissions
                  </p>
                </div>
              </div>
            </div>
            
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Couleur secondaire</label>
              <p style={{ fontSize: '12px', color: '#6b7280', marginBottom: '8px' }}>
                Pour les accents et boutons
              </p>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <input
                  type="color"
                  value={settings.secondary_color || '#1F2937'}
                  onChange={(e) => setSettings(prev => ({ ...prev, secondary_color: e.target.value }))}
                  style={{
                    width: '80px',
                    height: '50px',
                    border: '2px solid #e2e8f0',
                    borderRadius: '8px',
                    cursor: 'pointer'
                  }}
                />
                <div>
                  <p style={{ margin: 0, fontWeight: '600', color: settings.secondary_color || '#1F2937' }}>
                    {settings.secondary_color || '#1F2937'}
                  </p>
                  <p style={{ margin: 0, fontSize: '12px', color: '#6b7280' }}>
                    Textes & accents
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Save Button */}
        <div style={{ textAlign: 'center' }}>
          <button
            type="submit"
            disabled={saving}
            style={{
              background: saving ? '#9ca3af' : 'linear-gradient(135deg, #10b981, #047857)',
              color: 'white', border: 'none', padding: '16px 32px',
              borderRadius: '12px', cursor: saving ? 'not-allowed' : 'pointer',
              fontSize: '16px', fontWeight: '700'
            }}
          >
            {saving ? 'Sauvegarde...' : '💾 Sauvegarder tous les paramètres'}
          </button>
        </div>
      </form>
    </div>
  );
};

// Change Password Page
const ChangePasswordPage = () => {
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (newPassword !== confirmPassword) {
      setError('Les mots de passe ne correspondent pas');
      return;
    }

    if (newPassword.length < 6) {
      setError('Le mot de passe doit contenir au moins 6 caractères');
      return;
    }

    setLoading(true);

    try {
      await axios.post(`${BACKEND_URL}/api/auth/change-password`, {
        old_password: oldPassword,
        new_password: newPassword
      });

      setSuccess('Mot de passe modifié avec succès !');
      setOldPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (error) {
      setError(error.response?.data?.detail || 'Erreur lors du changement de mot de passe');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '600px', margin: '0 auto' }}>
      <h1 style={{ fontSize: '32px', fontWeight: '800', marginBottom: '24px' }}>🔒 Changer le mot de passe</h1>

      {error && (
        <div style={{
          background: '#fef2f2',
          border: '1px solid #fecaca',
          color: '#991b1b',
          padding: '16px',
          borderRadius: '8px',
          marginBottom: '20px'
        }}>
          {error}
        </div>
      )}

      {success && (
        <div style={{
          background: '#f0fdf4',
          border: '1px solid #bbf7d0',
          color: '#166534',
          padding: '16px',
          borderRadius: '8px',
          marginBottom: '20px'
        }}>
          {success}
        </div>
      )}

      <form onSubmit={handleSubmit} style={{
        background: 'white',
        border: '1px solid #e2e8f0',
        borderRadius: '12px',
        padding: '32px'
      }}>
        <div style={{ marginBottom: '24px' }}>
          <label style={{ display: 'block', marginBottom: '8px', fontWeight: '600' }}>
            Ancien mot de passe
          </label>
          <input
            type="password"
            value={oldPassword}
            onChange={(e) => setOldPassword(e.target.value)}
            required
            style={{
              width: '100%',
              padding: '12px',
              border: '1px solid #d1d5db',
              borderRadius: '8px',
              fontSize: '16px',
              boxSizing: 'border-box'
            }}
          />
        </div>

        <div style={{ marginBottom: '24px' }}>
          <label style={{ display: 'block', marginBottom: '8px', fontWeight: '600' }}>
            Nouveau mot de passe
          </label>
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            style={{
              width: '100%',
              padding: '12px',
              border: '1px solid #d1d5db',
              borderRadius: '8px',
              fontSize: '16px',
              boxSizing: 'border-box'
            }}
          />
        </div>

        <div style={{ marginBottom: '32px' }}>
          <label style={{ display: 'block', marginBottom: '8px', fontWeight: '600' }}>
            Confirmer le nouveau mot de passe
          </label>
          <input
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            style={{
              width: '100%',
              padding: '12px',
              border: '1px solid #d1d5db',
              borderRadius: '8px',
              fontSize: '16px',
              boxSizing: 'border-box'
            }}
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          style={{
            width: '100%',
            background: loading ? '#9ca3af' : '#3b82f6',
            color: 'white',
            border: 'none',
            padding: '16px',
            borderRadius: '8px',
            fontSize: '16px',
            fontWeight: '700',
            cursor: loading ? 'not-allowed' : 'pointer'
          }}
        >
          {loading ? 'Modification en cours...' : '🔐 Changer le mot de passe'}
        </button>
      </form>
    </div>
  );
};

// Billing Page
const BillingPage = () => {
  const { user } = useAuth();
  const [subscription, setSubscription] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchSubscription = async () => {
      try {
        const response = await axios.get(`${BACKEND_URL}/api/subscription/info`);
        setSubscription(response.data);
      } catch (error) {
        console.error('Error fetching subscription:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchSubscription();
  }, []);

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '60px' }}>
        <p>Chargement...</p>
      </div>
    );
  }

  const getStatusBadge = (status) => {
    const styles = {
      active: { background: '#dcfce7', color: '#166534', border: '1px solid #bbf7d0' },
      trial: { background: '#fef3c7', color: '#92400e', border: '1px solid #fde68a' },
      expired: { background: '#fee2e2', color: '#991b1b', border: '1px solid #fecaca' }
    };

    const labels = {
      active: '✅ Actif',
      trial: '⏳ Période d\'essai',
      expired: '❌ Expiré'
    };

    return (
      <span style={{
        ...styles[status],
        padding: '6px 16px',
        borderRadius: '20px',
        fontSize: '14px',
        fontWeight: '600',
        display: 'inline-block'
      }}>
        {labels[status]}
      </span>
    );
  };

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto' }}>
      <h1 style={{ fontSize: '32px', fontWeight: '800', marginBottom: '24px' }}>💳 Facturation</h1>

      {/* Current Subscription */}
      <div style={{
        background: 'white',
        border: '1px solid #e2e8f0',
        borderRadius: '12px',
        padding: '32px',
        marginBottom: '24px'
      }}>
        <h2 style={{ fontSize: '24px', fontWeight: '700', marginBottom: '20px' }}>Abonnement actuel</h2>

        <div style={{ marginBottom: '16px' }}>
          <p style={{ color: '#6b7280', marginBottom: '8px' }}>Statut</p>
          {getStatusBadge(subscription?.subscription_status)}
        </div>

        {subscription?.is_lifetime_free && (
          <div style={{
            background: 'linear-gradient(135deg, #fbbf24, #f59e0b)',
            color: 'white',
            padding: '20px',
            borderRadius: '8px',
            marginTop: '20px'
          }}>
            <h3 style={{ fontSize: '20px', fontWeight: '700', margin: '0 0 8px 0' }}>🎉 Accès Gratuit à Vie</h3>
            <p style={{ margin: 0 }}>Vous bénéficiez d'un accès illimité et gratuit à toutes les fonctionnalités !</p>
          </div>
        )}

        {subscription?.subscription_plan && !subscription?.is_lifetime_free && (
          <div style={{ marginTop: '20px' }}>
            <p style={{ color: '#6b7280', marginBottom: '8px' }}>Plan</p>
            <p style={{ fontSize: '20px', fontWeight: '700' }}>
              {subscription.subscription_plan === 'monthly' ? 'Mensuel - 15 $/mois' : 'Annuel - 162 $/an'}
            </p>
          </div>
        )}

        {subscription?.trial_end_date && (
          <div style={{ marginTop: '20px' }}>
            <p style={{ color: '#6b7280', marginBottom: '8px' }}>Fin de la période d'essai</p>
            <p style={{ fontSize: '18px', fontWeight: '600' }}>
              {new Date(subscription.trial_end_date).toLocaleDateString('fr-FR')}
            </p>
          </div>
        )}
      </div>

      {/* Plans Available */}
      {!subscription?.is_lifetime_free && subscription?.subscription_status === 'trial' && (
        <div style={{
          background: 'white',
          border: '1px solid #e2e8f0',
          borderRadius: '12px',
          padding: '32px'
        }}>
          <h2 style={{ fontSize: '24px', fontWeight: '700', marginBottom: '20px' }}>Plans disponibles</h2>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
            {/* Monthly Plan */}
            <div style={{
              border: '2px solid #e2e8f0',
              borderRadius: '12px',
              padding: '24px',
              textAlign: 'center'
            }}>
              <h3 style={{ fontSize: '20px', fontWeight: '700', marginBottom: '12px' }}>Mensuel</h3>
              <p style={{ fontSize: '32px', fontWeight: '800', color: '#3b82f6', margin: '16px 0' }}>
                15 $<span style={{ fontSize: '16px', fontWeight: '400' }}>/mois</span>
              </p>
              <p style={{ color: '#6b7280', marginBottom: '20px' }}>Sans engagement</p>
              <button style={{
                width: '100%',
                background: '#3b82f6',
                color: 'white',
                border: 'none',
                padding: '12px',
                borderRadius: '8px',
                cursor: 'pointer',
                fontWeight: '600'
              }}>
                Choisir
              </button>
            </div>

            {/* Yearly Plan */}
            <div style={{
              border: '2px solid #10b981',
              borderRadius: '12px',
              padding: '24px',
              textAlign: 'center',
              position: 'relative'
            }}>
              <div style={{
                position: 'absolute',
                top: '-12px',
                right: '20px',
                background: '#10b981',
                color: 'white',
                padding: '4px 12px',
                borderRadius: '12px',
                fontSize: '12px',
                fontWeight: '700'
              }}>
                ÉCONOMISEZ 10%
              </div>
              <h3 style={{ fontSize: '20px', fontWeight: '700', marginBottom: '12px' }}>Annuel</h3>
              <p style={{ fontSize: '32px', fontWeight: '800', color: '#10b981', margin: '16px 0' }}>
                162 $<span style={{ fontSize: '16px', fontWeight: '400' }}>/an</span>
              </p>
              <p style={{ color: '#6b7280', marginBottom: '20px' }}>13.50 $/mois</p>
              <button style={{
                width: '100%',
                background: '#10b981',
                color: 'white',
                border: 'none',
                padding: '12px',
                borderRadius: '8px',
                cursor: 'pointer',
                fontWeight: '600'
              }}>
                Choisir
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const ExportPage = () => {
  const [dataType, setDataType] = useState('invoices');
  const [format, setFormat] = useState('csv');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleExport = async () => {
    setError('');
    setSuccess('');
    setLoading(true);

    try {
      const response = await axios.get(`${BACKEND_URL}/api/${dataType}`, {
        params: { start_date: startDate, end_date: endDate }
      });
      
      const data = response.data;
      
      if (data.length === 0) {
        setError('Aucune donnée à exporter pour cette période');
        setLoading(false);
        return;
      }

      if (format === 'csv') {
        // Export CSV
        const headers = Object.keys(data[0]).filter(key => key !== '_id' && key !== 'user_id');
        const csvContent = [
          headers.join(','),
          ...data.map(row => headers.map(h => `"${row[h] || ''}"`).join(','))
        ].join('\n');

        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `${dataType}_${new Date().toISOString().split('T')[0]}.csv`;
        link.click();
        setSuccess(`Fichier CSV téléchargé avec succès (${data.length} éléments)`);
      } else if (format === 'pdf') {
        // Export PDF - Simple HTML to PDF conversion
        const headers = Object.keys(data[0]).filter(key => key !== '_id' && key !== 'user_id');
        
        // Create HTML content for PDF
        let htmlContent = `
          <html>
            <head>
              <meta charset="utf-8">
              <style>
                body { font-family: Arial, sans-serif; padding: 20px; }
                h1 { color: #0d9488; margin-bottom: 20px; }
                table { width: 100%; border-collapse: collapse; margin-top: 20px; }
                th { background: #0d9488; color: white; padding: 12px; text-align: left; border: 1px solid #ddd; }
                td { padding: 10px; border: 1px solid #ddd; }
                tr:nth-child(even) { background-color: #f9fafb; }
                .header { margin-bottom: 30px; }
                .date { color: #6b7280; font-size: 14px; }
              </style>
            </head>
            <body>
              <div class="header">
                <h1>FacturePro - Export ${dataType}</h1>
                <p class="date">Généré le ${new Date().toLocaleDateString('fr-FR')} à ${new Date().toLocaleTimeString('fr-FR')}</p>
                <p>Nombre d'éléments: ${data.length}</p>
              </div>
              <table>
                <thead>
                  <tr>${headers.map(h => `<th>${h}</th>`).join('')}</tr>
                </thead>
                <tbody>
                  ${data.map(row => `<tr>${headers.map(h => `<td>${row[h] || '-'}</td>`).join('')}</tr>`).join('')}
                </tbody>
              </table>
            </body>
          </html>
        `;
        
        // Create a blob with HTML content
        const blob = new Blob([htmlContent], { type: 'text/html' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `${dataType}_${new Date().toISOString().split('T')[0]}.html`;
        link.click();
        setSuccess(`Document HTML téléchargé avec succès (${data.length} éléments) - Ouvrez-le et imprimez en PDF depuis votre navigateur`);
      }
    } catch (error) {
      setError(error.response?.data?.detail || 'Erreur lors de l\'export');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto' }}>
      <div style={{ marginBottom: '32px' }}>
        <h1 style={{ fontSize: '32px', fontWeight: '800', margin: '0 0 8px 0' }}>📊 Exports</h1>
        <p style={{ color: '#6b7280', margin: 0 }}>Exportez vos données en CSV ou PDF</p>
      </div>

      {error && (
        <div style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#991b1b', padding: '16px', borderRadius: '8px', marginBottom: '20px' }}>
          {error}
        </div>
      )}
      {success && (
        <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', color: '#166534', padding: '16px', borderRadius: '8px', marginBottom: '20px' }}>
          {success}
        </div>
      )}

      <div style={{ background: 'white', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '32px' }}>
        {/* Data Type Selection */}
        <div style={{ marginBottom: '24px' }}>
          <label style={{ display: 'block', marginBottom: '12px', fontWeight: '600', fontSize: '16px' }}>
            📁 Type de données
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
            {[
              { value: 'invoices', label: '📄 Factures', icon: '📄' },
              { value: 'quotes', label: '📝 Soumissions', icon: '📝' },
              { value: 'clients', label: '👥 Clients', icon: '👥' },
              { value: 'products', label: '📦 Produits', icon: '📦' },
              { value: 'employees', label: '👨‍💼 Employés', icon: '👨‍💼' },
              { value: 'expenses', label: '💳 Dépenses', icon: '💳' }
            ].map(type => (
              <button
                key={type.value}
                type="button"
                onClick={() => setDataType(type.value)}
                style={{
                  padding: '16px',
                  border: dataType === type.value ? '2px solid #3b82f6' : '1px solid #d1d5db',
                  background: dataType === type.value ? '#eff6ff' : 'white',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  textAlign: 'center',
                  fontWeight: '600',
                  fontSize: '14px'
                }}
              >
                <div style={{ fontSize: '24px', marginBottom: '4px' }}>{type.icon}</div>
                {type.label.replace(type.icon + ' ', '')}
              </button>
            ))}
          </div>
        </div>

        {/* Date Range */}
        <div style={{ marginBottom: '24px' }}>
          <label style={{ display: 'block', marginBottom: '12px', fontWeight: '600', fontSize: '16px' }}>
            📅 Période
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '14px', color: '#6b7280' }}>
                Date début
              </label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                style={{
                  width: '100%',
                  padding: '12px',
                  border: '1px solid #d1d5db',
                  borderRadius: '8px',
                  boxSizing: 'border-box'
                }}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontSize: '14px', color: '#6b7280' }}>
                Date fin
              </label>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                style={{
                  width: '100%',
                  padding: '12px',
                  border: '1px solid #d1d5db',
                  borderRadius: '8px',
                  boxSizing: 'border-box'
                }}
              />
            </div>
          </div>
          <p style={{ fontSize: '12px', color: '#6b7280', marginTop: '8px' }}>
            Laissez vide pour exporter toutes les données
          </p>
        </div>

        {/* Format Selection */}
        <div style={{ marginBottom: '32px' }}>
          <label style={{ display: 'block', marginBottom: '12px', fontWeight: '600', fontSize: '16px' }}>
            💾 Format d'export
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <button
              type="button"
              onClick={() => setFormat('csv')}
              style={{
                padding: '16px',
                border: format === 'csv' ? '2px solid #10b981' : '1px solid #d1d5db',
                background: format === 'csv' ? '#f0fdf4' : 'white',
                borderRadius: '8px',
                cursor: 'pointer',
                textAlign: 'left',
                fontWeight: '600'
              }}
            >
              <div style={{ fontSize: '24px', marginBottom: '4px' }}>📊</div>
              <div>CSV (Excel)</div>
              <div style={{ fontSize: '12px', color: '#6b7280', fontWeight: '400' }}>
                Compatible avec Excel, Google Sheets
              </div>
            </button>
            <button
              type="button"
              onClick={() => setFormat('pdf')}
              style={{
                padding: '16px',
                border: format === 'pdf' ? '2px solid #10b981' : '1px solid #d1d5db',
                background: format === 'pdf' ? '#f0fdf4' : 'white',
                borderRadius: '8px',
                cursor: 'pointer',
                textAlign: 'left',
                fontWeight: '600'
              }}
            >
              <div style={{ fontSize: '24px', marginBottom: '4px' }}>📄</div>
              <div>PDF</div>
              <div style={{ fontSize: '12px', color: '#6b7280', fontWeight: '400' }}>
                Format universel pour documents
              </div>
            </button>
          </div>
        </div>

        {/* Export Button */}
        <button
          onClick={handleExport}
          disabled={loading}
          style={{
            width: '100%',
            background: loading ? '#9ca3af' : 'linear-gradient(135deg, #10b981, #059669)',
            color: 'white',
            border: 'none',
            padding: '18px',
            borderRadius: '12px',
            cursor: loading ? 'not-allowed' : 'pointer',
            fontWeight: '700',
            fontSize: '16px',
            boxShadow: loading ? 'none' : '0 4px 12px rgba(16,185,129,0.4)'
          }}
        >
          {loading ? '⏳ Export en cours...' : '📥 Exporter les données'}
        </button>

        {/* Info Box */}
        <div style={{
          marginTop: '24px',
          padding: '16px',
          background: '#f0f9ff',
          border: '1px solid #bae6fd',
          borderRadius: '8px'
        }}>
          <p style={{ margin: 0, fontSize: '14px', color: '#0369a1' }}>
            💡 <strong>Astuce :</strong> Les exports CSV peuvent être ouverts dans Excel ou Google Sheets. Les exports PDF génèrent un fichier HTML que vous pouvez imprimer en PDF depuis votre navigateur.
          </p>
        </div>
      </div>
    </div>
  );
};

// Main App with Provider
function AppWithAuth() {
  return (
    <AuthProvider>
      <App />
    </AuthProvider>
  );
}

export default AppWithAuth;