import React, { useState } from 'react';
import axios from 'axios';
import { BACKEND_URL } from '../config';

const QUARTERS = [
  { value: 'Q1', label: 'T1 (jan-mar)', start: '01-01', end: '03-31' },
  { value: 'Q2', label: 'T2 (avr-jun)', start: '04-01', end: '06-30' },
  { value: 'Q3', label: 'T3 (jul-sep)', start: '07-01', end: '09-30' },
  { value: 'Q4', label: 'T4 (oct-déc)', start: '10-01', end: '12-31' },
];

const currentYear = new Date().getFullYear();
const YEARS = [currentYear, currentYear - 1, currentYear - 2, currentYear - 3];

const fmt = v => (v || 0).toLocaleString('fr-CA', { style: 'currency', currency: 'CAD' });

function SalesTaxReportSection() {
  const [periodMode, setPeriodMode] = useState('quarter');
  const [year, setYear] = useState(String(currentYear));
  const [quarter, setQuarter] = useState('Q1');
  const [customStart, setCustomStart] = useState('');
  const [customEnd, setCustomEnd] = useState('');
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);

  const getDates = () => {
    if (periodMode === 'quarter') {
      const q = QUARTERS.find(x => x.value === quarter);
      return { start: `${year}-${q.start}`, end: `${year}-${q.end}` };
    }
    return { start: customStart, end: customEnd };
  };

  const generate = async () => {
    const { start, end } = getDates();
    if (!start || !end) return;
    setLoading(true);
    try {
      const token = localStorage.getItem('access_token');
      const resp = await axios.get(`${BACKEND_URL}/api/reports/sales-tax`, {
        headers: { Authorization: `Bearer ${token}` },
        params: { start, end },
      });
      setReport(resp.data);
    } finally {
      setLoading(false);
    }
  };

  const downloadPdf = async () => {
    const { start, end } = getDates();
    if (!start || !end) return;
    const token = localStorage.getItem('access_token');
    const resp = await fetch(
      `${BACKEND_URL}/api/reports/sales-tax/pdf?start=${start}&end=${end}`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    const blob = await resp.blob();
    const url = window.URL.createObjectURL(blob);
    window.open(url, '_blank');
  };

  const netColor = v => v > 0 ? '#dc2626' : v < 0 ? '#059669' : '#1f2937';
  const arrow = v => v > 0 ? '↑' : v < 0 ? '↓' : '';

  return (
    <div style={{ background: 'white', padding: 20, borderRadius: 8, boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }}>
      <h3 style={{ marginTop: 0 }}>Rapport TPS / TVQ trimestriel</h3>

      <div style={{ marginBottom: 12 }}>
        <label style={{ marginRight: 16 }}>
          <input type="radio" checked={periodMode === 'quarter'}
            onChange={() => setPeriodMode('quarter')} /> Trimestre
        </label>
        <label>
          <input type="radio" checked={periodMode === 'custom'}
            onChange={() => setPeriodMode('custom')} /> Période personnalisée
        </label>
      </div>

      {periodMode === 'quarter' && (
        <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
          <select value={year} onChange={e => setYear(e.target.value)}
            style={{ padding: 8, borderRadius: 6, border: '1px solid #d1d5db' }}>
            {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
          </select>
          <select value={quarter} onChange={e => setQuarter(e.target.value)}
            style={{ padding: 8, borderRadius: 6, border: '1px solid #d1d5db' }}>
            {QUARTERS.map(q => <option key={q.value} value={q.value}>{q.label}</option>)}
          </select>
        </div>
      )}
      {periodMode === 'custom' && (
        <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
          <input type="date" value={customStart} onChange={e => setCustomStart(e.target.value)}
            style={{ padding: 8, borderRadius: 6, border: '1px solid #d1d5db' }} />
          <input type="date" value={customEnd} onChange={e => setCustomEnd(e.target.value)}
            style={{ padding: 8, borderRadius: 6, border: '1px solid #d1d5db' }} />
        </div>
      )}

      <button onClick={generate} disabled={loading}
        style={{ padding: '10px 18px', background: '#00A08C', color: 'white', border: 0, borderRadius: 6, cursor: 'pointer' }}>
        {loading ? 'Génération…' : 'Générer le rapport'}
      </button>

      {report && (
        <div style={{ marginTop: 24 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
            {['gst', 'qst', 'hst'].map(k => (
              <div key={k} style={{ background: '#f9fafb', padding: 14, borderRadius: 6 }}>
                <div style={{ fontWeight: 700, color: '#00A08C', textTransform: 'uppercase', fontSize: 11 }}>{k}</div>
                <div style={{ marginTop: 6, fontSize: 12 }}>Perçue : {fmt(report.summary[k].collected)}</div>
                <div style={{ fontSize: 12 }}>Payée : {fmt(report.summary[k].paid)}</div>
                <div style={{ marginTop: 6, fontWeight: 700, fontSize: 16, color: netColor(report.summary[k].net) }}>
                  Net : {fmt(report.summary[k].net)} {arrow(report.summary[k].net)}
                </div>
              </div>
            ))}
          </div>

          <details style={{ marginTop: 16 }}>
            <summary style={{ cursor: 'pointer', fontWeight: 600 }}>Détail format ARC (T1 GST/HST)</summary>
            <table style={{ width: '100%', marginTop: 8, borderCollapse: 'collapse' }}>
              <tbody>
                {[
                  ['101', 'Ventes et autres recettes', report.cra_detail.line_101_sales],
                  ['103', 'TPS perçue', report.cra_detail.line_103_gst_collected],
                  ['103', 'TVH perçue', report.cra_detail.line_103_hst_collected],
                  ['106', 'CTI TPS', report.cra_detail.line_106_itc_gst],
                  ['106', 'CTI TVH', report.cra_detail.line_106_itc_hst],
                  ['109', 'Taxe nette TPS', report.cra_detail.line_109_net_gst],
                  ['109', 'Taxe nette TVH', report.cra_detail.line_109_net_hst],
                ].map(([line, desc, amt], i) => (
                  <tr key={i} style={{ borderBottom: '1px solid #e5e7eb' }}>
                    <td style={{ padding: 6, fontFamily: 'monospace' }}>{line}</td>
                    <td style={{ padding: 6 }}>{desc}</td>
                    <td style={{ padding: 6, textAlign: 'right' }}>{fmt(amt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>

          <details style={{ marginTop: 8 }}>
            <summary style={{ cursor: 'pointer', fontWeight: 600 }}>Détail format Revenu Québec (FP-2500)</summary>
            <table style={{ width: '100%', marginTop: 8, borderCollapse: 'collapse' }}>
              <tbody>
                {[
                  ['201', 'Ventes taxables au Québec', report.rq_detail.line_201_taxable_sales_qc],
                  ['203', 'TVQ perçue', report.rq_detail.line_203_qst_collected],
                  ['205', 'RTI TVQ', report.rq_detail.line_205_itr_qst],
                  ['209', 'TVQ nette', report.rq_detail.line_209_net_qst],
                ].map(([line, desc, amt], i) => (
                  <tr key={i} style={{ borderBottom: '1px solid #e5e7eb' }}>
                    <td style={{ padding: 6, fontFamily: 'monospace' }}>{line}</td>
                    <td style={{ padding: 6 }}>{desc}</td>
                    <td style={{ padding: 6, textAlign: 'right' }}>{fmt(amt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>

          <div style={{ marginTop: 12, color: '#6b7280', fontSize: 12 }}>
            {report.invoice_count} factures · {report.expense_count} dépenses incluses
          </div>

          <button onClick={downloadPdf}
            style={{ marginTop: 12, padding: '10px 18px', background: '#1f2937', color: 'white', border: 0, borderRadius: 6, cursor: 'pointer' }}>
            Télécharger le PDF
          </button>
        </div>
      )}
    </div>
  );
}

function PnlReportSection() {
  return (
    <div style={{ background: 'white', padding: 20, borderRadius: 8, boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }}>
      <h3 style={{ marginTop: 0 }}>État des résultats (P&L)</h3>
      <p style={{ color: '#6b7280' }}>À venir (Task 7).</p>
    </div>
  );
}

function ReportsPage() {
  const [activeTab, setActiveTab] = useState('sales_tax');

  const tabStyle = (isActive) => ({
    padding: '10px 18px',
    background: isActive ? 'white' : '#f3f4f6',
    color: isActive ? '#00A08C' : '#6b7280',
    border: 0,
    borderBottom: isActive ? '2px solid #00A08C' : '2px solid transparent',
    fontSize: 14,
    fontWeight: isActive ? 600 : 500,
    cursor: 'pointer',
    marginRight: 4,
  });

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', padding: 20 }}>
      <h2 style={{ marginTop: 0 }}>Rapports</h2>
      <div style={{ display: 'flex', borderBottom: '1px solid #e5e7eb', marginBottom: 20 }}>
        <button style={tabStyle(activeTab === 'sales_tax')}
          onClick={() => setActiveTab('sales_tax')}>
          Rapport TPS / TVQ
        </button>
        <button style={tabStyle(activeTab === 'pnl')}
          onClick={() => setActiveTab('pnl')}>
          État des résultats (P&L)
        </button>
      </div>
      {activeTab === 'sales_tax' && <SalesTaxReportSection />}
      {activeTab === 'pnl' && <PnlReportSection />}
    </div>
  );
}

export default ReportsPage;
