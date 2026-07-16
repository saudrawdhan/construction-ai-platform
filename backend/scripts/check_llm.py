"""One-shot live check of the configured LLM provider. Spends a single request against whichever
engine LLM_PROVIDER selects (local, gemini, groq, ...). Prints the model reply, or a clear
diagnosis (quota / auth / transient) on failure.
"""

import asyncio

from app.config import get_settings
from app.services.llm import LLMError, LLMQuotaError, OpenAICompatLLM

settings = get_settings()


async def run() -> None:
    base_url, model = settings.resolved_llm_endpoint()
    if not base_url or not model:
        print(f"No endpoint configured for provider '{settings.llm_provider}'.")
        return
    client = OpenAICompatLLM(
        model=model,
        base_url=base_url,
        api_key=settings.llm_api_key or "not-required",
        timeout=settings.llm_request_timeout,
        max_retries=settings.llm_max_retries,
        backoff_base=settings.llm_backoff_base,
        backoff_cap=settings.llm_backoff_cap,
        provider=settings.llm_provider,
    )
    key_hint = f"{settings.llm_api_key[:6]}..." if settings.llm_api_key else "(none)"
    print(f"provider={settings.llm_provider} model={model} base_url={base_url} key={key_hint}")
    try:
        result = await client.complete(
            system="You are a terse assistant.",
            messages=[{"role": "user", "content": "Reply with exactly: CONSTRUCTION_AI_OK"}],
            max_tokens=20,
        )
        print("LIVE CALL OK ->", result.text.strip())
        print(f"tokens: prompt={result.prompt_tokens} completion={result.completion_tokens}")
    except LLMQuotaError as exc:
        print("QUOTA (429):", exc, "\n-> the key works but the provider's quota is spent.")
    except LLMError as exc:
        print(f"FAILED: {exc}")
        print("-> for a local provider, confirm Ollama is running and reachable on port 11434.")
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {type(exc).__name__}: {exc}")
        print("-> for a cloud provider, a 401/403 means the key is invalid or expired.")
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(run())
