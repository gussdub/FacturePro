import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { BACKEND_URL } from '../config';
import { useAuth } from '../context/AuthContext';

const TABS = [
  { key: 'accounts', label: 'Plan comptable' },
  { key: 'journal', label: 'Journal' },
  { key: 'opening', label: 'Bilan d\'ouverture' },
  { key: 'contribution', label: 'Apport' },
  { key: 'ledger', label: 'Grand livre' },
  { key: 'trial', label: 'Balance de vérification' },
  { key: 'balancesheet', label: 'Bilan' },
];

function AccountsTab() {
  const { hasPermission } = useAuth();
  const canWrite = hasPermission('accounting:write');
  const [accounts, setAccounts] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ account_number: '', name: '', sub_type: '' });
  const [error, setError] = useState(null);

  const load = () => {
    axios.get(`${BACKEND_URL}/api/ledger/accounts`)
      .then(r => setAccounts(r.data)).catch(() => {});
  };
  useEffect(() => { load(); }, []);

  const create = async (e) => {
    e.preventDefault();
    setError(null);
    try {
      await axios.post(`${BACKEND_URL}/api/ledger/accounts`, form);
      setShowModal(false);
      setForm({ account_number: '', name: '', sub_type: '' });
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur');
    }
  };

  const remove = async (id) => {
    if (!window.confirm('Supprimer ce compte ?')) return;
    try { await axios.delete(`${BACKEND_URL}/api/ledger/accounts/${id}`); load(); }
    catch (err) { alert(err.response?.data?.detail || 'Erreur'); }
  };

  const toggleActive = async (a) => {
    try {
      await axios.put(`${BACKEND_URL}/api/ledger/accounts/${a.id}`,
                      { is_active: !a.is_active });
      load();
    } catch (err) { alert(err.response?.data?.detail || 'Erreur'); }
  };

  const TYPE_FR = { asset: 'Actif', liability: 'Passif', equity: 'Capitaux propres',
                    revenue: 'Revenus', expense: 'Dépenses' };

  return (
    <div>
      {canWrite && (
        <button onClick={() => setShowModal(true)} style={{
          background: '#00A08C', color: '#fff', border: 'none', padding: '8px 16px',
          borderRadius: 6, cursor: 'pointer', marginBottom: 16, fontWeight: 600,
        }}>+ Nouveau compte</button>
      )}
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
        <thead>
          <tr style={{ borderBottom: '2px solid #e5e7eb', textAlign: 'left' }}>
            <th style={{ padding: 8 }}>Numéro</th>
            <th style={{ padding: 8 }}>Nom</th>
            <th style={{ padding: 8 }}>Type</th>
            <th style={{ padding: 8 }}>Solde normal</th>
            <th style={{ padding: 8 }}>Actif</th>
            {canWrite && <th style={{ padding: 8 }}></th>}
          </tr>
        </thead>
        <tbody>
          {accounts.map(a => (
            <tr key={a.id} style={{ borderBottom: '1px solid #f3f4f6',
                                    opacity: a.is_active ? 1 : 0.5 }}>
              <td style={{ padding: 8, fontFamily: 'monospace' }}>{a.account_number}</td>
              <td style={{ padding: 8 }}>{a.name}</td>
              <td style={{ padding: 8 }}>{TYPE_FR[a.account_type]}</td>
              <td style={{ padding: 8 }}>{a.normal_balance === 'debit' ? 'Débit' : 'Crédit'}</td>
              <td style={{ padding: 8 }}>{a.is_active ? 'Oui' : 'Non'}</td>
              {canWrite && (
                <td style={{ padding: 8 }}>
                  <button onClick={() => toggleActive(a)} style={{ marginRight: 8,
                    background: 'none', border: '1px solid #d1d5db', borderRadius: 4,
                    padding: '2px 8px', cursor: 'pointer', fontSize: 12 }}>
                    {a.is_active ? 'Désactiver' : 'Activer'}
                  </button>
                  {!a.is_system && (
                    <button onClick={() => remove(a.id)} style={{
                      background: 'none', border: '1px solid #fca5a5', color: '#991b1b',
                      borderRadius: 4, padding: '2px 8px', cursor: 'pointer', fontSize: 12 }}>
                      Suppr.
                    </button>
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>

      {showModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
          display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000 }}>
          <form onSubmit={create} style={{ background: '#fff', borderRadius: 8,
            padding: 24, width: 420, maxWidth: '90vw' }}>
            <h2 style={{ marginTop: 0 }}>Nouveau compte</h2>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
              Numéro (1000-5999)</label>
            <input required value={form.account_number}
                   onChange={e => setForm({ ...form, account_number: e.target.value })}
                   placeholder="1500"
                   style={{ width: '100%', padding: 8, marginBottom: 12,
                            border: '1px solid #d1d5db', borderRadius: 6, boxSizing: 'border-box' }} />
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
              Nom</label>
            <input required value={form.name}
                   onChange={e => setForm({ ...form, name: e.target.value })}
                   style={{ width: '100%', padding: 8, marginBottom: 12,
                            border: '1px solid #d1d5db', borderRadius: 6, boxSizing: 'border-box' }} />
            {error && <div style={{ color: '#991b1b', fontSize: 13, marginBottom: 12 }}>{error}</div>}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button type="button" onClick={() => setShowModal(false)} style={{
                background: '#fff', border: '1px solid #d1d5db', padding: '8px 16px',
                borderRadius: 6, cursor: 'pointer' }}>Annuler</button>
              <button type="submit" style={{ background: '#00A08C', color: '#fff',
                border: 'none', padding: '8px 16px', borderRadius: 6, cursor: 'pointer',
                fontWeight: 600 }}>Créer</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

export default function LedgerPage() {
  const [tab, setTab] = useState('accounts');
  return (
    <div style={{ padding: 24 }}>
      <h1 style={{ fontSize: 24, marginBottom: 16 }}>Grand livre</h1>
      <div style={{ display: 'flex', gap: 8, borderBottom: '1px solid #e5e7eb', marginBottom: 24, flexWrap: 'wrap' }}>
        {TABS.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)} style={{
            background: 'none', border: 'none', padding: '10px 14px', cursor: 'pointer',
            fontSize: 14, fontWeight: tab === t.key ? 700 : 500,
            color: tab === t.key ? '#00A08C' : '#6b7280',
            borderBottom: tab === t.key ? '2px solid #00A08C' : '2px solid transparent',
          }}>
            {t.label}
          </button>
        ))}
      </div>
      <div>{/* Onglets remplis aux Tasks 14-17 */}
        {tab === 'accounts' && <AccountsTab />}
      </div>
    </div>
  );
}
