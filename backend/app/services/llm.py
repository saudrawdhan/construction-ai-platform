"""Provider-agnostic LLM client.

All agent and workflow code depends on the ``LLMClient`` protocol, never on a concrete SDK.
``MockLLM`` is always used under tests (and available as a provider) so the suite and offline
demos spend nothing. ``OpenAICompatLLM`` speaks the OpenAI chat format and therefore serves any
compatible engine: a local open-weights model via Ollama or vLLM, or a hosted API such as Groq,
Gemini, or OpenAI. The real adapter retries transient 5xx responses with exponential backoff and
surfaces 429 rate-limit or quota exhaustion explicitly. The active engine is chosen by
``LLM_PROVIDER``; the endpoint and model come from the provider preset unless set explicitly.
"""

import asyncio
import hashlib
import json
import os
import random
from typing import Protocol, TypedDict

import httpx
from pydantic import BaseModel

from app.config import get_settings

settings = get_settings()

_RETRYABLE_STATUS = {500, 502, 503, 504}


class ChatMessage(TypedDict):
    role: str
    content: str


class LLMResult(BaseModel):
    text: str
    model: str
    provider: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class LLMError(RuntimeError):
    pass


class LLMQuotaError(LLMError):
    pass


class LLMClient(Protocol):
    provider: str

    async def complete(
        self,
        *,
        system: str,
        messages: list[ChatMessage],
        temperature: float = 0.2,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> LLMResult: ...


class MockLLM:
    """Deterministic offline client. Returns valid JSON when ``json_mode`` is set so
    structured-output workflows can be exercised without a network call."""

    provider = "mock"

    def __init__(self, model: str = "mock") -> None:
        self.model = model

    async def complete(
        self,
        *,
        system: str,
        messages: list[ChatMessage],
        temperature: float = 0.2,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> LLMResult:
        last_user = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
        )
        digest = hashlib.sha256((system + last_user).encode("utf-8")).hexdigest()[:8]
        if json_mode:
            text = json.dumps(
                {"mock": True, "trace": digest, "summary": last_user[:280].strip()}
            )
        else:
            text = f"[MOCK:{digest}] Grounded response based on provided context: " + (
                last_user[:280].strip()
            )
        return LLMResult(text=text, model=self.model, provider=self.provider)


class OpenAICompatLLM:
    def __init__(
        self,
        *,
        model: str,
        base_url: str,
        api_key: str,
        timeout: float,
        max_retries: int,
        backoff_base: float,
        backoff_cap: float,
        provider: str = "openai_compat",
    ) -> None:
        self.model = model
        self.provider = provider
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._backoff_cap = backoff_cap
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    async def complete(
        self,
        *,
        system: str,
        messages: list[ChatMessage],
        temperature: float = 0.2,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> LLMResult:
        payload: dict = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        data = await self._post_with_retry("/chat/completions", payload)
        message = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return LLMResult(
            text=message,
            model=self.model,
            provider=self.provider,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
        )

    async def _post_with_retry(self, path: str, payload: dict) -> dict:
        delay = self._backoff_base
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                response = await self._client.post(path, json=payload)
            except httpx.RequestError as exc:
                last_error = LLMError(f"network error: {exc}")
            else:
                if response.status_code == 429:
                    raise LLMQuotaError(
                        f"{self.provider} rate limit or quota exceeded (HTTP 429)"
                    )
                if response.status_code not in _RETRYABLE_STATUS:
                    response.raise_for_status()
                    return response.json()
                last_error = LLMError(f"transient upstream error HTTP {response.status_code}")

            if attempt < self._max_retries:
                await asyncio.sleep(min(delay, self._backoff_cap) + random.uniform(0, 0.5))
                delay *= 2
        raise last_error or LLMError("LLM request failed")

    async def aclose(self) -> None:
        await self._client.aclose()


_real_llm: OpenAICompatLLM | None = None


def get_llm() -> LLMClient:
    """Return the active LLM client. The real client owns a pooled ``httpx.AsyncClient`` and is
    cached as a single long-lived instance per process (httpx clients are made to be reused);
    creating one per request would leak connections. The mock is cheap and stateless."""
    global _real_llm
    if os.environ.get("TESTING") or settings.llm_provider == "mock":
        return MockLLM(model=settings.llm_model or "mock")
    if _real_llm is None:
        base_url, model = settings.resolved_llm_endpoint()
        if not base_url or not model:
            raise LLMError(
                f"LLM provider '{settings.llm_provider}' has no endpoint configured. "
                "Set LLM_PROVIDER to a known provider (local, gemini, groq, openai, mock) "
                "or provide LLM_BASE_URL and LLM_MODEL explicitly."
            )
        _real_llm = OpenAICompatLLM(
            model=model,
            base_url=base_url,
            # Local engines (Ollama) ignore the key but reject an empty bearer token.
            api_key=settings.llm_api_key or "not-required",
            timeout=settings.llm_request_timeout,
            max_retries=settings.llm_max_retries,
            backoff_base=settings.llm_backoff_base,
            backoff_cap=settings.llm_backoff_cap,
            provider=settings.llm_provider,
        )
    return _real_llm


async def close_llm() -> None:
    """Close the shared real client on application shutdown."""
    global _real_llm
    if _real_llm is not None:
        await _real_llm.aclose()
        _real_llm = None
