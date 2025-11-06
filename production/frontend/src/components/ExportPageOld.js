import React, { useState } from 'react';
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
  Building
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const ExportPage = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [filters, setFilters] = useState({
    period: 'month',
    start_date: '',
    end_date: '',
    status: 'all',
    employee_id: 'all'
  });

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('fr-CA', {
      style: 'currency',
      currency: 'CAD'
    }).format(amount || 0);
  };

  const exportStatistics = async () => {
    try {
      setLoading(true);
      setError('');
      
      const params = new URLSearchParams();
      if (filters.start_date) params.append('start_date', filters.start_date);
      if (filters.end_date) params.append('end_date', filters.end_date);
      params.append('period', filters.period);
      
      const response = await axios.get(`${API}/export/statistics?${params}`);
      setStatisticsData(response.data);
      setSuccess('Statistiques générées avec succès');
    } catch (error) {
      setError('Erreur lors de l\'export des statistiques');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const exportInvoicesCSV = async () => {
    try {
      setLoading(true);
      setError('');
      
      const params = new URLSearchParams();
      if (filters.start_date) params.append('start_date', filters.start_date);
      if (filters.end_date) params.append('end_date', filters.end_date);
      if (filters.status !== 'all') params.append('status', filters.status);
      
      const response = await axios.get(`${API}/export/invoices?${params}`);
      
      // Convert to CSV
      const invoices = response.data.invoices;
      if (invoices.length === 0) {
        setError('Aucune facture à exporter pour cette période');
        return;
      }
      
      const headers = [
        'Numéro facture',
        'Client',
        'Email client',
        'Date émission',
        'Date échéance',
        'Statut',
        'Sous-total',
        'TPS',
        'TVQ/PST',
        'HST',
        'Total',
        'Méthode paiement',
        'Date paiement',
        'Notes'
      ];
      
      let csvContent = headers.join(',') + '\n';
      
      invoices.forEach(invoice => {
        const row = [
          `"${invoice.invoice_number}"`,
          `"${invoice.client_name}"`,
          `"${invoice.client_email}"`,
          `"${new Date(invoice.issue_date).toLocaleDateString('fr-CA')}"`,
          `"${new Date(invoice.due_date).toLocaleDateString('fr-CA')}"`,
          `"${invoice.status}"`,
          invoice.subtotal,
          invoice.gst_amount,
          invoice.pst_amount,
          invoice.hst_amount,
          invoice.total,
          `"${invoice.payment_method || ''}"`,
          invoice.payment_date ? `"${new Date(invoice.payment_date).toLocaleDateString('fr-CA')}"` : '""',
          `"${invoice.notes || ''}"`
        ];
        csvContent += row.join(',') + '\n';
      });
      
      // Download file
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      const url = URL.createObjectURL(blob);
      link.setAttribute('href', url);
      link.setAttribute('download', `factures_${new Date().toISOString().split('T')[0]}.csv`);
      link.style.visibility = 'hidden';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      setSuccess('Export CSV téléchargé avec succès');
    } catch (error) {
      setError('Erreur lors de l\'export CSV');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const downloadStatisticsJSON = () => {
    if (!statisticsData) return;
    
    const dataStr = JSON.stringify(statisticsData, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `statistiques_${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    setSuccess('Statistiques JSON téléchargées');
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Exports et Statistiques</h1>
        <p className="text-gray-600">Exportez vos données pour la comptabilité et l'analyse</p>
      </div>

      {/* Success/Error messages */}
      {success && (
        <Alert className="border-green-200 bg-green-50">
          <AlertDescription className="text-green-800">{success}</AlertDescription>
        </Alert>
      )}

      {error && (
        <Alert className="border-red-200 bg-red-50">
          <AlertDescription className="text-red-800">{error}</AlertDescription>
        </Alert>
      )}

      {/* Filters */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Filtres d'export</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Période
            </label>
            <select 
              value={filters.period}
              onChange={(e) => setFilters(prev => ({ ...prev, period: e.target.value }))}
              className="w-full h-10 px-3 py-2 bg-white border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            >
              <option value="week">Semaine</option>
              <option value="month">Mois</option>
              <option value="year">Année</option>
            </select>
          </div>

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
              Statut
            </label>
            <select 
              value={filters.status}
              onChange={(e) => setFilters(prev => ({ ...prev, status: e.target.value }))}
              className="w-full h-10 px-3 py-2 bg-white border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            >
              <option value="all">Tous</option>
              <option value="draft">Brouillon</option>
              <option value="sent">Envoyées</option>
              <option value="paid">Payées</option>
              <option value="overdue">En retard</option>
            </select>
          </div>
        </div>
      </Card>

      {/* Export Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card className="p-6 card-hover">
          <div className="flex items-center mb-4">
            <TrendingUp className="w-8 h-8 text-blue-600 mr-3" />
            <div>
              <h3 className="text-lg font-semibold text-gray-900">Statistiques détaillées</h3>
              <p className="text-gray-600">Analyse complète de votre activité</p>
            </div>
          </div>
          <Button 
            onClick={exportStatistics}
            disabled={loading}
            className="w-full"
          >
            <BarChart3 className="w-4 h-4 mr-2" />
            Générer les statistiques
          </Button>
        </Card>

        <Card className="p-6 card-hover">
          <div className="flex items-center mb-4">
            <FileSpreadsheet className="w-8 h-8 text-green-600 mr-3" />
            <div>
              <h3 className="text-lg font-semibold text-gray-900">Export CSV</h3>
              <p className="text-gray-600">Données pour Excel/comptabilité</p>
            </div>
          </div>
          <Button 
            onClick={exportInvoicesCSV}
            disabled={loading}
            className="w-full bg-green-600 hover:bg-green-700"
          >
            <Download className="w-4 h-4 mr-2" />
            Télécharger CSV
          </Button>
        </Card>
      </div>

      {/* Statistics Display */}
      {statisticsData && (
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-semibold text-gray-900">Résultats des statistiques</h3>
            <Button 
              onClick={downloadStatisticsJSON}
              variant="outline"
              size="sm"
            >
              <Download className="w-4 h-4 mr-2" />
              Télécharger JSON
            </Button>
          </div>

          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card className="p-4 text-center">
              <div className="text-2xl font-bold text-blue-600">{statisticsData.summary.total_invoices}</div>
              <div className="text-sm text-gray-600">Total factures</div>
            </Card>

            <Card className="p-4 text-center">
              <div className="text-2xl font-bold text-green-600">{statisticsData.summary.paid_invoices}</div>
              <div className="text-sm text-gray-600">Factures payées</div>
            </Card>

            <Card className="p-4 text-center">
              <div className="text-2xl font-bold text-orange-600">{statisticsData.summary.pending_invoices}</div>
              <div className="text-sm text-gray-600">En attente</div>
            </Card>

            <Card className="p-4 text-center">
              <div className="text-2xl font-bold text-purple-600">{statisticsData.summary.collection_rate.toFixed(1)}%</div>
              <div className="text-sm text-gray-600">Taux de recouvrement</div>
            </Card>
          </div>

          {/* Financial Summary */}
          <Card className="p-6">
            <h4 className="text-lg font-semibold text-gray-900 mb-4">Résumé financier</h4>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="text-center">
                <div className="text-3xl font-bold text-green-600 mb-2">
                  {formatCurrency(statisticsData.summary.total_revenue)}
                </div>
                <div className="text-sm text-gray-600">Revenus encaissés</div>
              </div>

              <div className="text-center">
                <div className="text-3xl font-bold text-orange-600 mb-2">
                  {formatCurrency(statisticsData.summary.pending_amount)}
                </div>
                <div className="text-sm text-gray-600">En attente de paiement</div>
              </div>

              <div className="text-center">
                <div className="text-3xl font-bold text-red-600 mb-2">
                  {formatCurrency(statisticsData.summary.overdue_amount)}
                </div>
                <div className="text-sm text-gray-600">Factures en retard</div>
              </div>
            </div>
          </Card>

          {/* Period Breakdown */}
          {statisticsData.period_breakdown.length > 0 && (
            <Card className="p-6">
              <h4 className="text-lg font-semibold text-gray-900 mb-4">Évolution par période</h4>
              <div className="overflow-x-auto">
                <table className="w-full table-auto">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left py-2">Période</th>
                      <th className="text-center py-2">Factures</th>
                      <th className="text-center py-2">Payées</th>
                      <th className="text-right py-2">Montant total</th>
                      <th className="text-right py-2">Revenus</th>
                    </tr>
                  </thead>
                  <tbody>
                    {statisticsData.period_breakdown.map((period, index) => (
                      <tr key={index} className="border-b">
                        <td className="py-2 font-medium">{period.period}</td>
                        <td className="py-2 text-center">{period.total_invoices}</td>
                        <td className="py-2 text-center">{period.paid_count}</td>
                        <td className="py-2 text-right">{formatCurrency(period.total_amount)}</td>
                        <td className="py-2 text-right">{formatCurrency(period.paid_amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </div>
      )}
    </div>
  );
};

export default ExportPage;