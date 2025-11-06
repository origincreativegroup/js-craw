import { useEffect, useState, useRef } from 'react';
import {
  Play,
  Pause,
  Square,
  Clock,
  Building2,
  CheckCircle,
  Search,
  Briefcase,
  Settings,
  Activity,
  MessageSquare,
  Eye,
  EyeOff,
  RefreshCw,
  AlertCircle,
  XCircle,
  BarChart3,
  Zap,
} from 'lucide-react';
import Card from '../components/Card';
import Button from '../components/Button';
import {
  getCrawlStatus,
  updateSchedulerInterval,
  updateDiscoveryInterval,
  getDiscoveryStatus,
  runDiscovery,
  getPendingCompanies,
  approvePendingCompany,
  rejectPendingCompany,
  getOpenWebUIInfo,
  getOpenWebUIHealth,
  getOpenWebUIStatus,
  verifyOpenWebUIAuth,
} from '../services/api';
import type { CrawlStatus, DiscoveryStatus, PendingCompany } from '../types';
import { format, parseISO } from 'date-fns';
import './AutomationControl.css';

interface OpenWebUIInfo {
  enabled: boolean;
  url: string;
  health_status?: string;
  last_checked?: string;
  capabilities?: string[];
  auth_status?: string;
}

type SectionId = 'overview' | 'crawler' | 'discovery' | 'activity' | 'settings';

const AutomationControl = () => {
  const [activeSection, setActiveSection] = useState<SectionId>('overview');
  
  // Crawler state
  const [crawlStatus, setCrawlStatus] = useState<CrawlStatus | null>(null);
  const [schedulerStatus, setSchedulerStatus] = useState<any>(null);
  const [jobCrawlerAction, setJobCrawlerAction] = useState<string | null>(null);
  const [schedulerInterval, setSchedulerInterval] = useState<string>('');
  
  // Discovery state
  const [discoveryStatus, setDiscoveryStatus] = useState<DiscoveryStatus | null>(null);
  const [pendingCompanies, setPendingCompanies] = useState<PendingCompany[]>([]);
  const [discovering, setDiscovering] = useState(false);
  const [discoveryInterval, setDiscoveryInterval] = useState<string>('');
  const [processing, setProcessing] = useState<number | null>(null);
  
  // Settings state
  const [openwebuiInfo, setOpenwebuiInfo] = useState<OpenWebUIInfo | null>(null);
  const [healthStatus, setHealthStatus] = useState<any>(null);
  const [testingConnection, setTestingConnection] = useState(false);
  const [testingAuth, setTestingAuth] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);
  const [showAuthToken, setShowAuthToken] = useState(false);
  const [apiKey, setApiKey] = useState('');
  const [authToken, setAuthToken] = useState('');
  const [username, setUsername] = useState('');
  
  // Activity stream state
  const [activityLog, setActivityLog] = useState<any[]>([]);
  const [activityFilter, setActivityFilter] = useState<string>('all');
  
  // Polling state
  const [loading, setLoading] = useState(true);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const fastPollingRef = useRef<NodeJS.Timeout | null>(null);

  // Initialize and setup polling
  useEffect(() => {
    loadAllData();
    
    // Setup adaptive polling: faster when crawler is active
    const setupPolling = () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
      if (fastPollingRef.current) {
        clearInterval(fastPollingRef.current);
      }
      
      // Normal polling every 5 seconds
      pollingIntervalRef.current = setInterval(() => {
        loadAllData();
      }, 5000);
      
      // Fast polling every 1-2 seconds when crawler is running
      if (crawlStatus?.is_running) {
        fastPollingRef.current = setInterval(() => {
          loadCrawlStatus();
        }, 2000);
      }
    };
    
    setupPolling();
    
    return () => {
      if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
      if (fastPollingRef.current) clearInterval(fastPollingRef.current);
    };
  }, [crawlStatus?.is_running]);

  const loadAllData = async () => {
    try {
      await Promise.all([
        loadCrawlStatus(),
        loadDiscoveryData(),
        loadSettingsData(),
      ]);
    } catch (error) {
      console.error('Error loading automation data:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadCrawlStatus = async () => {
    try {
      const [crawlData, schedulerData] = await Promise.all([
        getCrawlStatus(),
        fetch('/api/automation/scheduler').then(r => r.ok ? r.json() : null).catch(() => null),
      ]);
      setCrawlStatus(crawlData);
      setSchedulerStatus(schedulerData);
      if (schedulerData?.interval_minutes) {
        setSchedulerInterval(schedulerData.interval_minutes.toString());
      }
      
      // Add to activity log
      if (crawlData?.recent_logs) {
        const newActivities = crawlData.recent_logs.slice(0, 5).map((log: any) => ({
          id: `log-${log.id}`,
          type: 'crawl',
          timestamp: log.started_at,
          message: `${log.company_name || 'Company'} - ${log.status} (${log.jobs_found || 0} jobs)`,
          status: log.status,
          details: log,
        }));
        setActivityLog(prev => {
          const combined = [...newActivities, ...prev];
          return combined.slice(0, 50); // Keep last 50 activities
        });
      }
    } catch (error) {
      console.error('Error loading crawl status:', error);
    }
  };

  const loadDiscoveryData = async () => {
    try {
      const [statusData, pendingData] = await Promise.all([
        getDiscoveryStatus(),
        getPendingCompanies(),
      ]);
      setDiscoveryStatus(statusData);
      setPendingCompanies(pendingData);
      if (statusData?.discovery_interval_hours) {
        setDiscoveryInterval(statusData.discovery_interval_hours.toString());
      }
    } catch (error) {
      console.error('Error loading discovery data:', error);
    }
  };

  const loadSettingsData = async () => {
    try {
      const [info, status] = await Promise.all([
        getOpenWebUIInfo(),
        getOpenWebUIStatus().catch(() => null),
      ]);
      setOpenwebuiInfo(info);
      setHealthStatus(status);
    } catch (error) {
      console.error('Error loading OpenWebUI settings:', error);
    }
  };

  // Job Crawler Controls
  const handleJobCrawlerStart = async () => {
    setJobCrawlerAction('start');
    try {
      const response = await fetch('/api/crawl/run?crawl_type=all', { method: 'POST' });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to start job crawler (${response.status})`);
      }
      setTimeout(() => loadCrawlStatus(), 1000);
      addActivity('crawl', 'Job crawler started', 'success');
    } catch (error: any) {
      console.error('Error starting job crawler:', error);
      alert(error.message || 'Failed to start job crawler. Please try again.');
      addActivity('crawl', `Failed to start: ${error.message}`, 'error');
    } finally {
      setJobCrawlerAction(null);
    }
  };

  const handleJobCrawlerPause = async () => {
    setJobCrawlerAction('pause');
    try {
      const response = await fetch('/api/automation/pause', { method: 'POST' });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to pause job crawler (${response.status})`);
      }
      setTimeout(() => loadCrawlStatus(), 1000);
      addActivity('crawl', 'Job crawler paused', 'info');
    } catch (error: any) {
      console.error('Error pausing job crawler:', error);
      alert(error.message || 'Failed to pause job crawler. Please try again.');
    } finally {
      setJobCrawlerAction(null);
    }
  };

  const handleJobCrawlerResume = async () => {
    setJobCrawlerAction('resume');
    try {
      const response = await fetch('/api/automation/resume', { method: 'POST' });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to resume job crawler (${response.status})`);
      }
      setTimeout(() => loadCrawlStatus(), 1000);
      addActivity('crawl', 'Job crawler resumed', 'success');
    } catch (error: any) {
      console.error('Error resuming job crawler:', error);
      alert(error.message || 'Failed to resume job crawler. Please try again.');
    } finally {
      setJobCrawlerAction(null);
    }
  };

  const handleJobCrawlerStop = async () => {
    if (!confirm('Are you sure you want to stop the current crawl?')) {
      return;
    }
    setJobCrawlerAction('stop');
    try {
      const response = await fetch('/api/crawl/cancel', { method: 'POST' });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to stop job crawler (${response.status})`);
      }
      setTimeout(() => loadCrawlStatus(), 1000);
      addActivity('crawl', 'Job crawler stopped', 'warning');
    } catch (error: any) {
      console.error('Error stopping job crawler:', error);
      alert(error.message || 'Failed to stop job crawler. Please try again.');
    } finally {
      setJobCrawlerAction(null);
    }
  };

  const handleUpdateSchedulerInterval = async () => {
    const interval = parseInt(schedulerInterval);
    if (isNaN(interval) || interval < 1) {
      alert('Please enter a valid interval (minimum 1 minute)');
      return;
    }
    try {
      await updateSchedulerInterval(interval);
      await loadCrawlStatus();
      addActivity('settings', `Scheduler interval updated to ${interval} minutes`, 'success');
    } catch (error) {
      console.error('Error updating scheduler interval:', error);
      alert('Failed to update scheduler interval.');
    }
  };

  // Discovery Controls
  const handleUpdateDiscoveryInterval = async () => {
    const interval = parseInt(discoveryInterval);
    if (isNaN(interval) || interval < 1) {
      alert('Please enter a valid interval (minimum 1 hour)');
      return;
    }
    try {
      await updateDiscoveryInterval(interval);
      await loadDiscoveryData();
      addActivity('discovery', `Discovery interval updated to ${interval} hours`, 'success');
    } catch (error: any) {
      console.error('Error updating discovery interval:', error);
      alert(error.message || 'Failed to update discovery interval.');
    }
  };

  const handleRunDiscovery = async () => {
    setDiscovering(true);
    try {
      await runDiscovery();
      await loadDiscoveryData();
      addActivity('discovery', 'Discovery run triggered', 'success');
    } catch (error) {
      console.error('Error running discovery:', error);
      alert('Failed to run discovery. Please try again.');
      addActivity('discovery', 'Discovery run failed', 'error');
    } finally {
      setDiscovering(false);
    }
  };

  const handleApprove = async (pendingId: number) => {
    setProcessing(pendingId);
    try {
      await approvePendingCompany(pendingId);
      await loadDiscoveryData();
      addActivity('discovery', `Company approved (ID: ${pendingId})`, 'success');
    } catch (error) {
      console.error('Error approving company:', error);
      alert('Failed to approve company. Please try again.');
    } finally {
      setProcessing(null);
    }
  };

  const handleReject = async (pendingId: number) => {
    if (!confirm('Are you sure you want to reject this company?')) {
      return;
    }
    setProcessing(pendingId);
    try {
      await rejectPendingCompany(pendingId);
      await loadDiscoveryData();
      addActivity('discovery', `Company rejected (ID: ${pendingId})`, 'warning');
    } catch (error) {
      console.error('Error rejecting company:', error);
      alert('Failed to reject company. Please try again.');
    } finally {
      setProcessing(null);
    }
  };

  // Settings Controls
  const handleTestConnection = async () => {
    setTestingConnection(true);
    try {
      const health = await getOpenWebUIHealth();
      setHealthStatus({ health });
      alert(`Connection status: ${health.status}\n${health.message}`);
      addActivity('settings', `OpenWebUI connection tested: ${health.status}`, health.status === 'online' ? 'success' : 'error');
    } catch (error) {
      console.error('Error testing connection:', error);
      alert('Failed to test connection. Please check the URL and try again.');
      addActivity('settings', 'OpenWebUI connection test failed', 'error');
    } finally {
      setTestingConnection(false);
    }
  };

  const handleTestAuth = async () => {
    setTestingAuth(true);
    try {
      const result = await verifyOpenWebUIAuth(apiKey || undefined, authToken || undefined);
      alert(`Authentication status: ${result.status}\n${result.message}`);
      addActivity('settings', `OpenWebUI auth tested: ${result.status}`, result.status === 'authenticated' ? 'success' : 'error');
    } catch (error) {
      console.error('Error testing authentication:', error);
      alert('Failed to test authentication. Please check your credentials.');
      addActivity('settings', 'OpenWebUI auth test failed', 'error');
    } finally {
      setTestingAuth(false);
    }
  };

  // Activity helper
  const addActivity = (type: string, message: string, status: string = 'info') => {
    const activity = {
      id: `activity-${Date.now()}-${Math.random()}`,
      type,
      timestamp: new Date().toISOString(),
      message,
      status,
    };
    setActivityLog(prev => [activity, ...prev].slice(0, 50));
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

  const getConfidenceColor = (score: number) => {
    if (score >= 70) return 'var(--success)';
    if (score >= 50) return 'var(--warning)';
    return 'var(--danger)';
  };

  const getSourceIcon = (source: string) => {
    switch (source) {
      case 'linkedin':
        return '💼';
      case 'indeed':
        return '🔍';
      case 'web_search':
        return '🌐';
      default:
        return '🏢';
    }
  };

  if (loading) {
    return <div className="loading">Loading automation control center...</div>;
  }

  const isPaused = schedulerStatus?.is_paused || false;
  const isJobCrawlerRunning = crawlStatus?.is_running || false;
  const filteredActivities = activityFilter === 'all' 
    ? activityLog 
    : activityLog.filter(a => a.type === activityFilter);

  const sections = [
    { id: 'overview' as SectionId, label: 'Overview', icon: BarChart3 },
    { id: 'crawler' as SectionId, label: 'Job Crawler', icon: Briefcase },
    { id: 'discovery' as SectionId, label: 'Discovery', icon: Search },
    { id: 'activity' as SectionId, label: 'Activity', icon: Activity },
    { id: 'settings' as SectionId, label: 'Settings', icon: Settings },
  ];

  return (
    <div className="automation-control-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Automation Control Center</h1>
          <p className="page-subtitle">
            Unified control for job crawling, company discovery, and system settings with live monitoring
          </p>
        </div>
        <div className="ai-badge">
          <Zap size={20} />
          <span>Live Monitoring</span>
        </div>
      </div>

      <div className="section-navigation">
        {sections.map((section) => {
          const Icon = section.icon;
          return (
            <button
              key={section.id}
              className={`section-button ${activeSection === section.id ? 'active' : ''}`}
              onClick={() => setActiveSection(section.id)}
            >
              <Icon size={18} />
              <span>{section.label}</span>
            </button>
          );
        })}
      </div>

      <div className="section-content-wrapper">
        {activeSection === 'overview' && (
          <div className="section-content">
            <div className="overview-grid">
              <Card className="metric-card">
                <div className="metric-header">
                  <Briefcase size={24} className="metric-icon" />
                  <div>
                    <div className="metric-value">
                      {isJobCrawlerRunning ? 'Running' : isPaused ? 'Paused' : 'Idle'}
                    </div>
                    <div className="metric-label">Job Crawler Status</div>
                  </div>
                </div>
                {crawlStatus?.progress && (
                  <div className="metric-progress">
                    <div className="progress-text">
                      {crawlStatus.progress.current} / {crawlStatus.progress.total} companies
                    </div>
                    <div className="progress-bar">
                      <div
                        className="progress-fill"
                        style={{
                          width: `${(crawlStatus.progress.current / crawlStatus.progress.total) * 100}%`,
                        }}
                      />
                    </div>
                  </div>
                )}
              </Card>

              <Card className="metric-card">
                <div className="metric-header">
                  <Search size={24} className="metric-icon" />
                  <div>
                    <div className="metric-value">{discoveryStatus?.active_companies || 0}</div>
                    <div className="metric-label">Active Companies</div>
                  </div>
                </div>
                {discoveryStatus && (
                  <div className="metric-progress">
                    <div className="progress-text">
                      {discoveryStatus.active_companies} / {discoveryStatus.target_companies} target
                    </div>
                    <div className="progress-bar">
                      <div
                        className="progress-fill"
                        style={{
                          width: `${Math.min(100, (discoveryStatus.active_companies / discoveryStatus.target_companies) * 100)}%`,
                        }}
                      />
                    </div>
                  </div>
                )}
              </Card>

              <Card className="metric-card">
                <div className="metric-header">
                  <Clock size={24} className="metric-icon" />
                  <div>
                    <div className="metric-value">{pendingCompanies.length}</div>
                    <div className="metric-label">Pending Approval</div>
                  </div>
                </div>
              </Card>

              <Card className="metric-card">
                <div className="metric-header">
                  <MessageSquare size={24} className="metric-icon" />
                  <div>
                    <div className="metric-value">
                      {openwebuiInfo?.health_status === 'online' || openwebuiInfo?.health_status === 'online_authenticated' ? 'Connected' : 'Disconnected'}
                    </div>
                    <div className="metric-label">OpenWebUI Status</div>
                  </div>
                </div>
              </Card>
            </div>

            <Card className="quick-actions-card">
              <h3 className="card-title">Quick Actions</h3>
              <div className="quick-actions">
                <Button
                  variant={isJobCrawlerRunning ? "danger" : "primary"}
                  size="md"
                  icon={isJobCrawlerRunning ? <Square size={16} /> : <Play size={16} />}
                  onClick={isJobCrawlerRunning ? handleJobCrawlerStop : handleJobCrawlerStart}
                  loading={jobCrawlerAction === (isJobCrawlerRunning ? 'stop' : 'start')}
                >
                  {isJobCrawlerRunning ? 'Stop Crawler' : 'Start Crawler'}
                </Button>
                <Button
                  variant="secondary"
                  size="md"
                  icon={<Search size={16} />}
                  onClick={handleRunDiscovery}
                  loading={discovering}
                >
                  Run Discovery
                </Button>
                <Button
                  variant="secondary"
                  size="md"
                  icon={<Settings size={16} />}
                  onClick={() => setActiveSection('settings')}
                >
                  Open Settings
                </Button>
              </div>
            </Card>
          </div>
        )}

        {activeSection === 'crawler' && (
          <div className="section-content">
            <Card className="automation-card crawl-status-card">
              <div className="card-header">
                <div className="card-header-content">
                  <Briefcase size={24} className="card-icon" style={{ color: '#8b5cf6' }} />
                  <div>
                    <h2 className="card-title">Job Crawler</h2>
                    <p className="card-subtitle">Crawl company career pages for new job postings</p>
                  </div>
                </div>
                <div className={`status-indicator ${isJobCrawlerRunning ? 'running' : isPaused ? 'paused' : 'idle'}`}>
                  <span className="status-dot"></span>
                  {isJobCrawlerRunning ? 'Running' : isPaused ? 'Paused' : 'Idle'}
                </div>
              </div>

              <div className="crawl-info">
                {isJobCrawlerRunning && crawlStatus ? (
                  <>
                    <div className="crawl-progress">
                      <div className="progress-header">
                        <span>Progress</span>
                        <span className="progress-text">
                          {crawlStatus.progress.current} / {crawlStatus.progress.total} companies
                        </span>
                      </div>
                      <div className="progress-bar">
                        <div
                          className="progress-fill"
                          style={{
                            width: `${(crawlStatus.progress.current / crawlStatus.progress.total) * 100}%`,
                          }}
                        />
                      </div>
                    </div>
                    {crawlStatus.current_company && (
                      <div className="current-company">
                        <Building2 size={16} />
                        <span>Currently crawling: <strong>{crawlStatus.current_company}</strong></span>
                      </div>
                    )}
                    {crawlStatus.eta_seconds && (
                      <div className="eta">
                        <Clock size={16} />
                        <span>ETA: {Math.round(crawlStatus.eta_seconds / 60)} minutes</span>
                      </div>
                    )}
                    <div className="crawl-actions" style={{ marginTop: '20px' }}>
                      <Button
                        variant="danger"
                        size="md"
                        icon={<Square size={16} />}
                        onClick={handleJobCrawlerStop}
                        loading={jobCrawlerAction === 'stop'}
                      >
                        Stop
                      </Button>
                    </div>
                  </>
                ) : isPaused ? (
                  <div className="paused-state">
                    <div className="idle-message">
                      <Pause size={48} style={{ color: '#f59e0b' }} />
                      <h3>Job crawler is paused</h3>
                      <p>Resume to continue scheduled crawling</p>
                    </div>
                    <div className="crawl-actions">
                      <Button
                        variant="success"
                        size="md"
                        icon={<Play size={16} />}
                        onClick={handleJobCrawlerResume}
                        loading={jobCrawlerAction === 'resume'}
                      >
                        Resume
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="idle-state">
                    <div className="idle-message">
                      <CheckCircle size={48} style={{ color: '#10b981' }} />
                      <h3>Job crawler is idle</h3>
                      <p>Start crawling {discoveryStatus?.active_companies || 0} active companies</p>
                      {schedulerStatus && (
                        <p style={{ fontSize: '14px', color: 'var(--text-muted)', marginTop: '8px' }}>
                          Scheduled: Every {schedulerStatus.interval_minutes} minutes
                        </p>
                      )}
                    </div>
                    <div className="crawl-actions">
                      <Button
                        variant="primary"
                        size="md"
                        icon={<Play size={16} />}
                        onClick={handleJobCrawlerStart}
                        loading={jobCrawlerAction === 'start'}
                      >
                        Start Crawling
                      </Button>
                      <Button
                        variant="warning"
                        size="md"
                        icon={<Pause size={16} />}
                        onClick={handleJobCrawlerPause}
                        loading={jobCrawlerAction === 'pause'}
                      >
                        Pause Scheduler
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </Card>

            <Card className="automation-card scheduler-card">
              <div className="card-header">
                <div className="card-header-content">
                  <Clock size={24} className="card-icon" />
                  <div>
                    <h2 className="card-title">Scheduler Configuration</h2>
                    <p className="card-subtitle">Configure automatic crawling intervals</p>
                  </div>
                </div>
              </div>
              <div className="scheduler-config">
                <div className="form-group">
                  <label className="form-label">Interval (minutes)</label>
                  <div className="form-input-group">
                    <input
                      type="number"
                      value={schedulerInterval}
                      onChange={(e) => setSchedulerInterval(e.target.value)}
                      className="form-input"
                      placeholder="Enter interval in minutes"
                      min="1"
                    />
                    <Button
                      variant="primary"
                      size="md"
                      onClick={handleUpdateSchedulerInterval}
                    >
                      Update
                    </Button>
                  </div>
                  <small className="form-help">Current interval: {schedulerStatus?.interval_minutes || 'N/A'} minutes</small>
                </div>
              </div>
            </Card>
          </div>
        )}

        {activeSection === 'discovery' && (
          <div className="section-content">
            <Card className="automation-card discovery-card">
              <div className="card-header">
                <div className="card-header-content">
                  <Search size={24} className="card-icon" style={{ color: '#ec4899' }} />
                  <div>
                    <h2 className="card-title">Company Discovery</h2>
                    <p className="card-subtitle">Discover new companies via LinkedIn, Indeed, and web search</p>
                  </div>
                </div>
                <div className={`status-indicator ${discoveryStatus?.discovery_enabled ? 'idle' : 'disabled'}`}>
                  <span className="status-dot"></span>
                  {discoveryStatus?.discovery_enabled ? 'Enabled' : 'Disabled'}
                </div>
              </div>

              <div className="discovery-info">
                <div className="stats-grid" style={{ marginBottom: '20px' }}>
                  <div className="stat-item">
                    <div className="stat-value">{discoveryStatus?.total_companies || 0}</div>
                    <div className="stat-label">Total Companies</div>
                  </div>
                  <div className="stat-item">
                    <div className="stat-value">{discoveryStatus?.active_companies || 0}</div>
                    <div className="stat-label">Active Companies</div>
                  </div>
                  <div className="stat-item">
                    <div className="stat-value">{discoveryStatus?.pending_count || 0}</div>
                    <div className="stat-label">Pending Approval</div>
                  </div>
                  <div className="stat-item">
                    <div className="stat-value">{discoveryStatus?.target_companies || 0}</div>
                    <div className="stat-label">Target</div>
                  </div>
                </div>

                <div className="progress-section" style={{ marginBottom: '20px' }}>
                  <div className="progress-header">
                    <span>Discovery Progress</span>
                    <span className="progress-text">
                      {discoveryStatus?.total_companies || 0} / {discoveryStatus?.target_companies || 0}
                      ({Math.round(((discoveryStatus?.total_companies || 0) / (discoveryStatus?.target_companies || 1)) * 100)}%)
                    </span>
                  </div>
                  <div className="progress-bar">
                    <div
                      className="progress-fill"
                      style={{
                        width: `${Math.min(100, ((discoveryStatus?.total_companies || 0) / (discoveryStatus?.target_companies || 1)) * 100)}%`,
                        background: 'linear-gradient(90deg, #ec4899, #8b5cf6)'
                      }}
                    />
                  </div>
                </div>

                {discoveryStatus?.discovery_enabled && (
                  <div style={{ marginBottom: '16px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                      <Clock size={14} style={{ color: 'var(--text-muted)' }} />
                      <span style={{ fontSize: '14px', color: 'var(--text-muted)' }}>
                        Runs automatically every {discoveryStatus.discovery_interval_hours} hours
                      </span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '8px' }}>
                      <input
                        type="number"
                        min="1"
                        max="168"
                        value={discoveryInterval}
                        onChange={(e) => setDiscoveryInterval(e.target.value)}
                        placeholder="Hours"
                        style={{
                          width: '80px',
                          padding: '6px 8px',
                          border: '1px solid var(--border-color)',
                          borderRadius: '4px',
                          fontSize: '14px'
                        }}
                      />
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={handleUpdateDiscoveryInterval}
                      >
                        Update Interval
                      </Button>
                    </div>
                  </div>
                )}

                <div className="discovery-actions">
                  <Button
                    variant="primary"
                    size="md"
                    icon={<Search size={16} />}
                    onClick={handleRunDiscovery}
                    loading={discovering}
                  >
                    Run Discovery Now
                  </Button>
                </div>
              </div>
            </Card>

            <div className="pending-section">
              <div className="section-header">
                <h2>Pending Companies</h2>
                <span className="count-badge">{pendingCompanies.length}</span>
              </div>

              {pendingCompanies.length === 0 ? (
                <Card className="empty-state-card">
                  <div className="empty-state">
                    <CheckCircle size={64} />
                    <h3>No pending companies</h3>
                    <p>All discovered companies have been reviewed. Run discovery to find more!</p>
                  </div>
                </Card>
              ) : (
                <div className="pending-companies-grid">
                  {pendingCompanies.map((company) => (
                    <Card key={company.id} className="pending-company-card">
                      <div className="pending-company-header">
                        <div className="company-info">
                          <h3 className="company-name">{company.name}</h3>
                          <div className="company-meta">
                            <span className="source-badge">
                              {getSourceIcon(company.discovery_source)} {company.discovery_source}
                            </span>
                            <span
                              className="confidence-badge"
                              style={{ color: getConfidenceColor(company.confidence_score) }}
                            >
                              {company.confidence_score.toFixed(1)}% confidence
                            </span>
                          </div>
                        </div>
                      </div>

                      <div className="pending-company-details">
                        <div className="detail-item">
                          <span className="detail-label">Career Page:</span>
                          <a
                            href={company.career_page_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="career-link"
                          >
                            {company.career_page_url}
                          </a>
                        </div>
                        <div className="detail-item">
                          <span className="detail-label">Crawler Type:</span>
                          <span className="detail-value">{company.crawler_type}</span>
                        </div>
                        <div className="detail-item">
                          <span className="detail-label">Discovered:</span>
                          <span className="detail-value">
                            {format(parseISO(company.created_at), 'MMM d, yyyy')}
                          </span>
                        </div>
                      </div>

                      <div className="pending-company-actions">
                        <Button
                          onClick={() => handleReject(company.id)}
                          disabled={processing === company.id}
                          variant="danger"
                          size="sm"
                        >
                          <XCircle size={16} />
                          Reject
                        </Button>
                        <Button
                          onClick={() => handleApprove(company.id)}
                          disabled={processing === company.id}
                          variant="primary"
                          size="sm"
                        >
                          {processing === company.id ? (
                            <RefreshCw size={16} className="spinning" />
                          ) : (
                            <CheckCircle size={16} />
                          )}
                          Approve
                        </Button>
                      </div>
                    </Card>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {activeSection === 'activity' && (
          <div className="section-content">
            <Card className="activity-stream-card">
              <div className="card-header">
                <div className="card-header-content">
                  <Activity size={24} className="card-icon" />
                  <div>
                    <h2 className="card-title">Activity Stream</h2>
                    <p className="card-subtitle">Real-time monitoring of system activities</p>
                  </div>
                </div>
                <div className="activity-filters">
                  <button
                    className={`filter-button ${activityFilter === 'all' ? 'active' : ''}`}
                    onClick={() => setActivityFilter('all')}
                  >
                    All
                  </button>
                  <button
                    className={`filter-button ${activityFilter === 'crawl' ? 'active' : ''}`}
                    onClick={() => setActivityFilter('crawl')}
                  >
                    Crawl
                  </button>
                  <button
                    className={`filter-button ${activityFilter === 'discovery' ? 'active' : ''}`}
                    onClick={() => setActivityFilter('discovery')}
                  >
                    Discovery
                  </button>
                  <button
                    className={`filter-button ${activityFilter === 'settings' ? 'active' : ''}`}
                    onClick={() => setActivityFilter('settings')}
                  >
                    Settings
                  </button>
                </div>
              </div>

              <div className="activity-list">
                {filteredActivities.length === 0 ? (
                  <div className="empty-activity">
                    <Activity size={48} style={{ opacity: 0.3 }} />
                    <p>No activities to display</p>
                  </div>
                ) : (
                  filteredActivities.map((activity) => (
                    <div key={activity.id} className={`activity-item activity-${activity.status}`}>
                      <div className="activity-icon">
                        {activity.type === 'crawl' && <Briefcase size={16} />}
                        {activity.type === 'discovery' && <Search size={16} />}
                        {activity.type === 'settings' && <Settings size={16} />}
                      </div>
                      <div className="activity-content">
                        <div className="activity-message">{activity.message}</div>
                        <div className="activity-time">
                          {format(parseISO(activity.timestamp), 'MMM d, yyyy HH:mm:ss')}
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </Card>
          </div>
        )}

        {activeSection === 'settings' && (
          <div className="section-content">
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
                            {format(parseISO(healthStatus.health.last_checked), 'MMM d, yyyy h:mm a')}
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
        )}
      </div>
    </div>
  );
};

export default AutomationControl;
