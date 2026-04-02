import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { BACKEND_URL, formatCurrency } from '../config';

const ProductsPage = () => {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [formData, setFormData] = useState({ name: '', description: '', unit_price: '', unit: 'unite', category: '' });

  useEffect(() => { fetchProducts(); }, []);

  const fetchProducts = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/products`);
      setProducts(response.data);
    } catch (err) {
      setError('Erreur lors du chargement des produits');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(''); setSuccess('');
    try {
      if (editingProduct) {
        await axios.put(`${BACKEND_URL}/api/products/${editingProduct.id}`, { ...formData, unit_price: parseFloat(formData.unit_price) });
        setSuccess('Produit modifie avec succes');
      } else {
        await axios.post(`${BACKEND_URL}/api/products`, { ...formData, unit_price: parseFloat(formData.unit_price) });
        setSuccess('Produit cree avec succes');
      }
      closeForm();
      fetchProducts();
    } catch (err) {
      setError('Erreur lors de la sauvegarde du produit');
    }
  };

  const handleEdit = (product) => {
    setEditingProduct(product);
    setFormData({ name: product.name, description: product.description || '', unit_price: String(product.unit_price), unit: product.unit || 'unite', category: product.category || '' });
    setShowForm(true);
  };

  const handleDuplicate = (product) => {
    setEditingProduct(null);
    setFormData({ name: `${product.name} (copie)`, description: product.description || '', unit_price: String(product.unit_price), unit: product.unit || 'unite', category: product.category || '' });
    setShowForm(true);
  };

  const closeForm = () => {
    setShowForm(false); setEditingProduct(null);
    setFormData({ name: '', description: '', unit_price: '', unit: 'unite', category: '' });
  };

  return (
    <div data-testid="products-page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <div style={{ fontSize: '32px', marginRight: '12px' }}>📦</div>
          <div>
            <h1 style={{ fontSize: '32px', fontWeight: '800', color: '#1f2937', margin: 0 }}>Produits & Services</h1>
            <p style={{ color: '#6b7280', margin: 0 }}>Gerez votre catalogue de produits et services</p>
          </div>
        </div>
        <button onClick={() => setShowForm(true)} data-testid="add-product-btn" style={{
          background: 'linear-gradient(135deg, #10b981, #047857)', color: 'white', border: 'none',
          padding: '14px 28px', borderRadius: '12px', cursor: 'pointer', fontWeight: '700', fontSize: '14px'
        }}>+ Nouveau Produit</button>
      </div>

      {error && <div style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#b91c1c', padding: '16px', borderRadius: '12px', marginBottom: '20px' }}>{error}</div>}
      {success && <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', color: '#166534', padding: '16px', borderRadius: '12px', marginBottom: '20px' }}>{success}</div>}

      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px' }}><p>Chargement des produits...</p></div>
      ) : products.length === 0 ? (
        <div style={{ background: 'white', border: '2px dashed #d1d5db', borderRadius: '16px', padding: '64px', textAlign: 'center' }}>
          <div style={{ fontSize: '80px', marginBottom: '24px' }}>📦</div>
          <h3 style={{ fontSize: '24px', fontWeight: '700', color: '#374151', margin: '0 0 12px 0' }}>Aucun produit cree</h3>
          <button onClick={() => setShowForm(true)} style={{ background: '#10b981', color: 'white', border: 'none', padding: '16px 32px', borderRadius: '12px', cursor: 'pointer', fontWeight: '700', fontSize: '16px' }}>
            Creer mon premier produit
          </button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '20px' }}>
          {products.map(product => (
            <div key={product.id} data-testid={`product-card-${product.id}`} style={{
              background: 'white', border: '1px solid #e5e7eb', borderRadius: '12px', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
                <h3 style={{ fontSize: '18px', fontWeight: '700', color: '#1f2937', margin: 0 }}>{product.name}</h3>
                {product.category && <span style={{ background: '#f3f4f6', color: '#374151', padding: '4px 8px', borderRadius: '6px', fontSize: '12px' }}>{product.category}</span>}
              </div>
              <p style={{ color: '#6b7280', fontSize: '14px', marginBottom: '16px' }}>{product.description}</p>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '16px', borderTop: '1px solid #e5e7eb' }}>
                <div>
                  <div style={{ fontSize: '20px', fontWeight: '800', color: '#10b981' }}>{formatCurrency(product.unit_price)}</div>
                  <div style={{ fontSize: '12px', color: '#6b7280' }}>par {product.unit}</div>
                </div>
                <div style={{ display: 'flex', gap: '6px' }}>
                  <button onClick={() => handleEdit(product)} data-testid={`edit-product-${product.id}`} style={{
                    background: '#f0f9ff', color: '#0369a1', border: 'none', padding: '8px 12px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px'
                  }}>Modifier</button>
                  <button onClick={() => handleDuplicate(product)} data-testid={`duplicate-product-${product.id}`} style={{
                    background: '#f0fdf4', color: '#166534', border: 'none', padding: '8px 12px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px'
                  }}>Dupliquer</button>
                  <button onClick={async () => {
                    if (window.confirm('Supprimer ce produit ?')) {
                      try { await axios.delete(`${BACKEND_URL}/api/products/${product.id}`); setSuccess('Produit supprime'); fetchProducts(); }
                      catch (err) { setError('Erreur suppression'); }
                    }
                  }} data-testid={`delete-product-${product.id}`} style={{
                    background: '#fef2f2', color: '#dc2626', border: 'none', padding: '8px 12px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px'
                  }}>Supprimer</button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {showForm && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '20px' }}>
          <div style={{ background: 'white', padding: '32px', borderRadius: '16px', width: '100%', maxWidth: '500px' }}>
            <h3 style={{ margin: '0 0 24px 0', fontSize: '20px', fontWeight: '700' }}>{editingProduct ? 'Modifier le produit' : 'Nouveau Produit/Service'}</h3>
            <form onSubmit={handleSubmit}>
              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Nom *</label>
                <input type="text" value={formData.name} onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                  required placeholder="Consultation, Kilometrage, Formation..." data-testid="product-name-input"
                  style={{ width: '100%', padding: '12px', border: '1px solid #ddd', borderRadius: '8px', boxSizing: 'border-box' }} />
              </div>
              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Description</label>
                <textarea value={formData.description} onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                  rows={3} placeholder="Description detaillee..."
                  style={{ width: '100%', padding: '12px', border: '1px solid #ddd', borderRadius: '8px', resize: 'vertical', boxSizing: 'border-box' }} />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px', marginBottom: '24px' }}>
                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Prix (CAD) *</label>
                  <input type="number" step="0.01" value={formData.unit_price} onChange={(e) => setFormData(prev => ({ ...prev, unit_price: e.target.value }))}
                    required data-testid="product-price-input"
                    style={{ width: '100%', padding: '12px', border: '1px solid #ddd', borderRadius: '8px', boxSizing: 'border-box' }} />
                </div>
                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Unite</label>
                  <select value={formData.unit} onChange={(e) => setFormData(prev => ({ ...prev, unit: e.target.value }))}
                    style={{ width: '100%', padding: '12px', border: '1px solid #ddd', borderRadius: '8px', boxSizing: 'border-box' }}>
                    <option value="unite">Unite</option><option value="heure">Heure</option>
                    <option value="km">Kilometre</option><option value="jour">Jour</option><option value="mois">Mois</option>
                  </select>
                </div>
                <div>
                  <label style={{ display: 'block', marginBottom: '6px', fontWeight: '600' }}>Categorie</label>
                  <input type="text" value={formData.category} onChange={(e) => setFormData(prev => ({ ...prev, category: e.target.value }))}
                    placeholder="Services, Transport..."
                    style={{ width: '100%', padding: '12px', border: '1px solid #ddd', borderRadius: '8px', boxSizing: 'border-box' }} />
                </div>
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                <button type="button" onClick={closeForm} style={{
                  background: 'white', color: '#374151', border: '1px solid #d1d5db', padding: '12px 24px', borderRadius: '8px', cursor: 'pointer'
                }}>Annuler</button>
                <button type="submit" data-testid="save-product-btn" style={{
                  background: '#10b981', color: 'white', border: 'none', padding: '12px 24px', borderRadius: '8px', cursor: 'pointer', fontWeight: '600'
                }}>{editingProduct ? 'Modifier' : 'Creer le produit'}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default ProductsPage;
