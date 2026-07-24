import { useEffect, useState } from "react";
import { Building2, AlertTriangle, Clock, Truck, FileWarning, ShieldAlert, ShoppingCart, FileBarChart2 } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useT } from "../lib/i18n";
import {
  Button,
  Card,
  Field,
  PageHeader,
  ProviderTag,
  StatCard,
} from "../components/ui";
import ProjectPicker from "../components/ProjectPicker";

interface ProjectOption {
  id: number;
  project_name: string;
}
interface ExecutiveReport {
  scope: string;
  projects_total: number;
  delayed_or_onhold: number;
  overdue_rfis: number;
  late_purchase_orders: number;
  open_ncrs: number;
  recent_safety_events: number;
  pending_purchase_requests: number;
  highlights: string[];
  narrative: string;
  summary_id: number | null;
  provider: string;
  model: string;
}

export default function Reports() {
  const { user } = useAuth();
  const t = useT();
  const canGenerate = !!user && ["admin", "executive", "project_manager"].includes(user.role);
  const [projects, setProjects] = useState<ProjectOption[]>([]);
  const [projectId, setProjectId] = useState("");
  const [store, setStore] = useState(false);
  const [report, setReport] = useState<ExecutiveReport>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  useEffect(() => {
    api.get<{ items: ProjectOption[] }>("/projects?size=100").then((p) => setProjects(p.items)).catch(() => {});
  }, []);

  async function generate() {
    setBusy(true);
    setError(undefined);
    try {
      setReport(
        await api.post<ExecutiveReport>("/reports/executive-weekly", {
          project_id: projectId ? Number(projectId) : null,
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
    <div>
      <PageHeader title={t("report.title")} subtitle={t("report.subtitle")} />

      {!canGenerate ? (
        <Card className="px-4 py-12 text-center text-sm text-slate-400">
          {t("report.restricted")}
        </Card>
      ) : (
        <Card className="mb-6 p-5">
          <div className="flex flex-wrap items-end gap-3">
            <Field label={t("report.scope")}>
              <div className="w-56">
                <ProjectPicker
                  projects={projects}
                  value={projectId}
                  onChange={setProjectId}
                  placeholder={t("report.wholePortfolio")}
                />
              </div>
            </Field>
            <label className="flex h-10 items-center gap-2 text-sm text-slate-600">
              <input
                type="checkbox"
                checked={store}
                onChange={(e) => setStore(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300"
              />
              {t("report.saveMemory")}
            </label>
            <Button disabled={busy} onClick={generate}>
              <FileBarChart2 size={15} /> {busy ? t("report.generating") : t("report.generate")}
            </Button>
          </div>
          {error && <div className="mt-3 text-sm text-red-600">{error}</div>}
        </Card>
      )}

      {report && (
        <div>
          <div className="mb-4 flex items-center gap-2 text-sm text-slate-500">
            <span className="font-medium text-slate-700">{t("report.scopeLabel", { scope: report.scope })}</span>
            <ProviderTag provider={report.provider} model={report.model} />
            {report.summary_id && <span className="text-xs text-slate-400">{t("report.savedAs", { id: report.summary_id })}</span>}
          </div>

          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatCard label={t("stat.projects")} value={report.projects_total} icon={Building2} tone="blue" />
            <StatCard label={t("stat.delayedOrHold")} value={report.delayed_or_onhold} icon={AlertTriangle} tone="red" />
            <StatCard label={t("stat.overdueRfis")} value={report.overdue_rfis} icon={Clock} tone="amber" />
            <StatCard label={t("stat.latePos")} value={report.late_purchase_orders} icon={Truck} tone="amber" />
            <StatCard label={t("stat.openNcrs")} value={report.open_ncrs} icon={FileWarning} tone="amber" />
            <StatCard label={t("stat.safetyEvents90d")} value={report.recent_safety_events} icon={ShieldAlert} tone="red" />
            <StatCard label={t("stat.pendingPrs")} value={report.pending_purchase_requests} icon={ShoppingCart} tone="slate" />
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            <Card>
              <div className="border-b border-slate-100 px-5 py-3 text-sm font-semibold text-slate-800">{t("report.highlights")}</div>
              <ul className="space-y-2 p-5">
                {report.highlights.map((h, i) => (
                  <li key={i} className="flex gap-2 text-sm text-slate-700">
                    <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-blue-500" />
                    {h}
                  </li>
                ))}
                {report.highlights.length === 0 && <li className="text-sm text-slate-400">{t("report.noHighlights")}</li>}
              </ul>
            </Card>
            <Card>
              <div className="border-b border-slate-100 px-5 py-3 text-sm font-semibold text-slate-800">{t("report.narrative")}</div>
              <p className="whitespace-pre-wrap p-5 text-sm leading-relaxed text-slate-700">{report.narrative}</p>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
