"""Тесты LLM-клиента: Structured Outputs, JSON-фолбэк, ошибки и ретраи."""

from types import SimpleNamespace

import httpx
import pytest
from openai import APITimeoutError, BadRequestError
from pydantic import SecretStr

from src.core.config import LLMConfig
from src.core.exceptions import LLMConfigurationError, LLMGenerationError
from src.llm.client import AsyncLLMClient
from src.llm.schemas import PresentationAnnotation
from tests.helpers import sample_annotation

PROMPTS = {"system_prompt": "system", "user_prompt": "user"}


class _FakeMessage:
    def __init__(self, parsed: object = None, content: str = "") -> None:
        self.parsed = parsed
        self.content = content


class _FakeChoice:
    def __init__(self, message: _FakeMessage, finish_reason: str = "stop") -> None:
        self.message = message
        self.finish_reason = finish_reason


class _FakeCompletion:
    def __init__(self, parsed: object = None, content: str = "", finish_reason: str = "stop"):
        self.choices = [_FakeChoice(_FakeMessage(parsed, content), finish_reason)]


class _FakeParseEndpoint:
    def __init__(self, outcome: object) -> None:
        self._outcome = outcome
        self.calls: list[dict[str, object]] = []

    async def parse(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if isinstance(self._outcome, BaseException):
            raise self._outcome
        return self._outcome


class _FakeCreateEndpoint:
    def __init__(self, completion: _FakeCompletion) -> None:
        self._completion = completion
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs: object) -> _FakeCompletion:
        self.calls.append(kwargs)
        return self._completion


class _FakeOpenAI:
    def __init__(
        self,
        *,
        parse_outcome: object,
        json_content: str = "",
        finish_reason: str = "stop",
    ) -> None:
        self.parse_endpoint = _FakeParseEndpoint(parse_outcome)
        self.create_endpoint = _FakeCreateEndpoint(
            _FakeCompletion(content=json_content, finish_reason=finish_reason)
        )
        self.beta = SimpleNamespace(chat=SimpleNamespace(completions=self.parse_endpoint))
        self.chat = SimpleNamespace(completions=self.create_endpoint)


def _client(
    monkeypatch: pytest.MonkeyPatch,
    fake: _FakeOpenAI,
    *,
    max_retries: int = 1,
) -> AsyncLLMClient:
    client = AsyncLLMClient(
        LLMConfig(api_key=SecretStr("test-key"), max_retries=max_retries, max_concurrency=2)
    )
    monkeypatch.setattr(client, "_client", fake)
    return client


async def test_structured_outputs_are_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = sample_annotation()
    fake = _FakeOpenAI(parse_outcome=_FakeCompletion(parsed=expected))
    client = _client(monkeypatch, fake)

    result = await client.parse_structured(
        system_prompt=PROMPTS["system_prompt"],
        user_prompt=PROMPTS["user_prompt"],
        response_model=PresentationAnnotation,
    )

    assert result == expected
    assert fake.parse_endpoint.calls
    assert fake.parse_endpoint.calls[0]["response_format"] is PresentationAnnotation
    assert fake.parse_endpoint.calls[0]["temperature"] == pytest.approx(0.1)


async def test_parsed_none_falls_back_to_json_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = sample_annotation()
    fake = _FakeOpenAI(
        parse_outcome=_FakeCompletion(parsed=None, content=expected.model_dump_json())
    )
    client = _client(monkeypatch, fake)

    result = await client.parse_structured(
        system_prompt="s", user_prompt="u", response_model=PresentationAnnotation
    )

    assert result.main_topic == expected.main_topic


async def test_unsupported_schema_falls_back_to_json_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = sample_annotation()
    request = httpx.Request("POST", "https://example.com/v1/chat/completions")
    error = BadRequestError(
        "response_format json_schema is not supported by this model",
        response=httpx.Response(400, request=request),
        body=None,
    )
    fake = _FakeOpenAI(
        parse_outcome=error,
        json_content=f"```json\n{expected.model_dump_json()}\n```",
    )
    client = _client(monkeypatch, fake)

    result = await client.parse_structured(
        system_prompt="s", user_prompt="u", response_model=PresentationAnnotation
    )

    assert result.sections == expected.sections
    assert fake.create_endpoint.calls
    assert fake.create_endpoint.calls[0]["response_format"] == {"type": "json_object"}


async def test_invalid_json_raises_generation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeOpenAI(parse_outcome=_FakeCompletion(parsed=None, content="не json"))
    client = _client(monkeypatch, fake)

    with pytest.raises(LLMGenerationError, match="не соответствует схеме"):
        await client.parse_structured(
            system_prompt="s", user_prompt="u", response_model=PresentationAnnotation
        )


async def test_empty_response_raises_generation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeOpenAI(parse_outcome=_FakeCompletion(parsed=None, content=""))
    client = _client(monkeypatch, fake)

    with pytest.raises(LLMGenerationError):
        await client.parse_structured(
            system_prompt="s", user_prompt="u", response_model=PresentationAnnotation
        )


async def test_truncated_response_raises_generation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeOpenAI(
        parse_outcome=_FakeCompletion(parsed=None, content="{}", finish_reason="length")
    )
    client = _client(monkeypatch, fake)

    with pytest.raises(LLMGenerationError, match="обрезан"):
        await client.parse_structured(
            system_prompt="s", user_prompt="u", response_model=PresentationAnnotation
        )


async def test_network_error_is_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request("POST", "https://example.com")
    fake = _FakeOpenAI(parse_outcome=APITimeoutError(request=request))
    client = _client(monkeypatch, fake, max_retries=1)

    with pytest.raises(LLMGenerationError, match="недоступен"):
        await client.parse_structured(
            system_prompt="s", user_prompt="u", response_model=PresentationAnnotation
        )


def test_missing_api_key_raises_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("ANNOTATE_LLM_API_KEY", "DASHSCOPE_API_KEY", "OPENAI_API_KEY", "QWEN_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    client = AsyncLLMClient(LLMConfig(api_key=None))

    with pytest.raises(LLMConfigurationError, match="API-ключ"):
        _ = client.client
