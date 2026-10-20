import React from 'react';
import { Cpu, ShieldCheck, Sliders, CheckCircle2, HelpCircle } from 'lucide-react';

export default function StateInspector({ state }) {
  if (!state) return null;

  const {
    category = 'laptop',
    budget_max,
    budget_min,
    primary_uses = [],
    hard_constraints = {},
    preferences = {},
    missing_fields = [],
    is_ready_for_recommendation,
    turn_count = 0,
  } = state;

  return (
    <aside className="state-sidebar">
      <div className="sidebar-title">
        <Cpu size={16} />
        <span>Agent Memory & Requirements</span>
      </div>

      <div className="state-card">
        <div className="state-group">
          <span className="state-label">Target Category</span>
          <span className="state-val" style={{ textTransform: 'capitalize' }}>
            {category || 'Laptop'}
          </span>
        </div>

        <div className="state-group">
          <span className="state-label">Max Budget (Hard Cap)</span>
          <span className="state-val highlight">
            {budget_max ? `₹${budget_max.toLocaleString('en-IN')}` : 'Not Specified Yet'}
          </span>
          {budget_min && (
            <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
              Min: ₹{budget_min.toLocaleString('en-IN')}
            </span>
          )}
        </div>

        <div className="state-group">
          <span className="state-label">Primary Uses</span>
          {primary_uses.length > 0 ? (
            <div className="tags-row">
              {primary_uses.map((u, i) => (
                <span key={i} className="tag-badge">
                  {u.replace('_', ' ')}
                </span>
              ))}
            </div>
          ) : (
            <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>None identified yet</span>
          )}
        </div>
      </div>

      <div className="state-card">
        <div className="sidebar-title" style={{ fontSize: '0.8rem', paddingBottom: '4px' }}>
          <ShieldCheck size={14} color="#f87171" />
          <span>Mandatory Constraints</span>
        </div>

        <div className="tags-row">
          {hard_constraints.max_budget && (
            <span className="tag-badge constraint">Max: ₹{hard_constraints.max_budget.toLocaleString('en-IN')}</span>
          )}
          {hard_constraints.min_ram_gb && (
            <span className="tag-badge constraint">RAM ≥ {hard_constraints.min_ram_gb} GB</span>
          )}
          {hard_constraints.requires_gpu && (
            <span className="tag-badge constraint">Dedicated GPU (CUDA)</span>
          )}
          {hard_constraints.required_os && (
            <span className="tag-badge constraint">OS: {hard_constraints.required_os}</span>
          )}
          {!hard_constraints.max_budget && !hard_constraints.min_ram_gb && !hard_constraints.requires_gpu && (
            <span style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>No hard constraints locked</span>
          )}
        </div>
      </div>

      <div className="state-card">
        <div className="sidebar-title" style={{ fontSize: '0.8rem', paddingBottom: '4px' }}>
          <Sliders size={14} color="#34d399" />
          <span>Soft Preferences</span>
        </div>

        <div className="tags-row">
          {preferences.portability && (
            <span className="tag-badge preference">Campus Portability (Lightweight)</span>
          )}
          {preferences.battery_priority && (
            <span className="tag-badge preference">Long Battery Life</span>
          )}
          {preferences.ml_environment && (
            <span className="tag-badge preference">ML: {preferences.ml_environment}</span>
          )}
          {!preferences.portability && !preferences.battery_priority && !preferences.ml_environment && (
            <span style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>None specified</span>
          )}
        </div>
      </div>

      <div className="state-card">
        <div className="state-group">
          <span className="state-label">Orchestrator Status</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '4px' }}>
            {is_ready_for_recommendation ? (
              <>
                <CheckCircle2 size={16} color="#34d399" />
                <span style={{ fontSize: '0.84rem', color: '#34d399', fontWeight: 600 }}>
                  Ready & Recommended
                </span>
              </>
            ) : (
              <>
                <HelpCircle size={16} color="#fbbf24" />
                <span style={{ fontSize: '0.84rem', color: '#fbbf24', fontWeight: 600 }}>
                  Clarifying Missing Details
                </span>
              </>
            )}
          </div>
          <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '2px' }}>
            Turn Count: {turn_count}
          </span>
        </div>
      </div>
    </aside>
  );
}
