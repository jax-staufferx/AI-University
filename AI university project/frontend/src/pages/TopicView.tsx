import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { getTopic, getConnections, continueBudget } from '../api';
import type { BudgetError, TopicConnection, TopicDetail } from '../types';
import { FORMAT_TIER_LABELS, MODULE_STATUS_LABELS } from '../constants';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';

const MODULE_STATUS_ICONS: Record<string, string> = {
  pending: '○',
  researched: '◉',
  in_progress: '◐',
  completed: '●',
};

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

  const hasMultipleModules = topic.modules.length > 1 || topic.format_tier === 'deep_dive';
  const completedCount = topic.modules.filter((m) => m.status === 'completed').length;
  const isResearching = topic.status === 'planning' || (topic.modules.length === 0 && topic.status !== 'completed');

  return (
    <div className="topic-view">
      <div className="page-header">
        <div>
          <h1 className="page-title">{topic.title}</h1>
          <div className="topic-meta">
            <span className="meta-tag">{FORMAT_TIER_LABELS[topic.format_tier]}</span>
            {hasMultipleModules && topic.modules.length > 0 && (
              <span className="meta-progress">
                {completedCount} of {topic.modules.length} modules complete
              </span>
            )}
          </div>
        </div>
        <Link to="/" className="btn btn-secondary">Back</Link>
      </div>

      {isResearching && (
        <LoadingState
          messages={['Researching your topic...', 'Reading through sources...', 'Structuring the curriculum...']}
          ariaLabel="Researching"
        />
      )}

      {topic.budget_soft_cap > 0 && (
        <p className="budget-line">
          {topic.budget_used} of {topic.budget_soft_cap} research calls used
        </p>
      )}

      {hasMultipleModules && topic.modules.length > 0 && (
        <section className="module-list" aria-label="Modules">
          {topic.modules.map((m) => {
            const isCurrent = topic.current_module_id === m.id;
            return (
              <div key={m.id} className={`module-row ${isCurrent ? 'current' : ''}`}>
                <div className="module-row-status">
                  <span className="module-status-icon" aria-hidden="true">
                    {MODULE_STATUS_ICONS[m.status]}
                  </span>
                  <span className="module-status-label">{MODULE_STATUS_LABELS[m.status]}</span>
                </div>
                <div className="module-row-body">
                  <span className="module-row-title">{m.title}</span>
                  {m.one_liner && <span className="module-row-liner">{m.one_liner}</span>}
                </div>
                {m.status !== 'pending' && (
                  <Link
                    to={`/topics/${tid}/modules/${m.id}`}
                    className={`btn ${isCurrent ? 'btn-primary' : 'btn-secondary'} btn-sm`}
                  >
                    {m.status === 'completed' ? 'Review' : isCurrent ? 'Continue' : 'Open'}
                  </Link>
                )}
              </div>
            );
          })}
        </section>
      )}

      {!hasMultipleModules && topic.modules.length === 1 && topic.modules[0].status !== 'pending' && (
        <div className="single-module-cta">
          <Link
            to={`/topics/${tid}/modules/${topic.modules[0].id}`}
            className="btn btn-primary btn-lg"
          >
            {topic.modules[0].status === 'completed' ? 'Review Module' : 'Continue Learning'}
          </Link>
        </div>
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
