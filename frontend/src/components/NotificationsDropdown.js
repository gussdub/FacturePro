import React from 'react';

const fmt = (n) => Number(n || 0).toFixed(2);

// Rappels « À relancer » (feature #7.15) : factures avec un solde dû dont la date convenue est
// arrivée (ou proche). La liste vient de Layout (GET /api/invoices/payment-reminders).
const NotificationsDropdown = ({ isOpen, onClose, reminders = [], onGoInvoices }) => {
  if (!isOpen) return null;

  return (
    <div style={{
      position: 'absolute', top: '100%', right: 0, background: 'white',
      border: '1px solid #e5e7eb', borderRadius: '12px',
      boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)', width: '340px', zIndex: 50, marginTop: '8px'
    }}>
      <div style={{ padding: '16px', borderBottom: '1px solid #e5e7eb' }}>
        <h3 style={{ fontSize: '16px', fontWeight: '700', color: '#1f2937', margin: 0 }}>
          À relancer {reminders.length > 0 ? `(${reminders.length})` : ''}
        </h3>
      </div>
      <div style={{ maxHeight: '320px', overflowY: 'auto' }}>
        {reminders.length === 0 && (
          <div style={{ padding: '20px 16px', color: '#6b7280', fontSize: 14 }}>
            Aucun paiement à relancer. 🎉
          </div>
        )}
        {reminders.map((r) => {
          const overdue = r.days_overdue > 0;
          const timing = overdue
            ? ` · en retard de ${r.days_overdue} j`
            : (r.days_overdue === 0 ? " · aujourd'hui" : ` · dans ${-r.days_overdue} j`);
          return (
            <div key={r.invoice_id} style={{ padding: '14px 16px', borderBottom: '1px solid #f3f4f6' }}>
              <div style={{ display: 'flex', alignItems: 'start', gap: '10px' }}>
                <div style={{
                  width: '8px', height: '8px', borderRadius: '50%',
                  background: overdue ? '#ef4444' : '#f59e0b', marginTop: '6px', flexShrink: 0
                }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{ fontSize: '14px', color: '#374151', margin: '0 0 2px', fontWeight: 600 }}>
                    {r.invoice_number} — {r.client_name || 'Client'}
                  </p>
                  <p style={{ fontSize: '13px', color: '#111827', margin: '0 0 2px' }}>
                    Solde à réclamer : <strong>{fmt(r.outstanding_cad)} $</strong>
                  </p>
                  <p style={{ fontSize: '12px', color: overdue ? '#dc2626' : '#6b7280', margin: 0 }}>
                    Date convenue : {r.balance_due_date}{timing}
                  </p>
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <div style={{ padding: '12px 16px', display: 'flex', justifyContent: 'space-between',
                    alignItems: 'center', borderTop: '1px solid #e5e7eb' }}>
        {reminders.length > 0 && onGoInvoices ? (
          <button onClick={onGoInvoices} style={{ background: 'none', border: 'none',
            color: '#00A08C', fontSize: '14px', fontWeight: 600, cursor: 'pointer' }}>
            Voir les factures →
          </button>
        ) : <span />}
        <button onClick={onClose} style={{ background: 'none', border: 'none',
          color: '#6b7280', fontSize: '14px', cursor: 'pointer' }}>
          Fermer
        </button>
      </div>
    </div>
  );
};

export default NotificationsDropdown;
