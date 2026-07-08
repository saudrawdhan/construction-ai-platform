import json

from app.services.llm import MockLLM, get_llm


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
