import { useState, useEffect, useRef } from 'react';
import { MessageSquare, X, Minimize2, Maximize2, ExternalLink } from 'lucide-react';
import Button from './Button';
import { getOpenWebUIInfo } from '../services/api';
import './OpenWebUIChat.css';

interface OpenWebUIChatProps {
  jobId?: number;
  jobTitle?: string;
  company?: string;
  className?: string;
  minimized?: boolean;
  onMinimize?: () => void;
  onClose?: () => void;
}

const OpenWebUIChat = ({
  jobId,
  jobTitle,
  company,
  className = '',
  minimized = false,
  onMinimize,
  onClose,
}: OpenWebUIChatProps) => {
  const [isMinimized, setIsMinimized] = useState(minimized);
  const [openwebuiUrl, setOpenwebuiUrl] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    loadOpenWebUIInfo();
  }, []);

  useEffect(() => {
    setIsMinimized(minimized);
  }, [minimized]);

  const loadOpenWebUIInfo = async () => {
    try {
      const info = await getOpenWebUIInfo();
      if (info.enabled && info.url) {
        setOpenwebuiUrl(info.url);
      }
    } catch (error) {
      console.error('Error loading OpenWebUI info:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleMinimize = () => {
    setIsMinimized(!isMinimized);
    onMinimize?.();
  };

  const handleOpenInNewTab = () => {
    if (openwebuiUrl) {
      window.open(openwebuiUrl, '_blank');
    }
  };

  const buildIframeUrl = () => {
    if (!openwebuiUrl) return '';
    
    let url = openwebuiUrl;
    
    // Add context parameters if job info is available
    if (jobId || jobTitle || company) {
      const params = new URLSearchParams();
      if (jobTitle) params.append('title', jobTitle);
      if (company) params.append('company', company);
      if (jobId) params.append('jobId', jobId.toString());
      
      const separator = url.includes('?') ? '&' : '?';
      url = `${url}${separator}${params.toString()}`;
    }
    
    return url;
  };

  if (loading) {
    return (
      <div className={`openwebui-chat-loading ${className}`}>
        <div className="loading-spinner">Loading OpenWebUI...</div>
      </div>
    );
  }

  if (!openwebuiUrl) {
    return (
      <div className={`openwebui-chat-error ${className}`}>
        <div className="error-message">
          <p>OpenWebUI is not configured</p>
          <p className="error-subtitle">Please configure OpenWebUI URL in settings</p>
        </div>
      </div>
    );
  }

  if (isMinimized) {
    return (
      <div className={`openwebui-chat-minimized ${className}`}>
        <div className="openwebui-chat-minimized-header" onClick={handleMinimize}>
          <div className="openwebui-chat-header-content">
            <div className="openwebui-avatar">
              <MessageSquare size={16} />
            </div>
            <span className="openwebui-chat-title">OpenWebUI Chat</span>
          </div>
          <Maximize2 size={16} />
        </div>
      </div>
    );
  }

  return (
    <div className={`openwebui-chat ${className}`}>
      <div className="openwebui-chat-header">
        <div className="openwebui-chat-header-content">
          <div className="openwebui-avatar">
            <MessageSquare size={20} />
          </div>
          <div>
            <h3 className="openwebui-chat-title">OpenWebUI Assistant</h3>
            <p className="openwebui-chat-subtitle">
              {jobTitle && company ? `${jobTitle} @ ${company}` : 'AI Chat Interface'}
            </p>
          </div>
        </div>
        <div className="openwebui-chat-actions">
          <Button
            variant="ghost"
            size="sm"
            icon={<ExternalLink size={14} />}
            onClick={handleOpenInNewTab}
            title="Open in new tab"
          >
            New Tab
          </Button>
          {onMinimize && (
            <button className="openwebui-chat-action-btn" onClick={handleMinimize} title="Minimize">
              <Minimize2 size={16} />
            </button>
          )}
          {onClose && (
            <button className="openwebui-chat-action-btn" onClick={onClose} title="Close">
              <X size={16} />
            </button>
          )}
        </div>
      </div>

      <div className="openwebui-chat-iframe-container">
        <iframe
          ref={iframeRef}
          src={buildIframeUrl()}
          className="openwebui-chat-iframe"
          title="OpenWebUI Chat"
          allow="microphone; camera"
          sandbox="allow-same-origin allow-scripts allow-forms allow-popups allow-popups-to-escape-sandbox"
        />
      </div>
    </div>
  );
};

export default OpenWebUIChat;

