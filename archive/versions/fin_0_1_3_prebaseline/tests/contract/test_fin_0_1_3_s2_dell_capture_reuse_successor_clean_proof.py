from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / (
    "scripts/releases/prove_fin_ia_0_1_3_s2_dell_capture_reuse_successor_clean.py"
)


def _module():
    spec = importlib.util.spec_from_file_location(
        "fixed_pack_capture_reuse_successor_clean_proof", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_worker_reuses_five_nodes_and_executes_only_remaining_eight() -> None:
    result = _module().run_worker(execution_git_commit="3" * 40)
    assert [row["node_key"] for row in result["predecessor_imported_nodes"]] == [
        "direct_baseline",
        "research_lead",
        "specialist::demand_authenticity_and_sustainability",
        "specialist::product_and_technology_position",
        "specialist::supply_capacity_and_competition",
    ]
    assert result["failed_predecessor_node"]["promoted_as_usable_output"] is False
    assert result["terminal"]["status"] == "completed"
    assert result["terminal"]["observed_counts"] == {
        "imported_usable_nodes": 5,
        "successor_provider_calls": 8,
        "successor_model_calls": 8,
        "combined_provider_attempts": 14,
        "logical_outputs_present": 13,
        "network_tool_calls": 0,
        "retries": 0,
        "fallbacks": 0,
        "findings": 0,
    }
    assert result["terminal"]["logical_node_indices"] == list(range(6, 14))
    assert result["request_captures"] == 8
    assert result["response_captures"] == 8
    assert result["real_provider_calls"] == 0
    assert result["model_calls"] == 0
    assert result["network_calls"] == 0


def test_fresh_worker_payload_is_deterministic() -> None:
    module = _module()
    first = module.run_worker(execution_git_commit="4" * 40)
    second = module.run_worker(execution_git_commit="4" * 40)
    assert first == second
    assert first["base_case_input_digest"] != first["successor_case_input_digest"]
