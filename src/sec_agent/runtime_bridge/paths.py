from __future__ import annotations

import os
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RuntimePathRegistry:
    repo_root: Path
    script_root: Path
    primary_data_root: Path
    secondary_data_roots: tuple[Path, ...]
    object_store_root: Path
    reviewed_evidence_root: Path
    workbench_private_root: Path
    milvus_mode: str
    milvus_note: str
    milvus_db_path: Path | None = None
    milvus_collection_name: str = ""
    milvus_embedding_model: str = ""
    milvus_vector_count: int | None = None
    milvus_vector_kinds: tuple[str, ...] = ()
    milvus_config_path: Path | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "repo_root": str(self.repo_root),
            "script_root": str(self.script_root),
            "primary_data_root": str(self.primary_data_root),
            "secondary_data_roots": [str(path) for path in self.secondary_data_roots],
            "object_store_root": str(self.object_store_root),
            "reviewed_evidence_root": str(self.reviewed_evidence_root),
            "workbench_private_root": str(self.workbench_private_root),
            "milvus_mode": self.milvus_mode,
            "milvus_note": self.milvus_note,
            "milvus_config_path": str(self.milvus_config_path) if self.milvus_config_path else "",
            "milvus_db_path": str(self.milvus_db_path) if self.milvus_db_path else "",
            "milvus_collection_name": self.milvus_collection_name,
            "milvus_embedding_model": self.milvus_embedding_model,
            "milvus_vector_count": self.milvus_vector_count,
            "milvus_vector_kinds": list(self.milvus_vector_kinds),
            "path_policy": "multi_root_no_hardcoded_migration_v0_1",
        }


def resolve_runtime_paths(repo_root: str | Path | None = None) -> RuntimePathRegistry:
    root = Path(repo_root or os.environ.get("FIN_REPO_ROOT") or Path.cwd()).resolve()
    milvus_config_path = _resolve_optional_path(os.environ.get("FINSIGHT_MILVUS_RUNTIME_CONFIG"), root=root)
    milvus_config = _load_json_config(milvus_config_path)
    primary = Path(os.environ.get("FINSIGHT_DATA_ROOT") or root / "data").resolve()
    secondary = tuple(
        Path(value).resolve()
        for value in _split_path_list(os.environ.get("FINSIGHT_SECONDARY_DATA_ROOTS", ""))
        if value.strip()
    )
    object_store = Path(os.environ.get("FINSIGHT_OBJECT_STORE_ROOT") or primary / "object_store").resolve()
    reviewed_evidence = Path(
        os.environ.get("FINSIGHT_REVIEWED_EVIDENCE_ROOT")
        or primary / "workbench_private"
    ).resolve()
    workbench_private = Path(os.environ.get("FINSIGHT_WORKBENCH_PRIVATE_ROOT") or primary / "workbench_private").resolve()
    milvus_mode = (
        os.environ.get("FINSIGHT_MILVUS_MODE")
        or str(milvus_config.get("mode") or milvus_config.get("status") or "")
        or "unbound_cloud_deferred"
    ).strip() or "unbound_cloud_deferred"
    milvus_note = os.environ.get(
        "FINSIGHT_MILVUS_NOTE",
        str(milvus_config.get("note") or "")
        or "Milvus remains an optional semantic supplement; cloud collection binding is deferred until runtime is available.",
    )
    milvus_db_path = _resolve_optional_path(
        os.environ.get("MILVUS_DB_PATH") or os.environ.get("FINSIGHT_MILVUS_DB_PATH") or str(milvus_config.get("db_path") or ""),
        root=root,
    )
    milvus_collection_name = (
        os.environ.get("MILVUS_COLLECTION_NAME")
        or os.environ.get("MILVUS_COLLECTION")
        or str(milvus_config.get("collection_name") or milvus_config.get("collection") or "")
    ).strip()
    milvus_embedding_model = (
        os.environ.get("MILVUS_EMBEDDING_MODEL")
        or os.environ.get("FINSIGHT_MILVUS_EMBEDDING_MODEL")
        or str(milvus_config.get("embedding_model") or "")
    ).strip()
    milvus_vector_count = _optional_int(os.environ.get("MILVUS_VECTOR_COUNT") or milvus_config.get("vector_count"))
    milvus_vector_kinds = tuple(
        _split_path_list(os.environ.get("MILVUS_VECTOR_KINDS", ""))
        or [str(item) for item in milvus_config.get("vector_kinds") or [] if str(item).strip()]
    )
    return RuntimePathRegistry(
        repo_root=root,
        script_root=root,
        primary_data_root=primary,
        secondary_data_roots=secondary,
        object_store_root=object_store,
        reviewed_evidence_root=reviewed_evidence,
        workbench_private_root=workbench_private,
        milvus_mode=milvus_mode,
        milvus_note=milvus_note,
        milvus_db_path=milvus_db_path,
        milvus_collection_name=milvus_collection_name,
        milvus_embedding_model=milvus_embedding_model,
        milvus_vector_count=milvus_vector_count,
        milvus_vector_kinds=milvus_vector_kinds,
        milvus_config_path=milvus_config_path,
    )


def _split_path_list(value: str) -> list[str]:
    if not value:
        return []
    separator = ";" if ";" in value else os.pathsep
    return [part for part in value.split(separator) if part.strip()]


def _resolve_optional_path(value: str | None, *, root: Path) -> Path | None:
    if not value or not str(value).strip():
        return None
    path = Path(str(value).strip())
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _load_json_config(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except Exception:
        return None
