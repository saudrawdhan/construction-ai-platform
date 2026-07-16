import { useEffect, useState } from "react";
import { Search, Sparkles, Plus, Trash2 } from "lucide-react";
import { api, ApiError, type Page } from "../lib/api";
import { useAuth } from "../lib/auth";
import { dateTime, titleCase } from "../lib/format";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorBox,
  Field,
  FilterBar,
  Input,
  Modal,
  PageHeader,
  Pagination,
  ProviderTag,
  Select,
  Spinner,
  Tabs,
  Textarea,
} from "../components/ui";
import CreateModal from "../components/CreateModal";

interface Memory {
  id: number;
  project_id: number | null;
  category: string;
  summary: string;
  detail: string | null;
  source_type: string | null;
  confidence: number | null;
  created_by: string;
  created_at: string;
}

const CATEGORIES = [
  "decision",
  "risk",
  "issue",
  "lesson_learned",
  "supplier_performance",
  "procurement_blocker",
  "safety_event",
  "client_instruction",
];

const MEMORY_FIELDS = [
  { name: "category", label: "Category", type: "select" as const, options: CATEGORIES, initial: "decision" },
  { name: "summary", label: "Summary", required: true, full: true },
  { name: "detail", label: "Detail", type: "textarea" as const },
  { name: "project_id", label: "Project (optional)", type: "project" as const },
  { name: "source_type", label: "Source type (optional)", type: "text" as const },
  { name: "confidence", label: "Confidence 0–1 (optional)", type: "number" as const },
];

const categoryTone: Record<string, "red" | "amber" | "blue" | "green" | "slate"> = {
  risk: "red",
  safety_event: "red",
  issue: "amber",
  procurement_blocker: "amber",
  decision: "blue",
  client_instruction: "blue",
  lesson_learned: "green",
  supplier_performance: "slate",
};

function MemoryCard({ m, score, onDeleted }: { m: Memory; score?: number; onDeleted?: () => void }) {
  const { user } = useAuth();
  const canManage = !!user && user.role !== "viewer";
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string>();

  async function confirmDelete() {
    setDeleting(true);
    setError(undefined);
    try {
      await api.del(`/memory/${m.id}`);
      setConfirming(false);
      onDeleted?.();
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="rounded-lg border border-slate-200 p-4">
      <div className="flex items-center justify-between">
        <Badge tone={categoryTone[m.category] ?? "slate"}>{titleCase(m.category)}</Badge>
        <div className="flex items-center gap-2 text-xs text-slate-400">
          {score !== undefined && <span className="font-medium text-blue-600">score {score.toFixed(3)}</span>}
          {m.confidence !== null && <span>conf {m.confidence.toFixed(2)}</span>}
          {canManage && onDeleted && (
            <button
              onClick={() => setConfirming(true)}
              aria-label="Delete memory"
              className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600"
            >
              <Trash2 size={14} />
            </button>
          )}
        </div>
      </div>
      <p className="mt-2 text-sm font-medium text-slate-800">{m.summary}</p>
      {m.detail && <p className="mt-1 text-sm text-slate-600">{m.detail}</p>}
      <div className="mt-2 text-xs text-slate-400">
        {m.created_by} · {dateTime(m.created_at)}
        {m.source_type ? ` · source: ${m.source_type}` : ""}
        {m.project_id ? ` · project #${m.project_id}` : ""}
      </div>

      {confirming && (
        <Modal title="Delete Memory" onClose={() => setConfirming(false)}>
          <div className="space-y-4">
            <p className="text-sm text-slate-600">
              This will permanently delete this memory. This action cannot be undone.
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

type Tab = "browse" | "search" | "extract";

export default function Memory() {
  const { user } = useAuth();
  const canExtract = !!user && user.role !== "viewer";
  const [tab, setTab] = useState<Tab>("browse");

  const tabs: { key: Tab; label: string }[] = [
    { key: "browse", label: "Browse" },
    { key: "search", label: "Semantic Search" },
    ...(canExtract ? [{ key: "extract" as Tab, label: "Extract Agent" }] : []),
  ];

  return (
    <div>
      <PageHeader title="Enterprise Memory" subtitle="Organizational knowledge with source attribution and hybrid retrieval" />
      <Tabs tabs={tabs} active={tab} onChange={setTab} />
      {tab === "browse" && <Browse />}
      {tab === "search" && <SearchTab />}
      {tab === "extract" && canExtract && <ExtractTab />}
    </div>
  );
}

function Browse() {
  const { user } = useAuth();
  const canManage = !!user && user.role !== "viewer";
  const [data, setData] = useState<Page<Memory>>();
  const [error, setError] = useState<string>();
  const [page, setPage] = useState(1);
  const [category, setCategory] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    const params = new URLSearchParams({ page: String(page), size: "20" });
    if (category) params.set("category", category);
    setError(undefined);
    api.get<Page<Memory>>(`/memory?${params}`).then(setData).catch((e) => setError(e.message));
  }, [page, category, refresh]);

  if (error) return <div className="text-sm text-red-600">{error}</div>;
  if (!data) return <Spinner />;

  return (
    <>
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
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {titleCase(c)}
              </option>
            ))}
          </Select>
        </Field>
        {canManage && (
          <Button onClick={() => setShowCreate(true)}>
            <Plus size={16} /> New Memory
          </Button>
        )}
      </FilterBar>
      {data.items.length === 0 ? (
        <Card>
          <EmptyState message="No memories recorded yet. Use the Extract Agent to build organizational memory." />
        </Card>
      ) : (
        <div className="space-y-3">
          {data.items.map((m) => (
            <MemoryCard key={m.id} m={m} onDeleted={() => setRefresh((r) => r + 1)} />
          ))}
        </div>
      )}
      <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />

      {showCreate && (
        <CreateModal
          title="New Memory"
          endpoint="/memory/create"
          fields={MEMORY_FIELDS}
          submitLabel="Save Memory"
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            setShowCreate(false);
            setPage(1);
            setRefresh((r) => r + 1);
          }}
        />
      )}
    </>
  );
}

function SearchTab() {
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [results, setResults] = useState<{ memory: Memory; score: number }[]>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  async function run(e: React.FormEvent) {
    e.preventDefault();
    if (q.trim().length < 2) return;
    setBusy(true);
    setError(undefined);
    try {
      const params = new URLSearchParams({ q: q.trim(), k: "10" });
      if (category) params.set("category", category);
      const res = await api.get<{ results: { memory: Memory; score: number }[] }>(`/memory/search?${params}`);
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
            className="w-72"
            placeholder="e.g. supplier delays on steel"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </Field>
        <Field label="Category">
          <Select value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">Any</option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {titleCase(c)}
              </option>
            ))}
          </Select>
        </Field>
        <Button type="submit" disabled={busy || q.trim().length < 2}>
          <Search size={15} /> {busy ? "Searching…" : "Search"}
        </Button>
      </form>

      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
      {results && (
        <div className="space-y-3">
          {results.map(({ memory, score }) => (
            <MemoryCard
              key={memory.id}
              m={memory}
              score={score}
              onDeleted={() =>
                setResults((prev) => prev?.filter((r) => r.memory.id !== memory.id))
              }
            />
          ))}
          {results.length === 0 && (
            <Card>
              <EmptyState message="No matching memories found." />
            </Card>
          )}
        </div>
      )}
    </>
  );
}

function ExtractTab() {
  const [text, setText] = useState("");
  const [store, setStore] = useState(false);
  const [result, setResult] = useState<{
    provider: string;
    model: string;
    extracted: { category: string; summary: string; detail: string | null; confidence_score: number }[];
    stored: Memory[];
  }>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  async function run(e: React.FormEvent) {
    e.preventDefault();
    if (text.trim().length < 10) return;
    setBusy(true);
    setError(undefined);
    try {
      setResult(await api.post("/memory/extract", { text, store }));
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Card className="mb-4 p-5">
        <form onSubmit={run} className="space-y-3">
          <Field label="Source text (meeting notes, site report, correspondence…)">
            <Textarea
              rows={5}
              placeholder="Paste construction text — the agent extracts categorized memories with confidence and source attribution."
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          </Field>
          <div className="flex items-center justify-between">
            <label className="flex items-center gap-2 text-sm text-slate-600">
              <input
                type="checkbox"
                checked={store}
                onChange={(e) => setStore(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300"
              />
              Persist extracted memories to the store
            </label>
            <Button type="submit" disabled={busy || text.trim().length < 10}>
              <Sparkles size={15} /> {busy ? "Extracting…" : "Extract"}
            </Button>
          </div>
        </form>
      </Card>

      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
      {result && (
        <div>
          <div className="mb-3 flex items-center gap-2 text-sm text-slate-500">
            <ProviderTag provider={result.provider} model={result.model} />
            <span>
              {result.extracted.length} extracted
              {result.stored.length > 0 ? ` · ${result.stored.length} persisted` : ""}
            </span>
          </div>
          <div className="space-y-3">
            {result.extracted.map((m, i) => (
              <div key={i} className="rounded-lg border border-slate-200 p-4">
                <div className="flex items-center justify-between">
                  <Badge tone={categoryTone[m.category] ?? "slate"}>{titleCase(m.category)}</Badge>
                  <span className="text-xs text-slate-400">conf {m.confidence_score.toFixed(2)}</span>
                </div>
                <p className="mt-2 text-sm font-medium text-slate-800">{m.summary}</p>
                {m.detail && <p className="mt-1 text-sm text-slate-600">{m.detail}</p>}
              </div>
            ))}
            {result.extracted.length === 0 && (
              <Card>
                <EmptyState message="No memories were extracted from this text." />
              </Card>
            )}
          </div>
        </div>
      )}
    </>
  );
}
