// Permissions éditables — miroir de PERMISSIONS_EDITABLE côté backend.
export const PERMISSIONS_EDITABLE = [
  { code: 'expenses:read',   group: 'Dépenses',  label: 'Lire les dépenses' },
  { code: 'expenses:write',  group: 'Dépenses',  label: 'Créer / modifier les dépenses' },
  { code: 'receipts:scan',   group: 'Dépenses',  label: 'Scanner les reçus (OCR)' },
  { code: 'invoices:read',   group: 'Factures',  label: 'Lire les factures' },
  { code: 'invoices:write',  group: 'Factures',  label: 'Créer / modifier les factures' },
  { code: 'quotes:read',     group: 'Devis',     label: 'Lire les devis' },
  { code: 'quotes:write',    group: 'Devis',     label: 'Créer / modifier les devis' },
  { code: 'clients:read',    group: 'Clients',   label: 'Lire les clients' },
  { code: 'clients:write',   group: 'Clients',   label: 'Créer / modifier les clients' },
  { code: 'products:read',   group: 'Produits',  label: 'Lire les produits' },
  { code: 'products:write',  group: 'Produits',  label: 'Créer / modifier les produits' },
  { code: 'employees:read',  group: 'Employés',  label: 'Lire les employés' },
  { code: 'employees:write', group: 'Employés',  label: 'Créer / modifier les employés' },
  { code: 'reports:read',    group: 'Rapports',  label: 'Consulter les rapports (P&L, TPS/TVQ, T2125)' },
  { code: 'bank:read',       group: 'Bancaire',  label: 'Lire les imports bancaires' },
  { code: 'bank:write',      group: 'Bancaire',  label: 'Créer / modifier les imports bancaires' },
];

export const PERMISSION_GROUPS = ['Dépenses', 'Factures', 'Devis', 'Clients', 'Produits', 'Employés', 'Rapports', 'Bancaire'];

// Libellés FR des rôles (le code interne reste anglais côté backend).
export const ROLE_LABELS = {
  owner: 'Propriétaire',
  accountant: 'Comptable',
  viewer: 'Lecteur',
};

export const roleLabel = (code) => ROLE_LABELS[code] || code;
