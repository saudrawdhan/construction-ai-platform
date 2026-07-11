# Architecture

This document explains how the platform is put together and why the main decisions were made. It
assumes you have read the [README](../README.md).

![Architecture diagram](architecture.svg)

## Shape of the system

There are three running processes and two data stores:

- **API** — a FastAPI application (uvicorn) that serves the REST API and the OpenAPI docs.
- **Worker** — an arq process that runs scheduled jobs against the same database.
- **Frontend** — a React single-page app that talks to the API over HTTP.
- **PostgreSQL 16 + pgvector** — the operational database and the vector store, in one place.
- **Redis 7** — backs the arq job queue and the rate limiter.

Keeping the vectors in Postgres rather than a separate vector database is a deliberate choice. The
data is relational — an embedding always belongs to a document that belongs to a project — and
having one store means one transaction, one backup, and one consistency model. pgvector handles the
similarity search and Postgres's own full-text search handles keyword matching; there was no reason
to add a second system.

## Backend layering

Every feature is built the same way, which makes the codebase predictable:

```
api/v1/<domain>.py     thin router: HTTP, auth dependency, status codes
     │
services/<domain>.py   business logic and all database access
     │
models/<domain>.py     SQLAlchemy ORM
schemas/<domain>.py     Pydantic request/response contracts (the API's shape)
```

Routers do almost nothing except declare the endpoint, its role requirement, and its response model,
then call a service. Services contain the queries and the rules. Schemas are separate from models on
purpose: the database shape and the API shape are allowed to diverge, and the API never leaks an ORM
object directly.

Cross-cutting pieces:

- `api/deps.py` and `security/deps.py` provide the `DbSession` and `CurrentUser` dependencies and the
  `require_roles(...)` guard.
- `main.py` adds CORS, a security-headers middleware, and a handler that turns database integrity
  violations into clean `409 Conflict` responses instead of 500s.
- `config.py` is a single Pydantic `Settings` object read from environment variables, so the same
  code runs locally, in Docker, and in CI by changing configuration only.

## Database

Thirty-nine tables, created and versioned through Alembic migrations. They are grouped by domain:
organization and users; projects and their milestones/risks/issues/decisions; procurement
(suppliers, evaluations, purchase requests and orders, material categories); subcontractors;
execution (site reports, daily and planned activities); technical (RFIs, change orders, NCRs, safety
events); commercial (claims, evidence, correspondence); meetings and action items; documents and
embeddings; the AI layer (conversations, messages, memories, recommendations, summaries, audit
logs); and governance (approvals, approval history, notifications).

Two columns are `vector(1024)`: `ai_memories.embedding` and `document_embeddings.embedding`. Both
have an HNSW cosine index for approximate nearest-neighbour search, and both have a GIN full-text
index so keyword queries use the index rather than scanning. Money is `NUMERIC(16,2)`, dates are
real `DATE` columns, and foreign keys and status/date columns are indexed.

The dataset is bilingual (English and Arabic) and reflects a Saudi construction context. The source
data arrived as a SQLite-dialect dump, so the schema and ETL were built to load it into PostgreSQL
faithfully — the loader verifies row-count parity, date null-parity, money-sum parity, and foreign-
key integrity against the source before the data is trusted.

## AI subsystem

The AI code lives under `app/agents/` and the services that support it under `app/services/`. There
is no orchestration framework; the pieces are small enough to read directly.

### Provider abstraction

`services/llm.py` defines an `LLMClient` protocol with two implementations. `OpenAICompatLLM` talks
to Gemini through its OpenAI-compatible endpoint over httpx, with exponential backoff on transient
5xx errors and a typed quota error on 429. `MockLLM` returns deterministic responses and valid JSON
in JSON mode. `get_llm()` returns the mock whenever `TESTING` is set and otherwise the configured
provider. The effect is that the entire system is exercised offline and for free in tests and demos,
and a real provider is one setting away.

Embeddings follow the same pattern in `services/embeddings.py`: a `HashEmbedder` (deterministic,
dependency-free, used in tests) and a `FastEmbedEmbedder` that runs `intfloat/multilingual-e5-large`
as ONNX through fastembed — chosen so the container needs no PyTorch and so Arabic and English embed
into the same space.

### Retrieval

`services/retrieval.py` implements hybrid search. A query is embedded and run as a cosine
nearest-neighbour search over `document_embeddings`; the same query text is run through Postgres
full-text search; the two ranked lists are combined with Reciprocal Rank Fusion. Vector search finds
semantically related passages and crosses the language boundary; full-text search nails exact tokens
like a PO number or a change-order reference. RRF merges them without having to reconcile score
scales. Long documents are chunked with overlap so context is not cut mid-sentence.

### Memory

The memory layer (`services/memory.py`, `agents/memory_extractor.py`) is the feature that makes the
platform accumulate knowledge rather than just answer one-off questions. Memories are categorized
(decision, risk, issue, lesson learned, supplier performance, procurement blocker, safety event,
client instruction), embedded on write, and searched with the same hybrid approach over their
summaries. Superseded memories are excluded from search so corrections take effect. The extraction
agent turns free text into categorized, confidence-scored memories using the memory-extraction
prompt. Workflows read relevant memory before they run and write findings back after — a supplier
risk assessment is informed by prior supplier-performance memories and produces a new one.

### Workflows

Each of the six workflows (`agents/workflows/`) follows the same contract: compute the facts
deterministically, use the LLM for judgment and wording, attach the sources and memory used, write
an audit-log entry, and — in mock mode — behave deterministically so it can be tested. Workflows are
advisory: they recommend and draft, they do not execute. Anything with real-world consequence goes
through the approval gate.

### Copilot

The copilot (`agents/copilot.py`) answers questions over memory and the document corpus. The hard
part is refusing gracefully when there is no evidence, because pure vector search always returns a
nearest neighbour and so can never say "I don't know". The solution is to gate grounding on keyword
matching: substantive terms are extracted from the question (stopwords dropped, Arabic preserved) and
run as a full-text query; if nothing matches, the copilot refuses without calling the LLM at all.
When there is evidence, it is passed to the LLM under a system prompt that also instructs it to flag
anything the evidence does not cover.

## Governance

Governance is not a feature bolted on the side; it is wired through the AI layer. Every AI call —
workflow, copilot, or extraction — writes an `ai_audit_logs` row with the workflow name, provider,
model, source ids, and an output excerpt, exposed through `GET /audit/ai-outputs` to admins and
executives. High-risk actions are never performed by the AI: they are created as approval requests
that a manager approves or rejects, each transition recorded in approval history and notified to the
requester. This directly implements the brief's requirement that high-risk AI actions have a human
in the loop.

## Scheduled automations

The `app/worker/` package holds the scheduled jobs as plain async functions that take a database
session, which makes them unit-testable without the cron runtime. The arq `WorkerSettings` registers
them on a schedule (daily site digest at 06:00, overdue-RFI reminder at 07:00, pending-PR alert at
07:30, weekly executive report Monday 08:00). Each opens a session, aggregates, writes an
`ai_summary` and role-targeted notifications, and commits. The worker container runs with the LLM
provider forced to mock, so a job that fires every morning never spends API quota.

## Frontend

The frontend is a React + TypeScript SPA built with Vite and styled with Tailwind. A small typed API
client holds the JWT and centralizes error handling; a set of UI primitives (cards, tables, badges,
modals, tabs, pagination) keeps every page consistent. Fifteen pages cover the dashboard, projects,
procurement, RFIs, claims, change orders, meetings, site reports, documents, reports, copilot,
approvals, memory, audit, and user management, with create/edit/delete forms, CSV/Excel import, an
in-app notifications bell, and a per-project workspace layered across them. Role-based visibility is
enforced in the UI (action buttons appear only for roles that can use them) on top of the server-side
RBAC, which remains the actual authority.

## Testing strategy

The suite runs against a real PostgreSQL instance for fidelity, but each test gets its own connection
and an outer transaction that is rolled back at teardown; the application's own commits become
savepoints, so nothing persists between tests. Under `TESTING` the mock LLM and hash embedder make
everything deterministic and offline. This is why the 103-test suite can cover real database
behavior, AI workflows, and RBAC without a network call or any cleanup.

## Notable decisions

- **No LangChain.** The agent loop, retrieval, memory, and workflows are written directly. For a
  system whose selling point is auditable, grounded AI, being able to read exactly what happens on
  every call was worth more than the convenience of a framework.
- **Mock-first AI.** Making the deterministic mock the default for tests and dev — rather than an
  afterthought — is what makes the project cheap to develop against a low-quota free tier and safe to
  demo repeatedly.
- **One database.** Relational data and vectors together in Postgres, rather than a separate vector
  store, keeps consistency and operations simple.
- **Deterministic core, generative surface.** Keeping the numbers in code and the prose in the model
  is the single biggest reason the AI output is trustworthy.
