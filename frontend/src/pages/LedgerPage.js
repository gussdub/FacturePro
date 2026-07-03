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

function JournalTab() {
  const { hasPermission } = useAuth();
  const canWrite = hasPermission('accounting:write');
  const [entries, setEntries] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [entryDate, setEntryDate] = useState(new Date().toISOString().slice(0, 10));
  const [description, setDescription] = useState('');
  const [lines, setLines] = useState([
    { account_id: '', debit: '', credit: '' },
    { account_id: '', debit: '', credit: '' },
  ]);
  const [error, setError] = useState(null);

  const load = () => {
    axios.get(`${BACKEND_URL}/api/ledger/entries`).then(r => setEntries(r.data)).catch(() => {});
    axios.get(`${BACKEND_URL}/api/ledger/accounts?active=true`)
      .then(r => setAccounts(r.data)).catch(() => {});
  };
  useEffect(() => { load(); }, []);

  // Le compteur live doit refléter EXACTEMENT ce qui sera envoyé au backend :
  // submit() ne garde que les lignes ayant un compte sélectionné. Compter les
  // lignes sans compte fausserait l'indicateur (montant tapé sur une ligne
  // « — compte — » → compteur « équilibré » mais l'écriture postée serait
  // déséquilibrée / < 2 lignes → 400 backend). On dérive tout du même sous-ensemble.
  const validLines = lines.filter(l => l.account_id);
  const totalDebit = validLines.reduce((s, l) => s + (parseFloat(l.debit) || 0), 0);
  const totalCredit = validLines.reduce((s, l) => s + (parseFloat(l.credit) || 0), 0);
  const diff = Math.round((totalDebit - totalCredit) * 100) / 100;
  // Équilibré = >= 2 lignes valides ET Dr = Cr (à 0,005 $) ET total > 0.
  // Mêmes invariants que _validate_entry_balance côté backend (§5.1).
  const balanced = validLines.length >= 2 && Math.abs(diff) < 0.005 && totalDebit > 0;

  const setLine = (i, field, value) => {
    const next = [...lines];
    next[i] = { ...next[i], [field]: value };
    // débit et crédit mutuellement exclusifs
    if (field === 'debit' && value) next[i].credit = '';
    if (field === 'credit' && value) next[i].debit = '';
    setLines(next);
  };
  const addLine = () => setLines([...lines, { account_id: '', debit: '', credit: '' }]);

  const submit = async (status) => {
    setError(null);
    try {
      await axios.post(`${BACKEND_URL}/api/ledger/entries`, {
        entry_date: entryDate, description, status,
        // Même sous-ensemble que le compteur d'équilibre (validLines) : ce qui est
        // affiché comme équilibré est exactement ce qui est envoyé.
        lines: validLines.map(l => ({
          account_id: l.account_id,
          debit: parseFloat(l.debit) || 0,
          credit: parseFloat(l.credit) || 0,
        })),
      });
      setShowModal(false);
      setLines([{ account_id: '', debit: '', credit: '' }, { account_id: '', debit: '', credit: '' }]);
      setDescription('');
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur');
    }
  };

  const reverse = async (id) => {
    if (!window.confirm('Contre-passer cette écriture ?')) return;
    try { await axios.post(`${BACKEND_URL}/api/ledger/entries/${id}/reverse`, {}); load(); }
    catch (err) { alert(err.response?.data?.detail || 'Erreur'); }
  };

  // Statuts d'écriture = draft | posted UNIQUEMENT (pas de 'reversed', §5.3).
  // Une écriture contre-passée reste 'posted' ; on la signale via reversed_by_entry_id.
  const STATUS_FR = { draft: 'Brouillon', posted: 'Postée' };
  const statusLabel = (e) =>
    e.reversed_by_entry_id ? 'Postée (contre-passée)'
      : e.entry_type === 'reversal' ? 'Postée (contre-passation)'
      : (STATUS_FR[e.status] || e.status);

  return (
    <div>
      {/* ⚠️ Avertissement Clôture annuelle (spec §7.2.1) — toujours visible */}
      <div style={{ background: '#FEF3C7', border: '1px solid #F59E0B',
        borderRadius: 6, padding: '10px 14px', marginBottom: 16, fontSize: 13,
        color: '#92400E' }}>
        <strong>Clôture annuelle</strong> — Le système ne clôture pas l'exercice
        automatiquement. À (ou après) la fin de votre exercice, passez une écriture
        de clôture manuelle (Dr Revenus / Cr Dépenses / vers Bénéfices non répartis 3200).
        Ne clôturez <strong>jamais en cours d'exercice</strong>. Un oubli
        <strong> déséquilibrera le bilan de l'exercice suivant</strong>.
      </div>
      {canWrite && (
        <button onClick={() => setShowModal(true)} style={{
          background: '#00A08C', color: '#fff', border: 'none', padding: '8px 16px',
          borderRadius: 6, cursor: 'pointer', marginBottom: 16, fontWeight: 600 }}>
          + Nouvelle écriture</button>
      )}
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
        <thead>
          <tr style={{ borderBottom: '2px solid #e5e7eb', textAlign: 'left' }}>
            <th style={{ padding: 8 }}>N°</th><th style={{ padding: 8 }}>Date</th>
            <th style={{ padding: 8 }}>Description</th>
            <th style={{ padding: 8, textAlign: 'right' }}>Débit total</th>
            <th style={{ padding: 8 }}>Statut</th>
            {canWrite && <th></th>}
          </tr>
        </thead>
        <tbody>
          {entries.map(e => (
            <tr key={e.id} style={{ borderBottom: '1px solid #f3f4f6' }}>
              <td style={{ padding: 8, fontFamily: 'monospace' }}>{e.entry_number}</td>
              <td style={{ padding: 8 }}>{e.entry_date}</td>
              <td style={{ padding: 8 }}>{e.description}</td>
              <td style={{ padding: 8, textAlign: 'right' }}>{e.total_debit.toFixed(2)} $</td>
              <td style={{ padding: 8 }}>{statusLabel(e)}</td>
              {canWrite && (
                <td style={{ padding: 8 }}>
                  {/* Contre-passer seulement si postée ET pas déjà contre-passée */}
                  {e.status === 'posted' && !e.reversed_by_entry_id
                    && e.entry_type !== 'reversal' && (
                    <button onClick={() => reverse(e.id)} style={{
                      background: 'none', border: '1px solid #d1d5db', borderRadius: 4,
                      padding: '2px 8px', cursor: 'pointer', fontSize: 12 }}>
                      Contre-passer</button>
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
          <div style={{ background: '#fff', borderRadius: 8, padding: 24,
            width: 720, maxWidth: '95vw', maxHeight: '90vh', overflow: 'auto' }}>
            <h2 style={{ marginTop: 0 }}>Nouvelle écriture</h2>
            <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
              <input type="date" value={entryDate} onChange={e => setEntryDate(e.target.value)}
                     style={{ padding: 8, border: '1px solid #d1d5db', borderRadius: 6 }} />
              <input placeholder="Description" value={description}
                     onChange={e => setDescription(e.target.value)}
                     style={{ flex: 1, padding: 8, border: '1px solid #d1d5db', borderRadius: 6 }} />
            </div>
            <table style={{ width: '100%', fontSize: 13, marginBottom: 8 }}>
              <thead><tr><th style={{ textAlign: 'left' }}>Compte</th>
                <th>Débit</th><th>Crédit</th></tr></thead>
              <tbody>
                {lines.map((l, i) => (
                  <tr key={i}>
                    <td>
                      <select value={l.account_id}
                              onChange={e => setLine(i, 'account_id', e.target.value)}
                              style={{ width: '100%', padding: 6 }}>
                        <option value="">— compte —</option>
                        {accounts.map(a => (
                          <option key={a.id} value={a.id}>{a.account_number} — {a.name}</option>
                        ))}
                      </select>
                    </td>
                    <td><input type="number" step="0.01" value={l.debit}
                               onChange={e => setLine(i, 'debit', e.target.value)}
                               style={{ width: 100, padding: 6 }} /></td>
                    <td><input type="number" step="0.01" value={l.credit}
                               onChange={e => setLine(i, 'credit', e.target.value)}
                               style={{ width: 100, padding: 6 }} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
            <button onClick={addLine} style={{ background: 'none', border: '1px dashed #d1d5db',
              borderRadius: 6, padding: '4px 12px', cursor: 'pointer', fontSize: 13,
              marginBottom: 12 }}>+ Ligne</button>

            <div style={{ display: 'flex', gap: 24, padding: 12,
              background: balanced ? '#ecfdf5' : '#fef2f2', borderRadius: 6, marginBottom: 12 }}>
              <span>Total Dr : <strong>{totalDebit.toFixed(2)} $</strong></span>
              <span>Total Cr : <strong>{totalCredit.toFixed(2)} $</strong></span>
              <span>Écart : <strong style={{ color: balanced ? '#059669' : '#dc2626' }}>
                {diff.toFixed(2)} $</strong></span>
            </div>
            {error && <div style={{ color: '#991b1b', fontSize: 13, marginBottom: 12 }}>{error}</div>}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button onClick={() => setShowModal(false)} style={{ background: '#fff',
                border: '1px solid #d1d5db', padding: '8px 16px', borderRadius: 6,
                cursor: 'pointer' }}>Annuler</button>
              <button onClick={() => submit('draft')} disabled={!balanced} style={{
                background: '#6b7280', color: '#fff', border: 'none', padding: '8px 16px',
                borderRadius: 6, cursor: balanced ? 'pointer' : 'not-allowed',
                opacity: balanced ? 1 : 0.5 }}>Enregistrer brouillon</button>
              <button onClick={() => submit('posted')} disabled={!balanced} style={{
                background: '#00A08C', color: '#fff', border: 'none', padding: '8px 16px',
                borderRadius: 6, cursor: balanced ? 'pointer' : 'not-allowed',
                fontWeight: 600, opacity: balanced ? 1 : 0.5 }}>Poster</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function OpeningTab() {
  const [accounts, setAccounts] = useState([]);
  const [openingDate, setOpeningDate] = useState('2026-01-01');
  const [balances, setBalances] = useState({}); // account_id -> {debit, credit}
  const [existing, setExisting] = useState(null);
  const [error, setError] = useState(null);
  const [ok, setOk] = useState(false);

  const load = () => {
    axios.get(`${BACKEND_URL}/api/ledger/accounts?active=true`)
      .then(r => setAccounts(r.data)).catch(() => {});
    axios.get(`${BACKEND_URL}/api/ledger/opening-balance`)
      .then(r => setExisting(r.data)).catch(() => {});
  };
  useEffect(() => { load(); }, []);

  const set = (id, field, value) => {
    setBalances(prev => {
      const next = { ...prev, [id]: { ...(prev[id] || {}), [field]: value } };
      if (field === 'debit' && value) next[id].credit = '';
      if (field === 'credit' && value) next[id].debit = '';
      return next;
    });
  };

  const rows = Object.entries(balances)
    .map(([id, v]) => ({ account_id: id,
      debit: parseFloat(v.debit) || 0, credit: parseFloat(v.credit) || 0 }))
    .filter(r => r.debit > 0 || r.credit > 0);
  const totalDr = rows.reduce((s, r) => s + r.debit, 0);
  const totalCr = rows.reduce((s, r) => s + r.credit, 0);
  const balanced = Math.abs(totalDr - totalCr) < 0.005 && totalDr > 0;

  const submit = async () => {
    setError(null); setOk(false);
    const method = existing?.exists ? 'put' : 'post';
    try {
      await axios[method](`${BACKEND_URL}/api/ledger/opening-balance`,
        { opening_date: openingDate, balances: rows });
      setOk(true); load();
    } catch (err) { setError(err.response?.data?.detail || 'Erreur'); }
  };

  return (
    <div>
      <div style={{ background: '#eff6ff', padding: 12, borderRadius: 6, marginBottom: 16,
        fontSize: 13, color: '#1e3a8a' }}>
        Saisissez la balance de vérification d'ouverture fournie par votre comptable.
        Les débits doivent égaler les crédits.
      </div>
      {existing?.exists && (
        <div style={{ color: '#92400e', fontSize: 13, marginBottom: 12 }}>
          Un bilan d'ouverture existe déjà ({existing.opening_date}). L'enregistrement le remplacera.
        </div>
      )}
      <label style={{ fontSize: 13, fontWeight: 600 }}>Date d'ouverture{' '}
        <input type="date" value={openingDate} onChange={e => setOpeningDate(e.target.value)}
               style={{ padding: 6, border: '1px solid #d1d5db', borderRadius: 6 }} />
      </label>
      <table style={{ width: '100%', fontSize: 13, marginTop: 12 }}>
        <thead><tr style={{ textAlign: 'left', borderBottom: '2px solid #e5e7eb' }}>
          <th style={{ padding: 6 }}>Compte</th><th>Débit</th><th>Crédit</th></tr></thead>
        <tbody>
          {accounts.map(a => (
            <tr key={a.id} style={{ borderBottom: '1px solid #f3f4f6' }}>
              <td style={{ padding: 6 }}>{a.account_number} — {a.name}</td>
              <td><input type="number" step="0.01" value={balances[a.id]?.debit || ''}
                         onChange={e => set(a.id, 'debit', e.target.value)}
                         style={{ width: 100, padding: 4 }} /></td>
              <td><input type="number" step="0.01" value={balances[a.id]?.credit || ''}
                         onChange={e => set(a.id, 'credit', e.target.value)}
                         style={{ width: 100, padding: 4 }} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ display: 'flex', gap: 24, padding: 12, marginTop: 12,
        background: balanced ? '#ecfdf5' : '#fef2f2', borderRadius: 6 }}>
        <span>Total Dr : <strong>{totalDr.toFixed(2)} $</strong></span>
        <span>Total Cr : <strong>{totalCr.toFixed(2)} $</strong></span>
        <span style={{ color: balanced ? '#059669' : '#dc2626' }}>
          {balanced ? 'Équilibré' : 'Déséquilibré'}</span>
      </div>
      {error && <div style={{ color: '#991b1b', fontSize: 13, marginTop: 8 }}>{error}</div>}
      {ok && <div style={{ color: '#059669', fontSize: 13, marginTop: 8 }}>Bilan d'ouverture enregistré.</div>}
      <button onClick={submit} disabled={!balanced} style={{ marginTop: 12,
        background: '#00A08C', color: '#fff', border: 'none', padding: '10px 20px',
        borderRadius: 6, cursor: balanced ? 'pointer' : 'not-allowed', fontWeight: 600,
        opacity: balanced ? 1 : 0.5 }}>Enregistrer le bilan d'ouverture</button>
    </div>
  );
}

function ContributionTab() {
  const [amount, setAmount] = useState('');
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [error, setError] = useState(null);
  const [ok, setOk] = useState(false);

  const submit = async () => {
    setError(null); setOk(false);
    try {
      await axios.post(`${BACKEND_URL}/api/ledger/owner-contribution`,
        { amount: parseFloat(amount), date });
      setOk(true); setAmount('');
    } catch (err) { setError(err.response?.data?.detail || 'Erreur'); }
  };

  return (
    <div style={{ maxWidth: 480 }}>
      <div style={{ background: '#eff6ff', padding: 12, borderRadius: 6, marginBottom: 16,
        fontSize: 13, color: '#1e3a8a' }}>
        Enregistre un apport personnel dans l'entreprise.
      </div>
      <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>Montant</label>
      <input type="number" step="0.01" value={amount} onChange={e => setAmount(e.target.value)}
             style={{ width: '100%', padding: 8, marginBottom: 12, border: '1px solid #d1d5db',
                      borderRadius: 6, boxSizing: 'border-box' }} />
      <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>Date</label>
      <input type="date" value={date} onChange={e => setDate(e.target.value)}
             style={{ padding: 8, marginBottom: 12, border: '1px solid #d1d5db', borderRadius: 6 }} />
      {amount > 0 && (
        <div style={{ background: '#f3f4f6', padding: 12, borderRadius: 6, marginBottom: 12, fontSize: 13 }}>
          Cela enregistrera : <strong>Débit Encaisse {parseFloat(amount).toFixed(2)} $</strong> /{' '}
          <strong>Crédit Apport du propriétaire {parseFloat(amount).toFixed(2)} $</strong>
        </div>
      )}
      {error && <div style={{ color: '#991b1b', fontSize: 13, marginBottom: 8 }}>{error}</div>}
      {ok && <div style={{ color: '#059669', fontSize: 13, marginBottom: 8 }}>Apport enregistré.</div>}
      <button onClick={submit} disabled={!(amount > 0)} style={{
        background: '#00A08C', color: '#fff', border: 'none', padding: '10px 20px',
        borderRadius: 6, cursor: amount > 0 ? 'pointer' : 'not-allowed', fontWeight: 600,
        opacity: amount > 0 ? 1 : 0.5 }}>Enregistrer l'apport</button>
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
        {tab === 'journal' && <JournalTab />}
        {tab === 'opening' && <OpeningTab />}
        {tab === 'contribution' && <ContributionTab />}
      </div>
    </div>
  );
}
