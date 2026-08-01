from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

# Why the change happened. Free text alone would make the portfolio unanalysable, so a small
# fixed vocabulary carries the cause and the description explains the specific instance.
CAUSE_CATEGORIES = (
    "design_change",
    "client_instruction",
    "site_condition",
    "regulatory",
    "error_or_omission",
    "other",
)


class ChangeOrderCreate(BaseModel):
    project_id: int
    co_number: str = Field(min_length=1, max_length=50)
    description: str = Field(min_length=1)
    value: Decimal
    status: str = "Pending"
    cause_rfi_id: int | None = None
    cause_category: str | None = None
    cause_description: str | None = None
    schedule_impact_days: int | None = None


class ChangeOrderUpdate(BaseModel):
    co_number: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = Field(default=None, min_length=1)
    value: Decimal | None = None
    status: str | None = None
    cause_rfi_id: int | None = None
    cause_category: str | None = None
    cause_description: str | None = None
    schedule_impact_days: int | None = None


class ClaimCreate(BaseModel):
    project_id: int
    claim_number: str = Field(min_length=1, max_length=50)
    claim_type: str = Field(min_length=1, max_length=100)
    amount: Decimal
    status: str = "Submitted"
    narrative: str = Field(min_length=1)


class ClaimUpdate(BaseModel):
    claim_number: str | None = Field(default=None, min_length=1, max_length=50)
    claim_type: str | None = Field(default=None, min_length=1, max_length=100)
    amount: Decimal | None = None
    status: str | None = None
    narrative: str | None = Field(default=None, min_length=1)


class ChangeOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    co_number: str
    description: str
    value: Decimal
    status: str
    cause_rfi_id: int | None = None
    cause_category: str | None = None
    cause_description: str | None = None
    schedule_impact_days: int | None = None


class ChangeOrderImpact(BaseModel):
    """What a project's change orders have done to its cost and programme, and what drove them.

    The brief asks a change order to connect to its cause and estimate impact; per change order
    that is a row, but the question a project manager actually asks is the total — so the roll-up
    is computed here rather than left to the reader to add up."""

    project_id: int
    change_order_count: int
    total_value: Decimal
    approved_value: Decimal
    total_schedule_impact_days: int
    by_cause: dict[str, int]
    caused_by_rfi_count: int


class ClaimRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    claim_number: str
    claim_type: str
    amount: Decimal
    status: str
    narrative: str


class DecisionBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    decision_date: date | None
    decision_text: str
    owner: str


class DocumentBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doc_type: str
    title: str
    doc_date: date | None


class CorrespondenceBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sent_date: date | None
    sender: str
    recipient: str
    subject: str


class EvidenceItem(BaseModel):
    evidence_note: str
    change_order: ChangeOrderRead | None
    decision: DecisionBrief | None
    document: DocumentBrief | None
    correspondence: CorrespondenceBrief | None


class ClaimEvidenceChain(BaseModel):
    claim: ClaimRead
    evidence_count: int
    evidence: list[EvidenceItem]
