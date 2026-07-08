import math

from app.services.embeddings import HashEmbedder, get_embedder


async def test_hash_embedder_dimension_and_determinism():
    embedder = HashEmbedder(dim=1024)
    a = await embedder.embed_query("late material delivery on PRJ-0014")
    b = await embedder.embed_query("late material delivery on PRJ-0014")
    assert len(a) == 1024
    assert a == b


async def test_hash_embedder_is_normalized():
    embedder = HashEmbedder(dim=1024)
    vector = await embedder.embed_query("supplier risk")
    norm = math.sqrt(sum(v * v for v in vector))
    assert abs(norm - 1.0) < 1e-6


async def test_different_text_differs():
    embedder = HashEmbedder(dim=256)
    a = await embedder.embed_query("concrete pour delayed")
    b = await embedder.embed_query("scaffolding inspection passed")
    assert a != b


async def test_factory_returns_hash_under_testing():
    embedder = get_embedder()
    assert embedder.provider == "hash"
    assert embedder.dim == 1024
