"""Portable code, data, capture and artifact path ownership."""

from .paths import RuntimePathRegistry, resolve_runtime_paths

__all__ = ["RuntimePathRegistry", "resolve_runtime_paths"]
