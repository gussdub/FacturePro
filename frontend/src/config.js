import axios from 'axios';

export const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'https://facturepro-api.onrender.com';

export const FACTUREPRO_LOGO_FILE_ID = '6b96d4e4-c7c0-45f1-b6c9-1019ab1ef3bd';

export const api = axios;

export const formatCurrency = (amount) => {
  return new Intl.NumberFormat('fr-CA', {
    style: 'currency',
    currency: 'CAD'
  }).format(amount || 0);
};
