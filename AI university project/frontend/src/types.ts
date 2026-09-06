// API types — match the backend Pydantic schemas exactly

export type FormatTier = 'quick_dive' | 'deep_dive' | 'short_course' | 'full_course';
export type ContentDepth = 'beginner' | 'intermediate' | 'advanced';
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
  depth: ContentDepth;
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
  unlocked: boolean;
  has_quiz: boolean;
  quiz_passed: boolean;
  quiz_score: number | null;
  sessions_count: number;
  best_session_score: number | null;
}

export interface TopicDetail {
  id: number;
  title: string;
  format_tier: FormatTier;
  depth: ContentDepth;
  status: TopicStatus;
  created_at: string;
  completed_at: string | null;
  digest_path: string | null;
  outline_approved: boolean;
  current_module_id: number | null;
  modules: ModuleSummary[];
  modules_total: number;
  modules_researched: number;
  research_in_progress: boolean;
  research_error: string | null;
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
  unlocked: boolean;
  digest_path: string | null;
  digest_markdown: string | null;
  quiz_passed: boolean;
  has_quiz: boolean;
  has_slideshow: boolean;
  sessions: SessionSummary[];
}

// ---------------------------------------------------------------------------
// Diagnostic quiz + adaptive slideshow
// ---------------------------------------------------------------------------

export type QuizQuestionType = 'multiple_choice' | 'short_answer';

export interface QuizQuestion {
  id: string;
  type: QuizQuestionType;
  concept: string;
  difficulty: number;
  question: string;
  options: string[] | null;
}

export interface Quiz {
  module_id: number;
  threshold: number;
  passed_before: boolean;
  questions: QuizQuestion[];
}

export interface QuizAnswer {
  question_id: string;
  response: string;
}

export interface QuizQuestionResult {
  question_id: string;
  concept: string;
  difficulty: number;
  correct: boolean;
  credit: number;
  user_answer: string;
  correct_answer: string;
  explanation: string;
}

export interface QuizSubmitResult {
  module_id: number;
  passed: boolean;
  weighted_score: number;
  threshold: number;
  results: QuizQuestionResult[];
  slideshow_ready: boolean;
}

export interface QuizOverrideResult {
  module_id: number;
  passed: boolean;
  slideshow_ready: boolean;
}

export interface SlideshowSlide {
  concept: string;
  difficulty: number;
  emphasis: 'light' | 'moderate' | 'heavy';
  content: string;
  examples: string[];
}

export interface Slideshow {
  module_id: number;
  slides: SlideshowSlide[];
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
