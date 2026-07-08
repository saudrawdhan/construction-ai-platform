"""Quality spot-check for hybrid retrieval using the real embedder. Reports, per query, how
many top hits contain Arabic script — computed in Python so it is not affected by terminal
encoding. Run against a populated document_embeddings table.
"""

import asyncio

from app.database.session import AsyncSessionLocal, engine
from app.services.embeddings import get_embedder
from app.services.retrieval import hybrid_search

QUERIES = {
    "EN semantic  ": "late material delivery affecting the site schedule",
    "EN safety     ": "unsafe work at height and scaffolding",
    "AR semantic  ": "تأخر توريد "
    "المواد في الموقع",
    "exact token  ": "CO-00023",
}


def _arabic_chars(text: str) -> int:
    return sum(1 for char in text if "؀" <= char <= "ۿ")


async def run() -> None:
    embedder = get_embedder()
    print(f"embedder provider={embedder.provider} dim={embedder.dim}")
    async with AsyncSessionLocal() as db:
        for label, query in QUERIES.items():
            hits = await hybrid_search(db, embedder, query=query, k=3)
            arabic_hits = sum(1 for hit in hits if _arabic_chars(hit.content) > 0)
            top = hits[0] if hits else None
            top_desc = (
                f"{top.source_type}#{top.source_id} arabic_chars={_arabic_chars(top.content)}"
                if top
                else "none"
            )
            print(f"[{label}] hits={len(hits)} arabic_hits={arabic_hits} top={top_desc}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
