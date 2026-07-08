"""Whitespace-normalized, overlap-aware text chunking for embedding. Most construction
records (emails, minutes, notices) are short and yield a single chunk; longer bodies are
split on word boundaries with overlap so context isn't cut mid-sentence."""


def chunk_text(text: str, *, size: int = 1000, overlap: int = 150) -> list[str]:
    normalized = " ".join(text.split())
    if not normalized:
        return []
    if len(normalized) <= size:
        return [normalized]

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = start + size
        window = normalized[start:end]
        if end < len(normalized):
            last_space = window.rfind(" ")
            if last_space > size * 0.6:
                end = start + last_space
                window = normalized[start:end]
        cleaned = window.strip()
        if cleaned:
            chunks.append(cleaned)
        start = max(end - overlap, start + 1)
    return chunks
