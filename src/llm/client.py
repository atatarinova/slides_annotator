"""Асинхронный клиент OpenAI-совместимого API со Structured Outputs и ретраями."""

import asyncio
import re
from typing import Any, TypeVar

from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    OpenAIError,
    RateLimitError,
)
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel, ValidationError
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.core.config import LLMConfig
from src.core.exceptions import LLMConfigurationError, LLMGenerationError
from src.core.logging import get_logger

logger = get_logger(__name__)

ModelT = TypeVar("ModelT", bound=BaseModel)

_RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
    InternalServerError,
)

_CODE_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)


class AsyncLLMClient:
    """Обертка над AsyncOpenAI: Structured Outputs, JSON-фолбэк, ретраи и лимит конкурентности."""

    def __init__(self, config: LLMConfig) -> None:
        self._config = config
        self._client: AsyncOpenAI | None = None
        self._semaphore = asyncio.Semaphore(config.max_concurrency)
        self._structured_outputs_supported: bool | None = None

    @property
    def config(self) -> LLMConfig:
        return self._config

    @property
    def client(self) -> AsyncOpenAI:
        """Лениво создает клиента, чтобы импорт модуля не требовал API-ключа."""
        if self._client is None:
            api_key = self._config.resolved_api_key()
            if not api_key:
                raise LLMConfigurationError(
                    "Не задан API-ключ LLM. Укажите ANNOTATE_LLM_API_KEY "
                    "(или DASHSCOPE_API_KEY / OPENAI_API_KEY / QWEN_API_KEY)."
                )
            self._client = AsyncOpenAI(
                api_key=api_key,
                base_url=self._config.base_url,
                timeout=self._config.timeout_seconds,
                max_retries=0,
            )
        return self._client

    async def aclose(self) -> None:
        """Закрывает HTTP-клиент, если он был создан."""
        if self._client is not None:
            await self._client.close()
            self._client = None

    async def __aenter__(self) -> "AsyncLLMClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def parse_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[ModelT],
        temperature: float | None = None,
    ) -> ModelT:
        """Запрашивает у LLM ответ, валидируемый Pydantic-моделью ``response_model``."""
        retrying = AsyncRetrying(
            stop=stop_after_attempt(max(1, self._config.max_retries)),
            wait=wait_exponential(multiplier=1.5, min=1.0, max=30.0),
            retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
            reraise=True,
        )

        async with self._semaphore:
            try:
                async for attempt in retrying:
                    with attempt:
                        return await self._request_completion(
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                            response_model=response_model,
                            temperature=temperature,
                        )
            except _RETRYABLE_EXCEPTIONS as exc:
                raise LLMGenerationError(
                    f"LLM API недоступен после {self._config.max_retries} попыток: {exc}"
                ) from exc
            except (AuthenticationError, BadRequestError) as exc:
                raise LLMGenerationError(f"LLM API отклонил запрос: {exc}") from exc
            except OpenAIError as exc:
                raise LLMGenerationError(f"Ошибка LLM API: {exc}") from exc

        raise LLMGenerationError(  # pragma: no cover - защита от недостижимого состояния
            "Не удалось получить ответ от LLM"
        )

    async def _request_completion(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[ModelT],
        temperature: float | None,
    ) -> ModelT:
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        resolved_temperature = self._config.temperature if temperature is None else temperature

        if self._structured_outputs_supported is not False:
            try:
                parsed_completion = await self.client.beta.chat.completions.parse(
                    model=self._config.model,
                    messages=messages,
                    response_format=response_model,
                    temperature=resolved_temperature,
                )
                return self._extract_parsed(parsed_completion, response_model)
            except BadRequestError as exc:
                if not _is_structured_output_unsupported(exc):
                    raise
                self._structured_outputs_supported = False
                logger.warning(
                    "Провайдер не поддерживает JSON Schema в response_format; "
                    "переключаюсь на JSON-режим: %s",
                    exc,
                )

        json_completion = await self.client.chat.completions.create(
            model=self._config.model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=resolved_temperature,
        )
        if not json_completion.choices:
            raise LLMGenerationError("LLM вернула пустой список вариантов ответа")
        choice = json_completion.choices[0]
        if choice.finish_reason == "length":
            raise LLMGenerationError("Ответ LLM обрезан по лимиту токенов")
        return _validate_json_response(choice.message.content or "", response_model)

    @staticmethod
    def _extract_parsed(completion: Any, response_model: type[ModelT]) -> ModelT:
        if not completion.choices:
            raise LLMGenerationError("LLM вернула пустой список вариантов ответа")
        choice = completion.choices[0]
        if choice.finish_reason == "length":
            raise LLMGenerationError("Ответ LLM обрезан по лимиту токенов")

        parsed = choice.message.parsed
        if parsed is None:
            return _validate_json_response(choice.message.content or "", response_model)
        if isinstance(parsed, response_model):
            return parsed
        return response_model.model_validate(parsed)


def _is_structured_output_unsupported(exc: BadRequestError) -> bool:
    message = str(exc).lower()
    return any(
        token in message
        for token in ("response_format", "json_schema", "json schema", "structured output")
    )


def _strip_code_fences(content: str) -> str:
    text = content.strip()
    match = _CODE_FENCE.match(text)
    return match.group(1).strip() if match else text


def _validate_json_response(content: str, response_model: type[ModelT]) -> ModelT:
    payload = _strip_code_fences(content)
    if not payload:
        raise LLMGenerationError("LLM вернула пустой ответ")
    try:
        return response_model.model_validate_json(payload)
    except ValidationError as exc:
        raise LLMGenerationError(
            f"Ответ LLM не соответствует схеме {response_model.__name__}: {exc}"
        ) from exc
