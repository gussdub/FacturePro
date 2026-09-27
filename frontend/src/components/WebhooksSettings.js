import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { BACKEND_URL } from '../config';

// Webhooks sortants — intégration ProFireManager (lot 0, étape 5).
//
// Le secret d'un endpoint n'existe que le temps de cette page : le serveur ne le renvoie plus
// ensuite. Il sert à PFM pour vérifier la signature HMAC de chaque livraison.
//
// ⚠️ Les livraisons partent d'une boucle d'arrière-plan qui ne tourne QUE pendant que
// l'instance Render est éveillée. Un réessai planifié à +30 min ne partira qu'au prochain
// réveil : c'est dit à l'utilisateur plutôt que de le laisser croire à un calendrier garanti.
const EVENEMENTS = [
  { code: 'client.created', label: 'Client créé' },
  { code: 'client.updated', label: 'Client modifié' },
  { code: 'quote.created', label: 'Soumission créée' },
  { code: 'quote.status_changed', label: 'Statut de soumission changé' },
  { code: 'invoice.created', label: 'Facture créée' },
  { code: 'invoice.status_changed', label: 'Statut de facture changé' },
  { code: 'invoice.paid', label: 'Facture payée' },
];

const TEAL = '#00796B';   // 5,32:1 sur blanc

function WebhooksSettings() {
  const [endpoints, setEndpoints] = useState([]);
  const [chargement, setChargement] = useState(true);
  const [erreur, setErreur] = useState(null);
  const [url, setUrl] = useState('');
  const [choisis, setChoisis] = useState(['client.created']);
  const [creation, setCreation] = useState(false);
  const [secretAffiche, setSecretAffiche] = useState(null);

  const charger = useCallback(async () => {
    setChargement(true);
    try {
      const r = await axios.get(`${BACKEND_URL}/api/org/webhooks`);
      setEndpoints(r.data.data || []);
      setErreur(null);
    } catch (e) {
      setErreur(e.response?.data?.detail || 'Impossible de charger les webhooks.');
    } finally {
      setChargement(false);
    }
  }, []);

  useEffect(() => { charger(); }, [charger]);

  const creer = async (e) => {
    e.preventDefault();
    setCreation(true);
    setErreur(null);
    try {
      const r = await axios.post(`${BACKEND_URL}/api/org/webhooks`,
        { url: url.trim(), events: choisis });
      setSecretAffiche(r.data);
      setUrl('');
      setChoisis(['client.created']);
      await charger();
    } catch (e2) {
      setErreur(e2.response?.data?.detail || 'Création impossible.');
    } finally {
      setCreation(false);
    }
  };

  const tester = async (ep) => {
    try {
      await axios.post(`${BACKEND_URL}/api/org/webhooks/${ep.id}/test`);
      setErreur(null);
      window.alert('Ping mis en file. Il partira au prochain tour de la boucle d\'envoi '
        + '(au plus tard 30 secondes). Recharge pour voir le résultat.');
      await charger();
    } catch (e) {
      setErreur(e.response?.data?.detail || 'Test impossible.');
    }
  };

  const desactiver = async (ep) => {
    if (!window.confirm(`Désactiver ${ep.url} ?\n\nPlus aucun événement ne lui sera livré.`)) return;
    try {
      await axios.delete(`${BACKEND_URL}/api/org/webhooks/${ep.id}`);
      await charger();
    } catch (e) {
      setErreur(e.response?.data?.detail || 'Désactivation impossible.');
    }
  };

  return (
    <div style={{ marginTop: 32, paddingTop: 24, borderTop: '1px solid #e5e7eb' }}>
      <h3 style={{ fontSize: 18, color: '#1f2937', margin: '0 0 4px' }}>Webhooks</h3>
      <p style={{ color: '#6b7280', fontSize: 14, marginTop: 0 }}>
        FacturePro peut prévenir un autre logiciel dès qu'un client, une soumission ou une
        facture change. Chaque envoi est signé&nbsp;: le destinataire vérifie la signature avec
        le secret ci-dessous.
      </p>
      <p style={{ background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 6,
                  padding: '10px 12px', fontSize: 13, color: '#1e3a8a' }}>
        Les envois partent d'une boucle d'arrière-plan qui ne tourne que pendant que le serveur
        est éveillé. Sur l'hébergement actuel, il s'endort après 15 minutes d'inactivité&nbsp;:
        un réessai peut donc arriver plus tard que prévu.
      </p>

      {erreur && (
        <p role="alert" style={{ background: '#fee2e2', border: '1px solid #fca5a5',
                                 borderRadius: 6, padding: '10px 12px', color: '#991b1b',
                                 fontSize: 14 }}>{erreur}</p>
      )}

      {secretAffiche && (
        <div style={{ background: '#fef3c7', border: '1px solid #fcd34d', borderRadius: 8,
                      padding: 16, marginBottom: 20 }}>
          <p style={{ margin: '0 0 8px', fontWeight: 700, color: '#78350f' }}>
            Copie ce secret maintenant. Il ne sera plus jamais affiché.
          </p>
          <p style={{ margin: '0 0 10px', fontSize: 13, color: '#78350f' }}>
            Le logiciel destinataire en a besoin pour vérifier la signature de chaque envoi.
          </p>
          <code style={{ display: 'block', background: '#fff', border: '1px solid #fcd34d',
                         borderRadius: 6, padding: '10px 12px', fontSize: 13,
                         wordBreak: 'break-all', marginBottom: 10 }}>
            {secretAffiche.secret}
          </code>
          <button type="button"
                  onClick={() => navigator.clipboard?.writeText(secretAffiche.secret)}
                  style={{ background: TEAL, color: '#fff', border: 'none', padding: '8px 16px',
                           borderRadius: 6, fontWeight: 600, cursor: 'pointer', marginRight: 8 }}>
            Copier
          </button>
          <button type="button" onClick={() => setSecretAffiche(null)}
                  style={{ background: 'none', border: '1px solid #d1d5db', padding: '8px 16px',
                           borderRadius: 6, cursor: 'pointer' }}>
            J'ai copié le secret
          </button>
        </div>
      )}

      <form onSubmit={creer} style={{ background: '#f9fafb', border: '1px solid #e5e7eb',
                                      borderRadius: 8, padding: 16, marginBottom: 20 }}>
        <label style={{ display: 'block', fontSize: 14, fontWeight: 600, marginBottom: 6 }}>
          URL de réception (https obligatoire)
          <input type="url" value={url} onChange={e => setUrl(e.target.value)} required
                 placeholder="https://profiremanager.ca/api/webhooks/facturepro"
                 style={{ display: 'block', width: '100%', maxWidth: 460, marginTop: 4,
                          padding: 8, borderRadius: 6, border: '1px solid #d1d5db',
                          fontWeight: 400 }} />
        </label>
        <fieldset style={{ border: 'none', padding: 0, margin: '14px 0 0' }}>
          <legend style={{ fontSize: 14, fontWeight: 600, padding: 0 }}>Événements envoyés</legend>
          {EVENEMENTS.map(ev => (
            <label key={ev.code} style={{ display: 'block', fontSize: 14, marginTop: 6 }}>
              <input type="checkbox" checked={choisis.includes(ev.code)}
                     onChange={() => setChoisis(prev => prev.includes(ev.code)
                       ? prev.filter(c => c !== ev.code) : [...prev, ev.code])} />
              {' '}{ev.label} <code style={{ fontSize: 12, color: '#6b7280' }}>{ev.code}</code>
            </label>
          ))}
        </fieldset>
        <button type="submit" disabled={creation || !url.trim() || !choisis.length}
                style={{ marginTop: 14, background: TEAL, color: '#fff', border: 'none',
                         padding: '10px 20px', borderRadius: 6, fontWeight: 600,
                         cursor: (creation || !url.trim() || !choisis.length)
                           ? 'not-allowed' : 'pointer',
                         opacity: (creation || !url.trim() || !choisis.length) ? 0.6 : 1 }}>
          {creation ? 'Création…' : 'Ajouter un webhook'}
        </button>
      </form>

      {chargement ? (
        <p style={{ color: '#6b7280', fontSize: 14 }}>Chargement…</p>
      ) : endpoints.length === 0 ? (
        <p style={{ color: '#6b7280', fontSize: 14 }}>Aucun webhook configuré.</p>
      ) : endpoints.map(ep => (
        <div key={ep.id} style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 14,
                                  marginBottom: 12, opacity: ep.actif ? 1 : 0.55 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12,
                        flexWrap: 'wrap', alignItems: 'flex-start' }}>
            <div style={{ minWidth: 0 }}>
              <code style={{ fontSize: 13, wordBreak: 'break-all' }}>{ep.url}</code>
              <p style={{ fontSize: 12, color: '#6b7280', margin: '6px 0 0' }}>
                {(ep.events || []).join(', ')}
              </p>
              <p style={{ fontSize: 12, margin: '6px 0 0' }}>
                {ep.actif
                  ? <span style={{ color: TEAL, fontWeight: 600 }}>Actif</span>
                  : <span style={{ color: '#991b1b', fontWeight: 600 }}>Désactivé</span>}
                {ep.last_success_at && <> · dernier succès {ep.last_success_at.slice(0, 16)}</>}
              </p>
              {ep.last_error && (
                <p style={{ fontSize: 12, color: '#991b1b', margin: '6px 0 0' }}>
                  Dernière erreur : {ep.last_error}
                </p>
              )}
            </div>
            {ep.actif && (
              <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                <button type="button" onClick={() => tester(ep)}
                        style={{ background: 'none', border: `1px solid ${TEAL}`, color: TEAL,
                                 padding: '6px 12px', borderRadius: 6, cursor: 'pointer',
                                 fontSize: 13 }}>
                  Tester
                </button>
                <button type="button" onClick={() => desactiver(ep)}
                        style={{ background: 'none', border: '1px solid #fca5a5',
                                 color: '#991b1b', padding: '6px 12px', borderRadius: 6,
                                 cursor: 'pointer', fontSize: 13 }}>
                  Désactiver
                </button>
              </div>
            )}
          </div>

          {(ep.deliveries_recentes || []).length > 0 && (
            <div style={{ marginTop: 12, overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr style={{ textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>
                    <th style={{ padding: '6px 8px' }}>Livraison</th>
                    <th style={{ padding: '6px 8px' }}>État</th>
                    <th style={{ padding: '6px 8px' }}>Essais</th>
                    <th style={{ padding: '6px 8px' }}>Code</th>
                    <th style={{ padding: '6px 8px' }}>Erreur</th>
                  </tr>
                </thead>
                <tbody>
                  {ep.deliveries_recentes.map(d => (
                    <tr key={d.id} style={{ borderBottom: '1px solid #f3f4f6' }}>
                      <td style={{ padding: '6px 8px' }}>
                        {(d.created_at || '').slice(0, 16)}
                      </td>
                      <td style={{ padding: '6px 8px' }}>{d.status}</td>
                      <td style={{ padding: '6px 8px' }}>{d.attempts}</td>
                      <td style={{ padding: '6px 8px' }}>{d.last_status_code ?? '—'}</td>
                      <td style={{ padding: '6px 8px', color: '#991b1b' }}>
                        {d.last_error || ''}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export default WebhooksSettings;
