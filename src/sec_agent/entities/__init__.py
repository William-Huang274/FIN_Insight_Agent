"""Entity resolution helpers for FinSight agent data contracts."""

from .entity_resolution import (
    ENTITY_RESOLUTION_SCHEMA_VERSION,
    build_entity_alias_registry,
    normalize_entity_name,
    resolve_entity_name,
)

__all__ = [
    "ENTITY_RESOLUTION_SCHEMA_VERSION",
    "build_entity_alias_registry",
    "normalize_entity_name",
    "resolve_entity_name",
]
