import React, { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Card } from './ui/card';
import { useAuth } from '../App';
import { User, Mail, Building, Phone, MapPin, Save } from 'lucide-react';

const UserProfileModal = ({ isOpen, onClose }) => {
  const { user } = useAuth();
  const [formData, setFormData] = useState({
    company_name: user?.company_name || '',
    email: user?.email || '',
    phone: '',
    address: '',
    city: '',
    postal_code: ''
  });

  const handleChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleSave = () => {
    // Ici vous pouvez implémenter la sauvegarde
    console.log('Saving profile:', formData);
    alert('Profil sauvegardé (fonctionnalité à implémenter)');
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center">
            <User className="w-5 h-5 mr-2" />
            Mon Profil
          </DialogTitle>
        </DialogHeader>
        
        <div className="space-y-6">
          {/* Avatar Section */}
          <div className="flex items-center space-x-4">
            <div className="w-16 h-16 bg-indigo-600 rounded-full flex items-center justify-center">
              <span className="text-xl font-bold text-white">
                {user?.company_name?.charAt(0)?.toUpperCase() || 'U'}
              </span>
            </div>
            <div>
              <h3 className="font-medium text-gray-900">{user?.company_name || 'Entreprise'}</h3>
              <p className="text-sm text-gray-500">{user?.email}</p>
            </div>
          </div>

          {/* Profile Form */}
          <Card className="p-4">
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  <Building className="w-4 h-4 inline mr-1" />
                  Nom de l'entreprise
                </label>
                <Input
                  value={formData.company_name}
                  onChange={(e) => handleChange('company_name', e.target.value)}
                  placeholder="Mon Entreprise"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  <Mail className="w-4 h-4 inline mr-1" />
                  Email
                </label>
                <Input
                  type="email"
                  value={formData.email}
                  onChange={(e) => handleChange('email', e.target.value)}
                  placeholder="email@entreprise.com"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  <Phone className="w-4 h-4 inline mr-1" />
                  Téléphone
                </label>
                <Input
                  value={formData.phone}
                  onChange={(e) => handleChange('phone', e.target.value)}
                  placeholder="514-123-4567"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  <MapPin className="w-4 h-4 inline mr-1" />
                  Adresse
                </label>
                <Input
                  value={formData.address}
                  onChange={(e) => handleChange('address', e.target.value)}
                  placeholder="123 Rue Principal"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Ville
                  </label>
                  <Input
                    value={formData.city}
                    onChange={(e) => handleChange('city', e.target.value)}
                    placeholder="Montréal"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Code postal
                  </label>
                  <Input
                    value={formData.postal_code}
                    onChange={(e) => handleChange('postal_code', e.target.value)}
                    placeholder="H1A 1A1"
                  />
                </div>
              </div>
            </div>
          </Card>

          {/* Action Buttons */}
          <div className="flex space-x-3">
            <Button onClick={handleSave} className="flex-1">
              <Save className="w-4 h-4 mr-2" />
              Sauvegarder
            </Button>
            <Button variant="outline" onClick={onClose}>
              Annuler
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default UserProfileModal;