"use client";

type Props = {
  score: number;       // 0–100
  complete: boolean;
};

export function IntakeProgressBar({ score, complete }: Props) {
  const pct = Math.min(100, Math.max(0, score));

  const barColor = complete
    ? "bg-emerald-500"
    : pct >= 75
      ? "bg-sky-500"
      : pct >= 40
        ? "bg-sky-400"
        : "bg-neutral-300";

  const label = complete
    ? "Intake complete"
    : `Intake ${pct}% complete`;

  return (
    <div className="px-4 py-2 border-b border-neutral-100">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium text-neutral-500">{label}</span>
        {complete && (
          <span className="text-xs font-semibold text-emerald-600">✓ Ready for research</span>
        )}
      </div>
      <div className="h-1.5 w-full rounded-full bg-neutral-100 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${barColor}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
