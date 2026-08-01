from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db

DbSession = Annotated[AsyncSession, Depends(get_db)]


def request_language(accept_language: Annotated[str | None, Header()] = None) -> str:
    """The language the caller wants generated prose written in, as "en" or "ar".

    A workflow analyzes stored records rather than a written question, so it has no question
    language to mirror — the interface language is the only signal available, and the frontend
    sends it on every request. Anything unrecognized falls back to English rather than guessing.
    """
    primary = (accept_language or "en").split(",")[0].strip().lower()
    return "ar" if primary.startswith("ar") else "en"


RequestLanguage = Annotated[str, Depends(request_language)]
