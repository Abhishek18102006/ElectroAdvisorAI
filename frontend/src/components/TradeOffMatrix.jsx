import React from 'react';
import { Scale } from 'lucide-react';

export default function TradeOffMatrix({ tradeOffs, productNames }) {
  if (!tradeOffs || tradeOffs.length === 0) return null;

  return (
    <div className="tradeoff-card">
      <div className="tradeoff-header">
        <Scale size={18} />
        <span>Side-by-Side Trade-off Analysis</span>
      </div>

      <table className="tradeoff-table">
        <thead>
          <tr>
            <th style={{ width: '25%' }}>Aspect</th>
            <th style={{ width: '35%' }}>{productNames[0] || 'Option 1'}</th>
            <th style={{ width: '40%' }}>{productNames[1] || 'Option 2'}</th>
          </tr>
        </thead>
        <tbody>
          {tradeOffs.map((row, idx) => (
            <tr key={`tradeoff-${idx}`}>
              <td>
                <strong>{row.criterion}</strong>
              </td>
              <td>
                <span className="spec-val">{row.product_1_verdict}</span>
              </td>
              <td>
                <span className="spec-val">{row.product_2_verdict}</span>
                {row.trade_off_explanation && (
                  <div className="tradeoff-expl">{row.trade_off_explanation}</div>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
