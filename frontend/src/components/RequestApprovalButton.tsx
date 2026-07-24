import { useState } from "react";
import { ShieldCheck, Check } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useT } from "../lib/i18n";
import { Button } from "./ui";

/**
 * Sends an AI-recommended high-risk action to the human-in-the-loop approval queue (POST /approvals).
 * Dropped into workflow result modals so the governance gate is reachable from the product, not just
 * the API: the AI recommends, a user requests approval, an approver resolves it, and the requester is
 * notified. Hidden from read-only (viewer) accounts.
 */
export default function RequestApprovalButton({
  actionType,
  projectId,
  payload,
  riskLevel = "high",
  label,
}: {
  actionType: string;
  projectId?: number | null;
  payload: Record<string, unknown>;
  riskLevel?: string;
  label?: string;
}) {
  const t = useT();
  const { user } = useAuth();
  const canRequest = !!user && user.role !== "viewer";
  const [state, setState] = useState<"idle" | "busy" | "done">("idle");
  const [error, setError] = useState<string>();

  if (!canRequest) return null;

  async function submit() {
    setState("busy");
    setError(undefined);
    try {
      await api.post("/approvals", {
        action_type: actionType,
        project_id: projectId ?? null,
        payload,
        risk_level: riskLevel,
      });
      setState("done");
    } catch (e) {
      setError((e as ApiError).message);
      setState("idle");
    }
  }

  if (state === "done") {
    return (
      <span className="inline-flex items-center gap-1.5 text-sm font-medium text-emerald-600">
        <Check size={15} /> {t("approval.sent")}
      </span>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <Button variant="secondary" onClick={submit} disabled={state === "busy"}>
        <ShieldCheck size={15} />{" "}
        {state === "busy" ? t("approval.requesting") : (label ?? t("approval.request"))}
      </Button>
      {error && <span className="text-xs text-red-600">{error}</span>}
    </div>
  );
}
