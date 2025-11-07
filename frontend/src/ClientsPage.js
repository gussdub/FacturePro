import React, { useState, createContext, useContext, useEffect } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'https://facturepro-api.onrender.com';

// Auth Context
const AuthContext = createContext();
export const useAuth = () => useContext(AuthContext);

// Navigation Component
const Navigation = ({ currentPage, onPageChange }) => {
  const { logout } = useAuth();

  const navStyle = {
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    color: 'white',
    padding: '15px 20px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center'
  };

  const menuStyle = {
    display: 'flex',
    gap: '20px'
  };

  const linkStyle = (active) => ({
    background: active ? 'rgba(255,255,255,0.2)' : 'transparent',
    padding: '8px 16px',
    borderRadius: '6px',
    cursor: 'pointer',
    fontWeight: active ? 'bold' : 'normal',
    transition: 'all 0.3s'
  });

  return (
    <nav style={navStyle}>
      <h1 style={{ margin: 0, fontSize: '24px' }}>🧾 FacturePro</h1>
      
      <div style={menuStyle}>
        <div 
          style={linkStyle(currentPage === 'dashboard')}
          onClick={() => onPageChange('dashboard')}
        >
          📊 Dashboard
        </div>
        <div 
          style={linkStyle(currentPage === 'clients')}
          onClick={() => onPageChange('clients')}
        >
          👥 Clients
        </div>
        <div 
          style={linkStyle(currentPage === 'settings')}
          onClick={() => onPageChange('settings')}
        >
          ⚙️ Paramètres
        </div>
      </div>

      <button
        onClick={logout}
        style={{
          background: '#ef4444',
          color: 'white',
          border: 'none',
          padding: '8px 16px',
          borderRadius: '6px',
          cursor: 'pointer'
        }}
      >
        🚪 Déconnexion
      </button>
    </nav>
  );
};

// Dashboard Component
const Dashboard = () => {
  const { user } = useAuth();
  const [stats, setStats] = useState({ loading: true });

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/health`);
      setStats({ loading: false, data: response.data });
    } catch (error) {
      setStats({ loading: false, error: error.message });
    }
  };

  return (
    <div style={{ padding: '30px' }}>
      <h2 style={{ marginBottom: '20px', color: '#333' }}>Tableau de bord</h2>
      
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '20px' }}>
        <div style={{
          background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
          color: 'white',
          padding: '20px',
          borderRadius: '10px',
          textAlign: 'center'
        }}>
          <h3 style={{ margin: '0 0 10px 0' }}>✅ Migration Réussie</h3>
          <p style={{ margin: 0 }}>FacturePro sur Vercel + Render</p>
        </div>

        <div style={{
          background: '#f8fafc',
          border: '1px solid #e2e8f0',
          padding: '20px',
          borderRadius: '10px'
        }}>
          <h3 style={{ margin: '0 0 10px 0', color: '#333' }}>👤 Utilisateur</h3>
          <p style={{ margin: 0, color: '#666' }}>{user?.company_name}</p>
          <p style={{ margin: '5px 0 0 0', color: '#666', fontSize: '14px' }}>{user?.email}</p>
        </div>

        <div style={{
          background: '#f8fafc',
          border: '1px solid #e2e8f0',
          padding: '20px',
          borderRadius: '10px'
        }}>
          <h3 style={{ margin: '0 0 10px 0', color: '#333' }}>🔗 API Status</h3>
          {stats.loading ? (
            <p style={{ color: '#666' }}>Chargement...</p>
          ) : stats.error ? (
            <p style={{ color: '#dc2626' }}>❌ {stats.error}</p>
          ) : (
            <p style={{ color: '#059669' }}>✅ Connecté</p>
          )}
        </div>
      </div>
    </div>
  );
};

// Clients Component
const ClientsPage = () => {
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    name: '', email: '', phone: '', address: '', city: '', postal_code: '', country: ''
  });

  useEffect(() => {
    fetchClients();
  }, []);

  const fetchClients = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/clients`);
      setClients(response.data);
    } catch (error) {
      console.error('Error fetching clients:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await axios.post(`${BACKEND_URL}/api/clients`, formData);
      setFormData({ name: '', email: '', phone: '', address: '', city: '', postal_code: '', country: '' });
      setShowForm(false);
      fetchClients();
    } catch (error) {
      alert('Erreur lors de la création du client');
    }
  };

  const deleteClient = async (clientId) => {
    if (window.confirm('Supprimer ce client ?')) {
      try {
        await axios.delete(`${BACKEND_URL}/api/clients/${clientId}`);
        fetchClients();
      } catch (error) {
        alert('Erreur lors de la suppression');
      }
    }
  };

  return (
    <div style={{ padding: '30px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px' }}>
        <h2 style={{ margin: 0, color: '#333' }}>👥 Clients ({clients.length})</h2>
        <button
          onClick={() => setShowForm(true)}
          style={{
            background: '#3b82f6',
            color: 'white',
            border: 'none',
            padding: '10px 20px',
            borderRadius: '6px',
            cursor: 'pointer'
          }}
        >
          ➕ Nouveau Client
        </button>
      </div>

      {loading ? (
        <p>Chargement...</p>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '20px' }}>
          {clients.map(client => (
            <div key={client.id} style={{
              background: 'white',
              border: '1px solid #e2e8f0',
              padding: '20px',
              borderRadius: '10px',
              boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
            }}>
              <h3 style={{ margin: '0 0 10px 0', color: '#333' }}>{client.name}</h3>
              <p style={{ margin: '5px 0', color: '#666' }}>📧 {client.email}</p>
              {client.phone && <p style={{ margin: '5px 0', color: '#666' }}>📱 {client.phone}</p>}
              {client.address && <p style={{ margin: '5px 0', color: '#666' }}>📍 {client.address}</p>}
              
              <div style={{ marginTop: '15px', textAlign: 'right' }}>
                <button
                  onClick={() => deleteClient(client.id)}
                  style={{
                    background: '#ef4444',
                    color: 'white',
                    border: 'none',
                    padding: '5px 10px',
                    borderRadius: '4px',
                    cursor: 'pointer',
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

      {/* Client Form Modal */}
      {showForm && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            background: 'white',
            padding: '30px',
            borderRadius: '10px',
            width: '90%',
            maxWidth: '500px',
            maxHeight: '80vh',
            overflow: 'auto'
          }}>
            <h3 style={{ marginTop: 0 }}>Nouveau Client</h3>
            
            <form onSubmit={handleSubmit}>
              <div style={{ marginBottom: '15px' }}>
                <label style={{ display: 'block', marginBottom: '5px', fontWeight: '600' }}>Nom *</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                  required
                  style={{
                    width: '100%',
                    padding: '10px',
                    border: '1px solid #ddd',
                    borderRadius: '5px',
                    boxSizing: 'border-box'
                  }}
                />
              </div>

              <div style={{ marginBottom: '15px' }}>
                <label style={{ display: 'block', marginBottom: '5px', fontWeight: '600' }}>Email *</label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData(prev => ({ ...prev, email: e.target.value }))}
                  required
                  style={{
                    width: '100%',
                    padding: '10px',
                    border: '1px solid #ddd',
                    borderRadius: '5px',
                    boxSizing: 'border-box'
                  }}
                />
              </div>

              <div style={{ marginBottom: '15px' }}>
                <label style={{ display: 'block', marginBottom: '5px', fontWeight: '600' }}>Téléphone</label>
                <input
                  type="tel"
                  value={formData.phone}
                  onChange={(e) => setFormData(prev => ({ ...prev, phone: e.target.value }))}
                  style={{
                    width: '100%',
                    padding: '10px',
                    border: '1px solid #ddd',
                    borderRadius: '5px',
                    boxSizing: 'border-box'
                  }}
                />
              </div>

              <div style={{ marginBottom: '15px' }}>
                <label style={{ display: 'block', marginBottom: '5px', fontWeight: '600' }}>Adresse</label>
                <input
                  type="text"
                  value={formData.address}
                  onChange={(e) => setFormData(prev => ({ ...prev, address: e.target.value }))}
                  style={{
                    width: '100%',
                    padding: '10px',
                    border: '1px solid #ddd',
                    borderRadius: '5px',
                    boxSizing: 'border-box'
                  }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  style={{
                    background: '#6b7280',
                    color: 'white',
                    border: 'none',
                    padding: '10px 20px',
                    borderRadius: '6px',
                    cursor: 'pointer'
                  }}
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  style={{
                    background: '#3b82f6',
                    color: 'white',
                    border: 'none',
                    padding: '10px 20px',
                    borderRadius: '6px',
                    cursor: 'pointer'
                  }}
                >
                  Créer
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};