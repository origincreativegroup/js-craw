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

