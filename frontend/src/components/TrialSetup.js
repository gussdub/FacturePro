import React, { useState, useEffect } from 'react';
import { useAuth } from '../App';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Alert, AlertDescription } from './ui/alert';
import { CheckCircle, Clock, CreditCard } from 'lucide-react';

const TrialSetup = () => {
  const { user } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [trialInfo, setTrialInfo] = useState(null);

  useEffect(() => {
    fetchTrialInfo();
  }, []);

  const fetchTrialInfo = async () => {
    try {
      const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/subscription/user-status`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        setTrialInfo(data);
      }
    } catch (err) {
      console.error('Error fetching trial info:', err);
    }
  };

  const handleStartSubscription = async (plan = 'monthly') => {
    setLoading(true);
    setError('');

    try {
      const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/subscription/checkout`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({ plan })
      });

      if (response.ok) {
        const data = await response.json();
        window.location.href = data.checkout_url;
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Erreur lors de la création de la session de paiement');
      }
    } catch (err) {
      setError('Une erreur est survenue');
    } finally {
      setLoading(false);
    }
  };

  const handleContinueWithTrial = () => {
    // Redirect to dashboard to continue with trial
    window.location.href = '/dashboard';
  };

  if (!trialInfo) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <Card className="w-full max-w-2xl p-8 shadow-2xl border-0">
        <div className="text-center mb-8">
          <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" />
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Bienvenue dans FacturePro !
          </h1>
          <p className="text-gray-600">
            Votre compte a été créé avec succès. Configurons votre abonnement.
          </p>
        </div>

        {error && (
          <Alert className="mb-6 border-red-200 bg-red-50">
            <AlertDescription className="text-red-800">
              {error}
            </AlertDescription>
          </Alert>
        )}

        <div className="space-y-6">
          {/* Trial Info */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
            <div className="flex items-center space-x-3 mb-3">
              <Clock className="w-6 h-6 text-blue-600" />
              <h3 className="text-lg font-semibold text-blue-900">
                Essai gratuit actif
              </h3>
            </div>
            <p className="text-blue-700 mb-2">
              Vous avez {trialInfo.days_remaining} jours restants dans votre période d'essai gratuite.
            </p>
            <p className="text-sm text-blue-600">
              Profitez de toutes les fonctionnalités de FacturePro sans restrictions.
            </p>
          </div>

          {/* Subscription Options */}
          <div className="grid md:grid-cols-2 gap-4">
            {/* Monthly Plan */}
            <Card className="p-6 border-2 border-gray-200 hover:border-indigo-300 transition-colors">
              <div className="text-center">
                <h3 className="text-xl font-bold text-gray-900 mb-2">Mensuel</h3>
                <div className="mb-4">
                  <span className="text-3xl font-bold text-indigo-600">15$</span>
                  <span className="text-gray-600">/mois</span>
                </div>
                <p className="text-gray-600 text-sm mb-4">
                  Facturé mensuellement
                </p>
                <Button
                  onClick={() => handleStartSubscription('monthly')}
                  disabled={loading}
                  className="w-full bg-indigo-600 hover:bg-indigo-700"
                >
                  {loading ? (
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                  ) : (
                    <>
                      <CreditCard className="w-4 h-4 mr-2" />
                      Ajouter les informations de paiement
                    </>
                  )}
                </Button>
              </div>
            </Card>

            {/* Annual Plan */}
            <Card className="p-6 border-2 border-indigo-200 bg-indigo-50 hover:border-indigo-300 transition-colors relative">
              <div className="absolute -top-3 left-1/2 transform -translate-x-1/2">
                <span className="bg-indigo-600 text-white px-3 py-1 rounded-full text-sm font-medium">
                  2 mois gratuits
                </span>
              </div>
              <div className="text-center">
                <h3 className="text-xl font-bold text-gray-900 mb-2">Annuel</h3>
                <div className="mb-4">
                  <span className="text-3xl font-bold text-indigo-600">150$</span>
                  <span className="text-gray-600">/an</span>
                </div>
                <p className="text-gray-600 text-sm mb-4">
                  Économisez 30$ par année
                </p>
                <Button
                  onClick={() => handleStartSubscription('annual')}
                  disabled={loading}
                  className="w-full bg-indigo-600 hover:bg-indigo-700"
                >
                  {loading ? (
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                  ) : (
                    <>
                      <CreditCard className="w-4 h-4 mr-2" />
                      Ajouter les informations de paiement
                    </>
                  )}
                </Button>
              </div>
            </Card>
          </div>

          {/* Continue with Trial */}
          <div className="text-center pt-4">
            <Button
              onClick={handleContinueWithTrial}
              variant="outline"
              className="border-gray-300 hover:bg-gray-50"
            >
              Continuer avec l'essai gratuit
            </Button>
            <p className="text-xs text-gray-500 mt-2">
              Vous pouvez configurer votre abonnement à tout moment depuis les paramètres
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default TrialSetup;