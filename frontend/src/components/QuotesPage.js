import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from './ui/dialog';
import { Alert, AlertDescription } from './ui/alert';
import { 
  Plus, 
  Search, 
  Edit, 
  Trash2, 
  FileText,
  Calendar,
  Euro,
  ArrowRight,
  ScrollText,
  X,
  CheckCircle
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const QuotesPage = () => {
  const [quotes, setQuotes] = useState([]);
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [showQuoteDialog, setShowQuoteDialog] = useState(false);
  const [showConvertDialog, setShowConvertDialog] = useState(false);
  const [editingQuote, setEditingQuote] = useState(null);
  const [convertingQuote, setConvertingQuote] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [formData, setFormData] = useState({
    client_id: '',
    valid_until: '',
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
  const [convertData, setConvertData] = useState({
    due_date: ''
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [quotesRes, clientsRes] = await Promise.all([
        axios.get(`${API}/quotes`),
        axios.get(`${API}/clients`)
      ]);
      setQuotes(quotesRes.data);
      setClients(clientsRes.data);
    } catch (error) {
      console.error('Erreur lors du chargement:', error);
      setError('Erreur lors du chargement des données');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    try {
      // Validation
      if (!formData.client_id) {
        setError('Veuillez sélectionner un client');
        return;
      }

      if (formData.items.some(item => !item.description || item.unit_price <= 0)) {
        setError('Veuillez remplir tous les articles avec des prix valides');
        return;
      }

      const quoteData = {
        ...formData,
        valid_until: new Date(formData.valid_until).toISOString(),
        tax_rate: parseFloat(formData.tax_rate) || 0
      };

      if (editingQuote) {
        await axios.put(`${API}/quotes/${editingQuote.id}`, quoteData);
        setSuccess('Soumission modifiée avec succès');
      } else {
        await axios.post(`${API}/quotes`, quoteData);
        setSuccess('Soumission créée avec succès');
      }
      
      await fetchData();
      setShowQuoteDialog(false);
      resetForm();
    } catch (error) {
      setError(error.response?.data?.detail || 'Erreur lors de la sauvegarde');
    }
  };

  const handleConvert = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    try {
      if (!convertData.due_date) {
        setError('Veuillez sélectionner une date d\'échéance');
        return;
      }

      await axios.post(`${API}/quotes/${convertingQuote.id}/convert?due_date=${new Date(convertData.due_date).toISOString()}`);
      setSuccess('Soumission convertie en facture avec succès');
      await fetchData();
      setShowConvertDialog(false);
      setConvertingQuote(null);
      setConvertData({ due_date: '' });
    } catch (error) {
      setError(error.response?.data?.detail || 'Erreur lors de la conversion');
    }
  };

  const handleEdit = (quote) => {
    setEditingQuote(quote);
    setFormData({
      client_id: quote.client_id,
      valid_until: quote.valid_until.split('T')[0],
      tax_rate: quote.tax_rate,
      notes: quote.notes || '',
      items: quote.items
    });
    setShowQuoteDialog(true);
  };

  const handleDelete = async (quoteId) => {
    if (!window.confirm('Êtes-vous sûr de vouloir supprimer ce devis ?')) {
      return;
    }

    try {
      await axios.delete(`${API}/quotes/${quoteId}`);
      await fetchData();
      setSuccess('Devis supprimé avec succès');
    } catch (error) {
      setError('Erreur lors de la suppression du devis');
    }
  };

  const openConvertDialog = (quote) => {
    setConvertingQuote(quote);
    // Set default due date to 30 days from now
    const defaultDueDate = new Date();
    defaultDueDate.setDate(defaultDueDate.getDate() + 30);
    setConvertData({ due_date: defaultDueDate.toISOString().split('T')[0] });
    setShowConvertDialog(true);
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
    setEditingQuote(null);
    setFormData({
      client_id: '',
      valid_until: '',
      tax_rate: 20,
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
      pending: 'bg-yellow-100 text-yellow-800',
      accepted: 'bg-green-100 text-green-800',
      rejected: 'bg-red-100 text-red-800',
      expired: 'bg-gray-100 text-gray-600'
    };
    return colors[status] || 'bg-gray-100 text-gray-800';
  };

  const getStatusText = (status) => {
    const texts = {
      pending: 'En attente',
      accepted: 'Accepté',
      rejected: 'Refusé',
      expired: 'Expiré'
    };
    return texts[status] || status;
  };

  const getClientName = (clientId) => {
    const client = clients.find(c => c.id === clientId);
    return client ? client.name : 'Client inconnu';
  };

  const isExpired = (validUntil) => {
    return new Date(validUntil) < new Date();
  };

  const filteredQuotes = quotes.filter(quote => {
    const matchesSearch = quote.quote_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         getClientName(quote.client_id).toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || quote.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const calculateItemTotal = (item) => {
    return item.quantity * item.unit_price;
  };

  const calculateSubtotal = () => {
    return formData.items.reduce((sum, item) => sum + calculateItemTotal(item), 0);
  };

  const calculateTax = () => {
    return calculateSubtotal() * (formData.tax_rate / 100);
  };

  const calculateTotal = () => {
    return calculateSubtotal() + calculateTax();
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
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Devis</h1>
          <p className="text-gray-600">Créez et gérez vos devis clients</p>
        </div>
        
        <Dialog open={showQuoteDialog} onOpenChange={(open) => {
          setShowQuoteDialog(open);
          if (!open) resetForm();
        }}>
          <DialogTrigger asChild>
            <Button className="mt-4 sm:mt-0 btn-hover" data-testid="add-quote-btn">
              <Plus className="w-4 h-4 mr-2" />
              Nouveau devis
            </Button>
          </DialogTrigger>
          
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>
                {editingQuote ? 'Modifier le devis' : 'Nouveau devis'}
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
                    Valable jusqu'au *
                  </label>
                  <Input
                    type="date"
                    value={formData.valid_until}
                    onChange={(e) => setFormData(prev => ({ ...prev, valid_until: e.target.value }))}
                    required
                    data-testid="valid-until-input"
                  />
                </div>
              </div>

              {/* Items - Same as InvoicesPage */}
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

              {/* Totals */}
              <div className="bg-gray-50 p-4 rounded-lg">
                <div className="space-y-2 text-right">
                  <div className="flex justify-between">
                    <span className="font-medium">Sous-total:</span>
                    <span>{formatCurrency(calculateSubtotal())}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <div className="flex items-center space-x-2">
                      <span className="font-medium">TVA:</span>
                      <Input
                        type="number"
                        step="0.1"
                        value={formData.tax_rate}
                        onChange={(e) => setFormData(prev => ({ ...prev, tax_rate: parseFloat(e.target.value) || 0 }))}
                        className="w-20 h-8"
                        data-testid="tax-rate-input"
                      />
                      <span>%</span>
                    </div>
                    <span>{formatCurrency(calculateTax())}</span>
                  </div>
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
                  onClick={() => setShowQuoteDialog(false)}
                  data-testid="cancel-quote-btn"
                >
                  Annuler
                </Button>
                <Button type="submit" data-testid="save-quote-btn">
                  {editingQuote ? 'Modifier' : 'Créer'}
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Convert Dialog */}
      <Dialog open={showConvertDialog} onOpenChange={setShowConvertDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Convertir en facture</DialogTitle>
          </DialogHeader>

          <p className="text-gray-600 mb-4">
            Convertir le devis <strong>{convertingQuote?.quote_number}</strong> en facture.
          </p>

          {error && (
            <Alert className="border-red-200 bg-red-50">
              <AlertDescription className="text-red-800">{error}</AlertDescription>
            </Alert>
          )}

          <form onSubmit={handleConvert} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Date d'échéance de la facture *
              </label>
              <Input
                type="date"
                value={convertData.due_date}
                onChange={(e) => setConvertData(prev => ({ ...prev, due_date: e.target.value }))}
                required
                data-testid="convert-due-date"
              />
            </div>

            <div className="flex justify-end space-x-3 pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowConvertDialog(false)}
                data-testid="cancel-convert-btn"
              >
                Annuler
              </Button>
              <Button type="submit" data-testid="confirm-convert-btn">
                <ArrowRight className="w-4 h-4 mr-2" />
                Convertir en facture
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

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
            placeholder="Rechercher un devis..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
            data-testid="search-quotes-input"
          />
        </div>

        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-full sm:w-48" data-testid="status-filter">
            <SelectValue placeholder="Filtrer par statut" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tous les statuts</SelectItem>
            <SelectItem value="pending">En attente</SelectItem>
            <SelectItem value="accepted">Accepté</SelectItem>
            <SelectItem value="rejected">Refusé</SelectItem>
            <SelectItem value="expired">Expiré</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Quotes List */}
      {filteredQuotes.length === 0 ? (
        <Card className="p-12 text-center" data-testid="no-quotes">
          <ScrollText className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            {quotes.length === 0 ? 'Aucun devis' : 'Aucun résultat'}
          </h3>
          <p className="text-gray-500 mb-6">
            {quotes.length === 0 
              ? 'Créez votre premier devis pour commencer'
              : 'Aucun devis ne correspond à vos critères'
            }
          </p>
          {quotes.length === 0 && (
            <Button onClick={() => setShowQuoteDialog(true)} data-testid="create-first-quote-btn">
              <Plus className="w-4 h-4 mr-2" />
              Créer un devis
            </Button>
          )}
        </Card>
      ) : (
        <div className="space-y-4">
          {filteredQuotes.map((quote) => (
            <Card key={quote.id} className="card-hover" data-testid={`quote-card-${quote.id}`}>
              <div className="p-6">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-4 mb-2">
                      <h3 className="text-lg font-semibold text-gray-900">
                        {quote.quote_number}
                      </h3>
                      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(quote.status)}`}>
                        {getStatusText(quote.status)}
                      </span>
                      {isExpired(quote.valid_until) && quote.status === 'pending' && (
                        <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-red-100 text-red-800">
                          Expiré
                        </span>
                      )}
                    </div>
                    
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-sm text-gray-600">
                      <div>
                        <span className="font-medium">Client:</span> {getClientName(quote.client_id)}
                      </div>
                      <div>
                        <span className="font-medium">Valable jusqu'au:</span> {formatDate(quote.valid_until)}
                      </div>
                      <div>
                        <span className="font-medium">Montant:</span> {formatCurrency(quote.total)}
                      </div>
                      <div>
                        <span className="font-medium">Créé le:</span> {formatDate(quote.issue_date)}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2 ml-4">
                    {quote.status === 'pending' && !isExpired(quote.valid_until) && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => openConvertDialog(quote)}
                        data-testid={`convert-quote-${quote.id}`}
                        className="text-green-600 border-green-300 hover:bg-green-50"
                      >
                        <ArrowRight className="w-4 h-4 mr-1" />
                        Convertir
                      </Button>
                    )}

                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleEdit(quote)}
                      data-testid={`edit-quote-${quote.id}`}
                      className="text-gray-500 hover:text-indigo-600"
                    >
                      <Edit className="w-4 h-4" />
                    </Button>
                    
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleDelete(quote.id)}
                      data-testid={`delete-quote-${quote.id}`}
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
            <p className="text-2xl font-bold text-blue-600">{quotes.length}</p>
            <p className="text-sm text-gray-600">Total devis</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-yellow-600">
              {quotes.filter(q => q.status === 'pending').length}
            </p>
            <p className="text-sm text-gray-600">En attente</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-green-600">
              {quotes.filter(q => q.status === 'accepted').length}
            </p>
            <p className="text-sm text-gray-600">Acceptés</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-purple-600">
              {formatCurrency(quotes.reduce((sum, q) => sum + (q.total || 0), 0))}
            </p>
            <p className="text-sm text-gray-600">Montant total</p>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default QuotesPage;