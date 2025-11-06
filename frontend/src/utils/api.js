// Force production URL when on facturepro.ca
export const BACKEND_URL = window.location.hostname === 'facturepro.ca' 
  ? 'https://facturepro.ca'
  : process.env.REACT_APP_BACKEND_URL;

export const API = `${BACKEND_URL}/api`;

export default { BACKEND_URL, API };