import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.api.v1 import api_router
from app.config import get_settings
from app.database.redis import create_redis
from app.database.session import engine
from app.services.llm import close_llm

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = create_redis()
    yield
    await app.state.redis.aclose()
    await close_llm()
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    for header, value in _SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    return response


app.include_router(api_router)


_FOREIGN_KEY_VIOLATION = "23503"
# Postgres names the offending column in the error's detail line. The same SQLSTATE covers two
# opposite situations, distinguished only by that wording:
#   writing a bad parent id -> "Key (project_id)=(999999) is not present in table ..."
#   deleting a parent still in use -> "Key (id)=(7)  is still referenced from table ..."
_FK_COLUMN = re.compile(r"Key \((?P<column>[^)]+)\)=")
_STILL_REFERENCED = "is still referenced"


def _integrity_detail(exc: IntegrityError) -> str:
    orig = getattr(exc, "orig", None)
    return getattr(orig, "detail", None) or str(orig) or ""


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    # A missing parent, a still-referenced parent and a duplicate key are all IntegrityError, but
    # they are three different client mistakes. Answering all of them with one 409 left a caller
    # unable to tell "project 999999 does not exist" from "that RFI number is already taken" —
    # both arrived as the same opaque sentence. Naming the case (and the column the database
    # rejected) costs nothing and makes the API self-explaining.
    detail = _integrity_detail(exc)
    if getattr(getattr(exc, "orig", None), "sqlstate", None) == _FOREIGN_KEY_VIOLATION:
        if _STILL_REFERENCED in detail:
            # The record exists and is in use — a genuine conflict with existing state, so 409
            # stays correct here; only the wording was unhelpful.
            return JSONResponse(
                status_code=409,
                content={
                    "detail": "This record is still referenced by other records "
                    "and cannot be deleted"
                },
            )
        match = _FK_COLUMN.search(detail)
        target = f" '{match.group('column')}'" if match else ""
        return JSONResponse(
            status_code=422,
            content={"detail": f"Referenced record{target} does not exist"},
        )
    return JSONResponse(
        status_code=409,
        content={"detail": "Request conflicts with an existing record or constraint"},
    )


@app.exception_handler(DBAPIError)
async def dbapi_error_handler(request: Request, exc: DBAPIError) -> JSONResponse:
    # A value the database itself cannot store — too long for a column, out of numeric range,
    # or an invalid byte sequence — arrives as SQLSTATE class 22 ("data exception"). That is a
    # client mistake, not a server fault, so answer with 422 instead of a raw 500. Anything else
    # (a genuine operational/server error) is re-raised to surface and be logged as a 500.
    sqlstate = getattr(exc.orig, "sqlstate", None)
    if isinstance(sqlstate, str) and sqlstate.startswith("22"):
        return JSONResponse(
            status_code=422,
            content={
                "detail": "A submitted value is invalid for storage "
                "(too long, out of range, or malformed)."
            },
        )
    raise exc


@app.get("/health", tags=["system"])
async def health() -> JSONResponse:
    database_ok = await _check_database()
    redis_ok = await _check_redis(app)
    healthy = database_ok and redis_ok
    payload = {
        "status": "ok" if healthy else "degraded",
        "environment": settings.environment,
        "services": {"database": database_ok, "redis": redis_ok},
    }
    return JSONResponse(payload, status_code=200 if healthy else 503)


async def _check_database() -> bool:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def _check_redis(app: FastAPI) -> bool:
    try:
        return bool(await app.state.redis.ping())
    except Exception:
        return False
