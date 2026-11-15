"""Фильтрация колонтитулов, номеров слайдов и повторяющегося шума верстки."""

import math
from collections import defaultdict
from dataclasses import dataclass

from src.core.logging import get_logger
from src.core.models import BBox, RawSlide
from src.processors.text_utils import is_page_number_like, noise_key, normalize_text

logger = get_logger(__name__)

MARGIN_RATIO = 0.12


@dataclass(frozen=True)
class _Occurrence:
    slide_number: int
    block_index: int
    bbox: BBox
    page_height: float


class NoiseFilter:
    """Удаляет блоки, повторяющиеся более чем на заданной доле слайдов."""

    def __init__(
        self,
        *,
        slide_ratio_threshold: float = 0.4,
        bbox_tolerance: float = 4.0,
        min_slides: int = 3,
    ) -> None:
        if not 0.0 < slide_ratio_threshold <= 1.0:
            raise ValueError("slide_ratio_threshold должен быть в интервале (0, 1]")
        self._ratio = slide_ratio_threshold
        self._bbox_tolerance = bbox_tolerance
        self._min_slides = max(1, min_slides)

    def apply(self, slides: list[RawSlide]) -> list[RawSlide]:
        """Возвращает слайды без повторяющихся колонтитулов и номеров страниц."""
        if len(slides) < self._min_slides:
            return slides

        required = max(2, math.ceil(len(slides) * self._ratio))
        occurrences: dict[str, list[_Occurrence]] = defaultdict(list)
        page_number_items: list[_Occurrence] = []
        for slide in slides:
            for block_index, block in enumerate(slide.blocks):
                occurrence = _Occurrence(slide.slide_number, block_index, block.bbox, slide.height)
                if is_page_number_like(block.text):
                    page_number_items.append(occurrence)
                # Номера страниц отрезаем только в колонтитулах: в теле слайда
                # число может быть частью содержания.
                key = (
                    noise_key(block.text)
                    if _is_marginal_item(occurrence)
                    else normalize_text(block.text)
                )
                if key:
                    occurrences[key].append(occurrence)

        to_drop: set[tuple[int, int]] = set()
        marginal_page_numbers = [item for item in page_number_items if _is_marginal_item(item)]
        if len({item.slide_number for item in marginal_page_numbers}) >= required:
            to_drop.update((item.slide_number, item.block_index) for item in marginal_page_numbers)

        for items in occurrences.values():
            slide_numbers = {item.slide_number for item in items}
            if len(slide_numbers) < required:
                continue
            if self._is_repeated_geometry(items, required) or self._is_marginal(items, required):
                to_drop.update((item.slide_number, item.block_index) for item in items)

        if not to_drop:
            return slides

        logger.info(
            "Отфильтровано %d повторяющихся блоков (колонтитулы/номера слайдов)", len(to_drop)
        )
        result: list[RawSlide] = []
        for slide in slides:
            kept = [
                block
                for index, block in enumerate(slide.blocks)
                if (slide.slide_number, index) not in to_drop
            ]
            if len(kept) == len(slide.blocks):
                result.append(slide)
            else:
                result.append(slide.model_copy(update={"blocks": kept}))
        return result

    def _is_repeated_geometry(self, items: list[_Occurrence], required: int) -> bool:
        for cluster in _cluster_by_bbox(items, self._bbox_tolerance):
            if len({item.slide_number for item in cluster}) >= required:
                return True
        return False

    @staticmethod
    def _is_marginal(items: list[_Occurrence], required: int) -> bool:
        slide_numbers = {item.slide_number for item in items}
        if len(slide_numbers) < required:
            return False
        return all(_is_marginal_item(item) for item in items)


def _is_marginal_item(item: _Occurrence) -> bool:
    return (
        item.bbox.y0 <= MARGIN_RATIO * item.page_height
        or item.bbox.y1 >= (1.0 - MARGIN_RATIO) * item.page_height
    )


def _cluster_by_bbox(items: list[_Occurrence], tolerance: float) -> list[list[_Occurrence]]:
    clusters: list[list[_Occurrence]] = []
    for item in items:
        for cluster in clusters:
            if item.bbox.is_close_to(cluster[0].bbox, tolerance):
                cluster.append(item)
                break
        else:
            clusters.append([item])
    return clusters
