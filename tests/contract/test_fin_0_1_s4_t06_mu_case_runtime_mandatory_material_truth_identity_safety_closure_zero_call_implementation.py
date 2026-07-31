from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    CaseDeliveryIdentityPolicy,
    CaseNumericAuthorityPolicy,
    S4_CASE_DELIVERY_IDENTITY_CURRENT_CASE_AWARE_POLICY_REF,
    S4_CASE_DELIVERY_IDENTITY_POLICY_REF,
    S4_CASE_NUMERIC_AUTHORITY_POLICY_REF,
    S4_CASE_RUNTIME_MANDATORY_MATERIAL_TRUTH_IDENTITY_SAFETY_REF,
    research_lead_transport_contract,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_ARTIFACT_TYPES,
    BOUNDED_AGENT_JUDGMENT_ARTIFACT_TYPE,
    BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE,
    BOUNDED_AGENT_NUMERIC_ARTIFACT_TYPE,
    BOUNDED_AGENT_REPORT_ARTIFACT_TYPE,
    BOUNDED_AGENT_TRACE_ARTIFACT_TYPE,
    BOUNDED_AGENT_VERIFICATION_ARTIFACT_TYPE,
    BOUNDED_AGENT_WORKPAPER_ARTIFACT_TYPE,
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V7_REF,
    S3ThreeCellBoundedAgentAdmission,
    S3ThreeCellBoundedAgentExecutor,
    build_s3_three_cell_bounded_agent_executor_for_admission,
    compile_profile_aware_artifact_lineage_contract,
    compile_s4_case_runtime_mandatory_safety_admission,
)
from test_fin_0_1_s4_t05_case_numeric_authority_and_delivery_identity_zero_call_implementation import (
    _NumericIdentitySafeFake,
    _case_fixture_input_and_admission,
    _sanitize_provider_narratives,
    _shared_local_id_specialists,
)
from test_fin_0_1_s4_t06_mu_research_lead_fact_presence_local_materialization_zero_call_implementation import (
    _MuSourceGroundedV7FullFakeProvider,
    _mu_input_and_admission,
)


MU_R2_ADMISSION = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t06_mu_research_lead_fact_presence_local_"
    "materialization_fresh_exact_admission_r2.json"
)
IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_case_runtime_mandatory_"
    "material_truth_identity_safety_closure_minimum_zero_call_"
    "implementation_v1_0.json"
)
PROGRAM_BACKLOG = (
    ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
S4_BACKLOG = (
    ROOT
    / "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)


class _NumericIdentitySafeMuV7Fake(
    _MuSourceGroundedV7FullFakeProvider
):
    def __call__(self, **kwargs: Any) -> Mapping[str, Any]:
        response = dict(super().__call__(**kwargs))
        output = json.loads(str(response["content"]))
        response["content"] = json.dumps(
            _sanitize_provider_narratives(output),
            ensure_ascii=False,
            sort_keys=True,
        )
        return response


def _mu_r2_admission() -> S3ThreeCellBoundedAgentAdmission:
    return S3ThreeCellBoundedAgentAdmission.model_validate(
        json.loads(MU_R2_ADMISSION.read_text(encoding="utf-8"))
    )


def _run_bound_mu(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Any, Any, dict[str, dict[str, Any]]]:
    input_pack, _ = _mu_input_and_admission()
    admission = compile_s4_case_runtime_mandatory_safety_admission(
        _mu_r2_admission(),
        updates={
            "admission_id": "fixture-s4-t06-mu-r2-safety-closure",
            "execution_mode": "zero_call_mu_r2_safety_closure",
        },
    )
    _, specialists = _shared_local_id_specialists()
    fake = _NumericIdentitySafeMuV7Fake(specialists)
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv(
        "DEEPSEEK_API_KEY", "fixture-not-a-real-secret"
    )
    result = build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=fake,
    ).execute(
        input_pack,
        admission,
        run_identity={
            "research_run_id": "fixture-s4-t06-mu-r2-safety-closure",
            "attempt_id": "fixture-s4-t06-mu-r2-safety-closure",
        },
    )
    artifacts = {
        row.artifact_type: row.payload for row in result.artifacts
    }
    return input_pack, result, artifacts


def test_consumed_mu_r2_without_safety_pair_fails_before_provider() -> None:
    input_pack, _ = _mu_input_and_admission()
    calls: list[dict[str, Any]] = []

    def must_not_call(**kwargs: Any) -> Mapping[str, Any]:
        calls.append(dict(kwargs))
        raise AssertionError("provider_must_not_be_called")

    executor = build_s3_three_cell_bounded_agent_executor_for_admission(
        _mu_r2_admission(),
        chat_completion_fn=must_not_call,
    )
    with pytest.raises(
        ValueError,
        match=(
            "s4_case_runtime_mandatory_material_truth_and_"
            "identity_safety_profile_required"
        ),
    ):
        executor.execute(
            input_pack,
            _mu_r2_admission(),
            run_identity={"research_run_id": "fixture-pre-provider"},
        )
    assert calls == []


def test_lead_v7_composes_safety_without_inheriting_v6_gap_atoms() -> None:
    compiled = compile_s4_case_runtime_mandatory_safety_admission(
        _mu_r2_admission()
    )
    compiled.assert_profile_admissible()
    assert compiled.case_numeric_authority_policy_ref == (
        S4_CASE_NUMERIC_AUTHORITY_POLICY_REF
    )
    assert compiled.case_delivery_identity_policy_ref == (
        S4_CASE_DELIVERY_IDENTITY_CURRENT_CASE_AWARE_POLICY_REF
    )
    capability = research_lead_transport_contract(
        S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V7_REF
    )
    assert capability.case_material_truth_identity_safety_composable
    assert capability.gap_atom_deterministic_projection is False
    assert (
        capability.conflict_fact_presence_materialization_policy_ref
        is not None
    )


def test_mu_s4_path_reaches_twelve_calls_nine_final_artifacts_with_safety_markers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, result, artifacts = _run_bound_mu(monkeypatch)
    assert len(result.provider_output_captures) == 12
    assert len(result.artifacts) == 9
    assert set(artifacts) == set(BOUNDED_AGENT_ARTIFACT_TYPES)
    manifest = artifacts[BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE]
    assert manifest["case_runtime_safety_profile_ref"] == (
        S4_CASE_RUNTIME_MANDATORY_MATERIAL_TRUTH_IDENTITY_SAFETY_REF
    )
    assert manifest["case_ticker"] == "MU"
    assert manifest["case_numeric_authority_policy_ref"] == (
        S4_CASE_NUMERIC_AUTHORITY_POLICY_REF
    )
    assert manifest["case_delivery_identity_policy_ref"] == (
        S4_CASE_DELIVERY_IDENTITY_CURRENT_CASE_AWARE_POLICY_REF
    )
    assert len(
        artifacts[BOUNDED_AGENT_NUMERIC_ARTIFACT_TYPE][
            "case_numeric_authority_projections"
        ]
    ) == 3
    assert artifacts[BOUNDED_AGENT_REPORT_ARTIFACT_TYPE][
        "report"
    ]["title_zh_cn"] == "MU 三单元内部研究备忘录"
    assert artifacts[BOUNDED_AGENT_WORKPAPER_ARTIFACT_TYPE][
        "entity_label"
    ] == "MU"
    assert artifacts[BOUNDED_AGENT_VERIFICATION_ARTIFACT_TYPE][
        "entity_label"
    ] == "MU"
    assert all(
        payload["s4_case_runtime"]["case_ticker"] == "MU"
        for payload in artifacts.values()
    )


def test_final_mu_artifact_envelope_rejects_projection_numeric_and_identity_mutations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_pack, _, original = _run_bound_mu(monkeypatch)
    contracts = deepcopy(
        original[BOUNDED_AGENT_NUMERIC_ARTIFACT_TYPE][
            "case_numeric_authority_projections"
        ]
    )
    policies = {
        policy.program_cell_id: policy
        for policy in (
            CaseNumericAuthorityPolicy.from_prompt_contract(row)
            for row in contracts
        )
    }
    specialists = deepcopy(
        original[BOUNDED_AGENT_JUDGMENT_ARTIFACT_TYPE][
            "specialist_outputs"
        ]
    )
    identity_projection = CaseDeliveryIdentityPolicy.compile(
        company="MU",
        s4_case_runtime=input_pack.s4_case_runtime,
        contract_ref=(
            S4_CASE_DELIVERY_IDENTITY_CURRENT_CASE_AWARE_POLICY_REF
        ),
    ).projection()
    lineage_contract = compile_profile_aware_artifact_lineage_contract(
        input_pack.lineage,
        s4_case_runtime=input_pack.s4_case_runtime,
    )
    lineage_projection = {
        "manifest": {
            "lineage_contract_ref": lineage_contract.contract_ref,
            "lineage_family": lineage_contract.lineage_family,
            "lineage_digest": lineage_contract.lineage_digest,
        },
        "trace_lineage": input_pack.lineage,
    }

    mutations: list[
        tuple[str, Any, str]
    ] = []

    missing_marker = deepcopy(original)
    missing_marker[BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE].pop(
        "case_runtime_safety_profile_ref"
    )
    mutations.append(
        (
            "manifest_marker",
            missing_marker,
            "manifest_safety_binding_mismatch",
        )
    )

    numeric_projection = deepcopy(original)
    next(
        row
        for contract in numeric_projection[
            BOUNDED_AGENT_NUMERIC_ARTIFACT_TYPE
        ]["case_numeric_authority_projections"]
        for row in contract["rows"]
    )["exact_value"] = "999"
    mutations.append(
        (
            "numeric_projection",
            numeric_projection,
            "numeric_projection_payload_mismatch",
        )
    )

    wrong_title = deepcopy(original)
    wrong_title[BOUNDED_AGENT_REPORT_ARTIFACT_TYPE]["report"][
        "title_zh_cn"
    ] = "NVDA 三单元内部研究备忘录"
    mutations.append(
        (
            "title",
            wrong_title,
            "delivery_identity_surface_mismatch",
        )
    )

    report_numeric = deepcopy(original)
    rendering = report_numeric[BOUNDED_AGENT_REPORT_ARTIFACT_TYPE][
        "report"
    ]["sections"][0]["claim_renderings"][0]
    rendering["rendered_text_zh_cn"] += " 123"
    mutations.append(
        (
            "report_numeric",
            report_numeric,
            "report_nonlocal_numeric_token",
        )
    )

    wrong_review_label = deepcopy(original)
    wrong_review_label[BOUNDED_AGENT_VERIFICATION_ARTIFACT_TYPE][
        "entity_label"
    ] = "DELL"
    mutations.append(
        (
            "review_label",
            wrong_review_label,
            "delivery_identity_surface_mismatch",
        )
    )

    wrong_manifest_lineage = deepcopy(original)
    wrong_manifest_lineage[BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE][
        "lineage_digest"
    ] = "0" * 64
    mutations.append(
        (
            "manifest_lineage",
            wrong_manifest_lineage,
            "artifact_lineage_projection_mismatch",
        )
    )

    wrong_trace_lineage = deepcopy(original)
    wrong_trace_lineage[BOUNDED_AGENT_TRACE_ARTIFACT_TYPE][
        "lineage"
    ] = {"tampered": True}
    mutations.append(
        (
            "trace_lineage",
            wrong_trace_lineage,
            "artifact_lineage_projection_mismatch",
        )
    )

    for mutation_id, artifacts, expected_subtype in mutations:
        writer = deepcopy(
            artifacts[BOUNDED_AGENT_REPORT_ARTIFACT_TYPE]["report"]
        )
        verifier = deepcopy(
            artifacts[BOUNDED_AGENT_VERIFICATION_ARTIFACT_TYPE][
                "verification"
            ]
        )
        violation = (
            S3ThreeCellBoundedAgentExecutor
            ._first_s4_final_artifact_safety_violation(
                artifact_payloads=artifacts,
                specialists=specialists,
                writer=writer,
                verifier=verifier,
                case_numeric_policies=policies,
                case_numeric_contracts=contracts,
                case_delivery_identity_projection=(
                    identity_projection
                ),
                require_s4_runtime_projection=True,
                artifact_lineage_projection=lineage_projection,
            )
        )
        assert violation is not None, mutation_id
        assert violation.subtype == expected_subtype, mutation_id
        assert violation.telemetry()["acceptance_layer"] == (
            "L1_hard_integrity"
        )


def test_final_numeric_fact_statement_mutation_fails_exact_correspondence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_pack, admission = _case_fixture_input_and_admission("DELL")
    _, specialists = _shared_local_id_specialists()
    fake = _NumericIdentitySafeFake(input_pack, specialists)
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv(
        "DEEPSEEK_API_KEY", "fixture-not-a-real-secret"
    )
    result = build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=fake,
    ).execute(
        input_pack,
        admission,
        run_identity={
            "research_run_id": "fixture-dell-final-envelope-mutation",
            "attempt_id": "fixture-dell-final-envelope-mutation",
        },
    )
    artifacts = {
        row.artifact_type: deepcopy(row.payload)
        for row in result.artifacts
    }
    canonical_specialists = deepcopy(
        artifacts[BOUNDED_AGENT_JUDGMENT_ARTIFACT_TYPE][
            "specialist_outputs"
        ]
    )
    mutated_specialists = deepcopy(canonical_specialists)
    numeric_fact = next(
        fact
        for specialist in mutated_specialists
        for fact in specialist["fact_layer"]
        if fact["support_type"] == "Numeric"
    )
    numeric_fact["statement"] = "DELL wrong numeric statement 999"
    artifacts[BOUNDED_AGENT_JUDGMENT_ARTIFACT_TYPE][
        "specialist_outputs"
    ] = mutated_specialists
    artifacts[BOUNDED_AGENT_WORKPAPER_ARTIFACT_TYPE][
        "cells"
    ] = mutated_specialists
    artifacts[BOUNDED_AGENT_NUMERIC_ARTIFACT_TYPE][
        "agent_numeric_fact_rows"
    ] = [
        dict(fact)
        for specialist in mutated_specialists
        for fact in specialist["fact_layer"]
        if fact["support_type"] == "Numeric"
    ]
    contracts = artifacts[BOUNDED_AGENT_NUMERIC_ARTIFACT_TYPE][
        "case_numeric_authority_projections"
    ]
    policies = {
        policy.program_cell_id: policy
        for policy in (
            CaseNumericAuthorityPolicy.from_prompt_contract(row)
            for row in contracts
        )
    }
    violation = (
        S3ThreeCellBoundedAgentExecutor
        ._first_s4_final_artifact_safety_violation(
            artifact_payloads=artifacts,
            specialists=mutated_specialists,
            writer=artifacts[BOUNDED_AGENT_REPORT_ARTIFACT_TYPE][
                "report"
            ],
            verifier=artifacts[
                BOUNDED_AGENT_VERIFICATION_ARTIFACT_TYPE
            ]["verification"],
            case_numeric_policies=policies,
            case_numeric_contracts=contracts,
            case_delivery_identity_projection=(
                CaseDeliveryIdentityPolicy.compile(
                    company="DELL",
                    s4_case_runtime=input_pack.s4_case_runtime,
                    contract_ref=(
                        S4_CASE_DELIVERY_IDENTITY_POLICY_REF
                    ),
                ).projection()
            ),
            require_s4_runtime_projection=True,
        )
    )
    assert violation is not None
    assert violation.subtype == "canonical_numeric_fact_mismatch"


def test_implementation_record_binds_one_bundle_and_next_fresh_proof() -> None:
    implementation = json.loads(
        IMPLEMENTATION.read_text(encoding="utf-8")
    )
    expected_next = (
        "S4-T06-MU-CASE-RUNTIME-MANDATORY-MATERIAL-TRUTH-AND-IDENTITY-"
        "SAFETY-CLOSURE-FRESH-AGENT-PROOF-DECISION"
    )
    current_disposition = (
        "S4-T06-MU-CURRENT-CASE-AWARE-DELIVERY-IDENTITY-BOUNDARY-"
        "SCOPE-REPLACEMENT-MINIMUM-ZERO-CALL-IMPLEMENTATION"
    )
    current_fresh_proof = (
        "S4-T06-MU-CURRENT-CASE-AWARE-DELIVERY-IDENTITY-BOUNDARY-"
        "FRESH-AGENT-PROOF-DECISION"
    )
    current_post_R4 = (
        "S4-T06-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-"
        "CLASSIFIER-MINIMUM-ZERO-CALL-IMPLEMENTATION"
    )
    current_after_v2 = (
        "S4-T06-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-"
        "CLASSIFIER-FRESH-AGENT-PROOF-DECISION"
    )
    current_after_fresh = (
        "S4-T06-MU-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-"
        "CLASSIFIER-R5-EXACT-LIVE-EXECUTION-AND-SUCCESS-ONLY-PAIRED-ASSESSMENT"
    )
    assert implementation["status"] == (
        "pass_single_zero_call_bundle_fixture_proven_"
        "fresh_agent_proof_pending"
    )
    assert implementation["authority"][
        "implementation_bundles_consumed"
    ] == 1
    assert implementation["authority"][
        "automatic_follow_on_repair_bundles"
    ] == 0
    assert set(implementation["observed_counts"].values()) == {0}
    assert implementation["next_action"] == expected_next
    assert json.loads(
        PROGRAM_BACKLOG.read_text(encoding="utf-8")
    )["next_action"]["item_id"] in {
        expected_next,
        current_disposition,
        current_fresh_proof,
        current_post_R4,
        current_after_v2,
        current_after_fresh,
            "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
            "TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION",
            "S4-T06-MU-WWC-PROVIDER-CANDIDATE-VALIDATION-AND-"
            "DETERMINISTIC-FINAL-SELECTION-MINIMUM-ZERO-CALL-"
            "IMPLEMENTATION",
            "S4-T06-MU-WWC-PROVIDER-CANDIDATE-VALIDATION-AND-"
            "DETERMINISTIC-FINAL-SELECTION-INDEPENDENT-FRESH-AGENT-"
            "PROOF-DECISION",
        }
    assert json.loads(
        S4_BACKLOG.read_text(encoding="utf-8")
    )["current_next_action"] in {
        expected_next,
        current_disposition,
        current_fresh_proof,
        current_post_R4,
        current_after_v2,
        current_after_fresh,
            "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
            "TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION",
            "S4-T06-MU-WWC-PROVIDER-CANDIDATE-VALIDATION-AND-"
            "DETERMINISTIC-FINAL-SELECTION-MINIMUM-ZERO-CALL-"
            "IMPLEMENTATION",
            "S4-T06-MU-WWC-PROVIDER-CANDIDATE-VALIDATION-AND-"
            "DETERMINISTIC-FINAL-SELECTION-INDEPENDENT-FRESH-AGENT-"
            "PROOF-DECISION",
        }
    for relative_path, expected_sha256 in implementation[
        "exact_code_bindings"
    ].items():
        observed = __import__("hashlib").sha256(
            (ROOT / relative_path).read_bytes()
        ).hexdigest()
        if relative_path == str(
            Path(__file__).resolve().relative_to(ROOT)
        ).replace("\\", "/"):
            continue
        if observed != expected_sha256:
            assert relative_path in implementation[
                "historical_exact_binding_supersession"
            ]["allowed_changed_paths"]
