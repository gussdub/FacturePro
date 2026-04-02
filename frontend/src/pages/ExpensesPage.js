import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { BACKEND_URL, formatCurrency } from '../config';

const ExpensesPage = () => {
  const [expenses, setExpenses] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [formData, setFormData] = useState({
    employee_id: '', description: '', amount: '', category: '', expense_date: new Date().toISOString().split('T')[0], notes: '', receipt_url: ''
  });

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    try {
      const [expensesRes, employeesRes] = await Promise.all([
        axios.get(`${BACKEND_URL}/api/expenses`),
        axios.get(`${BACKEND_URL}/api/employees`)
      ]);
      setExpenses(expensesRes.data); setEmployees(employeesRes.data);
    } catch (err) { setError('Erreur lors du chargement'); }
    finally { setLoading(false); }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(''); setSuccess('');
    try {
      await axios.post(`${BACKEND_URL}/api/expenses`, { ...formData, amount: parseFloat(formData.amount) });
      setSuccess('Depense creee avec succes'); setShowForm(false);
      setFormData({ employee_id: '', description: '', amount: '', category: '', expense_date: new Date().toISOString().split('T')[0], notes: '', receipt_url: '' });
      fetchData();
    } catch (err) { setError('Erreur lors de la creation'); }
  };

  const updateStatus = async (id, status) => {
    try {
      await axios.put(`${BACKEND_URL}/api/expenses/${id}/status`, { status });
      setSuccess(`Depense ${status === 'approved' ? 'approuvee' : 'rejetee'}`);
      fetchData();
    } catch (err) { setError('Erreur'); }
  };

  const handleDelete = async (id) => {
    if (window.confirm('Supprimer cette depense ?')) {
      try { await axios.delete(`${BACKEND_URL}/api/expenses/${id}`); setSuccess('Depense supprimee'); fetchData(); }
      catch (err) { setError('Erreur suppression'); }
    }
  };

  const getEmployeeName = (id) => employees.find(e => e.id === id)?.name || 'N/A';

  const statusColors = {
    pending: { bg: '#fef3c7', color: '#92400e', label: 'En attente' },
    approved: { bg: '#dcfce7', color: '#166534', label: 'Approuvee' },
    rejected: { bg: '#fef2f2', color: '#b91c1c', label: 'Rejetee' }
  };

  if (loading) return <div style={{ textAlign: 'center', padding: '64px' }}><p style={{ color: '#6b7280' }}>Chargement des depenses...</p></div>;

  return (
    <div data-testid="expenses-page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <div style={{ fontSize: '32px', marginRight: '12px' }}>💳</div>
          <div>
            <h1 style={{ fontSize: '32px', fontWeight: '800', color: '#1f2937', margin: 0 }}>Depenses</h1>
            <p style={{ color: '#6b7280', margin: 0 }}>Systeme de depenses et remboursements</p>
          </div>
        </div>
        <button onClick={() => setShowForm(true)} data-testid="add-expense-btn" style={{
          background: 'linear-gradient(135deg, #00A08C, #008F7A)', color: 'white', border: 'none',
          padding: '14px 28px', borderRadius: '12px', cursor: 'pointer', fontWeight: '700', fontSize: '14px'
        }}>+ Nouvelle Depense</button>
      </div>

      {error && <div style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#b91c1c', padding: '16px', borderRadius: '12px', marginBottom: '20px' }}>{error}</div>}
      {success && <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', color: '#166534', padding: '16px', borderRadius: '12px', marginBottom: '20px' }}>{success}</div>}

      {expenses.length === 0 ? (
        <div style={{ background: 'white', border: '2px dashed #d1d5db', borderRadius: '16px', padding: '64px', textAlign: 'center' }}>
          <div style={{ fontSize: '80px', marginBottom: '24px' }}>💳</div>
          <h3 style={{ fontSize: '24px', fontWeight: '700', color: '#374151', margin: '0 0 12px 0' }}>Aucune depense enregistree</h3>
          <button onClick={() => setShowForm(true)} style={{ background: '#00A08C', color: 'white', border: 'none', padding: '16px 32px', borderRadius: '12px', cursor: 'pointer', fontWeight: '700' }}>
            Ajouter une depense
          </button>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '16px' }}>
          {expenses.map(exp => {
            const st = statusColors[exp.status] || statusColors.pending;
            return (
              <div key={exp.id} data-testid={`expense-card-${exp.id}`} style={{
                background: 'white', border: '1px solid #e5e7eb', borderRadius: '12px', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                  <div>
                    <h3 style={{ fontSize: '18px', fontWeight: '700', color: '#1f2937', margin: '0 0 8px 0' }}>{exp.description}</h3>
                    <p style={{ color: '#6b7280', margin: '4px 0', fontSize: '14px' }}>Employe: {getEmployeeName(exp.employee_id)}</p>
                    <p style={{ color: '#6b7280', margin: '4px 0', fontSize: '14px' }}>Date: {new Date(exp.expense_date).toLocaleDateString('fr-CA')}</p>
                    {exp.category && <p style={{ color: '#6b7280', margin: '4px 0', fontSize: '14px' }}>Categorie: {exp.category}</p>}
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '24px', fontWeight: '800', color: '#1f2937', marginBottom: '8px' }}>{formatCurrency(exp.amount)}</div>
                    <span style={{ background: st.bg, color: st.color, padding: '4px 8px', borderRadius: '6px', fontSize: '12px', fontWeight: '600' }}>{st.label}</span>
                    <div style={{ display: 'flex', gap: '8px', marginTop: '12px', justifyContent: 'flex-end' }}>
                      {exp.status === 'pending' && (
                        <>
                          <button onClick={() => updateStatus(exp.id, 'approved')} style={{ background: '#dcfce7', color: '#166534', border: 'none', padding: '6px 10px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' }}>Approuver</button>
                          <button onClick={() => updateStatus(exp.id, 'rejected')} style={{ background: '#fef2f2', color: '#dc2626', border: 'none', padding: '6px 10px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' }}>Rejeter</button>
                        </>
                      )}
                      <button onClick={() => handleDelete(exp.id)} style={{ background: '#fef2f2', color: '#dc2626', border: 'none', padding: '6px 10px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' }}>Supprimer</button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {showForm && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '20px' }}>
          <div style={{ background: 'white', padding: '32px', borderRadius: '16px', width: '100%', maxWidth: '500px' }}>
            <h3 style={{ margin: '0 0 24px 0', fontSize: '20px', fontWeight: '700' }}>Nouvelle Depense</h3>
            <form onSubmit={handleSubmit}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Employe</label>
                  <select value={formData.employee_id} onChange={(e) => setFormData(prev => ({ ...prev, employee_id: e.target.value }))}
                    data-testid="expense-employee-select"
                    style={{ width: '100%', padding: '12px', border: '1px solid #ddd', borderRadius: '8px', boxSizing: 'border-box' }}>
                    <option value="">Selectionner</option>
                    {employees.map(emp => <option key={emp.id} value={emp.id}>{emp.name}</option>)}
                  </select>
                </div>
                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Montant (CAD) *</label>
                  <input type="number" step="0.01" value={formData.amount} onChange={(e) => setFormData(prev => ({ ...prev, amount: e.target.value }))}
                    required data-testid="expense-amount-input"
                    style={{ width: '100%', padding: '12px', border: '1px solid #ddd', borderRadius: '8px', boxSizing: 'border-box' }} />
                </div>
              </div>
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Description *</label>
                <input type="text" value={formData.description} onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                  required placeholder="Description de la depense" data-testid="expense-description-input"
                  style={{ width: '100%', padding: '12px', border: '1px solid #ddd', borderRadius: '8px', boxSizing: 'border-box' }} />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Categorie</label>
                  <input type="text" value={formData.category} onChange={(e) => setFormData(prev => ({ ...prev, category: e.target.value }))}
                    placeholder="Transport, Repas..."
                    style={{ width: '100%', padding: '12px', border: '1px solid #ddd', borderRadius: '8px', boxSizing: 'border-box' }} />
                </div>
                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Date</label>
                  <input type="date" value={formData.expense_date} onChange={(e) => setFormData(prev => ({ ...prev, expense_date: e.target.value }))}
                    style={{ width: '100%', padding: '12px', border: '1px solid #ddd', borderRadius: '8px', boxSizing: 'border-box' }} />
                </div>
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', paddingTop: '16px', borderTop: '1px solid #e5e7eb' }}>
                <button type="button" onClick={() => setShowForm(false)} style={{ background: 'white', color: '#374151', border: '1px solid #d1d5db', padding: '12px 24px', borderRadius: '8px', cursor: 'pointer' }}>Annuler</button>
                <button type="submit" data-testid="save-expense-btn" style={{ background: '#00A08C', color: 'white', border: 'none', padding: '12px 24px', borderRadius: '8px', cursor: 'pointer', fontWeight: '600' }}>Creer la depense</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default ExpensesPage;
