"""Pydantic-схемы HTTP API."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Ответ проверки работоспособности сервиса."""

    status: str
    model: str
