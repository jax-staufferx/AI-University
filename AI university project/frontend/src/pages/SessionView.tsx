import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { getSession, submitResponse } from '../api';
import type { ExecutionResult, SessionDetail, SessionMessage } from '../types';
import { METHOD_INFO } from '../constants';
import MarkdownRenderer from '../components/MarkdownRenderer';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';

const GRADING_MESSAGES = [
  'Reviewing your answer...',
  'Comparing against the research...',
  'Writing feedback...',
];

export default function SessionView() {
  const { topicId, moduleId, sessionId } = useParams<{ topicId: string; moduleId: string; sessionId: string }>();
  const tid = Number(topicId);
  const mid = Number(moduleId);
  const sid = Number(sessionId);
  const navigate = useNavigate();

  const [session, setSession] = useState<SessionDetail | null>(null);
  const [messages, setMessages] = useState<SessionMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [score, setScore] = useState<number | null>(null);
  const [completed, setCompleted] = useState(false);
  const [round, setRound] = useState(1);
  const [execution, setExecution] = useState<ExecutionResult | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const load = () => {
    setLoading(true);
    setError(false);
    getSession(sid)
      .then((s) => {
        setSession(s);
        setMessages(s.messages);
        if (s.completed_at !== null) {
          setCompleted(true);
          setScore(s.score);
          if (s.outcome_summary) setFeedback(s.outcome_summary);
        }
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  };

  useEffect(load, [sid]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, submitting, feedback]);

  const handleSubmit = async () => {
    if (!input.trim() || submitting || completed) return;
    const response = input.trim();
    setInput('');
    setSubmitting(true);

    setMessages((prev) => [...prev, { role: 'user', content: response, created_at: new Date().toISOString() }]);

    try {
      const result = await submitResponse(sid, response);
      if (result.completed) {
        setFeedback(result.feedback);
        setScore(result.score);
        setCompleted(true);
        if (result.execution) setExecution(result.execution);
      } else if (result.next_prompt) {
        setMessages((prev) => [...prev, { role: 'agent', content: result.next_prompt!, created_at: new Date().toISOString() }]);
        setRound((r) => r + 1);
      }
    } catch {
      setError(true);
      setMessages((prev) => prev.filter((m) => m.content !== response || m.role !== 'user'));
      setInput(response);
    } finally {
      setSubmitting(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Tab') {
      if (isCodeInput) {
        e.preventDefault();
        const ta = e.currentTarget;
        const start = ta.selectionStart;
        const end = ta.selectionEnd;
        const newValue = input.substring(0, start) + '  ' + input.substring(end);
        setInput(newValue);
        requestAnimationFrame(() => {
          ta.selectionStart = ta.selectionEnd = start + 2;
        });
      }
    }
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSubmit();
    }
  };

  if (loading) {
    return <LoadingState messages={['Loading session...']} ariaLabel="Loading session" />;
  }

  if (error || !session) {
    return <ErrorState onRetry={load} />;
  }

  const methodInfo = METHOD_INFO[session.method_used];
  const isCodeInput = session.method_used === 'ship_it';
  const moduleUrl = '/topics/' + tid + '/modules/' + mid;
  const topicUrl = '/topics/' + tid;
  const inputClassName = 'session-input ' + (isCodeInput ? 'code-input' : '');

  return (
    <div className="session-view">
      <div className="session-header">
        <div>
          <h1 className="session-method-name">{methodInfo.label}</h1>
          <p className="session-method-desc">{methodInfo.description}</p>
        </div>
        <Link to={moduleUrl} className="btn btn-secondary btn-sm">
          Back to Module
        </Link>
      </div>

      <div className="conversation" ref={scrollRef}>
        {messages.map((msg, i) => (
          <div key={i} className={'turn turn-' + msg.role}>
            <div className="turn-label">{msg.role === 'agent' ? 'Coach' : 'You'}</div>
            <div className="turn-content">
              <MarkdownRenderer content={msg.content} />
            </div>
          </div>
        ))}

        {round > 1 && !completed && messages.length > 0 && (
          <div className="round-indicator" aria-live="polite">Round {round}</div>
        )}

        {submitting && (
          <LoadingState messages={GRADING_MESSAGES} ariaLabel="Grading your response" />
        )}

        {completed && feedback && (
          <div className="feedback-panel" role="region" aria-label="Session feedback">
            <div className="feedback-score">
              <span className="score-label">Score</span>
              <span className="score-value">{score ?? '—'}<span className="score-max">/100</span></span>
            </div>
            <div className="feedback-text">
              <MarkdownRenderer content={feedback} />
            </div>
            {execution && (
              <div className="execution-panel" aria-label="Code execution result">
                <h3 className="execution-title">
                  {execution.timed_out
                    ? 'Timed out'
                    : execution.return_code === 0
                    ? 'Ran successfully'
                    : 'Exited with an error'}
                </h3>
                {execution.stdout && (
                  <div className="execution-block">
                    <span className="execution-label">stdout</span>
                    <pre className="execution-output"><code>{execution.stdout}</code></pre>
                  </div>
                )}
                {execution.stderr && (
                  <div className="execution-block">
                    <span className="execution-label">stderr</span>
                    <pre className="execution-output"><code>{execution.stderr}</code></pre>
                  </div>
                )}
              </div>
            )}
            <div className="feedback-actions">
              <Link to={topicUrl} className="btn btn-secondary">
                Back to Topic
              </Link>
              <button
                className="btn btn-primary"
                onClick={() => navigate(moduleUrl)}
              >
                Try This Module Again
              </button>
            </div>
          </div>
        )}
      </div>

      {!completed && !submitting && (
        <div className="session-input-area">
          <label htmlFor="session-input" className="form-label">
            {isCodeInput ? 'Your code' : 'Your response'}
          </label>
          <textarea
            id="session-input"
            ref={inputRef}
            className={inputClassName}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isCodeInput ? 'Write your code here. Tab to indent, Cmd/Ctrl+Enter to submit.' : 'Write your response. Cmd/Ctrl+Enter to submit.'}
            rows={isCodeInput ? 12 : 6}
            aria-label={isCodeInput ? 'Code editor' : 'Response input'}
          />
          <button
            className="btn btn-primary"
            onClick={handleSubmit}
            disabled={!input.trim()}
          >
            Submit
          </button>
        </div>
      )}
    </div>
  );
}
