"""Тесты командной строки."""

import json
from pathlib import Path
from typing import Any

import pytest

from src.cli import main
from src.core.config import Settings
from src.exporters import render_markdown
from src.llm.schemas import PresentationAnnotation
from tests.helpers import sample_annotation


def test_analyze_command_writes_json(presentation_pdf: Path, tmp_path: Path) -> None:
    output = tmp_path / "slides.json"

    code = main(["analyze", str(presentation_pdf), "-o", str(output), "--log-level", "ERROR"])

    assert code == 0
    slides = json.loads(output.read_text(encoding="utf-8"))
    assert len(slides) == 6
    assert slides[0]["title"] == "Машинное обучение"
    assert slides[0]["is_title_slide"] is True


def test_analyze_command_prints_to_stdout(
    presentation_pdf: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["analyze", str(presentation_pdf), "--log-level", "ERROR"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload) == 6


def test_missing_file_returns_error_code(tmp_path: Path) -> None:
    code = main(["analyze", str(tmp_path / "missing.pdf"), "--log-level", "ERROR"])

    assert code == 1


def test_annotate_command_writes_markdown(
    presentation_pdf: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _StubPipeline:
        async def annotate(self, pdf: Path) -> PresentationAnnotation:
            return sample_annotation()

        def export(
            self,
            annotation: PresentationAnnotation,
            destination: Path,
            format_name: str | None = None,
        ) -> Path:
            destination.write_text(render_markdown(annotation), encoding="utf-8")
            return destination

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(
        "src.cli.AnnotationPipeline.create",
        lambda settings=None: _StubPipeline(),
    )
    output = tmp_path / "annotation.md"

    code = main(["annotate", str(presentation_pdf), "-o", str(output), "--log-level", "ERROR"])

    assert code == 0
    assert output.read_text(encoding="utf-8").startswith("# Основная тема:")


def test_annotate_command_prints_markdown_to_stdout(
    presentation_pdf: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class _StubPipeline:
        async def annotate(self, pdf: Path) -> PresentationAnnotation:
            return sample_annotation()

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr("src.cli.AnnotationPipeline.create", lambda settings=None: _StubPipeline())

    code = main(["annotate", str(presentation_pdf), "--log-level", "ERROR"])

    assert code == 0
    assert capsys.readouterr().out.startswith("# Основная тема:")


def test_required_subcommand() -> None:
    with pytest.raises(SystemExit):
        main([])


def test_settings_override_model(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class _StubPipeline:
        async def annotate(self, pdf: Path) -> PresentationAnnotation:
            return sample_annotation()

        async def aclose(self) -> None:
            return None

    def _create(settings: Settings | None = None) -> _StubPipeline:
        captured["model"] = settings.llm_model if settings else None
        return _StubPipeline()

    monkeypatch.setattr("src.cli.AnnotationPipeline.create", _create)
    monkeypatch.setattr("src.cli.render_annotation", lambda annotation, fmt: "# ok\n")

    code = main(["annotate", "lecture.pdf", "--model", "qwen-max", "--log-level", "ERROR"])

    assert code == 0
    assert captured["model"] == "qwen-max"
