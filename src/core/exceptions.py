"""Доменные исключения системы аннотирования."""


class AnnotationError(Exception):
    """Базовое исключение системы аннотирования."""


class PDFParsingError(AnnotationError):
    """Не удалось прочитать или разобрать PDF-файл."""


class EmptyTextLayerError(PDFParsingError):
    """В PDF отсутствует извлекаемый текстовый слой (например, скан без OCR)."""


class LLMGenerationError(AnnotationError):
    """Не удалось получить структурированный ответ от LLM."""


class LLMConfigurationError(LLMGenerationError):
    """Некорректная конфигурация LLM-клиента (нет API-ключа и т. п.)."""


class PromptError(AnnotationError):
    """Ошибка загрузки или рендеринга шаблона промпта."""


class ExportError(AnnotationError):
    """Ошибка экспорта готовой аннотации."""


class UnsupportedFormatError(ExportError):
    """Запрошен неизвестный формат экспорта."""


class MissingDependencyError(AnnotationError):
    """Не установлена зависимость, необходимая для выбранной операции."""
