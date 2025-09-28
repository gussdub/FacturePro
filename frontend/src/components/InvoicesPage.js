import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Alert, AlertDescription } from './ui/alert';
import VisualInvoiceForm from './VisualInvoiceForm';
import InvoiceActionsDialog from './InvoiceActionsDialog';
import { 
  Plus, 
  Search, 
  Edit, 
  Trash2, 
  Download,
  Send,
  Eye,
  FileText,
  Calendar,
  Euro,
  Filter,
  X,
  MoreVertical,
  Settings
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Helper function for province tax settings
const getProvinceSettings = (province) => {
  const settings = {
    QC: { pst_rate: 9.975, apply_pst: true, apply_hst: false, hst_rate: 0 }, // Québec - TVQ
    ON: { pst_rate: 0, apply_pst: false, apply_hst: true, hst_rate: 13 }, // Ontario - HST
    BC: { pst_rate: 7, apply_pst: true, apply_hst: false, hst_rate: 0 }, // Colombie-Britannique - PST
    AB: { pst_rate: 0, apply_pst: false, apply_hst: false, hst_rate: 0 }, // Alberta - Pas de taxe provinciale
    MB: { pst_rate: 7, apply_pst: true, apply_hst: false, hst_rate: 0 }, // Manitoba - PST
    SK: { pst_rate: 6, apply_pst: true, apply_hst: false, hst_rate: 0 }, // Saskatchewan - PST
    NS: { pst_rate: 0, apply_pst: false, apply_hst: true, hst_rate: 15 }, // Nouvelle-Écosse - HST
    NB: { pst_rate: 0, apply_pst: false, apply_hst: true, hst_rate: 15 }, // Nouveau-Brunswick - HST
    NL: { pst_rate: 0, apply_pst: false, apply_hst: true, hst_rate: 15 }, // Terre-Neuve-et-Labrador - HST
    PE: { pst_rate: 0, apply_pst: false, apply_hst: true, hst_rate: 15 }, // Île-du-Prince-Édouard - HST
  };
  return settings[province] || settings.QC;
};

const InvoicesPage = () => {
  const [invoices, setInvoices] = useState([]);
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [showInvoiceForm, setShowInvoiceForm] = useState(false);
  const [editingInvoice, setEditingInvoice] = useState(null);
  const [showActionsDialog, setShowActionsDialog] = useState(false);
  const [selectedInvoice, setSelectedInvoice] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  // Form data now handled by VisualInvoiceForm component

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [invoicesRes, clientsRes] = await Promise.all([
        axios.get(`${API}/invoices`),
        axios.get(`${API}/clients`)
      ]);
      setInvoices(invoicesRes.data);
      setClients(clientsRes.data);
    } catch (error) {
      console.error('Erreur lors du chargement:', error);
      setError('Erreur lors du chargement des données');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveInvoice = async (invoiceData, status = 'draft') => {
    setError('');
    setSuccess('');

    try {
      // Validation
      if (!invoiceData.client_id) {
        setError('Veuillez sélectionner un client');
        return;
      }

      if (invoiceData.items.some(item => !item.description || item.unit_price <= 0)) {
        setError('Veuillez remplir tous les articles avec des prix valides');
        return;
      }

      const finalData = {
        ...invoiceData,
        due_date: invoiceData.due_date ? new Date(invoiceData.due_date).toISOString() : undefined,
        gst_rate: parseFloat(invoiceData.gst_rate) || 0,
        pst_rate: parseFloat(invoiceData.pst_rate) || 0,
        hst_rate: parseFloat(invoiceData.hst_rate) || 0
      };

      let response;
      if (editingInvoice) {
        response = await axios.put(`${API}/invoices/${editingInvoice.id}`, finalData);
        setSuccess('Facture modifiée avec succès');
      } else {
        response = await axios.post(`${API}/invoices`, finalData);
        setSuccess('Facture créée avec succès');
        
        // Update status if needed
        if (status !== 'draft') {
          await axios.put(`${API}/invoices/${response.data.id}/status?status=${status}`);
        }
      }
      
      await fetchData();
      setShowInvoiceForm(false);
      setEditingInvoice(null);
    } catch (error) {
      setError(error.response?.data?.detail || 'Erreur lors de la sauvegarde');
    }
  };

  const handleEdit = (invoice) => {
    setEditingInvoice(invoice);
    setShowInvoiceForm(true);
  };

  const handleDelete = async (invoiceId) => {
    if (!window.confirm('Êtes-vous sûr de vouloir supprimer cette facture ?')) {
      return;
    }

    try {
      await axios.delete(`${API}/invoices/${invoiceId}`);
      await fetchData();
      setSuccess('Facture supprimée avec succès');
    } catch (error) {
      setError('Erreur lors de la suppression de la facture');
    }
  };

  const updateInvoiceStatus = async (invoiceId, newStatus) => {
    try {
      await axios.put(`${API}/invoices/${invoiceId}/status?status=${newStatus}`);
      await fetchData();
      setSuccess('Statut mis à jour avec succès');
    } catch (error) {
      setError('Erreur lors de la mise à jour du statut');
    }
  };

  const handleItemChange = (index, field, value) => {
    const newItems = [...formData.items];
    newItems[index] = { ...newItems[index], [field]: value };
    setFormData(prev => ({ ...prev, items: newItems }));
  };

  const addItem = () => {
    setFormData(prev => ({
      ...prev,
      items: [...prev.items, { description: '', quantity: 1, unit_price: 0 }]
    }));
  };

  const removeItem = (index) => {
    if (formData.items.length > 1) {
      setFormData(prev => ({
        ...prev,
        items: prev.items.filter((_, i) => i !== index)
      }));
    }
  };

  const resetForm = () => {
    setEditingInvoice(null);
    setFormData({
      client_id: '',
      due_date: '',
      gst_rate: 5.0,
      pst_rate: 9.975,
      hst_rate: 0.0,
      apply_gst: true,
      apply_pst: true,
      apply_hst: false,
      province: 'QC',
      notes: '',
      items: [{ description: '', quantity: 1, unit_price: 0 }]
    });
    setError('');
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('fr-CA', {
      style: 'currency',
      currency: 'CAD'
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
      cancelled: 'bg-gray-100 text-gray-600'
    };
    return colors[status] || 'bg-gray-100 text-gray-800';
  };

  const getStatusText = (status) => {
    const texts = {
      draft: 'Brouillon',
      sent: 'Envoyée',
      paid: 'Payée',
      overdue: 'En retard',
      cancelled: 'Annulée'
    };
    return texts[status] || status;
  };

  const getClientName = (clientId) => {
    const client = clients.find(c => c.id === clientId);
    return client ? client.name : 'Client inconnu';
  };

  const filteredInvoices = invoices.filter(invoice => {
    const matchesSearch = invoice.invoice_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         getClientName(invoice.client_id).toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || invoice.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const calculateItemTotal = (item) => {
    return item.quantity * item.unit_price;
  };

  // Helper function removed since now handled by VisualInvoiceForm

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="animate-shimmer h-8 bg-gray-200 rounded w-1/3"></div>
        <div className="space-y-4">
          {[...Array(5)].map((_, i) => (
            <Card key={i} className="p-6">
              <div className="animate-shimmer h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
              <div className="animate-shimmer h-4 bg-gray-200 rounded w-1/2"></div>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Factures</h1>
          <p className="text-gray-600">Gérez vos factures et leur suivi</p>
        </div>
        
        <Button 
          className="mt-4 sm:mt-0 btn-hover" 
          data-testid="add-invoice-btn"
          onClick={() => setShowInvoiceForm(true)}
        >
          <Plus className="w-4 h-4 mr-2" />
          Nouvelle facture
        </Button>
      </div>

      {/* Visual Invoice Form */}
      {showInvoiceForm && (
        <div className="fixed inset-0 z-50 bg-black bg-opacity-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg max-w-7xl w-full max-h-[95vh] overflow-y-auto">
            <VisualInvoiceForm
              invoiceData={editingInvoice}
              onSave={handleSaveInvoice}
              onCancel={() => {
                setShowInvoiceForm(false);
                setEditingInvoice(null);
              }}
              isQuote={false}
            />
          </div>
        </div>
      )}

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
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
          <Input
            type="text"
            placeholder="Rechercher une facture..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
            data-testid="search-invoices-input"
          />
        </div>

        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-full sm:w-48" data-testid="status-filter">
            <SelectValue placeholder="Filtrer par statut" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tous les statuts</SelectItem>
            <SelectItem value="draft">Brouillon</SelectItem>
            <SelectItem value="sent">Envoyée</SelectItem>
            <SelectItem value="paid">Payée</SelectItem>
            <SelectItem value="overdue">En retard</SelectItem>
            <SelectItem value="cancelled">Annulée</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Invoices List */}
      {filteredInvoices.length === 0 ? (
        <Card className="p-12 text-center" data-testid="no-invoices">
          <FileText className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            {invoices.length === 0 ? 'Aucune facture' : 'Aucun résultat'}
          </h3>
          <p className="text-gray-500 mb-6">
            {invoices.length === 0 
              ? 'Créez votre première facture pour commencer'
              : 'Aucune facture ne correspond à vos critères'
            }
          </p>
          {invoices.length === 0 && (
            <Button onClick={() => setShowInvoiceDialog(true)} data-testid="create-first-invoice-btn">
              <Plus className="w-4 h-4 mr-2" />
              Créer une facture
            </Button>
          )}
        </Card>
      ) : (
        <div className="space-y-4">
          {filteredInvoices.map((invoice) => (
            <Card key={invoice.id} className="card-hover" data-testid={`invoice-card-${invoice.id}`}>
              <div className="p-6">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-4 mb-2">
                      <h3 className="text-lg font-semibold text-gray-900">
                        {invoice.invoice_number}
                      </h3>
                      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(invoice.status)}`}>
                        {getStatusText(invoice.status)}
                      </span>
                    </div>
                    
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-sm text-gray-600">
                      <div>
                        <span className="font-medium">Client:</span> {getClientName(invoice.client_id)}
                      </div>
                      <div>
                        <span className="font-medium">Échéance:</span> {formatDate(invoice.due_date)}
                      </div>
                      <div>
                        <span className="font-medium">Montant:</span> {formatCurrency(invoice.total)}
                      </div>
                      <div>
                        <span className="font-medium">Créée le:</span> {formatDate(invoice.issue_date)}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2 ml-4">
                    {invoice.status === 'draft' && (
                      <>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => updateInvoiceStatus(invoice.id, 'sent')}
                          data-testid={`send-invoice-${invoice.id}`}
                          className="text-blue-600 border-blue-300 hover:bg-blue-50"
                        >
                          <Send className="w-4 h-4 mr-1" />
                          Envoyer
                        </Button>
                      </>
                    )}

                    {invoice.status === 'sent' && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => updateInvoiceStatus(invoice.id, 'paid')}
                        data-testid={`mark-paid-${invoice.id}`}
                        className="text-green-600 border-green-300 hover:bg-green-50"
                      >
                        Marquer payée
                      </Button>
                    )}

                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleEdit(invoice)}
                      data-testid={`edit-invoice-${invoice.id}`}
                      className="text-gray-500 hover:text-indigo-600"
                    >
                      <Edit className="w-4 h-4" />
                    </Button>
                    
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleDelete(invoice.id)}
                      data-testid={`delete-invoice-${invoice.id}`}
                      className="text-gray-500 hover:text-red-600"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Stats */}
      <Card className="p-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 text-center">
          <div>
            <p className="text-2xl font-bold text-blue-600">{invoices.length}</p>
            <p className="text-sm text-gray-600">Total factures</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-green-600">
              {invoices.filter(i => i.status === 'paid').length}
            </p>
            <p className="text-sm text-gray-600">Payées</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-orange-600">
              {invoices.filter(i => i.status === 'sent').length}
            </p>
            <p className="text-sm text-gray-600">En attente</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-purple-600">
              {formatCurrency(invoices.reduce((sum, i) => sum + (i.total || 0), 0))}
            </p>
            <p className="text-sm text-gray-600">Montant total</p>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default InvoicesPage;