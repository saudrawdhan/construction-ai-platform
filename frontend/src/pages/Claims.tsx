import { useEffect, useState } from "react";
import { FileText, GitBranch, Landmark, Mail, Link2, Plus, Upload } from "lucide-react";
import { api, ApiError, type Page } from "../lib/api";
import { useAuth } from "../lib/auth";
import { date, money, enumLabel } from "../lib/format";
import { useT, type Translate } from "../lib/i18n";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Modal,
  PageHeader,
  Pagination,
  Spinner,
  Table,
  statusTone,
} from "../components/ui";
import CreateModal from "../components/CreateModal";
import ImportModal from "../components/ImportModal";
import RowActions from "../components/RowActions";

const claimFields = (t: Translate) => [
  { name: "project_id", label: t("common.project"), type: "project" as const, required: true },
  { name: "claim_number", label: t("field.claimNumber"), required: true },
  {
    name: "claim_type",
    label: t("field.type"),
    type: "select" as const,
    options: ["Cost", "EOT", "Acceleration", "Variation"],
    initial: "Cost",
  },
  {
    name: "status",
    label: t("field.status"),
    type: "select" as const,
    options: ["Submitted", "Under Review", "Approved", "Rejected"],
    initial: "Submitted",
  },
  { name: "amount", label: t("field.amountSar"), type: "number" as const, required: true },
  { name: "narrative", label: t("field.narrative"), type: "textarea" as const, required: true },
];

interface Claim {
  id: number;
  claim_number: string;
  claim_type: string;
  amount: string;
  status: string;
  narrative: string;
}
interface EvidenceItem {
  evidence_note: string;
  change_order: { co_number: string; description: string; value: string; status: string } | null;
  decision: { decision_date: string | null; decision_text: string; owner: string } | null;
  document: { doc_type: string; title: string; doc_date: string | null } | null;
  correspondence: { sent_date: string | null; sender: string; recipient: string; subject: string } | null;
}
interface EvidenceChain {
  claim: Claim;
  evidence_count: number;
  evidence: EvidenceItem[];
}

function EvidenceRow({ item, t }: { item: EvidenceItem; t: Translate }) {
  let icon = <Link2 size={15} />;
  let title = "";
  let body: React.ReactNode = null;

  if (item.change_order) {
    icon = <GitBranch size={15} className="text-blue-600" />;
    title = t("claim.changeOrderTitle", { n: item.change_order.co_number });
    body = (
      <>
        <div>{item.change_order.description}</div>
        <div className="mt-0.5 text-xs text-slate-400">
          {money(item.change_order.value)} · {enumLabel(item.change_order.status, t)}
        </div>
      </>
    );
  } else if (item.decision) {
    icon = <Landmark size={15} className="text-amber-600" />;
    title = t("claim.projectDecision");
    body = (
      <>
        <div>{item.decision.decision_text}</div>
        <div className="mt-0.5 text-xs text-slate-400">
          {date(item.decision.decision_date)} · {item.decision.owner}
        </div>
      </>
    );
  } else if (item.document) {
    icon = <FileText size={15} className="text-slate-600" />;
    title = item.document.title;
    body = (
      <div className="text-xs text-slate-400">
        {item.document.doc_type} · {date(item.document.doc_date)}
      </div>
    );
  } else if (item.correspondence) {
    icon = <Mail size={15} className="text-emerald-600" />;
    title = item.correspondence.subject;
    body = (
      <div className="text-xs text-slate-400">
        {item.correspondence.sender} → {item.correspondence.recipient} · {date(item.correspondence.sent_date)}
      </div>
    );
  }

  return (
    <div className="flex gap-3 rounded-lg border border-slate-200 p-3">
      <div className="mt-0.5">{icon}</div>
      <div className="min-w-0 flex-1">
        <div className="text-xs font-medium uppercase tracking-wide text-slate-400">{item.evidence_note}</div>
        <div className="mt-0.5 text-sm font-medium text-slate-800">{title}</div>
        <div className="text-sm text-slate-600">{body}</div>
      </div>
    </div>
  );
}

export default function Claims() {
  const { user } = useAuth();
  const t = useT();
  const canManage = !!user && ["admin", "project_manager"].includes(user.role);
  const [data, setData] = useState<Page<Claim>>();
  const [error, setError] = useState<string>();
  const [page, setPage] = useState(1);
  const [chain, setChain] = useState<EvidenceChain>();
  const [busy, setBusy] = useState<number>();
  const [showCreate, setShowCreate] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    setError(undefined);
    api.get<Page<Claim>>(`/claims?page=${page}&size=20`).then(setData).catch((e) => setError(e.message));
  }, [page, refresh]);

  async function openEvidence(claim: Claim) {
    setBusy(claim.id);
    try {
      setChain(await api.get<EvidenceChain>(`/claims/${claim.id}/evidence`));
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(undefined);
    }
  }

  return (
    <div>
      <div className="flex items-start justify-between">
        <PageHeader title={t("nav.claims")} subtitle={t("claim.subtitle")} />
        {canManage && (
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setShowImport(true)}>
              <Upload size={16} /> {t("common.import")}
            </Button>
            <Button onClick={() => setShowCreate(true)}>
              <Plus size={16} /> {t("claim.new")}
            </Button>
          </div>
        )}
      </div>

      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
      {!data && !error && <Spinner />}

      {data && (
        <Card>
          <Table head={[t("col.claim"), t("col.type"), t("col.amount"), t("col.status"), t("col.evidence"), ""]}>
            {data.items.map((c) => (
              <tr key={c.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-mono text-xs text-slate-500">{c.claim_number}</td>
                <td className="px-4 py-3 text-slate-700">{enumLabel(c.claim_type, t)}</td>
                <td className="px-4 py-3 font-medium text-slate-800">{money(c.amount)}</td>
                <td className="px-4 py-3">
                  <Badge tone={statusTone(c.status)}>{enumLabel(c.status, t)}</Badge>
                </td>
                <td className="px-4 py-3">
                  <Button variant="secondary" disabled={busy === c.id} onClick={() => openEvidence(c)}>
                    <Link2 size={14} /> {t("claim.viewChain")}
                  </Button>
                </td>
                <td className="px-4 py-3 text-end">
                  <RowActions
                    record={c}
                    entityLabel={t("entity.claim")}
                    endpoint="/claims"
                    fields={claimFields(t)}
                    canManage={canManage}
                    onChanged={() => setRefresh((n) => n + 1)}
                  />
                </td>
              </tr>
            ))}
          </Table>
          {data.items.length === 0 && <EmptyState message={t("claim.noneRecorded")} />}
          <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
        </Card>
      )}

      {chain && (
        <Modal title={t("claim.evidenceChainTitle", { n: chain.claim.claim_number })} onClose={() => setChain(undefined)}>
          <div className="mb-4 rounded-lg bg-slate-50 p-3">
            <div className="flex items-center justify-between">
              <Badge tone={statusTone(chain.claim.status)}>{enumLabel(chain.claim.status, t)}</Badge>
              <span className="font-medium text-slate-800">{money(chain.claim.amount)}</span>
            </div>
            <p className="mt-2 text-sm text-slate-600">{chain.claim.narrative}</p>
          </div>
          <div className="mb-2 text-xs font-medium text-slate-500">
            {t("claim.linkedRecords", { n: chain.evidence_count })}
          </div>
          <div className="space-y-2">
            {chain.evidence.map((item, i) => (
              <EvidenceRow key={i} item={item} t={t} />
            ))}
            {chain.evidence.length === 0 && <EmptyState message={t("claim.noEvidence")} />}
          </div>
        </Modal>
      )}

      {showCreate && (
        <CreateModal
          title={t("claim.new")}
          endpoint="/claims"
          fields={claimFields(t)}
          submitLabel={t("claim.createClaim")}
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            setShowCreate(false);
            setPage(1);
            setRefresh((r) => r + 1);
          }}
        />
      )}

      {showImport && (
        <ImportModal
          title={t("claim.importTitle")}
          importPath="/claims/import"
          templatePath="/claims/import/template"
          templateFilename="claims_template.csv"
          onClose={() => setShowImport(false)}
          onImported={() => {
            setPage(1);
            setRefresh((r) => r + 1);
          }}
        />
      )}
    </div>
  );
}
