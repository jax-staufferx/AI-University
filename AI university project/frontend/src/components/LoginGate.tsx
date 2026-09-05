import { useEffect, useState, type FormEvent, type ReactNode } from 'react';
import { authLogin, authStatus } from '../api';
import LoadingState from './LoadingState';

export default function LoginGate({ children }: { children: ReactNode }) {
  const [checking, setChecking] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    authStatus()
      .then((s) => setAuthenticated(s.authenticated))
      .catch(() => setAuthenticated(false))
      .finally(() => setChecking(false));
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!password.trim() || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await authLogin(password);
      setAuthenticated(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setSubmitting(false);
    }
  };

  if (checking) {
    return <LoadingState messages={['Loading...']} ariaLabel="Checking login" />;
  }

  if (!authenticated) {
    return (
      <div className="login-gate">
        <form onSubmit={handleSubmit} className="login-form">
          <h1 className="page-title">Personal Learning Agent</h1>
          <div className="form-field">
            <label htmlFor="login-password" className="form-label">Password</label>
            <input
              id="login-password"
              type="password"
              className="text-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoFocus
              autoComplete="current-password"
            />
          </div>
          {error && <p className="error-text" role="alert">{error}</p>}
          <button
            type="submit"
            className="btn btn-primary btn-lg"
            disabled={!password.trim() || submitting}
          >
            {submitting ? 'Checking...' : 'Log In'}
          </button>
        </form>
      </div>
    );
  }

  return <>{children}</>;
}
