"""Mature-runtime vertical slices for the current FIN Insight product.

Agent dependencies live in an optional installation profile.  Keeping this
package initializer lazy lets the read-only Workbench import the shared runtime
configuration without silently loading LangGraph or a model provider.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


_GRAPH_EXPORTS = {
    "DellReferenceVerticalDependencies",
    "DellReferenceVerticalGraphError",
    "DellReferenceVerticalGraphInput",
    "GRAPH_CONTRACT_VERSION",
    "build_dell_reference_vertical_state_graph",
}


def __getattr__(name: str) -> Any:
    if name not in _GRAPH_EXPORTS:
        raise AttributeError(name)
    value = getattr(import_module(".dell_reference_vertical_graph", __name__), name)
    globals()[name] = value
    return value

__all__ = [
    "DellReferenceVerticalDependencies",
    "DellReferenceVerticalGraphError",
    "DellReferenceVerticalGraphInput",
    "GRAPH_CONTRACT_VERSION",
    "build_dell_reference_vertical_state_graph",
]
