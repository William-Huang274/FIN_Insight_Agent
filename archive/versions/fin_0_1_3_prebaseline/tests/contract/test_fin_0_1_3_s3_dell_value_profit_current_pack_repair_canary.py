from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s3_dell_value_profit_repair_canary import (  # noqa: E402
    S3DellValueProfitRepairCanaryError,
    adjudicate_repair_canary_output,
    compile_repair_canary_material,
    execute_fixture_repair_canary,
    issue_fixture_admission,
    load_repair_canary_policy,
)
from sec_agent.shared_admission_ledger import (  # noqa: E402
    SharedAdmissionConsumptionLedger,
)


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s3_dell_value_profit_current_pack_"
    "repair_canary_policy_v1_0.json"
)


@pytest.fixture(scope="module")
def material() -> dict:
    policy = load_repair_canary_policy(POLICY_PATH, repo_root=ROOT)
    return compile_repair_canary_material(policy=policy, repo_root=ROOT)


def _row(
    cell_id: str,
    *,
    state: str,
    changed: bool,
    support: list[str],
    counter: list[str] | None = None,
    numeric: list[str] | None = None,
    mechanism: str,
    boundary: str,
    wwc: str = "",
) -> dict:
    return {
        "cell_id": cell_id,
        "judgment_state": state,
        "judgment_changed": changed,
        "support_refs": support,
        "counterevidence_refs": counter or [],
        "numeric_refs": numeric or [],
        "mechanism_atom": mechanism,
        "boundary_atom": boundary,
        "wwc_ref": wwc,
    }


def _valid_output() -> dict:
    required_num = "NUM:DELL:OPERATING_MARGIN_TARGET:2894219F450D"
    return {
        "schema_version": (
            "fin_ia_0_1_3_s3_dell_value_profit_current_pack_"
            "repair_canary_output_v1_0"
        ),
        "case_key": "DELL",
        "node_id": "dell_value_profit_current_pack_repair_adjudicator_v1",
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
        "affected_cell_readjudications": [
            _row(
                "bottleneck_counterevidence_and_what_would_change",
                state="supported_with_limits",
                changed=True,
                support=["E021"],
                mechanism=(
                    "Issuer profitability commentary narrows the monitoring question "
                    "to explicit product or segment attribution."
                ),
                boundary=(
                    "The observation does not establish audited product profit, "
                    "gross margin or cash conversion."
                ),
                wwc="DELL_W_AI_MARGIN",
            ),
            _row(
                "cross_chain_price_in_and_expectations",
                state="cannot_infer",
                changed=False,
                support=["E002"],
                mechanism=(
                    "Segment financial context does not establish how the market "
                    "prices the product economics."
                ),
                boundary=(
                    "No valuation or expectations conclusion follows from this "
                    "profitability evidence."
                ),
            ),
            _row(
                "value_and_profit_capture",
                state="supported_with_limits",
                changed=True,
                support=["E021"],
                counter=["E002", "E008"],
                numeric=[required_num],
                mechanism=(
                    "Issuer commentary supports bounded AI server operating "
                    "profitability while mix evidence limits the transmission from "
                    "revenue scale to profit."
                ),
                boundary=(
                    "Segment operating income cannot be substituted for product "
                    "profit, and product gross margin and cash conversion remain open."
                ),
                wwc="DELL_W_AI_MARGIN",
            ),
            _row(
                "writer_admission_boundary",
                state="supported_with_limits",
                changed=True,
                support=["E021", "E002"],
                mechanism=(
                    "The report may state the bounded issuer profitability comparison "
                    "and must keep the segment bridge separate."
                ),
                boundary=(
                    "The report cannot present audited product profit, gross margin, "
                    "cash conversion, valuation or a recommendation."
                ),
                wwc="DELL_W_AI_MARGIN",
            ),
        ],
        "used_numeric_refs": [required_num],
    }


def test_current_pack_compiles_a_small_prose_bounded_repair_request(
    material: dict,
) -> None:
    compiled = material["compiled_input"]
    assert [
        row["evidence_alias"] for row in compiled["current_pack_evidence"]
    ] == ["E002", "E008", "E021", "E023"]
    assert compiled["authoritative_affected_cell_ids"] == [
        "bottleneck_counterevidence_and_what_would_change",
        "cross_chain_price_in_and_expectations",
        "value_and_profit_capture",
        "writer_admission_boundary",
    ]
    assert compiled["raw_source_text_in_model_input"] is False
    serialized = json.dumps(compiled, ensure_ascii=False)
    assert '"source_text"' not in serialized
    request = material["provider_request"]
    assert request["node_type"] == "repair_adjudicator"
    assert request["max_tokens"] == 1800
    assert len(json.dumps(request, ensure_ascii=False)) <= 30000


def test_valid_output_partially_resolves_target_and_projects_exact_successor_state(
    material: dict,
) -> None:
    result = adjudicate_repair_canary_output(
        output=_valid_output(),
        material=material,
        capture_ref="fixture://repair-canary/pass",
        capture_digest="a" * 64,
    )
    validation = result["validation"]
    assert validation["status"] == "pass"
    assert validation["repair_request_status"] == "re_adjudicated"
    assert validation["affected_cell_ids"] == [
        "bottleneck_counterevidence_and_what_would_change",
        "cross_chain_price_in_and_expectations",
        "value_and_profit_capture",
        "writer_admission_boundary",
    ]
    assert validation["local_numeric_projection"] == {
        "numeric_ref": "NUM:DELL:OPERATING_MARGIN_TARGET:2894219F450D",
        "rendered": "mid-single-digit",
        "authority": "local_numeric_presentation_program",
        "model_authored_surface": False,
    }
    successor = result["successor_program"]
    repaired = next(
        row
        for row in successor["repair_requests"]
        if row["gap_id"] == "DELL_GAP_AI_SERVER_PROFIT_ATTRIBUTION"
    )
    assert repaired["status"] == "re_adjudicated"
    assert len(validation["readjudication_receipt_digests"]) == 4


@pytest.mark.parametrize(
    ("mutator", "code"),
    [
        (
            lambda output: output.update(
                accepted_evidence_refs=["E002"]
            ),
            "s3_repair_canary_evidence_or_gap_set_invalid",
        ),
        (
            lambda output: output["evidence_semantics"].update(
                isg_profit_attribution_status="allowed_product_profit_proxy"
            ),
            "s3_repair_canary_evidence_semantics_invalid",
        ),
        (
            lambda output: output["retained_gap_components"].remove(
                "cash_conversion"
            ),
            "s3_repair_canary_evidence_or_gap_set_invalid",
        ),
        (
            lambda output: output["affected_cell_readjudications"].pop(),
            "s3_repair_canary_readjudication_coverage_invalid",
        ),
        (
            lambda output: output["affected_cell_readjudications"][2].update(
                mechanism_atom="Product margin was five percent."
            ),
            "s3_repair_canary_model_numeric_surface_forbidden",
        ),
        (
            lambda output: output["affected_cell_readjudications"][1].update(
                judgment_state="supported_with_limits",
                judgment_changed=True,
                support_refs=["E021"],
            ),
            "s3_repair_canary_price_in_boundary_invalid",
        ),
    ],
)
def test_financial_and_scope_mutations_fail_closed(
    material: dict, mutator, code: str
) -> None:
    output = deepcopy(_valid_output())
    mutator(output)
    with pytest.raises(S3DellValueProfitRepairCanaryError, match=code):
        adjudicate_repair_canary_output(
            output=output,
            material=material,
            capture_ref="fixture://repair-canary/mutation",
            capture_digest="b" * 64,
        )


def test_fixture_execution_is_capture_first_exact_once_and_zero_external_call(
    material: dict, tmp_path: Path
) -> None:
    admission = issue_fixture_admission(
        material=material,
        run_id="s3_repair_canary_fixture_pass",
        attempt_id="attempt_1",
        observed_at="2026-08-11T12:00:00Z",
    )
    ledger = SharedAdmissionConsumptionLedger(tmp_path / "shared.sqlite")
    runtime_root = tmp_path / "attempt"

    def fake_provider(_request: dict) -> dict:
        return {
            "status": "ok",
            "content": json.dumps(_valid_output(), ensure_ascii=False),
            "finish_reason": "stop",
            "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        }

    terminal = execute_fixture_repair_canary(
        admission=admission,
        material=material,
        provider_call=fake_provider,
        runtime_root=runtime_root,
        shared_ledger=ledger,
        observed_at="2026-08-11T12:00:00Z",
    )
    assert terminal["status"] == "completed"
    assert terminal["terminal_code"] == "s3_repair_canary_pass"
    assert terminal["observed_counts"] == {
        "fixture_provider_callbacks": 1,
        "provider_calls": 0,
        "model_calls": 0,
        "source_calls": 0,
        "network_tool_calls": 0,
        "retries": 0,
        "fallbacks": 0,
    }
    assert (runtime_root / "raw_model_only/calls/call_01/capture.json").is_file()
    assert (runtime_root / "validated/successor_program.json").is_file()
    with pytest.raises(Exception):
        execute_fixture_repair_canary(
            admission=admission,
            material=material,
            provider_call=fake_provider,
            runtime_root=tmp_path / "duplicate",
            shared_ledger=ledger,
            observed_at="2026-08-11T12:00:01Z",
        )


def test_invalid_output_is_preserved_as_terminal_failure(
    material: dict, tmp_path: Path
) -> None:
    admission = issue_fixture_admission(
        material=material,
        run_id="s3_repair_canary_fixture_fail",
        attempt_id="attempt_1",
        observed_at="2026-08-11T12:01:00Z",
    )
    ledger = SharedAdmissionConsumptionLedger(tmp_path / "failed.sqlite")
    runtime_root = tmp_path / "failed_attempt"
    invalid = deepcopy(_valid_output())
    invalid["evidence_semantics"]["isg_profit_attribution_status"] = (
        "allowed_product_profit_proxy"
    )
    terminal = execute_fixture_repair_canary(
        admission=admission,
        material=material,
        provider_call=lambda _request: {
            "status": "ok",
            "content": json.dumps(invalid, ensure_ascii=False),
            "finish_reason": "stop",
        },
        runtime_root=runtime_root,
        shared_ledger=ledger,
        observed_at="2026-08-11T12:01:00Z",
    )
    assert terminal["status"] == "failed"
    assert terminal["terminal_phase"] == "contract_validation"
    assert terminal["terminal_code"] == (
        "s3_repair_canary_evidence_semantics_invalid"
    )
    assert terminal["parsed_output_ref"] == "parsed/repair_output.json"
    assert terminal["validated_output_ref"] is None
    assert (runtime_root / "parsed/repair_output.json").is_file()
    assert not (runtime_root / "validated/repair_output.json").exists()
    assert (runtime_root / "raw_model_only/calls/call_01/capture.json").is_file()
    assert terminal["business_artifact_promotion"] is False
