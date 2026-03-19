import { CandidateDashboard } from "@/components/CandidateDashboard";
import { EmailLoginCard } from "@/components/EmailLoginCard";
import { HomeGate } from "@/components/HomeGate";

export default function HomePage() {
  return (
    <main className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">
        AI Admissions
      </h1>
      <p className="mt-2 text-sm text-neutral-600">
        Enter your email to load or create your <strong>candidate</strong> record. Diagnostics below
        appear after you continue (same <code className="rounded bg-neutral-100 px-1">NEXT_PUBLIC_API_URL</code>{" "}
        + CORS as before).
      </p>
      <div className="mt-8 space-y-8">
        <HomeGate fallback={<EmailLoginCard />} authenticated={<CandidateDashboard />} />
      </div>
    </main>
  );
}
