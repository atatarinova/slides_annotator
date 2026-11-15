"""Экспорт аннотации в Markdown."""

from src.llm.schemas import PresentationAnnotation


def render_markdown(annotation: PresentationAnnotation) -> str:
    """Формирует Markdown-представление в иерархии «тема → разделы → аннотации»."""
    lines: list[str] = [f"# Основная тема: {annotation.main_topic.strip()}", ""]
    for index, section in enumerate(annotation.sections, start=1):
        lines.append(f"## {index}. {section.section_title.strip()}")
        if section.slide_range.strip():
            lines.append(f"*{section.slide_range.strip()}*")
            lines.append("")
        lines.append(section.section_summary.strip())
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
