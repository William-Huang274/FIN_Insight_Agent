from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest


RESULT = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_live_"
    "terminal_and_semantic_audit_v1_0.json"
)
AUTHORITY = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_live_"
    "execution_authority_decision_v1_0.json"
)


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_public_result_is_canonical_and_authority_bound() -> None:
    result = _load(RESULT)
    authority = _load(AUTHORITY)
    body = {key: value for key, value in result.items() if key != "result_digest"}

    assert result["result_digest"] == canonical_digest(body)
    assert result["execution_authority"]["execution_authority_digest"] == (
        authority["execution_authority_digest"]
    )
    assert result["execution_authority"]["issuance_digest"] == (
        authority["issuance_digest"]
    )
    assert result["execution_authority"]["admission_digest"] == (
        authority["admission_digest"]
    )


def test_formal_terminal_remains_failed_and_exact_once() -> None:
    result = _load(RESULT)
    terminal = result["formal_terminal"]
    observed = result["provider_observation"]

    assert terminal["status"] == "failed"
    assert terminal["terminal_phase"] == "contract_validation"
    assert terminal["terminal_code"] == (
        "natural_node_canary_required_presentations_missing"
    )
    assert observed["provider_calls"] == 1
    assert observed["model_calls"] == 1
    assert observed["retries"] == 0
    assert observed["fallbacks"] == 0
    assert result["disposition"]["admission_consumed"] is True
    assert result["disposition"]["automatic_retry_or_second_canary"] is False
    assert result["stage_acceptance"]["formal_canary_contract_pass"] is False


def test_failure_is_exact_inflection_not_financial_content_error() -> None:
    result = _load(RESULT)
    audit = result["captured_output_audit"]
    failure = result["first_credible_failure_audit"]

    assert audit["json_and_identity_valid"]
    assert len(audit["used_numeric_refs"]) == 4
    assert audit["hpe_readthrough_not_recast_as_dell_direct_fact"]
    assert audit["pull_forward_not_quantified"]
    assert audit["orders_and_backlog_not_recast_as_unconditional_revenue"]
    assert audit["cancellation_or_linear_conversion_not_inferred"]
    assert audit["asp_or_margin_bridge_not_inferred"]
    assert not audit["free_arithmetic_observed"]
    assert failure["required_canonical_surface"] == (
        "customer count surpassed 5,000"
    )
    assert failure["observed_surface"] == "customer count surpassing 5,000"
    assert not failure["numeric_value_changed"]
    assert not failure["qualifier_direction_changed"]
    assert not failure["numeric_ref_missing_or_wrong"]
    assert failure["formal_exact_surface_contract_compliance"] is False
    assert failure["substantive_financial_or_research_error"] is False
    assert failure["project_hard_gate_severity_classification_correct"] is False


def test_zero_call_counterfactual_is_one_word_only_and_passes_all_later_gates() -> None:
    result = _load(RESULT)
    replay = result["zero_call_counterfactual_replay"]

    assert replay["provider_calls"] == 0
    assert replay["model_calls"] == 0
    assert replay["network_calls"] == 0
    assert replay["retries"] == 0
    assert replay["all_other_output_fields_and_text_unchanged"]
    assert replay["only_change"] == (
        "replace customer count surpassing 5,000 with customer count surpassed 5,000"
    )
    assert replay["validator_status"] == "pass"
    assert set(replay["boundary_topic_groups"]) == {"conversion", "margin"}


def test_no_product_or_stage_promotion_is_claimed() -> None:
    result = _load(RESULT)
    stage = result["stage_acceptance"]

    assert result["formal_terminal"]["business_artifact_promotion"] is False
    assert not stage["dell_delivery_pass"]
    assert not stage["S2_closeout"]
    assert not stage["owner_acceptance"]
    assert not stage["release"]
    assert result["disposition"]["owner_stage"] == "S2"
