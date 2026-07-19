"""Deterministic package hashing for the narrow M6 SEC pilot approval."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import Field

from .models import StrictModel, canonical_digest


class M6PilotPackageError(RuntimeError):
    """The human-approval package must be complete, stable and repo-local."""


class M6PilotPackageDigest(StrictModel):
    package_ref: str = Field(min_length=1)
    package_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    file_sha256: dict[str, str]


def compute_m6_pilot_package(*, root: Path, manifest_path: Path) -> M6PilotPackageDigest:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise M6PilotPackageError("m6_pilot_package_manifest_unreadable") from exc
    package_ref = str(manifest.get("package_ref") or "")
    paths = tuple(str(path) for path in manifest.get("included_paths", ()))
    if not package_ref or not paths or len(paths) != len(set(paths)):
        raise M6PilotPackageError("m6_pilot_package_manifest_invalid")
    resolved_root = root.resolve()
    hashes: dict[str, str] = {}
    for relative in paths:
        path = (root / relative).resolve()
        if resolved_root not in path.parents or not path.is_file():
            raise M6PilotPackageError(f"m6_pilot_package_path_invalid:{relative}")
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    package_digest = canonical_digest(
        {
            "package_ref": package_ref,
            "manifest": manifest,
            "manifest_digest": manifest_digest,
            "file_sha256": hashes,
        }
    )
    return M6PilotPackageDigest(
        package_ref=package_ref,
        package_digest=package_digest,
        manifest_digest=manifest_digest,
        file_sha256=hashes,
    )
