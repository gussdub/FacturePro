import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import { BACKEND_URL, CURRENCY_LABELS } from '../config';

const SettingsPage = () => {
  const [settings, setSettings] = useState({
    company_name: '', email: '', phone: '', address: '', city: '', postal_code: '', country: '',
    logo_url: '', primary_color: '#00A08C', secondary_color: '#1F2937',
    gst_number: '', pst_number: '', hst_number: '', default_due_days: 30,
    default_currency: 'CAD'
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef(null);

  useEffect(() => { fetchSettings(); }, []);

  const fetchSettings = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/settings/company`);
      setSettings(prev => ({ ...prev, ...response.data }));
    } catch (err) { setError('Erreur lors du chargement des parametres'); }
    finally { setLoading(false); }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true); setError(''); setSuccess('');
    try {
      await axios.put(`${BACKEND_URL}/api/settings/company`, settings);
      setSuccess('Parametres sauvegardes avec succes');
    } catch (err) { setError('Erreur lors de la sauvegarde'); }
    finally { setSaving(false); }
  };

  const uploadLogo = useCallback(async (file) => {
    if (!file) return;
    const allowed = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
    if (!allowed.includes(file.type)) {
      setError('Format accepte: JPG, PNG, GIF, WebP'); return;
    }
    if (file.size > 2 * 1024 * 1024) {
      setError('Le logo ne doit pas depasser 2 Mo'); return;
    }

    setUploading(true); setError(''); setSuccess('');
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await axios.post(`${BACKEND_URL}/api/settings/company/upload-logo-file`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setSettings(prev => ({ ...prev, logo_url: response.data.logo_url }));
      setSuccess('Logo televerse avec succes !');
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur lors du telechargement du logo');
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
    if (e.dataTransfer.files?.[0]) uploadLogo(e.dataTransfer.files[0]);
  }, [uploadLogo]);

  const handleFileSelect = (e) => {
    if (e.target.files?.[0]) uploadLogo(e.target.files[0]);
  };

  const getLogoDisplayUrl = (url) => {
    if (!url) return null;
    if (url.startsWith('/api')) return `${BACKEND_URL}${url}`;
    if (url.startsWith('http')) return url;
    return null;
  };

  if (loading) return <div style={{ textAlign: 'center', padding: '60px' }}><p>Chargement des parametres...</p></div>;

  const inputStyle = { width: '100%', padding: '12px', border: '1px solid #d1d5db', borderRadius: '8px', boxSizing: 'border-box' };

  return (
    <div data-testid="settings-page">
      <div style={{ marginBottom: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
          <div style={{ fontSize: '32px', marginRight: '12px' }}>&#9881;&#65039;</div>
          <h1 style={{ fontSize: '32px', fontWeight: '800', color: '#1f2937', margin: 0 }}>Parametres</h1>
        </div>
        <p style={{ color: '#6b7280', margin: 0 }}>Configuration de votre entreprise</p>
      </div>

      {error && <div style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#b91c1c', padding: '16px', borderRadius: '12px', marginBottom: '20px' }}>{error}</div>}
      {success && <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', color: '#166534', padding: '16px', borderRadius: '12px', marginBottom: '20px' }}>{success}</div>}

      <form onSubmit={handleSubmit}>
        {/* Logo Upload Section */}
        <div style={{ background: 'white', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '24px', marginBottom: '24px' }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: '700' }}>Logo de l'entreprise</h3>

          <div style={{ display: 'flex', gap: '24px', alignItems: 'flex-start' }}>
            {/* Current Logo Preview */}
            <div style={{
              width: '120px', height: '120px', borderRadius: '12px', overflow: 'hidden',
              border: '2px solid #e5e7eb', display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: '#f9fafb', flexShrink: 0
            }}>
              {getLogoDisplayUrl(settings.logo_url) ? (
                <img
                  src={getLogoDisplayUrl(settings.logo_url)}
                  alt="Logo actuel"
                  style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
                  onError={(e) => { e.target.style.display = 'none'; }}
                />
              ) : (
                <div style={{ textAlign: 'center', color: '#9ca3af', fontSize: '14px' }}>
                  <div style={{ fontSize: '32px', marginBottom: '4px' }}>&#128247;</div>
                  Aucun logo
                </div>
              )}
            </div>

            {/* Drag & Drop Zone */}
            <div
              data-testid="logo-dropzone"
              onDragEnter={handleDrag} onDragOver={handleDrag} onDragLeave={handleDrag} onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              style={{
                flex: 1, padding: '32px', borderRadius: '12px', textAlign: 'center', cursor: 'pointer',
                border: dragActive ? '2px dashed #00A08C' : '2px dashed #d1d5db',
                background: dragActive ? '#f0fdfa' : '#fafafa',
                transition: 'all 0.2s ease'
              }}
            >
              <input
                ref={fileInputRef} type="file" accept="image/jpeg,image/png,image/gif,image/webp"
                onChange={handleFileSelect} style={{ display: 'none' }}
                data-testid="logo-file-input"
              />
              {uploading ? (
                <div>
                  <div style={{ fontSize: '32px', marginBottom: '8px', animation: 'spin 1s linear infinite' }}>&#8987;</div>
                  <p style={{ color: '#00A08C', fontWeight: '600', margin: 0 }}>Telechargement en cours...</p>
                </div>
              ) : (
                <div>
                  <div style={{ fontSize: '40px', marginBottom: '8px' }}>&#9729;&#65039;</div>
                  <p style={{ fontWeight: '600', color: '#374151', margin: '0 0 4px 0', fontSize: '16px' }}>
                    Glissez-deposez votre logo ici
                  </p>
                  <p style={{ color: '#6b7280', margin: '0 0 12px 0', fontSize: '14px' }}>
                    ou cliquez pour parcourir vos fichiers
                  </p>
                  <span style={{
                    display: 'inline-block', background: '#00A08C', color: 'white',
                    padding: '8px 20px', borderRadius: '8px', fontSize: '14px', fontWeight: '600'
                  }}>
                    Choisir un fichier
                  </span>
                  <p style={{ color: '#9ca3af', margin: '8px 0 0 0', fontSize: '12px' }}>
                    JPG, PNG, GIF, WebP - Max 2 Mo
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Company Info */}
        <div style={{ background: 'white', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '24px', marginBottom: '24px' }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: '700' }}>Informations de l'entreprise</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Nom de l'entreprise *</label>
              <input type="text" value={settings.company_name} onChange={(e) => setSettings(prev => ({ ...prev, company_name: e.target.value }))}
                required data-testid="company-name-input" style={inputStyle} />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Email *</label>
              <input type="email" value={settings.email} onChange={(e) => setSettings(prev => ({ ...prev, email: e.target.value }))}
                required data-testid="company-email-input" style={inputStyle} />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Telephone</label>
              <input type="tel" value={settings.phone || ''} onChange={(e) => setSettings(prev => ({ ...prev, phone: e.target.value }))} style={inputStyle} />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Ville</label>
              <input type="text" value={settings.city || ''} onChange={(e) => setSettings(prev => ({ ...prev, city: e.target.value }))} style={inputStyle} />
            </div>
          </div>
        </div>

        {/* Tax Numbers */}
        <div style={{ background: 'white', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '24px', marginBottom: '24px' }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: '700' }}>Numeros de taxes canadiens</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '16px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>TPS (Federal)</label>
              <input type="text" value={settings.gst_number || ''} onChange={(e) => setSettings(prev => ({ ...prev, gst_number: e.target.value }))}
                placeholder="123456789 RT0001" data-testid="gst-number-input" style={inputStyle} />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>TVQ (Quebec)</label>
              <input type="text" value={settings.pst_number || ''} onChange={(e) => setSettings(prev => ({ ...prev, pst_number: e.target.value }))}
                placeholder="1234567890 TQ0001" data-testid="pst-number-input" style={inputStyle} />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>HST (Ontario)</label>
              <input type="text" value={settings.hst_number || ''} onChange={(e) => setSettings(prev => ({ ...prev, hst_number: e.target.value }))}
                placeholder="123456789 RT0001" data-testid="hst-number-input" style={inputStyle} />
            </div>
          </div>
        </div>

        {/* Default Currency */}
        <div style={{ background: 'white', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '24px', marginBottom: '24px' }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: '700' }}>Devise par defaut</h3>
          <p style={{ color: '#6b7280', fontSize: '14px', margin: '0 0 16px' }}>Choisissez la devise utilisee par defaut pour vos factures et depenses. Vous pourrez toujours changer la devise par document.</p>
          <div style={{ maxWidth: '320px' }}>
            <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Devise</label>
            <select
              data-testid="default-currency-select"
              value={settings.default_currency || 'CAD'}
              onChange={(e) => setSettings(prev => ({ ...prev, default_currency: e.target.value }))}
              style={inputStyle}
            >
              {Object.entries(CURRENCY_LABELS).map(([code, label]) => (
                <option key={code} value={code}>{label}</option>
              ))}
            </select>
          </div>
        </div>

        <div style={{ textAlign: 'center' }}>
          <button type="submit" disabled={saving} data-testid="save-settings-btn" style={{
            background: saving ? '#9ca3af' : 'linear-gradient(135deg, #10b981, #047857)',
            color: 'white', border: 'none', padding: '16px 32px', borderRadius: '12px',
            cursor: saving ? 'not-allowed' : 'pointer', fontSize: '16px', fontWeight: '700'
          }}>{saving ? 'Sauvegarde...' : 'Sauvegarder tous les parametres'}</button>
        </div>
      </form>

      <style>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
    </div>
  );
};

export default SettingsPage;
