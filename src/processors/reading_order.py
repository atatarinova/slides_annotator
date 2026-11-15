"""Восстановление логического порядка чтения текстовых блоков слайда."""

from src.core.models import TextBlock

WIDE_BLOCK_RATIO = 0.65
MIN_COLUMN_GAP_RATIO = 0.04
MIN_BLOCK_GAP_POINTS = 6.0
MIN_BLOCKS_PER_COLUMN = 2
ROW_TOLERANCE_RATIO = 0.5


def order_blocks(blocks: list[TextBlock], page_width: float) -> list[TextBlock]:
    """Сортирует блоки сверху вниз и слева направо, не смешивая колонки."""
    if len(blocks) <= 1:
        return list(blocks)

    columns = _detect_columns(blocks, page_width)
    if len(columns) <= 1:
        return _order_region(blocks)

    ordered: list[TextBlock] = []
    for column in columns:
        ordered.extend(_order_region(column))
    return ordered


def _detect_columns(blocks: list[TextBlock], page_width: float) -> list[list[TextBlock]]:
    if page_width <= 0 or len(blocks) < 4:
        return [list(blocks)]

    min_gap = max(page_width * MIN_COLUMN_GAP_RATIO, MIN_BLOCK_GAP_POINTS)
    narrow: list[TextBlock] = []
    wide: list[TextBlock] = []
    for block in blocks:
        if block.bbox.width >= page_width * WIDE_BLOCK_RATIO:
            wide.append(block)
        else:
            narrow.append(block)

    bands = _build_x_bands(narrow, min_gap)
    columns = [band for band in bands if len(band) >= MIN_BLOCKS_PER_COLUMN]
    if len(columns) < 2:
        return [list(blocks)]

    for band in bands:
        if len(band) >= MIN_BLOCKS_PER_COLUMN:
            continue
        for block in band:
            target = min(columns, key=lambda column: abs(_center_x(column) - block.bbox.center_x))
            target.append(block)

    columns.sort(key=lambda column: min(block.bbox.x0 for block in column))
    column_top = min(block.bbox.y0 for column in columns for block in column)
    column_bottom = max(block.bbox.y1 for column in columns for block in column)

    leading = [block for block in wide if block.bbox.y1 <= column_top + 1.0]
    trailing = [block for block in wide if block.bbox.y0 >= column_bottom - 1.0]
    leading_ids = {id(block) for block in leading}
    trailing_ids = {id(block) for block in trailing}
    middle = [block for block in wide if id(block) not in leading_ids | trailing_ids]

    result: list[list[TextBlock]] = []
    header = leading + middle
    if header:
        result.append(_order_region(header))
    result.extend(columns)
    if trailing:
        result.append(_order_region(trailing))
    return result


def _build_x_bands(blocks: list[TextBlock], min_gap: float) -> list[list[TextBlock]]:
    bands: list[list[TextBlock]] = []
    for block in sorted(blocks, key=lambda item: item.bbox.x0):
        if bands and block.bbox.x0 <= max(item.bbox.x1 for item in bands[-1]) + min_gap:
            bands[-1].append(block)
        else:
            bands.append([block])
    return bands


def _center_x(blocks: list[TextBlock]) -> float:
    left = min(block.bbox.x0 for block in blocks)
    right = max(block.bbox.x1 for block in blocks)
    return (left + right) / 2


def _order_region(blocks: list[TextBlock]) -> list[TextBlock]:
    if len(blocks) <= 1:
        return list(blocks)

    heights = sorted(block.bbox.height for block in blocks)
    tolerance = max(1.0, heights[len(heights) // 2] * ROW_TOLERANCE_RATIO)

    rows: list[list[TextBlock]] = []
    for block in sorted(blocks, key=lambda item: (item.bbox.y0, item.bbox.x0)):
        if rows and abs(block.bbox.y0 - rows[-1][0].bbox.y0) <= tolerance:
            rows[-1].append(block)
        else:
            rows.append([block])

    ordered: list[TextBlock] = []
    for row in rows:
        ordered.extend(sorted(row, key=lambda item: item.bbox.x0))
    return ordered
