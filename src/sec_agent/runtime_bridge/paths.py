from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimePathRegistry:
    repo_root: Path
    script_root: Path
    primary_data_root: Path
    secondary_data_roots: tuple[Path, ...]
    object_store_root: Path
    workbench_private_root: Path
    milvus_mode: str
    milvus_note: str

    def as_dict(self) -> dict[str, object]:
        return {
            "repo_root": str(self.repo_root),
            "script_root": str(self.script_root),
            "primary_data_root": str(self.primary_data_root),
            "secondary_data_roots": [str(path) for path in self.secondary_data_roots],
            "object_store_root": str(self.object_store_root),
            "workbench_private_root": str(self.workbench_private_root),
            "milvus_mode": self.milvus_mode,
            "milvus_note": self.milvus_note,
            "path_policy": "multi_root_no_hardcoded_migration_v0_1",
        }


def resolve_runtime_paths(repo_root: str | Path | None = None) -> RuntimePathRegistry:
    root = Path(repo_root or os.environ.get("FIN_REPO_ROOT") or Path.cwd()).resolve()
    primary = Path(os.environ.get("FINSIGHT_DATA_ROOT") or root / "data").resolve()
    secondary = tuple(
        Path(value).resolve()
        for value in _split_path_list(os.environ.get("FINSIGHT_SECONDARY_DATA_ROOTS", ""))
        if value.strip()
    )
    object_store = Path(os.environ.get("FINSIGHT_OBJECT_STORE_ROOT") or primary / "object_store").resolve()
    workbench_private = Path(os.environ.get("FINSIGHT_WORKBENCH_PRIVATE_ROOT") or primary / "workbench_private").resolve()
    milvus_mode = os.environ.get("FINSIGHT_MILVUS_MODE", "unbound_cloud_deferred").strip() or "unbound_cloud_deferred"
    milvus_note = os.environ.get(
        "FINSIGHT_MILVUS_NOTE",
        "Milvus remains an optional semantic supplement; cloud collection binding is deferred until runtime is available.",
    )
    return RuntimePathRegistry(
        repo_root=root,
        script_root=root,
        primary_data_root=primary,
        secondary_data_roots=secondary,
        object_store_root=object_store,
        workbench_private_root=workbench_private,
        milvus_mode=milvus_mode,
        milvus_note=milvus_note,
    )


def _split_path_list(value: str) -> list[str]:
    if not value:
        return []
    separator = ";" if ";" in value else os.pathsep
    return [part for part in value.split(separator) if part.strip()]
