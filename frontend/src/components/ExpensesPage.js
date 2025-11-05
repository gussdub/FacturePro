import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Alert, AlertDescription } from './ui/alert';
import { Badge } from './ui/badge';
import { 
  Receipt, 
  Plus, 
  Search, 
  Edit, 
  Trash2, 
  User,
  Calendar,
  DollarSign,
  CheckCircle,
  Clock,
  XCircle,
  Eye,
  Save,
  X
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const ExpensesPage = () => {
  const [expenses, setExpenses] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [filteredExpenses, setFilteredExpenses] = useState([]);
  const [showExpenseForm, setShowExpenseForm] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [formData, setFormData] = useState({
    employee_id: '',
    description: '',
    amount: 0,
    category: '',
    expense_date: new Date().toISOString().split('T')[0],
    notes: ''
  });

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    let filtered = expenses.filter(expense => {
      const matchesSearch = expense.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          getEmployeeName(expense.employee_id).toLowerCase().includes(searchTerm.toLowerCase());
      const matchesStatus = statusFilter === 'all' || expense.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
    setFilteredExpenses(filtered);
  }, [expenses, searchTerm, statusFilter]);

  const fetchData = async () => {
    try {
      const [expensesRes, employeesRes] = await Promise.all([
        axios.get(`${API}/expenses`),
        axios.get(`${API}/employees`)
      ]);
      setExpenses(expensesRes.data);
      setEmployees(employeesRes.data);
      setLoading(false);
    } catch (error) {
      setError('Erreur lors du chargement des données');
      setLoading(false);
    }
  };

  const getEmployeeName = (employeeId) => {
    const employee = employees.find(e => e.id === employeeId);
    return employee ? employee.name : 'Employé inconnu';
  };

  const getStatusBadge = (status) => {
    const statusConfig = {
      pending: { label: 'En attente', className: 'bg-yellow-100 text-yellow-800' },
      approved: { label: 'Approuvé', className: 'bg-blue-100 text-blue-800' },
      paid: { label: 'Payé', className: 'bg-green-100 text-green-800' },
      rejected: { label: 'Refusé', className: 'bg-red-100 text-red-800' }
    };
    
    const config = statusConfig[status] || statusConfig.pending;
    return <Badge className={config.className}>{config.label}</Badge>;
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('fr-CA', {
      style: 'currency',
      currency: 'CAD'
    }).format(amount || 0);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    try {
      await axios.post(`${API}/expenses`, {
        ...formData,
        amount: parseFloat(formData.amount),
        expense_date: new Date(formData.expense_date).toISOString()
      });
      
      setSuccess('Dépense créée avec succès');
      setShowExpenseForm(false);
      setFormData({
        employee_id: '',
        description: '',
        amount: 0,
        category: '',
        expense_date: new Date().toISOString().split('T')[0],
        notes: ''
      });
      fetchData();
    } catch (error) {
      setError(error.response?.data?.detail || 'Erreur lors de la création');
    }
  };

  const updateExpenseStatus = async (expenseId, newStatus) => {
    try {
      await axios.put(`${API}/expenses/${expenseId}/status?status=${newStatus}`);
      setSuccess(`Dépense marquée comme ${newStatus === 'approved' ? 'approuvée' : newStatus === 'paid' ? 'payée' : 'refusée'}`);
      fetchData();
    } catch (error) {
      setError('Erreur lors de la mise à jour du statut');
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div className="flex items-center">
          <Receipt className="w-8 h-8 text-green-600 mr-3" />
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Dépenses</h1>
            <p className="text-gray-600">Gérez les dépenses et remboursements d'employés</p>
          </div>
        </div>
        <Button onClick={() => setShowExpenseForm(true)} className="btn-primary">
          <Plus className="w-4 h-4 mr-2" />
          Nouvelle dépense
        </Button>
      </div>

      {error && (
        <Alert className="border-red-200 bg-red-50">
          <AlertDescription className="text-red-800">{error}</AlertDescription>
        </Alert>
      )}

      {success && (
        <Alert className="border-green-200 bg-green-50">
          <AlertDescription className="text-green-800">{success}</AlertDescription>
        </Alert>
      )}

      {/* Filters */}
      <Card className="p-6">
        <div className="flex flex-col sm:flex-row sm:items-center space-y-4 sm:space-y-0 sm:space-x-4">
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
            <Input
              type="text"
              placeholder="Rechercher..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
            />
          </div>
          
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="all">Tous les statuts</option>
            <option value="pending">En attente</option>
            <option value="approved">Approuvé</option>
            <option value="paid">Payé</option>
            <option value="rejected">Refusé</option>
          </select>
        </div>
      </Card>

      {/* Expenses List */}
      <div className="space-y-4">
        {filteredExpenses.map((expense) => (
          <Card key={expense.id} className="p-6 card-hover">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="font-medium text-gray-900">{expense.description}</h3>
                    <p className="text-sm text-gray-600">
                      Par {getEmployeeName(expense.employee_id)} • {new Date(expense.expense_date).toLocaleDateString('fr-CA')}
                    </p>
                    {expense.category && (
                      <Badge variant="outline" className="mt-1">
                        {expense.category}
                      </Badge>
                    )}
                  </div>
                  <div className="text-right">
                    <div className="text-lg font-semibold text-gray-900">
                      {formatCurrency(expense.amount)}
                    </div>
                    {getStatusBadge(expense.status)}
                  </div>
                </div>
                
                {expense.notes && (
                  <p className="text-sm text-gray-500 mb-3">{expense.notes}</p>
                )}
                
                {expense.expense_type === 'automatic' && expense.related_invoice_id && (
                  <div className="text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded">
                    Généré automatiquement depuis facture #{expense.related_invoice_id}
                  </div>
                )}
              </div>
            </div>
            
            {expense.status === 'pending' && (
              <div className="flex justify-end space-x-2 mt-4 pt-4 border-t">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => updateExpenseStatus(expense.id, 'approved')}
                  className="text-blue-600"
                >
                  <CheckCircle className="w-4 h-4 mr-1" />
                  Approuver
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => updateExpenseStatus(expense.id, 'paid')}
                  className="text-green-600"
                >
                  <DollarSign className="w-4 h-4 mr-1" />
                  Marquer payé
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => updateExpenseStatus(expense.id, 'rejected')}
                  className="text-red-600"
                >
                  <XCircle className="w-4 h-4 mr-1" />
                  Refuser
                </Button>
              </div>
            )}
          </Card>
        ))}
      </div>

      {filteredExpenses.length === 0 && !loading && (
        <Card className="p-12 text-center">
          <Receipt className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            Aucune dépense trouvée
          </h3>
          <p className="text-gray-600 mb-4">
            {searchTerm ? 'Aucune dépense ne correspond à votre recherche' : 'Aucune dépense enregistrée'}
          </p>
        </Card>
      )}

      {/* Expense Form Modal */}
      {showExpenseForm && (
        <div className="fixed inset-0 z-50 bg-black bg-opacity-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg max-w-md w-full p-6">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-lg font-semibold">Nouvelle dépense</h3>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowExpenseForm(false)}
              >
                <X className="w-4 h-4" />
              </Button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Employé *
                </label>
                <select
                  value={formData.employee_id}
                  onChange={(e) => setFormData(prev => ({ ...prev, employee_id: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  required
                >
                  <option value="">Sélectionner un employé</option>
                  {employees.map(employee => (
                    <option key={employee.id} value={employee.id}>
                      {employee.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Description *
                </label>
                <Input
                  value={formData.description}
                  onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                  placeholder="Déplacement client, repas, fournitures..."
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Montant (CAD) *
                </label>
                <Input
                  type="number"
                  step="0.01"
                  value={formData.amount}
                  onChange={(e) => setFormData(prev => ({ ...prev, amount: e.target.value }))}
                  placeholder="0.00"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Catégorie
                </label>
                <Input
                  value={formData.category}
                  onChange={(e) => setFormData(prev => ({ ...prev, category: e.target.value }))}
                  placeholder="Transport, Repas, Fournitures..."
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Date de dépense
                </label>
                <Input
                  type="date"
                  value={formData.expense_date}
                  onChange={(e) => setFormData(prev => ({ ...prev, expense_date: e.target.value }))}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Notes
                </label>
                <textarea
                  value={formData.notes}
                  onChange={(e) => setFormData(prev => ({ ...prev, notes: e.target.value }))}
                  placeholder="Notes additionnelles..."
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div className="flex justify-end space-x-3 pt-4">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowExpenseForm(false)}
                >
                  Annuler
                </Button>
                <Button type="submit">
                  <Save className="w-4 h-4 mr-2" />
                  Créer la dépense
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default ExpensesPage;