import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { BACKEND_URL } from '../config';
import { useAuth } from '../context/AuthContext';
import {
  formatCoverage, sourceDocRoute, sourceDocLabel, isAutoEntry, backfillTotal,
} from '../utils/ledgerAutopost';

const TABS = [
  { key: 'accounts', label: 'Plan comptable' },
  { key: 'journal', label: 'Journal' },
  { key: 'autopost', label: 'Auto-posting' },
  { key: 'opening', label: 'Bilan d\'ouverture' },
  { key: 'contribution', label: 'Apport' },
  { key: 'ledger', label: 'Grand livre' },
  { key: 'trial', label: 'Balance de vérification' },
  { key: 'balancesheet', label: 'Bilan' },
];

// Navigation manuelle (pas de router lib) — aligne sur App.js navigate().
const goTo = (path) => {
  window.history.pushState({}, '', path);
  window.dispatchEvent(new PopStateEvent('popstate'));
};

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

export function JournalTab() {
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
          {entries.map(e => {
            const auto = isAutoEntry(e);
            const srcRoute = auto ? sourceDocRoute(e.source_type) : null;
            return (
            <tr key={e.id} style={{ borderBottom: '1px solid #f3f4f6' }}>
              <td style={{ padding: 8, fontFamily: 'monospace' }}>{e.entry_number}</td>
              <td style={{ padding: 8 }}>{e.entry_date}</td>
              <td style={{ padding: 8 }}>
                {e.description}
                {auto && (
                  <>
                    {/* Pastille « Auto » : écriture générée par l'auto-posting (§8.3).
                        Verrouillée — pas de contre-passation manuelle possible. */}
                    <span title="Écriture générée automatiquement depuis un document source (verrouillée)"
                      style={{ marginLeft: 8, background: '#EDE9FE', color: '#5B21B6',
                        border: '1px solid #C4B5FD', borderRadius: 4, padding: '1px 6px',
                        fontSize: 11, fontWeight: 600 }}>Auto</span>
                    {srcRoute && (
                      <button onClick={() => goTo(srcRoute)} title="Ouvrir le document source"
                        style={{ marginLeft: 6, background: 'none', border: 'none',
                          color: '#00A08C', cursor: 'pointer', fontSize: 12,
                          textDecoration: 'underline', padding: 0 }}>
                        {sourceDocLabel(e.source_type)} →</button>
                    )}
                  </>
                )}
              </td>
              <td style={{ padding: 8, textAlign: 'right' }}>{e.total_debit.toFixed(2)} $</td>
              <td style={{ padding: 8 }}>{statusLabel(e)}</td>
              {canWrite && (
                <td style={{ padding: 8 }}>
                  {/* Contre-passer seulement si postée, pas déjà contre-passée, ET
                      NON auto (les auto se gèrent via le document source, verrou §8.3). */}
                  {!auto && e.status === 'posted' && !e.reversed_by_entry_id
                    && e.entry_type !== 'reversal' && (
                    <button onClick={() => reverse(e.id)} style={{
                      background: 'none', border: '1px solid #d1d5db', borderRadius: 4,
                      padding: '2px 8px', cursor: 'pointer', fontSize: 12 }}>
                      Contre-passer</button>
                  )}
                </td>
              )}
            </tr>
            );
          })}
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

// ─── Onglet Auto-posting (feature #12 Phase 2, §12) ───
// Gaté `accounting:read` au niveau route (App.js). Les actions d'écriture
// (toggle, sélecteur, réparation, backfill) sont gatées `accounting:write`.
export function AutopostTab() {
  const { hasPermission } = useAuth();
  const canWrite = hasPermission('accounting:write');

  const [status, setStatus] = useState(null);      // GET /autopost/status
  const [loading, setLoading] = useState(true);
  const [savingSettings, setSavingSettings] = useState(false);
  const [msg, setMsg] = useState(null);            // {type:'ok'|'err', text}
  const [repairing, setRepairing] = useState(false);

  // Assistant backfill
  const [bfStart, setBfStart] = useState('');
  const [bfEnd, setBfEnd] = useState('');
  const [bfPreview, setBfPreview] = useState(null); // réponse dry-run
  const [bfBusy, setBfBusy] = useState(false);
  const [bfResult, setBfResult] = useState(null);   // réponse apply

  const loadStatus = () => {
    setLoading(true);
    axios.get(`${BACKEND_URL}/api/ledger/autopost/status`)
      .then(r => setStatus(r.data))
      .catch(() => setStatus(null))
      .finally(() => setLoading(false));
  };
  useEffect(() => { loadStatus(); }, []);

  // Persiste un champ de settings via le PUT existant, puis recharge le statut.
  const saveSetting = async (patch) => {
    setSavingSettings(true); setMsg(null);
    try {
      await axios.put(`${BACKEND_URL}/api/settings/company`, patch);
      loadStatus();
    } catch (err) {
      setMsg({ type: 'err', text: err.response?.data?.detail || 'Erreur d\'enregistrement' });
    } finally {
      setSavingSettings(false);
    }
  };

  const toggleEnabled = () => {
    if (!status) return;
    saveSetting({ autopost_enabled: !status.enabled });
  };

  const changeCreditAccount = (value) => {
    saveSetting({ expense_default_credit_account: value });
  };

  const runRepair = async () => {
    setRepairing(true); setMsg(null);
    try {
      const r = await axios.post(`${BACKEND_URL}/api/ledger/autopost/repair`, {});
      const stillFailing = (r.data?.still_failing || []).length;
      setMsg({
        type: stillFailing ? 'err' : 'ok',
        text: stillFailing
          ? `${r.data.repaired} réparé(s), ${stillFailing} en échec persistant.`
          : `${r.data.repaired} écriture(s) réparée(s).`,
      });
      loadStatus();
    } catch (err) {
      setMsg({ type: 'err', text: err.response?.data?.detail || 'Erreur de réparation' });
    } finally {
      setRepairing(false);
    }
  };

  // Backfill : dry-run (aperçu) puis apply (confirmation).
  const previewBackfill = async () => {
    setBfBusy(true); setBfPreview(null); setBfResult(null); setMsg(null);
    try {
      const params = { dry_run: true };
      if (bfStart) params.start = bfStart;
      if (bfEnd) params.end = bfEnd;
      const r = await axios.post(`${BACKEND_URL}/api/ledger/autopost/backfill`, {}, { params });
      setBfPreview(r.data);
    } catch (err) {
      setMsg({ type: 'err', text: err.response?.data?.detail || 'Erreur d\'aperçu' });
    } finally {
      setBfBusy(false);
    }
  };

  const applyBackfill = async () => {
    setBfBusy(true); setMsg(null);
    try {
      const params = { dry_run: false };
      if (bfStart) params.start = bfStart;
      if (bfEnd) params.end = bfEnd;
      const r = await axios.post(`${BACKEND_URL}/api/ledger/autopost/backfill`, {}, { params });
      setBfResult(r.data);
      setBfPreview(null);
      loadStatus();
    } catch (err) {
      setMsg({ type: 'err', text: err.response?.data?.detail || 'Erreur d\'application' });
    } finally {
      setBfBusy(false);
    }
  };

  if (loading) return <div style={{ color: '#6b7280' }}>Chargement…</div>;
  if (!status) return <div style={{ color: '#991b1b' }}>Impossible de charger l'état de l'auto-posting.</div>;

  const cov = formatCoverage(status.coverage);
  const previewTotal = bfPreview ? backfillTotal(bfPreview.would_create) : 0;
  const cardStyle = { background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8,
    padding: 16, marginBottom: 16 };
  const sectionTitle = { fontSize: 15, fontWeight: 700, marginBottom: 12, marginTop: 0 };

  const CoverageBar = ({ percent, color }) => (
    <div style={{ background: '#f3f4f6', borderRadius: 4, height: 8, overflow: 'hidden', marginTop: 6 }}>
      <div style={{ width: `${percent}%`, background: color, height: '100%' }} />
    </div>
  );

  return (
    <div style={{ maxWidth: 760 }}>
      <div style={{ background: '#eff6ff', padding: 12, borderRadius: 6, marginBottom: 16,
        fontSize: 13, color: '#1e3a8a' }}>
        L'auto-posting génère automatiquement les écritures du grand livre à partir
        de vos factures, paiements et dépenses. Désactivé par défaut : activez-le,
        puis lancez un backfill sur votre exercice pour comptabiliser l'historique.
      </div>

      {msg && (
        <div style={{ padding: '10px 14px', borderRadius: 6, marginBottom: 16, fontSize: 13,
          background: msg.type === 'ok' ? '#ecfdf5' : '#fef2f2',
          color: msg.type === 'ok' ? '#065f46' : '#991b1b',
          border: `1px solid ${msg.type === 'ok' ? '#a7f3d0' : '#fecaca'}` }}>
          {msg.text}
        </div>
      )}

      {/* ── Activation + compte de crédit dépenses ── */}
      <div style={cardStyle}>
        <h3 style={sectionTitle}>Activation</h3>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontWeight: 600 }}>Auto-posting {status.enabled ? 'activé' : 'désactivé'}</div>
            <div style={{ fontSize: 12, color: '#6b7280' }}>
              {status.enabled
                ? 'Les nouvelles factures/paiements/dépenses sont comptabilisés automatiquement.'
                : 'Aucune écriture automatique n\'est générée.'}
            </div>
          </div>
          <button onClick={toggleEnabled} disabled={!canWrite || savingSettings}
            title={canWrite ? '' : 'Permission accounting:write requise'}
            style={{ border: 'none', borderRadius: 20, width: 52, height: 28, position: 'relative',
              cursor: canWrite && !savingSettings ? 'pointer' : 'not-allowed',
              background: status.enabled ? '#00A08C' : '#d1d5db',
              opacity: canWrite ? 1 : 0.5, transition: 'background 0.15s' }}>
            <span style={{ position: 'absolute', top: 3, left: status.enabled ? 27 : 3,
              width: 22, height: 22, borderRadius: '50%', background: '#fff',
              transition: 'left 0.15s' }} />
          </button>
        </div>

        <div style={{ marginTop: 16 }}>
          <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
            Compte de crédit des dépenses</label>
          <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 6 }}>
            Contrepartie créditée lors de la comptabilisation d'une dépense.
          </div>
          <select value={status.expense_default_credit_account}
            disabled={!canWrite || savingSettings}
            onChange={e => changeCreditAccount(e.target.value)}
            style={{ padding: 8, border: '1px solid #d1d5db', borderRadius: 6, fontSize: 14,
              cursor: canWrite ? 'pointer' : 'not-allowed', opacity: canWrite ? 1 : 0.6 }}>
            <option value="1000">1000 — Encaisse (payé comptant)</option>
            <option value="2000">2000 — Comptes fournisseurs (à payer)</option>
          </select>
        </div>
        {!canWrite && (
          <div style={{ marginTop: 12, fontSize: 12, color: '#92400e' }}>
            Lecture seule — la permission « comptabilité : écriture » est requise pour modifier ces réglages.
          </div>
        )}
      </div>

      {/* ── Couverture ── */}
      <div style={cardStyle}>
        <h3 style={sectionTitle}>Couverture</h3>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 220 }}>
            <div style={{ fontSize: 13, color: '#374151' }}>
              Factures postées <strong>{cov.invoices.posted}/{cov.invoices.total}</strong>
              {' '}({cov.invoices.percent} %)
            </div>
            <CoverageBar percent={cov.invoices.percent} color="#00A08C" />
          </div>
          <div style={{ flex: 1, minWidth: 220 }}>
            <div style={{ fontSize: 13, color: '#374151' }}>
              Dépenses postées <strong>{cov.expenses.posted}/{cov.expenses.total}</strong>
              {' '}({cov.expenses.percent} %)
            </div>
            <CoverageBar percent={cov.expenses.percent} color="#00A08C" />
          </div>
        </div>

        {/* Badge erreurs en attente + réparation */}
        <div style={{ marginTop: 16, display: 'flex', alignItems: 'center', gap: 12 }}>
          {status.pending_errors > 0 ? (
            <span style={{ background: '#FEE2E2', color: '#991B1B', border: '1px solid #FCA5A5',
              borderRadius: 6, padding: '4px 10px', fontSize: 13, fontWeight: 600 }}>
              ⚠ {status.pending_errors} écriture(s) en erreur
            </span>
          ) : (
            <span style={{ background: '#ecfdf5', color: '#065f46', border: '1px solid #a7f3d0',
              borderRadius: 6, padding: '4px 10px', fontSize: 13, fontWeight: 600 }}>
              ✓ Aucune erreur en attente
            </span>
          )}
          {canWrite && status.pending_errors > 0 && (
            <button onClick={runRepair} disabled={repairing}
              style={{ background: '#00A08C', color: '#fff', border: 'none', padding: '6px 14px',
                borderRadius: 6, cursor: repairing ? 'wait' : 'pointer', fontWeight: 600, fontSize: 13 }}>
              {repairing ? 'Réparation…' : 'Réparer'}
            </button>
          )}
        </div>
      </div>

      {/* ── Assistant backfill ── */}
      <div style={cardStyle}>
        <h3 style={sectionTitle}>Assistant de backfill</h3>
        <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 12 }}>
          Comptabilise l'historique existant sur une période. L'aperçu n'écrit rien ;
          l'application est idempotente (ne crée jamais de doublon). Période vide = exercice courant.
        </div>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end', marginBottom: 12 }}>
          <label style={{ fontSize: 13, fontWeight: 600 }}>Début{' '}
            <input type="date" value={bfStart} onChange={e => { setBfStart(e.target.value); setBfPreview(null); }}
              style={{ padding: 6, border: '1px solid #d1d5db', borderRadius: 6, display: 'block', marginTop: 4 }} />
          </label>
          <label style={{ fontSize: 13, fontWeight: 600 }}>Fin{' '}
            <input type="date" value={bfEnd} onChange={e => { setBfEnd(e.target.value); setBfPreview(null); }}
              style={{ padding: 6, border: '1px solid #d1d5db', borderRadius: 6, display: 'block', marginTop: 4 }} />
          </label>
          <button onClick={previewBackfill} disabled={!canWrite || bfBusy}
            style={{ background: '#fff', border: '1px solid #00A08C', color: '#00A08C',
              padding: '8px 16px', borderRadius: 6, fontWeight: 600, fontSize: 13,
              cursor: canWrite && !bfBusy ? 'pointer' : 'not-allowed', opacity: canWrite ? 1 : 0.5 }}>
            {bfBusy && !bfResult ? 'Calcul…' : 'Aperçu (dry-run)'}
          </button>
        </div>

        {bfPreview && (
          <div style={{ background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 6,
            padding: 12, fontSize: 13 }}>
            <div style={{ fontWeight: 700, marginBottom: 6 }}>
              {previewTotal} écriture(s) seront créées
              {' '}<span style={{ fontWeight: 400, color: '#6b7280' }}>
                (période {bfPreview.period?.start} → {bfPreview.period?.end})
              </span>
            </div>
            <ul style={{ margin: '6px 0', paddingLeft: 20, color: '#374151' }}>
              <li>Factures : {bfPreview.would_create?.invoice || 0}</li>
              <li>Paiements : {bfPreview.would_create?.invoice_payment || 0}</li>
              <li>Dépenses : {bfPreview.would_create?.expense || 0}</li>
            </ul>
            <div style={{ color: '#6b7280', marginBottom: 10 }}>
              Déjà comptabilisées (ignorées) : {bfPreview.skipped_existing || 0}
            </div>
            {canWrite && previewTotal > 0 && (
              <button onClick={applyBackfill} disabled={bfBusy}
                style={{ background: '#00A08C', color: '#fff', border: 'none', padding: '8px 16px',
                  borderRadius: 6, fontWeight: 600, fontSize: 13,
                  cursor: bfBusy ? 'wait' : 'pointer' }}>
                {bfBusy ? 'Application…' : `Confirmer et créer ${previewTotal} écriture(s)`}
              </button>
            )}
            {previewTotal === 0 && (
              <div style={{ color: '#065f46', fontWeight: 600 }}>
                Rien à créer — tout est déjà comptabilisé sur cette période.
              </div>
            )}
          </div>
        )}

        {bfResult && (
          <div style={{ background: '#ecfdf5', border: '1px solid #a7f3d0', borderRadius: 6,
            padding: 12, fontSize: 13, color: '#065f46' }}>
            <div style={{ fontWeight: 700, marginBottom: 6 }}>Backfill appliqué</div>
            <ul style={{ margin: '6px 0', paddingLeft: 20 }}>
              <li>Factures : {bfResult.created?.invoice || 0}</li>
              <li>Paiements : {bfResult.created?.invoice_payment || 0}</li>
              <li>Dépenses : {bfResult.created?.expense || 0}</li>
            </ul>
            {(bfResult.failed || []).length > 0 && (
              <div style={{ color: '#991b1b', marginTop: 6 }}>
                {bfResult.failed.length} échec(s) — voir le badge d'erreurs et « Réparer ».
              </div>
            )}
          </div>
        )}
      </div>
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

async function downloadPdf(url, filename) {
  const resp = await axios.get(url, { responseType: 'blob' });
  const blobUrl = window.URL.createObjectURL(new Blob([resp.data], { type: 'application/pdf' }));
  const a = document.createElement('a');
  a.href = blobUrl; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
  window.URL.revokeObjectURL(blobUrl);
}

// [COMPTA] Diagnostic orphelins — mêmes lignes que le PDF (unmapped_accounts).
// Une ligne d'écriture posted qui référence un account_id absent du plan comptable
// n'apparaît dans aucune colonne/section de compte, mais EST comptée dans les totaux
// (source de vérité partie double). Sans ce bloc, l'écran afficherait des totaux que
// la somme visuelle des lignes ne reconstitue pas — et un « Déséquilibré » sans cause
// affichée. On rend donc le diagnostic à l'écran, à l'identique du PDF.
function UnmappedAccountsNotice({ unmapped }) {
  if (!unmapped || unmapped.length === 0) return null;
  return (
    <div style={{ background: '#FEF2F2', border: '1px solid #DC2626', borderRadius: 6,
      padding: '8px 12px', marginTop: 12, fontSize: 12, color: '#991B1B' }}>
      <strong>Comptes hors plan (orphelins)</strong> — {unmapped.length} compte(s)
      référencé(s) par des écritures mais absent(s) du plan comptable. Leurs montants
      sont inclus dans les totaux mais n'apparaissent dans aucune ligne ci-dessus, ce
      qui explique tout écart entre la somme visuelle des colonnes et les totaux, et un
      éventuel « Déséquilibré ». À corriger (réassocier ou recréer le compte).
      <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 6, fontSize: 12 }}>
        <thead><tr style={{ textAlign: 'left' }}>
          <th style={{ padding: 4 }}>account_id</th>
          <th style={{ padding: 4, textAlign: 'right' }}>Débit</th>
          <th style={{ padding: 4, textAlign: 'right' }}>Crédit</th></tr></thead>
        <tbody>
          {unmapped.map(u => (
            <tr key={u.account_id}>
              <td style={{ padding: 4, fontFamily: 'monospace' }}>{u.account_id}</td>
              <td style={{ padding: 4, textAlign: 'right' }}>{u.debit.toFixed(2)} $</td>
              <td style={{ padding: 4, textAlign: 'right' }}>{u.credit.toFixed(2)} $</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TrialBalanceTab() {
  const [asOf, setAsOf] = useState(new Date().toISOString().slice(0, 10));
  const [data, setData] = useState(null);
  const load = () => axios.get(`${BACKEND_URL}/api/ledger/trial-balance?as_of=${asOf}`)
    .then(r => setData(r.data)).catch(() => {});
  useEffect(() => { load(); }, [asOf]);
  return (
    <div>
      <div style={{ display: 'flex', gap: 12, marginBottom: 16, alignItems: 'center' }}>
        <input type="date" value={asOf} onChange={e => setAsOf(e.target.value)}
               style={{ padding: 6, border: '1px solid #d1d5db', borderRadius: 6 }} />
        <button onClick={() => downloadPdf(
          `${BACKEND_URL}/api/ledger/trial-balance/pdf?as_of=${asOf}`,
          `balance-verification-${asOf}.pdf`)} style={{
          background: '#00A08C', color: '#fff', border: 'none', padding: '6px 14px',
          borderRadius: 6, cursor: 'pointer' }}>Télécharger PDF</button>
        {data && (
          <span style={{ padding: '4px 12px', borderRadius: 999, fontSize: 13,
            background: data.balanced ? '#ecfdf5' : '#fef2f2',
            color: data.balanced ? '#059669' : '#dc2626' }}>
            {data.balanced ? 'Équilibrée' : 'Déséquilibrée'}</span>
        )}
      </div>
      {data && (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
          <thead><tr style={{ borderBottom: '2px solid #e5e7eb', textAlign: 'left' }}>
            <th style={{ padding: 8 }}>Compte</th>
            <th style={{ padding: 8, textAlign: 'right' }}>Débit</th>
            <th style={{ padding: 8, textAlign: 'right' }}>Crédit</th></tr></thead>
          <tbody>
            {data.accounts.map(a => (
              <tr key={a.account_number} style={{ borderBottom: '1px solid #f3f4f6' }}>
                <td style={{ padding: 8 }}>{a.account_number} — {a.name}</td>
                <td style={{ padding: 8, textAlign: 'right' }}>
                  {a.debit_balance ? a.debit_balance.toFixed(2) + ' $' : ''}</td>
                <td style={{ padding: 8, textAlign: 'right' }}>
                  {a.credit_balance ? a.credit_balance.toFixed(2) + ' $' : ''}</td>
              </tr>
            ))}
            <tr style={{ fontWeight: 700, borderTop: '2px solid #1f2937' }}>
              <td style={{ padding: 8 }}>Total</td>
              <td style={{ padding: 8, textAlign: 'right' }}>{data.total_debit.toFixed(2)} $</td>
              <td style={{ padding: 8, textAlign: 'right' }}>{data.total_credit.toFixed(2)} $</td>
            </tr>
          </tbody>
        </table>
      )}
      {data && <UnmappedAccountsNotice unmapped={data.unmapped_accounts} />}
    </div>
  );
}

function BalanceSheetTab() {
  const [asOf, setAsOf] = useState(new Date().toISOString().slice(0, 10));
  const [data, setData] = useState(null);
  const load = () => axios.get(`${BACKEND_URL}/api/ledger/balance-sheet?as_of=${asOf}`)
    .then(r => setData(r.data)).catch(() => {});
  useEffect(() => { load(); }, [asOf]);
  const Section = ({ title, rows, total }) => (
    <div style={{ marginBottom: 16 }}>
      <h3 style={{ fontSize: 15, borderBottom: '1px solid #e5e7eb', paddingBottom: 4 }}>{title}</h3>
      {rows.map(r => (
        <div key={r.account_number} style={{ display: 'flex', justifyContent: 'space-between',
          padding: '4px 0', fontSize: 14 }}>
          <span>{r.account_number} — {r.name}</span><span>{r.balance.toFixed(2)} $</span>
        </div>
      ))}
      <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 700,
        borderTop: '1px solid #1f2937', paddingTop: 4, marginTop: 4 }}>
        <span>Total</span><span>{total.toFixed(2)} $</span></div>
    </div>
  );
  return (
    <div style={{ maxWidth: 640 }}>
      <div style={{ display: 'flex', gap: 12, marginBottom: 16, alignItems: 'center' }}>
        <input type="date" value={asOf} onChange={e => setAsOf(e.target.value)}
               style={{ padding: 6, border: '1px solid #d1d5db', borderRadius: 6 }} />
        <button onClick={() => downloadPdf(
          `${BACKEND_URL}/api/ledger/balance-sheet/pdf?as_of=${asOf}`, `bilan-${asOf}.pdf`)}
          style={{ background: '#00A08C', color: '#fff', border: 'none', padding: '6px 14px',
            borderRadius: 6, cursor: 'pointer' }}>Télécharger PDF</button>
        {data && (
          <span style={{ padding: '4px 12px', borderRadius: 999, fontSize: 13,
            background: data.balanced ? '#ecfdf5' : '#fef2f2',
            color: data.balanced ? '#059669' : '#dc2626' }}>
            {data.balanced ? 'Équilibré' : 'Déséquilibré'}</span>
        )}
      </div>
      {data && (
        <>
          <Section title="Actif" rows={data.assets.accounts} total={data.assets.total} />
          <Section title="Passif" rows={data.liabilities.accounts} total={data.liabilities.total} />
          <div style={{ marginBottom: 16 }}>
            <h3 style={{ fontSize: 15, borderBottom: '1px solid #e5e7eb', paddingBottom: 4 }}>
              Capitaux propres</h3>
            {data.equity.accounts.map(r => (
              <div key={r.account_number} style={{ display: 'flex',
                justifyContent: 'space-between', padding: '4px 0', fontSize: 14 }}>
                <span>{r.account_number} — {r.name}</span><span>{r.balance.toFixed(2)} $</span>
              </div>
            ))}
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0',
              fontSize: 14, fontStyle: 'italic' }}>
              <span>Résultat net de l'exercice</span>
              <span>{data.equity.net_income_current_year.toFixed(2)} $</span></div>
            {/* Note Clôture annuelle (spec §7.2.1) */}
            <div style={{ background: '#FEF3C7', border: '1px solid #F59E0B',
              borderRadius: 6, padding: '8px 12px', marginTop: 8, fontSize: 12,
              color: '#92400E' }}>
              « Résultat net de l'exercice » est <strong>dérivé</strong> de l'exercice
              courant. La <strong>clôture annuelle</strong> (virement vers Bénéfices non
              répartis 3200) doit être passée manuellement <strong>à ou après la fin
              d'exercice</strong>, jamais en cours d'exercice. Sans elle, le bilan de
              l'exercice suivant sera <strong>déséquilibré</strong>.
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 700,
              borderTop: '1px solid #1f2937', paddingTop: 4, marginTop: 4 }}>
              <span>Total capitaux propres</span><span>{data.equity.total.toFixed(2)} $</span></div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 700,
            fontSize: 15, borderTop: '2px solid #1f2937', paddingTop: 8 }}>
            <span>Total passif + capitaux propres</span>
            <span>{data.total_liabilities_and_equity.toFixed(2)} $</span></div>
          <UnmappedAccountsNotice unmapped={data.unmapped_accounts} />
        </>
      )}
    </div>
  );
}

function LedgerDetailTab() {
  const [accounts, setAccounts] = useState([]);
  const [accountId, setAccountId] = useState('');
  const [data, setData] = useState(null);
  useEffect(() => {
    axios.get(`${BACKEND_URL}/api/ledger/accounts?active=true`)
      .then(r => setAccounts(r.data)).catch(() => {});
  }, []);
  useEffect(() => {
    if (!accountId) { setData(null); return; }
    axios.get(`${BACKEND_URL}/api/ledger/general-ledger?account_id=${accountId}`)
      .then(r => setData(r.data)).catch(() => {});
  }, [accountId]);
  return (
    <div>
      <select value={accountId} onChange={e => setAccountId(e.target.value)}
              style={{ padding: 8, marginBottom: 16, border: '1px solid #d1d5db', borderRadius: 6 }}>
        <option value="">— choisir un compte —</option>
        {accounts.map(a => (
          <option key={a.id} value={a.id}>{a.account_number} — {a.name}</option>
        ))}
      </select>
      {data && (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
          <thead><tr style={{ borderBottom: '2px solid #e5e7eb', textAlign: 'left' }}>
            <th style={{ padding: 8 }}>Date</th><th style={{ padding: 8 }}>N°</th>
            <th style={{ padding: 8 }}>Description</th>
            <th style={{ padding: 8, textAlign: 'right' }}>Débit</th>
            <th style={{ padding: 8, textAlign: 'right' }}>Crédit</th>
            <th style={{ padding: 8, textAlign: 'right' }}>Solde</th></tr></thead>
          <tbody>
            <tr><td colSpan={5} style={{ padding: 8, fontStyle: 'italic' }}>Solde d'ouverture</td>
              <td style={{ padding: 8, textAlign: 'right' }}>{data.opening_balance.toFixed(2)} $</td></tr>
            {data.lines.map((ln, i) => (
              <tr key={i} style={{ borderBottom: '1px solid #f3f4f6' }}>
                <td style={{ padding: 8 }}>{ln.entry_date}</td>
                <td style={{ padding: 8, fontFamily: 'monospace' }}>{ln.entry_number}</td>
                <td style={{ padding: 8 }}>{ln.description}</td>
                <td style={{ padding: 8, textAlign: 'right' }}>{ln.debit ? ln.debit.toFixed(2) + ' $' : ''}</td>
                <td style={{ padding: 8, textAlign: 'right' }}>{ln.credit ? ln.credit.toFixed(2) + ' $' : ''}</td>
                <td style={{ padding: 8, textAlign: 'right' }}>{ln.running_balance.toFixed(2)} $</td>
              </tr>
            ))}
            <tr style={{ fontWeight: 700, borderTop: '2px solid #1f2937' }}>
              <td colSpan={5} style={{ padding: 8 }}>Solde de clôture</td>
              <td style={{ padding: 8, textAlign: 'right' }}>{data.closing_balance.toFixed(2)} $</td></tr>
          </tbody>
        </table>
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
        {tab === 'journal' && <JournalTab />}
        {tab === 'autopost' && <AutopostTab />}
        {tab === 'opening' && <OpeningTab />}
        {tab === 'contribution' && <ContributionTab />}
        {tab === 'ledger' && <LedgerDetailTab />}
        {tab === 'trial' && <TrialBalanceTab />}
        {tab === 'balancesheet' && <BalanceSheetTab />}
      </div>
    </div>
  );
}
