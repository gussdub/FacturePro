import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Alert, AlertDescription } from './ui/alert';
import { Badge } from './ui/badge';
import { 
  Users, 
  Plus, 
  Search, 
  Edit, 
  Trash2, 
  User,
  Mail,
  Phone,
  Building,
  Save,
  X
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const EmployeesPage = () => {
  const [employees, setEmployees] = useState([]);
  const [filteredEmployees, setFilteredEmployees] = useState([]);
  const [showEmployeeForm, setShowEmployeeForm] = useState(false);
  const [editingEmployee, setEditingEmployee] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    employee_number: '',
    department: ''
  });

  useEffect(() => {
    fetchEmployees();
  }, []);

  useEffect(() => {
    const filtered = employees.filter(employee =>
      employee.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      employee.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (employee.department && employee.department.toLowerCase().includes(searchTerm.toLowerCase()))
    );
    setFilteredEmployees(filtered);
  }, [employees, searchTerm]);

  const fetchEmployees = async () => {
    try {
      const response = await axios.get(`${API}/employees`);
      setEmployees(response.data);
      setLoading(false);
    } catch (error) {
      setError('Erreur lors du chargement des employés');
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    try {
      if (editingEmployee) {
        await axios.put(`${API}/employees/${editingEmployee.id}`, formData);
        setSuccess('Employé modifié avec succès');
      } else {
        await axios.post(`${API}/employees`, formData);
        setSuccess('Employé créé avec succès');
      }
      
      setShowEmployeeForm(false);
      setEditingEmployee(null);
      setFormData({ name: '', email: '', phone: '', employee_number: '', department: '' });
      fetchEmployees();
    } catch (error) {
      setError(error.response?.data?.detail || 'Erreur lors de la sauvegarde');
    }
  };

  const handleEdit = (employee) => {
    setEditingEmployee(employee);
    setFormData({
      name: employee.name,
      email: employee.email,
      phone: employee.phone || '',
      employee_number: employee.employee_number || '',
      department: employee.department || ''
    });
    setShowEmployeeForm(true);
  };

  const handleDelete = async (employeeId) => {
    if (window.confirm('Êtes-vous sûr de vouloir supprimer cet employé ?')) {
      try {
        await axios.delete(`${API}/employees/${employeeId}`);
        setSuccess('Employé supprimé avec succès');
        fetchEmployees();
      } catch (error) {
        setError('Erreur lors de la suppression');
      }
    }
  };

  const handleChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
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
          <Users className="w-8 h-8 text-indigo-600 mr-3" />
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Employés</h1>
            <p className="text-gray-600">Gérez les employés de votre entreprise</p>
          </div>
        </div>
        <Button onClick={() => setShowEmployeeForm(true)} className="btn-primary">
          <Plus className="w-4 h-4 mr-2" />
          Ajouter un employé
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

      {/* Search and Stats */}
      <Card className="p-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-4 sm:space-y-0">
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
            <Input
              type="text"
              placeholder="Rechercher un employé..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
            />
          </div>
          <div className="text-sm text-gray-600">
            {filteredEmployees.length} employé{filteredEmployees.length > 1 ? 's' : ''}
          </div>
        </div>
      </Card>

      {/* Employees List */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredEmployees.map((employee) => (
          <Card key={employee.id} className="p-6 card-hover">
            <div className="flex items-start justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-12 h-12 bg-indigo-100 rounded-full flex items-center justify-center">
                  <User className="w-6 h-6 text-indigo-600" />
                </div>
                <div className="flex-1">
                  <h3 className="font-medium text-gray-900">{employee.name}</h3>
                  <p className="text-sm text-gray-600">{employee.email}</p>
                  {employee.department && (
                    <Badge variant="secondary" className="mt-1">
                      {employee.department}
                    </Badge>
                  )}
                </div>
              </div>
              
              <div className="flex space-x-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleEdit(employee)}
                >
                  <Edit className="w-4 h-4" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleDelete(employee.id)}
                  className="text-red-600 hover:text-red-700"
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            </div>
            
            <div className="mt-4 space-y-2 text-sm text-gray-600">
              {employee.phone && (
                <div className="flex items-center">
                  <Phone className="w-4 h-4 mr-2" />
                  {employee.phone}
                </div>
              )}
              {employee.employee_number && (
                <div className="flex items-center">
                  <Building className="w-4 h-4 mr-2" />
                  #{employee.employee_number}
                </div>
              )}
            </div>
          </Card>
        ))}
      </div>

      {filteredEmployees.length === 0 && !loading && (
        <Card className="p-12 text-center">
          <Users className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            Aucun employé trouvé
          </h3>
          <p className="text-gray-600 mb-4">
            {searchTerm ? 'Aucun employé ne correspond à votre recherche' : 'Commencez par ajouter votre premier employé'}
          </p>
          <Button onClick={() => setShowEmployeeForm(true)}>
            <Plus className="w-4 h-4 mr-2" />
            Ajouter un employé
          </Button>
        </Card>
      )}

      {/* Employee Form Modal */}
      {showEmployeeForm && (
        <div className="fixed inset-0 z-50 bg-black bg-opacity-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg max-w-md w-full p-6">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-lg font-semibold">
                {editingEmployee ? 'Modifier l\'employé' : 'Nouvel employé'}
              </h3>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setShowEmployeeForm(false);
                  setEditingEmployee(null);
                  setFormData({ name: '', email: '', phone: '', employee_number: '', department: '' });
                }}
              >
                <X className="w-4 h-4" />
              </Button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Nom complet *
                </label>
                <Input
                  value={formData.name}
                  onChange={(e) => handleChange('name', e.target.value)}
                  placeholder="John Doe"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Email *
                </label>
                <Input
                  type="email"
                  value={formData.email}
                  onChange={(e) => handleChange('email', e.target.value)}
                  placeholder="john@entreprise.com"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Téléphone
                </label>
                <Input
                  value={formData.phone}
                  onChange={(e) => handleChange('phone', e.target.value)}
                  placeholder="514-123-4567"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Numéro d'employé
                </label>
                <Input
                  value={formData.employee_number}
                  onChange={(e) => handleChange('employee_number', e.target.value)}
                  placeholder="EMP001"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Département
                </label>
                <Input
                  value={formData.department}
                  onChange={(e) => handleChange('department', e.target.value)}
                  placeholder="Ventes, IT, Administration..."
                />
              </div>

              <div className="flex justify-end space-x-3 pt-4">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setShowEmployeeForm(false);
                    setEditingEmployee(null);
                    setFormData({ name: '', email: '', phone: '', employee_number: '', department: '' });
                  }}
                >
                  Annuler
                </Button>
                <Button type="submit">
                  <Save className="w-4 h-4 mr-2" />
                  {editingEmployee ? 'Modifier' : 'Créer'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default EmployeesPage;