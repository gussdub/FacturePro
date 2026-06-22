import React, { useState } from 'react';
import axios from 'axios';
import { BACKEND_URL } from '../config';
import T2125ReportSection from '../components/T2125ReportSection';

const QUARTERS = [
  { value: 'Q1', label: 'T1 (jan-mar)', start: '01-01', end: '03-31' },
  { value: 'Q2', label: 'T2 (avr-jun)', start: '04-01', end: '06-30' },
  { value: 'Q3', label: 'T3 (jul-sep)', start: '07-01', end: '09-30' },
  { value: 'Q4', label: 'T4 (oct-déc)', start: '10-01', end: '12-31' },
];

const currentYear = new Date().getFullYear();
const YEARS = [currentYear, currentYear - 1, currentYear - 2, currentYear - 3];

const MONTHS = [
  { value: '01', label: 'Janvier' }, { value: '02', label: 'Février' },
  { value: '03', label: 'Mars' },    { value: '04', label: 'Avril' },
  { value: '05', label: 'Mai' },     { value: '06', label: 'Juin' },
  { value: '07', label: 'Juillet' }, { value: '08', label: 'Août' },
  { value: '09', label: 'Septembre' },{ value: '10', label: 'Octobre' },
  { value: '11', label: 'Novembre' },{ value: '12', label: 'Décembre' },
];

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
  const [periodMode, setPeriodMode] = useState('quarter');
  const [year, setYear] = useState(String(new Date().getFullYear()));
  const [quarter, setQuarter] = useState('Q1');
  const [month, setMonth] = useState('01');
  const [customStart, setCustomStart] = useState('');
  const [customEnd, setCustomEnd] = useState('');
  const [basis, setBasis] = useState('accrual');
  const [compare, setCompare] = useState('none');
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);

  const getDates = () => {
    if (periodMode === 'quarter') {
      const q = QUARTERS.find(x => x.value === quarter);
      return { start: `${year}-${q.start}`, end: `${year}-${q.end}` };
    }
    if (periodMode === 'month') {
      const lastDay = new Date(parseInt(year), parseInt(month), 0).getDate();
      return { start: `${year}-${month}-01`, end: `${year}-${month}-${String(lastDay).padStart(2, '0')}` };
    }
    if (periodMode === 'year') {
      return { start: `${year}-01-01`, end: `${year}-12-31` };
    }
    return { start: customStart, end: customEnd };
  };

  const generate = async () => {
    const { start, end } = getDates();
    if (!start || !end) return;
    setLoading(true);
    try {
      const token = localStorage.getItem('access_token');
      const resp = await axios.get(`${BACKEND_URL}/api/reports/pnl`, {
        headers: { Authorization: `Bearer ${token}` },
        params: { start, end, basis, compare },
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
      `${BACKEND_URL}/api/reports/pnl/pdf?start=${start}&end=${end}&basis=${basis}&compare=${compare}`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    const blob = await resp.blob();
    const url = window.URL.createObjectURL(blob);
    window.open(url, '_blank');
  };

  const fmt2 = v => (v || 0).toLocaleString('fr-CA', { style: 'currency', currency: 'CAD' });
  const deltaColor = d => d > 0 ? '#059669' : d < 0 ? '#dc2626' : '#6b7280';
  const deltaArrow = d => d > 0 ? '↑' : d < 0 ? '↓' : '';
  const hasCompare = report && report.compare !== 'none' && report.compare_period;

  return (
    <div style={{ background: 'white', padding: 20, borderRadius: 8, boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }}>
      <h3 style={{ marginTop: 0 }}>État des résultats (P&L)</h3>

      <div style={{ marginBottom: 12 }}>
        <label style={{ marginRight: 12 }}>
          <input type="radio" checked={periodMode === 'month'} onChange={() => setPeriodMode('month')} /> Mois
        </label>
        <label style={{ marginRight: 12 }}>
          <input type="radio" checked={periodMode === 'quarter'} onChange={() => setPeriodMode('quarter')} /> Trimestre
        </label>
        <label style={{ marginRight: 12 }}>
          <input type="radio" checked={periodMode === 'year'} onChange={() => setPeriodMode('year')} /> Année
        </label>
        <label>
          <input type="radio" checked={periodMode === 'custom'} onChange={() => setPeriodMode('custom')} /> Personnalisée
        </label>
      </div>

      <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
        {(periodMode === 'quarter' || periodMode === 'year' || periodMode === 'month') && (
          <select value={year} onChange={e => setYear(e.target.value)}
            style={{ padding: 8, borderRadius: 6, border: '1px solid #d1d5db' }}>
            {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
          </select>
        )}
        {periodMode === 'quarter' && (
          <select value={quarter} onChange={e => setQuarter(e.target.value)}
            style={{ padding: 8, borderRadius: 6, border: '1px solid #d1d5db' }}>
            {QUARTERS.map(q => <option key={q.value} value={q.value}>{q.label}</option>)}
          </select>
        )}
        {periodMode === 'month' && (
          <select value={month} onChange={e => setMonth(e.target.value)}
            style={{ padding: 8, borderRadius: 6, border: '1px solid #d1d5db' }}>
            {MONTHS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select>
        )}
        {periodMode === 'custom' && (
          <>
            <input type="date" value={customStart} onChange={e => setCustomStart(e.target.value)}
              style={{ padding: 8, borderRadius: 6, border: '1px solid #d1d5db' }} />
            <input type="date" value={customEnd} onChange={e => setCustomEnd(e.target.value)}
              style={{ padding: 8, borderRadius: 6, border: '1px solid #d1d5db' }} />
          </>
        )}
      </div>

      <div style={{ marginBottom: 12 }}>
        <span style={{ fontSize: 13, fontWeight: 500, marginRight: 12 }}>Base :</span>
        <label style={{ marginRight: 12 }}>
          <input type="radio" checked={basis === 'accrual'} onChange={() => setBasis('accrual')} /> Comptabilité d'exercice
        </label>
        <label>
          <input type="radio" checked={basis === 'cash'} onChange={() => setBasis('cash')} /> Comptabilité de caisse
        </label>
      </div>

      <div style={{ marginBottom: 12 }}>
        <span style={{ fontSize: 13, fontWeight: 500, marginRight: 12 }}>Comparer :</span>
        <label style={{ marginRight: 12 }}>
          <input type="radio" checked={compare === 'none'} onChange={() => setCompare('none')} /> Aucune
        </label>
        <label style={{ marginRight: 12 }}>
          <input type="radio" checked={compare === 'previous'} onChange={() => setCompare('previous')} /> Période précédente
        </label>
        <label>
          <input type="radio" checked={compare === 'prior_year'} onChange={() => setCompare('prior_year')} /> Année précédente
        </label>
      </div>

      <button onClick={generate} disabled={loading}
        style={{ padding: '10px 18px', background: '#00A08C', color: 'white', border: 0, borderRadius: 6, cursor: 'pointer' }}>
        {loading ? 'Génération…' : 'Générer le rapport'}
      </button>

      {report && (
        <div style={{ marginTop: 24 }}>
          <h4 style={{ marginBottom: 8 }}>Sommaire</h4>
          <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 16 }}>
            <thead>
              <tr style={{ background: '#f8fafb' }}>
                <th style={{ padding: 8, textAlign: 'left' }}></th>
                <th style={{ padding: 8, textAlign: 'right' }}>Période</th>
                {hasCompare && <th style={{ padding: 8, textAlign: 'right' }}>Compare</th>}
                {hasCompare && <th style={{ padding: 8, textAlign: 'right' }}>Δ %</th>}
              </tr>
            </thead>
            <tbody>
              <tr style={{ borderBottom: '1px solid #e5e7eb' }}>
                <td style={{ padding: 8 }}>Revenus</td>
                <td style={{ padding: 8, textAlign: 'right' }}>{fmt2(report.revenue.current)}</td>
                {hasCompare && <td style={{ padding: 8, textAlign: 'right' }}>{fmt2(report.revenue.previous)}</td>}
                {hasCompare && (
                  <td style={{ padding: 8, textAlign: 'right', color: deltaColor(report.revenue.delta_pct) }}>
                    {report.revenue.delta_pct.toFixed(1)} % {deltaArrow(report.revenue.delta_pct)}
                  </td>
                )}
              </tr>
              <tr style={{ borderBottom: '1px solid #e5e7eb' }}>
                <td style={{ padding: 8 }}>Total dépenses (brut)</td>
                <td style={{ padding: 8, textAlign: 'right' }}>{fmt2(report.total_expenses.current.gross)}</td>
                {hasCompare && <td style={{ padding: 8, textAlign: 'right' }}>{fmt2(report.total_expenses.previous.gross)}</td>}
                {hasCompare && <td></td>}
              </tr>
              <tr style={{ borderTop: '2px solid #00A08C', fontWeight: 700 }}>
                <td style={{ padding: 8 }}>Bénéfice de gestion</td>
                <td style={{ padding: 8, textAlign: 'right' }}>{fmt2(report.net_income.current.management)}</td>
                {hasCompare && <td style={{ padding: 8, textAlign: 'right' }}>{fmt2(report.net_income.previous.management)}</td>}
                {hasCompare && (
                  <td style={{ padding: 8, textAlign: 'right', color: deltaColor(report.net_income.delta_pct.management) }}>
                    {report.net_income.delta_pct.management.toFixed(1)} % {deltaArrow(report.net_income.delta_pct.management)}
                  </td>
                )}
              </tr>
              <tr style={{ fontWeight: 700 }}>
                <td style={{ padding: 8 }}>Bénéfice imposable</td>
                <td style={{ padding: 8, textAlign: 'right' }}>{fmt2(report.net_income.current.taxable)}</td>
                {hasCompare && <td style={{ padding: 8, textAlign: 'right' }}>{fmt2(report.net_income.previous.taxable)}</td>}
                {hasCompare && (
                  <td style={{ padding: 8, textAlign: 'right', color: deltaColor(report.net_income.delta_pct.taxable) }}>
                    {report.net_income.delta_pct.taxable.toFixed(1)} % {deltaArrow(report.net_income.delta_pct.taxable)}
                  </td>
                )}
              </tr>
            </tbody>
          </table>

          <h4 style={{ marginBottom: 8 }}>Détail des dépenses</h4>
          {report.expense_groups.map(g => (
            <details key={g.group} open style={{ marginBottom: 8 }}>
              <summary style={{ cursor: 'pointer', fontWeight: 600, padding: '6px 8px', background: '#f9fafb', borderRadius: 4 }}>
                {g.label} — Brut {fmt2(g.subtotal.current.gross)} · Déduct. {fmt2(g.subtotal.current.deductible)}
                {hasCompare && ` (cmp ${fmt2(g.subtotal.previous.gross)} / ${fmt2(g.subtotal.previous.deductible)})`}
              </summary>
              <table style={{ width: '100%', marginTop: 4, borderCollapse: 'collapse' }}>
                <tbody>
                  {g.categories.map(cat => (
                    <tr key={cat.code} style={{ borderBottom: '1px solid #f3f4f6' }}>
                      <td style={{ padding: '4px 16px', fontSize: 13 }}>
                        · {cat.label}
                        {cat.arc_line && <span style={{ color: '#9ca3af', fontSize: 11, marginLeft: 4 }}>({cat.arc_line})</span>}
                        {cat.code === 'meals_entertainment' && cat.current.gross > cat.current.deductible && (
                          <span style={{ marginLeft: 6, fontSize: 11, color: '#92400e' }}>⚠ 50%</span>
                        )}
                      </td>
                      <td style={{ padding: '4px 8px', textAlign: 'right', fontSize: 13 }}>{fmt2(cat.current.gross)}</td>
                      <td style={{ padding: '4px 8px', textAlign: 'right', fontSize: 13 }}>{fmt2(cat.current.deductible)}</td>
                      {hasCompare && <td style={{ padding: '4px 8px', textAlign: 'right', fontSize: 13, color: '#6b7280' }}>{fmt2(cat.previous.gross)}</td>}
                      {hasCompare && <td style={{ padding: '4px 8px', textAlign: 'right', fontSize: 13, color: '#6b7280' }}>{fmt2(cat.previous.deductible)}</td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          ))}

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
        <button style={tabStyle(activeTab === 't2125')}
          onClick={() => setActiveTab('t2125')}>
          Déclaration T2125
        </button>
      </div>
      {activeTab === 'sales_tax' && <SalesTaxReportSection />}
      {activeTab === 'pnl' && <PnlReportSection />}
      {activeTab === 't2125' && <T2125ReportSection />}
    </div>
  );
}

export default ReportsPage;
