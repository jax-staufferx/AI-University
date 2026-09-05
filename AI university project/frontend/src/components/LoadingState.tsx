import { useEffect, useRef, useState } from 'react';

interface LoadingStateProps {
  messages: string[];
  ariaLabel?: string;
}

/** Calm, honest loading state with rotating status text and aria-live for screen readers. */
export default function LoadingState({ messages, ariaLabel = 'Loading' }: LoadingStateProps) {
  const [index, setIndex] = useState(0);
  const liveRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const interval = setInterval(() => {
      setIndex((i) => (i + 1) % messages.length);
    }, 3500);
    return () => clearInterval(interval);
  }, [messages.length]);

  return (
    <div className="loading-state" role="status" aria-live="polite" aria-label={ariaLabel}>
      <div className="loading-pulse" aria-hidden="true" />
      <div className="loading-text" ref={liveRef}>{messages[index]}</div>
    </div>
  );
}
