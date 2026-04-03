import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { BACKEND_URL, CURRENCY_SYMBOLS, formatCurrency } from '../config';

const CurrencySelector = ({ currency, onChange, amount, style }) => {
  const [rates, setRates] = useState(null);

  const fetchRates = useCallback(async () => {
    try {
      const res = await axios.get(`${BACKEND_URL}/api/exchange-rates`);
      setRates(res.data.rates);
    } catch {
      setRates({ CAD: 1.0, USD: 0.73, EUR: 0.67, GBP: 0.57 });
    }
  }, []);

  useEffect(() => { fetchRates(); }, [fetchRates]);

  const handleChange = (newCurrency) => {
    const rate = rates?.[newCurrency] || 1.0;
    onChange(newCurrency, rate);
  };

  const cadEquivalent = currency !== 'CAD' && amount > 0 && rates
    ? amount / (rates[currency] || 1.0)
    : null;

  return (
    <div>
      <div style={{ display: 'flex', gap: '6px', ...style }}>
        {['CAD', 'USD', 'EUR', 'GBP'].map(cur => (
          <button
            key={cur}
            type="button"
            data-testid={`currency-btn-${cur}`}
            onClick={() => handleChange(cur)}
            style={{
              padding: '6px 12px', borderRadius: '4px', fontSize: '12px', fontWeight: '600',
              cursor: 'pointer', transition: 'all 0.15s ease',
              border: currency === cur ? '1px solid #09090b' : '1px solid #e4e4e7',
              background: currency === cur ? '#09090b' : '#ffffff',
              color: currency === cur ? '#ffffff' : '#52525b'
            }}
          >
            {CURRENCY_SYMBOLS[cur]} {cur}
          </button>
        ))}
      </div>
      {cadEquivalent !== null && (
        <div data-testid="cad-conversion-preview" style={{
          marginTop: '6px', fontSize: '12px', color: '#71717a',
          display: 'flex', alignItems: 'center', gap: '4px'
        }}>
          <span style={{ color: '#a1a1aa' }}>=</span>
          <span style={{ fontWeight: '600', color: '#09090b' }}>{formatCurrency(cadEquivalent, 'CAD')}</span>
          <span>CAD</span>
          <span style={{ color: '#d4d4d8' }}>|</span>
          <span>Taux: 1 CAD = {(rates[currency] || 1).toFixed(4)} {currency}</span>
        </div>
      )}
    </div>
  );
};

export default CurrencySelector;
