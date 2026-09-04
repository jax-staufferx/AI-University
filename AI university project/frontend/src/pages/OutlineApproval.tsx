import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { getOutline, approveOutline } from '../api';
import type { ContentType, OutlineModule } from '../types';
import { CONTENT_TYPE_LABELS } from '../constants';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';

const APPROVE_MESSAGES = [
  'Starting research on your first module...',
  'Reading through sources...',
  'This may take a moment...',
];

export default function OutlineApproval() {
  const { topicId } = useParams<{ topicId: string }>();
  const tid = Number(topicId);
  const navigate = useNavigate();
  const [modules, setModules] = useState<OutlineModule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [approving, setApproving] = useState(false);

  const load = () => {
    setLoading(true);
    setError(false);
    getOutline(tid)
      .then((res) => setModules(res.modules))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  };

  useEffect(load, [tid]);

  const updateModule = (index: number, field: keyof OutlineModule, value: string) => {
    setModules((prev) =>
      prev.map((m, i) =>
        i === index ? { ...m, [field]: field === 'order_index' ? Number(value) : value } : m
      )
    );
  };

  const moveModule = (index: number, dir: -1 | 1) => {
    setModules((prev) => {
      const next = [...prev];
      const target = index + dir;
      if (target < 0 || target >= next.length) return prev;
      [next[index], next[target]] = [next[target], next[index]];
      return next.map((m, i) => ({ ...m, order_index: i }));
    });
  };

  const deleteModule = (index: number) => {
    setModules((prev) => prev.filter((_, i) => i !== index).map((m, i) => ({ ...m, order_index: i })));
  };

  const handleApprove = async () => {
    setApproving(true);
    try {
      const payload = modules.map((m) => ({
        order_index: m.order_index,
        title: m.title,
        one_liner: m.one_liner || '',
        content_type: m.content_type as ContentType,
      }));
      const topic = await approveOutline(tid, payload);
      if (topic.current_module_id) {
        navigate(`/topics/${tid}/modules/${topic.current_module_id}`);
      } else {
        navigate(`/topics/${tid}`);
      }
    } catch {
      setError(true);
      setApproving(false);
    }
  };

  if (loading) {
    return <LoadingState messages={['Loading outline...']} ariaLabel="Loading outline" />;
  }

  if (error) {
    return <ErrorState onRetry={load} />;
  }

  if (approving) {
    return <LoadingState messages={APPROVE_MESSAGES} ariaLabel="Starting research" />;
  }

  return (
    <div className="outline-approval">
      <div className="page-header">
        <h1 className="page-title">Review Your Curriculum</h1>
        <button className="btn btn-secondary" onClick={() => navigate(`/topics/${tid}`)}>
          Back
        </button>
      </div>

      <p className="page-subtitle">
        Here's the proposed structure for your topic. You can edit titles, descriptions,
        and content types, reorder modules, or remove any you don't want.
        Once approved, we'll start researching your first module right away.
      </p>

      <ol className="outline-list">
        {modules.map((m, i) => (
          <li key={i} className="outline-item">
            <div className="outline-item-header">
              <span className="outline-number">{i + 1}</span>
              <div className="outline-fields">
                <label className="sr-only" htmlFor={`title-${i}`}>Module title</label>
                <input
                  id={`title-${i}`}
                  type="text"
                  className="text-input outline-title-input"
                  value={m.title}
                  onChange={(e) => updateModule(i, 'title', e.target.value)}
                />
                <label className="sr-only" htmlFor={`liner-${i}`}>Module description</label>
                <input
                  id={`liner-${i}`}
                  type="text"
                  className="text-input outline-liner-input"
                  value={m.one_liner || ''}
                  onChange={(e) => updateModule(i, 'one_liner', e.target.value)}
                  placeholder="One-liner description"
                />
                <label className="sr-only" htmlFor={`ctype-${i}`}>Content type</label>
                <select
                  id={`ctype-${i}`}
                  className="select-input outline-ctype"
                  value={m.content_type}
                  onChange={(e) => updateModule(i, 'content_type', e.target.value)}
                >
                  {Object.entries(CONTENT_TYPE_LABELS).map(([val, label]) => (
                    <option key={val} value={val}>{label}</option>
                  ))}
                </select>
              </div>
              <div className="outline-controls">
                <button
                  className="icon-btn"
                  onClick={() => moveModule(i, -1)}
                  disabled={i === 0}
                  aria-label={`Move module ${i + 1} up`}
                >
                  ↑
                </button>
                <button
                  className="icon-btn"
                  onClick={() => moveModule(i, 1)}
                  disabled={i === modules.length - 1}
                  aria-label={`Move module ${i + 1} down`}
                >
                  ↓
                </button>
                <button
                  className="icon-btn icon-btn-danger"
                  onClick={() => deleteModule(i)}
                  aria-label={`Delete module ${i + 1}`}
                >
                  ✕
                </button>
              </div>
            </div>
          </li>
        ))}
      </ol>

      <div className="outline-approve-zone">
        <p className="approve-hint">
          Once approved, we'll start researching your first module right away.
        </p>
        <button className="btn btn-primary btn-lg" onClick={handleApprove}>
          Approve &amp; Start
        </button>
      </div>
    </div>
  );
}
