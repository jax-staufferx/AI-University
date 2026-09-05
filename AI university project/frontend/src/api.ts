import type {
  MonitorProposal, ModuleDetail, OutlineResponse, SessionDetail,
  SessionSubmitResult, TopicConnection, TopicDetail, TopicListItem,
  BudgetError, Quiz, QuizAnswer, QuizSubmitResult, Slideshow,
} from './types';

const BASE = '/api';

export interface AuthStatus {
  authenticated: boolean;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    if (res.status === 402 && body.detail) {
      const err = new Error('BUDGET_EXCEEDED') as Error & { budgetError: BudgetError };
      err.budgetError = body.detail as BudgetError;
      throw err;
    }
    const message = body.detail
      ? typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
      : `Request failed (${res.status})`;
    throw new Error(message);
  }

  if (res.status === 204) {
    return undefined as T;
  }
  return res.json();
}

// Auth
export const authStatus = () => request<AuthStatus>('/auth/status');
export const authLogin = (password: string) =>
  request<AuthStatus>('/auth/login', { method: 'POST', body: JSON.stringify({ password }) });
export const authLogout = () => request<AuthStatus>('/auth/logout', { method: 'POST' });

// Topics
export const listTopics = () => request<TopicListItem[]>('/topics');
export const getTopic = (id: number) => request<TopicDetail>(`/topics/${id}`);
export const createTopic = (title: string, format_tier: string, depth: string, learner_context?: string) =>
  request<TopicDetail>('/topics', {
    method: 'POST',
    body: JSON.stringify({ title, format_tier, depth, learner_context: learner_context ?? null }),
  });
export const getIntakeQuestions = (title: string, format_tier: string) =>
  request<{ questions: string[] }>('/topics/intake-questions', {
    method: 'POST',
    body: JSON.stringify({ title, format_tier }),
  }).then((r) => r.questions);
export const getOutline = (id: number) => request<OutlineResponse>(`/topics/${id}/outline`);
export const approveOutline = (id: number, modules?: unknown[]) =>
  request<TopicDetail>(`/topics/${id}/outline/approve`, {
    method: 'POST',
    body: JSON.stringify(modules ? { modules } : {}),
  });
export const continueBudget = (id: number) =>
  request<TopicDetail>(`/topics/${id}/budget/continue`, {
    method: 'POST',
    body: JSON.stringify({ continue_anyway: true }),
  });
export const getConnections = (id: number) =>
  request<TopicConnection[]>(`/topics/${id}/connections`);
export const deleteTopic = (id: number) =>
  request<void>(`/topics/${id}`, { method: 'DELETE' });

// Modules
export const getModule = (topicId: number, moduleId: number) =>
  request<ModuleDetail>(`/topics/${topicId}/modules/${moduleId}`);
export const deleteModule = (topicId: number, moduleId: number) =>
  request<void>(`/topics/${topicId}/modules/${moduleId}`, { method: 'DELETE' });

// Diagnostic quiz + adaptive slideshow
export const getQuiz = (topicId: number, moduleId: number) =>
  request<Quiz>(`/topics/${topicId}/modules/${moduleId}/quiz`);
export const submitQuiz = (topicId: number, moduleId: number, answers: QuizAnswer[]) =>
  request<QuizSubmitResult>(`/topics/${topicId}/modules/${moduleId}/quiz/submit`, {
    method: 'POST',
    body: JSON.stringify({ answers }),
  });
export const getSlideshow = (topicId: number, moduleId: number) =>
  request<Slideshow>(`/topics/${topicId}/modules/${moduleId}/slideshow`);
export const getQuizResult = (topicId: number, moduleId: number) =>
  request<QuizSubmitResult>(`/topics/${topicId}/modules/${moduleId}/quiz/result`);

// Sessions
export const startSession = (module_id: number, method?: string) =>
  request<SessionDetail>('/sessions', {
    method: 'POST',
    body: JSON.stringify(method ? { module_id, method } : { module_id }),
  });
export const getSession = (id: number) => request<SessionDetail>(`/sessions/${id}`);
export const submitResponse = (id: number, response: string) =>
  request<SessionSubmitResult>(`/sessions/${id}/submit`, {
    method: 'POST',
    body: JSON.stringify({ response }),
  });

// Monitor
export const listProposals = () => request<MonitorProposal[]>('/monitor/proposals');
export const respondProposal = (id: number, approve: boolean) =>
  request<MonitorProposal>(`/monitor/proposals/${id}/respond`, {
    method: 'POST',
    body: JSON.stringify({ approve }),
  });
