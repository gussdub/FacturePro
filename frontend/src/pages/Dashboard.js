import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { BACKEND_URL, formatCurrency } from '../config';
import QuickActionCard from '../components/QuickActionCard';

const Dashboard = ({ navigate }) => {
  const { user } = useAuth();
  const [stats, setStats] = useState({ loading: true });
  const [overdue, setOverdue] = useState({ loading: true, data: null });
  const [sendingReminder, setSendingReminder] = useState(null);
  const [reminderMsg, setReminderMsg] = useState('');

  useEffect(() => { fetchStats(); fetchOverdue(); }, []);

  const fetchStats = async () => {
    try {
      const res = await axios.get(`${BACKEND_URL}/api/dashboard/stats`);
      setStats({ loading: false, data: res.data });
    } catch (err) {
      setStats({ loading: false, error: err.message });
    }
  };

  const fetchOverdue = async () => {
    try {
      const res = await axios.get(`${BACKEND_URL}/api/dashboard/overdue`);
      setOverdue({ loading: false, data: res.data });
    } catch {
      setOverdue({ loading: false, data: { overdue_invoices: [], total_overdue: 0, count: 0 } });
    }
  };

  const sendReminder = async (inv) => {
    setSendingReminder(inv.id);
    setReminderMsg('');
    try {
      await axios.post(`${BACKEND_URL}/api/invoices/${inv.id}/remind`, { to_email: inv.client_email });
      setReminderMsg(`Rappel envoyé à ${inv.client_email}`);
      fetchOverdue();
    } catch (err) {
      setReminderMsg(err.response?.data?.detail || 'Erreur envoi du rappel');
    } finally {
      setSendingReminder(null);
    }
  };

  if (stats.loading) {
    return (
      <div style={{ textAlign: 'center', padding: '60px' }}>
        <p style={{ fontSize: '18px', color: '#6b7280' }}>Chargement du tableau de bord...</p>
      </div>
    );
  }

  const overdueData = overdue.data || { overdue_invoices: [], total_overdue: 0, count: 0 };
  const hasOverdue = overdueData.count > 0;

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

      {/* ═══ Overdue Invoices Tracker ═══ */}
      <div data-testid="overdue-tracker" style={{
        background: '#fff', border: hasOverdue ? '2px solid #fecaca' : '1px solid #e5e7eb',
        borderRadius: '16px', padding: '28px', marginBottom: '32px'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '42px', height: '42px', borderRadius: '10px',
              background: hasOverdue ? '#fef2f2' : '#f0fdf4',
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '20px'
            }}>
              {hasOverdue ? '⚠' : '✓'}
            </div>
            <div>
              <h3 style={{ margin: 0, fontSize: '18px', fontWeight: '700', color: '#1f2937' }}>
                Suivi des paiements
              </h3>
              <p style={{ margin: '2px 0 0', fontSize: '13px', color: '#6b7280' }}>
                {hasOverdue
                  ? `${overdueData.count} facture(s) en retard — ${formatCurrency(overdueData.total_overdue)} impayé`
                  : 'Aucune facture en retard'}
              </p>
            </div>
          </div>
          {hasOverdue && (
            <div data-testid="overdue-total-badge" style={{
              background: '#fef2f2', color: '#991b1b', padding: '8px 16px',
              borderRadius: '10px', fontWeight: '700', fontSize: '16px'
            }}>
              {formatCurrency(overdueData.total_overdue)}
            </div>
          )}
        </div>

        {reminderMsg && (
          <div data-testid="reminder-message" style={{
            background: reminderMsg.includes('Erreur') ? '#fef2f2' : '#f0fdf4',
            border: `1px solid ${reminderMsg.includes('Erreur') ? '#fecaca' : '#bbf7d0'}`,
            color: reminderMsg.includes('Erreur') ? '#991b1b' : '#166534',
            padding: '10px 14px', borderRadius: '8px', marginBottom: '16px', fontSize: '13px'
          }} onClick={() => setReminderMsg('')}>
            {reminderMsg}
          </div>
        )}

        {hasOverdue ? (
          <div style={{ borderRadius: '10px', overflow: 'hidden', border: '1px solid #e5e7eb' }}>
            {/* Table header */}
            <div style={{
              display: 'grid', gridTemplateColumns: '1fr 1.2fr 0.8fr 0.7fr 0.8fr 0.8fr',
              background: '#f9fafb', padding: '10px 16px', fontSize: '12px',
              fontWeight: '600', color: '#6b7280', borderBottom: '1px solid #e5e7eb'
            }}>
              <span>Facture</span>
              <span>Client</span>
              <span style={{ textAlign: 'right' }}>Montant</span>
              <span style={{ textAlign: 'center' }}>Retard</span>
              <span style={{ textAlign: 'center' }}>Dernier rappel</span>
              <span style={{ textAlign: 'right' }}>Action</span>
            </div>
            {overdueData.overdue_invoices.map(inv => (
              <div key={inv.id} data-testid={`overdue-row-${inv.id}`} style={{
                display: 'grid', gridTemplateColumns: '1fr 1.2fr 0.8fr 0.7fr 0.8fr 0.8fr',
                padding: '12px 16px', borderBottom: '1px solid #f3f4f6',
                alignItems: 'center', fontSize: '14px'
              }}>
                <span style={{ fontWeight: '600', color: '#1f2937' }}>{inv.invoice_number}</span>
                <span style={{ color: '#374151' }}>{inv.client_name}</span>
                <span style={{ textAlign: 'right', fontWeight: '700', color: '#991b1b' }}>
                  {formatCurrency(inv.total)}
                </span>
                <span style={{ textAlign: 'center' }}>
                  <span style={{
                    background: inv.days_overdue > 30 ? '#fef2f2' : '#fef3c7',
                    color: inv.days_overdue > 30 ? '#991b1b' : '#92400e',
                    padding: '2px 8px', borderRadius: '12px', fontSize: '12px', fontWeight: '600'
                  }}>
                    {inv.days_overdue}j
                  </span>
                </span>
                <span style={{ textAlign: 'center', fontSize: '12px', color: '#9ca3af' }}>
                  {inv.last_reminded
                    ? new Date(inv.last_reminded).toLocaleDateString('fr-CA')
                    : '—'}
                </span>
                <div style={{ textAlign: 'right' }}>
                  <button
                    data-testid={`send-reminder-${inv.id}`}
                    onClick={() => sendReminder(inv)}
                    disabled={sendingReminder === inv.id || !inv.client_email}
                    title={inv.client_email ? `Envoyer rappel à ${inv.client_email}` : 'Aucun email client'}
                    style={{
                      background: inv.client_email ? '#008F7A' : '#d1d5db',
                      color: '#fff', border: 'none', padding: '6px 14px',
                      borderRadius: '6px', cursor: inv.client_email ? 'pointer' : 'not-allowed',
                      fontSize: '12px', fontWeight: '600',
                      opacity: sendingReminder === inv.id ? 0.6 : 1
                    }}
                  >
                    {sendingReminder === inv.id ? 'Envoi...' : 'Rappel'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '20px', color: '#6b7280', fontSize: '14px' }}>
            Toutes vos factures sont à jour. Excellent travail !
          </div>
        )}
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
