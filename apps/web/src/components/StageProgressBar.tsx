"use client";

const STAGES = [
  {
    name: "Intake & Discovery",
    short: "Intake",
    description: "Understanding your background, goals, and aspirations.",
  },
  {
    name: "Diagnosis",
    short: "Diagnosis",
    description: "Evaluating your profile strengths and gaps.",
  },
  {
    name: "Program Research",
    short: "Research",
    description: "Identifying the best programs for your goals.",
  },
  {
    name: "Strategy",
    short: "Strategy",
    description: "Crafting your overall application strategy.",
  },
  {
    name: "Narrative",
    short: "Narrative",
    description: "Developing your personal story and key themes.",
  },
  {
    name: "School List",
    short: "Schools",
    description: "Finalizing your target school list.",
  },
  {
    name: "Application Work",
    short: "Applications",
    description: "Building and refining your applications.",
  },
  {
    name: "Iteration",
    short: "Iteration",
    description: "Reviewing and improving your materials.",
  },
  {
    name: "Interview Preparation",
    short: "Interviews",
    description: "Preparing for admissions interviews.",
  },
] as const;

export type ConsultancyStage = (typeof STAGES)[number]["name"];

export { STAGES };

type Props = {
  /** 1-indexed current stage number */
  currentStage: number;
};

export function StageProgressBar({ currentStage }: Props) {
  const idx = Math.max(0, Math.min(currentStage - 1, STAGES.length - 1));
  const stage = STAGES[idx];
  const progressRatio = (currentStage - 1) / (STAGES.length - 1);

  return (
    <div className="border-t border-slate-800 px-6 pb-4 pt-4">
      {/* Label row */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
            Current Stage
          </span>
          <span className="rounded-full bg-indigo-600 px-3 py-0.5 text-xs font-semibold text-white">
            {stage.name}
          </span>
        </div>
        <span className="text-xs text-slate-500">
          Step {currentStage} of {STAGES.length}
        </span>
      </div>

      {/* Step circles + labels */}
      <div className="relative">
        {/* Track */}
        <div className="absolute left-3.5 right-3.5 top-3.5 h-px bg-slate-700" />
        {/* Progress */}
        <div
          className="absolute left-3.5 top-3.5 h-px bg-indigo-600 transition-all duration-500"
          style={{ width: `calc(${progressRatio} * (100% - 7px))` }}
        />

        <div className="flex justify-between">
          {STAGES.map((s, i) => {
            const stepNum = i + 1;
            const isCompleted = stepNum < currentStage;
            const isCurrent = stepNum === currentStage;

            return (
              <div key={s.name} className="relative z-10 flex flex-col items-center gap-1.5">
                <div
                  className={[
                    "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold transition-all",
                    isCompleted
                      ? "bg-indigo-600 text-white"
                      : isCurrent
                        ? "bg-indigo-600 text-white ring-4 ring-indigo-500/30"
                        : "bg-slate-700 text-white",
                  ].join(" ")}
                >
                  {isCompleted ? (
                    <svg
                      className="h-3.5 w-3.5"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2.5}
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                  ) : (
                    stepNum
                  )}
                </div>
                <span
                  className={[
                    "w-14 text-center text-[9px] leading-tight",
                    isCurrent
                      ? "font-semibold text-indigo-400"
                      : isCompleted
                        ? "text-slate-400"
                        : "text-white",
                  ].join(" ")}
                >
                  {s.short}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Stage description */}
      <p className="mt-2 text-[11px] text-slate-500">{stage.description}</p>
    </div>
  );
}
