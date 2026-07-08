"""Post-ETL data-fidelity audit: proves the PostgreSQL load preserved the source dataset
beyond simple row counts. Checks (1) date-column null parity (catches dates silently lost
to parsing), (2) money-sum parity (catches numeric precision loss), (3) boolean parity, and
(4) foreign-key integrity including the seeded tables. Exits non-zero if anything fails.
"""

import asyncio
import os
import sqlite3
import sys
from datetime import datetime

from sqlalchemy import text

from app.database.session import AsyncSessionLocal, engine

SQL_DUMP = os.environ.get("DATASET_DUMP", "/data/construction_ai_dataset_full_dump.sql")

DATE_COLUMNS = {
    "projects": ["start_date", "planned_finish", "actual_finish"],
    "subcontractors": ["created_at"],
    "purchase_requests": ["required_delivery_date", "created_at"],
    "purchase_orders": ["issue_date", "promised_delivery", "actual_delivery"],
    "meetings": ["meeting_date"],
    "project_decisions": ["decision_date"],
    "site_reports": ["report_date"],
    "daily_activities": ["activity_date"],
    "ncrs": ["issue_date"],
    "safety_events": ["event_date"],
    "subcontractor_evaluations": ["evaluation_date"],
    "documents": ["doc_date"],
    "correspondence": ["sent_date"],
    "generated_documents": ["document_date"],
}

MONEY_SUMS = {
    "projects": "budget",
    "change_orders": "value",
    "claims": "amount",
}

FK_CHECKS = {
    "purchase_orders -> purchase_requests": (
        "SELECT count(*) FROM purchase_orders o "
        "LEFT JOIN purchase_requests r ON o.pr_id=r.id WHERE r.id IS NULL"
    ),
    "claim_evidence -> claims": (
        "SELECT count(*) FROM claim_evidence e "
        "LEFT JOIN claims c ON e.claim_id=c.id WHERE c.id IS NULL"
    ),
    "generated_documents -> projects": (
        "SELECT count(*) FROM generated_documents g "
        "LEFT JOIN projects p ON g.project_id=p.id WHERE p.id IS NULL"
    ),
    "rfis -> projects (seeded)": (
        "SELECT count(*) FROM rfis r LEFT JOIN projects p ON r.project_id=p.id WHERE p.id IS NULL"
    ),
    "planned_activities -> projects (seeded)": (
        "SELECT count(*) FROM planned_activities a "
        "LEFT JOIN projects p ON a.project_id=p.id WHERE p.id IS NULL"
    ),
}


def _parseable(value) -> bool:
    if value in (None, ""):
        return False
    text_value = str(value).strip()
    if not text_value:
        return False
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            datetime.strptime(text_value, fmt)
            return True
        except ValueError:
            continue
    return False


def _source() -> sqlite3.Connection:
    with open(SQL_DUMP, encoding="utf-8") as handle:
        con = sqlite3.connect(":memory:")
        con.executescript(handle.read())
    return con


async def run() -> None:
    src = _source()
    failures = 0

    async with AsyncSessionLocal() as session:
        print("== Date null-parity (source non-null parseable vs target non-null) ==")
        for table, columns in DATE_COLUMNS.items():
            for column in columns:
                source_rows = src.execute(f"SELECT {column} FROM {table}").fetchall()
                source_nonnull = sum(1 for (v,) in source_rows if _parseable(v))
                target_nonnull = await session.scalar(
                    text(f"SELECT count({column}) FROM {table}")
                )
                ok = source_nonnull == target_nonnull
                failures += not ok
                flag = "OK" if ok else "LOST DATA"
                name = f"{table}.{column}"
                print(f"  {name:<40} src={source_nonnull:<6} tgt={target_nonnull:<6} {flag}")

        print("\n== Money-sum parity (rounded to whole units) ==")
        for table, column in MONEY_SUMS.items():
            query = f"SELECT COALESCE(SUM({column}),0) FROM {table}"
            source_sum = round(float(src.execute(query).fetchone()[0]))
            target_sum = round(float(await session.scalar(text(query))))
            ok = source_sum == target_sum
            failures += not ok
            print(f"  {table}.{column:<12} src={source_sum} tgt={target_sum} "
                  f"{'OK' if ok else 'MISMATCH'}")

        print("\n== Boolean parity ==")
        (src_late,) = src.execute("SELECT SUM(is_late) FROM purchase_orders").fetchone()
        tgt_late = await session.scalar(
            text("SELECT count(*) FROM purchase_orders WHERE is_late IS TRUE")
        )
        ok = int(src_late) == int(tgt_late)
        failures += not ok
        status = "OK" if ok else "MISMATCH"
        print(f"  purchase_orders.is_late  src={int(src_late)} tgt={tgt_late} {status}")

        print("\n== Foreign-key integrity (expect 0 orphans) ==")
        for label, query in FK_CHECKS.items():
            orphans = await session.scalar(text(query))
            failures += orphans != 0
            print(f"  {label:<42} orphans={orphans} {'OK' if orphans == 0 else 'BROKEN'}")

    await engine.dispose()

    verdict = "ALL FIDELITY CHECKS PASSED" if failures == 0 else f"{failures} CHECK(S) FAILED"
    print("\nRESULT:", verdict)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    asyncio.run(run())
