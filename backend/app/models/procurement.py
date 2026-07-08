from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.mixins import TimestampMixin


class MaterialCategory(Base):
    __tablename__ = "material_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)


class Supplier(Base, TimestampMixin):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_name: Mapped[str] = mapped_column(String(255), index=True)
    category: Mapped[str] = mapped_column(String(100), index=True)
    city: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), index=True)


class SupplierEvaluation(Base, TimestampMixin):
    __tablename__ = "supplier_evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), index=True)
    evaluation_date: Mapped[date | None] = mapped_column(Date)
    risk_score: Mapped[float] = mapped_column(Numeric(5, 2))
    on_time_rate: Mapped[float | None] = mapped_column(Numeric(5, 2))
    late_po_count: Mapped[int] = mapped_column(Integer, default=0)
    ncr_count: Mapped[int] = mapped_column(Integer, default=0)
    delay_days_total: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[str | None] = mapped_column(Text)
    generated_by: Mapped[str] = mapped_column(String(50), default="agent")


class PurchaseRequest(Base):
    __tablename__ = "purchase_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    request_no: Mapped[str] = mapped_column(String(50), index=True)
    material_category: Mapped[str | None] = mapped_column(String(100), index=True)
    material_category_id: Mapped[int | None] = mapped_column(
        ForeignKey("material_categories.id"), index=True
    )
    specification: Mapped[str | None] = mapped_column(Text)
    required_delivery_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(50), index=True)
    rework_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[date | None] = mapped_column(Date)


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    pr_id: Mapped[int] = mapped_column(ForeignKey("purchase_requests.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True)
    po_number: Mapped[str] = mapped_column(String(50), index=True)
    issue_date: Mapped[date | None] = mapped_column(Date)
    promised_delivery: Mapped[date | None] = mapped_column(Date)
    actual_delivery: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(50), index=True)
    is_late: Mapped[bool] = mapped_column(Boolean, index=True)
    delay_days: Mapped[int] = mapped_column(Integer, default=0)
    delay_root_cause: Mapped[str | None] = mapped_column(Text)
