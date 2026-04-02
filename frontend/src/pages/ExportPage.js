import React from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { BACKEND_URL } from '../config';

const ExportPage = () => {
  const { token } = useAuth();

  const downloadCSV = async (type) => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/export/${type}/csv`, {
        headers: { Authorization: `Bearer ${token}` },
        responseType: 'blob'
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', type === 'invoices' ? 'factures.csv' : 'depenses.csv');
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert("Erreur lors de l'export");
    }
  };

  return (
    <div data-testid="export-page" style={{ padding: '40px', maxWidth: '800px', margin: '0 auto' }}>
      <h2 style={{ fontSize: '28px', fontWeight: '700', marginBottom: '32px', color: '#1f2937' }}>Exports</h2>
      <p style={{ color: '#6b7280', marginBottom: '32px' }}>Exportez vos donnees au format CSV.</p>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
        <div data-testid="export-invoices-card" style={{
          background: 'white', borderRadius: '12px', padding: '32px', border: '1px solid #e5e7eb', textAlign: 'center'
        }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>📄</div>
          <h3 style={{ fontSize: '20px', fontWeight: '600', marginBottom: '8px' }}>Factures</h3>
          <p style={{ color: '#6b7280', marginBottom: '20px', fontSize: '14px' }}>Exportez toutes vos factures</p>
          <button data-testid="export-invoices-btn" onClick={() => downloadCSV('invoices')} style={{
            background: '#00A08C', color: 'white', border: 'none', padding: '10px 24px',
            borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '14px'
          }}>Telecharger CSV</button>
        </div>

        <div data-testid="export-expenses-card" style={{
          background: 'white', borderRadius: '12px', padding: '32px', border: '1px solid #e5e7eb', textAlign: 'center'
        }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>💰</div>
          <h3 style={{ fontSize: '20px', fontWeight: '600', marginBottom: '8px' }}>Depenses</h3>
          <p style={{ color: '#6b7280', marginBottom: '20px', fontSize: '14px' }}>Exportez toutes vos depenses</p>
          <button data-testid="export-expenses-btn" onClick={() => downloadCSV('expenses')} style={{
            background: '#00A08C', color: 'white', border: 'none', padding: '10px 24px',
            borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '14px'
          }}>Telecharger CSV</button>
        </div>
      </div>
    </div>
  );
};

export default ExportPage;
