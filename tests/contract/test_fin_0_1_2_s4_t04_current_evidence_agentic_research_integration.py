from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "src"),
    str(ROOT / "tests" / "contract"),
]

from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_ARTIFACT_TYPES,
    S4_T04_CURRENT_EVIDENCE_VERIFIER_MODEL_VIEW_CONTRACT_REF,
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from apps.workbench.backend.application.bounded_agent_contract_policies import (
    estimate_provider_input_tokens,
)
from apps.workbench.backend.application.fin_0_1_2_s4_natural_case_entry import (
    load_current_fin_0_1_2_s4_t01_case_entry,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t04_current_evidence_research import (
    Fin012S4T04EvidenceError,
    compile_current_t04_execution_envelope,
    compile_current_nvda_agent_input,
    prepare_current_nvda_agent_execution,
    validate_current_nvda_evidence_pack,
)
from apps.workbench.backend.application.fin_0_1_2_s3_t04_product_surface import (
    S3T04ProductSurfaceError,
    materialize_verified_product_surface,
    validate_verified_product_surface,
)
from apps.workbench.backend.application.research_runtime import (
    prepare_s3_three_cell_bounded_agent_exact_input,
)
from scripts.releases.run_fin_ia_0_1_2_s3_t03_nvda_supervised_exact_live import (
    _principal,
    rehydrate_exact_input_services,
)
from sec_agent.canonical_runtime.models import canonical_digest
from test_fin_0_1_2_s3_t02_production_runtime_integration import (
    _CurrentS3ProductionFake,
)


PACK = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_2_s4_t04_nvda_current_evidence_pack_v1_0.json"
)
ADMISSION_TEMPLATE = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_2_s3_t03_nvda_replacement_fresh_exact_admission_r2.json"
)
CAPACITY_PROOF = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_2_s4_t04_compiled_node_request_capacity_proof_v1_0.json"
)


def _pack() -> dict:
    return json.loads(PACK.read_text(encoding="utf-8"))


def _baseline_prepared():
    with tempfile.TemporaryDirectory(prefix="fin012-s4-t04-current-input-") as temporary:
        local, evidence, case, accepted = rehydrate_exact_input_services(Path(temporary))
        return prepare_s3_three_cell_bounded_agent_exact_input(
            local,
            evidence,
            str(case["case_id"]),
            _principal(),
            decision_surface_contract_ref=str(accepted["contract_version_id"]),
            execution_identity="fin012-s4-t04-current-evidence-zero-call-proof",
        )


def _current_input():
    baseline = _baseline_prepared()
    return compile_current_nvda_agent_input(
        baseline.input_pack,
        _pack(),
        t01_entry=load_current_fin_0_1_2_s4_t01_case_entry("NVDA"),
    )


def test_fresh_execution_identity_and_envelope_are_exactly_bound() -> None:
    prepared = prepare_current_nvda_agent_execution(
        _baseline_prepared(),
        _pack(),
        t01_entry=load_current_fin_0_1_2_s4_t01_case_entry("NVDA"),
        principal=_principal(),
        execution_identity="fin012-s4-t04-current-evidence-zero-call-proof",
    )
    envelope = compile_current_t04_execution_envelope(
        prepared,
        _pack(),
        admission_ref="fixture:T04-admission",
    )
    assert prepared.input_digest == _current_input().input_digest
    assert prepared.work_unit_id.startswith("wu_p02_5_")
    assert envelope["fresh_t03"]["attempt_id"] == prepared.attempt_id
    assert envelope["fresh_t03"]["research_run_id"] == prepared.research_run_id
    assert envelope["current_evidence"]["evidence_numeric_gap_counts"] == [15, 3, 3]
    assert envelope["hard_budget"]["provider_calls"] == 9
    assert envelope["hard_budget"]["maximum_input_tokens"] == 108000
    assert envelope["input_capacity_contract"][
        "cost_derived_absolute_maximum_input_tokens"
    ] == 117931
    assert envelope["observed_counts"]["model_calls"] == 0


def test_capacity_proof_is_content_addressed_and_has_real_headroom() -> None:
    proof = json.loads(CAPACITY_PROOF.read_text(encoding="utf-8"))
    assert proof["proof_digest"] == canonical_digest(
        {key: value for key, value in proof.items() if key != "proof_digest"}
    )
    projection = proof["compiled_projection"]
    assert sum(projection["per_interaction_estimated_input_tokens"]) == (
        projection["aggregate_estimated_input_tokens"]
    )
    assert (
        proof["maximum_input_tokens"]
        - projection["aggregate_estimated_input_tokens"]
        == projection["hard_limit_headroom_tokens"]
    )
    assert proof["maximum_input_tokens"] < (
        proof["cost_derived_absolute_maximum_input_tokens"]
    )


def test_current_pack_is_exact_T03_partition_with_typed_gaps() -> None:
    pack = validate_current_nvda_evidence_pack(_pack())
    assert pack["evidence_pack_digest"] == (
        "fdc1a10010f0d47ba7be5b420fc5cac860c3044d6690696463865ecce4b7bf65"
    )
    assert [len(pack["evidence_rows"]), len(pack["numeric_rows"])] == [15, 3]
    assert len(pack["typed_gaps"]) == 3
    assert pack["t03_terminal_digest"] == (
        "7ec970b6c2f10983852c9cd52357499baccb08f50a00262de64d8f74a6f6f156"
    )
    text = json.dumps(pack, ensure_ascii=False).lower()
    assert all(token not in text for token in ("fixture://", "p03_fixture", "dell", "micron"))


@pytest.mark.parametrize("mutation", ("cross_case", "row_digest", "writer", "future"))
def test_pack_mutations_fail_closed(mutation: str) -> None:
    changed = deepcopy(_pack())
    if mutation == "cross_case":
        changed["evidence_rows"][0]["entity_ref"] = "DELL"
    elif mutation == "row_digest":
        changed["evidence_rows"][0]["statement"] += " mutation"
    elif mutation == "writer":
        changed["numeric_rows"][0]["writer_citable"] = True
    else:
        changed["evidence_rows"][0]["published_at"] = "2027-01-01"
    changed["evidence_pack_digest"] = canonical_digest(
        {key: value for key, value in changed.items() if key != "evidence_pack_digest"}
    )
    with pytest.raises(Fin012S4T04EvidenceError):
        validate_current_nvda_evidence_pack(changed)


def test_current_input_replaces_fixture_surface_and_binds_current_lineage() -> None:
    current = _current_input()
    payload = current.model_dump(mode="json")
    text = json.dumps(payload, ensure_ascii=False).lower()
    assert current.query.startswith("评估 NVIDIA AI 基础设施需求")
    assert current.input_digest == (
        "1c1da27001ea081e156a456f8806a52ec702c8669b1f6b7169d0ed5f2d16159b"
    )
    assert current.verifier_contract["input_contract_ref"] == (
        S4_T04_CURRENT_EVIDENCE_VERIFIER_MODEL_VIEW_CONTRACT_REF
    )
    assert all(token not in text for token in ("fixture://", "p03_fixture", "metadata_fixture_compiled", "execute the fin"))
    assert payload["lineage"]["T03_evidence_route_plan"]["digest"] == (
        _pack()["t03_terminal_digest"]
    )
    assert [
        len(row["authority_refs"]["accepted_evidence_refs"])
        for row in payload["cell_inputs"]
    ] == [6, 3, 6]
    value_cell = next(
        row for row in payload["cell_inputs"]
        if row["program_cell_id"] == "value_and_profit_capture"
    )
    assert len(value_cell["authority_refs"]["numeric_refs"]) == 5
    assert all(
        row["source_snapshot_digest"]
        for row in value_cell["numeric_input"]["selected_financial_rows"]
    )
    assert "exact_fact_fixture" not in text
    assert all(not row["graph_context_input"]["graph_edges"] for row in payload["cell_inputs"])


def test_current_input_full_fake_reaches_six_nodes_nine_calls_nine_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current = _current_input()
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        json.loads(ADMISSION_TEMPLATE.read_text(encoding="utf-8"))
    ).model_copy(
        update={
            "admission_id": "fin012-s4-t04-current-evidence-zero-call-proof",
            "execution_mode": "zero_call_current_evidence_agentic_research_integration",
            "case_id": current.case_id,
            "case_version": current.case_version,
            "as_of": current.as_of,
            "input_digest": current.input_digest,
        }
    )
    admission.assert_profile_admissible()
    fake = _CurrentS3ProductionFake(safe_lead=True)
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")
    result = build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=fake,
    ).execute(
        current,
        admission,
        run_identity={
            "research_run_id": "fin012-s4-t04-current-evidence-zero-call-proof",
            "attempt_id": "fin012-s4-t04-current-evidence-zero-call-proof",
        },
    )
    assert len(fake.calls) == 9
    assert len(result.provider_output_captures) == 9
    assert len(result.artifacts) == 9
    assert {row.artifact_type for row in result.artifacts} == set(
        BOUNDED_AGENT_ARTIFACT_TYPES
    )
    artifact_text = json.dumps(
        [row.model_dump(mode="json") for row in result.artifacts],
        ensure_ascii=False,
    )
    assert _pack()["evidence_pack_digest"] in artifact_text
    assert "fixture://" not in artifact_text

    verifier_request = fake.calls[-1]["request"]
    verifier_input = verifier_request["analysis_input"]
    assert verifier_input["model_view_contract_ref"] == (
        S4_T04_CURRENT_EVIDENCE_VERIFIER_MODEL_VIEW_CONTRACT_REF
    )
    assert len(verifier_input["claim_evidence_rendering_rows"]) == 3
    assert all(
        row["claim"]["statement"]
        and row["writer_rendering"]["rendered_text_zh_cn"]
        and row["what_would_change"]
        for row in verifier_input["claim_evidence_rendering_rows"]
    )
    assert "specialist_claim_cards" not in verifier_input
    assert "scoped_identity_surface" not in verifier_input
    assert "case_numeric_authority_contracts" not in verifier_input
    assert "case_delivery_identity_projection" not in verifier_input
    assert len(verifier_request["case_numeric_authority_contracts"]) == 3

    projected_by_call = [
        estimate_provider_input_tokens(
            str(row["kwargs"]["messages"][0]["content"])
            + str(row["kwargs"]["messages"][1]["content"])
        )
        for row in fake.calls
    ]
    assert len(projected_by_call) == 9
    assert sum(projected_by_call) < 108000
    assert projected_by_call[-1] < 20000

    execution_result = {
        "status": "success",
        "business_promotable": True,
        "artifacts": [row.model_dump(mode="json") for row in result.artifacts],
    }
    surface = materialize_verified_product_surface(
        execution_result=execution_result,
        input_pack=current.model_dump(mode="json"),
    )
    validate_verified_product_surface(surface)
    preview_text = json.dumps(
        surface["final_delivery_preview"], ensure_ascii=False
    )
    assert surface["status"] == "delivery_and_fixture_qualification_pass"
    assert surface["owner_acceptance_eligible"] is True
    assert all(
        token not in preview_text
        for token in ("__company_total__", "FY2025-FY")
    )
    assert "USD 130497000000 USD" not in preview_text
    assert surface["final_delivery_verification"][
        "final_delivery_preview_digest"
    ] == surface["final_delivery_preview"]["final_delivery_preview_digest"]

    unlocalized = deepcopy(execution_result)
    report = next(
        row["payload"]["report"]
        for row in unlocalized["artifacts"]
        if row["artifact_type"] == "bounded_agent_report"
    )
    report["limitations_zh_cn"] = ["An unknown English limitation remains."]
    with pytest.raises(
        S3T04ProductSurfaceError,
        match="s3_t04_delivery_limitation_localization_missing",
    ):
        materialize_verified_product_surface(
            execution_result=unlocalized,
            input_pack=current.model_dump(mode="json"),
        )

    unauthorized_task = deepcopy(execution_result)
    judgment = next(
        row["payload"]
        for row in unauthorized_task["artifacts"]
        if row["artifact_type"] == "bounded_agent_judgment"
    )
    judgment["specialist_outputs"][0]["what_would_change"][0][
        "authority_refs"
    ] = ["unknown:authority"]
    with pytest.raises(
        S3T04ProductSurfaceError,
        match="s4_t04_current_WWC_delivery_binding_incomplete",
    ):
        materialize_verified_product_surface(
            execution_result=unauthorized_task,
            input_pack=current.model_dump(mode="json"),
        )
