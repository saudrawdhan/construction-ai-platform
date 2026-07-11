"""Shared plumbing for the bulk-import endpoints.

Every ``POST /{entity}/import`` reads the upload, parses it, guards size, and hands the rows to the
import service with the entity's create-schema. Keeping that flow here means each router only has to
say which schema, create function, and (optionally) row resolver to use.
"""

from typing import Any

from fastapi import HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.imports import ImportReport
from app.services import imports as imports_service


async def handle_tabular_import(
    db: AsyncSession,
    file: UploadFile,
    dry_run: bool,
    *,
    schema: type[BaseModel],
    create: Any,
    resolve: imports_service.RowResolver | None = None,
) -> ImportReport:
    data = await file.read()
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Uploaded file is empty")
    try:
        rows = imports_service.parse_tabular(file.filename or "", data)
    except imports_service.UnsupportedImport as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)) from exc
    except imports_service.ImportParseError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    if len(rows) > imports_service.MAX_IMPORT_ROWS:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Too many rows (limit {imports_service.MAX_IMPORT_ROWS})",
        )
    return await imports_service.import_rows(
        db, rows, schema=schema, create=create, dry_run=dry_run, resolve=resolve
    )
