import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { BACKEND_URL, formatCurrency } from '../config';

const InvoicesPage = () => {
  const [invoices, setInvoices] = useState([]);
  const [clients, setClients] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [formData, setFormData] = useState({
    client_id: '', due_date: new Date(Date.now() + 30*24*60*60*1000).toISOString().split('T')[0],
    items: [{ description: '', quantity: 1, unit_price: 0 }], province: 'QC', notes: ''
  });

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    try {
      const [invoicesRes, clientsRes, productsRes] = await Promise.all([
        axios.get(`${BACKEND_URL}/api/invoices`),
        axios.get(`${BACKEND_URL}/api/clients`),
        axios.get(`${BACKEND_URL}/api/products`)
      ]);
      setInvoices(invoicesRes.data); setClients(clientsRes.data); setProducts(productsRes.data);
    } catch (err) {
      setError('Erreur lors du chargement des donnees');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(''); setSuccess('');
    try {
      await axios.post(`${BACKEND_URL}/api/invoices`, {
        ...formData, items: formData.items.map(item => ({ ...item, total: item.quantity * item.unit_price }))
      });
      setSuccess('Facture creee avec succes'); setShowForm(false);
      setFormData({ client_id: '', due_date: new Date(Date.now() + 30*24*60*60*1000).toISOString().split('T')[0],
        items: [{ description: '', quantity: 1, unit_price: 0 }], province: 'QC', notes: '' });
      fetchData();
    } catch (err) {
      setError('Erreur lors de la creation de la facture');
    }
  };

  const addItem = () => setFormData(prev => ({ ...prev, items: [...prev.items, { description: '', quantity: 1, unit_price: 0 }] }));
  const updateItem = (index, field, value) => {
    const newItems = [...formData.items]; newItems[index] = { ...newItems[index], [field]: value };
    setFormData(prev => ({ ...prev, items: newItems }));
  };
  const removeItem = (index) => { if (formData.items.length > 1) setFormData(prev => ({ ...prev, items: prev.items.filter((_, i) => i !== index) })); };
  const getClientName = (clientId) => clients.find(c => c.id === clientId)?.name || 'Client inconnu';

  return (
    <div data-testid="invoices-page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <div style={{ fontSize: '32px', marginRight: '12px' }}>📄</div>
          <div>
            <h1 style={{ fontSize: '32px', fontWeight: '800', color: '#1f2937', margin: 0 }}>Factures</h1>
            <p style={{ color: '#6b7280', margin: 0 }}>Creez et gerez vos factures clients</p>
          </div>
        </div>
        <button onClick={() => setShowForm(true)} data-testid="add-invoice-btn" style={{
          background: 'linear-gradient(135deg, #00A08C, #008F7A)', color: 'white', border: 'none',
          padding: '14px 28px', borderRadius: '12px', cursor: 'pointer', fontWeight: '700', fontSize: '14px'
        }}>+ Nouvelle Facture</button>
      </div>

      {error && <div style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#b91c1c', padding: '16px', borderRadius: '12px', marginBottom: '20px' }}>{error}</div>}
      {success && <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', color: '#166534', padding: '16px', borderRadius: '12px', marginBottom: '20px' }}>{success}</div>}

      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px' }}><p>Chargement des factures...</p></div>
      ) : invoices.length === 0 ? (
        <div style={{ background: 'white', border: '2px dashed #d1d5db', borderRadius: '16px', padding: '64px', textAlign: 'center' }}>
          <div style={{ fontSize: '80px', marginBottom: '24px' }}>📄</div>
          <h3 style={{ fontSize: '24px', fontWeight: '700', color: '#374151', margin: '0 0 12px 0' }}>Aucune facture creee</h3>
          <button onClick={() => setShowForm(true)} style={{ background: '#00A08C', color: 'white', border: 'none', padding: '16px 32px', borderRadius: '12px', cursor: 'pointer', fontWeight: '700', fontSize: '16px' }}>
            Creer ma premiere facture
          </button>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '16px' }}>
          {invoices.map(invoice => (
            <div key={invoice.id} data-testid={`invoice-card-${invoice.id}`} style={{
              background: 'white', border: '1px solid #e5e7eb', borderRadius: '12px', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                <div>
                  <h3 style={{ fontSize: '20px', fontWeight: '700', color: '#1f2937', margin: '0 0 8px 0' }}>{invoice.invoice_number}</h3>
                  <p style={{ color: '#6b7280', margin: '4px 0' }}>Client: {getClientName(invoice.client_id)}</p>
                  <p style={{ color: '#6b7280', margin: '4px 0', fontSize: '14px' }}>Echeance: {new Date(invoice.due_date).toLocaleDateString('fr-CA')}</p>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '24px', fontWeight: '800', color: '#1f2937' }}>{formatCurrency(invoice.total)}</div>
                  <span style={{
                    background: invoice.status === 'paid' ? '#dcfce7' : '#fef3c7',
                    color: invoice.status === 'paid' ? '#166534' : '#92400e',
                    padding: '4px 8px', borderRadius: '6px', fontSize: '12px', fontWeight: '600'
                  }}>{invoice.status === 'paid' ? 'Payee' : invoice.status}</span>
                  <div style={{ marginTop: '8px' }}>
                    <button onClick={async () => {
                      if (window.confirm('Supprimer cette facture ?')) {
                        try { await axios.delete(`${BACKEND_URL}/api/invoices/${invoice.id}`); setSuccess('Facture supprimee'); fetchData(); }
                        catch (err) { setError('Erreur suppression'); }
                      }
                    }} data-testid={`delete-invoice-${invoice.id}`} style={{
                      background: '#fef2f2', color: '#dc2626', border: 'none', padding: '6px 12px',
                      borderRadius: '6px', cursor: 'pointer', fontSize: '12px', fontWeight: '600'
                    }}>Supprimer</button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Invoice Form Modal */}
      {showForm && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '20px' }}>
          <div style={{ background: 'white', padding: '32px', borderRadius: '16px', width: '95%', maxWidth: '800px', maxHeight: '90vh', overflow: 'auto' }}>
            <h3 style={{ margin: '0 0 24px 0', fontSize: '20px', fontWeight: '700' }}>Nouvelle Facture</h3>
            <form onSubmit={handleSubmit}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '16px', marginBottom: '24px' }}>
                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Client *</label>
                  <select value={formData.client_id} onChange={(e) => setFormData(prev => ({ ...prev, client_id: e.target.value }))} required
                    data-testid="invoice-client-select"
                    style={{ width: '100%', padding: '12px', border: '1px solid #ddd', borderRadius: '8px', boxSizing: 'border-box' }}>
                    <option value="">Selectionner un client</option>
                    {clients.map(client => <option key={client.id} value={client.id}>{client.name}</option>)}
                  </select>
                </div>
                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Echeance *</label>
                  <input type="date" value={formData.due_date} onChange={(e) => setFormData(prev => ({ ...prev, due_date: e.target.value }))} required
                    style={{ width: '100%', padding: '12px', border: '1px solid #ddd', borderRadius: '8px', boxSizing: 'border-box' }} />
                </div>
                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Province</label>
                  <select value={formData.province} onChange={(e) => setFormData(prev => ({ ...prev, province: e.target.value }))}
                    data-testid="invoice-province-select"
                    style={{ width: '100%', padding: '12px', border: '1px solid #ddd', borderRadius: '8px', boxSizing: 'border-box' }}>
                    <option value="QC">Quebec (TPS 5% + TVQ 9.975%)</option>
                    <option value="ON">Ontario (HST 13%)</option>
                  </select>
                </div>
              </div>

              <div style={{ marginBottom: '24px' }}>
                <h4 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: '700' }}>Articles et Services</h4>
                {formData.items.map((item, index) => (
                  <div key={index} style={{
                    display: 'grid', gridTemplateColumns: '2fr 100px 120px 120px auto',
                    gap: '12px', marginBottom: '12px', padding: '16px', background: '#f8fafc', borderRadius: '8px', alignItems: 'center'
                  }}>
                    <input type="text" value={item.description} onChange={(e) => updateItem(index, 'description', e.target.value)}
                      placeholder="Description" required
                      style={{ padding: '10px', border: '1px solid #ddd', borderRadius: '6px', boxSizing: 'border-box' }} />
                    <input type="number" step="0.01" value={item.quantity} onChange={(e) => updateItem(index, 'quantity', parseFloat(e.target.value) || 0)}
                      style={{ padding: '10px', border: '1px solid #ddd', borderRadius: '6px', textAlign: 'center', boxSizing: 'border-box' }} />
                    <input type="number" step="0.01" value={item.unit_price} onChange={(e) => updateItem(index, 'unit_price', parseFloat(e.target.value) || 0)}
                      style={{ padding: '10px', border: '1px solid #ddd', borderRadius: '6px', textAlign: 'center', boxSizing: 'border-box' }} />
                    <div style={{ padding: '10px', background: '#e5e7eb', borderRadius: '6px', textAlign: 'center', fontWeight: '600' }}>
                      {formatCurrency(item.quantity * item.unit_price)}
                    </div>
                    <button type="button" onClick={() => removeItem(index)} disabled={formData.items.length === 1}
                      style={{ background: formData.items.length === 1 ? '#f3f4f6' : '#ef4444', color: formData.items.length === 1 ? '#9ca3af' : 'white',
                        border: 'none', padding: '8px', borderRadius: '6px', cursor: formData.items.length === 1 ? 'not-allowed' : 'pointer' }}>X</button>
                  </div>
                ))}
                <button type="button" onClick={addItem} style={{
                  background: '#10b981', color: 'white', border: 'none', padding: '10px 20px', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', marginTop: '8px'
                }}>+ Ajouter un article</button>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                <button type="button" onClick={() => setShowForm(false)} style={{
                  background: 'white', color: '#374151', border: '1px solid #d1d5db', padding: '12px 24px', borderRadius: '8px', cursor: 'pointer'
                }}>Annuler</button>
                <button type="submit" data-testid="save-invoice-btn" style={{
                  background: '#00A08C', color: 'white', border: 'none', padding: '12px 24px', borderRadius: '8px', cursor: 'pointer', fontWeight: '600'
                }}>Creer la facture</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default InvoicesPage;
