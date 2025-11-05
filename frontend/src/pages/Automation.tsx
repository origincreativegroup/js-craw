import { useEffect, useState } from 'react';
import {
  Play,
  Pause,
  Square,
  Clock,
  Building2,
  CheckCircle,
  TrendingUp,
  Search,
  Briefcase
} from 'lucide-react';
import Card from '../components/Card';
import Button from '../components/Button';
import { getCrawlStatus } from '../services/api';
import type { CrawlStatus } from '../types';
import './Automation.css';

interface DiscoveryStatus {
  total_companies: number;
  active_companies: number;
  target_companies: number;
  pending_count: number;
  discovery_enabled: boolean;
  discovery_interval_hours: number;
}

const Automation = () => {
  const [crawlStatus, setCrawlStatus] = useState<CrawlStatus | null>(null);
  const [discoveryStatus, setDiscoveryStatus] = useState<DiscoveryStatus | null>(null);
  const [schedulerStatus, setSchedulerStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [jobCrawlerAction, setJobCrawlerAction] = useState<string | null>(null);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const [crawlData, discoveryData] = await Promise.all([
        getCrawlStatus(),
        fetch('/api/companies/discovery/status').then(r => r.json()),
      ]);
      setCrawlStatus(crawlData);
      setDiscoveryStatus(discoveryData);

      try {
        const response = await fetch('/api/automation/scheduler');
        if (response.ok) {
          const schedulerData = await response.json();
          setSchedulerStatus(schedulerData);
        }
      } catch (e) {
        console.log('Scheduler endpoint not available');
      }
    } catch (error) {
      console.error('Error loading automation data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleJobCrawlerStart = async () => {
    setJobCrawlerAction('start');
    try {
      const response = await fetch('/api/crawl/run?crawl_type=all', { method: 'POST' });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to start job crawler (${response.status})`);
      }
      setTimeout(() => loadData(), 1000);
    } catch (error: any) {
      console.error('Error starting job crawler:', error);
      alert(error.message || 'Failed to start job crawler. Please try again.');
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
      setTimeout(() => loadData(), 1000);
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
      setTimeout(() => loadData(), 1000);
    } catch (error: any) {
      console.error('Error resuming job crawler:', error);
      alert(error.message || 'Failed to resume job crawler. Please try again.');
    } finally {
      setJobCrawlerAction(null);
    }
  };

  const handleJobCrawlerStop = async () => {
    setJobCrawlerAction('stop');
    try {
      const response = await fetch('/api/crawl/cancel', { method: 'POST' });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to stop job crawler (${response.status})`);
      }
      setTimeout(() => loadData(), 1000);
    } catch (error: any) {
      console.error('Error stopping job crawler:', error);
      alert(error.message || 'Failed to stop job crawler. Please try again.');
    } finally {
      setJobCrawlerAction(null);
    }
  };

  if (loading) {
    return <div className="loading">Loading automation settings...</div>;
  }

  const isPaused = schedulerStatus?.is_paused || false;
  const isJobCrawlerRunning = crawlStatus?.is_running || false;

  return (
    <div className="automation-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Automation & Control</h1>
          <p className="page-subtitle">
            Control job crawling and company discovery - start, pause, or stop crawlers independently
          </p>
        </div>
      </div>

      <div className="automation-grid">
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
              <p style={{ fontSize: '14px', color: 'var(--text-muted)', marginBottom: '16px' }}>
                <Clock size={14} style={{ display: 'inline', marginRight: '4px' }} />
                Runs automatically every {discoveryStatus.discovery_interval_hours} hours
              </p>
            )}

            <div className="discovery-actions">
              <Button
                variant="secondary"
                size="md"
                icon={<Building2 size={16} />}
                onClick={() => window.location.href = '/discover'}
              >
                View Pending Companies
              </Button>
            </div>
          </div>
        </Card>

        <Card className="automation-card stats-card">
          <div className="card-header">
            <div className="card-header-content">
              <TrendingUp size={24} className="card-icon" />
              <div>
                <h2 className="card-title">System Stats</h2>
                <p className="card-subtitle">Overview metrics</p>
              </div>
            </div>
          </div>

          <div className="stats-grid">
            <div className="stat-item">
              <div className="stat-value">{discoveryStatus?.active_companies || 0}</div>
              <div className="stat-label">Active Companies</div>
            </div>
            <div className="stat-item">
              <div className="stat-value">{crawlStatus?.active_companies || 0}</div>
              <div className="stat-label">In Job Crawler</div>
            </div>
            <div className="stat-item">
              <div className="stat-value">{discoveryStatus?.pending_count || 0}</div>
              <div className="stat-label">Awaiting Approval</div>
            </div>
            <div className="stat-item">
              <div className="stat-value">
                {schedulerStatus?.interval_minutes ? `${schedulerStatus.interval_minutes}m` : 'N/A'}
              </div>
              <div className="stat-label">Crawl Interval</div>
            </div>
          </div>

          {crawlStatus?.recent_logs && crawlStatus.recent_logs.length > 0 && (
            <div style={{ marginTop: '20px', paddingTop: '20px', borderTop: '1px solid var(--border-color)' }}>
              <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '12px', color: 'var(--text-primary)' }}>
                Recent Activity
              </h3>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                {crawlStatus.recent_logs.slice(0, 3).map((log, idx) => (
                  <div key={idx} style={{ marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <div className={`status-indicator ${log.status === 'completed' ? 'success' : log.status === 'failed' ? 'danger' : 'running'}`} style={{ fontSize: '10px' }}>
                      <span className="status-dot" style={{ width: '6px', height: '6px' }}></span>
                    </div>
                    <span>
                      {log.company_name || `Company #${log.company_id}`} - {log.status} ({log.jobs_found || 0} jobs)
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
};

export default Automation;
