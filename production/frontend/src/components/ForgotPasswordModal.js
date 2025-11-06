import React, { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Alert, AlertDescription } from './ui/alert';
import { Mail, ArrowLeft, Key } from 'lucide-react';
import axios from 'axios';

const ForgotPasswordModal = ({ isOpen, onClose }) => {
  const [step, setStep] = useState('email'); // 'email' or 'reset'
  const [email, setEmail] = useState('');
  const [resetData, setResetData] = useState({
    token: '',
    new_password: '',
    confirm_password: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleSendResetEmail = async () => {
    setLoading(true);
    setError('');
    setSuccess('');

    try {
      const response = await axios.post(`${process.env.REACT_APP_BACKEND_URL}/api/auth/forgot-password`, {
        email: email
      });

      setSuccess('Un code de récupération a été généré. Utilisez le code affiché ci-dessous pour réinitialiser votre mot de passe.');
      setResetData(prev => ({ ...prev, token: response.data.reset_token }));
      setStep('reset');
    } catch (error) {
      setError(error.response?.data?.detail || 'Erreur lors de la génération du code de récupération');
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async () => {
    if (resetData.new_password !== resetData.confirm_password) {
      setError('Les mots de passe ne correspondent pas');
      return;
    }

    if (resetData.new_password.length < 6) {
      setError('Le mot de passe doit contenir au moins 6 caractères');
      return;
    }

    setLoading(true);
    setError('');

    try {
      await axios.post(`${process.env.REACT_APP_BACKEND_URL}/api/auth/reset-password`, {
        token: resetData.token,
        new_password: resetData.new_password
      });

      setSuccess('Mot de passe réinitialisé avec succès ! Vous pouvez maintenant vous connecter.');
      setTimeout(() => {
        onClose();
        setStep('email');
        setEmail('');
        setResetData({ token: '', new_password: '', confirm_password: '' });
        setError('');
        setSuccess('');
      }, 2000);
    } catch (error) {
      setError(error.response?.data?.detail || 'Erreur lors de la réinitialisation du mot de passe');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    onClose();
    setStep('email');
    setEmail('');
    setResetData({ token: '', new_password: '', confirm_password: '' });
    setError('');
    setSuccess('');
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center">
            <Key className="w-5 h-5 mr-2" />
            {step === 'email' ? 'Mot de passe oublié' : 'Nouveau mot de passe'}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {error && (
            <Alert className="border-red-200 bg-red-50">
              <AlertDescription className="text-red-800">{error}</AlertDescription>
            </Alert>
          )}

          {success && (
            <Alert className="border-green-200 bg-green-50">
              <AlertDescription className="text-green-800">{success}</AlertDescription>
            </Alert>
          )}

          {step === 'email' && (
            <>
              <div>
                <p className="text-sm text-gray-600 mb-4">
                  Entrez votre adresse email pour recevoir un code de récupération.
                </p>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Adresse email
                </label>
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="votre@email.com"
                  className="w-full"
                />
              </div>

              <div className="flex space-x-3">
                <Button onClick={handleSendResetEmail} disabled={loading || !email} className="flex-1">
                  {loading ? (
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                  ) : (
                    <Mail className="w-4 h-4 mr-2" />
                  )}
                  Générer le code
                </Button>
                <Button variant="outline" onClick={handleClose}>
                  Annuler
                </Button>
              </div>
            </>
          )}

          {step === 'reset' && (
            <>
              <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
                <p className="text-sm text-blue-800 mb-2">
                  <strong>Code de récupération :</strong>
                </p>
                <div className="bg-white border border-blue-300 rounded p-2 font-mono text-sm break-all">
                  {resetData.token}
                </div>
                <p className="text-xs text-blue-600 mt-2">
                  Copiez ce code et utilisez-le ci-dessous pour réinitialiser votre mot de passe.
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Code de récupération
                </label>
                <Input
                  value={resetData.token}
                  onChange={(e) => setResetData(prev => ({ ...prev, token: e.target.value }))}
                  placeholder="Collez le code ici"
                  className="font-mono text-xs"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Nouveau mot de passe
                </label>
                <Input
                  type="password"
                  value={resetData.new_password}
                  onChange={(e) => setResetData(prev => ({ ...prev, new_password: e.target.value }))}
                  placeholder="Nouveau mot de passe"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Confirmer le mot de passe
                </label>
                <Input
                  type="password"
                  value={resetData.confirm_password}
                  onChange={(e) => setResetData(prev => ({ ...prev, confirm_password: e.target.value }))}
                  placeholder="Confirmez le mot de passe"
                />
              </div>

              <div className="flex space-x-3">
                <Button
                  onClick={handleResetPassword}
                  disabled={loading || !resetData.token || !resetData.new_password || !resetData.confirm_password}
                  className="flex-1"
                >
                  {loading ? (
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                  ) : (
                    <Key className="w-4 h-4 mr-2" />
                  )}
                  Réinitialiser
                </Button>
                <Button variant="outline" onClick={() => setStep('email')}>
                  <ArrowLeft className="w-4 h-4 mr-2" />
                  Retour
                </Button>
              </div>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ForgotPasswordModal;