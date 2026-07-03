import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import { Trash2, UserPlus, X as XIcon, Pencil, Crown } from 'lucide-react';
import { BACKEND_URL, CURRENCY_LABELS } from '../config';
import TaxNumberInput from '../components/TaxNumberInput';
import InviteMemberModal from '../components/InviteMemberModal';
import { useAuth } from '../context/AuthContext';
import { PERMISSIONS_EDITABLE, PERMISSION_GROUPS, roleLabel } from '../constants/permissions';

const SettingsPage = () => {
  const [settings, setSettings] = useState({
    company_name: '', email: '', phone: '', address: '', city: '', postal_code: '', country: '',
    logo_url: '', primary_color: '#00A08C', secondary_color: '#1F2937',
    bn_number: '', gst_number: '', qst_number: '', hst_number: '', neq_number: '',
    default_due_days: 30, default_currency: 'CAD', entity_type: 'sole_proprietor', province: 'QC'
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef(null);

  // Onglets + gestion équipe (T14)
  const [activeTab, setActiveTab] = useState('company');
  const [orgData, setOrgData] = useState(null);
  const [orgLoading, setOrgLoading] = useState(false);
  const [invitations, setInvitations] = useState([]);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const { hasPermission, user: currentUser, role: currentUserRole } = useAuth();
  const canViewSettings = hasPermission('settings:read');
  const canEditSettings = hasPermission('settings:write');

  const fetchOrgData = useCallback(async () => {
    setOrgLoading(true);
    try {
      const [orgMe, invs] = await Promise.all([
        axios.get(`${BACKEND_URL}/api/org/me`),
        axios.get(`${BACKEND_URL}/api/org/invitations`),
      ]);
      setOrgData(orgMe.data);
      setInvitations(invs.data);
    } catch (e) {
      console.error(e);
    } finally {
      setOrgLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === 'team' && hasPermission('team:manage')) fetchOrgData();
  }, [activeTab, hasPermission, fetchOrgData]);

  useEffect(() => { fetchSettings(); }, []);

  const fetchSettings = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/settings/company`);
      setSettings(prev => ({ ...prev, ...response.data }));
    } catch (err) { setError('Erreur lors du chargement des parametres'); }
    finally { setLoading(false); }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true); setError(''); setSuccess('');
    try {
      await axios.put(`${BACKEND_URL}/api/settings/company`, settings);
      setSuccess('Parametres sauvegardes avec succes');
    } catch (err) { setError('Erreur lors de la sauvegarde'); }
    finally { setSaving(false); }
  };

  const uploadLogo = useCallback(async (file) => {
    if (!file) return;
    const allowed = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
    if (!allowed.includes(file.type)) {
      setError('Format accepte: JPG, PNG, GIF, WebP'); return;
    }
    if (file.size > 2 * 1024 * 1024) {
      setError('Le logo ne doit pas depasser 2 Mo'); return;
    }

    setUploading(true); setError(''); setSuccess('');
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await axios.post(`${BACKEND_URL}/api/settings/company/upload-logo-file`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setSettings(prev => ({ ...prev, logo_url: response.data.logo_url }));
      setSuccess('Logo televerse avec succes !');
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur lors du telechargement du logo');
    } finally {
      setUploading(false);
    }
  }, []);

  const handleDrag = useCallback((e) => {
    e.preventDefault(); e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true);
    else if (e.type === 'dragleave') setDragActive(false);
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault(); e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files?.[0]) uploadLogo(e.dataTransfer.files[0]);
  }, [uploadLogo]);

  const handleFileSelect = (e) => {
    if (e.target.files?.[0]) uploadLogo(e.target.files[0]);
  };

  const getLogoDisplayUrl = (url) => {
    if (!url) return null;
    if (url.startsWith('/api')) return `${BACKEND_URL}${url}`;
    if (url.startsWith('http')) return url;
    return null;
  };

  if (loading) return <div style={{ textAlign: 'center', padding: '60px' }}><p>Chargement des parametres...</p></div>;

  const inputStyle = { width: '100%', padding: '12px', border: '1px solid #d1d5db', borderRadius: '8px', boxSizing: 'border-box' };

  return (
    <div data-testid="settings-page">
      <div style={{ marginBottom: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
          <div style={{ fontSize: '32px', marginRight: '12px' }}>&#9881;&#65039;</div>
          <h1 style={{ fontSize: '32px', fontWeight: '800', color: '#1f2937', margin: 0 }}>Parametres</h1>
        </div>
        <p style={{ color: '#6b7280', margin: 0 }}>Configuration de votre entreprise</p>
      </div>

      {error && <div style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#b91c1c', padding: '16px', borderRadius: '12px', marginBottom: '20px' }}>{error}</div>}
      {success && <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', color: '#166534', padding: '16px', borderRadius: '12px', marginBottom: '20px' }}>{success}</div>}

      {/* Barre d'onglets */}
      <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid #e5e7eb', marginBottom: 24 }}>
        {canViewSettings && (
        <button
          type="button"
          onClick={() => setActiveTab('company')}
          data-testid="tab-company"
          style={{
            background: 'none', border: 'none', padding: '12px 20px', cursor: 'pointer',
            fontSize: 14, fontWeight: 600,
            color: activeTab === 'company' ? '#00A08C' : '#6b7280',
            borderBottom: activeTab === 'company' ? '2px solid #00A08C' : '2px solid transparent',
            marginBottom: -1,
          }}
        >
          Entreprise
        </button>
        )}
        {hasPermission('team:manage') && (
          <button
            type="button"
            onClick={() => setActiveTab('team')}
            data-testid="tab-team"
            style={{
              background: 'none', border: 'none', padding: '12px 20px', cursor: 'pointer',
              fontSize: 14, fontWeight: 600,
              color: activeTab === 'team' ? '#00A08C' : '#6b7280',
              borderBottom: activeTab === 'team' ? '2px solid #00A08C' : '2px solid transparent',
              marginBottom: -1,
            }}
          >
            Équipe
          </button>
        )}
      </div>

      {activeTab === 'team' && hasPermission('team:manage') && (
        <TeamManagementSection
          orgData={orgData}
          invitations={invitations}
          loading={orgLoading}
          onRefresh={fetchOrgData}
          onInvite={() => setShowInviteModal(true)}
          currentUserId={currentUser?.id}
          currentUserRole={currentUserRole}
        />
      )}
      {showInviteModal && (
        <InviteMemberModal
          onClose={() => setShowInviteModal(false)}
          onSuccess={() => { setShowInviteModal(false); fetchOrgData(); }}
        />
      )}

      {activeTab === 'company' && !canViewSettings && (
        <div style={{ padding: 40, textAlign: 'center', color: '#6b7280' }}>
          Vous n'avez pas l'autorisation de voir les paramètres de l'entreprise.
        </div>
      )}

      {activeTab === 'company' && canViewSettings && (
      <form onSubmit={handleSubmit}>
        {/* Logo Upload Section */}
        <div style={{ background: 'white', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '24px', marginBottom: '24px' }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: '700' }}>Logo de l'entreprise</h3>

          <div style={{ display: 'flex', gap: '24px', alignItems: 'flex-start' }}>
            {/* Current Logo Preview */}
            <div style={{
              width: '120px', height: '120px', borderRadius: '12px', overflow: 'hidden',
              border: '2px solid #e5e7eb', display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: '#f9fafb', flexShrink: 0
            }}>
              {getLogoDisplayUrl(settings.logo_url) ? (
                <img
                  src={getLogoDisplayUrl(settings.logo_url)}
                  alt="Logo actuel"
                  style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
                  onError={(e) => { e.target.style.display = 'none'; }}
                />
              ) : (
                <div style={{ textAlign: 'center', color: '#9ca3af', fontSize: '14px' }}>
                  <div style={{ fontSize: '32px', marginBottom: '4px' }}>&#128247;</div>
                  Aucun logo
                </div>
              )}
            </div>

            {/* Drag & Drop Zone */}
            <div
              data-testid="logo-dropzone"
              onDragEnter={handleDrag} onDragOver={handleDrag} onDragLeave={handleDrag} onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              style={{
                flex: 1, padding: '32px', borderRadius: '12px', textAlign: 'center', cursor: 'pointer',
                border: dragActive ? '2px dashed #00A08C' : '2px dashed #d1d5db',
                background: dragActive ? '#f0fdfa' : '#fafafa',
                transition: 'all 0.2s ease'
              }}
            >
              <input
                ref={fileInputRef} type="file" accept="image/jpeg,image/png,image/gif,image/webp"
                onChange={handleFileSelect} style={{ display: 'none' }}
                data-testid="logo-file-input"
              />
              {uploading ? (
                <div>
                  <div style={{ fontSize: '32px', marginBottom: '8px', animation: 'spin 1s linear infinite' }}>&#8987;</div>
                  <p style={{ color: '#00A08C', fontWeight: '600', margin: 0 }}>Telechargement en cours...</p>
                </div>
              ) : (
                <div>
                  <div style={{ fontSize: '40px', marginBottom: '8px' }}>&#9729;&#65039;</div>
                  <p style={{ fontWeight: '600', color: '#374151', margin: '0 0 4px 0', fontSize: '16px' }}>
                    Glissez-deposez votre logo ici
                  </p>
                  <p style={{ color: '#6b7280', margin: '0 0 12px 0', fontSize: '14px' }}>
                    ou cliquez pour parcourir vos fichiers
                  </p>
                  <span style={{
                    display: 'inline-block', background: '#00A08C', color: 'white',
                    padding: '8px 20px', borderRadius: '8px', fontSize: '14px', fontWeight: '600'
                  }}>
                    Choisir un fichier
                  </span>
                  <p style={{ color: '#9ca3af', margin: '8px 0 0 0', fontSize: '12px' }}>
                    JPG, PNG, GIF, WebP - Max 2 Mo
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Company Info */}
        <div style={{ background: 'white', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '24px', marginBottom: '24px' }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: '700' }}>Informations de l'entreprise</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Nom de l'entreprise *</label>
              <input type="text" value={settings.company_name} onChange={(e) => setSettings(prev => ({ ...prev, company_name: e.target.value }))}
                required data-testid="company-name-input" style={inputStyle} />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Email *</label>
              <input type="email" value={settings.email} onChange={(e) => setSettings(prev => ({ ...prev, email: e.target.value }))}
                required data-testid="company-email-input" style={inputStyle} />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Telephone</label>
              <input type="tel" value={settings.phone || ''} onChange={(e) => setSettings(prev => ({ ...prev, phone: e.target.value }))} style={inputStyle} />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Adresse (numero et rue)</label>
              <input type="text" value={settings.address || ''} onChange={(e) => setSettings(prev => ({ ...prev, address: e.target.value }))}
                placeholder="123 Rue Exemple" data-testid="company-address-input" style={inputStyle} />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Ville</label>
              <input type="text" value={settings.city || ''} onChange={(e) => setSettings(prev => ({ ...prev, city: e.target.value }))} style={inputStyle} />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Code postal</label>
              <input type="text" value={settings.postal_code || ''} onChange={(e) => setSettings(prev => ({ ...prev, postal_code: e.target.value }))}
                placeholder="H1A 1A1" data-testid="company-postal-code-input" style={inputStyle} />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Province / Pays</label>
              <input type="text" value={settings.country || ''} onChange={(e) => setSettings(prev => ({ ...prev, country: e.target.value }))}
                placeholder="Quebec, Canada" data-testid="company-country-input" style={inputStyle} />
            </div>
          </div>
        </div>

        {/* Entity Type */}
        <div style={{ background: 'white', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '24px', marginBottom: '24px' }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: '700' }}>Type d&#8217;entité</h3>
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 500, color: '#374151', marginBottom: 4 }}>
              Type d&#8217;entité fiscale
              <span
                title="Détermine le formulaire de déclaration fiscale utilisé pour exporter tes dépenses."
                style={{ cursor: 'help', color: '#6b7280', fontSize: 14 }}
              >
                ⓘ
              </span>
            </label>
            <select
              value={settings.entity_type || 'sole_proprietor'}
              onChange={(e) => setSettings(prev => ({ ...prev, entity_type: e.target.value }))}
              style={inputStyle}
            >
              <option value="sole_proprietor">Travailleur autonome (T2125)</option>
              <option value="corporation">Société par actions (T2)</option>
            </select>
          </div>
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 500, color: '#374151', marginBottom: 4 }}>
              Province
              <span
                title="Utilisée pour le calcul automatique des taxes sur tes dépenses (TPS/TVQ/TVH)."
                style={{ cursor: 'help', color: '#6b7280', fontSize: 14 }}
              >
                ⓘ
              </span>
            </label>
            <select
              value={settings.province || 'QC'}
              onChange={(e) => setSettings(prev => ({ ...prev, province: e.target.value }))}
              style={{
                width: '100%', padding: '12px',
                border: '1.5px solid #d1d5db', borderRadius: 8,
                fontSize: 14, background: 'white', boxSizing: 'border-box',
              }}
            >
              <option value="QC">Québec</option>
              <option value="ON">Ontario</option>
              <option value="BC">Colombie-Britannique</option>
              <option value="AB">Alberta</option>
              <option value="SK">Saskatchewan</option>
              <option value="MB">Manitoba</option>
              <option value="NB">Nouveau-Brunswick</option>
              <option value="NS">Nouvelle-Écosse</option>
              <option value="PE">Île-du-Prince-Édouard</option>
              <option value="NL">Terre-Neuve-et-Labrador</option>
              <option value="YT">Yukon</option>
              <option value="NU">Nunavut</option>
              <option value="NT">Territoires du Nord-Ouest</option>
            </select>
          </div>
          {/* Feature #12.1 — % bureau à domicile + véhicule : mécanismes T2125,
              pertinents uniquement pour les travailleurs autonomes non incorporés.
              Masqués pour une société par actions (voir aussi onglet T2125 caché). */}
          {(settings.entity_type || 'sole_proprietor') === 'sole_proprietor' && (
          <>
          <div style={{ marginTop: 16 }}>
            <label style={{ display: 'block', fontWeight: 500, marginBottom: 4 }}>
              Bureau à domicile — % surface utilisée pour l'entreprise
            </label>
            <input
              type="number"
              min="0" max="100" step="0.1"
              value={settings.home_office_percentage ?? 0}
              onChange={(e) => {
                const v = e.target.value;
                setSettings(prev => ({ ...prev,
                  home_office_percentage: v === '' ? 0 : parseFloat(v) || 0 }));
              }}
              placeholder="0"
              style={{ width: 120, padding: 8, border: '1px solid #d1d5db',
                       borderRadius: 6, fontSize: 14 }}
            />
            <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>
              Ex: bureau de 15 m² dans une maison de 100 m² = 15. Mettre 0 si bureau commercial.
            </div>
          </div>
          <div style={{ marginTop: 16 }}>
            <label style={{ display: 'block', fontWeight: 500, marginBottom: 4 }}>
              Véhicule — % utilisation commerciale
            </label>
            <input
              type="number"
              min="0" max="100" step="0.1"
              value={settings.vehicle_business_percentage ?? 0}
              onChange={(e) => {
                const v = e.target.value;
                setSettings(prev => ({ ...prev,
                  vehicle_business_percentage: v === '' ? 0 : parseFloat(v) || 0 }));
              }}
              placeholder="0"
              style={{ width: 120, padding: 8, border: '1px solid #d1d5db',
                       borderRadius: 6, fontSize: 14 }}
            />
            <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>
              Ex: 12 000 km commerciaux / 30 000 km total = 40. Mettre 0 si véhicule purement commercial.
            </div>
          </div>
          </>
          )}
        </div>

        {/* Tax Numbers */}
        <div style={{ background: 'white', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '24px', marginBottom: '24px' }}>
          <h3 style={{ margin: '0 0 8px 0', fontSize: '18px', fontWeight: '700' }}>Num&#233;ros officiels</h3>
          <p style={{ marginTop: 0, marginBottom: 16, fontSize: 13, color: '#6b7280' }}>
            Ces num&#233;ros apparaissent dans l&#8217;encadr&#233; &#171;&#160;Num&#233;ros d&#8217;enregistrement&#160;&#187; en bas des factures et devis.
          </p>
          <TaxNumberInput
            label="BN &#8212; Num&#233;ro d&#8217;entreprise f&#233;d&#233;ral"
            fieldName="bn_number"
            value={settings.bn_number}
            onChange={(v) => setSettings(prev => ({ ...prev, bn_number: v }))}
            placeholder="123456789"
            tooltip="9 chiffres attribu&#233;s par l&#8217;ARC"
          />
          <TaxNumberInput
            label="TPS / GST"
            fieldName="gst_number"
            value={settings.gst_number}
            onChange={(v) => setSettings(prev => ({ ...prev, gst_number: v }))}
            placeholder="123456789RT0001"
            tooltip="BN suivi de RT0001"
          />
          <TaxNumberInput
            label="TVQ / QST"
            fieldName="qst_number"
            value={settings.qst_number}
            onChange={(v) => setSettings(prev => ({ ...prev, qst_number: v }))}
            placeholder="1234567890TQ0001"
            tooltip="10 chiffres suivis de TQ0001 (Revenu Qu&#233;bec)"
          />
          <TaxNumberInput
            label="TVH / HST"
            fieldName="hst_number"
            value={settings.hst_number}
            onChange={(v) => setSettings(prev => ({ ...prev, hst_number: v }))}
            placeholder="123456789RT0001"
            tooltip="Pour ON, NB, NS, PE, NL (taxe harmonis&#233;e)"
          />
          <TaxNumberInput
            label="NEQ &#8212; Num&#233;ro d&#8217;entreprise Qu&#233;bec"
            fieldName="neq_number"
            value={settings.neq_number}
            onChange={(v) => setSettings(prev => ({ ...prev, neq_number: v }))}
            placeholder="1234567890"
            tooltip="10 chiffres attribu&#233;s par le REQ (corporations QC)"
          />
        </div>

        {/* Default Currency */}
        <div style={{ background: 'white', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '24px', marginBottom: '24px' }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: '18px', fontWeight: '700' }}>Devise par defaut</h3>
          <p style={{ color: '#6b7280', fontSize: '14px', margin: '0 0 16px' }}>Choisissez la devise utilisee par defaut pour vos factures et depenses. Vous pourrez toujours changer la devise par document.</p>
          <div style={{ maxWidth: '320px' }}>
            <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Devise</label>
            <select
              data-testid="default-currency-select"
              value={settings.default_currency || 'CAD'}
              onChange={(e) => setSettings(prev => ({ ...prev, default_currency: e.target.value }))}
              style={inputStyle}
            >
              {Object.entries(CURRENCY_LABELS).map(([code, label]) => (
                <option key={code} value={code}>{label}</option>
              ))}
            </select>
          </div>
        </div>

        {canEditSettings ? (
          <div style={{ textAlign: 'center' }}>
            <button type="submit" disabled={saving} data-testid="save-settings-btn" style={{
              background: saving ? '#9ca3af' : 'linear-gradient(135deg, #10b981, #047857)',
              color: 'white', border: 'none', padding: '16px 32px', borderRadius: '12px',
              cursor: saving ? 'not-allowed' : 'pointer', fontSize: '16px', fontWeight: '700'
            }}>{saving ? 'Sauvegarde...' : 'Sauvegarder tous les parametres'}</button>
          </div>
        ) : (
          <div style={{ textAlign: 'center', color: '#6b7280', fontSize: 14, padding: 12,
                        background: '#f8fafc', borderRadius: 8 }}>
            🔒 Lecture seule — vous n'avez pas l'autorisation de modifier les paramètres.
          </div>
        )}
      </form>
      )}

      <style>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
    </div>
  );
};

function TeamManagementSection({ orgData, invitations, loading, onRefresh, onInvite, currentUserId, currentUserRole }) {
  const [matrixEdits, setMatrixEdits] = useState({});
  const [savingRole, setSavingRole] = useState(null);

  if (loading || !orgData) return <div style={{ padding: 24 }}>Chargement…</div>;

  const { organization, members } = orgData;
  const rolePermissions = { ...organization.role_permissions, ...matrixEdits };

  const changeMemberRole = async (userId, newRole) => {
    if (!window.confirm(`Changer le rôle en ${newRole} ?`)) return;
    try {
      await axios.put(`${BACKEND_URL}/api/org/members/${userId}/role`, { role: newRole });
      onRefresh();
    } catch (e) {
      alert(e.response?.data?.detail || 'Erreur');
    }
  };

  const removeMember = async (userId, email) => {
    if (!window.confirm(`Retirer ${email} de l'organisation ?`)) return;
    try {
      await axios.delete(`${BACKEND_URL}/api/org/members/${userId}`);
      onRefresh();
    } catch (e) {
      alert(e.response?.data?.detail || 'Erreur');
    }
  };

  const promptEditEmail = async (currentEmail) => {
    const newEmail = window.prompt("Nouvelle adresse email :", currentEmail);
    if (!newEmail || newEmail.trim().toLowerCase() === currentEmail.toLowerCase()) return;
    try {
      await axios.put(`${BACKEND_URL}/api/auth/me/email`, {
        email: newEmail.trim().toLowerCase(),
      });
      onRefresh();
    } catch (e) {
      alert(e.response?.data?.detail || "Erreur lors du changement d'email");
    }
  };

  const transferOwnership = async (userId, email) => {
    const confirmed = window.confirm(
      `Rendre ${email} propriétaire ?\n\n` +
      `Tu deviendras Comptable — tu gardes l'accès aux dépenses/factures/rapports ` +
      `mais perds l'accès aux paramètres entreprise, à l'abonnement et à la gestion de l'équipe.\n\n` +
      `Cette action est immédiate.`
    );
    if (!confirmed) return;
    try {
      await axios.post(`${BACKEND_URL}/api/org/transfer-ownership`, {
        new_owner_user_id: userId,
      });
      onRefresh();
      // Force full reload so AuthContext re-fetches role/permissions
      window.location.reload();
    } catch (e) {
      alert(e.response?.data?.detail || 'Erreur lors du transfert');
    }
  };

  const revokeInvitation = async (invId, email) => {
    if (!window.confirm(`Révoquer l'invitation pour ${email} ?`)) return;
    try {
      await axios.delete(`${BACKEND_URL}/api/org/invitations/${invId}`);
      onRefresh();
    } catch (e) {
      alert(e.response?.data?.detail || 'Erreur');
    }
  };

  const togglePermission = (role, code) => {
    const current = rolePermissions[role] || [];
    const next = current.includes(code)
      ? current.filter(c => c !== code)
      : [...current, code];
    setMatrixEdits(prev => ({ ...prev, [role]: next }));
  };

  const saveRoleMatrix = async (role) => {
    setSavingRole(role);
    try {
      await axios.put(`${BACKEND_URL}/api/org/role-permissions`, {
        role, permissions: rolePermissions[role] || [],
      });
      setMatrixEdits(prev => {
        const next = { ...prev };
        delete next[role];
        return next;
      });
      onRefresh();
    } catch (e) {
      alert(e.response?.data?.detail || 'Erreur');
    } finally {
      setSavingRole(null);
    }
  };

  const isOwner = (uid) => organization.owner_id === uid;
  const isCurrentUserOwner = currentUserRole === 'owner';

  return (
    <div style={{ padding: 24 }} data-testid="team-management-section">
      {/* Section : Membres */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h3 style={{ margin: 0, fontSize: 18 }}>Membres actifs</h3>
        <button onClick={onInvite} data-testid="invite-member-btn" style={{
          background: '#00A08C', color: '#fff', border: 'none',
          padding: '8px 16px', borderRadius: 6, cursor: 'pointer',
          fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6,
        }}>
          <UserPlus size={16} /> Inviter un membre
        </button>
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14, marginBottom: 32 }}>
        <thead>
          <tr style={{ background: '#f9fafb', textAlign: 'left' }}>
            <th style={{ padding: 10 }}>Email</th>
            <th style={{ padding: 10 }}>Rôle</th>
            <th style={{ padding: 10 }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {members.map(m => (
            <tr key={m.id} style={{ borderTop: '1px solid #e5e7eb' }}>
              <td style={{ padding: 10 }}>
                {m.email}
                {isOwner(m.id) && <span style={{
                  marginLeft: 8, fontSize: 11, background: '#00A08C', color: '#fff',
                  padding: '2px 6px', borderRadius: 4,
                }}>Propriétaire</span>}
                {m.id === currentUserId && (
                  <button onClick={() => promptEditEmail(m.email)}
                          title="Modifier mon email"
                          data-testid="edit-own-email-btn"
                          style={{
                            marginLeft: 8, background: 'none', border: 'none',
                            cursor: 'pointer', color: '#6b7280', verticalAlign: 'middle',
                          }}>
                    <Pencil size={14} />
                  </button>
                )}
              </td>
              <td style={{ padding: 10 }}>
                {isOwner(m.id) ? (
                  <span style={{ color: '#6b7280' }}>Propriétaire</span>
                ) : (
                  <select value={m.role || 'viewer'}
                          onChange={e => changeMemberRole(m.id, e.target.value)}
                          style={{ padding: 6, border: '1px solid #d1d5db', borderRadius: 4 }}>
                    <option value="accountant">Comptable</option>
                    <option value="viewer">Lecteur</option>
                  </select>
                )}
              </td>
              <td style={{ padding: 10 }}>
                {isCurrentUserOwner && !isOwner(m.id) && m.id !== currentUserId && (
                  <button onClick={() => transferOwnership(m.id, m.email)}
                          data-testid={`transfer-ownership-btn-${m.id}`}
                          style={{
                            background: 'none', border: 'none', cursor: 'pointer',
                            color: '#b45309', display: 'flex', alignItems: 'center',
                            gap: 4, marginBottom: 4,
                          }}>
                    <Crown size={14} /> Transférer propriété
                  </button>
                )}
                {!isOwner(m.id) && m.id !== currentUserId && (
                  <button onClick={() => removeMember(m.id, m.email)} style={{
                    background: 'none', border: 'none', cursor: 'pointer',
                    color: '#991b1b', display: 'flex', alignItems: 'center', gap: 4,
                  }}>
                    <Trash2 size={14} /> Retirer
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Section : Invitations en cours */}
      <h3 style={{ margin: '0 0 16px', fontSize: 18 }}>Invitations en cours</h3>
      {invitations.length === 0 ? (
        <p style={{ color: '#6b7280', fontSize: 14, marginBottom: 32 }}>
          Aucune invitation en attente.
        </p>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14, marginBottom: 32 }}>
          <thead>
            <tr style={{ background: '#f9fafb', textAlign: 'left' }}>
              <th style={{ padding: 10 }}>Email</th>
              <th style={{ padding: 10 }}>Rôle</th>
              <th style={{ padding: 10 }}>Expire le</th>
              <th style={{ padding: 10 }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {invitations.map(inv => (
              <tr key={inv.id} style={{ borderTop: '1px solid #e5e7eb' }}>
                <td style={{ padding: 10 }}>{inv.email}</td>
                <td style={{ padding: 10 }}>{roleLabel(inv.role)}</td>
                <td style={{ padding: 10 }}>
                  {new Date(inv.expires_at).toLocaleDateString('fr-CA')}
                </td>
                <td style={{ padding: 10 }}>
                  <button onClick={() => revokeInvitation(inv.id, inv.email)} style={{
                    background: 'none', border: 'none', cursor: 'pointer',
                    color: '#991b1b', display: 'flex', alignItems: 'center', gap: 4,
                  }}>
                    <XIcon size={14} /> Révoquer
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* Section : Matrice permissions */}
      <h3 style={{ margin: '0 0 16px', fontSize: 18 }}>Rôles et permissions</h3>
      {['accountant', 'viewer'].map(role => (
        <RoleMatrixCard
          key={role}
          role={role}
          permissions={rolePermissions[role] || []}
          isDirty={matrixEdits[role] !== undefined}
          saving={savingRole === role}
          onToggle={(code) => togglePermission(role, code)}
          onSave={() => saveRoleMatrix(role)}
        />
      ))}
    </div>
  );
}


function RoleMatrixCard({ role, permissions, isDirty, saving, onToggle, onSave }) {
  return (
    <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16, marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h4 style={{ margin: 0, fontSize: 16 }}>{roleLabel(role)}</h4>
        {isDirty && (
          <button onClick={onSave} disabled={saving} style={{
            background: '#00A08C', color: '#fff', border: 'none',
            padding: '6px 14px', borderRadius: 6, cursor: 'pointer', fontWeight: 600,
          }}>
            {saving ? 'Enregistrement…' : 'Enregistrer'}
          </button>
        )}
      </div>
      {PERMISSION_GROUPS.map(group => (
        <div key={group} style={{ marginBottom: 10 }}>
          <div style={{ fontWeight: 600, fontSize: 13, color: '#374151', marginBottom: 4 }}>{group}</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
            {PERMISSIONS_EDITABLE.filter(p => p.group === group).map(p => (
              <label key={p.code} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={permissions.includes(p.code)}
                  onChange={() => onToggle(p.code)}
                />
                {p.label}
              </label>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export default SettingsPage;
