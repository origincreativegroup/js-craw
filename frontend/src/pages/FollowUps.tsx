import { useEffect, useState } from 'react';
import { Calendar, Sparkles, CheckCircle, Clock, AlertCircle, Plus, Zap, MessageSquare } from 'lucide-react';
import Card from '../components/Card';
import Button from '../components/Button';
import AIChat from '../components/AIChat';
import OpenWebUIChat from '../components/OpenWebUIChat';
import { getFollowUpRecommendations, createFollowUp, getJobs } from '../services/api';
import type { FollowUpRecommendation } from '../types';
import { format, parseISO, addDays } from 'date-fns';
import './FollowUps.css';

const FollowUps = () => {
  const [recommendations, setRecommendations] = useState<FollowUpRecommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState<number | null>(null);
  const [selectedJob, setSelectedJob] = useState<{ id: number; title: string; company: string } | null>(null);
  const [showChat, setShowChat] = useState(false);
  const [chatType, setChatType] = useState<'ai' | 'openwebui'>('ai');

  useEffect(() => {
    loadRecommendations();
    const interval = setInterval(loadRecommendations, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  const loadRecommendations = async () => {
    try {
      const data = await getFollowUpRecommendations();
      setRecommendations(data);
    } catch (error) {
      console.error('Error loading follow-up recommendations:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateFollowUp = async (rec: FollowUpRecommendation) => {
    setCreating(rec.job_id);
    try {
      const followUpDate = rec.follow_up_date
        ? parseISO(rec.follow_up_date)
        : addDays(new Date(), 7);

      await createFollowUp({
        job_id: rec.job_id,
        follow_up_date: followUpDate.toISOString(),
        action_type: rec.action_type || 'email',
        notes: rec.suggested_action,
      });

      // Remove from recommendations
      setRecommendations((prev) => prev.filter((r) => r.job_id !== rec.job_id));
    } catch (error) {
      console.error('Error creating follow-up:', error);
      alert('Failed to create follow-up. Please try again.');
    } finally {
      setCreating(null);
    }
  };

  const handleAskAI = (rec: FollowUpRecommendation) => {
    setSelectedJob({
      id: rec.job_id,
      title: rec.job_title,
      company: rec.company,
    });
    setShowChat(true);
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'high':
        return 'var(--danger)';
      case 'medium':
        return 'var(--warning)';
      default:
        return 'var(--info)';
    }
  };

  const getPriorityIcon = (priority: string) => {
    switch (priority) {
      case 'high':
        return <AlertCircle size={16} />;
      case 'medium':
        return <Clock size={16} />;
      default:
        return <CheckCircle size={16} />;
    }
  };

  if (loading) {
    return <div className="loading">Loading AI recommendations...</div>;
  }

  const groupedRecs = recommendations.reduce((acc, rec) => {
    const key = rec.type;
    if (!acc[key]) acc[key] = [];
    acc[key].push(rec);
    return acc;
  }, {} as Record<string, FollowUpRecommendation[]>);

  return (
    <div className="follow-ups-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">AI Follow-Up Recommendations</h1>
          <p className="page-subtitle">
            Intelligent suggestions powered by AI to help you stay on top of your job applications
          </p>
        </div>
        <div className="header-actions">
          <div className="chat-toggle">
            <Button
              variant={chatType === 'ai' ? 'primary' : 'ghost'}
              size="sm"
              icon={<Sparkles size={16} />}
              onClick={() => {
                setChatType('ai');
                setShowChat(true);
              }}
            >
              AI Chat
            </Button>
            <Button
              variant={chatType === 'openwebui' ? 'primary' : 'ghost'}
              size="sm"
              icon={<MessageSquare size={16} />}
              onClick={() => {
                setChatType('openwebui');
                setShowChat(true);
              }}
            >
              OpenWebUI
            </Button>
          </div>
          {showChat && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowChat(false)}
            >
              Hide
            </Button>
          )}
          <div className="ai-badge">
            <Sparkles size={20} />
            <span>AI-Powered</span>
          </div>
        </div>
      </div>

      <div className="follow-ups-layout">
        <div className={`follow-ups-content ${showChat ? 'with-chat' : ''}`}>
          {recommendations.length === 0 ? (
            <Card className="empty-state-card">
              <div className="empty-state">
                <Calendar size={64} />
                <h3>No Follow-Up Recommendations</h3>
                <p>You're all caught up! Check back later for new recommendations.</p>
                {!showChat && (
                  <Button
                    variant="primary"
                    size="md"
                    icon={<MessageSquare size={18} />}
                    onClick={() => setShowChat(true)}
                    style={{ marginTop: '24px' }}
                  >
                    Ask AI for Advice
                  </Button>
                )}
              </div>
            </Card>
          ) : (
            <div className="recommendations-container">
              {Object.entries(groupedRecs).map(([type, recs]) => (
                <div key={type} className="recommendation-group">
                  <h2 className="group-title">
                    {type === 'follow_up' && 'Jobs Needing Follow-Up'}
                    {type === 'upcoming_followup' && 'Upcoming Follow-Ups'}
                    {type === 'apply_now' && 'High-Priority Applications'}
                  </h2>

                  <div className="recommendations-grid">
                    {recs.map((rec) => (
                      <Card key={`${rec.type}-${rec.job_id}`} className="recommendation-card">
                        <div className="recommendation-header">
                          <div className="priority-badge" style={{ color: getPriorityColor(rec.priority) }}>
                            {getPriorityIcon(rec.priority)}
                            <span>{rec.priority.toUpperCase()}</span>
                          </div>
                          {rec.ai_match_score && (
                            <div className="match-score-badge">
                              <Zap size={14} />
                              {Math.round(rec.ai_match_score)}% Match
                            </div>
                          )}
                        </div>

                        <div className="recommendation-content">
                          <h3 className="job-title-recommendation">{rec.job_title}</h3>
                          <div className="job-meta">
                            <span className="company-name">{rec.company}</span>
                            <span className="job-location">{rec.location}</span>
                          </div>

                          <div className="recommendation-ai-insight">
                            <Sparkles size={16} className="ai-icon" />
                            <p className="ai-suggestion">{rec.suggested_action}</p>
                          </div>

                          {rec.follow_up_date && (
                            <div className="follow-up-date">
                              <Calendar size={14} />
                              <span>
                                {format(parseISO(rec.follow_up_date), 'MMM d, yyyy h:mm a')}
                              </span>
                            </div>
                          )}

                          {rec.applied_at && (
                            <div className="applied-date">
                              Applied: {format(parseISO(rec.applied_at), 'MMM d, yyyy')}
                            </div>
                          )}
                        </div>

                        <div className="recommendation-actions">
                          <Button
                            variant="ghost"
                            size="sm"
                            icon={<MessageSquare size={14} />}
                            onClick={() => handleAskAI(rec)}
                          >
                            Ask AI
                          </Button>
                          {rec.type === 'apply_now' ? (
                            <Button
                              variant="primary"
                              size="sm"
                              icon={<Zap size={16} />}
                              onClick={() => handleCreateFollowUp(rec)}
                              loading={creating === rec.job_id}
                            >
                              Schedule Application
                            </Button>
                          ) : rec.type === 'follow_up' ? (
                            <Button
                              variant="success"
                              size="sm"
                              icon={<Plus size={16} />}
                              onClick={() => handleCreateFollowUp(rec)}
                              loading={creating === rec.job_id}
                            >
                              Create Follow-Up
                            </Button>
                          ) : (
                            <Button
                              variant="primary"
                              size="sm"
                              icon={<CheckCircle size={16} />}
                              onClick={() => handleCreateFollowUp(rec)}
                              loading={creating === rec.job_id}
                            >
                              Mark Complete
                            </Button>
                          )}
                        </div>
                      </Card>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {showChat && (
          <div className="ai-chat-sidebar">
            {chatType === 'ai' ? (
              <AIChat
                jobTitle={selectedJob?.title}
                company={selectedJob?.company}
                jobId={selectedJob?.id}
                onClose={() => setShowChat(false)}
                onMinimize={() => setShowChat(false)}
              />
            ) : (
              <OpenWebUIChat
                jobId={selectedJob?.id}
                jobTitle={selectedJob?.title}
                company={selectedJob?.company}
                onClose={() => setShowChat(false)}
                onMinimize={() => setShowChat(false)}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default FollowUps;
