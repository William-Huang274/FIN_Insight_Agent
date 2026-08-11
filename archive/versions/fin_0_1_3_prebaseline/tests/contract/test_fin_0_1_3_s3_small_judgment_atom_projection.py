from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s3_small_judgment_atom_projection import (  # noqa: E402
    S3SmallJudgmentAtomProjectionError,
    audit_failed_legacy_output,
    compile_portfolio_shape_receipts,
    compile_small_judgment_material,
    load_small_judgment_projection_policy,
    normalize_model_atom,
    project_small_judgment_output,
)


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s3_small_judgment_atom_projection_policy_v1_0.json"
)
IMPLEMENTATION_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s3_small_judgment_atom_projection_minimum_zero_call_"
    "implementation_v1_0.json"
)


def _valid_output() -> dict:
    return {
        "schema_version": "fin_ia_0_1_3_s3_small_judgment_atom_output_v1_0",
        "case_key": "DELL",
        "node_id": "dell_value_profit_small_judgment_atom_v1",
        "repair_request_id": "evidence_request_0eb73a1c4b81a05d96b7",
        "observation_outcome": "accepted",
        "repair_resolution": "accepted_partial_resolution",
        "accepted_evidence_refs": ["E021"],
        "boundary_evidence_refs": ["E002", "E008", "E023"],
        "evidence_semantics": {
            "e021_evidence_role": "issuer_direct_source",
            "operating_profitability_status": (
                "issuer_management_observed_in_line_with_target"
            ),
            "isg_profit_attribution_status": "forbidden_substitution",
            "gross_margin_status": "typed_gap",
            "cash_conversion_status": "typed_gap",
            "audited_product_profit_bridge_status": "typed_gap",
        },
        "retained_gap_components": [
            "audited_product_profit_bridge",
            "cash_conversion",
            "gross_margin",
        ],
        "used_numeric_refs": [
            "NUM:DELL:OPERATING_MARGIN_TARGET:2894219F450D"
        ],
        "profitability_direction": (
            "management_target_consistent_product_profit_unproven"
        ),
        "attribution_boundary": "segment_profit_not_product_profit",
        "mechanism_atom": (
            "Issuer commentary supports bounded operating profitability while "
            "mix evidence limits transmission to product profit."
        ),
        "boundary_atom": (
            "Segment income cannot replace product profit; margin and cash "
            "conversion remain open."
        ),
    }


@pytest.fixture(scope="module")
def basis() -> tuple[dict, dict]:
    policy = load_small_judgment_projection_policy(POLICY_PATH, repo_root=ROOT)
    material = compile_small_judgment_material(policy=policy, repo_root=ROOT)
    return policy, material


def test_implementation_record_is_canonical_and_source_bound() -> None:
    implementation = json.loads(IMPLEMENTATION_PATH.read_text(encoding="utf-8"))
    from sec_agent.canonical_runtime.models import canonical_digest

    body = {
        key: value for key, value in implementation.items() if key != "result_digest"
    }
    assert implementation["result_digest"] == canonical_digest(body)
    for ref, expected in implementation["implementation_bindings"].items():
        actual = hashlib.sha256(
            (ROOT / ref).read_text(encoding="utf-8").encode("utf-8")
        ).hexdigest()
        if ref == (
            "tests/contract/"
            "test_fin_0_1_3_s3_small_judgment_atom_projection.py"
        ):
            continue
        assert actual == expected
    assert implementation["scope"]["model_calls"] == 0
    assert implementation["stage_acceptance"]["successor_natural_canary"] is False


def test_compiler_removes_values_and_cell_state_from_model_surface(
    basis: tuple[dict, dict],
) -> None:
    policy, material = basis
    compiled = material["compiled_input"]
    serialized = json.dumps(compiled, ensure_ascii=False)
    assert compiled["raw_source_text_in_model_input"] is False
    assert compiled["authoritative_numeric_values_in_model_input"] is False
    assert "authoritative_value" not in serialized
    assert "allowed_presentations" not in serialized
    contract = compiled["output_contract"]
    assert "affected_cell_readjudications" not in contract["top_level_fields"]
    assert "judgment_state" not in contract["top_level_fields"]
    assert material["compiled_request_characters"] <= policy["request_budget"][
        "maximum_compiled_request_characters"
    ]


def test_small_output_projects_exact_cells_state_refs_wwc_and_numeric_locally(
    basis: tuple[dict, dict],
) -> None:
    _policy, material = basis
    result = project_small_judgment_output(
        output=_valid_output(),
        material=material,
        capture_ref="fixture://small-atom/pass",
        capture_digest="a" * 64,
    )
    assert result["status"] == "pass"
    rows = {row["cell_id"]: row for row in result["deterministic_cell_rows"]}
    assert rows["value_and_profit_capture"]["judgment_state"] == (
        "supported_with_limits"
    )
    assert rows["value_and_profit_capture"]["judgment_changed"] is True
    assert rows["cross_chain_price_in_and_expectations"] == {
        "cell_id": "cross_chain_price_in_and_expectations",
        "judgment_state": "cannot_infer",
        "judgment_changed": False,
        "support_refs": ["E002"],
        "counterevidence_refs": [],
        "numeric_refs": [],
        "mechanism": (
            "Operating evidence does not establish market expectations or valuation."
        ),
        "boundary": "Price-in, valuation and recommendation remain unproven.",
        "wwc_ref": "",
    }
    assert result["local_numeric_projection"] == {
        "numeric_ref": "NUM:DELL:OPERATING_MARGIN_TARGET:2894219F450D",
        "rendered": "mid-single-digit",
        "authority": "local_numeric_presentation_program",
        "model_authored_surface": False,
    }
    assert len(result["readjudication_receipt_digests"]) == 4


def test_alias_tokens_are_classified_separately_and_removed_without_weakening_numeric_gate(
) -> None:
    normalized = normalize_model_atom(
        "E021 supports the bounded direction; E002 preserves the boundary.",
        maximum_characters=420,
    )
    assert normalized["removed_alias_tokens"] == ["E021", "E002"]
    assert normalized["normalized_text"] == (
        "The cited Evidence supports the bounded direction; the cited Evidence "
        "preserves the boundary."
    )
    with pytest.raises(
        S3SmallJudgmentAtomProjectionError,
        match="s3_small_atom_financial_numeric_surface_forbidden",
    ):
        normalize_model_atom(
            "Profitability reached a mid-single-digit band.",
            maximum_characters=420,
        )
    with pytest.raises(
        S3SmallJudgmentAtomProjectionError,
        match="s3_small_atom_financial_numeric_surface_forbidden",
    ):
        normalize_model_atom("Margin improved by five percent.", maximum_characters=420)


@pytest.mark.parametrize(
    ("mutator", "code"),
    [
        (
            lambda output: output.update(judgment_state="supported"),
            "s3_small_atom_output_fields_invalid",
        ),
        (
            lambda output: output.update(case_key="MU"),
            "s3_small_atom_output_identity_invalid",
        ),
        (
            lambda output: output.update(accepted_evidence_refs=["E002"]),
            "s3_small_atom_ref_or_gap_set_invalid",
        ),
        (
            lambda output: output["evidence_semantics"].update(
                isg_profit_attribution_status="allowed_product_profit_proxy"
            ),
            "s3_small_atom_evidence_semantics_invalid",
        ),
        (
            lambda output: output.update(
                profitability_direction="cannot_infer"
            ),
            "s3_small_atom_financial_boundary_invalid",
        ),
        (
            lambda output: output.update(
                mechanism_atom="Profitability reached a mid-single-digit band."
            ),
            "s3_small_atom_financial_numeric_surface_forbidden",
        ),
    ],
)
def test_contract_and_financial_mutations_fail_closed(
    basis: tuple[dict, dict], mutator, code: str
) -> None:
    _policy, material = basis
    output = deepcopy(_valid_output())
    mutator(output)
    with pytest.raises(S3SmallJudgmentAtomProjectionError, match=code):
        project_small_judgment_output(
            output=output,
            material=material,
            capture_ref="fixture://small-atom/mutation",
            capture_digest="b" * 64,
        )


def test_failed_legacy_shape_remains_diagnostic_and_not_promotable() -> None:
    legacy = {
        "accepted_evidence_refs": ["E021"],
        "used_numeric_refs": [
            "NUM:DELL:OPERATING_MARGIN_TARGET:2894219F450D"
        ],
        "affected_cell_readjudications": [
            {
                "cell_id": "value_and_profit_capture",
                "judgment_changed": False,
                "mechanism_atom": "E021 supports the target comparison.",
                "boundary_atom": "E002 preserves the product boundary.",
            },
            {
                "cell_id": "cross_chain_price_in_and_expectations",
                "judgment_state": "mixed",
                "judgment_changed": True,
                "mechanism_atom": "E023 suggests discipline.",
                "boundary_atom": "Valuation evidence is absent.",
            },
        ],
    }
    audit = audit_failed_legacy_output(legacy)
    assert audit["accepted_evidence_refs_exact"] is True
    assert audit["required_numeric_ref_selected"] is True
    assert audit["target_changed_flag_valid"] is False
    assert audit["price_in_boundary_valid"] is False
    assert audit["atom_alias_token_count"] == 3
    assert audit["failed_output_promotable"] is False


def test_portfolio_shapes_are_provider_neutral_and_case_isolated(
    basis: tuple[dict, dict],
) -> None:
    policy, _material = basis
    receipts = compile_portfolio_shape_receipts(policy)
    assert [row["case_key"] for row in receipts] == ["DELL", "MU", "NVDA"]
    assert len({row["shape_digest"] for row in receipts}) == 3
    for row in receipts:
        assert "judgment_state" in row["local_owned_fields"]
        assert "profitability_direction" in row["model_owned_fields"]
        assert row["accepted_ref"].startswith("E")
        assert row["numeric_ref"].startswith(f"NUM:{row['case_key']}:")
