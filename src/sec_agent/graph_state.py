from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "sec_agent_graph_state_v0.1"

ARTIFACT_KEYS = (
    "query_contract",
    "retrieval_plan",
    "retrieved_context",
    "market_snapshot_context",
    "runtime_exact_value_ledger",
    "evidence_coverage_matrix",
    "judgment_plan",
    "evidence_pack",
    "memo_answer",
    "claim_verification",
    "deterministic_gates",
    "rendered_answer",
    "multi_agent_summary",
)

OPTIONAL_ARTIFACT_KEYS = (
    "retrieval_plan",
    "market_snapshot_context",
    "multi_agent_summary",
)


@dataclass
class ArtifactRef:
    key: str
    path: str
    schema_version: str = ""
    row_count: int | None = None
    digest: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ArtifactRef":
        return cls(
            key=str(payload.get("key") or ""),
            path=str(payload.get("path") or ""),
            schema_version=str(payload.get("schema_version") or ""),
            row_count=_optional_int(payload.get("row_count")),
            digest=str(payload.get("digest") or ""),
            metadata=dict(payload.get("metadata") or {}),
        )


@dataclass
class StageRecord:
    name: str
    status: str
    started_at: str = ""
    finished_at: str = ""
    elapsed_ms: int | None = None
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StageRecord":
        return cls(
            name=str(payload.get("name") or ""),
            status=str(payload.get("status") or ""),
            started_at=str(payload.get("started_at") or ""),
            finished_at=str(payload.get("finished_at") or ""),
            elapsed_ms=_optional_int(payload.get("elapsed_ms")),
            message=str(payload.get("message") or ""),
            metadata=dict(payload.get("metadata") or {}),
        )


@dataclass
class SecAgentState:
    run_id: str
    user_query: str
    output_dir: str
    schema_version: str = SCHEMA_VERSION
    created_at: str = field(default_factory=lambda: _utc_now())
    updated_at: str = field(default_factory=lambda: _utc_now())
    status: str = "created"
    source_policy: str = "SEC_ONLY"
    inventory_digest: str = ""
    selected_tickers: list[str] = field(default_factory=list)
    selected_years: list[int] = field(default_factory=list)
    model_routes: dict[str, dict[str, Any]] = field(default_factory=dict)
    artifacts: dict[str, ArtifactRef] = field(default_factory=dict)
    stages: list[StageRecord] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        user_query: str,
        output_dir: str | Path,
        selected_tickers: list[str] | None = None,
        selected_years: list[int] | None = None,
        inventory_digest: str = "",
        model_routes: dict[str, dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "SecAgentState":
        return cls(
            run_id=str(run_id),
            user_query=str(user_query),
            output_dir=str(output_dir),
            selected_tickers=[str(item).upper() for item in (selected_tickers or [])],
            selected_years=[int(item) for item in (selected_years or [])],
            inventory_digest=str(inventory_digest or ""),
            model_routes=dict(model_routes or {}),
            metadata=dict(metadata or {}),
        )

    def with_artifact(
        self,
        key: str,
        path: str | Path,
        *,
        schema_version: str = "",
        row_count: int | None = None,
        digest: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> "SecAgentState":
        normalized_key = str(key or "").strip()
        if normalized_key not in ARTIFACT_KEYS:
            raise ValueError(f"unknown artifact key: {normalized_key}")
        artifact_path = Path(path)
        self.artifacts[normalized_key] = ArtifactRef(
            key=normalized_key,
            path=str(artifact_path),
            schema_version=str(schema_version or ""),
            row_count=row_count,
            digest=str(digest or _file_digest(artifact_path)),
            metadata=dict(metadata or {}),
        )
        self.touch()
        return self

    def mark_stage(
        self,
        name: str,
        status: str,
        *,
        started_at: str = "",
        finished_at: str = "",
        elapsed_ms: int | None = None,
        message: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> "SecAgentState":
        self.stages.append(
            StageRecord(
                name=str(name),
                status=str(status),
                started_at=str(started_at or ""),
                finished_at=str(finished_at or ""),
                elapsed_ms=elapsed_ms,
                message=str(message or ""),
                metadata=dict(metadata or {}),
            )
        )
        self.status = str(status or self.status)
        self.touch()
        return self

    def add_error(self, *, stage: str, message: str, metadata: dict[str, Any] | None = None) -> "SecAgentState":
        self.errors.append({"stage": str(stage), "message": str(message), "metadata": dict(metadata or {})})
        self.status = "failed"
        self.touch()
        return self

    def touch(self) -> None:
        self.updated_at = _utc_now()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["artifacts"] = {key: ref.to_dict() for key, ref in self.artifacts.items()}
        payload["stages"] = [stage.to_dict() for stage in self.stages]
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SecAgentState":
        state = cls(
            schema_version=str(payload.get("schema_version") or SCHEMA_VERSION),
            run_id=str(payload.get("run_id") or ""),
            user_query=str(payload.get("user_query") or ""),
            output_dir=str(payload.get("output_dir") or ""),
            created_at=str(payload.get("created_at") or _utc_now()),
            updated_at=str(payload.get("updated_at") or _utc_now()),
            status=str(payload.get("status") or "created"),
            source_policy=str(payload.get("source_policy") or "SEC_ONLY"),
            inventory_digest=str(payload.get("inventory_digest") or ""),
            selected_tickers=[str(item).upper() for item in payload.get("selected_tickers") or []],
            selected_years=[int(item) for item in payload.get("selected_years") or []],
            model_routes=dict(payload.get("model_routes") or {}),
            metadata=dict(payload.get("metadata") or {}),
        )
        state.artifacts = {
            key: ArtifactRef.from_dict(ref)
            for key, ref in (payload.get("artifacts") or {}).items()
            if isinstance(ref, dict)
        }
        state.stages = [
            StageRecord.from_dict(item)
            for item in (payload.get("stages") or [])
            if isinstance(item, dict)
        ]
        state.errors = [dict(item) for item in (payload.get("errors") or []) if isinstance(item, dict)]
        return state

    def write_json(self, path: str | Path | None = None) -> Path:
        output_path = Path(path) if path else Path(self.output_dir) / "sec_agent_state.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return output_path

    @classmethod
    def read_json(cls, path: str | Path) -> "SecAgentState":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def _file_digest(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()[:16]


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
