from __future__ import annotations

"""Small, auditable environment-file loader for admitted data connectors."""

import os
from pathlib import Path


def load_env_file(path: str | Path, *, override: bool = False) -> list[str]:
    env_path = Path(path)
    if not env_path.exists():
        return []
    loaded: list[str] = []
    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        if override or not os.environ.get(key):
            os.environ[key] = _strip_quotes(value.strip())
            loaded.append(key)
    return loaded


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


__all__ = ["load_env_file"]
