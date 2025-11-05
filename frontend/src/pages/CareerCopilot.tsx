import { ChangeEvent, useEffect, useMemo, useState } from 'react';
import {
  Upload,
  Save,
  Trash2,
  Sparkles,
  Wand2,
  ClipboardList,
  FileText,
  PenTool,
} from 'lucide-react';
import Card from '../components/Card';
import Button from '../components/Button';
import {
  fetchUserDocuments,
  uploadUserDocuments,
  updateUserDocumentContent,
  deleteUserDocument,
  analyzeJobFit,
  generateTailoredDocuments,
  getUserProfile,
} from '../services/api';
import type {
  UserDocument,
  JobFitResponse,
  TailoredDocumentsResponse,
  UserProfile,
} from '../types';
import './CareerCopilot.css';

const formatExperience = (profile: UserProfile | null): string => {
  if (!profile?.experience || profile.experience.length === 0) {
    return '';
  }

  return profile.experience
    .map((exp) => {
      const company = exp.company || 'Company';
      const role = exp.role || exp.title || 'Role';
      const dates = [exp.start_date, exp.end_date].filter(Boolean).join(' → ');
      const description = exp.description || '';
      return `${role} at ${company}${dates ? ` (${dates})` : ''}\n${description}`.trim();
    })
    .join('\n\n');
};

const CareerCopilot = () => {
  const [documents, setDocuments] = useState<UserDocument[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [selectedDocumentId, setSelectedDocumentId] = useState<number | null>(null);
  const [selectedDocumentContent, setSelectedDocumentContent] = useState('');
  const [savingDocument, setSavingDocument] = useState(false);
  const [_profile, setProfile] = useState<UserProfile | null>(null);

  const [jobTitle, setJobTitle] = useState('');
  const [jobCompany, setJobCompany] = useState('');
  const [jobDescription, setJobDescription] = useState('');
  const [jobRequirements, setJobRequirements] = useState('');
  const [userSummary, setUserSummary] = useState('');
  const [userExperience, setUserExperience] = useState('');
  const [userSkillsInput, setUserSkillsInput] = useState('');
  const [analysisDocs, setAnalysisDocs] = useState<number[]>([]);
  const [jobFitResult, setJobFitResult] = useState<JobFitResponse | null>(null);
  const [jobFitLoading, setJobFitLoading] = useState(false);

  const [tailorDocs, setTailorDocs] = useState<number[]>([]);
  const [selectedDocumentTypes, setSelectedDocumentTypes] = useState<string[]>(['resume', 'cover_letter']);
  const [generatedDocuments, setGeneratedDocuments] = useState<TailoredDocumentsResponse['documents']>({});
  const [generateLoading, setGenerateLoading] = useState(false);

  useEffect(() => {
    const initialize = async () => {
      await Promise.all([loadProfile(), loadDocuments()]);
    };
    initialize();
  }, []);

  const loadProfile = async () => {
    try {
      const data = await getUserProfile();
      setProfile(data);
      if (!userSummary) {
        setUserSummary(data.base_resume ? data.base_resume.slice(0, 900) : '');
      }
      if (!userSkillsInput && data.skills) {
        setUserSkillsInput(data.skills.join(', '));
      }
      if (!userExperience) {
        setUserExperience(formatExperience(data));
      }
    } catch (error) {
      console.error('Failed to load profile', error);
    }
  };

  const loadDocuments = async () => {
    try {
      setDocumentsLoading(true);
      const docs = await fetchUserDocuments();
      setDocuments(docs);
      if (docs.length > 0 && !selectedDocumentId) {
        setSelectedDocumentId(docs[0].id);
      }
    } catch (error) {
      console.error('Failed to load documents', error);
    } finally {
      setDocumentsLoading(false);
    }
  };

  const handleUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    if (!event.target.files || event.target.files.length === 0) {
      return;
    }

    try {
      setDocumentsLoading(true);
      await uploadUserDocuments(event.target.files);
      event.target.value = '';
      await loadDocuments();
    } catch (error) {
      console.error('Upload failed', error);
    } finally {
      setDocumentsLoading(false);
    }
  };

  const selectedDocument = useMemo(
    () => documents.find((doc) => doc.id === selectedDocumentId) || null,
    [documents, selectedDocumentId]
  );

  useEffect(() => {
    if (selectedDocument) {
      setSelectedDocumentContent(selectedDocument.content);
    } else {
      setSelectedDocumentContent('');
    }
  }, [selectedDocument]);

  const handleSaveDocument = async () => {
    if (!selectedDocument) return;
    try {
      setSavingDocument(true);
      const updated = await updateUserDocumentContent(selectedDocument.id, {
        content: selectedDocumentContent,
      });
      setDocuments((prev) => prev.map((doc) => (doc.id === updated.id ? { ...doc, ...updated } : doc)));
    } catch (error) {
      console.error('Failed to save document', error);
    } finally {
      setSavingDocument(false);
    }
  };

  const handleDeleteDocument = async () => {
    if (!selectedDocument) return;
    if (!window.confirm('Remove this document from your library?')) {
      return;
    }
    try {
      await deleteUserDocument(selectedDocument.id);
      setDocuments((prev) => prev.filter((doc) => doc.id !== selectedDocument.id));
      setSelectedDocumentId(null);
    } catch (error) {
      console.error('Failed to delete document', error);
    }
  };

  const toggleAnalysisDoc = (id: number) => {
    setAnalysisDocs((prev) => (prev.includes(id) ? prev.filter((docId) => docId !== id) : [...prev, id]));
  };

  const toggleTailorDoc = (id: number) => {
    setTailorDocs((prev) => (prev.includes(id) ? prev.filter((docId) => docId !== id) : [...prev, id]));
  };

  const toggleDocumentType = (docType: string) => {
    setSelectedDocumentTypes((prev) =>
      prev.includes(docType) ? prev.filter((t) => t !== docType) : [...prev, docType]
    );
  };

  const handleAnalyzeJobFit = async () => {
    if (!jobDescription.trim()) return;
    try {
      setJobFitLoading(true);
      const skills = userSkillsInput
        .split(',')
        .map((skill) => skill.trim())
        .filter(Boolean);
      const analysis = await analyzeJobFit({
        job_title: jobTitle || undefined,
        company: jobCompany || undefined,
        job_description: jobDescription,
        requirements: jobRequirements || undefined,
        user_summary: userSummary || undefined,
        user_experience: userExperience || undefined,
        user_skills: skills,
        supporting_document_ids: analysisDocs,
      });
      setJobFitResult(analysis);
    } catch (error) {
      console.error('Job fit analysis failed', error);
    } finally {
      setJobFitLoading(false);
    }
  };

  const handleGenerateDocuments = async () => {
    if (!jobTitle || !jobCompany || !jobDescription) {
      return;
    }
    try {
      setGenerateLoading(true);
      const skills = userSkillsInput
        .split(',')
        .map((skill) => skill.trim())
        .filter(Boolean);
      const payload = await generateTailoredDocuments({
        job_title: jobTitle,
        company: jobCompany,
        job_description: jobDescription,
        requirements: jobRequirements || undefined,
        user_summary: userSummary || undefined,
        user_skills: skills,
        document_ids: tailorDocs,
        document_types: selectedDocumentTypes,
      });
      setGeneratedDocuments(payload.documents);
    } catch (error) {
      console.error('Failed to generate documents', error);
    } finally {
      setGenerateLoading(false);
    }
  };

  return (
    <div className="career-copilot-page">
      <div className="section-header">
        <div>
          <h1 className="page-title">Career Copilot</h1>
          <p className="page-subtitle">
            Upload your materials, understand what employers want, and instantly tailor your applications.
          </p>
        </div>
        <Sparkles size={32} color="#6366f1" />
      </div>

      <div className="career-copilot-grid">
        <div className="document-sidebar">
          <Card className="document-upload">
            <div className="card-header">
              <div className="card-header-content">
                <FileText className="card-icon" size={20} />
                <div>
                  <h3 className="card-title">Document Library</h3>
                  <p className="card-subtitle">Upload resumes, project writeups, and transcripts.</p>
                </div>
              </div>
            </div>
            <label className="btn btn-secondary btn-sm" style={{ cursor: 'pointer', width: 'fit-content' }}>
              <Upload size={16} />
              <span style={{ marginLeft: 6 }}>Upload files</span>
              <input type="file" multiple onChange={handleUpload} style={{ display: 'none' }} />
            </label>
          </Card>

          <div className="document-list">
            {documentsLoading && <div>Loading documents...</div>}
            {!documentsLoading && documents.length === 0 && (
              <Card>
                <p>No supporting documents yet. Upload resumes, cover letters, CSVs, or PDFs to build your knowledge base.</p>
              </Card>
            )}
            {documents.map((doc) => (
              <Card
                key={doc.id}
                className={`document-item ${selectedDocumentId === doc.id ? 'active' : ''}`}
                onClick={() => setSelectedDocumentId(doc.id)}
              >
                <strong>{doc.filename}</strong>
                <div className="document-metadata">
                  <span>{doc.file_type}</span>
                  {doc.metadata?.word_count && <span>{doc.metadata.word_count} words</span>}
                  {doc.metadata?.row_count && <span>{doc.metadata.row_count} rows</span>}
                </div>
              </Card>
            ))}
          </div>
        </div>

        <Card>
          {selectedDocument ? (
            <div className="document-editor">
              <div className="section-header">
                <h2>Edit “{selectedDocument.filename}”</h2>
                <div style={{ display: 'flex', gap: 8 }}>
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={<Trash2 size={14} />}
                    onClick={handleDeleteDocument}
                  >
                    Delete
                  </Button>
                  <Button
                    variant="primary"
                    size="sm"
                    icon={<Save size={14} />}
                    onClick={handleSaveDocument}
                    loading={savingDocument}
                  >
                    Save
                  </Button>
                </div>
              </div>
              <textarea
                value={selectedDocumentContent}
                onChange={(e) => setSelectedDocumentContent(e.target.value)}
              />
              <p className="card-subtitle">
                Changes here are saved back to your personal library so every generation stays up to date.
              </p>
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '60px 20px' }}>
              <PenTool size={32} color="#6366f1" />
              <p>Select a document to review or edit.</p>
            </div>
          )}
        </Card>
      </div>

      <Card>
        <div className="section-header">
          <div>
            <h2>Understand what the company really wants</h2>
            <p className="card-subtitle">
              Paste the job details and we’ll translate the posting into plain language guidance.
            </p>
          </div>
          <ClipboardList size={24} />
        </div>

        <div className="job-fit-section">
          <div>
            <label className="form-label">Job Title</label>
            <input
              className="form-input"
              value={jobTitle}
              onChange={(e) => setJobTitle(e.target.value)}
              placeholder="Senior Frontend Engineer"
            />
            <label className="form-label">Company</label>
            <input
              className="form-input"
              value={jobCompany}
              onChange={(e) => setJobCompany(e.target.value)}
              placeholder="Awesome Startup"
            />
            <label className="form-label">Job Description</label>
            <textarea
              className="form-textarea"
              value={jobDescription}
              onChange={(e) => setJobDescription(e.target.value)}
              placeholder="Paste the full job description here"
              rows={10}
            />
          </div>
          <div>
            <label className="form-label">Requirements (optional)</label>
            <textarea
              className="form-textarea"
              value={jobRequirements}
              onChange={(e) => setJobRequirements(e.target.value)}
              placeholder="Bullet list of requirements if separate from description"
              rows={6}
            />
            <label className="form-label">Your Summary</label>
            <textarea
              className="form-textarea"
              value={userSummary}
              onChange={(e) => setUserSummary(e.target.value)}
              rows={4}
              placeholder="Short summary you want to present"
            />
            <label className="form-label">Experience Highlights</label>
            <textarea
              className="form-textarea"
              value={userExperience}
              onChange={(e) => setUserExperience(e.target.value)}
              rows={4}
              placeholder="Key roles, achievements, or projects"
            />
            <label className="form-label">Skills (comma separated)</label>
            <input
              className="form-input"
              value={userSkillsInput}
              onChange={(e) => setUserSkillsInput(e.target.value)}
              placeholder="React, leadership, system design"
            />
            <div>
              <p className="card-subtitle">Include supporting documents:</p>
              <div className="document-checkboxes">
                {documents.map((doc) => (
                  <label key={`analysis-${doc.id}`} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <input
                      type="checkbox"
                      checked={analysisDocs.includes(doc.id)}
                      onChange={() => toggleAnalysisDoc(doc.id)}
                    />
                    <span>{doc.filename}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="job-fit-actions">
          <div className="card-subtitle">
            We’ll analyze the posting and highlight matched and missing skills.
          </div>
          <Button
            variant="primary"
            icon={<Sparkles size={16} />}
            onClick={handleAnalyzeJobFit}
            loading={jobFitLoading}
          >
            Analyze Fit
          </Button>
        </div>

        {jobFitResult && (
          <div className="analysis-card" style={{ marginTop: 20 }}>
            <Card>
              <h3>Summary</h3>
              <p>{jobFitResult.analysis.summary}</p>
            </Card>
            {jobFitResult.analysis.company_focus && (
              <Card>
                <h3>Company focus</h3>
                <p>{jobFitResult.analysis.company_focus}</p>
              </Card>
            )}
            <Card>
              <h3>Key requirements</h3>
              <ul className="analysis-list">
                {jobFitResult.analysis.key_requirements.map((req, index) => (
                  <li key={`req-${index}`}>{req}</li>
                ))}
              </ul>
            </Card>
            <Card>
              <h3>Skill alignment</h3>
              <p>Overall fit: {jobFitResult.analysis.skill_alignment.overall_fit}</p>
              {jobFitResult.analysis.skill_alignment.matched_skills.length > 0 && (
                <>
                  <strong>Matches</strong>
                  <ul className="analysis-list">
                    {jobFitResult.analysis.skill_alignment.matched_skills.map((skill, index) => (
                      <li key={`match-${index}`}>{skill}</li>
                    ))}
                  </ul>
                </>
              )}
              {jobFitResult.analysis.skill_alignment.missing_skills.length > 0 && (
                <>
                  <strong>Gaps</strong>
                  <ul className="analysis-list">
                    {jobFitResult.analysis.skill_alignment.missing_skills.map((skill, index) => (
                      <li key={`gap-${index}`}>{skill}</li>
                    ))}
                  </ul>
                </>
              )}
              {jobFitResult.analysis.skill_alignment.upskill_suggestions.length > 0 && (
                <>
                  <strong>Suggested next steps</strong>
                  <ul className="analysis-list">
                    {jobFitResult.analysis.skill_alignment.upskill_suggestions.map((tip, index) => (
                      <li key={`upskill-${index}`}>{tip}</li>
                    ))}
                  </ul>
                </>
              )}
            </Card>
            {jobFitResult.analysis.tailoring_tips.length > 0 && (
              <Card>
                <h3>Tailoring tips</h3>
                <ul className="analysis-list">
                  {jobFitResult.analysis.tailoring_tips.map((tip, index) => (
                    <li key={`tailor-${index}`}>{tip}</li>
                  ))}
                </ul>
              </Card>
            )}
            {jobFitResult.analysis.interview_prep.length > 0 && (
              <Card>
                <h3>Interview prep</h3>
                <ul className="analysis-list">
                  {jobFitResult.analysis.interview_prep.map((tip, index) => (
                    <li key={`prep-${index}`}>{tip}</li>
                  ))}
                </ul>
              </Card>
            )}
          </div>
        )}
      </Card>

      <Card>
        <div className="section-header">
          <div>
            <h2>Create tailored application materials</h2>
            <p className="card-subtitle">
              Mix and match resumes, project narratives, or CSV data to generate ATS-ready materials.
            </p>
          </div>
          <Wand2 size={24} />
        </div>

        <div className="tailored-documents-section">
          <div>
            <label className="form-label">Use these documents</label>
            <div className="document-checkboxes">
              {documents.map((doc) => (
                <label key={`tailor-${doc.id}`} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <input
                    type="checkbox"
                    checked={tailorDocs.includes(doc.id)}
                    onChange={() => toggleTailorDoc(doc.id)}
                  />
                  <span>{doc.filename}</span>
                </label>
              ))}
            </div>
            <label className="form-label">Generate</label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input
                  type="checkbox"
                  checked={selectedDocumentTypes.includes('resume')}
                  onChange={() => toggleDocumentType('resume')}
                />
                Resume
              </label>
              <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input
                  type="checkbox"
                  checked={selectedDocumentTypes.includes('cover_letter')}
                  onChange={() => toggleDocumentType('cover_letter')}
                />
                Cover Letter
              </label>
            </div>
          </div>
          <div>
            {Object.entries(generatedDocuments).map(([key, value]) => (
              value && (
                <div key={key} style={{ marginBottom: 16 }}>
                  <h3 style={{ textTransform: 'capitalize' }}>{key.replace('_', ' ')}</h3>
                  <div className="generated-output">{value}</div>
                </div>
              )
            ))}
            {Object.keys(generatedDocuments).length === 0 && (
              <div className="card-subtitle" style={{ paddingTop: 24 }}>
                Generated documents will appear here ready to copy or download.
              </div>
            )}
          </div>
        </div>

        <div className="tailored-actions">
          <div className="card-subtitle">
            Tip: Select only the documents you want the AI to learn from before generating.
          </div>
          <Button
            variant="primary"
            icon={<Wand2 size={16} />}
            onClick={handleGenerateDocuments}
            loading={generateLoading}
            disabled={selectedDocumentTypes.length === 0}
          >
            Generate Materials
          </Button>
        </div>
      </Card>
    </div>
  );
};

export default CareerCopilot;
