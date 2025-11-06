import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Alert, AlertDescription } from './ui/alert';
import { Badge } from './ui/badge';
import { 
  Download, 
  Calendar, 
  TrendingUp, 
  FileSpreadsheet,
  BarChart3,
  PieChart,
  Receipt,
  Users,
  FileText,
  ScrollText,
  CreditCard,
  DollarSign,
  Calculator,
  Building,
  Printer
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const ExportPage = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [employees, setEmployees] = useState([]);
  const [filters, setFilters] = useState({
    period: 'month',
    start_date: new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().split('T')[0],
    end_date: new Date().toISOString().split('T')[0],
    status: 'all',
    employee_id: 'all'
  });

  useEffect(() => {
    fetchEmployees();
  }, []);

  const fetchEmployees = async () => {
    try {
      const response = await axios.get(`${API}/employees`);
      setEmployees(response.data);
    } catch (error) {
      console.error('Erreur chargement employés:', error);
    }
  };

  const downloadFile = (data, filename, type = 'json') => {
    let blob;
    let mimeType;
    
    if (type === 'csv') {
      // Convert to CSV
      const csv = convertToCSV(data);
      blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      mimeType = 'text/csv';
    } else if (type === 'excel') {
      // For Excel, we'll use CSV format (simple approach)
      const csv = convertToCSV(data);
      blob = new Blob([csv], { type: 'application/vnd.ms-excel' });
      mimeType = 'application/vnd.ms-excel';
      filename = filename.replace('.csv', '.xls');
    } else {
      // JSON
      blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      mimeType = 'application/json';
    }

    const link = document.createElement('a');
    if (link.download !== undefined) {
      const url = URL.createObjectURL(blob);
      link.setAttribute('href', url);
      link.setAttribute('download', filename);
      link.style.visibility = 'hidden';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  };

  const convertToCSV = (data) => {
    if (!data || !Array.isArray(data) || data.length === 0) {
      return '';
    }

    const headers = Object.keys(data[0]);
    const csvContent = [
      headers.join(','),
      ...data.map(row => 
        headers.map(header => {
          const value = row[header];
          // Escape commas and quotes in CSV
          return typeof value === 'string' && (value.includes(',') || value.includes('"')) 
            ? `"${value.replace(/"/g, '""')}"` 
            : value;
        }).join(',')
      )
    ].join('\n');

    return csvContent;
  };

  const exportData = async (exportType, format = 'json') => {
    setLoading(true);
    setError('');

    try {
      let endpoint = '';
      let params = {};

      // Build params
      if (filters.start_date) params.start_date = filters.start_date;
      if (filters.end_date) params.end_date = filters.end_date;
      
      switch (exportType) {
        case 'expenses':
          if (format === 'pdf') {
            endpoint = '/export/expenses-pdf';
          } else if (format === 'excel') {
            endpoint = '/export/expenses-excel';
          } else {
            endpoint = '/export/expenses';
          }
          
          if (filters.employee_id && filters.employee_id !== 'all') {
            params.employee_id = filters.employee_id;
          }
          if (filters.status && filters.status !== 'all') {
            params.status = filters.status;
          }
          break;
        
        case 'quotes':
          if (format === 'pdf') {
            endpoint = '/export/pending-quotes-pdf';
          } else {
            endpoint = '/export/pending-quotes';
          }
          break;
        
        case 'invoices':
          if (format === 'pdf') {
            endpoint = '/export/invoices-pdf';
          } else {
            endpoint = '/export/invoices';
          }
          if (filters.status && filters.status !== 'all') {
            params.status = filters.status;
          }
          break;
        
        case 'tax-report':
          endpoint = '/export/tax-report';
          break;
        
        case 'business-summary':
          endpoint = '/export/business-summary';
          break;
        
        default:
          throw new Error('Type d\'export non reconnu');
      }

      if (format === 'pdf' || format === 'excel') {
        // For file downloads (PDF, Excel)
        const response = await axios.get(`${API}${endpoint}`, {
          params,
          responseType: 'blob'
        });
        
        // Create download link
        const contentType = format === 'pdf' ? 'application/pdf' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
        const fileExt = format === 'excel' ? 'xlsx' : format;
        
        const blob = new Blob([response.data], { type: contentType });
        const link = document.createElement('a');
        const url = window.URL.createObjectURL(blob);
        
        link.href = url;
        link.download = `${exportType}_${new Date().toISOString().split('T')[0]}.${fileExt}`;
        document.body.appendChild(link);
        link.click();
        
        // Clean up
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
        
        setSuccess(`Export ${format.toUpperCase()} téléchargé avec succès`);
      } else {
        // For CSV and JSON
        const response = await axios.get(`${API}${endpoint}`, { params });
        
        let exportData = response.data;
        let filename = `${exportType}_${new Date().toISOString().split('T')[0]}`;
        
        // Extract the right data based on export type
        if (exportType === 'expenses') {
          exportData = response.data.expenses;
        } else if (exportType === 'quotes') {
          exportData = response.data.quotes;
        } else if (exportType === 'invoices') {
          exportData = response.data.invoices;
        }
        
        downloadFile(exportData, filename + (format === 'csv' ? '.csv' : '.json'), format);
        setSuccess(`Export ${format.toUpperCase()} téléchargé avec succès`);
      }
      
    } catch (error) {
      setError(error.response?.data?.detail || 'Erreur lors de l\'export');
    } finally {
      setLoading(false);
    }
  };

  const exportCards = [
    {
      title: 'Dépenses',
      description: 'Export des dépenses avec filtres par employé et statut',
      icon: CreditCard,
      type: 'expenses',
      color: 'text-green-600',
      filters: ['dates', 'employee', 'status']
    },
    {
      title: 'Soumissions en Cours',
      description: 'Toutes les soumissions non converties en factures',
      icon: ScrollText,
      type: 'quotes',
      color: 'text-blue-600',
      filters: []
    },
    {
      title: 'Factures',
      description: 'Export des factures avec filtres par période et statut',
      icon: Receipt,
      type: 'invoices',
      color: 'text-indigo-600',
      filters: ['dates', 'status']
    },
    {
      title: 'Rapport TPS/TVQ',
      description: 'Rapport fiscal pour déclarations de taxes',
      icon: Calculator,
      type: 'tax-report',
      color: 'text-red-600',
      filters: ['dates']
    },
    {
      title: 'Bilan Entreprise',
      description: 'Résumé financier complet (revenus, dépenses, profits)',
      icon: TrendingUp,
      type: 'business-summary',
      color: 'text-purple-600',
      filters: ['dates']
    }
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center">
        <BarChart3 className="w-8 h-8 text-indigo-600 mr-3" />
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Exports et Rapports</h1>
          <p className="text-gray-600">Exportez vos données en différents formats</p>
        </div>
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

      {/* Global Filters */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Filtres généraux</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Date de début
            </label>
            <Input
              type="date"
              value={filters.start_date}
              onChange={(e) => setFilters(prev => ({ ...prev, start_date: e.target.value }))}
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Date de fin
            </label>
            <Input
              type="date"
              value={filters.end_date}
              onChange={(e) => setFilters(prev => ({ ...prev, end_date: e.target.value }))}
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Employé
            </label>
            <select
              value={filters.employee_id}
              onChange={(e) => setFilters(prev => ({ ...prev, employee_id: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="all">Tous les employés</option>
              {employees.map(employee => (
                <option key={employee.id} value={employee.id}>
                  {employee.name}
                </option>
              ))}
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Statut
            </label>
            <select
              value={filters.status}
              onChange={(e) => setFilters(prev => ({ ...prev, status: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="all">Tous</option>
              <option value="pending">En attente</option>
              <option value="approved">Approuvé</option>
              <option value="paid">Payé</option>
              <option value="sent">Envoyé</option>
              <option value="draft">Brouillon</option>
            </select>
          </div>
        </div>
      </Card>

      {/* Export Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {exportCards.map((card) => {
          const Icon = card.icon;
          return (
            <Card key={card.type} className="p-6 card-hover">
              <div className="flex items-start space-x-4">
                <div className={`p-3 rounded-lg bg-gray-50 ${card.color}`}>
                  <Icon className="w-6 h-6" />
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-gray-900 mb-1">{card.title}</h3>
                  <p className="text-sm text-gray-600 mb-4">{card.description}</p>
                  
                  {/* Format Buttons */}
                  <div className="space-y-2">
                    <div className="flex space-x-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => exportData(card.type, 'excel')}
                        disabled={loading}
                        className="flex-1 text-green-600 border-green-200"
                      >
                        <FileSpreadsheet className="w-4 h-4 mr-1" />
                        Excel
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => exportData(card.type, 'pdf')}
                        disabled={loading}
                        className="flex-1 text-red-600 border-red-200"
                      >
                        <Printer className="w-4 h-4 mr-1" />
                        PDF
                      </Button>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => exportData(card.type, 'csv')}
                      disabled={loading}
                      className="w-full text-blue-600 border-blue-200"
                    >
                      <BarChart3 className="w-4 h-4 mr-1" />
                      CSV
                    </Button>
                  </div>
                  
                  {/* Applicable Filters */}
                  {card.filters.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-gray-200">
                      <p className="text-xs text-gray-500 mb-1">Filtres appliqués :</p>
                      <div className="flex flex-wrap gap-1">
                        {card.filters.includes('dates') && (
                          <Badge variant="outline" className="text-xs">Dates</Badge>
                        )}
                        {card.filters.includes('employee') && filters.employee_id !== 'all' && (
                          <Badge variant="outline" className="text-xs">Employé</Badge>
                        )}
                        {card.filters.includes('status') && filters.status !== 'all' && (
                          <Badge variant="outline" className="text-xs">Statut</Badge>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      {/* Loading State */}
      {loading && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <Card className="p-6">
            <div className="flex items-center space-x-3">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-indigo-500"></div>
              <span className="text-lg">Génération de l'export en cours...</span>
            </div>
          </Card>
        </div>
      )}

      {/* Quick Stats */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Aperçu rapide</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="text-center">
            <div className="text-2xl font-bold text-indigo-600">📊</div>
            <p className="text-sm text-gray-600">Données temps réel</p>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-green-600">💼</div>
            <p className="text-sm text-gray-600">Multi-formats</p>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-blue-600">📈</div>
            <p className="text-sm text-gray-600">Rapports fiscaux</p>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-purple-600">🎯</div>
            <p className="text-sm text-gray-600">Analyses business</p>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default ExportPage;