import { useEffect, useRef, useState } from "react";
import { Search, Upload, FileText, Download, Trash2 } from "lucide-react";
import { api, ApiError, type Page } from "../lib/api";
import { useAuth } from "../lib/auth";
import { date } from "../lib/format";
import ProjectPicker from "../components/ProjectPicker";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  FilterBar,
  Input,
  LabelValue,
  Modal,
  PageHeader,
  Pagination,
  Select,
  Spinner,
  Table,
  Tabs,
} from "../components/ui";

interface Document {
  id: number;
  project_id: number;
  doc_type: string;
  title: string;
  doc_date: string | null;
  content_summary: string;
  original_filename: string | null;
  has_file: boolean;
}
interface ProjectOption {
  id: number;
  project_name: string;
}
interface SearchHit {
  id: number;
  source_type: string;
  source_id: number;
  project_id: number | null;
  content: string;
  score: number;
}
interface UploadResult {
  document_id: number;
  title: string;
  doc_type: string;
  characters: number;
  chunks_indexed: number;
  embedding_provider: string;
}

interface GeneratedDocument {
  id: number;
  file_name: string;
  type: string;
  project_id: number;
  document_date: string | null;
  sender: string | null;
  recipient: string | null;
  subject: string;
  body: string;
}

type Tab = "search" | "upload" | "browse" | "generated";

export default function Documents() {
  const { user } = useAuth();
  const canUpload = !!user && user.role !== "viewer";
  const [tab, setTab] = useState<Tab>("search");
  const [projects, setProjects] = useState<ProjectOption[]>([]);

  useEffect(() => {
    api.get<Page<ProjectOption>>("/projects?size=100").then((p) => setProjects(p.items)).catch(() => {});
  }, []);

  const tabs: { key: Tab; label: string }[] = [
    { key: "search", label: "Semantic Search" },
    ...(canUpload ? [{ key: "upload" as Tab, label: "Upload" }] : []),
    { key: "browse", label: "Browse" },
    { key: "generated", label: "Generated" },
  ];

  return (
    <div>
      <PageHeader title="Documents" subtitle="Hybrid RAG search over the corpus and document ingestion" />
      <Tabs tabs={tabs} active={tab} onChange={setTab} />
      {tab === "search" && <SearchTab projects={projects} />}
      {tab === "upload" && canUpload && <UploadTab projects={projects} />}
      {tab === "browse" && <BrowseTab projects={projects} canManage={canUpload} />}
      {tab === "generated" && <GeneratedTab projects={projects} />}
    </div>
  );
}

const GENERATED_TYPES = ["email", "site_report", "meeting_minutes", "claim_thread"];

function GeneratedTab({ projects }: { projects: ProjectOption[] }) {
  const [data, setData] = useState<Page<GeneratedDocument>>();
  const [error, setError] = useState<string>();
  const [page, setPage] = useState(1);
  const [docType, setDocType] = useState("");
  const [selected, setSelected] = useState<GeneratedDocument>();

  const projectName = (id: number) => projects.find((p) => p.id === id)?.project_name ?? `#${id}`;

  useEffect(() => {
    const params = new URLSearchParams({ page: String(page), size: "20" });
    if (docType) params.set("doc_type", docType);
    setError(undefined);
    api.get<Page<GeneratedDocument>>(`/documents/generated?${params}`).then(setData).catch((e) => setError(e.message));
  }, [page, docType]);

  if (!data && error) return <div className="text-sm text-red-600">{error}</div>;
  if (!data) return <Spinner />;

  return (
    <>
      <FilterBar>
        <Field label="Type">
          <Select
            value={docType}
            onChange={(e) => {
              setDocType(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All types</option>
            {GENERATED_TYPES.map((t) => (
              <option key={t} value={t}>
                {t.replace("_", " ")}
              </option>
            ))}
          </Select>
        </Field>
      </FilterBar>
      <Card>
        <Table head={["Subject", "Type", "Project", "Date"]}>
          {data.items.map((d) => (
            <tr key={d.id} className="hover:bg-slate-50">
              <td className="px-4 py-3">
                <button
                  onClick={() => setSelected(d)}
                  className="max-w-xl truncate text-left font-medium text-slate-800 hover:text-blue-700 hover:underline"
                >
                  {d.subject}
                </button>
              </td>
              <td className="px-4 py-3">
                <Badge tone="slate">{d.type.replace("_", " ")}</Badge>
              </td>
              <td className="whitespace-nowrap px-4 py-3 text-slate-600">{projectName(d.project_id)}</td>
              <td className="whitespace-nowrap px-4 py-3 text-slate-600">{date(d.document_date)}</td>
            </tr>
          ))}
        </Table>
        {data.items.length === 0 && <EmptyState message="No generated documents match this filter." />}
        <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
      </Card>

      {selected && (
        <Modal title={selected.subject} onClose={() => setSelected(undefined)}>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <LabelValue label="Type" value={selected.type.replace("_", " ")} />
              <LabelValue label="Date" value={date(selected.document_date)} />
              {selected.sender && <LabelValue label="From" value={selected.sender} />}
              {selected.recipient && <LabelValue label="To" value={selected.recipient} />}
            </div>
            <div className="whitespace-pre-wrap rounded-lg bg-slate-50 p-4 text-sm text-slate-700">
              {selected.body}
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}

function SearchTab({ projects }: { projects: ProjectOption[] }) {
  const [q, setQ] = useState("");
  const [projectId, setProjectId] = useState("");
  const [results, setResults] = useState<SearchHit[]>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  const projectName = (id: number | null) => (id ? projects.find((p) => p.id === id)?.project_name ?? `#${id}` : "—");

  async function run(e: React.FormEvent) {
    e.preventDefault();
    if (q.trim().length < 2) return;
    setBusy(true);
    setError(undefined);
    try {
      const params = new URLSearchParams({ q: q.trim(), k: "10" });
      if (projectId) params.set("project_id", projectId);
      const res = await api.get<{ results: SearchHit[] }>(`/documents/search?${params}`);
      setResults(res.results);
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <form onSubmit={run} className="mb-4 flex flex-wrap items-end gap-3">
        <Field label="Query">
          <Input
            className="w-80"
            placeholder="e.g. delayed steel delivery, unsafe work at height"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </Field>
        <Field label="Project">
          <div className="w-56">
            <ProjectPicker projects={projects} value={projectId} onChange={setProjectId} />
          </div>
        </Field>
        <Button type="submit" disabled={busy || q.trim().length < 2}>
          <Search size={15} /> {busy ? "Searching…" : "Search"}
        </Button>
      </form>

      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
      {results && (
        <div className="space-y-3">
          {results.map((hit) => (
            <div key={hit.id} className="rounded-lg border border-slate-200 p-4">
              <div className="mb-1 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Badge tone="blue">{hit.source_type.replace("_", " ")}</Badge>
                  <span className="text-xs text-slate-400">{projectName(hit.project_id)}</span>
                </div>
                <span className="text-xs font-medium text-blue-600">score {hit.score.toFixed(4)}</span>
              </div>
              <p className="text-sm text-slate-700">{hit.content}</p>
            </div>
          ))}
          {results.length === 0 && (
            <Card>
              <EmptyState message="No matching passages found." />
            </Card>
          )}
        </div>
      )}
    </>
  );
}

function UploadTab({ projects }: { projects: ProjectOption[] }) {
  const [projectId, setProjectId] = useState("");
  const [docType, setDocType] = useState("uploaded");
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<UploadResult>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const fileRef = useRef<HTMLInputElement>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!projectId || !file) return;
    setBusy(true);
    setError(undefined);
    setResult(undefined);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("project_id", projectId);
      form.append("doc_type", docType || "uploaded");
      if (title) form.append("title", title);
      const res = await api.upload<UploadResult>("/documents/upload", form);
      setResult(res);
      setFile(null);
      setTitle("");
      if (fileRef.current) fileRef.current.value = "";
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="max-w-2xl p-5">
      <form onSubmit={submit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Project">
            <ProjectPicker
              projects={projects}
              value={projectId}
              onChange={setProjectId}
              placeholder="Select a project…"
              required
            />
          </Field>
          <Field label="Document type">
            <Input value={docType} onChange={(e) => setDocType(e.target.value)} placeholder="uploaded" />
          </Field>
        </div>
        <Field label="Title (optional)">
          <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Defaults to the file name" />
        </Field>
        <Field label="File (PDF, DOCX, or text — max 10 MB)">
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.docx,.txt,.md,.csv,.log"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:text-sm file:font-medium file:text-slate-700 hover:file:bg-slate-200"
          />
        </Field>
        <Button type="submit" disabled={busy || !projectId || !file}>
          <Upload size={15} /> {busy ? "Ingesting…" : "Upload & Index"}
        </Button>
        {error && <div className="text-sm text-red-600">{error}</div>}
      </form>

      {result && (
        <div className="mt-5 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
          <div className="font-medium">Indexed “{result.title}”</div>
          <div className="mt-1 text-emerald-700">
            {result.characters.toLocaleString()} characters · {result.chunks_indexed} chunk(s) embedded ·
            document #{result.document_id}. It is now searchable and available to the copilot.
          </div>
        </div>
      )}
    </Card>
  );
}

function BrowseTab({ projects, canManage }: { projects: ProjectOption[]; canManage: boolean }) {
  const [data, setData] = useState<Page<Document>>();
  const [error, setError] = useState<string>();
  const [page, setPage] = useState(1);
  const [projectFilter, setProjectFilter] = useState("");
  const [downloadingId, setDownloadingId] = useState<number>();
  const [confirmDelete, setConfirmDelete] = useState<Document>();
  const [deleting, setDeleting] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const projectName = (id: number) => projects.find((p) => p.id === id)?.project_name ?? `#${id}`;

  useEffect(() => {
    const params = new URLSearchParams({ page: String(page), size: "20" });
    if (projectFilter) params.set("project_id", projectFilter);
    setError(undefined);
    api.get<Page<Document>>(`/documents?${params}`).then(setData).catch((e) => setError(e.message));
  }, [page, projectFilter, reloadKey]);

  async function downloadDocument(d: Document) {
    setError(undefined);
    setDownloadingId(d.id);
    try {
      await api.download(`/documents/${d.id}/download`, d.original_filename ?? d.title);
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setDownloadingId(undefined);
    }
  }

  async function deleteDocument() {
    if (!confirmDelete) return;
    setDeleting(true);
    setError(undefined);
    try {
      await api.del(`/documents/${confirmDelete.id}`);
      setConfirmDelete(undefined);
      setReloadKey((k) => k + 1);
    } catch (e) {
      const err = e as ApiError;
      setError(
        err.status === 409
          ? "This document is cited as claim evidence and cannot be deleted."
          : err.message
      );
    } finally {
      setDeleting(false);
    }
  }

  if (!data && error) return <div className="text-sm text-red-600">{error}</div>;
  if (!data) return <Spinner />;

  return (
    <>
      <FilterBar>
        <Field label="Project">
          <div className="w-56">
            <ProjectPicker
              projects={projects}
              value={projectFilter}
              onChange={(v) => {
                setProjectFilter(v);
                setPage(1);
              }}
            />
          </div>
        </Field>
      </FilterBar>
      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
      <Card>
        <Table head={["Title", "Type", "Project", "Date", ""]}>
          {data.items.map((d) => (
            <tr key={d.id} className="hover:bg-slate-50">
              <td className="px-4 py-3">
                <div className="flex items-center gap-2 font-medium text-slate-800">
                  <FileText size={15} className="text-slate-400" />
                  {d.title}
                </div>
                <div className="mt-0.5 max-w-xl truncate text-xs text-slate-500">{d.content_summary}</div>
              </td>
              <td className="px-4 py-3">
                <Badge tone="slate">{d.doc_type}</Badge>
              </td>
              <td className="whitespace-nowrap px-4 py-3 text-slate-600">{projectName(d.project_id)}</td>
              <td className="whitespace-nowrap px-4 py-3 text-slate-600">{date(d.doc_date)}</td>
              <td className="whitespace-nowrap px-4 py-3 text-right">
                <div className="flex items-center justify-end gap-1.5">
                  {d.has_file && (
                    <Button
                      variant="secondary"
                      onClick={() => downloadDocument(d)}
                      disabled={downloadingId === d.id}
                    >
                      <Download size={14} /> {downloadingId === d.id ? "Downloading…" : "Download"}
                    </Button>
                  )}
                  {canManage && (
                    <Button
                      variant="ghost"
                      className="px-2 text-red-600 hover:bg-red-50"
                      onClick={() => {
                        setError(undefined);
                        setConfirmDelete(d);
                      }}
                      aria-label="Delete"
                    >
                      <Trash2 size={15} />
                    </Button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </Table>
        {data.items.length === 0 && <EmptyState message="No documents match this filter." />}
        <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
      </Card>

      {confirmDelete && (
        <Modal title="Delete Document" onClose={() => setConfirmDelete(undefined)}>
          <div className="space-y-4">
            <p className="text-sm text-slate-600">
              This will permanently delete “{confirmDelete.title}”, its indexed search chunks, and its
              stored file. This action cannot be undone.
            </p>
            {error && <div className="text-sm text-red-600">{error}</div>}
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setConfirmDelete(undefined)}>
                Cancel
              </Button>
              <Button variant="danger" disabled={deleting} onClick={deleteDocument}>
                {deleting ? "Deleting…" : "Delete"}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}
