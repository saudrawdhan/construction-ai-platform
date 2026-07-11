import { useRef, useState } from "react";
import { Download, Upload } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { Badge, Button, ErrorBox, Field, Modal } from "./ui";

interface ImportReport {
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  created: number;
  dry_run: boolean;
  errors: { row: number; errors: string[] }[];
}

export default function ImportModal({
  title,
  importPath,
  templatePath,
  templateFilename,
  onImported,
  onClose,
}: {
  title: string;
  importPath: string;
  templatePath: string;
  templateFilename: string;
  onImported: () => void;
  onClose: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [dryRun, setDryRun] = useState(true);
  const [report, setReport] = useState<ImportReport>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const fileRef = useRef<HTMLInputElement>(null);

  async function getTemplate() {
    setError(undefined);
    try {
      await api.download(templatePath, templateFilename);
    } catch (e) {
      setError((e as ApiError).message);
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(undefined);
    setReport(undefined);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("dry_run", String(dryRun));
      const res = await api.upload<ImportReport>(importPath, form);
      setReport(res);
      if (!res.dry_run && res.created > 0) onImported();
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={title} onClose={onClose}>
      <div className="space-y-4">
        <div className="rounded-lg bg-slate-50 p-3 text-sm text-slate-600">
          Upload a <span className="font-medium">.csv</span> or{" "}
          <span className="font-medium">.xlsx</span> file whose columns match the template.{" "}
          <button
            type="button"
            onClick={getTemplate}
            className="inline-flex items-center gap-1 font-medium text-blue-600 hover:underline"
          >
            <Download size={14} /> Download template
          </button>
        </div>

        <form onSubmit={submit} className="space-y-3">
          <Field label="File">
            <input
              ref={fileRef}
              type="file"
              accept=".csv,.xlsx"
              onChange={(e) => {
                setFile(e.target.files?.[0] ?? null);
                setReport(undefined);
              }}
              className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:text-sm file:font-medium file:text-slate-700 hover:file:bg-slate-200"
            />
          </Field>
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={dryRun}
              onChange={(e) => setDryRun(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300"
            />
            Validate first without saving (recommended)
          </label>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={onClose}>
              Close
            </Button>
            <Button type="submit" disabled={busy || !file}>
              <Upload size={16} /> {busy ? "Processing…" : dryRun ? "Validate" : "Import"}
            </Button>
          </div>
        </form>

        {error && <ErrorBox message={error} />}

        {report && (
          <div className="rounded-lg border border-slate-200 p-4">
            <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
              <Badge tone="slate">{report.total_rows} rows</Badge>
              <Badge tone="green">{report.valid_rows} valid</Badge>
              {report.invalid_rows > 0 && <Badge tone="red">{report.invalid_rows} invalid</Badge>}
              {report.dry_run ? (
                <span className="text-slate-500">Preview only — nothing saved.</span>
              ) : (
                <span className="font-medium text-emerald-700">{report.created} imported.</span>
              )}
            </div>
            {report.dry_run && report.valid_rows > 0 && report.invalid_rows === 0 && (
              <p className="text-sm text-slate-600">
                All rows are valid. Uncheck “Validate first” and import to save them.
              </p>
            )}
            {report.errors.length > 0 && (
              <div className="mt-2">
                <div className="mb-1 text-xs font-medium text-slate-500">Rows with problems</div>
                <div className="max-h-48 space-y-1 overflow-y-auto">
                  {report.errors.map((e, i) => (
                    <div key={i} className="rounded bg-red-50 px-2 py-1 text-xs text-red-700">
                      Row {e.row}: {e.errors.join("; ")}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </Modal>
  );
}
