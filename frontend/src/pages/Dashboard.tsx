import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Building2,
  AlertTriangle,
  Clock,
  Truck,
  Users,
  Scale,
  ArrowRight,
  CheckCircle2,
} from "lucide-react";
import { api, type Page } from "../lib/api";
import { useAuth } from "../lib/auth";
import { money } from "../lib/format";
import {
  Button,
  Card,
  EmptyState,
  PageHeader,
  StatCard,
  Badge,
  Table,
  Spinner,
  ErrorBox,
  statusTone,
} from "../components/ui";

interface Project {
  id: number;
  project_code: string;
  project_name: string;
  city: string;
  status: string;
  budget: string;
}
interface Rfi {
  rfi_number: string;
  subject: string;
  discipline: string;
  required_date: string | null;
  priority: string;
}

async function total(path: string): Promise<number> {
  const p = await api.get<Page<unknown>>(path);
  return p.total;
}

export default function Dashboard() {
  const { user } = useAuth();
  const canCreate = !!user && ["admin", "project_manager"].includes(user.role);
  const [stats, setStats] = useState<Record<string, number>>();
  const [delayed, setDelayed] = useState<Project[]>([]);
  const [overdue, setOverdue] = useState<Rfi[]>([]);
  const [error, setError] = useState<string>();

  useEffect(() => {
    Promise.all([
      total("/projects?size=1"),
      total("/projects?status=Delayed&size=1"),
      total("/projects?status=On Hold&size=1"),
      total("/rfis?overdue=true&size=1"),
      total("/procurement/purchase-orders?is_late=true&size=1"),
      total("/suppliers?size=1"),
      total("/claims?size=1"),
      api.get<Page<Project>>("/projects?status=Delayed&size=6"),
      api.get<Page<Rfi>>("/rfis?overdue=true&size=6"),
    ])
      .then(([projects, del, hold, rfis, latePo, suppliers, claims, delList, rfiList]) => {
        setStats({ projects, delayedOrHold: del + hold, rfis, latePo, suppliers, claims });
        setDelayed(delList.items);
        setOverdue(rfiList.items);
      })
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <ErrorBox message={error} />;
  if (!stats) return <Spinner />;

  return (
    <div>
      <PageHeader title="Executive Dashboard" subtitle="Portfolio health across all projects" />

      {stats.projects === 0 ? (
        <EmptyWorkspace canCreate={canCreate} hasSuppliers={stats.suppliers > 0} />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-6">
            <StatCard label="Projects" value={stats.projects} icon={Building2} tone="blue" />
            <StatCard label="Delayed / On Hold" value={stats.delayedOrHold} icon={AlertTriangle} tone="red" />
            <StatCard label="Overdue RFIs" value={stats.rfis} icon={Clock} tone="amber" />
            <StatCard label="Late POs" value={stats.latePo} icon={Truck} tone="amber" />
            <StatCard label="Suppliers" value={stats.suppliers} icon={Users} tone="slate" />
            <StatCard label="Claims" value={stats.claims} icon={Scale} tone="slate" />
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            <Card>
              <div className="border-b border-slate-100 px-5 py-3 text-sm font-semibold text-slate-800">
                Delayed &amp; On-Hold Projects
              </div>
              {delayed.length === 0 ? (
                <PositiveEmpty message="No delayed or on-hold projects — the portfolio is on track." />
              ) : (
                <Table head={["Code", "Project", "City", "Status", "Budget"]}>
                  {delayed.map((p) => (
                    <tr key={p.id} className="hover:bg-slate-50">
                      <td className="px-4 py-3 font-mono text-xs text-slate-500">{p.project_code}</td>
                      <td className="px-4 py-3 font-medium text-slate-800">{p.project_name}</td>
                      <td className="px-4 py-3 text-slate-600">{p.city}</td>
                      <td className="px-4 py-3">
                        <Badge tone={statusTone(p.status)}>{p.status}</Badge>
                      </td>
                      <td className="px-4 py-3 text-slate-600">{money(p.budget)}</td>
                    </tr>
                  ))}
                </Table>
              )}
            </Card>

            <Card>
              <div className="border-b border-slate-100 px-5 py-3 text-sm font-semibold text-slate-800">
                Most Overdue RFIs
              </div>
              {overdue.length === 0 ? (
                <PositiveEmpty message="No overdue RFIs — nothing needs escalation right now." />
              ) : (
                <Table head={["RFI", "Subject", "Discipline", "Due", "Priority"]}>
                  {overdue.map((r) => (
                    <tr key={r.rfi_number} className="hover:bg-slate-50">
                      <td className="px-4 py-3 font-mono text-xs text-slate-500">{r.rfi_number}</td>
                      <td className="px-4 py-3 text-slate-800">{r.subject}</td>
                      <td className="px-4 py-3 text-slate-600">{r.discipline}</td>
                      <td className="px-4 py-3 text-slate-600">{r.required_date}</td>
                      <td className="px-4 py-3">
                        <Badge tone={statusTone(r.priority)}>{r.priority}</Badge>
                      </td>
                    </tr>
                  ))}
                </Table>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}

function PositiveEmpty({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-2 px-5 py-8 text-sm text-slate-500">
      <CheckCircle2 size={16} className="text-emerald-500" />
      {message}
    </div>
  );
}

function EmptyWorkspace({ canCreate, hasSuppliers }: { canCreate: boolean; hasSuppliers: boolean }) {
  return (
    <Card>
      <div className="mx-auto max-w-xl px-6 py-12 text-center">
        <span className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
          <Building2 size={26} />
        </span>
        <h2 className="text-lg font-semibold text-slate-900">Your workspace is ready</h2>
        <p className="mx-auto mt-2 text-sm text-slate-600">
          No projects have been added yet. Once you create your first project, this dashboard tracks
          portfolio health — delayed projects, overdue RFIs, late deliveries, and more — across
          everything your company runs.
        </p>
        {canCreate ? (
          <div className="mt-6 flex flex-col items-center gap-3">
            <Link to="/projects">
              <Button>
                Create your first project <ArrowRight size={16} />
              </Button>
            </Link>
            <p className="text-xs text-slate-400">
              You can also import projects{hasSuppliers ? "" : " and suppliers"} in bulk from a CSV or
              Excel file from their pages.
            </p>
          </div>
        ) : (
          <p className="mt-6 text-sm text-slate-500">
            Ask an administrator or project manager to add the first project.
          </p>
        )}
      </div>
    </Card>
  );
}
