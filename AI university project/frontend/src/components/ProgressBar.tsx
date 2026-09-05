interface ProgressBarProps {
  value: number;
  max: number;
  label: string;
  /** Text shown next to the label, e.g. "3 of 5". Defaults to "value/max". */
  detail?: string;
}

/** Accessible progress bar: real role=progressbar semantics plus a visible text
 * equivalent, so progress isn't conveyed by color/width alone. */
export default function ProgressBar({ value, max, label, detail }: ProgressBarProps) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  const detailText = detail ?? `${value}/${max}`;
  return (
    <div className="progress-bar">
      <div className="progress-bar-header">
        <span className="progress-bar-label">{label}</span>
        <span className="progress-bar-detail">{detailText}</span>
      </div>
      <div
        className="progress-bar-track"
        role="progressbar"
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuetext={`${detailText}, ${pct} percent`}
        aria-label={label}
      >
        <div className="progress-bar-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
