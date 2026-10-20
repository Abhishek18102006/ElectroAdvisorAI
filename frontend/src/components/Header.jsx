import React from 'react';
import { Sparkles, Database, GitBranch, RefreshCw } from 'lucide-react';

export default function Header({ onReset, onOpenCatalog, onOpenArchitecture, backendHealth }) {
  const isHealthy = backendHealth && backendHealth.status === 'ok';

  return (
    <header className="app-header">
      <div className="brand-wrapper">
        <div className="brand-logo">⚡</div>
        <div className="brand-text">
          <h1>
            ElectroAdvisor AI
            <span className="brand-tag">FARM Stack</span>
          </h1>
          <p className="brand-subtitle">Smart Electronics Sales Assistant with Grounded Recommendations</p>
        </div>
      </div>

      <div className="header-actions">
        <div className="status-pill">
          <span className="status-dot"></span>
          <span>
            {isHealthy
              ? `Backend Ready (${backendHealth.products_count} Products)`
              : 'Connecting to API...'}
          </span>
        </div>

        <button className="btn-header" onClick={onOpenCatalog} title="Browse synthetic product catalog">
          <Database size={15} />
          <span>Catalog</span>
        </button>

        <button className="btn-header" onClick={onOpenArchitecture} title="View Mermaid & ASCII Architecture">
          <GitBranch size={15} />
          <span>Architecture</span>
        </button>

        <button className="btn-header btn-primary" onClick={onReset} title="Start fresh conversation">
          <RefreshCw size={14} />
          <span>New Chat</span>
        </button>
      </div>
    </header>
  );
}
