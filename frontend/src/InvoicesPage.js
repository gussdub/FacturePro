import React, { useState, useEffect } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'https://facturepro-api.onrender.com';

const InvoicesPage = () => {
  const [invoices, setInvoices] = useState([]);
  const [clients, setClients] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    client_id: '',
    due_date: '',
    items: [{ description: '', quantity: 1, unit_price: 0, product_id: '' }],
    province: 'QC',
    notes: ''
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [invoicesRes, clientsRes, productsRes] = await Promise.all([
        axios.get(`${BACKEND_URL}/api/invoices`),
        axios.get(`${BACKEND_URL}/api/clients`),
        axios.get(`${BACKEND_URL}/api/products`)
      ]);
      setInvoices(invoicesRes.data);
      setClients(clientsRes.data);
      setProducts(productsRes.data);
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    try {
      // Calculate totals for items
      const processedItems = formData.items.map(item => ({
        ...item,
        total: item.quantity * item.unit_price
      }));

      const invoiceData = {
        ...formData,
        items: processedItems,
        due_date: new Date(formData.due_date).toISOString(),
        apply_gst: formData.province === 'QC',
        apply_pst: formData.province === 'QC',
        apply_hst: formData.province === 'ON',
        gst_rate: formData.province === 'QC' ? 5.0 : 0,
        pst_rate: formData.province === 'QC' ? 9.975 : 0,
        hst_rate: formData.province === 'ON' ? 13.0 : 0
      };

      await axios.post(`${BACKEND_URL}/api/invoices`, invoiceData);
      
      setShowForm(false);
      setFormData({
        client_id: '',
        due_date: '',
        items: [{ description: '', quantity: 1, unit_price: 0, product_id: '' }],
        province: 'QC',
        notes: ''
      });
      fetchData();
    } catch (error) {
      alert('Erreur lors de la création de la facture');
    }
  };

  const addItem = () => {
    setFormData(prev => ({
      ...prev,
      items: [...prev.items, { description: '', quantity: 1, unit_price: 0, product_id: '' }]
    }));
  };

  const updateItem = (index, field, value) => {
    const newItems = [...formData.items];
    newItems[index] = { ...newItems[index], [field]: value };
    
    // Auto-fill from product if product selected
    if (field === 'product_id' && value) {
      const product = products.find(p => p.id === value);
      if (product) {
        newItems[index].description = product.name;
        newItems[index].unit_price = product.unit_price;
      }
    }
    
    setFormData(prev => ({ ...prev, items: newItems }));
  };

  const removeItem = (index) => {
    if (formData.items.length > 1) {
      setFormData(prev => ({
        ...prev,
        items: prev.items.filter((_, i) => i !== index)
      }));
    }
  };

  const getClientName = (clientId) => {
    const client = clients.find(c => c.id === clientId);
    return client ? client.name : 'Client inconnu';
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('fr-CA', {
      style: 'currency',
      currency: 'CAD'
    }).format(amount || 0);
  };

  if (loading) {
    return <div style={{ padding: '30px' }}>Chargement...</div>;
  }

  return (
    <div style={{ padding: '30px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px' }}>
        <h2 style={{ margin: 0, color: '#333' }}>📄 Factures ({invoices.length})</h2>
        <button
          onClick={() => setShowForm(true)}
          style={{
            background: '#3b82f6',
            color: 'white',
            border: 'none',
            padding: '12px 24px',
            borderRadius: '8px',
            cursor: 'pointer',
            fontWeight: '600'
          }}
        >
          ➕ Nouvelle Facture
        </button>
      </div>

      {/* Invoices List */}
      <div style={{ display: 'grid', gap: '15px' }}>
        {invoices.map(invoice => (
          <div key={invoice.id} style={{
            background: 'white',
            border: '1px solid #e2e8f0',
            padding: '20px',
            borderRadius: '10px',
            boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}>
            <div>
              <h3 style={{ margin: '0 0 8px 0', color: '#333' }}>
                {invoice.invoice_number}
              </h3>
              <p style={{ margin: '4px 0', color: '#666', fontSize: '14px' }}>
                Client: {getClientName(invoice.client_id)}
              </p>
              <p style={{ margin: '4px 0', color: '#666', fontSize: '14px' }}>
                Échéance: {new Date(invoice.due_date).toLocaleDateString('fr-CA')}
              </p>
            </div>
            
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#333' }}>
                {formatCurrency(invoice.total)}
              </div>
              <span style={{
                background: invoice.status === 'paid' ? '#dcfce7' : invoice.status === 'sent' ? '#fef3c7' : '#f3f4f6',
                color: invoice.status === 'paid' ? '#166534' : invoice.status === 'sent' ? '#92400e' : '#374151',
                padding: '4px 8px',
                borderRadius: '4px',
                fontSize: '12px',
                fontWeight: '500'
              }}>
                {invoice.status === 'paid' ? '✅ Payée' : 
                 invoice.status === 'sent' ? '📤 Envoyée' : 
                 '📝 Brouillon'}
              </span>
            </div>
          </div>
        ))}
      </div>

      {invoices.length === 0 && (
        <div style={{
          background: 'white',
          border: '2px dashed #e2e8f0',
          borderRadius: '12px',
          padding: '40px',
          textAlign: 'center',
          color: '#6b7280'
        }}>
          <div style={{ fontSize: '48px', marginBottom: '15px' }}>📄</div>
          <h3 style={{ margin: '0 0 10px 0' }}>Aucune facture</h3>
          <p style={{ margin: 0 }}>Créez votre première facture pour commencer</p>
        </div>
      )}

      {/* Invoice Form Modal */}
      {showForm && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.6)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            background: 'white',
            padding: '30px',
            borderRadius: '12px',
            width: '95%',
            maxWidth: '800px',
            maxHeight: '90vh',
            overflow: 'auto'
          }}>
            <h3 style={{ marginTop: 0, marginBottom: '25px' }}>📄 Nouvelle Facture</h3>
            
            <form onSubmit={handleSubmit}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '20px', marginBottom: '25px' }}>
                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Client *</label>
                  <select
                    value={formData.client_id}
                    onChange={(e) => setFormData(prev => ({ ...prev, client_id: e.target.value }))}
                    required
                    style={{
                      width: '100%',
                      padding: '10px',
                      border: '1px solid #ddd',
                      borderRadius: '6px',
                      fontSize: '14px',
                      boxSizing: 'border-box'
                    }}
                  >
                    <option value="">Sélectionner un client</option>
                    {clients.map(client => (
                      <option key={client.id} value={client.id}>
                        {client.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Date d'échéance *</label>
                  <input
                    type="date"
                    value={formData.due_date}
                    onChange={(e) => setFormData(prev => ({ ...prev, due_date: e.target.value }))}
                    required
                    style={{
                      width: '100%',
                      padding: '10px',
                      border: '1px solid #ddd',
                      borderRadius: '6px',
                      boxSizing: 'border-box'
                    }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Province</label>
                  <select
                    value={formData.province}
                    onChange={(e) => setFormData(prev => ({ ...prev, province: e.target.value }))}
                    style={{
                      width: '100%',
                      padding: '10px',
                      border: '1px solid #ddd',
                      borderRadius: '6px',
                      boxSizing: 'border-box'
                    }}
                  >
                    <option value="QC">Québec (TPS 5% + TVQ 9.975%)</option>
                    <option value="ON">Ontario (HST 13%)</option>
                  </select>
                </div>
              </div>

              {/* Items */}
              <div style={{ marginBottom: '25px' }}>
                <label style={{ display: 'block', marginBottom: '10px', fontWeight: '600' }}>Articles et Services</label>
                
                {formData.items.map((item, index) => (
                  <div key={index} style={{
                    display: 'grid',
                    gridTemplateColumns: '2fr 1fr 1fr 1fr auto',
                    gap: '10px',
                    marginBottom: '10px',
                    padding: '15px',
                    background: '#f8fafc',
                    borderRadius: '8px',
                    alignItems: 'end'
                  }}>
                    <div>
                      <label style={{ fontSize: '12px', color: '#6b7280' }}>Description</label>
                      <input
                        type="text"
                        value={item.description}
                        onChange={(e) => updateItem(index, 'description', e.target.value)}
                        placeholder="Description du service/produit"
                        style={{
                          width: '100%',
                          padding: '8px',
                          border: '1px solid #ddd',
                          borderRadius: '4px',
                          boxSizing: 'border-box'
                        }}
                      />
                      <select
                        value={item.product_id || ''}
                        onChange={(e) => updateItem(index, 'product_id', e.target.value)}
                        style={{
                          width: '100%',
                          padding: '6px',
                          border: '1px solid #ddd',
                          borderRadius: '4px',
                          fontSize: '12px',
                          marginTop: '5px',
                          boxSizing: 'border-box'
                        }}
                      >
                        <option value="">Ou choisir un produit</option>
                        {products.map(product => (
                          <option key={product.id} value={product.id}>
                            {product.name} - {formatCurrency(product.unit_price)}
                          </option>
                        ))}
                      </select>
                    </div>
                    
                    <div>
                      <label style={{ fontSize: '12px', color: '#6b7280' }}>Quantité</label>
                      <input
                        type="number"
                        step="0.01"
                        value={item.quantity}
                        onChange={(e) => updateItem(index, 'quantity', parseFloat(e.target.value) || 0)}
                        style={{
                          width: '100%',
                          padding: '8px',
                          border: '1px solid #ddd',
                          borderRadius: '4px',
                          textAlign: 'center',
                          boxSizing: 'border-box'
                        }}
                      />
                    </div>
                    
                    <div>
                      <label style={{ fontSize: '12px', color: '#6b7280' }}>Prix unitaire</label>
                      <input
                        type="number"
                        step="0.01"
                        value={item.unit_price}
                        onChange={(e) => updateItem(index, 'unit_price', parseFloat(e.target.value) || 0)}
                        style={{
                          width: '100%',
                          padding: '8px',
                          border: '1px solid #ddd',
                          borderRadius: '4px',
                          textAlign: 'center',
                          boxSizing: 'border-box'
                        }}
                      />
                    </div>
                    
                    <div>
                      <label style={{ fontSize: '12px', color: '#6b7280' }}>Total</label>
                      <div style={{
                        padding: '8px',
                        background: '#e5e7eb',
                        borderRadius: '4px',
                        textAlign: 'center',
                        fontWeight: '600'
                      }}>
                        {formatCurrency(item.quantity * item.unit_price)}
                      </div>
                    </div>
                    
                    <div>
                      <button
                        type="button"
                        onClick={() => removeItem(index)}
                        style={{
                          background: '#ef4444',
                          color: 'white',
                          border: 'none',
                          padding: '8px',
                          borderRadius: '4px',
                          cursor: 'pointer'
                        }}
                      >
                        🗑️
                      </button>
                    </div>
                  </div>
                ))}
                
                <button
                  type="button"
                  onClick={addItem}
                  style={{
                    background: '#10b981',
                    color: 'white',
                    border: 'none',
                    padding: '10px 20px',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    marginTop: '10px'
                  }}
                >
                  ➕ Ajouter un article
                </button>
              </div>

              <div style={{ marginBottom: '25px' }}>
                <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Notes</label>
                <textarea
                  value={formData.notes}
                  onChange={(e) => setFormData(prev => ({ ...prev, notes: e.target.value }))}
                  rows={3}
                  placeholder="Notes additionnelles..."
                  style={{
                    width: '100%',
                    padding: '10px',
                    border: '1px solid #ddd',
                    borderRadius: '6px',
                    resize: 'vertical',
                    boxSizing: 'border-box'
                  }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  style={{
                    background: '#6b7280',
                    color: 'white',
                    border: 'none',
                    padding: '10px 20px',
                    borderRadius: '6px',
                    cursor: 'pointer'
                  }}
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  style={{
                    background: '#3b82f6',
                    color: 'white',
                    border: 'none',
                    padding: '10px 20px',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontWeight: '600'
                  }}
                >
                  💾 Créer la facture
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default InvoicesPage;