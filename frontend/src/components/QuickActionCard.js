import React from 'react';

const QuickActionCard = ({ icon: Icon, title, description, onClick }) => {
  const isComponent = Icon && typeof Icon !== 'string' && typeof Icon !== 'number';
  return (
    <button
      onClick={onClick}
      data-testid={`quick-action-${title.toLowerCase().replace(/\s+/g, '-')}`}
      style={{
        background: '#ffffff', border: '1px solid #e4e4e7',
        padding: '20px', borderRadius: '6px', cursor: 'pointer',
        textAlign: 'left', transition: 'all 0.15s ease', width: '100%'
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = '#09090b';
        e.currentTarget.style.transform = 'translateY(-1px)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = '#e4e4e7';
        e.currentTarget.style.transform = 'translateY(0)';
      }}
    >
      <div style={{ marginBottom: '12px' }}>
        {isComponent ? <Icon size={22} strokeWidth={1.5} color="#52525b" /> : <span style={{ fontSize: '24px' }}>{Icon}</span>}
      </div>
      <div style={{ fontWeight: '600', color: '#09090b', fontSize: '14px', marginBottom: '3px', letterSpacing: '-0.01em' }}>{title}</div>
      <div style={{ fontSize: '12px', color: '#a1a1aa' }}>{description}</div>
    </button>
  );
};

export default QuickActionCard;
