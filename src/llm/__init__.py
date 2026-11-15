"""Клиенты LLM, промпты и схемы итоговой аннотации."""

from src.llm.annotator import PresentationAnnotator
from src.llm.client import AsyncLLMClient
from src.llm.prompts import PromptLibrary, PromptTemplate
from src.llm.schemas import PresentationAnnotation, SectionAnnotation

__all__ = [
    "AsyncLLMClient",
    "PresentationAnnotation",
    "PresentationAnnotator",
    "PromptLibrary",
    "PromptTemplate",
    "SectionAnnotation",
]
