from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ArtifactSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    label: str
    rel_path: str
    path: str
    kind: str
    exists: bool
    required: bool
    status: str
    size_bytes: int = 0
    modified_at: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    preview: str = ""
    error: str = ""


class RunArtifactIndex(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_dir: str
    status: str
    artifacts: list[ArtifactSummary]
    missing_required: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    answer_preview: str = ""
    state_summary: dict[str, Any] = Field(default_factory=dict)
    gate_summary: dict[str, Any] = Field(default_factory=dict)
    performance_summary: dict[str, Any] = Field(default_factory=dict)


KNOWN_ARTIFACTS: tuple[dict[str, Any], ...] = (
    {
        "artifact_id": "graph_state",
        "label": "Graph state",
        "rel_path": "sec_agent_state.json",
        "kind": "json",
        "required": True,
    },
    {
        "artifact_id": "query_contract",
        "label": "Query Contract",
        "rel_path": "query_contract.json",
        "kind": "json",
        "required": False,
    },
    {
        "artifact_id": "coverage_matrix",
        "label": "Evidence Coverage Matrix",
        "rel_path": "runtime_evidence_coverage_matrix.json",
        "kind": "json",
        "required": False,
    },
    {
        "artifact_id": "exact_value_ledger",
        "label": "Exact-Value Ledger",
        "rel_path": "runtime_exact_value_ledger.json",
        "kind": "json",
        "required": False,
    },
    {
        "artifact_id": "judgment_plan",
        "label": "Judgment Plan",
        "rel_path": "runtime_judgment_plan.json",
        "kind": "json",
        "required": False,
    },
    {
        "artifact_id": "rendered_answer",
        "label": "Rendered answer",
        "rel_path": "qwen/rendered_answer.md",
        "kind": "markdown",
        "required": False,
    },
    {
        "artifact_id": "agent_outputs",
        "label": "Model outputs",
        "rel_path": "qwen/agent_outputs.jsonl",
        "kind": "jsonl",
        "required": False,
    },
    {
        "artifact_id": "post_gates",
        "label": "Post gates",
        "rel_path": "post_gates/sec_benchmark_post_gates_summary.json",
        "kind": "json",
        "required": False,
    },
    {
        "artifact_id": "market_context",
        "label": "Market snapshot context",
        "rel_path": "market_snapshot_context_rows.jsonl",
        "kind": "jsonl",
        "required": False,
    },
    {
        "artifact_id": "data_fingerprint",
        "label": "Run data fingerprint",
        "rel_path": "run_data_fingerprint.json",
        "kind": "json",
        "required": False,
    },
    {
        "artifact_id": "performance",
        "label": "Run performance",
        "rel_path": "run_performance.json",
        "kind": "json",
        "required": False,
    },
    {
        "artifact_id": "native_checkpoints",
        "label": "LangGraph native checkpoints",
        "rel_path": "langgraph_node_checkpoints.json",
        "kind": "json",
        "required": False,
    },
    {
        "artifact_id": "native_summary",
        "label": "LangGraph native summary",
        "rel_path": "langgraph_native_summary.json",
        "kind": "json",
        "required": False,
    },
)


def inspect_run_artifacts(run_dir: str | Path) -> RunArtifactIndex:
    root = Path(run_dir).resolve()
    if not root.exists():
        return RunArtifactIndex(
            run_dir=str(root),
            status="fail",
            artifacts=[],
            errors=["run_dir_not_found"],
        )
    if not root.is_dir():
        return RunArtifactIndex(
            run_dir=str(root),
            status="fail",
            artifacts=[],
            errors=["run_dir_not_directory"],
        )

    artifacts = [_inspect_artifact(root, spec) for spec in KNOWN_ARTIFACTS]
    has_native_state = bool(_find_artifact(artifacts, "native_checkpoints") and _find_artifact(artifacts, "native_checkpoints").exists)
    missing_required = [
        artifact.artifact_id
        for artifact in artifacts
        if artifact.required and not artifact.exists and not (artifact.artifact_id == "graph_state" and has_native_state)
    ]
    errors = [f"{artifact.artifact_id}: {artifact.error}" for artifact in artifacts if artifact.error]
    warnings = [
        f"{artifact.artifact_id}: missing"
        for artifact in artifacts
        if not artifact.exists and artifact.required and not (artifact.artifact_id == "graph_state" and has_native_state)
    ]
    status = "fail" if errors else "warn" if missing_required else "pass"
    rendered = _find_artifact(artifacts, "rendered_answer")
    state = _find_artifact(artifacts, "graph_state")
    native_summary = _find_artifact(artifacts, "native_summary")
    gates = _find_artifact(artifacts, "post_gates")
    performance = _find_artifact(artifacts, "performance")
    return RunArtifactIndex(
        run_dir=str(root),
        status=status,
        artifacts=artifacts,
        missing_required=missing_required,
        warnings=warnings,
        errors=errors,
        answer_preview=rendered.preview if rendered else "",
        state_summary=state.summary if state and state.exists else native_summary.summary if native_summary and native_summary.exists else {},
        gate_summary=gates.summary if gates else {},
        performance_summary=performance.summary if performance else {},
    )


def _inspect_artifact(root: Path, spec: dict[str, Any]) -> ArtifactSummary:
    rel_path = str(spec["rel_path"])
    path = root / rel_path
    base = {
        "artifact_id": str(spec["artifact_id"]),
        "label": str(spec["label"]),
        "rel_path": rel_path,
        "path": str(path),
        "kind": str(spec["kind"]),
        "required": bool(spec["required"]),
    }
    if not path.exists():
        return ArtifactSummary(
            **base,
            exists=False,
            status="warn" if spec["required"] else "missing",
        )
    if not path.is_file():
        return ArtifactSummary(
            **base,
            exists=False,
            status="fail",
            error="artifact_path_not_file",
        )
    stat = path.stat()
    try:
        summary, preview = _summarize_artifact(path, str(spec["kind"]), str(spec["artifact_id"]))
        status = "pass"
        error = ""
    except Exception as exc:
        summary = {}
        preview = ""
        status = "fail"
        error = f"{type(exc).__name__}: {exc}"
    return ArtifactSummary(
        **base,
        exists=True,
        status=status,
        size_bytes=stat.st_size,
        modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        summary=summary,
        preview=preview,
        error=error,
    )


def _summarize_artifact(path: Path, kind: str, artifact_id: str) -> tuple[dict[str, Any], str]:
    if kind == "json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return _json_summary(payload, artifact_id), _compact_preview(payload)
    if kind == "jsonl":
        rows = _read_jsonl(path)
        summary = {
            "row_count": len(rows),
            "first_row_keys": sorted(rows[0].keys())[:20] if rows else [],
        }
        return summary, _compact_preview(rows[:2])
    text = path.read_text(encoding="utf-8", errors="replace")
    return {"line_count": len(text.splitlines()), "char_count": len(text)}, text[:1200]


def _json_summary(payload: Any, artifact_id: str) -> dict[str, Any]:
    if isinstance(payload, list):
        return {"type": "list", "row_count": len(payload)}
    if not isinstance(payload, dict):
        return {"type": type(payload).__name__}
    summary: dict[str, Any] = {
        "type": "object",
        "keys": sorted(payload.keys())[:24],
    }
    if artifact_id == "graph_state":
        summary.update(
            {
                "run_id": payload.get("run_id"),
                "status": payload.get("status"),
                "source_policy": payload.get("source_policy"),
                "selected_tickers": payload.get("selected_tickers") or [],
                "selected_years": payload.get("selected_years") or [],
                "stage_count": len(payload.get("stages") or []),
            }
        )
    elif artifact_id == "coverage_matrix":
        inner = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        summary.update(
            {
                "coverage_complete": inner.get("coverage_complete"),
                "primary_task_support_complete": inner.get("primary_task_support_complete"),
                "context_row_count": inner.get("context_row_count"),
                "ledger_row_count": inner.get("ledger_row_count"),
            }
        )
    elif artifact_id == "query_contract":
        summary.update(
            {
                "task_type": payload.get("task_type"),
                "source_policy": payload.get("source_policy"),
                "ticker_count": len(payload.get("selected_tickers") or payload.get("tickers") or []),
                "filing_types": payload.get("filing_types") or [],
            }
        )
    elif artifact_id == "exact_value_ledger":
        rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
        summary["row_count"] = len(rows)
    elif artifact_id == "judgment_plan":
        plans = payload.get("plans") if isinstance(payload.get("plans"), list) else []
        summary["plan_count"] = len(plans)
    elif artifact_id == "native_checkpoints":
        summary.update(
            {
                "run_id": payload.get("run_id"),
                "status": payload.get("status"),
                "checkpoint_count": payload.get("checkpoint_count"),
                "latest_completed_node": payload.get("latest_completed_node"),
                "latest_checkpoint_id": payload.get("latest_checkpoint_id"),
            }
        )
    elif artifact_id == "native_summary":
        state_summary = payload.get("state_summary") if isinstance(payload.get("state_summary"), dict) else {}
        summary.update(
            {
                "run_id": payload.get("run_id"),
                "status": payload.get("status"),
                "node_count": len(payload.get("node_checkpoints") or []),
                "latest_completed_node": state_summary.get("latest_completed_node") or payload.get("latest_completed_node"),
            }
        )
    elif artifact_id == "post_gates":
        false_gates = [key for key, value in payload.items() if key.endswith("_gate_pass") and value is False]
        true_gate_count = sum(1 for key, value in payload.items() if key.endswith("_gate_pass") and value is True)
        summary.update({"false_gates": false_gates, "true_gate_count": true_gate_count})
    elif artifact_id == "performance":
        stages = payload.get("stages") if isinstance(payload.get("stages"), list) else []
        summary.update(
            {
                "total_elapsed_ms": payload.get("total_elapsed_ms") or payload.get("elapsed_ms"),
                "stage_count": len(stages),
            }
        )
    return summary


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _compact_preview(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)[:1200]


def _find_artifact(artifacts: list[ArtifactSummary], artifact_id: str) -> ArtifactSummary | None:
    return next((artifact for artifact in artifacts if artifact.artifact_id == artifact_id), None)
