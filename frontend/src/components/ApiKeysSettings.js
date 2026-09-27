import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { BACKEND_URL } from '../config';

// Clés API — intégration machine à machine (lot 0, ProFireManager).
//
// Le secret complet n'existe que le temps de cette page : le serveur n'en garde qu'un hachage
// et ne le renverra jamais. D'où l'encart d'avertissement, volontairement insistant.
//
// Les scopes affichés doivent rester alignés sur _API_KEY_ALLOWED_SCOPES côté serveur, qui
// refuse en 400 tout code hors de sa liste blanche. Cette liste-ci n'est qu'un confort de
// saisie : c'est le serveur qui décide.
const SCOPES = [
  { code: 'clients:read', label: 'Lire les clients' },
  { code: 'quotes:read', label: 'Lire les soumissions' },
  { code: 'quotes:write', label: 'Créer des soumissions en brouillon' },
  { code: 'invoices:read', label: 'Lire les factures' },
];

const TEAL = '#00796B';   // 5,32:1 sur blanc — le teal de marque #00A08C ne fait que 3,28:1

function ApiKeysSettings() {
  const [cles, setCles] = useState([]);
  const [chargement, setChargement] = useState(true);
  const [erreur, setErreur] = useState(null);
  const [nom, setNom] = useState('');
  const [scopesChoisis, setScopesChoisis] = useState(['clients:read']);
  const [creation, setCreation] = useState(false);
  const [secretAffiche, setSecretAffiche] = useState(null);

  const charger = useCallback(async () => {
    setChargement(true);
    try {
      const r = await axios.get(`${BACKEND_URL}/api/org/api-keys`);
      setCles(r.data.data || []);
      setErreur(null);
    } catch (e) {
      setErreur(e.response?.data?.detail || 'Impossible de charger les clés API.');
    } finally {
      setChargement(false);
    }
  }, []);

  useEffect(() => { charger(); }, [charger]);

  const basculerScope = (code) => {
    setScopesChoisis(prev => prev.includes(code)
      ? prev.filter(c => c !== code)
      : [...prev, code]);
  };

  const creer = async (e) => {
    e.preventDefault();
    setCreation(true);
    setErreur(null);
    try {
      const r = await axios.post(`${BACKEND_URL}/api/org/api-keys`,
        { name: nom.trim(), scopes: scopesChoisis });
      setSecretAffiche(r.data);   // seule et unique occasion de le montrer
      setNom('');
      setScopesChoisis(['clients:read']);
      await charger();
    } catch (e2) {
      setErreur(e2.response?.data?.detail || 'Création impossible.');
    } finally {
      setCreation(false);
    }
  };

  const revoquer = async (cle) => {
    // Irréversible du point de vue de l'intégration : tout appel portant cette clé cessera
    // immédiatement de fonctionner. D'où la confirmation nommant la clé.
    if (!window.confirm(
      `Révoquer « ${cle.name} » ?\n\nToute intégration utilisant cette clé cessera `
      + `immédiatement de fonctionner. Cette action est irréversible.`)) return;
    try {
      await axios.delete(`${BACKEND_URL}/api/org/api-keys/${cle.id}`);
      await charger();
    } catch (e) {
      setErreur(e.response?.data?.detail || 'Révocation impossible.');
    }
  };

  return (
    <div>
      <h3 style={{ fontSize: 18, color: '#1f2937', margin: '0 0 4px' }}>Clés API</h3>
      <p style={{ color: '#6b7280', fontSize: 14, marginTop: 0 }}>
        Une clé API permet à un autre logiciel de lire tes données de facturation sans passer par
        l'interface. Donne-lui uniquement les accès dont il a besoin, et révoque-la dès qu'elle
        ne sert plus.
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
            Copie cette clé maintenant. Elle ne sera plus jamais affichée.
          </p>
          <p style={{ margin: '0 0 10px', fontSize: 13, color: '#78350f' }}>
            FacturePro n'en conserve qu'une empreinte : personne, pas même nous, ne peut te la
            redonner. Si tu la perds, révoque-la et crées-en une nouvelle.
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
            J'ai copié la clé
          </button>
        </div>
      )}

      <form onSubmit={creer} style={{ background: '#f9fafb', border: '1px solid #e5e7eb',
                                      borderRadius: 8, padding: 16, marginBottom: 20 }}>
        <label style={{ display: 'block', fontSize: 14, fontWeight: 600, marginBottom: 6 }}>
          Nom de la clé
          <input type="text" value={nom} onChange={e => setNom(e.target.value)} required
                 placeholder="ProFireManager CRM"
                 style={{ display: 'block', width: '100%', maxWidth: 360, marginTop: 4,
                          padding: 8, borderRadius: 6, border: '1px solid #d1d5db',
                          fontWeight: 400 }} />
        </label>

        <fieldset style={{ border: 'none', padding: 0, margin: '14px 0 0' }}>
          <legend style={{ fontSize: 14, fontWeight: 600, padding: 0 }}>Accès accordés</legend>
          {SCOPES.map(s => (
            <label key={s.code} style={{ display: 'block', fontSize: 14, marginTop: 6 }}>
              <input type="checkbox" checked={scopesChoisis.includes(s.code)}
                     onChange={() => basculerScope(s.code)} />
              {' '}{s.label} <code style={{ fontSize: 12, color: '#6b7280' }}>{s.code}</code>
            </label>
          ))}
        </fieldset>

        <button type="submit" disabled={creation || !nom.trim() || !scopesChoisis.length}
                style={{ marginTop: 14, background: TEAL, color: '#fff', border: 'none',
                         padding: '10px 20px', borderRadius: 6, fontWeight: 600,
                         cursor: (creation || !nom.trim() || !scopesChoisis.length)
                           ? 'not-allowed' : 'pointer',
                         opacity: (creation || !nom.trim() || !scopesChoisis.length) ? 0.6 : 1 }}>
          {creation ? 'Création…' : 'Créer une clé'}
        </button>
      </form>

      {chargement ? (
        <p style={{ color: '#6b7280', fontSize: 14 }}>Chargement…</p>
      ) : cles.length === 0 ? (
        <p style={{ color: '#6b7280', fontSize: 14 }}>Aucune clé API pour l'instant.</p>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
            <thead>
              <tr style={{ textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>
                <th style={{ padding: '8px 10px' }}>Nom</th>
                <th style={{ padding: '8px 10px' }}>Préfixe</th>
                <th style={{ padding: '8px 10px' }}>Accès</th>
                <th style={{ padding: '8px 10px' }}>Dernière utilisation</th>
                <th style={{ padding: '8px 10px' }}>État</th>
                <th style={{ padding: '8px 10px' }} />
              </tr>
            </thead>
            <tbody>
              {cles.map(c => (
                <tr key={c.id} style={{ borderBottom: '1px solid #f3f4f6',
                                        opacity: c.revoked_at ? 0.55 : 1 }}>
                  <td style={{ padding: '8px 10px' }}>{c.name}</td>
                  <td style={{ padding: '8px 10px' }}>
                    <code style={{ fontSize: 12 }}>{c.key_prefix}…</code>
                  </td>
                  <td style={{ padding: '8px 10px', fontSize: 12, color: '#6b7280' }}>
                    {(c.scopes || []).join(', ')}
                  </td>
                  <td style={{ padding: '8px 10px', fontSize: 13 }}>
                    {c.last_used_at ? c.last_used_at.slice(0, 10) : 'jamais'}
                  </td>
                  <td style={{ padding: '8px 10px', fontSize: 13 }}>
                    {c.revoked_at
                      ? <span style={{ color: '#991b1b', fontWeight: 600 }}>Révoquée</span>
                      : <span style={{ color: TEAL, fontWeight: 600 }}>Active</span>}
                  </td>
                  <td style={{ padding: '8px 10px' }}>
                    {!c.revoked_at && (
                      <button type="button" onClick={() => revoquer(c)}
                              style={{ background: 'none', border: '1px solid #fca5a5',
                                       color: '#991b1b', padding: '6px 12px', borderRadius: 6,
                                       cursor: 'pointer', fontSize: 13 }}>
                        Révoquer
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default ApiKeysSettings;
