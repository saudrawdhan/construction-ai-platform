import { useEffect, useState } from "react";
import { Sparkles, ListChecks } from "lucide-react";
import { api, ApiError, type Page } from "../lib/api";
import { useAuth } from "../lib/auth";
import { date } from "../lib/format";
import {
  Badge,
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

interface Meeting {
  id: number;
  project_id: number;
  meeting_date: string | null;
  title: string;
  meeting_type: string;
}
interface ProjectOption {
  id: number;
  project_name: string;
}
interface ActionItem {
  description: string;
  owner: string | null;
  due_date: string | null;
}
interface DecisionItem {
  text: string;
  owner: string | null;
}
interface MeetingSummary {
  summary: string;
  action_items: ActionItem[];
  decisions: DecisionItem[];
  risks: string[];
  meeting_id: number | null;
  stored_action_items: number;
  stored_decisions: number;
  provider: string;
  model: string;
}

const MEETING_TYPES = ["General", "Technical Coordination", "Safety Review", "Progress Review", "Client Meeting"];

export default function Meetings() {
  const { user } = useAuth();
  const canSummarize = !!user && ["admin", "project_manager", "qa_qc"].includes(user.role);
  const [data, setData] = useState<Page<Meeting>>();
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
    api.get<Page<Meeting>>(`/meetings?${params}`).then(setData).catch((e) => setError(e.message));
  }, [page, projectFilter]);

  const projectName = (id: number) => projects.find((p) => p.id === id)?.project_name ?? `#${id}`;

  return (
    <div>
      <PageHeader title="Meetings" subtitle="Meeting records and AI minutes summarization" />

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
        {canSummarize && (
          <Button onClick={() => setOpen(true)}>
            <Sparkles size={15} /> Summarize Notes
          </Button>
        )}
      </div>

      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
      {!data && !error && <Spinner />}

      {data && (
        <Card>
          <Table head={["Title", "Type", "Project", "Date"]}>
            {data.items.map((m) => (
              <tr key={m.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-medium text-slate-800">{m.title}</td>
                <td className="px-4 py-3">
                  <Badge tone="slate">{m.meeting_type}</Badge>
                </td>
                <td className="px-4 py-3 text-slate-600">{projectName(m.project_id)}</td>
                <td className="px-4 py-3 text-slate-600">{date(m.meeting_date)}</td>
              </tr>
            ))}
          </Table>
          {data.items.length === 0 && <EmptyState message="No meetings match this filter." />}
          <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
        </Card>
      )}

      {open && <SummarizeModal projects={projects} onClose={() => setOpen(false)} />}
    </div>
  );
}

function SummarizeModal({ projects, onClose }: { projects: ProjectOption[]; onClose: () => void }) {
  const [projectId, setProjectId] = useState("");
  const [title, setTitle] = useState("Project Meeting");
  const [meetingType, setMeetingType] = useState("General");
  const [meetingDate, setMeetingDate] = useState("");
  const [notes, setNotes] = useState("");
  const [store, setStore] = useState(false);
  const [result, setResult] = useState<MeetingSummary>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  async function run() {
    if (!projectId || notes.trim().length < 10) return;
    setBusy(true);
    setError(undefined);
    try {
      setResult(
        await api.post<MeetingSummary>(`/meetings/${projectId}/summarize`, {
          notes,
          title,
          meeting_type: meetingType,
          meeting_date: meetingDate || null,
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
    <Modal title="Summarize Meeting Notes" onClose={onClose}>
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
          <Field label="Meeting Type">
            <Select value={meetingType} onChange={(e) => setMeetingType(e.target.value)}>
              {MEETING_TYPES.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </Select>
          </Field>
          <Field label="Title">
            <Input value={title} onChange={(e) => setTitle(e.target.value)} />
          </Field>
          <Field label="Date">
            <Input type="date" value={meetingDate} onChange={(e) => setMeetingDate(e.target.value)} />
          </Field>
        </div>
        <Field label="Meeting notes / minutes">
          <Textarea
            rows={6}
            placeholder="Paste raw meeting minutes — the agent extracts a summary, action items with owners, decisions, and risks."
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
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
            Persist meeting, action items, decisions &amp; memory
          </label>
          <Button disabled={busy || !projectId || notes.trim().length < 10} onClick={run}>
            <Sparkles size={15} /> {busy ? "Summarizing…" : "Summarize"}
          </Button>
        </div>
        {error && <div className="text-sm text-red-600">{error}</div>}

        {result && (
          <div className="space-y-4 border-t border-slate-100 pt-4">
            <div className="flex items-center gap-2">
              <ProviderTag provider={result.provider} model={result.model} />
              {result.meeting_id && (
                <span className="text-xs text-slate-400">
                  saved meeting #{result.meeting_id} · {result.stored_action_items} action items ·{" "}
                  {result.stored_decisions} decisions
                </span>
              )}
            </div>
            <LabelValue label="Summary" value={<p className="whitespace-pre-wrap">{result.summary}</p>} />
            {result.action_items.length > 0 && (
              <div>
                <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-slate-500">
                  <ListChecks size={13} /> Action Items
                </div>
                <div className="space-y-1.5">
                  {result.action_items.map((a, i) => (
                    <div key={i} className="rounded-lg bg-slate-50 px-3 py-2 text-sm">
                      <span className="text-slate-700">{a.description}</span>
                      {(a.owner || a.due_date) && (
                        <span className="ml-1 text-xs text-slate-400">
                          — {a.owner ?? "unassigned"}
                          {a.due_date ? ` · due ${date(a.due_date)}` : ""}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
            {result.decisions.length > 0 && (
              <LabelValue
                label="Decisions"
                value={
                  <ul className="list-inside list-disc text-slate-700">
                    {result.decisions.map((d, i) => (
                      <li key={i}>
                        {d.text}
                        {d.owner ? <span className="text-xs text-slate-400"> — {d.owner}</span> : null}
                      </li>
                    ))}
                  </ul>
                }
              />
            )}
            {result.risks.length > 0 && (
              <LabelValue
                label="Risks"
                value={
                  <div className="flex flex-wrap gap-1.5">
                    {result.risks.map((r, i) => (
                      <Badge key={i} tone="red">
                        {r}
                      </Badge>
                    ))}
                  </div>
                }
              />
            )}
          </div>
        )}
      </div>
    </Modal>
  );
}
