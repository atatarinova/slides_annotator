"""Конфигурация приложения на основе pydantic-settings."""

import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROMPTS_DIR = PROJECT_ROOT / "prompts"
DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
API_KEY_ENV_VARS: tuple[str, ...] = ("DASHSCOPE_API_KEY", "OPENAI_API_KEY", "QWEN_API_KEY")
LOG_LEVELS: frozenset[str] = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


class LLMConfig(BaseModel):
    """Параметры подключения к OpenAI-совместимому API."""

    model: str = "qwen-plus"
    base_url: str = DEFAULT_BASE_URL
    api_key: SecretStr | None = None
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_concurrency: int = Field(default=4, ge=1)
    max_retries: int = Field(default=3, ge=1)
    timeout_seconds: float = Field(default=120.0, gt=0)

    def resolved_api_key(self) -> str | None:
        """Возвращает API-ключ из настроек или стандартных переменных окружения."""
        if self.api_key is not None:
            value = self.api_key.get_secret_value().strip()
            if value:
                return value
        for env_var in API_KEY_ENV_VARS:
            value = os.environ.get(env_var, "").strip()
            if value:
                return value
        return None


class ParsingConfig(BaseModel):
    """Пороги и коэффициенты эвристик разбора презентации."""

    min_text_layer_chars: int = Field(default=20, ge=1)
    heading_font_scale: float = Field(default=1.2, gt=1.0)
    section_divider_font_scale: float = Field(default=1.5, gt=1.0)
    title_zone_ratio: float = Field(default=0.3, gt=0.0, le=1.0)
    noise_slide_ratio: float = Field(default=0.4, gt=0.0, le=1.0)
    max_title_chars: int = Field(default=200, ge=1)
    extract_tables: bool = True


class GroupingConfig(BaseModel):
    """Параметры семантической группировки слайдов."""

    long_presentation_slides: int = Field(default=50, ge=1)
    untitled_section_title: str = "Введение"


class Settings(BaseSettings):
    """Настройки приложения, читаемые из окружения с префиксом ``ANNOTATE_``."""

    model_config = SettingsConfigDict(
        env_prefix="ANNOTATE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_model: str = "qwen-plus"
    llm_base_url: str = DEFAULT_BASE_URL
    llm_api_key: SecretStr | None = None
    llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    llm_max_concurrency: int = Field(default=4, ge=1)
    llm_max_retries: int = Field(default=3, ge=1)
    llm_timeout_seconds: float = Field(default=120.0, gt=0)

    min_text_layer_chars: int = Field(default=20, ge=1)
    heading_font_scale: float = Field(default=1.2, gt=1.0)
    section_divider_font_scale: float = Field(default=1.5, gt=1.0)
    title_zone_ratio: float = Field(default=0.3, gt=0.0, le=1.0)
    noise_slide_ratio: float = Field(default=0.4, gt=0.0, le=1.0)
    max_title_chars: int = Field(default=200, ge=1)
    extract_tables: bool = True
    long_presentation_slides: int = Field(default=50, ge=1)

    prompts_dir: Path = DEFAULT_PROMPTS_DIR
    log_level: str = "INFO"

    @field_validator("log_level")
    @classmethod
    def _normalize_log_level(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in LOG_LEVELS:
            allowed = ", ".join(sorted(LOG_LEVELS))
            raise ValueError(
                f"Недопустимый уровень логирования {value!r}; ожидается один из: {allowed}"
            )
        return normalized

    def llm_config(self) -> LLMConfig:
        """Собирает конфигурацию LLM-клиента."""
        return LLMConfig(
            model=self.llm_model,
            base_url=self.llm_base_url,
            api_key=self.llm_api_key,
            temperature=self.llm_temperature,
            max_concurrency=self.llm_max_concurrency,
            max_retries=self.llm_max_retries,
            timeout_seconds=self.llm_timeout_seconds,
        )

    def parsing_config(self) -> ParsingConfig:
        """Собирает конфигурацию эвристик парсинга."""
        return ParsingConfig(
            min_text_layer_chars=self.min_text_layer_chars,
            heading_font_scale=self.heading_font_scale,
            section_divider_font_scale=self.section_divider_font_scale,
            title_zone_ratio=self.title_zone_ratio,
            noise_slide_ratio=self.noise_slide_ratio,
            max_title_chars=self.max_title_chars,
            extract_tables=self.extract_tables,
        )

    def grouping_config(self) -> GroupingConfig:
        """Собирает конфигурацию группировки слайдов."""
        return GroupingConfig(long_presentation_slides=self.long_presentation_slides)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Возвращает единственный экземпляр настроек приложения."""
    return Settings()
