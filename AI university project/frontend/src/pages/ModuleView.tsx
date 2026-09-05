import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { getModule, startSession, deleteModule } from '../api';
import type { ModuleDetail } from '../types';
import { METHOD_INFO } from '../constants';
import MarkdownRenderer from '../components/MarkdownRenderer';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';

export default function ModuleView() {
  const { topicId, moduleId } = useParams<{ topicId: string; moduleId: string }>();
  const tid = Number(topicId);
  const mid = Number(moduleId);
  const navigate = useNavigate();
  const [module, setModule] = useState<ModuleDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [starting, setStarting] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined);
  const [deleting, setDeleting] = useState(false);

  const load = () => {
    setLoading(true);
    setError(false);
    setErrorMessage(undefined);
    getModule(tid, mid)
      .then(setModule)
      .catch((err) => {
        setErrorMessage(err instanceof Error ? err.message : undefined);
        setError(true);
      })
      .finally(() => setLoading(false));
  };

  useEffect(load, [tid, mid]);

  const handleStartSession = async (method?: string) => {
    setStarting(true);
    setErrorMessage(undefined);
    try {
      const session = await startSession(mid, method);
      navigate(`/topics/${tid}/modules/${mid}/session/${session.id}`);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : undefined);
      setError(true);
      setStarting(false);
    }
  };

  const handleDelete = async () => {
    if (!module) return;
    if (!window.confirm(`Delete "${module.title}"? This removes its digest, quiz, and session history for good.`)) {
      return;
    }
    setDeleting(true);
    setErrorMessage(undefined);
    try {
      await deleteModule(tid, mid);
      navigate(`/topics/${tid}`);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : undefined);
      setError(true);
      setDeleting(false);
    }
  };

  if (loading || starting || deleting) {
    return (
      <LoadingState
        messages={
          deleting ? ['Deleting module...']
          : starting ? ['Starting your session...', 'Preparing the exercise...']
          : ['Loading module...']
        }
        ariaLabel={deleting ? 'Deleting module' : starting ? 'Starting session' : 'Loading module'}
      />
    );
  }

  if (error || !module) {
    return <ErrorState message={errorMessage} onRetry={load} />;
  }

  if (!module.unlocked) {
    return (
      <div className="module-view">
        <div className="page-header">
          <button onClick={() => navigate(`/topics/${tid}`)} className="btn btn-secondary">Back to Topic</button>
        </div>
        <div className="empty-state">
          <h1 className="empty-title">Locked</h1>
          <p className="empty-body">Complete the earlier modules in this topic first to unlock this one.</p>
        </div>
      </div>
    );
  }

  if (module.status === 'pending') {
    return (
      <div className="module-view">
        <div className="page-header">
          <button onClick={() => navigate(`/topics/${tid}`)} className="btn btn-secondary">Back to Topic</button>
        </div>
        <LoadingState
          messages={['This module is being researched...', 'Reading through sources...', 'Compiling the digest...']}
          ariaLabel="Researching module"
        />
      </div>
    );
  }

  return (
    <div className="module-view">
      <div className="page-header">
        <button onClick={() => navigate(`/topics/${tid}`)} className="btn btn-secondary">Back to Topic</button>
        <button onClick={handleDelete} className="btn btn-secondary btn-danger">Delete Module</button>
      </div>

      <article className="reading-article">
        <header className="reading-header">
          <h1 className="reading-title">{module.title}</h1>
          {module.one_liner && <p className="reading-subtitle">{module.one_liner}</p>}
        </header>

        {module.digest_markdown ? (
          <MarkdownRenderer content={module.digest_markdown} />
        ) : (
          <p className="empty-inline">The digest for this module is not available yet.</p>
        )}
      </article>

      {module.sessions.length > 0 && (
        <section className="session-history">
          <button
            className="collapsible-header"
            onClick={() => setShowHistory(!showHistory)}
            aria-expanded={showHistory}
          >
            <span>{showHistory ? '▼' : '▶'}</span> Previous attempts ({module.sessions.length})
          </button>
          {showHistory && (
            <ul className="history-list">
              {module.sessions.map((s) => (
                <li key={s.id}>
                  <Link to={`/topics/${tid}/modules/${mid}/session/${s.id}`} className="history-item">
                    <span className="history-method">{METHOD_INFO[s.method_used].label}</span>
                    <span className="history-score">{s.score !== null ? `${s.score}/100` : 'In progress'}</span>
                    <span className="history-date">
                      {new Date(s.started_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {module.has_quiz && !module.quiz_passed ? (
        <div className="module-cta">
          <p className="empty-inline">Pass the diagnostic quiz to unlock practice sessions for this module.</p>
          <Link to={`/topics/${tid}/modules/${mid}/quiz`} className="btn btn-primary btn-lg">
            Take Diagnostic Quiz
          </Link>
        </div>
      ) : (
        <div className="module-cta">
          {showAdvanced && (
            <div className="advanced-methods">
              <p className="advanced-label">Choose an exercise method (optional — otherwise we pick for you):</p>
              <div className="method-grid">
                {Object.entries(METHOD_INFO).map(([key, info]) => (
                  <button
                    key={key}
                    className="method-pick-btn"
                    onClick={() => handleStartSession(key)}
                  >
                    <span className="method-pick-name">{info.label}</span>
                    <span className="method-pick-desc">{info.description}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
          <button
            className="btn btn-link"
            onClick={() => setShowAdvanced(!showAdvanced)}
          >
            {showAdvanced ? 'Hide options' : 'Advanced: choose method'}
          </button>
          <button
            className="btn btn-primary btn-lg"
            onClick={() => handleStartSession()}
          >
            Start Learning Session
          </button>
        </div>
      )}
    </div>
  );
}
