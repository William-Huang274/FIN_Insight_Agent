from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


_ENV_LINE_RE = re.compile(r"^(?:export\s+)?(?P<key>[A-Za-z_][A-Za-z0-9_]*)=(?P<value>.*)$")


class ModelRouteProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backend: str = "deepseek"
    base_url: str | None = None
    chat_completions_path: str = "/chat/completions"
    model_name: str | None = None
    api_key_env: str | None = None
    query_planner: str = "llm"


class SourceArtifactsProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_policy: str = "SEC_PRIMARY_MIXED_RECENT"
    manifest_path: str | None = None
    bm25_index_dir: str | None = None
    object_bm25_index_dir: str | None = None
    source_gap_path: str | None = None
    market_evidence_path: str | None = None
    market_snapshot_id: str | None = None
    market_as_of_date: str | None = None


class RuntimeProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    python: str = "python"
    bge_model: str | None = None
    bge_device: str = "cpu"
    graph_execution: str | None = None
    output_root: str | None = None
    execution_shell: str = "auto"
    wsl_distro: str | None = None
    wsl_repo_root: str | None = None


class WorkbenchProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str
    display_name: str
    env_file: str | None = None
    model_route: ModelRouteProfile = Field(default_factory=ModelRouteProfile)
    sources: SourceArtifactsProfile = Field(default_factory=SourceArtifactsProfile)
    runtime: RuntimeProfile = Field(default_factory=RuntimeProfile)

    def to_runtime_env(self) -> dict[str, str]:
        """Return non-secret environment values needed to launch the agent."""
        env: dict[str, str] = {
            "LLM_BACKEND": self.model_route.backend,
            "CHAT_COMPLETIONS_PATH": self.model_route.chat_completions_path,
            "QUERY_PLANNER": self.model_route.query_planner,
            "PY": self.runtime.python,
            "BGE_DEVICE": self.runtime.bge_device,
            "SEC_AGENT_SOURCE_POLICY": self.sources.source_policy,
        }
        optional_values = {
            "BASE_URL": self.model_route.base_url,
            "MODEL_NAME": self.model_route.model_name,
            "API_KEY_ENV": self.model_route.api_key_env,
            "BGE_MODEL": self.runtime.bge_model,
            "SEC_AGENT_GRAPH_EXECUTION": self.runtime.graph_execution,
            "OUTPUT_ROOT": self.runtime.output_root,
            "MANIFEST_PATH": self.sources.manifest_path,
            "BM25_INDEX_DIR": self.sources.bm25_index_dir,
            "OBJECT_BM25_INDEX_DIR": self.sources.object_bm25_index_dir,
            "SOURCE_GAP_PATH": self.sources.source_gap_path,
            "MARKET_EVIDENCE_PATH": self.sources.market_evidence_path,
            "MARKET_SNAPSHOT_ID": self.sources.market_snapshot_id,
            "MARKET_AS_OF_DATE": self.sources.market_as_of_date,
        }
        for key, value in optional_values.items():
            if value is not None and str(value) != "":
                env[key] = str(value)
        return env


def profile_from_env_file(
    env_path: str | Path,
    *,
    profile_id: str | None = None,
    display_name: str | None = None,
) -> WorkbenchProfile:
    path = Path(env_path)
    values = parse_env_file(path)
    resolved_profile_id = profile_id or _slug_from_path(path)
    return WorkbenchProfile(
        profile_id=resolved_profile_id,
        display_name=display_name or resolved_profile_id.replace("_", " "),
        env_file=str(path),
        model_route=ModelRouteProfile(
            backend=values.get("LLM_BACKEND", "deepseek"),
            base_url=_none_if_blank(values.get("BASE_URL")),
            chat_completions_path=values.get("CHAT_COMPLETIONS_PATH", "/chat/completions"),
            model_name=_none_if_blank(values.get("MODEL_NAME")),
            api_key_env=_none_if_blank(values.get("API_KEY_ENV")),
            query_planner=values.get("QUERY_PLANNER", "llm"),
        ),
        sources=SourceArtifactsProfile(
            source_policy=values.get("SEC_AGENT_SOURCE_POLICY", "SEC_PRIMARY_MIXED_RECENT"),
            manifest_path=_none_if_blank(values.get("MANIFEST_PATH")),
            bm25_index_dir=_none_if_blank(values.get("BM25_INDEX_DIR")),
            object_bm25_index_dir=_none_if_blank(values.get("OBJECT_BM25_INDEX_DIR")),
            source_gap_path=_none_if_blank(values.get("SOURCE_GAP_PATH")),
            market_evidence_path=_none_if_blank(values.get("MARKET_EVIDENCE_PATH")),
            market_snapshot_id=_none_if_blank(values.get("MARKET_SNAPSHOT_ID")),
            market_as_of_date=_none_if_blank(values.get("MARKET_AS_OF_DATE")),
        ),
        runtime=RuntimeProfile(
            python=values.get("PY", "python"),
            bge_model=_none_if_blank(values.get("BGE_MODEL")),
            bge_device=values.get("BGE_DEVICE", "cpu"),
            graph_execution=_none_if_blank(values.get("SEC_AGENT_GRAPH_EXECUTION")),
            output_root=_none_if_blank(values.get("OUTPUT_ROOT")),
            execution_shell=values.get("WORKBENCH_EXECUTION_SHELL", "auto"),
            wsl_distro=_none_if_blank(values.get("WORKBENCH_WSL_DISTRO")),
            wsl_repo_root=_none_if_blank(values.get("WORKBENCH_WSL_REPO_ROOT")),
        ),
    )


def parse_env_file(env_path: str | Path) -> dict[str, str]:
    path = Path(env_path)
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _ENV_LINE_RE.match(line)
        if not match:
            continue
        key = match.group("key")
        value = _strip_env_value(match.group("value").strip())
        values[key] = value
    return values


def resolve_profile_path(repo_root: str | Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else Path(repo_root) / path


def _strip_env_value(value: str) -> str:
    if not value:
        return ""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return _strip_unquoted_comment(value).strip()


def _strip_unquoted_comment(value: str) -> str:
    escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "#" and (index == 0 or value[index - 1].isspace()):
            return value[:index]
    return value


def _none_if_blank(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _slug_from_path(path: Path) -> str:
    slug = re.sub(r"[^A-Za-z0-9_]+", "_", path.stem).strip("_").lower()
    return slug or "default"
