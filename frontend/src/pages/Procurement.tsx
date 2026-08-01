import { useCallback, useEffect, useState } from "react";
import { Sparkles, Gauge, Activity, Plus, Upload } from "lucide-react";
import { api, ApiError, type Page } from "../lib/api";
import { useAuth } from "../lib/auth";
import { date, enumLabel } from "../lib/format";
import { useT, type Translate } from "../lib/i18n";
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
import ProjectPicker from "../components/ProjectPicker";

const MATERIAL_CATEGORIES = [
  "Civil", "Concrete", "Steel", "MEP", "Electrical", "Plumbing", "HVAC", "Facade", "Finishing", "Safety",
];

const purchaseRequestFields = (t: Translate) => [
  { name: "project_id", label: t("common.project"), type: "project" as const, required: true },
  { name: "request_no", label: t("field.requestNo"), required: true },
  {
    name: "material_category",
    label: t("field.materialCategory"),
    type: "select" as const,
    options: MATERIAL_CATEGORIES,
    initial: "Steel",
  },
  {
    name: "status",
    label: t("field.status"),
    type: "select" as const,
    options: ["Under Review", "Approved", "Rejected", "Needs Rework"],
    initial: "Under Review",
  },
  { name: "specification", label: t("field.specification"), type: "textarea" as const },
  { name: "required_delivery_date", label: t("field.requiredDelivery"), type: "date" as const },
];

const supplierFields = (t: Translate) => [
  { name: "supplier_name", label: t("field.supplierName"), required: true, full: true },
  { name: "category", label: t("field.category"), type: "select" as const, options: MATERIAL_CATEGORIES, initial: "Civil" },
  { name: "city", label: t("field.city"), required: true },
  { name: "status", label: t("field.status"), type: "select" as const, options: ["Active", "Inactive"], initial: "Active" },
];

// Edit-only fields for a purchase order (its project/supplier/request links are fixed; lateness is
// recomputed server-side from the delivery dates).
const purchaseOrderEditFields = (t: Translate) => [
  { name: "po_number", label: t("field.poNumber"), required: true },
  { name: "status", label: t("field.status"), type: "select" as const, options: ["Issued", "Delivered", "Cancelled"] },
  { name: "issue_date", label: t("field.issueDate"), type: "date" as const },
  { name: "promised_delivery", label: t("field.promisedDelivery"), type: "date" as const },
  { name: "actual_delivery", label: t("field.actualDelivery"), type: "date" as const },
  { name: "delay_root_cause", label: t("field.delayRootCause"), full: true },
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
  pr_id: number;
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
  const t = useT();
  const [tab, setTab] = useState<Tab>("requests");
  return (
    <div>
      <PageHeader title={t("nav.procurement")} subtitle={t("proc.subtitle")} />
      <Tabs
        tabs={[
          { key: "requests", label: t("proc.tabRequests") },
          { key: "orders", label: t("proc.tabOrders") },
          { key: "suppliers", label: t("proc.tabSuppliers") },
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
  const t = useT();
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
          {t("proc.incompleteOnly")}
        </label>
        {canAnalyze && (
          <>
            <Button variant="secondary" onClick={() => setShowImport(true)}>
              <Upload size={16} /> {t("common.import")}
            </Button>
            <Button onClick={() => setShowCreate(true)}>
              <Plus size={16} /> {t("proc.newRequest")}
            </Button>
          </>
        )}
      </FilterBar>
      <Card>
        <Table head={[t("col.request"), t("col.material"), t("col.requiredBy"), t("col.status"), t("col.ai"), ""]}>
          {data.items.map((pr) => (
            <tr key={pr.id} className="hover:bg-slate-50">
              <td className="px-4 py-3 font-mono text-xs text-slate-500">{pr.request_no}</td>
              <td className="px-4 py-3 text-slate-700">{pr.material_category ? enumLabel(pr.material_category, t) : <span className="text-red-500">{t("proc.missing")}</span>}</td>
              <td className="px-4 py-3 text-slate-600">{date(pr.required_delivery_date)}</td>
              <td className="px-4 py-3">
                <Badge tone={statusTone(pr.status)}>{enumLabel(pr.status, t)}</Badge>
              </td>
              <td className="px-4 py-3">
                {canAnalyze && (
                  <Button variant="secondary" disabled={busy === pr.id} onClick={() => analyze(pr)}>
                    <Sparkles size={14} /> {busy === pr.id ? t("proc.analyzing") : t("common.analyze")}
                  </Button>
                )}
              </td>
              <td className="px-4 py-3 text-end">
                <RowActions
                  record={pr}
                  entityLabel={t("entity.purchaseRequest")}
                  endpoint="/procurement/purchase-requests"
                  fields={purchaseRequestFields(t)}
                  canManage={canAnalyze}
                  onChanged={() => setRefresh((n) => n + 1)}
                />
              </td>
            </tr>
          ))}
        </Table>
        {data.items.length === 0 && <EmptyState message={t("proc.noRequests")} />}
        <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
      </Card>

      {review && (
        <Modal title={t("proc.prReviewTitle", { no: review.request_no })} onClose={() => setReview(undefined)}>
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <Badge tone={statusTone(review.risk_level)}>{t("proc.riskSuffix", { level: enumLabel(review.risk_level, t) })}</Badge>
              <ProviderTag provider={review.provider} model={review.model} />
            </div>
            <LabelValue label={t("proc.materialCategory")} value={review.material_category ? enumLabel(review.material_category, t) : t("proc.notSpecified")} />
            <LabelValue label={t("proc.recommendation")} value={review.recommendation} />
            {review.missing_information.length > 0 && (
              <LabelValue
                label={t("proc.missingInfo")}
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
                label={t("proc.requiredApprovals")}
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
              <LabelValue label={t("proc.supplierHistory")} value={review.supplier_history_note} />
            )}
            {review.memory_used.length > 0 && (
              <div className="text-xs text-slate-400">{t("proc.groundedOn", { n: review.memory_used.length })}</div>
            )}
            <div className="border-t border-slate-100 pt-3">
              <RequestApprovalButton
                actionType="approve_purchase_request"
                projectId={reviewProjectId}
                subjectType="purchase_request"
                subjectId={review.pr_id}
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
          title={t("proc.newRequest")}
          endpoint="/procurement/purchase-requests"
          fields={purchaseRequestFields(t)}
          submitLabel={t("proc.createRequest")}
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
          title={t("proc.importRequests")}
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
  const t = useT();
  const canManage = !!user && ["admin", "procurement_officer", "project_manager"].includes(user.role);
  const [data, setData] = useState<Page<PurchaseOrder>>();
  const [error, setError] = useState<string>();
  const [page, setPage] = useState(1);
  const [lateOnly, setLateOnly] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [showImport, setShowImport] = useState(false);
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
          {t("proc.lateOnly")}
        </label>
        {canManage && (
          <>
            <Button variant="secondary" onClick={() => setShowImport(true)}>
              <Upload size={16} /> {t("common.import")}
            </Button>
            <Button onClick={() => setShowForm(true)}>
              <Plus size={16} /> {t("proc.newOrder")}
            </Button>
          </>
        )}
      </FilterBar>
      <Card>
        <Table head={[t("col.po"), t("col.promised"), t("col.delivered"), t("col.status"), t("col.delay"), t("col.rootCause"), ""]}>
          {data.items.map((po) => (
            <tr key={po.id} className="hover:bg-slate-50">
              <td className="px-4 py-3 font-mono text-xs text-slate-500">{po.po_number}</td>
              <td className="px-4 py-3 text-slate-600">{date(po.promised_delivery)}</td>
              <td className="px-4 py-3 text-slate-600">{date(po.actual_delivery)}</td>
              <td className="px-4 py-3">
                <Badge tone={statusTone(po.status)}>{enumLabel(po.status, t)}</Badge>
              </td>
              <td className="px-4 py-3">
                {po.is_late ? (
                  <span className="font-medium text-red-600">{t("pd.daysLate", { n: po.delay_days })}</span>
                ) : (
                  <span className="text-emerald-600">{t("pd.onTime")}</span>
                )}
              </td>
              <td className="px-4 py-3 text-slate-600">{po.delay_root_cause ?? "—"}</td>
              <td className="px-4 py-3 text-end">
                <RowActions
                  record={po}
                  entityLabel={t("col.po")}
                  endpoint="/procurement/purchase-orders"
                  fields={purchaseOrderEditFields(t)}
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
                ? t("proc.noLateOrders")
                : canManage
                  ? t("proc.noOrdersCreate")
                  : t("proc.noOrders")
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

      {showImport && (
        <ImportModal
          title={t("proc.importOrders")}
          importPath="/procurement/purchase-orders/import"
          templatePath="/procurement/purchase-orders/import/template"
          templateFilename="purchase_orders_template.csv"
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
  const t = useT();
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
    <Modal title={t("proc.newOrderTitle")} onClose={onClose}>
      <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
        <Field label={t("common.project")}>
          <ProjectPicker
            projects={projects}
            value={form.project_id}
            onChange={(v) => set("project_id", v)}
            placeholder={t("form.selectProject")}
            required
          />
        </Field>
        <Field label={t("field.purchaseRequest")}>
          <Select
            required
            value={form.pr_id}
            onChange={(e) => set("pr_id", e.target.value)}
            disabled={!form.project_id}
          >
            <option value="">{form.project_id ? t("proc.selectRequest") : t("proc.chooseProjectFirst")}</option>
            {requests.map((r) => (
              <option key={r.id} value={r.id}>
                {r.request_no}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("field.supplier")}>
          <Select required value={form.supplier_id} onChange={(e) => set("supplier_id", e.target.value)}>
            <option value="">{t("proc.selectSupplier")}</option>
            {suppliers.map((s) => (
              <option key={s.id} value={s.id}>
                {s.supplier_name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("field.poNumber")}>
          <Input required value={form.po_number} onChange={(e) => set("po_number", e.target.value)} />
        </Field>
        <Field label={t("field.issueDate")}>
          <Input type="date" value={form.issue_date} onChange={(e) => set("issue_date", e.target.value)} />
        </Field>
        <Field label={t("field.status")}>
          <Select value={form.status} onChange={(e) => set("status", e.target.value)}>
            {["Issued", "Delivered", "Cancelled"].map((s) => (
              <option key={s} value={s}>{enumLabel(s, t)}</option>
            ))}
          </Select>
        </Field>
        <Field label={t("field.promisedDelivery")}>
          <Input
            type="date"
            value={form.promised_delivery}
            onChange={(e) => set("promised_delivery", e.target.value)}
          />
        </Field>
        <Field label={t("field.actualDelivery")}>
          <Input
            type="date"
            value={form.actual_delivery}
            onChange={(e) => set("actual_delivery", e.target.value)}
          />
        </Field>
        <div className="sm:col-span-2">
          <Field label={t("field.delayRootCauseOptional")}>
            <Input value={form.delay_root_cause} onChange={(e) => set("delay_root_cause", e.target.value)} />
          </Field>
        </div>
        <div className="sm:col-span-2">
          {error && <ErrorBox message={error} />}
          <div className="mt-2 flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={onClose}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? t("project.creating") : t("proc.createOrder")}
            </Button>
          </div>
        </div>
      </form>
    </Modal>
  );
}

function Suppliers() {
  const { user } = useAuth();
  const t = useT();
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
        <Field label={t("field.category")}>
          <Select
            value={category}
            onChange={(e) => {
              setCategory(e.target.value);
              setPage(1);
            }}
          >
            <option value="">{t("mem.allCategories")}</option>
            {["Civil", "Concrete", "Steel", "MEP", "Electrical", "Plumbing", "HVAC", "Facade", "Finishing", "Safety"].map(
              (c) => (
                <option key={c} value={c}>{enumLabel(c, t)}</option>
              )
            )}
          </Select>
        </Field>
        {canManage && (
          <>
            <Button variant="secondary" onClick={() => setShowImport(true)}>
              <Upload size={16} /> {t("common.import")}
            </Button>
            <Button onClick={() => setShowForm(true)}>
              <Plus size={16} /> {t("proc.newSupplier")}
            </Button>
          </>
        )}
      </FilterBar>
      <Card>
        <Table head={[t("col.supplier"), t("col.category"), t("col.city"), t("col.status"), t("col.actions")]}>
          {data.items.map((s) => (
            <tr key={s.id} className="hover:bg-slate-50">
              <td className="px-4 py-3 font-medium text-slate-800">{s.supplier_name}</td>
              <td className="px-4 py-3 text-slate-600">{enumLabel(s.category, t)}</td>
              <td className="px-4 py-3 text-slate-600">{s.city}</td>
              <td className="px-4 py-3">
                <Badge tone={statusTone(s.status)}>{enumLabel(s.status, t)}</Badge>
              </td>
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  <Button variant="secondary" disabled={busy === s.id} onClick={() => performance(s)}>
                    <Activity size={14} /> {t("proc.performance")}
                  </Button>
                  {canAssess && (
                    <Button variant="secondary" disabled={busy === s.id} onClick={() => assess(s)}>
                      <Gauge size={14} /> {t("proc.risk")}
                    </Button>
                  )}
                  <RowActions
                    record={s}
                    entityLabel={t("entity.supplier")}
                    endpoint="/suppliers"
                    fields={supplierFields(t)}
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
                ? t("proc.noSuppliersMatch")
                : canManage
                  ? t("proc.noSuppliersCreate")
                  : t("proc.noSuppliers")
            }
          />
        )}
        <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
      </Card>

      {perf && (
        <Modal title={t("proc.perfTitle", { name: perf.supplier_name })} onClose={() => setPerf(undefined)}>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            <LabelValue label={t("proc.totalPos")} value={perf.total_purchase_orders} />
            <LabelValue label={t("proc.latePos")} value={perf.late_purchase_orders} />
            <LabelValue label={t("proc.onTimeRate")} value={`${perf.on_time_rate.toFixed(1)}%`} />
            <LabelValue label={t("proc.totalDelay")} value={t("proc.daysUnit", { n: perf.total_delay_days })} />
            <LabelValue label={t("proc.avgDelayLate")} value={t("proc.daysUnit", { n: perf.average_delay_days_when_late.toFixed(1) })} />
            <LabelValue label={t("proc.ncrs")} value={perf.ncr_count} />
          </div>
          {perf.top_delay_causes.length > 0 && (
            <div className="mt-5">
              <div className="mb-2 text-xs font-medium text-slate-500">{t("proc.topDelayCauses")}</div>
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
        <Modal title={t("proc.riskTitle", { name: risk.supplier_name })} onClose={() => setRisk(undefined)}>
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <Badge tone={statusTone(risk.risk_level)}>{enumLabel(risk.risk_level, t)}</Badge>
              <span className="text-sm text-slate-500">{t("proc.score", { n: risk.risk_score.toFixed(1) })}</span>
              <ProviderTag provider={risk.provider} model={risk.model} />
            </div>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <LabelValue label={t("proc.onTimeRate")} value={`${risk.on_time_rate.toFixed(1)}%`} />
              <LabelValue label={t("proc.latePos")} value={risk.late_purchase_orders} />
              <LabelValue label={t("proc.ncrs")} value={risk.ncr_count} />
              <LabelValue label={t("proc.totalDelay")} value={t("proc.daysUnit", { n: risk.total_delay_days })} />
            </div>
            {risk.drivers.length > 0 && (
              <LabelValue
                label={t("proc.riskDrivers")}
                value={
                  <ul className="list-inside list-disc text-slate-700">
                    {risk.drivers.map((d, i) => (
                      <li key={i}>{d}</li>
                    ))}
                  </ul>
                }
              />
            )}
            <LabelValue label={t("proc.recommendation")} value={risk.recommendation} />
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
          title={t("proc.importSuppliers")}
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
  const t = useT();
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
    <Modal title={t("proc.newSupplier")} onClose={onClose}>
      <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <Field label={t("field.supplierName")}>
            <Input required value={form.supplier_name} onChange={(e) => set("supplier_name", e.target.value)} />
          </Field>
        </div>
        <Field label={t("field.category")}>
          <Select value={form.category} onChange={(e) => set("category", e.target.value)}>
            {SUPPLIER_CATEGORIES.map((c) => (
              <option key={c} value={c}>{enumLabel(c, t)}</option>
            ))}
          </Select>
        </Field>
        <Field label={t("field.city")}>
          <Input required value={form.city} onChange={(e) => set("city", e.target.value)} />
        </Field>
        <Field label={t("field.status")}>
          <Select value={form.status} onChange={(e) => set("status", e.target.value)}>
            {["Active", "Inactive"].map((s) => (
              <option key={s} value={s}>{enumLabel(s, t)}</option>
            ))}
          </Select>
        </Field>
        <div className="sm:col-span-2">
          {error && <ErrorBox message={error} />}
          <div className="mt-2 flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={onClose}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? t("project.creating") : t("proc.createSupplier")}
            </Button>
          </div>
        </div>
      </form>
    </Modal>
  );
}
