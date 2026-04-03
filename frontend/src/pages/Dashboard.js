import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { BACKEND_URL, formatCurrency } from '../config';
import QuickActionCard from '../components/QuickActionCard';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { Users, FileText, FilePen, DollarSign, AlertTriangle, CheckCircle, ArrowUpRight, Receipt } from 'lucide-react';

const CHART_COLORS = ['#09090b', '#52525b', '#a1a1aa', '#002FA7', '#d4d4d8', '#71717a', '#3f3f46', '#e4e4e7'];

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
      setReminderMsg(`Rappel envoye a ${inv.client_email}`); fetchOverdue();
    } catch (err) { setReminderMsg(err.response?.data?.detail || 'Erreur envoi du rappel'); }
    finally { setSendingReminder(null); }
  };

  if (stats.loading) return <div style={{ textAlign: 'center', padding: '60px' }}><p style={{ fontSize: '14px', color: '#a1a1aa' }}>Chargement du tableau de bord...</p></div>;

  const overdueData = overdue.data || { overdue_invoices: [], total_overdue: 0, count: 0 };
  const hasOverdue = overdueData.count > 0;
  const expData = analytics.data;
  const hasExpenses = expData && expData.by_category && expData.by_category.length > 0;

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      return (
        <div style={{ background: '#09090b', border: 'none', borderRadius: '6px', padding: '8px 12px', fontSize: '12px', color: '#fff' }}>
          {payload.map((p, i) => (
            <div key={i} style={{ margin: '2px 0' }}>
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
      <div style={{ marginBottom: '28px' }}>
        <h1 style={{ fontSize: '28px', fontWeight: '700', color: '#09090b', margin: '0 0 4px 0', letterSpacing: '-0.03em' }}>
          Bonjour, {user?.company_name || 'Entreprise'}
        </h1>
        <p style={{ margin: 0, color: '#a1a1aa', fontSize: '14px' }}>Voici un apercu de votre activite.</p>
      </div>

      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '28px' }}>
        {[
          { id: 'clients', icon: Users, val: stats.data?.total_clients || 0, label: 'Clients' },
          { id: 'invoices', icon: FileText, val: stats.data?.total_invoices || 0, label: 'Factures' },
          { id: 'quotes', icon: FilePen, val: stats.data?.total_quotes || 0, label: 'Soumissions' },
          { id: 'revenue', icon: DollarSign, val: formatCurrency(stats.data?.total_revenue || 0), label: 'Revenus', isText: true },
        ].map(s => {
          const Icon = s.icon;
          return (
            <div key={s.id} data-testid={`stat-${s.id}`} style={{
              background: '#ffffff', border: '1px solid #e4e4e7', padding: '20px',
              borderRadius: '6px', transition: 'all 0.15s ease'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                <Icon size={18} strokeWidth={1.5} color="#a1a1aa" />
                <ArrowUpRight size={14} strokeWidth={1.5} color="#a1a1aa" />
              </div>
              <div style={{ fontSize: s.isText ? '18px' : '28px', fontWeight: '700', color: '#09090b', marginBottom: '2px', letterSpacing: '-0.03em' }}>{s.val}</div>
              <div style={{ fontSize: '12px', color: '#a1a1aa', fontWeight: '500', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{s.label}</div>
            </div>
          );
        })}
      </div>

      {/* Overdue Tracker */}
      <div data-testid="overdue-tracker" style={{ background: '#ffffff', border: `1px solid ${hasOverdue ? '#fecaca' : '#e4e4e7'}`, borderRadius: '6px', padding: '20px', marginBottom: '28px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            {hasOverdue ? <AlertTriangle size={18} color="#dc2626" strokeWidth={2} /> : <CheckCircle size={18} color="#16a34a" strokeWidth={2} />}
            <div>
              <h3 style={{ margin: 0, fontSize: '14px', fontWeight: '700', color: '#09090b' }}>Suivi des paiements</h3>
              <p style={{ margin: '2px 0 0', fontSize: '12px', color: '#a1a1aa' }}>
                {hasOverdue ? `${overdueData.count} facture(s) en retard — ${formatCurrency(overdueData.total_overdue)} impaye` : 'Aucune facture en retard'}
              </p>
            </div>
          </div>
          {hasOverdue && <div data-testid="overdue-total-badge" style={{ background: '#fef2f2', color: '#991b1b', padding: '4px 12px', borderRadius: '4px', fontWeight: '700', fontSize: '13px' }}>{formatCurrency(overdueData.total_overdue)}</div>}
        </div>
        {reminderMsg && <div data-testid="reminder-message" style={{ background: reminderMsg.includes('Erreur') ? '#fef2f2' : '#f0fdf4', border: `1px solid ${reminderMsg.includes('Erreur') ? '#fecaca' : '#bbf7d0'}`, color: reminderMsg.includes('Erreur') ? '#991b1b' : '#166534', padding: '8px 14px', borderRadius: '4px', marginBottom: '12px', fontSize: '12px', cursor: 'pointer' }} onClick={() => setReminderMsg('')}>{reminderMsg}</div>}
        {hasOverdue ? (
          <div style={{ borderRadius: '4px', overflow: 'hidden', border: '1px solid #e4e4e7' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.2fr 0.8fr 0.7fr 0.8fr 0.8fr', background: '#fafafa', padding: '8px 14px', fontSize: '11px', fontWeight: '600', color: '#a1a1aa', borderBottom: '1px solid #e4e4e7', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              <span>Facture</span><span>Client</span><span style={{ textAlign: 'right' }}>Montant</span><span style={{ textAlign: 'center' }}>Retard</span><span style={{ textAlign: 'center' }}>Dernier rappel</span><span style={{ textAlign: 'right' }}>Action</span>
            </div>
            {overdueData.overdue_invoices.map(inv => (
              <div key={inv.id} data-testid={`overdue-row-${inv.id}`} style={{ display: 'grid', gridTemplateColumns: '1fr 1.2fr 0.8fr 0.7fr 0.8fr 0.8fr', padding: '10px 14px', borderBottom: '1px solid #f4f4f5', alignItems: 'center', fontSize: '13px' }}>
                <span style={{ fontWeight: '600', color: '#09090b' }}>{inv.invoice_number}</span>
                <span style={{ color: '#52525b' }}>{inv.client_name}</span>
                <span style={{ textAlign: 'right', fontWeight: '700', color: '#dc2626' }}>{formatCurrency(inv.total)}</span>
                <span style={{ textAlign: 'center' }}><span style={{ background: inv.days_overdue > 30 ? '#fef2f2' : '#fef3c7', color: inv.days_overdue > 30 ? '#991b1b' : '#92400e', padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: '600' }}>{inv.days_overdue}j</span></span>
                <span style={{ textAlign: 'center', fontSize: '11px', color: '#a1a1aa' }}>{inv.last_reminded ? new Date(inv.last_reminded).toLocaleDateString('fr-CA') : '—'}</span>
                <div style={{ textAlign: 'right' }}>
                  <button data-testid={`send-reminder-${inv.id}`} onClick={() => sendReminder(inv)} disabled={sendingReminder === inv.id || !inv.client_email}
                    style={{ background: inv.client_email ? '#09090b' : '#d4d4d8', color: '#fff', border: 'none', padding: '5px 12px', borderRadius: '4px', cursor: inv.client_email ? 'pointer' : 'not-allowed', fontSize: '11px', fontWeight: '600', opacity: sendingReminder === inv.id ? 0.6 : 1 }}>
                    {sendingReminder === inv.id ? 'Envoi...' : 'Rappel'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : <div style={{ textAlign: 'center', padding: '12px', color: '#a1a1aa', fontSize: '13px' }}>Toutes vos factures sont a jour.</div>}
      </div>

      {/* Expense Analytics Charts */}
      {hasExpenses && (
        <div data-testid="expense-analytics" style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', gap: '16px', marginBottom: '28px' }}>
          {/* Pie Chart */}
          <div style={{ background: '#ffffff', border: '1px solid #e4e4e7', borderRadius: '6px', padding: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <h3 style={{ margin: 0, fontSize: '14px', fontWeight: '700', color: '#09090b' }}>Depenses par categorie</h3>
              <span style={{ fontSize: '13px', fontWeight: '700', color: '#09090b' }}>{formatCurrency(expData.total)}</span>
            </div>
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie data={expData.by_category} cx="50%" cy="50%" innerRadius={55} outerRadius={95} paddingAngle={2} dataKey="value" nameKey="name">
                  {expData.by_category.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                </Pie>
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ fontSize: '11px' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Bar Chart */}
          <div style={{ background: '#ffffff', border: '1px solid #e4e4e7', borderRadius: '6px', padding: '20px' }}>
            <h3 style={{ margin: '0 0 14px', fontSize: '14px', fontWeight: '700', color: '#09090b' }}>Depenses mensuelles</h3>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={expData.by_month} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f4f4f5" />
                <XAxis dataKey="month" tick={{ fontSize: 11, fill: '#a1a1aa' }} />
                <YAxis tick={{ fontSize: 11, fill: '#a1a1aa' }} tickFormatter={v => `${v}$`} />
                <Tooltip content={<CustomTooltip />} />
                {expData.categories.map((cat, i) => (
                  <Bar key={cat} dataKey={cat} stackId="a" fill={CHART_COLORS[i % CHART_COLORS.length]} radius={i === expData.categories.length - 1 ? [3, 3, 0, 0] : [0, 0, 0, 0]} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Quick Actions */}
      <div style={{ background: '#ffffff', border: '1px solid #e4e4e7', borderRadius: '6px', padding: '20px' }}>
        <h3 style={{ margin: '0 0 16px 0', fontSize: '14px', fontWeight: '700', color: '#09090b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Actions rapides</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px' }}>
          <QuickActionCard icon={Users} title="Gerer les clients" description="Ajouter, modifier vos clients" onClick={() => navigate('/clients')} />
          <QuickActionCard icon={FileText} title="Creer une facture" description="Nouvelle facture client" onClick={() => navigate('/invoices')} />
          <QuickActionCard icon={FilePen} title="Creer une soumission" description="Devis pour prospect" onClick={() => navigate('/quotes')} />
          <QuickActionCard icon={Receipt} title="Ajouter une depense" description="Suivre vos depenses" onClick={() => navigate('/expenses')} />
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
