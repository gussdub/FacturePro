import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import axios from 'axios';
import './App.css';

// Components
import LoginPage from './components/LoginPage';
import Dashboard from './components/Dashboard';
import ClientsPage from './components/ClientsPage';
import ProductsPage from './components/ProductsPage';
import InvoicesPage from './components/InvoicesPage';
import QuotesPage from './components/QuotesPage';
import ExportPage from './components/ExportPage';
import SettingsPage from './components/SettingsPage';
import EmployeesPage from './components/EmployeesPage';
import ExpensesPage from './components/ExpensesPage';
import SubscriptionPage from './components/SubscriptionPage';
import SubscriptionSuccess from './components/SubscriptionSuccess';
import SubscriptionCancel from './components/SubscriptionCancel';
import TrialSetup from './components/TrialSetup';
import Layout from './components/Layout';

// Force production URL when on facturepro.ca
const BACKEND_URL = window.location.hostname === 'facturepro.ca' 
  ? 'https://facturepro.ca'
  : process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Auth Context
const AuthContext = React.createContext();

export const useAuth = () => {
  const context = React.useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

// Auth Provider
const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      // You could validate token here if needed
    }
    setLoading(false);

    // Aggressive watermark removal
    const removeWatermark = () => {
      // Remove elements by text content
      const walker = document.createTreeWalker(
        document.body,
        NodeFilter.SHOW_TEXT,
        null,
        false
      );

      let node;
      const elementsToRemove = [];
      
      while (node = walker.nextNode()) {
        if (node.textContent && (
          node.textContent.includes('Made with Emergent') ||
          node.textContent.includes('Made with') ||
          node.textContent.includes('Emergent')
        )) {
          let parent = node.parentElement;
          while (parent && parent !== document.body) {
            elementsToRemove.push(parent);
            parent = parent.parentElement;
          }
        }
      }

      // Remove elements with specific styles (fixed position at bottom right)
      const allElements = document.querySelectorAll('*');
      allElements.forEach(el => {
        const style = window.getComputedStyle(el);
        if (style.position === 'fixed' && 
            (style.bottom === '10px' || style.bottom === '20px') &&
            (style.right === '10px' || style.right === '20px')) {
          elementsToRemove.push(el);
        }
      });

      // Actually remove the elements
      elementsToRemove.forEach(el => {
        if (el && el.parentNode) {
          el.parentNode.removeChild(el);
        }
      });
    };

    // Run immediately and on intervals
    removeWatermark();
    const interval = setInterval(removeWatermark, 1000);

    // Run on DOM changes
    const observer = new MutationObserver(removeWatermark);
    observer.observe(document.body, { 
      childList: true, 
      subtree: true 
    });

    return () => {
      clearInterval(interval);
      observer.disconnect();
    };
  }, [token]);

  const login = async (email, password) => {
    try {
      const response = await axios.post(`${API}/auth/login`, {
        email,
        password
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
        error: error.response?.data?.detail || 'Erreur de connexion' 
      };
    }
  };

  const register = async (email, password, companyName) => {
    try {
      const response = await axios.post(`${API}/auth/register`, {
        email,
        password,
        company_name: companyName
      });

      const { access_token, user: userData } = response.data;
      
      setToken(access_token);
      setUser(userData);
      localStorage.setItem('token', access_token);
      axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
      
      // Redirect to trial setup after successful registration
      window.location.href = '/trial/setup';
      
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

  const value = {
    user,
    token,
    login,
    register,
    logout,
    loading
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

// Protected Route Component
const ProtectedRoute = ({ children }) => {
  const { token, loading } = useAuth();
  
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600"></div>
      </div>
    );
  }
  
  return token ? children : <Navigate to="/login" replace />;
};

// Public Route Component (redirect to dashboard if already logged in)
const PublicRoute = ({ children }) => {
  const { token, loading } = useAuth();
  
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600"></div>
      </div>
    );
  }
  
  return token ? <Navigate to="/dashboard" replace /> : children;
};

function App() {
  return (
    <AuthProvider>
      <div className="App">
        <BrowserRouter>
          <Routes>
            {/* Public Routes */}
            <Route 
              path="/login" 
              element={
                <PublicRoute>
                  <LoginPage />
                </PublicRoute>
              } 
            />
            
            {/* Protected Routes */}
            <Route 
              path="/" 
              element={
                <ProtectedRoute>
                  <Layout />
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="/dashboard" replace />} />
              <Route path="dashboard" element={<Dashboard />} />
              <Route path="clients" element={<ClientsPage />} />
              <Route path="products" element={<ProductsPage />} />
              <Route path="employees" element={<EmployeesPage />} />
              <Route path="expenses" element={<ExpensesPage />} />
              <Route path="invoices" element={<InvoicesPage />} />
              <Route path="quotes" element={<QuotesPage />} />
              <Route path="export" element={<ExportPage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="subscription" element={<SubscriptionPage />} />
            </Route>
            
            {/* Trial Setup Route */}
            <Route path="trial/setup" element={<TrialSetup />} />
            
            {/* Subscription Routes (can be accessed without full auth) */}
            <Route path="subscription/success" element={<SubscriptionSuccess />} />
            <Route path="subscription/cancel" element={<SubscriptionCancel />} />
          </Routes>
        </BrowserRouter>
      </div>
    </AuthProvider>
  );
}

export default App;