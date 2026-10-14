import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { X, Mail } from 'lucide-react';
import { BACKEND_URL } from '../config';


export default function InviteMemberModal({ onClose, onSuccess, existingEmails = [] }) {
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('accountant');
  const [employees, setEmployees] = useState([]);
  const [employeeId, setEmployeeId] = useState('');

  // Fiches employés déjà saisies : on propose celles qui ont un courriel et qui ne sont ni
  // membres ni invitées, pour éviter de ressaisir le courriel.
  useEffect(() => {
    const taken = new Set(existingEmails.map(e => (e || '').trim().toLowerCase()));
    axios.get(`${BACKEND_URL}/api/employees`)
      .then(res => setEmployees((res.data || []).filter(emp => {
        const em = (emp.email || '').trim().toLowerCase();
        return em && !taken.has(em);
      })))
      .catch(() => setEmployees([]));  // sans permission employees:read : pas de sélecteur
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const pickEmployee = (id) => {
    setEmployeeId(id);
    const emp = employees.find(e => e.id === id);
    if (emp) {
      setEmail(emp.email.trim());
      setRole('employee');
    }
  };
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await axios.post(`${BACKEND_URL}/api/org/invitations`, {
        email: email.trim().toLowerCase(), role,
      });
      onSuccess();
    } catch (err) {
      setError(err.response?.data?.detail || 'Erreur lors de l\'envoi');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
      display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000,
    }}>
      <div style={{
        background: '#fff', borderRadius: 8, padding: 24,
        width: 480, maxWidth: '90vw', maxHeight: '90vh', overflow: 'auto',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h2 style={{ margin: 0, fontSize: 18, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Mail size={20} /> Inviter un membre
          </h2>
          <button onClick={onClose} style={{
            background: 'none', border: 'none', cursor: 'pointer', padding: 4,
          }}>
            <X size={20} />
          </button>
        </div>

        <form onSubmit={submit}>
          {employees.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: 'block', fontSize: 13, color: '#374151', marginBottom: 4, fontWeight: 600 }}>
                Choisir un employé existant
              </label>
              <select value={employeeId} onChange={e => pickEmployee(e.target.value)}
                      data-testid="invite-employee-select"
                      style={{
                        width: '100%', padding: 10, border: '1px solid #d1d5db',
                        borderRadius: 6, fontSize: 14,
                      }}>
                <option value="">— Saisir un courriel manuellement —</option>
                {employees.map(emp => (
                  <option key={emp.id} value={emp.id}>{emp.name || emp.email} ({emp.email})</option>
                ))}
              </select>
            </div>
          )}

          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: 13, color: '#374151', marginBottom: 4, fontWeight: 600 }}>
              Email
            </label>
            <input type="email" required autoFocus value={email}
                   onChange={e => { setEmail(e.target.value); setEmployeeId(''); }}
                   placeholder="comptable@exemple.com"
                   style={{
                     width: '100%', padding: 10, border: '1px solid #d1d5db',
                     borderRadius: 6, fontSize: 14, boxSizing: 'border-box',
                   }} />
          </div>

          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: 13, color: '#374151', marginBottom: 4, fontWeight: 600 }}>
              Rôle
            </label>
            <select value={role} onChange={e => setRole(e.target.value)}
                    style={{
                      width: '100%', padding: 10, border: '1px solid #d1d5db',
                      borderRadius: 6, fontSize: 14,
                    }}>
              <option value="accountant">Comptable — accès complet aux données métier</option>
              <option value="viewer">Lecteur — accès en lecture seule</option>
              <option value="employee">Employé — crée des soumissions et des clients</option>
            </select>
          </div>

          <div style={{ background: '#f3f4f6', padding: 12, borderRadius: 6, marginBottom: 16, fontSize: 13, color: '#6b7280' }}>
            Un email d'invitation sera envoyé avec un lien valide 7 jours. Le destinataire pourra créer son compte ou se connecter s'il en a déjà un.
          </div>

          {error && (
            <div style={{ background: '#fee2e2', color: '#991b1b', padding: 10, borderRadius: 6, marginBottom: 16, fontSize: 13 }}>
              {error}
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
            <button type="button" onClick={onClose} disabled={loading} style={{
              background: '#fff', border: '1px solid #d1d5db', color: '#374151',
              padding: '10px 16px', borderRadius: 6, cursor: 'pointer',
            }}>
              Annuler
            </button>
            <button type="submit" disabled={loading || !email} style={{
              background: '#00A08C', color: '#fff', border: 'none',
              padding: '10px 20px', borderRadius: 6, cursor: 'pointer', fontWeight: 600,
            }}>
              {loading ? 'Envoi…' : 'Envoyer l\'invitation'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
