from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


DEFAULT_MAX_ARTIFACT_BYTES = 200_000

KNOWN_RUN_ARTIFACTS: dict[str, str] = {
    "graph_state": "sec_agent_state.json",
    "query_contract": "query_contract.json",
    "coverage_matrix": "runtime_evidence_coverage_matrix.json",
    "exact_value_ledger": "runtime_exact_value_ledger.json",
    "judgment_plan": "runtime_judgment_plan.json",
    "rendered_answer": "qwen/rendered_answer.md",
    "agent_outputs": "qwen/agent_outputs.jsonl",
    "post_gates": "post_gates/sec_benchmark_post_gates_summary.json",
    "market_context": "market_snapshot_context_rows.jsonl",
    "industry_context": "industry_snapshot_context_rows.jsonl",
    "data_fingerprint": "run_data_fingerprint.json",
    "performance": "run_performance.json",
    "native_checkpoints": "langgraph_node_checkpoints.json",
    "native_summary": "langgraph_native_summary.json",
}


def read_bounded_artifact(
    *,
    run_dir: str | Path,
    artifact_id: str = "",
    rel_path: str = "",
    max_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES,
    parse_json: bool = False,
) -> dict[str, Any]:
    """Read one saved run artifact without allowing path escape or unbounded output."""
    root = Path(run_dir).resolve()
    if not root.exists() or not root.is_dir():
        return {"status": "error", "error": "run_dir_not_found", "run_dir": str(root)}

    resolved_rel_path = _resolve_artifact_rel_path(artifact_id=artifact_id, rel_path=rel_path)
    if not resolved_rel_path:
        return {"status": "error", "error": "artifact_id_or_rel_path_required", "run_dir": str(root)}

    path = (root / resolved_rel_path).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return {"status": "error", "error": "artifact_path_escapes_run_dir", "run_dir": str(root), "rel_path": resolved_rel_path}
    if not path.exists() or not path.is_file():
        return {"status": "error", "error": "artifact_not_found", "run_dir": str(root), "rel_path": resolved_rel_path}

    limit = max(1, min(int(max_bytes or DEFAULT_MAX_ARTIFACT_BYTES), 2_000_000))
    raw = path.read_bytes()
    truncated = len(raw) > limit
    content = raw[:limit].decode("utf-8", errors="replace")
    payload: dict[str, Any] = {
        "status": "truncated" if truncated else "ok",
        "artifact_id": artifact_id or _artifact_id_for_rel_path(resolved_rel_path),
        "rel_path": resolved_rel_path,
        "digest": hashlib.sha256(raw).hexdigest(),
        "content": content,
        "json": {},
        "truncated": truncated,
    }
    if parse_json and not truncated and path.suffix.lower() == ".json":
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            payload["status"] = "error"
            payload["error"] = f"json_parse_failed:{exc.msg}"
        else:
            payload["json"] = parsed if isinstance(parsed, dict) else {"value": parsed}
    return payload


def _resolve_artifact_rel_path(*, artifact_id: str, rel_path: str) -> str:
    artifact = str(artifact_id or "").strip()
    rel = str(rel_path or "").strip().replace("\\", "/")
    if artifact:
        return KNOWN_RUN_ARTIFACTS.get(artifact, "")
    if rel.startswith("/") or rel.startswith("../") or "/../" in rel:
        return ""
    return rel


def _artifact_id_for_rel_path(rel_path: str) -> str:
    normalized = str(rel_path or "").replace("\\", "/")
    for artifact_id, candidate in KNOWN_RUN_ARTIFACTS.items():
        if normalized == candidate:
            return artifact_id
    return ""

