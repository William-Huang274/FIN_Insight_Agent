from __future__ import annotations

import json
import os
import re
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONTEXT_STORE_SCHEMA_VERSION = "sec_agent_context_store_v0.1"


@dataclass
class JsonContextStore:
    """Small JSON-backed store for user-level context metadata.

    The session files remain the source of truth for analyses and artifacts.
    This store only keeps user-level routing state such as the active session.
    """

    root: Path

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def load_user_profile(self, *, tenant_id: str, user_id: str) -> dict[str, Any]:
        path = self.user_profile_path(tenant_id=tenant_id, user_id=user_id)
        if path.exists():
            payload = _read_json(path)
            payload.setdefault("schema_version", CONTEXT_STORE_SCHEMA_VERSION)
            payload.setdefault("tenant_id", str(tenant_id or ""))
            payload.setdefault("user_id", str(user_id or ""))
            payload.setdefault("preferences", {})
            payload.setdefault("active_session_id", "")
            payload.setdefault("recent_session_ids", [])
            payload.setdefault("last_references", {})
            return payload
        return {
            "schema_version": CONTEXT_STORE_SCHEMA_VERSION,
            "tenant_id": str(tenant_id or ""),
            "user_id": str(user_id or ""),
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
            "preferences": {
                "language": "zh",
                "default_source_policy": "SEC_ONLY_10K",
                "preferred_output": "investment_memo",
                "risk_tone": "conservative",
            },
            "active_session_id": "",
            "recent_session_ids": [],
            "last_references": {},
        }

    def save_user_profile(self, profile: dict[str, Any]) -> Path:
        profile = dict(profile)
        profile["schema_version"] = CONTEXT_STORE_SCHEMA_VERSION
        profile["updated_at"] = _utc_now()
        profile.setdefault("created_at", profile["updated_at"])
        path = self.user_profile_path(
            tenant_id=str(profile.get("tenant_id") or ""),
            user_id=str(profile.get("user_id") or ""),
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(profile, ensure_ascii=False, indent=2) + "\n"
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=str(path.parent),
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_path = Path(handle.name)
            handle.write(text)
        _replace_with_retry(tmp_path, path)
        return path

    def user_profile_path(self, *, tenant_id: str, user_id: str) -> Path:
        return self.root / "users" / _safe_id(tenant_id) / f"{_safe_id(user_id)}.json"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _replace_with_retry(source: Path, target: Path, *, attempts: int = 6, delay_s: float = 0.02) -> None:
    last_error: PermissionError | None = None
    for attempt in range(max(int(attempts), 1)):
        try:
            os.replace(source, target)
            return
        except PermissionError as exc:
            last_error = exc
            time.sleep(delay_s * (attempt + 1))
    raise last_error or PermissionError(f"could not replace {target}")


def _safe_id(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    return text[:120] or "default"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
