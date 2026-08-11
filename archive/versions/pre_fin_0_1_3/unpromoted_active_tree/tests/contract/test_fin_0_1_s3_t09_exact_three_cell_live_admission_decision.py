from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s3_t09_exact_three_cell_live_admission_decision_v1_0.json"
)
BACKLOG = ROOT / "configs" / "releases" / "fin_ia_0_1_program_release_backlog_v2_0.json"
EXECUTOR = ROOT / "apps" / "workbench" / "backend" / "application" / "bounded_agent_executor.py"
RUNTIME = ROOT / "apps" / "workbench" / "backend" / "application" / "research_runtime.py"
ROOT_CAUSES = ROOT / "docs" / "project_os" / "root_cause_issue_ledger.jsonl"


def _decision() -> dict[str, object]:
    return json.loads(DECISION.read_text(encoding="utf-8"))


def test_t09_decision_selects_exact_target_without_issuing_or_executing() -> None:
    decision = _decision()
    target = decision["selected_target_binding"]
    budget = decision["frozen_six_node_budget"]
    observed = decision["observed_counts"]

    assert target["provider"] == "deepseek"
    assert target["model"] == "deepseek-v4-pro"
    assert target["credential_env"] == "DEEPSEEK_API_KEY"
    assert target["credential_value_read_or_persisted"] is False
    assert len(budget["node_topology"]) == 6
    assert budget["max_semantic_model_calls"] == 6
    assert budget["max_provider_calls"] == 6
    assert budget["max_execution_network_calls"] == 6
    assert budget["max_transport_attempts_per_call"] == 1
    assert budget["retry_budget"] == 0
    assert budget["maximum_aggregate_output_tokens"] == 7800
    assert set(observed.values()) == {0}
    assert decision["decision"]["issue_exact_admission_now"] is False
    assert decision["decision"]["execute_live_run_now"] is False


def test_t09_decision_preserves_both_owned_preissuance_blockers_as_history() -> None:
    decision = _decision()
    input_binding = decision["immutable_input_binding_decision"]
    adapter = decision["owned_provider_node_adapter_decision"]

    assert input_binding["input_digest"] is None
    assert input_binding["status"] == "blocked_owned_zero_call_prepare_contract_missing"
    assert adapter["status"] == "blocked_owned_six_node_provider_adapter_missing"

    executor_source = EXECUTOR.read_text(encoding="utf-8")
    runtime_source = RUNTIME.read_text(encoding="utf-8")
    assert "class S3ThreeCellAgentNodeExecutorPort(Protocol)" in executor_source
    assert executor_source.count("S3ThreeCellAgentNodeExecutorPort") == 2
    assert "def build_bounded_agent_executor_for_admission(" in executor_source
    assert "def build_s3_three_cell_bounded_agent_executor_for_admission(" in executor_source
    assert "def prepare_s3_three_cell_bounded_agent_exact_input(" in runtime_source
    assert runtime_source.index("start_result = self._facade.start_research_run(start)") < runtime_source.index(
        "profile_result = adapter.execute("
    )
    assert runtime_source.index(
        "class _S3ThreeCellBoundedAgentAdapter:"
    ) < runtime_source.rindex(
        "input_pack = _compile_s3_three_cell_bounded_agent_input_from_plans("
    )


def test_t09_backlog_stays_fail_closed_on_repair_before_admission() -> None:
    decision = _decision()
    backlog = json.loads(BACKLOG.read_text(encoding="utf-8"))
    next_action = backlog["next_action"]

    assert decision["next_action"] == (
        "S3-T09-DEEPSEEK-SIX-NODE-TRANSPORT-AND-EXACT-INPUT-ZERO-CALL-PREFLIGHT-REPAIR"
    )
    assert next_action["item_id"] == (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V5-RESEARCH-LEAD-OUTPUT-TRUNCATION-RESULT-AND-ROOT-CAUSE-DECISION"
    )
    assert next_action["fresh_v3_agent_proof_decision_authorized"] is True
    assert next_action["fresh_v3_exact_admission_issuance_authorized"] is True
    assert next_action["fresh_v3_exact_admission_issued"] is True
    assert next_action["fresh_v3_exact_live_execution_authorized"] is True
    assert next_action["S3_T09_decision_authorized"] is True
    assert next_action["S3_T09_admission_issuance_authorized"] is True
    assert next_action["S3_T09_execution_authorized"] is True
    assert next_action[
        "S3_T09_replacement_exact_admission_issuance_authorized"
    ] is True
    assert next_action["S3_T09_replacement_exact_admission_consumed"] is True
    assert next_action["S3_T09_replacement_exact_live_execution_authorized"] is True
    assert next_action[
        "S3_T09_replacement_artifact_paired_baseline_validation_authorized"
    ] is True
    assert next_action["deterministic_baseline_materialization_authorized"] is True
    assert next_action["replacement_admission_or_execution_authorized"] is False
    assert next_action["source_network_or_external_tool_execution_authorized"] is False


def test_t09_owned_blockers_preserve_machine_recognized_open_status_history() -> None:
    rows = [
        json.loads(line)
        for line in ROOT_CAUSES.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    expected = {
        "RC-P36-032-s3-three-cell-six-node-provider-adapter-missing",
        "RC-P36-033-s3-exact-input-run-before-prepare-cycle",
    }
    for issue_id in expected:
        historical = [
            row
            for row in rows
            if row.get("issue_id") == issue_id
            and row.get("status") == "root_cause_repair_required"
        ]
        assert len(historical) == 1
        assert historical[0]["full_chain_blocker"] is True
        assert "broad_full_chain" in historical[0]["blocking_run_scopes"]
