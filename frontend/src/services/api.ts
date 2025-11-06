import axios from 'axios';
import type {
  Job,
  Task,
  FollowUp,
  FollowUpRecommendation,
  Company,
  SearchCriteria,
  Stats,
  CrawlStatus,
  TaskRecommendation,
  Application,
  GeneratedDocument,
  SearchRecipe,
  UserProfile,
  UserProfileUpdate,
  PendingCompany,
  DiscoveryStatus,
  AnalyzeJobResponse,
  UserDocument,
  JobFitResponse,
  JobFitPayload,
  TailoredDocumentsPayload,
  TailoredDocumentsResponse,
} from '../types';

const API_BASE = '/api';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add error interceptor to match original fetch() error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Extract error message from axios error response
    if (error.response) {
      const errorData = error.response.data;
      const errorMessage = errorData?.detail || errorData?.message || `Request failed with status ${error.response.status}`;
      const enhancedError = new Error(errorMessage);
      (enhancedError as any).response = error.response;
      return Promise.reject(enhancedError);
    }
    return Promise.reject(error);
  }
);

// Jobs
export const getJobs = async (params?: {
  status?: string;
  search_id?: number;
  new_only?: boolean;
  match?: string;  // 'high', 'medium', 'low'
  ready_to_apply?: boolean;
  sort?: string;  // 'discovered_at', 'ai_match_score', 'posted_date'
  limit?: number;
}): Promise<Job[]> => {
  const response = await api.get('/jobs', { params });
  return response.data;
};

export const getJob = async (id: number): Promise<Job> => {
  const response = await api.get(`/jobs/${id}`);
  return response.data;
};

export const updateJob = async (id: number, data: { status?: string; notes?: string }): Promise<void> => {
  await api.patch(`/jobs/${id}`, data);
};

export const analyzeJob = async (id: number): Promise<AnalyzeJobResponse> => {
  const response = await api.post(`/jobs/${id}/analyze`);
  return response.data as AnalyzeJobResponse;
};

// Tasks
export const getTasks = async (params?: {
  status?: string;
  priority?: string;
  task_type?: string;
  job_id?: number;
  include_snoozed?: boolean;
  limit?: number;
}): Promise<Task[]> => {
  const response = await api.get('/tasks', { params });
  return response.data;
};

export const getTask = async (id: number): Promise<Task> => {
  const response = await api.get(`/tasks/${id}`);
  return response.data;
};

export const createTask = async (data: {
  job_id: number;
  task_type: string;
  title: string;
  due_date?: string;
  priority?: string;
  notes?: string;
}): Promise<Task> => {
  const response = await api.post('/tasks', data);
  return response.data.task;
};

export const updateTask = async (id: number, data: {
  status?: string;
  priority?: string;
  due_date?: string;
  title?: string;
  notes?: string;
}): Promise<void> => {
  await api.patch(`/tasks/${id}`, data);
};

export const completeTask = async (id: number): Promise<void> => {
  await api.post(`/tasks/${id}/complete`);
};

export const snoozeTask = async (id: number, duration: string = '1d'): Promise<void> => {
  await api.post(`/tasks/${id}/snooze`, { duration });
};

export const getTaskRecommendations = async (limit: number = 10): Promise<TaskRecommendation[]> => {
  const response = await api.get('/tasks/recommendations', { params: { limit } });
  return response.data;
};

export const generateTasksFromJob = async (jobId: number, forceRegenerate: boolean = false): Promise<Task[]> => {
  const response = await api.post(`/tasks/generate-from-job/${jobId}`, null, {
    params: { force_regenerate: forceRegenerate },
  });
  return response.data.tasks;
};

// Follow-ups
export const getFollowUps = async (upcomingOnly: boolean = true): Promise<FollowUp[]> => {
  const response = await api.get('/followups', { params: { upcoming_only: upcomingOnly } });
  return response.data;
};

export const getFollowUpRecommendations = async (): Promise<FollowUpRecommendation[]> => {
  const response = await api.get('/followups/recommendations');
  return response.data;
};

export const createFollowUp = async (data: {
  job_id: number;
  follow_up_date: string;
  action_type: string;
  notes?: string;
}): Promise<FollowUp> => {
  const response = await api.post('/followups', data);
  return response.data;
};

// Companies
export const getCompanies = async (activeOnly: boolean = false): Promise<Company[]> => {
  const response = await api.get('/companies', { params: { active_only: activeOnly } });
  return response.data;
};

// Company Discovery
export const getDiscoveryStatus = async (): Promise<DiscoveryStatus> => {
  const response = await api.get('/companies/discovery/status');
  return response.data;
};

export const runDiscovery = async (keywords?: string, maxCompanies?: number): Promise<any> => {
  const response = await api.post('/companies/discover/run', null, {
    params: { keywords, max_companies: maxCompanies },
  });
  return response.data;
};

export const getPendingCompanies = async (limit?: number): Promise<PendingCompany[]> => {
  const response = await api.get('/companies/pending', { params: { limit } });
  return response.data;
};

export const approvePendingCompany = async (pendingId: number): Promise<any> => {
  const response = await api.post(`/companies/pending/${pendingId}/approve`);
  return response.data;
};

export const rejectPendingCompany = async (pendingId: number): Promise<any> => {
  const response = await api.post(`/companies/pending/${pendingId}/reject`);
  return response.data;
};

// Stats
export const getStats = async (): Promise<Stats> => {
  const response = await api.get('/stats');
  return response.data;
};

// Crawl status
export const getCrawlStatus = async (): Promise<CrawlStatus> => {
  const response = await api.get('/crawl/status');
  return response.data;
};

export const triggerCrawl = async (crawlType: 'searches' | 'all' = 'all'): Promise<void> => {
  await api.post('/crawl/run', null, { params: { crawl_type: crawlType } });
};

export const cancelCrawl = async (): Promise<void> => {
  await api.post('/crawl/cancel');
};

export const updateSchedulerInterval = async (intervalMinutes: number): Promise<void> => {
  await api.patch('/automation/scheduler', { interval_minutes: intervalMinutes });
};

export const updateDiscoveryInterval = async (intervalHours: number): Promise<void> => {
  await api.patch('/automation/discovery-interval', { interval_hours: intervalHours });
};

export const getSchedulerStatus = async (): Promise<{
  status: string;
  next_run?: string;
  interval_minutes: number;
  is_paused: boolean;
}> => {
  const response = await api.get('/automation/scheduler');
  return response.data;
};

export const pauseScheduler = async (): Promise<void> => {
  await api.post('/automation/pause');
};

export const resumeScheduler = async (): Promise<void> => {
  await api.post('/automation/resume');
};

// Searches
export const getSearches = async (): Promise<SearchCriteria[]> => {
  const response = await api.get('/searches');
  return response.data;
};

// AI Chat
export const sendChatMessage = async (message: string, jobId?: number, context?: any): Promise<{ response: string; model?: string; error?: boolean }> => {
  const response = await api.post('/ai/chat', {
    message,
    job_id: jobId,
    context,
  });
  return response.data;
};

export const uploadUserDocuments = async (files: FileList | File[]): Promise<UserDocument[]> => {
  const formData = new FormData();
  const list: File[] = Array.isArray(files) ? files : Array.from(files as FileList);
  list.forEach((file) => formData.append('files', file));

  const response = await api.post('/user-documents/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

  return response.data.documents as UserDocument[];
};

export const fetchUserDocuments = async (): Promise<UserDocument[]> => {
  const response = await api.get('/user-documents');
  return response.data as UserDocument[];
};

export const updateUserDocumentContent = async (
  id: number,
  data: { content?: string; metadata?: Record<string, any> }
): Promise<UserDocument> => {
  const response = await api.patch(`/user-documents/${id}`, data);
  return response.data as UserDocument;
};

export const deleteUserDocument = async (id: number): Promise<void> => {
  await api.delete(`/user-documents/${id}`);
};

export const analyzeJobFit = async (payload: JobFitPayload): Promise<JobFitResponse> => {
  const response = await api.post('/ai/job-fit', payload);
  return response.data as JobFitResponse;
};

export const generateTailoredDocuments = async (
  payload: TailoredDocumentsPayload
): Promise<TailoredDocumentsResponse> => {
  const response = await api.post('/ai/tailored-documents', payload);
  return response.data as TailoredDocumentsResponse;
};

// OpenWebUI
export const getOpenWebUIInfo = async (): Promise<any> => {
  const response = await api.get('/openwebui');
  return response.data;
};

export const getOpenWebUIHealth = async (): Promise<any> => {
  const response = await api.get('/openwebui/health');
  return response.data;
};

export const getOpenWebUIStatus = async (): Promise<any> => {
  const response = await api.get('/openwebui/status');
  return response.data;
};

export const verifyOpenWebUIAuth = async (apiKey?: string, authToken?: string): Promise<any> => {
  const response = await api.post('/openwebui/verify-auth', {
    api_key: apiKey,
    auth_token: authToken,
  });
  return response.data;
};

// Settings
export const getSettings = async (): Promise<any> => {
  const response = await api.get('/settings');
  return response.data;
};

export const updateSettings = async (settings: any): Promise<any> => {
  const response = await api.patch('/settings', settings);
  return response.data;
};

export const getFullContext = async (limitPerType: number = 50, daysBack: number = 30): Promise<any> => {
  const response = await api.get('/openwebui/context/full', {
    params: {
      limit_per_type: limitPerType,
      days_back: daysBack,
    },
  });
  return response.data;
};

export const sendFullContextToOpenWebUI = async (limitPerType: number = 50, daysBack: number = 30): Promise<any> => {
  // Get full context first
  const context = await getFullContext(limitPerType, daysBack);
  
  // Send to OpenWebUI
  const response = await api.post('/openwebui/send-context', {
    full_context: context,
    prompt_type: 'full_analysis',
  });
  return response.data;
};

export const sendJobToOpenWebUI = async (jobId: number, promptType: 'analyze' | 'follow_up' | 'interview_prep' | 'cover_letter' = 'analyze'): Promise<any> => {
  const response = await api.post('/openwebui/send-context', {
    job_id: jobId,
    prompt_type: promptType,
  });
  return response.data;
};

// Application endpoints
export const createApplication = async (jobId: number, data: {
  status?: string;
  application_date?: string;
  portal_url?: string;
  confirmation_number?: string;
  resume_version_id?: number;
  cover_letter_id?: number;
  notes?: string;
}): Promise<Application> => {
  const response = await api.post(`/jobs/${jobId}/applications`, { job_id: jobId, ...data });
  return response.data.application;
};

export const getApplications = async (params?: {
  status?: string;
  job_id?: number;
  limit?: number;
}): Promise<Application[]> => {
  const response = await api.get('/applications', { params });
  return response.data;
};

export const getApplication = async (id: number): Promise<Application> => {
  const response = await api.get(`/applications/${id}`);
  return response.data;
};

export const updateApplication = async (id: number, data: {
  status?: string;
  application_date?: string;
  portal_url?: string;
  confirmation_number?: string;
  resume_version_id?: number;
  cover_letter_id?: number;
  notes?: string;
}): Promise<void> => {
  await api.patch(`/applications/${id}`, data);
};

export const deleteApplication = async (id: number): Promise<void> => {
  await api.delete(`/applications/${id}`);
};

// Job actions
export const queueJobForApplication = async (jobId: number): Promise<any> => {
  const response = await api.post(`/jobs/${jobId}/actions`, { action: 'queue_application' });
  return response.data;
};

export const markJobHighPriority = async (jobId: number): Promise<any> => {
  const response = await api.post(`/jobs/${jobId}/actions`, { action: 'mark_priority' });
  return response.data;
};

// Document generation endpoints
export const generateDocuments = async (jobId: number, documentTypes: string[] = ['resume', 'cover_letter']): Promise<any> => {
  const response = await api.post(`/jobs/${jobId}/generate-documents`, {
    document_types: documentTypes,
  });
  return response.data;
};

export const getDocuments = async (jobId: number): Promise<GeneratedDocument[]> => {
  const response = await api.get(`/jobs/${jobId}/documents`);
  return response.data;
};

export const getDocument = async (documentId: number): Promise<GeneratedDocument> => {
  const response = await api.get(`/documents/${documentId}`);
  return response.data;
};

export const updateDocument = async (documentId: number, content: string): Promise<void> => {
  await api.patch(`/documents/${documentId}`, { content });
};

export const finalizeDocument = async (documentId: number): Promise<any> => {
  const response = await api.post(`/documents/${documentId}/finalize`);
  return response.data;
};

// Search recipes
export const getSearchRecipes = async (): Promise<{ recipes: SearchRecipe[] }> => {
  const response = await api.get('/automation/search-recipes');
  return response.data;
};

export const createSearchFromRecipe = async (recipe: SearchRecipe, name?: string): Promise<any> => {
  const response = await api.post('/searches', {
    name: name || recipe.name,
    keywords: recipe.keywords,
    location: recipe.location || undefined,
    remote_only: recipe.remote_only,
    job_type: recipe.job_type || undefined,
    experience_level: recipe.experience_level || undefined,
  });
  return response.data;
};

// Task notification
export const toggleTaskNotification = async (taskId: number, enabled: boolean): Promise<any> => {
  const response = await api.post(`/tasks/${taskId}/notify`, null, {
    params: { enabled },
  });
  return response.data;
};

// User Profile endpoints
export const getUserProfile = async (): Promise<UserProfile> => {
  const response = await api.get('/user-profile');
  return response.data;
};

export const createUserProfile = async (data: UserProfileUpdate): Promise<UserProfile> => {
  const response = await api.post('/user-profile', data);
  return response.data;
};

export const updateUserProfile = async (data: UserProfileUpdate): Promise<UserProfile> => {
  const response = await api.patch('/user-profile', data);
  return response.data;
};

export default api;

