import React, { useState, useEffect } from 'react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Alert, AlertDescription } from './ui/alert';
import { useAuth } from '../App';
import { Crown, Check, Zap, Shield, Sparkles, Clock } from 'lucide-react';
import axios from 'axios';

const SubscriptionPage = () => {
  const [subscription, setSubscription] = useState(null);
  const [trialDaysLeft, setTrialDaysLeft] = useState(14);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const { user } = useAuth();

  useEffect(() => {
    fetchSubscription();
  }, []);

  const fetchSubscription = async () => {
    try {
      const API = process.env.REACT_APP_BACKEND_URL || import.meta.env.REACT_APP_BACKEND_URL;
      const response = await axios.get(`${API}/api/subscription/current`);
      setSubscription(response.data.subscription);
      setTrialDaysLeft(response.data.trial_days_left);
    } catch (error) {
      console.error('Error fetching subscription:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubscribe = async (plan) => {
    setProcessing(true);
    try {
      const API = process.env.REACT_APP_BACKEND_URL || import.meta.env.REACT_APP_BACKEND_URL;
      const response = await axios.post(`${API}/api/subscription/checkout`, {
        plan: plan
      });

      if (response.data.checkout_url) {
        window.location.href = response.data.checkout_url;
      }
    } catch (error) {
      console.error('Error creating checkout:', error);
      alert('Erreur lors de la création du paiement. Veuillez réessayer.');
    } finally {
      setProcessing(false);
    }
  };

  const getStatusBadge = (status) => {
    const badges = {
      active: { text: 'Actif', color: 'bg-green-100 text-green-800' },
      trial: { text: 'Essai gratuit', color: 'bg-blue-100 text-blue-800' },
      canceled: { text: 'Annulé', color: 'bg-red-100 text-red-800' },
      past_due: { text: 'Impayé', color: 'bg-orange-100 text-orange-800' },
      suspended: { text: 'Suspendu', color: 'bg-gray-100 text-gray-800' }
    };
    
    const badge = badges[status] || badges.suspended;
    return (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${badge.color}`}>
        {badge.text}
      </span>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Abonnement</h1>
        <p className="text-gray-600">Gérez votre abonnement FacturePro</p>
      </div>

      {/* Current Subscription Status */}
      {subscription ? (
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-3">
              <div className="w-12 h-12 bg-indigo-100 rounded-lg flex items-center justify-center">
                <Crown className="w-6 h-6 text-indigo-600" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-gray-900">
                  FacturePro {subscription.plan === 'monthly' ? 'Mensuel' : 'Annuel'}
                </h3>
                <p className="text-sm text-gray-500">
                  {subscription.plan === 'monthly' ? '15$ / mois' : '150$ / an'}
                </p>
              </div>
            </div>
            {getStatusBadge(subscription.status)}
          </div>
          
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-500">Période actuelle :</span>
              <p className="font-medium">
                {new Date(subscription.current_period_start).toLocaleDateString('fr-CA')} - {' '}
                {new Date(subscription.current_period_end).toLocaleDateString('fr-CA')}
              </p>
            </div>
            <div>
              <span className="text-gray-500">Prochaine facturation :</span>
              <p className="font-medium">
                {new Date(subscription.current_period_end).toLocaleDateString('fr-CA')}
              </p>
            </div>
          </div>
        </Card>
      ) : (
        <Alert>
          <Clock className="w-4 h-4" />
          <AlertDescription>
            <strong>Essai gratuit :</strong> Il vous reste {trialDaysLeft} jours d'utilisation gratuite.
            Souscrivez pour continuer à utiliser FacturePro sans interruption.
          </AlertDescription>
        </Alert>
      )}

      {/* Pricing Plans */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Monthly Plan */}
        <Card className="p-6 border-2 hover:border-indigo-200 transition-colors">
          <div className="text-center mb-6">
            <div className="w-16 h-16 bg-indigo-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
              <Zap className="w-8 h-8 text-indigo-600" />
            </div>
            <h3 className="text-xl font-bold text-gray-900 mb-2">Plan Mensuel</h3>
            <div className="mb-4">
              <span className="text-3xl font-bold text-gray-900">15$</span>
              <span className="text-gray-500 ml-1">/mois</span>
            </div>
            <p className="text-gray-600 text-sm">Parfait pour démarrer</p>
          </div>

          <ul className="space-y-3 mb-6">
            <li className="flex items-center">
              <Check className="w-5 h-5 text-green-500 mr-3" />
              <span className="text-sm text-gray-700">Factures et soumissions illimitées</span>
            </li>
            <li className="flex items-center">
              <Check className="w-5 h-5 text-green-500 mr-3" />
              <span className="text-sm text-gray-700">Gestion des clients</span>
            </li>
            <li className="flex items-center">
              <Check className="w-5 h-5 text-green-500 mr-3" />
              <span className="text-sm text-gray-700">Personnalisation (logo, couleurs)</span>
            </li>
            <li className="flex items-center">
              <Check className="w-5 h-5 text-green-500 mr-3" />
              <span className="text-sm text-gray-700">Exports de données</span>
            </li>
          </ul>

          <Button 
            onClick={() => handleSubscribe('monthly')} 
            className="w-full"
            disabled={processing || (subscription?.plan === 'monthly' && subscription?.status === 'active')}
          >
            {processing ? 'Traitement...' : 'Choisir Mensuel'}
          </Button>
        </Card>

        {/* Annual Plan */}
        <Card className="p-6 border-2 border-indigo-500 bg-gradient-to-br from-indigo-50 to-purple-50 relative">
          <div className="absolute -top-3 left-1/2 transform -translate-x-1/2">
            <span className="bg-indigo-500 text-white px-3 py-1 rounded-full text-xs font-medium flex items-center">
              <Sparkles className="w-3 h-3 mr-1" />
              Économisez 2 mois !
            </span>
          </div>
          
          <div className="text-center mb-6 pt-2">
            <div className="w-16 h-16 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
              <Crown className="w-8 h-8 text-white" />
            </div>
            <h3 className="text-xl font-bold text-gray-900 mb-2">Plan Annuel</h3>
            <div className="mb-2">
              <span className="text-3xl font-bold text-gray-900">150$</span>
              <span className="text-gray-500 ml-1">/an</span>
            </div>
            <div className="text-sm">
              <span className="text-gray-500 line-through">180$</span>
              <span className="text-green-600 font-medium ml-2">Économisez 30$</span>
            </div>
            <p className="text-gray-600 text-sm mt-2">Le meilleur rapport qualité-prix</p>
          </div>

          <ul className="space-y-3 mb-6">
            <li className="flex items-center">
              <Check className="w-5 h-5 text-green-500 mr-3" />
              <span className="text-sm text-gray-700">Tout du plan mensuel</span>
            </li>
            <li className="flex items-center">
              <Check className="w-5 h-5 text-green-500 mr-3" />
              <span className="text-sm text-gray-700">2 mois gratuits (économie de 20$)</span>
            </li>
            <li className="flex items-center">
              <Shield className="w-5 h-5 text-indigo-500 mr-3" />
              <span className="text-sm text-gray-700">Support prioritaire</span>
            </li>
            <li className="flex items-center">
              <Shield className="w-5 h-5 text-indigo-500 mr-3" />
              <span className="text-sm text-gray-700">Nouvelles fonctionnalités en avant-première</span>
            </li>
          </ul>

          <Button 
            onClick={() => handleSubscribe('annual')} 
            className="w-full bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700"
            disabled={processing || (subscription?.plan === 'annual' && subscription?.status === 'active')}
          >
            {processing ? 'Traitement...' : 'Choisir Annuel'}
          </Button>
        </Card>
      </div>

      {/* Features included */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Toutes les fonctionnalités incluses
        </h3>
        <div className="grid md:grid-cols-2 gap-4">
          <div className="flex items-start space-x-3">
            <Check className="w-5 h-5 text-green-500 mt-0.5" />
            <div>
              <h4 className="font-medium text-gray-900">Facturation complète</h4>
              <p className="text-sm text-gray-600">Créez des factures et soumissions professionnelles</p>
            </div>
          </div>
          <div className="flex items-start space-x-3">
            <Check className="w-5 h-5 text-green-500 mt-0.5" />
            <div>
              <h4 className="font-medium text-gray-900">Gestion client</h4>
              <p className="text-sm text-gray-600">Base de données clients complète</p>
            </div>
          </div>
          <div className="flex items-start space-x-3">
            <Check className="w-5 h-5 text-green-500 mt-0.5" />
            <div>
              <h4 className="font-medium text-gray-900">Personnalisation</h4>
              <p className="text-sm text-gray-600">Logo, couleurs, et branding personnalisés</p>
            </div>
          </div>
          <div className="flex items-start space-x-3">
            <Check className="w-5 h-5 text-green-500 mt-0.5" />
            <div>
              <h4 className="font-medium text-gray-900">Exports & Rapports</h4>
              <p className="text-sm text-gray-600">Analysez vos données financières</p>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default SubscriptionPage;