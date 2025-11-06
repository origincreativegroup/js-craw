export interface Job {
  id: number;
  title: string;
  company: string;
  location: string;
  platform: string;
  url: string;
  status: string;
  is_new: boolean;
  description?: string;
  ai_match_score?: number;
  ai_summary?: string;
  ai_pros?: string[];
  ai_cons?: string[];
  ai_keywords_matched?: string[];
  ai_recommended?: boolean;
  posted_date?: string;
  discovered_at: string;
  notes?: string;
  application?: Application;
  generated_documents?: GeneratedDocument[];
  pipeline_stage?: string;
  ai_content?: {
    summary?: string;
    pros?: string[];
    cons?: string[];
    keywords_matched?: string[];
    match_score?: number;
    recommended?: boolean;
  };
}

export interface SuggestedStep {
  id: string;
  label: string;
  task_type: string; // apply, research, network, prepare_interview, follow_up
  title: string;
  notes?: string;
  suggested_due_date?: string;
}

export interface AnalyzeJobResponse {
  job_id: number;
  analysis: any;
  suggested_next_steps: SuggestedStep[];
}

export interface Task {
  id: number;
  job_id: number;
  task_type: string;
  title: string;
  priority: string;
  status: string;
  due_date?: string;
  snooze_until?: string;
  snooze_count: number;
  notes?: string;
  recommended_by?: string;
  ai_insights?: any;
  created_at: string;
  completed_at?: string;
  job?: Job;
}

export interface FollowUp {
  id: number;
  job_id: number;
  follow_up_date: string;
  action_type: string;
  notes?: string;
  completed: boolean;
}

export interface FollowUpRecommendation {
  type: string;
  priority: string;
  job_id: number;
  job_title: string;
  company: string;
  location: string;
  suggested_action: string;
  ai_match_score?: number;
  follow_up_date?: string;
  action_type?: string;
  notes?: string;
  followup_id?: number;
  applied_at?: string;
  discovered_at?: string;
}

export interface Company {
  id: number;
  name: string;
  career_page_url: string;
  crawler_type: string;
  is_active: boolean;
  last_crawled_at?: string;
  jobs_found_total: number;
  consecutive_empty_crawls: number;
  viability_score?: number;
  priority_score?: number;
}

export interface PendingCompany {
  id: number;
  name: string;
  career_page_url: string;
  discovery_source: string;
  confidence_score: number;
  crawler_type: string;
  crawler_config?: any;
  discovery_metadata?: any;
  created_at: string;
  updated_at: string;
}

export interface DiscoveryStatus {
  total_companies: number;
  active_companies: number;
  target_companies: number;
  pending_count: number;
  discovery_enabled: boolean;
  discovery_interval_hours: number;
  auto_approve_threshold: number;
  recent_pending: PendingCompany[];
}

export interface SearchCriteria {
  id: number;
  name: string;
  keywords: string;
  location?: string;
  remote_only: boolean;
  job_type?: string;
  experience_level?: string;
  is_active: boolean;
  target_companies?: number[];
}

export interface Stats {
  total_jobs: number;
  new_jobs_24h: number;
  jobs_by_status: Record<string, number>;
  active_searches: number;
}

export interface CrawlStatus {
  is_running: boolean;
  running_count: number;
  queue_length: number;
  current_company?: string;
  progress: {
    current: number;
    total: number;
  };
  eta_seconds?: number;
  run_type?: string;
  recent_logs: CrawlLog[];
  active_companies: number;
  crawler_health: Record<string, CrawlerHealth>;
}

export interface CrawlLog {
  id: number;
  company_id?: number;
  company_name?: string;
  crawler_type?: string;
  crawler_class?: string;
  status: string;
  started_at: string;
  completed_at?: string;
  jobs_found: number;
  new_jobs: number;
  error_message?: string;
  duration_seconds?: number;
}

export interface CrawlerHealth {
  success_rate: number;
  avg_duration_seconds: number;
  error_count: number;
  total_runs: number;
}

export interface TaskRecommendation {
  job_id: number;
  job_title: string;
  company: string;
  match_score: number;
  recommended_action: string;
  priority: string;
  reason: string;
}

export interface Application {
  id: number;
  job_id: number;
  status: string;  // queued, drafting, submitted, interviewing, rejected, accepted
  application_date?: string;
  portal_url?: string;
  confirmation_number?: string;
  resume_version_id?: number;
  cover_letter_id?: number;
  notes?: string;
  created_at: string;
  updated_at: string;
  job?: Job;
}

export interface GeneratedDocument {
  id: number;
  job_id: number;
  document_type: string;  // "resume" or "cover_letter"
  content: string;
  generated_at: string;
  file_path?: string;
  job?: Job;
}

export interface SearchRecipe {
  name: string;
  description: string;
  keywords: string;
  location?: string | null;
  remote_only: boolean;
  job_type?: string | null;
  experience_level?: string | null;
  icon: string;
}

export interface JobAction {
  action: string;  // queue_application, mark_priority, mark_favorite
  metadata?: Record<string, any>;
}

export interface UserProfilePreferences {
  keywords?: string;
  location?: string;
  locations?: string[];
  remote_preferred?: boolean;
  work_type?: 'remote' | 'office' | 'hybrid' | 'any';
  experience_level?: string;
}

export interface UserProfile {
  id: number | null;
  user_id: number | null;
  base_resume: string | null;
  skills: string[];
  experience: Array<{
    company?: string;
    role?: string;
    start_date?: string;
    end_date?: string;
    description?: string;
    [key: string]: any;
  }>;
  education: {
    degree?: string;
    field?: string;
    institution?: string;
    graduation_date?: string;
    [key: string]: any;
  } | null;
  preferences: UserProfilePreferences;
  created_at: string | null;
  updated_at: string | null;
}

export interface UserDocument {
  id: number;
  filename: string;
  file_type: string;
  content: string;
  metadata?: Record<string, any> | null;
  created_at: string;
  updated_at?: string | null;
}

export interface JobFitAnalysis {
  summary: string;
  company_focus?: string | null;
  key_requirements: string[];
  skill_alignment: {
    overall_fit: string;
    matched_skills: string[];
    missing_skills: string[];
    upskill_suggestions: string[];
  };
  tailoring_tips: string[];
  interview_prep: string[];
}

export interface JobFitResponse {
  analysis: JobFitAnalysis;
  documents_used: number[];
}

export interface TailoredDocumentsResponse {
  documents: Record<string, string | null | undefined>;
  used_documents: number[];
}

export interface JobFitPayload {
  job_title?: string;
  company?: string;
  job_description: string;
  requirements?: string;
  user_summary?: string;
  user_skills?: string[];
  user_experience?: string;
  supporting_document_ids?: number[];
}

export interface TailoredDocumentsPayload {
  job_title: string;
  company: string;
  job_description: string;
  requirements?: string;
  user_summary?: string;
  user_skills?: string[];
  document_ids?: number[];
  document_types?: string[];
}

export interface UserProfileUpdate {
  base_resume?: string;
  skills?: string[];
  experience?: Array<{
    company?: string;
    role?: string;
    start_date?: string;
    end_date?: string;
    description?: string;
    [key: string]: any;
  }>;
  education?: {
    degree?: string;
    field?: string;
    institution?: string;
    graduation_date?: string;
    [key: string]: any;
  };
  preferences?: UserProfilePreferences;
}

// Unified automation and companies types
export interface UnifiedCompany extends Company {
  last_crawl_at?: string;
  automation: {
    total_crawls_30d: number;
    successful_crawls_30d: number;
    success_rate?: number;
    health_status: 'healthy' | 'warning' | 'critical' | 'inactive' | 'unknown';
    needs_attention: boolean;
  };
}

export interface UnifiedStatus {
  automation: {
    scheduler: {
      status: string;
      next_run?: string;
      interval_minutes?: number;
      is_paused: boolean;
      job_id?: string;
      job_name?: string;
      error?: string;
    };
    crawler: {
      is_running: boolean;
      running_count: number;
      queue_length: number;
      current_company?: string;
      progress: {
        current: number;
        total: number;
      };
      eta_seconds?: number;
      run_type?: string;
      recent_logs: CrawlLog[];
      crawler_health: Record<string, CrawlerHealth>;
      error?: string;
    };
    discovery: DiscoveryStatus & {
      error?: string;
    };
  };
  companies: {
    total_companies: number;
    active_companies: number;
    inactive_companies: number;
    needs_attention: number;
    unchecked_viability: number;
    average_viability_score?: number;
    error?: string;
  };
  recent_activity: {
    recent_crawls: Array<{
      id: number;
      company_id?: number;
      status: string;
      started_at?: string;
      jobs_found: number;
      new_jobs: number;
    }>;
    recent_discoveries: Array<{
      id: number;
      name: string;
      discovery_source: string;
      confidence_score: number;
      created_at: string;
    }>;
    error?: string;
  };
  metrics: {
    crawl_success_rate_30d?: number;
    total_crawls_30d: number;
    successful_crawls_30d: number;
    average_crawl_duration_seconds?: number;
    error?: string;
  };
  timestamp: string;
}

