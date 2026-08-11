from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


RUN_AUDIT_STORE_SCHEMA_VERSION = "sec_agent_run_audit_store_v0.2"
RUN_AUDIT_TABLES = (
    "run",
    "node_execution",
    "artifact_ref",
    "retrieval_task",
    "tool_call",
    "evidence_row",
    "claim_card",
    "gap",
    "gate_result",
    "reflection_event",
    "repair_task",
    "model_call",
    "resource_usage",
    "report_artifact",
    "context_snapshot",
    "context_event",
    "context_injection_plan",
    "uploaded_file",
    "parsed_input_artifact",
)


def migrate_run_audit_store(db_path: str | Path) -> dict[str, Any]:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as conn:
        _create_schema(conn)
        _set_metadata(conn, "schema_version", RUN_AUDIT_STORE_SCHEMA_VERSION)
        _set_metadata(conn, "schema_migration_id", "run_audit_store_v0_2")
    return {
        "schema_version": RUN_AUDIT_STORE_SCHEMA_VERSION,
        "db_path": str(path.resolve()),
        "schema_migration_status": "applied",
        "schema_objects": list(RUN_AUDIT_TABLES),
    }


def materialize_run_audit_store(db_path: str | Path, state: Mapping[str, Any]) -> dict[str, Any]:
    path = Path(db_path)
    migration = migrate_run_audit_store(path)
    run_id = _run_id(state)
    case_id = _case_id(state)
    code_commit = _code_commit(state)
    data_snapshot_id = _data_snapshot_id(state)
    rows = _audit_rows(
        state,
        run_id=run_id,
        case_id=case_id,
        code_commit=code_commit,
        data_snapshot_id=data_snapshot_id,
    )
    with _connect(path) as conn:
        _delete_run(conn, run_id)
        _insert_rows(conn, rows)
    counts = read_run_audit_counts(path, run_id=run_id)
    return {
        "schema_version": RUN_AUDIT_STORE_SCHEMA_VERSION,
        "db_path": str(path.resolve()),
        "run_id": run_id,
        "case_id": case_id,
        "status": "pass",
        "migration": migration,
        "table_counts": counts,
        "run_audit_policy": "sqlite_is_final_audit_source_redis_coordination_only_v0_1",
    }


def read_run_audit_counts(db_path: str | Path, *, run_id: str = "") -> dict[str, int]:
    with _connect(Path(db_path)) as conn:
        if run_id:
            return {table: _count_where_run(conn, table, run_id) for table in RUN_AUDIT_TABLES}
        return {table: _count_all(conn, table) for table in RUN_AUDIT_TABLES}


def _audit_rows(
    state: Mapping[str, Any],
    *,
    run_id: str,
    case_id: str,
    code_commit: str,
    data_snapshot_id: str,
) -> dict[str, list[dict[str, Any]]]:
    common = {
        "run_id": run_id,
        "case_id": case_id,
        "code_commit": code_commit,
        "data_snapshot_id": data_snapshot_id,
    }
    rows = {table: [] for table in RUN_AUDIT_TABLES}
    rows["run"].append(_run_row(state, common))
    rows["node_execution"].extend(_node_rows(state, common))
    rows["artifact_ref"].extend(_artifact_rows(state, common))
    rows["retrieval_task"].extend(_retrieval_task_rows(state, common))
    rows["tool_call"].extend(_tool_call_rows(state, common))
    rows["evidence_row"].extend(_evidence_rows(state, common))
    rows["claim_card"].extend(_claim_rows(state, common))
    rows["gap"].extend(_gap_rows(state, common))
    rows["gate_result"].extend(_gate_rows(state, common))
    rows["reflection_event"].extend(_reflection_event_rows(state, common))
    rows["repair_task"].extend(_repair_task_rows(state, common))
    rows["model_call"].extend(_model_call_rows(state, common))
    rows["resource_usage"].extend(_resource_usage_rows(state, common, model_call_rows=rows["model_call"]))
    rows["report_artifact"].extend(_report_artifact_rows(state, common))
    rows["context_snapshot"].extend(_context_snapshot_rows(state, common))
    rows["context_event"].extend(_context_event_rows(state, common))
    rows["context_injection_plan"].extend(_context_injection_plan_rows(state, common))
    rows["uploaded_file"].extend(_uploaded_file_rows(state, common))
    rows["parsed_input_artifact"].extend(_parsed_input_artifact_rows(state, common))
    return rows


def _run_row(state: Mapping[str, Any], common: Mapping[str, str]) -> dict[str, Any]:
    checkpoints = [row for row in state.get("node_checkpoints") or [] if isinstance(row, Mapping)]
    started_at = str(checkpoints[0].get("started_at") or checkpoints[0].get("finished_at") or "") if checkpoints else ""
    finished_at = str(checkpoints[-1].get("finished_at") or "") if checkpoints else ""
    elapsed_ms = sum(int(row.get("elapsed_ms") or 0) for row in checkpoints)
    output_dir = str(state.get("output_dir") or "")
    return {
        **common,
        "node": "",
        "input_digest": _digest(state.get("query_contract") or state.get("user_query") or ""),
        "output_digest": _digest(_summary_payload(state)),
        "artifact_uri": output_dir,
        "status": str(state.get("status") or ""),
        "started_at": started_at,
        "finished_at": finished_at,
        "elapsed_ms": elapsed_ms,
        "payload_json": _json(
            {
                "user_query": state.get("user_query") or "",
                "response_language": state.get("response_language") or "",
                "output_dir": output_dir,
                "artifact_refs": state.get("artifact_refs") or {},
                "query_contract": state.get("query_contract") or {},
            }
        ),
    }


def _node_rows(state: Mapping[str, Any], common: Mapping[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    previous_digest = ""
    for checkpoint in state.get("node_checkpoints") or []:
        if not isinstance(checkpoint, Mapping):
            continue
        node = str(checkpoint.get("node") or "")
        output_digest = str(checkpoint.get("checkpoint_id") or _digest(checkpoint))
        rows.append(
            {
                **common,
                "node": node,
                "input_digest": previous_digest,
                "output_digest": output_digest,
                "artifact_uri": "",
                "node_index": int(checkpoint.get("index") or len(rows) + 1),
                "checkpoint_id": output_digest,
                "previous_checkpoint_id": str(checkpoint.get("previous_checkpoint_id") or ""),
                "started_at": str(checkpoint.get("started_at") or ""),
                "finished_at": str(checkpoint.get("finished_at") or ""),
                "elapsed_ms": int(checkpoint.get("elapsed_ms") or 0),
                "payload_json": _json(checkpoint),
            }
        )
        previous_digest = output_digest
    return rows


def _artifact_rows(state: Mapping[str, Any], common: Mapping[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, uri in sorted((state.get("artifact_refs") or {}).items()):
        artifact_uri = str(uri or "")
        payload = {"artifact_key": key, "artifact_uri": artifact_uri, "exists": Path(artifact_uri).exists() if artifact_uri else False}
        rows.append(
            {
                **common,
                "node": "",
                "input_digest": "",
                "output_digest": _digest(payload),
                "artifact_uri": artifact_uri,
                "artifact_key": str(key),
                "artifact_type": _artifact_type(str(key), artifact_uri),
                "payload_json": _json(payload),
            }
        )
    return rows


def _evidence_rows(state: Mapping[str, Any], common: Mapping[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    sources = (
        ("context_rows", state.get("context_rows") or []),
        ("runtime_ledger_rows", state.get("runtime_ledger_rows") or []),
        ("market_snapshot_rows", state.get("market_snapshot_rows") or []),
        ("industry_snapshot_rows", state.get("industry_snapshot_rows") or []),
    )
    for source_name, values in sources:
        for index, row in enumerate(values if isinstance(values, list) else [], start=1):
            if not isinstance(row, Mapping):
                continue
            evidence_id = _first_text(
                row.get("evidence_ref"),
                row.get("evidence_id"),
                row.get("source_evidence_id"),
                row.get("object_id"),
                row.get("metric_id"),
                f"{source_name}_{index}",
            )
            payload = {"source": source_name, **dict(row)}
            rows.append(
                {
                    **common,
                    "node": _evidence_node(source_name),
                    "input_digest": "",
                    "output_digest": _digest(payload),
                    "artifact_uri": str(row.get("artifact_uri") or row.get("source_path") or ""),
                    "evidence_id": evidence_id,
                    "source_family": str(row.get("source_family") or row.get("source_tier") or ""),
                    "ticker": _ticker_text(row),
                    "metric": _metric_text(row),
                    "payload_json": _json(payload),
                }
            )
    return rows


def _retrieval_task_rows(state: Mapping[str, Any], common: Mapping[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    candidates = [
        ("retrieval_plan", state.get("retrieval_plan")),
        ("second_pass_retrieval_plan", state.get("second_pass_retrieval_plan")),
        ("evidence_requirement_plan", state.get("evidence_requirement_plan")),
        ("multi_agent_evidence_requirement_plan", state.get("multi_agent_evidence_requirement_plan")),
    ]
    for source_name, value in candidates:
        if not isinstance(value, Mapping) or not value:
            continue
        task_items = (
            value.get("routes")
            or value.get("tasks")
            or value.get("requirements")
            or value.get("evidence_requirements")
            or []
        )
        if not isinstance(task_items, list):
            task_items = [value]
        for index, task in enumerate(task_items, start=1):
            if not isinstance(task, Mapping):
                continue
            payload = {"source": source_name, **dict(task)}
            task_id = _first_text(
                task.get("task_id"),
                task.get("route_id"),
                task.get("requirement_id"),
                f"{source_name}_{index}",
            )
            rows.append(
                {
                    **common,
                    "node": "execute_retrieval_routes",
                    "input_digest": _digest(value),
                    "output_digest": _digest(payload),
                    "artifact_uri": str(task.get("artifact_uri") or ""),
                    "retrieval_task_id": task_id,
                    "route": str(task.get("route") or task.get("source_route") or task.get("source_family") or ""),
                    "source_family": str(task.get("source_family") or ""),
                    "status": str(task.get("status") or task.get("gate_status") or ""),
                    "pre_rerank_count": _int(task.get("pre_rerank_count") or task.get("candidate_count")),
                    "post_rerank_count": _int(task.get("post_rerank_count") or task.get("selected_count")),
                    "role_visible_count": _int(task.get("role_visible_count") or task.get("visible_count")),
                    "cap_reason": str(task.get("cap_reason") or task.get("drop_reason") or ""),
                    "payload_json": _json(payload),
                }
            )
    budget = state.get("retrieval_budget_audit") if isinstance(state.get("retrieval_budget_audit"), Mapping) else {}
    for index, task in enumerate(budget.get("routes") or budget.get("tasks") or [], start=len(rows) + 1):
        if not isinstance(task, Mapping):
            continue
        payload = {"source": "retrieval_budget_audit", **dict(task)}
        rows.append(
            {
                **common,
                "node": "execute_retrieval_routes",
                "input_digest": _digest(budget),
                "output_digest": _digest(payload),
                "artifact_uri": "",
                "retrieval_task_id": _first_text(task.get("task_id"), task.get("route"), f"retrieval_budget_{index}"),
                "route": str(task.get("route") or ""),
                "source_family": str(task.get("source_family") or ""),
                "status": str(task.get("status") or ""),
                "pre_rerank_count": _int(task.get("pre_rerank_count")),
                "post_rerank_count": _int(task.get("post_rerank_count")),
                "role_visible_count": _int(task.get("role_visible_count")),
                "cap_reason": str(task.get("cap_reason") or ""),
                "payload_json": _json(payload),
            }
        )
    return rows


def _tool_call_rows(state: Mapping[str, Any], common: Mapping[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    values: list[Mapping[str, Any]] = []
    for key in ("tool_calls", "tool_observations"):
        raw = state.get(key)
        if isinstance(raw, list):
            values.extend(item for item in raw if isinstance(item, Mapping))
    ledger = state.get("tool_call_ledger")
    if isinstance(ledger, Mapping):
        for key in ("calls", "entries", "events"):
            raw = ledger.get(key)
            if isinstance(raw, list):
                values.extend(item for item in raw if isinstance(item, Mapping))
    for index, call in enumerate(values, start=1):
        payload = dict(call)
        rows.append(
            {
                **common,
                "node": str(call.get("node") or call.get("agent_id") or "tool_execution"),
                "input_digest": _digest(call.get("args") or call.get("input") or {}),
                "output_digest": _digest(call.get("result") or call.get("output") or call),
                "artifact_uri": str(call.get("artifact_uri") or ""),
                "tool_call_id": _first_text(call.get("tool_call_id"), call.get("call_id"), f"tool_call_{index}"),
                "tool_name": str(call.get("tool_name") or call.get("name") or ""),
                "agent_id": str(call.get("agent_id") or call.get("owner") or ""),
                "status": str(call.get("status") or ""),
                "payload_json": _json(payload),
            }
        )
    return rows


def _claim_rows(state: Mapping[str, Any], common: Mapping[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    judgment = state.get("verified_judgment_plan") if isinstance(state.get("verified_judgment_plan"), Mapping) else state.get("judgment_plan") or {}
    claims = [row for row in (judgment.get("supported_claims") if isinstance(judgment, Mapping) else []) or [] if isinstance(row, Mapping)]
    memo_claims = [row for row in (state.get("memo_answer") or {}).get("memo_claims") or [] if isinstance(row, Mapping)] if isinstance(state.get("memo_answer"), Mapping) else []
    for source_name, values in (("judgment_supported_claim", claims), ("memo_claim", memo_claims)):
        for index, claim in enumerate(values, start=1):
            claim_id = _first_text(claim.get("claim_id"), f"{source_name}_{index}")
            payload = {"source": source_name, **dict(claim)}
            rows.append(
                {
                    **common,
                    "node": "build_judgment_plan" if source_name == "judgment_supported_claim" else "synthesize_answer",
                    "input_digest": "",
                    "output_digest": _digest(payload),
                    "artifact_uri": "",
                    "claim_id": claim_id,
                    "claim_type": str(claim.get("claim_type") or ""),
                    "analysis_dimension": str(claim.get("analysis_dimension") or ""),
                    "source_families": _json(_string_list(claim.get("source_families") or claim.get("source_family"))),
                    "evidence_refs": _json(_string_list(claim.get("evidence_refs") or claim.get("refs"))),
                    "payload_json": _json(payload),
                }
            )
    return rows


def _gap_rows(state: Mapping[str, Any], common: Mapping[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, gap in enumerate(state.get("source_gaps") or [], start=1):
        if isinstance(gap, Mapping):
            rows.append(_gap_row(common, "source_gap", gap, index=index))
    register = state.get("bounded_gap_register") if isinstance(state.get("bounded_gap_register"), Mapping) else {}
    for index, gap in enumerate(register.get("gaps") or [], start=len(rows) + 1):
        if isinstance(gap, Mapping):
            rows.append(_gap_row(common, "bounded_gap", gap, index=index))
    ledger = state.get("typed_gap_ledger") if isinstance(state.get("typed_gap_ledger"), Mapping) else {}
    for index, gap in enumerate((ledger.get("gaps") or ledger.get("gap_events") or ledger.get("events") or []), start=len(rows) + 1):
        if isinstance(gap, Mapping):
            rows.append(_gap_row(common, "typed_gap_ledger", gap, index=index))
    judgment = state.get("verified_judgment_plan") if isinstance(state.get("verified_judgment_plan"), Mapping) else {}
    for index, gap in enumerate(judgment.get("unsupported_claims") or [], start=len(rows) + 1):
        if isinstance(gap, Mapping):
            rows.append(_gap_row(common, "unsupported_claim", gap, index=index))
    return rows


def _gap_row(common: Mapping[str, str], source_name: str, gap: Mapping[str, Any], *, index: int) -> dict[str, Any]:
    payload = {"source": source_name, **dict(gap)}
    return {
        **common,
        "node": "assess_evidence_coverage",
        "input_digest": "",
        "output_digest": _digest(payload),
        "artifact_uri": "",
        "gap_id": _first_text(gap.get("gap_id"), gap.get("id"), f"{source_name}_{index}"),
        "gap_type": str(gap.get("gap_type") or gap.get("type") or source_name),
        "severity": str(gap.get("severity") or gap.get("priority") or ""),
        "payload_json": _json(payload),
    }


def _gate_rows(state: Mapping[str, Any], common: Mapping[str, str]) -> list[dict[str, Any]]:
    candidates = {
        "specialist_verification": state.get("specialist_verification"),
        "claim_verification": state.get("claim_verification"),
        "analyst_depth_gate": (state.get("claim_verification") or {}).get("analyst_depth_gate") if isinstance(state.get("claim_verification"), Mapping) else {},
        "deterministic_gates": state.get("deterministic_gates"),
        "pre_memo_fact_selection": state.get("pre_memo_fact_selection"),
        "d_series_database_closeout_gate": state.get("d_series_database_closeout_gate"),
    }
    rows: list[dict[str, Any]] = []
    for gate_name, gate in candidates.items():
        if not isinstance(gate, Mapping) or not gate:
            continue
        payload = {"gate_name": gate_name, **dict(gate)}
        rows.append(
            {
                **common,
                "node": _gate_node(gate_name),
                "input_digest": "",
                "output_digest": _digest(payload),
                "artifact_uri": "",
                "gate_id": gate_name,
                "gate_name": gate_name,
                "status": str(gate.get("status") or gate.get("gate_status") or ""),
                "error_count": len(gate.get("errors") or []),
                "warning_count": len(gate.get("warnings") or []),
                "payload_json": _json(payload),
            }
        )
    matrix = state.get("gate_registry_eval_matrix") if isinstance(state.get("gate_registry_eval_matrix"), Mapping) else {}
    for index, gate in enumerate(matrix.get("gate_history") or matrix.get("gates") or [], start=1):
        if not isinstance(gate, Mapping):
            continue
        payload = {"gate_name": str(gate.get("gate_id") or gate.get("gate_name") or f"gate_{index}"), **dict(gate)}
        rows.append(
            {
                **common,
                "node": "run_deterministic_gates",
                "input_digest": "",
                "output_digest": _digest(payload),
                "artifact_uri": "",
                "gate_id": str(gate.get("gate_id") or f"gate_registry_{index}"),
                "gate_name": str(gate.get("gate_name") or gate.get("gate_id") or ""),
                "status": str(gate.get("status") or gate.get("gate_status") or ""),
                "error_count": len(gate.get("errors") or []),
                "warning_count": len(gate.get("warnings") or []),
                "payload_json": _json(payload),
            }
        )
    return rows


def _reflection_event_rows(state: Mapping[str, Any], common: Mapping[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    candidates = {
        "multi_agent_reflection_report": state.get("multi_agent_reflection_report"),
        "quality_second_pass_report": state.get("quality_second_pass_report"),
        "second_pass_reflection_diagnosis": state.get("second_pass_reflection_diagnosis"),
        "lead_review_checkpoint": state.get("lead_review_checkpoint"),
    }
    for event_id, event in candidates.items():
        if not isinstance(event, Mapping) or not event:
            continue
        payload = {"event_id": event_id, **dict(event)}
        rows.append(
            {
                **common,
                "node": "lead_review_checkpoint" if event_id == "lead_review_checkpoint" else "coverage_reflection",
                "input_digest": "",
                "output_digest": _digest(payload),
                "artifact_uri": "",
                "reflection_id": event_id,
                "event_type": str(event.get("trigger") or event.get("status") or event_id),
                "status": str(event.get("status") or event.get("sufficiency_level") or ""),
                "payload_json": _json(payload),
            }
        )
    return rows


def _repair_task_rows(state: Mapping[str, Any], common: Mapping[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_name in ("second_pass_repair_plan", "targeted_repair_plan"):
        plan = state.get(source_name)
        if not isinstance(plan, Mapping) or not plan:
            continue
        repairs = plan.get("repairs") or plan.get("repair_tasks") or plan.get("tasks") or []
        if not isinstance(repairs, list):
            repairs = [plan]
        for index, repair in enumerate(repairs, start=1):
            if not isinstance(repair, Mapping):
                continue
            payload = {"source": source_name, **dict(repair)}
            rows.append(
                {
                    **common,
                    "node": "lead_review_checkpoint" if source_name == "targeted_repair_plan" else "optional_second_pass",
                    "input_digest": _digest(plan),
                    "output_digest": _digest(payload),
                    "artifact_uri": "",
                    "repair_task_id": _first_text(repair.get("repair_id"), repair.get("task_id"), f"{source_name}_{index}"),
                    "route": str(repair.get("route") or repair.get("source_route") or ""),
                    "source_class": str(repair.get("source_class") or repair.get("source_family") or ""),
                    "expected_claim_type": str(repair.get("expected_claim_type") or repair.get("claim_type") or ""),
                    "status": str(repair.get("status") or ""),
                    "payload_json": _json(payload),
                }
            )
    return rows


def _model_call_rows(state: Mapping[str, Any], common: Mapping[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for route_name, diagnostics in _model_diagnostics(state):
        calls = diagnostics.get("calls") if isinstance(diagnostics.get("calls"), list) else []
        if not calls and diagnostics:
            calls = [diagnostics]
        for index, call in enumerate(calls, start=1):
            if not isinstance(call, Mapping):
                continue
            payload = {"route_name": route_name, **dict(call)}
            rows.append(
                {
                    **common,
                    "node": _model_node(route_name),
                    "input_digest": _digest({"route_name": route_name, "index": index}),
                    "output_digest": _digest(payload),
                    "artifact_uri": "",
                    "call_id": f"{route_name}_{index}",
                    "route_name": route_name,
                    "model": str(call.get("model") or call.get("model_name") or ""),
                    "status": str(call.get("status") or call.get("finish_reason") or ""),
                    "prompt_tokens": int(call.get("prompt_tokens") or call.get("input_tokens") or 0),
                    "completion_tokens": int(call.get("completion_tokens") or call.get("output_tokens") or 0),
                    "total_tokens": int(call.get("total_tokens") or 0),
                    "payload_json": _json(payload),
                }
            )
    return rows


def _resource_usage_rows(
    state: Mapping[str, Any],
    common: Mapping[str, str],
    *,
    model_call_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    total_tokens = sum(_int(row.get("total_tokens")) for row in model_call_rows)
    rows: list[dict[str, Any]] = []
    payload = {
        "model_call_count": len(model_call_rows),
        "total_tokens": total_tokens,
        "scheduler_audit": state.get("resource_scheduler_audit") or state.get("inference_resource_scheduler") or {},
    }
    rows.append(
        {
            **common,
            "node": "resource_audit",
            "input_digest": "",
            "output_digest": _digest(payload),
            "artifact_uri": "",
            "usage_id": "model_token_summary",
            "resource_type": "llm_tokens",
            "amount": total_tokens,
            "unit": "tokens",
            "payload_json": _json(payload),
        }
    )
    scheduler = payload["scheduler_audit"]
    if isinstance(scheduler, Mapping):
        for index, decision in enumerate(scheduler.get("scheduled_tasks") or scheduler.get("decisions") or [], start=1):
            if not isinstance(decision, Mapping):
                continue
            decision_payload = dict(decision)
            rows.append(
                {
                    **common,
                    "node": "resource_scheduler",
                    "input_digest": _digest(scheduler),
                    "output_digest": _digest(decision_payload),
                    "artifact_uri": "",
                    "usage_id": _first_text(decision.get("task_id"), f"scheduler_decision_{index}"),
                    "resource_type": str(decision.get("lane") or decision.get("resource_type") or ""),
                    "amount": _int(decision.get("queue_position") or decision.get("wait_ms")),
                    "unit": "queue_position_or_ms",
                    "payload_json": _json(decision_payload),
                }
            )
    return rows


def _report_artifact_rows(state: Mapping[str, Any], common: Mapping[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rendered = str(state.get("rendered_answer") or "")
    memo = state.get("memo_answer") if isinstance(state.get("memo_answer"), Mapping) else {}
    values = [
        ("rendered_answer", rendered, ""),
        ("memo_answer", memo, ""),
    ]
    for key, value, uri in values:
        if value in ("", {}) or value is None:
            continue
        payload = {"artifact_key": key, "value": value}
        rows.append(
            {
                **common,
                "node": "render_answer" if key == "rendered_answer" else "synthesize_answer",
                "input_digest": "",
                "output_digest": _digest(payload),
                "artifact_uri": uri,
                "report_id": key,
                "artifact_type": "markdown" if key == "rendered_answer" else "json",
                "status": str(state.get("status") or ""),
                "payload_json": _json(payload),
            }
        )
    for key, uri in sorted((state.get("artifact_refs") or {}).items()):
        if "memo" not in str(key) and "report" not in str(key) and "answer" not in str(key):
            continue
        payload = {"artifact_key": key, "artifact_uri": uri}
        rows.append(
            {
                **common,
                "node": "render_answer",
                "input_digest": "",
                "output_digest": _digest(payload),
                "artifact_uri": str(uri or ""),
                "report_id": str(key),
                "artifact_type": _artifact_type(str(key), str(uri or "")),
                "status": str(state.get("status") or ""),
                "payload_json": _json(payload),
            }
        )
    return rows


def _context_snapshot_rows(state: Mapping[str, Any], common: Mapping[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    candidates = {
        "multi_agent_context": state.get("multi_agent_context"),
        "shared_specialist_context": state.get("shared_specialist_context"),
        "research_objective_contract": state.get("research_objective_contract"),
        "context_engine_snapshot": state.get("context_engine_snapshot"),
    }
    for snapshot_id, snapshot in candidates.items():
        if not isinstance(snapshot, Mapping) or not snapshot:
            continue
        payload = {"snapshot_id": snapshot_id, **dict(snapshot)}
        rows.append(
            {
                **common,
                "node": "context_engine",
                "input_digest": "",
                "output_digest": _digest(payload),
                "artifact_uri": "",
                "snapshot_id": snapshot_id,
                "context_type": snapshot_id,
                "visibility_scope": str(snapshot.get("visibility_scope") or snapshot.get("scope") or ""),
                "payload_json": _json(payload),
            }
        )
    return rows


def _context_event_rows(state: Mapping[str, Any], common: Mapping[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    events = state.get("context_events")
    if not isinstance(events, list):
        return rows
    for index, event in enumerate(events, start=1):
        if not isinstance(event, Mapping):
            continue
        payload = dict(event)
        rows.append(
            {
                **common,
                "node": "context_engine",
                "input_digest": "",
                "output_digest": _digest(payload),
                "artifact_uri": str(event.get("artifact_uri") or ""),
                "event_id": _first_text(event.get("event_id"), f"context_event_{index}"),
                "event_type": str(event.get("event_type") or event.get("type") or ""),
                "payload_json": _json(payload),
            }
        )
    return rows


def _context_injection_plan_rows(state: Mapping[str, Any], common: Mapping[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    plans = state.get("context_injection_plans") or state.get("context_injection_plan")
    if isinstance(plans, Mapping):
        plans = [plans]
    if not isinstance(plans, list):
        return rows
    for index, plan in enumerate(plans, start=1):
        if not isinstance(plan, Mapping):
            continue
        payload = dict(plan)
        rows.append(
            {
                **common,
                "node": str(plan.get("node") or "context_engine"),
                "input_digest": _digest(plan.get("available_context") or {}),
                "output_digest": _digest(payload),
                "artifact_uri": "",
                "plan_id": _first_text(plan.get("plan_id"), f"context_injection_plan_{index}"),
                "target_node": str(plan.get("target_node") or plan.get("node") or ""),
                "token_budget": _int(plan.get("token_budget")),
                "payload_json": _json(payload),
            }
        )
    return rows


def _uploaded_file_rows(state: Mapping[str, Any], common: Mapping[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    files = state.get("uploaded_files") or state.get("user_uploaded_files")
    if not isinstance(files, list):
        return rows
    for index, file_ref in enumerate(files, start=1):
        if not isinstance(file_ref, Mapping):
            continue
        payload = dict(file_ref)
        rows.append(
            {
                **common,
                "node": "input_parser",
                "input_digest": _digest(file_ref.get("path") or file_ref.get("uri") or file_ref),
                "output_digest": _digest(payload),
                "artifact_uri": str(file_ref.get("artifact_uri") or file_ref.get("path") or file_ref.get("uri") or ""),
                "file_id": _first_text(file_ref.get("file_id"), file_ref.get("checksum"), f"uploaded_file_{index}"),
                "filename": str(file_ref.get("filename") or Path(str(file_ref.get("path") or "")).name),
                "mime_type": str(file_ref.get("mime_type") or ""),
                "payload_json": _json(payload),
            }
        )
    return rows


def _parsed_input_artifact_rows(state: Mapping[str, Any], common: Mapping[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    artifacts = state.get("parsed_input_artifacts") or state.get("user_provided_evidence_pack")
    if isinstance(artifacts, Mapping):
        artifacts = artifacts.get("artifacts") or artifacts.get("items") or [artifacts]
    if not isinstance(artifacts, list):
        return rows
    for index, artifact in enumerate(artifacts, start=1):
        if not isinstance(artifact, Mapping):
            continue
        payload = dict(artifact)
        rows.append(
            {
                **common,
                "node": "input_parser",
                "input_digest": _digest(artifact.get("source_file_id") or artifact.get("source_uri") or artifact),
                "output_digest": _digest(payload),
                "artifact_uri": str(artifact.get("artifact_uri") or ""),
                "parsed_artifact_id": _first_text(artifact.get("artifact_id"), artifact.get("parsed_artifact_id"), f"parsed_input_{index}"),
                "parser": str(artifact.get("parser") or ""),
                "status": str(artifact.get("status") or ""),
                "payload_json": _json(payload),
            }
        )
    return rows


def _model_diagnostics(state: Mapping[str, Any]) -> list[tuple[str, Mapping[str, Any]]]:
    pairs: list[tuple[str, Mapping[str, Any]]] = []
    for key in ("research_lead_model_diagnostics", "universe_relationship_model_diagnostics"):
        value = state.get(key)
        if isinstance(value, Mapping) and value:
            pairs.append((key.replace("_model_diagnostics", ""), value))
    memo_route = state.get("memo_route_result") if isinstance(state.get("memo_route_result"), Mapping) else {}
    if isinstance(memo_route.get("model_diagnostics"), Mapping):
        pairs.append(("memo_writer", memo_route["model_diagnostics"]))
    claim = state.get("claim_verification") if isinstance(state.get("claim_verification"), Mapping) else {}
    if isinstance(claim.get("model_diagnostics"), Mapping):
        pairs.append(("verifier", claim["model_diagnostics"]))
    for route in state.get("specialist_route_results") or []:
        if isinstance(route, Mapping) and isinstance(route.get("model_diagnostics"), Mapping):
            pairs.append((f"specialist_{route.get('agent_id') or len(pairs) + 1}", route["model_diagnostics"]))
    return pairs


def _insert_rows(conn: sqlite3.Connection, rows: Mapping[str, Sequence[Mapping[str, Any]]]) -> None:
    for table, table_rows in rows.items():
        for row in table_rows:
            _insert_row(conn, table, row)


def _insert_row(conn: sqlite3.Connection, table: str, row: Mapping[str, Any]) -> None:
    columns = list(row.keys())
    placeholders = ", ".join("?" for _ in columns)
    column_sql = ", ".join(f'"{column}"' for column in columns)
    conn.execute(
        f'insert or replace into "{table}" ({column_sql}) values ({placeholders})',
        [row.get(column) for column in columns],
    )


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists run_audit_metadata (
            key text primary key,
            value_json text not null,
            updated_at text not null
        );
        create table if not exists "run" (
            run_id text primary key,
            case_id text not null,
            node text not null default '',
            input_digest text not null default '',
            output_digest text not null default '',
            code_commit text not null default '',
            data_snapshot_id text not null default '',
            artifact_uri text not null default '',
            status text not null default '',
            started_at text not null default '',
            finished_at text not null default '',
            elapsed_ms integer not null default 0,
            payload_json text not null
        );
        create table if not exists node_execution (
            run_id text not null,
            case_id text not null,
            node text not null,
            input_digest text not null default '',
            output_digest text not null default '',
            code_commit text not null default '',
            data_snapshot_id text not null default '',
            artifact_uri text not null default '',
            node_index integer not null,
            checkpoint_id text not null,
            previous_checkpoint_id text not null default '',
            started_at text not null default '',
            finished_at text not null default '',
            elapsed_ms integer not null default 0,
            payload_json text not null,
            primary key (run_id, node_index)
        );
        create table if not exists artifact_ref (
            run_id text not null,
            case_id text not null,
            node text not null default '',
            input_digest text not null default '',
            output_digest text not null default '',
            code_commit text not null default '',
            data_snapshot_id text not null default '',
            artifact_uri text not null,
            artifact_key text not null,
            artifact_type text not null default '',
            payload_json text not null,
            primary key (run_id, artifact_key, artifact_uri)
        );
        create table if not exists retrieval_task (
            run_id text not null,
            case_id text not null,
            node text not null default '',
            input_digest text not null default '',
            output_digest text not null default '',
            code_commit text not null default '',
            data_snapshot_id text not null default '',
            artifact_uri text not null default '',
            retrieval_task_id text not null,
            route text not null default '',
            source_family text not null default '',
            status text not null default '',
            pre_rerank_count integer not null default 0,
            post_rerank_count integer not null default 0,
            role_visible_count integer not null default 0,
            cap_reason text not null default '',
            payload_json text not null,
            primary key (run_id, retrieval_task_id, output_digest)
        );
        create table if not exists tool_call (
            run_id text not null,
            case_id text not null,
            node text not null default '',
            input_digest text not null default '',
            output_digest text not null default '',
            code_commit text not null default '',
            data_snapshot_id text not null default '',
            artifact_uri text not null default '',
            tool_call_id text not null,
            tool_name text not null default '',
            agent_id text not null default '',
            status text not null default '',
            payload_json text not null,
            primary key (run_id, tool_call_id, output_digest)
        );
        create table if not exists evidence_row (
            run_id text not null,
            case_id text not null,
            node text not null default '',
            input_digest text not null default '',
            output_digest text not null default '',
            code_commit text not null default '',
            data_snapshot_id text not null default '',
            artifact_uri text not null default '',
            evidence_id text not null,
            source_family text not null default '',
            ticker text not null default '',
            metric text not null default '',
            payload_json text not null,
            primary key (run_id, evidence_id, output_digest)
        );
        create table if not exists claim_card (
            run_id text not null,
            case_id text not null,
            node text not null default '',
            input_digest text not null default '',
            output_digest text not null default '',
            code_commit text not null default '',
            data_snapshot_id text not null default '',
            artifact_uri text not null default '',
            claim_id text not null,
            claim_type text not null default '',
            analysis_dimension text not null default '',
            source_families text not null default '[]',
            evidence_refs text not null default '[]',
            payload_json text not null,
            primary key (run_id, claim_id, output_digest)
        );
        create table if not exists gap (
            run_id text not null,
            case_id text not null,
            node text not null default '',
            input_digest text not null default '',
            output_digest text not null default '',
            code_commit text not null default '',
            data_snapshot_id text not null default '',
            artifact_uri text not null default '',
            gap_id text not null,
            gap_type text not null default '',
            severity text not null default '',
            payload_json text not null,
            primary key (run_id, gap_id, output_digest)
        );
        create table if not exists gate_result (
            run_id text not null,
            case_id text not null,
            node text not null default '',
            input_digest text not null default '',
            output_digest text not null default '',
            code_commit text not null default '',
            data_snapshot_id text not null default '',
            artifact_uri text not null default '',
            gate_id text not null,
            gate_name text not null default '',
            status text not null default '',
            error_count integer not null default 0,
            warning_count integer not null default 0,
            payload_json text not null,
            primary key (run_id, gate_id, output_digest)
        );
        create table if not exists reflection_event (
            run_id text not null,
            case_id text not null,
            node text not null default '',
            input_digest text not null default '',
            output_digest text not null default '',
            code_commit text not null default '',
            data_snapshot_id text not null default '',
            artifact_uri text not null default '',
            reflection_id text not null,
            event_type text not null default '',
            status text not null default '',
            payload_json text not null,
            primary key (run_id, reflection_id, output_digest)
        );
        create table if not exists repair_task (
            run_id text not null,
            case_id text not null,
            node text not null default '',
            input_digest text not null default '',
            output_digest text not null default '',
            code_commit text not null default '',
            data_snapshot_id text not null default '',
            artifact_uri text not null default '',
            repair_task_id text not null,
            route text not null default '',
            source_class text not null default '',
            expected_claim_type text not null default '',
            status text not null default '',
            payload_json text not null,
            primary key (run_id, repair_task_id, output_digest)
        );
        create table if not exists model_call (
            run_id text not null,
            case_id text not null,
            node text not null default '',
            input_digest text not null default '',
            output_digest text not null default '',
            code_commit text not null default '',
            data_snapshot_id text not null default '',
            artifact_uri text not null default '',
            call_id text not null,
            route_name text not null default '',
            model text not null default '',
            status text not null default '',
            prompt_tokens integer not null default 0,
            completion_tokens integer not null default 0,
            total_tokens integer not null default 0,
            payload_json text not null,
            primary key (run_id, call_id, output_digest)
        );
        create table if not exists resource_usage (
            run_id text not null,
            case_id text not null,
            node text not null default '',
            input_digest text not null default '',
            output_digest text not null default '',
            code_commit text not null default '',
            data_snapshot_id text not null default '',
            artifact_uri text not null default '',
            usage_id text not null,
            resource_type text not null default '',
            amount integer not null default 0,
            unit text not null default '',
            payload_json text not null,
            primary key (run_id, usage_id, output_digest)
        );
        create table if not exists report_artifact (
            run_id text not null,
            case_id text not null,
            node text not null default '',
            input_digest text not null default '',
            output_digest text not null default '',
            code_commit text not null default '',
            data_snapshot_id text not null default '',
            artifact_uri text not null default '',
            report_id text not null,
            artifact_type text not null default '',
            status text not null default '',
            payload_json text not null,
            primary key (run_id, report_id, output_digest)
        );
        create table if not exists context_snapshot (
            run_id text not null,
            case_id text not null,
            node text not null default '',
            input_digest text not null default '',
            output_digest text not null default '',
            code_commit text not null default '',
            data_snapshot_id text not null default '',
            artifact_uri text not null default '',
            snapshot_id text not null,
            context_type text not null default '',
            visibility_scope text not null default '',
            payload_json text not null,
            primary key (run_id, snapshot_id, output_digest)
        );
        create table if not exists context_event (
            run_id text not null,
            case_id text not null,
            node text not null default '',
            input_digest text not null default '',
            output_digest text not null default '',
            code_commit text not null default '',
            data_snapshot_id text not null default '',
            artifact_uri text not null default '',
            event_id text not null,
            event_type text not null default '',
            payload_json text not null,
            primary key (run_id, event_id, output_digest)
        );
        create table if not exists context_injection_plan (
            run_id text not null,
            case_id text not null,
            node text not null default '',
            input_digest text not null default '',
            output_digest text not null default '',
            code_commit text not null default '',
            data_snapshot_id text not null default '',
            artifact_uri text not null default '',
            plan_id text not null,
            target_node text not null default '',
            token_budget integer not null default 0,
            payload_json text not null,
            primary key (run_id, plan_id, output_digest)
        );
        create table if not exists uploaded_file (
            run_id text not null,
            case_id text not null,
            node text not null default '',
            input_digest text not null default '',
            output_digest text not null default '',
            code_commit text not null default '',
            data_snapshot_id text not null default '',
            artifact_uri text not null default '',
            file_id text not null,
            filename text not null default '',
            mime_type text not null default '',
            payload_json text not null,
            primary key (run_id, file_id, output_digest)
        );
        create table if not exists parsed_input_artifact (
            run_id text not null,
            case_id text not null,
            node text not null default '',
            input_digest text not null default '',
            output_digest text not null default '',
            code_commit text not null default '',
            data_snapshot_id text not null default '',
            artifact_uri text not null default '',
            parsed_artifact_id text not null,
            parser text not null default '',
            status text not null default '',
            payload_json text not null,
            primary key (run_id, parsed_artifact_id, output_digest)
        );
        create index if not exists idx_run_case_id on "run"(case_id);
        create index if not exists idx_node_execution_run_node on node_execution(run_id, node);
        create index if not exists idx_artifact_ref_run_key on artifact_ref(run_id, artifact_key);
        create index if not exists idx_retrieval_task_run_route on retrieval_task(run_id, route);
        create index if not exists idx_tool_call_run_tool on tool_call(run_id, tool_name);
        create index if not exists idx_evidence_row_run_source on evidence_row(run_id, source_family);
        create index if not exists idx_claim_card_run_dimension on claim_card(run_id, analysis_dimension);
        create index if not exists idx_gap_run_type on gap(run_id, gap_type);
        create index if not exists idx_gate_result_run_status on gate_result(run_id, status);
        create index if not exists idx_reflection_event_run_status on reflection_event(run_id, status);
        create index if not exists idx_repair_task_run_route on repair_task(run_id, route);
        create index if not exists idx_model_call_run_route on model_call(run_id, route_name);
        create index if not exists idx_context_snapshot_run_type on context_snapshot(run_id, context_type);
        """
    )


def _delete_run(conn: sqlite3.Connection, run_id: str) -> None:
    for table in RUN_AUDIT_TABLES:
        conn.execute(f'delete from "{table}" where run_id = ?', (run_id,))


def _set_metadata(conn: sqlite3.Connection, key: str, value: Any) -> None:
    conn.execute(
        """
        insert into run_audit_metadata(key, value_json, updated_at)
        values (?, ?, ?)
        on conflict(key) do update set value_json = excluded.value_json, updated_at = excluded.updated_at
        """,
        (key, _json(value), datetime.now(timezone.utc).isoformat()),
    )


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma journal_mode=WAL")
    conn.execute("pragma synchronous=NORMAL")
    conn.execute("pragma busy_timeout=30000")
    return conn


def _count_where_run(conn: sqlite3.Connection, table: str, run_id: str) -> int:
    return int(conn.execute(f'select count(*) from "{table}" where run_id = ?', (run_id,)).fetchone()[0])


def _count_all(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f'select count(*) from "{table}"').fetchone()[0])


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _run_id(state: Mapping[str, Any]) -> str:
    return _first_text(state.get("run_id"), "unknown_run")


def _case_id(state: Mapping[str, Any]) -> str:
    if str(state.get("case_id") or "").strip():
        return str(state.get("case_id") or "").strip()
    run_id = _run_id(state)
    if "_" in run_id:
        return run_id.split("_", 1)[1]
    return run_id


def _code_commit(state: Mapping[str, Any]) -> str:
    explicit = str(state.get("code_commit") or "").strip()
    if explicit:
        return explicit
    try:
        return subprocess.check_output(["git", "rev-parse", "--short=12", "HEAD"], cwd=Path.cwd(), text=True).strip()
    except Exception:
        return ""


def _data_snapshot_id(state: Mapping[str, Any]) -> str:
    context = state.get("multi_agent_context") if isinstance(state.get("multi_agent_context"), Mapping) else {}
    contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    values = [
        context.get("market_snapshot_id"),
        (context.get("market_snapshot") or {}).get("snapshot_id") if isinstance(context.get("market_snapshot"), Mapping) else "",
        context.get("manifest_path"),
        context.get("ledger_store_path"),
        contract.get("data_snapshot_id"),
    ]
    clean = [str(item) for item in values if str(item or "").strip()]
    return _digest(clean) if clean else ""


def _summary_payload(state: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": state.get("status") or "",
        "rendered_answer": state.get("rendered_answer") or "",
        "artifact_refs": state.get("artifact_refs") or {},
        "claim_verification": state.get("claim_verification") or {},
    }


def _artifact_type(key: str, uri: str) -> str:
    suffix = Path(uri).suffix.lower()
    if suffix in {".json", ".jsonl"}:
        return "json"
    if suffix in {".md", ".txt"}:
        return "text"
    if suffix in {".sqlite", ".db"}:
        return "sqlite"
    return key


def _evidence_node(source_name: str) -> str:
    return {
        "context_rows": "execute_retrieval_routes",
        "runtime_ledger_rows": "build_runtime_ledger",
        "market_snapshot_rows": "attach_market_snapshot",
        "industry_snapshot_rows": "attach_industry_snapshot",
    }.get(source_name, "execute_retrieval_routes")


def _gate_node(gate_name: str) -> str:
    return {
        "specialist_verification": "build_judgment_plan",
        "claim_verification": "verify_claims",
        "analyst_depth_gate": "verify_claims",
        "deterministic_gates": "run_deterministic_gates",
        "pre_memo_fact_selection": "build_judgment_plan",
        "d_series_database_closeout_gate": "persist_session_state",
    }.get(gate_name, "run_deterministic_gates")


def _model_node(route_name: str) -> str:
    if route_name.startswith("specialist_"):
        return "build_judgment_plan"
    return {
        "research_lead": "research_lead_plan",
        "universe_relationship": "universe_relationship_scope",
        "memo_writer": "synthesize_answer",
        "verifier": "verify_claims",
    }.get(route_name, "")


def _ticker_text(row: Mapping[str, Any]) -> str:
    return ",".join(_string_list(row.get("ticker_scope") or row.get("tickers") or row.get("ticker")))[:240]


def _metric_text(row: Mapping[str, Any]) -> str:
    return ",".join(_string_list(row.get("metric_scope") or row.get("metrics") or row.get("metric") or row.get("metric_family")))[:240]


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item or "").strip() for item in value if str(item or "").strip()]
    return [str(value).strip()] if str(value).strip() else []


def _first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
