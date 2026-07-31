# Security and governance

This document describes how access is controlled, how AI output is governed, and which trade-offs
were made deliberately. It covers the security model as built, not aspirations — where something is
a pilot-stage simplification, it is called out as one.

## Authentication

Users authenticate at `POST /api/v1/auth/login` with an email and password. Passwords are hashed
with bcrypt; the plaintext is never stored or logged. On success the server issues an HS256 JWT
signed with a secret from configuration, carrying the user id and role with a 30-minute expiry.

The token is delivered as an **httpOnly, SameSite cookie** — it is not readable by JavaScript, which
removes the cross-site-scripting token-theft vector that a `localStorage` token would expose. The
single-page app never sees the token; the browser attaches the cookie automatically on each request.
The token is also returned in the login response body so Swagger's Authorize dialog and API clients
can use a bearer header. `get_current_user` accepts either source: it reads the cookie, or falls back
to an `Authorization: Bearer` header, then decodes the token, loads the user, and rejects the request
if the token is invalid or the account is inactive. `POST /api/v1/auth/logout` clears the cookie.

The cookie is marked `secure` in production (HTTPS only) via `COOKIE_SECURE`. The login endpoint is
rate limited (see below) to make credential brute-forcing impractical.

## Authorization (RBAC)

There are seven roles. Authorization is enforced server-side with a `require_roles(...)` dependency
on each endpoint that needs it; the frontend additionally hides controls a role cannot use, but the
server is the authority — a hidden button is a convenience, not a control.

| Capability | admin | executive | project_manager | site_engineer | procurement_officer | qa_qc | viewer |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Read operational data | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Create projects / risks | ✓ | | ✓ | | | | |
| Analyze purchase requests | ✓ | | ✓ | | ✓ | | |
| Supplier risk assessment | ✓ | ✓ | | | ✓ | | |
| RFI escalation | ✓ | | ✓ | ✓ | | | |
| Summarize meetings | ✓ | | ✓ | | | ✓ | |
| Analyze site reports | ✓ | | ✓ | ✓ | | | |
| Executive report | ✓ | ✓ | ✓ | | | | |
| Upload documents | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | |
| Write / extract memory | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | |
| Approve / reject approvals | ✓ | ✓ | ✓ | | | | |
| Run the agent / view its history | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | |
| View AI audit trail | ✓ | ✓ | | | | | |

The `viewer` role is strictly read-only across the platform.

## AI governance

The brief requires that AI never take high-risk actions autonomously and that its output be
auditable. Both are enforced structurally, not by convention.

- **Advisory by construction.** The workflows and copilot produce recommendations, drafts, and
  summaries. None of them execute an action with external consequence.
- **Human-in-the-loop approvals.** A high-risk action is created as an approval request in `pending`
  state. A manager (admin, executive, or project_manager) approves or rejects it; the transition is
  recorded in approval history and a notification is sent to the requester. The transition is a
  single atomic `UPDATE … WHERE status = 'pending'`, so a request resolves exactly once even if two
  approvers act at the same moment — the second is rejected with a `409` and writes no duplicate
  history or notification. Nothing runs until a human approves it.
- **Audit trail.** Every AI call — every workflow, copilot answer, and memory extraction — writes an
  `ai_audit_logs` row capturing the workflow, provider, model, the source ids it used, and an output
  excerpt. `GET /audit/ai-outputs` exposes this to admins and executives.
- **Source attribution.** Workflow and copilot responses carry the documents and memory records they
  drew on, so a reader can trace any recommendation back to its evidence.
- **Tool-level authorization inside the agent.** The agent can reach every AI workflow through a
  single tool registry, so reaching a capability through a goal must never grant more than calling
  that capability's own endpoint would. Each tool carries the same role restriction as its direct API
  route (for example, the agent's `assess_supplier_risk` tool is limited to admin, executive, and
  procurement_officer, matching `POST /suppliers/{id}/risk-assessment`), checked before every
  execution — a disallowed tool is refused with an explanation, not silently run. This check also
  applies when the agent replays a stored skill: a skill is re-authorized against whoever is running
  it now, not the role that originally created it, so a skill can never become a way to route around
  a restriction that was never bypassable directly. Because agent trajectories can surface the output
  of role-restricted tools, the agent's run history and skill library are not exposed to `viewer`,
  matching the same rule already applied to `GET /audit/ai-outputs`.
- **Agent runs and conversations are owned, not shared, by default.** `GET /ai/agent/runs` and
  `GET /ai/agent/runs/{id}` scope to the requesting user unless the role is admin or executive; a run
  that exists but belongs to someone else returns `404`, the same response as a run that does not
  exist at all, so the endpoint cannot be used to confirm another user's activity. Supplying another
  user's `conversation_id` does not continue their conversation — a mismatched id is treated as no id
  at all and a fresh conversation starts instead. Skills remain intentionally shared and org-wide,
  since a reusable procedure is not any one person's data.
- **Untrusted retrieved content.** Text pulled back from memory, documents, or past sessions is fed
  into an LLM as *evidence*, but nothing about a plain string distinguishes organizational data from
  an embedded instruction. Retrieved content is screened for two independent patterns before it
  reaches any prompt: attack-style phrasing (for example, an "ignore all prior instructions"
  override) and a specific governance claim — an approval, threshold, or review step framed as
  already waived — regardless of how ordinary the wording sounds. Both pattern sets are bilingual
  (English and Arabic), since the platform's data and retrieval are bilingual and an English-only
  screen would leave every Arabic record unprotected; the governance patterns are approval-context-
  bound so ordinary Arabic text about a real review or approval is not falsely flagged. A match is
  wrapped in an explicit warning marker, and the prompt instructs the model that retrieved content is
  data, never instructions, and that a suspicious or unverified claim must be reported to the human,
  not acted on or restated as settled fact. The screen runs on both AI surfaces that ground on
  retrieved text — the agent's tools and the copilot's RAG — through one shared implementation, so
  neither can be hardened while the other drifts behind. This is a heuristic layered on top of the
  model's own judgment, not a guarantee against every possible phrasing — it closed a live-reproduced
  case where a single poisoned memory record talked the agent into recommending that a real
  purchase-order approval step be skipped, and a separate case where the copilot restated a
  fabricated Arabic "auto-approve without review" claim as policy.
- **No individual user profiling.** The agent recalls a user's own recent runs ahead of the wider
  organizational record (`recall_past_sessions` ranks the requester's own prior work first), and a
  follow-up in the same conversation carries its project scope forward. Neither mechanism builds a
  behavioral, preference, or personality model of a person — nothing beyond a user id association on
  each run is retained about *who* asked. This is a deliberate boundary for a workplace tool used by
  many employees under a shared audit trail, not a missing feature.

## Rate limiting

A Redis-backed fixed-window limiter (`security/rate_limit.py`) protects the two endpoints that most
need it: login (against brute force) and the copilot (against runaway LLM cost). It is best-effort by
design — if Redis is unreachable it fails open rather than locking users out, and it is disabled
under `TESTING` so the suite stays deterministic. In production a shared Redis makes the limit apply
across all API instances.

The limiter keys on the authenticated user's id, decoded from the same bearer token or cookie the
request is already carrying, so a shared corporate egress IP does not throttle every employee behind
it as a single budget — a limit that matters more on the heavier-weight agent and copilot endpoints
than it does on login. It falls back to the request's direct peer address (`request.client.host`)
only when no valid token is present, which is exactly the login endpoint's own case (no token exists
yet by definition), so login's brute-force protection is unchanged. Behind a reverse proxy or load
balancer that fallback address is the proxy's, so IP-based limiting for unauthenticated requests
still requires the deployment to resolve the real client IP from a trusted `X-Forwarded-For` hop (for
example via Uvicorn's `--proxy-headers` with a configured trusted-host list).

## Transport and headers

Every response carries a small set of hardening headers via middleware: `X-Content-Type-Options:
nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, and a restrictive
`Permissions-Policy`. CORS is restricted to a configured allow-list of origins rather than a
wildcard.

HTTPS/HSTS is expected to be terminated at the deployment's reverse proxy or load balancer rather
than in the application, which is the usual arrangement for a containerized service; the app is
designed to run behind TLS in any real deployment.

## Secrets and configuration

All secrets — the database URL, the JWT signing secret, and the LLM API key — come from environment
variables through the single `Settings` object. The `.env` file is git-ignored and never committed;
`.env.example` documents the shape without values. The dataset and local working files are likewise
git-ignored. On a hosted deployment the same variables are supplied by the platform's secret store,
using the same code path.

The signing key is enforced rather than merely documented: unless `ENVIRONMENT` is exactly
`development`, the application refuses to start if `JWT_SECRET` is still the repository's published
development default or is shorter than 32 characters. A forgeable signing key is not a degraded
state the platform can usefully run in — every role gate, approval, and audit entry depends on the
token being unforgeable — so a misconfigured deployment fails immediately and loudly instead of
serving traffic that only appears to be authenticated. The check fails closed: any environment name
other than `development` is treated as deployed.

## Input handling

Request bodies are validated by Pydantic before any handler runs, which rejects malformed input with
a 422 automatically. The full-text query built for the copilot is constructed from alphanumeric
tokens only, so it cannot inject into the `tsquery`. Uploaded files are size-capped at 10 MB, checked
for an extractable text type, and rejected with a clear status code otherwise. Database integrity
violations are caught and returned as `409 Conflict` rather than leaking a stack trace. A value that
passes Pydantic but the database itself cannot store — a string longer than its column, a number out
of range, or an invalid byte sequence, which Postgres reports as a SQLSTATE class-22 data error — is
likewise caught and returned as a clean `422`, so oversized or malformed input never surfaces as a
raw `500`; any other database error is re-raised so a genuine server fault is still logged as one.

## Known trade-offs and deferred work

These are deliberate pilot-stage decisions, documented so they are not mistaken for oversights.

- **CSRF.** Because the auth cookie is `SameSite=Lax`, cross-site POSTs do not carry it, which
  defends the state-changing endpoints against CSRF for normal browser flows. A deployment that
  needs to relax `SameSite` (for example to embed the app cross-site) should add an explicit
  anti-CSRF token at that point.
- **No token refresh or revocation list.** Tokens expire after 30 minutes and the user logs in again.
  A refresh-token flow and a revocation list are future work.
- **Rate-limit scope.** Limiting is applied to login and the copilot. A production deployment would
  likely extend it to the other AI endpoints and add a general per-IP ceiling.
- **Content-Security-Policy.** A strict CSP is not set on API responses because the Swagger UI it
  also serves needs relaxed script rules; a deployment that serves the frontend and API from the same
  origin should add one there.
