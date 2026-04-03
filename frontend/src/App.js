import React, { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import Layout from './components/Layout';
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
      case '/clients': return <ClientsPage />;
      case '/products': return <ProductsPage />;
      case '/invoices': return <InvoicesPage />;
      case '/quotes': return <QuotesPage />;
      case '/employees': return <EmployeesPage />;
      case '/expenses': return <ExpensesPage />;
      case '/export': return <ExportPage />;
      case '/settings': return <SettingsPage />;
      case '/subscription': return <SubscriptionPage />;
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
