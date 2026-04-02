import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { BACKEND_URL, formatCurrency } from '../config';

const STATUS_CONFIG = {
  draft:   { label: 'Brouillon', bg: '#f3f4f6', color: '#374151', icon: '✎' },
  sent:    { label: 'Envoyée',   bg: '#dbeafe', color: '#1e40af', icon: '📨' },
  paid:    { label: 'Payée',     bg: '#dcfce7', color: '#166534', icon: '✓' },
  overdue: { label: 'En retard', bg: '#fef2f2', color: '#991b1b', icon: '!' },
};

const InvoicesPage = () => {
  const [invoices, setInvoices] = useState([]);
  const [clients, setClients] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [showEmailModal, setShowEmailModal] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [sortBy, setSortBy] = useState('date_desc');
  const [emailData, setEmailData] = useState({ to_email: '', subject: '', message: '' });
  const [sending, setSending] = useState(false);

  const defaultForm = () => ({
    client_id: '', due_date: new Date(Date.now() + 30*24*60*60*1000).toISOString().split('T')[0],
    items: [{ description: '', quantity: 1, unit_price: 0 }], province: 'QC', notes: ''
  });
  const [formData, setFormData] = useState(defaultForm());

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    try {
      const [inv, c, p] = await Promise.all([
        axios.get(`${BACKEND_URL}/api/invoices`),
        axios.get(`${BACKEND_URL}/api/clients`),
        axios.get(`${BACKEND_URL}/api/products`)
      ]);
      setInvoices(inv.data); setClients(c.data); setProducts(p.data);
    } catch { setError('Erreur lors du chargement'); }
    finally { setLoading(false); }
  };

  const filteredInvoices = useMemo(() => {
    let list = [...invoices];
    if (filterStatus !== 'all') list = list.filter(i => i.status === filterStatus);
    list.sort((a, b) => {
      if (sortBy === 'date_desc') return new Date(b.created_at) - new Date(a.created_at);
      if (sortBy === 'date_asc') return new Date(a.created_at) - new Date(b.created_at);
      if (sortBy === 'total_desc') return (b.total || 0) - (a.total || 0);
      if (sortBy === 'total_asc') return (a.total || 0) - (b.total || 0);
      return 0;
    });
    return list;
  }, [invoices, filterStatus, sortBy]);

  const getClientName = (id) => clients.find(c => c.id === id)?.name || 'Client inconnu';

  const addProductToItems = (product) => {
    setFormData(prev => ({
      ...prev,
      items: [...prev.items, { description: product.name + (product.description ? ` - ${product.description}` : ''), quantity: 1, unit_price: product.unit_price }]
    }));
  };

  const updateItem = (i, field, value) => {
    setFormData(prev => {
      const items = [...prev.items];
      items[i] = { ...items[i], [field]: value };
      return { ...prev, items };
    });
  };

  const removeItem = (i) => {
    if (formData.items.length > 1) setFormData(prev => ({ ...prev, items: prev.items.filter((_, idx) => idx !== i) }));
  };

  const addBlankItem = () => setFormData(prev => ({ ...prev, items: [...prev.items, { description: '', quantity: 1, unit_price: 0 }] }));

  const formSubtotal = formData.items.reduce((s, it) => s + (it.quantity * it.unit_price), 0);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(''); setSuccess('');
    try {
      await axios.post(`${BACKEND_URL}/api/invoices`, {
        ...formData,
        items: formData.items.map(it => ({ ...it, total: it.quantity * it.unit_price }))
      });
      setSuccess('Facture créée avec succès');
      setShowForm(false);
      setFormData(defaultForm());
      fetchData();
    } catch { setError('Erreur lors de la création'); }
  };

  const handleStatusChange = async (id, status) => {
    try {
      await axios.put(`${BACKEND_URL}/api/invoices/${id}/status`, { status });
      setSuccess(`Statut mis à jour: ${STATUS_CONFIG[status]?.label}`);
      fetchData();
    } catch { setError('Erreur mise à jour du statut'); }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Supprimer cette facture ?')) return;
    try {
      await axios.delete(`${BACKEND_URL}/api/invoices/${id}`);
      setSuccess('Facture supprimée');
      fetchData();
    } catch { setError('Erreur suppression'); }
  };

  const handleDownloadPdf = async (id, invNum) => {
    try {
      const res = await axios.get(`${BACKEND_URL}/api/invoices/${id}/pdf`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a'); a.href = url; a.download = `facture_${invNum}.pdf`;
      document.body.appendChild(a); a.click(); a.remove(); window.URL.revokeObjectURL(url);
    } catch { setError('Erreur téléchargement PDF'); }
  };

  const openEmailModal = (invoice) => {
    const client = clients.find(c => c.id === invoice.client_id);
    setEmailData({
      to_email: client?.email || '',
      subject: `Facture ${invoice.invoice_number}`,
      message: `Bonjour,\n\nVeuillez trouver ci-joint la facture ${invoice.invoice_number}.\n\nCordialement`
    });
    setShowEmailModal(invoice);
  };

  const handleSendEmail = async () => {
    if (!emailData.to_email) { setError('Adresse email requise'); return; }
    setSending(true);
    try {
      await axios.post(`${BACKEND_URL}/api/invoices/${showEmailModal.id}/send`, emailData);
      setSuccess(`Facture envoyée à ${emailData.to_email}`);
      setShowEmailModal(null);
      fetchData();
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur envoi email');
    } finally { setSending(false); }
  };

  const inputStyle = { width: '100%', padding: '10px 12px', border: '1px solid #d1d5db', borderRadius: '8px', fontSize: '14px', boxSizing: 'border-box', outline: 'none', transition: 'border 0.2s' };
  const labelStyle = { display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '13px', color: '#374151' };
  const btnPrimary = { background: 'linear-gradient(135deg, #00A08C, #008F7A)', color: '#fff', border: 'none', padding: '10px 20px', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '14px' };
  const btnSecondary = { background: '#f3f4f6', color: '#374151', border: '1px solid #d1d5db', padding: '10px 20px', borderRadius: '8px', cursor: 'pointer', fontWeight: '500', fontSize: '14px' };

  return (
    <div data-testid="invoices-page">
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '28px', fontWeight: '800', color: '#1f2937', margin: 0 }}>Factures</h1>
          <p style={{ color: '#6b7280', margin: '4px 0 0', fontSize: '14px' }}>Créez et gérez vos factures clients</p>
        </div>
        <button onClick={() => { setFormData(defaultForm()); setShowForm(true); }} data-testid="add-invoice-btn" style={btnPrimary}>
          + Nouvelle Facture
        </button>
      </div>

      {/* Messages */}
      {error && <div data-testid="invoice-error" style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#b91c1c', padding: '12px 16px', borderRadius: '8px', marginBottom: '16px', fontSize: '14px' }} onClick={() => setError('')}>{error}</div>}
      {success && <div data-testid="invoice-success" style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', color: '#166534', padding: '12px 16px', borderRadius: '8px', marginBottom: '16px', fontSize: '14px' }} onClick={() => setSuccess('')}>{success}</div>}

      {/* Filters */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '20px', flexWrap: 'wrap', alignItems: 'center' }}>
        <select data-testid="filter-status" value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
          style={{ ...inputStyle, width: 'auto', minWidth: '160px' }}>
          <option value="all">Tous les statuts</option>
          {Object.entries(STATUS_CONFIG).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
        <select data-testid="sort-invoices" value={sortBy} onChange={e => setSortBy(e.target.value)}
          style={{ ...inputStyle, width: 'auto', minWidth: '160px' }}>
          <option value="date_desc">Plus récent</option>
          <option value="date_asc">Plus ancien</option>
          <option value="total_desc">Montant décroissant</option>
          <option value="total_asc">Montant croissant</option>
        </select>
        <span style={{ color: '#6b7280', fontSize: '13px' }}>{filteredInvoices.length} facture(s)</span>
      </div>

      {/* List */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px', color: '#6b7280' }}>Chargement...</div>
      ) : filteredInvoices.length === 0 ? (
        <div style={{ background: '#fff', border: '2px dashed #d1d5db', borderRadius: '12px', padding: '48px', textAlign: 'center' }}>
          <h3 style={{ fontSize: '20px', fontWeight: '700', color: '#374151', margin: '0 0 8px' }}>Aucune facture</h3>
          <p style={{ color: '#6b7280', margin: '0 0 16px' }}>Créez votre première facture pour commencer</p>
          <button onClick={() => { setFormData(defaultForm()); setShowForm(true); }} style={btnPrimary}>Créer une facture</button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {filteredInvoices.map(inv => {
            const st = STATUS_CONFIG[inv.status] || STATUS_CONFIG.draft;
            return (
              <div key={inv.id} data-testid={`invoice-card-${inv.id}`} style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '12px', padding: '20px', transition: 'box-shadow 0.2s' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
                  {/* Left */}
                  <div style={{ flex: '1', minWidth: '200px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
                      <span style={{ fontWeight: '700', fontSize: '16px', color: '#1f2937' }}>{inv.invoice_number}</span>
                      <span data-testid={`invoice-status-${inv.id}`} style={{ background: st.bg, color: st.color, padding: '3px 10px', borderRadius: '20px', fontSize: '12px', fontWeight: '600' }}>
                        {st.icon} {st.label}
                      </span>
                    </div>
                    <p style={{ margin: '2px 0', color: '#6b7280', fontSize: '14px' }}>Client: <strong>{getClientName(inv.client_id)}</strong></p>
                    <p style={{ margin: '2px 0', color: '#9ca3af', fontSize: '13px' }}>
                      Échéance: {inv.due_date ? new Date(inv.due_date).toLocaleDateString('fr-CA') : '—'}
                    </p>
                    {inv.items && inv.items.length > 0 && (
                      <p style={{ margin: '4px 0 0', color: '#9ca3af', fontSize: '12px' }}>
                        {inv.items.length} article(s) — Sous-total: {formatCurrency(inv.subtotal)}
                      </p>
                    )}
                  </div>

                  {/* Right */}
                  <div style={{ textAlign: 'right', minWidth: '140px' }}>
                    <div style={{ fontSize: '22px', fontWeight: '800', color: '#008F7A', marginBottom: '8px' }}>{formatCurrency(inv.total)}</div>

                    {/* Status dropdown */}
                    <select data-testid={`invoice-status-select-${inv.id}`} value={inv.status || 'draft'}
                      onChange={e => handleStatusChange(inv.id, e.target.value)}
                      style={{ ...inputStyle, width: 'auto', fontSize: '12px', padding: '4px 8px', marginBottom: '8px' }}>
                      {Object.entries(STATUS_CONFIG).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
                    </select>

                    {/* Action buttons */}
                    <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end', flexWrap: 'wrap' }}>
                      <button data-testid={`download-pdf-inv-${inv.id}`} onClick={() => handleDownloadPdf(inv.id, inv.invoice_number)}
                        title="Télécharger PDF"
                        style={{ background: '#eff6ff', color: '#1d4ed8', border: 'none', padding: '6px 10px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', fontWeight: '600' }}>
                        PDF
                      </button>
                      <button data-testid={`send-email-inv-${inv.id}`} onClick={() => openEmailModal(inv)}
                        title="Envoyer par email"
                        style={{ background: '#f0fdf4', color: '#166534', border: 'none', padding: '6px 10px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', fontWeight: '600' }}>
                        Email
                      </button>
                      <button data-testid={`delete-invoice-${inv.id}`} onClick={() => handleDelete(inv.id)}
                        title="Supprimer"
                        style={{ background: '#fef2f2', color: '#dc2626', border: 'none', padding: '6px 10px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', fontWeight: '600' }}>
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

      {/* ═══ New Invoice Form Modal ═══ */}
      {showForm && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '20px' }}>
          <div style={{ background: '#fff', borderRadius: '16px', width: '95%', maxWidth: '820px', maxHeight: '92vh', overflow: 'auto', boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25)' }}>
            <div style={{ padding: '24px 28px', borderBottom: '1px solid #e5e7eb' }}>
              <h3 style={{ margin: 0, fontSize: '20px', fontWeight: '700', color: '#1f2937' }}>Nouvelle Facture</h3>
            </div>
            <form onSubmit={handleSubmit} style={{ padding: '24px 28px' }}>
              {/* Row 1: Client, Date, Province */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '16px', marginBottom: '20px' }}>
                <div>
                  <label style={labelStyle}>Client *</label>
                  <select data-testid="invoice-client-select" value={formData.client_id}
                    onChange={e => setFormData(prev => ({ ...prev, client_id: e.target.value }))} required style={inputStyle}>
                    <option value="">Sélectionner un client</option>
                    {clients.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </div>
                <div>
                  <label style={labelStyle}>Échéance *</label>
                  <input type="date" value={formData.due_date}
                    onChange={e => setFormData(prev => ({ ...prev, due_date: e.target.value }))} required style={inputStyle} />
                </div>
                <div>
                  <label style={labelStyle}>Province</label>
                  <select data-testid="invoice-province-select" value={formData.province}
                    onChange={e => setFormData(prev => ({ ...prev, province: e.target.value }))} style={inputStyle}>
                    <option value="QC">Québec (TPS 5% + TVQ 9.975%)</option>
                    <option value="ON">Ontario (TVH 13%)</option>
                  </select>
                </div>
              </div>

              {/* Product catalog quick-add */}
              {products.length > 0 && (
                <div style={{ marginBottom: '20px' }}>
                  <label style={labelStyle}>Ajouter un produit du catalogue</label>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    {products.map(p => (
                      <button type="button" key={p.id} data-testid={`add-product-inv-${p.id}`}
                        onClick={() => addProductToItems(p)}
                        style={{ background: '#f0fdfa', border: '1px solid #99f6e4', color: '#0f766e', padding: '6px 14px', borderRadius: '20px', cursor: 'pointer', fontSize: '13px', fontWeight: '500', transition: 'all 0.15s' }}>
                        + {p.name} ({formatCurrency(p.unit_price)})
                      </button>
                    ))}
                  </div>
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
                  {formData.items.map((item, i) => (
                    <div key={i} style={{ display: 'grid', gridTemplateColumns: '2fr 80px 110px 110px 40px', gap: '8px', padding: '10px 12px', background: i % 2 === 0 ? '#fff' : '#f9fafb', alignItems: 'center' }}>
                      <input data-testid={`inv-item-desc-${i}`} type="text" value={item.description}
                        onChange={e => updateItem(i, 'description', e.target.value)} required placeholder="Description"
                        style={{ ...inputStyle, padding: '8px' }} />
                      <input data-testid={`inv-item-qty-${i}`} type="number" step="0.01" min="0.01" value={item.quantity}
                        onChange={e => updateItem(i, 'quantity', parseFloat(e.target.value) || 0)}
                        style={{ ...inputStyle, padding: '8px', textAlign: 'center' }} />
                      <input data-testid={`inv-item-price-${i}`} type="number" step="0.01" min="0" value={item.unit_price}
                        onChange={e => updateItem(i, 'unit_price', parseFloat(e.target.value) || 0)}
                        style={{ ...inputStyle, padding: '8px', textAlign: 'center' }} />
                      <div style={{ textAlign: 'center', fontWeight: '600', fontSize: '14px', color: '#008F7A' }}>
                        {formatCurrency(item.quantity * item.unit_price)}
                      </div>
                      <button type="button" onClick={() => removeItem(i)} disabled={formData.items.length <= 1}
                        style={{ background: 'none', border: 'none', color: formData.items.length <= 1 ? '#d1d5db' : '#ef4444', cursor: formData.items.length <= 1 ? 'default' : 'pointer', fontSize: '18px', padding: '0' }}>
                        ×
                      </button>
                    </div>
                  ))}
                </div>
                <button type="button" data-testid="add-blank-item-inv" onClick={addBlankItem}
                  style={{ marginTop: '8px', background: 'none', border: '1px dashed #00A08C', color: '#00A08C', padding: '8px 16px', borderRadius: '8px', cursor: 'pointer', fontSize: '13px', fontWeight: '600' }}>
                  + Ajouter un article
                </button>
              </div>

              {/* Subtotal preview */}
              <div style={{ background: '#f8fafb', border: '1px solid #e5e7eb', borderRadius: '10px', padding: '14px 16px', marginBottom: '20px', textAlign: 'right' }}>
                <span style={{ color: '#6b7280', fontSize: '14px' }}>Sous-total: </span>
                <span style={{ fontWeight: '700', fontSize: '18px', color: '#008F7A' }}>{formatCurrency(formSubtotal)}</span>
              </div>

              {/* Notes */}
              <div style={{ marginBottom: '24px' }}>
                <label style={labelStyle}>Notes / Commentaires</label>
                <textarea data-testid="invoice-notes" value={formData.notes}
                  onChange={e => setFormData(prev => ({ ...prev, notes: e.target.value }))}
                  rows={3} placeholder="Instructions de paiement, conditions..."
                  style={{ ...inputStyle, resize: 'vertical' }} />
              </div>

              {/* Actions */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', borderTop: '1px solid #e5e7eb', paddingTop: '20px' }}>
                <button type="button" onClick={() => setShowForm(false)} style={btnSecondary}>Annuler</button>
                <button type="submit" data-testid="save-invoice-btn" style={btnPrimary}>Créer la facture</button>
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
              <p style={{ margin: '4px 0 0', color: '#6b7280', fontSize: '13px' }}>Facture {showEmailModal.invoice_number}</p>
            </div>
            <div style={{ padding: '20px 24px' }}>
              <div style={{ marginBottom: '14px' }}>
                <label style={labelStyle}>Destinataire *</label>
                <input data-testid="email-to-inv" type="email" value={emailData.to_email}
                  onChange={e => setEmailData(prev => ({ ...prev, to_email: e.target.value }))}
                  placeholder="email@client.com" required style={inputStyle} />
              </div>
              <div style={{ marginBottom: '14px' }}>
                <label style={labelStyle}>Objet</label>
                <input data-testid="email-subject-inv" type="text" value={emailData.subject}
                  onChange={e => setEmailData(prev => ({ ...prev, subject: e.target.value }))} style={inputStyle} />
              </div>
              <div style={{ marginBottom: '14px' }}>
                <label style={labelStyle}>Message</label>
                <textarea data-testid="email-message-inv" value={emailData.message}
                  onChange={e => setEmailData(prev => ({ ...prev, message: e.target.value }))}
                  rows={4} style={{ ...inputStyle, resize: 'vertical' }} />
              </div>
              <p style={{ color: '#6b7280', fontSize: '12px', margin: '0 0 16px' }}>Le PDF de la facture sera joint automatiquement.</p>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button onClick={() => setShowEmailModal(null)} style={btnSecondary}>Annuler</button>
                <button data-testid="send-email-inv-btn" onClick={handleSendEmail} disabled={sending}
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

export default InvoicesPage;
