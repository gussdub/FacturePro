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
    items: [{ description: '', quantity: 1, unit_price: 0, product_id: '' }],
    gst_rate: 5.0,
    pst_rate: 9.975,
    hst_rate: 0.0,
    apply_gst: true,
    apply_pst: true,
    apply_hst: false,
    province: 'QC',
    notes: '',
    is_recurring: false,
    recurrence_type: 'monthly',
    recurrence_interval: 1
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
    console.log(`Changing item ${index}, field ${field} to:`, value);
    const newItems = [...formData.items];
    newItems[index] = { ...newItems[index], [field]: value };
    setFormData(prev => ({ ...prev, items: newItems }));
    console.log('Updated formData items:', newItems);
  };

  const addItem = () => {
    setFormData(prev => ({
      ...prev,
      items: [...prev.items, { description: '', quantity: 1, unit_price: 0, product_id: '' }]
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

 

  const clientData = getClientData();

  return (
    <div className="max-w-6xl mx-auto bg-white shadow-2xl rounded-lg overflow-hidden">
      {/* Header */}
      <div 
        className="px-8 py-6 text-white"
        style={{
          background: settings?.primary_color 
            ? `linear-gradient(to right, ${settings.primary_color}, ${settings.secondary_color || settings.primary_color})` 
            : 'linear-gradient(to right, #0f766e, #134e4a)'
        }}
      >
        <div className="flex justify-between items-center">
          <div className="flex items-center space-x-4">
            {/* Company Logo */}
            {settings?.logo_url ? (
              <div className="w-16 h-16 bg-white/10 rounded-lg p-2 flex items-center justify-center">
                <img 
                  src={settings.logo_url} 
                  alt="Logo entreprise" 
                  className="max-w-full max-h-full object-contain"
                  onError={(e) => {
                    console.log('Logo failed to load:', settings.logo_url);
                    e.target.style.display = 'none';
                  }}
                />
              </div>
            ) : (
              <div className="w-16 h-16 bg-white/10 rounded-lg p-2 flex items-center justify-center">
                <div className="text-white/70 text-xs text-center">
                  <div className="w-8 h-8 bg-white/20 rounded-md mb-1 flex items-center justify-center">
                    <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor">
                      <path d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M18,20H6V4H13V9H18V20Z" />
                    </svg>
                  </div>
                  <div className="text-[8px]">Logo</div>
                </div>
              </div>
            )}
            <div>
              <div className="flex items-center space-x-2 mb-1">
                <div className="px-3 py-2 bg-white/20 rounded-lg">
                  <span className="text-xl font-bold">
                    {isQuote ? 'SOUMISSION' : 'FACTURE'}
                  </span>
                </div>
              </div>
              <p className="font-medium text-lg opacity-90">{settings?.company_name || 'Mon Entreprise'}</p>
            </div>
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
                
                {/* Tax Numbers */}
                {(settings?.gst_number || settings?.pst_number || settings?.hst_number) && (
                  <div className="border-t border-gray-300 pt-2 mt-3">
                    {settings?.gst_number && (
                      <div className="text-xs text-gray-600">
                        <strong>TPS :</strong> {settings.gst_number}
                      </div>
                    )}
                    {settings?.pst_number && (
                      <div className="text-xs text-gray-600">
                        <strong>TVQ :</strong> {settings.pst_number}
                      </div>
                    )}
                    {settings?.hst_number && (
                      <div className="text-xs text-gray-600">
                        <strong>HST :</strong> {settings.hst_number}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Client Info */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-4">À:</h3>
            <div className="space-y-4">
              {/* Alternative dropdown while fixing Select component */}
              <div className="relative">
                <select 
                  value={formData.client_id}
                  onChange={(e) => setFormData(prev => ({ ...prev, client_id: e.target.value }))}
                  className="w-full h-10 px-3 py-2 bg-gray-50 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                >
                  <option value="">Sélectionner un client</option>
                  {clients.map(client => (
                    <option key={client.id} value={client.id}>
                      {client.name}
                    </option>
                  ))}
                </select>
              </div>

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
          <div 
            className="text-white p-4 rounded-t-lg"
            style={{
              backgroundColor: settings?.primary_color || '#0f766e'
            }}
          >
            <h3 className="font-semibold">Articles et Services</h3>
          </div>
          
          <div className="border border-t-0 rounded-b-lg overflow-hidden">
            <div 
              className="grid grid-cols-12 gap-2 p-3 text-sm font-medium"
              style={{
                backgroundColor: settings?.primary_color ? `${settings.primary_color}20` : '#f0fdfa',
                color: settings?.primary_color || '#134e4a'
              }}
            >
              <div className="col-span-5">Description</div>
              <div className="col-span-2 text-center">Quantité</div>
              <div className="col-span-2 text-center">Prix unitaire</div>
              <div className="col-span-2 text-center">Total</div>
              <div className="col-span-1 text-center">Action</div>
            </div>

            {formData.items.map((item, index) => (
              <div key={index} className="grid grid-cols-12 gap-2 p-3 border-t border-gray-200">
                <div className="col-span-5 space-y-2">
                  {/* Ligne Produit */}
                  <div className="flex items-center gap-2">
                    <label className="w-20 text-sm font-medium text-gray-700">Produit:</label>
                    <select 
                      data-item-index={index}
                      value={item.product_id || ''}
                      onChange={(e) => {
                        const productId = e.target.value;
                        console.log('Product selected:', productId);
                        
                        // Update directly in one step
                        const newItems = [...formData.items];
                        newItems[index] = { ...newItems[index], product_id: productId };
                        
                        // If a product is selected, populate the fields
                        if (productId) {
                          const product = products.find(p => p.id === productId);
                          if (product) {
                            newItems[index].description = product.name + (product.description ? ` - ${product.description}` : '');
                            newItems[index].unit_price = product.unit_price;
                          }
                        }
                        
                        setFormData(prev => ({ ...prev, items: newItems }));
                        console.log('Updated items:', newItems);
                      }}
                      className="flex-1 text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="">Sélectionner un produit</option>
                      {products.map(product => (
                        <option key={product.id} value={product.id}>
                          {product.name} - {formatCurrency(product.unit_price)}
                        </option>
                      ))}
                    </select>
                  </div>
                  
                  {/* Ligne Description */}
                  <div className="flex items-center gap-2">
                    <label className="w-20 text-sm font-medium text-gray-700">Description:</label>
                    <Input
                      value={item.description || ''}
                      onChange={(e) => handleItemChange(index, 'description', e.target.value)}
                      placeholder="Description du service/produit"
                      className="flex-1 text-sm"
                    />
                  </div>
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
                    value={item.unit_price || 0}
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
                style={{
                  color: settings?.primary_color || '#0f766e',
                  borderColor: settings?.primary_color || '#0f766e',
                }}
                className="border hover:opacity-80"
              >
                <Plus className="w-4 h-4 mr-2" />
                Ajouter un article
              </Button>
            </div>
          </div>
        </div>

        {/* Province and Tax Configuration */}
        <div className="mt-6 p-4 bg-blue-50 rounded-lg">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Configuration des taxes</h3>
          <div className="flex items-center gap-4">
            <label className="text-sm font-medium text-gray-700">Province:</label>
            <select 
              value={formData.province}
              onChange={(e) => {
                const province = e.target.value;
                setFormData(prev => {
                  if (province === 'ON') {
                    return {
                      ...prev,
                      province: province,
                      gst_rate: 0,
                      pst_rate: 0,
                      hst_rate: 13.0,
                      apply_gst: false,
                      apply_pst: false,
                      apply_hst: true
                    };
                  } else if (province === 'QC') {
                    return {
                      ...prev,
                      province: province,
                      gst_rate: 5.0,
                      pst_rate: 9.975,
                      hst_rate: 0,
                      apply_gst: true,
                      apply_pst: true,
                      apply_hst: false
                    };
                  }
                  return { ...prev, province: province };
                });
              }}
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="QC">Québec (TPS 5% + TVQ 9.975%)</option>
              <option value="ON">Ontario (HST 13%)</option>
            </select>
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
                  <div 
                    className="flex justify-between text-lg font-bold"
                    style={{
                      color: settings?.primary_color || '#0f766e'
                    }}
                  >
                    <span>TOTAL:</span>
                    <span>{formatCurrency(calculateTotal())}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Recurring Invoice Settings */}
        {!isQuote && (
          <div className="mt-6 p-4 bg-gray-50 rounded-lg">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Récurrence</h3>
            <div className="space-y-4">
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="is_recurring"
                  checked={formData.is_recurring}
                  onChange={(e) => setFormData(prev => ({ ...prev, is_recurring: e.target.checked }))}
                  className="mr-2"
                />
                <label htmlFor="is_recurring" className="text-sm font-medium text-gray-700">
                  Facture récurrente
                </label>
              </div>
              
              {formData.is_recurring && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 ml-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Fréquence
                    </label>
                    <select 
                      value={formData.recurrence_type}
                      onChange={(e) => setFormData(prev => ({ ...prev, recurrence_type: e.target.value }))}
                      className="w-full h-10 px-3 py-2 bg-white border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    >
                      <option value="weekly">Hebdomadaire</option>
                      <option value="monthly">Mensuel</option>
                      <option value="quarterly">Trimestriel</option>
                      <option value="yearly">Annuel</option>
                    </select>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Intervalle
                    </label>
                    <Input
                      type="number"
                      min="1"
                      max="12"
                      value={formData.recurrence_interval}
                      onChange={(e) => setFormData(prev => ({ ...prev, recurrence_interval: parseInt(e.target.value) || 1 }))}
                      placeholder="1"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Répéter tous les {formData.recurrence_interval} {
                        formData.recurrence_type === 'weekly' ? 'semaine(s)' :
                        formData.recurrence_type === 'monthly' ? 'mois' :
                        formData.recurrence_type === 'quarterly' ? 'trimestre(s)' : 'année(s)'
                      }
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

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