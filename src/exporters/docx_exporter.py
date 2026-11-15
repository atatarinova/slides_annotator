"""Экспорт аннотации в DOCX."""

import io

from src.core.exceptions import MissingDependencyError
from src.llm.schemas import PresentationAnnotation


def render_docx(annotation: PresentationAnnotation) -> bytes:
    """Формирует DOCX-документ с заголовками разделов и текстом аннотаций."""
    try:
        from docx import Document
    except ImportError as exc:  # pragma: no cover - зависит от окружения
        raise MissingDependencyError(
            "Для экспорта в DOCX установите python-docx: pip install python-docx"
        ) from exc

    document = Document()
    document.add_heading(f"Основная тема: {annotation.main_topic.strip()}", level=1)
    for index, section in enumerate(annotation.sections, start=1):
        document.add_heading(f"{index}. {section.section_title.strip()}", level=2)
        if section.slide_range.strip():
            paragraph = document.add_paragraph()
            run = paragraph.add_run(section.slide_range.strip())
            run.italic = True
        document.add_paragraph(section.section_summary.strip())

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()
