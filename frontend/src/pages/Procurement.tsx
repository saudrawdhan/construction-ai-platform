import { useCallback, useEffect, useState } from "react";
import { Sparkles, Gauge, Activity, Plus, Upload } from "lucide-react";
import { api, ApiError, type Page } from "../lib/api";
import { useAuth } from "../lib/auth";
import { date } from "../lib/format";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorBox,
  Field,
  FilterBar,
  Input,
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
import ImportModal from "../components/ImportModal";
import CreateModal from "../components/CreateModal";
import RowActions from "../components/RowActions";
import RequestApprovalButton from "../components/RequestApprovalButton";

const MATERIAL_CATEGORIES = [
  "Civil", "Concrete", "Steel", "MEP", "Electrical", "Plumbing", "HVAC", "Facade", "Finishing", "Safety",
];

const PURCHASE_REQUEST_FIELDS = [
  { name: "project_id", label: "Project", type: "project" as const, required: true },
  { name: "request_no", label: "Request no.", required: true },
  {
    name: "material_category",
    label: "Material category",
    type: "select" as const,
    options: MATERIAL_CATEGORIES,
    initial: "Steel",
  },
  {
    name: "status",
    label: "Status",
    type: "select" as const,
    options: ["Under Review", "Approved", "Rejected", "Needs Rework"],
    initial: "Under Review",
  },
  { name: "specification", label: "Specification", type: "textarea" as const },
  { name: "required_delivery_date", label: "Required delivery", type: "date" as const },
];

const SUPPLIER_FIELDS = [
  { name: "supplier_name", label: "Supplier name", required: true, full: true },
  { name: "category", label: "Category", type: "select" as const, options: MATERIAL_CATEGORIES, initial: "Civil" },
  { name: "city", label: "City", required: true },
  { name: "status", label: "Status", type: "select" as const, options: ["Active", "Inactive"], initial: "Active" },
];

// Edit-only fields for a purchase order (its project/supplier/request links are fixed; lateness is
// recomputed server-side from the delivery dates).
const PURCHASE_ORDER_EDIT_FIELDS = [
  { name: "po_number", label: "PO number", required: true },
  { name: "status", label: "Status", type: "select" as const, options: ["Issued", "Delivered", "Cancelled"] },
  { name: "issue_date", label: "Issue date", type: "date" as const },
  { name: "promised_delivery", label: "Promised delivery", type: "date" as const },
  { name: "actual_delivery", label: "Actual delivery", type: "date" as const },
  { name: "delay_root_cause", label: "Delay root cause", full: true },
];

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
  const [reviewProjectId, setReviewProjectId] = useState<number>();
  const [busy, setBusy] = useState<number>();
  const [showCreate, setShowCreate] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    const params = new URLSearchParams({ page: String(page), size: "20" });
    if (incomplete) params.set("incomplete", "true");
    setError(undefined);
    api.get<Page<PurchaseRequest>>(`/procurement/purchase-requests?${params}`).then(setData).catch((e) => setError(e.message));
  }, [page, incomplete, refresh]);

  async function analyze(pr: PurchaseRequest) {
    setBusy(pr.id);
    try {
      setReview(await api.post<PRReview>("/procurement/purchase-requests/analyze", { pr_id: pr.id }));
      setReviewProjectId(pr.project_id);
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
        <label className="flex h-10 items-center gap-2 text-sm text-slate-600">
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
        {canAnalyze && (
          <>
            <Button variant="secondary" onClick={() => setShowImport(true)}>
              <Upload size={16} /> Import
            </Button>
            <Button onClick={() => setShowCreate(true)}>
              <Plus size={16} /> New Request
            </Button>
          </>
        )}
      </FilterBar>
      <Card>
        <Table head={["Request", "Material", "Required By", "Status", "AI", ""]}>
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
              <td className="px-4 py-3 text-right">
                <RowActions
                  record={pr}
                  entityLabel="Purchase Request"
                  endpoint="/procurement/purchase-requests"
                  fields={PURCHASE_REQUEST_FIELDS}
                  canManage={canAnalyze}
                  onChanged={() => setRefresh((n) => n + 1)}
                />
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
            <div className="border-t border-slate-100 pt-3">
              <RequestApprovalButton
                actionType="approve_purchase_request"
                projectId={reviewProjectId}
                riskLevel={review.risk_level?.toLowerCase() === "low" ? "medium" : "high"}
                payload={{
                  request_no: review.request_no,
                  recommendation: review.recommendation,
                  risk_level: review.risk_level,
                }}
              />
            </div>
          </div>
        </Modal>
      )}

      {showCreate && (
        <CreateModal
          title="New Purchase Request"
          endpoint="/procurement/purchase-requests"
          fields={PURCHASE_REQUEST_FIELDS}
          submitLabel="Create Request"
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
          title="Import Purchase Requests"
          importPath="/procurement/purchase-requests/import"
          templatePath="/procurement/purchase-requests/import/template"
          templateFilename="purchase_requests_template.csv"
          onClose={() => setShowImport(false)}
          onImported={() => {
            setPage(1);
            setRefresh((r) => r + 1);
          }}
        />
      )}
    </>
  );
}

function Orders() {
  const { user } = useAuth();
  const canManage = !!user && ["admin", "procurement_officer", "project_manager"].includes(user.role);
  const [data, setData] = useState<Page<PurchaseOrder>>();
  const [error, setError] = useState<string>();
  const [page, setPage] = useState(1);
  const [lateOnly, setLateOnly] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    const params = new URLSearchParams({ page: String(page), size: "20" });
    if (lateOnly) params.set("is_late", "true");
    setError(undefined);
    api.get<Page<PurchaseOrder>>(`/procurement/purchase-orders?${params}`).then(setData).catch((e) => setError(e.message));
  }, [page, lateOnly, refresh]);

  if (!data && error) return <div className="text-sm text-red-600">{error}</div>;
  if (!data) return <Spinner />;

  return (
    <>
      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
      <FilterBar>
        <label className="flex h-10 items-center gap-2 text-sm text-slate-600">
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
        {canManage && (
          <Button onClick={() => setShowForm(true)}>
            <Plus size={16} /> New Order
          </Button>
        )}
      </FilterBar>
      <Card>
        <Table head={["PO", "Promised", "Delivered", "Status", "Delay", "Root Cause", ""]}>
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
              <td className="px-4 py-3 text-right">
                <RowActions
                  record={po}
                  entityLabel="Purchase Order"
                  endpoint="/procurement/purchase-orders"
                  fields={PURCHASE_ORDER_EDIT_FIELDS}
                  canManage={canManage}
                  onChanged={() => setRefresh((n) => n + 1)}
                />
              </td>
            </tr>
          ))}
        </Table>
        {data.items.length === 0 && (
          <EmptyState
            message={
              lateOnly
                ? "No late purchase orders."
                : canManage
                  ? "No purchase orders yet. Use “New Order” to add one."
                  : "No purchase orders yet."
            }
          />
        )}
        <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
      </Card>

      {showForm && (
        <NewOrderModal
          onClose={() => setShowForm(false)}
          onCreated={() => {
            setShowForm(false);
            setPage(1);
            setRefresh((r) => r + 1);
          }}
        />
      )}
    </>
  );
}

interface ProjectOption {
  id: number;
  project_name: string;
}
interface PrOption {
  id: number;
  request_no: string;
}

/**
 * Purchase orders sit at the intersection of a project, a purchase request within that project, and
 * a supplier — so the form loads projects and suppliers up front and lazily fetches the purchase
 * requests for the chosen project. is_late and delay_days are computed server-side from the promised
 * vs. actual delivery dates, so they are not entered here.
 */
function NewOrderModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [projects, setProjects] = useState<ProjectOption[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [requests, setRequests] = useState<PrOption[]>([]);
  const [form, setForm] = useState({
    project_id: "",
    pr_id: "",
    supplier_id: "",
    po_number: "",
    issue_date: "",
    promised_delivery: "",
    actual_delivery: "",
    status: "Issued",
    delay_root_cause: "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();

  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  useEffect(() => {
    api.get<Page<ProjectOption>>("/projects?size=100").then((p) => setProjects(p.items)).catch(() => {});
    api.get<Page<Supplier>>("/suppliers?size=100").then((s) => setSuppliers(s.items)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!form.project_id) {
      setRequests([]);
      return;
    }
    api
      .get<Page<PrOption>>(`/procurement/purchase-requests?project_id=${form.project_id}&size=100`)
      .then((r) => setRequests(r.items))
      .catch(() => setRequests([]));
    setForm((f) => ({ ...f, pr_id: "" }));
  }, [form.project_id]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(undefined);
    try {
      const body: Record<string, unknown> = {
        project_id: Number(form.project_id),
        pr_id: Number(form.pr_id),
        supplier_id: Number(form.supplier_id),
        po_number: form.po_number,
        status: form.status,
      };
      for (const k of ["issue_date", "promised_delivery", "actual_delivery", "delay_root_cause"] as const) {
        if (form[k]) body[k] = form[k];
      }
      await api.post("/procurement/purchase-orders", body);
      onCreated();
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal title="New Purchase Order" onClose={onClose}>
      <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
        <Field label="Project">
          <Select required value={form.project_id} onChange={(e) => set("project_id", e.target.value)}>
            <option value="">Select a project…</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.project_name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Purchase request">
          <Select
            required
            value={form.pr_id}
            onChange={(e) => set("pr_id", e.target.value)}
            disabled={!form.project_id}
          >
            <option value="">{form.project_id ? "Select a request…" : "Choose a project first"}</option>
            {requests.map((r) => (
              <option key={r.id} value={r.id}>
                {r.request_no}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Supplier">
          <Select required value={form.supplier_id} onChange={(e) => set("supplier_id", e.target.value)}>
            <option value="">Select a supplier…</option>
            {suppliers.map((s) => (
              <option key={s.id} value={s.id}>
                {s.supplier_name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="PO number">
          <Input required value={form.po_number} onChange={(e) => set("po_number", e.target.value)} />
        </Field>
        <Field label="Issue date">
          <Input type="date" value={form.issue_date} onChange={(e) => set("issue_date", e.target.value)} />
        </Field>
        <Field label="Status">
          <Select value={form.status} onChange={(e) => set("status", e.target.value)}>
            {["Issued", "Delivered", "Cancelled"].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </Select>
        </Field>
        <Field label="Promised delivery">
          <Input
            type="date"
            value={form.promised_delivery}
            onChange={(e) => set("promised_delivery", e.target.value)}
          />
        </Field>
        <Field label="Actual delivery">
          <Input
            type="date"
            value={form.actual_delivery}
            onChange={(e) => set("actual_delivery", e.target.value)}
          />
        </Field>
        <div className="sm:col-span-2">
          <Field label="Delay root cause (optional)">
            <Input value={form.delay_root_cause} onChange={(e) => set("delay_root_cause", e.target.value)} />
          </Field>
        </div>
        <div className="sm:col-span-2">
          {error && <ErrorBox message={error} />}
          <div className="mt-2 flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? "Creating…" : "Create Order"}
            </Button>
          </div>
        </div>
      </form>
    </Modal>
  );
}

function Suppliers() {
  const { user } = useAuth();
  const canAssess = !!user && ["admin", "executive", "procurement_officer"].includes(user.role);
  const canManage = !!user && ["admin", "procurement_officer"].includes(user.role);
  const [data, setData] = useState<Page<Supplier>>();
  const [error, setError] = useState<string>();
  const [page, setPage] = useState(1);
  const [category, setCategory] = useState("");
  const [risk, setRisk] = useState<SupplierRisk>();
  const [perf, setPerf] = useState<SupplierPerformance>();
  const [busy, setBusy] = useState<number>();
  const [showForm, setShowForm] = useState(false);
  const [showImport, setShowImport] = useState(false);

  const load = useCallback(() => {
    const params = new URLSearchParams({ page: String(page), size: "20" });
    if (category) params.set("category", category);
    setError(undefined);
    api.get<Page<Supplier>>(`/suppliers?${params}`).then(setData).catch((e) => setError(e.message));
  }, [page, category]);

  useEffect(() => {
    load();
  }, [load]);

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
        {canManage && (
          <>
            <Button variant="secondary" onClick={() => setShowImport(true)}>
              <Upload size={16} /> Import
            </Button>
            <Button onClick={() => setShowForm(true)}>
              <Plus size={16} /> New Supplier
            </Button>
          </>
        )}
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
                <div className="flex items-center gap-2">
                  <Button variant="secondary" disabled={busy === s.id} onClick={() => performance(s)}>
                    <Activity size={14} /> Performance
                  </Button>
                  {canAssess && (
                    <Button variant="secondary" disabled={busy === s.id} onClick={() => assess(s)}>
                      <Gauge size={14} /> Risk
                    </Button>
                  )}
                  <RowActions
                    record={s}
                    entityLabel="Supplier"
                    endpoint="/suppliers"
                    fields={SUPPLIER_FIELDS}
                    canManage={canManage}
                    onChanged={load}
                  />
                </div>
              </td>
            </tr>
          ))}
        </Table>
        {data.items.length === 0 && (
          <EmptyState
            message={
              category
                ? "No suppliers match this filter."
                : canManage
                  ? "No suppliers yet. Use “New Supplier” to add one."
                  : "No suppliers yet."
            }
          />
        )}
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
            <div className="border-t border-slate-100 pt-3">
              <RequestApprovalButton
                actionType="supplier_risk_mitigation"
                riskLevel={risk.risk_level?.toLowerCase() === "high" ? "high" : "medium"}
                payload={{
                  supplier_name: risk.supplier_name,
                  risk_level: risk.risk_level,
                  recommendation: risk.recommendation,
                }}
              />
            </div>
          </div>
        </Modal>
      )}

      {showForm && (
        <NewSupplierModal
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
          title="Import Suppliers"
          importPath="/suppliers/import"
          templatePath="/suppliers/import/template"
          templateFilename="suppliers_template.csv"
          onClose={() => setShowImport(false)}
          onImported={() => {
            setPage(1);
            load();
          }}
        />
      )}
    </>
  );
}

const SUPPLIER_CATEGORIES = [
  "Civil", "Concrete", "Steel", "MEP", "Electrical", "Plumbing", "HVAC", "Facade", "Finishing", "Safety",
];

function NewSupplierModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [form, setForm] = useState({
    supplier_name: "",
    category: "Civil",
    city: "",
    status: "Active",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();

  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(undefined);
    try {
      await api.post("/suppliers", form);
      onCreated();
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal title="New Supplier" onClose={onClose}>
      <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <Field label="Supplier name">
            <Input required value={form.supplier_name} onChange={(e) => set("supplier_name", e.target.value)} />
          </Field>
        </div>
        <Field label="Category">
          <Select value={form.category} onChange={(e) => set("category", e.target.value)}>
            {SUPPLIER_CATEGORIES.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </Select>
        </Field>
        <Field label="City">
          <Input required value={form.city} onChange={(e) => set("city", e.target.value)} />
        </Field>
        <Field label="Status">
          <Select value={form.status} onChange={(e) => set("status", e.target.value)}>
            {["Active", "Inactive"].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </Select>
        </Field>
        <div className="sm:col-span-2">
          {error && <ErrorBox message={error} />}
          <div className="mt-2 flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? "Creating…" : "Create Supplier"}
            </Button>
          </div>
        </div>
      </form>
    </Modal>
  );
}
