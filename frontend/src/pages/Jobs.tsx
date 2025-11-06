import { useEffect, useState } from 'react';
import { Search, Sparkles, ExternalLink, MessageSquare } from 'lucide-react';
import Card from '../components/Card';
import Button from '../components/Button';
import JobCard from '../components/JobCard';
import OpenWebUIChat from '../components/OpenWebUIChat';
import { getJobs, analyzeJob, createTask } from '../services/api';
import type { Job, SuggestedStep, AnalyzeJobResponse } from '../types';
import './Jobs.css';

const Jobs = () => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [analyzing, setAnalyzing] = useState<number | null>(null);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [showChat, setShowChat] = useState(false);
  const [suggestionsJobId, setSuggestionsJobId] = useState<number | null>(null);
  const [suggestedSteps, setSuggestedSteps] = useState<SuggestedStep[] | null>(null);
  const [creatingTaskId, setCreatingTaskId] = useState<string | null>(null);

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

  const handleSuggestions = async (jobId: number) => {
    setAnalyzing(jobId);
    try {
      const resp: AnalyzeJobResponse = await analyzeJob(jobId);
      setSuggestionsJobId(jobId);
      setSuggestedSteps(resp.suggested_next_steps || []);
    } catch (error) {
      console.error('Error getting suggestions:', error);
      alert('Failed to get next steps. Please try again.');
    } finally {
      setAnalyzing(null);
    }
  };

  const handleCreateTaskFromSuggestion = async (jobId: number, step: SuggestedStep) => {
    setCreatingTaskId(step.id);
    try {
      await createTask({
        job_id: jobId,
        task_type: step.task_type,
        title: step.title,
        due_date: step.suggested_due_date,
        notes: step.notes,
        priority: 'medium',
      });
      alert('Task created');
    } catch (error) {
      console.error('Error creating task:', error);
      alert('Failed to create task');
    } finally {
      setCreatingTaskId(null);
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
              <Search size={64} />
              <h3>No jobs found</h3>
              <p>Try adjusting your filters or search terms.</p>
            </div>
          </Card>
        ) : (
          filteredJobs.map((job) => (
            <JobCard
              key={job.id}
              job={job}
              onAnalyze={handleAnalyze}
              onSuggestions={handleSuggestions}
              onChat={handleChatWithJob}
              analyzing={analyzing === job.id}
              showActions={true}
            />
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

      {suggestionsJobId && suggestedSteps && (
        <div className="jobs-suggestions-overlay">
          <Card className="suggestions-card">
            <div className="suggestions-header">
              <h3>Next steps</h3>
              <button className="close" onClick={() => { setSuggestionsJobId(null); setSuggestedSteps(null); }}>×</button>
            </div>
            <div className="suggestions-list">
              {suggestedSteps.length === 0 ? (
                <div className="empty-state">No suggestions available.</div>
              ) : (
                suggestedSteps.map((step) => (
                  <div key={step.id} className="suggestion-item">
                    <div className="suggestion-main">
                      <div className="suggestion-label">{step.label}</div>
                      <div className="suggestion-title">{step.title}</div>
                      {step.notes && <div className="suggestion-notes">{step.notes}</div>}
                      {step.suggested_due_date && (
                        <div className="suggestion-due">Due: {new Date(step.suggested_due_date).toLocaleDateString()}</div>
                      )}
                    </div>
                    <div className="suggestion-actions">
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => handleCreateTaskFromSuggestion(suggestionsJobId, step)}
                        loading={creatingTaskId === step.id}
                      >
                        Create task
                      </Button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};

export default Jobs;

