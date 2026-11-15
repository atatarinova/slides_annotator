"""Семантическая группировка слайдов в логические разделы."""

from src.core.constants import UNTITLED_TITLE
from src.core.logging import get_logger
from src.core.models import ParsedSlide, SectionGroup
from src.processors.text_utils import title_key

logger = get_logger(__name__)


class SlideGrouper:
    """Объединяет слайды в разделы по разделителям, заголовкам и продолжениям."""

    def __init__(self, *, untitled_title: str = "Введение") -> None:
        self._untitled_title = untitled_title

    def group(self, slides: list[ParsedSlide]) -> list[SectionGroup]:
        if not slides:
            return []

        grouped: list[list[ParsedSlide]] = []
        divider_section = False
        for slide in slides:
            if not grouped:
                grouped.append([slide])
                divider_section = slide.is_section_divider and not slide.is_title_slide
                continue

            current_title = _section_title(grouped[-1], self._untitled_title)
            candidate_title = slide.title or self._untitled_title
            same_title = title_key(candidate_title) == title_key(current_title)

            if slide.is_title_slide:
                start_new = False
            elif slide.is_section_divider and not same_title:
                start_new = True
            elif divider_section or slide.is_continuation or slide.title_inherited or same_title:
                start_new = False
            else:
                start_new = True

            if start_new:
                grouped.append([slide])
                divider_section = slide.is_section_divider and not slide.is_title_slide
            else:
                grouped[-1].append(slide)

        result = [
            SectionGroup(
                section_index=index,
                title=_section_title(group, self._untitled_title),
                slides=group,
            )
            for index, group in enumerate(grouped, start=1)
        ]
        logger.info("Слайды сгруппированы в %d логических разделов", len(result))
        return result


def _section_title(slides: list[ParsedSlide], fallback: str) -> str:
    for slide in slides:
        if slide.is_title_slide:
            continue
        if slide.title:
            return slide.title
    for slide in slides:
        if slide.title:
            return slide.title
    return fallback


__all__ = ["UNTITLED_TITLE", "SlideGrouper"]
