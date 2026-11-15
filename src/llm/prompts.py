"""Загрузка и рендеринг шаблонов промптов из директории ``prompts/``."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jinja2 import StrictUndefined, Template, TemplateError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.core.exceptions import PromptError


class PromptFile(BaseModel):
    """Структура YAML-файла промпта."""

    model_config = ConfigDict(extra="ignore")

    name: str
    description: str = ""
    version: str = "1.0"
    system_prompt: str = Field(min_length=1)
    user_prompt_template: str = Field(min_length=1)


@dataclass(frozen=True)
class PromptTemplate:
    """Готовый к использованию шаблон промпта."""

    name: str
    system_prompt: str
    user_template: Template

    def render_user(self, **context: Any) -> str:
        """Рендерит пользовательскую часть промпта."""
        try:
            return self.user_template.render(**context).strip()
        except TemplateError as exc:
            raise PromptError(f"Не удалось отрендерить промпт {self.name!r}: {exc}") from exc


class PromptLibrary:
    """Читает и кеширует промпты из указанной директории."""

    def __init__(self, prompts_dir: Path) -> None:
        self._prompts_dir = prompts_dir
        self._cache: dict[str, PromptTemplate] = {}

    @property
    def prompts_dir(self) -> Path:
        return self._prompts_dir

    def get(self, name: str) -> PromptTemplate:
        """Возвращает промпт по имени файла без расширения."""
        if name in self._cache:
            return self._cache[name]

        path = self._prompts_dir / f"{name}.yaml"
        if not path.is_file():
            raise PromptError(f"Файл промпта не найден: {path}")

        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise PromptError(f"Не удалось прочитать промпт {path}: {exc}") from exc

        if not isinstance(payload, dict):
            raise PromptError(f"Промпт {path} должен содержать YAML-словарь")

        try:
            prompt_file = PromptFile.model_validate(payload)
        except ValidationError as exc:
            raise PromptError(f"Некорректная структура промпта {path}: {exc}") from exc

        template = PromptTemplate(
            name=prompt_file.name,
            system_prompt=prompt_file.system_prompt.strip(),
            user_template=Template(prompt_file.user_prompt_template, undefined=StrictUndefined),
        )
        self._cache[name] = template
        return template
