// Sélecteur « Choisir un employé existant » : préremplit le courriel et le rôle Employé,
// et n'offre que les fiches avec courriel qui ne sont pas déjà membres ou invitées.
import React from 'react';
import { createRoot } from 'react-dom/client';
import { act } from 'react-dom/test-utils';
import InviteMemberModal from './InviteMemberModal';

jest.mock('axios', () => ({
  __esModule: true,
  default: { get: jest.fn(), post: jest.fn() },
}));
const axios = require('axios').default;

let container, root;
beforeEach(() => {
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
  axios.get.mockResolvedValue({ data: [
    { id: 'e1', name: 'Marie Tremblay', email: 'Marie@Exemple.com' },
    { id: 'e2', name: 'Sans courriel', email: '' },
    { id: 'e3', name: 'Déjà membre', email: 'membre@exemple.com' },
  ] });
});
afterEach(() => { act(() => root.unmount()); container.remove(); });

test('préremplit le courriel et le rôle Employé', async () => {
  await act(async () => {
    root.render(<InviteMemberModal onClose={() => {}} onSuccess={() => {}}
      existingEmails={['MEMBRE@exemple.com']} />);
  });
  const select = container.querySelector('[data-testid="invite-employee-select"]');
  const values = [...select.options].map(o => o.value);
  expect(values).toEqual(['', 'e1']);
  await act(async () => {
    const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;
    setter.call(select, 'e1');
    select.dispatchEvent(new Event('change', { bubbles: true }));
  });
  expect(container.querySelector('input[type="email"]').value).toBe('Marie@Exemple.com');
  const selects = container.querySelectorAll('select');
  expect(selects[selects.length - 1].value).toBe('employee');
});

test('aucun sélecteur sans permission employees:read', async () => {
  axios.get.mockRejectedValue({ response: { status: 403 } });
  await act(async () => {
    root.render(<InviteMemberModal onClose={() => {}} onSuccess={() => {}} />);
  });
  expect(container.querySelector('[data-testid="invite-employee-select"]')).toBeNull();
});
