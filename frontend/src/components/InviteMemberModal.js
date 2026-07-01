// Stub — sera implémenté dans Task 15.
// Fournit un default export pour que SettingsPage.js compile.
import React from 'react';

export default function InviteMemberModal({ onClose, onSuccess }) {
  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
      display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000,
    }}>
      <div style={{
        background: '#fff', borderRadius: 8, padding: 24,
        width: 480, maxWidth: '90vw',
      }}>
        <p>Invitation modal (à implémenter en Task 15).</p>
        <button onClick={onClose} style={{ padding: '8px 16px' }}>Fermer</button>
      </div>
    </div>
  );
}
