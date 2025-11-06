import { useEffect, useState } from 'react';
import { Download, FileText, Sparkles, History, Eye } from 'lucide-react';
import Card from './Card';
import Button from './Button';
import { getJobDocuments, generateDocuments } from '../services/api';
import { syncService } from '../services/syncService';
import './JobFileManager.css';

interface JobFileManagerProps {
  jobId: number;
  onRefresh?: () => void;
}

const JobFileManager: React.FC<JobFileManagerProps> = ({ jobId, onRefresh }) => {
  const [documents, setDocuments] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [selectedFolder, setSelectedFolder] = useState<'user' | 'generated' | 'exports'>('generated');
  const [selectedDocument, setSelectedDocument] = useState<any>(null);
  const [generating, setGenerating] = useState<string[]>([]);

  useEffect(() => {
    loadDocuments();
  }, [jobId]);

  const loadDocuments = async (forceRefresh = false) => {
    try {
      setLoading(true);
      // Use sync service for caching
      const data = await syncService.get(
        `job-documents:${jobId}`,
        () => getJobDocuments(jobId),
        { forceRefresh }
      );
      setDocuments(data);
    } catch (error) {
      console.error('Error loading documents:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async (type: string) => {
    try {
      setGenerating(prev => [...prev, type]);
      await generateDocuments(jobId, [type]);
      // Invalidate cache to force refresh
      syncService.invalidate(`job-documents:${jobId}`);
      await loadDocuments(true);
      if (onRefresh) onRefresh();
    } catch (error) {
      console.error('Error generating document:', error);
      alert('Failed to generate document');
    } finally {
      setGenerating(prev => prev.filter(t => t !== type));
    }
  };

  const handleDownload = (doc: any) => {
    const blob = new Blob([doc.content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${doc.document_type}-${jobId}-v${doc.version || 1}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleView = (doc: any) => {
    setSelectedDocument(doc);
  };

  if (loading) {
    return <div className="loading">Loading documents...</div>;
  }

  const userDocs = documents?.user_documents || [];
  const generatedDocs = documents?.generated_documents || [];
  const resume = generatedDocs.find((d: any) => d.document_type === 'resume');
  const coverLetter = generatedDocs.find((d: any) => d.document_type === 'cover_letter');
  const versions = documents?.versions || {};

  return (
    <div className="job-file-manager">
      {/* Folder Tabs */}
      <div className="folder-tabs">
        <button
          className={`folder-tab ${selectedFolder === 'user' ? 'active' : ''}`}
          onClick={() => setSelectedFolder('user')}
        >
          <FileText size={16} />
          User Documents ({userDocs.length})
        </button>
        <button
          className={`folder-tab ${selectedFolder === 'generated' ? 'active' : ''}`}
          onClick={() => setSelectedFolder('generated')}
        >
          <Sparkles size={16} />
          Generated ({generatedDocs.length})
        </button>
        <button
          className={`folder-tab ${selectedFolder === 'exports' ? 'active' : ''}`}
          onClick={() => setSelectedFolder('exports')}
        >
          <Download size={16} />
          Exports
        </button>
      </div>

      {/* Content Area */}
      <div className="file-manager-content">
        {selectedFolder === 'user' && (
          <div className="folder-content">
            {userDocs.length === 0 ? (
              <div className="empty-state">
                <FileText size={48} />
                <p>No user documents available</p>
                <p className="empty-hint">Upload documents in Career Hub to use them for job applications</p>
              </div>
            ) : (
              <div className="document-list">
                {userDocs.map((doc: any) => (
                  <Card key={doc.id} className="document-item">
                    <div className="document-header">
                      <FileText size={20} />
                      <div className="document-info">
                        <div className="document-name">{doc.filename}</div>
                        <div className="document-meta">
                          {doc.file_type} • {doc.metadata?.word_count || 0} words
                        </div>
                      </div>
                    </div>
                    <div className="document-actions">
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={<Eye size={14} />}
                        onClick={() => handleView(doc)}
                      >
                        View
                      </Button>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}

        {selectedFolder === 'generated' && (
          <div className="folder-content">
            <div className="generate-actions">
              <Card className="generate-card">
                <div className="generate-header">
                  <FileText size={20} />
                  <div>
                    <h4>Resume</h4>
                    <p className="generate-hint">Generate a tailored resume for this job</p>
                  </div>
                </div>
                <Button
                  variant={resume ? 'secondary' : 'primary'}
                  size="sm"
                  icon={<Sparkles size={16} />}
                  onClick={() => handleGenerate('resume')}
                  loading={generating.includes('resume')}
                >
                  {resume ? 'Regenerate' : 'Generate Resume'}
                </Button>
              </Card>

              <Card className="generate-card">
                <div className="generate-header">
                  <FileText size={20} />
                  <div>
                    <h4>Cover Letter</h4>
                    <p className="generate-hint">Generate a tailored cover letter for this job</p>
                  </div>
                </div>
                <Button
                  variant={coverLetter ? 'secondary' : 'primary'}
                  size="sm"
                  icon={<Sparkles size={16} />}
                  onClick={() => handleGenerate('cover_letter')}
                  loading={generating.includes('cover_letter')}
                >
                  {coverLetter ? 'Regenerate' : 'Generate Cover Letter'}
                </Button>
              </Card>
            </div>

            {generatedDocs.length > 0 && (
              <div className="document-list">
                {generatedDocs.map((doc: any) => (
                  <Card key={doc.id} className="document-item">
                    <div className="document-header">
                      <FileText size={20} />
                      <div className="document-info">
                        <div className="document-name">
                          {doc.document_type.replace('_', ' ').replace(/\b\w/g, (l: string) => l.toUpperCase())}
                          {doc.version > 1 && <span className="version-badge">v{doc.version}</span>}
                        </div>
                        <div className="document-meta">
                          Generated {new Date(doc.generated_at).toLocaleDateString()}
                          {versions[doc.document_type] && versions[doc.document_type].length > 1 && (
                            <span> • {versions[doc.document_type].length} versions</span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="document-actions">
                      {versions[doc.document_type] && versions[doc.document_type].length > 1 && (
                        <Button
                          variant="ghost"
                          size="sm"
                          icon={<History size={14} />}
                          onClick={() => setSelectedDocument({ ...doc, showVersions: true })}
                        >
                          Versions
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={<Eye size={14} />}
                        onClick={() => handleView(doc)}
                      >
                        View
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={<Download size={14} />}
                        onClick={() => handleDownload(doc)}
                      >
                        Download
                      </Button>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}

        {selectedFolder === 'exports' && (
          <div className="folder-content">
            <div className="empty-state">
              <Download size={48} />
              <p>Export functionality coming soon</p>
              <p className="empty-hint">Export all documents for this job as a ZIP file</p>
            </div>
          </div>
        )}
      </div>

      {/* Document Viewer Modal */}
      {selectedDocument && (
        <div className="document-viewer-overlay" onClick={() => setSelectedDocument(null)}>
          <div className="document-viewer" onClick={(e) => e.stopPropagation()}>
            <div className="viewer-header">
              <h3>
                {selectedDocument.filename || 
                 selectedDocument.document_type?.replace('_', ' ').replace(/\b\w/g, (l: string) => l.toUpperCase())}
                {selectedDocument.version && ` v${selectedDocument.version}`}
              </h3>
              <button className="close-viewer" onClick={() => setSelectedDocument(null)}>×</button>
            </div>
            <div className="viewer-content">
              {selectedDocument.showVersions && versions[selectedDocument.document_type] ? (
                <div className="versions-list">
                  {versions[selectedDocument.document_type].map((version: any) => (
                    <Card key={version.id} className="version-item">
                      <div className="version-header">
                        <span>Version {version.version}</span>
                        <span className="version-date">
                          {new Date(version.generated_at).toLocaleDateString()}
                        </span>
                      </div>
                      <div className="version-actions">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setSelectedDocument(version);
                          }}
                        >
                          View
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          icon={<Download size={14} />}
                          onClick={() => handleDownload(version)}
                        >
                          Download
                        </Button>
                      </div>
                    </Card>
                  ))}
                </div>
              ) : (
                <pre className="document-content">{selectedDocument.content}</pre>
              )}
            </div>
            <div className="viewer-footer">
              <Button
                variant="secondary"
                size="sm"
                icon={<Download size={16} />}
                onClick={() => handleDownload(selectedDocument)}
              >
                Download
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSelectedDocument(null)}
              >
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default JobFileManager;

