import React from 'react';

const NotificationsDropdown = ({ isOpen, onClose }) => {
  const notifications = [
    { id: 1, type: 'info', message: 'Bienvenue dans FacturePro !', time: 'Il y a 2 minutes' },
    { id: 2, type: 'success', message: 'Application deployee avec succes', time: 'Il y a 1 heure' },
    { id: 3, type: 'warning', message: 'Pensez a configurer vos numeros de taxes', time: 'Il y a 2 heures' }
  ];

  if (!isOpen) return null;

  return (
    <div style={{
      position: 'absolute', top: '100%', right: 0, background: 'white',
      border: '1px solid #e5e7eb', borderRadius: '12px',
      boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)', width: '320px', zIndex: 50, marginTop: '8px'
    }}>
      <div style={{ padding: '16px', borderBottom: '1px solid #e5e7eb' }}>
        <h3 style={{ fontSize: '16px', fontWeight: '700', color: '#1f2937', margin: 0 }}>
          Notifications
        </h3>
      </div>
      <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
        {notifications.map(notification => (
          <div key={notification.id} style={{ padding: '16px', borderBottom: '1px solid #f3f4f6' }}>
            <div style={{ display: 'flex', alignItems: 'start', gap: '12px' }}>
              <div style={{
                width: '8px', height: '8px', borderRadius: '50%',
                background: notification.type === 'success' ? '#10b981' : notification.type === 'warning' ? '#f59e0b' : '#00A08C',
                marginTop: '6px'
              }} />
              <div style={{ flex: 1 }}>
                <p style={{ fontSize: '14px', color: '#374151', margin: '0 0 4px 0', fontWeight: '500' }}>
                  {notification.message}
                </p>
                <p style={{ fontSize: '12px', color: '#6b7280', margin: 0 }}>{notification.time}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
      <div style={{ padding: '12px 16px', textAlign: 'center', borderTop: '1px solid #e5e7eb' }}>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#6b7280', fontSize: '14px', cursor: 'pointer' }}>
          Fermer
        </button>
      </div>
    </div>
  );
};

export default NotificationsDropdown;
