from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest


ROOT = Path(__file__).resolve().parents[2]
DECISION = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_3_s2_05_experiment_a_"
    "admission_authority_decision_v1_0.json"
)
FREEZE = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_3_s2_04_shared_benchmark_"
    "evidence_freeze_v1_0.json"
)
BLIND = ROOT / "eval_sets" / "fin_0_1_3_same_evidence_v1" / (
    "model_visible/experiment_a_blind_inputs_v1.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate(decision: dict) -> None:
    body = {
        key: deepcopy(value)
        for key, value in decision.items()
        if key != "decision_digest"
    }
    if decision.get("decision_digest") != canonical_digest(body):
        raise ValueError("s2_05_authority_decision_digest_invalid")
    authority = decision.get("authority") or {}
    blockers = decision.get("blocking_findings") or []
    if blockers and (
        authority.get("admission_issuance_authorized") is not False
        or authority.get("admission_consumption_authorized") is not False
    ):
        raise ValueError("s2_05_authority_cannot_open_with_material_blockers")
    if any(authority.get(key) != 0 for key in (
        "model_calls",
        "provider_calls",
        "network_calls",
        "mcp_calls",
        "business_runs",
    )):
        raise ValueError("s2_05_decision_must_be_zero_call")
    frozen = decision.get("frozen_input_binding") or {}
    if frozen.get("model_file_allowlist") != [frozen.get("model_visible_input_ref")]:
        raise ValueError("s2_05_model_allowlist_not_exact")
    if not frozen.get("evaluator_only_ref_forbidden_to_raw_runner"):
        raise ValueError("s2_05_hidden_gold_denial_missing")
    scope = decision.get("single_successor_implementation_scope") or {}
    nodes = scope.get("dynamic_node_envelope") or {}
    unit_range = nodes.get("specialist_research_units_per_case") or {}
    if unit_range != {"minimum": 6, "maximum": 8}:
        raise ValueError("s2_05_dynamic_research_unit_range_invalid")
    if nodes.get("provider_calls_per_case") != {"minimum": 10, "maximum": 12}:
        raise ValueError("s2_05_case_call_range_invalid")
    if nodes.get("provider_calls_campaign_maximum") != 36:
        raise ValueError("s2_05_campaign_call_ceiling_invalid")
    if nodes.get("retry_count") != 0 or nodes.get("fallback_count") != 0:
        raise ValueError("s2_05_retry_or_fallback_forbidden")
    case_admissions = scope.get("case_admissions") or {}
    if (
        case_admissions.get("maximum") != 3
        or case_admissions.get("one_case_per_admission") is not True
        or case_admissions.get("automatic_next_case_after_material_failure") is not False
    ):
        raise ValueError("s2_05_case_admission_boundary_invalid")
    tracks = scope.get("persistence_boundaries") or {}
    if set(tracks) != {
        "raw_model_only",
        "supervisor_corrections",
        "corrected_candidates",
        "evaluator_only",
    }:
        raise ValueError("s2_05_persistence_tracks_invalid")


def test_current_authority_decision_is_zero_call_honest_block() -> None:
    decision = _load(DECISION)
    _validate(decision)
    assert decision["status"].startswith("authority_not_issued")
    assert len(decision["blocking_findings"]) == 5
    assert all(row["material"] for row in decision["blocking_findings"])
    assert decision["next_action"].endswith(
        "DYNAMIC-NODE-RUNNER-AND-ZERO-CALL-PREFLIGHT-MINIMUM-IMPLEMENTATION"
    )


def test_frozen_input_binding_matches_s2_04_without_hidden_gold_access() -> None:
    decision = _load(DECISION)
    freeze = _load(FREEZE)
    blind = _load(BLIND)
    binding = decision["frozen_input_binding"]

    assert binding["freeze_manifest_sha256"] == _sha256(FREEZE)
    assert binding["model_visible_input_sha256"] == _sha256(BLIND)
    assert binding["freeze_manifest_digest"] == freeze["manifest_digest"]
    assert binding["model_visible_input_digest"] == blind["blind_input_digest"]
    assert binding["cases"] == ["DELL", "MU", "NVDA"]
    assert binding["as_of"] == "2026-08-06"
    assert "evaluator_only" not in binding["model_file_allowlist"][0]
    assert "evaluator_only" in binding[
        "evaluator_only_ref_forbidden_to_raw_runner"
    ]


def test_successor_is_dynamic_product_research_not_old_nine_call_reuse() -> None:
    decision = _load(DECISION)
    scope = decision["single_successor_implementation_scope"]
    envelope = scope["dynamic_node_envelope"]

    assert len(scope["mandatory_research_families"]) == 6
    assert envelope["provider_calls_per_case"]["minimum"] > 9
    assert envelope["provider_calls_campaign_maximum"] == 36
    assert len(scope["node_contract_requirements"]) == 5
    assert len(scope["material_stop_conditions"]) >= 10
    assert all(
        row["compatible"] is False
        for row in decision["compatibility_audit"]["existing_runners"]
    )


@pytest.mark.parametrize(
    ("mutator", "expected"),
    [
        (
            lambda value: value["authority"].update(
                admission_issuance_authorized=True
            ),
            "s2_05_authority_cannot_open_with_material_blockers",
        ),
        (
            lambda value: value["frozen_input_binding"].update(
                model_file_allowlist=["eval_sets/fin_0_1_3_same_evidence_v1"]
            ),
            "s2_05_model_allowlist_not_exact",
        ),
        (
            lambda value: value["single_successor_implementation_scope"][
                "dynamic_node_envelope"
            ].update(retry_count=1),
            "s2_05_retry_or_fallback_forbidden",
        ),
    ],
)
def test_material_authority_mutations_fail_closed(mutator, expected: str) -> None:
    decision = _load(DECISION)
    mutator(decision)
    body = {
        key: deepcopy(value)
        for key, value in decision.items()
        if key != "decision_digest"
    }
    decision["decision_digest"] = canonical_digest(body)
    with pytest.raises(ValueError, match=expected):
        _validate(decision)


def test_digest_mutation_fails_closed() -> None:
    decision = _load(DECISION)
    decision["execution_head"] = "0" * 40
    with pytest.raises(ValueError, match="s2_05_authority_decision_digest_invalid"):
        _validate(decision)
