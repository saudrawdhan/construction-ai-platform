"""Calibration tool for the agent skill-matching semantic threshold (_MIN_SEMANTIC_SIMILARITY
in app/services/agent_skills.py). Embeds a reference skill description alongside a set of
known paraphrases (should match) and known-unrelated goals in the same domain (should not),
and prints the cosine similarity for each so the threshold can be picked from real numbers
rather than guessed. Re-run this if the embedding model or provider ever changes.
"""

import asyncio

from app.services.embeddings import get_embedder

REFERENCE_DESCRIPTION = "Assess the risk of supplier"

PARAPHRASES = [
    "Assess the risk of supplier 3",
    "What is the risk level for supplier 12?",
    "How risky is it to keep working with supplier 15?",
    "Check supplier 18 for any red flags before we sign the next order.",
    "How trustworthy has supplier 22 been with deliveries?",
    "Assess the risk of supplier 27",
]

UNRELATED_SAME_DOMAIN = [
    "What's the weather like today?",
    "What's the schedule status for project 5?",
    "Are there any overdue RFIs on this project?",
    "Summarize the latest meeting notes for the team.",
    "Review purchase request 11 for completeness.",
]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    return dot / (norm_a * norm_b)


async def main() -> None:
    embedder = get_embedder()
    (reference_vec,) = await embedder.embed_documents([REFERENCE_DESCRIPTION])

    print(f"Reference skill description: {REFERENCE_DESCRIPTION!r}\n")
    print("Should MATCH (paraphrases of the same intent):")
    match_scores = []
    for goal in PARAPHRASES:
        query_vec = await embedder.embed_query(goal)
        score = _cosine_similarity(reference_vec, query_vec)
        match_scores.append(score)
        print(f"  {score:.4f}  {goal!r}")

    print("\nShould NOT match (unrelated tasks, same construction domain):")
    unrelated_scores = []
    for goal in UNRELATED_SAME_DOMAIN:
        query_vec = await embedder.embed_query(goal)
        score = _cosine_similarity(reference_vec, query_vec)
        unrelated_scores.append(score)
        print(f"  {score:.4f}  {goal!r}")

    print(
        f"\nLowest true-positive score: {min(match_scores):.4f}\n"
        f"Highest true-negative score: {max(unrelated_scores):.4f}\n"
        "A threshold between these two values separates them cleanly."
    )


if __name__ == "__main__":
    asyncio.run(main())
