import React from 'react';
import { X, Layers } from 'lucide-react';

export default function ArchitectureModal({ isOpen, onClose }) {
  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" style={{ maxWidth: '850px' }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Layers size={18} color="#6366f1" />
            <h2 style={{ fontSize: '1.1rem', fontWeight: 700 }}>System Architecture & Decision Flow</h2>
          </div>
          <button className="close-btn" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className="modal-body">
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            This diagram illustrates the multi-tier FARM architecture (FastAPI + React + SQLite) and the AI recommendation agent workflow.
          </p>

          <div
            style={{
              background: '#0a0f1d',
              padding: '16px',
              borderRadius: '8px',
              border: '1px solid rgba(255,255,255,0.1)',
              overflowX: 'auto',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.74rem',
              lineHeight: 1.4,
              color: '#93c5fd',
            }}
          >
            <pre>{` ┌─────────────────────────────────────────────────────────┐
 │                     REACT FRONTEND                      │
 │    (Chat Interface, Product Cards, Trade-off Display)   │
 └──────────────────────────┬──────────────────────────────┘
                            │ 1. Customer Message
                            ▼
 ┌─────────────────────────────────────────────────────────┐
 │                   FASTAPI BACKEND                       │
 │  (/conversations/{id}/messages, Validation, Routing)    │
 └──────────────────────────┬──────────────────────────────┘
                            │ 2. Process Message
                            ▼
 ┌─────────────────────────────────────────────────────────┐
 │               AI AGENT ORCHESTRATION                    │
 │  ┌──────────────┐   ┌─────────────┐   ┌──────────────┐  │
 │  │ LLM Engine   │──▶│ State       │──▶│ Orchestrator │  │
 │  │ (Extraction) │   │ Manager     │   │ (Decision)   │  │
 │  └──────────────┘   └─────────────┘   └──────┬───────┘  │
 └──────────────────────────────────────────────┼──────────┘
           ▲                                    │ 3. Check Info
           │ (Missing Info: Loop back to UI)    ▼
           │                           /─────────────────\\
           └──────────────────────────/ Enough Info for   \\
                                      \\ Recommendation?   /
                                       \\─────────────────/
                                                │ (Yes)
                                                ▼
 ┌─────────────────────────────────────────────────────────┐
 │              FILTERING & RANKING ENGINE                 │
 │  ┌──────────────────────┐       ┌────────────────────┐  │
 │  │ Filtering Engine     │──────▶│ Ranking Engine     │  │
 │  │ (Hard constraints:   │       │ (Soft preferences: │  │
 │  │ Budget, Category)    │       │ Portability, Specs)│  │
 │  └──────────┬───────────┘       └─────────┬──────────┘  │
 └─────────────┼─────────────────────────────┼─────────────┘
               │ 4. Query Matching Items     │ 5. Select Top 2 
               ▼                             ▼
 ┌─────────────────────────────────────────────────────────┐
 │                   SQLITE DATABASE                       │
 │ ┌──────────────────┐ ┌────────────────┐ ┌─────────────┐ │
 │ │ Products Catalog │ │ Conversations  │ │ Messages    │ │
 │ └──────────────────┘ └────────────────┘ └─────────────┘ │
 └─────────────────────────────────────────────────────────┘`}</pre>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginTop: '6px' }}>
            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '12px', borderRadius: '8px' }}>
              <strong style={{ fontSize: '0.85rem', color: '#6ee7b7' }}>1. State & Clarification Loop</strong>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                The agent tracks requirements across conversation turns without forgetting context. When essential details (e.g. use case or budget) are missing, it asks one focused follow-up instead of blindly interrogating the customer.
              </p>
            </div>
            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '12px', borderRadius: '8px' }}>
              <strong style={{ fontSize: '0.85rem', color: '#93c5fd' }}>2. Two-Stage Hard/Soft Engine</strong>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                Hard constraints (strict budget ceiling, category, 16GB RAM for ML) are enforced in Python code. Remaining candidates are ranked by preference alignment, selecting the top 2 with clear trade-offs.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
