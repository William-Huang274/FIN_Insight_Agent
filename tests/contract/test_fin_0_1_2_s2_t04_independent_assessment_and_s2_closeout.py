from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CLOSEOUT = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_2_s2_t04_independent_blind_assessment_"
    "model_surface_disposition_and_s2_closeout_v1_0.json"
)
PROJECTION = ROOT / (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_20.json"
)
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
ROOT_CAUSE_LEDGER = ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"
CAPABILITY_LEDGER = ROOT / "docs/project_os/capability_status_ledger.jsonl"
PATTERN_LEDGER = ROOT / "docs/project_os/external_pattern_registry.jsonl"

EXPECTED_CLOSEOUT_SHA256 = (
    "72aed9bed5ef9ab735c7cb3054bdbc4352c5bbb57b6c53ead7c9f2e9189be73c"
)
EXPECTED_PROJECTION_SHA256 = (
    "6a71a8f8eeb59f17b86b807b0e0e942ba9915796c9b2a9c0e325c2a0c938ea00"
)
NEXT_ACTION = (
    "FIN-0.1.2-S3-STAGE-PLAN-AND-BOUNDED-MODEL-SURFACE-ENTRY-DECISION"
)
ISSUE_ID = (
    "RC-P36-104-fin-0-1-2-s2-t04-same-context-model-identity-"
    "contamination-and-unsealed-blind-assessment"
)


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load(path: Path) -> dict[str, Any]:
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_strict_object,
    )


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line, object_pairs_hook=_strict_object)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_closeout_bindings_exist_and_match_content_digests() -> None:
    closeout = _load(CLOSEOUT)
    assert _sha256(CLOSEOUT) == EXPECTED_CLOSEOUT_SHA256

    for binding in closeout["bindings"]:
        bound_path = ROOT / binding["ref"]
        assert bound_path.is_file(), binding["ref"]
        assert _sha256(bound_path) == binding["sha256"], binding["ref"]


def test_blind_selection_and_family_surface_boundary_are_frozen() -> None:
    closeout = _load(CLOSEOUT)
    assessment = closeout["independent_blind_assessment"]
    selection = closeout["model_selection"]
    surfaces = closeout["family_surface_disposition"]

    assert assessment["blind_scores"] == {"candidate_A": 18, "candidate_B": 13}
    assert assessment["revealed_mapping"] == {
        "candidate_A": "pro_preview",
        "candidate_B": "flash_stable",
    }
    assert assessment["revealed_scores"] == {
        "pro_preview": 18,
        "flash_stable": 13,
    }
    assert assessment["Pro_minus_Flash"] == 5
    assert selection["selected_candidate"] == "pro_preview"
    assert selection["automatic_runtime_fallback"] is False
    assert selection["runtime_mainline_changed_in_S2"] is False

    assert surfaces["specialist_fact_atoms"]["retained_model_surface"] is False
    assert surfaces["specialist_fact_atoms"]["scores"]["epistemic_discipline"] == 0
    assert surfaces["claim_candidate_atoms"]["retained_model_surface"] is True
    assert surfaces["what_would_change_atoms"]["retained_model_surface"] is True


def test_S2_is_closed_without_inflating_S3_or_release_state() -> None:
    closeout = _load(CLOSEOUT)
    acceptance = closeout["stage_acceptance"]
    counts = closeout["observed_counts"]

    assert acceptance["S2_T04"] == "pass"
    assert acceptance["S2"].startswith("pass_closed_")
    assert acceptance["S3_eligible"] is True
    assert acceptance["S3_started"] is False
    assert acceptance["release_qualified"] is False
    assert counts == {
        "product_model_calls": 0,
        "provider_calls": 0,
        "execution_network_calls": 0,
        "independent_evaluator_contexts": 1,
        "business_Run_or_Artifact_writes": 0,
    }
    assert closeout["next_action"] == NEXT_ACTION


def test_projection_and_backlog_point_to_the_same_current_truth() -> None:
    projection = _load(PROJECTION)
    backlog = _load(BACKLOG)
    rebaseline = backlog["current_version_rebaseline"]
    next_action = backlog["next_action"]

    assert _sha256(PROJECTION) == EXPECTED_PROJECTION_SHA256
    assert projection["implementation_binding"] == {
        "ref": str(CLOSEOUT.relative_to(ROOT)).replace("\\", "/"),
        "sha256": EXPECTED_CLOSEOUT_SHA256,
        "binding_role": (
            "S2_T04_independent_blind_assessment_model_local_surface_"
            "disposition_and_S2_closeout"
        ),
    }
    truth = projection["current_truth"]
    assert truth["stage"] == "S2_closed_S3_not_started"
    assert truth["current_next_action"] == NEXT_ACTION
    assert truth["runtime_mainline_changed_in_S2"] is False
    assert truth["retained_model_families"] == [
        "claim_candidate_atoms",
        "what_would_change_atoms",
    ]
    assert truth["local_deterministic_families"] == ["specialist_fact_atoms"]
    assert truth["release_qualified"] is False

    assert rebaseline["projection_ref"] == str(PROJECTION.relative_to(ROOT)).replace(
        "\\", "/"
    )
    assert rebaseline["current_stage"] == "S2_closed_S3_not_started"
    assert rebaseline["current_next_action"] == NEXT_ACTION
    assert next_action["current_projection_sha256"] == EXPECTED_PROJECTION_SHA256
    assert next_action["S2_T04_closeout_sha256"] == EXPECTED_CLOSEOUT_SHA256
    assert next_action["S2_T04_revealed_scores_Pro_Flash"] == [18, 13]
    assert next_action["S2_T04_S2_closed"] is True
    assert next_action["S3_started"] is False


def test_project_os_ledgers_preserve_internal_only_closure_boundary() -> None:
    issues = [
        item
        for item in _load_jsonl(ROOT_CAUSE_LEDGER)
        if item.get("issue_id") == ISSUE_ID
    ]
    assert issues[-1]["status"] == "closed"
    assert issues[-1]["full_chain_blocker"] is False
    assert issues[-1]["verification"]["score_frozen_before_mapping_read"] is True
    assert "no physically isolated external-audit claim" in issues[-1]["known_boundary"]

    capability = _load_jsonl(CAPABILITY_LEDGER)[-1]
    assert capability["capability_id"] == (
        "fin_0_1_2_S2_T04_independent_blind_assessment_"
        "model_surface_disposition_and_S2_closeout"
    )
    assert capability["stage_acceptance"]["FIN_0_1_2_S2"] == "pass_closed"
    assert capability["stage_acceptance"]["FIN_0_1_2_S3"] == (
        "not_started_ready_for_stage_plan"
    )
    assert capability["current_next"] == NEXT_ACTION

    pattern = _load_jsonl(PATTERN_LEDGER)[-1]
    assert pattern["pattern_id"] == (
        "blinded_model_assessment_requires_identity_isolation_"
        "and_score_freeze_before_reveal"
    )
    assert pattern["verification"]["mapping_nonce_bits"] == 256
    assert pattern["verification"]["score_frozen_before_reveal"] is True
    assert "not physical external-audit isolation" in pattern["known_boundary"]
