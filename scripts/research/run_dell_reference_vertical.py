"""Run the single-case DELL reference vertical with durable HITL state.

This is intentionally a narrow composition root, not a reusable runner
framework.  ``start`` binds the current nine-branch DELL foundation to the
qualified A02 knowledge bridge, A04 S2 fact mart, current Reviewed Evidence,
the research MCP server, bounded public-source discovery/capture, and the
existing DeepSeek structured agents.  ``resume`` only supplies an approve or
reject decision to the same SQLite-backed LangGraph thread.

All runtime/data identities are explicit CLI inputs.  Credentials are read
only from the named environment variable, wrapped in ``SecretStr``, and are
never projected into logs, checkpoints, summaries, or artifacts.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
from datetime import datetime
from hashlib import sha256
import importlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any, Mapping, NoReturn, Sequence


SCHEMA_VERSION = "fin_ia_dell_reference_vertical_cli_attempt_v1_1"
EXPECTED_BRANCH_COUNT = 9
DEFAULT_API_KEY_ENV = "DEEPSEEK_API_KEY"
MAX_GRAPH_CONCURRENCY = 3
EXPECTED_GIT_BRANCH = "codex/fin013-dell-s1-s2-product-bridge"
IMPLEMENTATION_BINDING_SCHEMA_VERSION = (
    "fin_ia_dell_reference_vertical_implementation_binding_v1_1"
)
SCRIPT_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_SOURCE_ROOT = SCRIPT_REPOSITORY_ROOT / "src"
for _runtime_import_root in (str(SCRIPT_SOURCE_ROOT), str(SCRIPT_REPOSITORY_ROOT)):
    while _runtime_import_root in sys.path:
        sys.path.remove(_runtime_import_root)
sys.path[:0] = [str(SCRIPT_SOURCE_ROOT), str(SCRIPT_REPOSITORY_ROOT)]
_IMPLEMENTATION_MODULE_PATHS = {
    "apps.workbench.backend.application.research_evidence_pack_service": (
        "apps/workbench/backend/application/research_evidence_pack_service.py"
    ),
    "financial_facts.sec_snapshot": "src/financial_facts/sec_snapshot.py",
    "scripts.data_retrieval.materialize_dell_q2_reviewed_evidence_overlay": (
        "scripts/data_retrieval/materialize_dell_q2_reviewed_evidence_overlay.py"
    ),
    "sec_agent.agent_runtime.deepseek_structured_agents": (
        "src/sec_agent/agent_runtime/deepseek_structured_agents.py"
    ),
    "sec_agent.agent_runtime.dell_reference_vertical_contracts": (
        "src/sec_agent/agent_runtime/dell_reference_vertical_contracts.py"
    ),
    "sec_agent.agent_runtime.dell_reference_vertical_graph": (
        "src/sec_agent/agent_runtime/dell_reference_vertical_graph.py"
    ),
    "sec_agent.agent_runtime.dell_reference_vertical_mcp_tools": (
        "src/sec_agent/agent_runtime/dell_reference_vertical_mcp_tools.py"
    ),
    "sec_agent.agent_runtime.planner_tool_capabilities": (
        "src/sec_agent/agent_runtime/planner_tool_capabilities.py"
    ),
    "sec_agent.agent_runtime.runtime_foundation": (
        "src/sec_agent/agent_runtime/runtime_foundation.py"
    ),
    "sec_agent.research_foundation.contracts": (
        "src/sec_agent/research_foundation/contracts.py"
    ),
    "sec_agent.research_foundation.data_ports": (
        "src/sec_agent/research_foundation/data_ports.py"
    ),
    "sec_agent.research_foundation.external_sources": (
        "src/sec_agent/research_foundation/external_sources.py"
    ),
    "sec_agent.research_foundation.mcp_server": (
        "src/sec_agent/research_foundation/mcp_server.py"
    ),
    "sec_agent.runtime_bridge.paths": "src/sec_agent/runtime_bridge/paths.py",
}
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,159}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_GIT_OBJECT_ID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_FORBIDDEN_SECRET_KEYS = frozenset(
    {
        "api_key",
        "api_key_value",
        "authorization",
        "credential",
        "credentials",
        "password",
        "secret",
    }
)


class DellReferenceVerticalCLIError(RuntimeError):
    """One explicit composition, state, or artifact boundary failed."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run or resume the bounded nine-branch DELL reference vertical. "
            "Use start --preflight-only for a zero-model-call composition check."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser(
        "start",
        help="validate explicit inputs and start a new graph thread until HITL",
    )
    start.add_argument("--repository-root", type=Path, required=True)
    start.add_argument("--state-root", type=Path, required=True)
    start.add_argument("--attempt-id", required=True)
    start.add_argument("--run-id", required=True)
    start.add_argument("--case-id", required=True)
    start.add_argument("--snapshot-id", required=True)
    start.add_argument("--research-as-of", required=True)
    start.add_argument("--research-question", required=True)
    start.add_argument("--foundation-path", type=Path, required=True)
    start.add_argument("--foundation-sha256", required=True)
    start.add_argument("--deepseek-config-path", type=Path, required=True)
    start.add_argument("--deepseek-config-sha256", required=True)
    start.add_argument("--project-os-decision-source-path", type=Path)
    start.add_argument("--project-os-decision-source-sha256")
    start.add_argument("--knowledge-bridge-result-path", type=Path, required=True)
    start.add_argument("--knowledge-bridge-result-sha256", required=True)
    start.add_argument("--knowledge-records-path", type=Path, required=True)
    start.add_argument("--knowledge-records-sha256", required=True)
    start.add_argument("--knowledge-record-count", type=int, required=True)
    start.add_argument("--structured-rag-result-path", type=Path, required=True)
    start.add_argument("--structured-rag-result-sha256", required=True)
    start.add_argument("--structured-rag-nodes-path", type=Path, required=True)
    start.add_argument("--structured-rag-nodes-sha256", required=True)
    start.add_argument("--structured-rag-node-count", type=int, required=True)
    start.add_argument(
        "--allow-engineering-preview-candidate-runtime",
        action="store_true",
        help=(
            "explicitly allow a review-required structured RAG artifact only as "
            "candidate input for an engineering demo; never claims formal "
            "qualification, retrieval promotion, or Evidence admission"
        ),
    )
    start.add_argument("--s2-result-path", type=Path, required=True)
    start.add_argument("--s2-result-sha256", required=True)
    start.add_argument("--s2-mart-path", type=Path, required=True)
    start.add_argument("--s2-mart-sha256", required=True)
    start.add_argument("--reviewed-evidence-root", type=Path, required=True)
    start.add_argument("--workbench-private-root", type=Path, required=True)
    start.add_argument("--reviewed-evidence-projection-digest", required=True)
    start.add_argument(
        "--reviewed-evidence-overlay-projection-path",
        type=Path,
        help=(
            "optional case-only Reviewed Evidence overlay projection; when set, "
            "its SHA and immutable materialization receipt are also required"
        ),
    )
    start.add_argument("--reviewed-evidence-overlay-projection-sha256")
    start.add_argument("--reviewed-evidence-overlay-receipt-path", type=Path)
    start.add_argument("--reviewed-evidence-overlay-receipt-sha256")
    start.add_argument(
        "--external-candidate-pack-manifest-path",
        type=Path,
        help=(
            "optional frozen exact-URL qualification manifest; when bound, "
            "same-branch candidates are replayed from its verified local text "
            "before live discovery, without Evidence or citation authority"
        ),
    )
    start.add_argument("--external-candidate-pack-manifest-sha256")
    start.add_argument(
        "--api-key-env",
        default=DEFAULT_API_KEY_ENV,
        help=(
            "environment variable containing the DeepSeek credential "
            f"(default: {DEFAULT_API_KEY_ENV}); its value is never emitted"
        ),
    )
    start.add_argument(
        "--preflight-only",
        action="store_true",
        help=(
            "construct and validate every dependency, MCP discovery, and SQLite "
            "checkpointer without invoking the graph or any model/source tool"
        ),
    )

    resume = subparsers.add_parser(
        "resume",
        help="resume one existing HITL checkpoint with approve or reject",
    )
    resume.add_argument("--state-root", type=Path, required=True)
    resume.add_argument("--attempt-id", required=True)
    resume.add_argument("--run-id", required=True)
    resume.add_argument("--action", choices=("approve", "reject"), required=True)
    resume.add_argument("--reason", default="")
    return parser


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        _json_ready(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _canonical_digest(value: Any) -> str:
    return sha256(_canonical_bytes(value)).hexdigest()


def _stream_sha256(path: Path) -> str:
    digest = sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise DellReferenceVerticalCLIError(
            f"input_file_unreadable:{path.name}"
        ) from exc
    return digest.hexdigest()


def _required_digest(value: str, label: str) -> str:
    normalized = str(value).strip().lower()
    if not _DIGEST.fullmatch(normalized):
        raise DellReferenceVerticalCLIError(f"{label}_invalid")
    return normalized


def _required_identifier(value: str, label: str) -> str:
    normalized = str(value).strip()
    if not _IDENTIFIER.fullmatch(normalized):
        raise DellReferenceVerticalCLIError(f"{label}_invalid")
    return normalized


def _required_git_object_id(value: str, label: str) -> str:
    normalized = str(value).strip().lower()
    if not _GIT_OBJECT_ID.fullmatch(normalized):
        raise DellReferenceVerticalCLIError(f"{label}_invalid")
    return normalized


def _required_file(path: Path, expected_sha256: str, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise DellReferenceVerticalCLIError(f"{label}_unavailable")
    expected = _required_digest(expected_sha256, f"{label}_sha256")
    if _stream_sha256(resolved) != expected:
        raise DellReferenceVerticalCLIError(f"{label}_sha256_mismatch")
    return resolved


def _required_directory(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_dir():
        raise DellReferenceVerticalCLIError(f"{label}_unavailable")
    return resolved


def _git_output(repository_root: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repository_root), *arguments],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        raise DellReferenceVerticalCLIError("git_command_unavailable") from exc
    if result.returncode != 0:
        raise DellReferenceVerticalCLIError(
            f"git_command_failed:{arguments[0] if arguments else 'unknown'}"
        )
    return result.stdout.strip()


def _implementation_source_paths(
    repository_root: Path,
    *,
    project_os_decision_path: Path | None = None,
) -> tuple[Path, ...]:
    explicit = (
        repository_root / "scripts/research/run_dell_reference_vertical.py",
        repository_root
        / "scripts/research/run_dell_reference_vertical_q1_a01.ps1",
        repository_root / "src/financial_facts/__init__.py",
        repository_root / "src/financial_facts/sec_snapshot.py",
        repository_root / "src/sec_agent/runtime_bridge/paths.py",
        repository_root
        / "apps/workbench/backend/application/research_evidence_pack_service.py",
        repository_root / "pyproject.toml",
        repository_root / "uv.lock",
    )
    discovered = tuple(
        sorted(
            (
                *(
                    repository_root / "src/sec_agent/agent_runtime"
                ).rglob("*.py"),
                *(
                    repository_root / "src/sec_agent/research_foundation"
                ).rglob("*.py"),
            ),
            key=lambda path: path.relative_to(repository_root).as_posix(),
        )
    )
    additional: tuple[Path, ...] = ()
    if project_os_decision_path is not None:
        decision_path = project_os_decision_path.resolve()
        try:
            decision_path.relative_to(repository_root)
        except ValueError as exc:
            raise DellReferenceVerticalCLIError(
                "project_os_decision_source_outside_repository"
            ) from exc
        additional = (decision_path,)
    paths = tuple(dict.fromkeys((*explicit, *additional, *discovered)))
    if not paths or any(not path.is_file() for path in paths):
        raise DellReferenceVerticalCLIError(
            "implementation_source_bundle_incomplete"
        )
    return paths


def _bound_project_os_decision_source(
    *,
    repository_root: Path,
    path: Path | None,
    sha256: str | None,
) -> tuple[Path | None, dict[str, str] | None]:
    if path is None and not str(sha256 or "").strip():
        return None, None
    if path is None or not str(sha256 or "").strip():
        raise DellReferenceVerticalCLIError(
            "project_os_decision_source_binding_incomplete"
        )
    bound_path = _required_file(path, str(sha256), "project_os_decision_source")
    try:
        relative = bound_path.relative_to(repository_root).as_posix()
    except ValueError as exc:
        raise DellReferenceVerticalCLIError(
            "project_os_decision_source_outside_repository"
        ) from exc
    return bound_path, {
        "path": relative,
        "sha256": _required_digest(
            str(sha256),
            "project_os_decision_source_sha256",
        )
    }


def _implementation_module_origins(
    repository_root: Path,
) -> list[dict[str, str]]:
    """Prove that live imports resolve to the bound checkout, not another install."""

    origins: list[dict[str, str]] = []
    for module_name, relative_path in sorted(_IMPLEMENTATION_MODULE_PATHS.items()):
        expected = (repository_root / relative_path).resolve()
        if not expected.is_file():
            raise DellReferenceVerticalCLIError(
                "implementation_module_expected_source_unavailable"
            )
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            raise DellReferenceVerticalCLIError(
                f"implementation_module_import_failed:{module_name}"
            ) from exc
        raw_origin = getattr(module, "__file__", None)
        if not isinstance(raw_origin, str) or not raw_origin.strip():
            raise DellReferenceVerticalCLIError(
                f"implementation_module_origin_missing:{module_name}"
            )
        actual = Path(raw_origin).resolve()
        if actual != expected:
            raise DellReferenceVerticalCLIError(
                f"implementation_module_origin_mismatch:{module_name}"
            )
        origins.append(
            {
                "module": module_name,
                "path": expected.relative_to(repository_root).as_posix(),
                "sha256": _stream_sha256(expected),
            }
        )
    return origins


def _repository_implementation_binding(
    repository_root: Path,
    *,
    project_os_decision_path: Path | None = None,
) -> dict[str, Any]:
    from sec_agent.agent_runtime.dell_reference_vertical_graph import (
        GRAPH_CONTRACT_VERSION,
    )

    root = _required_directory(repository_root, "repository_root")
    status = _git_output(
        root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )
    if status:
        raise DellReferenceVerticalCLIError(
            "repository_worktree_must_be_clean_for_bound_run"
        )
    commit = _required_git_object_id(
        _git_output(root, "rev-parse", "--verify", "HEAD"),
        "git_commit",
    )
    tree = _required_git_object_id(
        _git_output(root, "rev-parse", "HEAD^{tree}"),
        "git_tree",
    )
    branch = _git_output(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    if branch != EXPECTED_GIT_BRANCH:
        raise DellReferenceVerticalCLIError("git_branch_binding_mismatch")
    source_paths = (
        _implementation_source_paths(
            root,
            project_os_decision_path=project_os_decision_path,
        )
        if project_os_decision_path is not None
        else _implementation_source_paths(root)
    )
    relative_paths = tuple(
        path.relative_to(root).as_posix() for path in source_paths
    )
    tracked_output = _git_output(
        root,
        "ls-files",
        "--stage",
        "--",
        *relative_paths,
    )
    tracked_paths = {
        line.split("\t", 1)[1]
        for line in tracked_output.splitlines()
        if "\t" in line
    }
    if tracked_paths != set(relative_paths):
        raise DellReferenceVerticalCLIError(
            "implementation_source_bundle_not_fully_tracked"
        )
    source_files = [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": _stream_sha256(path),
        }
        for path in source_paths
    ]
    dependency_files = {
        row["path"]: row["sha256"]
        for row in source_files
        if row["path"] in {"pyproject.toml", "uv.lock"}
    }
    module_origins = _implementation_module_origins(root)
    body = {
        "schema_version": IMPLEMENTATION_BINDING_SCHEMA_VERSION,
        "repository_root": str(root),
        "git_branch": branch,
        "git_commit": commit,
        "git_tree": tree,
        "worktree_clean": True,
        "graph_contract_version": GRAPH_CONTRACT_VERSION,
        "source_files": source_files,
        "source_bundle_digest": _canonical_digest(source_files),
        "dependency_file_digests": dependency_files,
        "runtime_module_origins": module_origins,
        "runtime_module_origin_digest": _canonical_digest(module_origins),
    }
    return {**body, "binding_digest": _canonical_digest(body)}


def _assert_current_implementation_matches(manifest: Mapping[str, Any]) -> None:
    expected = manifest.get("implementation_binding")
    if not isinstance(expected, Mapping):
        raise DellReferenceVerticalCLIError("implementation_binding_missing")
    input_bindings = manifest.get("input_bindings")
    if not isinstance(input_bindings, Mapping):
        raise DellReferenceVerticalCLIError("input_bindings_missing")
    repository_root = input_bindings.get("repository_root")
    if not isinstance(repository_root, str) or not repository_root.strip():
        raise DellReferenceVerticalCLIError(
            "implementation_repository_root_missing"
        )
    root = Path(repository_root).resolve()
    raw_decision = input_bindings.get("project_os_decision_source")
    if raw_decision is not None and (
        not isinstance(raw_decision, Mapping)
        or set(raw_decision) != {"path", "sha256"}
    ):
        raise DellReferenceVerticalCLIError(
            "project_os_decision_source_manifest_invalid"
        )
    decision_path, normalized_decision = _bound_project_os_decision_source(
        repository_root=root,
        path=(root / str(raw_decision.get("path") or ""))
        if isinstance(raw_decision, Mapping)
        else None,
        sha256=str(raw_decision.get("sha256") or "")
        if isinstance(raw_decision, Mapping)
        else None,
    )
    if normalized_decision != raw_decision:
        raise DellReferenceVerticalCLIError(
            "project_os_decision_source_manifest_drift"
        )
    current = (
        _repository_implementation_binding(
            root,
            project_os_decision_path=decision_path,
        )
        if decision_path is not None
        else _repository_implementation_binding(root)
    )
    if current != dict(expected):
        raise DellReferenceVerticalCLIError("implementation_binding_drift")


def _state_root(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if os.name == "nt" and resolved.drive.upper() != "Z:":
        raise DellReferenceVerticalCLIError("state_root_must_be_on_z_drive")
    try:
        resolved.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DellReferenceVerticalCLIError("state_root_unwritable") from exc
    if not resolved.is_dir():
        raise DellReferenceVerticalCLIError("state_root_unavailable")
    return resolved


def _aware_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise DellReferenceVerticalCLIError("research_as_of_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DellReferenceVerticalCLIError("research_as_of_timezone_required")
    return parsed


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DellReferenceVerticalCLIError(f"{label}_json_invalid") from exc
    if not isinstance(value, dict):
        raise DellReferenceVerticalCLIError(f"{label}_shape_invalid")
    return value


def _same_path(left: Any, right: Path) -> bool:
    if not isinstance(left, str) or not left.strip():
        return False
    try:
        return Path(left).expanduser().resolve() == right.resolve()
    except OSError:
        return False


def _validate_knowledge_bridge(
    *, result_path: Path, records_path: Path, records_sha256: str, record_count: int
) -> dict[str, Any]:
    value = _read_json(result_path, "knowledge_bridge_result")
    output = value.get("output")
    schema_version = value.get("schema_version")
    schema_supported = schema_version in {
        "fin_ia_dell_knowledge_reader_bridge_result_v1_0",
        "fin_ia_dell_knowledge_reader_bridge_result_v1_2",
    }
    v1_2_contract_valid = schema_version != (
        "fin_ia_dell_knowledge_reader_bridge_result_v1_2"
    ) or (
        value.get("provenance_fields_preserved") is True
        and value.get("text_sha256_recomputed") is True
        and value.get("parent_content_materialized") is False
        and value.get("parent_child_retrieval_performed") is False
    )
    if (
        not schema_supported
        or not v1_2_contract_valid
        or value.get("status")
        != "qualification_candidate_bridge_materialized"
        or value.get("authority_state") != "retrieval_candidate_set"
        or value.get("candidate_is_not_evidence") is not True
        or value.get("citation_eligible") is not False
        or value.get("evidence_admission_performed") is not False
        or not isinstance(output, Mapping)
        or not _same_path(output.get("records_path"), records_path)
        or str(output.get("sha256") or "").lower() != records_sha256
        or output.get("record_count") != record_count
    ):
        raise DellReferenceVerticalCLIError("knowledge_bridge_binding_invalid")
    return value


def _validate_structured_rag_result(
    *,
    result_path: Path,
    nodes_path: Path,
    nodes_sha256: str,
    allow_engineering_preview: bool = False,
) -> dict[str, Any]:
    """Bind the runtime to the reviewed BM25 candidate artifact.

    This is deliberately not a formal-qualification or Evidence-promotion
    check.  A review-required artifact is rejected by default and can enter an
    engineering demo only through the explicit CLI opt-in.  The opt-in never
    reverses the producer's promotion flags.
    """

    value = _read_json(result_path, "structured_rag_result")
    artifacts = value.get("artifacts")
    nodes = (
        artifacts.get("retrieval_nodes.jsonl")
        if isinstance(artifacts, Mapping)
        else None
    )
    metrics = value.get("metrics")
    bm25 = metrics.get("bm25") if isinstance(metrics, Mapping) else None
    if (
        value.get("schema_version")
        != "fin_ia_dell_structured_rag_qualification_result_v1_0"
        or value.get("status")
        != "ENGINEERING_PREVIEW_MEASURED_REVIEW_REQUIRED"
        or value.get("attempt_mode") != "engineering_preview"
        or value.get("formal_eligible") is not False
        or value.get("manual_review_complete") is not False
        or value.get("deepseek_calls") != 0
        or value.get("generation_model_calls") != 0
        or value.get("paid_calls") != 0
        or value.get("retrieval_promotion_authorized") is not False
        or value.get("mcp_promotion_authorized") is not False
        or not isinstance(nodes, Mapping)
        or not _same_path(nodes.get("path"), nodes_path)
        or str(nodes.get("sha256") or "").lower() != nodes_sha256
        or not isinstance(bm25, Mapping)
        or bm25.get("hit_rate_at_10") != 1.0
        or bm25.get("critical_miss_count_at_5") != 0
        or bm25.get("critical_delivered_context_required_facet_miss_count_at_5")
        != 0
        or bm25.get("hard_negative_rank_1_count") != 0
        or bm25.get("critical_acceptable_precedence_failure_count") != 0
    ):
        raise DellReferenceVerticalCLIError("structured_rag_binding_invalid")
    if not allow_engineering_preview:
        raise DellReferenceVerticalCLIError(
            "structured_rag_engineering_preview_not_authorized"
        )
    return value


def _validate_s2_result(
    *, result_path: Path, mart_path: Path, mart_sha256: str
) -> dict[str, Any]:
    value = _read_json(result_path, "s2_result")
    claimed_result_digest = value.get("result_digest")
    unsigned_result = {
        key: item for key, item in value.items() if key != "result_digest"
    }
    storage = value.get("storage")
    acceptance = value.get("acceptance")
    if (
        value.get("schema_version")
        != "fin_ia_s2_company_financial_fact_mart_build_result_v1_0"
        or value.get("status") != "s2_company_financial_fact_mart_engineering_pass"
        or not isinstance(storage, Mapping)
        or not _same_path(storage.get("sqlite_ref"), mart_path)
        or str(storage.get("sqlite_sha256") or "").lower() != mart_sha256
        or not isinstance(acceptance, Mapping)
        or acceptance.get("candidate_or_metric_row_grants_numeric_authority")
        is not False
        or not isinstance(claimed_result_digest, str)
        or claimed_result_digest != _canonical_digest(unsigned_result)
    ):
        raise DellReferenceVerticalCLIError("s2_result_binding_invalid")
    return value


def _compose_case_only_evidence_overlay(
    base_projection: Mapping[str, Any],
    *,
    projection_path: Path,
    projection_sha256: str,
    receipt_path: Path,
    receipt_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate and compose one immutable case-only Evidence overlay.

    The materializer owns quote/source validation.  This composition root only
    verifies the frozen artifact/receipt binding and exposes the already
    reviewed projection through the existing reader; it performs no Evidence
    admission, product-Pack mutation, S2 write, or model call.
    """

    from scripts.data_retrieval.materialize_dell_q2_reviewed_evidence_overlay import (
        RECEIPT_SCHEMA,
        compose_case_projection,
    )

    bound_projection_path = _required_file(
        projection_path,
        projection_sha256,
        "reviewed_evidence_overlay_projection",
    )
    bound_receipt_path = _required_file(
        receipt_path,
        receipt_sha256,
        "reviewed_evidence_overlay_receipt",
    )
    overlay = _read_json(
        bound_projection_path, "reviewed_evidence_overlay_projection"
    )
    receipt = _read_json(bound_receipt_path, "reviewed_evidence_overlay_receipt")
    receipt_digest = str(receipt.get("receipt_payload_digest") or "")
    unsigned_receipt = dict(receipt)
    unsigned_receipt.pop("receipt_payload_digest", None)
    artifacts = receipt.get("artifacts")
    projection_artifact = (
        artifacts.get("case_projection") if isinstance(artifacts, Mapping) else None
    )
    authority = receipt.get("authority")
    review = receipt.get("review")
    expected_projection_sha = _required_digest(
        projection_sha256, "reviewed_evidence_overlay_projection_sha256"
    )
    expected_receipt_sha = _required_digest(
        receipt_sha256, "reviewed_evidence_overlay_receipt_sha256"
    )
    if not (
        receipt.get("schema_version") == RECEIPT_SCHEMA
        and receipt.get("status")
        == "case_only_reviewed_evidence_overlay_materialized"
        and receipt.get("case_key") == "DELL"
        and receipt_digest == _canonical_digest(unsigned_receipt)
        and isinstance(projection_artifact, Mapping)
        and _same_path(projection_artifact.get("path"), bound_projection_path)
        and str(projection_artifact.get("sha256") or "").lower()
        == expected_projection_sha
        and isinstance(authority, Mapping)
        and authority.get("case_only_reviewed_evidence") is True
        and authority.get("writer_citable_within_case") is True
        and authority.get("automatic_evidence_promotion") is False
        and authority.get("qualified_human_review") is False
        and authority.get("s2_numeric_fact_authority") is False
        and authority.get("derived_current_q2_arithmetic_authorized") is False
        and authority.get("product_pack_mutation_authorized") is False
        and isinstance(review, Mapping)
        and review.get("pack_validator") == "PASS"
        and isinstance(review.get("mcp_reviewed_evidence_reader"), Mapping)
        and review["mcp_reviewed_evidence_reader"].get("status") == "PASS"
        and review.get("item_count") == len(overlay.get("evidence_items", []))
    ):
        raise DellReferenceVerticalCLIError(
            "reviewed_evidence_overlay_receipt_binding_invalid"
        )
    try:
        composite = compose_case_projection(base_projection, overlay)
    except (TypeError, ValueError) as exc:
        raise DellReferenceVerticalCLIError(
            f"reviewed_evidence_overlay_composition_invalid:{exc}"
        ) from exc
    binding = {
        "projection_path": str(bound_projection_path),
        "projection_file_sha256": expected_projection_sha,
        "projection_digest": overlay.get("projection_digest"),
        "receipt_path": str(bound_receipt_path),
        "receipt_file_sha256": expected_receipt_sha,
        "receipt_payload_digest": receipt_digest,
        "overlay_evidence_count": review["item_count"],
        "composite_projection_digest": composite["projection_digest"],
        "current_q2_s2_numeric_fact_authority": False,
        "product_pack_mutation_authorized": False,
    }
    return composite, binding


def _json_ready(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "model_dump"):
        return _json_ready(value.model_dump(mode="json"))
    if is_dataclass(value):
        return _json_ready(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_ready(item) for item in value]
    # LangGraph Interrupt is a named object rather than a Pydantic model.
    if hasattr(value, "value") and hasattr(value, "id"):
        return {
            "id": _json_ready(getattr(value, "id")),
            "value": _json_ready(getattr(value, "value")),
        }
    raise DellReferenceVerticalCLIError(
        f"artifact_value_not_json:{type(value).__name__}"
    )


def _assert_secret_free(value: Any, secrets: Sequence[str]) -> None:
    def visit(item: Any) -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                if str(key).strip().lower() in _FORBIDDEN_SECRET_KEYS:
                    raise DellReferenceVerticalCLIError(
                        "secret_bearing_artifact_key_forbidden"
                    )
                visit(child)
        elif isinstance(item, Sequence) and not isinstance(
            item, (str, bytes, bytearray)
        ):
            for child in item:
                visit(child)

    ready = _json_ready(value)
    visit(ready)
    encoded = _canonical_bytes(ready)
    for secret in secrets:
        if secret and secret.encode("utf-8") in encoded:
            raise DellReferenceVerticalCLIError("credential_projection_forbidden")


def _write_new_json(path: Path, value: Any, *, secrets: Sequence[str] = ()) -> None:
    ready = _json_ready(value)
    _assert_secret_free(ready, secrets)
    if path.exists():
        raise DellReferenceVerticalCLIError(f"artifact_already_exists:{path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(
                json.dumps(
                    ready,
                    ensure_ascii=False,
                    allow_nan=False,
                    sort_keys=True,
                    indent=2,
                ).encode("utf-8")
            )
            stream.write(b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise


def _write_or_validate_json(
    path: Path,
    value: Any,
    *,
    secrets: Sequence[str] = (),
) -> bool:
    """Create one immutable JSON artifact or verify its existing identity.

    Returns ``True`` only when this call created the file.  A prior byte-layout
    may differ, but its canonical JSON identity must match exactly.
    """

    ready = _json_ready(value)
    _assert_secret_free(ready, secrets)
    if path.exists():
        existing = _read_json(path, f"existing_{path.stem}")
        if _canonical_digest(existing) != _canonical_digest(ready):
            raise DellReferenceVerticalCLIError(
                f"existing_artifact_identity_mismatch:{path.name}"
            )
        return False
    temporary = path.with_name(path.name + ".tmp")
    if temporary.exists():
        try:
            temporary_value = _read_json(
                temporary,
                f"orphan_temporary_{path.stem}",
            )
        except DellReferenceVerticalCLIError as exc:
            raise DellReferenceVerticalCLIError(
                f"orphan_temporary_artifact_conflict:{path.name}"
            ) from exc
        if _canonical_digest(temporary_value) != _canonical_digest(ready):
            raise DellReferenceVerticalCLIError(
                f"orphan_temporary_artifact_conflict:{path.name}"
            )
        temporary.replace(path)
        return True
    _write_new_json(path, ready, secrets=secrets)
    return True


class _ModelCallArtifactJournal:
    """Append-only two-event journal for each paid model call."""

    def __init__(self, attempt_dir: Path, *, secrets: Sequence[str]) -> None:
        self._root = attempt_dir / "model-calls"
        self._secrets = tuple(secrets)

    def __call__(self, event: Mapping[str, Any]) -> None:
        call_id = str(event.get("call_id") or "")
        event_name = str(event.get("event") or "")
        if not re.fullmatch(r"[a-z]+-[0-9a-f]{12}-[0-9a-f]{20}", call_id):
            raise DellReferenceVerticalCLIError("model_call_audit_id_invalid")
        if event_name not in {"started", "outcome"}:
            raise DellReferenceVerticalCLIError("model_call_audit_event_invalid")
        _write_new_json(
            self._root / f"{call_id}.{event_name}.json",
            event,
            secrets=self._secrets,
        )


def _model_call_audit_summary(attempt_dir: Path) -> dict[str, Any]:
    root = attempt_dir / "model-calls"
    started = sorted(root.glob("*.started.json")) if root.is_dir() else []
    outcomes = sorted(root.glob("*.outcome.json")) if root.is_dir() else []
    statuses: dict[str, int] = {}
    provider_reported_total_tokens = 0
    successful_call_tokens = 0
    failed_post_response_call_tokens = 0
    for path in outcomes:
        value = _read_json(path, "model_call_audit_outcome")
        status = str(value.get("status") or "unknown")
        statuses[status] = statuses.get(status, 0) + 1
        tokens = value.get("total_tokens")
        if not (
            isinstance(tokens, int)
            and not isinstance(tokens, bool)
            and tokens >= 0
        ):
            raw_response = value.get("raw_response")
            usage = (
                raw_response.get("usage_metadata")
                if isinstance(raw_response, Mapping)
                else None
            )
            tokens = usage.get("total_tokens") if isinstance(usage, Mapping) else None
        if isinstance(tokens, int) and not isinstance(tokens, bool) and tokens >= 0:
            provider_reported_total_tokens += tokens
            if status == "success":
                successful_call_tokens += tokens
            elif status in {
                "structured_parse_failed",
                "host_payload_validation_failed",
                "structured_raw_missing",
            }:
                failed_post_response_call_tokens += tokens
    return {
        "journal_root": str(root),
        "started_call_count": len(started),
        "outcome_call_count": len(outcomes),
        "unfinished_call_count": max(0, len(started) - len(outcomes)),
        "outcome_status_counts": dict(sorted(statuses.items())),
        "provider_reported_total_tokens": provider_reported_total_tokens,
        "successful_call_tokens": successful_call_tokens,
        "failed_post_response_call_tokens": failed_post_response_call_tokens,
        "successful_total_tokens": successful_call_tokens,
        "append_only_started_and_outcome_events": True,
    }


def _checkpoint_path(state_root: Path, run_id: str) -> Path:
    return (state_root / "checkpoints" / f"{run_id}.sqlite3").resolve()


def _attempt_dir(state_root: Path, attempt_id: str) -> Path:
    return (state_root / "attempts" / attempt_id).resolve()


def _safe_error(exc: BaseException, secret: str = "") -> dict[str, str]:
    message = str(exc)[:500]
    if secret:
        message = message.replace(secret, "[REDACTED]")
    return {
        "error_type": type(exc).__name__,
        "error_code": message or type(exc).__name__,
    }


def _runtime_registry(
    *,
    repository_root: Path,
    reviewed_evidence_root: Path,
    workbench_private_root: Path,
    s2_mart_path: Path,
) -> Any:
    from sec_agent.runtime_bridge.paths import RuntimePathRegistry

    return RuntimePathRegistry(
        repo_root=repository_root,
        script_root=repository_root,
        primary_data_root=reviewed_evidence_root.parent,
        secondary_data_roots=(),
        object_store_root=reviewed_evidence_root / "object_store",
        reviewed_evidence_root=reviewed_evidence_root,
        workbench_private_root=workbench_private_root,
        company_financial_fact_mart_path=s2_mart_path,
        milvus_mode="unbound_cloud_deferred",
        milvus_note="not_used_by_dell_reference_vertical_cli",
    )


def _compose_start(args: argparse.Namespace) -> dict[str, Any]:
    from pydantic import SecretStr

    from apps.workbench.backend.application.research_evidence_pack_service import (
        ResearchEvidencePackPrincipal,
        ResearchEvidencePackService,
    )
    from sec_agent.agent_runtime.deepseek_structured_agents import (
        DeepSeekStructuredAgentAdapter,
        load_deepseek_structured_agent_config,
    )
    from sec_agent.agent_runtime.dell_reference_vertical_graph import (
        DellReferenceVerticalDependencies,
        GRAPH_CONTRACT_VERSION,
    )
    from sec_agent.agent_runtime.dell_reference_vertical_mcp_tools import (
        DellMCPToolLaneAdapter,
        compose_dell_mcp_graph_run,
    )
    from sec_agent.agent_runtime.planner_tool_capabilities import (
        derive_planner_tool_capabilities,
    )
    from sec_agent.research_foundation.contracts import (
        canonical_sha256 as foundation_canonical_sha256,
        load_dell_reference_vertical_foundation,
    )
    from sec_agent.research_foundation.data_ports import (
        CurrentReviewedEvidenceReader,
        ExistingS2FinancialFactReader,
        StructuredLocalKnowledgeReader,
    )
    from sec_agent.research_foundation.external_sources import (
        DDGSDiagnosticProvider,
        ExaHostedMCPProvider,
        ExternalSourceCapture,
        ExternalSourceDiscovery,
    )
    from sec_agent.research_foundation.frozen_external_candidate_pack import (
        FrozenExternalCandidatePack,
        FrozenExternalCandidatePackProvider,
        FrozenFirstExternalSourceCapture,
    )
    from sec_agent.research_foundation.mcp_server import (
        DellFoundationMethodReader,
        ResearchDataMCPDependencies,
        build_research_data_mcp_server,
    )

    repository_root = _required_directory(args.repository_root, "repository_root")
    if repository_root != SCRIPT_REPOSITORY_ROOT:
        raise DellReferenceVerticalCLIError("repository_root_script_mismatch")
    project_os_decision_path, project_os_decision_binding = (
        _bound_project_os_decision_source(
            repository_root=repository_root,
            path=getattr(args, "project_os_decision_source_path", None),
            sha256=getattr(args, "project_os_decision_source_sha256", None),
        )
    )
    implementation_binding = _repository_implementation_binding(
        repository_root,
        project_os_decision_path=project_os_decision_path,
    )
    state_root = _state_root(args.state_root)
    attempt_id = _required_identifier(args.attempt_id, "attempt_id")
    run_id = _required_identifier(args.run_id, "run_id")
    attempt_dir = _attempt_dir(state_root, attempt_id)
    snapshot_id = _required_identifier(args.snapshot_id, "snapshot_id")
    research_as_of = _aware_datetime(args.research_as_of)
    if not str(args.research_question).strip():
        raise DellReferenceVerticalCLIError("research_question_required")

    foundation_path = _required_file(
        args.foundation_path, args.foundation_sha256, "foundation"
    )
    deepseek_config_path = _required_file(
        args.deepseek_config_path,
        args.deepseek_config_sha256,
        "deepseek_config",
    )
    bridge_result_path = _required_file(
        args.knowledge_bridge_result_path,
        args.knowledge_bridge_result_sha256,
        "knowledge_bridge_result",
    )
    knowledge_records_path = _required_file(
        args.knowledge_records_path,
        args.knowledge_records_sha256,
        "knowledge_records",
    )
    s2_result_path = _required_file(
        args.s2_result_path, args.s2_result_sha256, "s2_result"
    )
    s2_mart_path = _required_file(
        args.s2_mart_path, args.s2_mart_sha256, "s2_mart"
    )
    reviewed_root = _required_directory(
        args.reviewed_evidence_root, "reviewed_evidence_root"
    )
    workbench_private_root = _required_directory(
        args.workbench_private_root, "workbench_private_root"
    )
    knowledge_sha = _required_digest(
        args.knowledge_records_sha256, "knowledge_records_sha256"
    )
    structured_inputs = (
        getattr(args, "structured_rag_result_path", None),
        getattr(args, "structured_rag_result_sha256", None),
        getattr(args, "structured_rag_nodes_path", None),
        getattr(args, "structured_rag_nodes_sha256", None),
        getattr(args, "structured_rag_node_count", None),
    )
    structured_requested = any(value not in (None, "") for value in structured_inputs)
    if not structured_requested:
        raise DellReferenceVerticalCLIError(
            "structured_rag_runtime_binding_required"
        )
    if structured_requested and not all(
        value not in (None, "") for value in structured_inputs
    ):
        raise DellReferenceVerticalCLIError("structured_rag_binding_incomplete")
    structured_result_path: Path | None = None
    structured_nodes_path: Path | None = None
    structured_nodes_sha: str | None = None
    structured_node_count: int | None = None
    structured_result: dict[str, Any] | None = None
    if structured_requested:
        structured_result_path = _required_file(
            structured_inputs[0],
            str(structured_inputs[1]),
            "structured_rag_result",
        )
        structured_nodes_path = _required_file(
            structured_inputs[2],
            str(structured_inputs[3]),
            "structured_rag_nodes",
        )
        structured_nodes_sha = _required_digest(
            str(structured_inputs[3]), "structured_rag_nodes_sha256"
        )
        structured_node_count = int(structured_inputs[4])
        if structured_node_count < 1:
            raise DellReferenceVerticalCLIError(
                "structured_rag_node_count_invalid"
            )
        structured_result = _validate_structured_rag_result(
            result_path=structured_result_path,
            nodes_path=structured_nodes_path,
            nodes_sha256=structured_nodes_sha,
            allow_engineering_preview=bool(
                getattr(
                    args,
                    "allow_engineering_preview_candidate_runtime",
                    False,
                )
            ),
        )
    s2_sha = _required_digest(args.s2_mart_sha256, "s2_mart_sha256")
    evidence_digest = _required_digest(
        args.reviewed_evidence_projection_digest,
        "reviewed_evidence_projection_digest",
    )
    overlay_inputs = (
        getattr(args, "reviewed_evidence_overlay_projection_path", None),
        getattr(args, "reviewed_evidence_overlay_projection_sha256", None),
        getattr(args, "reviewed_evidence_overlay_receipt_path", None),
        getattr(args, "reviewed_evidence_overlay_receipt_sha256", None),
    )
    overlay_requested = any(value not in (None, "") for value in overlay_inputs)
    if overlay_requested and not all(value not in (None, "") for value in overlay_inputs):
        raise DellReferenceVerticalCLIError(
            "reviewed_evidence_overlay_binding_incomplete"
        )
    external_pack_inputs = (
        getattr(args, "external_candidate_pack_manifest_path", None),
        getattr(args, "external_candidate_pack_manifest_sha256", None),
    )
    external_pack_requested = any(
        value not in (None, "") for value in external_pack_inputs
    )
    if external_pack_requested and not all(
        value not in (None, "") for value in external_pack_inputs
    ):
        raise DellReferenceVerticalCLIError(
            "external_candidate_pack_binding_incomplete"
        )
    external_pack_manifest_path: Path | None = None
    if external_pack_requested:
        external_pack_manifest_path = _required_file(
            external_pack_inputs[0],
            str(external_pack_inputs[1]),
            "external_candidate_pack_manifest",
        )
    if args.knowledge_record_count < 1:
        raise DellReferenceVerticalCLIError("knowledge_record_count_invalid")
    _validate_knowledge_bridge(
        result_path=bridge_result_path,
        records_path=knowledge_records_path,
        records_sha256=knowledge_sha,
        record_count=args.knowledge_record_count,
    )
    _validate_s2_result(
        result_path=s2_result_path,
        mart_path=s2_mart_path,
        mart_sha256=s2_sha,
    )

    foundation = load_dell_reference_vertical_foundation(foundation_path)
    case_id = str(args.case_id).strip()
    if foundation.case_identity.case_id != case_id:
        raise DellReferenceVerticalCLIError("foundation_case_id_mismatch")
    branch_ids = tuple(row.branch_id for row in foundation.question_branches)
    if len(branch_ids) != EXPECTED_BRANCH_COUNT or len(set(branch_ids)) != len(
        branch_ids
    ):
        raise DellReferenceVerticalCLIError("foundation_must_have_exactly_nine_branches")
    external_candidate_pack = None
    if external_pack_manifest_path is not None:
        try:
            external_candidate_pack = FrozenExternalCandidatePack.load(
                external_pack_manifest_path,
                expected_sha256=str(external_pack_inputs[1]),
            )
            external_candidate_pack.validate_runtime_binding(
                case_id=case_id,
                branch_ids=branch_ids,
                research_as_of=research_as_of,
            )
        except Exception as exc:
            raise DellReferenceVerticalCLIError(
                f"external_candidate_pack_invalid:{exc}"
            ) from exc

    runtime_paths = _runtime_registry(
        repository_root=repository_root,
        reviewed_evidence_root=reviewed_root,
        workbench_private_root=workbench_private_root,
        s2_mart_path=s2_mart_path,
    )
    evidence_service = ResearchEvidencePackService.from_runtime_paths(
        repository_root, runtime_paths
    )
    evidence_principal = ResearchEvidencePackPrincipal(
        "current", frozenset({"current_product:read"})
    )
    evidence_projection = evidence_service.get_case("DELL", evidence_principal)
    if evidence_projection.get("projection_digest") != evidence_digest:
        raise DellReferenceVerticalCLIError(
            "reviewed_evidence_projection_digest_mismatch"
        )
    active_evidence_projection = evidence_projection
    evidence_overlay_binding: dict[str, Any] | None = None
    if overlay_requested:
        active_evidence_projection, evidence_overlay_binding = (
            _compose_case_only_evidence_overlay(
                evidence_projection,
                projection_path=overlay_inputs[0],
                projection_sha256=str(overlay_inputs[1]),
                receipt_path=overlay_inputs[2],
                receipt_sha256=str(overlay_inputs[3]),
            )
        )
    reviewed_reader = CurrentReviewedEvidenceReader(
        case_reader=lambda case_key: (
            active_evidence_projection
            if case_key == "DELL"
            else evidence_service.get_case(case_key, evidence_principal)
        )
    )
    local_reader = StructuredLocalKnowledgeReader(
        nodes_path=structured_nodes_path,
        expected_sha256=str(structured_nodes_sha),
        expected_node_count=int(structured_node_count),
        research_as_of=research_as_of.date(),
        allowed_branch_ids=branch_ids,
    )
    s2_reader = ExistingS2FinancialFactReader(
        s2_mart_path,
        expected_sha256=s2_sha,
    )
    planner_capabilities = derive_planner_tool_capabilities(
        sqlite_path=s2_mart_path,
        expected_mart_sha256=s2_sha,
        snapshot_id=snapshot_id,
    )
    composition = compose_dell_mcp_graph_run(
        foundation,
        branch_ids=branch_ids,
        research_as_of=research_as_of.isoformat(),
        snapshot_id=snapshot_id,
        execution_attempt_id=attempt_id,
    )

    discovery = ExternalSourceDiscovery(
        primary=ExaHostedMCPProvider(),
        diagnostic_fallback=DDGSDiagnosticProvider(),
        frozen_candidate_provider=(
            FrozenExternalCandidatePackProvider(external_candidate_pack)
            if external_candidate_pack is not None
            else None
        ),
    )
    live_capture = ExternalSourceCapture.with_default_transports()
    capture = (
        FrozenFirstExternalSourceCapture(
            pack=external_candidate_pack,
            fallback=live_capture,
        )
        if external_candidate_pack is not None
        else live_capture
    )
    mcp_server = build_research_data_mcp_server(
        ResearchDataMCPDependencies(
            method_reader=DellFoundationMethodReader(foundation),
            local_knowledge_reader=local_reader,
            reviewed_evidence_search_reader=reviewed_reader.search,
            reviewed_evidence_reader=reviewed_reader,
            financial_fact_reader=s2_reader,
            external_discovery=discovery,
            external_capture=capture,
        )
    )

    api_key_env = str(args.api_key_env).strip()
    if not api_key_env or not _IDENTIFIER.fullmatch(api_key_env):
        raise DellReferenceVerticalCLIError("api_key_env_invalid")
    api_key_value = os.environ.get(api_key_env, "")
    if not api_key_value.strip():
        raise DellReferenceVerticalCLIError(
            f"provider_credential_missing:{api_key_env}"
        )
    model_config = load_deepseek_structured_agent_config(deepseek_config_path)
    model_adapter = DeepSeekStructuredAgentAdapter.from_config(
        config=model_config,
        api_key=SecretStr(api_key_value),
        audit_sink=_ModelCallArtifactJournal(
            attempt_dir,
            secrets=(api_key_value,),
        ),
    )
    tool_adapter = DellMCPToolLaneAdapter(
        mcp_server,
        run_binding=composition.mcp_run_binding,
    )
    dependencies = DellReferenceVerticalDependencies(
        foundation_binder=composition.foundation_binder,
        planner_tool_capabilities=planner_capabilities.model_dump(mode="json"),
        planner_agent=model_adapter.planner,
        evidence_tool=tool_adapter.evidence_tool,
        finance_tool=tool_adapter.finance_tool,
        specialist_agent=model_adapter.specialist,
        counter_agent=model_adapter.counter,
        lead_agent=model_adapter.lead,
    )
    checkpoint_path = _checkpoint_path(state_root, run_id)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "attempt_id": attempt_id,
        "run_id": run_id,
        "case_id": case_id,
        "snapshot_id": snapshot_id,
        "research_as_of": research_as_of.isoformat(),
        "research_question": str(args.research_question).strip(),
        "branch_ids": list(branch_ids),
        "branch_count": len(branch_ids),
        "knowledge_record_count": args.knowledge_record_count,
        "local_retrieval_runtime": (
            "structured_metadata_prefilter_bm25"
            if structured_result is not None
            else "legacy_bm25_postfilter"
        ),
        "structured_rag_artifact_maturity": (
            "engineering_preview_candidate_only"
            if structured_result is not None
            else None
        ),
        "reviewed_evidence_count": len(
            active_evidence_projection.get("evidence_items", [])
        ),
        "checkpoint_path": str(checkpoint_path),
        "implementation_binding": implementation_binding,
        "graph_contract_version": GRAPH_CONTRACT_VERSION,
        "foundation_binding": composition.foundation_binding.model_dump(mode="json"),
        "foundation_canonical_digest": foundation_canonical_sha256(foundation),
        "planner_tool_capabilities": planner_capabilities.model_dump(mode="json"),
        "input_bindings": {
            "repository_root": str(repository_root),
            "project_os_decision_source": project_os_decision_binding,
            "foundation_path": str(foundation_path),
            "foundation_file_sha256": _required_digest(
                args.foundation_sha256, "foundation_sha256"
            ),
            "deepseek_config_path": str(deepseek_config_path),
            "deepseek_config_file_sha256": _required_digest(
                args.deepseek_config_sha256, "deepseek_config_sha256"
            ),
            "knowledge_bridge_result_path": str(bridge_result_path),
            "knowledge_bridge_result_sha256": _required_digest(
                args.knowledge_bridge_result_sha256,
                "knowledge_bridge_result_sha256",
            ),
            "knowledge_records_path": str(knowledge_records_path),
            "knowledge_records_sha256": knowledge_sha,
            "knowledge_record_count": args.knowledge_record_count,
            "structured_rag_result_path": (
                str(structured_result_path)
                if structured_result_path is not None
                else None
            ),
            "structured_rag_result_sha256": (
                _required_digest(
                    str(structured_inputs[1]),
                    "structured_rag_result_sha256",
                )
                if structured_result is not None
                else None
            ),
            "structured_rag_nodes_path": (
                str(structured_nodes_path)
                if structured_nodes_path is not None
                else None
            ),
            "structured_rag_nodes_sha256": structured_nodes_sha,
            "structured_rag_node_count": structured_node_count,
            "s2_result_path": str(s2_result_path),
            "s2_result_sha256": _required_digest(
                args.s2_result_sha256, "s2_result_sha256"
            ),
            "s2_mart_path": str(s2_mart_path),
            "s2_mart_sha256": s2_sha,
            "reviewed_evidence_root": str(reviewed_root),
            "workbench_private_root": str(workbench_private_root),
            "reviewed_evidence_base_projection_digest": evidence_digest,
            "reviewed_evidence_active_projection_digest": (
                active_evidence_projection["projection_digest"]
            ),
            "reviewed_evidence_case_only_overlay": evidence_overlay_binding,
            "external_candidate_pack": (
                external_candidate_pack.manifest_binding()
                if external_candidate_pack is not None
                else None
            ),
        },
        "authority_boundaries": {
            "candidate_is_not_evidence": True,
            "captured_candidate_requires_separate_admission": True,
            "frozen_external_candidate_pack_bound": (
                external_candidate_pack is not None
            ),
            "frozen_external_candidate_pack_source_capture_authority": False,
            "frozen_external_candidate_pack_evidence_admission_authorized": False,
            "frozen_external_candidate_pack_mcp_promotion_authorized": False,
            "frozen_external_candidate_pack_s2_write_authorized": False,
            "frozen_external_candidate_pack_numeric_fact_authority": False,
            "current_q2_source_visible_values_are_textual_evidence_only": True,
            "current_q2_s2_numeric_fact_authority": False,
            "current_q2_derived_arithmetic_authorized": False,
            "automatic_human_approval": False,
            "structured_rag_formal_eligible": (
                structured_result.get("formal_eligible")
                if structured_result is not None
                else None
            ),
            "structured_rag_manual_review_complete": (
                structured_result.get("manual_review_complete")
                if structured_result is not None
                else None
            ),
            "structured_rag_mcp_promotion_authorized": (
                structured_result.get("mcp_promotion_authorized")
                if structured_result is not None
                else None
            ),
            "formal_qualification_claimed": False,
            "model_transport_retries": model_config.max_retries,
            "maximum_counter_reroutes": (
                foundation.scope_ceiling.maximum_targeted_counter_reroutes
            ),
            "maximum_specialist_model_rounds": (
                composition.foundation_binding.scope_ceiling
                .maximum_specialist_model_rounds
            ),
            "maximum_branches": EXPECTED_BRANCH_COUNT,
            "maximum_graph_concurrency": MAX_GRAPH_CONCURRENCY,
            "token_budget_basis": {
                role: basis.model_dump(mode="json")
                for role, basis in model_config.token_budget_basis.items()
            },
            "api_key_env_name": api_key_env,
            "api_key_persisted": False,
            "model_calls_journaled_before_and_after_transport": True,
        },
    }
    unsigned = dict(manifest)
    manifest["composition_digest"] = _canonical_digest(unsigned)
    return {
        "state_root": state_root,
        "attempt_dir": attempt_dir,
        "checkpoint_path": checkpoint_path,
        "run_id": run_id,
        "attempt_id": attempt_id,
        "api_key_value": api_key_value,
        "tool_adapter": tool_adapter,
        "dependencies": dependencies,
        "manifest": manifest,
    }


def _graph_config(run_id: str) -> dict[str, Any]:
    return {
        "configurable": {"thread_id": run_id},
        "recursion_limit": 100,
        "max_concurrency": MAX_GRAPH_CONCURRENCY,
    }


def _start(args: argparse.Namespace) -> int:
    from sec_agent.agent_runtime.dell_reference_vertical_graph import (
        build_dell_reference_vertical_graph,
    )
    from sec_agent.agent_runtime.runtime_foundation import (
        DellRuntimeFoundation,
        open_runtime_checkpointer,
    )

    started_at = datetime.now().astimezone().isoformat()
    started_tick = perf_counter()
    composition = _compose_start(args)
    secret = composition["api_key_value"]
    attempt_dir: Path = composition["attempt_dir"]

    if args.preflight_only:
        if attempt_dir.exists():
            raise DellReferenceVerticalCLIError(
                "preflight_attempt_directory_already_exists"
            )
        if composition["checkpoint_path"].exists():
            raise DellReferenceVerticalCLIError(
                "preflight_run_checkpoint_already_exists"
            )
        _assert_current_implementation_matches(composition["manifest"])
        with TemporaryDirectory(
            prefix=".dell-preflight-",
            dir=composition["state_root"],
        ) as probe_root:
            probe_foundation = DellRuntimeFoundation(
                profile="sqlite_qualification",
                sqlite_path=Path(probe_root) / "checkpoint-probe.sqlite3",
            )
            with open_runtime_checkpointer(probe_foundation) as checkpointer:
                with composition["tool_adapter"]:
                        build_dell_reference_vertical_graph(
                        dependencies=composition["dependencies"],
                            checkpointer=checkpointer,
                        )
        _assert_current_implementation_matches(composition["manifest"])
        summary = {
            "schema_version": SCHEMA_VERSION,
            "status": "zero_call_preflight_pass",
            "attempt_id": composition["attempt_id"],
            "run_id": composition["run_id"],
            "branch_count": EXPECTED_BRANCH_COUNT,
            "knowledge_record_count": composition["manifest"][
                "knowledge_record_count"
            ],
            "reviewed_evidence_count": composition["manifest"][
                "reviewed_evidence_count"
            ],
            "composition_digest": composition["manifest"]["composition_digest"],
            "implementation_binding_digest": composition["manifest"][
                "implementation_binding"
            ]["binding_digest"],
            "model_calls": 0,
            "external_discovery_calls": 0,
            "external_capture_calls": 0,
            "graph_invoked": False,
            "api_key_persisted": False,
            "checkpoint_backend": "langgraph_sqlite_qualification",
            "sqlite_checkpoint_probe_cleaned": True,
            "maximum_graph_concurrency": MAX_GRAPH_CONCURRENCY,
        }
        _assert_secret_free(summary, (secret,))
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0

    if attempt_dir.exists():
        raise DellReferenceVerticalCLIError("attempt_directory_already_exists")
    if composition["checkpoint_path"].exists():
        raise DellReferenceVerticalCLIError("run_checkpoint_already_exists")
    foundation = DellRuntimeFoundation(
        profile="sqlite_qualification",
        sqlite_path=composition["checkpoint_path"],
    )
    attempt_dir.mkdir(parents=True, exist_ok=False)
    manifest = composition["manifest"]
    _write_new_json(attempt_dir / "composition.json", manifest, secrets=(secret,))
    initial = {
        "run_id": manifest["run_id"],
        "case_id": manifest["case_id"],
        "research_question": manifest["research_question"],
        "research_as_of": manifest["research_as_of"],
        "snapshot_id": manifest["snapshot_id"],
        "foundation_digest": manifest["foundation_canonical_digest"],
    }
    _write_new_json(
        attempt_dir / "start-input.json",
        {**initial, "started_at": started_at},
        secrets=(secret,),
    )
    try:
        _assert_current_implementation_matches(manifest)
        with open_runtime_checkpointer(foundation) as checkpointer:
            with composition["tool_adapter"]:
                graph = build_dell_reference_vertical_graph(
                    dependencies=composition["dependencies"],
                    checkpointer=checkpointer,
                )
                state = graph.invoke(initial, _graph_config(manifest["run_id"]))
        _assert_current_implementation_matches(manifest)
        ready_state = _json_ready(state)
        if ready_state.get("graph_contract_version") != manifest.get(
            "graph_contract_version"
        ):
            raise DellReferenceVerticalCLIError(
                "graph_contract_version_state_mismatch"
            )
        stopped_at = datetime.now().astimezone().isoformat()
        wall_elapsed_ms = round((perf_counter() - started_tick) * 1_000, 3)
        _write_new_json(
            attempt_dir / "state.at-start-stop.json", ready_state, secrets=(secret,)
        )
        interrupts = ready_state.get("__interrupt__", [])
        phase = ready_state.get("phase")
        awaiting_review = phase == "awaiting_review" and bool(interrupts)
        summary = {
            "schema_version": SCHEMA_VERSION,
            "status": (
                "awaiting_human_review" if awaiting_review else "stopped_before_hitl"
            ),
            "attempt_id": manifest["attempt_id"],
            "run_id": manifest["run_id"],
            "case_id": manifest["case_id"],
            "snapshot_id": manifest["snapshot_id"],
            "phase": phase,
            "branch_count": len(manifest["branch_ids"]),
            "reroute_count": ready_state.get("reroute_count", 0),
            "interrupt_count": len(interrupts),
            "verification": ready_state.get("verification"),
            "runtime_summary": ready_state.get("runtime_summary"),
            "model_call_audit": _model_call_audit_summary(attempt_dir),
            "plan_digest": ready_state.get("plan_digest"),
            "started_at": started_at,
            "stopped_at": stopped_at,
            "wall_elapsed_ms": wall_elapsed_ms,
            "composition_digest": manifest["composition_digest"],
            "implementation_binding_digest": manifest[
                "implementation_binding"
            ]["binding_digest"],
            "api_key_persisted": False,
            "automatic_human_approval": False,
        }
        _write_new_json(
            attempt_dir / "summary.at-start-stop.json", summary, secrets=(secret,)
        )
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0 if awaiting_review else 2
    except Exception as exc:
        failure = {
            "schema_version": SCHEMA_VERSION,
            "status": "start_failed",
            "attempt_id": manifest["attempt_id"],
            "run_id": manifest["run_id"],
            "started_at": started_at,
            "failed_at": datetime.now().astimezone().isoformat(),
            "wall_elapsed_ms": round((perf_counter() - started_tick) * 1_000, 3),
            "model_call_audit": _model_call_audit_summary(attempt_dir),
            **_safe_error(exc, secret),
            "api_key_persisted": False,
        }
        try:
            _write_new_json(
                attempt_dir / "failure.at-start.json", failure, secrets=(secret,)
            )
        except Exception:
            pass
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2


def _never_called(*_args: Any, **_kwargs: Any) -> NoReturn:
    raise DellReferenceVerticalCLIError("resume_attempted_to_reexecute_dependency")


def _load_manifest(attempt_dir: Path) -> dict[str, Any]:
    manifest = _read_json(attempt_dir / "composition.json", "composition")
    digest = manifest.get("composition_digest")
    unsigned = dict(manifest)
    unsigned.pop("composition_digest", None)
    if digest != _canonical_digest(unsigned):
        raise DellReferenceVerticalCLIError("composition_digest_mismatch")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise DellReferenceVerticalCLIError("composition_schema_invalid")
    return manifest


def _resume(args: argparse.Namespace) -> int:
    from langgraph.types import Command

    from sec_agent.agent_runtime.dell_reference_vertical_graph import (
        DellReferenceVerticalDependencies,
        build_dell_reference_vertical_graph,
    )
    from sec_agent.agent_runtime.runtime_foundation import (
        DellRuntimeFoundation,
        open_runtime_checkpointer,
    )

    resumed_at = datetime.now().astimezone().isoformat()
    resumed_tick = perf_counter()
    state_root = _state_root(args.state_root)
    attempt_id = _required_identifier(args.attempt_id, "attempt_id")
    run_id = _required_identifier(args.run_id, "run_id")
    attempt_dir = _attempt_dir(state_root, attempt_id)
    if not attempt_dir.is_dir():
        raise DellReferenceVerticalCLIError("attempt_directory_unavailable")
    manifest = _load_manifest(attempt_dir)
    expected_checkpoint = _checkpoint_path(state_root, run_id)
    if (
        manifest.get("attempt_id") != attempt_id
        or manifest.get("run_id") != run_id
        or not _same_path(manifest.get("checkpoint_path"), expected_checkpoint)
    ):
        raise DellReferenceVerticalCLIError("resume_identity_binding_mismatch")
    if not expected_checkpoint.is_file():
        raise DellReferenceVerticalCLIError("resume_checkpoint_unavailable")
    suffix = "approved" if args.action == "approve" else "rejected"
    _assert_current_implementation_matches(manifest)
    capabilities = manifest.get("planner_tool_capabilities")
    if not isinstance(capabilities, Mapping):
        raise DellReferenceVerticalCLIError("resume_capabilities_missing")
    dependencies = DellReferenceVerticalDependencies(
        foundation_binder=_never_called,
        planner_tool_capabilities=dict(capabilities),
        planner_agent=_never_called,
        evidence_tool=_never_called,
        finance_tool=_never_called,
        specialist_agent=_never_called,
        counter_agent=_never_called,
        lead_agent=_never_called,
    )
    foundation = DellRuntimeFoundation(
        profile="sqlite_qualification", sqlite_path=expected_checkpoint
    )
    config = _graph_config(run_id)
    with open_runtime_checkpointer(foundation) as checkpointer:
        graph = build_dell_reference_vertical_graph(
            dependencies=dependencies,
            checkpointer=checkpointer,
        )
        snapshot = graph.get_state(config)
        before = _json_ready(snapshot.values)
        for field, expected in (
            ("run_id", manifest.get("run_id")),
            ("case_id", manifest.get("case_id")),
            ("research_question", manifest.get("research_question")),
            ("snapshot_id", manifest.get("snapshot_id")),
            ("research_as_of", manifest.get("research_as_of")),
            ("foundation_digest", manifest.get("foundation_canonical_digest")),
        ):
            if before.get(field) != expected:
                raise DellReferenceVerticalCLIError(
                    f"resume_checkpoint_{field}_binding_mismatch"
                )
        if before.get("foundation_binding") != manifest.get("foundation_binding"):
            raise DellReferenceVerticalCLIError(
                "resume_checkpoint_foundation_binding_mismatch"
            )
        if before.get("foundation_binding_digest") != _canonical_digest(
            manifest.get("foundation_binding")
        ):
            raise DellReferenceVerticalCLIError(
                "resume_checkpoint_foundation_binding_digest_mismatch"
            )
        if before.get("graph_contract_version") != manifest.get(
            "graph_contract_version"
        ):
            raise DellReferenceVerticalCLIError(
                "resume_graph_contract_version_mismatch"
            )
        expected_phase = "completed" if args.action == "approve" else "rejected"
        awaiting_review = before.get("phase") == "awaiting_review" and (
            tuple(snapshot.next) == ("human_review",)
        )
        terminal_checkpoint_repair = (
            before.get("phase") == expected_phase and not tuple(snapshot.next)
        )
        approved_pending_render = (
            args.action == "approve"
            and before.get("phase") == "approved"
            and tuple(snapshot.next) == ("render",)
        )
        if awaiting_review:
            state = graph.invoke(
                Command(resume={"action": args.action, "reason": args.reason}),
                config,
            )
        elif approved_pending_render:
            decision = before.get("human_review")
            if not isinstance(decision, Mapping) or (
                decision.get("action") != args.action
                or decision.get("reason") != args.reason
            ):
                raise DellReferenceVerticalCLIError(
                    "terminal_review_decision_binding_mismatch"
                )
            state = graph.continue_from_checkpoint(config)
        elif terminal_checkpoint_repair:
            decision = before.get("human_review")
            if not isinstance(decision, Mapping) or (
                decision.get("action") != args.action
                or decision.get("reason") != args.reason
            ):
                raise DellReferenceVerticalCLIError(
                    "terminal_review_decision_binding_mismatch"
                )
            state = before
        else:
            raise DellReferenceVerticalCLIError(
                "checkpoint_not_awaiting_review_or_matching_terminal"
            )
    _assert_current_implementation_matches(manifest)
    ready_state = _json_ready(state)
    phase = ready_state.get("phase")
    if phase != expected_phase:
        raise DellReferenceVerticalCLIError("resume_terminal_phase_invalid")
    terminal_decision = ready_state.get("human_review")
    if not isinstance(terminal_decision, Mapping) or (
        terminal_decision.get("action") != args.action
        or terminal_decision.get("reason") != args.reason
    ):
        raise DellReferenceVerticalCLIError(
            "terminal_review_decision_binding_mismatch"
        )
    human_review_digest = _canonical_digest(terminal_decision)
    terminal_state_digest = _canonical_digest(ready_state)
    state_created = _write_or_validate_json(
        attempt_dir / f"state.{suffix}.json", ready_state
    )
    report_created = False
    if args.action == "approve":
        report = ready_state.get("final_report")
        if not isinstance(report, Mapping):
            raise DellReferenceVerticalCLIError("approved_report_missing")
        report_created = _write_or_validate_json(
            attempt_dir / "final-report.json", report
        )
    model_call_audit = _model_call_audit_summary(attempt_dir)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": suffix,
        "attempt_id": attempt_id,
        "run_id": run_id,
        "case_id": manifest["case_id"],
        "snapshot_id": manifest["snapshot_id"],
        "phase": phase,
        "action": args.action,
        "reason_recorded": bool(args.reason),
        "resumed_at": resumed_at,
        "completed_at": datetime.now().astimezone().isoformat(),
        "resume_wall_elapsed_ms": round((perf_counter() - resumed_tick) * 1_000, 3),
        "composition_digest": manifest["composition_digest"],
        "implementation_binding_digest": manifest["implementation_binding"][
            "binding_digest"
        ],
        "report_digest": (
            ready_state.get("final_report", {}).get("report_digest")
            if isinstance(ready_state.get("final_report"), Mapping)
            else None
        ),
        "human_review_digest": human_review_digest,
        "terminal_state_digest": terminal_state_digest,
        "model_or_tool_reexecution_on_resume": False,
        "model_call_audit": model_call_audit,
        "model_call_audit_digest": _canonical_digest(model_call_audit),
        "artifact_materialization_mode": (
            "terminal_checkpoint_repair"
            if terminal_checkpoint_repair
            else (
                "approved_checkpoint_render_recovery"
                if approved_pending_render
                else "post_resume_export"
            )
        ),
        "state_artifact_created": state_created,
        "report_artifact_created": report_created,
        "api_key_required_on_resume": False,
        "automatic_human_approval": False,
    }
    summary_path = attempt_dir / f"summary.{suffix}.json"
    if summary_path.exists():
        existing_summary = _read_json(summary_path, f"summary_{suffix}")
        stable_fields = (
            "schema_version",
            "status",
            "attempt_id",
            "run_id",
            "case_id",
            "snapshot_id",
            "phase",
            "action",
            "composition_digest",
            "implementation_binding_digest",
            "report_digest",
            "human_review_digest",
            "terminal_state_digest",
            "model_call_audit_digest",
            "model_or_tool_reexecution_on_resume",
            "api_key_required_on_resume",
            "automatic_human_approval",
        )
        if any(
            existing_summary.get(field) != summary.get(field)
            for field in stable_fields
        ):
            raise DellReferenceVerticalCLIError(
                f"existing_artifact_identity_mismatch:{summary_path.name}"
            )
        summary = existing_summary
    else:
        _write_new_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "start":
            return _start(args)
        return _resume(args)
    except DellReferenceVerticalCLIError as exc:
        failure = {
            "schema_version": SCHEMA_VERSION,
            "status": "cli_failed",
            **_safe_error(exc),
        }
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
