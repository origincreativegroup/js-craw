import { useEffect, useState } from 'react';
import { CheckSquare, Sparkles, Clock, AlertCircle, Zap, Plus } from 'lucide-react';
import Card from '../components/Card';
import Button from '../components/Button';
import { getTasks, getTaskRecommendations, createTask, completeTask, generateTasksFromJob } from '../services/api';
import type { Task, TaskRecommendation } from '../types';
import { format, parseISO, isPast } from 'date-fns';
import './Tasks.css';

const Tasks = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [recommendations, setRecommendations] = useState<TaskRecommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('pending');
  const [showRecommendations, setShowRecommendations] = useState(true);

  useEffect(() => {
    loadTasks();
    loadRecommendations();
    const interval = setInterval(() => {
      loadTasks();
      loadRecommendations();
    }, 30000);
    return () => clearInterval(interval);
  }, [filter]);

  const loadTasks = async () => {
    try {
      const params: any = { limit: 100 };
      if (filter !== 'all') {
        params.status = filter;
      }
      const data = await getTasks(params);
      setTasks(data);
    } catch (error) {
      console.error('Error loading tasks:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadRecommendations = async () => {
    try {
      const data = await getTaskRecommendations(5);
      setRecommendations(data);
    } catch (error) {
      console.error('Error loading recommendations:', error);
    }
  };

  const handleComplete = async (taskId: number) => {
    try {
      await completeTask(taskId);
      await loadTasks();
    } catch (error) {
      console.error('Error completing task:', error);
    }
  };

  const handleCreateFromRecommendation = async (rec: TaskRecommendation) => {
    try {
      await generateTasksFromJob(rec.job_id, false);
      await loadTasks();
      setRecommendations((prev) => prev.filter((r) => r.job_id !== rec.job_id));
    } catch (error) {
      console.error('Error creating task:', error);
      alert('Failed to create task. Please try again.');
    }
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
        return <CheckSquare size={16} />;
    }
  };

  if (loading) {
    return <div className="loading">Loading tasks...</div>;
  }

  const overdueTasks = tasks.filter((task) => task.due_date && isPast(parseISO(task.due_date)) && task.status === 'pending');

  return (
    <div className="tasks-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Tasks</h1>
          <p className="page-subtitle">AI-generated task recommendations and action items</p>
        </div>
      </div>

      {showRecommendations && recommendations.length > 0 && (
        <Card className="recommendations-banner">
          <div className="banner-header">
            <div className="banner-title">
              <Sparkles size={20} />
              <span>AI Task Recommendations</span>
            </div>
            <button className="close-banner" onClick={() => setShowRecommendations(false)}>
              ×
            </button>
          </div>
          <div className="recommendations-list">
            {recommendations.map((rec) => (
              <div key={rec.job_id} className="recommendation-item">
                <div className="rec-content">
                  <h4 className="rec-job-title">{rec.job_title}</h4>
                  <p className="rec-company">{rec.company}</p>
                  <p className="rec-reason">{rec.reason}</p>
                </div>
                <Button
                  variant="primary"
                  size="sm"
                  icon={<Plus size={16} />}
                  onClick={() => handleCreateFromRecommendation(rec)}
                >
                  Create Task
                </Button>
              </div>
            ))}
          </div>
        </Card>
      )}

      {overdueTasks.length > 0 && (
        <Card className="overdue-alert">
          <AlertCircle size={20} />
          <div>
            <strong>Overdue Tasks</strong>
            <p>You have {overdueTasks.length} overdue task{overdueTasks.length > 1 ? 's' : ''}.</p>
          </div>
        </Card>
      )}

      <div className="tasks-filters">
        {['all', 'pending', 'completed', 'cancelled'].map((status) => (
          <button
            key={status}
            className={`filter-btn ${filter === status ? 'active' : ''}`}
            onClick={() => setFilter(status)}
          >
            {status.charAt(0).toUpperCase() + status.slice(1)}
          </button>
        ))}
      </div>

      <div className="tasks-list">
        {tasks.length === 0 ? (
          <Card className="empty-state-card">
            <div className="empty-state">
              <CheckSquare size={64} />
              <h3>No tasks found</h3>
              <p>All caught up! Create a task or check recommendations.</p>
            </div>
          </Card>
        ) : (
          tasks.map((task) => (
            <Card key={task.id} className="task-card">
              <div className="task-header">
                <div className="task-title-section">
                  <h3 className="task-title">{task.title}</h3>
                  {task.job && (
                    <p className="task-job-link">
                      {task.job.title} at {task.job.company}
                    </p>
                  )}
                </div>
                <div className="task-priority" style={{ color: getPriorityColor(task.priority) }}>
                  {getPriorityIcon(task.priority)}
                  <span>{task.priority}</span>
                </div>
              </div>

              {task.ai_insights && (
                <div className="task-ai-insights">
                  <Sparkles size={14} />
                  <span>AI Recommended</span>
                </div>
              )}

              <div className="task-meta">
                {task.due_date && (
                  <div className={`task-due-date ${isPast(parseISO(task.due_date)) && task.status === 'pending' ? 'overdue' : ''}`}>
                    <Clock size={14} />
                    <span>Due: {format(parseISO(task.due_date), 'MMM d, yyyy')}</span>
                  </div>
                )}
                {task.recommended_by && (
                  <div className="task-recommended">
                    Recommended by: {task.recommended_by}
                  </div>
                )}
              </div>

              {task.notes && (
                <p className="task-notes">{task.notes}</p>
              )}

              {task.status === 'pending' && (
                <div className="task-actions">
                  <Button
                    variant="success"
                    size="sm"
                    icon={<CheckSquare size={16} />}
                    onClick={() => handleComplete(task.id)}
                  >
                    Complete
                  </Button>
                </div>
              )}
            </Card>
          ))
        )}
      </div>
    </div>
  );
};

export default Tasks;

