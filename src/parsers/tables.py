"""Извлечение текстовых таблиц из PDF с помощью pdfplumber."""

from pathlib import Path
from typing import Any, Protocol

from src.core.exceptions import MissingDependencyError
from src.core.logging import get_logger
from src.core.models import BBox, ExtractedTable

logger = get_logger(__name__)


class TableExtractor(Protocol):
    """Протокол извлекателя таблиц (позволяет подменять его в тестах)."""

    def extract(self, pdf_path: Path) -> dict[int, list[ExtractedTable]]:
        """Возвращает таблицы, сгруппированные по номеру слайда."""
        ...


class PdfPlumberTableExtractor:
    """Извлекает структурированные текстовые таблицы через pdfplumber."""

    def __init__(self, *, min_rows: int = 2, min_columns: int = 2) -> None:
        self._min_rows = max(1, min_rows)
        self._min_columns = max(1, min_columns)

    def extract(self, pdf_path: Path) -> dict[int, list[ExtractedTable]]:
        try:
            import pdfplumber
        except ImportError as exc:  # pragma: no cover - зависит от окружения
            raise MissingDependencyError(
                "Для извлечения таблиц установите pdfplumber: pip install pdfplumber"
            ) from exc

        tables_by_slide: dict[int, list[ExtractedTable]] = {}
        try:
            with pdfplumber.open(str(pdf_path)) as document:
                for slide_number, page in enumerate(document.pages, start=1):
                    for raw_table in page.find_tables():
                        table = self._build_table(raw_table, page_number=slide_number)
                        if table is not None:
                            tables_by_slide.setdefault(slide_number, []).append(table)
        except Exception as exc:
            logger.warning(
                "Не удалось извлечь таблицы из %s, продолжаю без таблиц: %s", pdf_path, exc
            )
            return {}
        return tables_by_slide

    def _build_table(self, raw_table: Any, *, page_number: int) -> ExtractedTable | None:
        rows: list[list[str]] = []
        for raw_row in raw_table.extract() or []:
            row = ["" if cell is None else str(cell) for cell in raw_row]
            if any(cell.strip() for cell in row):
                rows.append(row)
        if len(rows) < self._min_rows:
            return None
        table = ExtractedTable(rows=rows, bbox=_bbox_from_raw(raw_table.bbox))
        if not table.is_meaningful:
            return None
        logger.debug("Слайд %d: извлечена таблица %dx%d", page_number, len(rows), len(rows[0]))
        return table


def _bbox_from_raw(raw_bbox: Any) -> BBox | None:
    if raw_bbox is None:
        return None
    x0, top, x1, bottom = (float(value) for value in raw_bbox)
    return BBox(x0=x0, y0=top, x1=x1, y1=bottom)
