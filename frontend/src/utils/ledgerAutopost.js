// Helpers PURS pour l'auto-posting du grand livre (Phase 2, feature #12, T15).
// Aucune dépendance React/axios : logique testable en isolation (jest).

// Pourcentage de couverture entier (0-100). total=0 → 0 (jamais NaN). Un
// posted > total (données transitoires incohérentes) est plafonné à 100 pour
// ne jamais afficher « 120 % postées ».
export function coveragePercent(posted, total) {
  const p = Number(posted) || 0;
  const t = Number(total) || 0;
  if (t <= 0) return 0;
  const pct = Math.round((p / t) * 100);
  return Math.min(100, Math.max(0, pct));
}

// Décompose le bloc `coverage` de GET /api/ledger/autopost/status en deux
// résumés (factures, dépenses) avec pourcentage dérivé. Tolère un coverage
// absent (org jamais postée) → zéros.
export function formatCoverage(coverage) {
  const c = coverage || {};
  const invoicesPosted = Number(c.invoices_posted) || 0;
  const invoicesTotal = Number(c.invoices_total_postable) || 0;
  const expensesPosted = Number(c.expenses_posted) || 0;
  const expensesTotal = Number(c.expenses_total) || 0;
  return {
    invoices: {
      posted: invoicesPosted,
      total: invoicesTotal,
      percent: coveragePercent(invoicesPosted, invoicesTotal),
    },
    expenses: {
      posted: expensesPosted,
      total: expensesTotal,
      percent: coveragePercent(expensesPosted, expensesTotal),
    },
  };
}

// Route de la LISTE du document source d'une écriture auto. Les paiements sont
// embarqués dans la facture → même route que les factures. Type inconnu → null
// (pas de lien affiché).
export function sourceDocRoute(sourceType) {
  switch (sourceType) {
    case 'invoice':
    case 'invoice_payment':
      return '/invoices';
    case 'expense':
      return '/expenses';
    default:
      return null;
  }
}

// Libellé FR du type de source (pour la pastille « Auto »).
export function sourceDocLabel(sourceType) {
  switch (sourceType) {
    case 'invoice':
      return 'Facture';
    case 'invoice_payment':
      return 'Paiement';
    case 'expense':
      return 'Dépense';
    default:
      return 'Source';
  }
}

// Une écriture générée par l'auto-posting (verrouillée : édition/contre-passation
// masquées côté UI, §8.3). Seul `entry_type="auto"` compte comme « auto vivante ».
// Le miroir de contre-passation porte `entry_type="reversal"` → non marqué « Auto ».
export function isAutoEntry(entry) {
  return !!entry && entry.entry_type === 'auto';
}

// Un doc source (facture/dépense) porte-t-il un échec d'auto-posting ?
export function hasAutopostError(doc) {
  return !!(doc && doc.autopost_error);
}

// Total d'écritures qui seront créées par un backfill (somme des would_create).
export function backfillTotal(wouldCreate) {
  const w = wouldCreate || {};
  return (Number(w.invoice) || 0)
    + (Number(w.invoice_payment) || 0)
    + (Number(w.expense) || 0);
}
