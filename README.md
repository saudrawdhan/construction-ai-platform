# Construction Operations Intelligence Platform

A construction company runs on documents: emails, meeting minutes, daily site reports, purchase
requests, RFIs, non-conformance reports, and claims. Most of it never gets read twice. Decisions
get made, forgotten, and re-litigated; a supplier's poor delivery history sits invisible in a
spreadsheet until a project is already late; a claim goes to arbitration and nobody can quickly
assemble the change orders, correspondence, and decisions that support it.

This platform turns that paperwork into something you can query, summarize, and act on. It ingests
real project data, keeps an organizational memory of what was decided and why, runs AI workflows
over the operational record, and answers management's questions — with every AI answer tied back to
the records it came from, and every high-risk action held behind a human approval.

It is built to be run, not just demonstrated: a FastAPI backend, a PostgreSQL/pgvector database
loaded with real bilingual (English/Arabic) construction data, a Redis-backed job scheduler, and a
React dashboard covering thirteen operational areas.

## What it does

**Operational record.** Projects, procurement (purchase requests, orders, suppliers), RFIs and
change orders, claims, meetings, site reports, and a document library — all queryable with
filtering and pagination through the API and the dashboard.

**Six AI workflows**, each combining deterministic computation (where correctness matters) with an
LLM (for judgment and narrative):

- *Purchase Request Review* — flags missing information, scores risk, and factors in the assigned
  supplier's real delivery history.
- *Supplier Risk Assessment* — scores a supplier from cross-project on-time rate, NCRs, and delay
  patterns, and writes the result back as organizational memory.
- *RFI Escalation* — finds overdue RFIs and drafts an escalation with a suggested action per item.
- *Meeting Summary* — turns raw minutes into a summary, owner-assigned action items, decisions, and
  risks, and can persist them.
- *Daily Site Report Analysis* — extracts completed work, delays, risks, and an escalation
  recommendation from a field report.
- *Executive Weekly Report* — aggregates portfolio KPIs and writes an executive narrative.

**Enterprise memory.** A searchable store of decisions, risks, lessons learned, supplier
performance, and more, with source attribution. Workflows both read from it (so a review is informed
by past findings) and write to it (so findings accumulate). A memory-extraction agent turns free
text into categorized, confidence-scored memories.

**Grounded copilot.** A question-answering assistant over the memory and document corpus. It
retrieves evidence first and answers only from it — and when it finds no supporting evidence, it
says so rather than inventing an answer.

**Governance.** JWT authentication, seven-role RBAC, an audit log written on every AI call, and a
human-in-the-loop approval workflow: high-risk actions become approval requests that a manager
approves or rejects, with full history — the AI never executes them on its own.

**Scheduled automations.** A Redis/arq worker runs a daily site digest, an overdue-RFI reminder, a
pending-PR alert, and the weekly executive report on a cron schedule, notifying the right roles. The
worker runs in mock-LLM mode so recurring jobs never consume API quota.

**Document ingestion.** Upload a PDF, Word, or text file and it is parsed, chunked, embedded, and
indexed into the same store the copilot and search use, so it becomes retrievable immediately.

## Architecture at a glance

![Architecture diagram](docs/architecture.svg)

| Layer | Technology |
|---|---|
| Backend API | FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), Alembic |
| Database | PostgreSQL 16 + pgvector (39 tables) |
| Cache / scheduler | Redis 7 + arq worker |
| LLM | Provider-agnostic client; Google Gemini (`gemini-2.5-flash`) by default, deterministic mock adapter for tests and offline dev |
| Embeddings / RAG | `intfloat/multilingual-e5-large` (1024-dim, ONNX via fastembed — no PyTorch) + hybrid pgvector-cosine and Postgres full-text search fused with Reciprocal Rank Fusion |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| Security | JWT auth, RBAC, per-route rate limiting, security headers, audit logging, approval gate |

The backend is layered consistently: Pydantic `schemas` define the API contract, `services` hold the
business logic and database access, and thin `api/v1` routers wire them together. The AI layer lives
in `agents/` (prompts, the copilot, the memory extractor, and one module per workflow) with no
LangChain — the agent loop, retrieval, and memory are all written directly so the behavior is
auditable. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full design and
[docs/SECURITY.md](docs/SECURITY.md) for the security model.

## How the AI is kept reliable

Two ideas run through the whole AI layer:

1. **Deterministic where it counts, LLM where it helps.** Numbers — a supplier's on-time rate, the
   count of overdue RFIs, portfolio KPIs — are computed in Python from the database, not asked of a
   language model. The LLM is used for the parts it is actually good at: reading unstructured text
   and writing prose. A workflow's risk score is arithmetic; its recommendation is generated.

2. **Grounding and provider independence.** Every workflow and copilot answer carries the sources
   and memory records it used. The copilot refuses when it has no evidence. The LLM sits behind a
   small `LLMClient` protocol with two implementations: a real Gemini client (with retry and
   backoff) and a deterministic mock. Tests, local development, and demos default to the mock, so
   they are fully offline and spend zero API quota; switching to a real provider is one environment
   variable.

## Prerequisites

- Docker Desktop (WSL2 backend on Windows)
- Node.js 20+ (only for the frontend)
- A free Google AI Studio API key if you want live LLM output — <https://aistudio.google.com/apikey>.
  Everything runs without one in mock mode.

## Quickstart

```bash
# 1. Configure secrets
cp .env.example .env
# paste your Gemini key into LLM_API_KEY (optional — mock mode needs no key)

# 2. Start the stack: API + PostgreSQL/pgvector + Redis
docker compose up -d --build

# 3. Create the schema
docker compose run --rm api alembic upgrade head
```

`GET http://localhost:8000/health` returns `{"status": "ok"}` once the API can reach both Postgres
and Redis. Interactive API docs are at `http://localhost:8000/docs`.

The demonstration dataset is real construction data and is not included in this repository. The
migrations above create the full schema; with a dataset present under `data/`, the loader scripts
populate it:

```bash
docker compose run --rm api python -m scripts.import_dataset       # ETL from the source dump
docker compose run --rm api python -m scripts.seed_supplemental    # RFIs + planned activities
docker compose run --rm api python -m scripts.seed_users           # the seven role accounts
docker compose run --rm api python -m scripts.ingest_documents     # embed the document corpus
```

### Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

### Seeded logins

All accounts use the password `Passw0rd!`.

| Email | Role | Can do |
|---|---|---|
| `admin@construction-ops.com` | admin | everything |
| `executive@construction-ops.com` | executive | reports, approvals, audit, supplier risk |
| `pm@construction-ops.com` | project_manager | projects, RFIs, meetings, approvals |
| `engineer@construction-ops.com` | site_engineer | site reports, RFIs |
| `procurement@construction-ops.com` | procurement_officer | procurement, supplier risk |
| `qaqc@construction-ops.com` | qa_qc | meetings, memory |
| `viewer@construction-ops.com` | viewer | read-only |

## Testing and quality

```bash
docker compose run --rm -e TESTING=1 api pytest -q   # 106 tests, offline, deterministic
docker compose run --rm api ruff check app scripts tests
```

`TESTING=1` selects the mock LLM and a dependency-free hash embedder, and runs each test inside a
transaction that is rolled back afterward, so the suite never touches a real API or leaves data
behind.

## Repository layout

```
construction-ai-platform/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app, middleware, health check
│   │   ├── config.py          # environment-driven settings
│   │   ├── api/v1/            # versioned routers (one per domain)
│   │   ├── models/            # SQLAlchemy ORM models by domain
│   │   ├── schemas/           # Pydantic request/response contracts
│   │   ├── services/          # business logic and data access
│   │   ├── agents/            # prompts, copilot, memory extractor, workflows/
│   │   ├── worker/            # arq scheduled automations
│   │   ├── security/          # auth, roles, rate limiting
│   │   └── database/          # engine, session, redis
│   ├── scripts/               # ETL, seeding, ingestion, QA checks
│   ├── tests/
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/                  # React + TypeScript dashboard (13 pages)
├── docs/                      # ARCHITECTURE, SECURITY, DEMO
├── docker-compose.yml
└── README.md
```

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — system design, data flow, the AI subsystem, and the
  reasoning behind the main decisions.
- [docs/SECURITY.md](docs/SECURITY.md) — authentication, the RBAC matrix, rate limiting, audit,
  governance, and known trade-offs.
- [docs/DEMO.md](docs/DEMO.md) — a scripted end-to-end walkthrough for a live demonstration.
