import React, { useState } from 'react';

const TAX_FORMATS = {
  bn:  { regex: /^\d{9}$/,          hint: 'ex: 123456789' },
  gst: { regex: /^\d{9}RT\d{4}$/,   hint: 'ex: 123456789RT0001' },
  qst: { regex: /^\d{10}TQ\d{4}$/,  hint: 'ex: 1234567890TQ0001' },
  hst: { regex: /^\d{9}RT\d{4}$/,   hint: 'ex: 123456789RT0001' },
  neq: { regex: /^\d{10}$/,         hint: 'ex: 1234567890' },
};

export const normalizeTaxNumber = (v) => (v || '').trim().toUpperCase().replace(/[\s-]/g, '');

export const checkTaxNumber = (value, fieldName) => {
  if (!value) return { valid: true, expected: '' };
  const kind = fieldName.replace(/_number$/, ''); // bn_number -> bn
  const fmt = TAX_FORMATS[kind];
  if (!fmt) return { valid: true, expected: '' };
  return { valid: fmt.regex.test(value), expected: fmt.hint };
};

function TaxNumberInput({ label, fieldName, value, onChange, placeholder, tooltip }) {
  const [touched, setTouched] = useState(false);
  const [focused, setFocused] = useState(false);
  const inputId = `tax-${fieldName}`;
  const check = checkTaxNumber(value, fieldName);
  const showWarning = touched && value && !check.valid;
  const showOk = touched && value && check.valid;
  const borderColor = showWarning ? '#f59e0b' : showOk ? '#10b981' : '#d1d5db';
  const focusRing = focused ? '0 0 0 3px rgba(0, 160, 140, 0.18)' : 'none';

  return (
    <div style={{ marginBottom: 14 }}>
      <label htmlFor={inputId} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 500, color: '#374151', marginBottom: 4 }}>
        {label}
        {tooltip && (
          <span title={tooltip} style={{ cursor: 'help', color: '#6b7280', fontSize: 14 }}>&#9432;</span>
        )}
      </label>
      <input
        id={inputId}
        data-testid={`${fieldName}-input`}
        type="text"
        value={value || ''}
        placeholder={placeholder}
        onChange={(e) => onChange(normalizeTaxNumber(e.target.value))}
        onFocus={() => setFocused(true)}
        onBlur={() => { setFocused(false); setTouched(true); }}
        aria-invalid={showWarning ? 'true' : 'false'}
        aria-describedby={showWarning ? `${inputId}-warning` : undefined}
        style={{
          width: '100%',
          padding: '12px',
          border: `1.5px solid ${borderColor}`,
          borderRadius: 8,
          fontSize: 14,
          fontFamily: 'monospace',
          outline: 'none',
          boxShadow: focusRing,
          transition: 'box-shadow 0.15s, border-color 0.15s',
          boxSizing: 'border-box',
        }}
      />
      {showOk && (
        <div style={{ marginTop: 4, fontSize: 12, color: '#059669', display: 'flex', alignItems: 'center', gap: 4 }}>
          <span aria-hidden="true">✓</span> Format conforme
        </div>
      )}
      {showWarning && (
        <div id={`${inputId}-warning`} role="alert" style={{ marginTop: 4, fontSize: 12, color: '#b45309', display: 'flex', alignItems: 'center', gap: 4 }}>
          <span aria-hidden="true">⚠️</span> Format inhabituel — attendu : {check.expected}
        </div>
      )}
    </div>
  );
}

export default TaxNumberInput;
