import React from 'react';

const FactureProLogo = ({ size = 48 }) => (
  <svg width={size} height={size} viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
    <rect width="120" height="120" rx="28" fill="url(#tealGrad)" />
    <rect x="28" y="22" width="64" height="80" rx="8" fill="white" fillOpacity="0.95" />
    <rect x="28" y="22" width="64" height="24" rx="8" fill="white" />
    <path d="M50 38 L70 38" stroke="#00A08C" strokeWidth="3" strokeLinecap="round" />
    <path d="M42 54 L78 54" stroke="#B0E0D8" strokeWidth="2.5" strokeLinecap="round" />
    <path d="M42 64 L72 64" stroke="#B0E0D8" strokeWidth="2.5" strokeLinecap="round" />
    <path d="M42 74 L66 74" stroke="#B0E0D8" strokeWidth="2.5" strokeLinecap="round" />
    <circle cx="82" cy="82" r="22" fill="#00A08C" stroke="white" strokeWidth="4" />
    <text x="82" y="90" textAnchor="middle" fill="white" fontSize="28" fontWeight="bold" fontFamily="Arial">$</text>
    <defs>
      <linearGradient id="tealGrad" x1="0" y1="0" x2="120" y2="120" gradientUnits="userSpaceOnUse">
        <stop stopColor="#47D2A7" />
        <stop offset="1" stopColor="#00A08C" />
      </linearGradient>
    </defs>
  </svg>
);

export default FactureProLogo;
