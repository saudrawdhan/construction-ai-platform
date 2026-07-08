import { useEffect, useState } from "react";
import { Sparkles, CheckCircle2, AlertTriangle, TriangleAlert } from "lucide-react";
import { api, ApiError, type Page } from "../lib/api";
import { useAuth } from "../lib/auth";
import { date } from "../lib/format";
import {
  Button,
  Card,
  EmptyState,
  Field,
  FilterBar,
  Input,
  LabelValue,
  Modal,
  PageHeader,
  Pagination,
  ProviderTag,
  Select,
  Spinner,
  Table,
  Textarea,
} from "../components/ui";

interface SiteReport {
  id: number;
  project_id: number;
  report_date: string | null;
  weather: string;
  summary: string;
}
interface ProjectOption {
  id: number;
  project_name: string;
}
interface SiteAnalysis {
  summary: string;
  completed_work: string[];
  delays: string[];
  risks: string[];
  manpower_note: string | null;
  recommended_escalation: string;
  provider: string;
  model: string;
}

function BulletList({ items, tone }: { items: string[]; tone: string }) {
  return (
    <ul className="space-y-1">
      {items.map((it, i) => (
        <li key={i} className={`flex gap-2 text-sm ${tone}`}>
          <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-current opacity-60" />
          {it}
        </li>
      ))}
    </ul>
  );
}

export default function SiteReports() {
  const { user } = useAuth();
  const canAnalyze = !!user && ["admin", "project_manager", "site_engineer"].includes(user.role);
  const [data, setData] = useState<Page<SiteReport>>();
  const [projects, setProjects] = useState<ProjectOption[]>([]);
  const [error, setError] = useState<string>();
  const [page, setPage] = useState(1);
  const [projectFilter, setProjectFilter] = useState("");
  const [open, setOpen] = useState(false);

  useEffect(() => {
    api.get<Page<ProjectOption>>("/projects?size=100").then((p) => setProjects(p.items)).catch(() => {});
  }, []);

  useEffect(() => {
    const params = new URLSearchParams({ page: String(page), size: "20" });
    if (projectFilter) params.set("project_id", projectFilter);
    setError(undefined);
    api.get<Page<SiteReport>>(`/site-reports?${params}`).then(setData).catch((e) => setError(e.message));
  }, [page, projectFilter]);

  const projectName = (id: number) => projects.find((p) => p.id === id)?.project_name ?? `#${id}`;

  return (
    <div>
      <PageHeader title="Site Reports" subtitle="Daily site reports and AI field-report analysis" />

      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <FilterBar>
          <Field label="Project">
            <Select
              value={projectFilter}
              onChange={(e) => {
                setProjectFilter(e.target.value);
                setPage(1);
              }}
            >
              <option value="">All projects</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.project_name}
                </option>
              ))}
            </Select>
          </Field>
        </FilterBar>
        {canAnalyze && (
          <Button onClick={() => setOpen(true)}>
            <Sparkles size={15} /> Analyze Report
          </Button>
        )}
      </div>

      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
      {!data && !error && <Spinner />}

      {data && (
        <Card>
          <Table head={["Date", "Project", "Weather", "Summary"]}>
            {data.items.map((r) => (
              <tr key={r.id} className="hover:bg-slate-50">
                <td className="whitespace-nowrap px-4 py-3 text-slate-600">{date(r.report_date)}</td>
                <td className="whitespace-nowrap px-4 py-3 text-slate-600">{projectName(r.project_id)}</td>
                <td className="px-4 py-3 text-slate-600">{r.weather}</td>
                <td className="max-w-md px-4 py-3 text-slate-700">
                  <div className="truncate">{r.summary}</div>
                </td>
              </tr>
            ))}
          </Table>
          {data.items.length === 0 && <EmptyState message="No site reports match this filter." />}
          <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
        </Card>
      )}

      {open && <AnalyzeModal projects={projects} onClose={() => setOpen(false)} />}
    </div>
  );
}

function AnalyzeModal({ projects, onClose }: { projects: ProjectOption[]; onClose: () => void }) {
  const [projectId, setProjectId] = useState("");
  const [reportDate, setReportDate] = useState("");
  const [text, setText] = useState("");
  const [store, setStore] = useState(false);
  const [result, setResult] = useState<SiteAnalysis>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  async function run() {
    if (!projectId || text.trim().length < 10) return;
    setBusy(true);
    setError(undefined);
    try {
      setResult(
        await api.post<SiteAnalysis>(`/site-reports/${projectId}/analyze`, {
          text,
          report_date: reportDate || null,
          store,
        })
      );
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Analyze Site Report" onClose={onClose}>
      <div className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Project">
            <Select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
              <option value="">Select a project…</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.project_name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Report Date">
            <Input type="date" value={reportDate} onChange={(e) => setReportDate(e.target.value)} />
          </Field>
        </div>
        <Field label="Site report text">
          <Textarea
            rows={6}
            placeholder="Paste the field report — the agent extracts completed work, delays, risks, manpower notes, and an escalation recommendation."
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </Field>
        <div className="flex items-center justify-between">
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={store}
              onChange={(e) => setStore(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300"
            />
            Persist risk / issue memory
          </label>
          <Button disabled={busy || !projectId || text.trim().length < 10} onClick={run}>
            <Sparkles size={15} /> {busy ? "Analyzing…" : "Analyze"}
          </Button>
        </div>
        {error && <div className="text-sm text-red-600">{error}</div>}

        {result && (
          <div className="space-y-4 border-t border-slate-100 pt-4">
            <ProviderTag provider={result.provider} model={result.model} />
            <LabelValue label="Summary" value={<p className="whitespace-pre-wrap">{result.summary}</p>} />
            {result.completed_work.length > 0 && (
              <div>
                <div className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-emerald-600">
                  <CheckCircle2 size={13} /> Completed Work
                </div>
                <BulletList items={result.completed_work} tone="text-slate-700" />
              </div>
            )}
            {result.delays.length > 0 && (
              <div>
                <div className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-amber-600">
                  <AlertTriangle size={13} /> Delays
                </div>
                <BulletList items={result.delays} tone="text-amber-700" />
              </div>
            )}
            {result.risks.length > 0 && (
              <div>
                <div className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-red-600">
                  <TriangleAlert size={13} /> Risks
                </div>
                <BulletList items={result.risks} tone="text-red-700" />
              </div>
            )}
            {result.manpower_note && <LabelValue label="Manpower" value={result.manpower_note} />}
            <LabelValue label="Recommended Escalation" value={result.recommended_escalation} />
          </div>
        )}
      </div>
    </Modal>
  );
}
