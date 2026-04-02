import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { BACKEND_URL, formatCurrency } from '../config';

const STATUS_CONFIG = {
  pending:   { label: 'En attente', bg: '#fef3c7', color: '#92400e', icon: '⏳' },
  sent:      { label: 'Envoyée',    bg: '#dbeafe', color: '#1e40af', icon: '📨' },
  accepted:  { label: 'Acceptée',   bg: '#dcfce7', color: '#166534', icon: '✓' },
  refused:   { label: 'Refusée',    bg: '#fef2f2', color: '#991b1b', icon: '✗' },
  converted: { label: 'Convertie',  bg: '#f3e8ff', color: '#6b21a8', icon: '↗' },
};

const QuotesPage = () => {
  const [quotes, setQuotes] = useState([]);
  const [clients, setClients] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingQuote, setEditingQuote] = useState(null);
  const [showEmailModal, setShowEmailModal] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [sortBy, setSortBy] = useState('date_desc');
  const [emailData, setEmailData] = useState({ to_email: '', subject: '', message: '' });
  const [sending, setSending] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState('');

  const defaultForm = () => ({
    client_id: '', quote_number: '', valid_until: new Date(Date.now() + 30*24*60*60*1000).toISOString().split('T')[0],
    items: [], province: 'QC', notes: ''
  });
  const [formData, setFormData] = useState(defaultForm());

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    try {
      const [q, c, p] = await Promise.all([
        axios.get(`${BACKEND_URL}/api/quotes`),
        axios.get(`${BACKEND_URL}/api/clients`),
        axios.get(`${BACKEND_URL}/api/products`)
      ]);
      setQuotes(q.data); setClients(c.data); setProducts(p.data);
    } catch { setError('Erreur lors du chargement'); }
    finally { setLoading(false); }
  };

  const filteredQuotes = useMemo(() => {
    let list = [...quotes];
    if (filterStatus !== 'all') list = list.filter(q => q.status === filterStatus);
    list.sort((a, b) => {
      if (sortBy === 'date_desc') return new Date(b.created_at) - new Date(a.created_at);
      if (sortBy === 'date_asc') return new Date(a.created_at) - new Date(b.created_at);
      if (sortBy === 'total_desc') return (b.total || 0) - (a.total || 0);
      if (sortBy === 'total_asc') return (a.total || 0) - (b.total || 0);
      return 0;
    });
    return list;
  }, [quotes, filterStatus, sortBy]);

  const getClientName = (id) => clients.find(c => c.id === id)?.name || 'Client inconnu';

  const handleProductSelect = (productId) => {
    if (!productId) return;
    const product = products.find(p => p.id === productId);
    if (!product) return;
    setFormData(prev => ({
      ...prev,
      items: [...prev.items, {
        description: product.name + (product.description ? ` - ${product.description}` : ''),
        quantity: 1,
        unit_price: product.unit_price
      }]
    }));
    setSelectedProduct('');
  };

  const updateItem = (i, field, value) => {
    setFormData(prev => {
      const items = [...prev.items];
      items[i] = { ...items[i], [field]: value };
      return { ...prev, items };
    });
  };

  const removeItem = (i) => {
    setFormData(prev => ({ ...prev, items: prev.items.filter((_, idx) => idx !== i) }));
  };

  const addBlankItem = () => setFormData(prev => ({ ...prev, items: [...prev.items, { description: '', quantity: 1, unit_price: 0 }] }));

  const formSubtotal = formData.items.reduce((s, it) => s + (it.quantity * it.unit_price), 0);

  const openNewForm = () => {
    setEditingQuote(null);
    setFormData(defaultForm());
    setSelectedProduct('');
    setShowForm(true);
  };

  const openEditForm = (quote) => {
    setEditingQuote(quote);
    setFormData({
      client_id: quote.client_id || '',
      quote_number: quote.quote_number || '',
      valid_until: quote.valid_until ? quote.valid_until.substring(0, 10) : '',
      items: quote.items && quote.items.length > 0 ? quote.items.map(it => ({
        description: it.description || '',
        quantity: it.quantity || 1,
        unit_price: it.unit_price || 0
      })) : [],
      province: quote.province || 'QC',
      notes: quote.notes || ''
    });
    setSelectedProduct('');
    setShowForm(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(''); setSuccess('');
    const payload = {
      ...formData,
      items: formData.items.map(it => ({ ...it, total: it.quantity * it.unit_price }))
    };
    if (editingQuote && formData.quote_number) {
      payload.quote_number = formData.quote_number;
    }
    try {
      if (editingQuote) {
        await axios.put(`${BACKEND_URL}/api/quotes/${editingQuote.id}`, payload);
        setSuccess('Soumission modifiée avec succès');
      } else {
        await axios.post(`${BACKEND_URL}/api/quotes`, payload);
        setSuccess('Soumission créée avec succès');
      }
      setShowForm(false);
      setEditingQuote(null);
      setFormData(defaultForm());
      fetchData();
    } catch { setError(editingQuote ? 'Erreur lors de la modification' : 'Erreur lors de la création'); }
  };

  const handleStatusChange = async (id, status) => {
    try {
      await axios.put(`${BACKEND_URL}/api/quotes/${id}/status`, { status });
      setSuccess(`Statut mis à jour: ${STATUS_CONFIG[status]?.label}`);
      fetchData();
    } catch { setError('Erreur mise à jour du statut'); }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Supprimer cette soumission ?')) return;
    try {
      await axios.delete(`${BACKEND_URL}/api/quotes/${id}`);
      setSuccess('Soumission supprimée');
      fetchData();
    } catch { setError('Erreur suppression'); }
  };

  const handleDownloadPdf = async (id, quoteNum) => {
    try {
      const res = await axios.get(`${BACKEND_URL}/api/quotes/${id}/pdf`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a'); a.href = url; a.download = `soumission_${quoteNum}.pdf`;
      document.body.appendChild(a); a.click(); a.remove(); window.URL.revokeObjectURL(url);
    } catch { setError('Erreur téléchargement PDF'); }
  };

  const openEmailModal = (quote) => {
    const client = clients.find(c => c.id === quote.client_id);
    setEmailData({
      to_email: client?.email || '',
      subject: `Soumission ${quote.quote_number}`,
      message: `Bonjour,\n\nVeuillez trouver ci-joint la soumission ${quote.quote_number}.\n\nCordialement`
    });
    setShowEmailModal(quote);
  };

  const handleSendEmail = async () => {
    if (!emailData.to_email) { setError('Adresse email requise'); return; }
    setSending(true);
    try {
      await axios.post(`${BACKEND_URL}/api/quotes/${showEmailModal.id}/send`, emailData);
      setSuccess(`Soumission envoyée à ${emailData.to_email}`);
      setShowEmailModal(null);
      fetchData();
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur envoi email');
    } finally { setSending(false); }
  };

  const handleConvert = async (quoteId) => {
    if (!window.confirm('Convertir cette soumission en facture ?')) return;
    try {
      const dueDate = new Date(Date.now() + 30*24*60*60*1000).toISOString().split('T')[0];
      await axios.post(`${BACKEND_URL}/api/quotes/${quoteId}/convert`, { due_date: dueDate });
      setSuccess('Soumission convertie en facture !');
      fetchData();
    } catch { setError('Erreur conversion'); }
  };

  const inputStyle = { width: '100%', padding: '10px 12px', border: '1px solid #d1d5db', borderRadius: '8px', fontSize: '14px', boxSizing: 'border-box', outline: 'none', transition: 'border 0.2s' };
  const labelStyle = { display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '13px', color: '#374151' };
  const btnPrimary = { background: 'linear-gradient(135deg, #47D2A7, #008F7A)', color: '#fff', border: 'none', padding: '10px 20px', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '14px' };
  const btnSecondary = { background: '#f3f4f6', color: '#374151', border: '1px solid #d1d5db', padding: '10px 20px', borderRadius: '8px', cursor: 'pointer', fontWeight: '500', fontSize: '14px' };

  return (
    <div data-testid="quotes-page">
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '28px', fontWeight: '800', color: '#1f2937', margin: 0 }}>Soumissions</h1>
          <p style={{ color: '#6b7280', margin: '4px 0 0', fontSize: '14px' }}>Gérez vos devis et soumissions clients</p>
        </div>
        <button onClick={openNewForm} data-testid="add-quote-btn" style={btnPrimary}>+ Nouvelle Soumission</button>
      </div>

      {error && <div data-testid="quote-error" style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#b91c1c', padding: '12px 16px', borderRadius: '8px', marginBottom: '16px', fontSize: '14px' }} onClick={() => setError('')}>{error}</div>}
      {success && <div data-testid="quote-success" style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', color: '#166534', padding: '12px 16px', borderRadius: '8px', marginBottom: '16px', fontSize: '14px' }} onClick={() => setSuccess('')}>{success}</div>}

      {/* Filters */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '20px', flexWrap: 'wrap', alignItems: 'center' }}>
        <select data-testid="filter-status" value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
          style={{ ...inputStyle, width: 'auto', minWidth: '160px' }}>
          <option value="all">Tous les statuts</option>
          {Object.entries(STATUS_CONFIG).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
        <select data-testid="sort-quotes" value={sortBy} onChange={e => setSortBy(e.target.value)}
          style={{ ...inputStyle, width: 'auto', minWidth: '160px' }}>
          <option value="date_desc">Plus récent</option>
          <option value="date_asc">Plus ancien</option>
          <option value="total_desc">Montant décroissant</option>
          <option value="total_asc">Montant croissant</option>
        </select>
        <span style={{ color: '#6b7280', fontSize: '13px' }}>{filteredQuotes.length} soumission(s)</span>
      </div>

      {/* List */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px', color: '#6b7280' }}>Chargement...</div>
      ) : filteredQuotes.length === 0 ? (
        <div style={{ background: '#fff', border: '2px dashed #d1d5db', borderRadius: '12px', padding: '48px', textAlign: 'center' }}>
          <h3 style={{ fontSize: '20px', fontWeight: '700', color: '#374151', margin: '0 0 8px' }}>Aucune soumission</h3>
          <p style={{ color: '#6b7280', margin: '0 0 16px' }}>Créez votre première soumission pour commencer</p>
          <button onClick={openNewForm} style={btnPrimary}>Créer une soumission</button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {filteredQuotes.map(q => {
            const st = STATUS_CONFIG[q.status] || STATUS_CONFIG.pending;
            return (
              <div key={q.id} data-testid={`quote-card-${q.id}`} style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '12px', padding: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
                  <div style={{ flex: '1', minWidth: '200px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
                      <span style={{ fontWeight: '700', fontSize: '16px', color: '#1f2937' }}>{q.quote_number}</span>
                      <span data-testid={`quote-status-${q.id}`} style={{ background: st.bg, color: st.color, padding: '3px 10px', borderRadius: '20px', fontSize: '12px', fontWeight: '600' }}>
                        {st.icon} {st.label}
                      </span>
                    </div>
                    <p style={{ margin: '2px 0', color: '#6b7280', fontSize: '14px' }}>Client: <strong>{getClientName(q.client_id)}</strong></p>
                    <p style={{ margin: '2px 0', color: '#9ca3af', fontSize: '13px' }}>
                      Valide jusqu'au: {q.valid_until ? new Date(q.valid_until).toLocaleDateString('fr-CA') : '—'}
                    </p>
                    {q.items && q.items.length > 0 && (
                      <p style={{ margin: '4px 0 0', color: '#9ca3af', fontSize: '12px' }}>
                        {q.items.length} article(s) — Sous-total: {formatCurrency(q.subtotal)}
                      </p>
                    )}
                  </div>
                  <div style={{ textAlign: 'right', minWidth: '140px' }}>
                    <div style={{ fontSize: '22px', fontWeight: '800', color: '#008F7A', marginBottom: '8px' }}>{formatCurrency(q.total)}</div>
                    <select data-testid={`quote-status-select-${q.id}`} value={q.status || 'pending'}
                      onChange={e => handleStatusChange(q.id, e.target.value)}
                      style={{ ...inputStyle, width: 'auto', fontSize: '12px', padding: '4px 8px', marginBottom: '8px' }}>
                      {Object.entries(STATUS_CONFIG).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
                    </select>
                    <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end', flexWrap: 'wrap' }}>
                      <button data-testid={`edit-quote-${q.id}`} onClick={() => openEditForm(q)}
                        title="Modifier" style={{ background: '#fef3c7', color: '#92400e', border: 'none', padding: '6px 10px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', fontWeight: '600' }}>
                        Modifier
                      </button>
                      <button data-testid={`download-pdf-${q.id}`} onClick={() => handleDownloadPdf(q.id, q.quote_number)}
                        title="Télécharger PDF" style={{ background: '#eff6ff', color: '#1d4ed8', border: 'none', padding: '6px 10px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', fontWeight: '600' }}>
                        PDF
                      </button>
                      <button data-testid={`send-email-${q.id}`} onClick={() => openEmailModal(q)}
                        title="Envoyer par email" style={{ background: '#f0fdf4', color: '#166534', border: 'none', padding: '6px 10px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', fontWeight: '600' }}>
                        Email
                      </button>
                      {q.status !== 'converted' && (
                        <button data-testid={`convert-quote-${q.id}`} onClick={() => handleConvert(q.id)}
                          title="Convertir en facture" style={{ background: '#f3e8ff', color: '#6b21a8', border: 'none', padding: '6px 10px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', fontWeight: '600' }}>
                          Facture
                        </button>
                      )}
                      <button data-testid={`delete-quote-${q.id}`} onClick={() => handleDelete(q.id)}
                        title="Supprimer" style={{ background: '#fef2f2', color: '#dc2626', border: 'none', padding: '6px 10px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', fontWeight: '600' }}>
                        Suppr.
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ═══ Quote Form Modal (Create / Edit) ═══ */}
      {showForm && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '20px' }}>
          <div style={{ background: '#fff', borderRadius: '16px', width: '95%', maxWidth: '820px', maxHeight: '92vh', overflow: 'auto', boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25)' }}>
            <div style={{ padding: '24px 28px', borderBottom: '1px solid #e5e7eb' }}>
              <h3 style={{ margin: 0, fontSize: '20px', fontWeight: '700', color: '#1f2937' }}>
                {editingQuote ? `Modifier ${editingQuote.quote_number}` : 'Nouvelle Soumission'}
              </h3>
            </div>
            <form onSubmit={handleSubmit} style={{ padding: '24px 28px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
                <div>
                  <label style={labelStyle}>Client *</label>
                  <select data-testid="quote-client-select" value={formData.client_id}
                    onChange={e => setFormData(prev => ({ ...prev, client_id: e.target.value }))} required style={inputStyle}>
                    <option value="">Sélectionner un client</option>
                    {clients.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </div>
                <div>
                  <label style={labelStyle}>Numéro de soumission {editingQuote ? '' : '(auto si vide)'}</label>
                  <input data-testid="quote-number-input" type="text" value={formData.quote_number}
                    onChange={e => setFormData(prev => ({ ...prev, quote_number: e.target.value }))}
                    placeholder={editingQuote ? editingQuote.quote_number : 'Ex: QUO-0001'} style={inputStyle} />
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '20px' }}>
                <div>
                  <label style={labelStyle}>Valide jusqu'au *</label>
                  <input type="date" value={formData.valid_until}
                    onChange={e => setFormData(prev => ({ ...prev, valid_until: e.target.value }))} required style={inputStyle} />
                </div>
                <div>
                  <label style={labelStyle}>Province</label>
                  <select data-testid="quote-province-select" value={formData.province}
                    onChange={e => setFormData(prev => ({ ...prev, province: e.target.value }))} style={inputStyle}>
                    <option value="QC">Québec (TPS 5% + TVQ 9.975%)</option>
                    <option value="ON">Ontario (TVH 13%)</option>
                  </select>
                </div>
              </div>

              {/* Product catalog dropdown */}
              {products.length > 0 && (
                <div style={{ marginBottom: '20px' }}>
                  <label style={labelStyle}>Ajouter un produit du catalogue</label>
                  <select data-testid="quote-product-select" value={selectedProduct}
                    onChange={e => handleProductSelect(e.target.value)}
                    style={inputStyle}>
                    <option value="">-- Sélectionner un produit --</option>
                    {products.map(p => (
                      <option key={p.id} value={p.id}>
                        {p.name}{p.description ? ` - ${p.description}` : ''} ({formatCurrency(p.unit_price)})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Items table */}
              <div style={{ marginBottom: '20px' }}>
                <label style={labelStyle}>Articles et services</label>
                <div style={{ border: '1px solid #e5e7eb', borderRadius: '10px', overflow: 'hidden' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '2fr 80px 110px 110px 40px', gap: '0', background: '#008F7A', color: '#fff', padding: '10px 12px', fontSize: '12px', fontWeight: '600' }}>
                    <span>Description</span><span style={{ textAlign: 'center' }}>Qté</span>
                    <span style={{ textAlign: 'center' }}>Prix unit.</span><span style={{ textAlign: 'center' }}>Total</span><span></span>
                  </div>
                  {formData.items.length === 0 ? (
                    <div style={{ padding: '20px', textAlign: 'center', color: '#9ca3af', fontSize: '14px' }}>
                      Sélectionnez un produit ou ajoutez un article manuellement
                    </div>
                  ) : formData.items.map((item, i) => (
                    <div key={i} style={{ display: 'grid', gridTemplateColumns: '2fr 80px 110px 110px 40px', gap: '8px', padding: '10px 12px', background: i % 2 === 0 ? '#fff' : '#f9fafb', alignItems: 'center' }}>
                      <input data-testid={`item-desc-${i}`} type="text" value={item.description}
                        onChange={e => updateItem(i, 'description', e.target.value)} required placeholder="Description"
                        style={{ ...inputStyle, padding: '8px' }} />
                      <input data-testid={`item-qty-${i}`} type="number" step="0.01" min="0.01" value={item.quantity}
                        onChange={e => updateItem(i, 'quantity', parseFloat(e.target.value) || 0)}
                        style={{ ...inputStyle, padding: '8px', textAlign: 'center' }} />
                      <input data-testid={`item-price-${i}`} type="number" step="0.01" min="0" value={item.unit_price}
                        onChange={e => updateItem(i, 'unit_price', parseFloat(e.target.value) || 0)}
                        style={{ ...inputStyle, padding: '8px', textAlign: 'center' }} />
                      <div style={{ textAlign: 'center', fontWeight: '600', fontSize: '14px', color: '#008F7A' }}>
                        {formatCurrency(item.quantity * item.unit_price)}
                      </div>
                      <button type="button" onClick={() => removeItem(i)}
                        style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: '18px', padding: '0' }}>
                        ×
                      </button>
                    </div>
                  ))}
                </div>
                <button type="button" data-testid="add-blank-item" onClick={addBlankItem}
                  style={{ marginTop: '8px', background: 'none', border: '1px dashed #00A08C', color: '#00A08C', padding: '8px 16px', borderRadius: '8px', cursor: 'pointer', fontSize: '13px', fontWeight: '600' }}>
                  + Ajouter un article
                </button>
              </div>

              <div style={{ background: '#f8fafb', border: '1px solid #e5e7eb', borderRadius: '10px', padding: '14px 16px', marginBottom: '20px', textAlign: 'right' }}>
                <span style={{ color: '#6b7280', fontSize: '14px' }}>Sous-total: </span>
                <span style={{ fontWeight: '700', fontSize: '18px', color: '#008F7A' }}>{formatCurrency(formSubtotal)}</span>
              </div>

              <div style={{ marginBottom: '24px' }}>
                <label style={labelStyle}>Notes / Commentaires</label>
                <textarea data-testid="quote-notes" value={formData.notes}
                  onChange={e => setFormData(prev => ({ ...prev, notes: e.target.value }))}
                  rows={3} placeholder="Instructions spéciales, conditions..."
                  style={{ ...inputStyle, resize: 'vertical' }} />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', borderTop: '1px solid #e5e7eb', paddingTop: '20px' }}>
                <button type="button" onClick={() => { setShowForm(false); setEditingQuote(null); }} style={btnSecondary}>Annuler</button>
                <button type="submit" data-testid="save-quote-btn" style={btnPrimary}>
                  {editingQuote ? 'Sauvegarder les modifications' : 'Créer la soumission'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ═══ Email Modal ═══ */}
      {showEmailModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1100, padding: '20px' }}>
          <div style={{ background: '#fff', borderRadius: '16px', width: '95%', maxWidth: '500px', boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25)' }}>
            <div style={{ padding: '20px 24px', borderBottom: '1px solid #e5e7eb' }}>
              <h3 style={{ margin: 0, fontSize: '18px', fontWeight: '700' }}>Envoyer par email</h3>
              <p style={{ margin: '4px 0 0', color: '#6b7280', fontSize: '13px' }}>Soumission {showEmailModal.quote_number}</p>
            </div>
            <div style={{ padding: '20px 24px' }}>
              <div style={{ marginBottom: '14px' }}>
                <label style={labelStyle}>Destinataire *</label>
                <input data-testid="email-to" type="email" value={emailData.to_email}
                  onChange={e => setEmailData(prev => ({ ...prev, to_email: e.target.value }))}
                  placeholder="email@client.com" required style={inputStyle} />
              </div>
              <div style={{ marginBottom: '14px' }}>
                <label style={labelStyle}>Objet</label>
                <input data-testid="email-subject" type="text" value={emailData.subject}
                  onChange={e => setEmailData(prev => ({ ...prev, subject: e.target.value }))} style={inputStyle} />
              </div>
              <div style={{ marginBottom: '14px' }}>
                <label style={labelStyle}>Message</label>
                <textarea data-testid="email-message" value={emailData.message}
                  onChange={e => setEmailData(prev => ({ ...prev, message: e.target.value }))}
                  rows={4} style={{ ...inputStyle, resize: 'vertical' }} />
              </div>
              <p style={{ color: '#6b7280', fontSize: '12px', margin: '0 0 16px' }}>Le PDF de la soumission sera joint automatiquement.</p>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button onClick={() => setShowEmailModal(null)} style={btnSecondary}>Annuler</button>
                <button data-testid="send-email-btn" onClick={handleSendEmail} disabled={sending}
                  style={{ ...btnPrimary, opacity: sending ? 0.6 : 1 }}>
                  {sending ? 'Envoi...' : 'Envoyer'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default QuotesPage;
