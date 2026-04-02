import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { BACKEND_URL } from '../config';

const SettingsPage = () => {
  const [settings, setSettings] = useState({
    company_name: '', email: '', phone: '', address: '', city: '', postal_code: '', country: '',
    logo_url: '', primary_color: '#00A08C', secondary_color: '#1F2937',
    gst_number: '', pst_number: '', hst_number: '', default_due_days: 30
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

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

  const handleLogoSave = async () => {
    if (!settings.logo_url) { setError('Veuillez entrer une URL de logo'); return; }
    try {
      await axios.post(`${BACKEND_URL}/api/settings/company/upload-logo`, { logo_url: settings.logo_url });
      setSuccess('Logo sauvegarde avec succes');
    } catch (err) { setError('Erreur lors de la sauvegarde du logo'); }
  };

  if (loading) return <div style={{ textAlign: 'center', padding: '60px' }}><p>Chargement des parametres...</p></div>;

  const inputStyle = { width: '100%', padding: '12px', border: '1px solid #d1d5db', borderRadius: '8px', boxSizing: 'border-box' };

  return (
    <div data-testid="settings-page">
      <div style={{ marginBottom: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
          <div style={{ fontSize: '32px', marginRight: '12px' }}>⚙️</div>
          <h1 style={{ fontSize: '32px', fontWeight: '800', color: '#1f2937', margin: 0 }}>Parametres</h1>
        </div>
        <p style={{ color: '#6b7280', margin: 0 }}>Configuration de votre entreprise</p>
      </div>

      {error && <div style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#b91c1c', padding: '16px', borderRadius: '12px', marginBottom: '20px' }}>{error}</div>}
      {success && <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', color: '#166534', padding: '16px', borderRadius: '12px', marginBottom: '20px' }}>{success}</div>}

      <form onSubmit={handleSubmit}>
        {/* Logo Section */}
        <div style={{ background: 'white', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '24px', marginBottom: '24px' }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: '700' }}>Logo de l'entreprise</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '16px', alignItems: 'end' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>URL du logo</label>
              <input type="url" value={settings.logo_url || ''} onChange={(e) => setSettings(prev => ({ ...prev, logo_url: e.target.value }))}
                placeholder="https://exemple.com/votre-logo.png" data-testid="logo-url-input" style={inputStyle} />
            </div>
            <button type="button" onClick={handleLogoSave} data-testid="save-logo-btn" style={{
              background: '#00A08C', color: 'white', border: 'none', padding: '12px 20px', borderRadius: '8px', cursor: 'pointer', fontWeight: '600'
            }}>Sauvegarder logo</button>
          </div>
          {settings.logo_url && (
            <div style={{ marginTop: '16px', textAlign: 'center' }}>
              <img src={settings.logo_url} alt="Logo apercu" style={{
                maxWidth: '120px', maxHeight: '120px', objectFit: 'contain', border: '1px solid #e5e7eb', borderRadius: '8px'
              }} onError={() => setError("Impossible de charger l'image")} />
            </div>
          )}
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

        <div style={{ textAlign: 'center' }}>
          <button type="submit" disabled={saving} data-testid="save-settings-btn" style={{
            background: saving ? '#9ca3af' : 'linear-gradient(135deg, #10b981, #047857)',
            color: 'white', border: 'none', padding: '16px 32px', borderRadius: '12px',
            cursor: saving ? 'not-allowed' : 'pointer', fontSize: '16px', fontWeight: '700'
          }}>{saving ? 'Sauvegarde...' : 'Sauvegarder tous les parametres'}</button>
        </div>
      </form>
    </div>
  );
};

export default SettingsPage;
