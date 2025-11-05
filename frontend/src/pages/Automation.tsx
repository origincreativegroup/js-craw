import { useEffect, useState } from 'react';
import { 
  Settings, 
  Play, 
  Pause, 
  RefreshCw, 
  Clock, 
  Calendar, 
  Zap, 
  Building2,
  CheckCircle,
  AlertCircle,
  TrendingUp,
  Activity
} from 'lucide-react';
import Card from '../components/Card';
import Button from '../components/Button';
import { 
  getCrawlStatus, 
  triggerCrawl, 
  cancelCrawl,
  getSearches 
} from '../services/api';
import type { CrawlStatus, SearchCriteria } from '../types';
import { format } from 'date-fns';
import './Automation.css';

const Automation = () => {
  const [crawlStatus, setCrawlStatus] = useState<CrawlStatus | null>(null);
  const [schedulerStatus, setSchedulerStatus] = useState<any>(null);
  const [searches, setSearches] = useState<SearchCriteria[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000); // Refresh every 5s
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const [crawlData, searchesData] = await Promise.all([
        getCrawlStatus(),
        getSearches(),
      ]);
      setCrawlStatus(crawlData);
      setSearches(searchesData);
      
      // Try to get scheduler status (if endpoint exists)
      try {
        const response = await fetch('/api/automation/scheduler');
        if (response.ok) {
          const schedulerData = await response.json();
          setSchedulerStatus(schedulerData);
        }
      } catch (e) {
        // Scheduler endpoint might not exist
        console.log('Scheduler endpoint not available');
      }
    } catch (error) {
      console.error('Error loading automation data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleTriggerCrawl = async (type: 'searches' | 'all') => {
    setActionLoading(`crawl-${type}`);
    try {
      await triggerCrawl(type);
      setTimeout(() => loadData(), 1000);
    } catch (error) {
      console.error('Error triggering crawl:', error);
      alert('Failed to trigger crawl. Please try again.');
    } finally {
      setActionLoading(null);
    }
  };

  const handleCancelCrawl = async () => {
    setActionLoading('cancel');
    try {
      await cancelCrawl();
      setTimeout(() => loadData(), 1000);
    } catch (error) {
      console.error('Error cancelling crawl:', error);
      alert('Failed to cancel crawl. Please try again.');
    } finally {
      setActionLoading(null);
    }
  };

  const handlePauseScheduler = async () => {
    setActionLoading('pause');
    try {
      const response = await fetch('/api/automation/pause', { method: 'POST' });
      if (response.ok) {
        setTimeout(() => loadData(), 1000);
      }
    } catch (error) {
      console.error('Error pausing scheduler:', error);
    } finally {
      setActionLoading(null);
    }
  };

  const handleResumeScheduler = async () => {
    setActionLoading('resume');
    try {
      const response = await fetch('/api/automation/resume', { method: 'POST' });
      if (response.ok) {
        setTimeout(() => loadData(), 1000);
      }
    } catch (error) {
      console.error('Error resuming scheduler:', error);
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return <div className="loading">Loading automation settings...</div>;
  }

  const activeSearches = searches.filter(s => s.is_active).length;
  const crawlerHealth = crawlStatus?.crawler_health || {};

  return (
    <div className="automation-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Automation & Control</h1>
          <p className="page-subtitle">
            Manage automated crawling of companies and jobs - schedules, triggers, and system automation
          </p>
        </div>
        <div className="automation-badge">
          <Settings size={20} />
          <span>System Control</span>
        </div>
      </div>

      <div className="automation-grid">
        {/* Crawl Status Card */}
        <Card className="automation-card crawl-status-card">
          <div className="card-header">
            <div className="card-header-content">
              <Activity size={24} className="card-icon" />
              <div>
                <h2 className="card-title">Crawl Status</h2>
                <p className="card-subtitle">Crawling company career pages for new jobs</p>
              </div>
            </div>
            <div className={`status-indicator ${crawlStatus?.is_running ? 'running' : 'idle'}`}>
              <span className="status-dot"></span>
              {crawlStatus?.is_running ? 'Running' : 'Idle'}
            </div>
          </div>

          <div className="crawl-info">
            {crawlStatus?.is_running ? (
              <>
                <div className="crawl-progress">
                  <div className="progress-header">
                    <span>Progress</span>
                    <span className="progress-text">
                      {crawlStatus.progress.current} / {crawlStatus.progress.total} companies crawled
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
                    <span>Currently crawling jobs from: <strong>{crawlStatus.current_company}</strong></span>
                  </div>
                )}
                {crawlStatus.eta_seconds && (
                  <div className="eta">
                    <Clock size={16} />
                    <span>ETA: {Math.round(crawlStatus.eta_seconds / 60)} minutes</span>
                  </div>
                )}
                <div className="crawl-actions">
                  <Button
                    variant="danger"
                    size="md"
                    icon={<Pause size={16} />}
                    onClick={handleCancelCrawl}
                    loading={actionLoading === 'cancel'}
                  >
                    Cancel Crawl
                  </Button>
                </div>
              </>
            ) : (
              <div className="idle-state">
                <div className="idle-message">
                  <CheckCircle size={48} />
                  <h3>Crawler is idle</h3>
                  <p>No active crawling operations</p>
                </div>
                <div className="crawl-actions">
                  <Button
                    variant="primary"
                    size="md"
                    icon={<Play size={16} />}
                    onClick={() => handleTriggerCrawl('searches')}
                    loading={actionLoading === 'crawl-searches'}
                  >
                    Run Searches
                  </Button>
                  <Button
                    variant="secondary"
                    size="md"
                    icon={<RefreshCw size={16} />}
                    onClick={() => handleTriggerCrawl('all')}
                    loading={actionLoading === 'crawl-all'}
                  >
                    Crawl All Companies
                  </Button>
                </div>
              </div>
            )}
          </div>
        </Card>

        {/* Scheduler Card */}
        <Card className="automation-card scheduler-card">
          <div className="card-header">
            <div className="card-header-content">
              <Calendar size={24} className="card-icon" />
              <div>
                <h2 className="card-title">Scheduler</h2>
                <p className="card-subtitle">Automated crawl schedule</p>
              </div>
            </div>
          </div>

          <div className="scheduler-info">
            {schedulerStatus ? (
              <>
                <div className="scheduler-status">
                  <div className={`status-badge ${schedulerStatus.status === 'running' ? 'active' : 'inactive'}`}>
                    {schedulerStatus.status === 'running' ? (
                      <CheckCircle size={16} />
                    ) : (
                      <AlertCircle size={16} />
                    )}
                    <span>{schedulerStatus.status === 'running' ? 'Active' : 'Stopped'}</span>
                  </div>
                  {schedulerStatus.next_run && (
                    <div className="next-run">
                      <Clock size={16} />
                      <span>
                        Next run: {format(new Date(schedulerStatus.next_run), 'MMM d, h:mm a')}
                      </span>
                    </div>
                  )}
                  {schedulerStatus.interval_minutes && (
                    <div className="interval">
                      <span>Interval: Every {schedulerStatus.interval_minutes} minutes</span>
                    </div>
                  )}
                </div>
                <div className="scheduler-actions">
                  {schedulerStatus.is_paused ? (
                    <Button
                      variant="success"
                      size="md"
                      icon={<Play size={16} />}
                      onClick={handleResumeScheduler}
                      loading={actionLoading === 'resume'}
                    >
                      Resume
                    </Button>
                  ) : (
                    <Button
                      variant="warning"
                      size="md"
                      icon={<Pause size={16} />}
                      onClick={handlePauseScheduler}
                      loading={actionLoading === 'pause'}
                    >
                      Pause
                    </Button>
                  )}
                </div>
              </>
            ) : (
              <div className="scheduler-unavailable">
                <AlertCircle size={24} />
                <p>Scheduler information not available</p>
              </div>
            )}
          </div>
        </Card>

        {/* System Stats */}
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
              <div className="stat-value">{activeSearches}</div>
              <div className="stat-label">Active Searches</div>
            </div>
            <div className="stat-item">
              <div className="stat-value">{crawlStatus?.active_companies || 0}</div>
              <div className="stat-label">Active Companies</div>
            </div>
            <div className="stat-item">
              <div className="stat-value">{crawlStatus?.queue_length || 0}</div>
              <div className="stat-label">Queue Length</div>
            </div>
            <div className="stat-item">
              <div className="stat-value">{crawlStatus?.running_count || 0}</div>
              <div className="stat-label">Running Crawls</div>
            </div>
          </div>
        </Card>

        {/* Crawler Health */}
        {Object.keys(crawlerHealth).length > 0 && (
          <Card className="automation-card health-card">
            <div className="card-header">
              <div className="card-header-content">
                <Zap size={24} className="card-icon" />
                <div>
                  <h2 className="card-title">Crawler Health</h2>
                  <p className="card-subtitle">Performance metrics</p>
                </div>
              </div>
            </div>

            <div className="health-metrics">
              {Object.entries(crawlerHealth).map(([type, health]) => (
                <div key={type} className="health-item">
                  <div className="health-header">
                    <span className="health-type">{type}</span>
                    <span className={`health-status ${health.success_rate >= 80 ? 'good' : health.success_rate >= 50 ? 'warning' : 'bad'}`}>
                      {health.success_rate.toFixed(1)}% success
                    </span>
                  </div>
                  <div className="health-details">
                    <div className="health-detail">
                      <span>Avg Duration:</span>
                      <span>{health.avg_duration_seconds.toFixed(1)}s</span>
                    </div>
                    <div className="health-detail">
                      <span>Total Runs:</span>
                      <span>{health.total_runs}</span>
                    </div>
                    <div className="health-detail">
                      <span>Errors:</span>
                      <span>{health.error_count}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
    </div>
  );
};

export default Automation;

