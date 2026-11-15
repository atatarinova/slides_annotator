"""Конфигурация, логирование, модели данных и доменные исключения."""

from src.core.config import Settings, get_settings
from src.core.exceptions import (
    AnnotationError,
    EmptyTextLayerError,
    ExportError,
    LLMConfigurationError,
    LLMGenerationError,
    MissingDependencyError,
    PDFParsingError,
    PromptError,
    UnsupportedFormatError,
)
from src.core.models import (
    BBox,
    ExtractedTable,
    ParsedSlide,
    RawSlide,
    SectionGroup,
    TextBlock,
)

__all__ = [
    "AnnotationError",
    "BBox",
    "EmptyTextLayerError",
    "ExportError",
    "ExtractedTable",
    "LLMConfigurationError",
    "LLMGenerationError",
    "MissingDependencyError",
    "PDFParsingError",
    "ParsedSlide",
    "PromptError",
    "RawSlide",
    "SectionGroup",
    "Settings",
    "TextBlock",
    "UnsupportedFormatError",
    "get_settings",
]
