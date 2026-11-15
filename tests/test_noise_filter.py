"""Тесты фильтрации колонтитулов и номеров слайдов."""

from src.core.models import RawSlide
from src.processors.noise_filter import NoiseFilter
from tests.helpers import raw_slide, text_block


def _slide(number: int, body: str) -> RawSlide:
    return raw_slide(
        number,
        [
            text_block("Кафедра информатики", x0=60, y0=18, x1=220, y1=30, size=9),
            text_block(body, y0=150, y1=170),
            text_block("Курс ML", x0=60, y0=800, x1=150, y1=812, size=9),
            text_block(str(number), x0=520, y0=800, x1=540, y1=812, size=9),
        ],
    )


def test_removes_repeated_headers_footers_and_page_numbers() -> None:
    bodies = [f"Уникальный текст слайда номер {index}" for index in range(1, 6)]
    slides = [_slide(index, body) for index, body in enumerate(bodies, start=1)]

    filtered = NoiseFilter().apply(slides)

    assert [[block.text for block in slide.blocks] for slide in filtered] == [
        [body] for body in bodies
    ]


def test_keeps_unique_blocks_in_body() -> None:
    slides = [_slide(index, f"Содержание {index}") for index in range(1, 6)]
    slides[0].blocks.append(text_block("Уникальный вывод", y0=400, y1=420))

    filtered = NoiseFilter().apply(slides)

    assert any(block.text == "Уникальный вывод" for block in filtered[0].blocks)


def test_removes_repeated_block_with_identical_geometry() -> None:
    slides = []
    for index in range(1, 6):
        slide = _slide(index, f"Содержание {index}")
        if index <= 4:
            slide.blocks.append(text_block("Одинаковый тезис", y0=400, y1=420))
        slides.append(slide)

    filtered = NoiseFilter().apply(slides)

    assert not any(block.text == "Одинаковый тезис" for slide in filtered for block in slide.blocks)


def test_small_documents_are_not_filtered() -> None:
    slides = [_slide(index, f"Содержание {index}") for index in range(1, 3)]

    filtered = NoiseFilter().apply(slides)

    assert filtered == slides
