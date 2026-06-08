from __future__ import annotations

from uuid import uuid4


def new_trace_id() -> str:
    return f"trace_{uuid4().hex[:24]}"
