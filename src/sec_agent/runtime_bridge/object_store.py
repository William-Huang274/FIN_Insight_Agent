from __future__ import annotations

import hashlib
import json
import mimetypes
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OBJECT_STORE_SCHEMA_VERSION = "finsight_object_store_ref_v0_1"


def put_object(
    source_path: str | Path,
    *,
    object_store_root: str | Path,
    namespace: str = "runtime",
    artifact_type: str = "",
) -> dict[str, Any]:
    source = Path(source_path).resolve()
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(str(source))
    digest = _sha256_file(source)
    suffix = source.suffix
    root = Path(object_store_root).resolve()
    target_dir = root / namespace / digest[:2] / digest[2:4]
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{digest}{suffix}"
    if not target.exists():
        shutil.copy2(source, target)
    ref = _object_ref(
        target,
        source_path=str(source),
        namespace=namespace,
        artifact_type=artifact_type or _artifact_type(source),
        sha256=digest,
    )
    manifest = target.with_suffix(target.suffix + ".ref.json")
    manifest.write_text(json.dumps(ref, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return ref


def put_json_object(
    payload: Any,
    *,
    object_store_root: str | Path,
    namespace: str = "runtime",
    artifact_type: str = "json",
    stem: str = "payload",
) -> dict[str, Any]:
    root = Path(object_store_root).resolve()
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(serialized).hexdigest()
    target_dir = root / namespace / digest[:2] / digest[2:4]
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{stem}_{digest}.json"
    if not target.exists():
        target.write_bytes(serialized + b"\n")
    ref = _object_ref(target, source_path="", namespace=namespace, artifact_type=artifact_type, sha256=digest)
    manifest = target.with_suffix(target.suffix + ".ref.json")
    manifest.write_text(json.dumps(ref, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return ref


def read_object_ref(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _object_ref(target: Path, *, source_path: str, namespace: str, artifact_type: str, sha256: str) -> dict[str, Any]:
    return {
        "schema_version": OBJECT_STORE_SCHEMA_VERSION,
        "artifact_uri": str(target.resolve()),
        "source_path": source_path,
        "namespace": namespace,
        "artifact_type": artifact_type,
        "sha256": sha256,
        "byte_size": target.stat().st_size,
        "mime_type": mimetypes.guess_type(str(target))[0] or "",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "storage_policy": "content_addressed_local_or_minio_compatible_ref_v0_1",
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_type(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    return suffix or "binary"
