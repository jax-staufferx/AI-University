// API types — match the backend Pydantic schemas exactly

export type FormatTier = 'quick_dive' | 'deep_dive' | 'short_course' | 'full_course';
export type TopicStatus = 'planning' | 'active' | 'completed';
export type ModuleStatus = 'pending' | 'researched' | 'in_progress' | 'completed';
export type ContentType = 'skill' | 'conceptual' | 'mixed';
export type LearningMethod =
  | 'teach_it_back' | 'sparring' | 'ship_it' | 'analogy_builder'
  | 'error_hunt' | 'eli5' | 'scenario_application' | 'rapid_recall';
export type ProposalStatus = 'pending' | 'approved' | 'rejected';

export interface TopicListItem {
  id: number;
  title: string;
  format_tier: FormatTier;
  status: TopicStatus;
  created_at: string;
  completed_at: string | null;
}

export interface ModuleSummary {
  id: number;
  order_index: number;
  title: string;
  one_liner: string | null;
  status: ModuleStatus;
}

export interface TopicDetail {
  id: number;
  title: string;
  format_tier: FormatTier;
  status: TopicStatus;
  created_at: string;
  completed_at: string | null;
  digest_path: string | null;
  outline_approved: boolean;
  current_module_id: number | null;
  modules: ModuleSummary[];
  budget_used: number;
  budget_soft_cap: number;
  budget_cap_hit: boolean;
}

export interface OutlineModule {
  order_index: number;
  title: string;
  one_liner: string | null;
  content_type: ContentType;
}

export interface OutlineResponse {
  modules: OutlineModule[];
  approved: boolean;
}

export interface SessionSummary {
  id: number;
  module_id: number;
  method_used: LearningMethod;
  started_at: string;
  completed_at: string | null;
  score: number | null;
}

export interface ModuleDetail {
  id: number;
  topic_id: number;
  order_index: number;
  title: string;
  one_liner: string | null;
  content_type: ContentType;
  status: ModuleStatus;
  digest_path: string | null;
  digest_markdown: string | null;
  sessions: SessionSummary[];
}

export interface SessionMessage {
  role: 'agent' | 'user';
  content: string;
  created_at: string;
}

export interface SessionDetail {
  id: number;
  module_id: number;
  method_used: LearningMethod;
  started_at: string;
  completed_at: string | null;
  score: number | null;
  outcome_summary: string | null;
  messages: SessionMessage[];
}

export interface ExecutionResult {
  stdout: string;
  stderr: string;
  return_code: number | null;
  timed_out: boolean;
  network_sandboxed: boolean;
}

export interface SessionSubmitResult {
  session_id: number;
  completed: boolean;
  feedback: string;
  score: number | null;
  next_prompt: string | null;
  execution: ExecutionResult | null;
}

export interface MonitorProposal {
  id: number;
  created_at: string;
  content_type: ContentType;
  method: LearningMethod;
  current_weight: number;
  proposed_weight: number;
  rationale: string;
  status: ProposalStatus;
}

export interface TopicConnection {
  topic_id: number;
  topic_title: string | null;
  connection_note: string;
}

export interface BudgetError {
  message: string;
  topic_id: number;
  call_count: number;
  soft_cap: number;
  continue_endpoint: string;
}
