"use client";

type Props = {
  score: number;       // 0–100
  complete: boolean;
};

export function IntakeProgressBar({ score, complete }: Props) {
  const pct = Math.min(100, Math.max(0, score));

  const barColor = complete
    ? "intake-bar-complete"
    : pct >= 75
      ? "intake-bar-high"
      : pct >= 40
        ? "intake-bar-mid"
        : "intake-bar-low";

  const label = complete
    ? "Intake complete"
    : `Intake ${pct}% complete`;

  return (
    <div className="intake-bar-container">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium text-neutral-500">{label}</span>
        {complete && (
          <span className="intake-complete-label">✓ Ready for research</span>
        )}
      </div>
      <div className="intake-bar-track">
        <div
          className={`intake-bar-fill ${barColor}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
