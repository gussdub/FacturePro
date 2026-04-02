import axios from 'axios';

export const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'https://facturepro-api.onrender.com';

export const LOGO_URL = 'https://customer-assets.emergentagent.com/job_37455350-d4d4-40f6-ab0f-e859ab6de5ff/artifacts/menbvk51_2c256145-633e-411d-9781-dce2201c8da3_wm.jpeg';

export const api = axios;

export const formatCurrency = (amount) => {
  return new Intl.NumberFormat('fr-CA', {
    style: 'currency',
    currency: 'CAD'
  }).format(amount || 0);
};
