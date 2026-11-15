"""Тесты извлечения текстового слоя и таблиц из PDF."""

from pathlib import Path

import pytest

from src.core.exceptions import EmptyTextLayerError, PDFParsingError
from src.core.models import BBox, ExtractedTable
from src.parsers.pdf_parser import PDFParser


def test_parse_presentation_extracts_blocks_and_fonts(presentation_pdf: Path) -> None:
    slides = PDFParser(extract_tables=False).parse(presentation_pdf)

    assert len(slides) == 6
    assert [slide.slide_number for slide in slides] == [1, 2, 3, 4, 5, 6]
    assert all(slide.width > 0 and slide.height > 0 for slide in slides)

    title_block = slides[0].blocks[0]
    assert title_block.text == "Машинное обучение"
    assert title_block.font_size == pytest.approx(28.0)
    assert title_block.is_bold is True
    assert title_block.bbox.height > 0


def test_parse_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(PDFParsingError, match="не найден"):
        PDFParser(extract_tables=False).parse(tmp_path / "missing.pdf")


def test_empty_text_layer_raises(blank_pdf: Path) -> None:
    with pytest.raises(EmptyTextLayerError):
        PDFParser(extract_tables=False).parse(blank_pdf)


def test_not_a_pdf_raises(tmp_path: Path) -> None:
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"this is not a pdf")
    with pytest.raises(PDFParsingError):
        PDFParser(extract_tables=False).parse(broken)


class _StubTableExtractor:
    def __init__(self, tables: dict[int, list[ExtractedTable]]) -> None:
        self._tables = tables

    def extract(self, pdf_path: Path) -> dict[int, list[ExtractedTable]]:
        return self._tables


def test_tables_are_attached_and_duplicated_blocks_removed(presentation_pdf: Path) -> None:
    table = ExtractedTable(
        rows=[["Метод", "Тип"], ["Классификация", "С учителем"]],
        bbox=BBox(x0=60, y0=130, x1=520, y1=230),
    )
    parser = PDFParser(extract_tables=True, table_extractor=_StubTableExtractor({2: [table]}))

    slides = parser.parse(presentation_pdf)

    assert len(slides[1].tables) == 1
    assert slides[1].tables[0].rows == [["Метод", "Тип"], ["Классификация", "С учителем"]]
    assert slides[1].blocks
    assert all(
        not table.bbox.contains_point(block.bbox.center_x, block.bbox.center_y)
        for block in slides[1].blocks
    )
    assert "Классификация" in slides[1].tables[0].to_markdown()
