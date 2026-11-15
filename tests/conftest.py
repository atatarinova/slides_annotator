"""Общие pytest-фикстуры."""

from pathlib import Path

import pytest
from pydantic import SecretStr

from src.core.config import Settings
from src.llm.schemas import PresentationAnnotation
from tests.helpers import (
    PRESENTATION_SLIDES,
    PROMPTS_DIR,
    create_blank_pdf,
    create_presentation,
    sample_annotation,
)


@pytest.fixture(scope="session")
def presentation_pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Тестовая PDF-презентация с колонтитулами, разделителем и продолжением."""
    directory = tmp_path_factory.mktemp("presentation")
    return create_presentation(directory / "lecture.pdf", PRESENTATION_SLIDES)


@pytest.fixture(scope="session")
def blank_pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """PDF без текстового слоя."""
    directory = tmp_path_factory.mktemp("scans")
    return create_blank_pdf(directory / "scan.pdf")


@pytest.fixture
def annotation() -> PresentationAnnotation:
    return sample_annotation()


@pytest.fixture
def settings() -> Settings:
    """Настройки без обращения к реальному LLM и без pdfplumber-таблиц."""
    return Settings(
        llm_api_key=SecretStr("test-api-key"),
        llm_model="qwen-plus",
        extract_tables=False,
        prompts_dir=PROMPTS_DIR,
        log_level="WARNING",
    )
