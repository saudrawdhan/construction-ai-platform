# Demonstration Script

An end-to-end walkthrough of the platform, organized as ten scenarios that together cover the
operational record, all six AI workflows, the copilot, the agent, memory, document ingestion,
governance, and running the system as a product on your own data. Estimated duration: 13–16 minutes.

## Setup

Start the stack and confirm it is healthy:

```bash
docker compose up -d db redis api
cd frontend && npm run dev        # http://localhost:5173
```

The API uses Gemini by default. Its free tier is limited in volume, so for a rehearsal — or to avoid
using quota before the actual presentation — run the API with `LLM_PROVIDER=mock`; every AI feature
behaves identically, using deterministic reasoning instead of a live model call. A local open-weights
model is also a supported provider (`LLM_PROVIDER=local`, see the README) and runs unlimited real
inference with no quota concern at all. Switch to whichever provider fits the presentation itself.

Sign in as `executive@construction-ops.com` / `Passw0rd!` unless a step specifies a different account.

## 1. Executive Dashboard

Open the dashboard. It presents the portfolio at a glance, computed from real data: total projects,
projects delayed or on hold, overdue RFIs, late purchase orders, suppliers, and claims, alongside
tables of the most delayed projects and the most overdue RFIs.

**Demonstrates:** a single, current operational picture assembled from data that would otherwise live
across many disconnected sources.

## 2. Claims and the Evidence Chain

Open **Claims**, select a claim, and choose **View Chain**. The system reconstructs the claim's
supporting evidence — the linked change order, project decision, document, and correspondence — in a
single view.

**Demonstrates:** the relationships between commercial records are modeled, not merely filed, so the
evidence behind a claim can be assembled instantly rather than reconstructed by hand.

## 3. Procurement Intelligence

Open **Procurement → Suppliers**, select a supplier, and choose **Performance** to view its
cross-project record: on-time rate, late orders, total delay days, non-conformance reports, and
recurring delay causes. Then choose **Risk** to run the Supplier Risk workflow.

Switch to **Purchase Requests** and select **Analyze** on any request. The review flags missing
information, assigns a risk level, lists the approvals it would require, and incorporates the
assigned supplier's history.

**Demonstrates:** the risk score is computed from the supplier's actual delivery history; the AI
generates the written recommendation, not the underlying numbers. The assessment is also stored as
memory, so the platform reuses this finding in future analysis.

## 4. The Copilot — Grounded and Honest

Open **Copilot** and name a project in the question — for example: *"What are the risks on Riyadh
Hospital Project 3?"* The answer lists that project's risks ranked by severity with their owners and
likelihoods, carries a **Grounded** badge, and every source chip shows
`PRJ-0003 — Riyadh Hospital Project 3`, so it is visible at a glance that nothing was borrowed from
another project.

Then ask a question the data cannot support — a fabricated supplier name, or an unrelated topic. The
copilot returns **No evidence found** rather than producing an answer.

**Demonstrates:** the assistant answers only from retrieved evidence and explicitly declines when none
exists; the refusal path does not call the language model at all. It also shows the two grounding
guarantees worth calling out — retrieval is **scoped** to the project named in the question, and every
source carries the project it belongs to, so one project's records can never be narrated as another's.

The same question in Arabic (*"ما هي المخاطر في مشروع 3؟"*) answers in Arabic from the same records.

## 5. The Agent — Planning, Memory, Conversation, and Skills

Open **Agent**, choose a project from the scope selector, and give it a goal, for example: *"Give me
a status overview of this project's procurement health — any risks, overdue RFIs, or supplier
issues."* The agent plans and executes a sequence of tool calls, and the **trajectory** appears step
by step in a chat thread. Note the badge showing it **learned a skill** from the task, now visible in
the **Skill library** on the right.

Without touching the project selector again, ask a natural follow-up: *"What about the suppliers
involved — are any of them high risk?"* The reply stays in the same thread (shown by the
**Conversation #** label), and the trajectory shows the project scope carried forward automatically
— the agent is reasoning about what was just discussed, not starting over from an empty goal.

Start a **new conversation** and ask the same first question again on a different project. The badge
now shows it **reused** the earlier skill instead of planning from scratch.

**Demonstrates:** the agent reasons over a goal with visible, auditable tool use; it remembers this
conversation so a follow-up resolves naturally; it keeps its own memory across sessions; and it turns
experience into reusable skills — extending what it can do without executing any opaque code.

## 6. Enterprise Memory

Open **Memory** and search for a term such as *"supplier delays"* — the supplier risk finding from
Scenario 3 is now retrievable. Optionally, open **Extract Agent**, provide a short passage of meeting
notes, and show the categorized, confidence-scored memories it produces.

**Demonstrates:** findings are stored with their source and category and are fed back into future
analysis — the organizational-memory requirement made concrete.

## 7. Document Ingestion and Search

Open **Documents → Upload**, select a project, and upload a short PDF or text file. The response
confirms the file was parsed, chunked, embedded, and indexed. Switch to **Semantic Search** and query
a phrase from the uploaded file to confirm it returns as a result and is now available to the copilot.

**Demonstrates:** new documents enter the same knowledge base the AI already reasons over, with no
separate ingestion pipeline.

## 8. Governance and Human Approval

Run a workflow that recommends a high-risk action — for example **Procurement → Purchase Requests →
Analyze**, or **Suppliers → Risk**. In the result, choose **Request Approval**: the AI's
recommendation is sent to the approval queue rather than executed.

Sign in as `pm@construction-ops.com` and open **Approvals**. The request appears as *pending*, showing
the AI's recommendation as its payload. Approve it, and review the history entry ("requested" →
"approved"). Note the **bell** in the top bar: the person who requested it now has a notification of
the outcome.

Sign back in as the executive and open **Audit**. Every AI call made during the walkthrough is logged
with its workflow, provider, model, and an excerpt of the output.

**Demonstrates:** the full human-in-the-loop loop — the AI recommends, a person decides, the requester
is notified, and every AI action is recorded. No high-risk action proceeds on its own.

## 9. Running It as a Product — Data Entry from an Empty System

Sign in as `admin@construction-ops.com`. Open **Projects** and choose **New Project** to add a record
through a form; open its detail page to see its own workspace of RFIs, orders, meetings, and reports.
On any operational page, use the row **Edit** and **Delete** controls to amend or remove a record
(deletes are foreign-key-safe — a record with dependents is refused with a clear message, not a
crash). Then choose **Import** on Projects or Suppliers, download the template, and load several rows
from a CSV or Excel file with a validation preview before anything is saved.

To show the empty-start experience directly, a fresh database populated with
`scripts.seed_demo_data` — or no seed at all — presents an onboarding dashboard that invites the first
project instead of showing empty tables.

**Demonstrates:** the platform is not tied to one fixed dataset — a company can adopt it on an empty
database and enter, import, edit, and remove its own records, with the same permissions and validation
throughout.

## 10. Scheduled Automation (optional)

From the shell, run the automations in a dry run — the same logic the scheduled worker executes each
morning:

```bash
docker compose run --rm -e LLM_PROVIDER=mock api python -m scripts.run_automations
```

The output reports the daily site digest, the overdue-RFI reminder, the pending-PR alert, and the
weekly executive report against live data, then discards the results without saving them.

**Demonstrates:** routine reporting that a team would otherwise prepare by hand runs automatically on
a schedule, and always in a mode that uses no API quota.

## Closing

Every scenario above draws on one integrated system — running on the real dataset or on synthetic
demo data: reading the operational record, analyzing it, retaining what was learned, answering
questions from evidence, keeping high-risk actions behind a person, and letting a company enter and
manage its own data — the combination the platform is designed to deliver.
