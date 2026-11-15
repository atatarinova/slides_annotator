"""Тесты группировки слайдов в логические разделы."""

from src.processors.grouping import SlideGrouper
from tests.helpers import parsed_slide


def test_groups_by_title_changes() -> None:
    slides = [
        parsed_slide(1, "Введение"),
        parsed_slide(2, "Введение", is_continuation=True),
        parsed_slide(3, "Методы"),
    ]

    groups = SlideGrouper().group(slides)

    assert [group.title for group in groups] == ["Введение", "Методы"]
    assert [slide.slide_number for slide in groups[0].slides] == [1, 2]
    assert groups[0].slide_range == "Слайды 1–2"
    assert groups[1].slide_range == "Слайд 3"


def test_divider_starts_section_and_absorbs_following_titles() -> None:
    slides = [
        parsed_slide(1, "Лекция", is_title_slide=True),
        parsed_slide(2, "Определения"),
        parsed_slide(3, "Методы обучения", is_section_divider=True),
        parsed_slide(4, "Обучение с учителем"),
        parsed_slide(5, "Обучение с учителем", is_continuation=True),
        parsed_slide(6, "Обучение с учителем", title_inherited=True),
    ]

    groups = SlideGrouper().group(slides)

    assert [group.title for group in groups] == ["Лекция", "Определения", "Методы обучения"]
    assert [slide.slide_number for slide in groups[2].slides] == [3, 4, 5, 6]
    assert groups[2].slide_range == "Слайды 3–6"


def test_untitled_slides_get_fallback_section_title() -> None:
    slides = [parsed_slide(1, None), parsed_slide(2, None, title_inherited=False)]

    groups = SlideGrouper().group(slides)

    assert len(groups) == 1
    assert groups[0].title == "Введение"


def test_title_slide_does_not_start_new_section_after_first() -> None:
    slides = [
        parsed_slide(1, "Лекция"),
        parsed_slide(2, "Продолжение лекции", is_title_slide=True),
    ]

    groups = SlideGrouper().group(slides)

    assert len(groups) == 1
    assert [slide.slide_number for slide in groups[0].slides] == [1, 2]


def test_empty_input_returns_no_sections() -> None:
    assert SlideGrouper().group([]) == []
