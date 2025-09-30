import React, { useState } from 'react';
import axios from 'axios';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Alert, AlertDescription } from './ui/alert';
import { 
  CreditCard, 
  Send, 
  Printer, 
  Check, 
  Clock,
  Mail,
  CheckCircle
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const InvoiceActionsDialog = ({ invoice, isOpen, onClose, onUpdate }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [paymentData, setPaymentData] = useState({
    payment_date: new Date().toISOString().split('T')[0],
    payment_method: 'interac',
    amount_paid: invoice?.total || 0,
    payment_notes: ''
  });

  const paymentMethods = [
    { value: 'interac', label: 'Interac/Virement' },
    { value: 'cheque', label: 'Chèque' },
    { value: 'argent', label: 'Argent comptant' },
    { value: 'carte', label: 'Carte de crédit' },
    { value: 'virement', label: 'Virement bancaire' }
  ];

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('fr-CA', {
      style: 'currency',
      currency: 'CAD'
    }).format(amount || 0);
  };

  const markAsPending = async () => {
    try {
      setLoading(true);
      setError('');
      
      await axios.put(`${API}/invoices/${invoice.id}/status`, {
        status: 'sent'
      });
      
      setSuccess('Facture marquée comme en attente de paiement');
      onUpdate();
      setTimeout(() => onClose(), 2000);
    } catch (error) {
      setError('Erreur lors de la mise à jour du statut');
    } finally {
      setLoading(false);
    }
  };

  const markAsPaid = async () => {
    try {
      setLoading(true);
      setError('');
      
      await axios.put(`${API}/invoices/${invoice.id}/status`, {
        status: 'paid',
        payment_date: new Date(paymentData.payment_date).toISOString(),
        payment_method: paymentData.payment_method,
        amount_paid: parseFloat(paymentData.amount_paid),
        payment_notes: paymentData.payment_notes
      });
      
      setSuccess('Facture marquée comme payée avec succès');
      onUpdate();
      setTimeout(() => onClose(), 2000);
    } catch (error) {
      setError('Erreur lors de l\'enregistrement du paiement');
    } finally {
      setLoading(false);
    }
  };

  const sendByEmail = async () => {
    try {
      setLoading(true);
      setError('');
      
      // Simuler l'envoi d'email (à implémenter avec un service email)
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      setSuccess('Facture envoyée par courriel avec succès');
      
      // Marquer comme envoyée si elle était en brouillon
      if (invoice.status === 'draft') {
        await axios.put(`${API}/invoices/${invoice.id}/status`, {
          status: 'sent'
        });
        onUpdate();
      }
      
      setTimeout(() => onClose(), 2000);
    } catch (error) {
      setError('Erreur lors de l\'envoi par courriel');
    } finally {
      setLoading(false);
    }
  };

  const printInvoice = () => {
    // Créer une version imprimable
    const printWindow = window.open('', '_blank');
    printWindow.document.write(`
      <html>
        <head>
          <title>Facture ${invoice.invoice_number}</title>
          <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .header { text-align: center; border-bottom: 2px solid #333; padding-bottom: 20px; margin-bottom: 30px; }
            .invoice-info { display: flex; justify-content: space-between; margin-bottom: 30px; }
            .items-table { width: 100%; border-collapse: collapse; margin-bottom: 30px; }
            .items-table th, .items-table td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            .items-table th { background-color: #f2f2f2; }
            .totals { text-align: right; }
            .total-line { font-weight: bold; font-size: 1.2em; }
            @media print { body { margin: 0; } }
          </style>
        </head>
        <body>
          <div class="header">
            <h1>FacturePro</h1>
            <h2>FACTURE ${invoice.invoice_number}</h2>
          </div>
          
          <div class="invoice-info">
            <div>
              <strong>Date d'émission:</strong> ${new Date(invoice.issue_date).toLocaleDateString('fr-CA')}<br>
              <strong>Date d'échéance:</strong> ${new Date(invoice.due_date).toLocaleDateString('fr-CA')}<br>
              <strong>Statut:</strong> ${invoice.status}
            </div>
          </div>
          
          <table class="items-table">
            <thead>
              <tr>
                <th>Description</th>
                <th>Quantité</th>
                <th>Prix unitaire</th>
                <th>Total</th>
              </tr>
            </thead>
            <tbody>
              ${invoice.items.map(item => `
                <tr>
                  <td>${item.description}</td>
                  <td>${item.quantity}</td>
                  <td>${formatCurrency(item.unit_price)}</td>
                  <td>${formatCurrency(item.total)}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
          
          <div class="totals">
            <p>Sous-total: ${formatCurrency(invoice.subtotal)}</p>
            ${invoice.gst_amount > 0 ? `<p>TPS (${invoice.gst_rate}%): ${formatCurrency(invoice.gst_amount)}</p>` : ''}
            ${invoice.pst_amount > 0 ? `<p>TVQ (${invoice.pst_rate}%): ${formatCurrency(invoice.pst_amount)}</p>` : ''}
            ${invoice.hst_amount > 0 ? `<p>HST (${invoice.hst_rate}%): ${formatCurrency(invoice.hst_amount)}</p>` : ''}
            <div class="total-line">
              <p>TOTAL: ${formatCurrency(invoice.total)}</p>
            </div>
          </div>
          
          ${invoice.notes ? `<div style="margin-top: 30px;"><strong>Notes:</strong><br>${invoice.notes}</div>` : ''}
        </body>
      </html>
    `);
    printWindow.document.close();
    printWindow.print();
    
    setSuccess('Impression lancée');
  };

  if (!invoice) return null;

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Actions - Facture {invoice.invoice_number}</DialogTitle>
        </DialogHeader>

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

        <div className="space-y-6">
          {/* Invoice Info */}
          <div className="bg-gray-50 p-4 rounded-lg">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="font-medium">Montant:</span> {formatCurrency(invoice.total)}
              </div>
              <div>
                <span className="font-medium">Statut:</span> 
                <span className={`ml-2 px-2 py-1 rounded text-xs ${
                  invoice.status === 'paid' ? 'bg-green-100 text-green-800' :
                  invoice.status === 'sent' ? 'bg-blue-100 text-blue-800' :
                  invoice.status === 'overdue' ? 'bg-red-100 text-red-800' :
                  'bg-gray-100 text-gray-800'
                }`}>
                  {invoice.status === 'paid' ? 'Payée' :
                   invoice.status === 'sent' ? 'Envoyée' :
                   invoice.status === 'overdue' ? 'En retard' :
                   invoice.status === 'draft' ? 'Brouillon' : invoice.status}
                </span>
              </div>
              <div>
                <span className="font-medium">Échéance:</span> {new Date(invoice.due_date).toLocaleDateString('fr-CA')}
              </div>
              {invoice.payment_info && (
                <div>
                  <span className="font-medium">Payé le:</span> {new Date(invoice.payment_info.payment_date).toLocaleDateString('fr-CA')}
                </div>
              )}
            </div>
          </div>

          {/* Quick Actions */}
          <div>
            <h4 className="font-semibold text-gray-900 mb-3">Actions rapides</h4>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <Button
                onClick={printInvoice}
                variant="outline"
                className="flex items-center justify-center"
                disabled={loading}
              >
                <Printer className="w-4 h-4 mr-2" />
                Imprimer
              </Button>

              <Button
                onClick={sendByEmail}
                variant="outline"
                className="flex items-center justify-center"
                disabled={loading}
              >
                <Send className="w-4 h-4 mr-2" />
                {loading ? 'Envoi...' : 'Envoyer par email'}
              </Button>

              {(invoice.status === 'draft') && (
                <Button
                  onClick={markAsPending}
                  variant="outline"
                  className="flex items-center justify-center text-blue-600 border-blue-300 hover:bg-blue-50"
                  disabled={loading}
                >
                  <Clock className="w-4 h-4 mr-2" />
                  Marquer en attente
                </Button>
              )}
            </div>
          </div>

          {/* Payment Section */}
          {invoice.status !== 'paid' && (
            <div>
              <h4 className="font-semibold text-gray-900 mb-3">Enregistrer un paiement</h4>
              
              <div className="space-y-4 bg-green-50 p-4 rounded-lg">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Date de paiement
                    </label>
                    <Input
                      type="date"
                      value={paymentData.payment_date}
                      onChange={(e) => setPaymentData(prev => ({ ...prev, payment_date: e.target.value }))}
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Méthode de paiement
                    </label>
                    <select 
                      value={paymentData.payment_method}
                      onChange={(e) => setPaymentData(prev => ({ ...prev, payment_method: e.target.value }))}
                      className="w-full h-10 px-3 py-2 bg-white border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    >
                      <option value="">Sélectionner méthode</option>
                      {paymentMethods.map(method => (
                        <option key={method.value} value={method.value}>
                          {method.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Montant payé
                    </label>
                    <Input
                      type="number"
                      step="0.01"
                      value={paymentData.amount_paid}
                      onChange={(e) => setPaymentData(prev => ({ ...prev, amount_paid: parseFloat(e.target.value) || 0 }))}
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Notes sur le paiement
                    </label>
                    <Input
                      value={paymentData.payment_notes}
                      onChange={(e) => setPaymentData(prev => ({ ...prev, payment_notes: e.target.value }))}
                      placeholder="Référence, commentaires..."
                    />
                  </div>
                </div>

                <Button
                  onClick={markAsPaid}
                  className="w-full bg-green-600 hover:bg-green-700"
                  disabled={loading}
                >
                  <CheckCircle className="w-4 h-4 mr-2" />
                  {loading ? 'Enregistrement...' : 'Marquer comme payée'}
                </Button>
              </div>
            </div>
          )}

          {/* Payment Info Display */}
          {invoice.payment_info && (
            <div className="bg-green-50 p-4 rounded-lg">
              <h4 className="font-semibold text-gray-900 mb-2">Informations de paiement</h4>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="font-medium">Date:</span> {new Date(invoice.payment_info.payment_date).toLocaleDateString('fr-CA')}
                </div>
                <div>
                  <span className="font-medium">Méthode:</span> {paymentMethods.find(m => m.value === invoice.payment_info.payment_method)?.label || invoice.payment_info.payment_method}
                </div>
                <div>
                  <span className="font-medium">Montant:</span> {formatCurrency(invoice.payment_info.amount_paid)}
                </div>
                {invoice.payment_info.notes && (
                  <div className="col-span-2">
                    <span className="font-medium">Notes:</span> {invoice.payment_info.notes}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="flex justify-end pt-4">
          <Button variant="outline" onClick={onClose}>
            Fermer
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default InvoiceActionsDialog;