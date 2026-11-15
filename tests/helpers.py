"""Общие хелперы для тестов: генерация PDF и моделей."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from src.core.models import BBox, ExtractedTable, ParsedSlide, RawSlide, TextBlock
from src.llm.schemas import PresentationAnnotation, SectionAnnotation

PAGE_WIDTH = 595.0
PAGE_HEIGHT = 842.0
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = PROJECT_ROOT / "prompts"
FONT_REGULAR = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
FONT_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")


@dataclass(frozen=True)
class SlideSpec:
    """Описание слайда для генерации тестового PDF."""

    title: str | None = None
    body: tuple[str, ...] = ()
    title_size: float = 24.0
    body_size: float = 12.0
    centered: bool = False
    title_bold: bool = True
    body_top: float = 170.0
    footer: str | None = "Курс ML"
    page_number: bool = True


PRESENTATION_SLIDES: tuple[SlideSpec, ...] = (
    SlideSpec(
        title="Машинное обучение",
        body=("Лекция 1. Введение",),
        title_size=28.0,
        body_size=14.0,
        body_top=150.0,
    ),
    SlideSpec(
        title="Определения",
        body=(
            "Машинное обучение — класс методов искусственного интеллекта.",
            "Модель обучается на данных и обобщает закономерности.",
        ),
    ),
    SlideSpec(title="Методы обучения", title_size=32.0, centered=True),
    SlideSpec(
        title="Обучение с учителем",
        body=("Используются размеченные данные.", "Примеры: классификация и регрессия."),
    ),
    SlideSpec(
        title="Обучение с учителем (продолжение)",
        body=("Метрики качества: accuracy, F1.",),
    ),
    SlideSpec(
        body=("Обучение без учителя ищет структуру в данных.",),
        body_top=150.0,
    ),
)


def create_presentation(path: Path, slides: Sequence[SlideSpec]) -> Path:
    """Создает PDF-презентацию с заголовками, текстом, колонтитулом и номерами."""
    path.parent.mkdir(parents=True, exist_ok=True)
    document = pymupdf.open()
    for index, spec in enumerate(slides, start=1):
        page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        page.insert_font(fontname="R", fontfile=str(FONT_REGULAR))
        page.insert_font(fontname="B", fontfile=str(FONT_BOLD))
        font_name = "B" if spec.title_bold else "R"

        if spec.title and spec.centered:
            page.insert_textbox(
                pymupdf.Rect(60, 330, PAGE_WIDTH - 60, 470),
                spec.title,
                fontsize=spec.title_size,
                fontname=font_name,
                align=pymupdf.TEXT_ALIGN_CENTER,
            )
            y = 500.0
        elif spec.title:
            page.insert_text((72, 90), spec.title, fontsize=spec.title_size, fontname=font_name)
            y = spec.body_top
        else:
            y = spec.body_top

        for line in spec.body:
            page.insert_text((72, y), line, fontsize=spec.body_size, fontname="R")
            y += spec.body_size * 1.8

        if spec.footer:
            page.insert_text((72, PAGE_HEIGHT - 30), spec.footer, fontsize=9, fontname="R")
        if spec.page_number:
            page.insert_text(
                (PAGE_WIDTH - 60, PAGE_HEIGHT - 30), str(index), fontsize=9, fontname="R"
            )

    document.save(str(path))
    document.close()
    return path


def create_blank_pdf(path: Path, pages: int = 2) -> Path:
    """Создает PDF без текстового слоя (имитация скана)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    document = pymupdf.open()
    for _ in range(pages):
        page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        page.draw_rect(pymupdf.Rect(100, 100, 300, 300), color=(0, 0, 0), fill=(0.8, 0.8, 0.8))
    document.save(str(path))
    document.close()
    return path


def text_block(
    text: str,
    *,
    x0: float = 72.0,
    y0: float = 100.0,
    x1: float = 500.0,
    y1: float = 130.0,
    size: float = 12.0,
    bold: bool = False,
) -> TextBlock:
    """Создает текстовый блок с заданной геометрией."""
    return TextBlock(
        text=text,
        bbox=BBox(x0=x0, y0=y0, x1=x1, y1=y1),
        font_size=size,
        is_bold=bold,
        line_count=max(1, text.count("\n") + 1),
    )


def raw_slide(
    number: int,
    blocks: Sequence[TextBlock],
    *,
    tables: Sequence[ExtractedTable] = (),
) -> RawSlide:
    """Создает сырой слайд из готовых блоков."""
    return RawSlide(
        slide_number=number,
        width=PAGE_WIDTH,
        height=PAGE_HEIGHT,
        blocks=list(blocks),
        tables=list(tables),
    )


def parsed_slide(
    number: int,
    title: str | None,
    *,
    body: str = "Текст слайда.",
    is_title_slide: bool = False,
    is_section_divider: bool = False,
    is_continuation: bool = False,
    title_inherited: bool = False,
) -> ParsedSlide:
    """Создает очищенный слайд для тестов процессоров и LLM."""
    return ParsedSlide(
        slide_number=number,
        title=title,
        title_inherited=title_inherited,
        is_title_slide=is_title_slide,
        is_section_divider=is_section_divider,
        is_continuation=is_continuation,
        body_text=body,
    )


def sample_annotation() -> PresentationAnnotation:
    """Эталонная аннотация для тестов экспортеров и API."""
    return PresentationAnnotation(
        main_topic="Введение в машинное обучение и основные методы обучения моделей.",
        sections=[
            SectionAnnotation(
                section_title="Определения",
                slide_range="Слайды 2–2",
                section_summary="Машинное обучение рассматривается как класс методов ИИ.",
            ),
            SectionAnnotation(
                section_title="Методы обучения",
                slide_range="Слайды 3–6",
                section_summary="Разбираются обучение с учителем и без учителя.",
            ),
        ],
    )
