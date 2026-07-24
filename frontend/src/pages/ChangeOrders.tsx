import { useEffect, useState } from "react";
import { Plus, Upload } from "lucide-react";
import { api, type Page } from "../lib/api";
import { useAuth } from "../lib/auth";
import { money, enumLabel } from "../lib/format";
import { useT, type Translate } from "../lib/i18n";
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

const changeOrderFields = (t: Translate) => [
  { name: "project_id", label: t("common.project"), type: "project" as const, required: true },
  { name: "co_number", label: t("field.coNumber"), required: true },
  {
    name: "status",
    label: t("field.status"),
    type: "select" as const,
    options: ["Pending", "Under Review", "Approved", "Rejected"],
    initial: "Pending",
  },
  { name: "value", label: t("field.valueSar"), type: "number" as const, required: true },
  { name: "description", label: t("field.description"), type: "textarea" as const, required: true },
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
  const t = useT();
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
        <PageHeader title={t("nav.changeOrders")} subtitle={t("co.subtitle")} />
        {canManage && (
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setShowImport(true)}>
              <Upload size={16} /> {t("common.import")}
            </Button>
            <Button onClick={() => setShowCreate(true)}>
              <Plus size={16} /> {t("co.new")}
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
              <option key={s} value={s}>{enumLabel(s, t)}</option>
            ))}
          </Select>
        </Field>
      </FilterBar>

      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
      {!data && !error && <Spinner />}

      {data && (
        <Card>
          <Table head={[t("col.changeOrder"), t("col.description"), t("col.value"), t("col.status"), ""]}>
            {data.items.map((co) => (
              <tr key={co.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-mono text-xs text-slate-500">{co.co_number}</td>
                <td className="max-w-md px-4 py-3 text-slate-700">
                  <div className="truncate">{co.description}</div>
                </td>
                <td className="px-4 py-3 font-medium text-slate-800">{money(co.value)}</td>
                <td className="px-4 py-3">
                  <Badge tone={statusTone(co.status)}>{enumLabel(co.status, t)}</Badge>
                </td>
                <td className="px-4 py-3 text-end">
                  <RowActions
                    record={co}
                    entityLabel={t("entity.changeOrder")}
                    endpoint="/change-orders"
                    fields={changeOrderFields(t)}
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
                  ? t("co.noneMatch")
                  : canManage
                    ? t("co.noneYetCreate")
                    : t("co.noneYet")
              }
            />
          )}
          <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
        </Card>
      )}

      {showCreate && (
        <CreateModal
          title={t("co.new")}
          endpoint="/change-orders"
          fields={changeOrderFields(t)}
          submitLabel={t("co.createCo")}
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
          title={t("co.importTitle")}
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
