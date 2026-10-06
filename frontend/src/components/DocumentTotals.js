import React from 'react';
import { formatCurrency } from '../config';

// Cartes de totaux cumulatifs (nombre + montant TTC en CAD) affichées en tête
// des listes Soumissions et Factures. Purement présentationnel : les chiffres
// viennent de utils/documentTotals.js.
//
// cards     : [{ label, value, sub?, accent? }]
// selection : { count, totalCad, noun } | null — résumé de la liste filtrée,
//             affiché seulement quand un filtre réduit la liste.

const ACCENT = '#00796B';

const DocumentTotals = ({ cards, selection, testId }) => (
  <div data-testid={testId} style={{ marginBottom: '20px' }}>
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '12px' }}>
      {cards.map((c) => (
        <div key={c.label} style={{
          background: '#fff', border: '1px solid #e5e7eb', borderRadius: '12px',
          padding: '14px 16px', borderTop: `3px solid ${c.accent || ACCENT}`,
        }}>
          <div style={{ fontSize: '12px', fontWeight: '600', color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.03em' }}>
            {c.label}
          </div>
          <div style={{ fontSize: '22px', fontWeight: '800', color: '#1f2937', marginTop: '4px', fontVariantNumeric: 'tabular-nums' }}>
            {c.value}
          </div>
          {c.sub && <div style={{ fontSize: '12px', color: '#6b7280', marginTop: '2px' }}>{c.sub}</div>}
        </div>
      ))}
    </div>
    {selection && (
      <div data-testid={testId ? `${testId}-selection` : undefined}
        style={{ marginTop: '8px', fontSize: '13px', color: '#4b5563' }}>
        Sélection affichée : <strong>{selection.count}</strong> {selection.noun} · <strong>{formatCurrency(selection.totalCad, 'CAD')}</strong>
      </div>
    )}
  </div>
);

export default DocumentTotals;
