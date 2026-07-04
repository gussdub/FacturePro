import {
  coveragePercent,
  formatCoverage,
  sourceDocRoute,
  sourceDocLabel,
  isAutoEntry,
  hasAutopostError,
  backfillTotal,
} from './ledgerAutopost';

describe('coveragePercent', () => {
  test('0 total → 0 (jamais NaN/division par zéro)', () => {
    expect(coveragePercent(0, 0)).toBe(0);
  });
  test('couverture totale → 100', () => {
    expect(coveragePercent(7, 7)).toBe(100);
  });
  test('couverture partielle arrondie à l\'entier', () => {
    expect(coveragePercent(1, 3)).toBe(33);
    expect(coveragePercent(2, 3)).toBe(67);
  });
  test('posted > total (données incohérentes) plafonné à 100', () => {
    expect(coveragePercent(5, 3)).toBe(100);
  });
  test('valeurs manquantes traitées comme 0', () => {
    expect(coveragePercent(undefined, undefined)).toBe(0);
    expect(coveragePercent(null, 4)).toBe(0);
  });
});

describe('formatCoverage', () => {
  const cov = {
    invoices_posted: 3,
    invoices_total_postable: 4,
    expenses_posted: 2,
    expenses_total: 2,
  };
  test('résume factures et dépenses séparément', () => {
    const r = formatCoverage(cov);
    expect(r.invoices).toEqual({ posted: 3, total: 4, percent: 75 });
    expect(r.expenses).toEqual({ posted: 2, total: 2, percent: 100 });
  });
  test('coverage absent → zéros sans planter', () => {
    const r = formatCoverage(undefined);
    expect(r.invoices).toEqual({ posted: 0, total: 0, percent: 0 });
    expect(r.expenses).toEqual({ posted: 0, total: 0, percent: 0 });
  });
});

describe('sourceDocRoute / sourceDocLabel', () => {
  test('invoice et invoice_payment renvoient vers les factures', () => {
    expect(sourceDocRoute('invoice')).toBe('/invoices');
    expect(sourceDocRoute('invoice_payment')).toBe('/invoices');
  });
  test('expense renvoie vers les dépenses', () => {
    expect(sourceDocRoute('expense')).toBe('/expenses');
  });
  test('type inconnu → null (pas de lien)', () => {
    expect(sourceDocRoute('mystery')).toBeNull();
    expect(sourceDocRoute(undefined)).toBeNull();
  });
  test('libellés FR', () => {
    expect(sourceDocLabel('invoice')).toBe('Facture');
    expect(sourceDocLabel('invoice_payment')).toBe('Paiement');
    expect(sourceDocLabel('expense')).toBe('Dépense');
    expect(sourceDocLabel('mystery')).toBe('Source');
  });
});

describe('isAutoEntry', () => {
  test('entry_type=auto → true', () => {
    expect(isAutoEntry({ entry_type: 'auto' })).toBe(true);
  });
  test('manual/opening/reversal → false', () => {
    expect(isAutoEntry({ entry_type: 'manual' })).toBe(false);
    expect(isAutoEntry({ entry_type: 'opening' })).toBe(false);
    expect(isAutoEntry({ entry_type: 'reversal' })).toBe(false);
  });
  test('entrée nulle → false', () => {
    expect(isAutoEntry(null)).toBe(false);
    expect(isAutoEntry({})).toBe(false);
  });
});

describe('hasAutopostError', () => {
  test('champ posé → true', () => {
    expect(hasAutopostError({ autopost_error: '2026-07-04 — échec' })).toBe(true);
  });
  test('null/absent → false', () => {
    expect(hasAutopostError({ autopost_error: null })).toBe(false);
    expect(hasAutopostError({})).toBe(false);
    expect(hasAutopostError(null)).toBe(false);
  });
});

describe('backfillTotal', () => {
  test('somme les compteurs would_create', () => {
    expect(backfillTotal({ invoice: 2, invoice_payment: 3, expense: 1 })).toBe(6);
  });
  test('champ absent → 0', () => {
    expect(backfillTotal(undefined)).toBe(0);
    expect(backfillTotal({})).toBe(0);
  });
});
