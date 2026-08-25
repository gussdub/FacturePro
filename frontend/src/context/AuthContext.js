import React, { useState, createContext, useContext, useEffect, useCallback } from 'react';
import axios from 'axios';
import { BACKEND_URL } from '../config';

const AuthContext = createContext();
export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [organization, setOrganization] = useState(null);
  const [permissions, setPermissions] = useState([]);
  const [role, setRole] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [loading, setLoading] = useState(true);

  const fetchUserAndOrg = useCallback(async (authToken) => {
    try {
      axios.defaults.headers.common['Authorization'] = `Bearer ${authToken}`;
      const [meRes, orgRes] = await Promise.all([
        axios.get(`${BACKEND_URL}/api/auth/me`),
        axios.get(`${BACKEND_URL}/api/org/me`),
      ]);
      setUser(meRes.data);
      setOrganization(orgRes.data.organization);
      setPermissions(orgRes.data.current_user.permissions || []);
      setRole(orgRes.data.current_user.role || null);
    } catch (error) {
      localStorage.removeItem('token');
      setToken(null);
      setUser(null);
      setOrganization(null);
      setPermissions([]);
      setRole(null);
      delete axios.defaults.headers.common['Authorization'];
    }
  }, []);

  useEffect(() => {
    const initAuth = async () => {
      if (token) {
        await fetchUserAndOrg(token);
      }
      setLoading(false);
    };
    initAuth();
  }, [token, fetchUserAndOrg]);

  useEffect(() => {
    const id = axios.interceptors.response.use(
      (res) => res,
      (err) => {
        if (err.response?.status === 401 && localStorage.getItem('token')) {
          localStorage.removeItem('token');
          setToken(null);
          setUser(null);
          setOrganization(null);
          setPermissions([]);
          setRole(null);
          delete axios.defaults.headers.common['Authorization'];
        }
        return Promise.reject(err);
      }
    );
    return () => axios.interceptors.response.eject(id);
  }, []);

  const refreshUser = useCallback(async () => {
    if (token) {
      await fetchUserAndOrg(token);
    }
  }, [token, fetchUserAndOrg]);

  const _completeLogin = async (access_token) => {
    setToken(access_token);
    localStorage.setItem('token', access_token);
    axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
    await fetchUserAndOrg(access_token);
  };

  const login = async (email, password) => {
    try {
      const response = await axios.post(`${BACKEND_URL}/api/auth/login`, { email, password });
      // [MFA] Double authentification activée → pas de JWT encore : on passe au 2e facteur.
      if (response.data?.mfa_required) {
        return { success: false, mfaRequired: true, mfaToken: response.data.mfa_token };
      }
      await _completeLogin(response.data.access_token);
      return { success: true };
    } catch (error) {
      return { success: false, error: error.response?.data?.detail || 'Email ou mot de passe incorrect' };
    }
  };

  const completeMfaChallenge = async (mfaToken, code) => {
    try {
      const response = await axios.post(`${BACKEND_URL}/api/auth/mfa/challenge`,
        { mfa_token: mfaToken, code });
      await _completeLogin(response.data.access_token);
      return { success: true };
    } catch (error) {
      return { success: false, error: error.response?.data?.detail || 'Code invalide' };
    }
  };

  const register = async (email, password, company_name) => {
    try {
      const response = await axios.post(`${BACKEND_URL}/api/auth/register`, { email, password, company_name });
      const { access_token } = response.data;
      setToken(access_token);
      localStorage.setItem('token', access_token);
      axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
      await fetchUserAndOrg(access_token);
      return { success: true };
    } catch (error) {
      return { success: false, error: error.response?.data?.detail || "Erreur d'inscription" };
    }
  };

  const acceptInvite = async ({ token: inviteToken, password, pipeda_consent }) => {
    try {
      const response = await axios.post(`${BACKEND_URL}/api/auth/accept-invite`, {
        token: inviteToken, password, pipeda_consent,
      });
      const { access_token } = response.data;
      setToken(access_token);
      localStorage.setItem('token', access_token);
      axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
      await fetchUserAndOrg(access_token);
      return { success: true };
    } catch (error) {
      return { success: false, error: error.response?.data?.detail || "Erreur lors de l'acceptation" };
    }
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    setOrganization(null);
    setPermissions([]);
    setRole(null);
    localStorage.removeItem('token');
    delete axios.defaults.headers.common['Authorization'];
  };

  const hasPermission = useCallback((code) => permissions.includes(code), [permissions]);

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', fontSize: '18px' }}>
        Chargement...
      </div>
    );
  }

  return (
    <AuthContext.Provider value={{
      user, organization, permissions, role,
      token, login, completeMfaChallenge, register, acceptInvite, logout, refreshUser,
      hasPermission,
      isAuthenticated: !!token,
    }}>
      {children}
    </AuthContext.Provider>
  );
};
