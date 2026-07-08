"""One-shot live check of the configured LLM provider + API key. Spends a single request.
Prints the model reply, or a clear diagnosis (quota / auth / transient) on failure.
"""

import asyncio

from app.config import get_settings
from app.services.llm import LLMQuotaError, OpenAICompatLLM

settings = get_settings()


async def run() -> None:
    client = OpenAICompatLLM(
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        timeout=settings.llm_request_timeout,
        max_retries=settings.llm_max_retries,
        backoff_base=settings.llm_backoff_base,
        backoff_cap=settings.llm_backoff_cap,
    )
    print(f"provider=gemini model={settings.llm_model} key_prefix={settings.llm_api_key[:6]}...")
    try:
        result = await client.complete(
            system="You are a terse assistant.",
            messages=[{"role": "user", "content": "Reply with exactly: CONSTRUCTION_AI_OK"}],
            max_tokens=20,
        )
        print("LIVE CALL OK ->", result.text.strip())
        print(f"tokens: prompt={result.prompt_tokens} completion={result.completion_tokens}")
    except LLMQuotaError as exc:
        print("QUOTA (429):", exc, "\n-> key works but free daily quota is spent; retry tomorrow.")
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {type(exc).__name__}: {exc}")
        print("-> if 401/403, the key is invalid/expired; regenerate at aistudio.google.com/apikey")
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(run())
