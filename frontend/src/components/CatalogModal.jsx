import React, { useState, useEffect } from 'react';
import { X, Search, Filter } from 'lucide-react';

export default function CatalogModal({ isOpen, onClose }) {
  const [products, setProducts] = useState([]);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen) {
      fetchProducts();
    }
  }, [isOpen, category]);

  const fetchProducts = async () => {
    setLoading(true);
    try {
      let url = '/api/v1/products?limit=50';
      if (category) url += `&category=${category}`;
      const res = await fetch(url);
      const data = await res.json();
      setProducts(data.items || []);
    } catch (err) {
      console.error('Failed to fetch catalog:', err);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  const filtered = products.filter(
    (p) =>
      p.name.toLowerCase().includes(search.toLowerCase()) ||
      p.brand.toLowerCase().includes(search.toLowerCase()) ||
      p.description.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h2 style={{ fontSize: '1.1rem', fontWeight: 700 }}>Database Product Catalog</h2>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Synthetic records seeded in SQLite (FastAPI + SQLAlchemy)
            </p>
          </div>
          <button className="close-btn" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div style={{ display: 'flex', gap: '10px', padding: '12px 20px', borderBottom: '1px solid var(--border-subtle)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'rgba(0,0,0,0.3)', padding: '6px 12px', borderRadius: '8px', flex: 1 }}>
            <Search size={15} color="var(--text-dim)" />
            <input
              type="text"
              placeholder="Search by model, brand, or feature..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ background: 'transparent', border: 'none', color: '#fff', width: '100%', outline: 'none', fontSize: '0.85rem' }}
            />
          </div>

          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border-subtle)', color: '#fff', padding: '6px 12px', borderRadius: '8px', fontSize: '0.85rem' }}
          >
            <option value="">All Categories</option>
            <option value="laptop">Laptops</option>
            <option value="smartphone">Smartphones</option>
            <option value="tablet">Tablets</option>
            <option value="monitor">Monitors</option>
            <option value="headphones">Headphones</option>
          </select>
        </div>

        <div className="modal-body">
          {loading ? (
            <div style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>Loading records...</div>
          ) : filtered.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>No products match your filter.</div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '14px' }}>
              {filtered.map((prod) => (
                <div
                  key={prod.id}
                  style={{
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: '8px',
                    padding: '12px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '6px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '0.7rem', color: '#a5b4fc', textTransform: 'uppercase', fontWeight: 700 }}>
                      {prod.category} • {prod.id}
                    </span>
                    <span style={{ fontSize: '0.88rem', fontWeight: 700, color: '#34d399', fontFamily: 'var(--font-mono)' }}>
                      ₹{prod.price.toLocaleString('en-IN')}
                    </span>
                  </div>
                  <strong style={{ fontSize: '0.9rem', color: '#fff' }}>{prod.name}</strong>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{prod.description}</p>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '4px' }}>
                    RAM: {prod.specs.ram_gb ? `${prod.specs.ram_gb}GB` : 'N/A'} | GPU: {prod.specs.gpu || 'None'} | Weight: {prod.specs.weight_kg ? `${prod.specs.weight_kg}kg` : 'N/A'}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
