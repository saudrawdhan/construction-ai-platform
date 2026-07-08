"""ETL importer: canonical SQL dump (SQLite dialect) -> operational PostgreSQL schema.

Loads the dataset into an in-memory SQLite database, transforms each record into the
PostgreSQL model shape (typed dates, booleans, normalized clients and material
categories), and bulk-inserts in foreign-key-safe order. Original primary keys are
preserved so every existing relationship stays intact; identity sequences are then
advanced past the imported ids. Finishes with a source-vs-target row-count report.
"""

import asyncio
import os
import sqlite3
import sys
from datetime import datetime

from sqlalchemy import func, insert, select, text

from app import models  # noqa: F401  registers every model on Base.registry
from app.database.base import Base
from app.database.session import AsyncSessionLocal, engine

SQL_DUMP = os.environ.get("DATASET_DUMP", "/data/construction_ai_dataset_full_dump.sql")

# Truncated (and reloaded) by this importer, in an order that CASCADE can resolve.
DATASET_TABLES = [
    "clients",
    "material_categories",
    "projects",
    "suppliers",
    "subcontractors",
    "purchase_requests",
    "purchase_orders",
    "meetings",
    "project_decisions",
    "site_reports",
    "daily_activities",
    "change_orders",
    "ncrs",
    "safety_events",
    "subcontractor_evaluations",
    "documents",
    "correspondence",
    "claims",
    "claim_evidence",
    "generated_documents",
]


def _load_source() -> sqlite3.Connection:
    with open(SQL_DUMP, encoding="utf-8") as handle:
        script = handle.read()
    con = sqlite3.connect(":memory:")
    con.executescript(script)
    con.row_factory = sqlite3.Row
    return con


def _read(con: sqlite3.Connection, table: str) -> list[dict]:
    return [dict(row) for row in con.execute(f"SELECT * FROM {table}")]


def _as_date(value):
    if value in (None, ""):
        return None
    text_value = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text_value, fmt).date()
        except ValueError:
            continue
    return None


def build_rows(con: sqlite3.Connection) -> dict[str, list[dict]]:
    projects = _read(con, "projects")
    client_names = sorted({p["client_name"] for p in projects})
    client_id = {name: index for index, name in enumerate(client_names, start=1)}

    purchase_requests = _read(con, "purchase_requests")
    category_names = sorted(
        {p["material_category"] for p in purchase_requests if p["material_category"]}
    )
    category_id = {name: index for index, name in enumerate(category_names, start=1)}

    out: dict[str, list[dict]] = {}

    out["clients"] = [{"id": cid, "name": name} for name, cid in client_id.items()]
    out["material_categories"] = [
        {"id": cid, "name": name} for name, cid in category_id.items()
    ]

    out["projects"] = [
        {
            "id": p["id"],
            "project_code": p["project_code"],
            "project_name": p["project_name"],
            "project_type": p["project_type"],
            "client_id": client_id[p["client_name"]],
            "client_name": p["client_name"],
            "city": p["city"],
            "start_date": _as_date(p["start_date"]),
            "planned_finish": _as_date(p["planned_finish"]),
            "actual_finish": _as_date(p["actual_finish"]),
            "status": p["status"],
            "budget": p["budget"],
        }
        for p in projects
    ]

    out["suppliers"] = [
        {
            "id": s["id"],
            "supplier_name": s["supplier_name"],
            "category": s["category"],
            "city": s["city"],
            "status": s["status"],
        }
        for s in _read(con, "suppliers")
    ]

    out["subcontractors"] = [
        {
            "id": s["id"],
            "name": s["name"],
            "trade": s["trade"],
            "contact_person": s["contact_person"],
            "phone": s["phone"],
            "email": s["email"],
            "classification": s["classification"],
            "city": s["city"],
            "status": s["status"],
            "created_at": _as_date(s["created_at"]),
        }
        for s in _read(con, "subcontractors")
    ]

    out["purchase_requests"] = [
        {
            "id": p["id"],
            "project_id": p["project_id"],
            "request_no": p["request_no"],
            "material_category": p["material_category"],
            "material_category_id": category_id.get(p["material_category"]),
            "specification": p["specification"],
            "required_delivery_date": _as_date(p["required_delivery_date"]),
            "status": p["status"],
            "rework_reason": p["rework_reason"],
            "created_at": _as_date(p["created_at"]),
        }
        for p in purchase_requests
    ]

    out["purchase_orders"] = [
        {
            "id": o["id"],
            "pr_id": o["pr_id"],
            "project_id": o["project_id"],
            "supplier_id": o["supplier_id"],
            "po_number": o["po_number"],
            "issue_date": _as_date(o["issue_date"]),
            "promised_delivery": _as_date(o["promised_delivery"]),
            "actual_delivery": _as_date(o["actual_delivery"]),
            "status": o["status"],
            "is_late": bool(o["is_late"]),
            "delay_days": o["delay_days"],
            "delay_root_cause": o["delay_root_cause"],
        }
        for o in _read(con, "purchase_orders")
    ]

    out["meetings"] = [
        {
            "id": m["id"],
            "project_id": m["project_id"],
            "meeting_date": _as_date(m["meeting_date"]),
            "title": m["title"],
            "meeting_type": m["meeting_type"],
        }
        for m in _read(con, "meetings")
    ]

    out["project_decisions"] = [
        {
            "id": d["id"],
            "project_id": d["project_id"],
            "meeting_id": d["meeting_id"],
            "decision_date": _as_date(d["decision_date"]),
            "decision_text": d["decision_text"],
            "owner": d["owner"],
        }
        for d in _read(con, "project_decisions")
    ]

    out["site_reports"] = [
        {
            "id": r["id"],
            "project_id": r["project_id"],
            "report_date": _as_date(r["report_date"]),
            "weather": r["weather"],
            "summary": r["summary"],
        }
        for r in _read(con, "site_reports")
    ]

    out["daily_activities"] = [
        {
            "id": a["id"],
            "project_id": a["project_id"],
            "subcontractor_id": a["subcontractor_id"],
            "site_report_id": a["site_report_id"],
            "activity_date": _as_date(a["activity_date"]),
            "activity_description": a["activity_description"],
            "manpower_count": a["manpower_count"],
        }
        for a in _read(con, "daily_activities")
    ]

    out["change_orders"] = [
        {
            "id": c["id"],
            "project_id": c["project_id"],
            "co_number": c["co_number"],
            "description": c["description"],
            "value": c["value"],
            "status": c["status"],
        }
        for c in _read(con, "change_orders")
    ]

    out["ncrs"] = [
        {
            "id": n["id"],
            "project_id": n["project_id"],
            "supplier_id": n["supplier_id"],
            "subcontractor_id": n["subcontractor_id"],
            "ncr_type": n["ncr_type"],
            "description": n["description"],
            "root_cause": n["root_cause"],
            "issue_date": _as_date(n["issue_date"]),
            "status": n["status"],
        }
        for n in _read(con, "ncrs")
    ]

    out["safety_events"] = [
        {
            "id": e["id"],
            "project_id": e["project_id"],
            "subcontractor_id": e["subcontractor_id"],
            "event_date": _as_date(e["event_date"]),
            "severity": e["severity"],
            "description": e["description"],
            "corrective_action": e["corrective_action"],
        }
        for e in _read(con, "safety_events")
    ]

    out["subcontractor_evaluations"] = [
        {
            "id": e["id"],
            "subcontractor_id": e["subcontractor_id"],
            "project_id": e["project_id"],
            "evaluation_date": _as_date(e["evaluation_date"]),
            "quality_score": e["quality_score"],
            "safety_score": e["safety_score"],
            "schedule_score": e["schedule_score"],
            "manpower_score": e["manpower_score"],
            "overall_rating": e["overall_rating"],
            "comments": e["comments"],
            "linked_safety_event_id": e["linked_safety_event_id"],
            "linked_ncr_id": e["linked_ncr_id"],
            "linked_daily_activity_id": e["linked_daily_activity_id"],
        }
        for e in _read(con, "subcontractor_evaluations")
    ]

    out["documents"] = [
        {
            "id": d["id"],
            "project_id": d["project_id"],
            "doc_type": d["doc_type"],
            "title": d["title"],
            "doc_date": _as_date(d["doc_date"]),
            "content_summary": d["content_summary"],
        }
        for d in _read(con, "documents")
    ]

    out["correspondence"] = [
        {
            "id": c["id"],
            "project_id": c["project_id"],
            "related_record_type": c["related_record_type"],
            "related_record_id": c["related_record_id"],
            "sent_date": _as_date(c["sent_date"]),
            "sender": c["sender"],
            "recipient": c["recipient"],
            "subject": c["subject"],
            "body": c["body"],
        }
        for c in _read(con, "correspondence")
    ]

    out["claims"] = [
        {
            "id": c["id"],
            "project_id": c["project_id"],
            "claim_number": c["claim_number"],
            "claim_type": c["claim_type"],
            "amount": c["amount"],
            "status": c["status"],
            "narrative": c["narrative"],
        }
        for c in _read(con, "claims")
    ]

    out["claim_evidence"] = [
        {
            "id": e["id"],
            "claim_id": e["claim_id"],
            "change_order_id": e["change_order_id"],
            "decision_id": e["decision_id"],
            "document_id": e["document_id"],
            "correspondence_id": e["correspondence_id"],
            "evidence_note": e["evidence_note"],
        }
        for e in _read(con, "claim_evidence")
    ]

    out["generated_documents"] = [
        {
            "id": g["id"],
            "file_name": g["file_name"],
            "type": g["type"],
            "project_id": g["project_id"],
            "related_record_id": g["related_record_id"],
            "document_date": _as_date(g["document_date"]),
            "sender": g["sender"],
            "recipient": g["recipient"],
            "subject": g["subject"],
            "body": g["body"],
        }
        for g in _read(con, "generated_documents")
    ]

    return out


_MODEL_BY_TABLE = {mapper.class_.__tablename__: mapper.class_ for mapper in Base.registry.mappers}

# TRUNCATE ... CASCADE below also clears any platform-layer rows that reference the dataset
# tables. Refuse to run if that would destroy real AI/governance data, unless forced.
_GUARD_TABLES = ["ai_memories", "ai_audit_logs", "ai_recommendations", "approval_requests"]


async def _abort_if_platform_data(session) -> None:
    if os.environ.get("FORCE_REIMPORT"):
        return
    existing = 0
    for table in _GUARD_TABLES:
        existing += await session.scalar(text(f"SELECT count(*) FROM {table}")) or 0
    if existing:
        print(
            f"Refusing to re-import: platform tables hold {existing} row(s) that a CASCADE "
            "truncate would delete. Set FORCE_REIMPORT=1 to override.",
            file=sys.stderr,
        )
        sys.exit(1)


async def run() -> None:
    source = _load_source()
    rows = build_rows(source)

    async with AsyncSessionLocal() as session:
        await _abort_if_platform_data(session)
        await session.execute(
            text(f"TRUNCATE {', '.join(DATASET_TABLES)} RESTART IDENTITY CASCADE")
        )
        for table in DATASET_TABLES:
            payload = rows[table]
            if payload:
                await session.execute(insert(_MODEL_BY_TABLE[table]), payload)
        for table in DATASET_TABLES:
            await session.execute(
                text(
                    "SELECT setval(pg_get_serial_sequence(:t, 'id'), "
                    "GREATEST((SELECT COALESCE(MAX(id), 1) FROM " + table + "), 1))"
                ),
                {"t": table},
            )
        await session.commit()

        print(f"{'table':<28}{'source':>10}{'target':>10}   status")
        print("-" * 60)
        all_ok = True
        for table in DATASET_TABLES:
            expected = len(rows[table])
            actual = await session.scalar(
                select(func.count()).select_from(_MODEL_BY_TABLE[table])
            )
            ok = expected == actual
            all_ok = all_ok and ok
            print(f"{table:<28}{expected:>10}{actual:>10}   {'OK' if ok else 'MISMATCH'}")
        print("-" * 60)
        print("RESULT:", "ALL TABLES MATCH" if all_ok else "MISMATCH DETECTED")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
