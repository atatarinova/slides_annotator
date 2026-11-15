"""Оркестрация генерации аннотации: один проход или map-reduce для длинных лекций."""

import asyncio

from src.core.exceptions import LLMGenerationError
from src.core.logging import get_logger
from src.core.models import ParsedSlide, SectionGroup
from src.llm.client import AsyncLLMClient
from src.llm.prompts import PromptLibrary, PromptTemplate
from src.llm.schemas import PresentationAnnotation, SectionAnnotation

logger = get_logger(__name__)

ANNOTATE_PROMPT = "annotate_presentation"
SECTION_PROMPT = "summarize_single_section"
SYNTHESIZE_PROMPT = "synthesize_presentation"


class PresentationAnnotator:
    """Формирует итоговую аннотацию по очищенным слайдам презентации."""

    def __init__(
        self,
        client: AsyncLLMClient,
        prompts: PromptLibrary,
        *,
        long_presentation_slides: int = 50,
    ) -> None:
        self._client = client
        self._prompts = prompts
        self._long_presentation_slides = long_presentation_slides

    async def annotate(
        self,
        slides: list[ParsedSlide],
        groups: list[SectionGroup] | None = None,
    ) -> PresentationAnnotation:
        """Генерирует аннотацию презентации по слайдам и (опционально) разделам."""
        if not slides:
            raise LLMGenerationError("Нет слайдов для аннотирования")

        section_groups = groups or []
        if len(slides) >= self._long_presentation_slides and len(section_groups) > 1:
            logger.info(
                "Длинная презентация (%d слайдов, %d разделов): поэтапная суммаризация",
                len(slides),
                len(section_groups),
            )
            return await self._annotate_map_reduce(slides, section_groups)

        logger.info("Аннотирование одним проходом (%d слайдов)", len(slides))
        return await self._annotate_single_pass(slides)

    async def aclose(self) -> None:
        """Освобождает сетевые ресурсы LLM-клиента."""
        await self._client.aclose()

    async def _annotate_single_pass(self, slides: list[ParsedSlide]) -> PresentationAnnotation:
        prompt = self._prompts.get(ANNOTATE_PROMPT)
        user_prompt = prompt.render_user(slides=slides)
        return await self._client.parse_structured(
            system_prompt=prompt.system_prompt,
            user_prompt=user_prompt,
            response_model=PresentationAnnotation,
        )

    async def _annotate_map_reduce(
        self,
        slides: list[ParsedSlide],
        groups: list[SectionGroup],
    ) -> PresentationAnnotation:
        section_prompt = self._prompts.get(SECTION_PROMPT)
        drafts = await asyncio.gather(
            *(self._summarize_group(section_prompt, group) for group in groups)
        )

        synthesize_prompt = self._prompts.get(SYNTHESIZE_PROMPT)
        title_slide = next((slide for slide in slides if slide.is_title_slide), slides[0])
        user_prompt = synthesize_prompt.render_user(
            section_drafts=list(drafts),
            slide_count=len(slides),
            title_slide=title_slide,
        )
        return await self._client.parse_structured(
            system_prompt=synthesize_prompt.system_prompt,
            user_prompt=user_prompt,
            response_model=PresentationAnnotation,
        )

    async def _summarize_group(
        self, prompt: PromptTemplate, group: SectionGroup
    ) -> SectionAnnotation:
        user_prompt = prompt.render_user(
            section_title=group.title,
            slide_range=group.slide_range,
            slides=group.slides,
        )
        return await self._client.parse_structured(
            system_prompt=prompt.system_prompt,
            user_prompt=user_prompt,
            response_model=SectionAnnotation,
        )
