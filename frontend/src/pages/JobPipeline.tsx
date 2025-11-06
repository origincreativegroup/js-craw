import { useEffect, useState } from 'react';
import { Search, X } from 'lucide-react';
import Button from '../components/Button';
import JobCard from '../components/JobCard';
import JobDetailPanel from '../components/JobDetailPanel';
import { getJobsPipeline, updatePipelineStage } from '../services/api';
import { useWorkflow } from '../contexts/WorkflowContext';
import { jobSync } from '../services/syncService';
import type { Job } from '../types';
import './JobPipeline.css';

const PIPELINE_STAGES = [
  { id: 'discover', label: 'Discover', color: 'var(--info)' },
  { id: 'review', label: 'Review', color: 'var(--warning)' },
  { id: 'prepare', label: 'Prepare', color: 'var(--primary)' },
  { id: 'apply', label: 'Apply', color: 'var(--success)' },
  { id: 'follow_up', label: 'Follow-up', color: 'var(--secondary)' },
  { id: 'archive', label: 'Archive', color: 'var(--muted)' },
];

const JobPipeline = () => {
  const { selectedJob, setSelectedJob, filterType, setFilterType, searchTerm, setSearchTerm, refreshTrigger } = useWorkflow();
  const [jobsByStage, setJobsByStage] = useState<Record<string, Job[]>>({});
  const [loading, setLoading] = useState(true);
  const [draggedJob, setDraggedJob] = useState<Job | null>(null);

  useEffect(() => {
    loadPipeline();
    
    // Subscribe to pipeline changes
    const unsubscribe = jobSync.subscribeToPipeline((data) => {
      setJobsByStage(data);
    });

    return () => {
      unsubscribe();
    };
  }, [filterType, refreshTrigger]);

  const loadPipeline = async (forceRefresh = false) => {
    try {
      setLoading(true);
      const data = await jobSync.getPipeline(
        () => getJobsPipeline(undefined, filterType || undefined),
        { forceRefresh }
      );
      setJobsByStage(data);
    } catch (error) {
      console.error('Error loading pipeline:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleStageChange = async (jobId: number, newStage: string) => {
    try {
      // Optimistic update with sync service
      await jobSync.updateStage(
        jobId,
        newStage,
        () => updatePipelineStage(jobId, newStage)
      );
      
      // Refresh pipeline data
      await loadPipeline(true);
      
      // Update selected job if it's the one being moved
      if (selectedJob?.id === jobId) {
        setSelectedJob({ ...selectedJob, pipeline_stage: newStage });
      }
    } catch (error) {
      console.error('Error updating pipeline stage:', error);
      alert('Failed to move job. Please try again.');
      // Sync service will rollback on error
      await loadPipeline(true);
    }
  };

  const handleDragStart = (job: Job) => {
    setDraggedJob(job);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = async (e: React.DragEvent, targetStage: string) => {
    e.preventDefault();
    if (draggedJob && draggedJob.pipeline_stage !== targetStage) {
      await handleStageChange(draggedJob.id, targetStage);
    }
    setDraggedJob(null);
  };

  const filterJobs = (jobs: Job[]) => {
    if (!searchTerm) return jobs;
    const term = searchTerm.toLowerCase();
    return jobs.filter(job =>
      job.title.toLowerCase().includes(term) ||
      job.company.toLowerCase().includes(term) ||
      job.location?.toLowerCase().includes(term)
    );
  };

  const getFilterButtons = () => [
    { id: null, label: 'All' },
    { id: 'high_match', label: 'High Match' },
    { id: 'recently_found', label: 'Recently Found' },
    { id: 'needs_action', label: 'Needs Action' },
  ];

  if (loading) {
    return <div className="loading">Loading pipeline...</div>;
  }

  return (
    <div className="job-pipeline-page">
      <div className="pipeline-header">
        <div>
          <h1 className="page-title">Job Pipeline</h1>
          <p className="page-subtitle">Manage your job search workflow</p>
        </div>
        <div className="pipeline-actions">
          <div className="search-box">
            <Search size={20} />
            <input
              type="text"
              placeholder="Search jobs..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="search-input"
            />
            {searchTerm && (
              <button
                className="clear-search"
                onClick={() => setSearchTerm('')}
              >
                <X size={16} />
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="pipeline-filters">
        {getFilterButtons().map((filter) => (
          <button
            key={filter.id || 'all'}
            className={`filter-btn ${filterType === filter.id ? 'active' : ''}`}
            onClick={() => setFilterType(filter.id)}
          >
            {filter.label}
          </button>
        ))}
      </div>

      <div className="pipeline-container">
        <div className="pipeline-board">
          {PIPELINE_STAGES.map((stage) => {
            const stageJobs = filterJobs(jobsByStage[stage.id] || []);
            return (
              <div
                key={stage.id}
                className="pipeline-column"
                onDragOver={handleDragOver}
                onDrop={(e) => handleDrop(e, stage.id)}
              >
                <div className="column-header" style={{ borderTopColor: stage.color }}>
                  <h3 className="column-title">{stage.label}</h3>
                  <span className="column-count">{stageJobs.length}</span>
                </div>
                <div className="column-content">
                  {stageJobs.map((job) => (
                    <div
                      key={job.id}
                      draggable
                      onDragStart={() => handleDragStart(job)}
                      onClick={() => setSelectedJob(job)}
                      className={`job-card-wrapper ${selectedJob?.id === job.id ? 'selected' : ''}`}
                    >
                      <JobCard
                        job={job}
                        showActions={false}
                        customActions={
                          <div className="quick-actions">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={(e) => {
                                e.stopPropagation();
                                setSelectedJob(job);
                              }}
                            >
                              View
                            </Button>
                          </div>
                        }
                      />
                    </div>
                  ))}
                  {stageJobs.length === 0 && (
                    <div className="empty-column">
                      <p>No jobs in this stage</p>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {selectedJob && (
          <div className="pipeline-detail-panel">
            <JobDetailPanel
              job={selectedJob}
              onClose={() => setSelectedJob(null)}
              onStageChange={handleStageChange}
              onRefresh={loadPipeline}
            />
          </div>
        )}
      </div>
    </div>
  );
};

export default JobPipeline;

