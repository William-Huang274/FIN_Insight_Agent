from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sec_agent.graph_state import ARTIFACT_KEYS, SecAgentState


GRAPH_NODE_ORDER = (
    "plan_query",
    "validate_query_contract",
    "retrieve_context",
    "rerank_context",
    "build_runtime_ledger",
    "build_coverage_matrix",
    "build_judgment_plan",
    "synthesize_memo",
    "verify_claims",
    "run_deterministic_gates",
    "render_answer",
)

GRAPH_NODE_OUTPUTS = {
    "plan_query": ("query_contract",),
    "retrieve_context": ("retrieved_context",),
    "rerank_context": ("retrieved_context",),
    "build_runtime_ledger": ("runtime_exact_value_ledger",),
    "build_coverage_matrix": ("evidence_coverage_matrix",),
    "build_judgment_plan": ("judgment_plan",),
    "synthesize_memo": ("evidence_pack", "memo_answer"),
    "verify_claims": ("claim_verification",),
    "run_deterministic_gates": ("deterministic_gates",),
    "render_answer": ("rendered_answer",),
}

GRAPH_NODE_DEPENDENCIES = {
    "validate_query_contract": ("query_contract",),
    "retrieve_context": ("query_contract",),
    "rerank_context": ("retrieved_context",),
    "build_runtime_ledger": ("query_contract", "retrieved_context"),
    "build_coverage_matrix": ("query_contract", "retrieved_context", "runtime_exact_value_ledger"),
    "build_judgment_plan": ("query_contract", "retrieved_context", "runtime_exact_value_ledger", "evidence_coverage_matrix"),
    "synthesize_memo": ("query_contract", "retrieved_context", "runtime_exact_value_ledger", "evidence_coverage_matrix", "judgment_plan"),
    "verify_claims": ("memo_answer", "retrieved_context", "runtime_exact_value_ledger", "evidence_coverage_matrix", "judgment_plan"),
    "run_deterministic_gates": ("memo_answer", "claim_verification", "runtime_exact_value_ledger", "judgment_plan"),
    "render_answer": ("memo_answer", "deterministic_gates"),
}


@dataclass
class NodeResult:
    node_name: str
    status: str
    state: SecAgentState
    message: str = ""
    metadata: dict[str, Any] | None = None


SecAgentNode = Callable[[SecAgentState], SecAgentState]


def node_order() -> tuple[str, ...]:
    return GRAPH_NODE_ORDER


def expected_outputs(node_name: str) -> tuple[str, ...]:
    return GRAPH_NODE_OUTPUTS.get(str(node_name), ())


def missing_dependencies(state: SecAgentState, node_name: str) -> list[str]:
    required = GRAPH_NODE_DEPENDENCIES.get(str(node_name), ())
    return [key for key in required if key not in state.artifacts]


def validate_node_ready(state: SecAgentState, node_name: str) -> None:
    if str(node_name) not in GRAPH_NODE_ORDER:
        raise ValueError(f"unknown graph node: {node_name}")
    missing = missing_dependencies(state, node_name)
    if missing:
        raise ValueError(f"node {node_name} missing dependencies: {', '.join(missing)}")


def run_node(state: SecAgentState, node_name: str, func: SecAgentNode) -> NodeResult:
    validate_node_ready(state, node_name)
    started = time.time()
    started_at = _epoch_iso(started)
    state.mark_stage(node_name, "running", started_at=started_at)
    try:
        next_state = func(state)
    except Exception as exc:
        elapsed_ms = int((time.time() - started) * 1000)
        state.add_error(stage=node_name, message=f"{type(exc).__name__}: {exc}")
        state.mark_stage(
            node_name,
            "failed",
            started_at=started_at,
            finished_at=_epoch_iso(time.time()),
            elapsed_ms=elapsed_ms,
            message=str(exc),
        )
        return NodeResult(node_name=node_name, status="failed", state=state, message=str(exc))

    elapsed_ms = int((time.time() - started) * 1000)
    next_state.mark_stage(
        node_name,
        "completed",
        started_at=started_at,
        finished_at=_epoch_iso(time.time()),
        elapsed_ms=elapsed_ms,
    )
    return NodeResult(node_name=node_name, status="completed", state=next_state)


def artifact_contract() -> dict[str, Any]:
    return {
        "artifact_keys": list(ARTIFACT_KEYS),
        "node_order": list(GRAPH_NODE_ORDER),
        "node_outputs": {key: list(value) for key, value in GRAPH_NODE_OUTPUTS.items()},
        "node_dependencies": {key: list(value) for key, value in GRAPH_NODE_DEPENDENCIES.items()},
    }


def state_resume_report(state: SecAgentState) -> dict[str, Any]:
    artifact_status = {
        key: _artifact_status(key, state.artifacts.get(key))
        for key in ARTIFACT_KEYS
    }
    last_stage_status: dict[str, str] = {}
    for stage in state.stages:
        last_stage_status[stage.name] = stage.status

    completed_or_available = {
        key for key, status in artifact_status.items() if status.get("exists") and status.get("digest_ok")
    }
    missing_outputs = {
        node: [key for key in expected_outputs(node) if key not in completed_or_available]
        for node in GRAPH_NODE_ORDER
    }
    ready_nodes = []
    blocked_nodes = {}
    for node in GRAPH_NODE_ORDER:
        if not missing_outputs.get(node):
            continue
        missing = [
            key
            for key in GRAPH_NODE_DEPENDENCIES.get(node, ())
            if key not in completed_or_available
        ]
        if missing:
            blocked_nodes[node] = missing
        else:
            ready_nodes.append(node)

    return {
        "schema_version": "sec_agent_resume_report_v0.1",
        "run_id": state.run_id,
        "status": state.status,
        "output_dir": state.output_dir,
        "artifact_status": artifact_status,
        "last_stage_status": last_stage_status,
        "ready_nodes": ready_nodes,
        "next_ready_node": ready_nodes[0] if ready_nodes else None,
        "blocked_nodes": blocked_nodes,
        "missing_artifacts": [key for key, value in artifact_status.items() if not value.get("exists")],
        "digest_mismatch_artifacts": [
            key for key, value in artifact_status.items() if value.get("exists") and not value.get("digest_ok")
        ],
        "complete_artifacts": sorted(completed_or_available),
    }


def _artifact_status(key: str, artifact: Any) -> dict[str, Any]:
    if artifact is None:
        return {"key": key, "path": "", "exists": False, "digest_ok": False}
    path = Path(str(getattr(artifact, "path", "") or ""))
    exists = path.exists() and path.is_file()
    expected_digest = str(getattr(artifact, "digest", "") or "")
    actual_digest = _file_digest(path) if exists and expected_digest else ""
    digest_ok = bool(exists and (not expected_digest or actual_digest == expected_digest))
    return {
        "key": key,
        "path": str(path),
        "exists": exists,
        "digest_ok": digest_ok,
        "expected_digest": expected_digest,
        "actual_digest": actual_digest,
        "row_count": getattr(artifact, "row_count", None),
    }


def _file_digest(path: Path) -> str:
    import hashlib

    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()[:16]


def _epoch_iso(value: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(value))
