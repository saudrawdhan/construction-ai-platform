"""One real call to the configured LLM provider to validate the Memory Extraction Agent's live
path: confirms the model returns JSON the parser accepts. Spends a single request.
"""

import asyncio

from app.agents.memory_extractor import MemoryExtractor
from app.services.llm import LLMQuotaError, get_llm

SAMPLE = (
    "Meeting minutes: The client representative instructed the contractor to accelerate "
    "the facade works. Procurement reported a late delivery of long-lead switchgear that "
    "puts the MEP milestone at risk. QA/QC raised an NCR for nonconforming concrete on "
    "zone B. Decision: expedite the switchgear and submit a recovery schedule. "
    "ملاحظة: لوحظ عمل غير آمن على السقالة بدون حزام أمان."
)


async def run() -> None:
    extractor = MemoryExtractor(get_llm())
    print(f"provider={extractor.provider} model={extractor.model}")
    try:
        result = await extractor.extract(text=SAMPLE)
    except LLMQuotaError as exc:
        print("QUOTA (429):", exc, "-> mock path still works; retry live tomorrow.")
        return
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {type(exc).__name__}: {exc}")
        return

    print(f"extracted {len(result.memories)} memories "
          f"(tokens prompt={result.prompt_tokens} completion={result.completion_tokens}):")
    for memory in result.memories:
        summary = memory.summary[:110]
        print(f"  - [{memory.category.value}] conf={memory.confidence_score} :: {summary}")


if __name__ == "__main__":
    asyncio.run(run())
