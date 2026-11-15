"""Тесты FastAPI-эндпоинтов."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.core.config import Settings
from src.core.exceptions import EmptyTextLayerError
from src.llm.schemas import PresentationAnnotation
from tests.helpers import parsed_slide, sample_annotation


class _StubPipeline:
    def __init__(self, slides: list[Any] | None = None) -> None:
        self._slides = slides or [parsed_slide(1, "Тема", is_title_slide=True)]
        self.closed = False

    def parse(self, path: Path) -> list[Any]:
        return self._slides

    async def annotate_slides(
        self, slides: list[Any], groups: list[Any] | None = None
    ) -> PresentationAnnotation:
        return sample_annotation()

    def export(self, *args: Any, **kwargs: Any) -> Path:  # pragma: no cover - не используется
        raise AssertionError("export не должен вызываться из API")

    async def aclose(self) -> None:
        self.closed = True


class _EmptyPipeline(_StubPipeline):
    def parse(self, path: Path) -> list[Any]:
        raise EmptyTextLayerError("В PDF отсутствует текстовый слой")


@pytest.fixture
def api_client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings, pipeline_factory=_StubPipeline)
    with TestClient(app) as client:
        yield client


def test_health(api_client: TestClient) -> None:
    response = api_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "model": "qwen-plus"}


def test_annotate_returns_annotation(api_client: TestClient, presentation_pdf: Path) -> None:
    response = api_client.post(
        "/annotate",
        files={"file": ("lecture.pdf", presentation_pdf.read_bytes(), "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["main_topic"] == sample_annotation().main_topic
    assert len(payload["sections"]) == 2


def test_analyze_returns_parsed_slides(settings: Settings, presentation_pdf: Path) -> None:
    app = create_app(settings, pipeline_factory=_StubPipeline)
    with TestClient(app) as client:
        response = client.post(
            "/analyze",
            files={"file": ("lecture.pdf", presentation_pdf.read_bytes(), "application/pdf")},
        )

    assert response.status_code == 200
    assert response.json()[0]["title"] == "Тема"


def test_analyze_real_pipeline(presentation_pdf: Path, settings: Settings) -> None:
    from src.pipeline import AnnotationPipeline

    app = create_app(settings, pipeline_factory=lambda: AnnotationPipeline.create(settings))
    with TestClient(app) as client:
        response = client.post(
            "/analyze",
            files={"file": ("lecture.pdf", presentation_pdf.read_bytes(), "application/pdf")},
        )

    assert response.status_code == 200
    slides = response.json()
    assert len(slides) == 6
    assert slides[0]["is_title_slide"] is True


def test_export_markdown(api_client: TestClient, presentation_pdf: Path) -> None:
    response = api_client.post(
        "/annotate/export?format=markdown",
        files={"file": ("lecture.pdf", presentation_pdf.read_bytes(), "application/pdf")},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "attachment" in response.headers["content-disposition"]
    assert response.text.startswith("# Основная тема:")


def test_export_docx(api_client: TestClient, presentation_pdf: Path) -> None:
    response = api_client.post(
        "/annotate/export?format=docx",
        files={"file": ("lecture.pdf", presentation_pdf.read_bytes(), "application/pdf")},
    )

    assert response.status_code == 200
    assert response.content.startswith(b"PK")
    assert "lecture.docx" in response.headers["content-disposition"]


def test_unsupported_export_format(api_client: TestClient, presentation_pdf: Path) -> None:
    response = api_client.post(
        "/annotate/export?format=pdf",
        files={"file": ("lecture.pdf", presentation_pdf.read_bytes(), "application/pdf")},
    )

    assert response.status_code == 400


def test_non_pdf_upload_is_rejected(api_client: TestClient) -> None:
    response = api_client.post("/annotate", files={"file": ("notes.txt", b"text", "text/plain")})

    assert response.status_code == 415


def test_empty_upload_is_rejected(api_client: TestClient) -> None:
    response = api_client.post("/annotate", files={"file": ("empty.pdf", b"", "application/pdf")})

    assert response.status_code == 400


def test_empty_text_layer_returns_422(settings: Settings, presentation_pdf: Path) -> None:
    app = create_app(settings, pipeline_factory=_EmptyPipeline)
    with TestClient(app) as client:
        response = client.post(
            "/annotate",
            files={"file": ("scan.pdf", presentation_pdf.read_bytes(), "application/pdf")},
        )

    assert response.status_code == 422
    assert "текстовый слой" in response.json()["detail"]


def test_pipeline_is_closed_on_shutdown(settings: Settings) -> None:
    pipeline = _StubPipeline()
    app = create_app(settings, pipeline_factory=lambda: pipeline)

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200

    assert pipeline.closed is True
