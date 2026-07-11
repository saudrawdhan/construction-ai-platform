import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Upload } from "lucide-react";
import { api, ApiError, type Page } from "../lib/api";
import { useAuth } from "../lib/auth";
import { money } from "../lib/format";
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

const PROJECT_FIELDS = [
  { name: "project_code", label: "Project code", required: true },
  { name: "project_name", label: "Project name", required: true, full: true },
  { name: "project_type", label: "Type", type: "select" as const, options: TYPES, initial: "School" },
  { name: "client_name", label: "Client", required: true },
  { name: "city", label: "City", required: true },
  { name: "status", label: "Status", type: "select" as const, options: STATUSES, initial: "Active" },
  { name: "start_date", label: "Start date", type: "date" as const },
  { name: "planned_finish", label: "Planned finish", type: "date" as const },
  { name: "budget", label: "Budget (SAR)", type: "number" as const },
];

export default function Projects() {
  const navigate = useNavigate();
  const { user } = useAuth();
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
        <PageHeader title="Projects" subtitle="Portfolio of construction projects" />
        {canCreate && (
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setShowImport(true)}>
              <Upload size={16} /> Import
            </Button>
            <Button onClick={() => setShowForm(true)}>
              <Plus size={16} /> New Project
            </Button>
          </div>
        )}
      </div>

      <FilterBar>
        <Field label="Status">
          <Select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All statuses</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="City">
          <Input
            placeholder="Filter by city"
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
          <Table head={["Code", "Project", "Type", "City", "Status", "Budget", ""]}>
            {data.items.map((p) => (
              <tr
                key={p.id}
                onClick={() => navigate(`/projects/${p.id}`)}
                className="cursor-pointer hover:bg-slate-50"
              >
                <td className="px-4 py-3 font-mono text-xs text-slate-500">{p.project_code}</td>
                <td className="px-4 py-3 font-medium text-slate-800">{p.project_name}</td>
                <td className="px-4 py-3 text-slate-600">{p.project_type}</td>
                <td className="px-4 py-3 text-slate-600">{p.city}</td>
                <td className="px-4 py-3">
                  <Badge tone={statusTone(p.status)}>{p.status}</Badge>
                </td>
                <td className="px-4 py-3 text-slate-600">{money(p.budget)}</td>
                <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                  <RowActions
                    record={p}
                    entityLabel="Project"
                    endpoint="/projects"
                    fields={PROJECT_FIELDS}
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
                  ? "No projects match these filters."
                  : canCreate
                    ? "No projects yet. Use “New Project” to add your first one."
                    : "No projects yet."
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
          title="Import Projects"
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
    <Modal title="New Project" onClose={onClose}>
      <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
        <Field label="Project code">
          <Input required value={form.project_code} onChange={(e) => set("project_code", e.target.value)} placeholder="PRJ-0100" />
        </Field>
        <Field label="Project name">
          <Input required value={form.project_name} onChange={(e) => set("project_name", e.target.value)} />
        </Field>
        <Field label="Type">
          <Select value={form.project_type} onChange={(e) => set("project_type", e.target.value)}>
            {TYPES.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </Select>
        </Field>
        <Field label="Client">
          <Input required value={form.client_name} onChange={(e) => set("client_name", e.target.value)} />
        </Field>
        <Field label="City">
          <Input required value={form.city} onChange={(e) => set("city", e.target.value)} />
        </Field>
        <Field label="Status">
          <Select value={form.status} onChange={(e) => set("status", e.target.value)}>
            {STATUSES.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </Select>
        </Field>
        <Field label="Start date">
          <Input type="date" value={form.start_date} onChange={(e) => set("start_date", e.target.value)} />
        </Field>
        <Field label="Planned finish">
          <Input type="date" value={form.planned_finish} onChange={(e) => set("planned_finish", e.target.value)} />
        </Field>
        <Field label="Budget (SAR)">
          <Input type="number" min="0" value={form.budget} onChange={(e) => set("budget", e.target.value)} placeholder="0" />
        </Field>
        <div className="sm:col-span-2">
          {error && <ErrorBox message={error} />}
          <div className="mt-2 flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? "Creating…" : "Create Project"}
            </Button>
          </div>
        </div>
      </form>
    </Modal>
  );
}
