import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import { BACKEND_URL, formatCurrency } from '../config';
import CurrencySelector from '../components/CurrencySelector';

const ExpensesPage = () => {
  const [expenses, setExpenses] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [importData, setImportData] = useState(null);
  const [importRows, setImportRows] = useState([]);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const fileInputRef = useRef(null);
  const receiptInputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [previewReceipt, setPreviewReceipt] = useState(null);
  const [formData, setFormData] = useState({
    employee_id: '', description: '', amount: '', category: '', expense_date: new Date().toISOString().split('T')[0], notes: '', receipt_url: '',
    currency: 'CAD', exchange_rate_to_cad: 1.0
  });

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    try {
      const [expensesRes, employeesRes] = await Promise.all([
        axios.get(`${BACKEND_URL}/api/expenses`),
        axios.get(`${BACKEND_URL}/api/employees`)
      ]);
      setExpenses(expensesRes.data); setEmployees(employeesRes.data);
    } catch { setError('Erreur lors du chargement'); }
    finally { setLoading(false); }
  };

  const resetForm = () => {
    setFormData({ employee_id: '', description: '', amount: '', category: '', expense_date: new Date().toISOString().split('T')[0], notes: '', receipt_url: '', currency: 'CAD', exchange_rate_to_cad: 1.0 });
    setPreviewReceipt(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault(); setError(''); setSuccess('');
    try {
      await axios.post(`${BACKEND_URL}/api/expenses`, { ...formData, amount: parseFloat(formData.amount) });
      setSuccess('Depense creee avec succes'); setShowForm(false);
      resetForm();
      fetchData();
    } catch { setError('Erreur lors de la creation'); }
  };

  const updateStatus = async (id, status) => {
    try {
      await axios.put(`${BACKEND_URL}/api/expenses/${id}/status`, { status });
      setSuccess(`Depense ${status === 'approved' ? 'approuvee' : 'rejetee'}`);
      fetchData();
    } catch { setError('Erreur'); }
  };

  const handleDelete = async (id) => {
    if (window.confirm('Supprimer cette depense ?')) {
      try { await axios.delete(`${BACKEND_URL}/api/expenses/${id}`); setSuccess('Depense supprimee'); fetchData(); }
      catch { setError('Erreur suppression'); }
    }
  };

  const getEmployeeName = (id) => {
    if (!id) return null;
    return employees.find(e => e.id === id)?.name || null;
  };

  const statusColors = {
    pending: { bg: '#fef3c7', color: '#92400e', label: 'En attente' },
    approved: { bg: '#dcfce7', color: '#166534', label: 'Approuvee' },
    rejected: { bg: '#fef2f2', color: '#b91c1c', label: 'Rejetee' }
  };

  // ─── Receipt Upload ───
  const handleReceiptUpload = useCallback(async (file) => {
    if (!file) return;
    const allowed = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'application/pdf'];
    if (!allowed.includes(file.type)) {
      setError('Type de fichier non supporte. Utilisez JPG, PNG, GIF, WebP ou PDF.');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setError('Fichier trop volumineux (max 5 Mo)');
      return;
    }
    setUploading(true); setError('');
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await axios.post(`${BACKEND_URL}/api/upload`, form, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      const receiptUrl = `/api/files/${res.data.file_id}`;
      setFormData(prev => ({ ...prev, receipt_url: receiptUrl }));
      setPreviewReceipt({ name: file.name, type: file.type, url: receiptUrl });
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur upload du recu');
    } finally {
      setUploading(false);
    }
  }, []);

  const handleDrag = useCallback((e) => {
    e.preventDefault(); e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true);
    else if (e.type === 'dragleave') setDragActive(false);
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault(); e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleReceiptUpload(e.dataTransfer.files[0]);
    }
  }, [handleReceiptUpload]);

  const handleReceiptFileSelect = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleReceiptUpload(e.target.files[0]);
    }
    if (receiptInputRef.current) receiptInputRef.current.value = '';
  };

  const removeReceipt = () => {
    setFormData(prev => ({ ...prev, receipt_url: '' }));
    setPreviewReceipt(null);
  };

  // ─── CSV Import Logic ───
  const handleFileSelect = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setError(''); setSuccess('');
    const form = new FormData();
    form.append('file', file);
    try {
      const res = await axios.post(`${BACKEND_URL}/api/expenses/import-csv`, form, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setImportData(res.data);
      setImportRows(res.data.preview.map(r => ({ ...r, _include: true })));
      setShowImport(true);
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur lecture CSV');
    }
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const toggleRow = (i) => {
    setImportRows(prev => prev.map((r, idx) => idx === i ? { ...r, _include: !r._include } : r));
  };

  const updateImportRow = (i, field, value) => {
    setImportRows(prev => prev.map((r, idx) => idx === i ? { ...r, [field]: value } : r));
  };

  const handleImportConfirm = async () => {
    const rows = importRows.filter(r => r._include).map(({ _include, ...rest }) => rest);
    if (rows.length === 0) { setError('Aucune ligne selectionnee'); return; }
    setImporting(true);
    try {
      const res = await axios.post(`${BACKEND_URL}/api/expenses/import-confirm`, { rows });
      setSuccess(res.data.message);
      setShowImport(false); setImportData(null); setImportRows([]);
      fetchData();
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur import');
    } finally { setImporting(false); }
  };

  const FIELD_LABELS = {
    description: 'Description', amount: 'Montant', expense_date: 'Date', category: 'Categorie', notes: 'Notes'
  };

  const inputStyle = { width: '100%', padding: '10px 12px', border: '1px solid #d1d5db', borderRadius: '8px', fontSize: '14px', boxSizing: 'border-box' };
  const labelStyle = { display: 'block', marginBottom: '6px', fontWeight: '600', fontSize: '13px', color: '#374151' };
  const btnPrimary = { background: 'linear-gradient(135deg, #00A08C, #008F7A)', color: '#fff', border: 'none', padding: '10px 20px', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '14px' };
  const btnSecondary = { background: '#f3f4f6', color: '#374151', border: '1px solid #d1d5db', padding: '10px 20px', borderRadius: '8px', cursor: 'pointer', fontWeight: '500', fontSize: '14px' };

  if (loading) return <div style={{ textAlign: 'center', padding: '64px' }}><p style={{ color: '#6b7280' }}>Chargement des depenses...</p></div>;

  return (
    <div data-testid="expenses-page">
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '28px', fontWeight: '800', color: '#1f2937', margin: 0 }}>Depenses</h1>
          <p style={{ color: '#6b7280', margin: '4px 0 0', fontSize: '14px' }}>Gerez vos depenses et importez des CSV</p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <input ref={fileInputRef} type="file" accept=".csv,.txt" onChange={handleFileSelect} style={{ display: 'none' }} />
          <button data-testid="import-csv-btn" onClick={() => fileInputRef.current?.click()} style={btnSecondary}>
            Importer CSV
          </button>
          <button onClick={() => { resetForm(); setShowForm(true); }} data-testid="add-expense-btn" style={btnPrimary}>
            + Nouvelle Depense
          </button>
        </div>
      </div>

      {error && <div data-testid="expense-error" style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#b91c1c', padding: '12px 16px', borderRadius: '8px', marginBottom: '16px', fontSize: '14px', cursor: 'pointer' }} onClick={() => setError('')}>{error}</div>}
      {success && <div data-testid="expense-success" style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', color: '#166534', padding: '12px 16px', borderRadius: '8px', marginBottom: '16px', fontSize: '14px', cursor: 'pointer' }} onClick={() => setSuccess('')}>{success}</div>}

      {/* List */}
      {expenses.length === 0 ? (
        <div style={{ background: '#fff', border: '2px dashed #d1d5db', borderRadius: '12px', padding: '48px', textAlign: 'center' }}>
          <h3 style={{ fontSize: '20px', fontWeight: '700', color: '#374151', margin: '0 0 8px' }}>Aucune depense enregistree</h3>
          <p style={{ color: '#6b7280', margin: '0 0 16px' }}>Ajoutez une depense manuellement ou importez un CSV</p>
          <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
            <button onClick={() => fileInputRef.current?.click()} style={btnSecondary}>Importer CSV</button>
            <button onClick={() => { resetForm(); setShowForm(true); }} style={btnPrimary}>Ajouter une depense</button>
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {expenses.map(exp => {
            const st = statusColors[exp.status] || statusColors.pending;
            const empName = getEmployeeName(exp.employee_id);
            return (
              <div key={exp.id} data-testid={`expense-card-${exp.id}`} style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '12px', padding: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
                  <div style={{ flex: '1', minWidth: '200px' }}>
                    <h3 style={{ fontSize: '16px', fontWeight: '700', color: '#1f2937', margin: '0 0 6px' }}>{exp.description}</h3>
                    <p style={{ color: '#6b7280', margin: '2px 0', fontSize: '14px' }}>
                      {empName ? `Employe: ${empName}` : (
                        <span style={{ color: '#9ca3af', fontStyle: 'italic' }}>Depense generale</span>
                      )}
                    </p>
                    <p style={{ color: '#9ca3af', margin: '2px 0', fontSize: '13px' }}>Date: {new Date(exp.expense_date).toLocaleDateString('fr-CA')}</p>
                    {exp.category && <p style={{ color: '#9ca3af', margin: '2px 0', fontSize: '12px' }}>Categorie: {exp.category}</p>}
                    {exp.receipt_url && (
                      <a
                        href={`${BACKEND_URL}${exp.receipt_url}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        data-testid={`receipt-link-${exp.id}`}
                        style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', marginTop: '6px', fontSize: '13px', color: '#008F7A', fontWeight: '600', textDecoration: 'none' }}
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"/></svg>
                        Voir le recu
                      </a>
                    )}
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '22px', fontWeight: '800', color: '#008F7A', marginBottom: '4px' }}>{formatCurrency(exp.amount, exp.currency)}</div>
                    {exp.currency && exp.currency !== 'CAD' && exp.amount_cad && (
                      <div style={{ fontSize: '12px', color: '#a1a1aa', marginBottom: '6px' }}>= {formatCurrency(exp.amount_cad, 'CAD')}</div>
                    )}
                    <span style={{ background: st.bg, color: st.color, padding: '3px 10px', borderRadius: '20px', fontSize: '12px', fontWeight: '600' }}>{st.label}</span>
                    <div style={{ display: 'flex', gap: '6px', marginTop: '10px', justifyContent: 'flex-end', flexWrap: 'wrap' }}>
                      {exp.status === 'pending' && (
                        <>
                          <button data-testid={`approve-${exp.id}`} onClick={() => updateStatus(exp.id, 'approved')} style={{ background: '#dcfce7', color: '#166534', border: 'none', padding: '6px 10px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', fontWeight: '600' }}>Approuver</button>
                          <button data-testid={`reject-${exp.id}`} onClick={() => updateStatus(exp.id, 'rejected')} style={{ background: '#fef2f2', color: '#dc2626', border: 'none', padding: '6px 10px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', fontWeight: '600' }}>Rejeter</button>
                        </>
                      )}
                      <button data-testid={`delete-expense-${exp.id}`} onClick={() => handleDelete(exp.id)} style={{ background: '#fef2f2', color: '#dc2626', border: 'none', padding: '6px 10px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', fontWeight: '600' }}>Suppr.</button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ═══ New Expense Form ═══ */}
      {showForm && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '20px' }}>
          <div style={{ background: '#fff', borderRadius: '16px', width: '95%', maxWidth: '560px', maxHeight: '92vh', overflow: 'auto', boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25)' }}>
            <div style={{ padding: '24px 28px', borderBottom: '1px solid #e5e7eb' }}>
              <h3 style={{ margin: 0, fontSize: '20px', fontWeight: '700' }}>Nouvelle Depense</h3>
            </div>
            <form onSubmit={handleSubmit} style={{ padding: '24px 28px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
                <div>
                  <label style={labelStyle}>Employe <span style={{ color: '#9ca3af', fontWeight: '400' }}>(optionnel)</span></label>
                  <select data-testid="expense-employee-select" value={formData.employee_id}
                    onChange={e => setFormData(prev => ({ ...prev, employee_id: e.target.value }))} style={inputStyle}>
                    <option value="">-- Depense generale --</option>
                    {employees.map(emp => <option key={emp.id} value={emp.id}>{emp.name}</option>)}
                  </select>
                </div>
                <div>
                  <label style={labelStyle}>Montant *</label>
                  <input type="number" step="0.01" data-testid="expense-amount-input" value={formData.amount}
                    onChange={e => setFormData(prev => ({ ...prev, amount: e.target.value }))} required style={inputStyle} />
                </div>
              </div>
              {/* Currency selector */}
              <div style={{ marginBottom: '16px' }}>
                <label style={labelStyle}>Devise</label>
                <CurrencySelector
                  currency={formData.currency}
                  amount={parseFloat(formData.amount) || 0}
                  onChange={(cur, rate) => setFormData(prev => ({ ...prev, currency: cur, exchange_rate_to_cad: rate }))}
                />
              </div>
              <div style={{ marginBottom: '16px' }}>
                <label style={labelStyle}>Description *</label>
                <input type="text" data-testid="expense-description-input" value={formData.description}
                  onChange={e => setFormData(prev => ({ ...prev, description: e.target.value }))}
                  required placeholder="Description de la depense" style={inputStyle} />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
                <div>
                  <label style={labelStyle}>Categorie</label>
                  <input type="text" value={formData.category}
                    onChange={e => setFormData(prev => ({ ...prev, category: e.target.value }))}
                    placeholder="Transport, Repas..." style={inputStyle} />
                </div>
                <div>
                  <label style={labelStyle}>Date</label>
                  <input type="date" value={formData.expense_date}
                    onChange={e => setFormData(prev => ({ ...prev, expense_date: e.target.value }))} style={inputStyle} />
                </div>
              </div>

              {/* Receipt Drag & Drop */}
              <div style={{ marginBottom: '16px' }}>
                <label style={labelStyle}>Recu <span style={{ color: '#9ca3af', fontWeight: '400' }}>(optionnel — glisser-deposer ou cliquer)</span></label>
                <input ref={receiptInputRef} type="file" accept="image/*,application/pdf" onChange={handleReceiptFileSelect} style={{ display: 'none' }} />
                {!previewReceipt && !formData.receipt_url ? (
                  <div
                    data-testid="receipt-dropzone"
                    onDragEnter={handleDrag}
                    onDragLeave={handleDrag}
                    onDragOver={handleDrag}
                    onDrop={handleDrop}
                    onClick={() => receiptInputRef.current?.click()}
                    style={{
                      border: `2px dashed ${dragActive ? '#00A08C' : '#d1d5db'}`,
                      borderRadius: '12px',
                      padding: '28px 20px',
                      textAlign: 'center',
                      cursor: 'pointer',
                      background: dragActive ? '#f0fdfa' : '#fafafa',
                      transition: 'all 0.2s ease'
                    }}
                  >
                    {uploading ? (
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
                        <div style={{ width: '28px', height: '28px', border: '3px solid #00A08C', borderTop: '3px solid transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
                        <span style={{ fontSize: '13px', color: '#6b7280' }}>Telechargement en cours...</span>
                      </div>
                    ) : (
                      <>
                        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ margin: '0 auto 8px' }}>
                          <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
                        </svg>
                        <p style={{ margin: '0 0 4px', fontSize: '14px', fontWeight: '600', color: '#374151' }}>
                          Glissez votre recu ici
                        </p>
                        <p style={{ margin: 0, fontSize: '12px', color: '#9ca3af' }}>
                          ou cliquez pour selectionner (JPG, PNG, PDF — max 5 Mo)
                        </p>
                      </>
                    )}
                  </div>
                ) : (
                  <div data-testid="receipt-preview" style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '10px', padding: '12px 16px'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
                      </svg>
                      <span style={{ fontSize: '14px', fontWeight: '600', color: '#065f46' }}>
                        {previewReceipt?.name || 'Recu attache'}
                      </span>
                    </div>
                    <button type="button" onClick={removeReceipt} data-testid="remove-receipt-btn" style={{
                      background: '#fef2f2', color: '#dc2626', border: 'none', padding: '4px 10px',
                      borderRadius: '6px', cursor: 'pointer', fontSize: '12px', fontWeight: '600'
                    }}>Retirer</button>
                  </div>
                )}
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', borderTop: '1px solid #e5e7eb', paddingTop: '20px' }}>
                <button type="button" onClick={() => { setShowForm(false); resetForm(); }} style={btnSecondary}>Annuler</button>
                <button type="submit" data-testid="save-expense-btn" disabled={uploading}
                  style={{ ...btnPrimary, opacity: uploading ? 0.6 : 1 }}>Creer la depense</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ═══ CSV Import Modal ═══ */}
      {showImport && importData && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '20px' }}>
          <div style={{ background: '#fff', borderRadius: '16px', width: '95%', maxWidth: '950px', maxHeight: '92vh', overflow: 'auto', boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25)' }}>
            <div style={{ padding: '24px 28px', borderBottom: '1px solid #e5e7eb' }}>
              <h3 style={{ margin: 0, fontSize: '20px', fontWeight: '700', color: '#1f2937' }}>Import CSV — Apercu</h3>
              <p style={{ margin: '4px 0 0', fontSize: '13px', color: '#6b7280' }}>
                {importData.total_rows} ligne(s) detectee(s) — Mapping automatique des colonnes
              </p>
            </div>

            <div style={{ padding: '24px 28px' }}>
              {/* Mapping info */}
              <div style={{ background: '#f0fdfa', border: '1px solid #99f6e4', borderRadius: '10px', padding: '14px 16px', marginBottom: '20px' }}>
                <p style={{ margin: '0 0 8px', fontWeight: '600', fontSize: '14px', color: '#0f766e' }}>Colonnes detectees :</p>
                <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                  {Object.entries(importData.mapping).map(([field, info]) => (
                    <span key={field} style={{ background: '#fff', border: '1px solid #99f6e4', padding: '4px 10px', borderRadius: '6px', fontSize: '12px' }}>
                      <strong>{FIELD_LABELS[field] || field}</strong> &larr; {info.column_name}
                    </span>
                  ))}
                </div>
                {Object.keys(importData.mapping).length < 2 && (
                  <p style={{ margin: '8px 0 0', color: '#b91c1c', fontSize: '13px' }}>
                    Peu de colonnes detectees. Verifiez que vos en-tetes CSV sont descriptifs.
                  </p>
                )}
              </div>

              {/* Preview table */}
              <div style={{ overflow: 'auto', marginBottom: '20px' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                  <thead>
                    <tr style={{ background: '#008F7A', color: '#fff' }}>
                      <th style={{ padding: '10px 8px', textAlign: 'center', width: '40px' }}>Incl.</th>
                      <th style={{ padding: '10px 8px', textAlign: 'left' }}>Description</th>
                      <th style={{ padding: '10px 8px', textAlign: 'right' }}>Montant</th>
                      <th style={{ padding: '10px 8px', textAlign: 'center' }}>Date</th>
                      <th style={{ padding: '10px 8px', textAlign: 'left' }}>Categorie</th>
                      <th style={{ padding: '10px 8px', textAlign: 'left' }}>Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {importRows.map((row, i) => (
                      <tr key={i} style={{ background: row._include ? (i % 2 === 0 ? '#fff' : '#f9fafb') : '#fef2f2', borderBottom: '1px solid #e5e7eb' }}>
                        <td style={{ padding: '8px', textAlign: 'center' }}>
                          <input type="checkbox" checked={row._include} onChange={() => toggleRow(i)} data-testid={`import-row-check-${i}`} />
                        </td>
                        <td style={{ padding: '8px' }}>
                          <input type="text" value={row.description || ''} data-testid={`import-row-desc-${i}`}
                            onChange={e => updateImportRow(i, 'description', e.target.value)}
                            style={{ ...inputStyle, padding: '6px 8px', fontSize: '12px' }} />
                        </td>
                        <td style={{ padding: '8px' }}>
                          <input type="number" step="0.01" value={row.amount || 0} data-testid={`import-row-amount-${i}`}
                            onChange={e => updateImportRow(i, 'amount', parseFloat(e.target.value) || 0)}
                            style={{ ...inputStyle, padding: '6px 8px', fontSize: '12px', textAlign: 'right', width: '100px' }} />
                        </td>
                        <td style={{ padding: '8px' }}>
                          <input type="text" value={row.expense_date || ''} data-testid={`import-row-date-${i}`}
                            onChange={e => updateImportRow(i, 'expense_date', e.target.value)}
                            style={{ ...inputStyle, padding: '6px 8px', fontSize: '12px', width: '110px', textAlign: 'center' }} />
                        </td>
                        <td style={{ padding: '8px' }}>
                          <input type="text" value={row.category || ''} data-testid={`import-row-cat-${i}`}
                            onChange={e => updateImportRow(i, 'category', e.target.value)}
                            style={{ ...inputStyle, padding: '6px 8px', fontSize: '12px' }} />
                        </td>
                        <td style={{ padding: '8px' }}>
                          <input type="text" value={row.notes || ''} data-testid={`import-row-notes-${i}`}
                            onChange={e => updateImportRow(i, 'notes', e.target.value)}
                            style={{ ...inputStyle, padding: '6px 8px', fontSize: '12px' }} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {importData.total_rows > 10 && (
                <p style={{ color: '#6b7280', fontSize: '12px', marginBottom: '16px' }}>
                  Apercu des 10 premieres lignes sur {importData.total_rows} au total. Toutes les lignes seront importees.
                </p>
              )}

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid #e5e7eb', paddingTop: '20px' }}>
                <span style={{ fontSize: '14px', color: '#374151' }}>
                  <strong>{importRows.filter(r => r._include).length}</strong> ligne(s) selectionnee(s)
                </span>
                <div style={{ display: 'flex', gap: '12px' }}>
                  <button onClick={() => { setShowImport(false); setImportData(null); setImportRows([]); }} style={btnSecondary}>Annuler</button>
                  <button data-testid="confirm-import-btn" onClick={handleImportConfirm} disabled={importing}
                    style={{ ...btnPrimary, opacity: importing ? 0.6 : 1 }}>
                    {importing ? 'Importation...' : `Importer ${importRows.filter(r => r._include).length} depense(s)`}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};

export default ExpensesPage;
