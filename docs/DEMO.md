# Demonstration Script

An end-to-end walkthrough of the platform, organized as eight scenarios that together cover the
operational record, all six AI workflows, the copilot, memory, document ingestion, and governance.
Estimated duration: 10–12 minutes.

## Setup

Start the stack and confirm it is healthy:

```bash
docker compose up -d db redis api
cd frontend && npm run dev        # http://localhost:5173
```

The API uses Gemini by default. Its free tier is limited in volume, so for a rehearsal — or to avoid
using quota before the actual presentation — run the API with `LLM_PROVIDER=mock`; every AI feature
behaves identically, using deterministic reasoning instead of a live model call. Switch to the real
provider for the presentation itself.

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

Open **Copilot** and ask a question the record can answer, for example: *"What are the main risks and
delays across the portfolio?"* The response carries a **Grounded** badge and lists the specific
records it drew on.

Then ask a question the data cannot support — a fabricated supplier name, or an unrelated topic. The
copilot returns **No evidence found** rather than producing an answer.

**Demonstrates:** the assistant answers only from retrieved evidence and explicitly declines when none
exists; the refusal path does not call the language model at all.

## 5. Enterprise Memory

Open **Memory** and search for a term such as *"supplier delays"* — the supplier risk finding from
Scenario 3 is now retrievable. Optionally, open **Extract Agent**, provide a short passage of meeting
notes, and show the categorized, confidence-scored memories it produces.

**Demonstrates:** findings are stored with their source and category and are fed back into future
analysis — the organizational-memory requirement made concrete.

## 6. Document Ingestion and Search

Open **Documents → Upload**, select a project, and upload a short PDF or text file. The response
confirms the file was parsed, chunked, embedded, and indexed. Switch to **Semantic Search** and query
a phrase from the uploaded file to confirm it returns as a result and is now available to the copilot.

**Demonstrates:** new documents enter the same knowledge base the AI already reasons over, with no
separate ingestion pipeline.

## 7. Governance and Human Approval

Sign in as `pm@construction-ops.com` and open **Approvals**. A high-risk action appears as a pending
request — proposed by the AI, not executed. Approve it and review the resulting history entry and the
notification sent to the requester.

Sign back in as the executive and open **Audit**. Every AI call made during the walkthrough is logged
with its workflow, provider, model, and an excerpt of the output.

**Demonstrates:** no high-risk action proceeds without a person, and every AI action is recorded —
the governance the platform is built around.

## 8. Scheduled Automation (optional)

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

Every scenario above draws on one integrated system and one real dataset: reading the operational
record, analyzing it, retaining what was learned, answering questions from evidence, and keeping
high-risk actions behind a person — the combination the platform is designed to deliver.
