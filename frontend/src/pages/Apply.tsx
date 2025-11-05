import { useEffect, useState } from 'react';
import { 
  FileText, 
  CheckCircle2, 
  Clock, 
  Edit, 
  Send, 
  MessageSquare, 
  XCircle, 
  Sparkles,
  Download,
  FileCheck,
  ArrowRight,
} from 'lucide-react';
import Card from '../components/Card';
import Button from '../components/Button';
import { 
  getApplications, 
  updateApplication, 
  generateDocuments, 
  getDocuments,
  getJob
} from '../services/api';
import type { Application, GeneratedDocument, Job } from '../types';
import { format } from 'date-fns';
import './Apply.css';

type ApplicationStatus = 'queued' | 'drafting' | 'submitted' | 'interviewing' | 'rejected' | 'accepted';

const STATUS_STEPS: { value: ApplicationStatus; label: string; icon: any }[] = [
  { value: 'queued', label: 'Queued', icon: Clock },
  { value: 'drafting', label: 'Drafting', icon: Edit },
  { value: 'submitted', label: 'Submitted', icon: Send },
  { value: 'interviewing', label: 'Interviewing', icon: MessageSquare },
  { value: 'rejected', label: 'Rejected', icon: XCircle },
  { value: 'accepted', label: 'Accepted', icon: CheckCircle2 },
];

const STATUS_ORDER: ApplicationStatus[] = ['queued', 'drafting', 'submitted', 'interviewing', 'rejected', 'accepted'];

const Apply = () => {
  const [applications, setApplications] = useState<(Application & { job?: Job })[]>([]);
  const [loading, setLoading] = useState(true);
  const [documents, setDocuments] = useState<Record<number, GeneratedDocument[]>>({});
  const [generating, setGenerating] = useState<number | null>(null);
  const [_updating, setUpdating] = useState<number | null>(null);
  const [expandedApp, setExpandedApp] = useState<number | null>(null);
  const [formData, setFormData] = useState<Record<number, { portal_url?: string; confirmation_number?: string; notes?: string }>>({});

  useEffect(() => {
    loadApplications();
    const interval = setInterval(loadApplications, 30000);
    return () => clearInterval(interval);
  }, []);

  const loadApplications = async () => {
    try {
      const data = await getApplications({ status: 'queued', limit: 100 });
      // Also load drafting applications
      const draftingData = await getApplications({ status: 'drafting', limit: 100 });
      const allApps = [...data, ...draftingData];
      
      // Fetch job details for applications that don't have job data
      const appsWithJobs = await Promise.all(
        allApps.map(async (app) => {
          if (app.job && app.job.url) return app;
          try {
            const job = await getJob(app.job_id);
            return { ...app, job };
          } catch {
            return app;
          }
        })
      );
      
      setApplications(appsWithJobs);
      
      // Initialize form data
      const initialFormData: Record<number, { portal_url?: string; confirmation_number?: string; notes?: string }> = {};
      appsWithJobs.forEach(app => {
        initialFormData[app.id] = {
          portal_url: app.portal_url || '',
          confirmation_number: app.confirmation_number || '',
          notes: app.notes || '',
        };
      });
      setFormData(initialFormData);
      
      // Load documents for each application
      for (const app of appsWithJobs) {
        await loadDocumentsForJob(app.job_id);
      }
    } catch (error) {
      console.error('Error loading applications:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadDocumentsForJob = async (jobId: number) => {
    try {
      const docs = await getDocuments(jobId);
      setDocuments(prev => ({ ...prev, [jobId]: docs }));
    } catch (error) {
      console.error(`Error loading documents for job ${jobId}:`, error);
    }
  };

  const handleGenerateDocuments = async (jobId: number) => {
    setGenerating(jobId);
    try {
      await generateDocuments(jobId, ['resume', 'cover_letter']);
      await loadDocumentsForJob(jobId);
    } catch (error) {
      console.error('Error generating documents:', error);
      alert('Failed to generate documents. Please ensure you have a user profile set up.');
    } finally {
      setGenerating(null);
    }
  };

  const handleStatusChange = async (appId: number, newStatus: ApplicationStatus) => {
    setUpdating(appId);
    try {
      const updateData: any = { status: newStatus };
      if (newStatus === 'submitted') {
        updateData.application_date = new Date().toISOString();
      }
      await updateApplication(appId, updateData);
      await loadApplications();
    } catch (error) {
      console.error('Error updating application:', error);
      alert('Failed to update application status.');
    } finally {
      setUpdating(null);
    }
  };

  const handleUpdateApplication = async (appId: number, data: Partial<Application>) => {
    setUpdating(appId);
    try {
      await updateApplication(appId, data);
      await loadApplications();
    } catch (error) {
      console.error('Error updating application:', error);
      alert('Failed to update application.');
    } finally {
      setUpdating(null);
    }
  };

  const getCurrentStepIndex = (status: ApplicationStatus): number => {
    return STATUS_ORDER.indexOf(status);
  };

  const getJobDocuments = (jobId: number): GeneratedDocument[] => {
    return documents[jobId] || [];
  };

  const getResume = (jobId: number): GeneratedDocument | undefined => {
    return getJobDocuments(jobId).find(doc => doc.document_type === 'resume');
  };

  const getCoverLetter = (jobId: number): GeneratedDocument | undefined => {
    return getJobDocuments(jobId).find(doc => doc.document_type === 'cover_letter');
  };

  if (loading) {
    return <div className="loading">Loading applications...</div>;
  }

  return (
    <div className="apply-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Application Preparation Hub</h1>
          <p className="page-subtitle">
            Manage your queued job applications, generate documents, and track your progress
          </p>
        </div>
        <div className="ai-badge">
          <Sparkles size={20} />
          <span>AI-Powered</span>
        </div>
      </div>

      {applications.length === 0 ? (
        <Card className="empty-state">
          <FileText size={48} className="empty-icon" />
          <h3>No queued applications</h3>
          <p>Queue jobs for application from the Discovery or Jobs page to get started.</p>
        </Card>
      ) : (
        <div className="applications-list">
          {applications.map((app) => {
            const currentStep = getCurrentStepIndex(app.status as ApplicationStatus);
            const resume = getResume(app.job_id);
            const coverLetter = getCoverLetter(app.job_id);
            const isExpanded = expandedApp === app.id;
            
            return (
              <Card key={app.id} className="application-card">
                <div className="application-header">
                  <div className="application-info">
                    <h3 className="application-title">
                      {app.job?.title || 'Loading job details...'}
                    </h3>
                    <div className="application-meta">
                      <span className="company-name">{app.job?.company}</span>
                      {app.job?.location && (
                        <>
                          <span className="meta-separator">•</span>
                          <span className="location">{app.job.location}</span>
                        </>
                      )}
                      {app.job?.ai_match_score && (
                        <>
                          <span className="meta-separator">•</span>
                          <span className="match-score">
                            {Math.round(app.job.ai_match_score)}% match
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setExpandedApp(isExpanded ? null : app.id)}
                  >
                    {isExpanded ? 'Collapse' : 'Expand'}
                  </Button>
                </div>

                {/* Application Stepper */}
                <div className="application-stepper">
                  {STATUS_STEPS.map((step, index) => {
                    const Icon = step.icon;
                    const isComplete = index < currentStep;
                    const isCurrent = index === currentStep;
                    const isFinalState = step.value === 'rejected' || step.value === 'accepted';
                    const isClickable = !isFinalState && (isComplete || index === currentStep + 1);
                    
                    return (
                      <div
                        key={step.value}
                        className={`stepper-step ${isComplete ? 'complete' : ''} ${isCurrent ? 'current' : ''} ${isClickable ? 'clickable' : ''}`}
                        onClick={() => isClickable && handleStatusChange(app.id, step.value)}
                      >
                        <div className="step-icon-wrapper">
                          <Icon size={20} />
                          {isComplete && <CheckCircle2 size={12} className="check-overlay" />}
                        </div>
                        <span className="step-label">{step.label}</span>
                        {index < STATUS_STEPS.length - 1 && (
                          <div className={`step-connector ${isComplete ? 'complete' : ''}`} />
                        )}
                      </div>
                    );
                  })}
                </div>

                {isExpanded && (
                  <div className="application-details">
                    {/* Document Generation Section */}
                    <div className="documents-section">
                      <h4 className="section-title">Documents</h4>
                      <div className="documents-grid">
                        <div className="document-card">
                          <div className="document-header">
                            <FileText size={20} />
                            <span className="document-type">Resume</span>
                          </div>
                          {resume ? (
                            <div className="document-content">
                              <p className="document-status">
                                Generated {format(new Date(resume.generated_at), 'MMM d, yyyy')}
                              </p>
                              <Button
                                variant="secondary"
                                size="sm"
                                icon={<Download size={16} />}
                                onClick={() => {
                                  const blob = new Blob([resume.content], { type: 'text/plain' });
                                  const url = URL.createObjectURL(blob);
                                  const a = document.createElement('a');
                                  a.href = url;
                                  a.download = `resume-${app.job?.company}-${app.id}.txt`;
                                  a.click();
                                  URL.revokeObjectURL(url);
                                }}
                              >
                                Download
                              </Button>
                            </div>
                          ) : (
                            <div className="document-content">
                              <p className="document-status">Not generated</p>
                              <Button
                                variant="primary"
                                size="sm"
                                icon={<Sparkles size={16} />}
                                onClick={() => handleGenerateDocuments(app.job_id)}
                                loading={generating === app.job_id}
                              >
                                Generate Resume
                              </Button>
                            </div>
                          )}
                        </div>

                        <div className="document-card">
                          <div className="document-header">
                            <FileCheck size={20} />
                            <span className="document-type">Cover Letter</span>
                          </div>
                          {coverLetter ? (
                            <div className="document-content">
                              <p className="document-status">
                                Generated {format(new Date(coverLetter.generated_at), 'MMM d, yyyy')}
                              </p>
                              <Button
                                variant="secondary"
                                size="sm"
                                icon={<Download size={16} />}
                                onClick={() => {
                                  const blob = new Blob([coverLetter.content], { type: 'text/plain' });
                                  const url = URL.createObjectURL(blob);
                                  const a = document.createElement('a');
                                  a.href = url;
                                  a.download = `cover-letter-${app.job?.company}-${app.id}.txt`;
                                  a.click();
                                  URL.revokeObjectURL(url);
                                }}
                              >
                                Download
                              </Button>
                            </div>
                          ) : (
                            <div className="document-content">
                              <p className="document-status">Not generated</p>
                              <Button
                                variant="primary"
                                size="sm"
                                icon={<Sparkles size={16} />}
                                onClick={() => handleGenerateDocuments(app.job_id)}
                                loading={generating === app.job_id}
                              >
                                Generate Cover Letter
                              </Button>
                            </div>
                          )}
                        </div>
                      </div>

                      {!resume && !coverLetter && (
                        <div className="generate-both">
                          <Button
                            variant="primary"
                            size="md"
                            icon={<Sparkles size={16} />}
                            onClick={() => handleGenerateDocuments(app.job_id)}
                            loading={generating === app.job_id}
                          >
                            Generate Both Documents
                          </Button>
                        </div>
                      )}
                    </div>

                    {/* Application Details Form */}
                    <div className="application-form">
                      <h4 className="section-title">Application Details</h4>
                      <div className="form-grid">
                        <div className="form-field">
                          <label>Portal URL</label>
                          <input
                            type="url"
                            placeholder="https://company.com/apply"
                            value={formData[app.id]?.portal_url || ''}
                            onChange={(e) => {
                              setFormData((prev: Record<number, { portal_url?: string; confirmation_number?: string; notes?: string }>) => ({
                                ...prev,
                                [app.id]: { ...(prev[app.id] || {}), portal_url: e.target.value }
                              }));
                            }}
                            onBlur={(e) => {
                              if (e.target.value !== app.portal_url) {
                                handleUpdateApplication(app.id, { portal_url: e.target.value || undefined });
                              }
                            }}
                          />
                        </div>
                        <div className="form-field">
                          <label>Confirmation Number</label>
                          <input
                            type="text"
                            placeholder="APP-123456"
                            value={formData[app.id]?.confirmation_number || ''}
                            onChange={(e) => {
                              setFormData((prev: Record<number, { portal_url?: string; confirmation_number?: string; notes?: string }>) => ({
                                ...prev,
                                [app.id]: { ...(prev[app.id] || {}), confirmation_number: e.target.value }
                              }));
                            }}
                            onBlur={(e) => {
                              if (e.target.value !== app.confirmation_number) {
                                handleUpdateApplication(app.id, { confirmation_number: e.target.value || undefined });
                              }
                            }}
                          />
                        </div>
                      </div>
                      <div className="form-field">
                        <label>Notes</label>
                        <textarea
                          rows={3}
                          placeholder="Add any notes about this application..."
                          value={formData[app.id]?.notes || ''}
                          onChange={(e) => {
                            setFormData((prev: Record<number, { portal_url?: string; confirmation_number?: string; notes?: string }>) => ({
                              ...prev,
                              [app.id]: { ...(prev[app.id] || {}), notes: e.target.value }
                            }));
                          }}
                          onBlur={(e) => {
                            if (e.target.value !== app.notes) {
                              handleUpdateApplication(app.id, { notes: e.target.value || undefined });
                            }
                          }}
                        />
                      </div>
                    </div>

                    {/* Job Details Link */}
                    {app.job?.url && (
                      <div className="job-link">
                        <Button
                          variant="secondary"
                          size="md"
                          icon={<ArrowRight size={16} />}
                          onClick={() => window.open(app.job!.url, '_blank')}
                        >
                          View Job Posting
                        </Button>
                      </div>
                    )}
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default Apply;
