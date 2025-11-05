import { useEffect, useState } from 'react';
import { 
  CheckCircle, 
  AlertCircle, 
  RefreshCw, 
  Eye, 
  EyeOff,
  Activity,
  MessageSquare
} from 'lucide-react';
import Card from '../components/Card';
import Button from '../components/Button';
import { 
  getOpenWebUIInfo, 
  getOpenWebUIHealth, 
  getOpenWebUIStatus,
  verifyOpenWebUIAuth 
} from '../services/api';
import './Settings.css';

interface OpenWebUIInfo {
  enabled: boolean;
  url: string;
  health_status?: string;
  last_checked?: string;
  capabilities?: string[];
  auth_status?: string;
}

const Settings = () => {
  const [openwebuiInfo, setOpenwebuiInfo] = useState<OpenWebUIInfo | null>(null);
  const [healthStatus, setHealthStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [testingConnection, setTestingConnection] = useState(false);
  const [testingAuth, setTestingAuth] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);
  const [showAuthToken, setShowAuthToken] = useState(false);
  const [apiKey, setApiKey] = useState('');
  const [authToken, setAuthToken] = useState('');
  const [username, setUsername] = useState('');

  useEffect(() => {
    loadSettings();
    const interval = setInterval(loadSettings, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  const loadSettings = async () => {
    try {
      const [info, status] = await Promise.all([
        getOpenWebUIInfo(),
        getOpenWebUIStatus().catch(() => null)
      ]);
      setOpenwebuiInfo(info);
      setHealthStatus(status);
    } catch (error) {
      console.error('Error loading OpenWebUI settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleTestConnection = async () => {
    setTestingConnection(true);
    try {
      const health = await getOpenWebUIHealth();
      setHealthStatus({ health });
      alert(`Connection status: ${health.status}\n${health.message}`);
    } catch (error) {
      console.error('Error testing connection:', error);
      alert('Failed to test connection. Please check the URL and try again.');
    } finally {
      setTestingConnection(false);
    }
  };

  const handleTestAuth = async () => {
    setTestingAuth(true);
    try {
      const result = await verifyOpenWebUIAuth(apiKey || undefined, authToken || undefined);
      alert(`Authentication status: ${result.status}\n${result.message}`);
    } catch (error) {
      console.error('Error testing authentication:', error);
      alert('Failed to test authentication. Please check your credentials.');
    } finally {
      setTestingAuth(false);
    }
  };

  const getHealthStatusColor = (status?: string) => {
    switch (status) {
      case 'online':
      case 'online_authenticated':
        return 'var(--success)';
      case 'offline':
      case 'error':
        return 'var(--danger)';
      case 'disabled':
        return 'var(--text-muted)';
      default:
        return 'var(--warning)';
    }
  };

  const getHealthStatusIcon = (status?: string) => {
    switch (status) {
      case 'online':
      case 'online_authenticated':
        return <CheckCircle size={16} />;
      case 'offline':
      case 'error':
        return <AlertCircle size={16} />;
      default:
        return <Activity size={16} />;
    }
  };

  if (loading) {
    return <div className="loading">Loading settings...</div>;
  }

  return (
    <div className="settings-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Settings</h1>
          <p className="page-subtitle">Configure application settings and integrations</p>
        </div>
      </div>

      <div className="settings-grid">
        <Card className="settings-card openwebui-settings-card">
          <div className="card-header">
            <div className="card-header-content">
              <MessageSquare size={24} className="card-icon" />
              <div>
                <h2 className="card-title">OpenWebUI Integration</h2>
                <p className="card-subtitle">Configure OpenWebUI connection and authentication</p>
              </div>
            </div>
            <div 
              className="health-status-badge"
              style={{ color: getHealthStatusColor(openwebuiInfo?.health_status) }}
            >
              {getHealthStatusIcon(openwebuiInfo?.health_status)}
              <span>{openwebuiInfo?.health_status || 'unknown'}</span>
            </div>
          </div>

          <div className="settings-content">
            <div className="form-group">
              <label className="form-label">
                <input
                  type="checkbox"
                  checked={openwebuiInfo?.enabled || false}
                  disabled
                  className="form-checkbox"
                />
                <span>Enable OpenWebUI Integration</span>
              </label>
              <small className="form-help">Toggle in environment configuration</small>
            </div>

            <div className="form-group">
              <label className="form-label">OpenWebUI URL</label>
              <input
                type="url"
                value={openwebuiInfo?.url || ''}
                disabled
                className="form-input"
                placeholder="https://ai.lan"
              />
              <small className="form-help">Configured in environment variables</small>
            </div>

            <div className="form-group">
              <label className="form-label">API Key</label>
              <div className="form-input-group">
                <input
                  type={showApiKey ? 'text' : 'password'}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  className="form-input"
                  placeholder="Enter API key (optional)"
                />
                <button
                  type="button"
                  className="form-toggle-visibility"
                  onClick={() => setShowApiKey(!showApiKey)}
                >
                  {showApiKey ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              <small className="form-help">API key for OpenWebUI API access</small>
            </div>

            <div className="form-group">
              <label className="form-label">Auth Token</label>
              <div className="form-input-group">
                <input
                  type={showAuthToken ? 'text' : 'password'}
                  value={authToken}
                  onChange={(e) => setAuthToken(e.target.value)}
                  className="form-input"
                  placeholder="Enter auth token (optional)"
                />
                <button
                  type="button"
                  className="form-toggle-visibility"
                  onClick={() => setShowAuthToken(!showAuthToken)}
                >
                  {showAuthToken ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              <small className="form-help">User session token for OpenWebUI</small>
            </div>

            <div className="form-group">
              <label className="form-label">Username (Optional)</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="form-input"
                placeholder="Enter username"
              />
              <small className="form-help">Username for basic authentication</small>
            </div>

            <div className="settings-actions">
              <Button
                variant="secondary"
                size="md"
                icon={<RefreshCw size={16} />}
                onClick={handleTestConnection}
                loading={testingConnection}
              >
                Test Connection
              </Button>
              <Button
                variant="secondary"
                size="md"
                icon={<CheckCircle size={16} />}
                onClick={handleTestAuth}
                loading={testingAuth}
              >
                Test Authentication
              </Button>
            </div>

            {openwebuiInfo?.capabilities && openwebuiInfo.capabilities.length > 0 && (
              <div className="capabilities-section">
                <h4 className="capabilities-title">Available Capabilities</h4>
                <div className="capabilities-list">
                  {openwebuiInfo.capabilities.map((cap, idx) => (
                    <span key={idx} className="capability-badge">
                      {cap}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {healthStatus?.health && (
              <div className="health-details">
                <h4 className="health-details-title">Health Details</h4>
                <div className="health-details-content">
                  <div className="health-detail-item">
                    <span className="health-detail-label">Status:</span>
                    <span className="health-detail-value">{healthStatus.health.status}</span>
                  </div>
                  {healthStatus.health.last_checked && (
                    <div className="health-detail-item">
                      <span className="health-detail-label">Last Checked:</span>
                      <span className="health-detail-value">
                        {new Date(healthStatus.health.last_checked).toLocaleString()}
                      </span>
                    </div>
                  )}
                  {healthStatus.health.message && (
                    <div className="health-detail-item">
                      <span className="health-detail-label">Message:</span>
                      <span className="health-detail-value">{healthStatus.health.message}</span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
};

export default Settings;

