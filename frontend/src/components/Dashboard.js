import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { 
  Users, 
  FileText, 
  ScrollText, 
  TrendingUp, 
  Euro,
  Clock,
  AlertCircle,
  Plus,
  ArrowUpRight,
  Calendar,
  DollarSign
} from 'lucide-react';
import { Link } from 'react-router-dom';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Dashboard = () => {
  const [stats, setStats] = useState({
    total_clients: 0,
    total_invoices: 0,
    total_quotes: 0,
    pending_invoices: 0,
    total_revenue: 0
  });
  const [recentInvoices, setRecentInvoices] = useState([]);
  const [recentQuotes, setRecentQuotes] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      const [statsRes, invoicesRes, quotesRes] = await Promise.all([
        axios.get(`${API}/dashboard/stats`),
        axios.get(`${API}/invoices`),
        axios.get(`${API}/quotes`)
      ]);

      setStats(statsRes.data);
      
      // Get last 5 invoices
      setRecentInvoices(invoicesRes.data.slice(0, 5));
      
      // Get last 5 quotes
      setRecentQuotes(quotesRes.data.slice(0, 5));
    } catch (error) {
      console.error('Erreur lors du chargement du tableau de bord:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('fr-FR', {
      style: 'currency',
      currency: 'EUR'
    }).format(amount);
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('fr-FR');
  };

  const getStatusColor = (status) => {
    const colors = {
      draft: 'bg-gray-100 text-gray-800',
      sent: 'bg-blue-100 text-blue-800',
      paid: 'bg-green-100 text-green-800',
      overdue: 'bg-red-100 text-red-800',
      cancelled: 'bg-gray-100 text-gray-600',
      pending: 'bg-yellow-100 text-yellow-800',
      accepted: 'bg-green-100 text-green-800',
      rejected: 'bg-red-100 text-red-800',
      expired: 'bg-gray-100 text-gray-600'
    };
    return colors[status] || 'bg-gray-100 text-gray-800';
  };

  const getStatusText = (status) => {
    const texts = {
      draft: 'Brouillon',
      sent: 'Envoyée',
      paid: 'Payée',
      overdue: 'En retard',
      cancelled: 'Annulée',
      pending: 'En attente',
      accepted: 'Accepté',
      rejected: 'Refusé',
      expired: 'Expiré'
    };
    return texts[status] || status;
  };

  if (loading) {
    return (
      <div className="space-y-6">
        {/* Loading skeleton */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[...Array(4)].map((_, i) => (
            <Card key={i} className="p-6">
              <div className="animate-shimmer h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
              <div className="animate-shimmer h-8 bg-gray-200 rounded w-1/2"></div>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Welcome Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Tableau de bord
          </h1>
          <p className="text-gray-600">
            Vue d'ensemble de votre activité de facturation
          </p>
        </div>
        
        <div className="flex space-x-3 mt-4 sm:mt-0">
          <Link to="/quotes">
            <Button data-testid="create-quote-btn" className="btn-hover bg-indigo-600 hover:bg-indigo-700">
              <Plus className="w-4 h-4 mr-2" />
              Nouvelle soumission
            </Button>
          </Link>
          <Link to="/invoices">
            <Button data-testid="create-invoice-btn" className="btn-hover bg-green-600 hover:bg-green-700">
              <Plus className="w-4 h-4 mr-2" />
              Nouvelle facture
            </Button>
          </Link>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className="p-6 card-hover" data-testid="clients-stat">
          <div className="flex items-center">
            <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
              <Users className="w-6 h-6 text-blue-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">Clients</p>
              <p className="text-2xl font-bold text-gray-900">{stats.total_clients}</p>
            </div>
          </div>
        </Card>

        <Card className="p-6 card-hover" data-testid="invoices-stat">
          <div className="flex items-center">
            <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
              <FileText className="w-6 h-6 text-green-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">Factures</p>
              <p className="text-2xl font-bold text-gray-900">{stats.total_invoices}</p>
            </div>
          </div>
        </Card>

        <Card className="p-6 card-hover" data-testid="quotes-stat">
          <div className="flex items-center">
            <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
              <ScrollText className="w-6 h-6 text-purple-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">Devis</p>
              <p className="text-2xl font-bold text-gray-900">{stats.total_quotes}</p>
            </div>
          </div>
        </Card>

        <Card className="p-6 card-hover" data-testid="revenue-stat">
          <div className="flex items-center">
            <div className="w-12 h-12 bg-yellow-100 rounded-lg flex items-center justify-center">
              <TrendingUp className="w-6 h-6 text-yellow-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">Chiffre d'affaires</p>
              <p className="text-2xl font-bold text-gray-900">{formatCurrency(stats.total_revenue)}</p>
            </div>
          </div>
        </Card>
      </div>

      {/* Alerts */}
      {stats.pending_invoices > 0 && (
        <Card className="p-4 bg-orange-50 border-orange-200" data-testid="pending-alert">
          <div className="flex items-center">
            <AlertCircle className="w-5 h-5 text-orange-500 mr-3" />
            <div>
              <p className="text-sm font-medium text-orange-800">
                Attention: {stats.pending_invoices} facture{stats.pending_invoices > 1 ? 's' : ''} en attente de paiement
              </p>
            </div>
            <Link to="/invoices" className="ml-auto">
              <Button variant="outline" size="sm" className="text-orange-600 border-orange-300 hover:bg-orange-100">
                Voir les factures
              </Button>
            </Link>
          </div>
        </Card>
      )}

      {/* Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Recent Invoices */}
        <Card className="card-hover">
          <div className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900">Dernières factures</h3>
              <Link to="/invoices">
                <Button variant="ghost" size="sm" data-testid="view-all-invoices-btn">
                  Voir tout
                  <ArrowUpRight className="w-4 h-4 ml-1" />
                </Button>
              </Link>
            </div>

            {recentInvoices.length === 0 ? (
              <div className="text-center py-8" data-testid="no-invoices">
                <FileText className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                <p className="text-gray-500">Aucune facture créée</p>
                <Link to="/invoices">
                  <Button className="mt-4" data-testid="create-first-invoice-btn">
                    <Plus className="w-4 h-4 mr-2" />
                    Créer votre première facture
                  </Button>
                </Link>
              </div>
            ) : (
              <div className="space-y-4">
                {recentInvoices.map((invoice) => (
                  <div key={invoice.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg table-row">
                    <div>
                      <p className="font-medium text-gray-900">{invoice.invoice_number}</p>
                      <p className="text-sm text-gray-500">Échéance: {formatDate(invoice.due_date)}</p>
                    </div>
                    <div className="text-right">
                      <p className="font-semibold text-gray-900">{formatCurrency(invoice.total)}</p>
                      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(invoice.status)}`}>
                        {getStatusText(invoice.status)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </Card>

        {/* Recent Quotes */}
        <Card className="card-hover">
          <div className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900">Derniers devis</h3>
              <Link to="/quotes">
                <Button variant="ghost" size="sm" data-testid="view-all-quotes-btn">
                  Voir tout
                  <ArrowUpRight className="w-4 h-4 ml-1" />
                </Button>
              </Link>
            </div>

            {recentQuotes.length === 0 ? (
              <div className="text-center py-8" data-testid="no-quotes">
                <ScrollText className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                <p className="text-gray-500">Aucun devis créé</p>
                <Link to="/quotes">
                  <Button className="mt-4" data-testid="create-first-quote-btn">
                    <Plus className="w-4 h-4 mr-2" />
                    Créer votre premier devis
                  </Button>
                </Link>
              </div>
            ) : (
              <div className="space-y-4">
                {recentQuotes.map((quote) => (
                  <div key={quote.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg table-row">
                    <div>
                      <p className="font-medium text-gray-900">{quote.quote_number}</p>
                      <p className="text-sm text-gray-500">Valable jusqu'au: {formatDate(quote.valid_until)}</p>
                    </div>
                    <div className="text-right">
                      <p className="font-semibold text-gray-900">{formatCurrency(quote.total)}</p>
                      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(quote.status)}`}>
                        {getStatusText(quote.status)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </Card>
      </div>

      {/* Quick Actions */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Actions rapides</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Link to="/clients">
            <div className="flex items-center p-4 bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors cursor-pointer">
              <Users className="w-8 h-8 text-blue-600 mr-3" />
              <div>
                <p className="font-medium text-blue-900">Gérer les clients</p>
                <p className="text-sm text-blue-600">Ajouter ou modifier vos clients</p>
              </div>
            </div>
          </Link>

          <Link to="/settings">
            <div className="flex items-center p-4 bg-purple-50 rounded-lg hover:bg-purple-100 transition-colors cursor-pointer">
              <Calendar className="w-8 h-8 text-purple-600 mr-3" />
              <div>
                <p className="font-medium text-purple-900">Personnaliser</p>
                <p className="text-sm text-purple-600">Configurer votre entreprise</p>
              </div>
            </div>
          </Link>

          <div className="flex items-center p-4 bg-green-50 rounded-lg">
            <DollarSign className="w-8 h-8 text-green-600 mr-3" />
            <div>
              <p className="font-medium text-green-900">Revenus ce mois</p>
              <p className="text-sm text-green-600">{formatCurrency(stats.total_revenue)}</p>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default Dashboard;