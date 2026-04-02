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

function App() {
  const [currentRoute, setCurrentRoute] = useState(
    window.location.pathname === '/' ? '/dashboard' : window.location.pathname
  );
  const { isAuthenticated } = useAuth();

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

  const renderPage = () => {
    switch (currentRoute) {
      case '/clients': return <ClientsPage />;
      case '/products': return <ProductsPage />;
      case '/invoices': return <InvoicesPage />;
      case '/quotes': return <QuotesPage />;
      case '/employees': return <EmployeesPage />;
      case '/expenses': return <ExpensesPage />;
      case '/export': return <ExportPage />;
      case '/settings': return <SettingsPage />;
      default: return <Dashboard navigate={navigate} />;
    }
  };

  return (
    <Layout currentRoute={currentRoute} navigate={navigate}>
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
