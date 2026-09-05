import { useEffect, useState, type FormEvent, type ReactNode } from 'react';
import { authLogin, authRegister, authStatus } from '../api';
import LoadingState from './LoadingState';

export default function LoginGate({ children }: { children: ReactNode }) {
  const [checking, setChecking] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    authStatus()
      .then((s) => setAuthenticated(s.authenticated))
      .catch(() => setAuthenticated(false))
      .finally(() => setChecking(false));
  }, []);

  const switchMode = (next: 'login' | 'register') => {
    setMode(next);
    setError(null);
    setPassword('');
    setConfirmPassword('');
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password || submitting) return;
    if (mode === 'register' && password !== confirmPassword) {
      setError("Passwords don't match");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      if (mode === 'register') {
        await authRegister(username.trim(), password, confirmPassword);
      } else {
        await authLogin(username.trim(), password);
      }
      setAuthenticated(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong');
    } finally {
      setSubmitting(false);
    }
  };

  if (checking) {
    return <LoadingState messages={['Loading...']} ariaLabel="Checking login" />;
  }

  if (!authenticated) {
    const disabled = !username.trim() || !password || (mode === 'register' && !confirmPassword) || submitting;
    return (
      <div className="login-gate">
        <form onSubmit={handleSubmit} className="login-form">
          <h1 className="page-title">Personal Learning Agent</h1>
          <div className="form-field">
            <label htmlFor="login-username" className="form-label">Username</label>
            <input
              id="login-username"
              type="text"
              className="text-input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
              autoComplete="username"
            />
          </div>
          <div className="form-field">
            <label htmlFor="login-password" className="form-label">Password</label>
            <input
              id="login-password"
              type="password"
              className="text-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
            />
          </div>
          {mode === 'register' && (
            <div className="form-field">
              <label htmlFor="login-confirm-password" className="form-label">Verify Password</label>
              <input
                id="login-confirm-password"
                type="password"
                className="text-input"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                autoComplete="new-password"
              />
            </div>
          )}
          {error && <p className="error-text" role="alert">{error}</p>}
          <button type="submit" className="btn btn-primary btn-lg" disabled={disabled}>
            {submitting ? 'Please wait...' : mode === 'register' ? 'Create Account' : 'Log In'}
          </button>
          <button
            type="button"
            className="btn btn-link login-mode-toggle"
            onClick={() => switchMode(mode === 'register' ? 'login' : 'register')}
          >
            {mode === 'register' ? 'Already have an account? Log in' : 'Need an account? Create one'}
          </button>
        </form>
      </div>
    );
  }

  return <>{children}</>;
}
