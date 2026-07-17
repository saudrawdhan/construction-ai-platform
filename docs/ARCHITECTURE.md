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

`services/llm.py` defines an `LLMClient` protocol so no agent or workflow depends on a concrete
model. `OpenAICompatLLM` speaks the OpenAI chat format over httpx — with exponential backoff on
transient 5xx errors and a typed quota error on 429 — which lets one adapter serve any compatible
engine: an open-weights model running locally through Ollama, or a hosted API such as Groq, Gemini,
or OpenAI. `MockLLM` returns deterministic responses and valid JSON in JSON mode. The engine is
selected by `LLM_PROVIDER`, with the endpoint and model resolved from a per-provider preset unless
overridden; `get_llm()` returns the mock whenever `TESTING` is set and otherwise the configured
provider. Because the platform computes every figure deterministically and asks the model only to
read text and produce prose or JSON, a compact local model is sufficient — so a construction company
can run the system entirely on its own hardware with no per-call cost and no data leaving the
network, or point it at a cloud API, by changing one setting.

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

Raw RRF ranks purely by retrieval-channel rank position, so two memories with similar textual
relevance but very different confidence would otherwise rank as equals — a live audit test proved
a poorly-attested finding could outrank a well-attested one this way. `search_memories` reranks its
RRF candidates by relevance weighted toward confidence (an unrated memory is treated as moderately
trustworthy, not penalized) before truncating to the requested count; the score returned to the
caller stays the raw relevance value, with confidence surfaced separately per result.

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

### Agent

The workflows and copilot can be invoked directly; the agent (`agents/core.py`) is a single
reasoning layer that sits above all of them and decides what to invoke. It is not a set of
task-specific mini-agents — one `ConstructionAgent` carries the same memory, the same skill
library, and the same reasoning loop into every goal, and its tool registry
(`agents/tools.py`) spans all six AI workflows plus retrieval and direct read-only lookups over
projects, claims, change orders, and safety events, so the same agent that assesses a supplier's
risk can also summarize a meeting, review a purchase request, analyze a site report, or total a
project's open claims — whichever the goal calls for. Extending the agent's reach is a matter of
registering another tool, not building a parallel agent.

Every run begins by consulting enterprise memory for related findings, so the agent reasons from
what the organization already knows rather than from the goal alone. It then runs a reason-act
loop: on each turn it selects a tool, executes it, and reads the observation, repeating until it
can answer or a step budget is reached. In mock mode a deterministic planner routes by intent, so
the loop is fully testable and offline; with a real provider the model chooses each step —
including recovering when a path is blocked, by trying a different tool rather than stopping. A
repeated-action guard stops the loop if the planner proposes an action it has already taken, and
the whole trajectory is persisted to `agent_runs` and the audit log. A smaller model does not
always act on every instruction embedded in a goal — for example, an explicit "please remember
this" was observed not to reliably trigger the `remember` tool on its own. Rather than depend on
prompting alone for that specific case, the run checks afterward whether the goal asked to persist
something and the planner never called `remember`, and if so calls it deterministically with the
user's own words. This mirrors the initial grounding step: a safe, additive action is guaranteed
rather than merely hoped for, while every tool that can change something governed — approve a
purchase request, escalate an RFI — stays entirely planner- and role-gated, never forced.

The same principle extends to the read-only lookup tools (`get_claims`, `get_change_orders`,
`get_safety_events`): none carry a role restriction or a side effect, so a goal whose deterministic
routing (`_analysis_route`) matches one of them, but whose trajectory never called it, gets it
called directly rather than trusting the planner. A live test proved this matters on real data — a
direct safety question was answered "no recent incidents" from memory grounding alone while a real
high-severity event sat on record, the same class of miss originally found for `assess_supplier_risk`
now recurring on a new tool. Their result is also never handed to the LLM to re-narrate: a separate
live test found the model can invent a different figure for one line item while silently dropping
another from its own sum when asked to summarize several named records with a total, identically
across repeated runs even with an explicit system-prompt instruction not to recompute. A goal
answered entirely by tools in this set therefore returns their computed observations directly as
the final answer — the same "deterministic computation stays authoritative" principle already
applied to risk scoring in `pr_review.py`, now applied to what the agent is allowed to say about a
number it did not compute itself.

**Conversation continuity.** Every run belongs to a conversation (the same `ai_conversations` table
the copilot uses), new or continued by passing back the id the previous turn returned. A follow-up
that omits a project defaults to the one the conversation is already scoped to, and the last few
turns are summarized into the planner's prompt, so a goal like "what about its delivery history"
resolves against what was actually just discussed instead of being planned as if nothing had
happened before it. Recall is additionally user-aware in a narrow, deliberate sense:
`recall_past_sessions` ranks the current user's own prior runs ahead of the wider organizational
record, so the agent surfaces "what you looked into last week" before a colleague's unrelated work.
This stops short of building any model of the person — no traits, preferences, or communication
style are inferred or stored. That boundary is intentional: this is a shared operational tool used
by many employees across roles under one audit trail, where a consistent answer to the same
question matters more than a personalized one, and profiling individual staff inside a system that
also feeds governance records is a liability this design avoids rather than a capability it lacks.

**Tool-level authorization.** Being able to reach a tool through the agent must never grant more
than calling that tool's own endpoint directly would. Each tool carries the same role restriction
as its equivalent API route (for example `assess_supplier_risk` is limited to admin, executive,
and procurement_officer, matching `/suppliers/{id}/risk-assessment`), and the agent checks it
before every execution — refusing with an explanation rather than running the tool. This check
also applies when replaying a stored skill: a skill authored under one role is re-authorized
against whichever role reuses it, so a skill can never become a way to route around governance
that was never bypassable directly.

The agent has its own memory. Beyond the grounding step it persists findings as it works and can
search its previous runs for what it concluded on a topic before, giving it recall across
sessions. When it solves a task, the trajectory is generalized into a **skill**
(`services/agent_skills.py`): a named, parameterized sequence of tool calls stored in
`agent_skills` as data, not generated code. A skill only forms from a trajectory that did real
analytical work and touched a single kind of record — grounding-plus-`remember` alone, or a
trajectory that mixed two different entity types in one plan, is refused, since either shape was
found to misfire silently on reuse.

On a later goal the agent runs a stored skill directly instead of re-planning, preferring the
skills that have worked best. Matching is hybrid: an exact keyword-overlap check runs first
(cheap, and trusted over inference when it fires), unioned with a semantic candidate search over
each skill's embedded description (`AgentSkill.embedding`, cosine similarity against a calibrated
0.78 floor — measured, not guessed, against real paraphrase and non-paraphrase scores; see
`scripts/debug_skill_similarity.py`). Keyword overlap alone fragments into a separate skill per
phrasing of the same intent; the semantic half closes that gap, so "how risky is supplier 12"
correctly reuses a skill built from "assess the risk of supplier 3" even though the two share no
words. Matching is skipped entirely when the goal itself signals an explicit topic change ("one
more thing, unrelated to the RFIs...") — a live test found a skill's own stored keywords can match
a phrase that names its topic only to say it does not apply, since "unrelated to the RFIs" still
contains the literal word "RFIs." That match then replayed an unrelated stored plan and produced a
confidently wrong answer on a genuinely new question, so an explicit topic-switch phrase overrides
the matcher deterministically rather than trusting keyword overlap to understand negation. Each
execution updates the skill's record — a run counts as a success only when its
analysis produces a real finding, not merely when nothing errors, and an outcome that just reflects
bad input (record not found, tool not authorized) is neutral rather than counted against it — and a
skill whose success rate genuinely collapses is deprecated. If that pattern later recurs, the agent
re-learns the skill from a fresh trajectory as a new version, so the library improves rather than
ossifies. An admin can also deprecate or delete a skill directly (`PATCH`/`DELETE
/ai/agent/skills/{id}`); deleting one with prior run history is blocked by the same foreign-key
constraint every other entity delete respects, surfacing as a 409 rather than silently orphaning
run history. Storing procedures as data keeps every reused action inspectable and consistent with
the governance model — the agent extends what it can do without ever executing opaque code.

**Untrusted content.** A tool observation pulled from memory, a document, or a past session is text
the organization stored, not an instruction the agent should follow — but nothing about its shape
distinguishes the two from a raw string. Retrieved content is screened for two independent
patterns before it reaches the planner or the final-answer synthesis: attack-style phrasing (for
example "ignore all prior instructions") and a governance claim that a specific approval or review
step has been waived, regardless of how ordinary the wording sounds. Either pattern wraps the
content in an explicit warning marker and both system prompts state plainly that retrieved content
is data, never instructions, and that a suspicious claim must be reported, not acted on or repeated
as fact. This is a heuristic layered on top of the agent's own reasoning, not a guarantee against
every possible phrasing — but it closed a live-reproduced failure where a single poisoned memory
record talked the unguarded agent into recommending that a real approval step be skipped. The
screening always runs against a source's full text before any preview is shortened for display —
an earlier version checked only a pre-truncated excerpt for `search_documents` and
`recall_past_sessions`, which let an identical payload through undetected simply because the
attack phrasing fell past the cutoff, even though the same content was correctly flagged when it
came from a memory record (which was never truncated before the check). A short, ordinary-looking
preamble was enough to clear that bar in practice, so this was closed uniformly across all three
retrieval channels rather than patched per call site.

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
modals, tabs, pagination) keeps every page consistent. Sixteen pages cover the dashboard, projects,
procurement, RFIs, claims, change orders, meetings, site reports, documents, reports, copilot, agent,
approvals, memory, audit, and user management, with create/edit/delete forms, CSV/Excel import, an
in-app notifications bell, and a per-project workspace layered across them. Role-based visibility is
enforced in the UI (action buttons appear only for roles that can use them) on top of the server-side
RBAC, which remains the actual authority.

## Testing strategy

The suite runs against a real PostgreSQL instance for fidelity, but each test gets its own connection
and an outer transaction that is rolled back at teardown; the application's own commits become
savepoints, so nothing persists between tests. Under `TESTING` the mock LLM and hash embedder make
everything deterministic and offline. This is why the 279-test suite can cover real database
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
- **Uploaded files live on disk, not in Postgres.** An uploaded document's original bytes are saved
  under a dedicated volume and referenced from its row by path, rather than stored as a database
  blob. This is the standard-scale-appropriate answer for a single-server deployment; if the platform
  ever runs on more than one server at once, that volume would need to become shared/object storage
  — nothing else in the current architecture is built for multi-server operation either, so this
  isn't a gap unique to file storage.
