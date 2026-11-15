"""Вспомогательные функции нормализации текста."""

from collections.abc import Iterable

from src.core.constants import (
    CONTINUATION_COUNTER,
    CONTINUATION_MARKERS,
    LEADING_NUMBERING,
    PAGE_NUMBER_PATTERNS,
    PAGE_NUMBER_SUFFIX,
    TRAILING_PUNCTUATION,
    WHITESPACE,
)


def clean_text(value: str) -> str:
    """Убирает управляющие символы, лишние пробелы и пустые края."""
    if not value:
        return ""
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    normalized = "".join(
        char if char in "\n\t" or char.isprintable() else " " for char in normalized
    )
    lines = [WHITESPACE.sub(" ", line).strip() for line in normalized.split("\n")]
    result: list[str] = []
    for line in lines:
        if line:
            result.append(line)
        elif result and result[-1]:
            result.append("")
    while result and not result[-1]:
        result.pop()
    return "\n".join(result).strip()


def normalize_text(value: str) -> str:
    """Нормализует текст для сравнения: регистр, пробелы, края."""
    return WHITESPACE.sub(" ", value).strip().casefold()


def normalize_title(value: str) -> str:
    """Приводит заголовок к одной строке без лишних пробелов."""
    return WHITESPACE.sub(" ", value.replace("\n", " ")).strip()


def title_key(value: str) -> str:
    """Ключ сравнения заголовков без номеров, маркеров продолжения и пунктуации."""
    text = normalize_text(value)
    text = CONTINUATION_MARKERS.sub(" ", text)
    text = CONTINUATION_COUNTER.sub(" ", text)
    text = LEADING_NUMBERING.sub("", text)
    text = TRAILING_PUNCTUATION.sub("", text)
    return WHITESPACE.sub(" ", text).strip()


def is_page_number_like(value: str) -> bool:
    """Проверяет, похож ли текст на номер слайда или колонтитул с номером."""
    normalized = normalize_text(value)
    if not normalized or len(normalized) > 40:
        return False
    return any(pattern.match(normalized) for pattern in PAGE_NUMBER_PATTERNS)


def strip_page_number_suffix(value: str) -> str:
    """Отрезает номер страницы в конце текста колонтитула («Курс ML 5», «Итог | 3»)."""
    text = value.strip()
    previous: str | None = None
    while text and text != previous:
        previous = text
        text = PAGE_NUMBER_SUFFIX.sub("", text).strip()
    return text


def noise_key(value: str) -> str:
    """Ключ сравнения колонтитулов без номеров страниц в конце текста."""
    return normalize_text(strip_page_number_suffix(value))


def has_continuation_marker(value: str) -> bool:
    """Проверяет наличие пометки продолжения: (продолжение), (cont.), 2/3 и т. п."""
    return bool(CONTINUATION_MARKERS.search(value) or CONTINUATION_COUNTER.search(value))


def clean_body_text(parts: Iterable[str]) -> str:
    """Собирает основной текст слайда, убирая пустые и повторяющиеся строки."""
    text = clean_text("\n".join(part for part in parts if part))
    lines: list[str] = []
    for line in text.split("\n"):
        if not line:
            continue
        if lines and lines[-1] == line:
            continue
        lines.append(line)
    return "\n".join(lines)
