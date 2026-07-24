import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Upload } from "lucide-react";
import { api, ApiError, type Page } from "../lib/api";
import { useAuth } from "../lib/auth";
import { money, enumLabel } from "../lib/format";
import { useT, type Translate } from "../lib/i18n";
import ImportModal from "../components/ImportModal";
import RowActions from "../components/RowActions";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorBox,
  Field,
  FilterBar,
  Input,
  Modal,
  PageHeader,
  Pagination,
  Select,
  Spinner,
  Table,
  statusTone,
} from "../components/ui";

interface Project {
  id: number;
  project_code: string;
  project_name: string;
  project_type: string;
  client_name: string;
  city: string;
  status: string;
  budget: string;
}

const STATUSES = ["Active", "Delayed", "On Hold", "Completed"];
const TYPES = ["School", "Tower", "Hospital", "Warehouse", "Infrastructure", "Residential"];

const projectFields = (t: Translate) => [
  { name: "project_code", label: t("field.projectCode"), required: true },
  { name: "project_name", label: t("field.projectName"), required: true, full: true },
  { name: "project_type", label: t("field.type"), type: "select" as const, options: TYPES, initial: "School" },
  { name: "client_name", label: t("field.client"), required: true },
  { name: "city", label: t("field.city"), required: true },
  { name: "status", label: t("field.status"), type: "select" as const, options: STATUSES, initial: "Active" },
  { name: "start_date", label: t("field.startDate"), type: "date" as const },
  { name: "planned_finish", label: t("field.plannedFinish"), type: "date" as const },
  { name: "budget", label: t("field.budgetSar"), type: "number" as const },
];

export default function Projects() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const t = useT();
  const canCreate = !!user && ["admin", "project_manager"].includes(user.role);
  const [data, setData] = useState<Page<Project>>();
  const [error, setError] = useState<string>();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [city, setCity] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [showImport, setShowImport] = useState(false);

  const load = useCallback(() => {
    const params = new URLSearchParams({ page: String(page), size: "20" });
    if (status) params.set("status", status);
    if (city) params.set("city", city);
    setError(undefined);
    api
      .get<Page<Project>>(`/projects?${params}`)
      .then(setData)
      .catch((e: ApiError) => setError(e.message));
  }, [page, status, city]);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = Boolean(status || city);

  return (
    <div>
      <div className="flex items-start justify-between">
        <PageHeader title={t("nav.projects")} subtitle={t("project.subtitle")} />
        {canCreate && (
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setShowImport(true)}>
              <Upload size={16} /> {t("common.import")}
            </Button>
            <Button onClick={() => setShowForm(true)}>
              <Plus size={16} /> {t("project.new")}
            </Button>
          </div>
        )}
      </div>

      <FilterBar>
        <Field label={t("field.status")}>
          <Select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
          >
            <option value="">{t("project.allStatuses")}</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {enumLabel(s, t)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("field.city")}>
          <Input
            placeholder={t("project.filterCity")}
            value={city}
            onChange={(e) => {
              setCity(e.target.value);
              setPage(1);
            }}
          />
        </Field>
      </FilterBar>

      {error && <div className="text-sm text-red-600">{error}</div>}
      {!data && !error && <Spinner />}

      {data && (
        <Card>
          <Table head={[t("col.code"), t("col.project"), t("col.type"), t("col.city"), t("col.status"), t("col.budget"), ""]}>
            {data.items.map((p) => (
              <tr
                key={p.id}
                onClick={() => navigate(`/projects/${p.id}`)}
                className="cursor-pointer hover:bg-slate-50"
              >
                <td className="px-4 py-3 font-mono text-xs text-slate-500">{p.project_code}</td>
                <td className="px-4 py-3 font-medium text-slate-800">{p.project_name}</td>
                <td className="px-4 py-3 text-slate-600">{enumLabel(p.project_type, t)}</td>
                <td className="px-4 py-3 text-slate-600">{p.city}</td>
                <td className="px-4 py-3">
                  <Badge tone={statusTone(p.status)}>{enumLabel(p.status, t)}</Badge>
                </td>
                <td className="px-4 py-3 text-slate-600">{money(p.budget)}</td>
                <td className="px-4 py-3 text-end" onClick={(e) => e.stopPropagation()}>
                  <RowActions
                    record={p}
                    entityLabel={t("entity.project")}
                    endpoint="/projects"
                    fields={projectFields(t)}
                    canManage={canCreate}
                    onChanged={load}
                  />
                </td>
              </tr>
            ))}
          </Table>
          {data.items.length === 0 && (
            <EmptyState
              message={
                filtered
                  ? t("project.noneMatch")
                  : canCreate
                    ? t("project.noneYetCreate")
                    : t("project.noneYet")
              }
            />
          )}
          <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
        </Card>
      )}

      {showForm && (
        <NewProjectModal
          onClose={() => setShowForm(false)}
          onCreated={() => {
            setShowForm(false);
            setPage(1);
            load();
          }}
        />
      )}

      {showImport && (
        <ImportModal
          title={t("project.importTitle")}
          importPath="/projects/import"
          templatePath="/projects/import/template"
          templateFilename="projects_template.csv"
          onClose={() => setShowImport(false)}
          onImported={() => {
            setPage(1);
            load();
          }}
        />
      )}
    </div>
  );
}

function NewProjectModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const t = useT();
  const [form, setForm] = useState({
    project_code: "",
    project_name: "",
    project_type: "School",
    client_name: "",
    city: "",
    status: "Active",
    start_date: "",
    planned_finish: "",
    budget: "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();

  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(undefined);
    try {
      await api.post("/projects", {
        project_code: form.project_code,
        project_name: form.project_name,
        project_type: form.project_type,
        client_name: form.client_name,
        city: form.city,
        status: form.status,
        start_date: form.start_date || null,
        planned_finish: form.planned_finish || null,
        budget: form.budget || "0",
      });
      onCreated();
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal title={t("project.new")} onClose={onClose}>
      <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
        <Field label={t("field.projectCode")}>
          <Input required value={form.project_code} onChange={(e) => set("project_code", e.target.value)} placeholder="PRJ-0100" />
        </Field>
        <Field label={t("field.projectName")}>
          <Input required value={form.project_name} onChange={(e) => set("project_name", e.target.value)} />
        </Field>
        <Field label={t("field.type")}>
          <Select value={form.project_type} onChange={(e) => set("project_type", e.target.value)}>
            {TYPES.map((o) => (
              <option key={o} value={o}>{enumLabel(o, t)}</option>
            ))}
          </Select>
        </Field>
        <Field label={t("field.client")}>
          <Input required value={form.client_name} onChange={(e) => set("client_name", e.target.value)} />
        </Field>
        <Field label={t("field.city")}>
          <Input required value={form.city} onChange={(e) => set("city", e.target.value)} />
        </Field>
        <Field label={t("field.status")}>
          <Select value={form.status} onChange={(e) => set("status", e.target.value)}>
            {STATUSES.map((s) => (
              <option key={s} value={s}>{enumLabel(s, t)}</option>
            ))}
          </Select>
        </Field>
        <Field label={t("field.startDate")}>
          <Input type="date" value={form.start_date} onChange={(e) => set("start_date", e.target.value)} />
        </Field>
        <Field label={t("field.plannedFinish")}>
          <Input type="date" value={form.planned_finish} onChange={(e) => set("planned_finish", e.target.value)} />
        </Field>
        <Field label={t("field.budgetSar")}>
          <Input type="number" min="0" value={form.budget} onChange={(e) => set("budget", e.target.value)} placeholder="0" />
        </Field>
        <div className="sm:col-span-2">
          {error && <ErrorBox message={error} />}
          <div className="mt-2 flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={onClose}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? t("project.creating") : t("project.createProject")}
            </Button>
          </div>
        </div>
      </form>
    </Modal>
  );
}
