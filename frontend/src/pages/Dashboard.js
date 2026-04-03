import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { BACKEND_URL, formatCurrency } from '../config';
import QuickActionCard from '../components/QuickActionCard';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

const CHART_COLORS = ['#008F7A', '#47D2A7', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#3b82f6', '#ec4899', '#14b8a6', '#f97316'];

const Dashboard = ({ navigate }) => {
  const { user } = useAuth();
  const [stats, setStats] = useState({ loading: true });
  const [overdue, setOverdue] = useState({ loading: true, data: null });
  const [analytics, setAnalytics] = useState({ loading: true, data: null });
  const [sendingReminder, setSendingReminder] = useState(null);
  const [reminderMsg, setReminderMsg] = useState('');

  useEffect(() => { fetchStats(); fetchOverdue(); fetchAnalytics(); }, []);

  const fetchStats = async () => {
    try {
      const res = await axios.get(`${BACKEND_URL}/api/dashboard/stats`);
      setStats({ loading: false, data: res.data });
    } catch (err) { setStats({ loading: false, error: err.message }); }
  };

  const fetchOverdue = async () => {
    try {
      const res = await axios.get(`${BACKEND_URL}/api/dashboard/overdue`);
      setOverdue({ loading: false, data: res.data });
    } catch { setOverdue({ loading: false, data: { overdue_invoices: [], total_overdue: 0, count: 0 } }); }
  };

  const fetchAnalytics = async () => {
    try {
      const res = await axios.get(`${BACKEND_URL}/api/dashboard/expense-analytics`);
      setAnalytics({ loading: false, data: res.data });
    } catch { setAnalytics({ loading: false, data: null }); }
  };

  const sendReminder = async (inv) => {
    setSendingReminder(inv.id); setReminderMsg('');
    try {
      await axios.post(`${BACKEND_URL}/api/invoices/${inv.id}/remind`, { to_email: inv.client_email });
      setReminderMsg(`Rappel envoyé à ${inv.client_email}`); fetchOverdue();
    } catch (err) { setReminderMsg(err.response?.data?.detail || 'Erreur envoi du rappel'); }
    finally { setSendingReminder(null); }
  };

  if (stats.loading) return <div style={{ textAlign: 'center', padding: '60px' }}><p style={{ fontSize: '18px', color: '#6b7280' }}>Chargement du tableau de bord...</p></div>;

  const overdueData = overdue.data || { overdue_invoices: [], total_overdue: 0, count: 0 };
  const hasOverdue = overdueData.count > 0;
  const expData = analytics.data;
  const hasExpenses = expData && expData.by_category && expData.by_category.length > 0;

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      return (
        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '10px 14px', boxShadow: '0 4px 12px rgba(0,0,0,0.1)', fontSize: '13px' }}>
          {payload.map((p, i) => (
            <div key={i} style={{ color: p.color, margin: '2px 0' }}>
              <strong>{p.name || p.dataKey}</strong>: {formatCurrency(p.value)}
            </div>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div data-testid="dashboard-page">
      {/* Welcome */}
      <div style={{ background: 'linear-gradient(135deg, #00A08C, #47D2A7)', color: 'white', padding: '32px', borderRadius: '16px', marginBottom: '32px', textAlign: 'center' }}>
        <h1 style={{ fontSize: '32px', fontWeight: '800', margin: '0 0 8px 0' }}>Bienvenue dans FacturePro !</h1>
        <p style={{ margin: 0, opacity: 0.9, fontSize: '18px' }}>Votre tableau de bord est pret.</p>
      </div>

      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '20px', marginBottom: '32px' }}>
        {[
          { id: 'clients', bg: '#00A08C', icon: '👥', val: stats.data?.total_clients || 0, label: 'Clients' },
          { id: 'invoices', bg: '#10b981', icon: '📄', val: stats.data?.total_invoices || 0, label: 'Factures' },
          { id: 'quotes', bg: '#47D2A7', icon: '📝', val: stats.data?.total_quotes || 0, label: 'Soumissions' },
          { id: 'revenue', bg: '#dc2626', icon: '💰', val: formatCurrency(stats.data?.total_revenue || 0), label: 'Revenus', isText: true },
        ].map(s => (
          <div key={s.id} data-testid={`stat-${s.id}`} style={{ background: s.bg, color: 'white', padding: '24px', borderRadius: '14px', textAlign: 'center' }}>
            <div style={{ fontSize: '36px', marginBottom: '8px' }}>{s.icon}</div>
            <div style={{ fontSize: s.isText ? '18px' : '32px', fontWeight: '800', marginBottom: '4px' }}>{s.val}</div>
            <div style={{ fontSize: '13px', opacity: 0.9, fontWeight: '600' }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Overdue Tracker */}
      <div data-testid="overdue-tracker" style={{ background: '#fff', border: hasOverdue ? '2px solid #fecaca' : '1px solid #e5e7eb', borderRadius: '16px', padding: '24px', marginBottom: '32px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ width: '38px', height: '38px', borderRadius: '10px', background: hasOverdue ? '#fef2f2' : '#f0fdf4', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '18px' }}>
              {hasOverdue ? '⚠' : '✓'}
            </div>
            <div>
              <h3 style={{ margin: 0, fontSize: '16px', fontWeight: '700', color: '#1f2937' }}>Suivi des paiements</h3>
              <p style={{ margin: '2px 0 0', fontSize: '12px', color: '#6b7280' }}>
                {hasOverdue ? `${overdueData.count} facture(s) en retard — ${formatCurrency(overdueData.total_overdue)} impayé` : 'Aucune facture en retard'}
              </p>
            </div>
          </div>
          {hasOverdue && <div data-testid="overdue-total-badge" style={{ background: '#fef2f2', color: '#991b1b', padding: '6px 14px', borderRadius: '10px', fontWeight: '700', fontSize: '15px' }}>{formatCurrency(overdueData.total_overdue)}</div>}
        </div>
        {reminderMsg && <div data-testid="reminder-message" style={{ background: reminderMsg.includes('Erreur') ? '#fef2f2' : '#f0fdf4', border: `1px solid ${reminderMsg.includes('Erreur') ? '#fecaca' : '#bbf7d0'}`, color: reminderMsg.includes('Erreur') ? '#991b1b' : '#166534', padding: '8px 14px', borderRadius: '8px', marginBottom: '12px', fontSize: '13px' }} onClick={() => setReminderMsg('')}>{reminderMsg}</div>}
        {hasOverdue ? (
          <div style={{ borderRadius: '10px', overflow: 'hidden', border: '1px solid #e5e7eb' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.2fr 0.8fr 0.7fr 0.8fr 0.8fr', background: '#f9fafb', padding: '8px 14px', fontSize: '11px', fontWeight: '600', color: '#6b7280', borderBottom: '1px solid #e5e7eb' }}>
              <span>Facture</span><span>Client</span><span style={{ textAlign: 'right' }}>Montant</span><span style={{ textAlign: 'center' }}>Retard</span><span style={{ textAlign: 'center' }}>Dernier rappel</span><span style={{ textAlign: 'right' }}>Action</span>
            </div>
            {overdueData.overdue_invoices.map(inv => (
              <div key={inv.id} data-testid={`overdue-row-${inv.id}`} style={{ display: 'grid', gridTemplateColumns: '1fr 1.2fr 0.8fr 0.7fr 0.8fr 0.8fr', padding: '10px 14px', borderBottom: '1px solid #f3f4f6', alignItems: 'center', fontSize: '13px' }}>
                <span style={{ fontWeight: '600', color: '#1f2937' }}>{inv.invoice_number}</span>
                <span style={{ color: '#374151' }}>{inv.client_name}</span>
                <span style={{ textAlign: 'right', fontWeight: '700', color: '#991b1b' }}>{formatCurrency(inv.total)}</span>
                <span style={{ textAlign: 'center' }}><span style={{ background: inv.days_overdue > 30 ? '#fef2f2' : '#fef3c7', color: inv.days_overdue > 30 ? '#991b1b' : '#92400e', padding: '2px 8px', borderRadius: '12px', fontSize: '11px', fontWeight: '600' }}>{inv.days_overdue}j</span></span>
                <span style={{ textAlign: 'center', fontSize: '11px', color: '#9ca3af' }}>{inv.last_reminded ? new Date(inv.last_reminded).toLocaleDateString('fr-CA') : '—'}</span>
                <div style={{ textAlign: 'right' }}>
                  <button data-testid={`send-reminder-${inv.id}`} onClick={() => sendReminder(inv)} disabled={sendingReminder === inv.id || !inv.client_email}
                    style={{ background: inv.client_email ? '#008F7A' : '#d1d5db', color: '#fff', border: 'none', padding: '5px 12px', borderRadius: '6px', cursor: inv.client_email ? 'pointer' : 'not-allowed', fontSize: '11px', fontWeight: '600', opacity: sendingReminder === inv.id ? 0.6 : 1 }}>
                    {sendingReminder === inv.id ? 'Envoi...' : 'Rappel'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : <div style={{ textAlign: 'center', padding: '16px', color: '#6b7280', fontSize: '13px' }}>Toutes vos factures sont à jour.</div>}
      </div>

      {/* ═══ Expense Analytics Charts ═══ */}
      {hasExpenses && (
        <div data-testid="expense-analytics" style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', gap: '24px', marginBottom: '32px' }}>
          {/* Pie Chart - By Category */}
          <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '16px', padding: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ margin: 0, fontSize: '16px', fontWeight: '700', color: '#1f2937' }}>Dépenses par catégorie</h3>
              <span style={{ fontSize: '13px', fontWeight: '700', color: '#008F7A' }}>{formatCurrency(expData.total)}</span>
            </div>
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie data={expData.by_category} cx="50%" cy="50%" innerRadius={55} outerRadius={95} paddingAngle={3} dataKey="value" nameKey="name">
                  {expData.by_category.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                </Pie>
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ fontSize: '12px' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Bar Chart - Monthly */}
          <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '16px', padding: '24px' }}>
            <h3 style={{ margin: '0 0 16px', fontSize: '16px', fontWeight: '700', color: '#1f2937' }}>Dépenses mensuelles</h3>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={expData.by_month} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                <XAxis dataKey="month" tick={{ fontSize: 11, fill: '#6b7280' }} />
                <YAxis tick={{ fontSize: 11, fill: '#6b7280' }} tickFormatter={v => `${v}$`} />
                <Tooltip content={<CustomTooltip />} />
                {expData.categories.map((cat, i) => (
                  <Bar key={cat} dataKey={cat} stackId="a" fill={CHART_COLORS[i % CHART_COLORS.length]} radius={i === expData.categories.length - 1 ? [4, 4, 0, 0] : [0, 0, 0, 0]} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Quick Actions */}
      <div style={{ background: 'white', border: '1px solid #e2e8f0', borderRadius: '16px', padding: '28px' }}>
        <h3 style={{ margin: '0 0 20px 0', fontSize: '18px', fontWeight: '700', color: '#1f2937' }}>Actions rapides</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
          <QuickActionCard icon="👥" title="Gerer les clients" description="Ajouter, modifier vos clients" onClick={() => navigate('/clients')} />
          <QuickActionCard icon="📄" title="Creer une facture" description="Nouvelle facture client" onClick={() => navigate('/invoices')} />
          <QuickActionCard icon="📦" title="Gerer les produits" description="Catalogue de services" onClick={() => navigate('/products')} />
          <QuickActionCard icon="📝" title="Creer une soumission" description="Devis pour prospect" onClick={() => navigate('/quotes')} />
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
