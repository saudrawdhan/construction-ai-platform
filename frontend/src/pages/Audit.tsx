import { useEffect, useState } from "react";
import { api, ApiError, type Page } from "../lib/api";
import { dateTime, titleCase } from "../lib/format";
import {
  Badge,
  Card,
  EmptyState,
  Field,
  FilterBar,
  PageHeader,
  Pagination,
  ProviderTag,
  Select,
  Spinner,
  Table,
} from "../components/ui";

interface AuditLog {
  id: number;
  user_id: number | null;
  workflow: string;
  provider: string;
  model: string;
  output_excerpt: string | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  created_at: string;
}

const WORKFLOWS = [
  "copilot",
  "memory_extraction",
  "pr_review",
  "supplier_risk",
  "rfi_escalation",
  "meeting_summary",
  "site_report",
  "executive_report",
];

export default function Audit() {
  const [data, setData] = useState<Page<AuditLog>>();
  const [error, setError] = useState<string>();
  const [forbidden, setForbidden] = useState(false);
  const [page, setPage] = useState(1);
  const [workflow, setWorkflow] = useState("");

  useEffect(() => {
    const params = new URLSearchParams({ page: String(page), size: "20" });
    if (workflow) params.set("workflow", workflow);
    setError(undefined);
    setForbidden(false);
    api
      .get<Page<AuditLog>>(`/audit/ai-outputs?${params}`)
      .then(setData)
      .catch((e: ApiError) => (e.status === 403 ? setForbidden(true) : setError(e.message)));
  }, [page, workflow]);

  if (forbidden)
    return (
      <div>
        <PageHeader title="AI Audit Trail" />
        <Card>
          <EmptyState message="The audit trail is restricted to admin and executive roles." />
        </Card>
      </div>
    );

  return (
    <div>
      <PageHeader title="AI Audit Trail" subtitle="Every AI call logged with provider, model, sources, and tokens" />

      <FilterBar>
        <Field label="Workflow">
          <Select
            value={workflow}
            onChange={(e) => {
              setWorkflow(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All workflows</option>
            {WORKFLOWS.map((w) => (
              <option key={w} value={w}>
                {titleCase(w)}
              </option>
            ))}
          </Select>
        </Field>
      </FilterBar>

      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
      {!data && !error && <Spinner />}

      {data && (
        <Card>
          <Table head={["Workflow", "Provider", "Output Excerpt", "Tokens", "When"]}>
            {data.items.map((log) => (
              <tr key={log.id} className="hover:bg-slate-50">
                <td className="px-4 py-3">
                  <Badge tone="blue">{titleCase(log.workflow)}</Badge>
                </td>
                <td className="px-4 py-3">
                  <ProviderTag provider={log.provider} model={log.model} />
                </td>
                <td className="max-w-md px-4 py-3 text-slate-600">
                  <div className="truncate">{log.output_excerpt ?? "—"}</div>
                </td>
                <td className="px-4 py-3 text-xs text-slate-500">
                  {log.prompt_tokens !== null || log.completion_tokens !== null
                    ? `${log.prompt_tokens ?? 0} / ${log.completion_tokens ?? 0}`
                    : "—"}
                </td>
                <td className="px-4 py-3 text-slate-600">{dateTime(log.created_at)}</td>
              </tr>
            ))}
          </Table>
          {data.items.length === 0 && <EmptyState message="No AI calls logged yet." />}
          <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
        </Card>
      )}
    </div>
  );
}
