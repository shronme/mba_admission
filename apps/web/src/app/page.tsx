import { BackendPing } from "@/components/BackendPing";
import { WiringSmoke } from "@/components/WiringSmoke";

export default function HomePage() {
  return (
    <main className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">
        AI Admissions — web scaffold
      </h1>
      <p className="mt-2 text-sm text-neutral-600">
        Real frontend lives in <code className="rounded bg-neutral-100 px-1">apps/web</code> per
        the engineering backlog. Feature slices go under{" "}
        <code className="rounded bg-neutral-100 px-1">src/features/</code>.
      </p>
      <p className="mt-2 text-sm text-neutral-600">
        The in-browser mock at <code className="rounded bg-neutral-100 px-1">/fe/</code> on the API
        is same-origin only; this app uses{" "}
        <code className="rounded bg-neutral-100 px-1">NEXT_PUBLIC_API_URL</code> + CORS.
      </p>
      <div className="mt-8 space-y-6">
        <BackendPing />
        <WiringSmoke />
      </div>
    </main>
  );
}
