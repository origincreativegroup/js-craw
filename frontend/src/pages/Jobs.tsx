import { useEffect, useState } from 'react';
import { Search, Sparkles, ExternalLink, MapPin, Building2, MessageSquare } from 'lucide-react';
import Card from '../components/Card';
import Button from '../components/Button';
import OpenWebUIChat from '../components/OpenWebUIChat';
import { getJobs, analyzeJob, sendJobToOpenWebUI } from '../services/api';
import type { Job } from '../types';
import { format } from 'date-fns';
import './Jobs.css';

const Jobs = () => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [analyzing, setAnalyzing] = useState<number | null>(null);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [showChat, setShowChat] = useState(false);

  useEffect(() => {
    loadJobs();
  }, [filter]);

  const loadJobs = async () => {
    try {
      const params: any = { limit: 100 };
      if (filter !== 'all') {
        params.status = filter;
      }
      const data = await getJobs(params);
      setJobs(data);
    } catch (error) {
      console.error('Error loading jobs:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyze = async (jobId: number) => {
    setAnalyzing(jobId);
    try {
      await analyzeJob(jobId);
      await loadJobs(); // Reload to get updated analysis
    } catch (error) {
      console.error('Error analyzing job:', error);
      alert('Failed to analyze job. Please try again.');
    } finally {
      setAnalyzing(null);
    }
  };

  const handleChatWithJob = (job: Job) => {
    setSelectedJob(job);
    setShowChat(true);
  };


  const filteredJobs = jobs.filter((job) => {
    if (!searchTerm) return true;
    const term = searchTerm.toLowerCase();
    return (
      job.title.toLowerCase().includes(term) ||
      job.company.toLowerCase().includes(term) ||
      job.location.toLowerCase().includes(term)
    );
  });

  const getScoreColor = (score?: number) => {
    if (!score) return 'var(--text-muted)';
    if (score >= 75) return 'var(--success)';
    if (score >= 50) return 'var(--warning)';
    return 'var(--danger)';
  };

  if (loading) {
    return <div className="loading">Loading jobs...</div>;
  }

  return (
    <div className="jobs-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Jobs</h1>
          <p className="page-subtitle">AI-analyzed job opportunities</p>
        </div>
      </div>

      <div className="jobs-filters">
        <div className="search-box">
          <Search size={20} />
          <input
            type="text"
            placeholder="Search jobs, companies, locations..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="search-input"
          />
        </div>
        <div className="filter-buttons">
          {['all', 'new', 'applied', 'rejected', 'archived'].map((status) => (
            <button
              key={status}
              className={`filter-btn ${filter === status ? 'active' : ''}`}
              onClick={() => setFilter(status)}
            >
              {status.charAt(0).toUpperCase() + status.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <div className="jobs-grid">
        {filteredJobs.length === 0 ? (
          <Card className="empty-state-card">
            <div className="empty-state">
              <Building2 size={64} />
              <h3>No jobs found</h3>
              <p>Try adjusting your filters or search terms.</p>
            </div>
          </Card>
        ) : (
          filteredJobs.map((job) => (
            <Card key={job.id} className="job-card">
              <div className="job-card-header">
                <div className="job-title-section">
                  <h3 className="job-card-title">{job.title}</h3>
                  <div className="job-meta-row">
                    <span className="job-company">
                      <Building2 size={14} />
                      {job.company}
                    </span>
                    <span className="job-location">
                      <MapPin size={14} />
                      {job.location}
                    </span>
                  </div>
                </div>
                {job.ai_match_score && (
                  <div
                    className="match-score-circle"
                    style={{ color: getScoreColor(job.ai_match_score) }}
                  >
                    <div className="score-value">{Math.round(job.ai_match_score)}</div>
                    <div className="score-label">Match</div>
                  </div>
                )}
              </div>

              {job.ai_summary && (
                <div className="ai-summary-section">
                  <div className="ai-badge-small">
                    <Sparkles size={14} />
                    AI Summary
                  </div>
                  <p className="ai-summary-text">{job.ai_summary}</p>
                </div>
              )}

              {job.ai_pros && job.ai_pros.length > 0 && (
                <div className="ai-pros-cons">
                  <div className="pros-section">
                    <h4 className="pros-cons-title">Pros</h4>
                    <ul className="pros-cons-list">
                      {job.ai_pros.slice(0, 3).map((pro, idx) => (
                        <li key={idx}>{pro}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}

              {job.ai_keywords_matched && job.ai_keywords_matched.length > 0 && (
                <div className="keywords-section">
                  <h4 className="keywords-title">Matched Keywords</h4>
                  <div className="keywords-list">
                    {job.ai_keywords_matched.slice(0, 5).map((keyword, idx) => (
                      <span key={idx} className="keyword-tag">
                        {keyword}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className="job-card-footer">
                <div className="job-dates">
                  {job.posted_date && (
                    <span className="date-info">
                      Posted: {format(new Date(job.posted_date), 'MMM d, yyyy')}
                    </span>
                  )}
                  <span className="date-info">
                    Found: {format(new Date(job.discovered_at), 'MMM d, yyyy')}
                  </span>
                </div>
                <div className="job-actions">
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={<Sparkles size={16} />}
                    onClick={() => handleAnalyze(job.id)}
                    loading={analyzing === job.id}
                  >
                    Re-analyze
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={<MessageSquare size={16} />}
                    onClick={() => handleChatWithJob(job)}
                  >
                    Chat
                  </Button>
                  <Button
                    variant="primary"
                    size="sm"
                    icon={<ExternalLink size={16} />}
                    onClick={() => window.open(job.url, '_blank')}
                  >
                    View Job
                  </Button>
                </div>
              </div>
            </Card>
          ))
        )}
      </div>

      {showChat && selectedJob && (
        <div className="jobs-chat-overlay">
          <OpenWebUIChat
            jobId={selectedJob.id}
            jobTitle={selectedJob.title}
            company={selectedJob.company}
            onClose={() => {
              setShowChat(false);
              setSelectedJob(null);
            }}
            onMinimize={() => setShowChat(false)}
          />
        </div>
      )}
    </div>
  );
};

export default Jobs;

