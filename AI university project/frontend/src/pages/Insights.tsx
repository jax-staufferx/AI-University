import { useEffect, useState } from 'react';
import { listProposals, respondProposal } from '../api';
import type { MonitorProposal } from '../types';
import { CONTENT_TYPE_LABELS, METHOD_INFO } from '../constants';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';

export default function Insights() {
  const [proposals, setProposals] = useState<MonitorProposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [responding, setResponding] = useState<number | null>(null);

  const load = () => {
    setLoading(true);
    setError(false);
    listProposals()
      .then(setProposals)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleRespond = async (id: number, approve: boolean) => {
    setResponding(id);
    try {
      await respondProposal(id, approve);
      setProposals((prev) => prev.filter((p) => p.id !== id));
    } catch {
      setError(true);
    } finally {
      setResponding(null);
    }
  };

  if (loading) {
    return <LoadingState messages={['Loading insights...']} ariaLabel="Loading insights" />;
  }

  if (error) {
    return <ErrorState onRetry={load} />;
  }

  if (proposals.length === 0) {
    return (
      <div className="empty-state">
        <h1 className="empty-title">Nothing to review yet</h1>
        <p className="empty-body">
          After a few more sessions, the system may suggest adjustments to which learning
          methods work best for you. Check back then.
        </p>
      </div>
    );
  }

  return (
    <div className="insights">
      <div className="page-header">
        <h1 className="page-title">Insights</h1>
      </div>

      <p className="page-subtitle">
        The system has noticed patterns in how you learn. Review these proposals —
        nothing changes until you decide.
      </p>

      <section className="proposal-list" aria-label="Pending proposals">
        {proposals.map((p) => (
          <div key={p.id} className="proposal-card">
            <div className="proposal-meta">
              <span className="proposal-method">{METHOD_INFO[p.method].label}</span>
              <span className="proposal-ctype">{CONTENT_TYPE_LABELS[p.content_type]}</span>
              <span className="proposal-weight">
                {p.current_weight.toFixed(1)} → {p.proposed_weight.toFixed(1)}
              </span>
            </div>
            <p className="proposal-rationale">{p.rationale}</p>
            <div className="proposal-actions">
              <button
                className="btn btn-primary btn-sm"
                onClick={() => handleRespond(p.id, true)}
                disabled={responding === p.id}
              >
                Approve
              </button>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => handleRespond(p.id, false)}
                disabled={responding === p.id}
              >
                Dismiss
              </button>
            </div>
          </div>
        ))}
      </section>
    </div>
  );
}
