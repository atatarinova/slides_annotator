# Система автоматического аннотирования лекционных PDF-презентаций

Извлекает текстовый слой PDF, очищает его от колонтитулов и мусора верстки,
восстанавливает порядок чтения, группирует слайды в логические разделы и генерирует
структурированную аннотацию через текстовую LLM (OpenAI-совместимый API, например Qwen).

## Возможности

- Извлечение текстовых блоков, заголовков и текстовых таблиц (`PyMuPDF` + `pdfplumber`).
- Медианный размер шрифта основного текста, позиционные эвристики заголовков.
- Определение титульного слайда, разделителей секций и слайдов-продолжений.
- Удаление повторяющихся колонтитулов, номеров слайдов и рамок верстки (> 40 % слайдов).
- Восстановление порядка чтения с поддержкой двухколоночной верстки.
- Один проход LLM для коротких презентаций и map-reduce (по разделам) для длинных (50+ слайдов).
- Structured Outputs с валидацией Pydantic v2, ретраи, ограничение конкурентности,
  фолбэк на JSON-режим для провайдеров без поддержки JSON Schema.
- Экспорт в Markdown, JSON, TXT и DOCX.
- CLI и FastAPI-сервис.

## Установка

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Для PDF с кириллицей в тестах используется шрифт DejaVu (пакет `fonts-dejavu` в Debian/Ubuntu).

## Настройка

Переменные окружения с префиксом `ANNOTATE_` (можно положить в `.env`):

| Переменная | Назначение | По умолчанию |
| --- | --- | --- |
| `ANNOTATE_LLM_API_KEY` | API-ключ (также читаются `DASHSCOPE_API_KEY`, `OPENAI_API_KEY`, `QWEN_API_KEY`) | — |
| `ANNOTATE_LLM_MODEL` | Модель | `qwen-plus` |
| `ANNOTATE_LLM_BASE_URL` | Базовый URL OpenAI-совместимого API | DashScope compatible-mode |
| `ANNOTATE_LLM_TEMPERATURE` | Температура генерации | `0.1` |
| `ANNOTATE_LLM_MAX_CONCURRENCY` | Лимит одновременных запросов | `4` |
| `ANNOTATE_LLM_MAX_RETRIES` | Число попыток при сетевых ошибках | `3` |
| `ANNOTATE_LONG_PRESENTATION_SLIDES` | Порог перехода на map-reduce | `50` |
| `ANNOTATE_NOISE_SLIDE_RATIO` | Доля слайдов для фильтрации повторов | `0.4` |
| `ANNOTATE_PROMPTS_DIR` | Директория промптов | `./prompts` |
| `ANNOTATE_LOG_LEVEL` | Уровень логирования | `INFO` |

## CLI

```bash
# Разбор PDF без обращения к LLM (удобно для отладки эвристик)
article-annotate analyze data/lecture.pdf -o data/slides.json

# Генерация аннотации в Markdown
article-annotate annotate data/lecture.pdf -o data/annotation.md

# JSON / TXT / DOCX
article-annotate annotate data/lecture.pdf -o data/annotation.json
article-annotate annotate data/lecture.pdf -o data/annotation.docx

# Другая модель
article-annotate annotate data/lecture.pdf --model qwen-max

# HTTP-сервис
article-annotate serve --host 0.0.0.0 --port 8000
```

Также доступен запуск через модуль: `python -m src annotate ...`.

## HTTP API

- `GET /health` — статус сервиса и имя модели.
- `POST /analyze` — загрузить PDF и получить очищенные слайды без вызова LLM.
- `POST /annotate` — загрузить PDF и получить JSON-аннотацию (`main_topic`, `sections`).
- `POST /annotate/export?format=markdown|json|txt|docx` — скачать готовый файл.

```bash
curl -F "file=@data/lecture.pdf" http://127.0.0.1:8000/annotate
curl -F "file=@data/lecture.pdf" "http://127.0.0.1:8000/annotate/export?format=docx" -o annotation.docx
```

## Структура проекта

```text
src/
  core/        конфигурация, логирование, модели Pydantic, исключения
  parsers/     PyMuPDF-блоки, метаданные шрифтов, таблицы pdfplumber
  processors/  порядок чтения, фильтрация шума, заголовки, группировка
  llm/         клиент, промпты, схемы аннотации, map-reduce оркестратор
  exporters/   Markdown, JSON, TXT, DOCX
  api/         FastAPI-приложение
  pipeline.py  сквозной конвейер
  cli.py       командная строка
prompts/       YAML-шаблоны промптов (Jinja2)
tests/         unit- и интеграционные тесты
```

Промпты не зашиваются в код: все системные инструкции лежат в `prompts/*.yaml`.

## Проверка качества

```bash
ruff check . && ruff format --check .
pytest tests/
mypy src/
```
