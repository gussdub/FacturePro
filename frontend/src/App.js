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

function App() {
  const [currentRoute, setCurrentRoute] = useState(
    window.location.pathname === '/' ? '/dashboard' : window.location.pathname
  );
  const { isAuthenticated, user } = useAuth();

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

  // Public route — no auth required
  if (window.location.pathname === '/accept-invite') {
    return <AcceptInvitePage />;
  }

  if (!isAuthenticated) {
    return <LoginPage />;
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
