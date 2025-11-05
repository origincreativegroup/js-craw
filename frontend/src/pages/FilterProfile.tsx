import { useEffect, useState } from 'react';
import { 
  Save, 
  Plus, 
  X, 
  FileText,
  Briefcase,
  GraduationCap,
  Settings,
  CheckCircle,
  AlertCircle
} from 'lucide-react';
import Card from '../components/Card';
import Button from '../components/Button';
import { 
  getUserProfile, 
  updateUserProfile 
} from '../services/api';
import type { UserProfile, UserProfileUpdate } from '../types';
import './FilterProfile.css';

const FilterProfile = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);
  
  // Form state
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

  useEffect(() => {
    loadProfile();
  }, []);

  const loadProfile = async () => {
    try {
      setLoading(true);
      const data = await getUserProfile();
      
      // Populate form state
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
    } catch (error) {
      console.error('Error loading profile:', error);
      setSaveMessage({ type: 'error', text: 'Failed to load profile' });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
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
      
      // Reload to get updated data
      await loadProfile();
      
      // Clear message after 3 seconds
      setTimeout(() => setSaveMessage(null), 3000);
    } catch (error) {
      console.error('Error saving profile:', error);
      setSaveMessage({ type: 'error', text: 'Failed to save profile' });
    } finally {
      setSaving(false);
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

  if (loading) {
    return <div className="loading">Loading profile...</div>;
  }

  return (
    <div className="filter-profile-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Filter Profile</h1>
          <p className="page-subtitle">Configure your profile for AI-powered job filtering</p>
        </div>
        <Button
          variant="primary"
          size="md"
          icon={<Save size={16} />}
          onClick={handleSave}
          loading={saving}
        >
          Save Profile
        </Button>
      </div>

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
        {/* Resume Section */}
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
                placeholder="Paste your resume content here in markdown format. You can paste multiple resumes separated by headers..."
                rows={15}
              />
              <small className="form-help">
                This content will be used by AI to match jobs to your background. Include multiple resume versions if needed.
              </small>
            </div>
          </div>
        </Card>

        {/* Skills Section */}
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

        {/* Experience Section */}
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

        {/* Education Section */}
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

        {/* Preferences Section */}
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
    </div>
  );
};

export default FilterProfile;

