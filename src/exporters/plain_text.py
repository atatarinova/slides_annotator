"""Экспорт аннотации в обычный текст."""

from src.llm.schemas import PresentationAnnotation


def render_txt(annotation: PresentationAnnotation) -> str:
    """Формирует текстовое представление аннотации."""
    lines: list[str] = [f"ОСНОВНАЯ ТЕМА: {annotation.main_topic.strip()}", ""]
    for index, section in enumerate(annotation.sections, start=1):
        header = f"{index}. {section.section_title.strip()}"
        if section.slide_range.strip():
            header += f" ({section.slide_range.strip()})"
        lines.extend([header, section.section_summary.strip(), ""])
    return "\n".join(lines).rstrip() + "\n"
