import { useState, useEffect } from 'react';
import { useAuth } from '../App';

export const useSubscription = () => {
  const { user } = useAuth();
  const [subscriptionStatus, setSubscriptionStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchSubscriptionStatus = async () => {
    if (!user) return;

    try {
      const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/subscription/user-status`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setSubscriptionStatus(data);
        setError(null);
      } else {
        setError('Erreur lors du chargement du statut d\'abonnement');
      }
    } catch (err) {
      setError('Erreur de connexion');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSubscriptionStatus();
  }, [user]);

  const refreshStatus = () => {
    setLoading(true);
    fetchSubscriptionStatus();
  };

  return {
    subscriptionStatus,
    loading,
    error,
    refreshStatus
  };
};

export default useSubscription;