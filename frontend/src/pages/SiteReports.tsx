import { useEffect, useState } from "react";
import { Sparkles, CheckCircle2, AlertTriangle, TriangleAlert, Plus, Upload } from "lucide-react";
import { api, ApiError, type Page } from "../lib/api";
import { useAuth } from "../lib/auth";
import { date, enumLabel } from "../lib/format";
import { useT, type Translate } from "../lib/i18n";
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
  Spinner,
  Table,
  Textarea,
} from "../components/ui";
import CreateModal from "../components/CreateModal";
import ImportModal from "../components/ImportModal";
import RowActions from "../components/RowActions";
import ProjectPicker from "../components/ProjectPicker";

const siteReportFields = (t: Translate) => [
  { name: "project_id", label: t("common.project"), type: "project" as const, required: true },
  { name: "report_date", label: t("common.date"), type: "date" as const },
  {
    name: "weather",
    label: t("field.weather"),
    type: "select" as const,
    options: ["Clear", "Cloudy", "Dusty", "Humid", "Rain"],
    initial: "Clear",
  },
  { name: "summary", label: t("field.summary"), type: "textarea" as const, required: true },
];

interface SiteReport {
  id: number;
  project_id: number;
  report_date: string | null;
  weather: string;
  summary: string;
}
interface ActivityRow {
  id: number;
  activity_date: string | null;
  activity_description: string;
  manpower_count: number;
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
  const t = useT();
  const canAnalyze = !!user && ["admin", "project_manager", "site_engineer"].includes(user.role);
  const [data, setData] = useState<Page<SiteReport>>();
  const [projects, setProjects] = useState<ProjectOption[]>([]);
  const [error, setError] = useState<string>();
  const [page, setPage] = useState(1);
  const [projectFilter, setProjectFilter] = useState("");
  const [open, setOpen] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [detail, setDetail] = useState<{ report: SiteReport; activities: ActivityRow[] }>();
  const [refresh, setRefresh] = useState(0);

  async function openDetail(r: SiteReport) {
    try {
      const activities = await api.get<ActivityRow[]>(`/site-reports/${r.id}/activities`);
      setDetail({ report: r, activities });
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
    api.get<Page<SiteReport>>(`/site-reports?${params}`).then(setData).catch((e) => setError(e.message));
  }, [page, projectFilter, refresh]);

  const projectName = (id: number) => projects.find((p) => p.id === id)?.project_name ?? `#${id}`;

  return (
    <div>
      <PageHeader title={t("nav.siteReports")} subtitle={t("sr.subtitle")} />

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
        {canAnalyze && (
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setShowImport(true)}>
              <Upload size={15} /> {t("common.import")}
            </Button>
            <Button variant="secondary" onClick={() => setShowCreate(true)}>
              <Plus size={15} /> {t("sr.new")}
            </Button>
            <Button onClick={() => setOpen(true)}>
              <Sparkles size={15} /> {t("sr.analyzeReport")}
            </Button>
          </div>
        )}
      </div>

      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
      {!data && !error && <Spinner />}

      {data && (
        <Card>
          <Table head={[t("col.date"), t("col.project"), t("col.weather"), t("col.summary"), ""]}>
            {data.items.map((r) => (
              <tr key={r.id} className="hover:bg-slate-50">
                <td className="whitespace-nowrap px-4 py-3 text-slate-600">{date(r.report_date)}</td>
                <td className="whitespace-nowrap px-4 py-3 text-slate-600">{projectName(r.project_id)}</td>
                <td className="px-4 py-3 text-slate-600">{enumLabel(r.weather, t)}</td>
                <td className="max-w-md px-4 py-3 text-slate-700">
                  <button
                    onClick={() => openDetail(r)}
                    className="block max-w-md truncate text-start hover:text-blue-700 hover:underline"
                    title={t("sr.viewActivities")}
                  >
                    {r.summary}
                  </button>
                </td>
                <td className="px-4 py-3 text-end">
                  <RowActions
                    record={r}
                    entityLabel={t("entity.siteReport")}
                    endpoint="/site-reports"
                    fields={siteReportFields(t)}
                    canManage={canAnalyze}
                    onChanged={() => setRefresh((n) => n + 1)}
                  />
                </td>
              </tr>
            ))}
          </Table>
          {data.items.length === 0 && <EmptyState message={t("sr.noneMatch")} />}
          <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
        </Card>
      )}

      {detail && (
        <Modal title={t("sr.detailTitle", { date: date(detail.report.report_date) })} onClose={() => setDetail(undefined)}>
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <span>{projectName(detail.report.project_id)}</span>
              <span>·</span>
              <span>{t("sr.weatherLabel", { w: enumLabel(detail.report.weather, t) })}</span>
            </div>
            <p className="rounded-lg bg-slate-50 p-3 text-sm text-slate-700">{detail.report.summary}</p>
            <div>
              <div className="mb-2 text-xs font-medium text-slate-500">
                {t("sr.activities", { n: detail.activities.length })}
              </div>
              {detail.activities.length === 0 ? (
                <p className="text-sm text-slate-400">{t("sr.noActivities")}</p>
              ) : (
                <div className="space-y-1.5">
                  {detail.activities.map((a) => (
                    <div key={a.id} className="flex items-start justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2 text-sm">
                      <span className="text-slate-700">{a.activity_description}</span>
                      <span className="flex-shrink-0 text-xs text-slate-400">
                        {t("sr.workers", { n: a.manpower_count })}{a.activity_date ? ` · ${date(a.activity_date)}` : ""}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </Modal>
      )}

      {open && <AnalyzeModal projects={projects} onClose={() => setOpen(false)} />}

      {showCreate && (
        <CreateModal
          title={t("sr.new")}
          endpoint="/site-reports"
          fields={siteReportFields(t)}
          submitLabel={t("sr.createSr")}
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
          title={t("sr.importTitle")}
          importPath="/site-reports/import"
          templatePath="/site-reports/import/template"
          templateFilename="site_reports_template.csv"
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

function AnalyzeModal({ projects, onClose }: { projects: ProjectOption[]; onClose: () => void }) {
  const t = useT();
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
    <Modal title={t("sr.analyzeTitle")} onClose={onClose}>
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
          <Field label={t("field.reportDate")}>
            <Input type="date" value={reportDate} onChange={(e) => setReportDate(e.target.value)} />
          </Field>
        </div>
        <Field label={t("sr.reportText")}>
          <Textarea
            rows={6}
            placeholder={t("sr.reportPlaceholder")}
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
            {t("sr.persistMemory")}
          </label>
          <Button disabled={busy || !projectId || text.trim().length < 10} onClick={run}>
            <Sparkles size={15} /> {busy ? t("sr.analyzing") : t("common.analyze")}
          </Button>
        </div>
        {error && <div className="text-sm text-red-600">{error}</div>}

        {result && (
          <div className="space-y-4 border-t border-slate-100 pt-4">
            <ProviderTag provider={result.provider} model={result.model} />
            <LabelValue label={t("field.summary")} value={<p className="whitespace-pre-wrap">{result.summary}</p>} />
            {result.completed_work.length > 0 && (
              <div>
                <div className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-emerald-600">
                  <CheckCircle2 size={13} /> {t("sr.completedWork")}
                </div>
                <BulletList items={result.completed_work} tone="text-slate-700" />
              </div>
            )}
            {result.delays.length > 0 && (
              <div>
                <div className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-amber-600">
                  <AlertTriangle size={13} /> {t("sr.delays")}
                </div>
                <BulletList items={result.delays} tone="text-amber-700" />
              </div>
            )}
            {result.risks.length > 0 && (
              <div>
                <div className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-red-600">
                  <TriangleAlert size={13} /> {t("sr.risks")}
                </div>
                <BulletList items={result.risks} tone="text-red-700" />
              </div>
            )}
            {result.manpower_note && <LabelValue label={t("sr.manpower")} value={result.manpower_note} />}
            <LabelValue label={t("sr.recommendedEscalation")} value={result.recommended_escalation} />
          </div>
        )}
      </div>
    </Modal>
  );
}
