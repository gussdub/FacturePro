import React from 'react';
import { Alert, AlertDescription } from './ui/alert';
import { Button } from './ui/button';
import { AlertTriangle, Clock, CreditCard } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../App';

const SubscriptionAlert = ({ subscriptionStatus }) => {
  const navigate = useNavigate();
  const { user } = useAuth();

  // Exempt users (never show subscription alerts)
  const EXEMPT_USERS = ["gussdub@gmail.com", "gussdub.prod@gmail.com"];
  if (user && EXEMPT_USERS.includes(user.email)) {
    return null; // Never show alerts for exempt users
  }

  if (!subscriptionStatus) {
    return null;
  }

  const handleUpgrade = () => {
    navigate('/subscription');
  };

  // Trial warning (3 days or less remaining) - show even if has_access is true
  if (subscriptionStatus.subscription_status === 'trial' && subscriptionStatus.days_remaining <= 3) {
    return (
      <Alert className="mb-6 border-yellow-200 bg-yellow-50">
        <Clock className="h-4 w-4 text-yellow-600" />
        <AlertDescription className="text-yellow-800 flex items-center justify-between">
          <span>
            Il vous reste {subscriptionStatus.days_remaining} jour(s) d'essai gratuit. 
            Ajoutez vos informations de paiement pour continuer après l'essai.
          </span>
          <Button
            onClick={handleUpgrade}
            size="sm"
            className="bg-yellow-600 hover:bg-yellow-700 text-white ml-4"
          >
            <CreditCard className="w-4 h-4 mr-2" />
            Configurer paiement
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  // Account is deactivated
  if (!subscriptionStatus.has_access) {
    return (
      <Alert className="mb-6 border-red-200 bg-red-50">
        <AlertTriangle className="h-4 w-4 text-red-600" />
        <AlertDescription className="text-red-800 flex items-center justify-between">
          <span>
            Votre abonnement a expiré. Veuillez renouveler votre abonnement pour continuer à utiliser FacturePro.
          </span>
          <Button
            onClick={handleUpgrade}
            size="sm"
            className="bg-red-600 hover:bg-red-700 text-white ml-4"
          >
            <CreditCard className="w-4 h-4 mr-2" />
            Renouveler
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  // Trial warning (3 days or less remaining)
  if (subscriptionStatus.subscription_status === 'trial' && subscriptionStatus.days_remaining <= 3) {
    return (
      <Alert className="mb-6 border-yellow-200 bg-yellow-50">
        <Clock className="h-4 w-4 text-yellow-600" />
        <AlertDescription className="text-yellow-800 flex items-center justify-between">
          <span>
            Il vous reste {subscriptionStatus.days_remaining} jour(s) d'essai gratuit. 
            Ajoutez vos informations de paiement pour continuer après l'essai.
          </span>
          <Button
            onClick={handleUpgrade}
            size="sm"
            className="bg-yellow-600 hover:bg-yellow-700 text-white ml-4"
          >
            <CreditCard className="w-4 h-4 mr-2" />
            Configurer paiement
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  // Cancelled subscription but still has access
  if (subscriptionStatus.subscription_status === 'cancelled' && subscriptionStatus.days_remaining > 0) {
    return (
      <Alert className="mb-6 border-orange-200 bg-orange-50">
        <AlertTriangle className="h-4 w-4 text-orange-600" />
        <AlertDescription className="text-orange-800 flex items-center justify-between">
          <span>
            Votre abonnement a été annulé. Vous avez encore accès pendant {subscriptionStatus.days_remaining} jour(s).
          </span>
          <Button
            onClick={handleUpgrade}
            size="sm"
            className="bg-orange-600 hover:bg-orange-700 text-white ml-4"
          >
            <CreditCard className="w-4 h-4 mr-2" />
            Réactiver
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  return null;
};

export default SubscriptionAlert;