import React, { useState } from 'react';
import axios from 'axios';
import { X, Trash2, Plus } from 'lucide-react';
import { BACKEND_URL } from '../config';
import { useAuth } from '../context/AuthContext';
import { todayQuebecISO } from '../utils/dateQuebec';

const METHOD_OPTIONS = [
  { value: 'cash', label: 'Comptant' },
  { value: 'cheque', label: 'Chèque' },
  { value: 'transfer', label: 'Virement bancaire' },
  { value: 'etransfer', label: 'Virement Interac' },
  { value: 'card', label: 'Carte' },
  { value: 'stripe', label: 'Stripe' },
  { value: 'other', label: 'Autre' },
];

const fmt = (n) => Number(n || 0).toFixed(2);

const PaymentModal = ({ invoice, onClose, onUpdated, token: tokenProp }) => {
  const auth = useAuth();
  const token = tokenProp || auth?.token;

  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({
    amount_cad: '',
    method: 'cheque',
    date: todayQuebecISO(),
    reference: '',
  });
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  if (!invoice) return null;

  const payments = invoice.payments || [];
  const totalPaid = payments.reduce((s, p) => s + Number(p.amount_cad || 0), 0);
  const outstanding = Math.max(0, Number(invoice.total || 0) - totalPaid);
  const headers = { Authorization: `Bearer ${token}` };

  const reset = () => {
    setForm({
      amount_cad: '',
      method: 'cheque',
      date: todayQuebecISO(),
      reference: '',
    });
    setErr(null);
    setAdding(false);
  };

  const submit = async (e) => {
    e.preventDefault();
    setErr(null);
    const amt = Number(form.amount_cad);
    if (!amt || amt <= 0) {
      setErr('Le montant doit être supérieur à 0.');
      return;
    }
    setBusy(true);
    try {
      const res = await axios.post(
        `${BACKEND_URL}/api/invoices/${invoice.id}/payments`,
        { ...form, amount_cad: amt },
        { headers }
      );
      onUpdated && onUpdated(res.data);
      reset();
    } catch (e2) {
      setErr(e2.response?.data?.detail || "Erreur lors de l'ajout du paiement.");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (pid) => {
    if (!window.confirm('Supprimer ce paiement ?')) return;
    setBusy(true);
    try {
      const res = await axios.delete(
        `${BACKEND_URL}/api/invoices/${invoice.id}/payments/${pid}`,
        { headers }
      );
      onUpdated && onUpdated(res.data);
    } catch (e2) {
      setErr(e2.response?.data?.detail || 'Erreur lors de la suppression.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
        background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center',
        justifyContent: 'center', zIndex: 1000, padding: '20px',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: 'white', borderRadius: '16px', width: '90%', maxWidth: 640,
          maxHeight: '85vh', overflow: 'auto', padding: '32px', position: 'relative',
        }}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h2 style={{ margin: 0, fontSize: 20, color: '#1f2937' }}>
            Paiements — Facture {invoice.invoice_number || invoice.id?.slice(0, 8)}
          </h2>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#6b7280', fontSize: 24 }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Summary */}
        <div style={{
          background: '#f8fafb', borderRadius: 8, padding: 16, marginBottom: 20,
          display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12,
        }}>
          <div>
            <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 4 }}>Total facture</div>
            <div style={{ fontWeight: 600, color: '#1f2937' }}>{fmt(invoice.total)} $</div>
          </div>
          <div>
            <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 4 }}>Total payé</div>
            <div style={{ fontWeight: 600, color: '#059669' }}>{fmt(totalPaid)} $</div>
          </div>
          <div>
            <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 4 }}>Solde dû</div>
            <div style={{ fontWeight: 600, color: outstanding > 0 ? '#dc2626' : '#059669' }}>
              {fmt(outstanding)} $
            </div>
          </div>
        </div>

        {/* Payment history */}
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8, color: '#374151' }}>Historique</h3>
        {payments.length === 0 ? (
          <p style={{ color: '#6b7280', fontStyle: 'italic', margin: '8px 0 16px' }}>
            Aucun paiement enregistré.
          </p>
        ) : (
          <table style={{ width: '100%', fontSize: 14, marginBottom: 16, borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#f3f4f6' }}>
                <th style={{ textAlign: 'left', padding: '8px 6px', fontWeight: 600, color: '#374151' }}>Date</th>
                <th style={{ textAlign: 'left', padding: '8px 6px', fontWeight: 600, color: '#374151' }}>Méthode</th>
                <th style={{ textAlign: 'left', padding: '8px 6px', fontWeight: 600, color: '#374151' }}>Référence</th>
                <th style={{ textAlign: 'right', padding: '8px 6px', fontWeight: 600, color: '#374151' }}>Montant</th>
                <th style={{ width: 36 }}></th>
              </tr>
            </thead>
            <tbody>
              {payments.map((p) => (
                <tr key={p.id} style={{ borderBottom: '1px solid #e5e7eb' }}>
                  <td style={{ padding: '8px 6px', color: '#374151' }}>{p.date}</td>
                  <td style={{ padding: '8px 6px', color: '#374151' }}>
                    {METHOD_OPTIONS.find((m) => m.value === p.method)?.label || p.method}
                  </td>
                  <td style={{ padding: '8px 6px', color: '#6b7280' }}>{p.reference || '—'}</td>
                  <td style={{ padding: '8px 6px', textAlign: 'right', fontWeight: 500 }}>{fmt(p.amount_cad)} $</td>
                  <td style={{ padding: '8px 6px' }}>
                    <button
                      onClick={() => remove(p.id)}
                      disabled={busy}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#dc2626', padding: 2 }}
                    >
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* Add payment */}
        {err && (
          <div style={{
            background: '#fee2e2', border: '1px solid #fecaca', borderRadius: 8,
            padding: '10px 12px', marginBottom: 12, color: '#b91c1c', fontSize: 13,
          }}>
            {err}
          </div>
        )}

        {!adding ? (
          outstanding > 0 && (
            <button
              onClick={() => setAdding(true)}
              style={{
                background: '#00A08C', color: 'white', border: 'none',
                padding: '10px 18px', borderRadius: 8, cursor: 'pointer',
                display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 14, fontWeight: 500,
              }}
            >
              <Plus size={16} /> Ajouter un paiement
            </button>
          )
        ) : (
          <form onSubmit={submit} style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
              <label style={{ fontSize: 13, fontWeight: 500, color: '#374151' }}>
                Montant ($CAD)
                <input
                  type="number" step="0.01" min="0.01" required
                  value={form.amount_cad}
                  onChange={(e) => setForm({ ...form, amount_cad: e.target.value })}
                  style={{ display: 'block', width: '100%', padding: '8px 10px', marginTop: 4, border: '1px solid #ddd', borderRadius: 6, boxSizing: 'border-box' }}
                />
              </label>
              <label style={{ fontSize: 13, fontWeight: 500, color: '#374151' }}>
                Date
                <input
                  type="date" required
                  value={form.date}
                  onChange={(e) => setForm({ ...form, date: e.target.value })}
                  style={{ display: 'block', width: '100%', padding: '8px 10px', marginTop: 4, border: '1px solid #ddd', borderRadius: 6, boxSizing: 'border-box' }}
                />
              </label>
              <label style={{ fontSize: 13, fontWeight: 500, color: '#374151' }}>
                Méthode
                <select
                  value={form.method}
                  onChange={(e) => setForm({ ...form, method: e.target.value })}
                  style={{ display: 'block', width: '100%', padding: '8px 10px', marginTop: 4, border: '1px solid #ddd', borderRadius: 6, boxSizing: 'border-box' }}
                >
                  {METHOD_OPTIONS.map((m) => (
                    <option key={m.value} value={m.value}>{m.label}</option>
                  ))}
                </select>
              </label>
              <label style={{ fontSize: 13, fontWeight: 500, color: '#374151' }}>
                Référence
                <input
                  type="text" placeholder="N° chèque, transaction…"
                  value={form.reference}
                  onChange={(e) => setForm({ ...form, reference: e.target.value })}
                  style={{ display: 'block', width: '100%', padding: '8px 10px', marginTop: 4, border: '1px solid #ddd', borderRadius: 6, boxSizing: 'border-box' }}
                />
              </label>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                type="submit" disabled={busy}
                style={{
                  background: busy ? '#9ca3af' : '#059669', color: 'white', border: 'none',
                  padding: '8px 16px', borderRadius: 6, cursor: 'pointer', fontWeight: 500,
                }}
              >
                {busy ? '...' : 'Enregistrer'}
              </button>
              <button
                type="button" onClick={reset}
                style={{ background: '#f3f4f6', border: 'none', padding: '8px 16px', borderRadius: 6, cursor: 'pointer' }}
              >
                Annuler
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};

export default PaymentModal;
