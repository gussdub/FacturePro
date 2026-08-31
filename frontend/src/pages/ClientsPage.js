import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { BACKEND_URL } from '../config';
import { useAuth } from '../context/AuthContext';
import TaxNumberInput from '../components/TaxNumberInput';

const ClientsPage = () => {
  const { role } = useAuth();
  const isOwner = role === 'owner';
  const [clients, setClients] = useState([]);
  const [filteredClients, setFilteredClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingClient, setEditingClient] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [formData, setFormData] = useState({
    name: '', email: '', phone: '', address: '', city: '', postal_code: '', country: '',
    bn_number: '', gst_number: '', qst_number: '', hst_number: '', neq_number: '',
  });
  const [showTaxNumbers, setShowTaxNumbers] = useState(false);

  useEffect(() => { fetchClients(); }, []);

  useEffect(() => {
    const filtered = clients.filter(client =>
      client.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      client.email.toLowerCase().includes(searchTerm.toLowerCase())
    );
    setFilteredClients(filtered);
  }, [clients, searchTerm]);

  const fetchClients = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/clients`);
      setClients(response.data);
    } catch (err) {
      setError('Erreur lors du chargement des clients');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(''); setSuccess('');
    try {
      if (editingClient) {
        const res = await axios.put(`${BACKEND_URL}/api/clients/${editingClient.id}`, formData);
        // Mise à jour directe depuis la réponse (pas de refetch bloquant → réactif)
        setClients(prev => prev.map(c => (c.id === editingClient.id ? res.data : c)));
        setSuccess('Client modifie avec succes');
      } else {
        const res = await axios.post(`${BACKEND_URL}/api/clients`, formData);
        // Append (et non prepend) pour refléter l'ordre d'insertion du serveur — pas de saut de
        // position au rechargement de la page.
        setClients(prev => [...prev, res.data]);
        setSuccess('Client cree avec succes');
      }
      setShowForm(false); setEditingClient(null);
      setFormData({ name: '', email: '', phone: '', address: '', city: '', postal_code: '', country: '', bn_number: '', gst_number: '', qst_number: '', hst_number: '', neq_number: '' });
      setShowTaxNumbers(false);
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur lors de la sauvegarde');
    }
  };

  const handleEdit = (client) => {
    setEditingClient(client);
    setFormData({ name: client.name, email: client.email, phone: client.phone || '', address: client.address || '', city: client.city || '', postal_code: client.postal_code || '', country: client.country || '', bn_number: client.bn_number || '', gst_number: client.gst_number || '', qst_number: client.qst_number || '', hst_number: client.hst_number || '', neq_number: client.neq_number || '' });
    setShowForm(true);
  };

  const handleDelete = async (clientId) => {
    if (window.confirm('Etes-vous sur de vouloir supprimer ce client ?')) {
      try {
        await axios.delete(`${BACKEND_URL}/api/clients/${clientId}`);
        setSuccess('Client supprime avec succes');
        fetchClients();
      } catch (err) {
        setError('Erreur lors de la suppression');
      }
    }
  };

  // Effacement Loi 25 (art. 28.1)
  const [eraseTarget, setEraseTarget] = useState(null);
  const [eraseText, setEraseText] = useState('');
  const [erasing, setErasing] = useState(false);
  const doErase = async () => {
    if (!eraseTarget) return;
    setErasing(true); setError('');
    try {
      const r = await axios.post(`${BACKEND_URL}/api/clients/${eraseTarget.id}/erase`,
        { confirm_name: eraseText });
      const o = r.data.outcome;
      setSuccess(o === 'deleted'
        ? 'Client supprimé (aucun document lié).'
        : `Client anonymisé — ${r.data.invoices_retained} facture(s) et ${r.data.quotes_retained} soumission(s) conservées (rétention fiscale), nom gardé sur les documents émis.`);
      setEraseTarget(null); setEraseText('');
      fetchClients();
    } catch (err) {
      setError(err.response?.data?.detail || "Erreur lors de l'effacement");
    } finally {
      setErasing(false);
    }
  };

  const closeForm = () => {
    setShowForm(false); setEditingClient(null);
    setFormData({ name: '', email: '', phone: '', address: '', city: '', postal_code: '', country: '', bn_number: '', gst_number: '', qst_number: '', hst_number: '', neq_number: '' });
    setShowTaxNumbers(false);
  };

  if (loading) {
    return <div style={{ textAlign: 'center', padding: '64px' }}><p style={{ fontSize: '18px', color: '#6b7280' }}>Chargement des clients...</p></div>;
  }

  return (
    <div data-testid="clients-page">
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <div style={{ fontSize: '32px', marginRight: '12px' }}>👥</div>
          <div>
            <h1 style={{ fontSize: '32px', fontWeight: '800', color: '#1f2937', margin: 0 }}>Clients</h1>
            <p style={{ color: '#6b7280', margin: 0 }}>Gerez vos clients et leurs informations</p>
          </div>
        </div>
        <button onClick={() => setShowForm(true)} data-testid="add-client-btn" style={{
          background: 'linear-gradient(135deg, #00A08C, #008F7A)', color: 'white', border: 'none',
          padding: '14px 28px', borderRadius: '12px', cursor: 'pointer', fontWeight: '700', fontSize: '14px'
        }}>
          + Nouveau Client
        </button>
      </div>

      {/* Messages */}
      {error && <div style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#b91c1c', padding: '16px', borderRadius: '12px', marginBottom: '20px' }}>{error}</div>}
      {success && <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', color: '#166534', padding: '16px', borderRadius: '12px', marginBottom: '20px' }}>{success}</div>}

      {/* Search */}
      <div style={{ background: 'white', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '24px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ position: 'relative', flex: 1, maxWidth: '320px' }}>
            <input type="text" placeholder="Rechercher un client..." value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)} data-testid="search-clients-input"
              style={{ width: '100%', padding: '12px 12px 12px 44px', border: '1px solid #d1d5db', borderRadius: '8px', fontSize: '14px', boxSizing: 'border-box' }} />
            <div style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: '#9ca3af', fontSize: '16px' }}>🔍</div>
          </div>
          <div style={{ fontSize: '14px', color: '#6b7280' }}>{filteredClients.length} client{filteredClients.length > 1 ? 's' : ''}</div>
        </div>
      </div>

      {/* Clients List */}
      {filteredClients.length === 0 && !searchTerm ? (
        <div style={{ background: 'white', border: '2px dashed #d1d5db', borderRadius: '16px', padding: '64px', textAlign: 'center' }}>
          <div style={{ fontSize: '80px', marginBottom: '24px' }}>👥</div>
          <h3 style={{ fontSize: '24px', fontWeight: '700', color: '#374151', margin: '0 0 12px 0' }}>Aucun client enregistre</h3>
          <p style={{ color: '#6b7280', fontSize: '16px', margin: '0 0 32px 0' }}>Commencez par ajouter votre premier client</p>
          <button onClick={() => setShowForm(true)} style={{ background: '#00A08C', color: 'white', border: 'none', padding: '16px 32px', borderRadius: '12px', cursor: 'pointer', fontWeight: '700', fontSize: '16px' }}>
            Ajouter mon premier client
          </button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '20px' }}>
          {filteredClients.map(client => (
            <div key={client.id} data-testid={`client-card-${client.id}`} style={{
              background: 'white', border: '1px solid #e5e7eb', borderRadius: '12px', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '16px' }}>
                <h3 style={{ fontSize: '18px', fontWeight: '700', color: '#1f2937', margin: 0 }}>
                  {client.name}
                  {client.anonymized && (
                    <span style={{ marginLeft: 8, fontSize: 11, fontWeight: 600, color: '#6b7280',
                      background: '#f3f4f6', padding: '2px 8px', borderRadius: 10 }}>anonymisé (Loi 25)</span>
                  )}
                </h3>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button onClick={() => handleEdit(client)} data-testid={`edit-client-${client.id}`} style={{
                    background: '#f0f9ff', color: '#0369a1', border: 'none', padding: '6px 10px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px'
                  }}>Modifier</button>
                  <button onClick={() => handleDelete(client.id)} data-testid={`delete-client-${client.id}`} style={{
                    background: '#fef2f2', color: '#dc2626', border: 'none', padding: '6px 10px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px'
                  }}>Supprimer</button>
                  {isOwner && !client.anonymized && (
                    <button onClick={() => { setEraseTarget(client); setEraseText(''); }}
                      data-testid={`erase-client-${client.id}`} title="Effacement Loi 25 (art. 28.1)" style={{
                      background: '#fff7ed', color: '#c2410c', border: '1px solid #fed7aa', padding: '6px 10px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px'
                    }}>Effacer (Loi 25)</button>
                  )}
                </div>
              </div>
              <div style={{ fontSize: '14px', color: '#6b7280', lineHeight: '1.6' }}>
                <div style={{ marginBottom: '6px' }}>📧 {client.email}</div>
                {client.phone && <div style={{ marginBottom: '6px' }}>📱 {client.phone}</div>}
                {client.address && <div style={{ marginBottom: '6px' }}>📍 {client.address}</div>}
                {client.city && <div>🏙️ {client.city} {client.postal_code}</div>}
              </div>
            </div>
          ))}
        </div>
      )}

      {filteredClients.length === 0 && searchTerm && (
        <div style={{ background: 'white', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '40px', textAlign: 'center' }}>
          <h3 style={{ color: '#374151', margin: '0 0 8px 0' }}>Aucun client trouve</h3>
          <p style={{ color: '#6b7280', margin: 0 }}>Aucun client ne correspond a "{searchTerm}"</p>
        </div>
      )}

      {/* Effacement Loi 25 (art. 28.1) Modal */}
      {eraseTarget && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60, padding: '16px' }}>
          <div style={{ background: 'white', borderRadius: '16px', maxWidth: '520px', width: '100%', padding: '24px' }}>
            <h3 style={{ margin: '0 0 12px 0', color: '#1f2937' }}>Effacer les renseignements personnels (Loi 25)</h3>
            <p style={{ color: '#374151', fontSize: 14, lineHeight: 1.6, margin: '0 0 12px 0' }}>
              Cette action est <strong>irréversible</strong>. Les coordonnées et numéros de taxes de
              <strong> {eraseTarget.name} </strong> seront effacés et le client sera anonymisé.
            </p>
            <ul style={{ color: '#6b7280', fontSize: 13, lineHeight: 1.6, margin: '0 0 16px 18px', padding: 0 }}>
              <li>Les factures et soumissions déjà émises sont <strong>conservées</strong> (rétention fiscale ~6 ans).</li>
              <li>Le <strong>nom</strong> est gardé sur ces documents déjà émis.</li>
              <li>Si le client n'a aucun document lié, il est <strong>supprimé</strong> complètement.</li>
            </ul>
            <label style={{ display: 'block', fontSize: 13, color: '#374151', marginBottom: 6 }}>
              Pour confirmer, saisir le nom exact du client :
            </label>
            <input type="text" value={eraseText} onChange={(e) => setEraseText(e.target.value)}
              data-testid="erase-confirm-input" placeholder={eraseTarget.name}
              style={{ width: '100%', padding: '10px 12px', border: '1px solid #d1d5db', borderRadius: 8, fontSize: 14, marginBottom: 16, boxSizing: 'border-box' }} />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button onClick={() => { setEraseTarget(null); setEraseText(''); }} disabled={erasing} style={{
                background: '#f3f4f6', color: '#374151', border: 'none', padding: '10px 16px', borderRadius: 8, cursor: 'pointer', fontSize: 14 }}>Annuler</button>
              <button onClick={doErase} data-testid="erase-confirm-btn"
                disabled={erasing || eraseText.trim().toLowerCase() !== (eraseTarget.name || '').trim().toLowerCase()}
                style={{ background: erasing ? '#9ca3af' : '#c2410c', color: 'white', border: 'none', padding: '10px 16px', borderRadius: 8,
                  cursor: erasing ? 'wait' : 'pointer', fontSize: 14, opacity: (eraseText.trim().toLowerCase() !== (eraseTarget.name || '').trim().toLowerCase()) ? 0.5 : 1 }}>
                {erasing ? 'Effacement…' : 'Effacer définitivement'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Client Form Modal */}
      {showForm && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50, padding: '16px' }}>
          <div style={{ background: 'white', borderRadius: '16px', maxWidth: '600px', width: '100%', maxHeight: '90vh', overflow: 'auto' }}>
            <div style={{ padding: '24px 24px 0 24px', borderBottom: '1px solid #e5e7eb', marginBottom: '24px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={{ fontSize: '20px', fontWeight: '700', color: '#1f2937', margin: 0 }}>
                  {editingClient ? 'Modifier le client' : 'Nouveau Client'}
                </h3>
                <button onClick={closeForm} style={{ background: 'none', border: 'none', fontSize: '24px', cursor: 'pointer', color: '#6b7280' }}>x</button>
              </div>
            </div>
            <div style={{ padding: '0 24px 24px 24px' }}>
              <form onSubmit={handleSubmit}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: '#374151', marginBottom: '6px' }}>Nom complet *</label>
                    <input type="text" value={formData.name} onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                      placeholder="Jean Dupont" required data-testid="client-name-input"
                      style={{ width: '100%', padding: '12px', border: '1px solid #d1d5db', borderRadius: '8px', fontSize: '16px', boxSizing: 'border-box' }} />
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: '#374151', marginBottom: '6px' }}>Adresse email *</label>
                    <input type="email" value={formData.email} onChange={(e) => setFormData(prev => ({ ...prev, email: e.target.value }))}
                      placeholder="jean@entreprise.com" required data-testid="client-email-input"
                      style={{ width: '100%', padding: '12px', border: '1px solid #d1d5db', borderRadius: '8px', fontSize: '16px', boxSizing: 'border-box' }} />
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: '#374151', marginBottom: '6px' }}>Telephone</label>
                    <input type="tel" value={formData.phone} onChange={(e) => setFormData(prev => ({ ...prev, phone: e.target.value }))}
                      placeholder="514-123-4567"
                      style={{ width: '100%', padding: '12px', border: '1px solid #d1d5db', borderRadius: '8px', fontSize: '16px', boxSizing: 'border-box' }} />
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: '#374151', marginBottom: '6px' }}>Ville</label>
                    <input type="text" value={formData.city} onChange={(e) => setFormData(prev => ({ ...prev, city: e.target.value }))}
                      placeholder="Montreal"
                      style={{ width: '100%', padding: '12px', border: '1px solid #d1d5db', borderRadius: '8px', fontSize: '16px', boxSizing: 'border-box' }} />
                  </div>
                </div>
                <div style={{ marginBottom: '16px' }}>
                  <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: '#374151', marginBottom: '6px' }}>Adresse complete</label>
                  <input type="text" value={formData.address} onChange={(e) => setFormData(prev => ({ ...prev, address: e.target.value }))}
                    placeholder="123 Rue Example, App 456"
                    style={{ width: '100%', padding: '12px', border: '1px solid #d1d5db', borderRadius: '8px', fontSize: '16px', boxSizing: 'border-box' }} />
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '24px' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: '#374151', marginBottom: '6px' }}>Code postal</label>
                    <input type="text" value={formData.postal_code} onChange={(e) => setFormData(prev => ({ ...prev, postal_code: e.target.value }))}
                      placeholder="H1A 1A1" data-testid="client-postal-code-input"
                      style={{ width: '100%', padding: '12px', border: '1px solid #d1d5db', borderRadius: '8px', fontSize: '16px', boxSizing: 'border-box' }} />
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: '#374151', marginBottom: '6px' }}>Pays</label>
                    <input type="text" value={formData.country} onChange={(e) => setFormData(prev => ({ ...prev, country: e.target.value }))}
                      placeholder="Canada" data-testid="client-country-input"
                      style={{ width: '100%', padding: '12px', border: '1px solid #d1d5db', borderRadius: '8px', fontSize: '16px', boxSizing: 'border-box' }} />
                  </div>
                </div>
                <div style={{ marginTop: 16, borderTop: '1px solid #e5e7eb', paddingTop: 12 }}>
                  <button
                    type="button"
                    onClick={() => setShowTaxNumbers(!showTaxNumbers)}
                    style={{
                      background: 'none', border: 0, padding: 0, color: '#00A08C',
                      fontSize: 13, fontWeight: 500, cursor: 'pointer',
                      display: 'flex', alignItems: 'center', gap: 6,
                    }}
                    aria-expanded={showTaxNumbers}
                  >
                    <span>{showTaxNumbers ? '▼' : '▶'}</span>
                    Numéros officiels (B2B, optionnel)
                  </button>
                  {showTaxNumbers && (
                    <div style={{ marginTop: 16 }}>
                      <TaxNumberInput
                        label="BN — Numéro d'entreprise fédéral"
                        fieldName="bn_number"
                        value={formData.bn_number}
                        onChange={(v) => setFormData(prev => ({ ...prev, bn_number: v }))}
                        placeholder="123456789"
                        tooltip="9 chiffres attribués par l'ARC"
                      />
                      <TaxNumberInput
                        label="TPS / GST"
                        fieldName="gst_number"
                        value={formData.gst_number}
                        onChange={(v) => setFormData(prev => ({ ...prev, gst_number: v }))}
                        placeholder="123456789RT0001"
                        tooltip="BN suivi de RT0001"
                      />
                      <TaxNumberInput
                        label="TVQ / QST"
                        fieldName="qst_number"
                        value={formData.qst_number}
                        onChange={(v) => setFormData(prev => ({ ...prev, qst_number: v }))}
                        placeholder="1234567890TQ0001"
                        tooltip="10 chiffres + TQ0001 (Revenu Québec)"
                      />
                      <TaxNumberInput
                        label="TVH / HST"
                        fieldName="hst_number"
                        value={formData.hst_number}
                        onChange={(v) => setFormData(prev => ({ ...prev, hst_number: v }))}
                        placeholder="123456789RT0001"
                        tooltip="Pour ON, NB, NS, PE, NL"
                      />
                      <TaxNumberInput
                        label="NEQ — Numéro d'entreprise Québec"
                        fieldName="neq_number"
                        value={formData.neq_number}
                        onChange={(v) => setFormData(prev => ({ ...prev, neq_number: v }))}
                        placeholder="1234567890"
                        tooltip="10 chiffres attribués par le REQ (corporations QC)"
                      />
                    </div>
                  )}
                </div>
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', paddingTop: '16px', borderTop: '1px solid #e5e7eb' }}>
                  <button type="button" onClick={closeForm} style={{
                    background: 'white', color: '#374151', border: '1px solid #d1d5db', padding: '12px 24px', borderRadius: '8px', cursor: 'pointer', fontSize: '14px', fontWeight: '500'
                  }}>Annuler</button>
                  <button type="submit" data-testid="save-client-btn" style={{
                    background: 'linear-gradient(135deg, #00A08C, #008F7A)', color: 'white', border: 'none', padding: '12px 24px', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '14px'
                  }}>{editingClient ? 'Modifier le client' : 'Creer le client'}</button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ClientsPage;
