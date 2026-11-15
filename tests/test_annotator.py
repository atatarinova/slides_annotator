"""Тесты оркестратора аннотирования (один проход и map-reduce)."""

from typing import Any

import pytest

from src.core.exceptions import LLMGenerationError
from src.core.models import ParsedSlide, SectionGroup
from src.llm.annotator import PresentationAnnotator
from src.llm.prompts import PromptLibrary
from src.llm.schemas import PresentationAnnotation, SectionAnnotation
from tests.helpers import PROMPTS_DIR, parsed_slide, sample_annotation


class _StubClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def parse_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[PresentationAnnotation] | type[SectionAnnotation],
        temperature: float | None = None,
    ) -> PresentationAnnotation | SectionAnnotation:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "response_model": response_model,
            }
        )
        if response_model is SectionAnnotation:
            return SectionAnnotation(
                section_title="Черновик раздела",
                slide_range="Слайды 1–2",
                section_summary="Краткая аннотация раздела.",
            )
        return sample_annotation()

    async def aclose(self) -> None:
        return None


def _annotator(client: _StubClient) -> PresentationAnnotator:
    return PresentationAnnotator(
        client,  # type: ignore[arg-type]
        PromptLibrary(PROMPTS_DIR),
        long_presentation_slides=50,
    )


async def test_short_presentation_uses_single_pass() -> None:
    client = _StubClient()
    annotator = _annotator(client)
    slides = [parsed_slide(index, f"Тема {index}") for index in range(1, 4)]

    result = await annotator.annotate(slides)

    assert isinstance(result, PresentationAnnotation)
    assert len(client.calls) == 1
    assert client.calls[0]["response_model"] is PresentationAnnotation
    assert "Слайд №1" in str(client.calls[0]["user_prompt"])


async def test_long_presentation_uses_map_reduce() -> None:
    client = _StubClient()
    annotator = _annotator(client)
    slides = [parsed_slide(index, f"Тема {index}") for index in range(1, 51)]
    groups = [
        SectionGroup(section_index=1, title="Первый", slides=slides[:20]),
        SectionGroup(section_index=2, title="Второй", slides=slides[20:40]),
        SectionGroup(section_index=3, title="Третий", slides=slides[40:]),
    ]

    result = await annotator.annotate(slides, groups)

    assert isinstance(result, PresentationAnnotation)
    assert len(client.calls) == 4
    assert [call["response_model"] for call in client.calls].count(SectionAnnotation) == 3
    assert client.calls[-1]["response_model"] is PresentationAnnotation
    assert "Черновик раздела" in str(client.calls[-1]["user_prompt"])


async def test_empty_slides_raise_generation_error() -> None:
    annotator = _annotator(_StubClient())

    with pytest.raises(LLMGenerationError, match="Нет слайдов"):
        await annotator.annotate([])


async def test_aclose_delegates_to_client() -> None:
    closed = False

    class _ClosingClient(_StubClient):
        async def aclose(self) -> None:
            nonlocal closed
            closed = True

    annotator = _annotator(_ClosingClient())
    await annotator.aclose()

    assert closed is True


def test_slide_group_slide_range() -> None:
    group = SectionGroup(section_index=1, title="Раздел", slides=[parsed_slide(4, "Раздел")])

    assert group.slide_range == "Слайд 4"
    assert group.first_slide_number == 4
    assert group.last_slide_number == 4


def test_parsed_slide_display_title() -> None:
    slide = ParsedSlide(
        slide_number=2,
        title="Тема",
        title_inherited=True,
        is_continuation=True,
        body_text="",
    )

    assert "Без заголовка / продолжение" in slide.display_title
    assert "продолжение" in slide.display_title
