import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Plus } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { date, money } from "../lib/format";
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
  Textarea,
  statusTone,
} from "../components/ui";

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
  const canEdit = user && ["admin", "project_manager"].includes(user.role);

  const [project, setProject] = useState<Project>();
  const [risks, setRisks] = useState<Risk[]>();
  const [error, setError] = useState<string>();
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
        <ArrowLeft size={15} /> Projects
      </Link>
      <PageHeader title={project.project_name} subtitle={`${project.project_code} · ${project.client_name}`} />

      <Card className="mb-6 p-5">
        <div className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4">
          <Detail label="Status" value={<Badge tone={statusTone(project.status)}>{project.status}</Badge>} />
          <Detail label="Type" value={project.project_type} />
          <Detail label="City" value={project.city} />
          <Detail label="Budget" value={money(project.budget)} />
          <Detail label="Start" value={date(project.start_date)} />
          <Detail label="Planned Finish" value={date(project.planned_finish)} />
          <Detail label="Actual Finish" value={date(project.actual_finish)} />
        </div>
      </Card>

      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-900">Risk Register</h2>
        {canEdit && (
          <Button variant={showForm ? "secondary" : "primary"} onClick={() => setShowForm((v) => !v)}>
            <Plus size={16} /> {showForm ? "Cancel" : "Add Risk"}
          </Button>
        )}
      </div>

      {showForm && canEdit && (
        <Card className="mb-4 p-5">
          <form onSubmit={submitRisk} className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Field label="Title">
                <Input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
              </Field>
            </div>
            <div className="sm:col-span-2">
              <Field label="Description">
                <Textarea
                  rows={2}
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                />
              </Field>
            </div>
            <Field label="Severity">
              <Select value={form.severity} onChange={(e) => setForm({ ...form, severity: e.target.value })}>
                {SEVERITIES.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </Select>
            </Field>
            <Field label="Likelihood">
              <Select value={form.likelihood} onChange={(e) => setForm({ ...form, likelihood: e.target.value })}>
                {LIKELIHOODS.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </Select>
            </Field>
            <Field label="Owner">
              <Input value={form.owner} onChange={(e) => setForm({ ...form, owner: e.target.value })} />
            </Field>
            <div className="flex items-end">
              <Button type="submit" disabled={saving}>
                {saving ? "Saving…" : "Save Risk"}
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

      <Card>
        <Table head={["Title", "Severity", "Likelihood", "Status", "Owner", "Raised"]}>
          {risks.map((r) => (
            <tr key={r.id} className="hover:bg-slate-50">
              <td className="px-4 py-3">
                <div className="font-medium text-slate-800">{r.title}</div>
                {r.description && <div className="mt-0.5 text-xs text-slate-500">{r.description}</div>}
              </td>
              <td className="px-4 py-3">
                <Badge tone={statusTone(r.severity)}>{r.severity}</Badge>
              </td>
              <td className="px-4 py-3 text-slate-600">{r.likelihood ?? "—"}</td>
              <td className="px-4 py-3">
                <Badge tone={statusTone(r.status)}>{r.status}</Badge>
              </td>
              <td className="px-4 py-3 text-slate-600">{r.owner ?? "—"}</td>
              <td className="px-4 py-3 text-slate-600">{date(r.created_at)}</td>
            </tr>
          ))}
        </Table>
        {risks.length === 0 && <EmptyState message="No risks recorded for this project yet." />}
      </Card>
    </div>
  );
}
