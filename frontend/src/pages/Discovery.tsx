import { useEffect, useState } from 'react';
import { Sparkles, Building2 } from 'lucide-react';
import JobCard from '../components/JobCard';
import Card from '../components/Card';
import { getJobs, queueJobForApplication, markJobHighPriority } from '../services/api';
import type { Job } from '../types';
import './Discovery.css';

const Discovery = () => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeFilter, setActiveFilter] = useState<string>('high_match');
  const [queueing, setQueueing] = useState<number | null>(null);
  const [marking, setMarking] = useState<number | null>(null);

  useEffect(() => {
    loadJobs();
  }, [activeFilter]);

  const loadJobs = async () => {
    setLoading(true);
    try {
      const params: any = { limit: 50 };
      
      if (activeFilter === 'high_match') {
        params.match = 'high';
        params.sort = 'ai_match_score';
      } else if (activeFilter === 'recently_found') {
        params.status = 'new';
        params.sort = 'discovered_at';
      } else if (activeFilter === 'ready_to_apply') {
        params.ready_to_apply = true;
        params.sort = 'ai_match_score';
      }
      
      const data = await getJobs(params);
      setJobs(data);
    } catch (error) {
      console.error('Error loading jobs:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleQueueApplication = async (jobId: number) => {
    setQueueing(jobId);
    try {
      await queueJobForApplication(jobId);
      // Refresh jobs to show updated status
      await loadJobs();
    } catch (error) {
      console.error('Error queueing application:', error);
      alert('Failed to queue application. Please try again.');
    } finally {
      setQueueing(null);
    }
  };

  const handleMarkPriority = async (jobId: number) => {
    setMarking(jobId);
    try {
      await markJobHighPriority(jobId);
      // Refresh jobs to show updated status
      await loadJobs();
    } catch (error) {
      console.error('Error marking priority:', error);
      alert('Failed to mark priority. Please try again.');
    } finally {
      setMarking(null);
    }
  };

  const handleViewDetails = (jobId: number) => {
    // Navigate to job details or open in new tab
    const job = jobs.find(j => j.id === jobId);
    if (job) {
      window.open(job.url, '_blank');
    }
  };

  const filterChips = [
    { id: 'high_match', label: 'High Match', description: '75%+ match score' },
    { id: 'recently_found', label: 'Recently Found', description: 'New opportunities' },
    { id: 'ready_to_apply', label: 'Ready to Apply', description: '70%+ match score' },
  ];

  if (loading) {
    return <div className="loading">Loading jobs...</div>;
  }

  return (
    <div className="discovery-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Discover</h1>
          <p className="page-subtitle">AI-curated job opportunities tailored for you</p>
        </div>
      </div>

      <div className="filter-chips-container">
        <div className="filter-chips">
          {filterChips.map((filter) => (
            <button
              key={filter.id}
              className={`filter-chip ${activeFilter === filter.id ? 'active' : ''}`}
              onClick={() => setActiveFilter(filter.id)}
            >
              <span className="filter-chip-label">{filter.label}</span>
              <span className="filter-chip-description">{filter.description}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="jobs-grid">
        {jobs.length === 0 ? (
          <Card className="empty-state-card">
            <div className="empty-state">
              <Building2 size={64} />
              <h3>No jobs found</h3>
              <p>Try selecting a different filter or check back later.</p>
            </div>
          </Card>
        ) : (
          jobs.map((job) => (
            <JobCard
              key={job.id}
              job={job}
              onQueueApplication={handleQueueApplication}
              onMarkPriority={handleMarkPriority}
              onViewDetails={handleViewDetails}
              showActions={true}
            />
          ))
        )}
      </div>
    </div>
  );
};

export default Discovery;
