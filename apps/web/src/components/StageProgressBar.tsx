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

function CheckIcon() {
  return (
    <svg
      className="h-3.5 w-3.5"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2.5}
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
    </svg>
  );
}

export function StageProgressBar({ currentStage }: Props) {
  const idx = Math.max(0, Math.min(currentStage - 1, STAGES.length - 1));
  const stage = STAGES[idx];
  const progressRatio = (currentStage - 1) / (STAGES.length - 1);

  return (
    <div className="stage-bar">
      {/* Label row */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span className="text-[10px] font-semibold uppercase tracking-widest text-neutral-600">
            Stage
          </span>
          <span className="stage-name-badge">{stage.name}</span>
        </div>
        <span className="text-xs text-neutral-600">
          Step {currentStage} of {STAGES.length}
        </span>
      </div>

      {/* Step circles + labels */}
      <div className="relative">
        <div className="stage-track" />
        <div
          className="stage-progress-fill"
          style={{ width: `calc(${progressRatio} * (100% - 7px))` }}
        />

        <div className="flex justify-between">
          {STAGES.map((s, i) => {
            const stepNum = i + 1;
            const isCompleted = stepNum < currentStage;
            const isCurrent = stepNum === currentStage;

            const stepClass = isCompleted
              ? "stage-step stage-step-completed"
              : isCurrent
                ? "stage-step stage-step-current"
                : "stage-step stage-step-pending";

            const labelClass = isCurrent
              ? "stage-label stage-label-current"
              : isCompleted
                ? "stage-label stage-label-completed"
                : "stage-label stage-label-pending";

            return (
              <div key={s.name} className="relative z-10 flex flex-col items-center gap-1.5">
                <div className={stepClass}>
                  {isCompleted ? <CheckIcon /> : stepNum}
                </div>
                <span className={labelClass}>{s.short}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Stage description */}
      <p className="stage-description">{stage.description}</p>
    </div>
  );
}
