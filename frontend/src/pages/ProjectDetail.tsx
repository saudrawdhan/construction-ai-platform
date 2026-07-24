import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Plus } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { date, money, enumLabel } from "../lib/format";
import { useT } from "../lib/i18n";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorBox,
  Field,
  Input,
  PageHeader,
  Select,
  Spinner,
  Table,
  Tabs,
  Textarea,
  statusTone,
} from "../components/ui";
import type { Page } from "../lib/api";

interface Project {
  id: number;
  project_code: string;
  project_name: string;
  project_type: string;
  client_name: string;
  city: string;
  start_date: string | null;
  planned_finish: string | null;
  actual_finish: string | null;
  status: string;
  budget: string;
}
interface Risk {
  id: number;
  title: string;
  description: string | null;
  severity: string;
  likelihood: string | null;
  status: string;
  owner: string | null;
  created_at: string;
}

const SEVERITIES = ["Low", "Medium", "High", "Critical"];
const LIKELIHOODS = ["Low", "Medium", "High"];

type WorkspaceTab = "risks" | "rfis" | "orders" | "meetings" | "reports";

/** Fetches a project-scoped list once and renders it, so a project's own RFIs, orders, meetings and
 * site reports live on its detail page (the project workspace) using the existing filtered endpoints. */
function RelatedList<T extends { id: number }>({
  endpoint,
  head,
  renderRow,
  empty,
}: {
  endpoint: string;
  head: string[];
  renderRow: (item: T) => React.ReactNode;
  empty: string;
}) {
  const [items, setItems] = useState<T[]>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    api
      .get<Page<T>>(endpoint)
      .then((p) => setItems(p.items))
      .catch((e: ApiError) => setError(e.message));
  }, [endpoint]);

  if (error) return <div className="text-sm text-red-600">{error}</div>;
  if (!items) return <Spinner />;

  return (
    <Card>
      <Table head={head}>{items.map(renderRow)}</Table>
      {items.length === 0 && <EmptyState message={empty} />}
    </Card>
  );
}

function Detail({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs font-medium text-slate-500">{label}</div>
      <div className="mt-0.5 text-sm text-slate-800">{value}</div>
    </div>
  );
}

export default function ProjectDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const t = useT();
  const canEdit = user && ["admin", "project_manager"].includes(user.role);

  const [project, setProject] = useState<Project>();
  const [risks, setRisks] = useState<Risk[]>();
  const [error, setError] = useState<string>();
  const [wtab, setWtab] = useState<WorkspaceTab>("risks");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", severity: "Medium", likelihood: "Medium", owner: "" });
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string>();

  useEffect(() => {
    setError(undefined);
    Promise.all([api.get<Project>(`/projects/${id}`), api.get<Risk[]>(`/projects/${id}/risks`)])
      .then(([p, r]) => {
        setProject(p);
        setRisks(r);
      })
      .catch((e: ApiError) => setError(e.message));
  }, [id]);

  async function submitRisk(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setFormError(undefined);
    try {
      const created = await api.post<Risk>(`/projects/${id}/risks`, {
        title: form.title,
        description: form.description || null,
        severity: form.severity,
        likelihood: form.likelihood || null,
        owner: form.owner || null,
      });
      setRisks((prev) => [created, ...(prev ?? [])]);
      setForm({ title: "", description: "", severity: "Medium", likelihood: "Medium", owner: "" });
      setShowForm(false);
    } catch (err) {
      setFormError((err as ApiError).message);
    } finally {
      setSaving(false);
    }
  }

  if (error) return <ErrorBox message={error} />;
  if (!project || !risks) return <Spinner />;

  return (
    <div>
      <Link to="/projects" className="mb-3 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800">
        <ArrowLeft size={15} /> {t("nav.projects")}
      </Link>
      <PageHeader title={project.project_name} subtitle={`${project.project_code} · ${project.client_name}`} />

      <Card className="mb-6 p-5">
        <div className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4">
          <Detail label={t("common.status")} value={<Badge tone={statusTone(project.status)}>{enumLabel(project.status, t)}</Badge>} />
          <Detail label={t("field.type")} value={enumLabel(project.project_type, t)} />
          <Detail label={t("field.city")} value={project.city} />
          <Detail label={t("col.budget")} value={money(project.budget)} />
          <Detail label={t("pd.start")} value={date(project.start_date)} />
          <Detail label={t("pd.plannedFinish")} value={date(project.planned_finish)} />
          <Detail label={t("pd.actualFinish")} value={date(project.actual_finish)} />
        </div>
      </Card>

      <Tabs
        tabs={[
          { key: "risks", label: t("pd.riskRegister") },
          { key: "rfis", label: t("nav.rfis") },
          { key: "orders", label: t("pd.purchaseOrders") },
          { key: "meetings", label: t("nav.meetings") },
          { key: "reports", label: t("nav.siteReports") },
        ]}
        active={wtab}
        onChange={setWtab}
      />

      {wtab === "rfis" && (
        <RelatedList<{ id: number; rfi_number: string; subject: string; status: string; priority: string }>
          endpoint={`/rfis?project_id=${id}&size=100`}
          head={[t("col.rfi"), t("col.subject"), t("col.status"), t("col.priority")]}
          empty={t("pd.noRfis")}
          renderRow={(r) => (
            <tr key={r.id} className="hover:bg-slate-50">
              <td className="px-4 py-3 font-mono text-xs text-slate-500">{r.rfi_number}</td>
              <td className="px-4 py-3 text-slate-800">{r.subject}</td>
              <td className="px-4 py-3"><Badge tone={statusTone(r.status)}>{enumLabel(r.status, t)}</Badge></td>
              <td className="px-4 py-3"><Badge tone={statusTone(r.priority)}>{enumLabel(r.priority, t)}</Badge></td>
            </tr>
          )}
        />
      )}

      {wtab === "orders" && (
        <RelatedList<{ id: number; po_number: string; status: string; is_late: boolean; delay_days: number; promised_delivery: string | null }>
          endpoint={`/procurement/purchase-orders?project_id=${id}&size=100`}
          head={[t("col.po"), t("col.promised"), t("col.status"), t("col.delay")]}
          empty={t("pd.noOrders")}
          renderRow={(o) => (
            <tr key={o.id} className="hover:bg-slate-50">
              <td className="px-4 py-3 font-mono text-xs text-slate-500">{o.po_number}</td>
              <td className="px-4 py-3 text-slate-600">{date(o.promised_delivery)}</td>
              <td className="px-4 py-3"><Badge tone={statusTone(o.status)}>{enumLabel(o.status, t)}</Badge></td>
              <td className="px-4 py-3">
                {o.is_late ? <span className="font-medium text-red-600">{t("pd.daysLate", { n: o.delay_days })}</span> : <span className="text-emerald-600">{t("pd.onTime")}</span>}
              </td>
            </tr>
          )}
        />
      )}

      {wtab === "meetings" && (
        <RelatedList<{ id: number; title: string; meeting_type: string; meeting_date: string | null }>
          endpoint={`/meetings?project_id=${id}&size=100`}
          head={[t("col.title"), t("col.type"), t("col.date")]}
          empty={t("pd.noMeetings")}
          renderRow={(m) => (
            <tr key={m.id} className="hover:bg-slate-50">
              <td className="px-4 py-3 font-medium text-slate-800">{m.title}</td>
              <td className="px-4 py-3"><Badge tone="slate">{enumLabel(m.meeting_type, t)}</Badge></td>
              <td className="px-4 py-3 text-slate-600">{date(m.meeting_date)}</td>
            </tr>
          )}
        />
      )}

      {wtab === "reports" && (
        <RelatedList<{ id: number; report_date: string | null; weather: string; summary: string }>
          endpoint={`/site-reports?project_id=${id}&size=100`}
          head={[t("col.date"), t("col.weather"), t("col.summary")]}
          empty={t("pd.noReports")}
          renderRow={(s) => (
            <tr key={s.id} className="hover:bg-slate-50">
              <td className="whitespace-nowrap px-4 py-3 text-slate-600">{date(s.report_date)}</td>
              <td className="px-4 py-3 text-slate-600">{enumLabel(s.weather, t)}</td>
              <td className="max-w-md px-4 py-3 text-slate-700"><div className="truncate">{s.summary}</div></td>
            </tr>
          )}
        />
      )}

      {wtab === "risks" && (
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-900">{t("pd.riskRegister")}</h2>
        {canEdit && (
          <Button variant={showForm ? "secondary" : "primary"} onClick={() => setShowForm((v) => !v)}>
            <Plus size={16} /> {showForm ? t("common.cancel") : t("pd.addRisk")}
          </Button>
        )}
      </div>
      )}

      {wtab === "risks" && showForm && canEdit && (
        <Card className="mb-4 p-5">
          <form onSubmit={submitRisk} className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Field label={t("col.title")}>
                <Input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
              </Field>
            </div>
            <div className="sm:col-span-2">
              <Field label={t("field.description")}>
                <Textarea
                  rows={2}
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                />
              </Field>
            </div>
            <Field label={t("field.severity")}>
              <Select value={form.severity} onChange={(e) => setForm({ ...form, severity: e.target.value })}>
                {SEVERITIES.map((s) => (
                  <option key={s} value={s}>{enumLabel(s, t)}</option>
                ))}
              </Select>
            </Field>
            <Field label={t("field.likelihood")}>
              <Select value={form.likelihood} onChange={(e) => setForm({ ...form, likelihood: e.target.value })}>
                {LIKELIHOODS.map((s) => (
                  <option key={s} value={s}>{enumLabel(s, t)}</option>
                ))}
              </Select>
            </Field>
            <Field label={t("field.owner")}>
              <Input value={form.owner} onChange={(e) => setForm({ ...form, owner: e.target.value })} />
            </Field>
            <div className="flex items-end">
              <Button type="submit" disabled={saving}>
                {saving ? t("common.saving") : t("pd.saveRisk")}
              </Button>
            </div>
            {formError && (
              <div className="sm:col-span-2">
                <ErrorBox message={formError} />
              </div>
            )}
          </form>
        </Card>
      )}

      {wtab === "risks" && (
      <Card>
        <Table head={[t("col.title"), t("col.severity"), t("col.likelihood"), t("col.status"), t("col.owner"), t("col.raised")]}>
          {risks.map((r) => (
            <tr key={r.id} className="hover:bg-slate-50">
              <td className="px-4 py-3">
                <div className="font-medium text-slate-800">{r.title}</div>
                {r.description && <div className="mt-0.5 text-xs text-slate-500">{r.description}</div>}
              </td>
              <td className="px-4 py-3">
                <Badge tone={statusTone(r.severity)}>{enumLabel(r.severity, t)}</Badge>
              </td>
              <td className="px-4 py-3 text-slate-600">{r.likelihood ? enumLabel(r.likelihood, t) : "—"}</td>
              <td className="px-4 py-3">
                <Badge tone={statusTone(r.status)}>{enumLabel(r.status, t)}</Badge>
              </td>
              <td className="px-4 py-3 text-slate-600">{r.owner ?? "—"}</td>
              <td className="px-4 py-3 text-slate-600">{date(r.created_at)}</td>
            </tr>
          ))}
        </Table>
        {risks.length === 0 && <EmptyState message={t("pd.noRisks")} />}
      </Card>
      )}
    </div>
  );
}
