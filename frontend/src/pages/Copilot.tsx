import { useEffect, useRef, useState } from "react";
import { Send, ShieldCheck, ShieldAlert, FileText, BrainCircuit, Mail, TriangleAlert, ListChecks, Gavel, CircleAlert, Flag } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { useT } from "../lib/i18n";
import { PageHeader, ProviderTag } from "../components/ui";

interface Source {
  type: string;
  id: number | null;
  label: string;
  project_id: number | null;
  project_label: string | null;
}
interface Answer {
  conversation_id: number;
  answer: string;
  grounded: boolean;
  sources: Source[];
  provider: string;
  model: string;
}
interface Turn {
  role: "user" | "assistant";
  text: string;
  answer?: Answer;
}

function sourceIcon(type: string) {
  if (type === "memory") return <BrainCircuit size={12} />;
  if (type === "correspondence") return <Mail size={12} />;
  if (type === "project_risk") return <TriangleAlert size={12} />;
  if (type === "meeting_action_item") return <ListChecks size={12} />;
  if (type === "project_decision") return <Gavel size={12} />;
  if (type === "project_issue") return <CircleAlert size={12} />;
  if (type === "project_milestone") return <Flag size={12} />;
  return <FileText size={12} />;
}

function SourceChip({ source }: { source: Source }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-md bg-white px-2 py-0.5 text-xs text-slate-600 ring-1 ring-inset ring-slate-200">
      {sourceIcon(source.type)}
      {source.label}
      {/* Which project a cited record belongs to, so an answer drawing on another project is
          visible at a glance rather than only inside the narrative text. */}
      {source.project_label && (
        <span className="text-slate-400">· {source.project_label}</span>
      )}
    </span>
  );
}

export default function Copilot() {
  const t = useT();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [question, setQuestion] = useState("");
  const [conversationId, setConversationId] = useState<number>();
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, busy]);

  async function ask(e: React.FormEvent) {
    e.preventDefault();
    const q = question.trim();
    if (q.length < 3 || busy) return;
    setTurns((t) => [...t, { role: "user", text: q }]);
    setQuestion("");
    setBusy(true);
    try {
      const res = await api.post<Answer>("/ai/copilot/chat", {
        question: q,
        conversation_id: conversationId,
      });
      setConversationId(res.conversation_id);
      setTurns((t) => [...t, { role: "assistant", text: res.answer, answer: res }]);
    } catch (err) {
      setTurns((prev) => [
        ...prev,
        { role: "assistant", text: t("copilot.error", { msg: (err as ApiError).message }) },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <PageHeader title={t("copilot.title")} subtitle={t("copilot.subtitle")} />

      <div className="flex-1 space-y-4 overflow-y-auto rounded-xl border border-slate-200 bg-white p-5">
        {turns.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-slate-400">
            <BrainCircuit size={36} />
            <p className="text-sm">{t("copilot.emptyHint1")}</p>
            <p className="text-xs">{t("copilot.emptyHint2")}</p>
          </div>
        )}
        {turns.map((turn, i) =>
          turn.role === "user" ? (
            <div key={i} className="flex justify-end">
              <div className="max-w-[80%] rounded-2xl rounded-ee-sm bg-blue-600 px-4 py-2 text-sm text-white">
                {turn.text}
              </div>
            </div>
          ) : (
            <div key={i} className="flex justify-start">
              <div className="max-w-[85%] space-y-2">
                <div className="rounded-2xl rounded-es-sm bg-slate-100 px-4 py-2 text-sm text-slate-800">
                  <p className="whitespace-pre-wrap">{turn.text}</p>
                </div>
                {turn.answer && (
                  <div className="flex flex-wrap items-center gap-2 ps-1">
                    {turn.answer.grounded ? (
                      <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-600">
                        <ShieldCheck size={13} /> {t("copilot.grounded")}
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-600">
                        <ShieldAlert size={13} /> {t("copilot.noEvidence")}
                      </span>
                    )}
                    {turn.answer.sources.map((s, j) => (
                      <SourceChip key={j} source={s} />
                    ))}
                    <ProviderTag provider={turn.answer.provider} model={turn.answer.model} />
                  </div>
                )}
              </div>
            </div>
          )
        )}
        {busy && <div className="ps-1 text-sm text-slate-400">{t("copilot.thinking")}</div>}
        <div ref={endRef} />
      </div>

      <form onSubmit={ask} className="mt-4 flex gap-2">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={t("copilot.placeholder")}
          className="flex-1 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
        />
        <button
          type="submit"
          disabled={busy || question.trim().length < 3}
          className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-blue-700 disabled:bg-blue-300"
        >
          <Send size={16} /> {t("common.send")}
        </button>
      </form>
    </div>
  );
}
