import React, { useState, useEffect, useRef } from 'react';
import Header from './components/Header';
import MessageBubble from './components/MessageBubble';
import StateInspector from './components/StateInspector';
import CatalogModal from './components/CatalogModal';
import ArchitectureModal from './components/ArchitectureModal';
import { Send } from 'lucide-react';

const API_BASE = '/api/v1';

export default function App() {
  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [currentState, setCurrentState] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [backendHealth, setBackendHealth] = useState(null);

  const [catalogOpen, setCatalogOpen] = useState(false);
  const [architectureOpen, setArchitectureOpen] = useState(false);

  const messagesEndRef = useRef(null);

  useEffect(() => {
    checkHealth();
    startNewConversation();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const checkHealth = async () => {
    try {
      const res = await fetch(`${API_BASE}/health`);
      if (res.ok) {
        const data = await res.json();
        setBackendHealth(data);
      }
    } catch (err) {
      console.warn('Backend health check error:', err);
    }
  };

  const startNewConversation = async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/conversations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      const data = await res.json();
      setConversationId(data.id);
      setCurrentState(data.state || null);

      // Seed initial welcoming message
      setMessages([
        {
          id: 'welcome',
          sender: 'agent',
          content:
            "Hello! Welcome to our electronics store. I'm your AI sales assistant. " +
            "Are you looking for a laptop, smartphone, tablet, monitor, or headphones today? " +
            "Tell me what you plan to use it for, and I'll recommend the two most suitable models with clear reasons and trade-offs.",
          created_at: new Date().toISOString(),
          metadata: {},
        },
      ]);
    } catch (err) {
      console.error('Failed to initialize conversation:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSendMessage = async (textToSend) => {
    const text = (textToSend || inputText).trim();
    if (!text || isLoading || !conversationId) return;

    setInputText('');

    // Append customer message immediately in UI
    const tempUserMsg = {
      id: `user-${Date.now()}`,
      sender: 'customer',
      content: text,
      created_at: new Date().toISOString(),
      metadata: {},
    };

    setMessages((prev) => [...prev, tempUserMsg]);
    setIsLoading(true);

    try {
      const res = await fetch(`${API_BASE}/conversations/${conversationId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: text }),
      });

      if (!res.ok) {
        throw new Error(`API error: ${res.statusText}`);
      }

      const data = await res.json();
      setMessages((prev) => [...prev, data.agent_message]);
      setCurrentState(data.decision?.state || null);
    } catch (err) {
      console.error('Failed to send message:', err);
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          sender: 'agent',
          content: "I'm having trouble connecting to the backend server. Please verify the FastAPI server is running.",
          created_at: new Date().toISOString(),
          metadata: {},
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const quickPrompts = [
    'I need a laptop for college.',
    'Programming and machine learning. My budget is limited.',
    'Around ₹80,000. Mostly local experiments, and I carry it around campus.',
    'Gaming laptop under ₹90,000 with 16GB RAM',
    'Lightweight MacBook for coding under ₹1,20,000',
    'Actually, my budget changed to ₹60,000.',
  ];

  return (
    <div className="app-container">
      <Header
        onReset={startNewConversation}
        onOpenCatalog={() => setCatalogOpen(true)}
        onOpenArchitecture={() => setArchitectureOpen(true)}
        backendHealth={backendHealth}
      />

      <div className="main-content">
        <main className="chat-pane">
          <div className="messages-area">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}

            {isLoading && (
              <div className="message-row agent">
                <div className="avatar agent">⚡</div>
                <div className="typing-bubble">
                  <span className="typing-dot"></span>
                  <span className="typing-dot"></span>
                  <span className="typing-dot"></span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="quick-prompts">
            {quickPrompts.map((prompt, idx) => (
              <button
                key={idx}
                className="chip-btn"
                onClick={() => handleSendMessage(prompt)}
                disabled={isLoading}
              >
                {prompt}
              </button>
            ))}
          </div>

          <div className="input-area">
            <div className="input-box-wrapper">
              <input
                type="text"
                className="chat-input"
                placeholder="Type your needs or questions (e.g. 'I need a laptop for machine learning under 80k')..."
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isLoading}
              />
              <button
                className="send-btn"
                onClick={() => handleSendMessage()}
                disabled={isLoading || !inputText.trim()}
                title="Send message"
              >
                <Send size={16} />
              </button>
            </div>
          </div>
        </main>

        <StateInspector state={currentState} />
      </div>

      <CatalogModal isOpen={catalogOpen} onClose={() => setCatalogOpen(false)} />
      <ArchitectureModal isOpen={architectureOpen} onClose={() => setArchitectureOpen(false)} />
    </div>
  );
}
