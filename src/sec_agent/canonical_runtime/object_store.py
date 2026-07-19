from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any


class ObjectDigestMismatch(RuntimeError):
    pass


class FileCanonicalObjectStore:
    """Content-addressed store whose portable identity never contains an absolute path."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put_json(self, payload: Any, *, namespace: str, artifact_type: str) -> dict[str, Any]:
        data = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()
        digest = hashlib.sha256(data).hexdigest()
        key = PurePosixPath(namespace) / digest[:2] / digest[2:4] / f"{digest}.json"
        target = self._resolve_key(str(key))
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(data)
        return {
            "object_key": str(key),
            "digest": digest,
            "byte_size": len(data),
            "media_type": "application/json",
            "artifact_type": artifact_type,
        }

    def get_json(self, object_key: str, *, expected_digest: str | None = None) -> Any:
        data = self._resolve_key(object_key).read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if expected_digest and digest != expected_digest:
            raise ObjectDigestMismatch("object_digest_mismatch")
        return json.loads(data)

    def _resolve_key(self, object_key: str) -> Path:
        relative = Path(PurePosixPath(object_key))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("portable_relative_object_key_required")
        target = (self.root / relative).resolve()
        target.relative_to(self.root)
        return target
