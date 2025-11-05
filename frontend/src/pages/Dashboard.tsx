import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { TrendingUp, Briefcase, CheckSquare, Calendar, Sparkles, ArrowRight } from 'lucide-react';
import Card from '../components/Card';
import { getStats, getCrawlStatus, getJobs } from '../services/api';
import type { Stats, CrawlStatus, Job } from '../types';
import './Dashboard.css';

const Dashboard = () => {
  const [stats, setStats] = useState<Stats | null>(null);
  const [crawlStatus, setCrawlStatus] = useState<CrawlStatus | null>(null);
  const [topJobs, setTopJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000); // Refresh every 10s
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const [statsData, crawlData, jobsData] = await Promise.all([
        getStats(),
        getCrawlStatus(),
        getJobs({ limit: 5, status: 'new' }),
      ]);
      setStats(statsData);
      setCrawlStatus(crawlData);
      setTopJobs(jobsData);
    } catch (error) {
      console.error('Error loading dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="loading">Loading dashboard...</div>;
  }

  const statusCounts = stats?.jobs_by_status || {};
  const newJobs = statusCounts['new'] || 0;
  const applied = statusCounts['applied'] || 0;

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">AI-Powered Job Search Overview</p>
        </div>
        <div className="crawler-status-badge">
          {crawlStatus?.is_running ? (
            <span className="status-indicator running"></span>
          ) : (
            <span className="status-indicator idle"></span>
          )}
          {crawlStatus?.is_running ? 'Crawling...' : 'Idle'}
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

      <div className="dashboard-grid">
        <Card className="top-jobs-card">
          <div className="card-header">
            <h2 className="card-title">Top AI-Matched Jobs</h2>
            <Link to="/jobs" className="view-all-link">
              View All <ArrowRight size={16} />
            </Link>
          </div>
          <div className="top-jobs-list">
            {topJobs.length === 0 ? (
              <div className="empty-state">No jobs found</div>
            ) : (
              topJobs.map((job) => (
                <Link key={job.id} to={`/jobs?job=${job.id}`} className="job-item">
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

        <Card className="crawl-status-card">
          <div className="card-header">
            <h2 className="card-title">Crawl Status</h2>
          </div>
          <div className="crawl-info">
            {crawlStatus?.is_running ? (
              <>
                <div className="crawl-progress">
                  <div className="progress-bar">
                    <div
                      className="progress-fill"
                      style={{
                        width: `${(crawlStatus.progress.current / crawlStatus.progress.total) * 100}%`,
                      }}
                    />
                  </div>
                  <div className="progress-text">
                    {crawlStatus.progress.current} / {crawlStatus.progress.total} companies
                  </div>
                </div>
                {crawlStatus.current_company && (
                  <div className="current-company">
                    Currently crawling: <strong>{crawlStatus.current_company}</strong>
                  </div>
                )}
                {crawlStatus.eta_seconds && (
                  <div className="eta">
                    ETA: {Math.round(crawlStatus.eta_seconds / 60)} minutes
                  </div>
                )}
              </>
            ) : (
              <div className="idle-message">Crawler is idle</div>
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

