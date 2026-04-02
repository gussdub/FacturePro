import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { BACKEND_URL, formatCurrency } from '../config';
import QuickActionCard from '../components/QuickActionCard';

const Dashboard = ({ navigate }) => {
  const { user } = useAuth();
  const [stats, setStats] = useState({ loading: true });

  useEffect(() => { fetchStats(); }, []);

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/dashboard/stats`);
      setStats({ loading: false, data: response.data });
    } catch (error) {
      setStats({ loading: false, error: error.message });
    }
  };

  if (stats.loading) {
    return (
      <div style={{ textAlign: 'center', padding: '60px' }}>
        <p style={{ fontSize: '18px', color: '#6b7280' }}>Chargement du tableau de bord...</p>
      </div>
    );
  }

  return (
    <div data-testid="dashboard-page">
      {/* Welcome Banner */}
      <div style={{
        background: 'linear-gradient(135deg, #00A08C, #47D2A7)', color: 'white',
        padding: '32px', borderRadius: '16px', marginBottom: '32px', textAlign: 'center'
      }}>
        <h1 style={{ fontSize: '32px', fontWeight: '800', margin: '0 0 8px 0' }}>
          Bienvenue dans FacturePro !
        </h1>
        <p style={{ margin: 0, opacity: 0.9, fontSize: '18px' }}>
          Votre tableau de bord est pret. Gerez votre entreprise en toute simplicite.
        </p>
      </div>

      {/* Stats Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '24px', marginBottom: '32px' }}>
        <div data-testid="stat-clients" style={{
          background: 'linear-gradient(135deg, #00A08C, #008F7A)', color: 'white',
          padding: '28px', borderRadius: '16px', textAlign: 'center'
        }}>
          <div style={{ fontSize: '48px', marginBottom: '12px' }}>👥</div>
          <div style={{ fontSize: '36px', fontWeight: '800', marginBottom: '4px' }}>{stats.data?.total_clients || 0}</div>
          <div style={{ fontSize: '14px', opacity: 0.9, fontWeight: '600' }}>Clients</div>
        </div>

        <div data-testid="stat-invoices" style={{
          background: 'linear-gradient(135deg, #10b981, #047857)', color: 'white',
          padding: '28px', borderRadius: '16px', textAlign: 'center'
        }}>
          <div style={{ fontSize: '48px', marginBottom: '12px' }}>📄</div>
          <div style={{ fontSize: '36px', fontWeight: '800', marginBottom: '4px' }}>{stats.data?.total_invoices || 0}</div>
          <div style={{ fontSize: '14px', opacity: 0.9, fontWeight: '600' }}>Factures</div>
        </div>

        <div data-testid="stat-quotes" style={{
          background: 'linear-gradient(135deg, #47D2A7, #008F7A)', color: 'white',
          padding: '28px', borderRadius: '16px', textAlign: 'center'
        }}>
          <div style={{ fontSize: '48px', marginBottom: '12px' }}>📝</div>
          <div style={{ fontSize: '36px', fontWeight: '800', marginBottom: '4px' }}>{stats.data?.total_quotes || 0}</div>
          <div style={{ fontSize: '14px', opacity: 0.9, fontWeight: '600' }}>Soumissions</div>
        </div>

        <div data-testid="stat-revenue" style={{
          background: 'linear-gradient(135deg, #dc2626, #991b1b)', color: 'white',
          padding: '28px', borderRadius: '16px', textAlign: 'center'
        }}>
          <div style={{ fontSize: '48px', marginBottom: '12px' }}>💰</div>
          <div style={{ fontSize: '20px', fontWeight: '800', marginBottom: '4px' }}>
            {formatCurrency(stats.data?.total_revenue || 0)}
          </div>
          <div style={{ fontSize: '14px', opacity: 0.9, fontWeight: '600' }}>Revenus</div>
        </div>
      </div>

      {/* Quick Actions */}
      <div style={{ background: 'white', border: '1px solid #e2e8f0', borderRadius: '16px', padding: '32px' }}>
        <h3 style={{ margin: '0 0 24px 0', fontSize: '20px', fontWeight: '700', color: '#1f2937' }}>
          Actions rapides
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
          <QuickActionCard icon="👥" title="Gerer les clients" description="Ajouter, modifier vos clients"
            onClick={() => navigate('/clients')} />
          <QuickActionCard icon="📄" title="Creer une facture" description="Nouvelle facture client"
            onClick={() => navigate('/invoices')} />
          <QuickActionCard icon="📦" title="Gerer les produits" description="Catalogue de services"
            onClick={() => navigate('/products')} />
          <QuickActionCard icon="📝" title="Creer une soumission" description="Devis pour prospect"
            onClick={() => navigate('/quotes')} />
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
