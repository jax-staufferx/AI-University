import { Link, useLocation } from 'react-router-dom';
import { useEffect, useState, type ReactNode } from 'react';
import { useTheme } from '../theme';
import { listProposals } from '../api';

export default function Layout({ children }: { children: ReactNode }) {
  const { theme, toggleTheme, textSize, setTextSize } = useTheme();
  const location = useLocation();
  const [pendingCount, setPendingCount] = useState(0);

  useEffect(() => {
    listProposals()
      .then((p) => setPendingCount(p.length))
      .catch(() => {});
  }, [location.pathname]);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-inner">
          <Link to="/" className="brand" aria-label="Learning Agent — home">
            <span className="brand-mark" aria-hidden="true">◐</span>
            <span className="brand-name">Learning Agent</span>
          </Link>
          <nav className="topbar-nav" aria-label="Main navigation">
            <Link to="/" className={`nav-link ${location.pathname === '/' ? 'active' : ''}`}>
              Topics
            </Link>
            <Link to="/insights" className={`nav-link ${location.pathname === '/insights' ? 'active' : ''}`}>
              Insights
              {pendingCount > 0 && (
                <span className="quiet-badge" aria-label={`${pendingCount} pending proposals`}>
                  {pendingCount}
                </span>
              )}
            </Link>
            <div className="text-size-control" role="group" aria-label="Reading text size">
              {(['small', 'medium', 'large', 'xlarge'] as const).map((size) => (
                <button
                  key={size}
                  className={`size-btn ${textSize === size ? 'active' : ''}`}
                  onClick={() => setTextSize(size)}
                  aria-label={`${size} text size`}
                  aria-pressed={textSize === size}
                >
                  {size === 'small' ? 'S' : size === 'medium' ? 'M' : size === 'large' ? 'L' : 'XL'}
                </button>
              ))}
            </div>
            <button
              className="theme-toggle"
              onClick={toggleTheme}
              aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
            >
              {theme === 'light' ? '☾' : '☀'}
            </button>
          </nav>
        </div>
      </header>
      <main className="main-content">
        {children}
      </main>
    </div>
  );
}
