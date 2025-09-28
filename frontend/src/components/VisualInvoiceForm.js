import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Calendar, Upload, Plus, X, Save, Send } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const VisualInvoiceForm = ({ invoiceData, onSave, onCancel, isQuote = false }) => {
  const [clients, setClients] = useState([]);
  const [products, setProducts] = useState([]);
  const [settings, setSettings] = useState(null);
  const [formData, setFormData] = useState({
    client_id: '',
    invoice_number: '',
    issue_date: new Date().toISOString().split('T')[0],
    due_date: '',
    items: [{ description: '', quantity: 1, unit_price: 0 }],
    gst_rate: 5.0,
    pst_rate: 9.975,
    hst_rate: 0.0,
    apply_gst: true,
    apply_pst: true,
    apply_hst: false,
    province: 'QC',
    notes: ''
  });

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    if (invoiceData) {
      setFormData({
        ...invoiceData,
        issue_date: invoiceData.issue_date ? invoiceData.issue_date.split('T')[0] : new Date().toISOString().split('T')[0],
        due_date: invoiceData.due_date ? invoiceData.due_date.split('T')[0] : ''
      });
    } else {
      // Set default due date from settings
      if (settings?.default_due_days) {
        const dueDate = new Date();
        dueDate.setDate(dueDate.getDate() + settings.default_due_days);
        setFormData(prev => ({ ...prev, due_date: dueDate.toISOString().split('T')[0] }));
      }
    }
  }, [invoiceData, settings]);

  const fetchData = async () => {
    try {
      const [clientsRes, productsRes, settingsRes] = await Promise.all([
        axios.get(`${API}/clients`),
        axios.get(`${API}/products`),
        axios.get(`${API}/settings/company`)
      ]);
      setClients(clientsRes.data);
      setProducts(productsRes.data);
      setSettings(settingsRes.data);
    } catch (error) {
      console.error('Erreur lors du chargement des données:', error);
    }
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('fr-CA', {
      style: 'currency',
      currency: 'CAD'
    }).format(amount || 0);
  };

  const getClientData = () => {
    return clients.find(c => c.id === formData.client_id) || {};
  };

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

  const calculateTotal = () => {
    return calculateSubtotal() + calculateGST() + calculatePST() + calculateHST();
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

  const addProductToItem = (index, productId) => {
    const product = products.find(p => p.id === productId);
    if (product) {
      handleItemChange(index, 'description', product.name + (product.description ? ` - ${product.description}` : ''));
      handleItemChange(index, 'unit_price', product.unit_price);
    }
  };

  const clientData = getClientData();

  return (
    <div className="max-w-6xl mx-auto bg-white shadow-2xl rounded-lg overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-teal-600 to-teal-700 px-8 py-6 text-white">
        <div className="flex justify-between items-center">
          <div>
            <div className="flex items-center space-x-2 mb-1">
              <div className="px-3 py-2 bg-white/20 rounded-lg">
                <span className="text-xl font-bold">
                  {isQuote ? 'SOUMISSION' : 'FACTURE'}
                </span>
              </div>
            </div>
            <p className="text-teal-100 font-medium text-lg">{settings?.company_name || 'Mon Entreprise'}</p>
          </div>
          
          <div className="text-right">
            <div className="flex items-center space-x-2 mb-2">
              <span className="text-teal-100">N°:</span>
              <Input
                value={formData.invoice_number || ''}
                onChange={(e) => setFormData(prev => ({ ...prev, invoice_number: e.target.value }))}
                className="w-32 bg-white/20 border-white/30 text-white placeholder-white/70"
                placeholder="Auto"
              />
            </div>
            <div className="text-sm text-teal-100">
              {new Date().toLocaleDateString('fr-CA')}
            </div>
          </div>
        </div>
      </div>

      <div className="p-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
          {/* Sender Info */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-4">De:</h3>
            <div className="bg-gray-50 p-4 rounded-lg">
              {settings?.logo_url && (
                <img src={settings.logo_url} alt="Logo" className="h-12 mb-3" />
              )}
              <div className="space-y-1 text-sm">
                <div className="font-medium">{settings?.company_name || 'Mon Entreprise'}</div>
                <div>{settings?.address}</div>
                <div>{settings?.city && settings?.postal_code && `${settings.city}, ${settings.postal_code}`}</div>
                <div>{settings?.country}</div>
                <div>{settings?.email}</div>
                <div>{settings?.phone}</div>
              </div>
            </div>
          </div>

          {/* Client Info */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-4">À:</h3>
            <div className="space-y-4">
              <Select 
                value={formData.client_id} 
                onValueChange={(value) => setFormData(prev => ({ ...prev, client_id: value }))}
              >
                <SelectTrigger className="bg-gray-50">
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

              {clientData.id && (
                <div className="bg-gray-50 p-4 rounded-lg">
                  <div className="space-y-1 text-sm">
                    <div className="font-medium">{clientData.name}</div>
                    <div>{clientData.address}</div>
                    <div>{clientData.city && clientData.postal_code && `${clientData.city}, ${clientData.postal_code}`}</div>
                    <div>{clientData.country}</div>
                    <div>{clientData.email}</div>
                    <div>{clientData.phone}</div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Invoice Details */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Date d'émission
            </label>
            <Input
              type="date"
              value={formData.issue_date || ''}
              onChange={(e) => setFormData(prev => ({ ...prev, issue_date: e.target.value }))}
              className="bg-gray-50"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {isQuote ? 'Valable jusqu\'au' : 'Date d\'échéance'}
            </label>
            <Input
              type="date"
              value={formData.due_date || ''}
              onChange={(e) => setFormData(prev => ({ ...prev, due_date: e.target.value }))}
              className="bg-gray-50"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Province
            </label>
            <Select 
              value={formData.province} 
              onValueChange={(value) => setFormData(prev => ({ ...prev, province: value }))}
            >
              <SelectTrigger className="bg-gray-50">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="QC">Québec</SelectItem>
                <SelectItem value="ON">Ontario</SelectItem>
                <SelectItem value="BC">Colombie-Britannique</SelectItem>
                <SelectItem value="AB">Alberta</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Items Table */}
        <div className="mb-8">
          <div className="bg-teal-600 text-white p-4 rounded-t-lg">
            <h3 className="font-semibold">Articles et Services</h3>
          </div>
          
          <div className="border border-t-0 rounded-b-lg overflow-hidden">
            <div className="bg-teal-50 grid grid-cols-12 gap-2 p-3 text-sm font-medium text-teal-800">
              <div className="col-span-5">Description</div>
              <div className="col-span-2 text-center">Quantité</div>
              <div className="col-span-2 text-center">Prix unitaire</div>
              <div className="col-span-2 text-center">Total</div>
              <div className="col-span-1 text-center">Action</div>
            </div>

            {formData.items.map((item, index) => (
              <div key={index} className="grid grid-cols-12 gap-2 p-3 border-t border-gray-200">
                <div className="col-span-5">
                  <Input
                    value={item.description || ''}
                    onChange={(e) => handleItemChange(index, 'description', e.target.value)}
                    placeholder="Description du service/produit"
                    className="mb-2"
                  />
                  <Select onValueChange={(value) => addProductToItem(index, value)}>
                    <SelectTrigger className="text-xs bg-gray-50">
                      <SelectValue placeholder="Ou choisir un produit" />
                    </SelectTrigger>
                    <SelectContent>
                      {products.map(product => (
                        <SelectItem key={product.id} value={product.id}>
                          {product.name} - {formatCurrency(product.unit_price)}/{product.unit}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="col-span-2">
                  <Input
                    type="number"
                    step="0.01"
                    value={item.quantity || 0}
                    onChange={(e) => handleItemChange(index, 'quantity', parseFloat(e.target.value) || 0)}
                    className="text-center"
                  />
                </div>
                
                <div className="col-span-2">
                  <Input
                    type="number"
                    step="0.01"
                    value={item.unit_price}
                    onChange={(e) => handleItemChange(index, 'unit_price', parseFloat(e.target.value) || 0)}
                    className="text-center"
                  />
                </div>
                
                <div className="col-span-2 flex items-center justify-center">
                  <span className="font-medium">{formatCurrency(calculateItemTotal(item))}</span>
                </div>
                
                <div className="col-span-1 flex justify-center">
                  {formData.items.length > 1 && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => removeItem(index)}
                      className="text-red-500 hover:text-red-700"
                    >
                      <X className="w-4 h-4" />
                    </Button>
                  )}
                </div>
              </div>
            ))}

            <div className="p-3 border-t border-gray-200 bg-gray-50">
              <Button
                variant="outline"
                size="sm"
                onClick={addItem}
                className="text-teal-600 border-teal-300 hover:bg-teal-50"
              >
                <Plus className="w-4 h-4 mr-2" />
                Ajouter un article
              </Button>
            </div>
          </div>
        </div>

        {/* Summary */}
        <div className="flex justify-between">
          <div className="w-1/2">
            <h4 className="font-semibold text-gray-900 mb-2">Notes</h4>
            <textarea
              value={formData.notes}
              onChange={(e) => setFormData(prev => ({ ...prev, notes: e.target.value }))}
              className="w-full p-3 border border-gray-300 rounded-lg resize-none"
              rows="4"
              placeholder="Notes visibles au client..."
            />
          </div>

          <div className="w-5/12">
            <div className="bg-gray-50 p-6 rounded-lg">
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span>Sous-total:</span>
                  <span className="font-medium">{formatCurrency(calculateSubtotal())}</span>
                </div>
                
                {formData.apply_gst && (
                  <div className="flex justify-between text-sm">
                    <span>TPS ({formData.gst_rate}%):</span>
                    <span>{formatCurrency(calculateGST())}</span>
                  </div>
                )}
                
                {formData.apply_pst && (
                  <div className="flex justify-between text-sm">
                    <span>TVQ ({formData.pst_rate}%):</span>
                    <span>{formatCurrency(calculatePST())}</span>
                  </div>
                )}
                
                {formData.apply_hst && (
                  <div className="flex justify-between text-sm">
                    <span>HST ({formData.hst_rate}%):</span>
                    <span>{formatCurrency(calculateHST())}</span>
                  </div>
                )}

                <div className="border-t pt-3">
                  <div className="flex justify-between text-lg font-bold text-teal-600">
                    <span>TOTAL:</span>
                    <span>{formatCurrency(calculateTotal())}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-between items-center mt-8 pt-6 border-t border-gray-200">
          <Button
            variant="outline"
            onClick={onCancel}
            className="px-6"
          >
            Annuler
          </Button>

          <div className="flex space-x-3">
            <Button
              onClick={() => onSave(formData, 'draft')}
              variant="outline"
              className="px-6"
            >
              <Save className="w-4 h-4 mr-2" />
              Sauvegarder
            </Button>
            
            <Button
              onClick={() => onSave(formData, 'sent')}
              className="px-6 bg-teal-600 hover:bg-teal-700"
            >
              <Send className="w-4 h-4 mr-2" />
              Sauvegarder et envoyer
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default VisualInvoiceForm;