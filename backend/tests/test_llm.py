import json

from app.config import Settings
from app.services.llm import MockLLM, OpenAICompatLLM, get_llm


async def test_mock_llm_is_deterministic():
    llm = MockLLM()
    messages = [{"role": "user", "content": "Summarize the meeting"}]
    first = await llm.complete(system="sys", messages=messages)
    second = await llm.complete(system="sys", messages=messages)
    assert first.text == second.text
    assert first.provider == "mock"


async def test_mock_llm_json_mode_returns_valid_json():
    llm = MockLLM()
    result = await llm.complete(
        system="sys",
        messages=[{"role": "user", "content": "Return structured data"}],
        json_mode=True,
    )
    payload = json.loads(result.text)
    assert payload["mock"] is True


async def test_factory_returns_mock_under_testing():
    # conftest / test runner sets TESTING=1
    llm = get_llm()
    assert llm.provider == "mock"


def test_provider_preset_resolves_endpoint():
    for provider, (base_url, model) in (
        ("local", ("http://host.docker.internal:11434/v1/", "qwen2.5:7b-instruct")),
        ("groq", ("https://api.groq.com/openai/v1/", "llama-3.3-70b-versatile")),
    ):
        settings = Settings(llm_provider=provider, llm_base_url="", llm_model="")
        assert settings.resolved_llm_endpoint() == (base_url, model)


def test_explicit_endpoint_overrides_preset():
    settings = Settings(
        llm_provider="local", llm_base_url="http://gpu-box:9000/v1/", llm_model="custom-14b"
    )
    assert settings.resolved_llm_endpoint() == ("http://gpu-box:9000/v1/", "custom-14b")


def test_openai_compat_reports_configured_provider():
    client = OpenAICompatLLM(
        model="qwen2.5:7b-instruct", base_url="http://host.docker.internal:11434/v1/",
        api_key="x", timeout=1.0, max_retries=1, backoff_base=1.0, backoff_cap=1.0,
        provider="local",
    )
    assert client.provider == "local"
