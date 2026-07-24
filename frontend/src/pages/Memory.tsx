import { useEffect, useState } from "react";
import { Search, Sparkles, Plus, Trash2 } from "lucide-react";
import { api, ApiError, type Page } from "../lib/api";
import { useAuth } from "../lib/auth";
import { dateTime, enumLabel } from "../lib/format";
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

const memoryFields = (t: Translate) => [
  { name: "category", label: t("mem.category"), type: "select" as const, options: CATEGORIES, initial: "decision" },
  { name: "summary", label: t("field.summary"), required: true, full: true },
  { name: "detail", label: t("field.detail"), type: "textarea" as const },
  { name: "project_id", label: t("field.projectOptional"), type: "project" as const },
  { name: "source_type", label: t("field.sourceTypeOptional"), type: "text" as const },
  { name: "confidence", label: t("field.confidenceOptional"), type: "number" as const },
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
  const t = useT();
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
        <Badge tone={categoryTone[m.category] ?? "slate"}>{enumLabel(m.category, t)}</Badge>
        <div className="flex items-center gap-2 text-xs text-slate-400">
          {score !== undefined && <span className="font-medium text-blue-600">{t("mem.score", { n: score.toFixed(3) })}</span>}
          {m.confidence !== null && <span>{t("mem.conf", { n: m.confidence.toFixed(2) })}</span>}
          {canManage && onDeleted && (
            <button
              onClick={() => setConfirming(true)}
              aria-label={t("mem.deleteAria")}
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
        {m.source_type ? t("mem.source", { src: m.source_type }) : ""}
        {m.project_id ? t("mem.projectRef", { id: m.project_id }) : ""}
      </div>

      {confirming && (
        <Modal title={t("mem.deleteTitle")} onClose={() => setConfirming(false)}>
          <div className="space-y-4">
            <p className="text-sm text-slate-600">{t("mem.confirmDelete")}</p>
            {error && <ErrorBox message={error} />}
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setConfirming(false)}>
                {t("common.cancel")}
              </Button>
              <Button variant="danger" disabled={deleting} onClick={confirmDelete}>
                {deleting ? t("rowActions.deleting") : t("common.delete")}
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
  const t = useT();
  const canExtract = !!user && user.role !== "viewer";
  const [tab, setTab] = useState<Tab>("browse");

  const tabs: { key: Tab; label: string }[] = [
    { key: "browse", label: t("mem.tabBrowse") },
    { key: "search", label: t("mem.tabSearch") },
    ...(canExtract ? [{ key: "extract" as Tab, label: t("mem.tabExtract") }] : []),
  ];

  return (
    <div>
      <PageHeader title={t("mem.title")} subtitle={t("mem.subtitle")} />
      <Tabs tabs={tabs} active={tab} onChange={setTab} />
      {tab === "browse" && <Browse />}
      {tab === "search" && <SearchTab />}
      {tab === "extract" && canExtract && <ExtractTab />}
    </div>
  );
}

function Browse() {
  const { user } = useAuth();
  const t = useT();
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
        <Field label={t("mem.category")}>
          <Select
            value={category}
            onChange={(e) => {
              setCategory(e.target.value);
              setPage(1);
            }}
          >
            <option value="">{t("mem.allCategories")}</option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {enumLabel(c, t)}
              </option>
            ))}
          </Select>
        </Field>
        {canManage && (
          <Button onClick={() => setShowCreate(true)}>
            <Plus size={16} /> {t("mem.new")}
          </Button>
        )}
      </FilterBar>
      {data.items.length === 0 ? (
        <Card>
          <EmptyState message={t("mem.noneYet")} />
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
          title={t("mem.new")}
          endpoint="/memory/create"
          fields={memoryFields(t)}
          submitLabel={t("mem.save")}
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
  const t = useT();
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
        <Field label={t("mem.query")}>
          <Input
            className="w-72"
            placeholder={t("mem.queryPlaceholder")}
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </Field>
        <Field label={t("mem.category")}>
          <Select value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">{t("mem.any")}</option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {enumLabel(c, t)}
              </option>
            ))}
          </Select>
        </Field>
        <Button type="submit" disabled={busy || q.trim().length < 2}>
          <Search size={15} /> {busy ? t("mem.searching") : t("common.search")}
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
              <EmptyState message={t("mem.noMatch")} />
            </Card>
          )}
        </div>
      )}
    </>
  );
}

function ExtractTab() {
  const t = useT();
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
          <Field label={t("mem.sourceText")}>
            <Textarea
              rows={5}
              placeholder={t("mem.sourcePlaceholder")}
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
              {t("mem.persist")}
            </label>
            <Button type="submit" disabled={busy || text.trim().length < 10}>
              <Sparkles size={15} /> {busy ? t("mem.extracting") : t("mem.extract")}
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
              {t("mem.extractedCount", { n: result.extracted.length })}
              {result.stored.length > 0 ? t("mem.persistedCount", { n: result.stored.length }) : ""}
            </span>
          </div>
          <div className="space-y-3">
            {result.extracted.map((m, i) => (
              <div key={i} className="rounded-lg border border-slate-200 p-4">
                <div className="flex items-center justify-between">
                  <Badge tone={categoryTone[m.category] ?? "slate"}>{enumLabel(m.category, t)}</Badge>
                  <span className="text-xs text-slate-400">{t("mem.conf", { n: m.confidence_score.toFixed(2) })}</span>
                </div>
                <p className="mt-2 text-sm font-medium text-slate-800">{m.summary}</p>
                {m.detail && <p className="mt-1 text-sm text-slate-600">{m.detail}</p>}
              </div>
            ))}
            {result.extracted.length === 0 && (
              <Card>
                <EmptyState message={t("mem.noneExtracted")} />
              </Card>
            )}
          </div>
        </div>
      )}
    </>
  );
}
