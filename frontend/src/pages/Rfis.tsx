import { useEffect, useState } from "react";
import { Siren, Plus, Upload } from "lucide-react";
import { api, ApiError, type Page } from "../lib/api";
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

const rfiFields = (t: Translate) => [
  { name: "project_id", label: t("common.project"), type: "project" as const, required: true },
  { name: "rfi_number", label: t("field.rfiNumber"), required: true },
  { name: "subject", label: t("field.subject"), required: true, full: true },
  { name: "question", label: t("field.question"), type: "textarea" as const, required: true },
  { name: "discipline", label: t("field.discipline"), required: true },
  {
    name: "priority",
    label: t("field.priority"),
    type: "select" as const,
    options: ["Low", "Medium", "High", "Critical"],
    initial: "Medium",
  },
  {
    name: "status",
    label: t("field.status"),
    type: "select" as const,
    options: ["Open", "In Review", "Answered", "Closed"],
    initial: "Open",
  },
  { name: "raised_by", label: t("field.raisedBy"), required: true },
  { name: "assigned_to", label: t("field.assignedTo"), required: true },
  { name: "raised_date", label: t("field.raisedDate"), type: "date" as const },
  { name: "required_date", label: t("field.requiredDate"), type: "date" as const },
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
  const t = useT();
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
        <PageHeader title={t("nav.rfis")} subtitle={t("rfi.subtitle")} />
        {canAnalyze && (
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setShowImport(true)}>
              <Upload size={16} /> {t("common.import")}
            </Button>
            <Button onClick={() => setShowCreate(true)}>
              <Plus size={16} /> {t("rfi.new")}
            </Button>
          </div>
        )}
      </div>

      <FilterBar>
        <Field label={t("common.project")}>
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
          {t("rfi.overdueOnly")}
        </label>
        {canAnalyze && (
          <Button disabled={!projectId || busy} onClick={analyze} title={!projectId ? t("rfi.selectFirst") : ""}>
            <Siren size={15} /> {busy ? t("rfi.analyzing") : t("rfi.analyze")}
          </Button>
        )}
      </FilterBar>

      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
      {!data && !error && <Spinner />}

      {data && (
        <Card>
          <Table head={[t("col.rfi"), t("col.subject"), t("col.discipline"), t("col.assigned"), t("col.due"), t("col.status"), t("col.priority"), ""]}>
            {data.items.map((r) => (
              <tr key={r.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-mono text-xs text-slate-500">{r.rfi_number}</td>
                <td className="px-4 py-3 text-slate-800">{r.subject}</td>
                <td className="px-4 py-3 text-slate-600">{r.discipline}</td>
                <td className="px-4 py-3 text-slate-600">{r.assigned_to}</td>
                <td className="px-4 py-3 text-slate-600">{date(r.required_date)}</td>
                <td className="px-4 py-3">
                  <Badge tone={statusTone(r.status)}>{enumLabel(r.status, t)}</Badge>
                </td>
                <td className="px-4 py-3">
                  <Badge tone={statusTone(r.priority)}>{enumLabel(r.priority, t)}</Badge>
                </td>
                <td className="px-4 py-3 text-end">
                  <RowActions
                    record={r}
                    entityLabel={t("entity.rfi")}
                    endpoint="/rfis"
                    fields={rfiFields(t)}
                    canManage={canAnalyze}
                    onChanged={() => setRefresh((n) => n + 1)}
                  />
                </td>
              </tr>
            ))}
          </Table>
          {data.items.length === 0 && <EmptyState message={t("rfi.noneMatch")} />}
          <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
        </Card>
      )}

      {escalation && (
        <Modal title={t("rfi.escalationTitle", { n: escalation.overdue_count })} onClose={() => setEscalation(undefined)}>
          <div className="space-y-4">
            <ProviderTag provider={escalation.provider} model={escalation.model} />
            <LabelValue
              label={t("rfi.draftedMessage")}
              value={<p className="whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-slate-700">{escalation.escalation_message}</p>}
            />
            {escalation.overdue_count > 0 && (
              <RequestApprovalButton
                actionType="send_rfi_escalation"
                projectId={escalation.project_id}
                label={t("rfi.requestApprovalSend")}
                payload={{
                  overdue_count: escalation.overdue_count,
                  escalation_message: escalation.escalation_message,
                }}
              />
            )}
            {escalation.items.length > 0 && (
              <div>
                <div className="mb-2 text-xs font-medium text-slate-500">{t("rfi.overdueItems")}</div>
                <div className="space-y-2">
                  {escalation.items.map((it, i) => (
                    <div key={i} className="rounded-lg border border-slate-200 p-3">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs text-slate-500">{it.rfi_number}</span>
                        <div className="flex items-center gap-2">
                          <Badge tone="red">{t("rfi.daysOverdue", { n: it.days_overdue })}</Badge>
                          <Badge tone={statusTone(it.priority)}>{enumLabel(it.priority, t)}</Badge>
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
          title={t("rfi.new")}
          endpoint="/rfis"
          fields={rfiFields(t)}
          submitLabel={t("rfi.createRfi")}
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
          title={t("rfi.importTitle")}
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
