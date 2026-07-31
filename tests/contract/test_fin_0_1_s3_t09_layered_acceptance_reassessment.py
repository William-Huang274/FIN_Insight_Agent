import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STANDARD = ROOT / "configs/releases/fin_ia_0_1_layered_agent_acceptance_standard_v1_0.json"
REASSESSMENT = (
    ROOT
    / "configs/releases/fin_ia_0_1_s3_t09_layered_acceptance_reassessment_v1_0.json"
)
CONCEPT = (
    ROOT
    / "docs/architecture/repository/RELEASE_FIN_IA_0_1_EXECUTION_PLAN_20260717.zh-CN.md"
)
DETAIL = (
    ROOT
    / "docs/architecture/repository/RELEASE_FIN_IA_0_1_DETAILED_PRODUCT_TECHNICAL_DESIGN_20260717.zh-CN.md"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_layered_standard_keeps_truth_hard_and_style_soft() -> None:
    standard = _load(STANDARD)
    layers = {row["layer_id"]: row for row in standard["acceptance_layers"]}
    hard = layers["L1_hard_integrity"]
    quality = layers["L3_analytical_quality"]

    assert hard["default_runtime_disposition"] == "terminal_fail_closed"
    assert any("unsupported material claim" in gate for gate in hard["gates"])
    assert quality["default_runtime_disposition"].startswith(
        "persist_quality_findings"
    )
    assert (
        standard["narrative_length_policy"]["quality_targets"]
        == "soft_quality_findings"
    )
    assert standard["runtime_state_model"]["historical_terminal_truth_is_immutable"]


def test_reassessment_does_not_invent_a_complete_product() -> None:
    result = _load(REASSESSMENT)
    decision = result["stage_decision"]
    cumulative = result["cumulative_capability_evidence"]

    assert (
        result["latest_exact_live_reclassification"]["new_classification"]
        == "L3_analytical_quality_or_L4_delivery_finding_not_L1_hard_integrity_failure"
    )
    assert (
        result["historical_complete_product_reassessment"]["new_classification"]
        == "L1_hard_integrity_failure"
    )
    assert not cumulative["current_owner_grade_complete_nine_artifact_live_product_exists"]
    assert decision["S3_T09"] == "blocked"
    assert decision["S3_T10"] == "not_authorized"
    assert not decision["conditional_pass_granted"]


def test_concept_and_detail_publish_the_same_layered_contract() -> None:
    concept = CONCEPT.read_text(encoding="utf-8")
    detail = DETAIL.read_text(encoding="utf-8")
    contract_ref = "fin01.agent_acceptance.layered_hard_integrity_and_quality:v1"

    assert contract_ref in concept
    assert contract_ref in detail
    for marker in (
        "L1 硬完整性",
        "L2 可恢复协议",
        "L3 分析质量",
        "L4 用户适配与交付",
    ):
        assert marker in concept
        assert marker in detail
