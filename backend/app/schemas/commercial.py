from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ChangeOrderCreate(BaseModel):
    project_id: int
    co_number: str = Field(min_length=1, max_length=50)
    description: str = Field(min_length=1)
    value: Decimal
    status: str = "Pending"


class ChangeOrderUpdate(BaseModel):
    co_number: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = Field(default=None, min_length=1)
    value: Decimal | None = None
    status: str | None = None


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
