"""Экспорт аннотации в JSON."""

from src.llm.schemas import PresentationAnnotation


def render_json(annotation: PresentationAnnotation) -> str:
    """Сериализует аннотацию в JSON с сохранением Unicode."""
    return annotation.model_dump_json(indent=2) + "\n"
