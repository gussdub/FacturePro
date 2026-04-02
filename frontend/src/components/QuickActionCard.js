import React from 'react';

const QuickActionCard = ({ icon, title, description, onClick }) => {
  return (
    <button
      onClick={onClick}
      data-testid={`quick-action-${title.toLowerCase().replace(/\s+/g, '-')}`}
      style={{
        background: '#f8fafc', border: '1px solid #e2e8f0',
        padding: '20px', borderRadius: '12px', cursor: 'pointer',
        textAlign: 'center', transition: 'all 0.3s ease', width: '100%'
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = '#f1f5f9';
        e.currentTarget.style.transform = 'translateY(-2px)';
        e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = '#f8fafc';
        e.currentTarget.style.transform = 'translateY(0)';
        e.currentTarget.style.boxShadow = 'none';
      }}
    >
      <div style={{ fontSize: '32px', marginBottom: '12px' }}>{icon}</div>
      <div style={{ fontWeight: '600', color: '#374151', fontSize: '16px', marginBottom: '4px' }}>{title}</div>
      <div style={{ fontSize: '14px', color: '#6b7280' }}>{description}</div>
    </button>
  );
};

export default QuickActionCard;
