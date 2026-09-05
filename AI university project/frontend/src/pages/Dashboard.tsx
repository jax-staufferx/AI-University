import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { listTopics, getTopic, deleteTopic } from '../api';
import type { TopicListItem } from '../types';
import { FORMAT_TIER_LABELS, TOPIC_STATUS_LABELS } from '../constants';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';

export default function Dashboard() {
  const [topics, setTopics] = useState<TopicListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [navigating, setNavigating] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const navigate = useNavigate();

  const load = () => {
    setLoading(true);
    setError(false);
    listTopics()
      .then(setTopics)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleDelete = async (topic: TopicListItem) => {
    if (!window.confirm(`Delete "${topic.title}"? This removes its research, quizzes, and session history for good.`)) {
      return;
    }
    setDeletingId(topic.id);
    try {
      await deleteTopic(topic.id);
      setTopics((prev) => prev.filter((t) => t.id !== topic.id));
    } catch {
      setError(true);
    } finally {
      setDeletingId(null);
    }
  };

  const handleCardClick = async (topicId: number) => {
    setNavigating(topicId);
    try {
      const detail = await getTopic(topicId);
      const hasOutline = detail.format_tier === 'short_course' || detail.format_tier === 'full_course';
      if (hasOutline && !detail.outline_approved) {
        navigate(`/topics/${topicId}/outline`);
      } else if (detail.current_module_id) {
        navigate(`/topics/${topicId}/modules/${detail.current_module_id}`);
      } else {
        navigate(`/topics/${topicId}`);
      }
    } catch {
      navigate(`/topics/${topicId}`);
    } finally {
      setNavigating(null);
    }
  };

  if (loading) {
    return (
      <LoadingState
        messages={['Loading your topics...']}
        ariaLabel="Loading dashboard"
      />
    );
  }

  if (error) {
    return <ErrorState onRetry={load} />;
  }

  const active = topics.filter((t) => t.status !== 'completed');
  const completed = topics.filter((t) => t.status === 'completed');

  if (topics.length === 0) {
    return (
      <div className="empty-state">
        <h1 className="empty-title">Welcome.</h1>
        <p className="empty-body">
          This is your personal learning space. Pick any topic you've been curious about,
          and the app will research it thoroughly, break it into digestible pieces, and
          test your understanding honestly — no participation trophies, just real learning.
        </p>
        <Link to="/topics/new" className="btn btn-primary btn-lg">
          Create your first topic
        </Link>
      </div>
    );
  }

  return (
    <div className="dashboard">
      <div className="page-header">
        <h1 className="page-title">Your Topics</h1>
        <Link to="/topics/new" className="btn btn-primary">
          New Topic
        </Link>
      </div>

      {navigating !== null && (
        <LoadingState messages={['Opening topic...']} ariaLabel="Opening topic" />
      )}

      <section className="topic-list" aria-label="Active topics">
        {active.map((topic) => (
          <TopicCard
            key={topic.id}
            topic={topic}
            onClick={() => handleCardClick(topic.id)}
            onDelete={() => handleDelete(topic)}
            deleting={deletingId === topic.id}
          />
        ))}
      </section>

      {completed.length > 0 && (
        <>
          <h2 className="section-divider">Completed</h2>
          <section className="topic-list completed-list" aria-label="Completed topics">
            {completed.map((topic) => (
              <TopicCard
                key={topic.id}
                topic={topic}
                onClick={() => handleCardClick(topic.id)}
                onDelete={() => handleDelete(topic)}
                deleting={deletingId === topic.id}
              />
            ))}
          </section>
        </>
      )}
    </div>
  );
}

function TopicCard({
  topic, onClick, onDelete, deleting,
}: {
  topic: TopicListItem; onClick: () => void; onDelete: () => void; deleting: boolean;
}) {
  return (
    <div className="topic-card">
      <button className="topic-card-main" onClick={onClick}>
        <div className="topic-card-header">
          <span className="topic-card-title">{topic.title}</span>
          <span className="topic-card-tier">{FORMAT_TIER_LABELS[topic.format_tier]}</span>
        </div>
        <div className="topic-card-footer">
          <span className={`topic-status status-${topic.status}`}>
            {TOPIC_STATUS_LABELS[topic.status]}
          </span>
          {topic.completed_at && (
            <span className="topic-completed-date">
              {new Date(topic.completed_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
            </span>
          )}
        </div>
      </button>
      <button
        className="icon-btn icon-btn-danger topic-delete-btn"
        onClick={(e) => { e.stopPropagation(); onDelete(); }}
        disabled={deleting}
        aria-label={`Delete topic: ${topic.title}`}
      >
        {deleting ? '…' : '×'}
      </button>
    </div>
  );
}
