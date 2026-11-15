"""Реестр форматов экспорта и запись результата на диск."""

from collections.abc import Callable
from pathlib import Path

from src.core.constants import EXPORT_FORMATS
from src.core.exceptions import UnsupportedFormatError
from src.exporters.docx_exporter import render_docx
from src.exporters.json_exporter import render_json
from src.exporters.markdown import render_markdown
from src.exporters.plain_text import render_txt
from src.llm.schemas import PresentationAnnotation

Renderer = Callable[[PresentationAnnotation], str | bytes]

_RENDERERS: dict[str, Renderer] = {
    "markdown": render_markdown,
    "json": render_json,
    "txt": render_txt,
    "docx": render_docx,
}

_ALIASES: dict[str, str] = {
    "md": "markdown",
    "text": "txt",
    "plain": "txt",
    "doc": "docx",
    "word": "docx",
}

_SUFFIXES: dict[str, str] = {
    "markdown": ".md",
    "json": ".json",
    "txt": ".txt",
    "docx": ".docx",
}

_MEDIA_TYPES: dict[str, str] = {
    "markdown": "text/markdown; charset=utf-8",
    "json": "application/json",
    "txt": "text/plain; charset=utf-8",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def resolve_format(value: str) -> str:
    """Приводит псевдоним формата к каноническому имени."""
    normalized = value.strip().lower()
    normalized = _ALIASES.get(normalized, normalized)
    if normalized not in _RENDERERS:
        allowed = ", ".join(EXPORT_FORMATS)
        raise UnsupportedFormatError(f"Неизвестный формат экспорта {value!r}; доступны: {allowed}")
    return normalized


def infer_format(path: Path) -> str:
    """Определяет формат по расширению файла (по умолчанию — Markdown)."""
    suffix = path.suffix.lower()
    if not suffix:
        return "markdown"
    for name, expected_suffix in _SUFFIXES.items():
        if suffix == expected_suffix:
            return name
    allowed = ", ".join(f"{name} ({suffix})" for name, suffix in _SUFFIXES.items())
    raise UnsupportedFormatError(
        f"Не удалось определить формат по расширению {suffix!r}; доступны: {allowed}"
    )


def suffix_for(format_name: str) -> str:
    """Возвращает расширение файла для формата."""
    return _SUFFIXES[resolve_format(format_name)]


def media_type(format_name: str) -> str:
    """Возвращает MIME-тип для формата."""
    return _MEDIA_TYPES[resolve_format(format_name)]


def render_annotation(annotation: PresentationAnnotation, format_name: str) -> str | bytes:
    """Рендерит аннотацию в выбранном формате."""
    return _RENDERERS[resolve_format(format_name)](annotation)


def export_annotation(
    annotation: PresentationAnnotation,
    destination: str | Path,
    format_name: str | None = None,
) -> Path:
    """Сохраняет аннотацию в файл и возвращает итоговый путь."""
    path = Path(destination).expanduser()
    resolved = resolve_format(format_name) if format_name else infer_format(path)
    payload = render_annotation(annotation, resolved)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, bytes):
        path.write_bytes(payload)
    else:
        path.write_text(payload, encoding="utf-8")
    return path
