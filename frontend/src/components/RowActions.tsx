import { useState } from "react";
import { Pencil, Trash2 } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { Button, ErrorBox, Modal } from "./ui";
import CreateModal, { type FormField } from "./CreateModal";

/**
 * Per-row Edit + Delete controls for an operational entity, reused across the list pages so the
 * behaviour stays identical everywhere. Edit reuses the shared `CreateModal` in edit mode (PATCH);
 * delete asks for confirmation, then DELETEs. Both call `onChanged` so the list reloads.
 *
 * `initial` values for the edit form are derived from the row: every editable field name is read off
 * the record and coerced to a string for the form inputs (a date field already arrives as YYYY-MM-DD).
 */
export default function RowActions<T extends { id: number }>({
  record,
  entityLabel,
  endpoint,
  fields,
  canManage,
  onChanged,
}: {
  record: T;
  entityLabel: string;
  endpoint: string;
  fields: FormField[];
  canManage: boolean;
  onChanged: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string>();

  if (!canManage) return null;

  const row = record as Record<string, unknown>;
  const initial = Object.fromEntries(
    fields
      .filter((f) => f.type !== "project")
      .map((f) => {
        const value = row[f.name];
        return [f.name, value === null || value === undefined ? "" : String(value)];
      })
  );

  async function confirmDelete() {
    setDeleting(true);
    setError(undefined);
    try {
      await api.del(`${endpoint}/${record.id}`);
      setConfirming(false);
      onChanged();
    } catch (e) {
      const err = e as ApiError;
      setError(
        err.status === 409
          ? `This ${entityLabel.toLowerCase()} still has related records and cannot be deleted.`
          : err.message
      );
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="flex gap-1.5">
      <Button variant="ghost" className="px-2" onClick={() => setEditing(true)} aria-label="Edit">
        <Pencil size={15} />
      </Button>
      <Button
        variant="ghost"
        className="px-2 text-red-600 hover:bg-red-50"
        onClick={() => {
          setError(undefined);
          setConfirming(true);
        }}
        aria-label="Delete"
      >
        <Trash2 size={15} />
      </Button>

      {editing && (
        <CreateModal
          title={`Edit ${entityLabel}`}
          endpoint={endpoint}
          editId={record.id}
          initial={initial}
          fields={fields}
          submitLabel="Save Changes"
          onClose={() => setEditing(false)}
          onCreated={() => {
            setEditing(false);
            onChanged();
          }}
        />
      )}

      {confirming && (
        <Modal title={`Delete ${entityLabel}`} onClose={() => setConfirming(false)}>
          <div className="space-y-4">
            <p className="text-sm text-slate-600">
              This will permanently delete this {entityLabel.toLowerCase()}. This action cannot be
              undone.
            </p>
            {error && <ErrorBox message={error} />}
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setConfirming(false)}>
                Cancel
              </Button>
              <Button variant="danger" disabled={deleting} onClick={confirmDelete}>
                {deleting ? "Deleting…" : "Delete"}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
