"""Сквозной конвейер: PDF → очищенные слайды → разделы → аннотация → экспорт."""

from pathlib import Path

from src.core.config import Settings, get_settings
from src.core.logging import get_logger
from src.core.models import ParsedSlide, SectionGroup
from src.exporters import export_annotation
from src.llm.annotator import PresentationAnnotator
from src.llm.client import AsyncLLMClient
from src.llm.prompts import PromptLibrary
from src.llm.schemas import PresentationAnnotation
from src.parsers.pdf_parser import PDFParser
from src.processors.grouping import SlideGrouper
from src.processors.heading_detector import HeadingDetector
from src.processors.noise_filter import NoiseFilter

logger = get_logger(__name__)


class AnnotationPipeline:
    """Связывает парсер, эвристики, LLM-аннотатор и экспортеры."""

    def __init__(
        self,
        *,
        parser: PDFParser,
        noise_filter: NoiseFilter,
        heading_detector: HeadingDetector,
        grouper: SlideGrouper,
        annotator: PresentationAnnotator,
    ) -> None:
        self._parser = parser
        self._noise_filter = noise_filter
        self._heading_detector = heading_detector
        self._grouper = grouper
        self._annotator = annotator

    @classmethod
    def create(cls, settings: Settings | None = None) -> "AnnotationPipeline":
        """Собирает конвейер из настроек приложения."""
        resolved = settings or get_settings()
        parsing = resolved.parsing_config()
        grouping = resolved.grouping_config()

        client = AsyncLLMClient(resolved.llm_config())
        return cls(
            parser=PDFParser(
                min_text_chars=parsing.min_text_layer_chars,
                extract_tables=parsing.extract_tables,
            ),
            noise_filter=NoiseFilter(slide_ratio_threshold=parsing.noise_slide_ratio),
            heading_detector=HeadingDetector(
                heading_font_scale=parsing.heading_font_scale,
                section_divider_font_scale=parsing.section_divider_font_scale,
                title_zone_ratio=parsing.title_zone_ratio,
                max_title_chars=parsing.max_title_chars,
            ),
            grouper=SlideGrouper(untitled_title=grouping.untitled_section_title),
            annotator=PresentationAnnotator(
                client,
                PromptLibrary(resolved.prompts_dir),
                long_presentation_slides=grouping.long_presentation_slides,
            ),
        )

    def parse(self, pdf_path: str | Path) -> list[ParsedSlide]:
        """Извлекает, очищает слайды и определяет заголовки."""
        raw_slides = self._parser.parse(pdf_path)
        cleaned_slides = self._noise_filter.apply(raw_slides)
        parsed = self._heading_detector.detect(cleaned_slides)
        logger.info("Подготовлено слайдов: %d", len(parsed))
        return parsed

    def group(self, slides: list[ParsedSlide]) -> list[SectionGroup]:
        """Группирует слайды в логические разделы."""
        return self._grouper.group(slides)

    async def annotate_slides(
        self,
        slides: list[ParsedSlide],
        groups: list[SectionGroup] | None = None,
    ) -> PresentationAnnotation:
        """Генерирует аннотацию по уже разобранным слайдам."""
        section_groups = groups if groups is not None else self.group(slides)
        return await self._annotator.annotate(slides, section_groups)

    async def annotate(self, pdf_path: str | Path) -> PresentationAnnotation:
        """Полный проход: разбор PDF и генерация аннотации."""
        slides = self.parse(pdf_path)
        return await self.annotate_slides(slides)

    def export(
        self,
        annotation: PresentationAnnotation,
        destination: str | Path,
        format_name: str | None = None,
    ) -> Path:
        """Сохраняет аннотацию в файл."""
        return export_annotation(annotation, destination, format_name)

    async def aclose(self) -> None:
        """Освобождает сетевые ресурсы LLM-клиента."""
        await self._annotator.aclose()
