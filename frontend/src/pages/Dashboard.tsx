import { useEffect, useState } from "react";
import { Building2, AlertTriangle, Clock, Truck, Users, Scale } from "lucide-react";
import { api, type Page } from "../lib/api";
import { Card, PageHeader, StatCard, Badge, Table, Spinner, ErrorBox, statusTone } from "../components/ui";

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

  const money = (v: string) =>
    `SAR ${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

  return (
    <div>
      <PageHeader title="Executive Dashboard" subtitle="Portfolio health across all projects" />

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
        </Card>

        <Card>
          <div className="border-b border-slate-100 px-5 py-3 text-sm font-semibold text-slate-800">
            Most Overdue RFIs
          </div>
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
        </Card>
      </div>
    </div>
  );
}
