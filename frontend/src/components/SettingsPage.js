import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Alert, AlertDescription } from './ui/alert';
import { 
  Building2, 
  Palette, 
  Upload,
  Save,
  User,
  Mail,
  Phone,
  MapPin,
  Settings
} from 'lucide-react';

// Force production URL when on facturepro.ca
const BACKEND_URL = window.location.hostname === 'facturepro.ca' 
  ? 'https://facturepro.ca'
  : process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

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
    primary_color: '#3B82F6',
    secondary_color: '#1F2937',
    default_due_days: 30,
    gst_number: '',
    pst_number: '',
    hst_number: ''
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [dragActive, setDragActive] = useState(false);

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/settings/company`);
      setSettings(response.data);
    } catch (error) {
      console.error('Erreur lors du chargement des paramètres:', error);
      setError('Erreur lors du chargement des paramètres');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    setSuccess('');

    try {
      await axios.put(`${API}/settings/company`, settings);
      setSuccess('Paramètres sauvegardés avec succès');
    } catch (error) {
      setError(error.response?.data?.detail || 'Erreur lors de la sauvegarde');
    } finally {
      setSaving(false);
    }
  };

  const handleChange = (field, value) => {
    setSettings(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const presetColors = {
    blue: { primary: '#3B82F6', secondary: '#1F2937' },
    green: { primary: '#059669', secondary: '#064E3B' },
    purple: { primary: '#7C3AED', secondary: '#1E1B4B' },
    red: { primary: '#DC2626', secondary: '#7F1D1D' },
    orange: { primary: '#EA580C', secondary: '#9A3412' },
    teal: { primary: '#0D9488', secondary: '#134E4A' }
  };

  const applyColorPreset = (colorName) => {
    const colors = presetColors[colorName];
    setSettings(prev => ({
      ...prev,
      primary_color: colors.primary,
      secondary_color: colors.secondary
    }));
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    const files = e.dataTransfer.files;
    if (files && files[0]) {
      handleFileUpload(files[0]);
    }
  };

  const handleFileChange = (e) => {
    const files = e.target.files;
    if (files && files[0]) {
      handleFileUpload(files[0]);
    }
  };

  const handleFileUpload = async (file) => {
    // Vérifier le type de fichier
    if (!file.type.startsWith('image/')) {
      setError('Veuillez sélectionner un fichier image');
      return;
    }

    // Vérifier la taille (max 5MB)
    if (file.size > 5 * 1024 * 1024) {
      setError('La taille du fichier ne doit pas dépasser 5MB');
      return;
    }

    setUploadingLogo(true);
    setError('');

    try {
      // Upload file to server
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await axios.post(`${API}/settings/company/upload-logo`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        }
      });
      
      // Update settings with server logo URL
      setSettings(prev => ({
        ...prev,
        logo_url: response.data.logo_url
      }));

      setSuccess('Logo uploadé et sauvegardé avec succès');
    } catch (error) {
      setError(error.response?.data?.detail || 'Erreur lors de l\'upload du logo');
    } finally {
      setUploadingLogo(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="animate-shimmer h-8 bg-gray-200 rounded w-1/3"></div>
        <Card className="p-6">
          <div className="animate-shimmer h-4 bg-gray-200 rounded w-3/4 mb-4"></div>
          <div className="animate-shimmer h-4 bg-gray-200 rounded w-1/2"></div>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Paramètres</h1>
        <p className="text-gray-600">Configurez votre entreprise et personnalisez l'apparence</p>
      </div>

      {/* Success/Error messages */}
      {success && (
        <Alert className="border-green-200 bg-green-50">
          <AlertDescription className="text-green-800">{success}</AlertDescription>
        </Alert>
      )}

      {error && (
        <Alert className="border-red-200 bg-red-50">
          <AlertDescription className="text-red-800">{error}</AlertDescription>
        </Alert>
      )}

      <form onSubmit={handleSubmit} className="space-y-8">
        {/* Company Information */}
        <Card className="card-hover">
          <div className="p-6">
            <div className="flex items-center mb-6">
              <Building2 className="w-6 h-6 text-indigo-600 mr-3" />
              <h2 className="text-xl font-semibold text-gray-900">Informations de l'entreprise</h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  <User className="w-4 h-4 inline mr-2" />
                  Nom de l'entreprise *
                </label>
                <Input
                  value={settings.company_name}
                  onChange={(e) => handleChange('company_name', e.target.value)}
                  placeholder="Mon Entreprise SARL"
                  required
                  data-testid="company-name-input"
                  className="form-input"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  <Mail className="w-4 h-4 inline mr-2" />
                  Email de contact *
                </label>
                <Input
                  type="email"
                  value={settings.email}
                  onChange={(e) => handleChange('email', e.target.value)}
                  placeholder="contact@monentreprise.ca"
                  required
                  data-testid="company-email-input"
                  className="form-input"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  <Phone className="w-4 h-4 inline mr-2" />
                  Téléphone
                </label>
                <Input
                  value={settings.phone}
                  onChange={(e) => handleChange('phone', e.target.value)}
                  placeholder="514-123-4567"
                  data-testid="company-phone-input"
                  className="form-input"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  <MapPin className="w-4 h-4 inline mr-2" />
                  Province
                </label>
                <Input
                  value={settings.country}
                  onChange={(e) => handleChange('country', e.target.value)}
                  placeholder="Québec"
                  data-testid="company-country-input"
                  className="form-input"
                />
              </div>

              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Adresse complète
                </label>
                <Input
                  value={settings.address}
                  onChange={(e) => handleChange('address', e.target.value)}
                  placeholder="123 Rue Sainte-Catherine Est"
                  data-testid="company-address-input"
                  className="form-input"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Ville
                </label>
                <Input
                  value={settings.city}
                  onChange={(e) => handleChange('city', e.target.value)}
                  placeholder="Montréal"
                  data-testid="company-city-input"
                  className="form-input"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Code postal
                </label>
                <Input
                  value={settings.postal_code}
                  onChange={(e) => handleChange('postal_code', e.target.value)}
                  placeholder="H1A 0A1"
                  data-testid="company-postal-input"
                  className="form-input"
                />
              </div>
            </div>
            
            {/* Tax Numbers Section */}
            <div className="pt-6 border-t border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Numéros de taxes</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Numéro TPS (Fédéral)
                  </label>
                  <Input
                    value={settings.gst_number || ''}
                    onChange={(e) => handleChange('gst_number', e.target.value)}
                    placeholder="123456789 RT0001"
                    data-testid="gst-number-input"
                    className="form-input"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Ex: 123456789 RT0001 (TPS/GST)
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Numéro TVQ (Québec)
                  </label>
                  <Input
                    value={settings.pst_number || ''}
                    onChange={(e) => handleChange('pst_number', e.target.value)}
                    placeholder="1234567890 TQ0001"
                    data-testid="pst-number-input"
                    className="form-input"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Ex: 1234567890 TQ0001 (TVQ)
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Numéro HST (Ontario+)
                  </label>
                  <Input
                    value={settings.hst_number || ''}
                    onChange={(e) => handleChange('hst_number', e.target.value)}
                    placeholder="123456789 RT0001"
                    data-testid="hst-number-input"
                    className="form-input"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Ex: 123456789 RT0001 (HST)
                  </p>
                </div>
              </div>
            </div>
            
            {/* Default Due Days */}
            <div className="pt-4 border-t border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Paramètres de facturation</h3>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Échéance par défaut (jours)
                </label>
                <Input
                  type="number"
                  value={settings.default_due_days}
                  onChange={(e) => handleChange('default_due_days', parseInt(e.target.value) || 30)}
                  placeholder="30"
                  data-testid="default-due-days-input"
                  className="form-input w-32"
                  min="1"
                  max="365"
                />
                <p className="text-sm text-gray-500 mt-1">
                  Nombre de jours par défaut pour l'échéance des factures (modifiable individuellement)
                </p>
              </div>
            </div>
          </div>
        </Card>

        {/* Logo Section */}
        <Card className="card-hover">
          <div className="p-6">
            <div className="flex items-center mb-6">
              <Upload className="w-6 h-6 text-indigo-600 mr-3" />
              <h2 className="text-xl font-semibold text-gray-900">Logo de l'entreprise</h2>
            </div>

            <div className="space-y-4">
              {/* Drag & Drop Zone */}
              <div
                className={`relative border-2 border-dashed rounded-lg p-6 text-center transition-colors ${
                  dragActive 
                    ? 'border-indigo-500 bg-indigo-50' 
                    : 'border-gray-300 hover:border-gray-400'
                }`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
              >
                <input
                  type="file"
                  id="logo-upload"
                  className="hidden"
                  accept="image/*"
                  onChange={handleFileChange}
                />
                
                {settings.logo_url ? (
                  <div className="space-y-4">
                    <div className="w-32 h-32 mx-auto border-2 border-gray-200 rounded-lg overflow-hidden bg-white">
                      <img
                        src={`${process.env.REACT_APP_BACKEND_URL}${settings.logo_url}`}
                        alt="Logo de l'entreprise"
                        className="w-full h-full object-contain"
                        onError={(e) => {
                          console.log('Settings logo failed to load:', `${process.env.REACT_APP_BACKEND_URL}${settings.logo_url}`);
                          e.target.style.display = 'none';
                          e.target.nextSibling.style.display = 'block';
                        }}
                        onLoad={() => {
                          console.log('Settings logo loaded successfully');
                        }}
                      />
                      <div className="w-full h-full flex items-center justify-center text-gray-400" style={{display: 'none'}}>
                        <Upload className="w-8 h-8" />
                      </div>
                    </div>
                    <div>
                      <p className="text-sm font-medium text-gray-700 mb-2">Logo actuel</p>
                      <label
                        htmlFor="logo-upload"
                        className="cursor-pointer inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
                      >
                        <Upload className="w-4 h-4 mr-2" />
                        Changer le logo
                      </label>
                      <button
                        type="button"
                        onClick={() => setSettings(prev => ({ ...prev, logo_url: '' }))}
                        className="ml-2 text-sm text-red-600 hover:text-red-800"
                      >
                        Supprimer
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <Upload className="w-12 h-12 text-gray-400 mx-auto" />
                    <div>
                      <p className="text-lg font-medium text-gray-700">
                        Glissez-déposez votre logo ici
                      </p>
                      <p className="text-sm text-gray-500">
                        ou{' '}
                        <label
                          htmlFor="logo-upload"
                          className="text-indigo-600 hover:text-indigo-800 cursor-pointer font-medium"
                        >
                          cliquez pour parcourir
                        </label>
                      </p>
                    </div>
                    <div className="text-xs text-gray-400">
                      PNG, JPG, GIF jusqu'à 5MB
                    </div>
                  </div>
                )}

                {uploadingLogo && (
                  <div className="absolute inset-0 bg-white bg-opacity-75 flex items-center justify-center rounded-lg">
                    <div className="flex items-center space-x-2">
                      <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-indigo-600"></div>
                      <span className="text-sm text-gray-600">Upload en cours...</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </Card>

        {/* Color Customization */}
        <Card className="card-hover">
          <div className="p-6">
            <div className="flex items-center mb-6">
              <Palette className="w-6 h-6 text-indigo-600 mr-3" />
              <h2 className="text-xl font-semibold text-gray-900">Personnalisation des couleurs</h2>
            </div>

            <div className="space-y-6">
              {/* Color Presets */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">
                  Thèmes prédéfinis
                </label>
                <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
                  {Object.entries(presetColors).map(([name, colors]) => (
                    <button
                      key={name}
                      type="button"
                      onClick={() => applyColorPreset(name)}
                      className="p-3 rounded-lg border-2 hover:border-gray-400 transition-colors"
                      style={{ 
                        background: `linear-gradient(135deg, ${colors.primary} 0%, ${colors.secondary} 100%)` 
                      }}
                      data-testid={`color-preset-${name}`}
                    >
                      <div className="w-full h-8 rounded"></div>
                      <p className="text-xs text-white mt-1 capitalize font-medium">
                        {name === 'blue' ? 'Bleu' : 
                         name === 'green' ? 'Vert' :
                         name === 'purple' ? 'Violet' :
                         name === 'red' ? 'Rouge' :
                         name === 'orange' ? 'Orange' :
                         name === 'teal' ? 'Sarcelle' : name}
                      </p>
                    </button>
                  ))}
                </div>
              </div>

              {/* Custom Colors */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Couleur principale
                  </label>
                  <div className="flex items-center space-x-3">
                    <input
                      type="color"
                      value={settings.primary_color}
                      onChange={(e) => handleChange('primary_color', e.target.value)}
                      className="w-12 h-10 rounded border border-gray-300 cursor-pointer"
                      data-testid="primary-color-input"
                    />
                    <Input
                      value={settings.primary_color}
                      onChange={(e) => handleChange('primary_color', e.target.value)}
                      className="flex-1 font-mono text-sm"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Couleur secondaire
                  </label>
                  <div className="flex items-center space-x-3">
                    <input
                      type="color"
                      value={settings.secondary_color}
                      onChange={(e) => handleChange('secondary_color', e.target.value)}
                      className="w-12 h-10 rounded border border-gray-300 cursor-pointer"
                      data-testid="secondary-color-input"
                    />
                    <Input
                      value={settings.secondary_color}
                      onChange={(e) => handleChange('secondary_color', e.target.value)}
                      className="flex-1 font-mono text-sm"
                    />
                  </div>
                </div>
              </div>

              {/* Color Preview */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">
                  Aperçu des couleurs
                </label>
                <div className="space-y-3">
                  <div 
                    className="p-4 rounded-lg text-white"
                    style={{ backgroundColor: settings.primary_color }}
                  >
                    <p className="font-semibold">Couleur principale</p>
                    <p className="text-sm opacity-90">Utilisée pour les boutons et éléments importants</p>
                  </div>
                  <div 
                    className="p-4 rounded-lg text-white"
                    style={{ backgroundColor: settings.secondary_color }}
                  >
                    <p className="font-semibold">Couleur secondaire</p>
                    <p className="text-sm opacity-90">Utilisée pour les en-têtes et éléments de navigation</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </Card>

        {/* Save Button */}
        <div className="flex justify-end">
          <Button
            type="submit"
            disabled={saving}
            data-testid="save-settings-btn"
            className="btn-hover px-8 py-3 text-base"
            style={{ 
              backgroundColor: settings.primary_color,
              borderColor: settings.primary_color 
            }}
          >
            {saving ? (
              <div className="flex items-center">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                Sauvegarde...
              </div>
            ) : (
              <>
                <Save className="w-4 h-4 mr-2" />
                Sauvegarder les paramètres
              </>
            )}
          </Button>
        </div>
      </form>

      {/* Info Card */}
      <Card className="bg-blue-50 border-blue-200">
        <div className="p-6">
          <div className="flex items-center mb-2">
            <Settings className="w-5 h-5 text-blue-600 mr-2" />
            <h3 className="font-semibold text-blue-900">À propos de la personnalisation</h3>
          </div>
          <p className="text-blue-800 text-sm">
            Ces paramètres apparaîtront sur vos factures et devis. Assurez-vous que les informations 
            sont correctes et à jour. Les couleurs personnalisées s'appliqueront à l'interface 
            utilisateur et aux documents générés.
          </p>
        </div>
      </Card>
    </div>
  );
};

export default SettingsPage;