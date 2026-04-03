import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { BACKEND_URL, FACTUREPRO_LOGO_FILE_ID } from '../config';
import NotificationsDropdown from './NotificationsDropdown';
import {
  LayoutDashboard, Users, Package, FileText, FilePen,
  UserCheck, Receipt, Download, Settings, Gem,
  LogOut, Search, Bell, ChevronRight
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
    <div style={{ display: 'flex', minHeight: '100vh', background: '#f4f4f5' }}>
      {/* Sidebar */}
      <aside style={{
        width: '260px',
        background: '#fafafa',
        borderRight: '1px solid #e4e4e7',
        display: 'flex', flexDirection: 'column',
        flexShrink: 0
      }}>
        {/* Logo Section */}
        <div style={{ padding: '20px 20px 16px', borderBottom: '1px solid #e4e4e7' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ width: '36px', height: '36px', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', background: '#fff', border: '1px solid #e4e4e7' }}>
              <img src={factureProLogoUrl} alt="FacturePro" style={{ width: '36px', height: '36px', objectFit: 'contain' }} />
            </div>
            <div>
              <div style={{ color: '#09090b', fontSize: '16px', fontWeight: '700', letterSpacing: '-0.02em' }}>FacturePro</div>
              <div style={{ color: '#a1a1aa', fontSize: '11px', fontWeight: '500', letterSpacing: '0.05em', textTransform: 'uppercase' }}>Facturation</div>
            </div>
          </div>
        </div>

        {/* Navigation Menu */}
        <nav style={{ padding: '12px 10px', flex: 1, overflow: 'auto' }}>
          {navigation.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.name}
                data-testid={`nav-${item.href.replace('/', '')}`}
                onClick={() => navigate(item.href)}
                style={{
                  display: 'flex', alignItems: 'center', width: '100%',
                  padding: '9px 12px', margin: '1px 0',
                  background: item.current ? '#09090b' : 'transparent',
                  color: item.current ? '#ffffff' : '#52525b',
                  border: 'none', borderRadius: '6px', cursor: 'pointer',
                  fontSize: '13px', fontWeight: item.current ? '600' : '500',
                  transition: 'all 0.15s ease', textAlign: 'left',
                  letterSpacing: '-0.01em'
                }}
                onMouseEnter={(e) => { if (!item.current) { e.currentTarget.style.background = '#f4f4f5'; e.currentTarget.style.color = '#09090b'; } }}
                onMouseLeave={(e) => { if (!item.current) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = '#52525b'; } }}
              >
                <Icon size={17} strokeWidth={1.8} style={{ marginRight: '10px', flexShrink: 0 }} />
                {item.name}
                {item.current && <ChevronRight size={14} style={{ marginLeft: 'auto', opacity: 0.5 }} />}
              </button>
            );
          })}
        </nav>

        {/* User Section */}
        <div style={{ padding: '16px', borderTop: '1px solid #e4e4e7' }}>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: '12px' }}>
            <div style={{
              width: '32px', height: '32px',
              background: settings?.logo_url ? '#fff' : '#09090b',
              borderRadius: '6px', display: 'flex', alignItems: 'center', justifyContent: 'center', marginRight: '10px',
              overflow: 'hidden', border: '1px solid #e4e4e7', flexShrink: 0
            }}>
              {getImageUrl(settings?.logo_url) ? (
                <img src={getImageUrl(settings.logo_url)} alt="Logo" style={{ width: '32px', height: '32px', objectFit: 'contain' }} />
              ) : (
                <span style={{ color: '#fff', fontSize: '13px', fontWeight: '700' }}>
                  {user?.company_name?.charAt(0)?.toUpperCase() || 'U'}
                </span>
              )}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ color: '#09090b', fontSize: '13px', fontWeight: '600', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user?.company_name || 'Entreprise'}</div>
              <div style={{ color: '#a1a1aa', fontSize: '11px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user?.email}</div>
            </div>
          </div>
          <button onClick={logout} data-testid="logout-btn" style={{
            width: '100%', padding: '8px 12px', background: '#fff', color: '#dc2626',
            border: '1px solid #e4e4e7', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', fontWeight: '600',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
            transition: 'all 0.15s ease'
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = '#fef2f2'; e.currentTarget.style.borderColor = '#fecaca'; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = '#fff'; e.currentTarget.style.borderColor = '#e4e4e7'; }}
          >
            <LogOut size={14} strokeWidth={2} />
            Se deconnecter
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* Header */}
        <header style={{
          background: '#ffffff', padding: '14px 28px',
          borderBottom: '1px solid #e4e4e7'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ flex: 1 }}>
              <h1 style={{ fontSize: '20px', fontWeight: '700', color: '#09090b', margin: 0, letterSpacing: '-0.02em' }}>
                {navigation.find(n => n.current)?.name || 'FacturePro'}
              </h1>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {/* Search */}
              <div style={{ position: 'relative' }}>
                <input type="text" placeholder="Rechercher..." style={{
                  paddingLeft: '34px', paddingRight: '12px', paddingTop: '7px', paddingBottom: '7px',
                  border: '1px solid #e4e4e7', borderRadius: '6px', fontSize: '13px', width: '200px',
                  background: '#fafafa', outline: 'none'
                }}
                onFocus={(e) => { e.target.style.borderColor = '#09090b'; e.target.style.background = '#fff'; }}
                onBlur={(e) => { e.target.style.borderColor = '#e4e4e7'; e.target.style.background = '#fafafa'; }}
                />
                <Search size={15} strokeWidth={1.8} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: '#a1a1aa' }} />
              </div>

              {/* Notifications */}
              <div style={{ position: 'relative' }}>
                <button onClick={() => setNotificationsOpen(!notificationsOpen)} data-testid="notifications-btn" style={{
                  position: 'relative', background: 'none', border: '1px solid #e4e4e7', padding: '7px',
                  borderRadius: '6px', cursor: 'pointer', color: '#52525b', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  transition: 'all 0.15s ease'
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = '#f4f4f5'; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
                >
                  <Bell size={16} strokeWidth={1.8} />
                  <span style={{
                    position: 'absolute', top: '4px', right: '4px', width: '6px', height: '6px',
                    background: '#dc2626', borderRadius: '50%'
                  }} />
                </button>
                <NotificationsDropdown isOpen={notificationsOpen} onClose={() => setNotificationsOpen(false)} />
              </div>

              {/* User Badge */}
              <div style={{
                display: 'flex', alignItems: 'center', gap: '8px', padding: '5px 12px 5px 6px',
                borderRadius: '6px', border: '1px solid #e4e4e7'
              }}>
                <div style={{
                  width: '26px', height: '26px', background: settings?.logo_url ? '#fff' : '#09090b',
                  borderRadius: '4px', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  overflow: 'hidden', border: settings?.logo_url ? '1px solid #e4e4e7' : 'none'
                }}>
                  {getImageUrl(settings?.logo_url) ? (
                    <img src={getImageUrl(settings.logo_url)} alt="Logo" style={{ width: '26px', height: '26px', objectFit: 'contain' }} />
                  ) : (
                    <span style={{ color: '#fff', fontSize: '11px', fontWeight: '700' }}>
                      {user?.company_name?.charAt(0)?.toUpperCase() || 'U'}
                    </span>
                  )}
                </div>
                <span style={{ fontSize: '13px', fontWeight: '600', color: '#09090b' }}>{user?.company_name}</span>
              </div>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main style={{ padding: '24px 28px', flex: 1 }}>
          {needsSubscription && currentRoute !== '/subscription' && (
            <div data-testid="subscription-expired-banner" style={{
              background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '6px',
              padding: '12px 20px', marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center'
            }}>
              <span style={{ color: '#991b1b', fontWeight: '600', fontSize: '13px' }}>
                Votre essai gratuit a expire. Abonnez-vous pour continuer.
              </span>
              <button onClick={() => navigate('/subscription')} style={{
                background: '#09090b', color: '#fff', border: 'none', borderRadius: '6px',
                padding: '6px 16px', fontWeight: '600', cursor: 'pointer', fontSize: '12px',
                transition: 'all 0.15s ease'
              }}>S'abonner</button>
            </div>
          )}
          {user?.subscription_status === 'trial' && !user?.is_exempt && currentRoute !== '/subscription' && (
            <div data-testid="trial-banner" style={{
              background: '#fffbeb', border: '1px solid #fcd34d', borderRadius: '6px',
              padding: '10px 20px', marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center'
            }}>
              <span style={{ color: '#92400e', fontSize: '12px' }}>
                Essai gratuit — Profitez de toutes les fonctionnalites gratuitement pendant votre periode d'essai.
              </span>
              <button onClick={() => navigate('/subscription')} style={{
                background: 'transparent', color: '#92400e', border: '1px solid #f59e0b', borderRadius: '6px',
                padding: '5px 14px', fontWeight: '600', cursor: 'pointer', fontSize: '11px'
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
