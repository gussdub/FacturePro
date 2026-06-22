import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import { BACKEND_URL, formatCurrency } from '../config';
import CurrencySelector from '../components/CurrencySelector';
import { ScanLine, Paperclip } from 'lucide-react';
import ReceiptScanConsentModal from '../components/ReceiptScanConsentModal';

function computeTaxesPaid(amountGross, province) {
  const a = parseFloat(amountGross) || 0;
  if (a <= 0) return { gst: 0, qst: 0, hst: 0 };
  const r2 = v => Math.round(v * 100) / 100;
  if (province === 'QC') {
    return { gst: r2(a * 5 / 114.975), qst: r2(a * 9.975 / 114.975), hst: 0 };
  }
  if (province === 'ON') {
    return { gst: 0, qst: 0, hst: r2(a * 13 / 113) };
  }
  if (['NB', 'NS', 'PE', 'NL'].includes(province)) {
    return { gst: 0, qst: 0, hst: r2(a * 15 / 115) };
  }
  return { gst: r2(a * 5 / 105), qst: 0, hst: 0 };
}

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
    currency: 'CAD', exchange_rate_to_cad: 1.0,
    category_code: '', category_custom_label: '',
    gst_paid_cad: 0, qst_paid_cad: 0, hst_paid_cad: 0, taxes_auto_computed: false,
  });
  const [categoryCatalog, setCategoryCatalog] = useState({ categories: [], groups: {} });
  const [companyProvince, setCompanyProvince] = useState('QC');
  const scanInputRef = useRef(null);
  const [scanLoading, setScanLoading] = useState(false);
  const [scanError, setScanError] = useState(null);
  const [receiptScan, setReceiptScan] = useState(null); // { fileId, extraction, blobUrl } | null
  const [needsConsent, setNeedsConsent] = useState(false);
  const [consentAt, setConsentAt] = useState(null);

  useEffect(() => { fetchData(); }, []);

  useEffect(() => {
    axios.get(`${BACKEND_URL}/api/expense-categories`)
      .then(resp => setCategoryCatalog(resp.data))
      .catch(err => console.error('Failed to fetch expense categories:', err));
  }, []);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) return;
    axios.get(`${BACKEND_URL}/api/settings/company`, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then(resp => setCompanyProvince(resp.data.province || 'QC'))
      .catch(() => {});
  }, []);

  useEffect(() => {
    axios.get(`${BACKEND_URL}/api/auth/me`).then(r => {
      setConsentAt(r.data?.receipt_ocr_consent_at || null);
    }).catch(() => {});
  }, []);

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
    setFormData({ employee_id: '', description: '', amount: '', category: '', expense_date: new Date().toISOString().split('T')[0], notes: '', receipt_url: '', currency: 'CAD', exchange_rate_to_cad: 1.0, category_code: '', category_custom_label: '', gst_paid_cad: 0, qst_paid_cad: 0, hst_paid_cad: 0, taxes_auto_computed: false });
    setPreviewReceipt(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault(); setError(''); setSuccess('');
    try {
      await axios.post(`${BACKEND_URL}/api/expenses`, { ...formData, amount: parseFloat(formData.amount) });
      // Clear scan state after successful save (file is now linked to the expense — do NOT delete it)
      if (receiptScan) {
        if (receiptScan.blobUrl) URL.revokeObjectURL(receiptScan.blobUrl);
        setReceiptScan(null);
      }
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

  const viewReceipt = async (fileId) => {
    try {
      const r = await axios.get(`${BACKEND_URL}/api/receipts/${fileId}`,
                                  { responseType: 'blob' });
      const url = URL.createObjectURL(r.data);
      window.open(url, "_blank");
      // Pas de revokeObjectURL — la nouvelle fenêtre utilise l'URL
    } catch (err) {
      setScanError("Reçu introuvable.");
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

  const removeReceiptFromForm = async () => {
    if (!receiptScan?.fileId) return;
    try {
      await axios.delete(`${BACKEND_URL}/api/files/${receiptScan.fileId}`);
    } catch { /* best-effort */ }
    if (receiptScan.blobUrl) URL.revokeObjectURL(receiptScan.blobUrl);
    setReceiptScan(null);
    setFormData((prev) => ({ ...prev, receipt_file_id: null }));
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

  const groupedCategories = (categoryCatalog.categories || []).reduce((acc, cat) => {
    if (!acc[cat.group]) acc[cat.group] = [];
    acc[cat.group].push(cat);
    return acc;
  }, {});

  const selectedCategory = (categoryCatalog.categories || []).find(
    c => c.code === formData.category_code
  );

  if (loading) return <div style={{ textAlign: 'center', padding: '64px' }}><p style={{ color: '#6b7280' }}>Chargement des depenses...</p></div>;

  const compressImage = async (file) => {
    if (file.size <= 1024 * 1024) return file;
    const img = await new Promise((res, rej) => {
      const i = new Image();
      i.onload = () => res(i);
      i.onerror = () => rej(new Error("Image illisible"));
      i.src = URL.createObjectURL(file);
    });
    const maxDim = 1600;
    const scale = Math.min(1, maxDim / Math.max(img.width, img.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(img.width * scale);
    canvas.height = Math.round(img.height * scale);
    canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
    return await new Promise((res) => canvas.toBlob(res, "image/jpeg", 0.85));
  };

  const handleScanClick = () => {
    setScanError(null);
    if (consentAt) {
      scanInputRef.current?.click();
    } else {
      setNeedsConsent(true);
    }
  };

  const acceptConsent = async () => {
    try {
      const r = await axios.post(`${BACKEND_URL}/api/auth/me/receipt-ocr-consent`);
      setConsentAt(r.data?.receipt_ocr_consent_at);
      setNeedsConsent(false);
      // ouvrir directement le file picker
      setTimeout(() => scanInputRef.current?.click(), 0);
    } catch {
      setScanError("Erreur d'enregistrement du consentement.");
      setNeedsConsent(false);
    }
  };

  const handleReceiptScan = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setScanError(null);
    setScanLoading(true);
    try {
      const compressed = await compressImage(file);
      if (compressed.size > 5 * 1024 * 1024) {
        setScanError("Photo trop volumineuse même après compression.");
        return;
      }
      const fd = new FormData();
      fd.append("file", compressed, file.name);
      const r = await axios.post(`${BACKEND_URL}/api/expenses/scan-receipt`,
        fd, { headers: { "Content-Type": "multipart/form-data" } });
      const ex = r.data.extraction;
      const blobUrl = URL.createObjectURL(compressed);
      setReceiptScan({ fileId: r.data.file_id, extraction: ex, blobUrl });
      // Pré-remplir formData et ouvrir le modal
      setFormData({
        employee_id: '', description: '', category: '', notes: '', receipt_url: '',
        currency: ex.currency_detected || 'CAD', exchange_rate_to_cad: 1.0,
        category_custom_label: '', taxes_auto_computed: false,
        vendor: ex.vendor || '',
        expense_date: ex.expense_date || new Date().toISOString().slice(0, 10),
        amount: ex.total_cad ?? '',
        gst_paid_cad: ex.gst_paid_cad ?? 0,
        qst_paid_cad: ex.qst_paid_cad ?? 0,
        hst_paid_cad: ex.hst_paid_cad ?? 0,
        category_code: ex.category_code || 'other',
        receipt_file_id: r.data.file_id,
      });
      setShowForm(true);
    } catch (err) {
      if (err.response?.status === 413) {
        setScanError("Photo trop volumineuse (max 5 MB).");
      } else if (err.response?.status === 422) {
        setScanError(err.response.data?.detail || "Format non supporté.");
      } else if (err.response?.status === 429) {
        setScanError("Limite mensuelle atteinte (200 scans).");
      } else if (err.response?.status === 502) {
        setScanError("Service temporairement indisponible.");
      } else {
        setScanError("Erreur d'extraction. Réessaye.");
      }
    } finally {
      setScanLoading(false);
    }
  };

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
          <button
            type="button"
            onClick={handleScanClick}
            disabled={scanLoading}
            style={{
              background: "#fff", color: "#00A08C", border: "1.5px solid #00A08C",
              padding: "8px 16px", borderRadius: 8, cursor: "pointer", fontSize: 14,
              fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 6,
              marginRight: 8,
            }}
            title="Scanner un reçu avec extraction automatique">
            <ScanLine size={16} /> Scanner reçu
          </button>
          <input
            ref={scanInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp,image/gif"
            style={{ display: "none" }}
            onChange={handleReceiptScan}
          />
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
                      {exp.receipt_file_id && (
                        <button
                          type="button"
                          onClick={(e) => { e.stopPropagation(); viewReceipt(exp.receipt_file_id); }}
                          title="Voir le reçu"
                          style={{ background: "none", border: "none", cursor: "pointer",
                                   color: "#6b7280", padding: 4,
                                   display: "inline-flex", alignItems: "center" }}>
                          <Paperclip size={14} />
                        </button>
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
              {receiptScan && (
                <div style={{ background: '#dbeafe', color: '#1e40af', padding: 10,
                               borderRadius: 6, marginBottom: 12, display: 'flex',
                               alignItems: 'center', gap: 12 }}>
                  <img src={receiptScan.blobUrl} alt="recu"
                       style={{ maxHeight: 80, maxWidth: 80, borderRadius: 4,
                                border: '1px solid #93c5fd', cursor: 'pointer',
                                objectFit: 'cover' }}
                       onClick={() => window.open(receiptScan.blobUrl, '_blank')} />
                  <div style={{ flex: 1, fontSize: 13 }}>
                    ✨ Données extraites automatiquement — vérifie avant d'enregistrer.
                  </div>
                  <button type="button" onClick={removeReceiptFromForm}
                          style={{ background: 'transparent', color: '#dc2626',
                                   border: '1px solid #fca5a5', padding: '4px 10px',
                                   borderRadius: 4, cursor: 'pointer', fontSize: 12 }}>
                    Retirer la photo
                  </button>
                </div>
              )}
              {receiptScan && (!receiptScan.extraction.vendor || !receiptScan.extraction.total_cad) && (
                <div style={{ background: '#fef3c7', color: '#92400e', padding: 8,
                               borderRadius: 6, marginBottom: 12, fontSize: 13 }}>
                  ⚠ Extraction partielle — remplis les champs manquants.
                </div>
              )}
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
              <div style={{ marginBottom: 14 }}>
                <label htmlFor="expense-category-select" style={{ display: 'block', fontSize: 13, fontWeight: 500, color: '#374151', marginBottom: 4 }}>
                  Categorie ARC
                </label>
                <select
                  id="expense-category-select"
                  value={formData.category_code}
                  onChange={e => setFormData(prev => ({ ...prev, category_code: e.target.value }))}
                  style={{
                    width: '100%', padding: '12px',
                    border: '1.5px solid #d1d5db', borderRadius: 8,
                    fontSize: 14, background: 'white', boxSizing: 'border-box',
                  }}
                >
                  <option value="">— Choisir une categorie —</option>
                  {Object.entries(groupedCategories)
                    .filter(([groupKey]) => groupKey !== 'other')
                    .map(([groupKey, cats]) => (
                      <optgroup key={groupKey} label={categoryCatalog.groups[groupKey] || groupKey}>
                        {cats.map(cat => (
                          <option key={cat.code} value={cat.code}>
                            {cat.label_fr}
                            {cat.deductible_percentage < 100 ? ` ${cat.deductible_percentage}%` : ''}
                            {cat.arc_line ? ` (${cat.arc_line})` : ''}
                          </option>
                        ))}
                      </optgroup>
                    ))
                  }
                  <optgroup label={categoryCatalog.groups && categoryCatalog.groups.other ? categoryCatalog.groups.other : 'Autre'}>
                    <option value="other">Autre categorie…</option>
                  </optgroup>
                </select>

                {formData.category_code === 'other' && (
                  <input
                    type="text"
                    placeholder="Preciser la categorie (ex: Cotisations syndicales)"
                    value={formData.category_custom_label}
                    onChange={e => setFormData(prev => ({ ...prev, category_custom_label: e.target.value }))}
                    style={{
                      width: '100%', padding: '12px', marginTop: 8,
                      border: '1.5px dashed #f59e0b', borderRadius: 8,
                      fontSize: 14, background: '#fffbeb', boxSizing: 'border-box',
                    }}
                  />
                )}

                {selectedCategory && selectedCategory.deductible_percentage < 100 && !isNaN(parseFloat(formData.amount)) && (
                  <div
                    role="status"
                    aria-live="polite"
                    style={{
                      marginTop: 8, padding: '8px 12px',
                      background: '#fef3c7', borderRadius: 6,
                      fontSize: 12.5, color: '#92400e',
                    }}>
                    {selectedCategory.deductible_percentage}% seulement deductible — montant deductible : <strong>
                      {(parseFloat(formData.amount) * selectedCategory.deductible_percentage / 100).toFixed(2)} $
                    </strong> sur {parseFloat(formData.amount).toFixed(2)} $
                  </div>
                )}
              </div>
              <div style={{ marginTop: 18, marginBottom: 16, padding: 16, background: '#f9fafb', borderRadius: 8, border: '1px solid #e5e7eb' }}>
                <h4 style={{ margin: '0 0 6px', fontSize: 14, color: '#1f2937' }}>Taxes payées (CTI/RTI)</h4>
                <p style={{ marginTop: 0, marginBottom: 12, fontSize: 12, color: '#6b7280' }}>
                  Saisis ces montants pour les inclure dans ton rapport TPS/TVQ trimestriel.
                </p>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
                  <div>
                    <label htmlFor="gst-paid-input" style={{ display: 'block', fontSize: 12, fontWeight: 500, color: '#374151' }}>TPS payée</label>
                    <input
                      id="gst-paid-input"
                      type="number" step="0.01" min="0"
                      value={formData.gst_paid_cad}
                      onChange={(e) => setFormData(prev => ({
                        ...prev,
                        gst_paid_cad: parseFloat(e.target.value) || 0,
                        taxes_auto_computed: false,
                      }))}
                      style={{ width: '100%', padding: '8px 10px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 13, boxSizing: 'border-box' }}
                    />
                  </div>
                  <div>
                    <label htmlFor="qst-paid-input" style={{ display: 'block', fontSize: 12, fontWeight: 500, color: '#374151' }}>TVQ payée</label>
                    <input
                      id="qst-paid-input"
                      type="number" step="0.01" min="0"
                      value={formData.qst_paid_cad}
                      onChange={(e) => setFormData(prev => ({
                        ...prev,
                        qst_paid_cad: parseFloat(e.target.value) || 0,
                        taxes_auto_computed: false,
                      }))}
                      style={{ width: '100%', padding: '8px 10px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 13, boxSizing: 'border-box' }}
                    />
                  </div>
                  <div>
                    <label htmlFor="hst-paid-input" style={{ display: 'block', fontSize: 12, fontWeight: 500, color: '#374151' }}>TVH payée</label>
                    <input
                      id="hst-paid-input"
                      type="number" step="0.01" min="0"
                      value={formData.hst_paid_cad}
                      onChange={(e) => setFormData(prev => ({
                        ...prev,
                        hst_paid_cad: parseFloat(e.target.value) || 0,
                        taxes_auto_computed: false,
                      }))}
                      style={{ width: '100%', padding: '8px 10px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 13, boxSizing: 'border-box' }}
                    />
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    const t = computeTaxesPaid(formData.amount, companyProvince);
                    setFormData(prev => ({
                      ...prev,
                      gst_paid_cad: t.gst,
                      qst_paid_cad: t.qst,
                      hst_paid_cad: t.hst,
                      taxes_auto_computed: true,
                    }));
                  }}
                  disabled={formData.currency !== 'CAD'}
                  style={{
                    marginTop: 10, padding: '8px 14px',
                    background: formData.currency === 'CAD' ? '#00A08C' : '#d1d5db',
                    color: 'white', border: 0, borderRadius: 6,
                    fontSize: 13, cursor: formData.currency === 'CAD' ? 'pointer' : 'not-allowed',
                  }}
                >
                  🧮 Calculer auto (province {companyProvince})
                </button>
                {formData.currency !== 'CAD' && (
                  <p role="status" aria-live="polite" style={{ marginTop: 6, fontSize: 11.5, color: '#92400e' }}>
                    ⚠ Calcul auto disponible seulement pour les dépenses en CAD.
                  </p>
                )}
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label style={labelStyle}>Date</label>
                <input type="date" value={formData.expense_date}
                  onChange={e => setFormData(prev => ({ ...prev, expense_date: e.target.value }))} style={inputStyle} />
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
                <button type="button" onClick={async () => { if (receiptScan) { await removeReceiptFromForm(); } setShowForm(false); resetForm(); }} style={btnSecondary}>Annuler</button>
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

      {scanLoading && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)",
                       display: "flex", flexDirection: "column",
                       alignItems: "center", justifyContent: "center", zIndex: 1200,
                       color: "#fff" }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>⏳</div>
          <p>Analyse du reçu en cours…</p>
        </div>
      )}
      {scanError && (
        <div style={{ position: "fixed", bottom: 24, left: "50%",
                       transform: "translateX(-50%)", background: "#fee2e2",
                       color: "#991b1b", padding: 12, borderRadius: 6, zIndex: 1300,
                       boxShadow: "0 4px 12px rgba(0,0,0,0.1)" }}>
          {scanError}
          <button onClick={() => setScanError(null)}
                  style={{ marginLeft: 8, background: "transparent",
                           border: "none", cursor: "pointer", color: "#991b1b",
                           fontWeight: 700 }}>×</button>
        </div>
      )}

      {needsConsent && (
        <ReceiptScanConsentModal
          onAccept={acceptConsent}
          onCancel={() => setNeedsConsent(false)} />
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
