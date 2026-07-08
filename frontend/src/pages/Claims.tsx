import { useEffect, useState } from "react";
import { FileText, GitBranch, Landmark, Mail, Link2 } from "lucide-react";
import { api, ApiError, type Page } from "../lib/api";
import { date, money } from "../lib/format";
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

function EvidenceRow({ item }: { item: EvidenceItem }) {
  let icon = <Link2 size={15} />;
  let title = "";
  let body: React.ReactNode = null;

  if (item.change_order) {
    icon = <GitBranch size={15} className="text-blue-600" />;
    title = `Change Order ${item.change_order.co_number}`;
    body = (
      <>
        <div>{item.change_order.description}</div>
        <div className="mt-0.5 text-xs text-slate-400">
          {money(item.change_order.value)} · {item.change_order.status}
        </div>
      </>
    );
  } else if (item.decision) {
    icon = <Landmark size={15} className="text-amber-600" />;
    title = "Project Decision";
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
  const [data, setData] = useState<Page<Claim>>();
  const [error, setError] = useState<string>();
  const [page, setPage] = useState(1);
  const [chain, setChain] = useState<EvidenceChain>();
  const [busy, setBusy] = useState<number>();

  useEffect(() => {
    setError(undefined);
    api.get<Page<Claim>>(`/claims?page=${page}&size=20`).then(setData).catch((e) => setError(e.message));
  }, [page]);

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
      <PageHeader title="Claims" subtitle="Commercial claims and their supporting evidence chain" />

      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
      {!data && !error && <Spinner />}

      {data && (
        <Card>
          <Table head={["Claim", "Type", "Amount", "Status", "Evidence"]}>
            {data.items.map((c) => (
              <tr key={c.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-mono text-xs text-slate-500">{c.claim_number}</td>
                <td className="px-4 py-3 text-slate-700">{c.claim_type}</td>
                <td className="px-4 py-3 font-medium text-slate-800">{money(c.amount)}</td>
                <td className="px-4 py-3">
                  <Badge tone={statusTone(c.status)}>{c.status}</Badge>
                </td>
                <td className="px-4 py-3">
                  <Button variant="secondary" disabled={busy === c.id} onClick={() => openEvidence(c)}>
                    <Link2 size={14} /> View Chain
                  </Button>
                </td>
              </tr>
            ))}
          </Table>
          {data.items.length === 0 && <EmptyState message="No claims recorded." />}
          <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
        </Card>
      )}

      {chain && (
        <Modal title={`Evidence Chain · ${chain.claim.claim_number}`} onClose={() => setChain(undefined)}>
          <div className="mb-4 rounded-lg bg-slate-50 p-3">
            <div className="flex items-center justify-between">
              <Badge tone={statusTone(chain.claim.status)}>{chain.claim.status}</Badge>
              <span className="font-medium text-slate-800">{money(chain.claim.amount)}</span>
            </div>
            <p className="mt-2 text-sm text-slate-600">{chain.claim.narrative}</p>
          </div>
          <div className="mb-2 text-xs font-medium text-slate-500">
            {chain.evidence_count} linked evidence record(s)
          </div>
          <div className="space-y-2">
            {chain.evidence.map((item, i) => (
              <EvidenceRow key={i} item={item} />
            ))}
            {chain.evidence.length === 0 && <EmptyState message="No linked evidence found." />}
          </div>
        </Modal>
      )}
    </div>
  );
}
