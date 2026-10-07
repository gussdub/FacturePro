import { docTotalCad, computeQuoteTotals, computeInvoiceTotals, computeSelectionTotals } from './documentTotals';

describe('docTotalCad', () => {
  it('utilise total_cad quand présent', () => {
    expect(docTotalCad({ total: 100, currency: 'USD', total_cad: 137.5 })).toBe(137.5);
  });
  it('replie sur total en CAD', () => {
    expect(docTotalCad({ total: 50, currency: 'CAD' })).toBe(50);
  });
  it('convertit une devise sans total_cad', () => {
    expect(docTotalCad({ total: 100, currency: 'USD', exchange_rate_to_cad: 0.8 })).toBe(125);
  });
});

describe('computeQuoteTotals', () => {
  it('exclut les soumissions converties (déjà comptées en facture)', () => {
    const t = computeQuoteTotals([
      { status: 'pending', total_cad: 100 },
      { status: 'converted', total_cad: 200 },
      { status: 'accepted', total_cad: 50.1 },
      { status: 'refused', total_cad: 10 },
    ]);
    expect(t).toEqual({ count: 3, totalCad: 160.1, acceptedCount: 1, acceptedCad: 50.1 });
  });
  it('liste vide', () => {
    expect(computeQuoteTotals([])).toEqual({ count: 0, totalCad: 0, acceptedCount: 0, acceptedCad: 0 });
  });
});

describe('computeInvoiceTotals', () => {
  it('exclut les brouillons des montants mais les compte', () => {
    const t = computeInvoiceTotals([
      { status: 'draft', total_cad: 999 },
      { status: 'sent', total_cad: 100, outstanding_cad: 100 },
      { status: 'partial', total_cad: 200, outstanding_cad: 50 },
      { status: 'paid', total_cad: 300, outstanding_cad: 0 },
    ]);
    expect(t).toEqual({ count: 4, draftCount: 1, billedCad: 600, paidCad: 450, outstandingCad: 150 });
  });
  it('calcule le solde sans outstanding_cad', () => {
    const t = computeInvoiceTotals([{ status: 'overdue', total_cad: 100, total_paid_cad: 30 }]);
    expect(t.outstandingCad).toBe(70);
    expect(t.paidCad).toBe(30);
  });
});

it('computeSelectionTotals', () => {
  expect(computeSelectionTotals([{ total_cad: 1.1 }, { total_cad: 2.2 }])).toEqual({ count: 2, totalCad: 3.3 });
});
