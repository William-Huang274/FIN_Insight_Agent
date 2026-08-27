from __future__ import annotations

from copy import deepcopy
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from retrieval.dell_report_internal_chain_ceiling_r12 import (
    ATTEMPT_ID,
    ATTEMPT_RECEIPT_REF,
    AUTHORITY,
    EXECUTION_CONTRACT,
    EXPECTED_BOUND_INPUT_IDS,
    EXPECTED_IMPLEMENTATION_PATHS,
    MIN_FREE_BYTES_BEFORE_ATTEMPT,
    POLICY_REF,
    POLICY_SCHEMA_VERSION,
    PRIVATE_REF,
    PRIVATE_RESULT_SCHEMA_VERSION,
    PROGRAM_ID,
    PUBLIC_REF,
    RAW_EXECUTION_CAPTURE_REF,
    SEMANTIC_CONTRACT,
    TERMINAL_FAILURE_RECEIPT_REF,
    DellReportInternalChainCeilingR12Error,
    assess_dell_report_internal_chain_r12_packages,
    build_route_contract_identity_registry_r12,
    build_dell_report_internal_chain_ceiling_r12_public_projection,
    validate_dell_report_internal_chain_r12_saved_raw_execution,
    validate_dell_report_internal_chain_ceiling_r12_policy,
)
from retrieval.dell_report_predicate_frames_r12 import ASP_TARGET, classify_package
from retrieval.query_plan import canonical_digest
from scripts.data_retrieval import (
    run_dell_report_internal_chain_ceiling_r12 as r12_runner,
)


ROOT = Path(__file__).resolve().parents[1]


def _redigest(value: dict) -> dict:
    body = dict(value)
    body.pop("result_digest", None)
    value["result_digest"] = canonical_digest(body)
    return value


def _redigest_named(value: dict, field: str) -> dict:
    body = dict(value)
    body.pop(field, None)
    value[field] = canonical_digest(body)
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _metadata() -> dict:
    return {
        "ticker": "DELL",
        "source_type": "PUBLIC_WEB",
        "source_tier": "named_counterparty_or_standards_primary",
        "publication_date": "2025-05-27",
    }


def _source(source_id: str, text: str) -> dict:
    return {
        "evidence_id": source_id,
        "text": text,
        "metadata": {},
        **_metadata(),
    }


def _object(object_id: str, source_id: str, text: str) -> dict:
    return {
        "compiled_object_id": object_id,
        "candidate_not_evidence": True,
        "evidence_promoted": False,
        "numeric_authority": False,
        "lineage_source_record_ids": [source_id],
        "model_text": text,
        "base_object_view": {
            "source_record_id": source_id,
            "focus_binding": {"mode": "parent_context"},
            **_metadata(),
        },
    }


def test_r12_assessment_emits_lossless_complete_frame_transformation() -> None:
    source_id = "SOURCE::DELL::ASP::R12"
    source_rows = [
        _source(
            source_id,
            "Context. Dell offered PowerEdge hardware for USD 15 in FY2026.",
        )
    ]
    object_rows = [
        _object(
            "OBJECT::DELL::ASP::R12",
            source_id,
            "Dell offered PowerEdge hardware for USD 15 in FY2026.",
        )
    ]
    result = assess_dell_report_internal_chain_r12_packages(
        target_id=ASP_TARGET,
        source_rows=source_rows,
        object_rows=object_rows,
    )
    assert result["coverage_gaps"] == []
    assert result["frame_transformation_binding_count"] == 1
    binding = result["frame_transformation_bindings"][0]
    assert binding["binding_accepted"] is True
    assert binding["semantic_signature_equal"] is True
    # The corpus compiler may select an exact sentence slice. Representation
    # equality is valid here; the dedicated transformation tests separately
    # prove that semantically equal bounded windows can differ in representation.
    assert binding["representation_digest_equal"] is True
    assert binding["loss_flags"] == []
    assert binding["addition_flags"] == []
    assert binding["proof_rebind_flags"] == []


def test_r12_deferred_irrelevant_boundaries_are_realized_for_selected_package() -> None:
    source_id = "SOURCE::DELL::ASP::NO_FRAME::R12"
    text = (
        "Dell PowerEdge AI server demand remained strong in FY2026, "
        "while HPE systems rose."
    )
    public_assessment = classify_package(
        target_id=ASP_TARGET,
        text=text,
        metadata=_metadata(),
    )
    assert public_assessment["predicate_frames"] == []
    assert public_assessment["frame_boundary_decisions"]
    result = assess_dell_report_internal_chain_r12_packages(
        target_id=ASP_TARGET,
        source_rows=[_source(source_id, text)],
        object_rows=[_object("OBJECT::DELL::ASP::NO_FRAME::R12", source_id, text)],
    )
    source_package = result["source_packages"][0]
    compiled_package = result["compiled_packages"][0]
    assert source_package["frame_boundary_decisions"] == public_assessment[
        "frame_boundary_decisions"
    ]
    assert compiled_package["frame_boundary_decisions"] == public_assessment[
        "frame_boundary_decisions"
    ]


def _r12_projection_fixture() -> dict:
    path = ROOT / (
        "data/workbench_private/fin_0_1_3_s1_dell_03b_internal_chain_"
        "candidate_ceiling/dell-rsq-03b-internal-chain-r11/full_result.json"
    )
    private = json.loads(path.read_text(encoding="utf-8"))
    private["schema_version"] = PRIVATE_RESULT_SCHEMA_VERSION
    private["attempt_id"] = ATTEMPT_ID
    private["status"] = (
        "dell_03B_R12_route_clause_governing_price_connector_proof_ceiling_executed"
    )
    private["authority"] = {
        "03B_R12_execution_consumed": True,
        "03C_external_capture_authorized": False,
        "03D_4B_embedding_authorized": False,
        "03D_reranker_authorized": False,
        "candidate_decision_authorized": False,
        "evidence_promotion_authorized": False,
        "proved_information_boundary_authorized": False,
        "G3_pass": False,
        "S1_pass": False,
        "S2_pass": False,
        "S3_pass": False,
        "report_quality_pass": False,
        "product_acceptance": False,
        "publication": False,
        "release_ready": False,
    }
    bindings = {
        binding_id: {
            "ref": f"configs/test/{binding_id}.json",
            "sha256": "a" * 64,
            "result_digest": "b" * 64,
        }
        for binding_id in EXPECTED_BOUND_INPUT_IDS | {"R12_policy"}
    }
    bindings["attempt_consumption_receipt"] = {
        "ref": "data/test/attempt.json",
        "sha256": "a" * 64,
        "result_digest": "b" * 64,
    }
    bindings["git_identity"] = {
        "branch": r12_runner.BRANCH,
        "head": "a" * 40,
        "head_tree": "b" * 40,
        "upstream": "a" * 40,
        "implementation_commit": "c" * 40,
        "implementation_tree": "d" * 40,
        "authority_commit_changed_paths": [POLICY_REF],
        "clean": True,
        "upstream_equal": True,
        "authority_parent_exact": True,
    }
    bindings["disk_capacity_preflight"] = {
        "free_bytes": MIN_FREE_BYTES_BEFORE_ATTEMPT,
        "minimum_free_bytes": MIN_FREE_BYTES_BEFORE_ATTEMPT,
    }
    private["input_bindings"] = bindings
    residual_program = json.loads(
        (
            ROOT
            / "configs/retrieval/fin_ia_0_1_3_s1_dell_report_"
            "residual_source_ladder_program_v1_1.json"
        ).read_text(encoding="utf-8")
    )
    route_registry = build_route_contract_identity_registry_r12(
        residual_program
    )
    for target in private["target_results"]:
        target_id = target["target_id"]
        route_identity = route_registry[target_id]
        external_required = target["downstream_disposition"][
            "03C_external_route_required_for_complete_bounded_target"
        ]
        active_ids = (
            route_identity["mandatory_external_route_contract_ids"]
            if external_required
            else []
        )
        target["downstream_disposition"][
            "mandatory_external_route_contract_ids_if_authorized"
        ] = active_ids
        target["private_route_contract_identity"] = {
            **route_identity,
            "active_external_route_required": external_required,
            "active_mandatory_external_route_contract_ids": active_ids,
        }
        target["private_frame_transformation_bindings"] = []
        target["private_frame_transformation_summary"] = {
            "binding_count": 0,
            "accepted_binding_count": 0,
            "binding_set_digest": canonical_digest([]),
            "unbound_source_family_count": 0,
            "unbound_source_family_ids": [],
            "unbound_complete_source_family_count": 0,
            "unbound_complete_source_family_ids": [],
            "unbound_partial_source_family_count": 0,
            "compiled_complete_without_source_antecedent_count": 0,
            "compiled_complete_without_source_antecedent_ids": [],
            "failed_binding_count": 0,
            "failed_complete_binding_count": 0,
            "proof_rebind_failure_count": 0,
            "source_governing_nominal_head_partial_count": 0,
            "compiled_governing_nominal_head_partial_count": 0,
            "source_clause_ownership_decision_counts": {},
            "compiled_clause_ownership_decision_counts": {},
            "complete_transformation_coverage_pass": True
        }
    private["policy_digest"] = "d" * 64
    return _redigest(private)


def test_r12_public_projection_drops_transformation_private_rows() -> None:
    private = _r12_projection_fixture()
    public = build_dell_report_internal_chain_ceiling_r12_public_projection(
        private_result=private,
        private_ref=PRIVATE_REF,
        private_sha256="c" * 64,
    )
    assert public["attempt_id"] == ATTEMPT_ID
    assert "raw_execution_receipt" not in public
    assert all(
        "private_frame_transformation_bindings" not in row
        for row in public["target_results"]
    )
    assert all(
        len(row["route_contract_identity_digest"]) == 64
        and len(row["active_mandatory_external_route_id_set_digest"]) == 64
        for row in public["target_results"]
    )


def test_r12_public_projection_rejects_resigned_transformation_summary_drift() -> None:
    private = _r12_projection_fixture()
    private["target_results"][0]["private_frame_transformation_summary"][
        "binding_count"
    ] = 1
    _redigest(private)

    with pytest.raises(
        DellReportInternalChainCeilingR12Error,
        match="private_transformation_summary_invalid",
    ):
        build_dell_report_internal_chain_ceiling_r12_public_projection(
            private_result=private,
            private_ref=PRIVATE_REF,
            private_sha256="c" * 64,
        )


def _residual_route_program() -> dict:
    return json.loads(
        (
            ROOT
            / "configs/retrieval/fin_ia_0_1_3_s1_dell_report_"
            "residual_source_ladder_program_v1_1.json"
        ).read_text(encoding="utf-8")
    )


def test_r12_route_registry_preserves_exact_mandatory_external_identity() -> None:
    registry = build_route_contract_identity_registry_r12(
        _residual_route_program()
    )
    expected_families = {
        "DELL-RSQ-03A-TARGET-ASP": {
            "official_issuer_regulator",
            "product_procurement_deployment",
        },
        "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE": {
            "named_supplier",
            "official_issuer_regulator",
        },
        "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD": {
            "industry_primary",
            "named_supplier",
            "official_issuer_regulator",
        },
        "DELL-RSQ-03A-TARGET-HBM-SUPPLY": {
            "industry_primary",
            "named_supplier",
            "official_issuer_regulator",
        },
        "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH": {
            "named_supplier",
            "official_issuer_regulator",
        },
        "DELL-RSQ-03A-TARGET-UNITS": {
            "industry_primary",
            "official_issuer_regulator",
        },
    }
    assert set(registry) == set(expected_families)
    for target_id, expected in expected_families.items():
        actual_ids = registry[target_id][
            "mandatory_external_route_contract_ids"
        ]
        assert {
            route_id.rsplit("::", 1)[-1] for route_id in actual_ids
        } == expected
        assert all(route_id.startswith(f"{target_id}::") for route_id in actual_ids)


def test_r12_route_registry_rejects_rehashed_semantic_route_drift() -> None:
    program = _residual_route_program()
    asp = next(
        row
        for row in program["route_targets"]
        if row["target_id"] == ASP_TARGET
    )
    for contract in asp["route_contracts"]:
        if contract["route_family_id"] != "local_data_object_index_sql":
            contract["mandatory_for_target"] = False
            _redigest_named(contract, "route_contract_digest")
    _redigest_named(asp, "target_program_digest")
    _redigest_named(program, "program_digest")
    with pytest.raises(
        DellReportInternalChainCeilingR12Error,
        match="residual_route_program_identity_invalid",
    ):
        build_route_contract_identity_registry_r12(program)


def test_r12_route_identity_survives_false_then_true_active_state() -> None:
    private = _r12_projection_fixture()
    asp = next(
        row for row in private["target_results"] if row["target_id"] == ASP_TARGET
    )
    route_identity = asp["private_route_contract_identity"]
    exact_ids = list(route_identity["mandatory_external_route_contract_ids"])

    asp["downstream_disposition"][
        "03C_external_route_required_for_complete_bounded_target"
    ] = False
    asp["downstream_disposition"][
        "mandatory_external_route_contract_ids_if_authorized"
    ] = []
    route_identity["active_external_route_required"] = False
    route_identity["active_mandatory_external_route_contract_ids"] = []
    _redigest(private)
    first = build_dell_report_internal_chain_ceiling_r12_public_projection(
        private_result=private,
        private_ref=PRIVATE_REF,
        private_sha256="c" * 64,
    )
    first_asp = next(
        row for row in first["target_results"] if row["target_id"] == ASP_TARGET
    )
    assert first_asp["downstream_disposition"][
        "mandatory_external_route_contract_ids_if_authorized"
    ] == []

    asp["downstream_disposition"][
        "03C_external_route_required_for_complete_bounded_target"
    ] = True
    asp["downstream_disposition"][
        "mandatory_external_route_contract_ids_if_authorized"
    ] = exact_ids
    route_identity["active_external_route_required"] = True
    route_identity["active_mandatory_external_route_contract_ids"] = exact_ids
    _redigest(private)
    second = build_dell_report_internal_chain_ceiling_r12_public_projection(
        private_result=private,
        private_ref=PRIVATE_REF,
        private_sha256="d" * 64,
    )
    second_asp = next(
        row for row in second["target_results"] if row["target_id"] == ASP_TARGET
    )
    assert second_asp["downstream_disposition"][
        "mandatory_external_route_contract_ids_if_authorized"
    ] == exact_ids


def test_r12_public_projection_rejects_true_external_state_with_empty_route_ids() -> None:
    private = _r12_projection_fixture()
    asp = next(
        row for row in private["target_results"] if row["target_id"] == ASP_TARGET
    )
    asp["downstream_disposition"][
        "mandatory_external_route_contract_ids_if_authorized"
    ] = []
    asp["private_route_contract_identity"][
        "active_mandatory_external_route_contract_ids"
    ] = []
    _redigest(private)
    with pytest.raises(
        DellReportInternalChainCeilingR12Error,
        match="private_route_identity_invalid",
    ):
        build_dell_report_internal_chain_ceiling_r12_public_projection(
            private_result=private,
            private_ref=PRIVATE_REF,
            private_sha256="c" * 64,
        )


def _binding(path: Path) -> tuple[dict, dict]:
    value = json.loads(path.read_text(encoding="utf-8"))
    row = {
        "ref": path.relative_to(ROOT).as_posix(),
        "sha256": _sha(path),
    }
    if value.get("result_digest"):
        row["result_digest"] = value["result_digest"]
    return row, value


def _r12_policy_fixture() -> tuple[dict, dict[str, dict]]:
    paths = {
        "R11_policy": ROOT / (
            "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_"
            "candidate_ceiling_policy_v2_0.json"
        ),
        "R11_public": ROOT / (
            "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_"
            "candidate_ceiling_result_v2_0.json"
        ),
        "R11_private": ROOT / (
            "data/workbench_private/fin_0_1_3_s1_dell_03b_internal_chain_"
            "candidate_ceiling/dell-rsq-03b-internal-chain-r11/full_result.json"
        ),
        "R11_attempt_receipt": ROOT / (
            "data/workbench_private/fin_0_1_3_s1_dell_03b_internal_chain_"
            "candidate_ceiling/dell-rsq-03b-internal-chain-r11/"
            "attempt_consumption_receipt.json"
        ),
        "R11_raw_execution_capture": ROOT / (
            "data/workbench_private/fin_0_1_3_s1_dell_03b_internal_chain_"
            "candidate_ceiling/dell-rsq-03b-internal-chain-r11/"
            "raw_execution_capture.json"
        ),
        "R11_fresh_audit": ROOT / (
            "configs/audits/fin_ia_0_1_3_commit_cd1d41b3_dell_03b_"
            "r11_fresh_dual_audit_fail_v1_0.json"
        ),
        "R11_fixed_audit_manifest": ROOT / (
            "configs/audits/fin_ia_0_1_3_commit_cd1d41b3_dell_03b_"
            "r11_fixed_dual_audit_manifest_v1_0.json"
        ),
        "residual_route_program": ROOT / (
            "configs/retrieval/fin_ia_0_1_3_s1_dell_report_"
            "residual_source_ladder_program_v1_1.json"
        ),
    }
    r11_private = json.loads(paths["R11_private"].read_text(encoding="utf-8"))
    inherited = r11_private["input_bindings"]
    for binding_id in (
        "R17_report_audit",
        "R17_report_bundle_carry_forward",
        "execution_program",
        "runtime_registry",
        "runtime_binding_receipt",
    ):
        paths[binding_id] = ROOT / inherited[binding_id]["ref"]
    for binding_id in ("source_records", "compiled_objects"):
        paths[binding_id] = ROOT / inherited[binding_id]["ref"]

    bound_inputs: dict[str, dict] = {}
    values: dict[str, dict] = {}
    for binding_id, path in paths.items():
        if path.suffix == ".jsonl":
            bound_inputs[binding_id] = {
                "ref": path.relative_to(ROOT).as_posix(),
                "sha256": _sha(path),
            }
            values[binding_id] = dict(bound_inputs[binding_id])
        else:
            bound_inputs[binding_id], values[binding_id] = _binding(path)
    assert set(bound_inputs) == EXPECTED_BOUND_INPUT_IDS
    policy = {
        "schema_version": POLICY_SCHEMA_VERSION,
        "status": (
            "same_stage_R12_execution_authorized_after_fresh_R11_audit_failure"
        ),
        "program_id": PROGRAM_ID,
        "attempt_id": ATTEMPT_ID,
        "recorded_at": "2026-08-27",
        "decision_target": "One bounded R12 exact attempt.",
        "owner_basis": "Owner-approved same-stage R12 implementation.",
        "execution_contract": dict(EXECUTION_CONTRACT),
        "semantic_contract": dict(SEMANTIC_CONTRACT),
        "output_contract": {
            "policy_ref": POLICY_REF,
            "private_result_ref": PRIVATE_REF,
            "public_result_ref": PUBLIC_REF,
            "attempt_consumption_receipt_ref": ATTEMPT_RECEIPT_REF,
            "raw_execution_capture_ref": RAW_EXECUTION_CAPTURE_REF,
            "terminal_failure_receipt_ref": TERMINAL_FAILURE_RECEIPT_REF,
            "alternate_output_paths_authorized": False,
            "private_public_same_path_authorized": False,
            "exclusive_create_required": True,
            "atomic_pair_with_rollback_required": True,
            "same_attempt_retry_authorized": False,
            "minimum_free_bytes_before_attempt": MIN_FREE_BYTES_BEFORE_ATTEMPT,
        },
        "bound_inputs": bound_inputs,
        "execution_identity": {
            "branch": r12_runner.BRANCH,
            "implementation_commit": "a" * 40,
            "implementation_tree": "b" * 40,
            "authority_commit_changed_paths": [POLICY_REF],
            "authority_commit_parent_must_equal_implementation_commit": True,
            "HEAD_must_equal_upstream": True,
        },
        "implementation_bindings": [
            {"path": path, "sha256": "a" * 64}
            for path in sorted(EXPECTED_IMPLEMENTATION_PATHS)
        ],
        "TokenBudgetBasis": {
            "node_purpose": "Bounded R12 qualification.",
            "input_scale": "Five requests and six targets.",
            "required_outputs": "Private/public immutable result.",
            "schema_burden": "Typed frames and transformation mappings.",
            "materiality_quality_risk": "False complete financial evidence.",
            "comparable_run_evidence": "R11 and zero-call R12 preview.",
            "reasoning_profile": "Deterministic compiler with zero new embedding.",
            "stop_and_truncation": "Fail closed before authority drift.",
        },
        "authority": dict(AUTHORITY),
        "known_boundary": "No downstream authority.",
    }
    _redigest(policy)
    return policy, values


def test_r12_policy_binds_r11_failure_and_r17_14_file_carry_forward() -> None:
    policy, values = _r12_policy_fixture()
    predecessor = validate_dell_report_internal_chain_ceiling_r12_policy(
        policy,
        **values,
    )
    assert predecessor["attempt_id"] == "dell-rsq-03b-internal-chain-r11"


@pytest.mark.parametrize(
    "binding_id",
    [
        "source_records",
        "compiled_objects",
        "execution_program",
        "runtime_registry",
        "runtime_binding_receipt",
    ],
)
def test_r12_policy_rejects_candidate_generation_binding_drift(
    binding_id: str,
) -> None:
    policy, values = _r12_policy_fixture()
    policy["bound_inputs"][binding_id]["sha256"] = "e" * 64
    _redigest(policy)

    with pytest.raises(
        DellReportInternalChainCeilingR12Error,
        match=f"candidate_generation_binding_drift:{binding_id}",
    ):
        validate_dell_report_internal_chain_ceiling_r12_policy(
            policy,
            **values,
        )


def test_r12_saved_raw_validation_projects_zero_new_embedding_batch() -> None:
    _, values = _r12_policy_fixture()
    private = values["R11_private"]
    raw = values["R11_raw_execution_capture"]
    execution = raw["raw_execution"]
    expected_request_ids = {
        request_id
        for target in private["target_results"]
        for request_id in target["request_ids"]
    }
    assert execution["summary"]["local_embedding_inference_batches"] == 1
    validated = validate_dell_report_internal_chain_r12_saved_raw_execution(
        execution,
        expected_request_ids=expected_request_ids,
    )
    assert validated["summary"]["local_embedding_inference_batches"] == 0
    assert all(
        validated["summary"][field] == 0
        for field in r12_runner.ZERO_EXECUTION_FIELDS
    )


def test_r12_formal_runner_has_no_fresh_retrieval_or_model_execution_path() -> None:
    source = inspect.getsource(r12_runner.run_authorized_formal)
    assert "ResearchRetrievalService" not in source
    assert "execute_current_runtime_requests" not in source
    assert "_validated_immutable_r11_execution" in source
    assert "_validated_r12_raw_reuse_capture" in source
    assert "R11_raw_execution_capture" in source


def test_r12_policy_rejects_changed_r17_bundle_population() -> None:
    policy, values = _r12_policy_fixture()
    drift = deepcopy(values)
    drift["R17_report_bundle_carry_forward"] = deepcopy(
        values["R17_report_bundle_carry_forward"]
    )
    drift["R17_report_bundle_carry_forward"][
        "R17_report_quality_bundle"
    ].pop("R17_report_bytes")
    _redigest(drift["R17_report_bundle_carry_forward"])
    # Rebind the deliberately changed in-memory artifact so this test reaches
    # the 14-file population invariant instead of stopping at digest drift.
    policy["bound_inputs"]["R17_report_bundle_carry_forward"][
        "result_digest"
    ] = drift["R17_report_bundle_carry_forward"]["result_digest"]
    _redigest(policy)
    with pytest.raises(
        DellReportInternalChainCeilingR12Error,
        match="R17_14_file_carry_forward_invalid",
    ):
        validate_dell_report_internal_chain_ceiling_r12_policy(
            policy,
            **drift,
        )


def test_r12_runner_requires_explicit_mode() -> None:
    with pytest.raises(SystemExit) as exc_info:
        r12_runner.main([])
    assert exc_info.value.code == 2


def test_r12_formal_fails_before_receipt_when_policy_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    private = tmp_path / "private" / "full_result.json"
    monkeypatch.setattr(r12_runner, "DEFAULT_PRIVATE", private)
    monkeypatch.setattr(r12_runner, "DEFAULT_PUBLIC", tmp_path / "public.json")
    monkeypatch.setattr(
        r12_runner,
        "ATTEMPT_RECEIPT",
        private.with_name("attempt_consumption_receipt.json"),
    )
    monkeypatch.setattr(
        r12_runner,
        "RAW_EXECUTION_CAPTURE",
        private.with_name("raw_execution_capture.json"),
    )
    monkeypatch.setattr(
        r12_runner,
        "TERMINAL_FAILURE_RECEIPT",
        private.with_name("terminal_failure_receipt.json"),
    )
    monkeypatch.setattr(r12_runner, "POLICY", tmp_path / "missing.json")
    monkeypatch.setattr(
        r12_runner,
        "_require_output_disk_capacity",
        lambda: {"free_bytes": 1, "minimum_free_bytes": 1},
    )
    with pytest.raises(FileNotFoundError, match="canonical_policy_missing"):
        r12_runner.run_authorized_formal()
    assert not r12_runner.ATTEMPT_RECEIPT.exists()


def test_r12_raw_capture_precedes_redacted_terminal_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    attempt_dir = tmp_path / "attempt"
    attempt_dir.mkdir()
    raw_path = attempt_dir / "raw_execution_capture.json"
    terminal_path = attempt_dir / "terminal_failure_receipt.json"
    monkeypatch.setattr(r12_runner, "RAW_EXECUTION_CAPTURE", raw_path)
    monkeypatch.setattr(r12_runner, "TERMINAL_FAILURE_RECEIPT", terminal_path)
    _, values = _r12_policy_fixture()
    source_capture = values["R11_raw_execution_capture"]
    r11_private = values["R11_private"]
    source_capture_path = ROOT / (
        "data/workbench_private/fin_0_1_3_s1_dell_03b_internal_chain_"
        "candidate_ceiling/dell-rsq-03b-internal-chain-r11/"
        "raw_execution_capture.json"
    )
    source_capture_ref = source_capture_path.relative_to(ROOT).as_posix()
    source_capture_sha256 = _sha(source_capture_path)
    execution = source_capture["raw_execution"]
    sha = hashlib.sha256(
        r12_runner.base._canonical_json_bytes(execution)
    ).hexdigest()
    r12_runner._write_raw_execution_capture(
        policy={"result_digest": "a" * 64},
        execution=execution,
        execution_sha256=sha,
        source_capture_ref=source_capture_ref,
        source_capture_sha256=source_capture_sha256,
        source_capture_result_digest=source_capture["result_digest"],
        recorded_at="2026-08-27T00:00:00+00:00",
    )
    captured = json.loads(raw_path.read_text(encoding="utf-8"))
    assert captured["R12_new_call_counters"] == r12_runner.R12_NEW_CALL_COUNTERS
    assert captured["reuse_reason"] == r12_runner.R12_RAW_REUSE_REASON
    proof = captured["candidate_generation_equivalence_proof"]
    assert proof["frozen_request_count"] == 5
    assert proof["frozen_unique_candidate_union_count"] == 338
    assert proof["frozen_final_review_count"] == 80
    assert proof["upstream_local_embedding_inference_batches"] == 1
    assert proof["R12_new_local_embedding_inference_batches"] == 0
    assert captured["source_R11_raw_execution_capture"]["attempt_id"] == (
        "dell-rsq-03b-internal-chain-r11"
    )
    validated_execution, validated_sha = (
        r12_runner._validated_r12_raw_reuse_capture(
            capture=captured,
            policy={"result_digest": "a" * 64},
            r11_private=r11_private,
            r11_raw_capture=source_capture,
            r11_raw_ref=source_capture_ref,
            r11_raw_sha256=source_capture_sha256,
        )
    )
    assert validated_execution == execution
    assert validated_sha == sha
    receipt = r12_runner._write_terminal_failure_receipt(
        policy={"result_digest": "a" * 64},
        stage="private_result_compilation",
        exception_type="RuntimeError",
        recorded_at="2026-08-27T00:00:01+00:00",
    )
    assert receipt["exception_message_persisted"] is False
    assert receipt["raw_execution_capture"]["sha256"] == _sha(raw_path)


def test_r12_attempt_receipt_is_exclusive_exact_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    receipt = tmp_path / "attempt" / "attempt_consumption_receipt.json"
    monkeypatch.setattr(r12_runner, "ATTEMPT_RECEIPT", receipt)
    kwargs = {
        "policy": {"result_digest": "a" * 64},
        "git_receipt": {
            "head": "b" * 40,
            "head_tree": "c" * 40,
            "implementation_commit": "d" * 40,
            "implementation_tree": "e" * 40,
        },
        "recorded_at": "2026-08-27T00:00:00+00:00",
    }
    first = r12_runner._write_attempt_consumption_receipt(**kwargs)
    assert json.loads(receipt.read_text(encoding="utf-8")) == first
    with pytest.raises(FileExistsError, match="attempt_already_consumed"):
        r12_runner._write_attempt_consumption_receipt(**kwargs)


def test_r12_atomic_pair_rolls_back_second_publish_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    private = tmp_path / "private" / "full_result.json"
    public = tmp_path / "public" / "result.json"
    monkeypatch.setattr(r12_runner, "DEFAULT_PRIVATE", private)
    monkeypatch.setattr(r12_runner, "DEFAULT_PUBLIC", public)
    real_link = r12_runner.os.link
    calls = 0

    def fail_second(source: Path, destination: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("synthetic_second_publish_failure")
        real_link(source, destination)

    monkeypatch.setattr(r12_runner.os, "link", fail_second)
    with pytest.raises(OSError, match="synthetic_second_publish_failure"):
        r12_runner._publish_atomic_pair(
            private_bytes=b"private",
            public_bytes=b"public",
        )
    assert not private.exists()
    assert not public.exists()
