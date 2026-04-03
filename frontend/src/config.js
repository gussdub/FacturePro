import axios from 'axios';

export const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'https://facturepro-api.onrender.com';

export const FACTUREPRO_LOGO_FILE_ID = '6b96d4e4-c7c0-45f1-b6c9-1019ab1ef3bd';

export const api = axios;

export const CURRENCY_SYMBOLS = { CAD: 'CA$', USD: 'US$', EUR: '€', GBP: '£' };
export const CURRENCY_LABELS = { CAD: 'Dollar canadien (CAD)', USD: 'Dollar americain (USD)', EUR: 'Euro (EUR)', GBP: 'Livre sterling (GBP)' };

export const formatCurrency = (amount, currency = 'CAD') => {
  const locale = currency === 'EUR' ? 'fr-FR' : 'fr-CA';
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency: currency || 'CAD'
  }).format(amount || 0);
};
