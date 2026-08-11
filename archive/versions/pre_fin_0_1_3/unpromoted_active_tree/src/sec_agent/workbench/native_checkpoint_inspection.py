from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


CHECKPOINT_RESUME_INSPECTION_SCHEMA = (
    "sec_agent_langgraph_checkpoint_resume_inspection_v0.1"
)
NATIVE_NODE_ORDER = (
    "load_session_state",
    "plan_query",
    "validate_query_contract",
    "compile_retrieval_plan",
    "execute_retrieval_routes",
    "attach_market_snapshot",
    "attach_industry_snapshot",
    "build_runtime_ledger",
    "assess_evidence_coverage",
    "assess_evidence_sufficiency",
    "build_judgment_plan",
    "synthesize_answer",
    "verify_claims",
    "run_deterministic_gates",
    "render_answer",
    "persist_session_state",
)
NATIVE_RESUME_REQUIRED_ARTIFACTS = {
    "execute_retrieval_routes": ("case", "retrieval_plan"),
    "attach_market_snapshot": ("retrieved_context",),
    "attach_industry_snapshot": ("retrieved_context",),
    "build_runtime_ledger": ("retrieved_context",),
    "assess_evidence_coverage": (
        "retrieved_context",
        "runtime_exact_value_ledger",
    ),
    "assess_evidence_sufficiency": ("evidence_coverage_matrix",),
    "execute_second_pass_retrieval": ("evidence_coverage_matrix",),
    "build_judgment_plan": (
        "runtime_exact_value_ledger",
        "evidence_coverage_matrix",
    ),
    "synthesize_answer": (
        "retrieved_context",
        "runtime_exact_value_ledger",
        "evidence_coverage_matrix",
        "judgment_plan",
    ),
    "verify_claims": (
        "retrieved_context",
        "runtime_exact_value_ledger",
        "memo_answer",
    ),
    "run_deterministic_gates": (
        "runtime_exact_value_ledger",
        "judgment_plan",
        "claim_verification",
    ),
    "render_answer": ("deterministic_gates",),
    "persist_session_state": ("rendered_answer",),
}


def inspect_native_checkpoint_artifact(path: str | Path) -> dict[str, Any]:
    """Inspect a saved graph checkpoint without importing the graph runtime."""

    checkpoint_path = _resolve_checkpoint_artifact_path(path)
    payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    latest_node = str(payload.get("latest_completed_node") or "")
    state_summary = (
        dict(payload["recoverable_state_summary"])
        if isinstance(payload.get("recoverable_state_summary"), dict)
        else {}
    )
    next_node = _next_recoverable_node(latest_node, state_summary)
    artifact_status = _inspect_artifact_refs(payload.get("artifact_refs") or {})
    required = list(NATIVE_RESUME_REQUIRED_ARTIFACTS.get(next_node, ()))
    missing = [
        key for key in required if not artifact_status.get(key, {}).get("exists")
    ]
    digest_mismatch = [
        key
        for key in required
        if artifact_status.get(key, {}).get("exists")
        and artifact_status.get(key, {}).get("digest")
        and artifact_status.get(key, {}).get("actual_digest")
        and artifact_status[key]["digest"]
        != artifact_status[key]["actual_digest"]
    ]
    blocked_reasons: list[str] = []
    if missing:
        blocked_reasons.append("missing_required_artifacts")
    if digest_mismatch:
        blocked_reasons.append("digest_mismatch_artifacts")
    if not next_node:
        blocked_reasons.append("no_next_node")
    return {
        "schema_version": CHECKPOINT_RESUME_INSPECTION_SCHEMA,
        "checkpoint_path": str(checkpoint_path.resolve()),
        "run_id": payload.get("run_id") or "",
        "status": payload.get("status") or "",
        "checkpoint_count": payload.get("checkpoint_count") or 0,
        "latest_checkpoint_id": payload.get("latest_checkpoint_id") or "",
        "latest_completed_node": latest_node,
        "next_recoverable_node": next_node,
        "required_artifacts_for_next_node": required,
        "resume_supported": bool(
            next_node and not missing and not digest_mismatch
        ),
        "blocked_reasons": blocked_reasons,
        "missing_required_artifacts": missing,
        "digest_mismatch_artifacts": digest_mismatch,
        "artifact_status": artifact_status,
        "recoverable_state_summary": state_summary,
    }


def _resolve_checkpoint_artifact_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_dir():
        candidate = candidate / "langgraph_node_checkpoints.json"
    if not candidate.is_file():
        raise FileNotFoundError(f"node checkpoint artifact not found: {candidate}")
    return candidate


def _next_recoverable_node(
    latest_node: str, state_summary: dict[str, Any]
) -> str:
    if not latest_node or latest_node == "persist_session_state":
        return ""
    if latest_node == "assess_evidence_sufficiency":
        if str(state_summary.get("sufficiency_level") or "") == "sufficient":
            return "build_judgment_plan"
        return "execute_second_pass_retrieval"
    if latest_node == "execute_second_pass_retrieval":
        return "build_runtime_ledger"
    if latest_node not in NATIVE_NODE_ORDER:
        return ""
    index = NATIVE_NODE_ORDER.index(latest_node)
    return (
        NATIVE_NODE_ORDER[index + 1]
        if index + 1 < len(NATIVE_NODE_ORDER)
        else ""
    )


def _inspect_artifact_refs(
    refs: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    status: dict[str, dict[str, Any]] = {}
    for key, ref in sorted(refs.items()):
        if not isinstance(ref, dict):
            continue
        path = Path(str(ref.get("path") or ""))
        self_referential = bool(ref.get("self_referential"))
        exists = path.is_file()
        actual_digest = "" if self_referential else _file_digest(path)
        expected_digest = str(ref.get("digest") or "")
        status[str(key)] = {
            "path": str(path),
            "exists": exists,
            "digest": expected_digest,
            "actual_digest": actual_digest,
            "digest_ok": bool(
                exists
                and (
                    self_referential
                    or not expected_digest
                    or expected_digest == actual_digest
                )
            ),
            "self_referential": self_referential,
        }
    return status


def _file_digest(path: Path) -> str:
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]


__all__ = ["inspect_native_checkpoint_artifact"]
