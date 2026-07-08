# Deployment

The platform is Docker-first, so a deployment is the same containers you run locally with
production settings applied. This directory holds a production Compose file; the notes below cover
what changes when you move off a developer laptop.

## What differs from local

The root `docker-compose.yml` is tuned for development: it mounts the source tree and runs the API
with `--reload`. `docker-compose.prod.yml` here instead builds the image, runs multiple uvicorn
workers without reload, sets `restart: unless-stopped`, turns debug off, and passes
`--proxy-headers` so the API sees the real client address behind a TLS terminator.

## Bring it up

```bash
# from the repository root
docker compose -f deployment/docker-compose.prod.yml --env-file .env up -d --build
docker compose -f deployment/docker-compose.prod.yml run --rm api alembic upgrade head
```

Then load data with the same `scripts.*` commands documented in the root README, if you are
seeding from the dataset.

## Configuration and secrets

Everything sensitive comes from the environment, never the image:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | async Postgres DSN (`postgresql+asyncpg://…`) |
| `REDIS_URL` | Redis DSN |
| `JWT_SECRET` | token signing key — must be a strong 32+ byte value in production |
| `POSTGRES_PASSWORD` | database password (required, no default) |
| `LLM_PROVIDER` | `gemini` for live AI, `mock` for offline |
| `LLM_API_KEY` | provider key, only needed when `LLM_PROVIDER` is not `mock` |
| `CORS_ORIGINS` | comma-separated allow-list of frontend origins |

On a managed host, supply these through the platform's secret store rather than a committed file.
The same code path reads them either way.

## TLS and the reverse proxy

The API does not terminate TLS. Put it behind a reverse proxy or load balancer (nginx, Caddy, an
ALB, or a platform ingress) that terminates HTTPS and forwards to port 8000. Two things to configure
there:

- Add HSTS at the proxy; the application already sends the other hardening headers.
- Forward `X-Forwarded-For`. The API runs with `--proxy-headers`, so with a trusted proxy the rate
  limiter and logs will see the real client IP instead of the proxy's.

## The worker

The `worker` service runs the arq scheduler (daily site digest, overdue-RFI reminder, pending-PR
alert, weekly executive report). It is deployed with `LLM_PROVIDER=mock` so the recurring jobs are
deterministic and never spend API quota. Run a single worker replica — the cron schedule is defined
once in `app/worker/settings.py`.

## Frontend

Build the static assets and serve them from any static host or the same reverse proxy:

```bash
cd frontend
npm ci
VITE_API_URL="https://your-api-host/api/v1" npm run build   # emits frontend/dist
```

## Scaling notes

The API is stateless, so it scales horizontally behind the proxy; run more replicas or raise
`--workers`. Rate-limit counters live in the shared Redis, so limits apply across all replicas. The
database is the one stateful component — use a managed Postgres with pgvector, or back up the
`pgdata` volume. The embedding model is cached in the `models` volume and downloaded once on first
ingest.
