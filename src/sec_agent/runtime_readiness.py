from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Callable

from sec_agent.context_engine import ContextEngine
from sec_agent.lead_supervision import (
    build_lead_review_checkpoint,
    build_research_objective_contract,
    build_targeted_repair_plan,
)
from sec_agent.memo_logic_plan import build_memo_logic_plan
from sec_agent.role_evidence_selector import select_role_evidence
from sec_agent.run_audit_store import RUN_AUDIT_TABLES, materialize_run_audit_store, read_run_audit_counts
from sec_agent.runtime_bridge.baseline import build_runtime_baseline_report, write_runtime_baseline_report
from sec_agent.runtime_bridge.data_quality import (
    evaluate_data_processing_quality,
    evaluate_index_asset_quality,
    evaluate_retrieval_quality,
)
from sec_agent.runtime_bridge.eval_store import (
    EVAL_TABLES,
    record_eval_case_result,
    record_eval_gold_promotion,
    register_eval_case,
)
from sec_agent.runtime_bridge.object_store import put_json_object
from sec_agent.runtime_bridge.paths import resolve_runtime_paths
from sec_agent.runtime_bridge.resource_scheduler import (
    InferenceTask,
    coalesce_agent_tasks,
    schedule_inference_tasks_with_audit,
)
from sec_agent.mcp_tool_registry import invoke_mcp_tool
from sec_agent.tool_capability_registry import default_tool_capability_registry, validate_tool_invocation
from sec_agent.user_input_pipeline import parse_user_input_file


READINESS_SCHEMA_VERSION = "finsight_r0_r11_readiness_report_v0_1"


def run_r0_r11_readiness(
    *,
    repo_root: str | Path,
    output_dir: str | Path,
    include_cloud_gates: bool = False,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    paths = resolve_runtime_paths(root)
    gate_results: list[dict[str, Any]] = []
    cloud_gaps: list[dict[str, Any]] = []

    def gate(gate_id: str, fn: Callable[[], dict[str, Any]]) -> None:
        try:
            result = fn()
            status = str(result.get("status") or "pass")
            gate_results.append({"gate_id": gate_id, **result, "status": status})
        except Exception as exc:  # pragma: no cover - defensive readiness capture
            gate_results.append({"gate_id": gate_id, "status": "fail", "error_type": type(exc).__name__, "error": str(exc)})

    baseline_path = out / "runtime_baseline_report.json"
    run_audit_db = out / "run_audit.sqlite"
    eval_db = out / "eval_store.sqlite"
    object_store_root = out / "object_store"

    gate("R0.baseline_freeze", lambda: _r0(root, baseline_path))
    gate("R1.sql_object_store_audit", lambda: _r1(run_audit_db, object_store_root))
    gate("R2.eval_registry_lifecycle", lambda: _r2(eval_db))
    gate("R3.local_data_parser_index_gates", lambda: _r3_local(paths))
    if paths.milvus_mode in {"unbound_cloud_deferred", "unavailable", ""} and not (paths.milvus_db_path and paths.milvus_collection_name):
        cloud_gaps.append(
            {
                "gate_id": "R3.cloud_milvus_parity",
                "gap_type": "cloud_resource_required",
                "reason": "Milvus cloud collection is not opened/bound in this local run.",
                "required_after_cloud_opens": ["collection_stats", "schema_parity", "603_company_coverage", "query_smoke"],
            }
        )
    elif include_cloud_gates:
        gate("R3.cloud_milvus_parity", lambda: _r3_milvus_runtime(paths))
    gate("R4.context_engine_memory", lambda: _r4())
    gate("R5.scheduler_retrieval_quality", lambda: _r5())
    gate("R6.tool_document_input", lambda: _r6(out, object_store_root))
    gate("R7.lead_supervised_loop", lambda: _r7())
    gate("R8.role_specific_selector", lambda: _r8())
    gate("R9.memo_logic_plan", lambda: _r9())
    gate("R10.backend_surface_contract", lambda: _r10(root))
    gate("R11.workbench_dashboard_surface", lambda: _r11(root))

    failed = [item for item in gate_results if item.get("status") not in {"pass", "manual_required"}]
    report = {
        "schema_version": READINESS_SCHEMA_VERSION,
        "repo_root": str(root),
        "output_dir": str(out),
        "status": "fail" if failed else "pass_with_cloud_gaps" if cloud_gaps else "pass",
        "gate_results": gate_results,
        "cloud_gaps": cloud_gaps,
        "summary": {
            "gate_count": len(gate_results),
            "failed_gate_count": len(failed),
            "cloud_gap_count": len(cloud_gaps),
            "run_audit_db": str(run_audit_db),
            "eval_db": str(eval_db),
            "baseline_report": str(baseline_path),
        },
    }
    (out / "r0_r11_readiness_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _r0(root: Path, baseline_path: Path) -> dict[str, Any]:
    report = write_runtime_baseline_report(baseline_path, repo_root=root)
    errors = []
    if not report["runtime_paths"]["repo_root"]:
        errors.append({"type": "repo_root_missing"})
    return {"status": "fail" if errors else "pass", "artifact_uri": str(baseline_path), "errors": errors, "baseline": report}


def _r1(run_audit_db: Path, object_store_root: Path) -> dict[str, Any]:
    state = _sample_state()
    object_ref = put_json_object({"hello": "audit"}, object_store_root=object_store_root, namespace="readiness", stem="sample")
    state["artifact_refs"]["object_store_sample"] = object_ref["artifact_uri"]
    report = materialize_run_audit_store(run_audit_db, state)
    counts = read_run_audit_counts(run_audit_db, run_id=state["run_id"])
    missing = [table for table in RUN_AUDIT_TABLES if table not in counts]
    zero_critical = [table for table in ("run", "node_execution", "artifact_ref", "retrieval_task", "tool_call", "evidence_row", "claim_card", "gap", "gate_result", "context_snapshot") if counts.get(table, 0) <= 0]
    return {
        "status": "fail" if missing or zero_critical else "pass",
        "db_path": str(run_audit_db),
        "object_ref": object_ref,
        "table_counts": counts,
        "missing_tables": missing,
        "zero_critical_tables": zero_critical,
        "materialization_report": report,
    }


def _r2(eval_db: Path) -> dict[str, Any]:
    register_eval_case(
        eval_db,
        {
            "eval_id": "r0_r11_readiness",
            "case_id": "readiness_case",
            "dataset_id": "readiness_dataset",
            "case_family": "runtime_readiness",
            "status": "current",
        },
    )
    record_eval_gold_promotion(
        eval_db,
        {
            "eval_id": "r0_r11_readiness",
            "case_id": "readiness_case",
            "state": "candidate",
            "criteria_version": "readiness_v0_1",
            "review_method": "system_gate",
        },
    )
    result = record_eval_case_result(
        eval_db,
        {
            "eval_id": "r0_r11_readiness",
            "case_id": "readiness_case",
            "run_id": "readiness_run",
            "case_family": "runtime_readiness",
            "status": "pass",
            "score": 1.0,
            "node_results": [{"node": "R2", "status": "pass", "metrics": [{"name": "eval_store_ready", "value": 1, "status": "pass"}]}],
            "annotations": [{"annotator": "system", "label": "readiness", "note": "eval lifecycle smoke"}],
            "judge_runs": [{"judge_model": "deterministic", "rubric_version": "readiness_v0_1", "prompt_digest": "sha256:deterministic", "score": 1}],
        },
    )
    missing = [table for table in EVAL_TABLES if result["counts"].get(table, 0) < 0]
    required_nonzero = ["eval_case_registry", "eval_case_membership", "eval_run", "eval_case_result", "eval_node_result", "eval_metric_result", "eval_gold_promotion", "eval_judge_run", "eval_dashboard_snapshot"]
    zero = [table for table in required_nonzero if result["counts"].get(table, 0) <= 0]
    return {"status": "fail" if missing or zero else "pass", "db_path": str(eval_db), "counts": result["counts"], "missing_tables": missing, "zero_required_tables": zero}


def _r3_local(paths: Any) -> dict[str, Any]:
    data_quality = evaluate_data_processing_quality(
        [{"chunk_id": "chunk_ok", "text": "Revenue table", "record_type": "table", "table_id": "t1", "row_index": 1}]
    )
    index_quality = evaluate_index_asset_quality(
        [{"record_id": "idx1", "ticker": "NVDA", "source_family": "primary_sec_filing", "vector_expected": True, "vector_present": True}]
    )
    retrieval_quality = evaluate_retrieval_quality(
        [{"task_id": "ret1", "target_in_candidates": True, "pre_rerank_count": 10, "post_rerank_count": 4, "role_visible_count": 2}]
    )
    results = [data_quality, index_quality, retrieval_quality]
    milvus_runtime = {}
    if paths.milvus_db_path and paths.milvus_collection_name:
        milvus_runtime = _r3_milvus_runtime(paths)
        results.append({"status": milvus_runtime.get("status") or "fail", "milvus_runtime": milvus_runtime})
    return {"status": "pass" if all(item["status"] == "pass" for item in results) else "fail", "results": results}


def _r3_milvus_runtime(paths: Any) -> dict[str, Any]:
    if not paths.milvus_db_path or not paths.milvus_collection_name:
        return {"status": "fail", "error": "milvus_runtime_not_bound", "runtime_paths": paths.as_dict()}
    result = invoke_mcp_tool(
        "sec_milvus_semantic_search",
        {
            "query": "AI infrastructure capex cloud data center demand",
            "tickers": ["MSFT", "AMZN", "NVDA"],
            "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing"],
            "milvus_db_path": str(paths.milvus_db_path),
            "milvus_collection_name": paths.milvus_collection_name,
            "embedding_model": paths.milvus_embedding_model,
            "vector_kinds": list(paths.milvus_vector_kinds or ["narrative_chunk", "table_chunk", "paraphrase_context", "relationship_context"]),
            "milvus_top_k": 5,
            "typed_filter_required": True,
        },
    )
    row_count = int(result.get("row_count") or 0)
    stats = result.get("collection_stats") if isinstance(result.get("collection_stats"), dict) else {}
    expected_count = paths.milvus_vector_count
    errors = []
    if result.get("status") != "ok":
        errors.append({"type": "milvus_search_failed", "error": result.get("error")})
    if row_count <= 0:
        errors.append({"type": "milvus_query_no_hits"})
    if expected_count is not None and int(stats.get("row_count") or 0) != int(expected_count):
        errors.append({"type": "milvus_row_count_mismatch", "expected": int(expected_count), "actual": int(stats.get("row_count") or 0)})
    return {
        "status": "fail" if errors else "pass",
        "milvus_mode": paths.milvus_mode,
        "milvus_db_path": str(paths.milvus_db_path),
        "collection_name": paths.milvus_collection_name,
        "expected_vector_count": expected_count,
        "query_row_count": row_count,
        "collection_stats": stats,
        "errors": errors,
        "sample_rows": (result.get("context_rows") or [])[:3],
    }


def _r4() -> dict[str, Any]:
    engine = ContextEngine()
    resolved = engine.resolve(_sample_state())
    selection = engine.select(resolved["snapshots"], target_node="research_lead")
    injection = engine.inject(selection, target_node="research_lead")
    memory = engine.write_memory({"state": "active", "claim_refs": ["claim_1"], "summary": "Readiness memory"})
    return {
        "status": "pass" if resolved["snapshot_count"] > 0 and injection["context_snapshot_ids"] and memory["governance"]["status"] == "pass" else "fail",
        "resolved": resolved,
        "injection_plan": injection,
        "memory": memory,
    }


def _r5() -> dict[str, Any]:
    tasks = coalesce_agent_tasks(
        [
            InferenceTask("retrieval", route="retrieval", priority=1, requires_cuda_bge=True),
            InferenceTask("product", route="specialist", priority=4, model_tier="standard"),
            InferenceTask("market", route="specialist", priority=5, model_tier="standard"),
            InferenceTask("memo", route="memo_writer", priority=6, model_tier="pro"),
        ]
    )
    audit = schedule_inference_tasks_with_audit(tasks, cuda_bge_slots=1, token_budget_pressure=True)
    retrieval_quality = evaluate_retrieval_quality(
        [{"task_id": "role_visible", "target_in_candidates": True, "pre_rerank_count": 20, "post_rerank_count": 8, "role_visible_count": 3}]
    )
    return {"status": "pass" if audit.status == "pass" and retrieval_quality["status"] == "pass" else "fail", "scheduler_audit": audit.__dict__, "retrieval_quality": retrieval_quality}


def _r6(out: Path, object_store_root: Path) -> dict[str, Any]:
    registry = default_tool_capability_registry()
    writer_gate = validate_tool_invocation("database_query", node="memo_writer", agent_id="memo_writer", registry=registry)
    renderer_gate = validate_tool_invocation("report_renderer", node="memo_writer", agent_id="memo_writer", registry=registry)
    sample = out / "sample_user_note.md"
    sample.write_text("# Product note\n\nA cited user-provided note.\n", encoding="utf-8")
    parsed = parse_user_input_file(sample, object_store_root=object_store_root, run_id="readiness_run")
    return {
        "status": "pass" if writer_gate["status"] == "fail" and renderer_gate["status"] == "pass" and parsed["status"] == "pass" else "fail",
        "registry": registry,
        "writer_db_gate": writer_gate,
        "renderer_gate": renderer_gate,
        "parsed_input": parsed,
    }


def _r7() -> dict[str, Any]:
    contract = build_research_objective_contract(query="Assess NVDA AI infrastructure fundamentals and product drivers.")
    checkpoint = build_lead_review_checkpoint(
        objective_contract=contract,
        retrieval_budget_audit={"routes": [{"route": "product", "source_family": "company_product_evidence_graph"}]},
        packs={"fundamental_statement_pack": {"status": "pass"}},
        claim_cards=[
            {"claim_id": "claim_1", "analysis_dimension": "fundamentals", "claim_type": "company_reported_financial_fact"},
        ],
        gaps=[{"gap_id": "gap_product", "dimension": "product_and_production", "gap_type": "parser_failed"}],
        source_capability={"company_product_evidence_graph": {"status": "available"}},
        run_audit={"run_id": "readiness_run"},
    )
    repair = build_targeted_repair_plan(checkpoint)
    return {"status": "pass" if contract["validation"]["status"] == "pass" and checkpoint["validation"]["status"] == "pass" else "fail", "contract": contract, "checkpoint": checkpoint, "repair_plan": repair}


def _r8() -> dict[str, Any]:
    rows = [
        {"evidence_ref": "p1", "source_family": "company_product_evidence_graph", "metric": "product spec", "product": "H100", "authority": "company_disclosed"},
        {"evidence_ref": "f1", "source_family": "primary_sec_filing", "metric": "revenue", "authority": "exact"},
    ]
    product = select_role_evidence(rows, role="product_technology_analyst")
    fundamental = select_role_evidence(rows, role="fundamental_analyst")
    return {"status": "pass" if product["selected_count"] >= 1 and fundamental["selected_count"] >= 1 else "fail", "product_selector": product, "fundamental_selector": fundamental}


def _r9() -> dict[str, Any]:
    judgment_state = {
        "schema_version": "sec_agent_judgment_state_v0.1",
        "dimension_judgments": [
            {"dimension_id": "fundamentals", "title": "Fundamentals", "claim_ids": ["claim_1"], "evidence_refs": ["ev1"], "summary": "Revenue bridge."}
        ],
    }
    lead = {"dimension_reviews": [{"dimension": "fundamentals", "status": "sufficient"}]}
    plan = build_memo_logic_plan(judgment_state=judgment_state, lead_review_checkpoint=lead)
    return {"status": plan["validation"]["status"], "memo_logic_plan": plan}


def _r10(root: Path) -> dict[str, Any]:
    java_files = [
        root / "apps/research_gateway/java/src/finsight/gateway/TaskGatewayServer.java",
        root / "apps/research_gateway/java/src/finsight/gateway/ResearchTask.java",
        root / "apps/research_gateway/java/src/finsight/gateway/JdbcTaskStore.java",
    ]
    missing = [str(path) for path in java_files if not path.exists()]
    server_text = java_files[0].read_text(encoding="utf-8") if not missing else ""
    required_surfaces = {
        "create": "handleCreateTask",
        "status": "handleGetTask",
        "events": "handleGetTaskEvents",
        "cancel": "handleCancelTask",
        "resume": "handleResumeTask",
        "sse": "sendSse",
        "worker_events": "handleWorkerUpdate",
    }
    missing_surfaces = [name for name, token in required_surfaces.items() if token not in server_text]
    return {"status": "fail" if missing or missing_surfaces else "pass", "missing_files": missing, "missing_surfaces": missing_surfaces, "note": "resume_sse_heartbeat_hardening_checked_by_java_tests_when_implemented"}


def _r11(root: Path) -> dict[str, Any]:
    app_path = root / "apps/workbench/backend/app.py"
    frontend_path = root / "apps/workbench/frontend/vite/src/main.tsx"
    missing = [str(path) for path in (app_path, frontend_path) if not path.exists()]
    app_text = app_path.read_text(encoding="utf-8") if app_path.exists() else ""
    frontend_text = frontend_path.read_text(encoding="utf-8") if frontend_path.exists() else ""
    required_backend = ["/api/runs", "/api/evals", "/api/evals/dashboard", "/api/system/status", "/api/runs/{job_id}/events/stream"]
    required_frontend_terms = ["Trace", "Checkpoint", "Run", "EvalDashboardPanel"]
    missing_backend = [term for term in required_backend if term not in app_text]
    missing_frontend = [term for term in required_frontend_terms if term not in frontend_text]
    return {
        "status": "fail" if missing or missing_backend or missing_frontend else "pass",
        "missing_files": missing,
        "missing_backend_terms": missing_backend,
        "missing_frontend_terms": missing_frontend,
        "note": "dedicated eval_dashboard_endpoint_added_in_R11_hardening_if_missing",
    }


def _sample_state() -> dict[str, Any]:
    return {
        "run_id": "r0_r11_readiness_run",
        "case_id": "r0_r11_readiness_case",
        "user_query": "Assess NVDA AI infrastructure fundamentals and product drivers.",
        "status": "completed",
        "output_dir": "",
        "query_contract": {"focus_tickers": ["NVDA"], "data_snapshot_id": "readiness_snapshot"},
        "node_checkpoints": [
            {"node": "research_lead_plan", "index": 1, "checkpoint_id": "c1", "elapsed_ms": 10},
            {"node": "lead_review_checkpoint", "index": 2, "checkpoint_id": "c2", "previous_checkpoint_id": "c1", "elapsed_ms": 15},
        ],
        "artifact_refs": {"memo_answer": ""},
        "retrieval_plan": {"routes": [{"task_id": "ret1", "route": "ledger_first", "source_family": "primary_sec_filing", "pre_rerank_count": 10, "post_rerank_count": 5, "role_visible_count": 3}]},
        "retrieval_budget_audit": {"routes": [{"task_id": "ret1", "route": "ledger_first", "pre_rerank_count": 10, "post_rerank_count": 5, "role_visible_count": 3}]},
        "tool_calls": [{"tool_call_id": "tool1", "tool_name": "sec_query_exact_value_ledger", "agent_id": "sec_operator", "status": "pass"}],
        "context_rows": [{"evidence_ref": "ev1", "source_family": "primary_sec_filing", "ticker": "NVDA", "metric": "revenue"}],
        "verified_judgment_plan": {
            "supported_claims": [{"claim_id": "claim_1", "analysis_dimension": "fundamentals", "claim_type": "company_reported_financial_fact", "evidence_refs": ["ev1"], "source_families": ["primary_sec_filing"]}],
            "unsupported_claims": [],
        },
        "source_gaps": [{"gap_id": "gap1", "gap_type": "commercial_gap", "dimension": "competition_and_market_position"}],
        "claim_verification": {"status": "pass", "analyst_depth_gate": {"status": "pass"}},
        "multi_agent_reflection_report": {"status": "partial", "sufficiency_level": "partial", "trigger": "readiness"},
        "second_pass_repair_plan": {"repairs": [{"repair_id": "repair1", "route": "ledger_first", "expected_claim_type": "company_reported_financial_fact", "status": "ready"}]},
        "research_lead_model_diagnostics": {"calls": [{"model": "deterministic", "total_tokens": 0, "status": "ok"}]},
        "resource_scheduler_audit": {"scheduled_tasks": [{"task_id": "ret1", "lane": "bge_cuda", "queue_position": 0}]},
        "rendered_answer": "# Readiness memo",
        "memo_answer": {"direct_answer": "Readiness memo.", "memo_claims": []},
        "multi_agent_context": {"visibility_scope": "global", "summary": "context"},
        "research_objective_contract": {"core_question": "Assess NVDA", "visibility_scope": "global"},
        "context_events": [{"event_id": "ctx1", "event_type": "resolve"}],
        "context_injection_plan": {"plan_id": "inject1", "target_node": "research_lead", "token_budget": 1000},
        "uploaded_files": [{"file_id": "file1", "filename": "sample.md", "artifact_uri": "memory://sample"}],
        "parsed_input_artifacts": [{"artifact_id": "parsed1", "parser": "plain_text_markdown_parser_v0_1", "status": "pass"}],
    }
