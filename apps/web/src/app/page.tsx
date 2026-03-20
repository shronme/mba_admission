import { CandidateDashboard } from "@/components/CandidateDashboard";
import { EmailLoginCard } from "@/components/EmailLoginCard";
import { HomeGate } from "@/components/HomeGate";

export default function HomePage() {
  return (
    <main className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">
        AI Admissions
      </h1>
      
      <div className="mt-8 space-y-8">
        <HomeGate fallback={<EmailLoginCard />} authenticated={<CandidateDashboard />} />
      </div>
    </main>
  );
}
