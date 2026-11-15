"""Тесты сквозного конвейера."""

from pathlib import Path
from typing import Any

import pytest

from src.core.config import Settings
from src.llm.annotator import PresentationAnnotator
from src.llm.prompts import PromptLibrary
from src.llm.schemas import PresentationAnnotation, SectionAnnotation
from src.parsers.pdf_parser import PDFParser
from src.pipeline import AnnotationPipeline
from src.processors.grouping import SlideGrouper
from src.processors.heading_detector import HeadingDetector
from src.processors.noise_filter import NoiseFilter
from tests.helpers import PROMPTS_DIR, sample_annotation


class _StubClient:
    async def parse_structured(
        self, *, system_prompt: str, user_prompt: str, response_model: Any, temperature: Any = None
    ) -> Any:
        if response_model is SectionAnnotation:
            return SectionAnnotation(
                section_title="Раздел", slide_range="Слайд 1", section_summary="Аннотация."
            )
        return sample_annotation()

    async def aclose(self) -> None:
        return None


def test_pipeline_parses_and_groups(presentation_pdf: Path, settings: Settings) -> None:
    pipeline = AnnotationPipeline.create(settings)

    slides = pipeline.parse(presentation_pdf)

    assert len(slides) == 6
    assert slides[0].is_title_slide is True
    assert slides[2].is_section_divider is True
    assert slides[4].is_continuation is True
    assert slides[5].title_inherited is True
    assert all("Курс ML" not in slide.body_text for slide in slides)

    groups = pipeline.group(slides)
    assert [group.title for group in groups] == [
        "Машинное обучение",
        "Определения",
        "Методы обучения",
    ]
    assert groups[-1].slide_range == "Слайды 3–6"


async def test_pipeline_annotates_and_exports(
    presentation_pdf: Path, settings: Settings, tmp_path: Path
) -> None:
    pipeline = AnnotationPipeline(
        parser=PDFParser(extract_tables=False),
        noise_filter=NoiseFilter(),
        heading_detector=HeadingDetector(),
        grouper=SlideGrouper(),
        annotator=PresentationAnnotator(
            _StubClient(),  # type: ignore[arg-type]
            PromptLibrary(PROMPTS_DIR),
            long_presentation_slides=50,
        ),
    )
    try:
        annotation = await pipeline.annotate(presentation_pdf)
        destination = pipeline.export(annotation, tmp_path / "result.md")
    finally:
        await pipeline.aclose()

    assert isinstance(annotation, PresentationAnnotation)
    assert destination.exists()
    assert destination.read_text(encoding="utf-8").startswith("# Основная тема:")


async def test_pipeline_annotate_slides_uses_given_groups(
    presentation_pdf: Path, settings: Settings
) -> None:
    pipeline = AnnotationPipeline(
        parser=PDFParser(extract_tables=False),
        noise_filter=NoiseFilter(),
        heading_detector=HeadingDetector(),
        grouper=SlideGrouper(),
        annotator=PresentationAnnotator(
            _StubClient(),  # type: ignore[arg-type]
            PromptLibrary(PROMPTS_DIR),
            long_presentation_slides=50,
        ),
    )
    slides = pipeline.parse(presentation_pdf)
    groups = pipeline.group(slides)

    try:
        annotation = await pipeline.annotate_slides(slides, groups)
    finally:
        await pipeline.aclose()

    assert annotation.sections


@pytest.mark.parametrize("suffix", [".md", ".json", ".txt", ".docx"])
def test_export_supports_all_formats(
    annotation: PresentationAnnotation, tmp_path: Path, suffix: str
) -> None:
    pipeline = AnnotationPipeline.create(Settings(extract_tables=False, prompts_dir=PROMPTS_DIR))

    destination = pipeline.export(annotation, tmp_path / f"annotation{suffix}")

    assert destination.exists()
    assert destination.stat().st_size > 0
