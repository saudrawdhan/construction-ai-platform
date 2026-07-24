import { useCallback, useEffect, useState } from "react";
import { Check, X, History } from "lucide-react";
import { api, ApiError, type Page } from "../lib/api";
import { useAuth } from "../lib/auth";
import { dateTime, titleCase, enumLabel } from "../lib/format";
import { useT } from "../lib/i18n";
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
  Select,
  Spinner,
  Table,
  Textarea,
  statusTone,
} from "../components/ui";

interface Approval {
  id: number;
  project_id: number | null;
  action_type: string;
  payload: Record<string, unknown> | null;
  risk_level: string;
  requested_by: string;
  status: string;
  resolved_by: string | null;
  resolved_at: string | null;
  created_at: string;
}
interface HistoryEntry {
  id: number;
  actor: string;
  action: string;
  note: string | null;
  created_at: string;
}

export default function Approvals() {
  const { user } = useAuth();
  const t = useT();
  const canResolve = !!user && ["admin", "executive", "project_manager"].includes(user.role);
  const [data, setData] = useState<Page<Approval>>();
  const [error, setError] = useState<string>();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("pending");
  const [selected, setSelected] = useState<Approval>();
  const [history, setHistory] = useState<HistoryEntry[]>();
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    const params = new URLSearchParams({ page: String(page), size: "20" });
    if (status) params.set("status", status);
    setError(undefined);
    api.get<Page<Approval>>(`/approvals?${params}`).then(setData).catch((e) => setError(e.message));
  }, [page, status]);

  useEffect(() => {
    load();
  }, [load]);

  async function open(a: Approval) {
    setSelected(a);
    setNote("");
    setHistory(undefined);
    try {
      setHistory(await api.get<HistoryEntry[]>(`/approvals/${a.id}/history`));
    } catch {
      setHistory([]);
    }
  }

  async function resolve(decision: "approve" | "reject") {
    if (!selected) return;
    setBusy(true);
    try {
      await api.post<Approval>(`/approvals/${selected.id}/${decision}`, { note: note || null });
      setSelected(undefined);
      load();
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader title={t("nav.approvals")} subtitle={t("approvals.subtitle")} />

      <FilterBar>
        <Field label={t("field.status")}>
          <Select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
          >
            {["pending", "approved", "rejected", ""].map((s) => (
              <option key={s} value={s}>
                {s ? enumLabel(s, t) : t("common.all")}
              </option>
            ))}
          </Select>
        </Field>
      </FilterBar>

      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
      {!data && !error && <Spinner />}

      {data && (
        <Card>
          <Table head={[t("col.action"), t("col.risk"), t("col.requestedBy"), t("col.status"), t("col.created"), ""]}>
            {data.items.map((a) => (
              <tr key={a.id} className="cursor-pointer hover:bg-slate-50" onClick={() => open(a)}>
                <td className="px-4 py-3 font-medium text-slate-800">{titleCase(a.action_type)}</td>
                <td className="px-4 py-3">
                  <Badge tone={statusTone(a.risk_level)}>{enumLabel(a.risk_level, t)}</Badge>
                </td>
                <td className="px-4 py-3 text-slate-600">{a.requested_by}</td>
                <td className="px-4 py-3">
                  <Badge tone={statusTone(a.status)}>{enumLabel(a.status, t)}</Badge>
                </td>
                <td className="px-4 py-3 text-slate-600">{dateTime(a.created_at)}</td>
                <td className="px-4 py-3 text-end text-xs text-blue-600">{t("approvals.review")}</td>
              </tr>
            ))}
          </Table>
          {data.items.length === 0 && <EmptyState message={t("approvals.noneView")} />}
          <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
        </Card>
      )}

      {selected && (
        <Modal title={titleCase(selected.action_type)} onClose={() => setSelected(undefined)}>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <LabelValue label={t("approvals.riskLevel")} value={<Badge tone={statusTone(selected.risk_level)}>{enumLabel(selected.risk_level, t)}</Badge>} />
              <LabelValue label={t("common.status")} value={<Badge tone={statusTone(selected.status)}>{enumLabel(selected.status, t)}</Badge>} />
              <LabelValue label={t("approvals.requestedBy")} value={selected.requested_by} />
              <LabelValue label={t("col.created")} value={dateTime(selected.created_at)} />
              {selected.resolved_by && <LabelValue label={t("approvals.resolvedBy")} value={selected.resolved_by} />}
              {selected.resolved_at && <LabelValue label={t("approvals.resolvedAt")} value={dateTime(selected.resolved_at)} />}
            </div>

            {selected.payload && Object.keys(selected.payload).length > 0 && (
              <LabelValue
                label={t("approvals.payload")}
                value={
                  <pre className="overflow-x-auto rounded-lg bg-slate-50 p-3 text-xs text-slate-700">
                    {JSON.stringify(selected.payload, null, 2)}
                  </pre>
                }
              />
            )}

            <div>
              <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-slate-500">
                <History size={13} /> {t("approvals.history")}
              </div>
              {!history ? (
                <div className="text-sm text-slate-400">{t("common.loading")}</div>
              ) : (
                <div className="space-y-2">
                  {history.map((h) => (
                    <div key={h.id} className="rounded-lg border border-slate-200 px-3 py-2 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-slate-700">
                          {enumLabel(h.action, t)} · {h.actor}
                        </span>
                        <span className="text-xs text-slate-400">{dateTime(h.created_at)}</span>
                      </div>
                      {h.note && <div className="mt-0.5 text-slate-600">{h.note}</div>}
                    </div>
                  ))}
                  {history.length === 0 && <div className="text-sm text-slate-400">{t("approvals.noHistory")}</div>}
                </div>
              )}
            </div>

            {selected.status === "pending" && canResolve && (
              <div className="border-t border-slate-100 pt-4">
                <Textarea
                  rows={2}
                  placeholder={t("approvals.optionalNote")}
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  className="mb-3"
                />
                <div className="flex gap-2">
                  <Button variant="primary" disabled={busy} onClick={() => resolve("approve")}>
                    <Check size={16} /> {t("approvals.approve")}
                  </Button>
                  <Button variant="danger" disabled={busy} onClick={() => resolve("reject")}>
                    <X size={16} /> {t("approvals.reject")}
                  </Button>
                </div>
              </div>
            )}
            {selected.status === "pending" && !canResolve && (
              <div className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">
                {t("approvals.cannotResolve")}
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}
