from __future__ import annotations

from pathlib import Path

from sec_agent.runtime_bridge.contracts import runtime_bridge_registry
from sec_agent.runtime_bridge.data_quality import evaluate_data_processing_quality
from sec_agent.runtime_bridge.eval_store import migrate_eval_store, read_eval_counts, record_eval_case_result
from sec_agent.runtime_bridge.resource_scheduler import InferenceTask, schedule_inference_tasks


def test_runtime_bridge_registry_records_storage_and_path_boundaries(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FINSIGHT_DATA_ROOT", str(tmp_path / "data_d"))
    monkeypatch.setenv("FINSIGHT_SECONDARY_DATA_ROOTS", str(tmp_path / "data_z"))
    monkeypatch.setenv("FINSIGHT_MILVUS_MODE", "unbound_cloud_deferred")

    registry = runtime_bridge_registry(repo_root=str(tmp_path))

    assert registry["architecture_policy"]["java_gateway"] == "frontdoor_for_research_tasks"
    assert registry["architecture_policy"]["milvus"] == "semantic_recall_supplement_not_exact_authority"
    assert registry["runtime_paths"]["primary_data_root"].endswith("data_d")
    assert registry["runtime_paths"]["secondary_data_roots"][0].endswith("data_z")
    assert registry["p_series_capabilities"]["P0"]["status"] == "implemented_minimal"
    assert registry["p_series_capabilities"]["P9"]["gates"] == [
        "queue_mode_declared",
        "redis_contract",
        "resource_scheduler_policy",
    ]


def test_eval_store_records_case_node_and_failure_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "eval_store.sqlite"
    migration = migrate_eval_store(db_path)

    report = record_eval_case_result(
        db_path,
        {
            "eval_id": "runtime_bridge_smoke",
            "case_id": "java_python_bridge",
            "run_id": "run_bridge_001",
            "status": "pass",
            "score": 1.0,
            "node_results": [{"node": "java_gateway", "status": "pass", "metrics": [{"name": "accepted", "value": 1}]}],
            "failure_events": [
                {
                    "failure_type": "table_refs_missing",
                    "node": "data_processing_quality",
                    "expected": "table refs",
                    "actual": "missing",
                    "status": "observed",
                }
            ],
        },
    )

    counts = read_eval_counts(db_path)
    assert migration["storage_policy"] == "sql_backed_eval_source_jsonl_import_export_only_v0_1"
    assert report["status"] == "pass"
    assert counts["eval_case_result"] == 1
    assert counts["eval_node_result"] == 1
    assert counts["eval_failure_event"] == 1


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
