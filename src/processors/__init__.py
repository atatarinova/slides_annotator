"""Эвристическая обработка извлеченного текста презентации."""

from src.processors.grouping import SlideGrouper
from src.processors.heading_detector import HeadingDetector
from src.processors.noise_filter import NoiseFilter
from src.processors.reading_order import order_blocks

__all__ = ["HeadingDetector", "NoiseFilter", "SlideGrouper", "order_blocks"]
