import { useEffect, useState } from "react";
import { Siren, Plus, Upload } from "lucide-react";
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
  LabelValue,
  Modal,
  PageHeader,
  Pagination,
  ProviderTag,
  Spinner,
  Table,
  statusTone,
} from "../components/ui";
import CreateModal from "../components/CreateModal";
import ImportModal from "../components/ImportModal";
import RowActions from "../components/RowActions";
import ProjectPicker from "../components/ProjectPicker";
import RequestApprovalButton from "../components/RequestApprovalButton";

const RFI_FIELDS = [
  { name: "project_id", label: "Project", type: "project" as const, required: true },
  { name: "rfi_number", label: "RFI number", required: true },
  { name: "subject", label: "Subject", required: true, full: true },
  { name: "question", label: "Question", type: "textarea" as const, required: true },
  { name: "discipline", label: "Discipline", required: true },
  {
    name: "priority",
    label: "Priority",
    type: "select" as const,
    options: ["Low", "Medium", "High", "Critical"],
    initial: "Medium",
  },
  {
    name: "status",
    label: "Status",
    type: "select" as const,
    options: ["Open", "In Review", "Answered", "Closed"],
    initial: "Open",
  },
  { name: "raised_by", label: "Raised by", required: true },
  { name: "assigned_to", label: "Assigned to", required: true },
  { name: "raised_date", label: "Raised date", type: "date" as const },
  { name: "required_date", label: "Required date", type: "date" as const },
];

interface Rfi {
  id: number;
  project_id: number;
  rfi_number: string;
  subject: string;
  discipline: string;
  assigned_to: string;
  required_date: string | null;
  status: string;
  priority: string;
}
interface ProjectOption {
  id: number;
  project_name: string;
}
interface EscalationItem {
  rfi_number: string;
  subject: string;
  discipline: string;
  days_overdue: number;
  assigned_to: string;
  priority: string;
  suggested_action: string;
}
interface Escalation {
  project_id: number;
  overdue_count: number;
  items: EscalationItem[];
  escalation_message: string;
  provider: string;
  model: string;
}

export default function Rfis() {
  const { user } = useAuth();
  const canAnalyze = !!user && ["admin", "project_manager", "site_engineer"].includes(user.role);
  const [data, setData] = useState<Page<Rfi>>();
  const [projects, setProjects] = useState<ProjectOption[]>([]);
  const [error, setError] = useState<string>();
  const [page, setPage] = useState(1);
  const [overdue, setOverdue] = useState(false);
  const [projectId, setProjectId] = useState("");
  const [escalation, setEscalation] = useState<Escalation>();
  const [busy, setBusy] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    api.get<Page<ProjectOption>>("/projects?size=100").then((p) => setProjects(p.items)).catch(() => {});
  }, []);

  useEffect(() => {
    const params = new URLSearchParams({ page: String(page), size: "20" });
    if (overdue) params.set("overdue", "true");
    if (projectId) params.set("project_id", projectId);
    setError(undefined);
    api.get<Page<Rfi>>(`/rfis?${params}`).then(setData).catch((e) => setError(e.message));
  }, [page, overdue, projectId, refresh]);

  async function analyze() {
    if (!projectId) return;
    setBusy(true);
    try {
      setEscalation(await api.post<Escalation>(`/rfis/${projectId}/analyze`));
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="flex items-start justify-between">
        <PageHeader title="RFIs" subtitle="Requests for Information and overdue escalation" />
        {canAnalyze && (
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setShowImport(true)}>
              <Upload size={16} /> Import
            </Button>
            <Button onClick={() => setShowCreate(true)}>
              <Plus size={16} /> New RFI
            </Button>
          </div>
        )}
      </div>

      <FilterBar>
        <Field label="Project">
          <div className="w-56">
            <ProjectPicker
              projects={projects}
              value={projectId}
              onChange={(v) => {
                setProjectId(v);
                setPage(1);
              }}
            />
          </div>
        </Field>
        <label className="flex h-10 items-center gap-2 text-sm text-slate-600">
          <input
            type="checkbox"
            checked={overdue}
            onChange={(e) => {
              setOverdue(e.target.checked);
              setPage(1);
            }}
            className="h-4 w-4 rounded border-slate-300"
          />
          Overdue only
        </label>
        {canAnalyze && (
          <Button disabled={!projectId || busy} onClick={analyze} title={!projectId ? "Select a project first" : ""}>
            <Siren size={15} /> {busy ? "Analyzing…" : "Analyze Overdue RFIs"}
          </Button>
        )}
      </FilterBar>

      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
      {!data && !error && <Spinner />}

      {data && (
        <Card>
          <Table head={["RFI", "Subject", "Discipline", "Assigned", "Due", "Status", "Priority", ""]}>
            {data.items.map((r) => (
              <tr key={r.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-mono text-xs text-slate-500">{r.rfi_number}</td>
                <td className="px-4 py-3 text-slate-800">{r.subject}</td>
                <td className="px-4 py-3 text-slate-600">{r.discipline}</td>
                <td className="px-4 py-3 text-slate-600">{r.assigned_to}</td>
                <td className="px-4 py-3 text-slate-600">{date(r.required_date)}</td>
                <td className="px-4 py-3">
                  <Badge tone={statusTone(r.status)}>{r.status}</Badge>
                </td>
                <td className="px-4 py-3">
                  <Badge tone={statusTone(r.priority)}>{r.priority}</Badge>
                </td>
                <td className="px-4 py-3 text-right">
                  <RowActions
                    record={r}
                    entityLabel="RFI"
                    endpoint="/rfis"
                    fields={RFI_FIELDS}
                    canManage={canAnalyze}
                    onChanged={() => setRefresh((n) => n + 1)}
                  />
                </td>
              </tr>
            ))}
          </Table>
          {data.items.length === 0 && <EmptyState message="No RFIs match these filters." />}
          <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
        </Card>
      )}

      {escalation && (
        <Modal title={`RFI Escalation · ${escalation.overdue_count} overdue`} onClose={() => setEscalation(undefined)}>
          <div className="space-y-4">
            <ProviderTag provider={escalation.provider} model={escalation.model} />
            <LabelValue
              label="Drafted Escalation Message"
              value={<p className="whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-slate-700">{escalation.escalation_message}</p>}
            />
            {escalation.overdue_count > 0 && (
              <RequestApprovalButton
                actionType="send_rfi_escalation"
                projectId={escalation.project_id}
                label="Request Approval to Send"
                payload={{
                  overdue_count: escalation.overdue_count,
                  escalation_message: escalation.escalation_message,
                }}
              />
            )}
            {escalation.items.length > 0 && (
              <div>
                <div className="mb-2 text-xs font-medium text-slate-500">Overdue Items</div>
                <div className="space-y-2">
                  {escalation.items.map((it, i) => (
                    <div key={i} className="rounded-lg border border-slate-200 p-3">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs text-slate-500">{it.rfi_number}</span>
                        <div className="flex items-center gap-2">
                          <Badge tone="red">{it.days_overdue}d overdue</Badge>
                          <Badge tone={statusTone(it.priority)}>{it.priority}</Badge>
                        </div>
                      </div>
                      <div className="mt-1 text-sm font-medium text-slate-800">{it.subject}</div>
                      <div className="mt-1 text-sm text-slate-600">{it.suggested_action}</div>
                      <div className="mt-1 text-xs text-slate-400">
                        {it.discipline} · {it.assigned_to}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </Modal>
      )}

      {showCreate && (
        <CreateModal
          title="New RFI"
          endpoint="/rfis"
          fields={RFI_FIELDS}
          submitLabel="Create RFI"
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
          title="Import RFIs"
          importPath="/rfis/import"
          templatePath="/rfis/import/template"
          templateFilename="rfis_template.csv"
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
