import { useEffect, useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import { 
  TrendingUp, 
  Briefcase, 
  CheckSquare, 
  Calendar, 
  Sparkles, 
  ArrowRight,
  Clock,
  Zap,
  Settings,
  Search,
  Building2,
  BarChart3
} from 'lucide-react';
import Card from '../components/Card';
import { 
  getStats, 
  getJobs, 
  getUnifiedStatus
} from '../services/api';
import type { Stats, Job, UnifiedStatus, CrawlerHealth } from '../types';
import { format, parseISO } from 'date-fns';
import './Dashboard.css';

const Dashboard = () => {
  const [stats, setStats] = useState<Stats | null>(null);
  const [unifiedStatus, setUnifiedStatus] = useState<UnifiedStatus | null>(null);
  const [topJobs, setTopJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  
  const pollingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const fastPollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadAllData = async () => {
    try {
      const [statsData, unifiedData, jobsData] = await Promise.all([
        getStats(),
        getUnifiedStatus(10),
        getJobs({ limit: 5, status: 'new' }),
      ]);
      setStats(statsData);
      setUnifiedStatus(unifiedData);
      setTopJobs(jobsData);
    } catch (error) {
      console.error('Error loading dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  // Initial load and setup normal polling
  useEffect(() => {
    loadAllData();
    
    // Normal polling for all data (every 10s)
    pollingIntervalRef.current = setInterval(() => {
      loadAllData();
    }, 10000);
    
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
      if (fastPollingRef.current) {
        clearInterval(fastPollingRef.current);
      }
    };
  }, []);

  // Adaptive fast polling when crawler is active
  useEffect(() => {
    const isRunning = unifiedStatus?.automation.crawler.is_running || false;
    if (isRunning) {
      // Clear any existing fast polling
      if (fastPollingRef.current) {
        clearInterval(fastPollingRef.current);
      }
      // Start fast polling (every 3s) for unified status
      fastPollingRef.current = setInterval(() => {
        getUnifiedStatus(10).then(setUnifiedStatus).catch(console.error);
      }, 3000);
    } else {
      // Stop fast polling when crawler is idle
      if (fastPollingRef.current) {
        clearInterval(fastPollingRef.current);
        fastPollingRef.current = null;
      }
    }
    
    return () => {
      if (fastPollingRef.current) {
        clearInterval(fastPollingRef.current);
      }
    };
  }, [unifiedStatus?.automation.crawler.is_running]);

  if (loading) {
    return <div className="loading">Loading dashboard...</div>;
  }

  const statusCounts = stats?.jobs_by_status || {};
  const newJobs = statusCounts['new'] || 0;
  const applied = statusCounts['applied'] || 0;
  
  const isCrawlerRunning = unifiedStatus?.automation.crawler.is_running || false;
  const isPaused = unifiedStatus?.automation.scheduler.is_paused || false;
  const crawlerHealth = unifiedStatus?.automation.crawler.crawler_health || {};
  const crawler = unifiedStatus?.automation.crawler;
  const scheduler = unifiedStatus?.automation.scheduler;
  const companies = unifiedStatus?.companies;
  
  const getHealthStatus = (health: CrawlerHealth | undefined): 'healthy' | 'warning' | 'error' => {
    if (!health || health.total_runs === 0) return 'warning';
    const successRate = health.success_rate;
    if (successRate >= 90) return 'healthy';
    if (successRate >= 70) return 'warning';
    return 'error';
  };

  const formatNextRun = (nextRun?: string) => {
    if (!nextRun) return 'N/A';
    try {
      return format(parseISO(nextRun), 'MMM d, h:mm a');
    } catch {
      return nextRun;
    }
  };

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">AI-Powered Job Search - Unified System Status & Monitoring</p>
        </div>
        <div className="unified-status-badge">
          <Zap size={16} />
          <span className="status-indicator-wrapper">
            {isCrawlerRunning ? (
              <span className="status-indicator running"></span>
            ) : isPaused ? (
              <span className="status-indicator paused"></span>
            ) : (
              <span className="status-indicator idle"></span>
            )}
          </span>
          <span>
            {isCrawlerRunning 
              ? 'Crawler Active'
              : isPaused 
              ? 'Scheduler Paused'
              : 'All Systems Idle'}
          </span>
        </div>
      </div>

      <div className="stats-grid">
        <Card className="stat-card stat-primary">
          <div className="stat-icon">
            <Briefcase />
          </div>
          <div className="stat-content">
            <div className="stat-value">{stats?.total_jobs || 0}</div>
            <div className="stat-label">Total Jobs</div>
            <div className="stat-change positive">
              <TrendingUp size={14} />
              +{stats?.new_jobs_24h || 0} today
            </div>
          </div>
        </Card>

        <Card className="stat-card stat-success">
          <div className="stat-icon">
            <CheckSquare />
          </div>
          <div className="stat-content">
            <div className="stat-value">{newJobs}</div>
            <div className="stat-label">New Jobs</div>
          </div>
        </Card>

        <Card className="stat-card stat-info">
          <div className="stat-icon">
            <Calendar />
          </div>
          <div className="stat-content">
            <div className="stat-value">{applied}</div>
            <div className="stat-label">Applied</div>
          </div>
        </Card>

        <Card className="stat-card stat-warning">
          <div className="stat-icon">
            <Sparkles />
          </div>
          <div className="stat-content">
            <div className="stat-value">{stats?.active_searches || 0}</div>
            <div className="stat-label">Active Searches</div>
          </div>
        </Card>
      </div>

      {/* Automation Status Section */}
      <div className="automation-status-section">
        <div className="automation-header">
          <h2 className="section-title">Automation Status</h2>
          <Link to="/automation-control" className="view-details-link">
            View Details <ArrowRight size={16} />
          </Link>
        </div>
        
        <div className="automation-grid">
          {/* Crawler Status Card */}
          <Card className="automation-card">
            <div className="card-header">
              <div className="card-header-content">
                <Briefcase size={24} className="card-icon" />
                <div>
                  <h3 className="card-title">Job Crawler</h3>
                  <p className="card-subtitle">
                    {isCrawlerRunning 
                      ? (crawler?.run_type === 'all_companies' 
                          ? 'Universal Company Crawl' 
                          : 'Search-Based Crawl')
                      : `Monitoring ${companies?.active_companies || 0} active companies`}
                  </p>
                </div>
              </div>
              <div className={`status-badge ${isCrawlerRunning ? 'running' : isPaused ? 'paused' : 'idle'}`}>
                {isCrawlerRunning ? 'Running' : isPaused ? 'Paused' : 'Idle'}
              </div>
            </div>
            <div className="automation-info">
              {isCrawlerRunning && crawler?.progress ? (
                <>
                  <div className="progress-section">
                    <div className="progress-text">
                      {crawler.progress.current} / {crawler.progress.total} companies
                    </div>
                    <div className="progress-bar">
                      <div
                        className="progress-fill"
                        style={{
                          width: `${Math.min(100, (crawler.progress.current / crawler.progress.total) * 100)}%`,
                        }}
                      />
                    </div>
                  </div>
                  {crawler.current_company && (
                    <div className="current-item">
                      Currently: <strong>{crawler.current_company}</strong>
                    </div>
                  )}
                  {crawler.eta_seconds && (
                    <div className="eta-info">
                      ETA: {Math.round(crawler.eta_seconds / 60)} minutes
                    </div>
                  )}
                  {crawler.queue_length > 0 && (
                    <div className="queue-info">
                      Queue: {crawler.queue_length} companies
                    </div>
                  )}
                </>
              ) : (
                <div className="idle-info">
                  <p>Monitoring {companies?.active_companies || 0} active companies</p>
                  {scheduler && !isPaused && scheduler.interval_minutes && (
                    <p className="next-run-info">
                      Next crawl in {scheduler.interval_minutes} minutes
                    </p>
                  )}
                </div>
              )}
            </div>
          </Card>

          {/* Scheduler Status Card */}
          <Card className="automation-card">
            <div className="card-header">
              <div className="card-header-content">
                <Clock size={24} className="card-icon" />
                <div>
                  <h3 className="card-title">Scheduler</h3>
                  <p className="card-subtitle">Automated crawl scheduling</p>
                </div>
              </div>
              <div className={`status-badge ${isPaused ? 'paused' : 'active'}`}>
                {isPaused ? 'Paused' : 'Active'}
              </div>
            </div>
            <div className="automation-info">
              {scheduler ? (
                <>
                  {scheduler.interval_minutes && (
                    <div className="scheduler-detail">
                      <span className="detail-label">Interval:</span>
                      <span className="detail-value">{scheduler.interval_minutes} minutes</span>
                    </div>
                  )}
                  {scheduler.next_run && (
                    <div className="scheduler-detail">
                      <span className="detail-label">Next Run:</span>
                      <span className="detail-value">{formatNextRun(scheduler.next_run)}</span>
                    </div>
                  )}
                  <div className="scheduler-detail">
                    <span className="detail-label">Status:</span>
                    <span className="detail-value">{scheduler.status}</span>
                  </div>
                </>
              ) : (
                <div className="idle-info">
                  <p>Scheduler information unavailable</p>
                </div>
              )}
            </div>
          </Card>
        </div>

        {/* Company Overview Card */}
        {companies && (
          <Card className="automation-card">
            <div className="card-header">
              <div className="card-header-content">
                <Building2 size={24} className="card-icon" />
                <div>
                  <h3 className="card-title">Companies</h3>
                  <p className="card-subtitle">Active company monitoring</p>
                </div>
              </div>
            </div>
            <div className="automation-info">
              <div className="scheduler-detail">
                <span className="detail-label">Active:</span>
                <span className="detail-value">{companies.active_companies} / {companies.total_companies}</span>
              </div>
              {companies.needs_attention > 0 && (
                <div className="scheduler-detail">
                  <span className="detail-label">Needs Attention:</span>
                  <span className="detail-value warning">{companies.needs_attention}</span>
                </div>
              )}
              {companies.average_viability_score !== null && companies.average_viability_score !== undefined && (
                <div className="scheduler-detail">
                  <span className="detail-label">Avg Viability:</span>
                  <span className="detail-value">{companies.average_viability_score.toFixed(1)}%</span>
                </div>
              )}
            </div>
          </Card>
        )}

        {/* Crawler Health Metrics */}
        {Object.keys(crawlerHealth).length > 0 && (
          <Card className="health-metrics-card">
            <div className="card-header">
              <div className="card-header-content">
                <BarChart3 size={24} className="card-icon" />
                <h3 className="card-title">Crawler Health Metrics</h3>
              </div>
            </div>
            <div className="health-metrics-grid">
              {Object.entries(crawlerHealth).map(([type, health]) => {
                const status = getHealthStatus(health);
                return (
                  <div key={type} className={`health-metric ${status}`}>
                    <div className="health-metric-header">
                      <span className="health-metric-type">{type}</span>
                      <span className={`health-status-badge ${status}`}>
                        {status === 'healthy' ? '✓' : status === 'warning' ? '⚠' : '✗'}
                      </span>
                    </div>
                    <div className="health-metric-details">
                      <div className="health-stat">
                        <span className="health-stat-label">Success Rate:</span>
                        <span className="health-stat-value">{health.success_rate.toFixed(1)}%</span>
                      </div>
                      <div className="health-stat">
                        <span className="health-stat-label">Avg Duration:</span>
                        <span className="health-stat-value">{Math.round(health.avg_duration_seconds)}s</span>
                      </div>
                      <div className="health-stat">
                        <span className="health-stat-label">Total Runs:</span>
                        <span className="health-stat-value">{health.total_runs}</span>
                      </div>
                      {health.error_count > 0 && (
                        <div className="health-stat">
                          <span className="health-stat-label">Errors:</span>
                          <span className="health-stat-value error">{health.error_count}</span>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        )}
      </div>

      {/* Quick Actions */}
      <Card className="quick-actions-card">
        <div className="card-header">
          <h3 className="card-title">Quick Actions</h3>
        </div>
        <div className="quick-actions-grid">
          <Link to="/career-hub" className="quick-action-item">
            <div className="quick-action-icon career-hub">
              <Briefcase size={24} />
            </div>
            <div className="quick-action-content">
              <h4 className="quick-action-title">Career Hub</h4>
              <p className="quick-action-desc">Manage applications & documents</p>
            </div>
            <ArrowRight size={16} className="quick-action-arrow" />
          </Link>
          
          <Link to="/automation-control" className="quick-action-item">
            <div className="quick-action-icon automation">
              <Settings size={24} />
            </div>
            <div className="quick-action-content">
              <h4 className="quick-action-title">Automation Control</h4>
              <p className="quick-action-desc">Control crawlers & discovery</p>
            </div>
            <ArrowRight size={16} className="quick-action-arrow" />
          </Link>
          
          <Link to="/pipeline" className="quick-action-item">
            <div className="quick-action-icon jobs">
              <Search size={24} />
            </div>
            <div className="quick-action-content">
              <h4 className="quick-action-title">Job Pipeline</h4>
              <p className="quick-action-desc">Manage your job search workflow</p>
            </div>
            <ArrowRight size={16} className="quick-action-arrow" />
          </Link>
          
          <Link to="/companies" className="quick-action-item">
            <div className="quick-action-icon companies">
              <Building2 size={24} />
            </div>
            <div className="quick-action-content">
              <h4 className="quick-action-title">Companies</h4>
              <p className="quick-action-desc">Manage company list</p>
            </div>
            <ArrowRight size={16} className="quick-action-arrow" />
          </Link>
        </div>
      </Card>

      <div className="dashboard-grid">
        <Card className="top-jobs-card">
          <div className="card-header">
            <h2 className="card-title">Top AI-Matched Jobs</h2>
            <Link to="/pipeline" className="view-all-link">
              View All <ArrowRight size={16} />
            </Link>
          </div>
          <div className="top-jobs-list">
            {topJobs.length === 0 ? (
              <div className="empty-state">No jobs found</div>
            ) : (
              topJobs.map((job) => (
                <Link key={job.id} to={`/pipeline`} className="job-item">
                  <div className="job-item-header">
                    <h3 className="job-title">{job.title}</h3>
                    {job.ai_match_score && (
                      <span className={`match-score score-${getScoreClass(job.ai_match_score)}`}>
                        {Math.round(job.ai_match_score)}%
                      </span>
                    )}
                  </div>
                  <div className="job-item-meta">
                    <span className="job-company">{job.company}</span>
                    <span className="job-location">{job.location}</span>
                  </div>
                  {job.ai_summary && (
                    <p className="job-summary">{job.ai_summary}</p>
                  )}
                </Link>
              ))
            )}
          </div>
        </Card>
      </div>
    </div>
  );
};

const getScoreClass = (score: number): string => {
  if (score >= 75) return 'high';
  if (score >= 50) return 'medium';
  return 'low';
};

export default Dashboard;

