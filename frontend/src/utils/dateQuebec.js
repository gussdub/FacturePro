// Helpers de date en fuseau America/Toronto (heure du Québec).
//
// Contexte : plusieurs endroits de l'app utilisaient `new Date().toISOString().slice(0, 10)`
// pour « la date d'aujourd'hui » — expression qui retourne toujours l'UTC. Entre
// 20 h et minuit ET (UTC-4 / UTC-5), UTC est déjà le lendemain → la balance de
// vérification, un paiement, une écriture ou une dépense saisie en soirée se
// retrouvait daté du jour suivant.

/**
 * Retourne la date d'aujourd'hui en heure du Québec, au format ISO `YYYY-MM-DD`.
 * La locale `en-CA` produit ce format sans manipulation supplémentaire.
 *
 * @returns {string} ex. "2026-07-09" (et non "2026-07-10" à 20 h ET)
 */
export function todayQuebecISO() {
  return new Date().toLocaleDateString('en-CA', { timeZone: 'America/Toronto' });
}
