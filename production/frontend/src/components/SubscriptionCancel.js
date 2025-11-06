import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { XCircle, ArrowLeft, Crown } from 'lucide-react';

const SubscriptionCancel = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <Card className="w-full max-w-md p-8 text-center">
        <div className="w-16 h-16 bg-orange-100 rounded-full flex items-center justify-center mx-auto mb-6">
          <XCircle className="w-10 h-10 text-orange-600" />
        </div>
        
        <h1 className="text-2xl font-bold text-gray-900 mb-2">
          Abonnement annulé
        </h1>
        
        <p className="text-gray-600 mb-6">
          Vous avez annulé votre abonnement. Aucun montant n'a été prélevé. 
          Vous pouvez toujours profiter de votre période d'essai gratuite.
        </p>

        <div className="bg-blue-50 rounded-lg p-4 mb-6">
          <div className="flex items-center justify-center mb-2">
            <Crown className="w-5 h-5 text-blue-600 mr-2" />
            <span className="font-semibold text-blue-900">Essai gratuit</span>
          </div>
          <p className="text-sm text-blue-800">
            Continuez à utiliser FacturePro gratuitement pendant votre période d'essai. 
            Vous pourrez souscrire à tout moment.
          </p>
        </div>

        <div className="space-y-3">
          <Button 
            onClick={() => navigate('/subscription')}
            className="w-full"
          >
            Voir les plans
          </Button>
          
          <Button 
            variant="outline"
            onClick={() => navigate('/dashboard')}
            className="w-full"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Retour au tableau de bord
          </Button>
        </div>

        <div className="mt-6 text-sm text-gray-500">
          <p>
            Des questions ? Contactez notre support pour obtenir de l'aide.
          </p>
        </div>
      </Card>
    </div>
  );
};

export default SubscriptionCancel;