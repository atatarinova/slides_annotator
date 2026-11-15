"""CLI для аннотирования лекционных PDF-презентаций."""

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from src.core.config import LOG_LEVELS, Settings, get_settings
from src.core.constants import EXPORT_FORMATS
from src.core.exceptions import AnnotationError, ExportError
from src.core.logging import configure_logging, get_logger
from src.exporters import render_annotation
from src.llm.schemas import PresentationAnnotation
from src.pipeline import AnnotationPipeline

logger = get_logger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Создает парсер аргументов командной строки."""
    parser = argparse.ArgumentParser(
        prog="article-annotate",
        description="Автоматическое аннотирование текстового слоя лекционных PDF-презентаций",
    )
    parser.add_argument("--log-level", choices=sorted(LOG_LEVELS), default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)

    annotate = subparsers.add_parser("annotate", help="Сгенерировать аннотацию презентации")
    _add_log_level(annotate)
    annotate.add_argument("pdf", type=Path, help="Путь к PDF-файлу")
    annotate.add_argument("-o", "--output", type=Path, help="Куда сохранить результат")
    annotate.add_argument(
        "-f",
        "--format",
        choices=EXPORT_FORMATS,
        default=None,
        help="Формат результата (по умолчанию — по расширению файла или Markdown)",
    )
    annotate.add_argument("--model", default=None, help="Имя LLM-модели (например, qwen-plus)")
    annotate.add_argument("--no-tables", action="store_true", help="Не извлекать текстовые таблицы")
    annotate.add_argument(
        "--slides-json",
        type=Path,
        default=None,
        help="Дополнительно сохранить разобранные слайды в JSON",
    )

    analyze = subparsers.add_parser("analyze", help="Разобрать PDF без вызова LLM")
    _add_log_level(analyze)
    analyze.add_argument("pdf", type=Path, help="Путь к PDF-файлу")
    analyze.add_argument("-o", "--output", type=Path, help="Куда сохранить JSON со слайдами")

    serve = subparsers.add_parser("serve", help="Запустить FastAPI-сервис")
    _add_log_level(serve)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")

    return parser


def _add_log_level(parser: argparse.ArgumentParser) -> None:
    """Добавляет --log-level и после имени подкоманды, не затирая глобальное значение."""
    parser.add_argument(
        "--log-level",
        choices=sorted(LOG_LEVELS),
        default=argparse.SUPPRESS,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Точка входа CLI."""
    args = build_parser().parse_args(argv)
    settings = get_settings()
    overrides: dict[str, object] = {}
    if args.log_level:
        overrides["log_level"] = args.log_level
    if getattr(args, "model", None):
        overrides["llm_model"] = args.model
    if getattr(args, "no_tables", False):
        overrides["extract_tables"] = False
    if overrides:
        settings = settings.model_copy(update=overrides)
    configure_logging(settings.log_level)

    try:
        if args.command == "serve":
            return _serve(args, settings)
        pipeline = AnnotationPipeline.create(settings)
        if args.command == "analyze":
            return _analyze(pipeline, args, settings)
        return _annotate(pipeline, args, settings)
    except AnnotationError as exc:
        logger.error("%s", exc)
        return 1


def _analyze(pipeline: AnnotationPipeline, args: argparse.Namespace, settings: Settings) -> int:
    slides = pipeline.parse(args.pdf)
    payload = json.dumps(
        [slide.model_dump(mode="json") for slide in slides], ensure_ascii=False, indent=2
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
        print(f"Разобранные слайды сохранены: {args.output}")
    else:
        print(payload)
    logger.info("Проверка LLM не выполнялась; модель для аннотирования: %s", settings.llm_model)
    return 0


def _annotate(pipeline: AnnotationPipeline, args: argparse.Namespace, settings: Settings) -> int:
    annotation = asyncio.run(_annotate_async(pipeline, args.pdf))
    logger.info("Аннотация готова: %d разделов", len(annotation.sections))

    if args.slides_json:
        slides = pipeline.parse(args.pdf)
        args.slides_json.parent.mkdir(parents=True, exist_ok=True)
        args.slides_json.write_text(
            json.dumps(
                [slide.model_dump(mode="json") for slide in slides],
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    if args.output:
        path = pipeline.export(annotation, args.output, args.format)
        print(f"Аннотация сохранена: {path}")
    else:
        payload = render_annotation(annotation, args.format or "markdown")
        if isinstance(payload, bytes):
            raise ExportError(
                "Двоичный формат требует указания --output (например, --output result.docx)"
            )
        print(payload, end="")
    logger.debug("Использована модель: %s", settings.llm_model)
    return 0


async def _annotate_async(pipeline: AnnotationPipeline, pdf: Path) -> PresentationAnnotation:
    try:
        return await pipeline.annotate(pdf)
    finally:
        await pipeline.aclose()


def _serve(args: argparse.Namespace, settings: Settings) -> int:
    import uvicorn

    from src.api.app import create_app

    if args.reload:
        uvicorn.run(
            "src.api.app:create_app",
            factory=True,
            host=args.host,
            port=args.port,
            reload=True,
        )
    else:
        uvicorn.run(create_app(settings), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
