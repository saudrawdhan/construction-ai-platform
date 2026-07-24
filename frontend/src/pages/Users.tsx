import { useCallback, useEffect, useState } from "react";
import { Plus, UserPlus } from "lucide-react";
import { api, ApiError, type Page, type User } from "../lib/api";
import { useAuth } from "../lib/auth";
import { dateTime, roleLabel } from "../lib/format";
import { useT } from "../lib/i18n";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorBox,
  Field,
  Input,
  Modal,
  PageHeader,
  Pagination,
  Select,
  Spinner,
  Table,
} from "../components/ui";

const ROLES = [
  "admin",
  "executive",
  "project_manager",
  "site_engineer",
  "procurement_officer",
  "qa_qc",
  "viewer",
];

export default function Users() {
  const { user: me } = useAuth();
  const t = useT();
  const [data, setData] = useState<Page<User>>();
  const [error, setError] = useState<string>();
  const [forbidden, setForbidden] = useState(false);
  const [page, setPage] = useState(1);
  const [showForm, setShowForm] = useState(false);
  const [rowBusy, setRowBusy] = useState<number>();

  const load = useCallback(() => {
    setError(undefined);
    setForbidden(false);
    api
      .get<Page<User>>(`/users?page=${page}&size=20`)
      .then(setData)
      .catch((e: ApiError) => (e.status === 403 ? setForbidden(true) : setError(e.message)));
  }, [page]);

  useEffect(() => {
    load();
  }, [load]);

  async function patchUser(id: number, body: Record<string, unknown>) {
    setRowBusy(id);
    setError(undefined);
    try {
      await api.patch<User>(`/users/${id}`, body);
      load();
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setRowBusy(undefined);
    }
  }

  if (forbidden)
    return (
      <div>
        <PageHeader title={t("nav.users")} />
        <Card>
          <EmptyState message={t("users.restricted")} />
        </Card>
      </div>
    );

  return (
    <div>
      <div className="flex items-start justify-between">
        <PageHeader title={t("nav.users")} subtitle={t("users.subtitle")} />
        <Button onClick={() => setShowForm(true)}>
          <Plus size={16} /> {t("users.addUser")}
        </Button>
      </div>

      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
      {!data && !error && <Spinner />}

      {data && (
        <Card>
          <Table head={[t("col.name"), t("col.email"), t("col.role"), t("col.status"), t("col.created"), t("col.actions")]}>
            {data.items.map((u) => {
              const isSelf = me?.id === u.id;
              return (
                <tr key={u.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-slate-800">
                    {u.full_name}
                    {isSelf && <span className="ms-2 text-xs text-slate-400">{t("users.you")}</span>}
                  </td>
                  <td className="px-4 py-3 text-slate-600">{u.email}</td>
                  <td className="px-4 py-3">
                    <Select
                      className="w-44"
                      value={u.role}
                      disabled={isSelf || rowBusy === u.id}
                      onChange={(e) => patchUser(u.id, { role: e.target.value })}
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r}>
                          {roleLabel(r, t)}
                        </option>
                      ))}
                    </Select>
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={u.is_active ? "green" : "slate"}>
                      {u.is_active ? t("users.activeBadge") : t("users.inactiveBadge")}
                    </Badge>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                    {dateTime(u.created_at)}
                  </td>
                  <td className="px-4 py-3">
                    {!isSelf && (
                      <Button
                        variant={u.is_active ? "secondary" : "primary"}
                        disabled={rowBusy === u.id}
                        onClick={() => patchUser(u.id, { is_active: !u.is_active })}
                      >
                        {u.is_active ? t("users.deactivate") : t("users.activate")}
                      </Button>
                    )}
                  </td>
                </tr>
              );
            })}
          </Table>
          {data.items.length === 0 && <EmptyState message={t("users.noneYet")} />}
          <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
        </Card>
      )}

      {showForm && (
        <NewUserModal
          onClose={() => setShowForm(false)}
          onCreated={() => {
            setShowForm(false);
            setPage(1);
            load();
          }}
        />
      )}
    </div>
  );
}

function NewUserModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const t = useT();
  const [form, setForm] = useState({
    email: "",
    full_name: "",
    role: "viewer",
    password: "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();

  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(undefined);
    try {
      await api.post("/users", form);
      onCreated();
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal title={t("users.addUser")} onClose={onClose}>
      <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
        <Field label={t("field.fullName")}>
          <Input required value={form.full_name} onChange={(e) => set("full_name", e.target.value)} />
        </Field>
        <Field label={t("login.email")}>
          <Input
            required
            type="email"
            value={form.email}
            onChange={(e) => set("email", e.target.value)}
            placeholder="name@company.com"
          />
        </Field>
        <Field label={t("col.role")}>
          <Select value={form.role} onChange={(e) => set("role", e.target.value)}>
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {roleLabel(r, t)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("field.password8")}>
          <Input
            required
            type="password"
            minLength={8}
            value={form.password}
            onChange={(e) => set("password", e.target.value)}
          />
        </Field>
        <div className="sm:col-span-2">
          {error && <ErrorBox message={error} />}
          <div className="mt-2 flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={onClose}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={saving}>
              <UserPlus size={16} /> {saving ? t("users.creating") : t("users.createUser")}
            </Button>
          </div>
        </div>
      </form>
    </Modal>
  );
}
