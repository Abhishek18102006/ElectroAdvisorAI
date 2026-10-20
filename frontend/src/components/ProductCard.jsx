import React from 'react';
import { Check, AlertCircle, Zap } from 'lucide-react';

export default function ProductCard({ item, rank }) {
  const { product, why_recommended, key_advantages, potential_drawbacks, suitability_score } = item;
  const specs = product.specs || {};

  return (
    <div className="product-card">
      <div className="product-header">
        <div>
          <span className="product-brand">{product.brand} • Choice #{rank}</span>
          <h3 className="product-name">{product.name}</h3>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div className="product-price">₹{product.price.toLocaleString('en-IN')}</div>
          {suitability_score > 0 && (
            <div className="score-badge">
              <Zap size={11} />
              <span>{Math.round(suitability_score)}% Match</span>
            </div>
          )}
        </div>
      </div>

      <div className="specs-grid">
        <div className="spec-item">
          <span className="spec-label">Processor</span>
          <span className="spec-val" title={specs.cpu}>{specs.cpu ? specs.cpu.split('(')[0] : 'N/A'}</span>
        </div>
        <div className="spec-item">
          <span className="spec-label">Memory</span>
          <span className="spec-val">{specs.ram_gb ? `${specs.ram_gb} GB RAM` : 'N/A'}</span>
        </div>
        <div className="spec-item">
          <span className="spec-label">Graphics (GPU)</span>
          <span className="spec-val" title={specs.gpu}>{specs.gpu || 'Integrated'}</span>
        </div>
        <div className="spec-item">
          <span className="spec-label">Storage</span>
          <span className="spec-val">{specs.storage_gb ? `${specs.storage_gb} GB SSD` : 'N/A'}</span>
        </div>
        <div className="spec-item">
          <span className="spec-label">Weight</span>
          <span className="spec-val">{specs.weight_kg ? `${specs.weight_kg} kg` : 'N/A'}</span>
        </div>
        <div className="spec-item">
          <span className="spec-label">Battery Life</span>
          <span className="spec-val">{specs.battery_life_hours ? `~${specs.battery_life_hours} hrs` : 'N/A'}</span>
        </div>
      </div>

      {why_recommended && (
        <div className="why-recommended-box">
          <strong>Why this model:</strong> {why_recommended}
        </div>
      )}

      <div className="pros-cons-list">
        {key_advantages && key_advantages.slice(0, 2).map((adv, idx) => (
          <div key={`pro-${idx}`} className="pro-item">
            <Check size={12} />
            <span>{adv}</span>
          </div>
        ))}
        {potential_drawbacks && potential_drawbacks.slice(0, 1).map((con, idx) => (
          <div key={`con-${idx}`} className="con-item">
            <AlertCircle size={12} />
            <span>{con}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
