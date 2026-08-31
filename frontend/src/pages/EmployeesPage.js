import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { BACKEND_URL } from '../config';
import { useAuth } from '../context/AuthContext';

const EmployeesPage = () => {
  const { role } = useAuth();
  const isOwner = role === 'owner';
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingEmployee, setEditingEmployee] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [formData, setFormData] = useState({ name: '', email: '', phone: '', employee_number: '', department: '' });

  useEffect(() => { fetchEmployees(); }, []);

  const fetchEmployees = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/employees`);
      setEmployees(response.data);
    } catch (err) { setError('Erreur lors du chargement des employes'); }
    finally { setLoading(false); }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(''); setSuccess('');
    try {
      if (editingEmployee) {
        await axios.put(`${BACKEND_URL}/api/employees/${editingEmployee.id}`, formData);
        setSuccess('Employe modifie avec succes');
      } else {
        await axios.post(`${BACKEND_URL}/api/employees`, formData);
        setSuccess('Employe cree avec succes');
      }
      setShowForm(false); setEditingEmployee(null);
      setFormData({ name: '', email: '', phone: '', employee_number: '', department: '' });
      fetchEmployees();
    } catch (err) { setError('Erreur lors de la sauvegarde'); }
  };

  const handleEdit = (emp) => {
    setEditingEmployee(emp);
    setFormData({ name: emp.name, email: emp.email, phone: emp.phone || '', employee_number: emp.employee_number || '', department: emp.department || '' });
    setShowForm(true);
  };

  const handleDelete = async (id) => {
    if (window.confirm('Supprimer cet employe ?')) {
      try { await axios.delete(`${BACKEND_URL}/api/employees/${id}`); setSuccess('Employe supprime'); fetchEmployees(); }
      catch (err) { setError('Erreur suppression'); }
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
      const r = await axios.post(`${BACKEND_URL}/api/employees/${eraseTarget.id}/erase`, { confirm_name: eraseText });
      setSuccess(r.data.outcome === 'deleted'
        ? 'Employé supprimé (aucun document lié).'
        : `Employé anonymisé — ${r.data.expenses_retained} dépense(s) et ${r.data.mileage_trips_retained} trajet(s) conservés (rétention fiscale).`);
      setEraseTarget(null); setEraseText('');
      fetchEmployees();
    } catch (err) {
      setError(err.response?.data?.detail || "Erreur lors de l'effacement");
    } finally { setErasing(false); }
  };

  const closeForm = () => { setShowForm(false); setEditingEmployee(null); setFormData({ name: '', email: '', phone: '', employee_number: '', department: '' }); };

  if (loading) return <div style={{ textAlign: 'center', padding: '64px' }}><p style={{ color: '#6b7280' }}>Chargement des employes...</p></div>;

  return (
    <div data-testid="employees-page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <div style={{ fontSize: '32px', marginRight: '12px' }}>👨‍💼</div>
          <div>
            <h1 style={{ fontSize: '32px', fontWeight: '800', color: '#1f2937', margin: 0 }}>Employes</h1>
            <p style={{ color: '#6b7280', margin: 0 }}>Gerez vos employes et leurs informations</p>
          </div>
        </div>
        <button onClick={() => setShowForm(true)} data-testid="add-employee-btn" style={{
          background: 'linear-gradient(135deg, #00A08C, #008F7A)', color: 'white', border: 'none',
          padding: '14px 28px', borderRadius: '12px', cursor: 'pointer', fontWeight: '700', fontSize: '14px'
        }}>+ Nouvel Employe</button>
      </div>

      {error && <div style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#b91c1c', padding: '16px', borderRadius: '12px', marginBottom: '20px' }}>{error}</div>}
      {success && <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', color: '#166534', padding: '16px', borderRadius: '12px', marginBottom: '20px' }}>{success}</div>}

      {employees.length === 0 ? (
        <div style={{ background: 'white', border: '2px dashed #d1d5db', borderRadius: '16px', padding: '64px', textAlign: 'center' }}>
          <div style={{ fontSize: '80px', marginBottom: '24px' }}>👨‍💼</div>
          <h3 style={{ fontSize: '24px', fontWeight: '700', color: '#374151', margin: '0 0 12px 0' }}>Aucun employe enregistre</h3>
          <button onClick={() => setShowForm(true)} style={{ background: '#00A08C', color: 'white', border: 'none', padding: '16px 32px', borderRadius: '12px', cursor: 'pointer', fontWeight: '700' }}>
            Ajouter mon premier employe
          </button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '20px' }}>
          {employees.map(emp => (
            <div key={emp.id} data-testid={`employee-card-${emp.id}`} style={{
              background: 'white', border: '1px solid #e5e7eb', borderRadius: '12px', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '16px' }}>
                <h3 style={{ fontSize: '18px', fontWeight: '700', color: '#1f2937', margin: 0 }}>
                  {emp.name}
                  {emp.anonymized && (
                    <span style={{ marginLeft: 8, fontSize: 11, fontWeight: 600, color: '#6b7280', background: '#f3f4f6', padding: '2px 8px', borderRadius: 10 }}>anonymisé (Loi 25)</span>
                  )}
                </h3>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button onClick={() => handleEdit(emp)} style={{ background: '#f0f9ff', color: '#0369a1', border: 'none', padding: '6px 10px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' }}>Modifier</button>
                  <button onClick={() => handleDelete(emp.id)} style={{ background: '#fef2f2', color: '#dc2626', border: 'none', padding: '6px 10px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' }}>Supprimer</button>
                  {isOwner && !emp.anonymized && (
                    <button onClick={() => { setEraseTarget(emp); setEraseText(''); }} data-testid={`erase-employee-${emp.id}`}
                      title="Effacement Loi 25 (art. 28.1)" style={{ background: '#fff7ed', color: '#c2410c', border: '1px solid #fed7aa', padding: '6px 10px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' }}>Effacer (Loi 25)</button>
                  )}
                </div>
              </div>
              <div style={{ fontSize: '14px', color: '#6b7280', lineHeight: '1.6' }}>
                <div style={{ marginBottom: '6px' }}>📧 {emp.email}</div>
                {emp.phone && <div style={{ marginBottom: '6px' }}>📱 {emp.phone}</div>}
                {emp.department && <div style={{ marginBottom: '6px' }}>🏢 {emp.department}</div>}
                {emp.employee_number && <div># {emp.employee_number}</div>}
              </div>
            </div>
          ))}
        </div>
      )}

      {eraseTarget && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60, padding: '16px' }}>
          <div style={{ background: 'white', borderRadius: '16px', maxWidth: '520px', width: '100%', padding: '24px' }}>
            <h3 style={{ margin: '0 0 12px 0', color: '#1f2937' }}>Effacer les renseignements personnels (Loi 25)</h3>
            <p style={{ color: '#374151', fontSize: 14, lineHeight: 1.6, margin: '0 0 12px 0' }}>
              Cette action est <strong>irréversible</strong>. Les coordonnées de
              <strong> {eraseTarget.name} </strong> seront effacées et l'employé sera anonymisé.
            </p>
            <ul style={{ color: '#6b7280', fontSize: 13, lineHeight: 1.6, margin: '0 0 16px 18px', padding: 0 }}>
              <li>Les dépenses et trajets déjà enregistrés sont <strong>conservés</strong> (rétention fiscale ~6 ans).</li>
              <li>Si l'employé n'a aucun document lié, il est <strong>supprimé</strong> complètement.</li>
            </ul>
            <label style={{ display: 'block', fontSize: 13, color: '#374151', marginBottom: 6 }}>Pour confirmer, saisir le nom exact de l'employé :</label>
            <input type="text" value={eraseText} onChange={(e) => setEraseText(e.target.value)} data-testid="erase-confirm-input" placeholder={eraseTarget.name}
              style={{ width: '100%', padding: '10px 12px', border: '1px solid #d1d5db', borderRadius: 8, fontSize: 14, marginBottom: 16, boxSizing: 'border-box' }} />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button onClick={() => { setEraseTarget(null); setEraseText(''); }} disabled={erasing} style={{ background: '#f3f4f6', color: '#374151', border: 'none', padding: '10px 16px', borderRadius: 8, cursor: 'pointer', fontSize: 14 }}>Annuler</button>
              <button onClick={doErase} data-testid="erase-confirm-btn"
                disabled={erasing || eraseText.trim().toLowerCase() !== (eraseTarget.name || '').trim().toLowerCase()}
                style={{ background: erasing ? '#9ca3af' : '#c2410c', color: 'white', border: 'none', padding: '10px 16px', borderRadius: 8, cursor: erasing ? 'wait' : 'pointer', fontSize: 14,
                  opacity: (eraseText.trim().toLowerCase() !== (eraseTarget.name || '').trim().toLowerCase()) ? 0.5 : 1 }}>
                {erasing ? 'Effacement…' : 'Effacer définitivement'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showForm && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50, padding: '16px' }}>
          <div style={{ background: 'white', borderRadius: '16px', maxWidth: '500px', width: '100%', padding: '32px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '24px' }}>
              <h3 style={{ fontSize: '20px', fontWeight: '700', margin: 0 }}>{editingEmployee ? 'Modifier' : 'Nouvel'} Employe</h3>
              <button onClick={closeForm} style={{ background: 'none', border: 'none', fontSize: '24px', cursor: 'pointer', color: '#6b7280' }}>x</button>
            </div>
            <form onSubmit={handleSubmit}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Nom *</label>
                  <input type="text" value={formData.name} onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                    required data-testid="employee-name-input"
                    style={{ width: '100%', padding: '12px', border: '1px solid #ddd', borderRadius: '8px', boxSizing: 'border-box' }} />
                </div>
                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Email *</label>
                  <input type="email" value={formData.email} onChange={(e) => setFormData(prev => ({ ...prev, email: e.target.value }))}
                    required data-testid="employee-email-input"
                    style={{ width: '100%', padding: '12px', border: '1px solid #ddd', borderRadius: '8px', boxSizing: 'border-box' }} />
                </div>
                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Telephone</label>
                  <input type="tel" value={formData.phone} onChange={(e) => setFormData(prev => ({ ...prev, phone: e.target.value }))}
                    style={{ width: '100%', padding: '12px', border: '1px solid #ddd', borderRadius: '8px', boxSizing: 'border-box' }} />
                </div>
                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Departement</label>
                  <input type="text" value={formData.department} onChange={(e) => setFormData(prev => ({ ...prev, department: e.target.value }))}
                    style={{ width: '100%', padding: '12px', border: '1px solid #ddd', borderRadius: '8px', boxSizing: 'border-box' }} />
                </div>
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', paddingTop: '16px', borderTop: '1px solid #e5e7eb' }}>
                <button type="button" onClick={closeForm} style={{ background: 'white', color: '#374151', border: '1px solid #d1d5db', padding: '12px 24px', borderRadius: '8px', cursor: 'pointer' }}>Annuler</button>
                <button type="submit" data-testid="save-employee-btn" style={{ background: '#00A08C', color: 'white', border: 'none', padding: '12px 24px', borderRadius: '8px', cursor: 'pointer', fontWeight: '600' }}>
                  {editingEmployee ? 'Modifier' : 'Creer'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default EmployeesPage;
