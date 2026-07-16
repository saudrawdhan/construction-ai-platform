import { useEffect, useRef, useState } from "react";
import {
  Bot,
  Send,
  Wrench,
  Sparkles,
  Repeat,
  BrainCircuit,
  FileText,
  ChevronRight,
  PlayCircle,
  MessageSquarePlus,
  History as HistoryIcon,
  Ban,
  RotateCcw,
  Trash2,
} from "lucide-react";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { dateTime } from "../lib/format";
import {
  PageHeader,
  Card,
  Badge,
  ProviderTag,
  Button,
  Spinner,
  ErrorBox,
  EmptyState,
  Field,
  Select,
  Modal,
  Pagination,
} from "../components/ui";

interface ProjectOption {
  id: number;
  project_name: string;
}

interface Source {
  type: string;
  id: number | null;
  label?: string;
}
interface Step {
  index: number;
  thought: string;
  tool: string;
  args: Record<string, unknown>;
  observation: string;
  sources: Source[];
}
interface RunResult {
  id: number | null;
  goal: string;
  status: string;
  final_answer: string;
  steps: Step[];
  sources: Source[];
  step_count: number;
  skill_used: string | null;
  skill_created: string | null;
  provider: string;
  model: string;
  conversation_id: number | null;
}
interface RunSummary {
  id: number;
  goal: string;
  status: string;
  step_count: number;
  skill_used: string | null;
  skill_created: string | null;
  provider: string;
  created_at: string;
}
interface Skill {
  id: number;
  name: string;
  description: string;
  parameters: string[];
  plan: { tool: string; args: Record<string, unknown> }[];
  usage_count: number;
  success_count: number;
  success_rate: number;
  status: string;
  version: number;
}

const CAN_RUN = ["admin", "executive", "project_manager", "site_engineer", "procurement_officer", "qa_qc"];

function StepCard({ step }: { step: Step }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <div className="flex items-center gap-2 text-sm font-medium text-slate-800">
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-slate-100 text-xs text-slate-500">
          {step.index + 1}
        </span>
        <Wrench size={14} className="text-blue-500" />
        <code className="rounded bg-slate-50 px-1.5 py-0.5 text-xs text-slate-700">
          {step.tool}({Object.entries(step.args).map(([k, v]) => `${k}=${v}`).join(", ")})
        </code>
      </div>
      {step.thought && <p className="mt-1.5 pl-7 text-xs italic text-slate-500">{step.thought}</p>}
      <p className="mt-1.5 whitespace-pre-wrap pl-7 text-sm text-slate-700">{step.observation}</p>
      {step.sources.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5 pl-7">
          {step.sources.map((s, i) => (
            <span
              key={i}
              className="inline-flex items-center gap-1 rounded-md bg-slate-50 px-2 py-0.5 text-xs text-slate-500 ring-1 ring-inset ring-slate-200"
            >
              {s.type === "memory" ? <BrainCircuit size={11} /> : <FileText size={11} />}
              {s.label || `${s.type} #${s.id}`}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function SkillCard({
  skill,
  isAdmin,
  onChanged,
}: {
  skill: Skill;
  isAdmin: boolean;
  onChanged?: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [toggleError, setToggleError] = useState<string>();
  const [confirming, setConfirming] = useState(false);
  const [deleteError, setDeleteError] = useState<string>();

  async function toggleStatus() {
    setBusy(true);
    setToggleError(undefined);
    try {
      const next = skill.status === "active" ? "deprecated" : "active";
      await api.patch(`/ai/agent/skills/${skill.id}`, { status: next });
      onChanged?.();
    } catch (e) {
      setToggleError((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  }

  async function confirmDelete() {
    setBusy(true);
    setDeleteError(undefined);
    try {
      await api.del(`/ai/agent/skills/${skill.id}`);
      setConfirming(false);
      onChanged?.();
    } catch (e) {
      const err = e as ApiError;
      setDeleteError(
        err.status === 409
          ? "This skill has run history and cannot be deleted — deprecate it instead."
          : err.message
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <Sparkles size={14} className="shrink-0 text-amber-500" />
            <code className="truncate text-sm font-medium text-slate-800">{skill.name}</code>
            <Badge tone={skill.status === "active" ? "green" : "slate"}>{skill.status}</Badge>
          </div>
          <p className="mt-1 line-clamp-2 text-xs text-slate-500">{skill.description}</p>
        </div>
        {isAdmin && (
          <div className="flex shrink-0 gap-1">
            <button
              onClick={toggleStatus}
              disabled={busy}
              aria-label={skill.status === "active" ? "Deprecate skill" : "Reactivate skill"}
              title={skill.status === "active" ? "Deprecate" : "Reactivate"}
              className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 disabled:opacity-50"
            >
              {skill.status === "active" ? <Ban size={14} /> : <RotateCcw size={14} />}
            </button>
            <button
              onClick={() => {
                setDeleteError(undefined);
                setConfirming(true);
              }}
              aria-label="Delete skill"
              title="Delete"
              className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600"
            >
              <Trash2 size={14} />
            </button>
          </div>
        )}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
        <span>steps: {skill.plan.length}</span>
        <span>used: {skill.usage_count}×</span>
        <span>success: {Math.round(skill.success_rate * 100)}%</span>
        {skill.parameters.length > 0 && <span>params: {skill.parameters.join(", ")}</span>}
      </div>
      <div className="mt-2 flex flex-wrap gap-1">
        {skill.plan.map((p, i) => (
          <span key={i} className="inline-flex items-center text-xs text-slate-400">
            {i > 0 && <ChevronRight size={11} className="mx-0.5" />}
            <code className="rounded bg-slate-50 px-1 py-0.5 text-slate-600">{p.tool}</code>
          </span>
        ))}
      </div>
      {toggleError && <p className="mt-2 text-xs text-red-600">{toggleError}</p>}

      {confirming && (
        <Modal title="Delete Skill" onClose={() => setConfirming(false)}>
          <div className="space-y-4">
            <p className="text-sm text-slate-600">
              This will permanently delete the skill "{skill.name}". This action cannot be undone.
            </p>
            {deleteError && <ErrorBox message={deleteError} />}
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setConfirming(false)}>
                Cancel
              </Button>
              <Button variant="danger" disabled={busy} onClick={confirmDelete}>
                {busy ? "Deleting…" : "Delete"}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

function TurnCard({ turn }: { turn: RunResult }) {
  return (
    <div className="space-y-2">
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-blue-600 px-4 py-2 text-sm text-white">
          {turn.goal}
        </div>
      </div>
      <Card>
        <div className="flex flex-wrap items-center gap-2">
          <Bot size={16} className="text-blue-600" />
          <span className="text-sm font-semibold text-slate-800">Answer</span>
          <Badge tone={turn.status === "completed" ? "green" : "amber"}>{turn.status}</Badge>
          <span className="text-xs text-slate-400">{turn.step_count} tool step(s)</span>
          {turn.skill_used && (
            <span className="inline-flex items-center gap-1 text-xs font-medium text-violet-600">
              <Repeat size={12} /> reused skill "{turn.skill_used}"
            </span>
          )}
          {turn.skill_created && (
            <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-600">
              <Sparkles size={12} /> learned skill "{turn.skill_created}"
            </span>
          )}
          <div className="ml-auto">
            <ProviderTag provider={turn.provider} model={turn.model} />
          </div>
        </div>
        <p className="mt-3 whitespace-pre-wrap text-sm text-slate-700">{turn.final_answer}</p>
      </Card>
      <div>
        <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-slate-500">
          <Wrench size={12} /> Trajectory
        </h3>
        <div className="space-y-2">
          {turn.steps.map((step) => (
            <StepCard key={step.index} step={step} />
          ))}
        </div>
      </div>
    </div>
  );
}

export default function Agent() {
  const { user } = useAuth();
  const canRun = !!user && CAN_RUN.includes(user.role);
  const isAdmin = user?.role === "admin";
  const [goal, setGoal] = useState("");
  const [projects, setProjects] = useState<ProjectOption[]>([]);
  const [projectId, setProjectId] = useState("");
  const [busy, setBusy] = useState(false);
  const [turns, setTurns] = useState<RunResult[]>([]);
  const [conversationId, setConversationId] = useState<number | undefined>();
  const [skills, setSkills] = useState<Skill[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [history, setHistory] = useState<RunSummary[]>([]);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [historyBusy, setHistoryBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  async function loadSkills() {
    try {
      setSkills(await api.get<Skill[]>("/ai/agent/skills"));
    } catch (err) {
      setError((err as ApiError).message);
    }
  }

  useEffect(() => {
    if (!canRun) return;
    loadSkills();
    api
      .get<{ items: ProjectOption[] }>("/projects?size=100")
      .then((p) => setProjects(p.items))
      .catch(() => {});
  }, [canRun]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, busy]);

  function newConversation() {
    setTurns([]);
    setConversationId(undefined);
    setGoal("");
    setError(null);
  }

  async function openHistory(page = 1) {
    setHistoryOpen(true);
    setHistoryBusy(true);
    try {
      const result = await api.get<{ items: RunSummary[]; total: number }>(
        `/ai/agent/runs?page=${page}&size=20`
      );
      setHistory(result.items);
      setHistoryTotal(result.total);
      setHistoryPage(page);
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setHistoryBusy(false);
    }
  }

  async function resumeRun(runId: number) {
    setHistoryBusy(true);
    try {
      const run = await api.get<RunResult>(`/ai/agent/runs/${runId}`);
      setTurns([run]);
      setConversationId(run.conversation_id ?? undefined);
      setHistoryOpen(false);
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setHistoryBusy(false);
    }
  }

  async function submit(path: string, body: Record<string, unknown>) {
    setBusy(true);
    setError(null);
    try {
      const result = await api.post<RunResult>(path, {
        ...body,
        project_id: projectId ? Number(projectId) : null,
        conversation_id: conversationId ?? null,
      });
      setTurns((t) => [...t, result]);
      setConversationId(result.conversation_id ?? undefined);
      await loadSkills();
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setBusy(false);
    }
  }

  async function runAgent(e: React.FormEvent) {
    e.preventDefault();
    const g = goal.trim();
    if (g.length < 3 || busy) return;
    setGoal("");
    await submit("/ai/agent/run", { goal: g });
  }

  async function runSkill(skill: Skill) {
    if (busy) return;
    const g = goal.trim();
    if (g.length < 3) {
      setError("Enter a goal (including any supplier or project number) before running a skill.");
      return;
    }
    setGoal("");
    await submit(`/ai/agent/skills/${skill.id}/run`, { goal: g });
  }

  if (!canRun) {
    return (
      <div>
        <PageHeader title="Construction Agent" />
        <Card>
          <EmptyState message="The agent is restricted to operational roles and is not available to viewers." />
        </Card>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Construction Agent"
        subtitle="Reasons over a goal, remembers this conversation, and turns experience into reusable skills"
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="flex h-[calc(100vh-220px)] min-h-[420px] flex-col lg:col-span-2">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs text-slate-400">
              {conversationId ? `Conversation #${conversationId} — follow-ups keep this context` : "New conversation"}
            </span>
            <div className="flex items-center gap-3">
              <button
                onClick={() => openHistory(1)}
                className="inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-slate-700"
              >
                <HistoryIcon size={13} /> History
              </button>
              {turns.length > 0 && (
                <button
                  onClick={newConversation}
                  className="inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-slate-700"
                >
                  <MessageSquarePlus size={13} /> New conversation
                </button>
              )}
            </div>
          </div>

          <div className="flex-1 space-y-4 overflow-y-auto rounded-xl border border-slate-200 bg-white p-4">
            {turns.length === 0 && !busy && (
              <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-slate-400">
                <Bot size={36} />
                <p className="text-sm">Give the agent a goal and watch it plan, call tools, and answer.</p>
                <p className="text-xs">
                  Follow-up goals stay in this conversation, so "what about its delivery history" resolves
                  against what you just discussed instead of starting from nothing.
                </p>
              </div>
            )}
            {turns.map((turn, i) => (
              <TurnCard key={turn.id ?? i} turn={turn} />
            ))}
            {busy && (
              <div className="flex items-center gap-2 pl-1 text-sm text-slate-400">
                <Spinner /> The agent is reasoning and calling tools…
              </div>
            )}
            <div ref={endRef} />
          </div>

          {error && <div className="mt-3"><ErrorBox message={error} /></div>}

          <form onSubmit={runAgent} className="mt-3 flex flex-wrap items-end gap-2">
            <Field label="Project (optional)">
              <Select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
                <option value="">Whole portfolio</option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.project_name}
                  </option>
                ))}
              </Select>
            </Field>
            <input
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder='Give the agent a goal, e.g. "Assess the risk of supplier 3"'
              className="min-w-[240px] flex-1 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
            />
            <Button type="submit" disabled={busy || goal.trim().length < 3}>
              <Send size={16} /> Run
            </Button>
          </form>
        </div>

        <div>
          <h3 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-slate-700">
            <Sparkles size={14} className="text-amber-500" /> Skill library
            <span className="text-xs font-normal text-slate-400">({skills.length})</span>
          </h3>
          <div className="space-y-2">
            {skills.length === 0 && (
              <Card>
                <p className="text-sm text-slate-400">
                  No skills yet. The agent creates one automatically after it solves a multi-step task.
                </p>
              </Card>
            )}
            {skills.map((skill) => (
              <div key={skill.id} className="space-y-1">
                <SkillCard skill={skill} isAdmin={isAdmin} onChanged={loadSkills} />
                {canRun && skill.status === "active" && (
                  <button
                    onClick={() => runSkill(skill)}
                    disabled={busy || goal.trim().length < 3}
                    className="inline-flex items-center gap-1 pl-1 text-xs font-medium text-blue-600 hover:text-blue-700 disabled:text-slate-300"
                  >
                    <PlayCircle size={13} /> Run this skill on the goal above
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {historyOpen && (
        <Modal title="Past agent runs" onClose={() => setHistoryOpen(false)}>
          {historyBusy && history.length === 0 ? (
            <div className="flex justify-center py-6"><Spinner /></div>
          ) : history.length === 0 ? (
            <EmptyState message="No past runs yet — goals you run will show up here." />
          ) : (
            <>
              <div className="space-y-2">
                {history.map((run) => (
                  <button
                    key={run.id}
                    onClick={() => resumeRun(run.id)}
                    disabled={historyBusy}
                    className="block w-full rounded-lg border border-slate-200 p-3 text-left hover:border-blue-300 hover:bg-blue-50/40 disabled:opacity-50"
                  >
                    <div className="flex items-center gap-2">
                      <Badge tone={run.status === "completed" ? "green" : "amber"}>{run.status}</Badge>
                      <span className="text-xs text-slate-400">{dateTime(run.created_at)}</span>
                      {run.skill_used && (
                        <span className="inline-flex items-center gap-1 text-xs text-violet-600">
                          <Repeat size={11} /> {run.skill_used}
                        </span>
                      )}
                    </div>
                    <p className="mt-1 line-clamp-2 text-sm text-slate-700">{run.goal}</p>
                  </button>
                ))}
              </div>
              <Pagination
                page={historyPage}
                pages={Math.max(1, Math.ceil(historyTotal / 20))}
                total={historyTotal}
                onPage={openHistory}
              />
            </>
          )}
        </Modal>
      )}
    </div>
  );
}
