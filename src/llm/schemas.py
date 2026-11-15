"""Pydantic-схемы итоговой аннотации и ответов LLM."""

from pydantic import BaseModel, ConfigDict, Field

from src.core.models import ParsedSlide

__all__ = ["ParsedSlide", "PresentationAnnotation", "SectionAnnotation"]


class SectionAnnotation(BaseModel):
    """Аннотация одного логического раздела лекции."""

    model_config = ConfigDict(extra="forbid")

    section_title: str = Field(
        ...,
        min_length=1,
        description=(
            "Точное или обобщенное название логического раздела на основе заголовков слайдов"
        ),
    )
    slide_range: str = Field(
        ...,
        min_length=1,
        description="Диапазон номеров слайдов, относящихся к разделу, например: 'Слайды 2–6'",
    )
    section_summary: str = Field(
        ...,
        min_length=1,
        description=(
            "Связная текстовая аннотация раздела (1–3 абзаца). Раскрывает основные тезисы, "
            "определения и выводы строго по тексту слайдов данного блока без маркдаун-заголовков."
        ),
    )


class PresentationAnnotation(BaseModel):
    """Итоговая структура аннотации всей лекционной презентации."""

    model_config = ConfigDict(extra="forbid")

    main_topic: str = Field(
        ...,
        min_length=1,
        description=(
            "Основная тема презентации (1–2 предложения), сформулированная на основе "
            "титульного слайда и сквозного анализа всех заголовков."
        ),
    )
    sections: list[SectionAnnotation] = Field(
        ...,
        min_length=1,
        description=(
            "Упорядоченный список основных тематических разделов лекции с их текстовыми аннотациями"
        ),
    )
