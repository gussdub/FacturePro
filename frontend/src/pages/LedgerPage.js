import React, { useState } from 'react';

const TABS = [
  { key: 'accounts', label: 'Plan comptable' },
  { key: 'journal', label: 'Journal' },
  { key: 'opening', label: 'Bilan d\'ouverture' },
  { key: 'contribution', label: 'Apport' },
  { key: 'ledger', label: 'Grand livre' },
  { key: 'trial', label: 'Balance de vérification' },
  { key: 'balancesheet', label: 'Bilan' },
];

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
        {tab === 'accounts' && <div>Plan comptable (à venir)</div>}
      </div>
    </div>
  );
}
