from datetime import date

from pydantic import BaseModel, ConfigDict


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
