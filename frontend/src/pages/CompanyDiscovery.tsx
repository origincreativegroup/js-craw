import { useEffect, useState } from 'react';
import { Search, CheckCircle, XCircle, RefreshCw, Globe, Building2, TrendingUp, Clock } from 'lucide-react';
import Card from '../components/Card';
import Button from '../components/Button';
import { getDiscoveryStatus, runDiscovery, getPendingCompanies, approvePendingCompany, rejectPendingCompany } from '../services/api';
import type { PendingCompany, DiscoveryStatus } from '../types';
import { format } from 'date-fns';
import './CompanyDiscovery.css';

const CompanyDiscovery = () => {
  const [status, setStatus] = useState<DiscoveryStatus | null>(null);
  const [pendingCompanies, setPendingCompanies] = useState<PendingCompany[]>([]);
  const [loading, setLoading] = useState(true);
  const [discovering, setDiscovering] = useState(false);
  const [processing, setProcessing] = useState<number | null>(null);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const [statusData, pendingData] = await Promise.all([
        getDiscoveryStatus(),
        getPendingCompanies(),
      ]);
      setStatus(statusData);
      setPendingCompanies(pendingData);
    } catch (error) {
      console.error('Error loading discovery data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleRunDiscovery = async () => {
    setDiscovering(true);
    try {
      await runDiscovery();
      await loadData(); // Refresh data after discovery
    } catch (error) {
      console.error('Error running discovery:', error);
      alert('Failed to run discovery. Please try again.');
    } finally {
      setDiscovering(false);
    }
  };

  const handleApprove = async (pendingId: number) => {
    setProcessing(pendingId);
    try {
      await approvePendingCompany(pendingId);
      await loadData(); // Refresh data
    } catch (error) {
      console.error('Error approving company:', error);
      alert('Failed to approve company. Please try again.');
    } finally {
      setProcessing(null);
    }
  };

  const handleReject = async (pendingId: number) => {
    if (!confirm('Are you sure you want to reject this company?')) {
      return;
    }
    setProcessing(pendingId);
    try {
      await rejectPendingCompany(pendingId);
      await loadData(); // Refresh data
    } catch (error) {
      console.error('Error rejecting company:', error);
      alert('Failed to reject company. Please try again.');
    } finally {
      setProcessing(null);
    }
  };

  const getConfidenceColor = (score: number) => {
    if (score >= 70) return 'var(--success)';
    if (score >= 50) return 'var(--warning)';
    return 'var(--danger)';
  };

  const getSourceIcon = (source: string) => {
    switch (source) {
      case 'linkedin':
        return '💼';
      case 'indeed':
        return '🔍';
      case 'web_search':
        return '🌐';
      default:
        return '🏢';
    }
  };

  if (loading) {
    return <div className="loading">Loading discovery data...</div>;
  }

  const progressPercent = status
    ? Math.min(100, (status.active_companies / status.target_companies) * 100)
    : 0;

  return (
    <div className="company-discovery-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Company Discovery</h1>
          <p className="page-subtitle">Automatically discover and add companies to your database</p>
        </div>
        <Button
          onClick={handleRunDiscovery}
          disabled={discovering}
          className="primary"
        >
          {discovering ? (
            <>
              <RefreshCw className="icon spinning" />
              Discovering...
            </>
          ) : (
            <>
              <Search className="icon" />
              Run Discovery Now
            </>
          )}
        </Button>
      </div>

      {status && (
        <div className="discovery-stats">
          <Card className="stat-card">
            <div className="stat-icon" style={{ background: 'var(--primary)' }}>
              <Building2 size={24} />
            </div>
            <div className="stat-content">
              <div className="stat-value">{status.active_companies.toLocaleString()}</div>
              <div className="stat-label">Active Companies</div>
              <div className="stat-target">Target: {status.target_companies.toLocaleString()}</div>
            </div>
          </Card>

          <Card className="stat-card">
            <div className="stat-icon" style={{ background: 'var(--warning)' }}>
              <Clock size={24} />
            </div>
            <div className="stat-content">
              <div className="stat-value">{status.pending_count}</div>
              <div className="stat-label">Pending Approval</div>
              <div className="stat-subtext">Awaiting review</div>
            </div>
          </Card>

          <Card className="stat-card">
            <div className="stat-icon" style={{ background: status.discovery_enabled ? 'var(--success)' : 'var(--text-muted)' }}>
              <TrendingUp size={24} />
            </div>
            <div className="stat-content">
              <div className="stat-value">{status.discovery_enabled ? 'ON' : 'OFF'}</div>
              <div className="stat-label">Auto Discovery</div>
              <div className="stat-subtext">Every {status.discovery_interval_hours}h</div>
            </div>
          </Card>

          <Card className="stat-card">
            <div className="stat-icon" style={{ background: 'var(--info)' }}>
              <Globe size={24} />
            </div>
            <div className="stat-content">
              <div className="stat-value">{status.auto_approve_threshold}%</div>
              <div className="stat-label">Auto-Approve Threshold</div>
              <div className="stat-subtext">Confidence score</div>
            </div>
          </Card>
        </div>
      )}

      {status && (
        <Card className="progress-card">
          <div className="progress-header">
            <span>Progress to Target</span>
            <span className="progress-text">
              {status.active_companies.toLocaleString()} / {status.target_companies.toLocaleString()}
            </span>
          </div>
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </Card>
      )}

      <div className="pending-section">
        <div className="section-header">
          <h2>Pending Companies</h2>
          <span className="count-badge">{pendingCompanies.length}</span>
        </div>

        {pendingCompanies.length === 0 ? (
          <Card className="empty-state-card">
            <div className="empty-state">
              <CheckCircle size={64} />
              <h3>No pending companies</h3>
              <p>All discovered companies have been reviewed. Run discovery to find more!</p>
            </div>
          </Card>
        ) : (
          <div className="pending-companies-grid">
            {pendingCompanies.map((company) => (
              <Card key={company.id} className="pending-company-card">
                <div className="pending-company-header">
                  <div className="company-info">
                    <h3 className="company-name">{company.name}</h3>
                    <div className="company-meta">
                      <span className="source-badge">
                        {getSourceIcon(company.discovery_source)} {company.discovery_source}
                      </span>
                      <span
                        className="confidence-badge"
                        style={{ color: getConfidenceColor(company.confidence_score) }}
                      >
                        {company.confidence_score.toFixed(1)}% confidence
                      </span>
                    </div>
                  </div>
                </div>

                <div className="pending-company-details">
                  <div className="detail-item">
                    <span className="detail-label">Career Page:</span>
                    <a
                      href={company.career_page_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="career-link"
                    >
                      {company.career_page_url}
                    </a>
                  </div>
                  <div className="detail-item">
                    <span className="detail-label">Crawler Type:</span>
                    <span className="detail-value">{company.crawler_type}</span>
                  </div>
                  <div className="detail-item">
                    <span className="detail-label">Discovered:</span>
                    <span className="detail-value">
                      {format(new Date(company.created_at), 'MMM d, yyyy')}
                    </span>
                  </div>
                </div>

                <div className="pending-company-actions">
                  <Button
                    onClick={() => handleReject(company.id)}
                    disabled={processing === company.id}
                    className="secondary danger"
                    size="sm"
                  >
                    <XCircle size={16} />
                    Reject
                  </Button>
                  <Button
                    onClick={() => handleApprove(company.id)}
                    disabled={processing === company.id}
                    className="primary"
                    size="sm"
                  >
                    {processing === company.id ? (
                      <RefreshCw size={16} className="spinning" />
                    ) : (
                      <CheckCircle size={16} />
                    )}
                    Approve
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default CompanyDiscovery;
