import { useEffect, useState } from 'react';
import { X, ChevronDown, ChevronUp, Sparkles, FileText, CheckSquare, Calendar, Clock, ExternalLink } from 'lucide-react';
import Card from './Card';
import Button from './Button';
import JobFileManager from './JobFileManager';
import { getJobContext, updatePipelineStage, generateDocuments, queueJobForApplication } from '../services/api';
import { jobSync, syncService } from '../services/syncService';
import type { Job } from '../types';
import './JobDetailPanel.css';

interface JobDetailPanelProps {
  job: Job;
  onClose: () => void;
  onStageChange: (jobId: number, newStage: string) => void;
  onRefresh: () => void;
}

const JobDetailPanel: React.FC<JobDetailPanelProps> = ({ job, onClose, onStageChange, onRefresh }) => {
  const [context, setContext] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    overview: true,
    ai_analysis: true,
    documents: false,
    application: false,
    tasks: false,
    follow_ups: false,
    activity: false,
  });

  useEffect(() => {
    loadContext();
    
    // Subscribe to job changes
    const unsubscribe = jobSync.subscribeToJob(job.id, (updatedJob) => {
      // Update context if job data changed
      setContext((prevContext: any) => {
        if (prevContext) {
          return { ...prevContext, job: updatedJob };
        }
        return prevContext;
      });
    });

    return () => {
      unsubscribe();
    };
  }, [job.id]);

  const loadContext = async (forceRefresh = false) => {
    try {
      setLoading(true);
      // Use sync service for caching
      const data = await syncService.get(
        `job-context:${job.id}`,
        () => getJobContext(job.id),
        { forceRefresh }
      );
      setContext(data);
    } catch (error) {
      console.error('Error loading job context:', error);
    } finally {
      setLoading(false);
    }
  };

  const toggleSection = (section: string) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  const getContextActions = () => {
    const stage = job.pipeline_stage || 'discover';
    const actions: Array<{ label: string; action: () => void; variant?: string }> = [];

    switch (stage) {
      case 'discover':
        actions.push(
          { label: 'Queue for Review', action: () => onStageChange(job.id, 'review') },
          { label: 'Mark Priority', action: () => {} },
          { label: 'Archive', action: () => onStageChange(job.id, 'archive') }
        );
        break;
      case 'review':
        actions.push(
          { label: 'Generate Documents', action: handleGenerateDocuments },
          { label: 'Queue Application', action: handleQueueApplication },
          { label: 'Research Company', action: () => {} }
        );
        break;
      case 'prepare':
        actions.push(
          { label: 'Generate Resume', action: () => handleGenerateDocuments(['resume']) },
          { label: 'Generate Cover Letter', action: () => handleGenerateDocuments(['cover_letter']) },
          { label: 'Submit Application', action: () => onStageChange(job.id, 'apply') }
        );
        break;
      case 'apply':
        actions.push(
          { label: 'Update Status', action: () => {} },
          { label: 'Add Portal Link', action: () => {} },
          { label: 'Schedule Follow-up', action: () => onStageChange(job.id, 'follow_up') }
        );
        break;
      case 'follow_up':
        actions.push(
          { label: 'Mark Response', action: () => {} },
          { label: 'Reschedule', action: () => {} },
          { label: 'Archive', action: () => onStageChange(job.id, 'archive') }
        );
        break;
    }

    return actions;
  };

  const handleGenerateDocuments = async (types: string[] = ['resume', 'cover_letter']) => {
    try {
      await generateDocuments(job.id, types);
      // Invalidate cache to force refresh
      syncService.invalidate(`job-context:${job.id}`);
      await loadContext(true);
      onRefresh();
    } catch (error) {
      console.error('Error generating documents:', error);
      alert('Failed to generate documents');
    }
  };

  const handleQueueApplication = async () => {
    try {
      await queueJobForApplication(job.id);
      // Update stage optimistically
      await jobSync.updateStage(
        job.id,
        'prepare',
        () => updatePipelineStage(job.id, 'prepare')
      );
      // Invalidate cache
      syncService.invalidate(`job-context:${job.id}`);
      await loadContext(true);
      onRefresh();
    } catch (error) {
      console.error('Error queueing application:', error);
      alert('Failed to queue application');
    }
  };

  if (loading) {
    return (
      <div className="job-detail-panel">
        <div className="panel-header">
          <h2>Loading...</h2>
          <button onClick={onClose} className="close-btn">
            <X size={20} />
          </button>
        </div>
      </div>
    );
  }

  const aiContent = context?.ai_content || {};
  const tasks = context?.tasks || [];
  const followUps = context?.follow_ups || [];
  const applications = context?.applications || [];
  const activities = context?.activities || [];

  return (
    <div className="job-detail-panel">
      <div className="panel-header">
        <div>
          <h2 className="panel-title">{job.title}</h2>
          <p className="panel-subtitle">{job.company} • {job.location}</p>
        </div>
        <button onClick={onClose} className="close-btn">
          <X size={20} />
        </button>
      </div>

      <div className="panel-content">
        {/* Context Actions */}
        <div className="context-actions">
          {getContextActions().map((action, idx) => (
            <Button
              key={idx}
              variant={idx === 0 ? 'primary' : 'secondary'}
              size="sm"
              onClick={action.action}
            >
              {action.label}
            </Button>
          ))}
        </div>

        {/* Overview Section */}
        <Card className="detail-section">
          <div className="section-header" onClick={() => toggleSection('overview')}>
            <h3>Overview</h3>
            {expandedSections.overview ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
          </div>
          {expandedSections.overview && (
            <div className="section-content">
              <div className="info-grid">
                <div className="info-item">
                  <span className="info-label">Match Score</span>
                  <span className={`match-score score-${getScoreClass(aiContent.match_score || job.ai_match_score || 0)}`}>
                    {Math.round(aiContent.match_score || job.ai_match_score || 0)}%
                  </span>
                </div>
                <div className="info-item">
                  <span className="info-label">Status</span>
                  <span className="info-value">{job.status}</span>
                </div>
                <div className="info-item">
                  <span className="info-label">Pipeline Stage</span>
                  <span className="info-value">{job.pipeline_stage || 'discover'}</span>
                </div>
                <div className="info-item">
                  <span className="info-label">Discovered</span>
                  <span className="info-value">
                    {new Date(job.discovered_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
              {job.url && (
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<ExternalLink size={16} />}
                  onClick={() => window.open(job.url, '_blank')}
                >
                  View Job Posting
                </Button>
              )}
            </div>
          )}
        </Card>

        {/* AI Analysis Section */}
        <Card className="detail-section">
          <div className="section-header" onClick={() => toggleSection('ai_analysis')}>
            <div className="section-title-with-icon">
              <Sparkles size={18} />
              <h3>AI Analysis</h3>
            </div>
            {expandedSections.ai_analysis ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
          </div>
          {expandedSections.ai_analysis && (
            <div className="section-content">
              {aiContent.summary && (
                <div className="ai-summary">
                  <p>{aiContent.summary}</p>
                </div>
              )}
              {aiContent.pros && aiContent.pros.length > 0 && (
                <div className="ai-pros-cons">
                  <h4>Pros</h4>
                  <ul>
                    {aiContent.pros.map((pro: string, idx: number) => (
                      <li key={idx}>{pro}</li>
                    ))}
                  </ul>
                </div>
              )}
              {aiContent.cons && aiContent.cons.length > 0 && (
                <div className="ai-pros-cons">
                  <h4>Cons</h4>
                  <ul>
                    {aiContent.cons.map((con: string, idx: number) => (
                      <li key={idx}>{con}</li>
                    ))}
                  </ul>
                </div>
              )}
              {aiContent.keywords_matched && aiContent.keywords_matched.length > 0 && (
                <div className="keywords-section">
                  <h4>Matched Keywords</h4>
                  <div className="keywords-list">
                    {aiContent.keywords_matched.map((keyword: string, idx: number) => (
                      <span key={idx} className="keyword-tag">{keyword}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </Card>

        {/* Documents Section */}
        <Card className="detail-section">
          <div className="section-header" onClick={() => toggleSection('documents')}>
            <div className="section-title-with-icon">
              <FileText size={18} />
              <h3>Documents</h3>
            </div>
            {expandedSections.documents ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
          </div>
          {expandedSections.documents && (
            <div className="section-content">
              <JobFileManager jobId={job.id} onRefresh={loadContext} />
            </div>
          )}
        </Card>

        {/* Application Section */}
        {applications.length > 0 && (
          <Card className="detail-section">
            <div className="section-header" onClick={() => toggleSection('application')}>
              <h3>Application</h3>
              {expandedSections.application ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
            </div>
            {expandedSections.application && (
              <div className="section-content">
                {applications.map((app: any) => (
                  <div key={app.id} className="application-info">
                    <div className="info-item">
                      <span className="info-label">Status</span>
                      <span className="info-value">{app.status}</span>
                    </div>
                    {app.application_date && (
                      <div className="info-item">
                        <span className="info-label">Applied</span>
                        <span className="info-value">
                          {new Date(app.application_date).toLocaleDateString()}
                        </span>
                      </div>
                    )}
                    {app.portal_url && (
                      <div className="info-item">
                        <span className="info-label">Portal</span>
                        <a href={app.portal_url} target="_blank" rel="noopener noreferrer">
                          {app.portal_url}
                        </a>
                      </div>
                    )}
                    {app.confirmation_number && (
                      <div className="info-item">
                        <span className="info-label">Confirmation</span>
                        <span className="info-value">{app.confirmation_number}</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Card>
        )}

        {/* Tasks Section */}
        {tasks.length > 0 && (
          <Card className="detail-section">
            <div className="section-header" onClick={() => toggleSection('tasks')}>
              <div className="section-title-with-icon">
                <CheckSquare size={18} />
                <h3>Tasks ({tasks.length})</h3>
              </div>
              {expandedSections.tasks ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
            </div>
            {expandedSections.tasks && (
              <div className="section-content">
                {tasks.map((task: any) => (
                  <div key={task.id} className="task-item">
                    <div className="task-header">
                      <span className="task-title">{task.title}</span>
                      <span className={`task-status status-${task.status}`}>{task.status}</span>
                    </div>
                    {task.due_date && (
                      <div className="task-meta">
                        <Clock size={14} />
                        <span>Due: {new Date(task.due_date).toLocaleDateString()}</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Card>
        )}

        {/* Follow-ups Section */}
        {followUps.length > 0 && (
          <Card className="detail-section">
            <div className="section-header" onClick={() => toggleSection('follow_ups')}>
              <div className="section-title-with-icon">
                <Calendar size={18} />
                <h3>Follow-ups ({followUps.length})</h3>
              </div>
              {expandedSections.follow_ups ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
            </div>
            {expandedSections.follow_ups && (
              <div className="section-content">
                {followUps.map((followUp: any) => (
                  <div key={followUp.id} className="followup-item">
                    <div className="followup-header">
                      <span className="followup-date">
                        {new Date(followUp.follow_up_date).toLocaleDateString()}
                      </span>
                      <span className={`followup-status ${followUp.completed ? 'completed' : 'pending'}`}>
                        {followUp.completed ? 'Completed' : 'Pending'}
                      </span>
                    </div>
                    {followUp.notes && <p className="followup-notes">{followUp.notes}</p>}
                  </div>
                ))}
              </div>
            )}
          </Card>
        )}

        {/* Activity Timeline */}
        {activities.length > 0 && (
          <Card className="detail-section">
            <div className="section-header" onClick={() => toggleSection('activity')}>
              <h3>Activity Timeline</h3>
              {expandedSections.activity ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
            </div>
            {expandedSections.activity && (
              <div className="section-content">
                <div className="activity-timeline">
                  {activities.map((activity: any) => (
                    <div key={activity.id} className="activity-item">
                      <div className="activity-time">
                        {new Date(activity.created_at).toLocaleString()}
                      </div>
                      <div className="activity-description">
                        {activity.activity_description || activity.activity_type}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Card>
        )}
      </div>
    </div>
  );
};

const getScoreClass = (score: number): string => {
  if (score >= 75) return 'high';
  if (score >= 50) return 'medium';
  return 'low';
};

export default JobDetailPanel;

