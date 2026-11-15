"""Общие константы и регулярные выражения проекта."""

import re

PAGE_NUMBER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\d{1,4}$"),
    re.compile(
        r"^(?:слайд|slide|стр\.?|page)\s*[№#]?\s*\d{1,4}"
        r"(?:\s*(?:из|of|/)\s*\d{1,4})?$",
        re.IGNORECASE,
    ),
    re.compile(r"^\d{1,4}\s*/\s*\d{1,4}$"),
)

CONTINUATION_MARKERS: re.Pattern[str] = re.compile(
    r"\(\s*(?:продолжение|продолж\.?|cont\.?|continued)\s*\)"
    r"|\[\s*(?:продолжение|продолж\.?|cont\.?|continued)\s*\]",
    re.IGNORECASE,
)

PAGE_NUMBER_SUFFIX: re.Pattern[str] = re.compile(
    r"(?:[|·•]|\s*[-–—]\s*|\s+)"
    r"(?:\d{1,4}(?:\s*(?:/|из|of)\s*\d{1,4})?"
    r"|(?:слайд|slide|стр\.?|page)\s*[№#]?\s*\d{1,4})$",
    re.IGNORECASE,
)

CONTINUATION_COUNTER: re.Pattern[str] = re.compile(r"\b\d{1,2}\s*/\s*\d{1,2}\b")

LEADING_NUMBERING: re.Pattern[str] = re.compile(r"^\s*\d{1,2}(?:\.\d{1,2})*[.)]?\s+")

TRAILING_PUNCTUATION: re.Pattern[str] = re.compile(r"[\s.,;:!?]+$")

BULLET_ONLY: re.Pattern[str] = re.compile(r"^[\s\u2022\u00b7\u25aa\u25e6\u2023\u2043\-–—*]+$")

WHITESPACE: re.Pattern[str] = re.compile(r"[ \t\u00a0\u200b\ufeff]+")

DEFAULT_BODY_FONT_SIZE = 12.0

UNTITLED_TITLE = "Без заголовка"

EXPORT_FORMATS: tuple[str, ...] = ("markdown", "json", "txt", "docx")

SUPPORTED_UPLOAD_SUFFIXES: tuple[str, ...] = (".pdf",)
