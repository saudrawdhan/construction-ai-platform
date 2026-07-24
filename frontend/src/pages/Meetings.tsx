import { useEffect, useState } from "react";
import { Sparkles, ListChecks, Plus, Upload } from "lucide-react";
import { api, ApiError, type Page } from "../lib/api";
import CreateModal from "../components/CreateModal";
import ImportModal from "../components/ImportModal";
import RowActions from "../components/RowActions";
import ProjectPicker from "../components/ProjectPicker";
import { useAuth } from "../lib/auth";
import { date, enumLabel } from "../lib/format";
import { useT, type Translate } from "../lib/i18n";
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
  statusTone,
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

const meetingFields = (t: Translate) => [
  { name: "project_id", label: t("common.project"), type: "project" as const, required: true },
  { name: "title", label: t("col.title"), required: true, full: true },
  { name: "meeting_type", label: t("field.type"), type: "select" as const, options: MEETING_TYPES, initial: "General" },
  { name: "meeting_date", label: t("common.date"), type: "date" as const },
];

interface ActionItemRow {
  id: number;
  description: string;
  owner: string | null;
  due_date: string | null;
  status: string;
}
interface DecisionRow {
  id: number;
  decision_text: string;
  owner: string;
  decision_date: string | null;
}

export default function Meetings() {
  const { user } = useAuth();
  const t = useT();
  const canSummarize = !!user && ["admin", "project_manager", "qa_qc"].includes(user.role);
  const [data, setData] = useState<Page<Meeting>>();
  const [projects, setProjects] = useState<ProjectOption[]>([]);
  const [error, setError] = useState<string>();
  const [page, setPage] = useState(1);
  const [projectFilter, setProjectFilter] = useState("");
  const [open, setOpen] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [detail, setDetail] = useState<{ meeting: Meeting; actions: ActionItemRow[]; decisions: DecisionRow[] }>();
  const [refresh, setRefresh] = useState(0);

  async function openDetail(m: Meeting) {
    try {
      const [actions, decisions] = await Promise.all([
        api.get<ActionItemRow[]>(`/meetings/${m.id}/action-items`),
        api.get<DecisionRow[]>(`/meetings/${m.id}/decisions`),
      ]);
      setDetail({ meeting: m, actions, decisions });
    } catch (e) {
      setError((e as ApiError).message);
    }
  }

  useEffect(() => {
    api.get<Page<ProjectOption>>("/projects?size=100").then((p) => setProjects(p.items)).catch(() => {});
  }, []);

  useEffect(() => {
    const params = new URLSearchParams({ page: String(page), size: "20" });
    if (projectFilter) params.set("project_id", projectFilter);
    setError(undefined);
    api.get<Page<Meeting>>(`/meetings?${params}`).then(setData).catch((e) => setError(e.message));
  }, [page, projectFilter, refresh]);

  const projectName = (id: number) => projects.find((p) => p.id === id)?.project_name ?? `#${id}`;

  return (
    <div>
      <PageHeader title={t("nav.meetings")} subtitle={t("mt.subtitle")} />

      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <FilterBar>
          <Field label={t("common.project")}>
            <div className="w-56">
              <ProjectPicker
                projects={projects}
                value={projectFilter}
                onChange={(v) => {
                  setProjectFilter(v);
                  setPage(1);
                }}
              />
            </div>
          </Field>
        </FilterBar>
        {canSummarize && (
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setShowImport(true)}>
              <Upload size={15} /> {t("common.import")}
            </Button>
            <Button variant="secondary" onClick={() => setShowCreate(true)}>
              <Plus size={15} /> {t("mt.new")}
            </Button>
            <Button onClick={() => setOpen(true)}>
              <Sparkles size={15} /> {t("mt.summarizeNotes")}
            </Button>
          </div>
        )}
      </div>

      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
      {!data && !error && <Spinner />}

      {data && (
        <Card>
          <Table head={[t("col.title"), t("col.type"), t("col.project"), t("col.date"), ""]}>
            {data.items.map((m) => (
              <tr key={m.id} className="hover:bg-slate-50">
                <td className="px-4 py-3">
                  <button
                    onClick={() => openDetail(m)}
                    className="text-start font-medium text-slate-800 hover:text-blue-700 hover:underline"
                  >
                    {m.title}
                  </button>
                </td>
                <td className="px-4 py-3">
                  <Badge tone="slate">{enumLabel(m.meeting_type, t)}</Badge>
                </td>
                <td className="px-4 py-3 text-slate-600">{projectName(m.project_id)}</td>
                <td className="px-4 py-3 text-slate-600">{date(m.meeting_date)}</td>
                <td className="px-4 py-3 text-end">
                  <RowActions
                    record={m}
                    entityLabel={t("entity.meeting")}
                    endpoint="/meetings"
                    fields={meetingFields(t)}
                    canManage={canSummarize}
                    onChanged={() => setRefresh((n) => n + 1)}
                  />
                </td>
              </tr>
            ))}
          </Table>
          {data.items.length === 0 && <EmptyState message={t("mt.noneMatch")} />}
          <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
        </Card>
      )}

      {detail && (
        <Modal title={detail.meeting.title} onClose={() => setDetail(undefined)}>
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Badge tone="slate">{enumLabel(detail.meeting.meeting_type, t)}</Badge>
              <span>{projectName(detail.meeting.project_id)}</span>
              <span>·</span>
              <span>{date(detail.meeting.meeting_date)}</span>
            </div>

            <div>
              <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-slate-500">
                <ListChecks size={13} /> {t("mt.actionItems", { n: detail.actions.length })}
              </div>
              {detail.actions.length === 0 ? (
                <p className="text-sm text-slate-400">{t("mt.noActionItems")}</p>
              ) : (
                <div className="space-y-1.5">
                  {detail.actions.map((a) => (
                    <div key={a.id} className="rounded-lg bg-slate-50 px-3 py-2 text-sm">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-slate-700">{a.description}</span>
                        <Badge tone={statusTone(a.status)}>{enumLabel(a.status, t)}</Badge>
                      </div>
                      {(a.owner || a.due_date) && (
                        <div className="mt-0.5 text-xs text-slate-400">
                          {a.owner ?? t("mt.unassigned")}
                          {a.due_date ? t("mt.dueSuffix", { date: date(a.due_date) }) : ""}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div>
              <div className="mb-2 text-xs font-medium text-slate-500">{t("mt.decisions", { n: detail.decisions.length })}</div>
              {detail.decisions.length === 0 ? (
                <p className="text-sm text-slate-400">{t("mt.noDecisions")}</p>
              ) : (
                <ul className="list-inside list-disc space-y-1 text-sm text-slate-700">
                  {detail.decisions.map((d) => (
                    <li key={d.id}>
                      {d.decision_text}
                      <span className="text-xs text-slate-400">
                        {" "}
                        — {d.owner}
                        {d.decision_date ? ` · ${date(d.decision_date)}` : ""}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </Modal>
      )}

      {open && <SummarizeModal projects={projects} onClose={() => setOpen(false)} />}

      {showCreate && (
        <CreateModal
          title={t("mt.new")}
          endpoint="/meetings"
          fields={meetingFields(t)}
          submitLabel={t("mt.createMeeting")}
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            setShowCreate(false);
            setPage(1);
            setRefresh((r) => r + 1);
          }}
        />
      )}

      {showImport && (
        <ImportModal
          title={t("mt.importTitle")}
          importPath="/meetings/import"
          templatePath="/meetings/import/template"
          templateFilename="meetings_template.csv"
          onClose={() => setShowImport(false)}
          onImported={() => {
            setPage(1);
            setRefresh((r) => r + 1);
          }}
        />
      )}
    </div>
  );
}

function SummarizeModal({ projects, onClose }: { projects: ProjectOption[]; onClose: () => void }) {
  const t = useT();
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
    <Modal title={t("mt.summarizeTitle")} onClose={onClose}>
      <div className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t("common.project")}>
            <ProjectPicker
              projects={projects}
              value={projectId}
              onChange={setProjectId}
              placeholder={t("form.selectProject")}
              required
            />
          </Field>
          <Field label={t("field.meetingType")}>
            <Select value={meetingType} onChange={(e) => setMeetingType(e.target.value)}>
              {MEETING_TYPES.map((mt) => (
                <option key={mt} value={mt}>{enumLabel(mt, t)}</option>
              ))}
            </Select>
          </Field>
          <Field label={t("col.title")}>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} />
          </Field>
          <Field label={t("common.date")}>
            <Input type="date" value={meetingDate} onChange={(e) => setMeetingDate(e.target.value)} />
          </Field>
        </div>
        <Field label={t("field.meetingNotes")}>
          <Textarea
            rows={6}
            placeholder={t("mt.notesPlaceholder")}
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
            {t("mt.persist")}
          </label>
          <Button disabled={busy || !projectId || notes.trim().length < 10} onClick={run}>
            <Sparkles size={15} /> {busy ? t("mt.summarizing") : t("mt.summarize")}
          </Button>
        </div>
        {error && <div className="text-sm text-red-600">{error}</div>}

        {result && (
          <div className="space-y-4 border-t border-slate-100 pt-4">
            <div className="flex items-center gap-2">
              <ProviderTag provider={result.provider} model={result.model} />
              {result.meeting_id && (
                <span className="text-xs text-slate-400">
                  {t("mt.savedMeeting", { id: result.meeting_id, a: result.stored_action_items, d: result.stored_decisions })}
                </span>
              )}
            </div>
            <LabelValue label={t("field.summary")} value={<p className="whitespace-pre-wrap">{result.summary}</p>} />
            {result.action_items.length > 0 && (
              <div>
                <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-slate-500">
                  <ListChecks size={13} /> {t("mt.actionItemsPlain")}
                </div>
                <div className="space-y-1.5">
                  {result.action_items.map((a, i) => (
                    <div key={i} className="rounded-lg bg-slate-50 px-3 py-2 text-sm">
                      <span className="text-slate-700">{a.description}</span>
                      {(a.owner || a.due_date) && (
                        <span className="ms-1 text-xs text-slate-400">
                          — {a.owner ?? t("mt.unassigned")}
                          {a.due_date ? t("mt.dueSuffix", { date: date(a.due_date) }) : ""}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
            {result.decisions.length > 0 && (
              <LabelValue
                label={t("mt.decisionsPlain")}
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
                label={t("mt.risksPlain")}
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
