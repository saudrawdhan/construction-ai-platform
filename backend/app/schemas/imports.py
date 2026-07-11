from pydantic import BaseModel


class ImportRowError(BaseModel):
    row: int
    errors: list[str]


class ImportReport(BaseModel):
    total_rows: int
    valid_rows: int
    invalid_rows: int
    created: int
    dry_run: bool
    errors: list[ImportRowError]
