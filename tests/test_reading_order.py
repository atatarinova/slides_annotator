"""Тесты восстановления порядка чтения и колонок."""

from src.processors.reading_order import order_blocks
from tests.helpers import text_block


def test_two_columns_are_read_top_to_bottom_per_column() -> None:
    blocks = [
        text_block("Заголовок", x0=100, y0=50, x1=500, y1=80, size=24, bold=True),
        text_block("L1", x0=60, y0=150, x1=280, y1=170),
        text_block("L2", x0=60, y0=200, x1=280, y1=220),
        text_block("L3", x0=60, y0=250, x1=280, y1=270),
        text_block("R1", x0=320, y0=150, x1=540, y1=170),
        text_block("R2", x0=320, y0=200, x1=540, y1=220),
        text_block("R3", x0=320, y0=250, x1=540, y1=270),
    ]

    ordered = order_blocks(blocks, page_width=595)

    assert [block.text for block in ordered] == ["Заголовок", "L1", "L2", "L3", "R1", "R2", "R3"]


def test_same_row_is_sorted_left_to_right() -> None:
    blocks = [
        text_block("Право", x0=320, y0=100, x1=500, y1=115),
        text_block("Лево", x0=60, y0=103, x1=280, y1=118),
    ]

    ordered = order_blocks(blocks, page_width=595)

    assert [block.text for block in ordered] == ["Лево", "Право"]


def test_single_column_is_sorted_by_y() -> None:
    blocks = [
        text_block("Второй", y0=200, y1=220),
        text_block("Первый", y0=100, y1=120),
    ]

    ordered = order_blocks(blocks, page_width=595)

    assert [block.text for block in ordered] == ["Первый", "Второй"]


def test_empty_or_single_block_is_returned_as_is() -> None:
    assert order_blocks([], page_width=595) == []
    block = text_block("Один")
    assert order_blocks([block], page_width=595) == [block]
