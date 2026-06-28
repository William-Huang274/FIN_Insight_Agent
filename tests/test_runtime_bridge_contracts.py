from __future__ import annotations

from pathlib import Path

from sec_agent.runtime_bridge.contracts import runtime_bridge_registry
from sec_agent.context_engine import ContextEngine
from sec_agent.lead_supervision import build_lead_review_checkpoint, build_research_objective_contract, build_targeted_repair_plan
from sec_agent.langgraph_orchestrator import _issuer_coverage_gaps_from_state, _lead_targeted_repair_context_claims
from sec_agent.memo_logic_plan import build_memo_logic_plan
from sec_agent.official_issuer_repair import execute_official_issuer_repair_plan
from sec_agent.role_evidence_selector import build_role_source_layer_distribution, select_role_evidence
from sec_agent.runtime_bridge.baseline import build_runtime_baseline_report
from sec_agent.runtime_bridge.data_quality import evaluate_data_processing_quality, evaluate_index_asset_quality, evaluate_retrieval_quality
from sec_agent.runtime_bridge.eval_store import (
    migrate_eval_store,
    read_eval_counts,
    record_eval_case_result,
    record_eval_gold_promotion,
    register_eval_case,
)
from sec_agent.runtime_bridge.object_store import put_json_object
from sec_agent.runtime_bridge.resource_scheduler import InferenceTask, coalesce_agent_tasks, schedule_inference_tasks, schedule_inference_tasks_with_audit
from sec_agent.runtime_bridge.task_worker import REAL_EVAL_IDS, _append_repeatable_args, _metadata_case_ids
from sec_agent.runtime_readiness import run_r0_r11_readiness
from sec_agent.tool_capability_registry import default_tool_capability_registry, validate_tool_invocation
from sec_agent.user_input_pipeline import parse_user_input_file


def test_runtime_bridge_registry_records_storage_and_path_boundaries(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FINSIGHT_DATA_ROOT", str(tmp_path / "data_d"))
    monkeypatch.setenv("FINSIGHT_SECONDARY_DATA_ROOTS", str(tmp_path / "data_z"))
    monkeypatch.setenv("FINSIGHT_MILVUS_MODE", "unbound_cloud_deferred")

    registry = runtime_bridge_registry(repo_root=str(tmp_path))

    assert registry["architecture_policy"]["java_gateway"] == "frontdoor_for_research_tasks"
    assert registry["architecture_policy"]["milvus"] == "semantic_recall_supplement_not_exact_authority"
    assert registry["runtime_paths"]["primary_data_root"].endswith("data_d")
    assert registry["runtime_paths"]["secondary_data_roots"][0].endswith("data_z")
    assert registry["p_series_capabilities"]["P0"]["status"] == "implemented_operational"
    assert "task_event_stream" in registry["p_series_capabilities"]["P1"]["gates"]
    assert registry["p_series_capabilities"]["P9"]["gates"] == [
        "queue_mode_declared",
        "redis_contract",
        "resource_scheduler_policy",
        "cuda_bge_queue_policy",
        "token_budget_model_tier_policy",
    ]


def test_role_source_layer_distribution_exposes_selector_gap_without_exact_promotion() -> None:
    distribution = build_role_source_layer_distribution(
        {
            "rows": [
                {
                    "source_id": "company_ir_reports",
                    "layer_id": "L1",
                    "evidence_graph_status": "staging_parser_gate_pending",
                    "specialist_slots": ["product_technology"],
                    "context_or_proxy_allowed": True,
                    "exact_value_authority_ready": False,
                    "can_support_company_exact_fact": False,
                },
                {
                    "source_id": "company_product_pages",
                    "layer_id": "L2",
                    "evidence_graph_status": "structured_not_promoted",
                    "specialist_slots": ["product_technology"],
                    "context_or_proxy_allowed": True,
                    "exact_value_authority_ready": False,
                    "can_support_company_exact_fact": False,
                },
                {
                    "source_id": "ecommerce_major_platforms",
                    "layer_id": "L3",
                    "evidence_graph_status": "not_registered",
                    "specialist_slots": ["product_technology"],
                    "context_or_proxy_allowed": False,
                    "exact_value_authority_ready": False,
                    "can_support_company_exact_fact": False,
                },
            ]
        },
        roles=["product_technology_analyst"],
    )

    product = distribution["roles"]["product_technology_analyst"]
    assert distribution["status"] == "gap"
    assert distribution["gap_roles"] == ["product_technology_analyst"]
    assert product["candidate_count"] == 3
    assert product["selected_by_layer"] == {"L1": 1, "L2": 1}
    assert product["selected_missing_required_layers"] == ["L3"]
    assert product["not_registered_count"] == 1
    assert product["exact_authority_violation_sources"] == []


def test_eval_store_records_case_node_and_failure_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "eval_store.sqlite"
    migration = migrate_eval_store(db_path)

    register_eval_case(
        db_path,
        {
            "eval_id": "runtime_bridge_smoke",
            "case_id": "java_python_bridge",
            "dataset_id": "bridge_dataset",
            "case_family": "bridge",
        },
    )
    record_eval_gold_promotion(
        db_path,
        {
            "eval_id": "runtime_bridge_smoke",
            "case_id": "java_python_bridge",
            "state": "candidate",
            "criteria_version": "unit",
            "review_method": "system",
        },
    )
    report = record_eval_case_result(
        db_path,
        {
            "eval_id": "runtime_bridge_smoke",
            "case_id": "java_python_bridge",
            "run_id": "run_bridge_001",
            "status": "pass",
            "score": 1.0,
            "node_results": [{"node": "java_gateway", "status": "pass", "metrics": [{"name": "accepted", "value": 1, "status": "pass"}]}],
            "failure_events": [
                {
                    "failure_type": "table_refs_missing",
                    "node": "data_processing_quality",
                    "expected": "table refs",
                    "actual": "missing",
                    "status": "observed",
                }
            ],
            "annotations": [{"annotator": "system", "label": "smoke"}],
            "judge_runs": [{"judge_model": "deterministic", "rubric_version": "unit", "prompt_digest": "sha256:test", "score": 1}],
        },
    )

    counts = read_eval_counts(db_path)
    assert migration["storage_policy"] == "sql_backed_eval_source_jsonl_import_export_only_v0_1"
    assert report["status"] == "pass"
    assert counts["eval_case_result"] == 1
    assert counts["eval_node_result"] == 1
    assert counts["eval_metric_result"] == 1
    assert counts["eval_failure_event"] == 1
    assert counts["eval_case_membership"] == 1
    assert counts["eval_gold_promotion"] == 1
    assert counts["eval_judge_run"] == 1
    assert counts["eval_dashboard_snapshot"] == 1


def test_data_processing_quality_flags_truncation_table_and_structured_binding() -> None:
    result = evaluate_data_processing_quality(
        [
            {
                "chunk_id": "good_chunk",
                "text": "Revenue table row",
                "record_type": "table",
                "table_id": "tbl1",
                "row_index": 1,
            },
            {"chunk_id": "bad_trunc", "text": "cut", "truncated": True},
            {"chunk_id": "bad_table", "text": "row", "record_type": "table"},
            {"chunk_id": "bad_structured", "text": "metric", "structured_metric": True, "value": "10"},
        ]
    )

    failure_types = {row["failure_type"] for row in result["failure_events"]}
    assert result["status"] == "fail"
    assert "truncation_reason_missing" in failure_types
    assert "table_refs_missing" in failure_types
    assert "structured_unit_missing" in failure_types
    assert "structured_period_missing" in failure_types
    assert "structured_entity_missing" in failure_types


def test_index_and_retrieval_quality_gates_flag_authority_and_visibility() -> None:
    index_result = evaluate_index_asset_quality(
        [
            {"record_id": "m1", "ticker": "NVDA", "source_family": "milvus_semantic", "milvus_record": True, "authority": "exact"},
            {"record_id": "ok", "ticker": "NVDA", "source_family": "primary_sec_filing", "vector_expected": True, "vector_present": True},
        ]
    )
    retrieval_result = evaluate_retrieval_quality(
        [{"task_id": "ret", "target_in_candidates": True, "pre_rerank_count": 8, "post_rerank_count": 3, "role_visible_count": 0}]
    )

    assert index_result["status"] == "fail"
    assert {row["failure_type"] for row in index_result["failure_events"]} == {"milvus_exact_authority_forbidden"}
    assert retrieval_result["status"] == "fail"
    assert retrieval_result["failure_events"][0]["failure_type"] == "role_visible_rows_missing"


def test_resource_scheduler_queues_cuda_before_cpu_spillover_and_coalesces_models() -> None:
    scheduled = schedule_inference_tasks(
        [
            InferenceTask("t3", route="memo_writer", priority=3, requires_cuda_bge=False, model_tier="pro"),
            InferenceTask("t1", route="retrieval", priority=1, requires_cuda_bge=True),
            InferenceTask("t2", route="retrieval", priority=2, requires_cuda_bge=True),
            InferenceTask("t4", route="retrieval", priority=4, requires_cuda_bge=True),
            InferenceTask("t5", route="exact_lookup", priority=5, requires_cuda_bge=False),
        ],
        cuda_bge_slots=2,
        token_budget_pressure=True,
    )

    by_id = {item.task_id: item for item in scheduled}
    assert by_id["t1"].lane == "bge_cuda"
    assert by_id["t2"].lane == "bge_cuda"
    assert by_id["t4"].lane == "bge_cpu_spillover"
    assert by_id["t3"].model_tier == "flash_or_coalesced"
    assert by_id["t5"].model_tier == "deterministic"


def test_resource_scheduler_audit_and_agent_coalescer() -> None:
    tasks = coalesce_agent_tasks(
        [
            InferenceTask("a", route="specialist", priority=4, model_tier="standard"),
            InferenceTask("b", route="specialist", priority=5, model_tier="standard"),
            InferenceTask("c", route="retrieval", priority=1, requires_cuda_bge=True, can_spill_to_cpu=False),
            InferenceTask("d", route="retrieval", priority=2, requires_cuda_bge=True, can_spill_to_cpu=False),
        ]
    )
    audit = schedule_inference_tasks_with_audit(tasks, cuda_bge_slots=1, cpu_spillover_allowed=False)

    assert any(task.task_id == "a+b" for task in tasks)
    queued = [item for item in audit.scheduled_tasks if item["lane"] == "queued_bge_cuda"]
    assert queued and queued[0]["queue_position"] == 1
    assert audit.lane_counts["bge_cuda"] == 1


def test_task_worker_supports_catalog_eval_ids_and_case_id_filters() -> None:
    assert {
        "agent_graph_vnext_r12_successor_12",
        "agent_graph_vnext_broader_release_20",
        "agent_graph_vnext_load_mix_15",
    } <= REAL_EVAL_IDS

    assert _metadata_case_ids({"case_ids": ["case_a", "case_b"]}) == ["case_a", "case_b"]
    assert _metadata_case_ids({"case_ids": "case_a, case_b"}) == ["case_a", "case_b"]
    assert _metadata_case_ids({"case_id": "case_single"}) == ["case_single"]

    args = _append_repeatable_args(["python", "runner.py"], "--case-id", ["case_a", "case_b"])
    assert args[-4:] == ["--case-id", "case_a", "--case-id", "case_b"]


def test_runtime_baseline_object_store_context_tool_input_and_lead_contracts(tmp_path: Path) -> None:
    baseline = build_runtime_baseline_report(repo_root=tmp_path)
    object_ref = put_json_object({"sample": True}, object_store_root=tmp_path / "objects", namespace="unit")

    engine = ContextEngine()
    resolved = engine.resolve({"query_contract": {"focus_tickers": ["NVDA"]}, "source_gaps": [{"gap_type": "bounded_gap"}]})
    selected = engine.select(resolved["snapshots"], target_node="research_lead")
    injection = engine.inject(selected, target_node="research_lead")
    memory = engine.write_memory({"state": "active", "claim_refs": ["claim1"], "summary": "memory"})

    registry = default_tool_capability_registry()
    writer_db_gate = validate_tool_invocation("database_query", node="memo_writer", agent_id="memo_writer", registry=registry)
    renderer_gate = validate_tool_invocation("report_renderer", node="memo_writer", agent_id="memo_writer", registry=registry)

    upload = tmp_path / "note.md"
    upload.write_text("# note\n", encoding="utf-8")
    parsed = parse_user_input_file(upload, object_store_root=tmp_path / "objects", run_id="run")

    contract = build_research_objective_contract(query="Assess NVDA")
    checkpoint = build_lead_review_checkpoint(
        objective_contract=contract,
        retrieval_budget_audit={"routes": [{"route": "product", "source_family": "company_product_evidence_graph"}]},
        claim_cards=[{"claim_id": "claim1", "analysis_dimension": "fundamentals"}],
        gaps=[{"gap_id": "gap_product", "dimension": "product_and_production", "gap_type": "parser_failed"}],
        source_capability={"company_product_evidence_graph": {"status": "available"}},
    )
    repair = build_targeted_repair_plan(checkpoint)

    selector = select_role_evidence(
        [
            {"evidence_ref": "p1", "source_family": "company_product_evidence_graph", "metric": "product spec", "product": "H100"},
            {"evidence_ref": "f1", "source_family": "primary_sec_filing", "metric": "revenue"},
        ],
        role="product_technology_analyst",
    )

    memo_plan = build_memo_logic_plan(
        judgment_state={"dimension_judgments": [{"dimension_id": "fundamentals", "claim_ids": ["claim1"], "evidence_refs": ["ev1"]}]},
        lead_review_checkpoint={"dimension_reviews": [{"dimension": "fundamentals", "status": "sufficient"}]},
    )

    assert baseline["schema_version"] == "finsight_runtime_baseline_report_v0_1"
    assert object_ref["schema_version"] == "finsight_object_store_ref_v0_1"
    assert injection["target_node"] == "research_lead"
    assert memory["governance"]["status"] == "pass"
    assert writer_db_gate["status"] == "fail"
    assert renderer_gate["status"] == "pass"
    assert parsed["status"] == "pass"
    assert checkpoint["validation"]["status"] == "pass"
    assert repair["status"] == "ready"
    assert selector["selected_count"] >= 1
    assert memo_plan["validation"]["status"] == "pass"


def test_lead_supervision_routes_non_us_issuer_scope_gap_to_official_source_repair() -> None:
    contract = build_research_objective_contract(
        query="分析 ASML 的订单、产品和财务质量",
        required_dimensions=["fundamentals", "product_and_production"],
    )
    checkpoint = build_lead_review_checkpoint(
        objective_contract=contract,
        gaps=[
            {
                "gap_id": "gap_asml_route_scope",
                "ticker": "ASML",
                "analysis_dimension": "fundamentals",
                "gap_type": "issuer_official_source_probe_required",
                "reason_code": "not_in_manifest_for_mcp_route_scope",
                "reason": "ASML is outside local SEC/MCP route scope; official issuer filings should be probed.",
            }
        ],
        source_capability={"live_public_web_context": {"status": "available"}},
    )
    repair = build_targeted_repair_plan(checkpoint)

    issuer_reviews = checkpoint["issuer_coverage_reviews"]
    assert issuer_reviews
    assert issuer_reviews[0]["ticker"] == "ASML"
    assert issuer_reviews[0]["status"] == "retrievable_gap"
    official_repairs = [row for row in repair["repairs"] if row.get("route") == "official_issuer_disclosure_repair"]
    assert official_repairs
    asml_repair = official_repairs[0]
    assert asml_repair["ticker"] == "ASML"
    assert asml_repair["web_search_allowed"] is True
    assert asml_repair["source_probe_order"][:2] == ["sec_fpi_filings_20f_6k", "company_ir_reports"]
    assert {"company_ir", "local_exchange_filings", "regulator_filings", "sec_fpi_filings"} <= set(
        asml_repair["official_source_classes"]
    )
    assert asml_repair["not_found_gap"]["gap_type"] == "bounded_gap_after_official_issuer_source_probe"
    assert repair["validation"]["status"] == "pass"
    assert checkpoint["memo_directive"]["issuer_targeted_repair_required"] is True
    assert checkpoint["memo_directive"]["gap_budget_policy"]["max_gap_share_in_user_memo"] == 0.25


def test_official_issuer_repair_materializes_asml_sec_context_without_promoting_exact_fact() -> None:
    contract = build_research_objective_contract(
        query="分析 ASML 的订单、产品和财务质量",
        required_dimensions=["fundamentals", "product_and_production"],
    )
    checkpoint = build_lead_review_checkpoint(
        objective_contract=contract,
        gaps=[
            {
                "gap_id": "gap_asml_route_scope",
                "ticker": "ASML",
                "analysis_dimension": "fundamentals",
                "gap_type": "issuer_official_source_probe_required",
                "reason_code": "not_in_manifest_for_mcp_route_scope",
            }
        ],
        source_capability={"live_public_web_context": {"status": "available"}},
    )
    repair = build_targeted_repair_plan(checkpoint)

    def fake_fetch(url: str) -> tuple[int, str, str]:
        assert "data.sec.gov/submissions/CIK0000937966.json" in url
        return (
            200,
            "application/json",
            '{"name":"ASML Holding N.V.","filings":{"recent":{"form":["6-K","20-F","144"],"filingDate":["2026-04-16","2026-02-12","2026-01-01"],"accessionNumber":["0001","0002","0003"]}}}',
        )

    execution = execute_official_issuer_repair_plan(repair, fetch=fake_fetch, max_probes_per_issuer=1)

    assert execution["status"] == "pass"
    assert execution["attempted_count"] == 1
    assert execution["success_count"] >= 1
    issuer_rows = [
        row
        for row in execution["context_rows"]
        if isinstance(row, dict) and str(row.get("evidence_ref") or "").startswith("official_")
        and ":product_surface:" not in str(row.get("evidence_ref") or "")
    ]
    assert issuer_rows
    row = issuer_rows[0]
    assert row["ticker"] == "ASML"
    assert row["source_family"] == "live_public_web_context"
    assert row["context_only"] is True
    assert row["exact_value_authority"] is False
    assert "20-F" in row["preview"]
    structured_rows = [
        row
        for row in execution["context_rows"]
        if row.get("structured_fact_status") == "bounded_context_fact_materialized"
    ]
    assert any(row.get("structured_context_type") == "official_filing_presence_context" for row in structured_rows)
    assert all(row["exact_value_authority"] is False for row in structured_rows)
    assert execution["tool_observations"][0]["tool_name"] == "web_evidence_snapshot"
    product_rows = [
        row
        for row in execution["context_rows"]
        if isinstance(row, dict) and str(row.get("product_family") or "").strip()
    ]
    assert product_rows
    assert any(row["product_family"] == "EUV lithography systems" for row in product_rows)
    assert all(row["context_only"] is True and row["exact_value_authority"] is False for row in product_rows)
    assert all("no exact orders/backlog/sales/share authority" in row["claim_boundary"] for row in product_rows)
    claims = _lead_targeted_repair_context_claims(execution)
    assert claims
    assert claims[0]["agent_id"] == "research_lead"
    assert claims[0]["claim_type"] == "product_taxonomy_context"
    assert claims[0]["analysis_dimension"] == "product_and_production"
    assert "EUV lithography systems" in claims[0]["claim"]
    assert "does not promote exact sales" in claims[0]["claim"]
    assert claims[0]["source_families"] == ["live_public_web_context"]


def test_research_lead_proactively_routes_known_non_us_issuer_to_official_probe() -> None:
    gaps = _issuer_coverage_gaps_from_state(
        {
            "user_query": "分析 ASML、AMAT、LRCX、KLAC 的半导体设备周期",
            "agent_activation_plan": {
                "focus_tickers": ["ASML", "AMAT"],
                "search_scope_tickers": ["ASML", "AMAT", "LRCX"],
            },
            "context_rows": [{"ticker": "AMAT", "source_family": "primary_sec_filing"}],
            "runtime_ledger_rows": [],
            "source_gaps": [],
            "specialist_route_results": [],
        }
    )

    asml_gaps = [row for row in gaps if row.get("ticker") == "ASML"]
    assert asml_gaps
    assert asml_gaps[0]["gap_type"] == "issuer_official_source_probe_required"
    assert asml_gaps[0]["repairability"] == "retrievable_gap"
    assert asml_gaps[0]["source"] == "lead_known_issuer_profile"


def test_r0_r11_readiness_runner_passes_with_cloud_gap(tmp_path: Path) -> None:
    report = run_r0_r11_readiness(repo_root=Path.cwd(), output_dir=tmp_path)

    assert report["status"] in {"pass", "pass_with_cloud_gaps"}
    assert report["summary"]["gate_count"] == 12
    assert (tmp_path / "r0_r11_readiness_report.json").exists()
