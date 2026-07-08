import pytest_asyncio

from app.models import DocumentEmbedding
from app.services.embeddings import get_embedder
from app.services.retrieval import hybrid_search

SEED = [
    ("generated_document", 101, 38,
     "Change order CO-00023 approved for additional MEP coordination works"),
    ("correspondence", 102, 38,
     "Claim Notice regarding repeated delay events and additional cost entitlement"),
    ("generated_document", 103, 14,
     "تمت متابعة الأعمال اليومية في الموقع مع وجود بعض الملاحظات المتعلقة بتأخر التوريد"),
    ("document", 104, 12,
     "Delay analysis report covering scaffolding and concrete works progress"),
]


@pytest_asyncio.fixture
async def seeded_embeddings(db_session):
    embedder = get_embedder()
    vectors = await embedder.embed_documents([row[3] for row in SEED])
    for (source_type, source_id, project_id, content), vector in zip(SEED, vectors, strict=True):
        db_session.add(
            DocumentEmbedding(
                source_type=source_type,
                source_id=source_id,
                project_id=project_id,
                chunk_index=0,
                content=content,
                token_count=10,
                embedding=vector,
            )
        )
    await db_session.flush()


async def test_fulltext_finds_exact_change_order_number(db_session, seeded_embeddings):
    hits = await hybrid_search(db_session, get_embedder(), query="CO-00023", k=5)
    assert any("CO-00023" in hit.content for hit in hits)


async def test_fulltext_matches_arabic_token(db_session, seeded_embeddings):
    hits = await hybrid_search(db_session, get_embedder(), query="متابعة", k=5)
    assert any("متابعة" in hit.content for hit in hits)


async def test_hybrid_respects_k_and_scores_descending(db_session, seeded_embeddings):
    hits = await hybrid_search(db_session, get_embedder(), query="delay", k=2)
    assert len(hits) <= 2
    scores = [hit.score for hit in hits]
    assert scores == sorted(scores, reverse=True)


async def test_project_filter(db_session, seeded_embeddings):
    hits = await hybrid_search(
        db_session, get_embedder(), query="works", k=10, project_id=38
    )
    assert hits
    assert all(hit.project_id == 38 for hit in hits)


async def test_search_endpoint(client, admin_headers, seeded_embeddings):
    response = await client.get("/api/v1/documents/search?q=CO-00023", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "CO-00023"
    assert any("CO-00023" in r["content"] for r in body["results"])
