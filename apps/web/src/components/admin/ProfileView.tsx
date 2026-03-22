"use client";

type ProfileAttributes = Record<string, unknown>;

const CANDIDATE_ATTRIBUTES: Array<{ key: string; label: string; icon: string; description: string }> = [
  { key: "core_identity", label: "Core Identity", icon: "👤", description: "Who they are as a leader or builder" },
  { key: "domain_base", label: "Domain & Background", icon: "🏢", description: "Professional domain, industry, seniority" },
  { key: "core_strengths", label: "Core Strengths", icon: "💪", description: "Key strengths with evidence" },
  { key: "differentiation_layer", label: "Differentiation", icon: "✨", description: "Personal resilience, values, unique experience" },
  { key: "intellectual_working_style", label: "Working Style", icon: "🧠", description: "Analytical style and decision-making approach" },
  { key: "motivation", label: "Motivation", icon: "🎯", description: "Authentic reason for pursuing their degree now" },
  { key: "core_tension", label: "Core Tension", icon: "⚡", description: "Gap between current position and target goal" },
  { key: "transferable_assets", label: "Transferable Assets", icon: "🔄", description: "Skills transferable to target field" },
  { key: "risks", label: "Profile Risks", icon: "⚠️", description: "Honest credibility gaps or weaknesses" },
];

const SYNTHESIZED_ATTRIBUTES: Array<{ key: string; label: string; icon: string; description: string }> = [
  { key: "strategy", label: "Strategy", icon: "🗺️", description: "Recommended application strategy" },
  { key: "narrative_direction", label: "Narrative Direction", icon: "📖", description: "Through-line narrative arc" },
  { key: "key_positioning", label: "Key Positioning", icon: "📍", description: "1-2 sentence positioning statement" },
  { key: "emphasis_areas", label: "Emphasis Areas", icon: "🔍", description: "What to amplify in essays and interviews" },
  { key: "downplay_areas", label: "Downplay Areas", icon: "🔇", description: "What to de-emphasize" },
];

function renderValue(value: unknown): React.ReactNode {
  if (value === null || value === undefined) return null;

  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-neutral-400 italic text-xs">None</span>;
    return (
      <div className="flex flex-wrap gap-1.5 mt-1">
        {value.map((item, i) => (
          <span
            key={i}
            className="inline-flex items-center rounded-full bg-indigo-50 px-2.5 py-0.5 text-xs font-medium text-indigo-700 ring-1 ring-indigo-100"
          >
            {String(item)}
          </span>
        ))}
      </div>
    );
  }

  if (typeof value === "object") {
    return (
      <div className="mt-1 space-y-1">
        {Object.entries(value as Record<string, unknown>).map(([k, v]) => (
          <div key={k} className="flex gap-2 text-xs">
            <span className="font-medium text-neutral-500 capitalize">{k.replace(/_/g, " ")}:</span>
            <span className="text-neutral-700">{String(v)}</span>
          </div>
        ))}
      </div>
    );
  }

  return <p className="mt-1 text-sm text-neutral-700 leading-relaxed">{String(value)}</p>;
}

function AttributeCard({
  icon,
  label,
  description,
  value,
  missing,
}: {
  icon: string;
  label: string;
  description: string;
  value: unknown;
  missing: boolean;
}) {
  return (
    <div
      className={`rounded-lg border p-4 ${
        missing
          ? "border-neutral-200 bg-neutral-50"
          : "border-neutral-200 bg-white"
      }`}
    >
      <div className="flex items-start gap-2.5">
        <span className="text-base leading-none mt-0.5">{icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">{label}</h4>
            {missing && (
              <span className="text-[10px] text-neutral-400 italic">Not yet gathered</span>
            )}
          </div>
          {!missing ? renderValue(value) : (
            <div className="mt-1 h-2 w-3/4 rounded bg-neutral-200" />
          )}
        </div>
      </div>
    </div>
  );
}

function Section({
  title,
  subtitle,
  attrs,
  attributes,
}: {
  title: string;
  subtitle: string;
  attrs: typeof CANDIDATE_ATTRIBUTES;
  attributes: ProfileAttributes;
}) {
  return (
    <div>
      <div className="mb-3">
        <h3 className="text-sm font-semibold text-neutral-800">{title}</h3>
        <p className="text-xs text-neutral-500">{subtitle}</p>
      </div>
      <div className="grid grid-cols-1 gap-3">
        {attrs.map((attr) => {
          const value = attributes[attr.key];
          const missing =
            value === null ||
            value === undefined ||
            (Array.isArray(value) && value.length === 0) ||
            value === "";
          return (
            <AttributeCard
              key={attr.key}
              icon={attr.icon}
              label={attr.label}
              description={attr.description}
              value={value}
              missing={missing}
            />
          );
        })}
      </div>
    </div>
  );
}

type Props = {
  profile: {
    headline: string | null;
    summary: string | null;
    attributes: ProfileAttributes;
    profile_complete: boolean;
    completeness_score: number;
  } | null;
};

export function ProfileView({ profile }: Props) {
  if (!profile) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-neutral-400">
        No profile data yet.
      </div>
    );
  }

  const { headline, summary, attributes, profile_complete, completeness_score } = profile;
  const pct = Math.max(0, Math.min(100, completeness_score));
  const barColor =
    pct >= 80 ? "bg-emerald-500" : pct >= 50 ? "bg-amber-400" : "bg-rose-400";

  return (
    <div className="space-y-6">
      {/* Header card */}
      <div className="rounded-lg border border-neutral-200 bg-white p-5">
        {headline && (
          <h2 className="text-base font-semibold text-neutral-900">{headline}</h2>
        )}
        {summary && (
          <p className="mt-1.5 text-sm text-neutral-600 leading-relaxed">{summary}</p>
        )}
        <div className="mt-4 flex items-center gap-3">
          <div className="flex-1">
            <div className="mb-1 flex items-center justify-between">
              <span className="text-xs font-medium text-neutral-500">Profile completeness</span>
              <span className="text-xs font-semibold text-neutral-700">{pct}%</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-neutral-200">
              <div
                className={`h-full rounded-full transition-all ${barColor}`}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
          {profile_complete && (
            <span className="shrink-0 rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-700">
              Complete
            </span>
          )}
        </div>
      </div>

      {/* Candidate attributes */}
      <Section
        title="Candidate Input"
        subtitle="Gathered through the intake interview"
        attrs={CANDIDATE_ATTRIBUTES}
        attributes={attributes}
      />

      {/* Synthesized attributes */}
      <Section
        title="AI Synthesis"
        subtitle="Generated by the profile agent"
        attrs={SYNTHESIZED_ATTRIBUTES}
        attributes={attributes}
      />
    </div>
  );
}
