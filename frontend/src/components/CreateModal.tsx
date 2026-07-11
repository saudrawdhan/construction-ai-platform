import { useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";
import { Button, ErrorBox, Field, Input, Modal, Select, Textarea } from "./ui";

export interface FormField {
  name: string;
  label: string;
  type?: "text" | "textarea" | "number" | "date" | "select" | "project";
  options?: string[];
  required?: boolean;
  initial?: string;
  full?: boolean;
}

interface ProjectOption {
  id: number;
  project_name: string;
}

/**
 * A generic, field-config-driven form used for both creating and editing a record. It renders the
 * right control per field, fetches the project list when a `project` field is present, drops empty
 * optional fields (so server defaults apply on create), and submits to `endpoint`.
 *
 * Pass `editId` + `initial` to switch to edit mode: the form pre-fills from `initial`, hides the
 * `project` field (an entity is not re-parented here), and PATCHes `${endpoint}/${editId}`.
 */
export default function CreateModal({
  title,
  endpoint,
  fields,
  submitLabel = "Create",
  editId,
  initial,
  onCreated,
  onClose,
}: {
  title: string;
  endpoint: string;
  fields: FormField[];
  submitLabel?: string;
  editId?: number;
  initial?: Record<string, string>;
  onCreated: () => void;
  onClose: () => void;
}) {
  const isEdit = editId !== undefined;
  const activeFields = isEdit ? fields.filter((f) => f.type !== "project") : fields;
  const [form, setForm] = useState<Record<string, string>>(() =>
    Object.fromEntries(activeFields.map((f) => [f.name, initial?.[f.name] ?? f.initial ?? ""]))
  );
  const [projects, setProjects] = useState<ProjectOption[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();

  useEffect(() => {
    if (activeFields.some((f) => f.type === "project")) {
      api
        .get<{ items: ProjectOption[] }>("/projects?size=100")
        .then((p) => setProjects(p.items))
        .catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const set = (name: string, value: string) => setForm((f) => ({ ...f, [name]: value }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(undefined);
    try {
      const body: Record<string, unknown> = {};
      for (const f of activeFields) {
        const value = form[f.name];
        // On create, an empty optional falls back to the server default. On edit, sending the empty
        // string would fail validation, so we simply omit unchanged/blank fields (PATCH is partial).
        if (value === "") continue;
        body[f.name] = f.type === "project" || f.name.endsWith("_id") ? Number(value) : value;
      }
      if (isEdit) {
        await api.patch(`${endpoint}/${editId}`, body);
      } else {
        await api.post(endpoint, body);
      }
      onCreated();
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal title={title} onClose={onClose}>
      <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
        {activeFields.map((f) => (
          <div key={f.name} className={f.type === "textarea" || f.full ? "sm:col-span-2" : ""}>
            <Field label={f.label}>
              {f.type === "project" ? (
                <Select
                  required={f.required}
                  value={form[f.name]}
                  onChange={(e) => set(f.name, e.target.value)}
                >
                  <option value="">Select a project…</option>
                  {projects.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.project_name}
                    </option>
                  ))}
                </Select>
              ) : f.type === "select" ? (
                <Select value={form[f.name]} onChange={(e) => set(f.name, e.target.value)}>
                  {/* When editing, the record's current value may not be one of the curated
                      options (e.g. a seeded status) — surface it so the dropdown isn't blank. */}
                  {form[f.name] && !(f.options ?? []).includes(form[f.name]) && (
                    <option key={form[f.name]}>{form[f.name]}</option>
                  )}
                  {(f.options ?? []).map((o) => (
                    <option key={o}>{o}</option>
                  ))}
                </Select>
              ) : f.type === "textarea" ? (
                <Textarea
                  required={f.required}
                  rows={3}
                  value={form[f.name]}
                  onChange={(e) => set(f.name, e.target.value)}
                />
              ) : (
                <Input
                  required={f.required}
                  type={f.type === "number" ? "number" : f.type === "date" ? "date" : "text"}
                  value={form[f.name]}
                  onChange={(e) => set(f.name, e.target.value)}
                />
              )}
            </Field>
          </div>
        ))}
        <div className="sm:col-span-2">
          {error && <ErrorBox message={error} />}
          <div className="mt-2 flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? "Saving…" : submitLabel}
            </Button>
          </div>
        </div>
      </form>
    </Modal>
  );
}
