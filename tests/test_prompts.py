"""Тесты загрузки и рендеринга промптов."""

from pathlib import Path

import pytest

from src.core.exceptions import PromptError
from src.llm.prompts import PromptLibrary
from src.llm.schemas import SectionAnnotation
from tests.helpers import PROMPTS_DIR, parsed_slide, sample_annotation


def test_all_project_prompts_load() -> None:
    library = PromptLibrary(PROMPTS_DIR)

    for name in ("annotate_presentation", "summarize_single_section", "synthesize_presentation"):
        prompt = library.get(name)
        assert prompt.system_prompt
        assert prompt.name == name


def test_prompt_library_caches_templates() -> None:
    library = PromptLibrary(PROMPTS_DIR)

    assert library.get("annotate_presentation") is library.get("annotate_presentation")


def test_annotate_prompt_renders_flags_and_text() -> None:
    library = PromptLibrary(PROMPTS_DIR)
    prompt = library.get("annotate_presentation")
    slides = [
        parsed_slide(1, "Лекция", is_title_slide=True),
        parsed_slide(2, "Раздел", is_section_divider=True),
        parsed_slide(3, "Раздел", is_continuation=True, title_inherited=True),
    ]

    rendered = prompt.render_user(slides=slides)

    assert "[ТИТУЛЬНЫЙ СЛАЙД]" in rendered
    assert "[РАЗДЕЛИТЕЛЬ СЕКЦИИ]" in rendered
    assert "[ПРОДОЛЖЕНИЕ]" in rendered
    assert "[Без заголовка / продолжение]" in rendered


def test_section_prompt_renders() -> None:
    library = PromptLibrary(PROMPTS_DIR)
    prompt = library.get("summarize_single_section")

    rendered = prompt.render_user(
        section_title="Раздел",
        slide_range="Слайды 1–2",
        slides=[parsed_slide(1, "Раздел")],
    )

    assert "Раздел" in rendered
    assert "Слайды 1–2" in rendered


def test_synthesize_prompt_renders() -> None:
    library = PromptLibrary(PROMPTS_DIR)
    prompt = library.get("synthesize_presentation")
    annotation = sample_annotation()

    rendered = prompt.render_user(
        section_drafts=annotation.sections,
        slide_count=6,
        title_slide=parsed_slide(1, "Лекция", is_title_slide=True),
    )

    assert "Всего слайдов: 6" in rendered
    assert annotation.sections[0].section_title in rendered


def test_unknown_prompt_raises() -> None:
    library = PromptLibrary(PROMPTS_DIR)

    with pytest.raises(PromptError, match="не найден"):
        library.get("missing_prompt")


def test_invalid_prompt_structure_raises(tmp_path: Path) -> None:
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "broken.yaml").write_text("name: broken\n", encoding="utf-8")

    with pytest.raises(PromptError, match="Некорректная структура"):
        PromptLibrary(prompts_dir).get("broken")


def test_missing_template_variable_raises() -> None:
    library = PromptLibrary(PROMPTS_DIR)
    prompt = library.get("synthesize_presentation")

    with pytest.raises(PromptError, match="отрендерить"):
        prompt.render_user(
            section_drafts=[],
            slide_count=1,
            title_slide=SectionAnnotation(section_title="x", slide_range="y", section_summary="z"),
        )
