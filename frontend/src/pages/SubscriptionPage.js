import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { BACKEND_URL, formatCurrency } from '../config';

const SubscriptionPage = () => {
  const { user, refreshUser } = useAuth();
  const [subscription, setSubscription] = useState(null);
  const [loading, setLoading] = useState(true);
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [pollingStatus, setPollingStatus] = useState(null);

  const fetchSubscription = useCallback(async () => {
    try {
      const res = await axios.get(`${BACKEND_URL}/api/subscription/current`);
      setSubscription(res.data);
    } catch (err) {
      console.error('Error fetching subscription:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSubscription();
  }, [fetchSubscription]);

  // Poll for checkout status if returning from Stripe
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const sessionId = params.get('session_id');
    if (!sessionId) return;

    let attempts = 0;
    const maxAttempts = 8;
    const pollInterval = 2500;

    const poll = async () => {
      if (attempts >= maxAttempts) {
        setPollingStatus('timeout');
        return;
      }
      attempts++;
      setPollingStatus('polling');
      try {
        const res = await axios.get(`${BACKEND_URL}/api/subscription/checkout-status/${sessionId}`);
        if (res.data.payment_status === 'paid') {
          setPollingStatus('success');
          await fetchSubscription();
          if (refreshUser) refreshUser();
          // Clean URL
          window.history.replaceState({}, '', '/subscription');
          return;
        }
        if (res.data.status === 'expired') {
          setPollingStatus('expired');
          window.history.replaceState({}, '', '/subscription');
          return;
        }
        setTimeout(poll, pollInterval);
      } catch {
        setTimeout(poll, pollInterval);
      }
    };
    poll();
  }, [fetchSubscription, refreshUser]);

  const handleCheckout = async () => {
    setCheckoutLoading(true);
    try {
      const res = await axios.post(`${BACKEND_URL}/api/subscription/create-checkout`, {
        origin_url: window.location.origin
      });
      if (res.data.url) {
        window.location.href = res.data.url;
      }
    } catch (err) {
      alert(err.response?.data?.detail || 'Erreur lors de la creation de la session de paiement');
    } finally {
      setCheckoutLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '60px' }}>
        <p style={{ fontSize: '18px', color: '#6b7280' }}>Chargement...</p>
      </div>
    );
  }

  const status = subscription?.subscription_status || user?.subscription_status || 'trial';
  const trialEnd = subscription?.trial_end_date || user?.trial_end_date;
  const isActive = status === 'active';
  const isTrial = status === 'trial';
  const isExpired = status === 'expired';

  const trialDaysLeft = trialEnd
    ? Math.max(0, Math.ceil((new Date(trialEnd) - new Date()) / (1000 * 60 * 60 * 24)))
    : 0;

  return (
    <div data-testid="subscription-page" style={{ maxWidth: '800px', margin: '0 auto' }}>
      {/* Polling status banner */}
      {pollingStatus === 'polling' && (
        <div data-testid="payment-processing-banner" style={{
          background: '#fef3c7', border: '1px solid #f59e0b', borderRadius: '12px',
          padding: '16px 24px', marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '12px'
        }}>
          <div style={{ width: '24px', height: '24px', border: '3px solid #f59e0b', borderTop: '3px solid transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
          <span style={{ fontWeight: '600', color: '#92400e' }}>Verification du paiement en cours...</span>
        </div>
      )}
      {pollingStatus === 'success' && (
        <div data-testid="payment-success-banner" style={{
          background: '#d1fae5', border: '1px solid #10b981', borderRadius: '12px',
          padding: '16px 24px', marginBottom: '24px', fontWeight: '600', color: '#065f46'
        }}>
          Paiement reussi ! Votre abonnement est maintenant actif.
        </div>
      )}
      {pollingStatus === 'timeout' && (
        <div style={{
          background: '#fef2f2', border: '1px solid #ef4444', borderRadius: '12px',
          padding: '16px 24px', marginBottom: '24px', fontWeight: '600', color: '#991b1b'
        }}>
          La verification du paiement a expire. Veuillez rafraichir la page ou contacter le support.
        </div>
      )}

      {/* Current Status Card */}
      <div style={{
        background: 'white', borderRadius: '16px', padding: '32px',
        boxShadow: '0 4px 24px rgba(0,0,0,0.06)', marginBottom: '32px',
        border: isActive ? '2px solid #10b981' : isTrial ? '2px solid #f59e0b' : '2px solid #ef4444'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
          <h2 style={{ fontSize: '24px', fontWeight: '800', color: '#1f2937', margin: 0 }}>
            Votre abonnement
          </h2>
          <span data-testid="subscription-status-badge" style={{
            padding: '6px 16px', borderRadius: '20px', fontWeight: '700', fontSize: '13px',
            background: isActive ? '#d1fae5' : isTrial ? '#fef3c7' : '#fef2f2',
            color: isActive ? '#065f46' : isTrial ? '#92400e' : '#991b1b'
          }}>
            {isActive ? 'Actif' : isTrial ? 'Essai gratuit' : 'Expire'}
          </span>
        </div>

        {isTrial && (
          <div style={{ background: '#fffbeb', borderRadius: '12px', padding: '20px', marginBottom: '20px' }}>
            <p style={{ margin: 0, color: '#92400e', fontSize: '15px' }}>
              <strong>Essai gratuit</strong> — Il vous reste <strong>{trialDaysLeft} jour{trialDaysLeft !== 1 ? 's' : ''}</strong> d'essai.
              {trialDaysLeft <= 3 && ' Abonnez-vous pour continuer a utiliser FacturePro.'}
            </p>
          </div>
        )}

        {isExpired && (
          <div style={{ background: '#fef2f2', borderRadius: '12px', padding: '20px', marginBottom: '20px' }}>
            <p style={{ margin: 0, color: '#991b1b', fontSize: '15px' }}>
              <strong>Votre essai gratuit a expire.</strong> Abonnez-vous pour continuer a utiliser toutes les fonctionnalites de FacturePro.
            </p>
          </div>
        )}

        {isActive && (
          <div style={{ background: '#f0fdf4', borderRadius: '12px', padding: '20px', marginBottom: '20px' }}>
            <p style={{ margin: 0, color: '#065f46', fontSize: '15px' }}>
              <strong>Votre abonnement est actif.</strong> Vous avez acces a toutes les fonctionnalites de FacturePro.
            </p>
          </div>
        )}

        {subscription?.last_payment && (
          <div style={{ fontSize: '14px', color: '#6b7280' }}>
            Dernier paiement: {formatCurrency(subscription.last_payment.amount)} le {new Date(subscription.last_payment.paid_at || subscription.last_payment.created_at).toLocaleDateString('fr-CA')}
          </div>
        )}
      </div>

      {/* Pricing Card */}
      {!isActive && (
        <div style={{
          background: 'linear-gradient(135deg, #1e293b 0%, #334155 100%)',
          borderRadius: '16px', padding: '40px', color: 'white',
          boxShadow: '0 8px 32px rgba(0,0,0,0.15)'
        }}>
          <div style={{ textAlign: 'center', marginBottom: '32px' }}>
            <h3 style={{ fontSize: '28px', fontWeight: '800', margin: '0 0 8px 0' }}>
              FacturePro Pro
            </h3>
            <p style={{ color: '#94a3b8', fontSize: '15px', margin: 0 }}>
              Tout ce dont vous avez besoin pour gerer votre facturation
            </p>
          </div>

          <div style={{ textAlign: 'center', marginBottom: '32px' }}>
            <span style={{ fontSize: '48px', fontWeight: '800' }}>15 $</span>
            <span style={{ fontSize: '18px', color: '#94a3b8' }}> CAD / mois</span>
          </div>

          <div style={{ marginBottom: '32px' }}>
            {[
              'Factures et soumissions illimitees',
              'Envoi par courriel avec PDF',
              'Suivi des paiements et rappels',
              'Import CSV des depenses',
              'Factures recurrentes automatiques',
              'Tableau de bord analytique',
              'Gestion des clients et produits',
              'Parametres d\'entreprise personnalisables'
            ].map((feature, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '8px 0' }}>
                <div style={{
                  width: '20px', height: '20px', borderRadius: '50%', background: '#00A08C',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '12px', flexShrink: 0
                }}>
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 6l3 3 5-5" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
                </div>
                <span style={{ fontSize: '15px' }}>{feature}</span>
              </div>
            ))}
          </div>

          <button
            data-testid="subscribe-btn"
            onClick={handleCheckout}
            disabled={checkoutLoading}
            style={{
              width: '100%', padding: '16px', background: '#00A08C', color: 'white',
              border: 'none', borderRadius: '12px', fontSize: '18px', fontWeight: '700',
              cursor: checkoutLoading ? 'not-allowed' : 'pointer',
              opacity: checkoutLoading ? 0.7 : 1,
              transition: 'all 0.3s ease'
            }}
          >
            {checkoutLoading ? 'Redirection vers Stripe...' : 'S\'abonner maintenant — 15 $/mois'}
          </button>

          <p style={{ textAlign: 'center', color: '#94a3b8', fontSize: '13px', marginTop: '16px' }}>
            Paiement securise via Stripe. Annulez a tout moment.
          </p>
        </div>
      )}

      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};

export default SubscriptionPage;
