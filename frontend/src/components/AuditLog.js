import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { BACKEND_URL } from '../config';

// Journal d'audit (Loi 25) — propriétaire seulement. Liste filtrable + export CSV/JSON.
const TEAL = '#00A08C';
const PAGE = 100;

const CAT_LABEL = { data: 'Données', security: 'Sécurité', auth: 'Authentification', admin: 'Administration' };
const OUTCOME_LABEL = { success: 'Succès', failure: 'Échec' };

const fmtTs = (iso) => {
  if (!iso) return '';
  try { return new Date(iso).toLocaleString('fr-CA', { hour12: false }); }
  catch { return iso; }
};

const AuditLog = () => {
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [filters, setFilters] = useState({ category: '', outcome: '', start: '', end: '' });

  const params = useCallback((extra) => {
    const p = { limit: PAGE, ...extra };
    if (filters.category) p.category = filters.category;
    if (filters.outcome) p.outcome = filters.outcome;
    if (filters.start) p.start = filters.start;
    if (filters.end) p.end = filters.end;
    return p;
  }, [filters]);

  const load = useCallback(async (reset) => {
    setLoading(true); setError('');
    try {
      const nextSkip = reset ? 0 : skip;
      const r = await axios.get(`${BACKEND_URL}/api/org/audit-logs`, { params: params({ skip: nextSkip }) });
      setTotal(r.data.total);
      setLogs((prev) => (reset ? r.data.logs : [...prev, ...r.data.logs]));
      setSkip(nextSkip + r.data.logs.length);
    } catch (e) { setError(e.response?.data?.detail || 'Erreur de chargement'); }
    finally { setLoading(false); }
  }, [skip, params]);

  // Recharge à chaque changement de filtre (depuis zéro).
  useEffect(() => { load(true); /* eslint-disable-next-line */ }, [filters]);

  const doExport = async (format) => {
    try {
      const r = await axios.get(`${BACKEND_URL}/api/org/audit-logs/export`,
        { params: params({ format }), responseType: 'blob' });
      const mime = format === 'json' ? 'application/json' : 'text/csv';
      const url = window.URL.createObjectURL(new Blob([r.data], { type: mime }));
      const a = document.createElement('a'); a.href = url;
      a.download = `journal-audit.${format}`;
      document.body.appendChild(a); a.click(); a.remove();
      window.URL.revokeObjectURL(url);
    } catch { setError("Erreur lors de l'export"); }
  };

  const sel = {
    padding: '8px 10px', border: '1px solid #d1d5db', borderRadius: 8, fontSize: 13,
    background: 'white',
  };
  const th = { textAlign: 'left', padding: '8px 10px', fontSize: 12, color: '#6b7280', fontWeight: 600 };
  const td = { padding: '8px 10px', fontSize: 13, color: '#1f2937', verticalAlign: 'top' };

  return (
    <div>
      <h3 style={{ fontSize: 18, color: '#1f2937', margin: '0 0 4px' }}>Journal d'audit</h3>
      <p style={{ color: '#6b7280', fontSize: 14, marginTop: 0 }}>
        Traçabilité des accès et actions (connexions, double authentification, gestion d'équipe,
        et toute création/modification/suppression de données). Conservé 12 mois. Réservé au propriétaire.
      </p>

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', margin: '12px 0' }}>
        <select value={filters.category} data-testid="audit-filter-category" style={sel}
          onChange={(e) => setFilters((f) => ({ ...f, category: e.target.value }))}>
          <option value="">Toutes catégories</option>
          <option value="data">Données</option>
          <option value="auth">Authentification</option>
          <option value="security">Sécurité</option>
          <option value="admin">Administration</option>
        </select>
        <select value={filters.outcome} style={sel}
          onChange={(e) => setFilters((f) => ({ ...f, outcome: e.target.value }))}>
          <option value="">Tous résultats</option>
          <option value="success">Succès</option>
          <option value="failure">Échec</option>
        </select>
        <label style={{ fontSize: 13, color: '#374151' }}>Du <input type="date" value={filters.start} style={sel}
          onChange={(e) => setFilters((f) => ({ ...f, start: e.target.value }))} /></label>
        <label style={{ fontSize: 13, color: '#374151' }}>Au <input type="date" value={filters.end} style={sel}
          onChange={(e) => setFilters((f) => ({ ...f, end: e.target.value }))} /></label>
        <span style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button onClick={() => doExport('csv')} style={{ ...sel, background: TEAL, color: 'white', cursor: 'pointer', fontWeight: 600 }}>Export CSV</button>
          <button onClick={() => doExport('json')} style={{ ...sel, background: '#1f2937', color: 'white', cursor: 'pointer', fontWeight: 600 }}>Export JSON</button>
        </span>
      </div>

      {error && (
        <div style={{ background: '#fee2e2', border: '1px solid #fecaca', borderRadius: 8,
          padding: '10px 12px', margin: '10px 0', color: '#b91c1c', fontSize: 13 }}>{error}</div>
      )}

      <div style={{ color: '#6b7280', fontSize: 13, marginBottom: 6 }}>
        {total} entrée(s){filters.category || filters.outcome || filters.start || filters.end ? ' (filtré)' : ''}
      </div>

      <div style={{ overflowX: 'auto', border: '1px solid #e5e7eb', borderRadius: 10 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 720 }}>
          <thead>
            <tr style={{ background: '#f9fafb' }}>
              <th style={th}>Date</th><th style={th}>Acteur</th><th style={th}>Action</th>
              <th style={th}>Catégorie</th><th style={th}>Cible</th><th style={th}>Résultat</th><th style={th}>IP</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((l) => (
              <tr key={l.id} style={{ borderTop: '1px solid #f3f4f6' }}>
                <td style={{ ...td, whiteSpace: 'nowrap' }}>{fmtTs(l.ts)}</td>
                <td style={td}>{l.actor_email || l.actor_user_id || '—'}</td>
                <td style={{ ...td, fontFamily: 'monospace', fontSize: 12 }}>{l.action}</td>
                <td style={td}>{CAT_LABEL[l.category] || l.category}</td>
                <td style={td}>{l.target_label || l.target_id || (l.target_type ? l.target_type : '—')}</td>
                <td style={{ ...td, color: l.outcome === 'failure' ? '#b91c1c' : '#065f46', fontWeight: 600 }}>
                  {OUTCOME_LABEL[l.outcome] || l.outcome}
                </td>
                <td style={{ ...td, color: '#9ca3af', fontSize: 12 }}>{l.ip || ''}</td>
              </tr>
            ))}
            {logs.length === 0 && !loading && (
              <tr><td colSpan={7} style={{ ...td, textAlign: 'center', color: '#9ca3af', padding: 24 }}>
                Aucune entrée.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div style={{ textAlign: 'center', marginTop: 12 }}>
        {loading && <span style={{ color: '#6b7280', fontSize: 13 }}>Chargement…</span>}
        {!loading && logs.length < total && (
          <button onClick={() => load(false)} style={{ ...sel, cursor: 'pointer', fontWeight: 600 }}>
            Charger plus ({logs.length}/{total})
          </button>
        )}
      </div>
    </div>
  );
};

export default AuditLog;
