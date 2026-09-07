from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable, Mapping, Sequence

from . import dell_report_internal_chain_ceiling_r3 as r3
from . import dell_report_internal_chain_ceiling_r4 as r4
from . import dell_report_internal_chain_ceiling_r7 as r7
from . import dell_report_internal_chain_ceiling_r8 as r8
from . import dell_report_internal_chain_ceiling_r11 as r11
from .dell_report_frame_transformation_r12 import (
    FrameTransformationBinding,
    FrameTransformationBindingR12Error,
    build_frame_transformation_binding_r12,
    build_missing_compiled_frame_binding_r12,
    transformation_binding_digest_r12,
    validate_frame_transformation_binding_record_r12,
)
from .dell_report_predicate_frames_r12 import (
    TARGET_IDS,
    PredicateFrame,
    classify_package as _classify_predicate_frame_r12,
    classify_package_with_frames as _classify_with_frames_r12,
    extract_predicate_frames,
    frame_boundary_decisions,
)
from .dell_report_public_validation_r8 import validate_public_scalar_tree_r8
from .query_plan import canonical_digest


POLICY_SCHEMA_VERSION = "fin_ia_dell_report_internal_chain_ceiling_policy_v2_1"
PRIVATE_RESULT_SCHEMA_VERSION = (
    "fin_ia_dell_report_internal_chain_candidate_ceiling_private_result_v2_1"
)
PUBLIC_RESULT_SCHEMA_VERSION = (
    "fin_ia_dell_report_internal_chain_candidate_ceiling_result_v2_1"
)
ATTEMPT_ID = "dell-rsq-03b-internal-chain-r12"
PROGRAM_ID = "FIN-0.1.3-S1-DELL-RSQ-03B-R12"
BRANCH = r11.BRANCH
POLICY_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_policy_v2_1.json"
)
PUBLIC_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_result_v2_1.json"
)
PRIVATE_REF = (
    "data/workbench_private/"
    "fin_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling/"
    f"{ATTEMPT_ID}/full_result.json"
)
ATTEMPT_RECEIPT_REF = (
    "data/workbench_private/"
    "fin_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling/"
    f"{ATTEMPT_ID}/attempt_consumption_receipt.json"
)
RAW_EXECUTION_CAPTURE_REF = (
    "data/workbench_private/"
    "fin_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling/"
    f"{ATTEMPT_ID}/raw_execution_capture.json"
)
TERMINAL_FAILURE_RECEIPT_REF = (
    "data/workbench_private/"
    "fin_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling/"
    f"{ATTEMPT_ID}/terminal_failure_receipt.json"
)
MIN_FREE_BYTES_BEFORE_ATTEMPT = r11.MIN_FREE_BYTES_BEFORE_ATTEMPT
ZERO_EXECUTION_FIELDS = r11.ZERO_EXECUTION_FIELDS
EXECUTION_CONTRACT = {
    **dict(r11.EXECUTION_CONTRACT),
    "local_embedding_inference_batches": 0,
    "upstream_R11_local_embedding_inference_batches": 1,
    "saved_R11_raw_reuse_count": 1,
}
AUTHORITY = {
    **dict(r11.AUTHORITY),
    "current_0_6B_query_embedding_authorized": False,
    "saved_R11_raw_reuse_authorized": True,
}
SEMANTIC_CONTRACT = {
    **dict(r11.SEMANTIC_CONTRACT),
    "predicate_frame_mode": (
        "structural_clause_ownership_decision_v3_typed_scope_argument_group_"
        "governing_price_head_proof_v2_frame_v8"
    ),
    "scope_mode": (
        "frame_local_assertion_owner_actuality_lifecycle_and_scope_edge_v1"
    ),
    "material_coverage_mode": (
        "connector_proof_identity_relational_semantic_signature_and_"
        "lossless_frame_transformation_binding_v4"
    ),
}
EXPECTED_IMPLEMENTATION_PATHS = frozenset(
    set(r11.EXPECTED_IMPLEMENTATION_PATHS)
    | {
        "src/retrieval/dell_report_predicate_frames_r12.py",
        "src/retrieval/dell_report_frame_transformation_r12.py",
        "src/retrieval/dell_report_internal_chain_ceiling_r12.py",
        "scripts/data_retrieval/run_dell_report_internal_chain_ceiling_r12.py",
    }
)
EXPECTED_BOUND_INPUT_IDS = frozenset(
    {
        "R11_policy",
        "R11_public",
        "R11_private",
        "R11_attempt_receipt",
        "R11_raw_execution_capture",
        "R11_fresh_audit",
        "R11_fixed_audit_manifest",
        "R17_report_audit",
        "R17_report_bundle_carry_forward",
        "source_records",
        "compiled_objects",
        "execution_program",
        "runtime_registry",
        "runtime_binding_receipt",
        "residual_route_program",
    }
)
R11_RAW_CANDIDATE_GENERATION_BINDING_IDS = frozenset(
    {
        "source_records",
        "compiled_objects",
        "execution_program",
        "runtime_registry",
        "runtime_binding_receipt",
    }
)
FROZEN_RESIDUAL_ROUTE_PROGRAM_ID = "FIN-0.1.3-S1-DELL-RSQ-03A-R2"
FROZEN_RESIDUAL_ROUTE_PROGRAM_DIGEST = (
    "ed6f11a8fe091d84362d2df041d5ea0bffa50a5c781274f60eaf9e73d6919d50"
)
FROZEN_ROUTE_IDENTITY_DIGESTS = {
    "DELL-RSQ-03A-TARGET-ASP": (
        "9f8b150c67813891fa6e498cd05207ff9f0e3dca820511d63cd62419f0a64cf2"
    ),
    "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE": (
        "a8ecd25680bc9106692f38011ccd637085829913e3a619d8b1e96b2f438d2511"
    ),
    "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD": (
        "6a4b73e34c15a4ad372393cc57c41c2a8aef11b6b079bea2fc6d1bfa96b79ee6"
    ),
    "DELL-RSQ-03A-TARGET-HBM-SUPPLY": (
        "74548171b8cac1b335c6d8d3019d6650bcfd1f9c1610c2c19739621cf750476b"
    ),
    "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH": (
        "ebe4dc3dbc24894e4075c3f9ed3e6e680228b6ebbfdbe69d124532c66bf9fcbb"
    ),
    "DELL-RSQ-03A-TARGET-UNITS": (
        "3ba48c1a1c25d6183fab6824a900d7ded36edc667003bf92c614b5cbb47bb06a"
    ),
}


class DellReportInternalChainCeilingR12Error(ValueError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DellReportInternalChainCeilingR12Error(code)


def _self_digest(value: Mapping[str, Any]) -> bool:
    body = dict(value)
    observed = str(body.pop("result_digest", ""))
    return bool(re.fullmatch(r"[0-9a-f]{64}", observed)) and (
        observed == canonical_digest(body)
    )


def _named_self_digest(
    value: Mapping[str, Any],
    *,
    digest_field: str,
) -> bool:
    body = dict(value)
    observed = str(body.pop(digest_field, ""))
    return bool(re.fullmatch(r"[0-9a-f]{64}", observed)) and (
        observed == canonical_digest(body)
    )


def build_route_contract_identity_registry_r12(
    residual_route_program: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Build immutable per-target route identity independent of active state."""

    program = dict(residual_route_program)
    _require(
        program.get("schema_version")
        == "fin_ia_dell_report_residual_source_ladder_program_v1_1"
        and program.get("program_id") == FROZEN_RESIDUAL_ROUTE_PROGRAM_ID
        and program.get("program_digest")
        == FROZEN_RESIDUAL_ROUTE_PROGRAM_DIGEST
        and program.get("status")
        == "route_manifest_frozen_zero_call_execution_not_authorized"
        and _named_self_digest(program, digest_field="program_digest"),
        "dell_03B_R12_residual_route_program_identity_invalid",
    )
    targets = {
        str(row.get("target_id") or ""): dict(row)
        for row in program.get("route_targets") or ()
        if isinstance(row, Mapping)
    }
    _require(
        set(TARGET_IDS).issubset(targets),
        "dell_03B_R12_residual_route_target_population_invalid",
    )
    registry: dict[str, dict[str, Any]] = {}
    for target_id in sorted(TARGET_IDS):
        target = targets[target_id]
        _require(
            target.get("target_id") == target_id
            and _named_self_digest(
                target,
                digest_field="target_program_digest",
            ),
            f"dell_03B_R12_route_target_digest_invalid:{target_id}",
        )
        contracts: dict[str, dict[str, Any]] = {}
        for raw_contract in target.get("route_contracts") or ():
            _require(
                isinstance(raw_contract, Mapping),
                f"dell_03B_R12_route_contract_not_mapping:{target_id}",
            )
            contract = dict(raw_contract)
            contract_id = str(contract.get("route_contract_id") or "")
            _require(
                contract_id
                and contract_id not in contracts
                and contract.get("target_id") == target_id
                and _named_self_digest(
                    contract,
                    digest_field="route_contract_digest",
                ),
                f"dell_03B_R12_route_contract_identity_invalid:{target_id}",
            )
            contracts[contract_id] = contract
        external = {
            contract_id: contract
            for contract_id, contract in contracts.items()
            if contract.get("route_family_id") != "local_data_object_index_sql"
        }
        mandatory = {
            contract_id: contract
            for contract_id, contract in external.items()
            if contract.get("mandatory_for_target") is True
        }
        _require(
            external and mandatory,
            f"dell_03B_R12_external_route_contract_population_invalid:{target_id}",
        )
        body = {
            "target_id": target_id,
            "source_program_id": program["program_id"],
            "source_program_digest": program["program_digest"],
            "target_program_digest": target["target_program_digest"],
            "all_route_contract_digests": {
                contract_id: contracts[contract_id]["route_contract_digest"]
                for contract_id in sorted(contracts)
            },
            "all_external_route_contract_ids": sorted(external),
            "mandatory_external_route_contract_ids": sorted(mandatory),
            "mandatory_external_route_contract_digests": {
                contract_id: mandatory[contract_id]["route_contract_digest"]
                for contract_id in sorted(mandatory)
            },
            "local_route_contract_ids": sorted(
                contract_id
                for contract_id, contract in contracts.items()
                if contract.get("route_family_id")
                == "local_data_object_index_sql"
            ),
        }
        registry[target_id] = {
            **body,
            "route_identity_digest": canonical_digest(body),
        }
        _require(
            registry[target_id]["route_identity_digest"]
            == FROZEN_ROUTE_IDENTITY_DIGESTS[target_id],
            f"dell_03B_R12_frozen_route_identity_drift:{target_id}",
        )
    return registry


_ROUTE_IDENTITY_BODY_KEYS = frozenset(
    {
        "target_id",
        "source_program_id",
        "source_program_digest",
        "target_program_digest",
        "all_route_contract_digests",
        "all_external_route_contract_ids",
        "mandatory_external_route_contract_ids",
        "mandatory_external_route_contract_digests",
        "local_route_contract_ids",
    }
)


def _validate_private_route_identity_r12(
    value: Mapping[str, Any],
    *,
    target_id: str,
    public_mandatory_ids: Sequence[str],
) -> None:
    row = dict(value)
    body = {key: row.get(key) for key in _ROUTE_IDENTITY_BODY_KEYS}
    all_external = set(body["all_external_route_contract_ids"] or ())
    mandatory = set(body["mandatory_external_route_contract_ids"] or ())
    local = set(body["local_route_contract_ids"] or ())
    all_contract_digests = dict(body["all_route_contract_digests"] or {})
    active = list(
        row.get("active_mandatory_external_route_contract_ids") or ()
    )
    external_required = row.get("active_external_route_required") is True
    _require(
        row.get("target_id") == target_id
        and row.get("route_identity_digest") == canonical_digest(body)
        and row.get("route_identity_digest")
        == FROZEN_ROUTE_IDENTITY_DIGESTS.get(target_id)
        and body["source_program_id"] == FROZEN_RESIDUAL_ROUTE_PROGRAM_ID
        and body["source_program_digest"]
        == FROZEN_RESIDUAL_ROUTE_PROGRAM_DIGEST
        and mandatory
        and mandatory.issubset(all_external)
        and not mandatory & local
        and set(all_contract_digests) == all_external | local
        and all(
            re.fullmatch(r"[0-9a-f]{64}", str(digest or ""))
            for digest in all_contract_digests.values()
        )
        and set(
            dict(body["mandatory_external_route_contract_digests"] or {})
        )
        == mandatory
        and all(
            re.fullmatch(r"[0-9a-f]{64}", str(digest or ""))
            for digest in dict(
                body["mandatory_external_route_contract_digests"] or {}
            ).values()
        )
        and active == list(public_mandatory_ids)
        and (active == sorted(mandatory) if external_required else active == []),
        f"dell_03B_R12_private_route_identity_invalid:{target_id}",
    )


_POLICY_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "program_id",
        "attempt_id",
        "recorded_at",
        "decision_target",
        "owner_basis",
        "execution_contract",
        "semantic_contract",
        "output_contract",
        "bound_inputs",
        "execution_identity",
        "implementation_bindings",
        "TokenBudgetBasis",
        "authority",
        "known_boundary",
        "result_digest",
    }
)
_TOKEN_BUDGET_KEYS = frozenset(
    {
        "node_purpose",
        "input_scale",
        "required_outputs",
        "schema_burden",
        "materiality_quality_risk",
        "comparable_run_evidence",
        "reasoning_profile",
        "stop_and_truncation",
    }
)
_POLICY_AUTHORITY = {
    "03B_internal_chain_execution_authorized": True,
    "current_0_6B_query_embedding_authorized": False,
    "saved_R11_raw_reuse_authorized": True,
    "network_authorized": False,
    "external_capture_authorized": False,
    "4B_embedding_authorized": False,
    "reranker_authorized": False,
    "candidate_decision_authorized": False,
    "evidence_promotion_authorized": False,
    "gap_closure_authorized": False,
    "public_information_boundary_authorized": False,
}


def validate_dell_report_internal_chain_ceiling_r12_policy(
    policy: Mapping[str, Any],
    **bound_values: Mapping[str, Any],
) -> dict[str, Any]:
    value = dict(policy)
    _require(
        set(value) == _POLICY_KEYS
        and value.get("schema_version") == POLICY_SCHEMA_VERSION
        and value.get("status")
        == "same_stage_R12_execution_authorized_after_fresh_R11_audit_failure"
        and value.get("program_id") == PROGRAM_ID
        and value.get("attempt_id") == ATTEMPT_ID
        and _self_digest(value),
        "dell_03B_R12_policy_identity_or_digest_invalid",
    )
    _require(
        value.get("execution_contract") == EXECUTION_CONTRACT
        and value.get("semantic_contract") == SEMANTIC_CONTRACT,
        "dell_03B_R12_policy_execution_or_semantic_contract_invalid",
    )
    output = dict(value.get("output_contract") or {})
    _require(
        output.get("policy_ref") == POLICY_REF
        and output.get("private_result_ref") == PRIVATE_REF
        and output.get("public_result_ref") == PUBLIC_REF
        and output.get("attempt_consumption_receipt_ref")
        == ATTEMPT_RECEIPT_REF
        and output.get("raw_execution_capture_ref")
        == RAW_EXECUTION_CAPTURE_REF
        and output.get("terminal_failure_receipt_ref")
        == TERMINAL_FAILURE_RECEIPT_REF
        and output.get("alternate_output_paths_authorized") is False
        and output.get("private_public_same_path_authorized") is False
        and output.get("exclusive_create_required") is True
        and output.get("atomic_pair_with_rollback_required") is True
        and output.get("same_attempt_retry_authorized") is False
        and output.get("minimum_free_bytes_before_attempt")
        == MIN_FREE_BYTES_BEFORE_ATTEMPT,
        "dell_03B_R12_policy_output_contract_invalid",
    )
    raw_bound = dict(value.get("bound_inputs") or {})
    _require(
        set(raw_bound) == set(EXPECTED_BOUND_INPUT_IDS)
        and set(bound_values) == set(EXPECTED_BOUND_INPUT_IDS),
        "dell_03B_R12_policy_bound_input_population_invalid",
    )
    for binding_id, raw in raw_bound.items():
        row = dict(raw or {})
        _require(
            set(row).issubset(r7._STANDARD_BINDING_KEYS)  # noqa: SLF001
            and {"ref", "sha256"}.issubset(row)
            and bool(str(row.get("ref") or ""))
            and bool(re.fullmatch(r"[0-9a-f]{64}", str(row.get("sha256") or ""))),
            f"dell_03B_R12_policy_bound_input_invalid:{binding_id}",
        )
        supplied = dict(bound_values[binding_id])
        if "result_digest" in row:
            _require(
                supplied.get("result_digest") == row.get("result_digest"),
                f"dell_03B_R12_policy_bound_result_digest_drift:{binding_id}",
            )

    r11_private = _validate_r11_predecessor_result(bound_values["R11_private"])
    r11_policy = dict(bound_values["R11_policy"])
    r11_public = dict(bound_values["R11_public"])
    r11_attempt = dict(bound_values["R11_attempt_receipt"])
    r11_raw = dict(bound_values["R11_raw_execution_capture"])
    _require(
        _self_digest(r11_policy)
        and _self_digest(r11_public)
        and _self_digest(r11_attempt)
        and _self_digest(r11_raw)
        and r11_policy.get("result_digest") == r11_private.get("policy_digest")
        and r11_public.get("private_result_digest")
        == r11_private.get("result_digest")
        and r11_attempt.get("attempt_id") == r11.ATTEMPT_ID
        and r11_attempt.get("policy_digest") == r11_private.get("policy_digest")
        and r11_raw.get("attempt_id") == r11.ATTEMPT_ID
        and r11_raw.get("policy_digest") == r11_private.get("policy_digest")
        and r11_raw.get("raw_execution_sha256")
        == r11_private.get("raw_execution_sha256"),
        "dell_03B_R12_R11_predecessor_chain_invalid",
    )
    predecessor_bindings = dict(r11_private.get("input_bindings") or {})
    for binding_id in sorted(R11_RAW_CANDIDATE_GENERATION_BINDING_IDS):
        _require(
            dict(raw_bound.get(binding_id) or {})
            == dict(predecessor_bindings.get(binding_id) or {}),
            f"dell_03B_R12_candidate_generation_binding_drift:{binding_id}",
        )
    route_registry = build_route_contract_identity_registry_r12(
        bound_values["residual_route_program"]
    )
    _require(
        len(route_registry) == len(TARGET_IDS),
        "dell_03B_R12_route_registry_population_invalid",
    )
    r11_audit = dict(bound_values["R11_fresh_audit"])
    r11_manifest = dict(bound_values["R11_fixed_audit_manifest"])
    r17_audit = dict(bound_values["R17_report_audit"])
    engineering_verdict = dict(r11_audit.get("R11_engineering_verdict") or {})
    report_verdict = dict(r11_audit.get("R17_report_quality") or {})
    _require(
        _self_digest(r11_audit)
        and _self_digest(r11_manifest)
        and r11_audit.get("audit_manifest", {}).get("result_digest")
        == r11_manifest.get("result_digest")
        and r11_audit.get("audit_id") == r11_manifest.get("audit_id")
        and engineering_verdict.get("verdict")
        == "FAIL_MATERIAL_FINDINGS_PRESERVED_SAME_STAGE_SUCCESSOR_REQUIRED"
        and engineering_verdict.get("new_severity_counts")
        == {"P0": 0, "P1": 1, "P2": 3, "P3": 0}
        and {
            str(row.get("finding_id") or "")
            for row in r11_audit.get("R11_material_findings") or ()
            if isinstance(row, Mapping)
        }
        == {
            "R11-P1-ROUTE-STATE-ERASURE-ASP",
            "R11-P2-CLAUSE-OWNERSHIP-OPEN-VOCAB-AND-CASE-DEPENDENCE",
            "R11-P2-PRICE-INTERVENING-NOMINAL-HEAD",
            "R11-P2-TRANSFORMATION-CONNECTOR-PROOF-REBIND",
        }
        and report_verdict.get("verdict")
        == "FAIL_GATE_OPEN_NOT_ASSESSABLE"
        and report_verdict.get("carried_severity_counts")
        == {"P0": 0, "P1": 1, "P2": 2, "P3": 1}
        and r17_audit.get("verdicts", {}).get("R17_report_quality")
        == "FAIL_GATE_OPEN_NOT_ASSESSABLE"
        and r17_audit.get("verdicts", {}).get("R17_open_P0_P1_P2_P3")
        == [0, 1, 2, 1],
        "dell_03B_R12_R11_or_R17_audit_failure_boundary_invalid",
    )
    carry = dict(bound_values["R17_report_bundle_carry_forward"])
    _require(
        _self_digest(carry)
        and len(dict(carry.get("R17_report_quality_bundle") or {})) == 14,
        "dell_03B_R12_R17_14_file_carry_forward_invalid",
    )
    identity = dict(value.get("execution_identity") or {})
    _require(
        identity.get("branch") == BRANCH
        and bool(
            re.fullmatch(
                r"[0-9a-f]{40}",
                str(identity.get("implementation_commit") or ""),
            )
        )
        and bool(
            re.fullmatch(
                r"[0-9a-f]{40}",
                str(identity.get("implementation_tree") or ""),
            )
        )
        and identity.get("authority_commit_changed_paths") == [POLICY_REF]
        and identity.get(
            "authority_commit_parent_must_equal_implementation_commit"
        )
        is True
        and identity.get("HEAD_must_equal_upstream") is True,
        "dell_03B_R12_policy_execution_identity_invalid",
    )
    implementation_rows = value.get("implementation_bindings")
    _require(
        isinstance(implementation_rows, Sequence)
        and not isinstance(implementation_rows, (str, bytes))
        and {
            str(row.get("path") or "")
            for row in implementation_rows
            if isinstance(row, Mapping)
        }
        == set(EXPECTED_IMPLEMENTATION_PATHS),
        "dell_03B_R12_policy_implementation_binding_population_invalid",
    )
    token_basis = dict(value.get("TokenBudgetBasis") or {})
    _require(
        set(token_basis) == _TOKEN_BUDGET_KEYS
        and all(bool(str(token_basis[key]).strip()) for key in _TOKEN_BUDGET_KEYS),
        "dell_03B_R12_policy_TokenBudgetBasis_invalid",
    )
    _require(
        value.get("authority") == _POLICY_AUTHORITY,
        "dell_03B_R12_policy_authority_invalid",
    )
    return r11_private


def classify_dell_report_internal_chain_r12_package(
    *, target_id: str, text: str, metadata: Mapping[str, Any]
) -> dict[str, Any]:
    return _classify_predicate_frame_r12(
        target_id=target_id,
        text=text,
        metadata=metadata,
    )


def build_dell_report_internal_chain_r12_corpus_index(
    *,
    source_rows: Sequence[Mapping[str, Any]],
    object_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return r11.build_dell_report_internal_chain_r11_corpus_index(
        source_rows=source_rows,
        object_rows=object_rows,
    )


def _package_windows_r12(
    *,
    target_id: str,
    units: Sequence[Mapping[str, Any]],
    metadata: Mapping[str, Any],
    selected_object_ids: set[str] | None,
    rank_by_object_id: Mapping[str, int] | None,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for unit in units:
        unit_id = str(unit["unit_id"])
        text = str(unit.get("text") or "")
        if (
            selected_object_ids is not None and unit_id not in selected_object_ids
        ) or not r8._target_hint_r8(target_id, text):  # noqa: SLF001
            continue
        assessment, runtime_frames, boundary_deferred = (
            _classify_with_frames_r12(
                target_id=target_id,
                text=text,
                metadata=metadata,
                defer_irrelevant_boundary_decisions=True,
            )
        )
        assessment["_R12_runtime_frame_objects"] = runtime_frames
        assessment["_R12_boundary_decisions_deferred"] = boundary_deferred
        position = int(unit["position"])
        assessment.update(
            {
                "unit_ids": [unit_id],
                "window_start_position": position,
                "window_end_position": position,
                "window_unit_span": 1,
                "completion_rank": None,
            }
        )
        if (
            assessment["classification"] == "complete_bounded_target_package"
            and rank_by_object_id
        ):
            accepted_rank = rank_by_object_id.get(unit_id)
            if accepted_rank is not None:
                assessment["completion_rank"] = int(accepted_rank)
        output.append(assessment)
    return output


def _best_package_r12(
    windows: Sequence[Mapping[str, Any]],
    *,
    family_id: str,
    metadata: Mapping[str, Any],
    object_package: bool,
) -> dict[str, Any]:
    priority = {
        "complete_bounded_target_package": 0,
        "partial_context_only": 1,
        "not_target_semantic_equivalent": 2,
    }
    if windows:
        selected = min(
            windows,
            key=lambda row: (
                priority[str(row["classification"])],
                row.get("completion_rank")
                if row.get("completion_rank") is not None
                else 10**9,
                -len(row.get("matched_group_ids") or ()),
                int(row.get("window_unit_span") or 10**9),
                tuple(row.get("unit_ids") or ()),
            ),
        )
        value = dict(selected)
        if value.pop("_R12_boundary_decisions_deferred", False):
            value["frame_boundary_decisions"] = [
                row.as_dict()
                for row in frame_boundary_decisions(
                    str(value.get("model_text") or "")
                )
            ]
    else:
        value = classify_dell_report_internal_chain_r12_package(
            target_id=str(metadata.get("target_id") or ""),
            text="",
            metadata=metadata,
        )
        value.update(
            {
                "unit_ids": [],
                "window_start_position": None,
                "window_end_position": None,
                "window_unit_span": 0,
                "completion_rank": None,
                "_R12_runtime_frame_objects": (),
            }
        )
    value["canonical_source_family_id"] = family_id
    value["source_record_id"] = family_id
    if object_package:
        value["compiled_object_ids"] = list(value.pop("unit_ids"))
    else:
        value["source_sentence_unit_ids"] = list(value.pop("unit_ids"))
    return value


def _selected_frame_r12(
    *,
    target_id: str,
    package: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> PredicateFrame | None:
    selected_id = package.get("selected_frame_id")
    if not isinstance(selected_id, str):
        return None
    if "_R12_runtime_frame_objects" in package:
        runtime_frames = package["_R12_runtime_frame_objects"]
        return next(
            (row for row in runtime_frames if row.frame_id == selected_id),
            None,
        )
    frames = extract_predicate_frames(
        target_id=target_id,
        text=str(package.get("model_text") or ""),
        metadata=metadata,
    )
    return next((row for row in frames if row.frame_id == selected_id), None)


def _family_transformation_binding_r12(
    *,
    target_id: str,
    family_id: str,
    metadata: Mapping[str, Any],
    source_package: Mapping[str, Any],
    compiled_package: Mapping[str, Any],
    source_frame: PredicateFrame | None = None,
    compiled_frame: PredicateFrame | None = None,
) -> FrameTransformationBinding | None:
    if (
        source_package.get("classification") == "not_target_semantic_equivalent"
        or compiled_package.get("classification")
        == "not_target_semantic_equivalent"
    ):
        return None
    source_frame = source_frame or _selected_frame_r12(
        target_id=target_id,
        package=source_package,
        metadata=metadata,
    )
    compiled_frame = compiled_frame or _selected_frame_r12(
        target_id=target_id,
        package=compiled_package,
        metadata=metadata,
    )
    if source_frame is None or compiled_frame is None:
        return None
    object_ids = [
        str(value)
        for value in (
            compiled_package.get("compiled_object_ids")
            or compiled_package.get("unit_ids")
            or ()
        )
    ]
    if not object_ids:
        return None
    source_text = str(source_package.get("model_text") or "")
    compiled_text = str(compiled_package.get("model_text") or "")
    if source_text == compiled_text:
        transformation_type = "exact_slice"
    elif len(object_ids) > 1:
        transformation_type = "many_object_same_source"
    else:
        transformation_type = "bounded_window"
    return build_frame_transformation_binding_r12(
        canonical_source_family_id=family_id,
        source_record_id=str(source_package.get("source_record_id") or family_id),
        source_frame=source_frame,
        compiled_object_ids=object_ids,
        compiled_window_ids=[f"WINDOW::R12::{value}" for value in object_ids],
        compiled_frame=compiled_frame,
        transformation_type=transformation_type,
        require_lossless=False,
    )


def _matching_compiled_frame_r12(
    *,
    target_id: str,
    source_frame: PredicateFrame,
    object_windows: Sequence[Mapping[str, Any]],
    metadata: Mapping[str, Any],
) -> tuple[dict[str, Any], PredicateFrame] | None:
    candidates: list[tuple[dict[str, Any], PredicateFrame]] = []
    for raw_window in object_windows:
        matching_ids = {
            str(row.get("frame_id") or "")
            for row in raw_window.get("predicate_frames") or ()
            if row.get("semantic_signature_digest")
            == source_frame.semantic_signature_digest
        }
        if not matching_ids:
            continue
        window = dict(raw_window)
        frames = (
            list(window["_R12_runtime_frame_objects"])
            if "_R12_runtime_frame_objects" in window
            else extract_predicate_frames(
                target_id=target_id,
                text=str(window.get("model_text") or ""),
                metadata=metadata,
            )
        )
        for frame in frames:
            if frame.frame_id in matching_ids:
                candidates.append((window, frame))
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda row: (
            row[0].get("completion_rank")
            if row[0].get("completion_rank") is not None
            else 10**9,
            tuple(row[0].get("unit_ids") or ()),
            row[1].sentence_index,
            row[1].frame_index,
            row[1].frame_id,
        ),
    )


def _coverage_gap_r12(
    *,
    target_id: str,
    family_id: str,
    source_package: Mapping[str, Any],
    binding: FrameTransformationBinding | None,
) -> dict[str, Any] | None:
    if source_package.get("classification") != "complete_bounded_target_package":
        return None
    if binding is not None and binding.binding_accepted:
        return None
    return {
        "target_id": target_id,
        "canonical_source_family_id": family_id,
        "source_record_ids": [
            str(source_package.get("source_record_id") or family_id)
        ],
        "source_occurrence_count": 1,
        "material_sentence_digest": canonical_digest(
            str(source_package.get("model_text") or "")
        ),
        "required_material_group_ids": sorted(
            str(value) for value in source_package.get("required_group_ids") or ()
        ),
        "material_anchors": sorted(
            str(value)
            for value in source_package.get("accepted_frame_role_anchors") or ()
        ),
        "anchor_mode": (
            "route_constant_governing_head_connector_proof_"
            "semantic_transformation_bound_v8"
        ),
        "reason": (
            "canonical_material_source_frame_missing_lossless_compiled_"
            "frame_transformation_binding"
        ),
        "transformation_findings": (
            []
            if binding is None
            else [
                *binding.loss_flags,
                *binding.addition_flags,
                *binding.ambiguity_flags,
                *binding.proof_rebind_flags,
            ]
        ),
    }


def assess_dell_report_internal_chain_r12_packages(
    *,
    target_id: str,
    source_rows: Sequence[Mapping[str, Any]],
    object_rows: Sequence[Mapping[str, Any]],
    selected_object_ids: Iterable[str] | None = None,
    rank_by_object_id: Mapping[str, int] | None = None,
    corpus_index: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    index = (
        dict(corpus_index)
        if corpus_index is not None
        else build_dell_report_internal_chain_r12_corpus_index(
            source_rows=source_rows,
            object_rows=object_rows,
        )
    )
    _require(
        int(index.get("source_record_count") or 0) == len(source_rows)
        and int(index.get("compiled_object_count") or 0) == len(object_rows)
        and index.get("source_position_mode")
        == "raw_occurrence_before_deduplication",
        "dell_03B_R12_corpus_index_population_or_position_drift",
    )
    families = dict(index["families"])
    source_units_by_family = dict(index["source_units_by_family"])
    objects_by_family = dict(index["objects_by_family"])
    selected = set(selected_object_ids) if selected_object_ids is not None else None
    source_packages: list[dict[str, Any]] = []
    compiled_packages: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    bindings: list[FrameTransformationBinding] = []
    family_ids = (
        sorted(families)
        if selected is None
        else sorted(
            family_id
            for family_id, units in objects_by_family.items()
            if any(str(unit["unit_id"]) in selected for unit in units)
        )
    )
    for family_id in family_ids:
        family_rows = families[family_id]
        metadata = {**dict(family_rows[0]), "target_id": target_id}
        source_package: dict[str, Any] | None = None
        if selected is None:
            source_windows = _package_windows_r12(
                target_id=target_id,
                units=list(source_units_by_family[family_id]),
                metadata=metadata,
                selected_object_ids=None,
                rank_by_object_id=None,
            )
            source_package = _best_package_r12(
                source_windows,
                family_id=family_id,
                metadata=metadata,
                object_package=False,
            )
            source_packages.append(source_package)
        object_windows = _package_windows_r12(
            target_id=target_id,
            units=objects_by_family.get(family_id, []),
            metadata=metadata,
            selected_object_ids=selected,
            rank_by_object_id=rank_by_object_id,
        )
        compiled_package = _best_package_r12(
            object_windows,
            family_id=family_id,
            metadata=metadata,
            object_package=True,
        )
        compiled_packages.append(compiled_package)
        if source_package is not None:
            source_frame = _selected_frame_r12(
                target_id=target_id,
                package=source_package,
                metadata=metadata,
            )
            matching_compiled = (
                _matching_compiled_frame_r12(
                    target_id=target_id,
                    source_frame=source_frame,
                    object_windows=object_windows,
                    metadata=metadata,
                )
                if source_frame is not None
                else None
            )
            transformation_compiled_package = (
                matching_compiled[0]
                if matching_compiled is not None
                else compiled_package
            )
            binding = _family_transformation_binding_r12(
                target_id=target_id,
                family_id=family_id,
                metadata=metadata,
                source_package=source_package,
                compiled_package=transformation_compiled_package,
                source_frame=source_frame,
                compiled_frame=(
                    matching_compiled[1]
                    if matching_compiled is not None
                    else None
                ),
            )
            if binding is None and source_frame is not None:
                binding = build_missing_compiled_frame_binding_r12(
                    canonical_source_family_id=family_id,
                    source_record_id=str(
                        source_package.get("source_record_id") or family_id
                    ),
                    source_frame=source_frame,
                )
            if binding is not None:
                bindings.append(binding)
            gap = _coverage_gap_r12(
                target_id=target_id,
                family_id=family_id,
                source_package=source_package,
                binding=binding,
            )
            if gap is not None:
                coverage.append(gap)
    def without_runtime_frames(row: Mapping[str, Any]) -> dict[str, Any]:
        value = dict(row)
        value.pop("_R12_runtime_frame_objects", None)
        value.pop("_R12_boundary_decisions_deferred", None)
        return value

    return {
        "source_packages": [
            without_runtime_frames(row) for row in source_packages
        ],
        "compiled_packages": [
            without_runtime_frames(row) for row in compiled_packages
        ],
        "coverage_gaps": coverage,
        "coverage_gap_canonical_family_claim_count": len(coverage),
        "coverage_gap_source_occurrence_count": sum(
            int(row["source_occurrence_count"]) for row in coverage
        ),
        "frame_transformation_bindings": [row.as_dict() for row in bindings],
        "frame_transformation_binding_digest": (
            transformation_binding_digest_r12(bindings)
        ),
        "frame_transformation_binding_count": len(bindings),
        "accepted_frame_transformation_binding_count": sum(
            row.binding_accepted for row in bindings
        ),
    }


def _clause_decision_counts_r12(
    packages: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for package in packages:
        for raw_decision in package.get("frame_boundary_decisions") or ():
            decision = str(raw_decision.get("decision") or "")
            if decision:
                counts[decision] = counts.get(decision, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def _governing_head_partial_count_r12(
    packages: Sequence[Mapping[str, Any]],
) -> int:
    return sum(
        any(
            "intervening_governing_nominal_head" in str(limitation)
            for limitation in package.get("limitations") or ()
        )
        for package in packages
        if package.get("classification") == "partial_context_only"
    )


def _validate_r11_predecessor_result(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    result = dict(value)
    _require(
        result.get("schema_version") == r11.PRIVATE_RESULT_SCHEMA_VERSION
        and result.get("attempt_id") == r11.ATTEMPT_ID
        and result.get("status")
        == "dell_03B_R11_clause_ownership_price_attachment_proof_ceiling_executed"
        and result.get("case_key") == "DELL"
        and _self_digest(result),
        "dell_03B_R12_R11_predecessor_private_identity_invalid",
    )
    return result


def validate_dell_report_internal_chain_r12_saved_raw_execution(
    execution: Mapping[str, Any],
    *,
    expected_request_ids: Iterable[str],
) -> dict[str, Any]:
    """Validate R11 raw identity, then project R12-stage zero-call counters."""

    validated = r3.validate_dell_report_internal_chain_ceiling_r3_execution(
        execution,
        expected_request_ids=expected_request_ids,
    )
    upstream_summary = dict(validated["summary"])
    _require(
        upstream_summary.get("local_embedding_inference_batches") == 1
        and all(upstream_summary.get(field) == 0 for field in ZERO_EXECUTION_FIELDS),
        "dell_03B_R12_upstream_R11_execution_counter_invalid",
    )
    return {
        **validated,
        "summary": {
            **upstream_summary,
            "local_embedding_inference_batches": 0,
        },
    }


def compile_dell_report_internal_chain_ceiling_r12_result(
    *,
    r11_private_result: Mapping[str, Any],
    r12_policy: Mapping[str, Any],
    execution: Mapping[str, Any],
    execution_sha256: str,
    source_rows: Sequence[Mapping[str, Any]],
    object_rows: Sequence[Mapping[str, Any]],
    residual_route_program: Mapping[str, Any],
    recorded_at: str,
    prepared_from_commit: str,
    input_bindings: Mapping[str, Any],
) -> dict[str, Any]:
    """Compile one fresh or explicitly saved execution through the R12 IR."""

    predecessor = _validate_r11_predecessor_result(r11_private_result)
    route_registry = build_route_contract_identity_registry_r12(
        residual_route_program
    )
    predecessor_targets = {
        str(row.get("target_id") or ""): dict(row)
        for row in predecessor.get("target_results") or ()
        if isinstance(row, Mapping)
    }
    _require(
        set(predecessor_targets) == set(TARGET_IDS),
        "dell_03B_R12_R11_predecessor_target_population_invalid",
    )
    expected_request_ids = {
        str(request_id)
        for row in predecessor_targets.values()
        for request_id in row.get("request_ids") or ()
    }
    execution = dict(execution)
    validated = validate_dell_report_internal_chain_r12_saved_raw_execution(
        execution,
        expected_request_ids=expected_request_ids,
    )
    actual_execution_sha256 = hashlib.sha256(
        json.dumps(
            execution,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    _require(
        bool(re.fullmatch(r"[0-9a-f]{64}", execution_sha256))
        and execution_sha256 == actual_execution_sha256,
        "dell_03B_R12_raw_execution_sha_mismatch",
    )
    request_by_id = validated["request_results_by_id"]
    corpus_index = build_dell_report_internal_chain_r12_corpus_index(
        source_rows=source_rows,
        object_rows=object_rows,
    )
    object_ids = {
        str(unit["unit_id"])
        for units in dict(corpus_index["objects_by_family"]).values()
        for unit in units
    }
    target_results: list[dict[str, Any]] = []
    total_union_occurrences = 0
    for target_id in sorted(TARGET_IDS):
        predecessor_target = predecessor_targets[target_id]
        request_ids = [
            str(value) for value in predecessor_target.get("request_ids") or ()
        ]
        scoped_results = [request_by_id[value] for value in request_ids]
        union_ids = {
            str(seed.get("compiled_object_id") or "")
            for row in scoped_results
            for seed in row["hybrid_object_retrieval"]["candidate_decision_seed"]
        }
        final_ids = {
            str(candidate.get("compiled_object_id") or "")
            for row in scoped_results
            for candidate in row["hybrid_object_retrieval"]["candidates"]
        }
        _require(
            union_ids.issubset(object_ids) and final_ids.issubset(union_ids),
            f"dell_03B_R12_candidate_object_binding_invalid:{target_id}",
        )
        total_union_occurrences += len(union_ids)
        corpus = assess_dell_report_internal_chain_r12_packages(
            target_id=target_id,
            source_rows=source_rows,
            object_rows=object_rows,
            corpus_index=corpus_index,
        )
        union_rank = r4._rank_map(  # noqa: SLF001
            union_ids,
            scoped_results,
            "minimum_raw_union_rank",
        )
        union = assess_dell_report_internal_chain_r12_packages(
            target_id=target_id,
            source_rows=source_rows,
            object_rows=object_rows,
            selected_object_ids=union_ids,
            rank_by_object_id=union_rank,
            corpus_index=corpus_index,
        )
        final_rank = r4._rank_map(  # noqa: SLF001
            final_ids,
            scoped_results,
            "minimum_final_output_rank",
        )
        final = assess_dell_report_internal_chain_r12_packages(
            target_id=target_id,
            source_rows=source_rows,
            object_rows=object_rows,
            selected_object_ids=final_ids,
            rank_by_object_id=final_rank,
            corpus_index=corpus_index,
        )
        source_complete = r4._complete_ids(corpus["source_packages"])  # noqa: SLF001
        compiled_complete = r4._complete_ids(  # noqa: SLF001
            corpus["compiled_packages"]
        )
        union_complete = r4._complete_ids(union["compiled_packages"])  # noqa: SLF001
        final_complete = r4._complete_ids(final["compiled_packages"])  # noqa: SLF001
        source_partial = r4._partial_ids(corpus["source_packages"])  # noqa: SLF001
        compiled_partial = r4._partial_ids(  # noqa: SLF001
            corpus["compiled_packages"]
        )
        materialization_gaps = source_complete - compiled_complete
        coverage_gaps = list(corpus["coverage_gaps"])
        bindings = list(corpus["frame_transformation_bindings"])
        accepted_binding_families = {
            str(row.get("canonical_source_family_id") or "")
            for row in bindings
            if row.get("binding_accepted") is True
        }
        unbound_source_families = sorted(
            (source_complete | source_partial) - accepted_binding_families
        )
        transformation_failures = [
            row for row in bindings if row.get("binding_accepted") is not True
        ]
        unbound_complete_source_families = sorted(
            source_complete - accepted_binding_families
        )
        unbound_partial_source_families = sorted(
            source_partial - accepted_binding_families
        )
        compiled_complete_without_source_antecedent = sorted(
            compiled_complete
            - {
                family_id
                for family_id in accepted_binding_families
                if family_id in source_complete
            }
        )
        failed_complete_bindings = [
            row
            for row in transformation_failures
            if row.get("canonical_source_family_id") in source_complete
        ]
        complete_transformation_coverage_pass = (
            not unbound_complete_source_families
            and not compiled_complete_without_source_antecedent
            and not failed_complete_bindings
        )
        coverage_pass = (
            not materialization_gaps
            and not coverage_gaps
            and complete_transformation_coverage_pass
        )

        if materialization_gaps or coverage_gaps:
            earliest = "local_source_to_object_materialization_or_coverage_gap"
        elif not complete_transformation_coverage_pass:
            earliest = "source_to_compiled_frame_transformation_binding_gap"
        elif not source_complete:
            earliest = "local_source_record_corpus_missing_complete_bounded_package"
        elif not compiled_complete:
            earliest = "local_compiled_package_missing_complete_target"
        elif not union_complete:
            earliest = "current_bm25_0_6b_graph_bounded_package_recall_miss"
        elif not final_complete:
            earliest = "post_union_rank_or_review_cut"
        else:
            earliest = "none_observed_through_final_bounded_package"

        completion_ranks = [
            int(row["completion_rank"])
            for row in final["compiled_packages"]
            if row.get("canonical_source_family_id") in final_complete
            and row.get("completion_rank") is not None
        ]
        best_final_rank = min(completion_ranks, default=None)
        embedding_eligible = bool(
            coverage_pass and compiled_complete and not union_complete
        )
        reranker_eligible = bool(
            coverage_pass
            and union_complete
            and (best_final_rank is None or best_final_rank > 10)
        )
        external_required = not source_complete
        predecessor_disposition = dict(
            predecessor_target.get("downstream_disposition") or {}
        )
        residual = list(
            predecessor_disposition.get("03C_residual_scope_if_authorized") or ()
        )
        route_identity = dict(route_registry[target_id])
        mandatory_external_routes = list(
            route_identity["mandatory_external_route_contract_ids"]
        )
        _require(
            (not external_required)
            or (
                bool(mandatory_external_routes)
                and all(
                    route_id
                    in route_identity["all_external_route_contract_ids"]
                    for route_id in mandatory_external_routes
                )
                and not set(mandatory_external_routes)
                & set(route_identity["local_route_contract_ids"])
            ),
            f"dell_03B_R12_external_route_identity_unresolved:{target_id}",
        )
        public_packages = sorted(
            (
                r4._public_package(row)  # noqa: SLF001
                for row in final["compiled_packages"]
                if row.get("classification")
                != "not_target_semantic_equivalent"
            ),
            key=lambda row: (
                row.get("classification")
                != "complete_bounded_target_package",
                row.get("completion_rank") or 10**9,
                row.get("canonical_source_family_id") or "",
            ),
        )[:20]
        target_results.append(
            {
                "target_id": target_id,
                "pack_gap_id": predecessor_target.get("pack_gap_id"),
                "target_proposition": predecessor_target.get("target_proposition"),
                "request_ids": request_ids,
                "semantic_evidence_unit": (
                    "one_typed_R12_assertion_frame_with_structural_clause_"
                    "ownership_governing_price_head_scope_edges_argument_"
                    "groups_and_connector_proof_identity_binding"
                ),
                "candidate_ceiling": {
                    "source_record_population": len(source_rows),
                    "canonical_source_family_population": len(
                        corpus["source_packages"]
                    ),
                    "compiled_object_population": len(object_rows),
                    "complete_target_in_source_record_corpus_count": len(
                        source_complete
                    ),
                    "complete_target_in_compiled_package_corpus_count": len(
                        compiled_complete
                    ),
                    "partial_context_in_source_record_corpus_count": len(
                        source_partial
                    ),
                    "partial_context_in_compiled_package_corpus_count": len(
                        compiled_partial
                    ),
                    "candidate_union_object_count": len(union_ids),
                    "complete_target_in_candidate_union_package_count": len(
                        union_complete
                    ),
                    "final_review_object_count": len(final_ids),
                    "complete_target_in_final_review_package_count": len(
                        final_complete
                    ),
                    "best_complete_package_final_completion_rank": best_final_rank,
                    "complete_target_useful_at_10": bool(
                        best_final_rank is not None and best_final_rank <= 10
                    ),
                    "earliest_observed_limitation": earliest,
                    "package_materialization_gap_count": len(materialization_gaps),
                    "material_source_claim_coverage_gap_canonical_count": len(
                        coverage_gaps
                    ),
                    "material_source_claim_coverage_gap_occurrence_count": corpus[
                        "coverage_gap_source_occurrence_count"
                    ],
                    "source_to_object_semantic_coverage_pass": coverage_pass,
                    "source_position_mode": (
                        "raw_occurrence_before_deduplication"
                    ),
                    "material_anchor_mode": (
                        "route_constant_governing_head_connector_proof_"
                        "semantic_transformation_bound_v8"
                    ),
                    "source_package_scan_digest": canonical_digest(
                        [
                            {
                                key: row.get(key)
                                for key in (
                                    "canonical_source_family_id",
                                    "classification",
                                    "package_role",
                                    "matched_group_ids",
                                    "limitations",
                                    "selected_frame_id",
                                    "selected_frame_representation_digest",
                                    "selected_frame_semantic_signature_digest",
                                    "accepted_frame_role_anchors",
                                    "window_start_position",
                                    "window_end_position",
                                )
                            }
                            for row in corpus["source_packages"]
                        ]
                    ),
                    "candidate_decision_state": (
                        "candidate_not_evidence_unadjudicated"
                    ),
                    "public_information_gap_eligible": False,
                },
                "downstream_disposition": {
                    "03D_4B_embedding_recall_challenger_eligible": (
                        embedding_eligible
                    ),
                    "03D_same_pool_reranker_challenger_eligible": (
                        reranker_eligible
                    ),
                    "03C_external_route_required_for_complete_bounded_target": (
                        external_required
                    ),
                    "03C_scope_if_authorized": (
                        residual if external_required else []
                    ),
                    "03C_residual_route_requires_prior_capture_crosswalk": bool(
                        residual
                    ),
                    "03C_residual_scope_if_authorized": residual,
                    "remaining_non_03C_research_boundaries": residual,
                    "local_source_to_object_repair_required": not coverage_pass,
                    "mandatory_external_route_contract_ids_if_authorized": (
                        mandatory_external_routes if external_required else []
                    ),
                    "authority_granted_by_this_result": False,
                },
                "public_top_bounded_packages": public_packages,
                "private_source_packages": [
                    row
                    for row in corpus["source_packages"]
                    if row.get("classification")
                    != "not_target_semantic_equivalent"
                ],
                "private_compiled_packages": [
                    row
                    for row in corpus["compiled_packages"]
                    if row.get("classification")
                    != "not_target_semantic_equivalent"
                ],
                "private_union_packages": [
                    row
                    for row in union["compiled_packages"]
                    if row.get("classification")
                    != "not_target_semantic_equivalent"
                ],
                "private_final_packages": [
                    row
                    for row in final["compiled_packages"]
                    if row.get("classification")
                    != "not_target_semantic_equivalent"
                ],
                "private_source_to_object_coverage_gaps": coverage_gaps,
                "private_route_contract_identity": {
                    **route_identity,
                    "active_external_route_required": external_required,
                    "active_mandatory_external_route_contract_ids": (
                        mandatory_external_routes if external_required else []
                    ),
                },
                "private_frame_transformation_bindings": bindings,
                "private_frame_transformation_summary": {
                    "binding_count": corpus[
                        "frame_transformation_binding_count"
                    ],
                    "accepted_binding_count": corpus[
                        "accepted_frame_transformation_binding_count"
                    ],
                    "binding_set_digest": corpus[
                        "frame_transformation_binding_digest"
                    ],
                    "unbound_source_family_count": len(unbound_source_families),
                    "unbound_source_family_ids": unbound_source_families,
                    "unbound_complete_source_family_count": len(
                        unbound_complete_source_families
                    ),
                    "unbound_complete_source_family_ids": (
                        unbound_complete_source_families
                    ),
                    "unbound_partial_source_family_count": len(
                        unbound_partial_source_families
                    ),
                    "compiled_complete_without_source_antecedent_count": len(
                        compiled_complete_without_source_antecedent
                    ),
                    "compiled_complete_without_source_antecedent_ids": (
                        compiled_complete_without_source_antecedent
                    ),
                    "failed_binding_count": len(transformation_failures),
                    "failed_complete_binding_count": len(
                        failed_complete_bindings
                    ),
                    "proof_rebind_failure_count": sum(
                        bool(row.get("proof_rebind_flags"))
                        for row in transformation_failures
                    ),
                    "source_governing_nominal_head_partial_count": (
                        _governing_head_partial_count_r12(
                            corpus["source_packages"]
                        )
                    ),
                    "compiled_governing_nominal_head_partial_count": (
                        _governing_head_partial_count_r12(
                            corpus["compiled_packages"]
                        )
                    ),
                    "source_clause_ownership_decision_counts": (
                        _clause_decision_counts_r12(
                            corpus["source_packages"]
                        )
                    ),
                    "compiled_clause_ownership_decision_counts": (
                        _clause_decision_counts_r12(
                            corpus["compiled_packages"]
                        )
                    ),
                    "complete_transformation_coverage_pass": (
                        complete_transformation_coverage_pass
                    ),
                },
            }
        )

    execution_summary = dict(validated["summary"])
    body = {
        "schema_version": PRIVATE_RESULT_SCHEMA_VERSION,
        "status": (
            "dell_03B_R12_route_clause_governing_price_connector_proof_ceiling_executed"
        ),
        "attempt_id": ATTEMPT_ID,
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "case_key": "DELL",
        "input_bindings": dict(input_bindings),
        "runtime_registry": dict(predecessor.get("runtime_registry") or {}),
        "raw_execution_receipt": execution,
        "raw_execution_sha256": execution_sha256,
        "raw_execution_projection_digest": execution.get("projection_digest"),
        "validated_execution_digest": validated["validated_execution_digest"],
        "execution_summary": execution_summary,
        "target_results": target_results,
        "summary": {
            "target_count": len(target_results),
            "held_target_execution_count": 0,
            "request_count": len(validated["request_results"]),
            "candidate_union_occurrence_count": total_union_occurrences,
            "embedding_challenger_eligible_target_count": sum(
                row["downstream_disposition"][
                    "03D_4B_embedding_recall_challenger_eligible"
                ]
                is True
                for row in target_results
            ),
            "reranker_challenger_eligible_target_count": sum(
                row["downstream_disposition"][
                    "03D_same_pool_reranker_challenger_eligible"
                ]
                is True
                for row in target_results
            ),
            "external_route_required_target_count": sum(
                row["downstream_disposition"][
                    "03C_external_route_required_for_complete_bounded_target"
                ]
                is True
                for row in target_results
            ),
            "residual_research_boundary_target_count": sum(
                bool(
                    row["downstream_disposition"].get(
                        "remaining_non_03C_research_boundaries"
                    )
                )
                for row in target_results
            ),
            "local_source_to_object_repair_target_count": sum(
                row["downstream_disposition"][
                    "local_source_to_object_repair_required"
                ]
                is True
                for row in target_results
            ),
            **{
                field: execution_summary[field]
                for field in ZERO_EXECUTION_FIELDS
            },
        },
        "authority": {
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
        },
        "known_boundary": (
            "R12 exact authority permits one digest-bound reuse of immutable "
            "R11 raw candidates and zero new embedding/model/network calls. "
            "R12 adds constant route identity, structural case-independent "
            "ClauseOwnershipDecision v3, GoverningPriceHeadProof v2 and "
            "connector-proof-identity source-to-compiled bindings. "
            "It grants no external capture, 4B embedding, reranker, Evidence, "
            "report or product authority."
        ),
        "policy_digest": r12_policy.get("result_digest"),
    }
    return {**body, "result_digest": canonical_digest(body)}


_R12_AUTHORITY_KEYS = frozenset(
    {
        "03B_R12_execution_consumed",
        "03C_external_capture_authorized",
        "03D_4B_embedding_authorized",
        "03D_reranker_authorized",
        "candidate_decision_authorized",
        "evidence_promotion_authorized",
        "proved_information_boundary_authorized",
        "G3_pass",
        "S1_pass",
        "S2_pass",
        "S3_pass",
        "report_quality_pass",
        "product_acceptance",
        "publication",
        "release_ready",
    }
)
_R12_PUBLIC_BINDING_IDS = frozenset(
    set(EXPECTED_BOUND_INPUT_IDS)
    | {
        "R12_policy",
        "attempt_consumption_receipt",
        "git_identity",
        "disk_capacity_preflight",
    }
)
_R12_TRANSFORMATION_SUMMARY_KEYS = frozenset(
    {
        "binding_count",
        "accepted_binding_count",
        "binding_set_digest",
        "unbound_source_family_count",
        "unbound_source_family_ids",
        "unbound_complete_source_family_count",
        "unbound_complete_source_family_ids",
        "unbound_partial_source_family_count",
        "compiled_complete_without_source_antecedent_count",
        "compiled_complete_without_source_antecedent_ids",
        "failed_binding_count",
        "failed_complete_binding_count",
        "proof_rebind_failure_count",
        "source_governing_nominal_head_partial_count",
        "compiled_governing_nominal_head_partial_count",
        "source_clause_ownership_decision_counts",
        "compiled_clause_ownership_decision_counts",
        "complete_transformation_coverage_pass",
    }
)


def _validate_private_transformation_surface_r12(
    *,
    bindings: Any,
    summary: Any,
    target_id: str,
) -> None:
    _require(
        isinstance(bindings, Sequence)
        and not isinstance(bindings, (str, bytes)),
        f"dell_03B_R12_private_transformation_bindings_invalid:{target_id}",
    )
    rows: list[dict[str, Any]] = []
    for raw_binding in bindings:
        _require(
            isinstance(raw_binding, Mapping),
            f"dell_03B_R12_private_transformation_binding_not_mapping:{target_id}",
        )
        rows.append(
            validate_frame_transformation_binding_record_r12(raw_binding)
        )
    summary_row = _exact_mapping(
        summary,
        _R12_TRANSFORMATION_SUMMARY_KEYS,
        f"dell_03B_R12_private_transformation_summary:{target_id}",
    )
    binding_ids = [str(row["binding_id"]) for row in rows]
    unbound_ids = list(summary_row["unbound_source_family_ids"] or ())
    unbound_complete_ids = list(
        summary_row["unbound_complete_source_family_ids"] or ()
    )
    compiled_without_source_ids = list(
        summary_row["compiled_complete_without_source_antecedent_ids"] or ()
    )
    failed_rows = [
        row for row in rows if row.get("binding_accepted") is not True
    ]
    expected_set_digest = canonical_digest(
        sorted(rows, key=lambda row: str(row["binding_id"]))
    )
    _require(
        len(binding_ids) == len(set(binding_ids))
        and summary_row["binding_count"] == len(rows)
        and summary_row["accepted_binding_count"]
        == len(rows) - len(failed_rows)
        and summary_row["failed_binding_count"] == len(failed_rows)
        and summary_row["binding_set_digest"] == expected_set_digest
        and summary_row["proof_rebind_failure_count"]
        == sum(bool(row.get("proof_rebind_flags")) for row in failed_rows)
        and summary_row["unbound_source_family_count"] == len(unbound_ids)
        and summary_row["unbound_complete_source_family_count"]
        == len(unbound_complete_ids)
        and summary_row["unbound_partial_source_family_count"]
        == len(set(unbound_ids) - set(unbound_complete_ids))
        and summary_row[
            "compiled_complete_without_source_antecedent_count"
        ]
        == len(compiled_without_source_ids)
        and all(
            isinstance(summary_row[key], int) and summary_row[key] >= 0
            for key in (
                "failed_complete_binding_count",
                "source_governing_nominal_head_partial_count",
                "compiled_governing_nominal_head_partial_count",
            )
        )
        and all(
            isinstance(summary_row[key], Mapping)
            and all(
                isinstance(count, int) and count >= 0
                for count in summary_row[key].values()
            )
            for key in (
                "source_clause_ownership_decision_counts",
                "compiled_clause_ownership_decision_counts",
            )
        )
        and isinstance(
            summary_row["complete_transformation_coverage_pass"],
            bool,
        ),
        f"dell_03B_R12_private_transformation_summary_invalid:{target_id}",
    )


def _exact_mapping(
    value: Any,
    keys: frozenset[str],
    code: str,
) -> dict[str, Any]:
    _require(isinstance(value, Mapping), f"{code}_not_mapping")
    result = dict(value)
    _require(set(result) == keys, f"{code}_unknown_or_missing_key")
    return result


def _public_input_bindings_r12(value: Any) -> dict[str, Any]:
    bindings = _exact_mapping(
        value,
        _R12_PUBLIC_BINDING_IDS,
        "dell_03B_R12_public_input_bindings",
    )
    output: dict[str, Any] = {}
    for binding_id, raw in bindings.items():
        if binding_id == "git_identity":
            row = _exact_mapping(
                raw,
                r7._GIT_IDENTITY_KEYS,  # noqa: SLF001
                "dell_03B_R12_public_git_identity",
            )
            _require(
                row.get("branch") == BRANCH
                and all(
                    bool(re.fullmatch(r"[0-9a-f]{40}", str(row.get(key) or "")))
                    for key in (
                        "head",
                        "head_tree",
                        "upstream",
                        "implementation_commit",
                        "implementation_tree",
                    )
                )
                and row.get("upstream_equal") is True
                and row.get("clean") is True
                and row.get("authority_parent_exact") is True
                and row.get("authority_commit_changed_paths") == [POLICY_REF],
                "dell_03B_R12_public_git_identity_value_invalid",
            )
            output[binding_id] = row
        elif binding_id == "disk_capacity_preflight":
            row = _exact_mapping(
                raw,
                r7._DISK_PREFLIGHT_KEYS,  # noqa: SLF001
                "dell_03B_R12_public_disk_preflight",
            )
            _require(
                isinstance(row.get("free_bytes"), int)
                and row.get("free_bytes") >= MIN_FREE_BYTES_BEFORE_ATTEMPT
                and row.get("minimum_free_bytes")
                == MIN_FREE_BYTES_BEFORE_ATTEMPT,
                "dell_03B_R12_public_disk_preflight_value_invalid",
            )
            output[binding_id] = row
        else:
            _require(
                isinstance(raw, Mapping),
                f"dell_03B_R12_public_binding_not_mapping:{binding_id}",
            )
            row = dict(raw)
            _require(
                {"ref", "sha256"}.issubset(row)
                and set(row).issubset(r7._STANDARD_BINDING_KEYS),  # noqa: SLF001
                f"dell_03B_R12_public_binding_unknown_or_missing_key:{binding_id}",
            )
            _require(
                bool(str(row.get("ref") or "").strip())
                and bool(re.fullmatch(r"[0-9a-f]{64}", str(row.get("sha256") or "")))
                and (
                    "result_digest" not in row
                    or bool(
                        re.fullmatch(
                            r"[0-9a-f]{64}",
                            str(row.get("result_digest") or ""),
                        )
                    )
                ),
                f"dell_03B_R12_public_binding_value_invalid:{binding_id}",
            )
            output[binding_id] = row
    return output


def build_dell_report_internal_chain_ceiling_r12_public_projection(
    *,
    private_result: Mapping[str, Any],
    private_ref: str,
    private_sha256: str,
) -> dict[str, Any]:
    private = _exact_mapping(
        private_result,
        r7._PRIVATE_RESULT_KEYS,  # noqa: SLF001
        "dell_03B_R12_private_result",
    )
    _require(
        private.get("schema_version") == PRIVATE_RESULT_SCHEMA_VERSION
        and private.get("attempt_id") == ATTEMPT_ID
        and private.get("status")
        == "dell_03B_R12_route_clause_governing_price_connector_proof_ceiling_executed"
        and private.get("case_key") == "DELL"
        and bool(
            re.fullmatch(
                r"[0-9a-f]{40}",
                str(private.get("prepared_from_commit") or ""),
            )
        )
        and all(
            bool(re.fullmatch(r"[0-9a-f]{64}", str(private.get(key) or "")))
            for key in (
                "raw_execution_sha256",
                "raw_execution_projection_digest",
                "validated_execution_digest",
                "policy_digest",
            )
        )
        and _self_digest(private),
        "dell_03B_R12_private_projection_identity_invalid",
    )
    _require(
        private_ref == PRIVATE_REF
        and bool(re.fullmatch(r"[0-9a-f]{64}", private_sha256)),
        "dell_03B_R12_private_projection_binding_invalid",
    )
    try:
        target_results = []
        for raw_row in private.get("target_results") or ():
            _require(
                isinstance(raw_row, Mapping),
                "dell_03B_R12_public_target_not_mapping",
            )
            row = dict(raw_row)
            transformation_bindings = row.pop(
                "private_frame_transformation_bindings",
                None,
            )
            transformation_summary = row.pop(
                "private_frame_transformation_summary",
                None,
            )
            route_identity = row.pop(
                "private_route_contract_identity",
                None,
            )
            _require(
                isinstance(transformation_bindings, (list, tuple))
                and isinstance(transformation_summary, Mapping),
                "dell_03B_R12_private_transformation_surface_invalid",
            )
            _validate_private_transformation_surface_r12(
                bindings=transformation_bindings,
                summary=transformation_summary,
                target_id=str(row.get("target_id") or ""),
            )
            _require(
                isinstance(route_identity, Mapping),
                "dell_03B_R12_private_route_identity_not_mapping",
            )
            _validate_private_route_identity_r12(
                route_identity,
                target_id=str(row.get("target_id") or ""),
                public_mandatory_ids=list(
                    (row.get("downstream_disposition") or {}).get(
                        "mandatory_external_route_contract_ids_if_authorized"
                    )
                    or ()
                ),
            )
            public_target = r7._public_target_row(row)  # noqa: SLF001
            active_route_ids = list(
                public_target["downstream_disposition"][
                    "mandatory_external_route_contract_ids_if_authorized"
                ]
            )
            public_target.update(
                {
                    "route_contract_identity_digest": route_identity[
                        "route_identity_digest"
                    ],
                    "active_mandatory_external_route_id_set_digest": (
                        canonical_digest(sorted(active_route_ids))
                    ),
                }
            )
            target_results.append(public_target)
    except r7.DellReportInternalChainCeilingR7Error as exc:
        raise DellReportInternalChainCeilingR12Error(
            str(exc).replace("dell_03B_R7_", "dell_03B_R12_", 1)
        ) from exc
    except FrameTransformationBindingR12Error as exc:
        raise DellReportInternalChainCeilingR12Error(str(exc)) from exc
    _require(
        len(target_results) == len(TARGET_IDS)
        and {str(row["target_id"]) for row in target_results} == set(TARGET_IDS),
        "dell_03B_R12_public_target_population_invalid",
    )
    authority = _exact_mapping(
        private["authority"],
        _R12_AUTHORITY_KEYS,
        "dell_03B_R12_public_authority",
    )
    _require(
        authority.get("03B_R12_execution_consumed") is True
        and all(
            authority.get(key) is False
            for key in _R12_AUTHORITY_KEYS - {"03B_R12_execution_consumed"}
        ),
        "dell_03B_R12_public_authority_value_invalid",
    )
    body = {
        "schema_version": PUBLIC_RESULT_SCHEMA_VERSION,
        "status": private["status"],
        "attempt_id": private["attempt_id"],
        "recorded_at": private["recorded_at"],
        "prepared_from_commit": private["prepared_from_commit"],
        "case_key": private["case_key"],
        "input_bindings": _public_input_bindings_r12(private["input_bindings"]),
        "runtime_registry": _exact_mapping(
            private["runtime_registry"],
            r7._RUNTIME_REGISTRY_KEYS,  # noqa: SLF001
            "dell_03B_R12_public_runtime_registry",
        ),
        "raw_execution_sha256": private["raw_execution_sha256"],
        "raw_execution_projection_digest": private[
            "raw_execution_projection_digest"
        ],
        "validated_execution_digest": private["validated_execution_digest"],
        "execution_summary": _exact_mapping(
            private["execution_summary"],
            r7._EXECUTION_SUMMARY_KEYS,  # noqa: SLF001
            "dell_03B_R12_public_execution_summary",
        ),
        "target_results": target_results,
        "summary": _exact_mapping(
            private["summary"],
            r7._SUMMARY_KEYS,  # noqa: SLF001
            "dell_03B_R12_public_summary",
        ),
        "private_result_ref": private_ref,
        "private_result_sha256": private_sha256,
        "private_result_digest": private["result_digest"],
        "authority": authority,
        "known_boundary": private["known_boundary"],
        "policy_digest": private["policy_digest"],
    }
    validate_r12_public_tree(body)
    return {**body, "result_digest": canonical_digest(body)}


def validate_r12_public_tree(value: Any) -> None:
    validate_public_scalar_tree_r8(
        value,
        target_ids=frozenset(TARGET_IDS),
        attempt_id=ATTEMPT_ID,
    )
