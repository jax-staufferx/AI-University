import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { getQuiz, getQuizResult, getSlideshow, submitQuiz } from '../api';
import type { Quiz, QuizSubmitResult, Slideshow } from '../types';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';

export default function QuizView() {
  const { topicId, moduleId } = useParams<{ topicId: string; moduleId: string }>();
  const tid = Number(topicId);
  const mid = Number(moduleId);
  const navigate = useNavigate();
  const moduleUrl = `/topics/${tid}/modules/${mid}`;

  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<QuizSubmitResult | null>(null);
  const [justSubmitted, setJustSubmitted] = useState(false);
  const [slideshow, setSlideshow] = useState<Slideshow | null>(null);
  const [loadingSlideshow, setLoadingSlideshow] = useState(false);

  const fetchSlideshow = () => {
    setLoadingSlideshow(true);
    getSlideshow(tid, mid)
      .then(setSlideshow)
      .catch(() => {})
      .finally(() => setLoadingSlideshow(false));
  };

  const load = () => {
    setLoading(true);
    setError(false);
    setJustSubmitted(false);
    Promise.all([
      getQuiz(tid, mid),
      getQuizResult(tid, mid).catch(() => null), // no past attempt yet isn't an error
    ])
      .then(([q, pastResult]) => {
        setQuiz(q);
        if (pastResult) {
          setResult(pastResult);
          if (pastResult.passed) fetchSlideshow();
        }
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  };

  useEffect(load, [tid, mid]);

  const allAnswered = quiz ? quiz.questions.every((q) => (answers[q.id] ?? '').trim().length > 0) : false;

  const handleSubmit = async () => {
    if (!quiz || !allAnswered || submitting) return;
    setSubmitting(true);
    setError(false);
    try {
      const payload = quiz.questions.map((q) => ({ question_id: q.id, response: answers[q.id] }));
      const res = await submitQuiz(tid, mid, payload);
      setResult(res);
      setJustSubmitted(true);
      if (res.passed && res.slideshow_ready) fetchSlideshow();
    } catch {
      setError(true);
    } finally {
      setSubmitting(false);
    }
  };

  const handleRetake = () => {
    setResult(null);
    setSlideshow(null);
    setAnswers({});
    setJustSubmitted(false);
  };

  if (loading) {
    return <LoadingState messages={['Loading quiz...']} ariaLabel="Loading quiz" />;
  }

  if (submitting) {
    return <LoadingState messages={['Grading your answers...']} ariaLabel="Grading quiz" />;
  }

  if (error || !quiz) {
    return <ErrorState onRetry={load} />;
  }

  if (result) {
    return (
      <div className="quiz-view">
        <div className="page-header">
          <h1 className="page-title">Diagnostic Quiz</h1>
          <Link to={moduleUrl} className="btn btn-secondary btn-sm">Back to Module</Link>
        </div>

        {!justSubmitted && (
          <p className="page-subtitle">Showing your most recent attempt.</p>
        )}

        <div className="feedback-panel" role="region" aria-label="Quiz results">
          <div className="feedback-score">
            <span className="score-label">{result.passed ? 'Passed' : 'Not yet'}</span>
            <span className="score-value">
              {Math.round(result.weighted_score * 100)}<span className="score-max">/100</span>
            </span>
            <span className="score-max">(need {Math.round(result.threshold * 100)})</span>
          </div>

          <ul className="quiz-results-list">
            {result.results.map((r) => (
              <li key={r.question_id} className={`quiz-result-item ${r.correct ? 'correct' : 'incorrect'}`}>
                <div className="quiz-result-header">
                  <span>{r.correct ? '✓' : '✗'} {r.concept}</span>
                  <span className="topic-card-tier">difficulty {r.difficulty}/10</span>
                </div>
                {!r.correct && (
                  <p className="quiz-explanation">
                    Correct answer: {r.correct_answer}<br />
                    {r.explanation}
                  </p>
                )}
              </li>
            ))}
          </ul>

          {result.passed ? (
            <>
              {loadingSlideshow && (
                <LoadingState messages={['Building your lesson...']} ariaLabel="Loading slideshow" />
              )}
              {slideshow && slideshow.slides.length > 0 && (
                <div className="slideshow-block">
                  <h2 className="section-divider">Lesson</h2>
                  {slideshow.slides.map((s, i) => (
                    <div key={i} className="slideshow-slide">
                      <h3>{s.concept}</h3>
                      <p>{s.content}</p>
                      {s.examples.length > 0 && (
                        <ul>
                          {s.examples.map((ex, j) => <li key={j}>{ex}</li>)}
                        </ul>
                      )}
                    </div>
                  ))}
                </div>
              )}
              <div className="feedback-actions">
                <button className="btn btn-primary" onClick={() => navigate(moduleUrl)}>
                  Continue to Practice
                </button>
                <button className="btn btn-secondary" onClick={handleRetake}>
                  Retake Quiz
                </button>
              </div>
            </>
          ) : (
            <div className="feedback-actions">
              <button className="btn btn-primary" onClick={handleRetake}>
                Try Again
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="quiz-view">
      <div className="page-header">
        <h1 className="page-title">Diagnostic Quiz</h1>
        <Link to={moduleUrl} className="btn btn-secondary btn-sm">Back to Module</Link>
      </div>
      <p className="page-subtitle">
        Answer honestly — this is diagnostic, not a test. You need {Math.round(quiz.threshold * 100)}/100
        (harder questions count for more) to unlock practice sessions for this module. You can retry
        as many times as you need.
      </p>

      <form onSubmit={(e) => { e.preventDefault(); handleSubmit(); }}>
        {quiz.questions.map((q, i) => {
          const label = (
            <>{i + 1}. {q.question} <span className="topic-card-tier">(difficulty {q.difficulty}/10)</span></>
          );

          if (q.type === 'multiple_choice' && q.options) {
            return (
              <fieldset key={q.id} className="form-field quiz-question">
                <legend className="form-label">{label}</legend>
                <div className="tier-cards">
                  {q.options.map((opt) => (
                    <label key={opt} className={`tier-card ${answers[q.id] === opt ? 'selected' : ''}`}>
                      <input
                        type="radio"
                        name={q.id}
                        value={opt}
                        checked={answers[q.id] === opt}
                        onChange={() => setAnswers((a) => ({ ...a, [q.id]: opt }))}
                        className="sr-only"
                      />
                      <span className="tier-card-name">{opt}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
            );
          }

          const inputId = `quiz-answer-${q.id}`;
          return (
            <div key={q.id} className="form-field quiz-question">
              <label htmlFor={inputId} className="form-label">{label}</label>
              <input
                id={inputId}
                type="text"
                className="text-input"
                value={answers[q.id] ?? ''}
                onChange={(e) => setAnswers((a) => ({ ...a, [q.id]: e.target.value }))}
                placeholder="Your answer..."
              />
            </div>
          );
        })}

        <button type="submit" className="btn btn-primary btn-lg" disabled={!allAnswered}>
          Submit Quiz
        </button>
      </form>
    </div>
  );
}
