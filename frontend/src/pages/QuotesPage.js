import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { BACKEND_URL, formatCurrency } from '../config';

const QuotesPage = () => {
  const [quotes, setQuotes] = useState([]);
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [formData, setFormData] = useState({
    client_id: '', valid_until: new Date(Date.now() + 30*24*60*60*1000).toISOString().split('T')[0],
    items: [{ description: '', quantity: 1, unit_price: 0 }], province: 'QC', notes: ''
  });

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    try {
      const [quotesRes, clientsRes] = await Promise.all([
        axios.get(`${BACKEND_URL}/api/quotes`),
        axios.get(`${BACKEND_URL}/api/clients`)
      ]);
      setQuotes(quotesRes.data); setClients(clientsRes.data);
    } catch (err) {
      setError('Erreur lors du chargement');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(''); setSuccess('');
    try {
      await axios.post(`${BACKEND_URL}/api/quotes`, {
        ...formData, items: formData.items.map(item => ({ ...item, total: item.quantity * item.unit_price }))
      });
      setSuccess('Soumission creee avec succes'); setShowForm(false);
      setFormData({ client_id: '', valid_until: new Date(Date.now() + 30*24*60*60*1000).toISOString().split('T')[0],
        items: [{ description: '', quantity: 1, unit_price: 0 }], province: 'QC', notes: '' });
      fetchData();
    } catch (err) {
      setError('Erreur lors de la creation');
    }
  };

  return (
    <div data-testid="quotes-page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <div style={{ fontSize: '32px', marginRight: '12px' }}>📝</div>
          <div>
            <h1 style={{ fontSize: '32px', fontWeight: '800', color: '#1f2937', margin: 0 }}>Soumissions</h1>
            <p style={{ color: '#6b7280', margin: 0 }}>Creez des devis pour vos prospects</p>
          </div>
        </div>
        <button onClick={() => setShowForm(true)} data-testid="add-quote-btn" style={{
          background: 'linear-gradient(135deg, #47D2A7, #008F7A)', color: 'white', border: 'none',
          padding: '14px 28px', borderRadius: '12px', cursor: 'pointer', fontWeight: '700', fontSize: '14px'
        }}>+ Nouvelle Soumission</button>
      </div>

      {error && <div style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#b91c1c', padding: '16px', borderRadius: '12px', marginBottom: '20px' }}>{error}</div>}
      {success && <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', color: '#166534', padding: '16px', borderRadius: '12px', marginBottom: '20px' }}>{success}</div>}

      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px' }}><p>Chargement des soumissions...</p></div>
      ) : quotes.length === 0 ? (
        <div style={{ background: 'white', border: '2px dashed #d1d5db', borderRadius: '16px', padding: '64px', textAlign: 'center' }}>
          <div style={{ fontSize: '80px', marginBottom: '24px' }}>📝</div>
          <h3 style={{ fontSize: '24px', fontWeight: '700', color: '#374151', margin: '0 0 12px 0' }}>Aucune soumission creee</h3>
          <button onClick={() => setShowForm(true)} style={{ background: '#47D2A7', color: 'white', border: 'none', padding: '16px 32px', borderRadius: '12px', cursor: 'pointer', fontWeight: '700', fontSize: '16px' }}>
            Creer ma premiere soumission
          </button>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '16px' }}>
          {quotes.map(quote => (
            <div key={quote.id} data-testid={`quote-card-${quote.id}`} style={{
              background: 'white', border: '1px solid #e5e7eb', borderRadius: '12px', padding: '24px'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <div>
                  <h3 style={{ fontSize: '20px', fontWeight: '700', margin: '0 0 8px 0' }}>{quote.quote_number}</h3>
                  <p style={{ color: '#6b7280' }}>Valide jusqu'au: {new Date(quote.valid_until).toLocaleDateString('fr-CA')}</p>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '24px', fontWeight: '800', color: '#47D2A7' }}>{formatCurrency(quote.total)}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {showForm && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '20px' }}>
          <div style={{ background: 'white', padding: '32px', borderRadius: '16px', width: '95%', maxWidth: '600px' }}>
            <h3 style={{ margin: '0 0 24px 0' }}>Nouvelle Soumission</h3>
            <form onSubmit={handleSubmit}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '24px' }}>
                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Client *</label>
                  <select value={formData.client_id} onChange={(e) => setFormData(prev => ({ ...prev, client_id: e.target.value }))} required
                    data-testid="quote-client-select"
                    style={{ width: '100%', padding: '12px', border: '1px solid #ddd', borderRadius: '8px', boxSizing: 'border-box' }}>
                    <option value="">Selectionner un client</option>
                    {clients.map(client => <option key={client.id} value={client.id}>{client.name}</option>)}
                  </select>
                </div>
                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Valide jusqu'au *</label>
                  <input type="date" value={formData.valid_until} onChange={(e) => setFormData(prev => ({ ...prev, valid_until: e.target.value }))} required
                    style={{ width: '100%', padding: '12px', border: '1px solid #ddd', borderRadius: '8px', boxSizing: 'border-box' }} />
                </div>
              </div>
              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Description *</label>
                <input type="text" value={formData.items[0]?.description || ''}
                  onChange={(e) => setFormData(prev => ({ ...prev, items: [{ ...prev.items[0], description: e.target.value }] }))}
                  required placeholder="Description de la soumission"
                  style={{ width: '100%', padding: '12px', border: '1px solid #ddd', borderRadius: '8px', boxSizing: 'border-box' }} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                <button type="button" onClick={() => setShowForm(false)} style={{
                  background: 'white', color: '#374151', border: '1px solid #d1d5db', padding: '12px 24px', borderRadius: '8px', cursor: 'pointer'
                }}>Annuler</button>
                <button type="submit" data-testid="save-quote-btn" style={{
                  background: '#47D2A7', color: 'white', border: 'none', padding: '12px 24px', borderRadius: '8px', cursor: 'pointer', fontWeight: '600'
                }}>Creer la soumission</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default QuotesPage;
