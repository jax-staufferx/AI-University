import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createTopic, continueBudget } from '../api';
import type { BudgetError, FormatTier } from '../types';
import { FORMAT_TIER_LABELS, FORMAT_TIER_DESCRIPTIONS } from '../constants';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';

const RESEARCH_MESSAGES = [
  'Researching your topic...',
  'Reading through sources...',
  'Synthesizing the digest...',
  'Structuring the curriculum...',
  'Almost there...',
];

const TIERS: FormatTier[] = ['quick_dive', 'deep_dive', 'short_course', 'full_course'];

export default function CreateTopic() {
  const navigate = useNavigate();
  const [title, setTitle] = useState('');
  const [tier, setTier] = useState<FormatTier | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(false);
  const [budgetError, setBudgetError] = useState<BudgetError | null>(null);
  const [continuing, setContinuing] = useState(false);

  const handleSubmit = async () => {
    if (!title.trim() || !tier) return;
    setSubmitting(true);
    setError(false);
    setBudgetError(null);
    try {
      const topic = await createTopic(title.trim(), tier);
      routeToTopic(topic.id, topic.outline_approved, topic.current_module_id, topic.format_tier);
    } catch (err: unknown) {
      const e = err as Error & { budgetError?: BudgetError };
      if (e.budgetError) {
        setBudgetError(e.budgetError);
      } else {
        setError(true);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const routeToTopic = (topicId: number, outlineApproved: boolean, currentModuleId: number | null, formatTier: string) => {
    if (!outlineApproved && (formatTier === 'short_course' || formatTier === 'full_course')) {
      navigate(`/topics/${topicId}/outline`);
    } else if (currentModuleId) {
      navigate(`/topics/${topicId}/modules/${currentModuleId}`);
    } else {
      navigate(`/topics/${topicId}`);
    }
  };

  const handleContinue = async () => {
    if (!budgetError || !tier) return;
    setContinuing(true);
    try {
      const topic = await continueBudget(budgetError.topic_id);
      routeToTopic(topic.id, topic.outline_approved, topic.current_module_id, topic.format_tier);
    } catch {
      setError(true);
    } finally {
      setContinuing(false);
    }
  };

  if (submitting || continuing) {
    return (
      <LoadingState
        messages={RESEARCH_MESSAGES}
        ariaLabel="Researching your topic"
      />
    );
  }

  if (budgetError) {
    return (
      <div className="budget-cap-state">
        <h1 className="page-title">Research budget reached</h1>
        <p className="budget-cap-text">
          You've used {budgetError.call_count} of {budgetError.soft_cap} research calls for this topic.
          That's the soft cap designed to keep things efficient. You can continue if you'd like —
          the research will pick up where it left off.
        </p>
        <div className="budget-cap-actions">
          <button className="btn btn-primary" onClick={handleContinue}>
            Continue Anyway
          </button>
          <button className="btn btn-secondary" onClick={() => navigate('/')}>
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  if (error) {
    return <ErrorState onRetry={() => { setError(false); navigate('/'); }} />;
  }

  return (
    <div className="create-topic">
      <div className="page-header">
        <h1 className="page-title">New Topic</h1>
        <button className="btn btn-secondary" onClick={() => navigate('/')}>
          Cancel
        </button>
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); handleSubmit(); }}
        className="create-topic-form"
      >
        <div className="form-field">
          <label htmlFor="topic-title" className="form-label">
            What do you want to learn?
          </label>
          <input
            id="topic-title"
            type="text"
            className="text-input"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Bayesian inference, Rust ownership model, history of the Silk Road..."
            autoFocus
          />
        </div>

        <fieldset className="tier-selector">
          <legend className="form-label">Choose a format</legend>
          <div className="tier-cards">
            {TIERS.map((t) => (
              <label
                key={t}
                className={`tier-card ${tier === t ? 'selected' : ''}`}
              >
                <input
                  type="radio"
                  name="format-tier"
                  value={t}
                  checked={tier === t}
                  onChange={() => setTier(t)}
                  className="sr-only"
                />
                <span className="tier-card-name">{FORMAT_TIER_LABELS[t]}</span>
                <span className="tier-card-desc">{FORMAT_TIER_DESCRIPTIONS[t]}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <button
          type="submit"
          className="btn btn-primary btn-lg"
          disabled={!title.trim() || !tier}
        >
          Start Research
        </button>
      </form>
    </div>
  );
}
