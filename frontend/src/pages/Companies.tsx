import { useEffect, useState } from 'react';
import { Building2, Globe, Activity, TrendingUp, CheckCircle, XCircle } from 'lucide-react';
import Card from '../components/Card';
import { getCompanies } from '../services/api';
import type { Company } from '../types';
import { format } from 'date-fns';
import './Companies.css';

const Companies = () => {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');

  useEffect(() => {
    loadCompanies();
  }, [filter]);

  const loadCompanies = async () => {
    try {
      const activeOnly = filter === 'active';
      const data = await getCompanies(activeOnly);
      setCompanies(data);
    } catch (error) {
      console.error('Error loading companies:', error);
    } finally {
      setLoading(false);
    }
  };

  const getViabilityColor = (score?: number) => {
    if (!score) return 'var(--text-muted)';
    if (score >= 70) return 'var(--success)';
    if (score >= 40) return 'var(--warning)';
    return 'var(--danger)';
  };

  if (loading) {
    return <div className="loading">Loading companies...</div>;
  }

  return (
    <div className="companies-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Companies</h1>
          <p className="page-subtitle">Tracked companies and career pages</p>
        </div>
      </div>

      <div className="companies-filters">
        {['all', 'active', 'inactive'].map((status) => (
          <button
            key={status}
            className={`filter-btn ${filter === status ? 'active' : ''}`}
            onClick={() => setFilter(status)}
          >
            {status.charAt(0).toUpperCase() + status.slice(1)}
          </button>
        ))}
      </div>

      <div className="companies-grid">
        {companies.length === 0 ? (
          <Card className="empty-state-card">
            <div className="empty-state">
              <Building2 size={64} />
              <h3>No companies found</h3>
              <p>Add companies to start tracking their career pages.</p>
            </div>
          </Card>
        ) : (
          companies.map((company) => (
            <Card key={company.id} className="company-card">
              <div className="company-header">
                <div className="company-info">
                  <h3 className="company-name">{company.name}</h3>
                  <div className="company-status">
                    {company.is_active ? (
                      <span className="status-badge active">
                        <CheckCircle size={14} />
                        Active
                      </span>
                    ) : (
                      <span className="status-badge inactive">
                        <XCircle size={14} />
                        Inactive
                      </span>
                    )}
                  </div>
                </div>
                {company.viability_score && (
                  <div
                    className="viability-score"
                    style={{ color: getViabilityColor(company.viability_score) }}
                  >
                    <TrendingUp size={16} />
                    {Math.round(company.viability_score)}%
                  </div>
                )}
              </div>

              <div className="company-details">
                <div className="detail-row">
                  <Globe size={16} />
                  <a
                    href={company.career_page_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="career-link"
                  >
                    {company.career_page_url}
                  </a>
                </div>
                <div className="detail-row">
                  <Activity size={16} />
                  <span>Crawler: {company.crawler_type}</span>
                </div>
              </div>

              <div className="company-stats">
                <div className="stat-item">
                  <div className="stat-value">{company.jobs_found_total}</div>
                  <div className="stat-label">Total Jobs</div>
                </div>
                <div className="stat-item">
                  <div className="stat-value">{company.consecutive_empty_crawls}</div>
                  <div className="stat-label">Empty Crawls</div>
                </div>
                {company.last_crawled_at && (
                  <div className="stat-item">
                    <div className="stat-value">
                      {format(new Date(company.last_crawled_at), 'MMM d')}
                    </div>
                    <div className="stat-label">Last Crawled</div>
                  </div>
                )}
              </div>
            </Card>
          ))
        )}
      </div>
    </div>
  );
};

export default Companies;

