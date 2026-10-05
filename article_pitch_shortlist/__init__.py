"""Public API for Article Pitch Shortlist."""

from .core import (
    EvaluationResult,
    InputError,
    analyze,
    draft_pitch,
    evaluate_publisher,
    normalize_publisher_host,
    same_publisher_host,
    validate_publisher_sources,
)

__all__ = [
    "EvaluationResult", "InputError", "analyze", "draft_pitch", "evaluate_publisher",
    "normalize_publisher_host", "same_publisher_host", "validate_publisher_sources",
]
__version__ = "0.1.0"
