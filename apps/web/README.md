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

## Deploy on Railway

1. **New service** in the same project → **GitHub repo** (same monorepo as the API).
2. **Settings → Source**
   - **Root Directory:** `apps/web` (critical: Railpack must see `package.json` here).
3. **Settings → Config as code**
   - Point to **`apps/web/railway.toml`** (path from repository root), **or** leave default and set **Builder = Railpack** and **Start Command** manually:
     ```bash
     npm run start -- -p $PORT -H 0.0.0.0
     ```
4. **Variables** (set **before** the first successful build if possible — `NEXT_PUBLIC_*` is baked in at build time):
   - **`NEXT_PUBLIC_API_URL`** = your **FastAPI** service’s public URL (the one where `curl …/health` returns `{"status":"ok"}`), e.g. `https://your-api.up.railway.app`. **Not** the Next.js frontend domain — using the frontend URL causes **404** on `/health`.
   - Optional: `NODE_ENV=production` (often set automatically).
5. **Networking** → generate a **public domain** for the frontend.
6. **API CORS:** on the **FastAPI web** service, set **`CORS_ORIGINS`** to include your **frontend** origin exactly, e.g. `https://your-frontend.up.railway.app` (comma-separate multiple). Redeploy the API after changing it.
7. Deploy the frontend service and open its URL; the home page should load the backend ping if CORS + `NEXT_PUBLIC_API_URL` are correct.

**Monorepo note:** the repo root [`railway.toml`](../railway.toml) is for the **Docker API/worker**. The frontend service must use **`apps/web`** as root + [`railway.toml`](railway.toml) in this folder (Railpack), not the root Docker config.
