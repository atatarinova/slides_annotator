"""Тесты экспортеров аннотации."""

import io
import json
from pathlib import Path

import pytest
from docx import Document

from src.core.exceptions import UnsupportedFormatError
from src.exporters import (
    export_annotation,
    infer_format,
    media_type,
    render_annotation,
    resolve_format,
    suffix_for,
)
from src.llm.schemas import PresentationAnnotation


def test_markdown_has_required_hierarchy(annotation: PresentationAnnotation) -> None:
    payload = render_annotation(annotation, "markdown")

    assert isinstance(payload, str)
    assert payload.startswith("# Основная тема: ")
    assert "## 1. Определения" in payload
    assert "## 2. Методы обучения" in payload
    assert payload.count("\n## ") == len(annotation.sections)


def test_markdown_contains_slide_range(annotation: PresentationAnnotation) -> None:
    payload = render_annotation(annotation, "markdown")

    assert "*Слайды 3–6*" in payload


def test_json_roundtrip(annotation: PresentationAnnotation) -> None:
    payload = render_annotation(annotation, "json")

    assert isinstance(payload, str)
    data = json.loads(payload)
    assert data["main_topic"] == annotation.main_topic
    assert data["sections"][0]["section_title"] == "Определения"
    assert "Определения" in payload


def test_txt_rendering(annotation: PresentationAnnotation) -> None:
    payload = render_annotation(annotation, "txt")

    assert isinstance(payload, str)
    assert payload.startswith("ОСНОВНАЯ ТЕМА:")
    assert "1. Определения (Слайды 2–2)" in payload


def test_docx_rendering(annotation: PresentationAnnotation) -> None:
    payload = render_annotation(annotation, "docx")

    assert isinstance(payload, bytes)
    assert payload.startswith(b"PK")
    document = Document(io.BytesIO(payload))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "Основная тема" in text
    assert "Определения" in text
    assert "Слайды 3–6" in text


@pytest.mark.parametrize(
    ("alias", "expected"),
    [("md", "markdown"), ("text", "txt"), ("doc", "docx"), ("JSON", "json")],
)
def test_resolve_format_aliases(alias: str, expected: str) -> None:
    assert resolve_format(alias) == expected


def test_infer_format_from_suffix(tmp_path: Path) -> None:
    assert infer_format(tmp_path / "result.md") == "markdown"
    assert infer_format(tmp_path / "result.docx") == "docx"
    assert infer_format(tmp_path / "result") == "markdown"


def test_unknown_format_raises() -> None:
    with pytest.raises(UnsupportedFormatError):
        resolve_format("pdf")
    with pytest.raises(UnsupportedFormatError):
        infer_format(Path("result.xlsx"))


def test_export_writes_file_by_suffix(annotation: PresentationAnnotation, tmp_path: Path) -> None:
    destination = export_annotation(annotation, tmp_path / "nested" / "annotation.md")

    assert destination.exists()
    assert destination.read_text(encoding="utf-8").startswith("# Основная тема:")


def test_export_with_explicit_format(annotation: PresentationAnnotation, tmp_path: Path) -> None:
    destination = export_annotation(annotation, tmp_path / "annotation.out", "json")

    assert json.loads(destination.read_text(encoding="utf-8"))["main_topic"]


def test_export_docx_writes_binary(annotation: PresentationAnnotation, tmp_path: Path) -> None:
    destination = export_annotation(annotation, tmp_path / "annotation.docx")

    assert destination.read_bytes().startswith(b"PK")


def test_media_type_and_suffix() -> None:
    assert media_type("markdown").startswith("text/markdown")
    assert suffix_for("docx") == ".docx"
