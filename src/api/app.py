"""FastAPI-приложение для аннотирования загруженных PDF-презентаций."""

import asyncio
import tempfile
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import Response

from src.api.schemas import HealthResponse
from src.core.config import Settings, get_settings
from src.core.exceptions import (
    EmptyTextLayerError,
    LLMConfigurationError,
    LLMGenerationError,
    PDFParsingError,
    UnsupportedFormatError,
)
from src.core.logging import configure_logging, get_logger
from src.core.models import ParsedSlide
from src.exporters import media_type, render_annotation, resolve_format, suffix_for
from src.llm.schemas import PresentationAnnotation
from src.pipeline import AnnotationPipeline

logger = get_logger(__name__)

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
UPLOAD_CHUNK_SIZE = 1024 * 1024

PipelineFactory = Callable[[], AnnotationPipeline]


def create_app(
    settings: Settings | None = None,
    pipeline_factory: PipelineFactory | None = None,
) -> FastAPI:
    """Создает FastAPI-приложение с ленивой инициализацией конвейера."""
    resolved = settings or get_settings()
    configure_logging(resolved.log_level)
    factory: PipelineFactory = pipeline_factory or (lambda: AnnotationPipeline.create(resolved))

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.pipeline = factory()
        try:
            yield
        finally:
            await application.state.pipeline.aclose()

    app = FastAPI(
        title="Article Annotation API",
        description="Аннотирование текстового слоя лекционных PDF-презентаций",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", model=resolved.llm_model)

    @app.post("/analyze", response_model=list[ParsedSlide])
    async def analyze(
        file: Annotated[UploadFile, File(description="PDF-презентация")],
    ) -> list[ParsedSlide]:
        """Возвращает очищенные слайды без обращения к LLM."""
        async with _uploaded_pdf(file) as path:
            try:
                return await asyncio.to_thread(app.state.pipeline.parse, path)
            except EmptyTextLayerError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            except PDFParsingError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/annotate", response_model=PresentationAnnotation)
    async def annotate(
        file: Annotated[UploadFile, File(description="PDF-презентация")],
    ) -> PresentationAnnotation:
        """Генерирует структурированную аннотацию презентации."""
        async with _uploaded_pdf(file) as path:
            return await _annotate_path(app, path)

    @app.post("/annotate/export")
    async def annotate_export(
        file: Annotated[UploadFile, File(description="PDF-презентация")],
        format_name: Annotated[str, Query(alias="format")] = "markdown",
    ) -> Response:
        """Генерирует аннотацию и сразу отдает ее в выбранном формате."""
        try:
            resolved_format = resolve_format(format_name)
        except UnsupportedFormatError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        stem = Path(file.filename or "annotation").stem or "annotation"
        async with _uploaded_pdf(file) as path:
            annotation = await _annotate_path(app, path)
            payload = render_annotation(annotation, resolved_format)

        return Response(
            content=payload,
            media_type=media_type(resolved_format),
            headers={
                "Content-Disposition": f'attachment; filename="{stem}{suffix_for(resolved_format)}"'
            },
        )

    return app


async def _annotate_path(app: FastAPI, path: Path) -> PresentationAnnotation:
    pipeline: AnnotationPipeline = app.state.pipeline
    try:
        slides = await asyncio.to_thread(pipeline.parse, path)
        return await pipeline.annotate_slides(slides)
    except (EmptyTextLayerError, PDFParsingError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@asynccontextmanager
async def _uploaded_pdf(file: UploadFile) -> AsyncIterator[Path]:
    filename = file.filename or ""
    if Path(filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=415, detail="Ожидается PDF-файл")

    with tempfile.TemporaryDirectory(prefix="article-annotation-") as tmp_dir:
        path = Path(tmp_dir) / "upload.pdf"
        size = 0
        try:
            with path.open("wb") as handle:
                while chunk := await file.read(UPLOAD_CHUNK_SIZE):
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        raise HTTPException(
                            status_code=413,
                            detail=f"Файл превышает лимит {MAX_UPLOAD_BYTES // (1024 * 1024)} МБ",
                        )
                    handle.write(chunk)
        finally:
            await file.close()

        if size == 0:
            raise HTTPException(status_code=400, detail="Загружен пустой файл")
        logger.info("Получен файл %s (%d байт)", filename, size)
        yield path


app = create_app()
