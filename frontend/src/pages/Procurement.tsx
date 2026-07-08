import { useEffect, useState } from "react";
import { Sparkles, Gauge, Activity } from "lucide-react";
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
  Select,
  Spinner,
  Table,
  Tabs,
  statusTone,
} from "../components/ui";

interface PurchaseRequest {
  id: number;
  project_id: number;
  request_no: string;
  material_category: string | null;
  specification: string | null;
  required_delivery_date: string | null;
  status: string;
}
interface PurchaseOrder {
  id: number;
  po_number: string;
  project_id: number;
  supplier_id: number;
  promised_delivery: string | null;
  actual_delivery: string | null;
  status: string;
  is_late: boolean;
  delay_days: number;
  delay_root_cause: string | null;
}
interface Supplier {
  id: number;
  supplier_name: string;
  category: string;
  city: string;
  status: string;
}
interface PRReview {
  request_no: string;
  material_category: string | null;
  missing_information: string[];
  risk_level: string;
  recommendation: string;
  required_approvals: string[];
  supplier_history_note: string | null;
  memory_used: number[];
  provider: string;
  model: string;
}
interface SupplierRisk {
  supplier_name: string;
  risk_score: number;
  risk_level: string;
  on_time_rate: number;
  late_purchase_orders: number;
  ncr_count: number;
  total_delay_days: number;
  drivers: string[];
  recommendation: string;
  provider: string;
  model: string;
}
interface DelayCause {
  cause: string;
  count: number;
}
interface SupplierPerformance {
  supplier_name: string;
  total_purchase_orders: number;
  late_purchase_orders: number;
  on_time_rate: number;
  total_delay_days: number;
  average_delay_days_when_late: number;
  ncr_count: number;
  top_delay_causes: DelayCause[];
}

type Tab = "requests" | "orders" | "suppliers";

export default function Procurement() {
  const [tab, setTab] = useState<Tab>("requests");
  return (
    <div>
      <PageHeader title="Procurement" subtitle="Purchase requests, orders, and supplier intelligence" />
      <Tabs
        tabs={[
          { key: "requests", label: "Purchase Requests" },
          { key: "orders", label: "Purchase Orders" },
          { key: "suppliers", label: "Suppliers" },
        ]}
        active={tab}
        onChange={setTab}
      />
      {tab === "requests" && <Requests />}
      {tab === "orders" && <Orders />}
      {tab === "suppliers" && <Suppliers />}
    </div>
  );
}

function Requests() {
  const { user } = useAuth();
  const canAnalyze = !!user && ["admin", "procurement_officer", "project_manager"].includes(user.role);
  const [data, setData] = useState<Page<PurchaseRequest>>();
  const [error, setError] = useState<string>();
  const [page, setPage] = useState(1);
  const [incomplete, setIncomplete] = useState(false);
  const [review, setReview] = useState<PRReview>();
  const [busy, setBusy] = useState<number>();

  useEffect(() => {
    const params = new URLSearchParams({ page: String(page), size: "20" });
    if (incomplete) params.set("incomplete", "true");
    setError(undefined);
    api.get<Page<PurchaseRequest>>(`/procurement/purchase-requests?${params}`).then(setData).catch((e) => setError(e.message));
  }, [page, incomplete]);

  async function analyze(pr: PurchaseRequest) {
    setBusy(pr.id);
    try {
      setReview(await api.post<PRReview>("/procurement/purchase-requests/analyze", { pr_id: pr.id }));
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(undefined);
    }
  }

  if (!data && error) return <div className="text-sm text-red-600">{error}</div>;
  if (!data) return <Spinner />;

  return (
    <>
      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
      <FilterBar>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input
            type="checkbox"
            checked={incomplete}
            onChange={(e) => {
              setIncomplete(e.target.checked);
              setPage(1);
            }}
            className="h-4 w-4 rounded border-slate-300"
          />
          Incomplete requests only
        </label>
      </FilterBar>
      <Card>
        <Table head={["Request", "Material", "Required By", "Status", "AI"]}>
          {data.items.map((pr) => (
            <tr key={pr.id} className="hover:bg-slate-50">
              <td className="px-4 py-3 font-mono text-xs text-slate-500">{pr.request_no}</td>
              <td className="px-4 py-3 text-slate-700">{pr.material_category ?? <span className="text-red-500">Missing</span>}</td>
              <td className="px-4 py-3 text-slate-600">{date(pr.required_delivery_date)}</td>
              <td className="px-4 py-3">
                <Badge tone={statusTone(pr.status)}>{pr.status}</Badge>
              </td>
              <td className="px-4 py-3">
                {canAnalyze && (
                  <Button variant="secondary" disabled={busy === pr.id} onClick={() => analyze(pr)}>
                    <Sparkles size={14} /> {busy === pr.id ? "Analyzing…" : "Analyze"}
                  </Button>
                )}
              </td>
            </tr>
          ))}
        </Table>
        {data.items.length === 0 && <EmptyState message="No purchase requests match this filter." />}
        <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
      </Card>

      {review && (
        <Modal title={`PR Review · ${review.request_no}`} onClose={() => setReview(undefined)}>
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <Badge tone={statusTone(review.risk_level)}>{review.risk_level} risk</Badge>
              <ProviderTag provider={review.provider} model={review.model} />
            </div>
            <LabelValue label="Material Category" value={review.material_category ?? "Not specified"} />
            <LabelValue label="Recommendation" value={review.recommendation} />
            {review.missing_information.length > 0 && (
              <LabelValue
                label="Missing Information"
                value={
                  <ul className="list-inside list-disc text-red-600">
                    {review.missing_information.map((m, i) => (
                      <li key={i}>{m}</li>
                    ))}
                  </ul>
                }
              />
            )}
            {review.required_approvals.length > 0 && (
              <LabelValue
                label="Required Approvals"
                value={
                  <div className="flex flex-wrap gap-1.5">
                    {review.required_approvals.map((a, i) => (
                      <Badge key={i} tone="blue">
                        {a}
                      </Badge>
                    ))}
                  </div>
                }
              />
            )}
            {review.supplier_history_note && (
              <LabelValue label="Supplier History" value={review.supplier_history_note} />
            )}
            {review.memory_used.length > 0 && (
              <div className="text-xs text-slate-400">Grounded on {review.memory_used.length} memory record(s)</div>
            )}
          </div>
        </Modal>
      )}
    </>
  );
}

function Orders() {
  const [data, setData] = useState<Page<PurchaseOrder>>();
  const [error, setError] = useState<string>();
  const [page, setPage] = useState(1);
  const [lateOnly, setLateOnly] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams({ page: String(page), size: "20" });
    if (lateOnly) params.set("is_late", "true");
    setError(undefined);
    api.get<Page<PurchaseOrder>>(`/procurement/purchase-orders?${params}`).then(setData).catch((e) => setError(e.message));
  }, [page, lateOnly]);

  if (error) return <div className="text-sm text-red-600">{error}</div>;
  if (!data) return <Spinner />;

  return (
    <>
      <FilterBar>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input
            type="checkbox"
            checked={lateOnly}
            onChange={(e) => {
              setLateOnly(e.target.checked);
              setPage(1);
            }}
            className="h-4 w-4 rounded border-slate-300"
          />
          Late deliveries only
        </label>
      </FilterBar>
      <Card>
        <Table head={["PO", "Promised", "Delivered", "Status", "Delay", "Root Cause"]}>
          {data.items.map((po) => (
            <tr key={po.id} className="hover:bg-slate-50">
              <td className="px-4 py-3 font-mono text-xs text-slate-500">{po.po_number}</td>
              <td className="px-4 py-3 text-slate-600">{date(po.promised_delivery)}</td>
              <td className="px-4 py-3 text-slate-600">{date(po.actual_delivery)}</td>
              <td className="px-4 py-3">
                <Badge tone={statusTone(po.status)}>{po.status}</Badge>
              </td>
              <td className="px-4 py-3">
                {po.is_late ? (
                  <span className="font-medium text-red-600">{po.delay_days}d late</span>
                ) : (
                  <span className="text-emerald-600">On time</span>
                )}
              </td>
              <td className="px-4 py-3 text-slate-600">{po.delay_root_cause ?? "—"}</td>
            </tr>
          ))}
        </Table>
        {data.items.length === 0 && <EmptyState message="No purchase orders match this filter." />}
        <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
      </Card>
    </>
  );
}

function Suppliers() {
  const { user } = useAuth();
  const canAssess = !!user && ["admin", "executive", "procurement_officer"].includes(user.role);
  const [data, setData] = useState<Page<Supplier>>();
  const [error, setError] = useState<string>();
  const [page, setPage] = useState(1);
  const [category, setCategory] = useState("");
  const [risk, setRisk] = useState<SupplierRisk>();
  const [perf, setPerf] = useState<SupplierPerformance>();
  const [busy, setBusy] = useState<number>();

  useEffect(() => {
    const params = new URLSearchParams({ page: String(page), size: "20" });
    if (category) params.set("category", category);
    setError(undefined);
    api.get<Page<Supplier>>(`/suppliers?${params}`).then(setData).catch((e) => setError(e.message));
  }, [page, category]);

  async function assess(s: Supplier) {
    setBusy(s.id);
    try {
      setRisk(await api.post<SupplierRisk>(`/suppliers/${s.id}/risk-assessment`));
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(undefined);
    }
  }
  async function performance(s: Supplier) {
    setBusy(s.id);
    try {
      setPerf(await api.get<SupplierPerformance>(`/suppliers/${s.id}/performance`));
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(undefined);
    }
  }

  if (!data && error) return <div className="text-sm text-red-600">{error}</div>;
  if (!data) return <Spinner />;

  return (
    <>
      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
      <FilterBar>
        <Field label="Category">
          <Select
            value={category}
            onChange={(e) => {
              setCategory(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All categories</option>
            {["Civil", "Concrete", "Steel", "MEP", "Electrical", "Plumbing", "HVAC", "Facade", "Finishing", "Safety"].map(
              (c) => (
                <option key={c}>{c}</option>
              )
            )}
          </Select>
        </Field>
      </FilterBar>
      <Card>
        <Table head={["Supplier", "Category", "City", "Status", "Actions"]}>
          {data.items.map((s) => (
            <tr key={s.id} className="hover:bg-slate-50">
              <td className="px-4 py-3 font-medium text-slate-800">{s.supplier_name}</td>
              <td className="px-4 py-3 text-slate-600">{s.category}</td>
              <td className="px-4 py-3 text-slate-600">{s.city}</td>
              <td className="px-4 py-3">
                <Badge tone={statusTone(s.status)}>{s.status}</Badge>
              </td>
              <td className="px-4 py-3">
                <div className="flex gap-2">
                  <Button variant="secondary" disabled={busy === s.id} onClick={() => performance(s)}>
                    <Activity size={14} /> Performance
                  </Button>
                  {canAssess && (
                    <Button variant="secondary" disabled={busy === s.id} onClick={() => assess(s)}>
                      <Gauge size={14} /> Risk
                    </Button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </Table>
        {data.items.length === 0 && <EmptyState message="No suppliers match this filter." />}
        <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
      </Card>

      {perf && (
        <Modal title={`Performance · ${perf.supplier_name}`} onClose={() => setPerf(undefined)}>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            <LabelValue label="Total POs" value={perf.total_purchase_orders} />
            <LabelValue label="Late POs" value={perf.late_purchase_orders} />
            <LabelValue label="On-time Rate" value={`${perf.on_time_rate.toFixed(1)}%`} />
            <LabelValue label="Total Delay" value={`${perf.total_delay_days}d`} />
            <LabelValue label="Avg Delay (late)" value={`${perf.average_delay_days_when_late.toFixed(1)}d`} />
            <LabelValue label="NCRs" value={perf.ncr_count} />
          </div>
          {perf.top_delay_causes.length > 0 && (
            <div className="mt-5">
              <div className="mb-2 text-xs font-medium text-slate-500">Top Delay Causes</div>
              <div className="space-y-1.5">
                {perf.top_delay_causes.map((c, i) => (
                  <div key={i} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-1.5 text-sm">
                    <span className="text-slate-700">{c.cause}</span>
                    <Badge tone="slate">{c.count}</Badge>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Modal>
      )}

      {risk && (
        <Modal title={`Risk Assessment · ${risk.supplier_name}`} onClose={() => setRisk(undefined)}>
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <Badge tone={statusTone(risk.risk_level)}>{risk.risk_level}</Badge>
              <span className="text-sm text-slate-500">Score {risk.risk_score.toFixed(1)}</span>
              <ProviderTag provider={risk.provider} model={risk.model} />
            </div>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <LabelValue label="On-time Rate" value={`${risk.on_time_rate.toFixed(1)}%`} />
              <LabelValue label="Late POs" value={risk.late_purchase_orders} />
              <LabelValue label="NCRs" value={risk.ncr_count} />
              <LabelValue label="Total Delay" value={`${risk.total_delay_days}d`} />
            </div>
            {risk.drivers.length > 0 && (
              <LabelValue
                label="Risk Drivers"
                value={
                  <ul className="list-inside list-disc text-slate-700">
                    {risk.drivers.map((d, i) => (
                      <li key={i}>{d}</li>
                    ))}
                  </ul>
                }
              />
            )}
            <LabelValue label="Recommendation" value={risk.recommendation} />
          </div>
        </Modal>
      )}
    </>
  );
}
