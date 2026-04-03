import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { BACKEND_URL, formatCurrency } from '../config';
import { Check, Loader2 } from 'lucide-react';

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

  useEffect(() => { fetchSubscription(); }, [fetchSubscription]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const sessionId = params.get('session_id');
    if (!sessionId) return;

    let attempts = 0;
    const maxAttempts = 8;
    const pollInterval = 2500;

    const poll = async () => {
      if (attempts >= maxAttempts) { setPollingStatus('timeout'); return; }
      attempts++;
      setPollingStatus('polling');
      try {
        const res = await axios.get(`${BACKEND_URL}/api/subscription/checkout-status/${sessionId}`);
        if (res.data.payment_status === 'paid') {
          setPollingStatus('success');
          await fetchSubscription();
          if (refreshUser) refreshUser();
          window.history.replaceState({}, '', '/subscription');
          return;
        }
        if (res.data.status === 'expired') {
          setPollingStatus('expired');
          window.history.replaceState({}, '', '/subscription');
          return;
        }
        setTimeout(poll, pollInterval);
      } catch { setTimeout(poll, pollInterval); }
    };
    poll();
  }, [fetchSubscription, refreshUser]);

  const handleCheckout = async () => {
    setCheckoutLoading(true);
    try {
      const res = await axios.post(`${BACKEND_URL}/api/subscription/create-checkout`, {
        origin_url: window.location.origin
      });
      if (res.data.url) window.location.href = res.data.url;
    } catch (err) {
      alert(err.response?.data?.detail || 'Erreur lors de la creation de la session de paiement');
    } finally { setCheckoutLoading(false); }
  };

  if (loading) {
    return <div style={{ textAlign: 'center', padding: '60px' }}><p style={{ fontSize: '14px', color: '#a1a1aa' }}>Chargement...</p></div>;
  }

  const status = subscription?.subscription_status || user?.subscription_status || 'trial';
  const trialEnd = subscription?.trial_end_date || user?.trial_end_date;
  const isActive = status === 'active';
  const isTrial = status === 'trial';
  const isExpired = status === 'expired';
  const trialDaysLeft = trialEnd ? Math.max(0, Math.ceil((new Date(trialEnd) - new Date()) / (1000 * 60 * 60 * 24))) : 0;

  return (
    <div data-testid="subscription-page" style={{ maxWidth: '720px', margin: '0 auto' }}>
      {/* Polling banners */}
      {pollingStatus === 'polling' && (
        <div data-testid="payment-processing-banner" style={{
          background: '#fffbeb', border: '1px solid #fcd34d', borderRadius: '6px',
          padding: '12px 20px', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px'
        }}>
          <Loader2 size={16} strokeWidth={2} color="#92400e" style={{ animation: 'spin 1s linear infinite' }} />
          <span style={{ fontWeight: '600', color: '#92400e', fontSize: '13px' }}>Verification du paiement en cours...</span>
        </div>
      )}
      {pollingStatus === 'success' && (
        <div data-testid="payment-success-banner" style={{
          background: '#f0fdf4', border: '1px solid #16a34a', borderRadius: '6px',
          padding: '12px 20px', marginBottom: '20px', fontWeight: '600', color: '#065f46', fontSize: '13px'
        }}>Paiement reussi ! Votre abonnement est maintenant actif.</div>
      )}
      {pollingStatus === 'timeout' && (
        <div style={{
          background: '#fef2f2', border: '1px solid #dc2626', borderRadius: '6px',
          padding: '12px 20px', marginBottom: '20px', fontWeight: '600', color: '#991b1b', fontSize: '13px'
        }}>La verification du paiement a expire. Veuillez rafraichir la page.</div>
      )}

      {/* Current Status */}
      <div style={{
        background: '#ffffff', borderRadius: '6px', padding: '24px',
        border: `1px solid ${isActive ? '#16a34a' : isExpired ? '#dc2626' : '#e4e4e7'}`,
        marginBottom: '24px'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h2 style={{ fontSize: '18px', fontWeight: '700', color: '#09090b', margin: 0, letterSpacing: '-0.02em' }}>Votre abonnement</h2>
          <span data-testid="subscription-status-badge" style={{
            padding: '4px 12px', borderRadius: '4px', fontWeight: '600', fontSize: '12px',
            background: isActive ? '#f0fdf4' : isTrial ? '#fffbeb' : '#fef2f2',
            color: isActive ? '#16a34a' : isTrial ? '#92400e' : '#dc2626',
            border: `1px solid ${isActive ? '#bbf7d0' : isTrial ? '#fcd34d' : '#fecaca'}`
          }}>
            {isActive ? 'Actif' : isTrial ? 'Essai gratuit' : 'Expire'}
          </span>
        </div>

        {isTrial && (
          <p style={{ margin: 0, color: '#52525b', fontSize: '13px' }}>
            Il vous reste <strong>{trialDaysLeft} jour{trialDaysLeft !== 1 ? 's' : ''}</strong> d'essai gratuit.
            {trialDaysLeft <= 3 && ' Abonnez-vous pour continuer a utiliser FacturePro.'}
          </p>
        )}
        {isExpired && (
          <p style={{ margin: 0, color: '#dc2626', fontSize: '13px' }}>
            Votre essai gratuit a expire. Abonnez-vous pour continuer a utiliser toutes les fonctionnalites.
          </p>
        )}
        {isActive && (
          <p style={{ margin: 0, color: '#16a34a', fontSize: '13px' }}>
            Votre abonnement est actif. Acces complet a toutes les fonctionnalites.
          </p>
        )}

        {subscription?.last_payment && (
          <p style={{ fontSize: '12px', color: '#a1a1aa', marginTop: '12px', marginBottom: 0 }}>
            Dernier paiement: {formatCurrency(subscription.last_payment.amount)} le {new Date(subscription.last_payment.paid_at || subscription.last_payment.created_at).toLocaleDateString('fr-CA')}
          </p>
        )}
      </div>

      {/* Pricing Card */}
      {!isActive && (
        <div style={{
          background: '#09090b', borderRadius: '6px', padding: '36px', color: '#ffffff'
        }}>
          <div style={{ marginBottom: '28px' }}>
            <h3 style={{ fontSize: '22px', fontWeight: '700', margin: '0 0 6px', letterSpacing: '-0.03em' }}>FacturePro Pro</h3>
            <p style={{ color: '#71717a', fontSize: '13px', margin: 0 }}>Tout ce dont vous avez besoin pour gerer votre facturation</p>
          </div>

          <div style={{ marginBottom: '28px' }}>
            <span style={{ fontSize: '40px', fontWeight: '700', letterSpacing: '-0.04em' }}>15 $</span>
            <span style={{ fontSize: '14px', color: '#71717a', marginLeft: '4px' }}>CAD / mois</span>
          </div>

          <div style={{ marginBottom: '28px' }}>
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
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '6px 0' }}>
                <Check size={15} strokeWidth={2.5} color="#16a34a" />
                <span style={{ fontSize: '13px', color: '#d4d4d8' }}>{feature}</span>
              </div>
            ))}
          </div>

          <button
            data-testid="subscribe-btn"
            onClick={handleCheckout}
            disabled={checkoutLoading}
            style={{
              width: '100%', padding: '12px', background: '#ffffff', color: '#09090b',
              border: 'none', borderRadius: '6px', fontSize: '14px', fontWeight: '700',
              cursor: checkoutLoading ? 'not-allowed' : 'pointer',
              opacity: checkoutLoading ? 0.7 : 1,
              transition: 'all 0.15s ease'
            }}
          >
            {checkoutLoading ? 'Redirection vers Stripe...' : 'S\'abonner maintenant — 15 $/mois'}
          </button>

          <p style={{ textAlign: 'center', color: '#52525b', fontSize: '11px', marginTop: '14px', marginBottom: 0 }}>
            Paiement securise via Stripe. Annulez a tout moment.
          </p>
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
};

export default SubscriptionPage;
