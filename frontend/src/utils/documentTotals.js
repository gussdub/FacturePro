// Totaux cumulatifs affichés en tête des pages Soumissions et Factures.
// Tous les montants sont ramenés en CAD (total_cad, figé à la création) pour
// pouvoir additionner des documents en devises différentes.

const round2 = (n) => Math.round(n * 100) / 100;

// Montant TTC en CAD d'une facture ou d'une soumission.
export const docTotalCad = (doc) => {
  if (!doc) return 0;
  if (doc.total_cad != null && Number.isFinite(Number(doc.total_cad))) return Number(doc.total_cad);
  const total = Number(doc.total) || 0;
  if (!doc.currency || doc.currency === 'CAD') return total;
  const rate = Number(doc.exchange_rate_to_cad);
  return rate > 0 ? total / rate : total;
};

const sumCad = (docs) => round2(docs.reduce((s, d) => s + docTotalCad(d), 0));

// Soumissions : toutes comptées, converties incluses (« combien j'en ai produit »).
export const computeQuoteTotals = (quotes = []) => {
  const won = quotes.filter(q => q.status === 'accepted' || q.status === 'converted');
  return {
    count: quotes.length,
    totalCad: sumCad(quotes),
    wonCount: won.length,
    wonCad: sumCad(won),
  };
};

const invoiceOutstandingCad = (inv) => {
  if (inv.outstanding_cad != null) return Number(inv.outstanding_cad) || 0;
  if (inv.status === 'paid') return 0;
  return Math.max(0, docTotalCad(inv) - (Number(inv.total_paid_cad) || 0));
};

// Factures : le nombre inclut les brouillons ; les montants ne portent que sur
// les factures émises (un brouillon n'est pas facturé).
export const computeInvoiceTotals = (invoices = []) => {
  const issued = invoices.filter(i => i.status !== 'draft');
  const outstanding = round2(issued.reduce((s, i) => s + invoiceOutstandingCad(i), 0));
  const billed = sumCad(issued);
  return {
    count: invoices.length,
    draftCount: invoices.length - issued.length,
    billedCad: billed,
    paidCad: round2(Math.max(0, billed - outstanding)),
    outstandingCad: outstanding,
  };
};

// Petit résumé de la sélection filtrée (nombre + montant).
export const computeSelectionTotals = (docs = []) => ({ count: docs.length, totalCad: sumCad(docs) });
