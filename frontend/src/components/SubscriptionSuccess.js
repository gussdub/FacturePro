import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { CheckCircle, Crown, ArrowRight } from 'lucide-react';
import axios from 'axios';

const SubscriptionSuccess = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState('checking');
  const [paymentInfo, setPaymentInfo] = useState(null);
  const sessionId = searchParams.get('session_id');

  useEffect(() => {
    if (sessionId) {
      checkPaymentStatus();
    } else {
      setStatus('error');
    }
  }, [sessionId]);

  const checkPaymentStatus = async () => {
    try {
      const API = process.env.REACT_APP_BACKEND_URL || import.meta.env.REACT_APP_BACKEND_URL;
      const response = await axios.get(`${API}/api/subscription/status/${sessionId}`);
      
      setPaymentInfo(response.data);
      
      if (response.data.payment_status === 'paid') {
        setStatus('success');
      } else if (response.data.status === 'expired') {
        setStatus('expired');
      } else {
        // Continue polling for a few more attempts
        setTimeout(checkPaymentStatus, 2000);
      }
    } catch (error) {
      console.error('Error checking payment status:', error);
      setStatus('error');
    }
  };

  const handleContinue = () => {
    navigate('/dashboard');
  };

  if (status === 'checking') {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <Card className="w-full max-w-md p-8 text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">
            Vérification du paiement...
          </h2>
          <p className="text-gray-600">
            Nous confirmons votre abonnement. Cela ne prendra qu'un moment.
          </p>
        </Card>
      </div>
    );
  }

  if (status === 'success') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-green-50 to-emerald-50 flex items-center justify-center p-4">
        <Card className="w-full max-w-md p-8 text-center">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
            <CheckCircle className="w-10 h-10 text-green-600" />
          </div>
          
          <h1 className="text-2xl font-bold text-gray-900 mb-2">
            Abonnement activé !
          </h1>
          
          <p className="text-gray-600 mb-6">
            Félicitations ! Votre abonnement FacturePro est maintenant actif. 
            Vous avez accès à toutes les fonctionnalités premium.
          </p>

          {paymentInfo && (
            <div className="bg-gray-50 rounded-lg p-4 mb-6 text-left">
              <h3 className="font-semibold text-gray-900 mb-2 flex items-center">
                <Crown className="w-4 h-4 mr-2 text-indigo-600" />
                Détails de l'abonnement
              </h3>
              <div className="text-sm space-y-1">
                <p><span className="text-gray-500">Montant :</span> {paymentInfo.amount_total / 100}$ {paymentInfo.currency.toUpperCase()}</p>
                <p><span className="text-gray-500">Status :</span> <span className="text-green-600 font-medium">Payé</span></p>
              </div>
            </div>
          )}

          <div className="space-y-3">
            <Button 
              onClick={handleContinue}
              className="w-full"
              size="lg"
            >
              Accéder au tableau de bord
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
            
            <Button 
              variant="outline"
              onClick={() => navigate('/subscription')}
              className="w-full"
            >
              Voir mon abonnement
            </Button>
          </div>

          <div className="mt-6 p-4 bg-indigo-50 rounded-lg">
            <p className="text-sm text-indigo-800">
              🎉 <strong>Bienvenue dans FacturePro Premium !</strong><br />
              Vous pouvez maintenant créer des factures illimitées, personnaliser votre branding, et bien plus encore.
            </p>
          </div>
        </Card>
      </div>
    );
  }

  // Error or expired states
  return (
    <div className="min-h-screen bg-red-50 flex items-center justify-center p-4">
      <Card className="w-full max-w-md p-8 text-center">
        <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-6">
          <Crown className="w-10 h-10 text-red-600" />
        </div>
        
        <h1 className="text-2xl font-bold text-gray-900 mb-2">
          {status === 'expired' ? 'Session expirée' : 'Erreur de paiement'}
        </h1>
        
        <p className="text-gray-600 mb-6">
          {status === 'expired' 
            ? 'Votre session de paiement a expiré. Veuillez réessayer.'
            : 'Une erreur est survenue lors du traitement de votre paiement.'
          }
        </p>

        <div className="space-y-3">
          <Button 
            onClick={() => navigate('/subscription')}
            className="w-full"
          >
            Réessayer
          </Button>
          
          <Button 
            variant="outline"
            onClick={() => navigate('/dashboard')}
            className="w-full"
          >
            Retour au tableau de bord
          </Button>
        </div>
      </Card>
    </div>
  );
};

export default SubscriptionSuccess;