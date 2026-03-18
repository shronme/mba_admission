# Deploy to Railway

This repo is set up so Railway can build one image from [backend/Dockerfile](/Users/shronme/development/mba_admission/backend/Dockerfile) and run it in either API or worker mode.

## Prerequisites

- Push the repo to GitHub.
- Create a Railway account and connect the GitHub repo.

## Services to create

Create four Railway services in the same project:

1. `api` from this repo
2. `worker` from this repo
3. `postgres` using Railway Postgres
4. `redis` using Railway Redis

The repo includes [railway.json](/Users/shronme/development/mba_admission/railway.json), so Railway will use `backend/Dockerfile` automatically from the repository root build context.

## Configure the API service

Set these variables on the `api` service:

- `APP_ROLE=api`
- `DATABASE_URL=<reference the Railway Postgres connection string>`
- `REDIS_URL=<reference the Railway Redis connection string>`

Then:

- Enable public networking.
- Set the health check path to `/health`.

The API will start with:

```bash
uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
```

## Configure the worker service

Set these variables on the `worker` service:

- `APP_ROLE=worker`
- `DATABASE_URL=<reference the Railway Postgres connection string>`
- `REDIS_URL=<reference the Railway Redis connection string>`

Then:

- Leave public networking disabled.

The worker will start with:

```bash
python -m app.worker
```

## Verify the deployment

After the `api` service deploys, open:

```text
https://<your-api-domain>/health
```

Expected response:

```json
{"status":"ok","service":"api"}
```

## Notes

- The same Docker image is used for both `api` and `worker`; `APP_ROLE` selects the process.
- Local development topology remains defined in [docker-compose.yml](/Users/shronme/development/mba_admission/docker-compose.yml).
- The Railway-first platform decision is documented in [infra/adr/ADR-001-railway-first-deployment.md](/Users/shronme/development/mba_admission/infra/adr/ADR-001-railway-first-deployment.md).
