"""Эвристики определения заголовков, разделителей секций и текста слайда."""

from src.core.constants import DEFAULT_BODY_FONT_SIZE
from src.core.logging import get_logger
from src.core.models import ParsedSlide, RawSlide, TextBlock
from src.processors.reading_order import order_blocks
from src.processors.text_utils import (
    clean_body_text,
    has_continuation_marker,
    normalize_title,
    title_key,
)

logger = get_logger(__name__)

BODY_LIKE_MIN_CHARS = 40


class HeadingDetector:
    """Определяет заголовок слайда, его тип и очищенный основной текст."""

    def __init__(
        self,
        *,
        heading_font_scale: float = 1.2,
        section_divider_font_scale: float = 1.5,
        title_zone_ratio: float = 0.3,
        max_title_chars: int = 200,
    ) -> None:
        self._heading_scale = heading_font_scale
        self._divider_scale = section_divider_font_scale
        self._title_zone_ratio = title_zone_ratio
        self._max_title_chars = max_title_chars

    def detect(self, slides: list[RawSlide]) -> list[ParsedSlide]:
        """Преобразует сырые слайды в очищенные слайды с заголовками."""
        body_font_size = self._estimate_body_font_size(slides)
        logger.info("Медианный размер шрифта основного текста: %.1f pt", body_font_size)

        parsed: list[ParsedSlide] = []
        previous_title: str | None = None
        for slide in slides:
            title_block = self._find_title_block(slide, body_font_size)
            title = normalize_title(title_block.text) if title_block is not None else None

            is_divider = self._is_section_divider(slide, body_font_size)
            is_title_slide = self._is_title_slide(slide, body_font_size)

            inherited = False
            if title is None and previous_title is not None:
                title = previous_title
                inherited = True

            is_continuation = (
                title is not None
                and previous_title is not None
                and not is_divider
                and _titles_match(title, previous_title)
            )

            body_parts: list[str] = []
            for block in order_blocks(slide.blocks, slide.width):
                if block is title_block:
                    continue
                if title is not None and title_key(block.text) == title_key(title):
                    continue
                body_parts.extend(_block_lines(block))
            body_parts.extend(table.to_markdown() for table in slide.tables if table.is_meaningful)

            parsed.append(
                ParsedSlide(
                    slide_number=slide.slide_number,
                    title=title,
                    title_inherited=inherited,
                    is_title_slide=is_title_slide,
                    is_section_divider=is_divider,
                    is_continuation=is_continuation,
                    body_text=clean_body_text(body_parts),
                )
            )
            if title is not None:
                previous_title = title
        return parsed

    def _estimate_body_font_size(self, slides: list[RawSlide]) -> float:
        samples: list[tuple[float, int]] = []
        for slide in slides:
            for block in slide.blocks:
                weight = max(1, min(block.char_count, 200))
                samples.append((block.font_size, weight))
        if not samples:
            return DEFAULT_BODY_FONT_SIZE
        samples.sort(key=lambda item: item[0])
        total_weight = sum(weight for _, weight in samples)
        cumulative = 0
        for size, weight in samples:
            cumulative += weight
            if cumulative >= total_weight / 2:
                return size
        return samples[-1][0]

    def _find_title_block(self, slide: RawSlide, body_font_size: float) -> TextBlock | None:
        blocks = [block for block in slide.blocks if block.text.strip()]
        if not blocks:
            return None

        threshold = body_font_size * self._heading_scale
        top_limit = slide.height * self._title_zone_ratio
        candidates = [
            block
            for block in blocks
            if block.bbox.y0 < top_limit
            and self._is_heading_candidate(block, threshold, body_font_size)
        ]
        if not candidates:
            candidates = [
                block
                for block in blocks
                if block.font_size >= threshold and block.char_count <= self._max_title_chars
            ]
        if not candidates:
            candidates = [
                block
                for block in blocks
                if block.is_bold
                and block.is_short
                and block.font_size >= body_font_size
                and block.char_count <= self._max_title_chars
            ]
        if not candidates:
            return None
        return max(candidates, key=lambda block: (block.font_size, -block.bbox.y0, -block.bbox.x0))

    def _is_heading_candidate(
        self, block: TextBlock, threshold: float, body_font_size: float
    ) -> bool:
        if block.char_count > self._max_title_chars:
            return False
        if block.font_size >= threshold:
            return True
        return block.is_bold and block.font_size >= body_font_size

    def _is_section_divider(self, slide: RawSlide, body_font_size: float) -> bool:
        blocks = [block for block in slide.blocks if block.text.strip()]
        if not 1 <= len(blocks) <= 2:
            return False
        if any(_is_body_like(block, body_font_size) for block in blocks):
            return False

        largest = max(blocks, key=lambda block: block.font_size)
        large_enough = largest.font_size >= body_font_size * self._divider_scale or (
            largest.is_bold and largest.font_size >= body_font_size * self._heading_scale
        )
        if not large_enough:
            return False

        centered_x = 0.3 * slide.width <= largest.bbox.center_x <= 0.7 * slide.width
        centered_y = 0.2 * slide.height <= largest.bbox.center_y <= 0.8 * slide.height
        return centered_x and centered_y

    def _is_title_slide(self, slide: RawSlide, body_font_size: float) -> bool:
        if slide.slide_number != 1:
            return False
        blocks = [block for block in slide.blocks if block.text.strip()]
        if not blocks or len(blocks) > 3:
            return False
        if any(_is_body_like(block, body_font_size) for block in blocks):
            return False
        return max(block.font_size for block in blocks) >= body_font_size * self._heading_scale


def _is_body_like(block: TextBlock, body_font_size: float) -> bool:
    return block.font_size <= body_font_size * 1.05 and block.char_count >= BODY_LIKE_MIN_CHARS


def _titles_match(current: str, previous: str) -> bool:
    if has_continuation_marker(current):
        return True
    current_key = title_key(current)
    return bool(current_key) and current_key == title_key(previous)


def _block_lines(block: TextBlock) -> list[str]:
    return [line for line in block.text.split("\n") if line.strip()]
