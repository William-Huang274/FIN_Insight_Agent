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
    {
        "artifact_id": "multi_agent_summary",
        "label": "Multi-agent summary",
        "rel_path": "multi_agent_summary.json",
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
    if (root / "real_chain_eval_summary.json").exists():
        return _inspect_vnext_eval_artifacts(root)

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
    multi_agent = _find_artifact(artifacts, "multi_agent_summary")
    state_summary = state.summary if state and state.exists else native_summary.summary if native_summary and native_summary.exists else {}
    if multi_agent and multi_agent.exists:
        state_summary = {**state_summary, "multi_agent": multi_agent.summary}
    return RunArtifactIndex(
        run_dir=str(root),
        status=status,
        artifacts=artifacts,
        missing_required=missing_required,
        warnings=warnings,
        errors=errors,
        answer_preview=rendered.preview if rendered else "",
        state_summary=state_summary,
        gate_summary=gates.summary if gates else {},
        performance_summary=performance.summary if performance else {},
    )


def _inspect_vnext_eval_artifacts(root: Path) -> RunArtifactIndex:
    summary_path = root / "real_chain_eval_summary.json"
    summary_payload: dict[str, Any] = {}
    try:
        loaded = json.loads(summary_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            summary_payload = loaded
    except Exception:
        summary_payload = {}
    case_ids = [
        str(case.get("case_id") or "").strip()
        for case in summary_payload.get("cases") or []
        if isinstance(case, dict) and str(case.get("case_id") or "").strip()
    ]
    if not case_ids:
        case_ids = sorted(path.name for path in root.iterdir() if path.is_dir() and (path / "real_chain_case_score.json").exists())

    specs: list[dict[str, Any]] = [
        {
            "artifact_id": "vnext_eval_summary",
            "label": "VNext eval summary",
            "rel_path": "real_chain_eval_summary.json",
            "kind": "json",
            "required": True,
        },
        {
            "artifact_id": "vnext_output_quality_audit",
            "label": "VNext output quality audit",
            "rel_path": "multi_agent_output_quality_audit.json",
            "kind": "json",
            "required": False,
        },
        {
            "artifact_id": "vnext_output_quality_audit_md",
            "label": "VNext output quality audit markdown",
            "rel_path": "multi_agent_output_quality_audit.md",
            "kind": "markdown",
            "required": False,
        },
    ]
    for case_id in case_ids:
        prefix = case_id
        specs.extend(
            [
                _case_artifact_spec(case_id, "case_score", "Case score", f"{prefix}/real_chain_case_score.json", "json", True),
                _case_artifact_spec(case_id, "rendered_answer", "Rendered answer", f"{prefix}/qwen/rendered_answer.md", "markdown", True),
                _case_artifact_spec(case_id, "memo_answer", "Memo answer", f"{prefix}/memo_answer.json", "json", True),
                _case_artifact_spec(case_id, "claim_cards", "ClaimCards", f"{prefix}/claim_cards.json", "json", True),
                _case_artifact_spec(case_id, "typed_gap_ledger", "Typed gap ledger", f"{prefix}/typed_gap_ledger.json", "json", True),
                _case_artifact_spec(case_id, "gate_registry", "Gate matrix", f"{prefix}/gate_registry_eval_matrix.json", "json", True),
                _case_artifact_spec(case_id, "run_audit", "Run audit materialization", f"{prefix}/run_audit_materialization_report.json", "json", True),
                _case_artifact_spec(case_id, "context_memory", "Analyst context memory", f"{prefix}/analyst_view_research_memory.json", "json", True),
                _case_artifact_spec(case_id, "native_checkpoints", "LangGraph checkpoints", f"{prefix}/langgraph_node_checkpoints.json", "json", True),
                _case_artifact_spec(case_id, "pre_memo_fact_selection", "Pre-memo fact selection", f"{prefix}/pre_memo_fact_selection.json", "json", True),
            ]
        )

    artifacts = [_inspect_artifact(root, spec) for spec in specs]
    missing_required = [artifact.artifact_id for artifact in artifacts if artifact.required and not artifact.exists]
    errors = [f"{artifact.artifact_id}: {artifact.error}" for artifact in artifacts if artifact.error]
    warnings = [f"{artifact.artifact_id}: missing" for artifact in artifacts if artifact.required and not artifact.exists]
    status = "fail" if errors or missing_required else "pass"
    case_summaries = [_vnext_case_trace_summary(root, case_id) for case_id in case_ids]
    rendered = next((artifact for artifact in artifacts if artifact.artifact_id.endswith(":rendered_answer") and artifact.exists), None)
    return RunArtifactIndex(
        run_dir=str(root),
        status=status,
        artifacts=artifacts,
        missing_required=missing_required,
        warnings=warnings,
        errors=errors,
        answer_preview=rendered.preview if rendered else "",
        state_summary={
            "eval_output_type": "multi_agent_vnext_real_chain",
            "run_id": summary_payload.get("run_id"),
            "gate_status": summary_payload.get("gate_status"),
            "case_count": len(case_ids),
            "pass_count": sum(1 for case in case_summaries if case.get("gate_status") == "pass"),
            "failure_count": sum(1 for case in case_summaries if case.get("gate_status") != "pass"),
            "cases": case_summaries,
        },
        gate_summary={
            "gate_status": summary_payload.get("gate_status"),
            "case_gate_statuses": {str(case.get("case_id")): case.get("gate_status") for case in summary_payload.get("cases") or [] if isinstance(case, dict)},
        },
        performance_summary={
            "elapsed_ms": summary_payload.get("elapsed_ms"),
            "case_elapsed_ms": {
                str(case.get("case_id")): case.get("elapsed_ms")
                for case in summary_payload.get("cases") or []
                if isinstance(case, dict)
            },
        },
    )


def _case_artifact_spec(case_id: str, artifact_id: str, label: str, rel_path: str, kind: str, required: bool) -> dict[str, Any]:
    return {
        "artifact_id": f"{case_id}:{artifact_id}",
        "label": f"{case_id} / {label}",
        "rel_path": rel_path,
        "kind": kind,
        "required": required,
    }


def _vnext_case_trace_summary(root: Path, case_id: str) -> dict[str, Any]:
    case_dir = root / case_id
    score = _read_json_object(case_dir / "real_chain_case_score.json")
    claims = _read_json_object(case_dir / "claim_cards.json")
    gaps = _read_json_object(case_dir / "typed_gap_ledger.json")
    gates = _read_json_object(case_dir / "gate_registry_eval_matrix.json")
    audit = _read_json_object(case_dir / "run_audit_materialization_report.json")
    memo = _read_json_object(case_dir / "memo_answer.json")
    rendered_path = case_dir / "qwen" / "rendered_answer.md"
    supported_claims = claims.get("supported_claims") if isinstance(claims.get("supported_claims"), list) else []
    return {
        "case_id": case_id,
        "gate_status": score.get("gate_status"),
        "memo_status": memo.get("answer_status"),
        "supported_claim_count": len(supported_claims),
        "gap_count": int(gaps.get("gap_count") or len(gaps.get("gaps") or [])) if gaps else 0,
        "gate_result_count": len(gates.get("gate_history") or []) if gates else 0,
        "run_audit_status": audit.get("status"),
        "run_audit_db_path": audit.get("db_path"),
        "rendered_answer_chars": rendered_path.stat().st_size if rendered_path.exists() else 0,
        "claim_dimensions": sorted(
            {
                str(claim.get("analysis_dimension") or "")
                for claim in supported_claims
                if str(claim.get("analysis_dimension") or "")
            }
        ),
    }


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


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
    elif artifact_id == "multi_agent_summary":
        summary.update(
            {
                "run_id": payload.get("run_id"),
                "status": payload.get("status"),
                "execution_mode": payload.get("execution_mode"),
                "activated_agent_count": len(payload.get("activated_agents") or []),
                "skipped_agent_count": len(payload.get("skipped_agents") or []),
                "tool_call_count": payload.get("tool_call_count"),
                "loop_break_reason": payload.get("loop_break_reason"),
                "bounded_answer_allowed": payload.get("bounded_answer_allowed"),
                "second_pass_attempts": (payload.get("second_pass") or {}).get("attempts") if isinstance(payload.get("second_pass"), dict) else None,
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
