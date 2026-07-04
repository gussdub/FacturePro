// Tests de RENDU (React Testing Library demandée par le prompt T15 ; ici réalisés
// SANS nouvelle dépendance via react-dom/client + react-dom/test-utils.act, déjà
// présents avec react-scripts — cf. contrainte « aucune nouvelle lib » du plan).
//
// Couvre le comportement du composant AutopostTab (et le gating auto du JournalTab)
// que les helpers purs (ledgerAutopost.test.js) ne peuvent pas exercer :
//   - toggle activation (accounting:write) → PUT /api/settings/company + rechargement
//   - sélecteur compte de crédit dépenses → PUT
//   - badge pending_errors + bouton « Réparer » → POST /repair
//   - assistant backfill dry-run → apply (deux POST /backfill successifs)
//   - gating canWrite (lecture seule : contrôles désactivés, actions masquées)
//   - JournalTab : pastille « Auto » + lien source, bouton Contre-passer MASQUÉ
//     sur les écritures entry_type="auto" (verrou §8.3), visible sur les manuelles.

import React from 'react';
import { createRoot } from 'react-dom/client';
import { act } from 'react-dom/test-utils';

// React 18 : signale à react-dom que nous sommes dans un environnement act()
// (équivalent de ce que fait @testing-library en interne). Sans ce flag,
// react-dom émet « The current testing environment is not configured to
// support act(...) » à chaque mise à jour d'état.
global.IS_REACT_ACT_ENVIRONMENT = true;

// ── Mocks ──────────────────────────────────────────────────────────────────
// axios v1.x expose de l'ESM dans son index racine que le jest de CRA ne
// transforme pas (transformIgnorePatterns exclut node_modules) : on le remplace
// intégralement par une factory de mocks jest (aucun `import 'axios'` réel).
jest.mock('axios', () => ({
  __esModule: true,
  default: { get: jest.fn(), put: jest.fn(), post: jest.fn() },
  get: jest.fn(),
  put: jest.fn(),
  post: jest.fn(),
}));
// eslint-disable-next-line global-require
const axios = require('axios').default;

// useAuth mocké : hasPermission piloté par la variable de module ci-dessous.
let mockPermissions = ['accounting:read', 'accounting:write'];
jest.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    hasPermission: (code) => mockPermissions.includes(code),
  }),
}));

// config.js importe process.env.REACT_APP_BACKEND_URL ; on fige une base.
jest.mock('../config', () => ({
  BACKEND_URL: 'http://test',
  formatCurrency: (n) => `${n} $`,
  CURRENCY_LABELS: {},
}));

// Import APRÈS les mocks (les tabs consomment useAuth/axios/config mockés).
const { AutopostTab, JournalTab } = require('./LedgerPage');

// ── Harnais de rendu jsdom (createRoot + act, sans @testing-library) ─────────
let container;
let root;

beforeEach(() => {
  mockPermissions = ['accounting:read', 'accounting:write'];
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
  jest.clearAllMocks();
  // Par défaut : GET status neutre. Chaque test peut surcharger avant render.
  axios.get.mockResolvedValue({ data: {} });
  axios.put.mockResolvedValue({ data: {} });
  axios.post.mockResolvedValue({ data: {} });
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  container = null;
});

// Monte un élément et laisse les effets/microtâches (fetch de status) se résoudre.
async function mount(element) {
  await act(async () => {
    root.render(element);
  });
  // Laisse les promesses .then/.finally des chargements initiaux se résoudre.
  await act(async () => { await Promise.resolve(); });
  await act(async () => { await Promise.resolve(); });
}

async function click(el) {
  await act(async () => {
    el.dispatchEvent(new MouseEvent('click', { bubbles: true }));
  });
  await act(async () => { await Promise.resolve(); });
  await act(async () => { await Promise.resolve(); });
}

async function change(el, value) {
  await act(async () => {
    const setter = Object.getOwnPropertyDescriptor(
      window.HTMLSelectElement.prototype, 'value'
    ) || Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
    setter.set.call(el, value);
    el.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await act(async () => { await Promise.resolve(); });
  await act(async () => { await Promise.resolve(); });
}

const STATUS_DISABLED = {
  enabled: false,
  expense_default_credit_account: '1000',
  pending_errors: 0,
  coverage: {
    invoices_posted: 3, invoices_total_postable: 4,
    expenses_posted: 1, expenses_total: 2,
  },
};

const STATUS_ENABLED_WITH_ERRORS = {
  enabled: true,
  expense_default_credit_account: '2000',
  pending_errors: 2,
  coverage: {
    invoices_posted: 5, invoices_total_postable: 5,
    expenses_posted: 4, expenses_total: 4,
  },
};

// Renvoie la réponse GET /autopost/status, laisse passer les autres GET.
function stubStatus(status) {
  axios.get.mockImplementation((url) => {
    if (url.includes('/autopost/status')) return Promise.resolve({ data: status });
    return Promise.resolve({ data: [] });
  });
}

// ════════════════════════════════════════════════════════════════════════════
describe('AutopostTab — rendu et chargement', () => {
  test('charge le statut et affiche la couverture (X/Y + %)', async () => {
    stubStatus(STATUS_DISABLED);
    await mount(<AutopostTab />);
    expect(axios.get).toHaveBeenCalledWith('http://test/api/ledger/autopost/status');
    const text = container.textContent;
    expect(text).toContain('Auto-posting désactivé');
    expect(text).toContain('3/4');   // factures postées
    expect(text).toContain('1/2');   // dépenses postées
    expect(text).toContain('Aucune erreur en attente');
  });

  test('statut illisible (GET échoue) → message d\'erreur', async () => {
    axios.get.mockImplementation((url) => {
      if (url.includes('/autopost/status')) return Promise.reject(new Error('boom'));
      return Promise.resolve({ data: [] });
    });
    await mount(<AutopostTab />);
    expect(container.textContent).toContain('Impossible de charger');
  });
});

describe('AutopostTab — activation (toggle + sélecteur)', () => {
  test('toggle → PUT autopost_enabled inversé + rechargement du statut', async () => {
    stubStatus(STATUS_DISABLED);
    await mount(<AutopostTab />);
    // Le toggle est le <button> arrondi (borderRadius 20px) de la carte Activation.
    const toggleBtn = Array.from(container.querySelectorAll('button'))
      .find(b => b.style.borderRadius === '20px');
    expect(toggleBtn).toBeTruthy();
    await click(toggleBtn);
    expect(axios.put).toHaveBeenCalledWith(
      'http://test/api/settings/company',
      { autopost_enabled: true },
    );
    // Rechargement du statut après sauvegarde (2e appel GET status).
    const statusCalls = axios.get.mock.calls.filter(c => c[0].includes('/autopost/status'));
    expect(statusCalls.length).toBeGreaterThanOrEqual(2);
  });

  test('sélecteur compte de crédit → PUT expense_default_credit_account', async () => {
    stubStatus(STATUS_DISABLED);
    await mount(<AutopostTab />);
    const select = container.querySelector('select');
    expect(select.value).toBe('1000');
    await change(select, '2000');
    expect(axios.put).toHaveBeenCalledWith(
      'http://test/api/settings/company',
      { expense_default_credit_account: '2000' },
    );
  });
});

describe('AutopostTab — gating lecture seule (sans accounting:write)', () => {
  test('contrôles désactivés, message lecture seule, aucun PUT au clic', async () => {
    mockPermissions = ['accounting:read'];
    stubStatus(STATUS_DISABLED);
    await mount(<AutopostTab />);
    expect(container.textContent).toContain('Lecture seule');
    const toggleBtn = Array.from(container.querySelectorAll('button'))
      .find(b => b.style.borderRadius === '20px');
    expect(toggleBtn.disabled).toBe(true);
    expect(container.querySelector('select').disabled).toBe(true);
    // Clic sur un toggle désactivé ne déclenche pas de PUT.
    await click(toggleBtn);
    expect(axios.put).not.toHaveBeenCalled();
  });

  test('bouton Réparer absent en lecture seule même avec erreurs', async () => {
    mockPermissions = ['accounting:read'];
    stubStatus(STATUS_ENABLED_WITH_ERRORS);
    await mount(<AutopostTab />);
    expect(container.textContent).toContain('2 écriture(s) en erreur');
    const repair = Array.from(container.querySelectorAll('button'))
      .find(b => b.textContent.trim() === 'Réparer');
    expect(repair).toBeUndefined();
  });
});

describe('AutopostTab — réparation', () => {
  test('badge erreurs + bouton Réparer → POST /repair + message succès', async () => {
    stubStatus(STATUS_ENABLED_WITH_ERRORS);
    axios.post.mockResolvedValueOnce({ data: { repaired: 2, still_failing: [] } });
    await mount(<AutopostTab />);
    expect(container.textContent).toContain('2 écriture(s) en erreur');
    const repair = Array.from(container.querySelectorAll('button'))
      .find(b => b.textContent.trim() === 'Réparer');
    expect(repair).toBeTruthy();
    await click(repair);
    expect(axios.post).toHaveBeenCalledWith('http://test/api/ledger/autopost/repair', {});
    expect(container.textContent).toContain('2 écriture(s) réparée(s)');
  });

  test('réparation partielle → message échec persistant (type err)', async () => {
    stubStatus(STATUS_ENABLED_WITH_ERRORS);
    axios.post.mockResolvedValueOnce({
      data: { repaired: 1, still_failing: [{ source_type: 'invoice', source_id: 'x' }] },
    });
    await mount(<AutopostTab />);
    const repair = Array.from(container.querySelectorAll('button'))
      .find(b => b.textContent.trim() === 'Réparer');
    await click(repair);
    expect(container.textContent).toContain('en échec persistant');
  });
});

describe('AutopostTab — assistant backfill (dry-run → apply)', () => {
  const PREVIEW = {
    would_create: { invoice: 2, invoice_payment: 1, expense: 3 },
    skipped_existing: 4,
    period: { start: '2026-01-01', end: '2026-12-31' },
  };

  test('aperçu dry-run affiche le total et le détail, puis apply crée les écritures', async () => {
    stubStatus(STATUS_DISABLED);
    // 1er POST = dry-run preview ; 2e POST = apply.
    axios.post
      .mockResolvedValueOnce({ data: PREVIEW })
      .mockResolvedValueOnce({
        data: { created: { invoice: 2, invoice_payment: 1, expense: 3 }, failed: [] },
      });
    await mount(<AutopostTab />);

    const previewBtn = Array.from(container.querySelectorAll('button'))
      .find(b => b.textContent.includes('Aperçu'));
    await click(previewBtn);

    // dry-run appelé avec dry_run:true
    expect(axios.post).toHaveBeenNthCalledWith(
      1, 'http://test/api/ledger/autopost/backfill', {},
      { params: { dry_run: true } },
    );
    // total = 2+1+3 = 6
    expect(container.textContent).toContain('6 écriture(s) seront créées');
    expect(container.textContent).toContain('Déjà comptabilisées (ignorées) : 4');

    const applyBtn = Array.from(container.querySelectorAll('button'))
      .find(b => b.textContent.includes('Confirmer et créer'));
    expect(applyBtn).toBeTruthy();
    await click(applyBtn);

    expect(axios.post).toHaveBeenNthCalledWith(
      2, 'http://test/api/ledger/autopost/backfill', {},
      { params: { dry_run: false } },
    );
    expect(container.textContent).toContain('Backfill appliqué');
  });

  test('aperçu avec 0 à créer → pas de bouton Confirmer, message « rien à créer »', async () => {
    stubStatus(STATUS_DISABLED);
    axios.post.mockResolvedValueOnce({
      data: { would_create: { invoice: 0, invoice_payment: 0, expense: 0 },
        skipped_existing: 9, period: { start: '2026-01-01', end: '2026-12-31' } },
    });
    await mount(<AutopostTab />);
    const previewBtn = Array.from(container.querySelectorAll('button'))
      .find(b => b.textContent.includes('Aperçu'));
    await click(previewBtn);
    expect(container.textContent).toContain('0 écriture(s) seront créées');
    expect(container.textContent).toContain('Rien à créer');
    const applyBtn = Array.from(container.querySelectorAll('button'))
      .find(b => b.textContent.includes('Confirmer et créer'));
    expect(applyBtn).toBeUndefined();
  });

  test('aperçu masqué en lecture seule (bouton Aperçu désactivé)', async () => {
    mockPermissions = ['accounting:read'];
    stubStatus(STATUS_DISABLED);
    await mount(<AutopostTab />);
    const previewBtn = Array.from(container.querySelectorAll('button'))
      .find(b => b.textContent.includes('Aperçu'));
    expect(previewBtn.disabled).toBe(true);
  });
});

// ════════════════════════════════════════════════════════════════════════════
describe('JournalTab — pastille Auto + verrou de contre-passation (§8.3)', () => {
  const ENTRIES = [
    { id: 'e-auto', entry_number: 'JE-0002', entry_date: '2026-03-01',
      description: 'Vente auto', total_debit: 100, status: 'posted',
      entry_type: 'auto', source_type: 'invoice', source_id: 'inv-1',
      reversed_by_entry_id: null },
    { id: 'e-manual', entry_number: 'JE-0001', entry_date: '2026-02-01',
      description: 'Ajustement manuel', total_debit: 50, status: 'posted',
      entry_type: 'manual', reversed_by_entry_id: null },
  ];

  function stubJournal() {
    axios.get.mockImplementation((url) => {
      if (url.includes('/ledger/entries')) return Promise.resolve({ data: ENTRIES });
      if (url.includes('/ledger/accounts')) return Promise.resolve({ data: [] });
      return Promise.resolve({ data: [] });
    });
  }

  test('écriture auto : pastille « Auto » + lien source ; écriture manuelle : aucune pastille', async () => {
    stubJournal();
    await mount(<JournalTab />);
    const text = container.textContent;
    expect(text).toContain('Auto');           // pastille
    expect(text).toContain('Facture');         // libellé du lien source (invoice)
    // Le lien source est un <button> soulignant « Facture → »
    const srcLink = Array.from(container.querySelectorAll('button'))
      .find(b => b.textContent.includes('Facture'));
    expect(srcLink).toBeTruthy();
  });

  test('bouton Contre-passer MASQUÉ sur auto, VISIBLE sur manuelle postée', async () => {
    stubJournal();
    await mount(<JournalTab />);
    const reverseButtons = Array.from(container.querySelectorAll('button'))
      .filter(b => b.textContent.trim() === 'Contre-passer');
    // Exactement 1 : celui de l'écriture manuelle (l'auto est verrouillée).
    expect(reverseButtons.length).toBe(1);
    // Vérifie qu'il est bien sur la ligne manuelle (dans la même <tr>).
    const row = reverseButtons[0].closest('tr');
    expect(row.textContent).toContain('Ajustement manuel');
    expect(row.textContent).not.toContain('Vente auto');
  });

  test('sans accounting:write : aucune colonne action, aucun bouton Contre-passer', async () => {
    mockPermissions = ['accounting:read'];
    stubJournal();
    await mount(<JournalTab />);
    const reverseButtons = Array.from(container.querySelectorAll('button'))
      .filter(b => b.textContent.trim() === 'Contre-passer');
    expect(reverseButtons.length).toBe(0);
  });
});
