"""Разбор PDF-презентации: текстовые блоки, шрифты, координаты и таблицы."""

from collections import defaultdict
from pathlib import Path
from typing import Any

import pymupdf

from src.core.constants import BULLET_ONLY
from src.core.exceptions import EmptyTextLayerError, PDFParsingError
from src.core.logging import get_logger
from src.core.models import BBox, ExtractedTable, RawSlide, TextBlock
from src.parsers.tables import PdfPlumberTableExtractor, TableExtractor
from src.processors.text_utils import clean_text

logger = get_logger(__name__)

_BOLD_FLAG = 1 << 4
_BOLD_FONT_TOKENS: tuple[str, ...] = ("bold", "semibold", "black", "heavy")


class PDFParser:
    """Извлекает сырые слайды из PDF через PyMuPDF и (опционально) pdfplumber."""

    def __init__(
        self,
        *,
        min_text_chars: int = 20,
        extract_tables: bool = True,
        table_extractor: TableExtractor | None = None,
    ) -> None:
        self._min_text_chars = min_text_chars
        self._extract_tables = extract_tables
        self._table_extractor: TableExtractor | None = None
        if extract_tables:
            self._table_extractor = table_extractor or PdfPlumberTableExtractor()

    def parse(self, pdf_path: str | Path) -> list[RawSlide]:
        """Возвращает слайды с текстовыми блоками и таблицами."""
        path = Path(pdf_path).expanduser()
        if not path.is_file():
            raise PDFParsingError(f"PDF-файл не найден: {path}")

        slides = self._parse_pages(path)
        if not slides:
            raise PDFParsingError(f"PDF-документ не содержит страниц: {path}")

        total_chars = sum(slide.text_length for slide in slides)
        if total_chars < self._min_text_chars:
            raise EmptyTextLayerError(
                f"В PDF отсутствует извлекаемый текстовый слой ({total_chars} символов): {path}. "
                "Документ, вероятно, является сканом и требует OCR, который не поддерживается."
            )

        if self._table_extractor is not None:
            tables = self._table_extractor.extract(path)
            if tables:
                slides = [
                    self._attach_tables(slide, tables.get(slide.slide_number, []))
                    for slide in slides
                ]
        return slides

    def _parse_pages(self, path: Path) -> list[RawSlide]:
        try:
            document = pymupdf.open(path)  # type: ignore[no-untyped-call]
        except (pymupdf.FileDataError, pymupdf.FileNotFoundError, RuntimeError, ValueError) as exc:
            raise PDFParsingError(f"Не удалось открыть PDF-файл {path}: {exc}") from exc

        with document:
            if document.needs_pass:
                raise PDFParsingError(f"PDF-файл защищен паролем: {path}")
            slides: list[RawSlide] = []
            try:
                for page_index in range(document.page_count):
                    page: pymupdf.Page = document.load_page(  # type: ignore[no-untyped-call]
                        page_index
                    )
                    slides.append(_parse_page(page, page_index + 1))
            except (RuntimeError, ValueError) as exc:
                raise PDFParsingError(f"Ошибка чтения страниц PDF {path}: {exc}") from exc
        logger.info("Разобрано слайдов: %d (%s)", len(slides), path.name)
        return slides

    @staticmethod
    def _attach_tables(slide: RawSlide, tables: list[ExtractedTable]) -> RawSlide:
        if not tables:
            return slide
        kept_blocks = [
            block
            for block in slide.blocks
            if not any(
                table.bbox is not None
                and table.bbox.contains_point(block.bbox.center_x, block.bbox.center_y)
                for table in tables
            )
        ]
        return slide.model_copy(update={"blocks": kept_blocks, "tables": [*slide.tables, *tables]})


def _parse_page(page: pymupdf.Page, slide_number: int) -> RawSlide:
    return RawSlide(
        slide_number=slide_number,
        width=float(page.rect.width),
        height=float(page.rect.height),
        blocks=_extract_blocks(page),
    )


def _extract_blocks(page: pymupdf.Page) -> list[TextBlock]:
    page_data: dict[str, Any] = page.get_text("dict")  # type: ignore[no-untyped-call]
    blocks: list[TextBlock] = []
    for raw_block in page_data.get("blocks", []):
        if raw_block.get("type", 0) != 0:
            continue
        block = _build_block(raw_block)
        if block is not None:
            blocks.append(block)
    return blocks


def _build_block(raw_block: dict[str, Any]) -> TextBlock | None:
    text_lines: list[str] = []
    size_weights: dict[float, int] = defaultdict(int)
    bold_chars = 0
    total_chars = 0
    x0 = y0 = float("inf")
    x1 = y1 = float("-inf")

    for raw_line in raw_block.get("lines", []):
        line_parts: list[str] = []
        for span in raw_line.get("spans", []):
            span_text = str(span.get("text", ""))
            if not span_text:
                continue
            line_parts.append(span_text)
            chars = len(span_text.strip()) or len(span_text)
            total_chars += chars
            size = round(float(span.get("size", 0.0)), 1)
            if size > 0:
                size_weights[size] += chars
            if _span_is_bold(span):
                bold_chars += chars
            span_bbox = span.get("bbox")
            if span_bbox is not None:
                sx0, sy0, sx1, sy1 = (float(value) for value in span_bbox)
                x0, y0 = min(x0, sx0), min(y0, sy0)
                x1, y1 = max(x1, sx1), max(y1, sy1)
        line_text = "".join(line_parts).strip()
        if line_text:
            text_lines.append(line_text)

    text = clean_text("\n".join(text_lines))
    if not text or BULLET_ONLY.match(text):
        return None
    if not size_weights or x0 == float("inf"):
        return None

    dominant_size = max(size_weights.items(), key=lambda item: item[1])[0]
    is_bold = total_chars > 0 and bold_chars / total_chars >= 0.5
    return TextBlock(
        text=text,
        bbox=BBox(x0=x0, y0=y0, x1=x1, y1=y1),
        font_size=dominant_size,
        is_bold=is_bold,
        line_count=len(text_lines),
    )


def _span_is_bold(span: dict[str, Any]) -> bool:
    font_name = str(span.get("font", "")).lower()
    if any(token in font_name for token in _BOLD_FONT_TOKENS):
        return True
    return bool(int(span.get("flags", 0)) & _BOLD_FLAG)
