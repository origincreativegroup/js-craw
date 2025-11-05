import { useState, useRef, useEffect } from 'react';
import { Send, Sparkles, Bot, User, Loader2, X, Minimize2, Maximize2 } from 'lucide-react';
import Button from './Button';
import { sendChatMessage } from '../services/api';
import './AIChat.css';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  error?: boolean;
}

interface AIChatProps {
  jobTitle?: string;
  company?: string;
  jobId?: number;
  onAction?: (action: string) => void;
  className?: string;
  minimized?: boolean;
  onMinimize?: () => void;
  onClose?: () => void;
}

const AIChat = ({ 
  jobTitle, 
  company, 
  jobId,
  onAction, 
  className = '',
  minimized = false,
  onMinimize,
  onClose 
}: AIChatProps) => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: jobTitle && company
        ? `I'm here to help you with follow-up strategies for **${jobTitle}** at **${company}**. I can help with:\n\n• When to follow up\n• Email templates\n• Interview prep\n• Career advice\n\nWhat would you like to know?`
        : 'I'm your AI assistant for job search follow-ups. How can I help you today?',
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isMinimized, setIsMinimized] = useState(minimized);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    setIsMinimized(minimized);
  }, [minimized]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    const currentInput = input;
    setInput('');
    setIsLoading(true);

    try {
      const response = await sendChatMessage(currentInput, jobId);
      
      const aiResponse: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.response,
        timestamp: new Date(),
        error: response.error,
      };
      
      setMessages((prev) => [...prev, aiResponse]);
    } catch (error) {
      console.error('Error sending message:', error);
      const errorResponse: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please check your connection and try again.',
        timestamp: new Date(),
        error: true,
      };
      setMessages((prev) => [...prev, errorResponse]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleMinimize = () => {
    setIsMinimized(!isMinimized);
    onMinimize?.();
  };

  if (isMinimized) {
    return (
      <div className={`ai-chat-minimized ${className}`}>
        <div className="ai-chat-minimized-header" onClick={handleMinimize}>
          <div className="ai-chat-header-content">
            <div className="ai-avatar">
              <Sparkles size={16} />
            </div>
            <span className="ai-chat-title">AI Assistant</span>
          </div>
          <Maximize2 size={16} />
        </div>
      </div>
    );
  }

  return (
    <div className={`ai-chat ${className}`}>
      <div className="ai-chat-header">
        <div className="ai-chat-header-content">
          <div className="ai-avatar">
            <Sparkles size={20} />
          </div>
          <div>
            <h3 className="ai-chat-title">AI Follow-Up Assistant</h3>
            <p className="ai-chat-subtitle">
              {jobTitle && company ? `${jobTitle} @ ${company}` : 'Get personalized guidance'}
            </p>
          </div>
        </div>
        <div className="ai-chat-actions">
          {onMinimize && (
            <button className="ai-chat-action-btn" onClick={handleMinimize} title="Minimize">
              <Minimize2 size={16} />
            </button>
          )}
          {onClose && (
            <button className="ai-chat-action-btn" onClick={onClose} title="Close">
              <X size={16} />
            </button>
          )}
        </div>
      </div>

      <div className="ai-chat-messages">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`message ${message.role === 'user' ? 'message-user' : 'message-assistant'} ${message.error ? 'message-error' : ''}`}
          >
            <div className="message-avatar">
              {message.role === 'user' ? (
                <User size={16} />
              ) : (
                <Bot size={16} />
              )}
            </div>
            <div className="message-content">
              <div className="message-text">{message.content}</div>
              <div className="message-time">
                {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </div>
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="message message-assistant">
            <div className="message-avatar">
              <Bot size={16} />
            </div>
            <div className="message-content">
              <div className="message-loading">
                <Loader2 size={16} className="spinner" />
                <span>AI is thinking...</span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="ai-chat-input">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Ask about follow-up strategies, timing, or templates..."
          className="chat-input"
          disabled={isLoading}
        />
        <Button
          variant="primary"
          size="sm"
          icon={<Send size={16} />}
          onClick={handleSend}
          disabled={!input.trim() || isLoading}
        >
          Send
        </Button>
      </div>
    </div>
  );
};

export default AIChat;
