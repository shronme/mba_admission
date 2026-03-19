# Web app (`apps/web`)

Real frontend scaffold aligned with the backlog: **Next.js (App Router)**, **TypeScript**, **Tailwind**, **TanStack Query**.

## Layout

- `src/app/` — routes, layout, global styles
- `src/components/` — shared UI
- `src/features/` — product slices (`chat`, `profile`, …) — add routes/components as you build
- `src/lib/` — API helpers (`NEXT_PUBLIC_API_URL`)

## Run locally

1. Start the API (e.g. `uvicorn` or `docker compose` on port **8000**).
2. Configure the browser-visible API URL:

   ```bash
   cp .env.example .env.local
   # edit NEXT_PUBLIC_API_URL if needed (default http://localhost:8000)
   ```

3. Install and dev:

   ```bash
   cd apps/web
   npm install
   npm run dev
   ```

4. Open [http://localhost:3000](http://localhost:3000). The home page calls `GET /health` via TanStack Query.

**CORS:** the FastAPI app allows origins from `CORS_ORIGINS` (defaults include `http://localhost:3000`). For production, set `CORS_ORIGINS` to your deployed web origin.

## vs `/fe/` mock

- **`/fe/`** on the API = static HTML served by FastAPI (same origin, quick smoke).
- **`apps/web`** = real SPA/SSR app; uses `NEXT_PUBLIC_API_URL` and CORS.
