from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class SupplierCreate(BaseModel):
    supplier_name: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=100)
    city: str = Field(min_length=1, max_length=100)
    status: str = "Active"


class SupplierUpdate(BaseModel):
    supplier_name: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    city: str | None = Field(default=None, min_length=1, max_length=100)
    status: str | None = None


class SupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    supplier_name: str
    category: str
    city: str
    status: str


class DelayCause(BaseModel):
    cause: str
    count: int


class SupplierPerformance(BaseModel):
    supplier_id: int
    supplier_name: str
    total_purchase_orders: int
    late_purchase_orders: int
    on_time_rate: float
    total_delay_days: int
    average_delay_days_when_late: float
    ncr_count: int
    top_delay_causes: list[DelayCause]


class PurchaseRequestCreate(BaseModel):
    project_id: int
    request_no: str = Field(min_length=1, max_length=50)
    material_category: str | None = None
    specification: str | None = None
    required_delivery_date: date | None = None
    status: str = "Under Review"


class PurchaseRequestUpdate(BaseModel):
    request_no: str | None = Field(default=None, min_length=1, max_length=50)
    material_category: str | None = None
    specification: str | None = None
    required_delivery_date: date | None = None
    status: str | None = None


class PurchaseOrderCreate(BaseModel):
    pr_id: int
    project_id: int
    supplier_id: int
    po_number: str = Field(min_length=1, max_length=50)
    issue_date: date | None = None
    promised_delivery: date | None = None
    actual_delivery: date | None = None
    status: str = "Issued"
    delay_root_cause: str | None = None


class PurchaseOrderUpdate(BaseModel):
    po_number: str | None = Field(default=None, min_length=1, max_length=50)
    issue_date: date | None = None
    promised_delivery: date | None = None
    actual_delivery: date | None = None
    status: str | None = None
    delay_root_cause: str | None = None


class PurchaseRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    request_no: str
    material_category: str | None
    material_category_id: int | None
    specification: str | None
    required_delivery_date: date | None
    status: str
    rework_reason: str | None
    created_at: date | None


class PurchaseOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pr_id: int
    project_id: int
    supplier_id: int
    po_number: str
    issue_date: date | None
    promised_delivery: date | None
    actual_delivery: date | None
    status: str
    is_late: bool
    delay_days: int
    delay_root_cause: str | None
