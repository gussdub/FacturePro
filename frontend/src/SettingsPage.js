import React, { useState, useEffect } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'https://facturepro-api.onrender.com';

const SettingsPage = () => {
  const [settings, setSettings] = useState({
    company_name: '',
    email: '',
    phone: '',
    address: '',
    city: '',
    postal_code: '',
    country: '',
    logo_url: '',
    gst_number: '',
    pst_number: '',
    hst_number: ''
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/settings/company`);
      setSettings(response.data);
    } catch (error) {
      console.error('Error fetching settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setMessage('');

    try {
      await axios.put(`${BACKEND_URL}/api/settings/company`, settings);
      setMessage('✅ Paramètres sauvegardés avec succès');
    } catch (error) {
      setMessage('❌ Erreur lors de la sauvegarde');
    } finally {
      setSaving(false);
    }
  };

  const handleLogoUpload = async () => {
    if (!settings.logo_url) {
      setMessage('❌ Veuillez entrer une URL de logo');
      return;
    }

    setUploading(true);
    setMessage('');

    try {
      const response = await axios.post(`${BACKEND_URL}/api/settings/company/upload-logo`, {
        logo_url: settings.logo_url
      });

      setMessage('✅ Logo sauvegardé avec succès');
    } catch (error) {
      setMessage('❌ Erreur lors de la sauvegarde du logo');
    } finally {
      setUploading(false);
    }
  };

  const handleChange = (field, value) => {
    setSettings(prev => ({ ...prev, [field]: value }));
  };

  if (loading) {
    return <div style={{ padding: '30px' }}>Chargement...</div>;
  }

  return (
    <div style={{ padding: '30px' }}>
      <h2 style={{ marginBottom: '30px', color: '#333' }}>⚙️ Paramètres de l'entreprise</h2>

      {message && (
        <div style={{
          background: message.includes('✅') ? '#f0f9ff' : '#fef2f2',
          border: `1px solid ${message.includes('✅') ? '#3b82f6' : '#ef4444'}`,
          color: message.includes('✅') ? '#1e40af' : '#dc2626',
          padding: '12px',
          borderRadius: '6px',
          marginBottom: '20px'
        }}>
          {message}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        {/* Logo Section */}
        <div style={{
          background: 'white',
          border: '1px solid #e2e8f0',
          borderRadius: '10px',
          padding: '25px',
          marginBottom: '25px'
        }}>
          <h3 style={{ marginTop: 0, color: '#333' }}>🖼️ Logo de l'entreprise</h3>
          
          {settings.logo_url && (
            <div style={{ marginBottom: '15px', textAlign: 'center' }}>
              <img
                src={settings.logo_url}
                alt="Logo entreprise"
                style={{
                  maxWidth: '150px',
                  maxHeight: '150px',
                  objectFit: 'contain',
                  border: '1px solid #ddd',
                  borderRadius: '8px'
                }}
              />
            </div>
          )}
          
          <input
            type="file"
            accept="image/*"
            onChange={handleLogoUpload}
            style={{ marginBottom: '10px' }}
          />
          {uploading && <p style={{ color: '#3b82f6' }}>Upload en cours...</p>}
        </div>

        {/* Company Info */}
        <div style={{
          background: 'white',
          border: '1px solid #e2e8f0',
          borderRadius: '10px',
          padding: '25px',
          marginBottom: '25px'
        }}>
          <h3 style={{ marginTop: 0, color: '#333' }}>🏢 Informations de l'entreprise</h3>
          
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '15px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: '600' }}>Nom de l'entreprise *</label>
              <input
                type="text"
                value={settings.company_name}
                onChange={(e) => handleChange('company_name', e.target.value)}
                required
                style={{
                  width: '100%',
                  padding: '10px',
                  border: '1px solid #ddd',
                  borderRadius: '5px',
                  boxSizing: 'border-box'
                }}
              />
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: '600' }}>Email *</label>
              <input
                type="email"
                value={settings.email}
                onChange={(e) => handleChange('email', e.target.value)}
                required
                style={{
                  width: '100%',
                  padding: '10px',
                  border: '1px solid #ddd',
                  borderRadius: '5px',
                  boxSizing: 'border-box'
                }}
              />
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: '600' }}>Téléphone</label>
              <input
                type="tel"
                value={settings.phone || ''}
                onChange={(e) => handleChange('phone', e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px',
                  border: '1px solid #ddd',
                  borderRadius: '5px',
                  boxSizing: 'border-box'
                }}
              />
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: '600' }}>Adresse</label>
              <input
                type="text"
                value={settings.address || ''}
                onChange={(e) => handleChange('address', e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px',
                  border: '1px solid #ddd',
                  borderRadius: '5px',
                  boxSizing: 'border-box'
                }}
              />
            </div>
          </div>
        </div>

        {/* Tax Numbers */}
        <div style={{
          background: 'white',
          border: '1px solid #e2e8f0',
          borderRadius: '10px',
          padding: '25px',
          marginBottom: '25px'
        }}>
          <h3 style={{ marginTop: 0, color: '#333' }}>📊 Numéros de taxes</h3>
          
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '15px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: '600' }}>TPS (Fédéral)</label>
              <input
                type="text"
                value={settings.gst_number || ''}
                onChange={(e) => handleChange('gst_number', e.target.value)}
                placeholder="123456789 RT0001"
                style={{
                  width: '100%',
                  padding: '10px',
                  border: '1px solid #ddd',
                  borderRadius: '5px',
                  boxSizing: 'border-box'
                }}
              />
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: '600' }}>TVQ (Québec)</label>
              <input
                type="text"
                value={settings.pst_number || ''}
                onChange={(e) => handleChange('pst_number', e.target.value)}
                placeholder="1234567890 TQ0001"
                style={{
                  width: '100%',
                  padding: '10px',
                  border: '1px solid #ddd',
                  borderRadius: '5px',
                  boxSizing: 'border-box'
                }}
              />
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: '600' }}>HST (Ontario)</label>
              <input
                type="text"
                value={settings.hst_number || ''}
                onChange={(e) => handleChange('hst_number', e.target.value)}
                placeholder="123456789 RT0001"
                style={{
                  width: '100%',
                  padding: '10px',
                  border: '1px solid #ddd',
                  borderRadius: '5px',
                  boxSizing: 'border-box'
                }}
              />
            </div>
          </div>
        </div>

        <div style={{ textAlign: 'center' }}>
          <button
            type="submit"
            disabled={saving}
            style={{
              background: saving ? '#9ca3af' : '#10b981',
              color: 'white',
              border: 'none',
              padding: '12px 30px',
              borderRadius: '6px',
              cursor: saving ? 'not-allowed' : 'pointer',
              fontSize: '16px',
              fontWeight: '600'
            }}
          >
            {saving ? 'Sauvegarde...' : '💾 Sauvegarder'}
          </button>
        </div>
      </form>
    </div>
  );
};