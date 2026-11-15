"""Тесты эвристик определения заголовков и разделителей секций."""

from src.processors.heading_detector import HeadingDetector
from tests.helpers import raw_slide, text_block


def test_detects_title_and_title_slide() -> None:
    slides = [
        raw_slide(
            1,
            [
                text_block("Лекция о нейронных сетях", y0=80, y1=115, x1=430, size=28, bold=True),
                text_block("Подзаголовок", y0=130, y1=145, size=14),
            ],
        ),
        raw_slide(2, [text_block("Основной текст " * 5, y0=170, y1=190)]),
    ]

    parsed = HeadingDetector().detect(slides)

    assert parsed[0].title == "Лекция о нейронных сетях"
    assert parsed[0].is_title_slide is True
    assert "Подзаголовок" in parsed[0].body_text
    assert parsed[1].title == "Лекция о нейронных сетях"
    assert parsed[1].title_inherited is True


def test_detects_section_divider() -> None:
    slides = [
        raw_slide(1, [text_block("Основной текст " * 4, y0=170, y1=190)]),
        raw_slide(
            2,
            [text_block("Методы обучения", x0=150, y0=400, x1=445, y1=440, size=32, bold=True)],
        ),
    ]

    parsed = HeadingDetector().detect(slides)

    assert parsed[1].is_section_divider is True
    assert parsed[1].title == "Методы обучения"


def test_continuation_and_inherited_titles() -> None:
    slides = [
        raw_slide(
            1,
            [
                text_block("Тема", y0=80, y1=110, size=24, bold=True),
                text_block("Основной текст " * 4, y0=170, y1=190),
            ],
        ),
        raw_slide(
            2,
            [
                text_block("Тема (продолжение)", y0=80, y1=110, size=24, bold=True),
                text_block("Еще текст", y0=170, y1=190),
            ],
        ),
        raw_slide(3, [text_block("Просто текст без заголовка", y0=170, y1=190)]),
    ]

    parsed = HeadingDetector().detect(slides)

    assert parsed[1].is_continuation is True
    assert parsed[2].title == "Тема (продолжение)"
    assert parsed[2].title_inherited is True
    assert "Просто текст без заголовка" in parsed[2].body_text


def test_untitled_slide_without_previous_title_stays_untitled() -> None:
    slides = [raw_slide(1, [text_block("Длинный основной текст без заголовка " * 2)])]

    parsed = HeadingDetector().detect(slides)

    assert parsed[0].title is None
    assert parsed[0].title_inherited is False
    assert parsed[0].is_title_slide is False


def test_top_zone_has_priority_over_larger_block_below() -> None:
    slides = [
        raw_slide(
            1,
            [
                text_block("Крупный заголовок вверху", y0=80, y1=120, size=24, bold=True),
                text_block("Основной текст " * 5, y0=200, y1=220),
                text_block("Еще крупнее внизу", y0=600, y1=650, x1=400, size=30, bold=True),
            ],
        )
    ]

    parsed = HeadingDetector().detect(slides)

    assert parsed[0].title == "Крупный заголовок вверху"


def test_bold_block_at_body_size_is_used_as_title() -> None:
    slides = [
        raw_slide(
            1,
            [
                text_block("Ключевой тезис", y0=80, y1=100, size=12, bold=True),
                text_block("Длинный основной текст " * 4, y0=140, y1=160),
            ],
        )
    ]

    parsed = HeadingDetector().detect(slides)

    assert parsed[0].title == "Ключевой тезис"


def test_tables_are_appended_to_body_text() -> None:
    from src.core.models import ExtractedTable

    table = ExtractedTable(rows=[["Метод", "Тип"], ["Классификация", "С учителем"]])
    slides = [
        raw_slide(
            1,
            [
                text_block("Тема", y0=80, y1=110, size=24, bold=True),
                text_block("Текст " * 10, y0=170, y1=190),
            ],
            tables=[table],
        )
    ]

    parsed = HeadingDetector().detect(slides)

    assert "| Метод | Тип |" in parsed[0].body_text
