import { useEffect, useState } from "react";
import { Plus, Upload } from "lucide-react";
import { api, type Page } from "../lib/api";
import { useAuth } from "../lib/auth";
import { money } from "../lib/format";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  FilterBar,
  PageHeader,
  Pagination,
  Select,
  Spinner,
  Table,
  statusTone,
} from "../components/ui";
import CreateModal from "../components/CreateModal";
import ImportModal from "../components/ImportModal";
import RowActions from "../components/RowActions";

const CHANGE_ORDER_FIELDS = [
  { name: "project_id", label: "Project", type: "project" as const, required: true },
  { name: "co_number", label: "Change order no.", required: true },
  {
    name: "status",
    label: "Status",
    type: "select" as const,
    options: ["Pending", "Under Review", "Approved", "Rejected"],
    initial: "Pending",
  },
  { name: "value", label: "Value (SAR)", type: "number" as const, required: true },
  { name: "description", label: "Description", type: "textarea" as const, required: true },
];

const STATUSES = ["Pending", "Under Review", "Approved", "Rejected"];

interface ChangeOrder {
  id: number;
  project_id: number;
  co_number: string;
  description: string;
  value: string;
  status: string;
}

export default function ChangeOrders() {
  const { user } = useAuth();
  const canManage = !!user && ["admin", "project_manager"].includes(user.role);
  const [data, setData] = useState<Page<ChangeOrder>>();
  const [error, setError] = useState<string>();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    const params = new URLSearchParams({ page: String(page), size: "20" });
    if (status) params.set("status", status);
    setError(undefined);
    api
      .get<Page<ChangeOrder>>(`/change-orders?${params}`)
      .then(setData)
      .catch((e) => setError(e.message));
  }, [page, status, refresh]);

  return (
    <div>
      <div className="flex items-start justify-between">
        <PageHeader title="Change Orders" subtitle="Scope and value variations against project contracts" />
        {canManage && (
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setShowImport(true)}>
              <Upload size={16} /> Import
            </Button>
            <Button onClick={() => setShowCreate(true)}>
              <Plus size={16} /> New Change Order
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
              <option key={s}>{s}</option>
            ))}
          </Select>
        </Field>
      </FilterBar>

      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
      {!data && !error && <Spinner />}

      {data && (
        <Card>
          <Table head={["Change Order", "Description", "Value", "Status", ""]}>
            {data.items.map((co) => (
              <tr key={co.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-mono text-xs text-slate-500">{co.co_number}</td>
                <td className="max-w-md px-4 py-3 text-slate-700">
                  <div className="truncate">{co.description}</div>
                </td>
                <td className="px-4 py-3 font-medium text-slate-800">{money(co.value)}</td>
                <td className="px-4 py-3">
                  <Badge tone={statusTone(co.status)}>{co.status}</Badge>
                </td>
                <td className="px-4 py-3 text-right">
                  <RowActions
                    record={co}
                    entityLabel="Change Order"
                    endpoint="/change-orders"
                    fields={CHANGE_ORDER_FIELDS}
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
                status
                  ? "No change orders match this filter."
                  : canManage
                    ? "No change orders yet. Use “New Change Order” to add one."
                    : "No change orders yet."
              }
            />
          )}
          <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
        </Card>
      )}

      {showCreate && (
        <CreateModal
          title="New Change Order"
          endpoint="/change-orders"
          fields={CHANGE_ORDER_FIELDS}
          submitLabel="Create Change Order"
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
          title="Import Change Orders"
          importPath="/change-orders/import"
          templatePath="/change-orders/import/template"
          templateFilename="change_orders_template.csv"
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
