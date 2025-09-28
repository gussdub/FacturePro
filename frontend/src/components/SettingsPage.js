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

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
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
    default_due_days: 30
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

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
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  URL du logo
                </label>
                <Input
                  value={settings.logo_url}
                  onChange={(e) => handleChange('logo_url', e.target.value)}
                  placeholder="https://monentreprise.fr/logo.png"
                  data-testid="logo-url-input"
                  className="form-input"
                />
                <p className="text-sm text-gray-500 mt-1">
                  Entrez l'URL de votre logo ou laissez vide pour utiliser le nom de l'entreprise
                </p>
              </div>

              {settings.logo_url && (
                <div className="mt-4">
                  <p className="text-sm font-medium text-gray-700 mb-2">Aperçu du logo:</p>
                  <div className="w-32 h-32 border-2 border-dashed border-gray-300 rounded-lg flex items-center justify-center bg-gray-50">
                    <img
                      src={settings.logo_url}
                      alt="Logo de l'entreprise"
                      className="max-w-full max-h-full object-contain"
                      onError={(e) => {
                        e.target.style.display = 'none';
                        e.target.nextSibling.style.display = 'block';
                      }}
                    />
                    <span className="text-gray-400 text-sm" style={{display: 'none'}}>
                      Erreur de chargement
                    </span>
                  </div>
                </div>
              )}
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