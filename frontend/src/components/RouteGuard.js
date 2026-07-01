import React from 'react';
import { useAuth } from '../context/AuthContext';

/**
 * Wrapper qui verifie la permission et affiche un ecran "Acces refuse" si absente.
 * Usage :
 *   <RouteGuard permission="expenses:read"><ExpensesPage /></RouteGuard>
 */
export default function RouteGuard({ permission, children, fallback = null }) {
  const { hasPermission } = useAuth();
  if (!hasPermission(permission)) {
    if (fallback) return fallback;
    return (
      <div data-testid="route-guard-denied" style={{ padding: 40, textAlign: 'center' }}>
        <h2 style={{ color: '#991b1b' }}>Acces refuse</h2>
        <p style={{ color: '#6b7280' }}>
          Vous n'avez pas la permission d'acceder a cette page.
          Contactez le proprietaire de l'organisation.
        </p>
        <a href="/dashboard" style={{
          display: 'inline-block', marginTop: 16,
          background: '#00A08C', color: '#fff', padding: '10px 20px',
          borderRadius: 6, textDecoration: 'none', fontWeight: 600,
        }}>Retour au tableau de bord</a>
      </div>
    );
  }
  return children;
}
