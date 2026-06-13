from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .paths import resolve_runtime_paths


def runtime_bridge_registry(*, repo_root: str | None = None) -> dict[str, Any]:
    """Machine-readable P0-P9 bridge baseline for backend/runtime/eval gates."""
    paths = resolve_runtime_paths(repo_root)
    return {
        "schema_version": "finsight_runtime_bridge_registry_v0_1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "architecture_policy": {
            "java_gateway": "frontdoor_for_research_tasks",
            "python_worker": "langgraph_and_evidence_runtime_owner",
            "sql_store": "final_audit_source",
            "redis_or_mq": "coordination_and_queue_only",
            "object_store": "raw_and_large_artifact_store",
            "milvus": "semantic_recall_supplement_not_exact_authority",
            "local_adapter_policy": "allowed_for_smoke_with_parity_contract_not_final_backend",
        },
        "runtime_paths": paths.as_dict(),
        "p_series_capabilities": {
            "P0": {
                "name": "baseline_registry_and_route",
                "status": "implemented_minimal",
                "gates": ["storage_route_declared", "resource_blocked_policy_declared", "path_registry_declared"],
            },
            "P1": {
                "name": "run_audit_foundation",
                "status": "implemented_minimal",
                "gates": ["java_task_id", "worker_status_callback", "task_status_lookup"],
            },
            "P2": {
                "name": "eval_store_skeleton",
                "status": "implemented_minimal",
                "gates": ["sql_backed_eval_schema", "failure_event_row", "gold_state_row"],
            },
            "P3": {
                "name": "context_runtime_contract",
                "status": "contract_only",
                "gates": ["context_snapshot_ref", "prompt_digest_ready"],
            },
            "P4": {
                "name": "retrieval_role_visible_data_quality",
                "status": "implemented_minimal",
                "gates": ["chunk_boundary_eval", "table_extraction_eval", "retrieval_loss_attribution"],
            },
            "P5": {
                "name": "research_lead_supervised_loop",
                "status": "contract_only",
                "gates": ["objective_contract", "lead_review_checkpoint", "targeted_repair_plan"],
            },
            "P6": {
                "name": "tool_and_input_capability",
                "status": "contract_only",
                "gates": ["document_parser_refs", "web_snapshot_first", "renderer_only_writer_tools"],
            },
            "P7": {
                "name": "judgment_memo_verifier_surface",
                "status": "contract_only",
                "gates": ["memo_logic_plan", "writer_no_new_facts", "verifier_return_path"],
            },
            "P8": {
                "name": "trace_eval_dashboard_surface",
                "status": "implemented_minimal_api",
                "gates": ["task_status_endpoint", "memo_and_evidence_response", "error_surface"],
            },
            "P9": {
                "name": "concurrency_sla_resource_scheduling",
                "status": "implemented_minimal",
                "gates": ["queue_mode_declared", "redis_contract", "resource_scheduler_policy"],
            },
        },
    }
