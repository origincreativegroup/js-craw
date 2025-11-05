import { useState } from 'react';
import { Building2, MapPin, Sparkles, ExternalLink, ChevronDown, ChevronUp, Zap } from 'lucide-react';
import Card from './Card';
import Button from './Button';
import type { Job } from '../types';
import { format } from 'date-fns';
import './JobCard.css';

interface JobCardProps {
  job: Job;
  onQueueApplication?: (jobId: number) => void;
  onMarkPriority?: (jobId: number) => void;
  onViewDetails?: (jobId: number) => void;
  showActions?: boolean;
}

const JobCard = ({ job, onQueueApplication, onMarkPriority, onViewDetails, showActions = true }: JobCardProps) => {
  const [expanded, setExpanded] = useState(false);

  const getScoreColor = (score?: number) => {
    if (!score) return 'var(--text-muted)';
    if (score >= 75) return 'var(--success)';
    if (score >= 50) return 'var(--warning)';
    return 'var(--danger)';
  };

  const handleQueueApplication = () => {
    if (onQueueApplication) {
      onQueueApplication(job.id);
    }
  };

  const handleMarkPriority = () => {
    if (onMarkPriority) {
      onMarkPriority(job.id);
    }
  };

  const handleViewDetails = () => {
    if (onViewDetails) {
      onViewDetails(job.id);
    } else {
      window.open(job.url, '_blank');
    }
  };

  return (
    <Card className="job-card">
      <div className="job-card-header">
        <div className="job-title-section">
          <h3 className="job-card-title">{job.title}</h3>
          <div className="job-meta-row">
            <span className="job-company">
              <Building2 size={14} />
              {job.company}
            </span>
            {job.location && (
              <span className="job-location">
                <MapPin size={14} />
                {job.location}
              </span>
            )}
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

      {job.ai_recommended && (
        <div className="ai-recommended-badge">
          <Zap size={14} />
          <span>AI Recommended</span>
        </div>
      )}

      {job.ai_summary && (
        <div className="ai-summary-section">
          <div className="ai-badge-small">
            <Sparkles size={14} />
            AI Summary
          </div>
          <p className="ai-summary-text">{job.ai_summary}</p>
          {job.ai_summary.length > 150 && (
            <button
              className="expand-button"
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? (
                <>
                  <ChevronUp size={14} /> Show Less
                </>
              ) : (
                <>
                  <ChevronDown size={14} /> Why this role?
                </>
              )}
            </button>
          )}
        </div>
      )}

      {expanded && (
        <div className="job-ai-insights">
          {job.ai_pros && job.ai_pros.length > 0 && (
            <div className="ai-pros-cons">
              <div className="pros-section">
                <h4 className="pros-cons-title">Pros</h4>
                <ul className="pros-cons-list">
                  {job.ai_pros.map((pro, idx) => (
                    <li key={idx}>{pro}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {job.ai_cons && job.ai_cons.length > 0 && (
            <div className="ai-pros-cons">
              <div className="cons-section">
                <h4 className="pros-cons-title">Cons</h4>
                <ul className="pros-cons-list">
                  {job.ai_cons.map((con, idx) => (
                    <li key={idx}>{con}</li>
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
        {showActions && (
          <div className="job-actions">
            {onQueueApplication && (
              <Button
                variant="primary"
                size="sm"
                onClick={handleQueueApplication}
              >
                Queue Application
              </Button>
            )}
            {onMarkPriority && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleMarkPriority}
              >
                Mark Priority
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              icon={<ExternalLink size={16} />}
              onClick={handleViewDetails}
            >
              View Details
            </Button>
          </div>
        )}
      </div>
    </Card>
  );
};

export default JobCard;
