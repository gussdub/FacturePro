import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Alert, AlertDescription } from './ui/alert';
import VisualInvoiceForm from './VisualInvoiceForm';
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
  X
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
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [formData, setFormData] = useState({
    client_id: '',
    due_date: '',
    gst_rate: 5.0,
    pst_rate: 9.975, // TVQ Québec
    hst_rate: 0.0,
    apply_gst: true,
    apply_pst: true,
    apply_hst: false,
    province: 'QC',
    notes: '',
    items: [{ description: '', quantity: 1, unit_price: 0 }]
  });

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

  const calculateSubtotal = () => {
    return formData.items.reduce((sum, item) => sum + calculateItemTotal(item), 0);
  };

  const calculateGST = () => {
    return formData.apply_gst ? calculateSubtotal() * (formData.gst_rate / 100) : 0;
  };

  const calculatePST = () => {
    return formData.apply_pst ? calculateSubtotal() * (formData.pst_rate / 100) : 0;
  };

  const calculateHST = () => {
    return formData.apply_hst ? calculateSubtotal() * (formData.hst_rate / 100) : 0;
  };

  const calculateTotalTax = () => {
    return calculateGST() + calculatePST() + calculateHST();
  };

  const calculateTotal = () => {
    return calculateSubtotal() + calculateTotalTax();
  };

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
          
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>
                {editingInvoice ? 'Modifier la facture' : 'Nouvelle facture'}
              </DialogTitle>
            </DialogHeader>

            {error && (
              <Alert className="border-red-200 bg-red-50">
                <AlertDescription className="text-red-800">{error}</AlertDescription>
              </Alert>
            )}

            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Client *
                  </label>
                  <Select 
                    value={formData.client_id} 
                    onValueChange={(value) => setFormData(prev => ({ ...prev, client_id: value }))}
                  >
                    <SelectTrigger data-testid="client-select">
                      <SelectValue placeholder="Sélectionner un client" />
                    </SelectTrigger>
                    <SelectContent>
                      {clients.map(client => (
                        <SelectItem key={client.id} value={client.id}>
                          {client.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Date d'échéance *
                  </label>
                  <Input
                    type="date"
                    value={formData.due_date}
                    onChange={(e) => setFormData(prev => ({ ...prev, due_date: e.target.value }))}
                    required
                    data-testid="due-date-input"
                  />
                </div>
              </div>

              {/* Items */}
              <div>
                <div className="flex justify-between items-center mb-4">
                  <label className="text-sm font-medium text-gray-700">
                    Articles *
                  </label>
                  <Button type="button" variant="outline" size="sm" onClick={addItem} data-testid="add-item-btn">
                    <Plus className="w-4 h-4 mr-1" />
                    Ajouter un article
                  </Button>
                </div>

                <div className="space-y-3">
                  {formData.items.map((item, index) => (
                    <div key={index} className="grid grid-cols-12 gap-3 items-end">
                      <div className="col-span-5">
                        <Input
                          placeholder="Description"
                          value={item.description}
                          onChange={(e) => handleItemChange(index, 'description', e.target.value)}
                          required
                          data-testid={`item-description-${index}`}
                        />
                      </div>
                      <div className="col-span-2">
                        <Input
                          type="number"
                          step="0.01"
                          placeholder="Qté"
                          value={item.quantity}
                          onChange={(e) => handleItemChange(index, 'quantity', parseFloat(e.target.value) || 0)}
                          required
                          data-testid={`item-quantity-${index}`}
                        />
                      </div>
                      <div className="col-span-2">
                        <Input
                          type="number"
                          step="0.01"
                          placeholder="Prix unitaire"
                          value={item.unit_price}
                          onChange={(e) => handleItemChange(index, 'unit_price', parseFloat(e.target.value) || 0)}
                          required
                          data-testid={`item-price-${index}`}
                        />
                      </div>
                      <div className="col-span-2">
                        <Input
                          value={formatCurrency(calculateItemTotal(item))}
                          disabled
                          className="bg-gray-50"
                        />
                      </div>
                      <div className="col-span-1">
                        {formData.items.length > 1 && (
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => removeItem(index)}
                            data-testid={`remove-item-${index}`}
                            className="text-red-500 hover:text-red-700"
                          >
                            <X className="w-4 h-4" />
                          </Button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Province selection */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Province/Territoire
                </label>
                <Select 
                  value={formData.province} 
                  onValueChange={(value) => {
                    const provinceSettings = getProvinceSettings(value);
                    setFormData(prev => ({ 
                      ...prev, 
                      province: value,
                      pst_rate: provinceSettings.pst_rate,
                      hst_rate: provinceSettings.hst_rate,
                      apply_pst: provinceSettings.apply_pst,
                      apply_hst: provinceSettings.apply_hst
                    }));
                  }}
                >
                  <SelectTrigger data-testid="province-select">
                    <SelectValue placeholder="Sélectionner une province" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="QC">Québec</SelectItem>
                    <SelectItem value="ON">Ontario</SelectItem>
                    <SelectItem value="BC">Colombie-Britannique</SelectItem>
                    <SelectItem value="AB">Alberta</SelectItem>
                    <SelectItem value="MB">Manitoba</SelectItem>
                    <SelectItem value="SK">Saskatchewan</SelectItem>
                    <SelectItem value="NS">Nouvelle-Écosse</SelectItem>
                    <SelectItem value="NB">Nouveau-Brunswick</SelectItem>
                    <SelectItem value="NL">Terre-Neuve-et-Labrador</SelectItem>
                    <SelectItem value="PE">Île-du-Prince-Édouard</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Tax Configuration */}
              <div className="bg-blue-50 p-4 rounded-lg">
                <h4 className="font-medium text-gray-900 mb-3">Configuration des taxes</h4>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  
                  {/* GST */}
                  <div className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={formData.apply_gst}
                      onChange={(e) => setFormData(prev => ({ ...prev, apply_gst: e.target.checked }))}
                      className="rounded border-gray-300"
                      data-testid="apply-gst-checkbox"
                    />
                    <div className="flex-1">
                      <label className="text-sm font-medium text-gray-700">TPS/GST</label>
                      <div className="flex items-center space-x-1">
                        <Input
                          type="number"
                          step="0.001"
                          value={formData.gst_rate}
                          onChange={(e) => setFormData(prev => ({ ...prev, gst_rate: parseFloat(e.target.value) || 0 }))}
                          className="w-16 h-8 text-xs"
                          disabled={!formData.apply_gst}
                          data-testid="gst-rate-input"
                        />
                        <span className="text-xs">%</span>
                      </div>
                    </div>
                  </div>

                  {/* PST/TVQ */}
                  <div className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={formData.apply_pst}
                      onChange={(e) => setFormData(prev => ({ ...prev, apply_pst: e.target.checked }))}
                      className="rounded border-gray-300"
                      data-testid="apply-pst-checkbox"
                    />
                    <div className="flex-1">
                      <label className="text-sm font-medium text-gray-700">TVQ/PST</label>
                      <div className="flex items-center space-x-1">
                        <Input
                          type="number"
                          step="0.001"
                          value={formData.pst_rate}
                          onChange={(e) => setFormData(prev => ({ ...prev, pst_rate: parseFloat(e.target.value) || 0 }))}
                          className="w-16 h-8 text-xs"
                          disabled={!formData.apply_pst}
                          data-testid="pst-rate-input"
                        />
                        <span className="text-xs">%</span>
                      </div>
                    </div>
                  </div>

                  {/* HST */}
                  <div className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={formData.apply_hst}
                      onChange={(e) => setFormData(prev => ({ ...prev, apply_hst: e.target.checked }))}
                      className="rounded border-gray-300"
                      data-testid="apply-hst-checkbox"
                    />
                    <div className="flex-1">
                      <label className="text-sm font-medium text-gray-700">HST</label>
                      <div className="flex items-center space-x-1">
                        <Input
                          type="number"
                          step="0.001"
                          value={formData.hst_rate}
                          onChange={(e) => setFormData(prev => ({ ...prev, hst_rate: parseFloat(e.target.value) || 0 }))}
                          className="w-16 h-8 text-xs"
                          disabled={!formData.apply_hst}
                          data-testid="hst-rate-input"
                        />
                        <span className="text-xs">%</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Totals */}
              <div className="bg-gray-50 p-4 rounded-lg">
                <div className="space-y-2 text-right">
                  <div className="flex justify-between">
                    <span className="font-medium">Sous-total:</span>
                    <span>{formatCurrency(calculateSubtotal())}</span>
                  </div>
                  
                  {formData.apply_gst && (
                    <div className="flex justify-between">
                      <span className="text-sm">TPS/GST ({formData.gst_rate}%):</span>
                      <span>{formatCurrency(calculateGST())}</span>
                    </div>
                  )}
                  
                  {formData.apply_pst && (
                    <div className="flex justify-between">
                      <span className="text-sm">TVQ/PST ({formData.pst_rate}%):</span>
                      <span>{formatCurrency(calculatePST())}</span>
                    </div>
                  )}
                  
                  {formData.apply_hst && (
                    <div className="flex justify-between">
                      <span className="text-sm">HST ({formData.hst_rate}%):</span>
                      <span>{formatCurrency(calculateHST())}</span>
                    </div>
                  )}
                  
                  <div className="flex justify-between text-lg font-bold border-t pt-2">
                    <span>Total:</span>
                    <span>{formatCurrency(calculateTotal())}</span>
                  </div>
                </div>
              </div>

              {/* Notes */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Notes
                </label>
                <textarea
                  className="w-full p-3 border border-gray-300 rounded-lg resize-none"
                  rows="3"
                  value={formData.notes}
                  onChange={(e) => setFormData(prev => ({ ...prev, notes: e.target.value }))}
                  placeholder="Notes additionnelles..."
                  data-testid="notes-input"
                />
              </div>

              <div className="flex justify-end space-x-3 pt-4">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowInvoiceDialog(false)}
                  data-testid="cancel-invoice-btn"
                >
                  Annuler
                </Button>
                <Button type="submit" data-testid="save-invoice-btn">
                  {editingInvoice ? 'Modifier' : 'Créer'}
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Success message */}
      {success && (
        <Alert className="border-green-200 bg-green-50">
          <AlertDescription className="text-green-800">{success}</AlertDescription>
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