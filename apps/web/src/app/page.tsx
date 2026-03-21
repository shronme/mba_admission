import { CandidateDashboard } from "@/components/CandidateDashboard";
import { EmailLoginCard } from "@/components/EmailLoginCard";
import { HomeGate } from "@/components/HomeGate";

export default function HomePage() {
  return (
    <HomeGate
      fallback={
        <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 px-4">
          <div className="mb-8 text-center">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              GradAdvisor
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              US Graduate Admissions Consultant
            </p>
          </div>
          <div className="w-full max-w-sm">
            <EmailLoginCard />
          </div>
        </div>
      }
      authenticated={<CandidateDashboard />}
    />
  );
}
