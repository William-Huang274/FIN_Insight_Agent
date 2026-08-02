from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from test_fin_0_1_2_s2_paired_model_canary_compiler import _compiler


AUTHORITY = ROOT / (
    "configs/releases/fin_ia_0_1_2_s2_t03_mu_three_family_flash_"
    "stable_vs_pro_preview_paired_natural_output_canary_authority_"
    "decision_v1_0.json"
)
PROJECTION = ROOT / (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_11.json"
)
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_authority_binds_current_assets_and_exact_six_compiled_calls() -> None:
    authority = _load(AUTHORITY)
    for binding in authority["bindings"]:
        assert hashlib.sha256((ROOT / binding["ref"]).read_bytes()).hexdigest() == (
            binding["sha256"]
        )

    compiled = _compiler("MU").compile_primary_calls()
    frozen = authority["exact_canary"]["call_plan"]
    assert len(compiled) == len(frozen) == 6
    assert [call.call_id for call in compiled] == [row["call_id"] for row in frozen]
    for call, row in zip(compiled, frozen, strict=True):
        assert call.family_id == row["family_id"]
        assert call.candidate.candidate_id == row["candidate_id"]
        assert call.candidate.model_ref == row["model_ref"]
        assert call.model_visible_request_digest == row["model_visible_request_digest"]
        assert call.request_equivalence_digest == row["request_equivalence_digest"]


def test_each_family_is_a_fair_flash_pro_pair() -> None:
    rows = _load(AUTHORITY)["exact_canary"]["call_plan"]
    families = {row["family_id"] for row in rows}
    assert families == {
        "specialist_fact_atoms",
        "claim_candidate_atoms",
        "what_would_change_atoms",
    }
    for family in families:
        pair = [row for row in rows if row["family_id"] == family]
        assert {row["candidate_id"] for row in pair} == {
            "flash_stable",
            "pro_preview",
        }
        assert len({row["model_visible_request_digest"] for row in pair}) == 1
        assert len({row["request_equivalence_digest"] for row in pair}) == 1


def test_authority_is_conditional_and_does_not_claim_execution() -> None:
    authority = _load(AUTHORITY)
    permission = authority["authority"]
    counts = authority["current_turn_observed_counts"]
    budget = authority["hard_budget"]

    assert permission["future_exact_six_call_canary_authorized"]
    assert permission[
        "authorization_effective_only_after_bound_runner_and_atomic_capture_preflight_pass"
    ]
    assert not permission["current_turn_credential_read_authorized"]
    assert not permission["current_turn_model_provider_or_execution_network_authorized"]
    assert not permission["business_run_or_artifact_write_authorized"]
    assert not permission["automatic_replacement_pair_authorized"]
    assert set(counts.values()) == {0}
    assert budget["primary_semantic_model_calls"] == 6
    assert budget["maximum_total_semantic_model_calls"] == 8
    assert budget["retry_budget"] == 0
    assert budget["fallback_budget"] == 0
    assert budget["canonical_business_Run_or_Artifact_writes"] == 0


def test_preexecution_gap_is_owned_by_t03_and_not_misclassified() -> None:
    authority = _load(AUTHORITY)
    gap = authority["preexecution_gap"]
    routes = authority["strict_schema_transport_boundary"]

    assert gap["issue_id"].startswith("RC-P36-101-")
    assert gap["not_a_model_failure"]
    assert gap["not_a_provider_failure"]
    assert gap["not_a_sub2api_route_issue"]
    assert len(gap["required_minimum_fix"]) == 5
    assert routes["sub2api_gpt_5_5_responses_route"].startswith("parked")
    assert routes["routes_are_not_interchangeable"]
    assert authority["stage_acceptance"]["S2_T03"].startswith(
        "conditional_authority_issued"
    )


def test_projection_and_backlog_route_to_runner_preflight_only() -> None:
    authority = _load(AUTHORITY)
    projection = _load(PROJECTION)
    backlog = _load(BACKLOG)["next_action"]
    authority_sha = hashlib.sha256(AUTHORITY.read_bytes()).hexdigest()
    projection_sha = hashlib.sha256(PROJECTION.read_bytes()).hexdigest()

    assert projection["decision_binding"]["sha256"] == authority_sha
    assert projection["current_truth"]["current_next_action"] == (
        authority["next_action"]
    )
    assert projection["current_truth"]["S2_model_calls"] == 0
    assert not projection["current_truth"]["S2_model_canary_execution_started"]
    assert backlog["item_id"] == authority["next_action"]
    assert backlog["current_projection_sha256"] == projection_sha
    assert backlog["S2_T03_authority_sha256"] == authority_sha
    assert backlog["S2_T03_current_model_provider_network_calls"] == [0, 0, 0]
