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
| View AI audit trail | ✓ | ✓ | | | | | |

The `viewer` role is strictly read-only across the platform.

## AI governance

The brief requires that AI never take high-risk actions autonomously and that its output be
auditable. Both are enforced structurally, not by convention.

- **Advisory by construction.** The workflows and copilot produce recommendations, drafts, and
  summaries. None of them execute an action with external consequence.
- **Human-in-the-loop approvals.** A high-risk action is created as an approval request in `pending`
  state. A manager (admin, executive, or project_manager) approves or rejects it; the transition is
  recorded in approval history and a notification is sent to the requester. A request cannot be
  resolved twice. Nothing runs until a human approves it.
- **Audit trail.** Every AI call — every workflow, copilot answer, and memory extraction — writes an
  `ai_audit_logs` row capturing the workflow, provider, model, the source ids it used, and an output
  excerpt. `GET /audit/ai-outputs` exposes this to admins and executives.
- **Source attribution.** Workflow and copilot responses carry the documents and memory records they
  drew on, so a reader can trace any recommendation back to its evidence.

## Rate limiting

A Redis-backed fixed-window limiter (`security/rate_limit.py`) protects the two endpoints that most
need it: login (against brute force) and the copilot (against runaway LLM cost). It is best-effort by
design — if Redis is unreachable it fails open rather than locking users out, and it is disabled
under `TESTING` so the suite stays deterministic. In production a shared Redis makes the limit apply
across all API instances.

The limiter keys on the request's direct peer address (`request.client.host`). Behind a reverse
proxy or load balancer that address is the proxy's, so per-client limiting requires the deployment to
resolve the real client IP from a trusted `X-Forwarded-For` hop (for example via Uvicorn's
`--proxy-headers` with a configured trusted-host list). Until that is configured, treat the login
limit as a global throttle rather than a strict per-client one.

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

## Input handling

Request bodies are validated by Pydantic before any handler runs, which rejects malformed input with
a 422 automatically. The full-text query built for the copilot is constructed from alphanumeric
tokens only, so it cannot inject into the `tsquery`. Uploaded files are size-capped at 10 MB, checked
for an extractable text type, and rejected with a clear status code otherwise. Database integrity
violations are caught and returned as `409 Conflict` rather than leaking a stack trace.

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
