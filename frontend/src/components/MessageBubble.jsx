import React from 'react';
import ProductCard from './ProductCard';
import TradeOffMatrix from './TradeOffMatrix';

export default function MessageBubble({ message }) {
  const isAgent = message.sender === 'agent';
  const isCustomer = message.sender === 'customer';
  const metadata = message.metadata || {};
  const recommendations = metadata.recommendations || [];
  const tradeOffs = metadata.trade_offs || [];

  // Simple formatting helper for markdown-like bold and bullet lines
  const renderFormattedText = (text) => {
    if (!text) return null;
    const lines = text.split('\n');

    return lines.map((line, idx) => {
      // Process bold markers **text**
      const parts = line.split(/(\*\*.*?\*\*)/g);
      const formattedParts = parts.map((part, pIdx) => {
        if (part.startsWith('**') && part.endsWith('**')) {
          return <strong key={pIdx}>{part.slice(2, -2)}</strong>;
        }
        return part;
      });

      return (
        <React.Fragment key={idx}>
          {formattedParts}
          {idx < lines.length - 1 && <br />}
        </React.Fragment>
      );
    });
  };

  return (
    <div className={`message-row ${message.sender}`}>
      <div className={`avatar ${message.sender}`}>
        {isAgent ? '⚡' : '👤'}
      </div>

      <div className="message-content-wrapper">
        <div className="message-bubble">
          {renderFormattedText(message.content)}

          {/* Render Grounded Product Recommendations */}
          {recommendations.length > 0 && (
            <div className="recommendations-container">
              <div className="product-cards-grid">
                {recommendations.map((item, idx) => (
                  <ProductCard key={item.product.id || idx} item={item} rank={idx + 1} />
                ))}
              </div>

              {/* Render Trade-Off Comparison Matrix */}
              {tradeOffs.length > 0 && (
                <TradeOffMatrix
                  tradeOffs={tradeOffs}
                  productNames={recommendations.map((r) => r.product.name)}
                />
              )}
            </div>
          )}
        </div>

        {message.created_at && (
          <div className="message-time">
            {new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </div>
        )}
      </div>
    </div>
  );
}
