"""Pydantic-модели, описывающие слайды, таблицы и логические разделы."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.core.constants import UNTITLED_TITLE


class BBox(BaseModel):
    """Прямоугольник в координатах страницы (origin — левый верхний угол)."""

    model_config = ConfigDict(frozen=True)

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return max(0.0, self.x1 - self.x0)

    @property
    def height(self) -> float:
        return max(0.0, self.y1 - self.y0)

    @property
    def center_x(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def center_y(self) -> float:
        return (self.y0 + self.y1) / 2

    def contains_point(self, x: float, y: float) -> bool:
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1

    def overlaps(self, other: "BBox") -> bool:
        return (
            self.x0 < other.x1 and other.x0 < self.x1 and self.y0 < other.y1 and other.y0 < self.y1
        )

    def is_close_to(self, other: "BBox", tolerance: float) -> bool:
        """Проверяет, что все координаты отличаются не более чем на ``tolerance``."""
        return (
            abs(self.x0 - other.x0) <= tolerance
            and abs(self.y0 - other.y0) <= tolerance
            and abs(self.x1 - other.x1) <= tolerance
            and abs(self.y1 - other.y1) <= tolerance
        )


class TextBlock(BaseModel):
    """Текстовый блок слайда с метаданными шрифта и координатами."""

    text: str
    bbox: BBox
    font_size: float = Field(gt=0)
    is_bold: bool = False
    line_count: int = Field(default=1, ge=1)

    @property
    def char_count(self) -> int:
        return len(self.text.strip())

    @property
    def is_short(self) -> bool:
        return self.char_count <= 80


class ExtractedTable(BaseModel):
    """Текстовая таблица, извлеченная со слайда."""

    rows: list[list[str]] = Field(default_factory=list)
    bbox: BBox | None = None

    @field_validator("rows")
    @classmethod
    def _normalize_rows(cls, rows: list[list[str]]) -> list[list[str]]:
        if not rows:
            return rows
        width = max(len(row) for row in rows)
        normalized: list[list[str]] = []
        for row in rows:
            cells = [cell.strip() for cell in row]
            cells.extend([""] * (width - len(cells)))
            normalized.append(cells)
        return normalized

    @property
    def is_meaningful(self) -> bool:
        if len(self.rows) < 2:
            return False
        width = max((len(row) for row in self.rows), default=0)
        if width < 2:
            return False
        return any(cell for row in self.rows for cell in row)

    def to_markdown(self) -> str:
        """Представляет таблицу в виде Markdown-таблицы."""
        if not self.rows:
            return ""
        header, *body = self.rows
        lines = [
            "| " + " | ".join(header) + " |",
            "| " + " | ".join("---" for _ in header) + " |",
        ]
        lines.extend("| " + " | ".join(row) + " |" for row in body)
        return "\n".join(lines)


class RawSlide(BaseModel):
    """Слайд после извлечения текстового слоя, до эвристической обработки."""

    slide_number: int = Field(ge=1)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    blocks: list[TextBlock] = Field(default_factory=list)
    tables: list[ExtractedTable] = Field(default_factory=list)

    @property
    def text_length(self) -> int:
        return sum(block.char_count for block in self.blocks)

    @property
    def has_text(self) -> bool:
        return self.text_length > 0


class ParsedSlide(BaseModel):
    """Очищенный слайд с определенным заголовком и текстом для LLM."""

    slide_number: int = Field(ge=1)
    title: str | None = None
    title_inherited: bool = Field(
        default=False,
        description="Заголовок унаследован от предыдущего слайда (слайд без явного заголовка)",
    )
    is_title_slide: bool = False
    is_section_divider: bool = False
    is_continuation: bool = False
    body_text: str = ""

    @field_validator("title")
    @classmethod
    def _normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None

    @property
    def display_title(self) -> str:
        """Заголовок для логов и отладочного вывода."""
        title = self.title or UNTITLED_TITLE
        if self.title_inherited:
            title = f"{title} [Без заголовка / продолжение]"
        if self.is_continuation:
            title = f"{title} [продолжение]"
        return title

    @property
    def char_count(self) -> int:
        return len(self.body_text)


class SectionGroup(BaseModel):
    """Логический раздел: набор слайдов с общим заголовком."""

    section_index: int = Field(ge=1)
    title: str
    slides: list[ParsedSlide] = Field(min_length=1)

    @property
    def first_slide_number(self) -> int:
        return min(slide.slide_number for slide in self.slides)

    @property
    def last_slide_number(self) -> int:
        return max(slide.slide_number for slide in self.slides)

    @property
    def slide_range(self) -> str:
        """Человекочитаемый диапазон слайдов, например «Слайды 3–8»."""
        first, last = self.first_slide_number, self.last_slide_number
        if first == last:
            return f"Слайд {first}"
        return f"Слайды {first}–{last}"

    @property
    def char_count(self) -> int:
        return sum(slide.char_count for slide in self.slides)
