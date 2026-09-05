import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { getTopic, getConnections, continueBudget } from '../api';
import type { BudgetError, ModuleSummary, TopicConnection, TopicDetail } from '../types';
import { FORMAT_TIER_LABELS, CONTENT_DEPTH_LABELS, TOPIC_STATUS_LABELS, MODULE_STATUS_LABELS } from '../constants';
import ProgressBar from '../components/ProgressBar';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';

const MODULE_STATUS_ICONS: Record<string, string> = {
  pending: '○',
  researched: '◉',
  in_progress: '◐',
  completed: '●',
};

const RESEARCH_POLL_MS = 4000;

export default function TopicView() {
  const { topicId } = useParams<{ topicId: string }>();
  const tid = Number(topicId);
  const navigate = useNavigate();
  const [topic, setTopic] = useState<TopicDetail | null>(null);
  const [connections, setConnections] = useState<TopicConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [budgetError, setBudgetError] = useState<BudgetError | null>(null);
  const [continuing, setContinuing] = useState(false);

  const load = () => {
    setLoading(true);
    setError(false);
    Promise.all([getTopic(tid), getConnections(tid)])
      .then(([t, c]) => {
        setTopic(t);
        setConnections(c);
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  };

  useEffect(load, [tid]);

  // While the course-tier background researcher is still working through modules, poll
  // so the progress bar actually moves instead of requiring a manual refresh.
  useEffect(() => {
    if (!topic?.research_in_progress) return;
    const interval = setInterval(() => {
      getTopic(tid).then(setTopic).catch(() => {});
    }, RESEARCH_POLL_MS);
    return () => clearInterval(interval);
  }, [tid, topic?.research_in_progress]);

  const handleContinue = async () => {
    if (!budgetError) return;
    setContinuing(true);
    try {
      const t = await continueBudget(budgetError.topic_id);
      setTopic(t);
      setBudgetError(null);
    } catch (err: unknown) {
      const e = err as Error & { budgetError?: BudgetError };
      if (e.budgetError) {
        setBudgetError(e.budgetError);
      } else {
        setError(true);
      }
    } finally {
      setContinuing(false);
    }
  };

  if (loading || continuing) {
    return <LoadingState messages={['Loading topic...']} ariaLabel="Loading topic" />;
  }

  if (error || !topic) {
    return <ErrorState onRetry={load} />;
  }

  if (budgetError) {
    return (
      <div className="budget-cap-state">
        <h1 className="page-title">Research budget reached</h1>
        <p className="budget-cap-text">
          You've used {budgetError.call_count} of {budgetError.soft_cap} research calls for this topic.
          You can continue if you'd like — the research will pick up where it left off.
        </p>
        <button className="btn btn-primary" onClick={handleContinue}>
          Continue Anyway
        </button>
      </div>
    );
  }

  const isPlanning = topic.status === 'planning' && topic.modules.length === 0;
  const completedCount = topic.modules.filter((m) => m.status === 'completed').length;

  if (isPlanning) {
    return (
      <div className="topic-view">
        <div className="page-header">
          <h1 className="page-title">{topic.title}</h1>
          <Link to="/" className="btn btn-secondary">Back</Link>
        </div>
        <LoadingState
          messages={['Researching your topic...', 'Reading through sources...', 'Structuring the curriculum...']}
          ariaLabel="Researching"
        />
      </div>
    );
  }

  return (
    <div className="topic-view">
      <div className="page-header">
        <div>
          <h1 className="page-title">{topic.title}</h1>
          <div className="topic-meta">
            <span className="meta-tag">{FORMAT_TIER_LABELS[topic.format_tier]}</span>
            <span className="meta-tag">{CONTENT_DEPTH_LABELS[topic.depth]}</span>
            <span className={`meta-tag topic-status status-${topic.status}`}>
              {TOPIC_STATUS_LABELS[topic.status]}
            </span>
          </div>
        </div>
        <Link to="/" className="btn btn-secondary">Back</Link>
      </div>

      <section className="topic-overview" aria-label="Progress overview">
        {topic.research_in_progress ? (
          <ProgressBar
            label="Researching modules"
            value={topic.modules_researched}
            max={topic.modules_total}
          />
        ) : topic.modules.length > 0 ? (
          <ProgressBar
            label="Course progress"
            value={completedCount}
            max={topic.modules.length}
            detail={`${completedCount} of ${topic.modules.length} complete`}
          />
        ) : null}

        {topic.research_error && (
          <p className="error-text" role="alert">
            Research hit a problem and stopped: {topic.research_error}
          </p>
        )}

        {topic.budget_soft_cap > 0 && (
          <p className="budget-line">
            {topic.budget_used} of {topic.budget_soft_cap} research calls used
          </p>
        )}
      </section>

      {topic.modules.length > 0 && (
        <section className="module-list" aria-label="Modules">
          <h2 className="section-divider">Modules</h2>
          {topic.modules.map((m) => (
            <ModuleRow key={m.id} tid={tid} module={m} isCurrent={topic.current_module_id === m.id} />
          ))}
        </section>
      )}

      {connections.length > 0 && (
        <section className="related-topics" aria-label="Related topics">
          <h2 className="section-divider">Related Topics</h2>
          {connections.map((c) => (
            <Link key={c.topic_id} to={`/topics/${c.topic_id}`} className="related-topic-card">
              <span className="related-topic-title">{c.topic_title}</span>
              <span className="related-topic-note">{c.connection_note}</span>
            </Link>
          ))}
        </section>
      )}
    </div>
  );
}

function ModuleRow({ tid, module, isCurrent }: { tid: number; module: ModuleSummary; isCurrent: boolean }) {
  const locked = !module.unlocked;
  const moduleUrl = `/topics/${tid}/modules/${module.id}`;
  const showBadges = module.has_quiz || module.sessions_count > 0;

  return (
    <div className={`module-row ${isCurrent ? 'current' : ''} ${locked ? 'locked' : ''}`}>
      <div className="module-row-status">
        <span className="module-status-icon" aria-hidden="true">
          {locked ? '🔒' : MODULE_STATUS_ICONS[module.status]}
        </span>
        <span className="module-status-label">{locked ? 'Locked' : MODULE_STATUS_LABELS[module.status]}</span>
      </div>

      <div className="module-row-body">
        <span className="module-row-title">{module.title}</span>
        {module.one_liner && <span className="module-row-liner">{module.one_liner}</span>}

        {showBadges && (
          <div className="module-row-badges">
            {module.has_quiz && (
              <Link
                to={`${moduleUrl}/quiz`}
                className={`module-badge ${
                  module.quiz_passed ? 'badge-pass' : module.quiz_score !== null ? 'badge-pending' : ''
                }`}
              >
                Quiz: {module.quiz_passed ? 'Passed' : module.quiz_score !== null ? 'Not passed yet' : 'Not taken yet'}
                {module.quiz_score !== null ? ` (${Math.round(module.quiz_score * 100)}%)` : ''}
              </Link>
            )}
            {module.sessions_count > 0 && (
              <Link to={moduleUrl} className="module-badge">
                {module.sessions_count} session{module.sessions_count === 1 ? '' : 's'}
                {module.best_session_score !== null ? ` · best ${module.best_session_score}/100` : ''}
              </Link>
            )}
          </div>
        )}
      </div>

      {!locked && module.status !== 'pending' && (
        <Link
          to={moduleUrl}
          className={`btn ${isCurrent ? 'btn-primary' : 'btn-secondary'} btn-sm`}
        >
          {module.status === 'completed' ? 'Review' : isCurrent ? 'Continue' : 'Open'}
        </Link>
      )}
    </div>
  );
}
