import React, { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import Layout from './components/Layout';
import RouteGuard from './components/RouteGuard';
import LoginPage from './pages/LoginPage';
import Dashboard from './pages/Dashboard';
import ClientsPage from './pages/ClientsPage';
import ProductsPage from './pages/ProductsPage';
import InvoicesPage from './pages/InvoicesPage';
import QuotesPage from './pages/QuotesPage';
import EmployeesPage from './pages/EmployeesPage';
import ExpensesPage from './pages/ExpensesPage';
import ExportPage from './pages/ExportPage';
import SettingsPage from './pages/SettingsPage';
import SubscriptionPage from './pages/SubscriptionPage';
import ReportsPage from './pages/ReportsPage';
import BankReconciliationPage from './pages/BankReconciliationPage';
import LedgerPage from './pages/LedgerPage';
import AcceptInvitePage from './pages/AcceptInvitePage';
import { PrivacyPolicyPage, TermsPage } from './pages/LegalPages';
import MfaSettings from './components/MfaSettings';

function App() {
  const [currentRoute, setCurrentRoute] = useState(
    window.location.pathname === '/' ? '/dashboard' : window.location.pathname
  );
  const { isAuthenticated, user, logout } = useAuth();

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

  // Public routes — no auth required
  if (window.location.pathname === '/accept-invite') {
    return <AcceptInvitePage />;
  }
  // Pages légales publiques (Loi 25) — les liens de consentement pointent ici.
  if (window.location.pathname === '/privacy') {
    return <PrivacyPolicyPage />;
  }
  if (window.location.pathname === '/cgu') {
    return <TermsPage />;
  }

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  // Imposition MFA par l'org (Loi 25) : si l'organisation exige la 2FA et que ce membre ne l'a
  // pas encore activée, on bloque TOUT l'accès applicatif derrière un écran d'enrôlement forcé
  // (miroir de l'enforcement backend dans require_permission ; le compte de service is_exempt est
  // épargné pour éviter un lockout d'exploitation). Il ne reste que : activer la 2FA, ou se déconnecter.
  const needsMfaEnrollment = user?.require_mfa && !user?.mfa_enabled && !user?.is_exempt;
  if (needsMfaEnrollment) {
    return (
      <div style={{ minHeight: '100vh', background: '#f8fafb', display: 'flex',
        alignItems: 'center', justifyContent: 'center', padding: 20 }}>
        <div style={{ background: '#fff', borderRadius: 16, boxShadow: '0 10px 30px rgba(0,0,0,0.1)',
          padding: 32, maxWidth: 680, width: '100%' }}>
          <h2 style={{ color: '#1f2937', marginTop: 0 }}>Double authentification requise</h2>
          <p style={{ color: '#6b7280' }}>
            Ton organisation exige la double authentification pour protéger les données financières.
            Configure-la ci-dessous pour continuer.
          </p>
          <MfaSettings />
          <button onClick={logout} style={{ marginTop: 20, background: 'none', border: 'none',
            color: '#6b7280', cursor: 'pointer', fontSize: 14, textDecoration: 'underline' }}>
            Se déconnecter
          </button>
        </div>
      </div>
    );
  }

  // Subscription gating: if expired, only allow subscription page and settings
  const subStatus = user?.subscription_status;
  const needsSubscription = subStatus === 'expired';
  const allowedWhenExpired = ['/subscription', '/settings'];

  if (needsSubscription && !allowedWhenExpired.includes(currentRoute)) {
    // Redirect to subscription page
    if (currentRoute !== '/subscription') {
      window.history.replaceState({}, '', '/subscription');
      setCurrentRoute('/subscription');
    }
  }

  const renderPage = () => {
    if (needsSubscription && !allowedWhenExpired.includes(currentRoute)) {
      return <SubscriptionPage />;
    }
    switch (currentRoute) {
      case '/clients': return <RouteGuard permission="clients:read"><ClientsPage /></RouteGuard>;
      case '/products': return <RouteGuard permission="products:read"><ProductsPage /></RouteGuard>;
      case '/invoices': return <RouteGuard permission="invoices:read"><InvoicesPage /></RouteGuard>;
      case '/quotes': return <RouteGuard permission="quotes:read"><QuotesPage /></RouteGuard>;
      case '/employees': return <RouteGuard permission="employees:read"><EmployeesPage /></RouteGuard>;
      case '/expenses': return <RouteGuard permission="expenses:read"><ExpensesPage /></RouteGuard>;
      case '/export': return <RouteGuard permission="reports:read"><ExportPage /></RouteGuard>;
      case '/reports': return <RouteGuard permission="reports:read"><ReportsPage /></RouteGuard>;
      case '/bank': return <RouteGuard permission="bank:read"><BankReconciliationPage /></RouteGuard>;
      case '/ledger': return <RouteGuard permission="accounting:read"><LedgerPage /></RouteGuard>;
      case '/settings': return <SettingsPage />;
      case '/subscription': return <RouteGuard permission="billing:manage"><SubscriptionPage /></RouteGuard>;
      default: return <Dashboard navigate={navigate} />;
    }
  };

  return (
    <Layout currentRoute={currentRoute} navigate={navigate} needsSubscription={needsSubscription}>
      {renderPage()}
    </Layout>
  );
}

function AppWithAuth() {
  return (
    <AuthProvider>
      <App />
    </AuthProvider>
  );
}

export default AppWithAuth;
