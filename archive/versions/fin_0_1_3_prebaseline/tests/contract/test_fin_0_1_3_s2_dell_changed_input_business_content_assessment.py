from __future__ import annotations

import json
from pathlib import Path

from sec_agent.s1_six_case_local_evidence_pack import (
    canonical_digest,
    file_sha256,
)


ROOT = Path(__file__).resolve().parents[2]
ASSESSMENT_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s2_dell_changed_input_business_content_assessment_v1_0.json"
)
CURRENT_RESULT_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s2_dell_changed_input_model_comparison_result_v1_0.json"
)
PRIOR_RESULT_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s2_dell_capture_reuse_successor_result_v1_0.json"
)


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_issue(issue_id: str) -> dict[str, object]:
    rows = [
        json.loads(line)
        for line in (
            ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return [row for row in rows if row.get("issue_id") == issue_id][-1]


def test_assessment_is_digest_and_result_bound() -> None:
    assessment = _json(ASSESSMENT_PATH)
    body = {
        key: value
        for key, value in assessment.items()
        if key != "assessment_digest"
    }
    assert assessment["assessment_digest"] == canonical_digest(body)

    current = _json(CURRENT_RESULT_PATH)
    prior = _json(PRIOR_RESULT_PATH)
    basis = assessment["comparison_basis"]
    assert basis["current_agent_result_digest"] == current["result_digest"]
    assert basis["prior_agent_result_digest"] == prior["result_digest"]
    assert basis["current_agent_result_sha256"] == file_sha256(
        CURRENT_RESULT_PATH
    )
    assert basis["prior_agent_result_sha256"] == file_sha256(PRIOR_RESULT_PATH)
    assert basis["strict_same_input_pair"] is False


def test_assessment_preserves_quality_gain_and_delivery_failure() -> None:
    assessment = _json(ASSESSMENT_PATH)
    disposition = assessment["product_disposition"]
    assert disposition["content_quality_increment"] == "material_positive"
    assert disposition["delivery_gate"] == "failed_L1"
    assert disposition["source_increment_not_utilized"] is False
    assert disposition["rerun_authorized"] is False
    assert disposition["owner_acceptance_eligible"] is False
    assert disposition["release_eligible"] is False

    shape = assessment["content_shape"]
    assert shape["current_agent"]["evidence_items_used"] == 24
    assert shape["current_agent"]["evidence_items_visible"] == 27
    assert shape["current_direct_baseline"]["local_L1_findings"] == 8
    assert assessment["layered_control_observation"][
        "agent_final_L1_findings"
    ] == 2

    tokens = sorted(
        token
        for row in assessment["L1_disposition"]
        for token in row["numeric_tokens"]
    )
    assert tokens == ["16.1", "5000", "97.8%"]


def test_project_os_keeps_failures_in_their_owning_stages() -> None:
    numeric = _latest_issue(
        "RC-P36-170-fin-0-1-3-s2-fixed-pack-numeric-presentation-alias-and-formula-lineage-gap"
    )
    verifier = _latest_issue(
        "RC-P36-171-fin-0-1-3-s2-fixed-pack-verifier-output-capacity-and-incomplete-terminal-classification"
    )
    content = _latest_issue(
        "RC-P36-172-fin-0-1-3-s3-dell-fixed-pack-causal-boundary-wwc-and-content-density-gap"
    )
    retrieval = _latest_issue(
        "RC-P36-165-fin-0-1-3-s0-s1-financial-retrieval-evidence-pack-semantic-completeness-gap"
    )

    assert numeric["owner_stage"] == "S2"
    assert numeric["blocker_state"] == "open"
    assert verifier["owner_stage"] == "S2"
    assert verifier["blocker_state"] == "closed"
    assert content["owner_stage"] == "S3"
    assert content["blocker_state"] == "open"
    assert retrieval["owner_stage"] == "S1"
    assert "must not be reopened" in retrieval["state_detail"]
