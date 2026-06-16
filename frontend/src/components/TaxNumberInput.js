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
  const check = checkTaxNumber(value, fieldName);
  const showWarning = touched && value && !check.valid;
  const showOk = touched && value && check.valid;
  const borderColor = showWarning ? '#f59e0b' : showOk ? '#10b981' : '#d1d5db';

  return (
    <div style={{ marginBottom: 14 }}>
      <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 500, color: '#374151', marginBottom: 4 }}>
        {label}
        {tooltip && (
          <span title={tooltip} style={{ cursor: 'help', color: '#6b7280', fontSize: 14 }}>&#9432;</span>
        )}
      </label>
      <input
        type="text"
        value={value || ''}
        placeholder={placeholder}
        onChange={(e) => onChange(normalizeTaxNumber(e.target.value))}
        onBlur={() => setTouched(true)}
        style={{
          width: '100%',
          padding: '8px 10px',
          border: `1.5px solid ${borderColor}`,
          borderRadius: 6,
          fontSize: 13,
          fontFamily: 'monospace',
          outline: 'none',
          boxSizing: 'border-box',
        }}
      />
      {showWarning && (
        <div style={{ marginTop: 4, fontSize: 12, color: '#b45309' }}>
          &#9888;&#65039; Format inhabituel — attendu : {check.expected}
        </div>
      )}
    </div>
  );
}

export default TaxNumberInput;
