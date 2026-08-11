from __future__ import annotations

from copy import deepcopy
import hashlib
import inspect
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s2_numeric_presentation_renderer import (  # noqa: E402
    render_protected_numeric_presentations,
)
from sec_agent.s2_selected_evidence_numeric_natural_node_canary import (  # noqa: E402
    SelectedEvidenceNumericNaturalNodeCanaryError,
    compile_canary_material,
    load_canary_policy,
    validate_canary_output,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "policy_v1_0.json"
)
RESULT_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s2_provider_neutral_numeric_presentation_equivalence_"
    "local_renderer_zero_call_result_v1_0.json"
)


@pytest.fixture(scope="module")
def material():
    policy = load_canary_policy(POLICY_PATH, repo_root=ROOT)
    return compile_canary_material(policy=policy, repo_root=ROOT)


def _captured_shape_output() -> dict:
    return {
        "schema_version": (
            "fin_ia_0_1_3_s2_demand_authenticity_numeric_view_atom_"
            "canary_output_v1_0"
        ),
        "case_key": "DELL",
        "node_id": "dell_demand_authenticity_numeric_view_atom_canary_v1",
        "judgment": "supported_with_limits",
        "support_atom": {
            "text": (
                "Dell Q1 FY27 AI orders of $24.4 billion, AI server revenue "
                "of $16.1 billion, record AI backlog of $51.3 billion, and "
                "customer count surpassing 5,000 indicate strong current "
                "demand. Demand exceeds supply with memory as the primary "
                "constraint."
            ),
            "epistemic_state": "fact_supported",
            "evidence_refs": ["E022"],
            "numeric_refs": [
                "NUM:DELL:AI_ORDERS:66F359E8F5E4",
                "NUM:DELL:AI_SERVER_REVENUE:C4947C75D942",
                "NUM:DELL:AI_BACKLOG:A82BF565C064",
                "NUM:DELL:CUSTOMER_COUNT:8C7F5A41CBF9",
            ],
        },
        "counterevidence_atom": {
            "text": (
                "HPE order digestion is only a competitor read-through, and "
                "Dell's supply-securing commentary introduces pull-forward "
                "risk rather than quantified direct proof."
            ),
            "epistemic_state": "bounded_inference",
            "evidence_refs": ["E018", "E023"],
            "numeric_refs": [],
        },
        "boundary_atom": {
            "text": (
                "Orders and backlog are not unconditional revenue; cannot "
                "infer linear conversion or cancellation rates, and no margin "
                "bridge is disclosed."
            ),
            "epistemic_state": "cannot_infer",
            "evidence_refs": ["E022", "E018", "E023"],
            "numeric_refs": [],
        },
        "used_numeric_refs": [
            "NUM:DELL:AI_ORDERS:66F359E8F5E4",
            "NUM:DELL:AI_SERVER_REVENUE:C4947C75D942",
            "NUM:DELL:AI_BACKLOG:A82BF565C064",
            "NUM:DELL:CUSTOMER_COUNT:8C7F5A41CBF9",
        ],
    }


def _render_receipts(validation: dict) -> list[dict]:
    support = validation["local_rendering_receipts"][0]["support_atom"]
    return list(support["receipts"])


def test_old_exact_surface_contract_remains_failed(material) -> None:
    with pytest.raises(SelectedEvidenceNumericNaturalNodeCanaryError) as exc:
        validate_canary_output(
            output=_captured_shape_output(),
            material=material,
        )
    assert exc.value.code == "natural_node_canary_required_presentations_missing"


def test_local_renderer_accepts_relation_equivalence_and_emits_canonical_surface(
    material,
) -> None:
    validation = validate_canary_output(
        output=_captured_shape_output(),
        material=material,
        presentation_mode="local_protected_renderer",
    )

    assert validation["status"] == "pass"
    assert validation["presentation_mode"] == "local_protected_renderer"
    assert validation["raw_delivery_digest"] != validation["rendered_delivery_digest"]
    count = next(
        row for row in _render_receipts(validation) if "CUSTOMER_COUNT" in row["numeric_ref"]
    )
    assert count == {
        "numeric_ref": "NUM:DELL:CUSTOMER_COUNT:8C7F5A41CBF9",
        "observed_surface": "customer count surpassing 5,000",
        "canonical_surface": "customer count surpassed 5,000",
        "equivalence_basis": "bounded_relation_equivalence",
        "relation": "greater_than",
    }


@pytest.mark.parametrize(
    ("old", "new", "expected_code"),
    [
        (
            "customer count surpassing 5,000",
            "customer count not surpassing 5,000",
            "numeric_presentation_renderer_negated_relation",
        ),
        (
            "customer count surpassing 5,000",
            "customer count below 5,000",
            "numeric_presentation_renderer_relation_direction_mismatch",
        ),
        (
            "customer count surpassing 5,000",
            "at most 5,000 customers",
            "numeric_presentation_renderer_relation_direction_mismatch",
        ),
        (
            "Dell Q1 FY27",
            "HPE Q1 FY27",
            "numeric_presentation_renderer_foreign_entity_mismatch",
        ),
        (
            "Dell Q1 FY27",
            "Dell Q1 FY26",
            "numeric_presentation_renderer_period_mismatch",
        ),
        (
            "$16.1 billion",
            "$16.1 million",
            "numeric_presentation_renderer_required_numeric_surface_missing",
        ),
        (
            "customer count surpassing 5,000",
            "customer count surpassing 4,999",
            "numeric_presentation_renderer_required_count_claim_missing",
        ),
    ],
)
def test_negation_direction_entity_period_unit_and_value_mutations_fail_closed(
    material, old: str, new: str, expected_code: str
) -> None:
    output = deepcopy(_captured_shape_output())
    output["support_atom"]["text"] = output["support_atom"]["text"].replace(
        old, new
    )
    with pytest.raises(SelectedEvidenceNumericNaturalNodeCanaryError) as exc:
        validate_canary_output(
            output=output,
            material=material,
            presentation_mode="local_protected_renderer",
        )
    assert exc.value.code == expected_code


def test_renderer_is_provider_neutral_and_does_not_rewrite_free_prose(material) -> None:
    output = _captured_shape_output()
    rendered = render_protected_numeric_presentations(
        atom_text=output["support_atom"]["text"],
        numeric_refs=output["support_atom"]["numeric_refs"],
        numeric_facts=material["compiled_input"]["numeric_facts"],
        case_key=output["case_key"],
        evidence=material["compiled_input"]["evidence"],
    )

    assert rendered["provider_specific_rule_used"] is False
    assert rendered["free_prose_changed"] is False
    assert rendered["non_protected_prose_changed"] is False
    assert "customer count surpassed 5,000" in rendered["rendered_text"]
    assert "Demand exceeds supply with memory as the primary constraint." in (
        rendered["rendered_text"]
    )
    source = inspect.getsource(render_protected_numeric_presentations).casefold()
    assert "deepseek" not in source


def test_additional_unbound_inflected_count_still_fails_local_numeric_gate(
    material,
) -> None:
    output = deepcopy(_captured_shape_output())
    output["support_atom"]["text"] += (
        " A separate customer count surpassing 4,999 is not authorized."
    )
    with pytest.raises(SelectedEvidenceNumericNaturalNodeCanaryError) as exc:
        validate_canary_output(
            output=output,
            material=material,
            presentation_mode="local_protected_renderer",
        )
    assert exc.value.code == "natural_node_canary_local_numeric_gate_failed"


def test_public_result_is_canonical_source_bound_and_claims_no_live_promotion() -> None:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    body = {key: value for key, value in result.items() if key != "result_digest"}

    assert result["result_digest"] == canonical_digest(body)
    for ref_key, hash_key in (
        ("renderer_ref", "renderer_sha256"),
        ("canary_validator_ref", "canary_validator_sha256"),
        ("shared_numeric_guard_ref", "shared_numeric_guard_sha256"),
    ):
        path = ROOT / result["implementation"][ref_key]
        normalized = path.read_text(encoding="utf-8").encode("utf-8")
        assert hashlib.sha256(normalized).hexdigest() == (
            result["implementation"][hash_key]
        )
    assert result["predecessor_terminal"]["formal_status"] == "failed"
    assert result["predecessor_terminal"]["rerun_or_relabel"] is False
    assert result["immutable_capture_replay"]["provider_calls"] == 0
    assert result["immutable_capture_replay"]["model_calls"] == 0
    assert result["stage_acceptance"]["old_formal_canary_contract_pass"] is False
    assert result["stage_acceptance"]["successor_clean_proof"] is False
    assert result["stage_acceptance"]["S2_closeout"] is False
    assert result["stage_acceptance"]["release"] is False
