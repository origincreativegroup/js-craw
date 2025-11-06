import { ChangeEvent, useEffect, useMemo, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Upload,
  Save,
  Trash2,
  Sparkles,
  Wand2,
  ClipboardList,
  FileText,
  PenTool,
  X,
  File,
  Loader,
  CheckCircle2,
  AlertCircle,
  Plus,
  Briefcase,
  GraduationCap,
  Settings,
  CheckCircle,
  Clock,
  Edit,
  Send,
  MessageSquare,
  XCircle,
  Download,
  FileCheck,
  ArrowRight,
  CheckSquare,
  Calendar,
  User,
  FolderOpen,
  BarChart3,
  Briefcase as BriefcaseIcon,
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
  updateUserProfile,
  getApplications,
  updateApplication,
  generateDocuments,
  getDocuments,
  getJob,
} from '../services/api';
import type {
  UserDocument,
  JobFitResponse,
  TailoredDocumentsResponse,
  UserProfile,
  UserProfileUpdate,
  Application,
  GeneratedDocument,
  Job,
} from '../types';
import { format, parseISO } from 'date-fns';
import './CareerHub.css';

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

interface FileUploadItem {
  file: File;
  status: 'pending' | 'uploading' | 'success' | 'error';
  error?: string;
  progress?: number;
}

type TabId = 'profile' | 'documents' | 'analyze' | 'applications';

const CareerHub = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<TabId>('profile');

  // Profile Tab State
  const [profileLoading, setProfileLoading] = useState(true);
  const [profileSaving, setProfileSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);
  const [baseResume, setBaseResume] = useState('');
  const [skills, setSkills] = useState<string[]>([]);
  const [newSkill, setNewSkill] = useState('');
  const [experience, setExperience] = useState<Array<{
    company?: string;
    role?: string;
    start_date?: string;
    end_date?: string;
    description?: string;
  }>>([]);
  const [education, setEducation] = useState<{
    degree?: string;
    field?: string;
    institution?: string;
    graduation_date?: string;
  } | null>(null);
  const [preferences, setPreferences] = useState<{
    keywords?: string;
    location?: string;
    locations?: string[];
    remote_preferred?: boolean;
    work_type?: 'remote' | 'office' | 'hybrid' | 'any';
    experience_level?: string;
  }>({
    keywords: '',
    location: '',
    locations: [],
    remote_preferred: true,
    work_type: 'any',
    experience_level: ''
  });
  const [newLocation, setNewLocation] = useState('');
  const [_profile, setProfile] = useState<UserProfile | null>(null);

  // Documents Tab State
  const [documents, setDocuments] = useState<UserDocument[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [selectedDocumentId, setSelectedDocumentId] = useState<number | null>(null);
  const [selectedDocumentContent, setSelectedDocumentContent] = useState('');
  const [savingDocument, setSavingDocument] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [uploadQueue, setUploadQueue] = useState<FileUploadItem[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Analyze Tab State
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

  // Applications Tab State
  const [applications, setApplications] = useState<(Application & { job?: Job })[]>([]);
  const [applicationsLoading, setApplicationsLoading] = useState(true);
  const [appDocuments, setAppDocuments] = useState<Record<number, GeneratedDocument[]>>({});
  const [generating, setGenerating] = useState<number | null>(null);
  const [expandedApp, setExpandedApp] = useState<number | null>(null);
  const [formData, setFormData] = useState<Record<number, { portal_url?: string; confirmation_number?: string; notes?: string }>>({});

  // Initialize data
  useEffect(() => {
    const initialize = async () => {
      await Promise.all([loadProfile(), loadDocuments()]);
    };
    initialize();
  }, []);

  useEffect(() => {
    if (activeTab === 'applications') {
      loadApplications();
      const interval = setInterval(loadApplications, 30000);
      return () => clearInterval(interval);
    }
  }, [activeTab]);

  // Profile Functions
  const loadProfile = async () => {
    try {
      setProfileLoading(true);
      const data = await getUserProfile();
      setProfile(data);
      setBaseResume(data.base_resume || '');
      setSkills(data.skills || []);
      setExperience(data.experience || []);
      setEducation(data.education || {
        degree: '',
        field: '',
        institution: '',
        graduation_date: ''
      });
      setPreferences({
        keywords: data.preferences?.keywords || '',
        location: data.preferences?.location || '',
        locations: data.preferences?.locations || [],
        remote_preferred: data.preferences?.remote_preferred ?? true,
        work_type: data.preferences?.work_type || 'any',
        experience_level: data.preferences?.experience_level || ''
      });
      // Sync to analyze tab
      setUserSummary(data.base_resume || '');
      setUserSkillsInput(data.skills ? data.skills.join(', ') : '');
      setUserExperience(formatExperience(data));
    } catch (error) {
      console.error('Error loading profile:', error);
      setSaveMessage({ type: 'error', text: 'Failed to load profile' });
    } finally {
      setProfileLoading(false);
    }
  };

  const handleSaveProfile = async () => {
    try {
      setProfileSaving(true);
      setSaveMessage(null);
      
      const update: UserProfileUpdate = {
        base_resume: baseResume,
        skills: skills,
        experience: experience,
        education: education || undefined,
        preferences: {
          keywords: preferences.keywords || undefined,
          location: preferences.location || undefined,
          locations: preferences.locations && preferences.locations.length > 0 ? preferences.locations : undefined,
          remote_preferred: preferences.remote_preferred,
          work_type: preferences.work_type,
          experience_level: preferences.experience_level || undefined
        }
      };
      
      await updateUserProfile(update);
      setSaveMessage({ type: 'success', text: 'Profile saved successfully!' });
      
      await loadProfile();
      
      setTimeout(() => setSaveMessage(null), 3000);
    } catch (error) {
      console.error('Error saving profile:', error);
      setSaveMessage({ type: 'error', text: 'Failed to save profile' });
    } finally {
      setProfileSaving(false);
    }
  };

  const addSkill = () => {
    if (newSkill.trim() && !skills.includes(newSkill.trim())) {
      setSkills([...skills, newSkill.trim()]);
      setNewSkill('');
    }
  };

  const removeSkill = (skill: string) => {
    setSkills(skills.filter(s => s !== skill));
  };

  const addExperience = () => {
    setExperience([...experience, {
      company: '',
      role: '',
      start_date: '',
      end_date: '',
      description: ''
    }]);
  };

  const updateExperience = (index: number, field: string, value: string) => {
    const updated = [...experience];
    updated[index] = { ...updated[index], [field]: value };
    setExperience(updated);
  };

  const removeExperience = (index: number) => {
    setExperience(experience.filter((_, i) => i !== index));
  };

  const addLocation = () => {
    if (newLocation.trim() && !preferences.locations?.includes(newLocation.trim())) {
      setPreferences({
        ...preferences,
        locations: [...(preferences.locations || []), newLocation.trim()]
      });
      setNewLocation('');
    }
  };

  const removeLocation = (location: string) => {
    setPreferences({
      ...preferences,
      locations: preferences.locations?.filter(l => l !== location) || []
    });
  };

  // Documents Functions
  const loadDocuments = async () => {
    try {
      setDocumentsLoading(true);
      const docs = await fetchUserDocuments();
      setDocuments(docs);
      if (docs.length > 0 && !selectedDocumentId) {
        setSelectedDocumentId(docs[0].id);
      }
      if (docs.length > 0) {
        setAnalysisDocs(docs.map(doc => doc.id));
        setTailorDocs(docs.map(doc => doc.id));
      }
    } catch (error) {
      console.error('Failed to load documents', error);
    } finally {
      setDocumentsLoading(false);
    }
  };

  const handleFiles = async (files: FileList | File[]) => {
    const fileArray = Array.from(files);
    if (fileArray.length === 0) return;

    const queueItems: FileUploadItem[] = fileArray.map((file) => ({
      file,
      status: 'uploading' as const,
      progress: 50,
    }));
    setUploadQueue(queueItems);

    try {
      const result = await uploadUserDocuments(fileArray);
      const uploadedMap = new Map(result.map((doc) => [doc.filename, doc]));

      setUploadQueue((prev) =>
        prev.map((item) => {
          const uploaded = uploadedMap.get(item.file.name);
          if (uploaded) {
            return { ...item, status: 'success' as const, progress: 100 };
          }
          return item;
        })
      );

      await loadDocuments();
    } catch (error: any) {
      const errorMessage = error?.response?.data?.detail || error?.message || 'Upload failed';
      setUploadQueue((prev) =>
        prev.map((item) => ({
          ...item,
          status: 'error' as const,
          error: errorMessage,
        }))
      );
    }

    setTimeout(() => {
      setUploadQueue([]);
    }, 3000);
  };

  const handleUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    if (!event.target.files || event.target.files.length === 0) {
      return;
    }
    await handleFiles(event.target.files);
    if (event.target) {
      event.target.value = '';
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      await handleFiles(e.dataTransfer.files);
    }
  };

  const removeFromQueue = (index: number) => {
    setUploadQueue((prev) => prev.filter((_, i) => i !== index));
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
    if (!selectedDocument) {
      return;
    }
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

  // Analyze Functions
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
      const skillsArray = userSkillsInput
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
        user_skills: skillsArray,
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
      const skillsArray = userSkillsInput
        .split(',')
        .map((skill) => skill.trim())
        .filter(Boolean);
      const payload = await generateTailoredDocuments({
        job_title: jobTitle,
        company: jobCompany,
        job_description: jobDescription,
        requirements: jobRequirements || undefined,
        user_summary: userSummary || undefined,
        user_skills: skillsArray,
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

  // Applications Functions
  const loadApplications = async () => {
    try {
      setApplicationsLoading(true);
      const data = await getApplications({ status: 'queued', limit: 100 });
      const draftingData = await getApplications({ status: 'drafting', limit: 100 });
      const allApps = [...data, ...draftingData];
      
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
      
      const initialFormData: Record<number, { portal_url?: string; confirmation_number?: string; notes?: string }> = {};
      appsWithJobs.forEach(app => {
        initialFormData[app.id] = {
          portal_url: app.portal_url || '',
          confirmation_number: app.confirmation_number || '',
          notes: app.notes || '',
        };
      });
      setFormData(initialFormData);
      
      for (const app of appsWithJobs) {
        await loadDocumentsForJob(app.job_id);
      }
    } catch (error) {
      console.error('Error loading applications:', error);
    } finally {
      setApplicationsLoading(false);
    }
  };

  const loadDocumentsForJob = async (jobId: number) => {
    try {
      const docs = await getDocuments(jobId);
      setAppDocuments(prev => ({ ...prev, [jobId]: docs }));
    } catch (error) {
      console.error(`Error loading documents for job ${jobId}:`, error);
    }
  };

  const handleGenerateDocumentsForJob = async (jobId: number) => {
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
    }
  };

  const handleUpdateApplication = async (appId: number, data: Partial<Application>) => {
    try {
      await updateApplication(appId, data);
      await loadApplications();
    } catch (error) {
      console.error('Error updating application:', error);
      alert('Failed to update application.');
    }
  };

  const getCurrentStepIndex = (status: ApplicationStatus): number => {
    return STATUS_ORDER.indexOf(status);
  };

  const getJobDocuments = (jobId: number): GeneratedDocument[] => {
    return appDocuments[jobId] || [];
  };

  const getResume = (jobId: number): GeneratedDocument | undefined => {
    return getJobDocuments(jobId).find(doc => doc.document_type === 'resume');
  };

  const getCoverLetter = (jobId: number): GeneratedDocument | undefined => {
    return getJobDocuments(jobId).find(doc => doc.document_type === 'cover_letter');
  };

  // Tab content
  const renderProfileTab = () => {
    if (profileLoading) {
      return <div className="loading">Loading profile...</div>;
    }

    return (
      <div className="career-hub-tab-content">
        {saveMessage && (
          <div className={`save-message save-message-${saveMessage.type}`}>
            {saveMessage.type === 'success' ? (
              <CheckCircle size={16} />
            ) : (
              <AlertCircle size={16} />
            )}
            <span>{saveMessage.text}</span>
          </div>
        )}

        <div className="profile-grid">
          <Card className="profile-card">
            <div className="card-header">
              <div className="card-header-content">
                <FileText size={24} className="card-icon" />
                <div>
                  <h2 className="card-title">Resume Content</h2>
                  <p className="card-subtitle">Paste your resume(s) in markdown format for AI filtering</p>
                </div>
              </div>
            </div>
            <div className="settings-content">
              <div className="form-group">
                <label className="form-label">Resume Text (Markdown)</label>
                <textarea
                  value={baseResume}
                  onChange={(e) => setBaseResume(e.target.value)}
                  className="form-textarea"
                  placeholder="Paste your resume content here in markdown format..."
                  rows={15}
                />
                <small className="form-help">
                  This content will be used by AI to match jobs to your background.
                </small>
              </div>
            </div>
          </Card>

          <Card className="profile-card">
            <div className="card-header">
              <div className="card-header-content">
                <Briefcase size={24} className="card-icon" />
                <div>
                  <h2 className="card-title">Skills</h2>
                  <p className="card-subtitle">List your technical and professional skills</p>
                </div>
              </div>
            </div>
            <div className="settings-content">
              <div className="form-group">
                <label className="form-label">Add Skill</label>
                <div className="form-input-group">
                  <input
                    type="text"
                    value={newSkill}
                    onChange={(e) => setNewSkill(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && addSkill()}
                    className="form-input"
                    placeholder="e.g., Python, React, Project Management"
                  />
                  <Button
                    variant="secondary"
                    size="md"
                    icon={<Plus size={16} />}
                    onClick={addSkill}
                  >
                    Add
                  </Button>
                </div>
              </div>
              {skills.length > 0 && (
                <div className="skills-list">
                  {skills.map((skill, index) => (
                    <span key={index} className="skill-tag">
                      {skill}
                      <button
                        type="button"
                        className="skill-remove"
                        onClick={() => removeSkill(skill)}
                      >
                        <X size={14} />
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>
          </Card>

          <Card className="profile-card">
            <div className="card-header">
              <div className="card-header-content">
                <Briefcase size={24} className="card-icon" />
                <div>
                  <h2 className="card-title">Work Experience</h2>
                  <p className="card-subtitle">Add your professional work experience</p>
                </div>
              </div>
              <Button
                variant="secondary"
                size="sm"
                icon={<Plus size={16} />}
                onClick={addExperience}
              >
                Add Experience
              </Button>
            </div>
            <div className="settings-content">
              {experience.length === 0 ? (
                <p className="empty-state">No experience entries. Click "Add Experience" to get started.</p>
              ) : (
                experience.map((exp, index) => (
                  <div key={index} className="experience-entry">
                    <div className="experience-header">
                      <h4 className="experience-title">Experience {index + 1}</h4>
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={<X size={14} />}
                        onClick={() => removeExperience(index)}
                      >
                        Remove
                      </Button>
                    </div>
                    <div className="experience-form">
                      <div className="form-row">
                        <div className="form-group">
                          <label className="form-label">Company</label>
                          <input
                            type="text"
                            value={exp.company || ''}
                            onChange={(e) => updateExperience(index, 'company', e.target.value)}
                            className="form-input"
                            placeholder="Company name"
                          />
                        </div>
                        <div className="form-group">
                          <label className="form-label">Role/Title</label>
                          <input
                            type="text"
                            value={exp.role || ''}
                            onChange={(e) => updateExperience(index, 'role', e.target.value)}
                            className="form-input"
                            placeholder="Job title"
                          />
                        </div>
                      </div>
                      <div className="form-row">
                        <div className="form-group">
                          <label className="form-label">Start Date</label>
                          <input
                            type="text"
                            value={exp.start_date || ''}
                            onChange={(e) => updateExperience(index, 'start_date', e.target.value)}
                            className="form-input"
                            placeholder="MM/YYYY or YYYY"
                          />
                        </div>
                        <div className="form-group">
                          <label className="form-label">End Date</label>
                          <input
                            type="text"
                            value={exp.end_date || ''}
                            onChange={(e) => updateExperience(index, 'end_date', e.target.value)}
                            className="form-input"
                            placeholder="MM/YYYY, YYYY, or 'Present'"
                          />
                        </div>
                      </div>
                      <div className="form-group">
                        <label className="form-label">Description</label>
                        <textarea
                          value={exp.description || ''}
                          onChange={(e) => updateExperience(index, 'description', e.target.value)}
                          className="form-textarea"
                          placeholder="Describe your responsibilities and achievements..."
                          rows={4}
                        />
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </Card>

          <Card className="profile-card">
            <div className="card-header">
              <div className="card-header-content">
                <GraduationCap size={24} className="card-icon" />
                <div>
                  <h2 className="card-title">Education</h2>
                  <p className="card-subtitle">Your educational background</p>
                </div>
              </div>
            </div>
            <div className="settings-content">
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Degree</label>
                  <input
                    type="text"
                    value={education?.degree || ''}
                    onChange={(e) => setEducation({ ...education, degree: e.target.value })}
                    className="form-input"
                    placeholder="e.g., Bachelor's, Master's, PhD"
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Field of Study</label>
                  <input
                    type="text"
                    value={education?.field || ''}
                    onChange={(e) => setEducation({ ...education, field: e.target.value })}
                    className="form-input"
                    placeholder="e.g., Computer Science, Business"
                  />
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Institution</label>
                  <input
                    type="text"
                    value={education?.institution || ''}
                    onChange={(e) => setEducation({ ...education, institution: e.target.value })}
                    className="form-input"
                    placeholder="University or school name"
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Graduation Date</label>
                  <input
                    type="text"
                    value={education?.graduation_date || ''}
                    onChange={(e) => setEducation({ ...education, graduation_date: e.target.value })}
                    className="form-input"
                    placeholder="YYYY or MM/YYYY"
                  />
                </div>
              </div>
            </div>
          </Card>

          <Card className="profile-card">
            <div className="card-header">
              <div className="card-header-content">
                <Settings size={24} className="card-icon" />
                <div>
                  <h2 className="card-title">Job Preferences</h2>
                  <p className="card-subtitle">Configure how AI filters jobs for you</p>
                </div>
              </div>
            </div>
            <div className="settings-content">
              <div className="form-group">
                <label className="form-label">Keywords</label>
                <input
                  type="text"
                  value={preferences.keywords || ''}
                  onChange={(e) => setPreferences({ ...preferences, keywords: e.target.value })}
                  className="form-input"
                  placeholder="e.g., software engineer, developer, programmer"
                />
                <small className="form-help">Keywords or job titles you're interested in</small>
              </div>

              <div className="form-group">
                <label className="form-label">Primary Location</label>
                <input
                  type="text"
                  value={preferences.location || ''}
                  onChange={(e) => setPreferences({ ...preferences, location: e.target.value })}
                  className="form-input"
                  placeholder="e.g., San Francisco, CA or Remote"
                />
                <small className="form-help">Primary location preference</small>
              </div>

              <div className="form-group">
                <label className="form-label">Additional Locations</label>
                <div className="form-input-group">
                  <input
                    type="text"
                    value={newLocation}
                    onChange={(e) => setNewLocation(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && addLocation()}
                    className="form-input"
                    placeholder="Add location"
                  />
                  <Button
                    variant="secondary"
                    size="md"
                    icon={<Plus size={16} />}
                    onClick={addLocation}
                  >
                    Add
                  </Button>
                </div>
                {preferences.locations && preferences.locations.length > 0 && (
                  <div className="skills-list">
                    {preferences.locations.map((loc, index) => (
                      <span key={index} className="skill-tag">
                        {loc}
                        <button
                          type="button"
                          className="skill-remove"
                          onClick={() => removeLocation(loc)}
                        >
                          <X size={14} />
                        </button>
                      </span>
                    ))}
                  </div>
                )}
              </div>

              <div className="form-group">
                <label className="form-label">Work Type</label>
                <select
                  value={preferences.work_type || 'any'}
                  onChange={(e) => setPreferences({ ...preferences, work_type: e.target.value as 'remote' | 'office' | 'hybrid' | 'any' })}
                  className="form-input"
                >
                  <option value="any">Any</option>
                  <option value="remote">Remote Only</option>
                  <option value="office">Office Only</option>
                  <option value="hybrid">Hybrid</option>
                </select>
                <small className="form-help">Preferred work arrangement</small>
              </div>

              <div className="form-group">
                <label className="form-label">Experience Level</label>
                <select
                  value={preferences.experience_level || ''}
                  onChange={(e) => setPreferences({ ...preferences, experience_level: e.target.value })}
                  className="form-input"
                >
                  <option value="">Any</option>
                  <option value="entry">Entry Level</option>
                  <option value="mid">Mid Level</option>
                  <option value="senior">Senior Level</option>
                  <option value="lead">Lead/Principal</option>
                </select>
                <small className="form-help">Preferred experience level</small>
              </div>
            </div>
          </Card>
        </div>

        <div className="profile-save-section">
          <Button
            variant="primary"
            size="md"
            icon={<Save size={16} />}
            onClick={handleSaveProfile}
            loading={profileSaving}
          >
            Save Profile
          </Button>
        </div>
      </div>
    );
  };

  const renderDocumentsTab = () => {
    return (
      <div className="career-hub-tab-content">
        <div className="career-copilot-grid">
          <div className="document-sidebar">
            <div
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
            <Card 
              className={`document-upload ${dragActive ? 'drag-active' : ''}`}
            >
              <div className="card-header">
                <div className="card-header-content">
                  <FileText className="card-icon" size={20} />
                  <div>
                    <h3 className="card-title">Document Library</h3>
                    <p className="card-subtitle">Upload multiple files: resumes, project writeups, and transcripts.</p>
                  </div>
                </div>
              </div>
              <div className="upload-zone">
                <div className="upload-zone-content">
                  <Upload size={24} className="upload-icon" />
                  <p className="upload-text">
                    Drag and drop files here, or <button 
                      type="button"
                      className="upload-link"
                      onClick={() => fileInputRef.current?.click()}
                    >
                      browse to select
                    </button>
                  </p>
                  <p className="upload-hint">You can select multiple files at once (PDF, TXT, MD, CSV)</p>
                </div>
                <input 
                  ref={fileInputRef}
                  type="file" 
                  multiple 
                  onChange={handleUpload} 
                  style={{ display: 'none' }}
                  accept=".pdf,.txt,.md,.csv,application/pdf,text/plain,text/markdown,text/csv"
                />
              </div>
              
              {uploadQueue.length > 0 && (
                <div className="upload-queue">
                  <div className="upload-queue-header">
                    <strong>Uploading {uploadQueue.length} file{uploadQueue.length > 1 ? 's' : ''}...</strong>
                  </div>
                  {uploadQueue.map((item, index) => (
                    <div key={index} className={`upload-item upload-item-${item.status}`}>
                      <div className="upload-item-info">
                        <File size={14} />
                        <span className="upload-item-name">{item.file.name}</span>
                        <span className="upload-item-size">
                          ({(item.file.size / 1024).toFixed(1)} KB)
                        </span>
                      </div>
                      <div className="upload-item-status">
                        {item.status === 'pending' && (
                          <span className="upload-status-text">Pending...</span>
                        )}
                        {item.status === 'uploading' && (
                          <>
                            <Loader size={14} className="spin" />
                            <span className="upload-status-text">Uploading...</span>
                          </>
                        )}
                        {item.status === 'success' && (
                          <>
                            <CheckCircle2 size={14} className="success-icon" />
                            <span className="upload-status-text">Uploaded</span>
                          </>
                        )}
                        {item.status === 'error' && (
                          <>
                            <AlertCircle size={14} className="error-icon" />
                            <span className="upload-status-text error-text">{item.error}</span>
                          </>
                        )}
                        <button
                          type="button"
                          className="upload-remove"
                          onClick={() => removeFromQueue(index)}
                          aria-label="Remove from queue"
                        >
                          <X size={12} />
                        </button>
                      </div>
                      {item.status === 'uploading' && (
                        <div className="upload-progress">
                          <div 
                            className="upload-progress-bar" 
                            style={{ width: `${item.progress || 0}%` }}
                          />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </Card>
            </div>

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
                  <h2>Edit "{selectedDocument.filename}"</h2>
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
                  className="document-editor-textarea"
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
      </div>
    );
  };

  const renderAnalyzeTab = () => {
    return (
      <div className="career-hub-tab-content">
        <Card>
          <div className="section-header">
            <div>
              <h2>Understand what the company really wants</h2>
              <p className="card-subtitle">
                Paste the job details and we'll translate the posting into plain language guidance.
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
              We'll analyze the posting and highlight matched and missing skills.
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

  const renderApplicationsTab = () => {
    if (applicationsLoading) {
      return <div className="loading">Loading applications...</div>;
    }

    return (
      <div className="career-hub-tab-content">
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
                                  Generated {format(parseISO(resume.generated_at), 'MMM d, yyyy')}
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
                                  onClick={() => handleGenerateDocumentsForJob(app.job_id)}
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
                                  Generated {format(parseISO(coverLetter.generated_at), 'MMM d, yyyy')}
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
                                  onClick={() => handleGenerateDocumentsForJob(app.job_id)}
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
                              onClick={() => handleGenerateDocumentsForJob(app.job_id)}
                              loading={generating === app.job_id}
                            >
                              Generate Both Documents
                            </Button>
                          </div>
                        )}
                      </div>

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

                      <div className="action-links">
                        {app.job?.url && (
                          <Button
                            variant="secondary"
                            size="md"
                            icon={<ArrowRight size={16} />}
                            onClick={() => window.open(app.job!.url, '_blank')}
                          >
                            View Job Posting
                          </Button>
                        )}
                        {app.status === 'submitted' && (
                          <>
                            <Button
                              variant="secondary"
                              size="md"
                              icon={<CheckSquare size={16} />}
                              onClick={() => navigate('/tasks')}
                            >
                              View Follow-up Task
                            </Button>
                            <Button
                              variant="secondary"
                              size="md"
                              icon={<Calendar size={16} />}
                              onClick={() => navigate('/follow-ups')}
                            >
                              Manage Follow-ups
                            </Button>
                          </>
                        )}
                      </div>
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

  const tabs = [
    { id: 'profile' as TabId, label: 'Profile', icon: User },
    { id: 'documents' as TabId, label: 'Documents', icon: FolderOpen },
    { id: 'analyze' as TabId, label: 'Analyze', icon: BarChart3 },
    { id: 'applications' as TabId, label: 'Applications', icon: BriefcaseIcon },
  ];

  return (
    <div className="career-hub-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Career Hub</h1>
          <p className="page-subtitle">
            Manage your profile, documents, job analysis, and applications in one unified workspace
          </p>
        </div>
        <div className="ai-badge">
          <Sparkles size={20} />
          <span>AI-Powered</span>
        </div>
      </div>

      <div className="tab-navigation">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              className={`tab-button ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              <Icon size={18} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      <div className="tab-content-wrapper">
        {activeTab === 'profile' && renderProfileTab()}
        {activeTab === 'documents' && renderDocumentsTab()}
        {activeTab === 'analyze' && renderAnalyzeTab()}
        {activeTab === 'applications' && renderApplicationsTab()}
      </div>
    </div>
  );
};

export default CareerHub;

