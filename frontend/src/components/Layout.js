import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { BACKEND_URL, FACTUREPRO_LOGO_FILE_ID } from '../config';
import NotificationsDropdown from './NotificationsDropdown';
import {
  LayoutDashboard, Users, Package, FileText, FilePen,
  UserCheck, Receipt, Download, Settings, Gem,
  LogOut, Search, Bell
} from 'lucide-react';

const getImageUrl = (url) => {
  if (!url) return null;
  if (url.startsWith('/api')) return `${BACKEND_URL}${url}`;
  if (url.startsWith('http')) return url;
  return null;
};

const factureProLogoUrl = `${BACKEND_URL}/api/files/${FACTUREPRO_LOGO_FILE_ID}`;

const Layout = ({ currentRoute, navigate, children, needsSubscription }) => {
  const { user, logout } = useAuth();
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [settings, setSettings] = useState(null);

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
    { name: 'Tableau de bord', href: '/dashboard', icon: LayoutDashboard, current: currentRoute === '/dashboard' },
    { name: 'Clients', href: '/clients', icon: Users, current: currentRoute === '/clients' },
    { name: 'Produits', href: '/products', icon: Package, current: currentRoute === '/products' },
    { name: 'Factures', href: '/invoices', icon: FileText, current: currentRoute === '/invoices' },
    { name: 'Soumissions', href: '/quotes', icon: FilePen, current: currentRoute === '/quotes' },
    { name: 'Employes', href: '/employees', icon: UserCheck, current: currentRoute === '/employees' },
    { name: 'Depenses', href: '/expenses', icon: Receipt, current: currentRoute === '/expenses' },
    { name: 'Exports', href: '/export', icon: Download, current: currentRoute === '/export' },
    { name: 'Parametres', href: '/settings', icon: Settings, current: currentRoute === '/settings' },
    { name: 'Abonnement', href: '/subscription', icon: Gem, current: currentRoute === '/subscription' },
  ];

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: '#f8fafc' }}>
      {/* Sidebar */}
      <aside style={{
        width: '280px',
        background: 'linear-gradient(180deg, #1e293b 0%, #334155 100%)',
        boxShadow: '4px 0 6px -1px rgba(0, 0, 0, 0.1)',
        display: 'flex', flexDirection: 'column',
        flexShrink: 0
      }}>
        {/* Logo Section */}
        <div style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ width: '48px', height: '48px', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
              <img src={factureProLogoUrl} alt="FacturePro" style={{ width: '48px', height: '48px', objectFit: 'contain', borderRadius: '12px' }} />
            </div>
            <div>
              <div style={{ color: 'white', fontSize: '20px', fontWeight: '800' }}>FacturePro</div>
              <div style={{ color: '#94a3b8', fontSize: '12px' }}>Solution complete</div>
            </div>
          </div>
        </div>

        {/* Navigation Menu */}
        <nav style={{ padding: '0 16px', flex: 1, overflow: 'auto' }}>
          {navigation.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.name}
                data-testid={`nav-${item.href.replace('/', '')}`}
                onClick={() => navigate(item.href)}
                style={{
                  display: 'flex', alignItems: 'center', width: '100%',
                  padding: '14px 16px', margin: '4px 0',
                  background: item.current ? 'rgba(0, 160, 140, 0.2)' : 'transparent',
                  color: item.current ? '#47D2A7' : '#cbd5e1',
                  border: 'none', borderRadius: '10px', cursor: 'pointer',
                  fontSize: '15px', fontWeight: '600', transition: 'all 0.3s ease', textAlign: 'left'
                }}
                onMouseEnter={(e) => { if (!item.current) e.currentTarget.style.background = 'rgba(255,255,255,0.05)'; }}
                onMouseLeave={(e) => { if (!item.current) e.currentTarget.style.background = 'transparent'; }}
              >
                <Icon size={18} strokeWidth={1.8} style={{ marginRight: '14px', flexShrink: 0, opacity: item.current ? 1 : 0.7 }} />
                {item.name}
              </button>
            );
          })}
        </nav>

        {/* User Section */}
        <div style={{ padding: '20px', borderTop: '1px solid #334155' }}>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: '16px' }}>
            <div style={{
              width: '40px', height: '40px',
              background: settings?.logo_url ? 'white' : '#00A08C',
              borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', marginRight: '12px',
              overflow: 'hidden', border: settings?.logo_url ? '1px solid #475569' : 'none',
              flexShrink: 0
            }}>
              {getImageUrl(settings?.logo_url) ? (
                <img src={getImageUrl(settings.logo_url)} alt="Logo" style={{ width: '40px', height: '40px', objectFit: 'contain' }} />
              ) : (
                <span style={{ color: 'white', fontSize: '16px', fontWeight: '700' }}>
                  {user?.company_name?.charAt(0)?.toUpperCase() || 'U'}
                </span>
              )}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ color: 'white', fontSize: '14px', fontWeight: '600', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user?.company_name || 'Entreprise'}</div>
              <div style={{ color: '#94a3b8', fontSize: '12px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user?.email}</div>
            </div>
          </div>
          <button onClick={logout} data-testid="logout-btn" style={{
            width: '100%', padding: '10px 16px', background: '#ef4444', color: 'white',
            border: 'none', borderRadius: '8px', cursor: 'pointer', fontSize: '14px', fontWeight: '600',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px'
          }}>
            <LogOut size={16} strokeWidth={2} />
            Se deconnecter
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* Header */}
        <header style={{
          background: 'white', padding: '16px 32px',
          borderBottom: '1px solid #e2e8f0',
          boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ flex: 1 }}>
              <h1 style={{ fontSize: '22px', fontWeight: '700', color: '#1e293b', margin: 0 }}>
                {navigation.find(n => n.current)?.name || 'FacturePro'}
              </h1>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              {/* Search */}
              <div style={{ position: 'relative' }}>
                <input type="text" placeholder="Rechercher..." style={{
                  paddingLeft: '36px', paddingRight: '12px', paddingTop: '8px', paddingBottom: '8px',
                  border: '1px solid #e2e8f0', borderRadius: '8px', fontSize: '14px', width: '220px',
                  background: '#f8fafc', outline: 'none'
                }}
                onFocus={(e) => { e.target.style.borderColor = '#00A08C'; e.target.style.background = '#fff'; }}
                onBlur={(e) => { e.target.style.borderColor = '#e2e8f0'; e.target.style.background = '#f8fafc'; }}
                />
                <Search size={16} strokeWidth={1.8} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
              </div>

              {/* Notifications */}
              <div style={{ position: 'relative' }}>
                <button onClick={() => setNotificationsOpen(!notificationsOpen)} data-testid="notifications-btn" style={{
                  position: 'relative', background: 'none', border: '1px solid #e2e8f0', padding: '8px',
                  borderRadius: '8px', cursor: 'pointer', color: '#64748b', display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>
                  <Bell size={18} strokeWidth={1.8} />
                  <span style={{
                    position: 'absolute', top: '4px', right: '4px', width: '8px', height: '8px',
                    background: '#ef4444', borderRadius: '50%'
                  }} />
                </button>
                <NotificationsDropdown isOpen={notificationsOpen} onClose={() => setNotificationsOpen(false)} />
              </div>

              {/* User Badge */}
              <div style={{
                display: 'flex', alignItems: 'center', gap: '10px', padding: '6px 14px 6px 8px',
                borderRadius: '8px', border: '1px solid #e2e8f0', background: '#f8fafc'
              }}>
                <div style={{
                  width: '28px', height: '28px', background: settings?.logo_url ? '#fff' : '#00A08C',
                  borderRadius: '6px', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  overflow: 'hidden', border: settings?.logo_url ? '1px solid #e2e8f0' : 'none'
                }}>
                  {getImageUrl(settings?.logo_url) ? (
                    <img src={getImageUrl(settings.logo_url)} alt="Logo" style={{ width: '28px', height: '28px', objectFit: 'contain' }} />
                  ) : (
                    <span style={{ color: '#fff', fontSize: '12px', fontWeight: '700' }}>
                      {user?.company_name?.charAt(0)?.toUpperCase() || 'U'}
                    </span>
                  )}
                </div>
                <span style={{ fontSize: '14px', fontWeight: '600', color: '#1e293b' }}>{user?.company_name}</span>
              </div>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main style={{ padding: '24px 32px', flex: 1 }}>
          {needsSubscription && currentRoute !== '/subscription' && (
            <div data-testid="subscription-expired-banner" style={{
              background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '10px',
              padding: '14px 24px', marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center'
            }}>
              <span style={{ color: '#991b1b', fontWeight: '600', fontSize: '14px' }}>
                Votre essai gratuit a expire. Abonnez-vous pour continuer.
              </span>
              <button onClick={() => navigate('/subscription')} style={{
                background: '#00A08C', color: 'white', border: 'none', borderRadius: '8px',
                padding: '8px 20px', fontWeight: '600', cursor: 'pointer', fontSize: '13px'
              }}>S'abonner</button>
            </div>
          )}
          {user?.subscription_status === 'trial' && !user?.is_exempt && currentRoute !== '/subscription' && (
            <div data-testid="trial-banner" style={{
              background: '#fffbeb', border: '1px solid #fcd34d', borderRadius: '10px',
              padding: '12px 24px', marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center'
            }}>
              <span style={{ color: '#92400e', fontSize: '13px' }}>
                Essai gratuit — Profitez de toutes les fonctionnalites gratuitement pendant votre periode d'essai.
              </span>
              <button onClick={() => navigate('/subscription')} style={{
                background: 'transparent', color: '#92400e', border: '1px solid #f59e0b', borderRadius: '8px',
                padding: '6px 16px', fontWeight: '600', cursor: 'pointer', fontSize: '12px'
              }}>Voir les plans</button>
            </div>
          )}
          <div style={{ maxWidth: '1400px', margin: '0 auto' }}>{children}</div>
        </main>
      </div>
    </div>
  );
};

export default Layout;
