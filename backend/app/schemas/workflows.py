from datetime import date

from pydantic import BaseModel


class SourceRef(BaseModel):
    type: str
    id: int


class PRAnalyzeRequest(BaseModel):
    pr_id: int


class PurchaseRequestReview(BaseModel):
    pr_id: int
    request_no: str
    material_category: str | None
    missing_information: list[str]
    risk_level: str
    recommendation: str
    required_approvals: list[str]
    supplier_history_note: str | None
    sources: list[SourceRef]
    memory_used: list[int]
    provider: str
    model: str


class SupplierRiskAssessment(BaseModel):
    supplier_id: int
    supplier_name: str
    risk_score: float
    risk_level: str
    on_time_rate: float
    late_purchase_orders: int
    ncr_count: int
    total_delay_days: int
    drivers: list[str]
    recommendation: str
    evaluation_id: int | None
    memory_used: list[int]
    provider: str
    model: str


class RfiEscalationItem(BaseModel):
    rfi_number: str
    subject: str
    discipline: str
    days_overdue: int
    assigned_to: str
    priority: str
    suggested_action: str


class RfiEscalation(BaseModel):
    project_id: int
    overdue_count: int
    items: list[RfiEscalationItem]
    escalation_message: str
    memory_used: list[int]
    provider: str
    model: str


class MeetingSummarizeRequest(BaseModel):
    notes: str
    title: str = "Project Meeting"
    meeting_date: date | None = None
    meeting_type: str = "General"
    store: bool = False


class ActionItem(BaseModel):
    description: str
    owner: str | None = None
    due_date: date | None = None


class DecisionItem(BaseModel):
    text: str
    owner: str | None = None


class MeetingSummary(BaseModel):
    project_id: int
    summary: str
    action_items: list[ActionItem]
    decisions: list[DecisionItem]
    risks: list[str]
    meeting_id: int | None
    stored_action_items: int
    stored_decisions: int
    memory_used: list[int]
    provider: str
    model: str


class SiteReportAnalyzeRequest(BaseModel):
    text: str
    report_date: date | None = None
    store: bool = False


class SiteReportAnalysis(BaseModel):
    project_id: int
    summary: str
    completed_work: list[str]
    delays: list[str]
    risks: list[str]
    manpower_note: str | None
    recommended_escalation: str
    memory_used: list[int]
    provider: str
    model: str


class ExecutiveReportRequest(BaseModel):
    project_id: int | None = None
    store: bool = True


class ExecutiveReport(BaseModel):
    scope: str
    projects_total: int
    delayed_or_onhold: int
    overdue_rfis: int
    late_purchase_orders: int
    open_ncrs: int
    recent_safety_events: int
    pending_purchase_requests: int
    highlights: list[str]
    narrative: str
    summary_id: int | None
    provider: str
    model: str
