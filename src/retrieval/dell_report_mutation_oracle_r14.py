from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from typing import Any, Mapping, Sequence

from .dell_report_r14_common import (
    canonical_digest,
    canonical_json_bytes,
    domain_rows_digest,
    require,
    require_identifier,
    require_sha256,
    validate_result_digest,
    with_result_digest,
)


CRITICAL_MUTATION_MANIFEST_SCHEMA = (
    "fin_ia_dell_03B_R14_critical_mutation_manifest_v1_0"
)
CRITICAL_MUTATION_KILL_RECEIPT_SCHEMA = (
    "fin_ia_dell_03B_R14_critical_mutation_kill_receipt_v1_0"
)
MUTATION_GENERATOR_VERSION = "R14_critical_mutation_generator_v1"
MUTATION_EXECUTION_PROTOCOL = "R14_bound_mutation_subprocess_v1"
ACTUAL_MUTATION_OBSERVATION_PROTOCOL = (
    "R14_actual_production_mutation_observation_v2"
)
EXACT_MUTATION_PATCH_SCHEMA = "fin_ia_dell_03B_R14_exact_mutation_patch_v1_0"
MUTATION_PATCH_CONTRACT_SCHEMA = (
    "fin_ia_dell_03B_R14_mutation_patch_contract_v1_0"
)
_HEX40 = re.compile(r"[0-9a-f]{40}")
_EXECUTION_SEAL = object()
_INJECTED_FIXTURE_CONSUMER_NODE = (
    "tests/test_dell_report_mutation_oracle_r14.py::"
    "test_r14_injected_operator_fixture_is_consumed_by_oracle_process"
)
_HANDLER_DEPENDENCY_PATHS = (
    "src/retrieval/dell_report_mutation_oracle_r14.py",
    "tests/test_dell_report_mutation_oracle_r14.py",
    "tests/test_dell_report_population_manifest_r14.py",
    "tests/test_dell_report_decision_vector_r14.py",
    "tests/test_dell_report_structural_graph_r14.py",
    "tests/test_dell_report_target_compiler_r14.py",
    "tests/test_dell_report_transformation_r14.py",
    "tests/test_dell_report_reconciliation_r14.py",
    "tests/test_dell_report_runner_r14.py",
    "tests/test_dell_report_transaction_r14.py",
)
_MISSING_VALUE_DIGEST = hashlib.sha256(
    b"FIN_IA_R14_EXACT_MUTATION_PATCH_MISSING_VALUE\0"
).hexdigest()


def _patch_contract(
    *,
    target_schema: str,
    mutation_relation: str,
    artifact_relation: str,
    shapes: Sequence[tuple[str, str]],
) -> dict[str, Any]:
    body = {
        "schema_version": MUTATION_PATCH_CONTRACT_SCHEMA,
        "target_schema": target_schema,
        "mutation_relation": mutation_relation,
        "artifact_relation": artifact_relation,
        "exact_change_count": len(shapes),
        "exact_change_shapes": [
            {"operation": operation, "json_pointer": pointer}
            for operation, pointer in shapes
        ],
    }
    return with_result_digest(body)


@dataclass(frozen=True, init=False)
class MutationExecutionReportR14:
    observations: tuple[Mapping[str, Any], ...]
    execution_group_receipts: tuple[Mapping[str, Any], ...]
    execution_root: str
    _seal: object = field(repr=False, compare=False)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs
        raise TypeError(
            "MutationExecutionReportR14 is minted only by "
            "execute_critical_mutation_suite_r14"
        )

    @classmethod
    def _mint(
        cls,
        *,
        observations: tuple[Mapping[str, Any], ...],
        execution_group_receipts: tuple[Mapping[str, Any], ...],
        execution_root: str,
        seal: object,
    ) -> "MutationExecutionReportR14":
        require(seal is _EXECUTION_SEAL, "R14_mutation_execution_mint_forbidden")
        instance = object.__new__(cls)
        object.__setattr__(instance, "observations", observations)
        object.__setattr__(instance, "execution_group_receipts", execution_group_receipts)
        object.__setattr__(instance, "execution_root", execution_root)
        object.__setattr__(instance, "_seal", seal)
        return instance

_FAMILY_CONTRACT = {
    "population": (
        "R13-P1-INDEPENDENT-INPUT-POPULATION-BIJECTION",
        "independent_population_or_vector_rebuilder",
        "P1",
    ),
    "authority": (
        "R14-AUTHORITY-TOPOLOGY",
        "lifecycle_or_formal_preflight",
        "P1",
    ),
    "event": (
        "R13-P2-FLAT-FRAME-CROSS-EVENT-ROLE-UNION",
        "structural_graph_or_target_topology",
        "P2",
    ),
    "price": (
        "R13-P2-CONNECTOR-ENUMERATED-GOVERNING-PRICE-HEAD",
        "price_graph_or_target_topology",
        "P2",
    ),
    "transformation": (
        "R14-TRANSFORMATION-PRESERVATION",
        "extraction_or_transformation_gate",
        "P2",
    ),
    "encoding_error": (
        "R14-DECISION-VECTOR-BIJECTION",
        "independent_decision_vector_rebuilder",
        "P1",
    ),
    "transaction": (
        "R14-WINDOWS-ATOMIC-TRANSACTION",
        "transaction_reader_or_recovery_preflight",
        "P1",
    ),
    "privacy_route": (
        "R14-PUBLIC-PROJECTION-ROUTE",
        "privacy_or_route_validator",
        "P1",
    ),
    "positive_protection": (
        "R14-POSITIVE-FAMILY-PROTECTION",
        "structural_graph_or_target_topology",
        "P2",
    ),
}

TRANSACTION_HARD_EXIT_BOUNDARIES = (
    "before_reservation",
    "after_reservation_write_before_flush",
    "after_reservation_flush_before_close",
    "after_reservation_flush",
    "after_staging_create",
    "after_artifact_0_write_before_flush",
    "after_artifact_0_flush_before_close",
    "after_artifact_flush:0",
    "after_artifact_rename:0",
    "after_artifact_1_write_before_flush",
    "after_artifact_1_flush_before_close",
    "after_artifact_flush:1",
    "after_artifact_rename:1",
    "after_manifest_write_before_flush",
    "after_manifest_flush_before_close",
    "after_manifest_flush",
    "after_manifest_rename",
    "after_marker_write_before_flush",
    "after_marker_flush_before_close",
    "after_marker_flush",
    "after_marker_rename",
    "before_publish_rename",
    "after_publish_rename",
)


def _operator_oracle_kind(family: str, operator: str) -> str:
    if (
        family == "transaction"
        and operator == "kill_at_each_write_flush_manifest_marker_rename_boundary"
    ) or (family == "positive_protection" and operator == "irrelevant_surface_substitution"):
        return "INVARIANT_PROTECTED"
    if family in {"transformation", "positive_protection"}:
        return "MUTATION_DETECTED_OR_DEGRADED"
    if family == "event" and operator == "known_to_nonce_predicate":
        return "MUTATION_DETECTED_OR_DEGRADED"
    return "MUTANT_REJECTED"


_PRODUCTION_MUTATION_CONTRACT_BY_OPERATOR: dict[
    tuple[str, str], tuple[str, str, str]
] = {
    **{
        ("population", operator): (
            "validate_input_population_manifest_r14",
            "src/retrieval/dell_report_population_manifest_r14.py",
            "DellReportR14ContractError::R14_",
        )
        for operator in (
            "delete_cell",
            "duplicate_cell",
            "move_cell",
            "resign_all_derived_surfaces",
            "replace_manifest_index_or_input_digest",
        )
    },
    ("authority", "replace_B_commitment"): (
        "mint_formal_transaction_authority_r14",
        "src/retrieval/dell_report_transaction_r14.py",
        "DellReportR14ContractError::R14_",
    ),
    ("authority", "change_I_B_A_P_parent_or_path"): (
        "mint_formal_transaction_authority_r14",
        "src/retrieval/dell_report_transaction_r14.py",
        "DellReportR14ContractError::R14_",
    ),
    ("authority", "feed_preview_vector_into_formal_compiler"): (
        "run_formal_recompute_and_compare_r14",
        "src/retrieval/dell_report_runner_r14.py",
        "DellReportR14ContractError::R14_formal_compiler_input_envelope_forbidden_preview_input",
    ),
    **{
        ("event", operator): (
            "validate_event_argument_graph_r14",
            "src/retrieval/dell_report_graph_schema_r14.py",
            "DellReportR14ContractError::R14_",
        )
        for operator in (
            "copy_material_role_across_shared_subject",
            "different_owner_or_period",
            "object_list_to_event",
        )
    },
    ("event", "known_to_nonce_predicate"): (
        "build_event_argument_graph_r14",
        "src/retrieval/dell_report_structural_graph_r14.py",
        "GraphOracle::KNOWN_TO_NONCE_PREDICATE_DEGRADED",
    ),
    **{
        ("price", operator): (
            "build_price_attachment_graph_r14",
            "src/retrieval/dell_report_price_graph_r14.py",
            f"PriceOracle::PROVED_TO_UNPROVED::{operator}",
        )
        for operator in (
            "known_to_nonce_higher_head_or_link",
            "direct_product_to_service_contract",
            "multi_head_or_multi_price",
        )
    },
    ("price", "path_rebind"): (
        "validate_price_attachment_graph_r14",
        "src/retrieval/dell_report_graph_schema_r14.py",
        "DellReportR14ContractError::R14_",
    ),
    **{
        ("transformation", operator): (
            "build_graph_transformation_receipt_r14",
            "src/retrieval/dell_report_transformation_r14.py",
            "TransformationOracle::",
        )
        for operator in (
            "event_node_role_period_head_or_path_add_delete_rebind",
            "common_mode_wrong_graph",
        )
    },
    **{
        ("encoding_error", operator): (
            "rebuild_decision_vector_r14",
            "src/retrieval/dell_report_decision_vector_rebuilder_r14.py",
            "DellReportR14ContractError::R14_",
        )
        for operator in ("bit_flip", "nonzero_padding", "wrong_endian", "C_null_topology")
    },
    **{
        ("encoding_error", operator): (
            "build_decision_vector_receipt_r14",
            "src/retrieval/dell_report_decision_vector_r14.py",
            "DellReportR14ContractError::R14_",
        )
        for operator in ("orphan_or_N_detail", "valid_ambiguity_to_E")
    },
    ("transaction", "kill_at_each_write_flush_manifest_marker_rename_boundary"): (
        "publish_atomic_attempt_r14",
        "src/retrieval/dell_report_transaction_r14.py",
        "TransactionOracle::kill_at_each_write_flush_manifest_marker_rename_boundary::",
    ),
    ("transaction", "collision"): (
        "publish_atomic_attempt_r14",
        "src/retrieval/dell_report_transaction_r14.py",
        "TransactionOracle::collision::default",
    ),
    ("transaction", "partial_staging"): (
        "publish_atomic_attempt_r14",
        "src/retrieval/dell_report_transaction_r14.py",
        "TransactionOracle::partial_staging::default",
    ),
    ("privacy_route", "inject_private_ID_text_or_locator"): (
        "validate_public_reconciliation_projection_r14",
        "src/retrieval/dell_report_reconciliation_r14.py",
        "DellReportR14ContractError::R14_public_projection_row_keyset_invalid",
    ),
    ("privacy_route", "route_omission_or_rebind"): (
        "project_public_reconciliation_r14",
        "src/retrieval/dell_report_reconciliation_r14.py",
        "DellReportR14ContractError::R14_",
    ),
    ("positive_protection", "direct_price_structure_damage"): (
        "compile_target_decisions_r14",
        "src/retrieval/dell_report_target_compiler_r14.py",
        "TargetCompiler::ASP_C_TO_P",
    ),
    ("positive_protection", "object_list_structure_damage"): (
        "build_event_argument_graph_r14",
        "src/retrieval/dell_report_structural_graph_r14.py",
        "GraphOracle::OBJECT_LIST_PROOF_REMOVED",
    ),
    ("positive_protection", "supplier_family_structure_damage"): (
        "compile_target_decisions_r14",
        "src/retrieval/dell_report_target_compiler_r14.py",
        "TargetCompiler::HBM_C_TO_P",
    ),
    ("positive_protection", "irrelevant_surface_substitution"): (
        "compile_target_decisions_r14",
        "src/retrieval/dell_report_target_compiler_r14.py",
        "TargetCompiler::IRRELEVANT_SURFACE_C_PROTECTED",
    ),
}


_PATCH_CONTRACT_BY_OPERATOR: dict[tuple[str, str], Mapping[str, Any]] = {
    ("population", "delete_cell"): _patch_contract(
        target_schema="input_population_manifest",
        mutation_relation="DATA_INPUT",
        artifact_relation="BASELINE_ACCEPTS_MUTANT_REJECTS",
        shapes=(("REPLACE", "/result_digest"), ("REMOVE", "/source_canonical_order/1")),
    ),
    ("population", "duplicate_cell"): _patch_contract(
        target_schema="input_population_manifest",
        mutation_relation="DATA_INPUT",
        artifact_relation="BASELINE_ACCEPTS_MUTANT_REJECTS",
        shapes=(("ADD", "/object_canonical_order/2"), ("REPLACE", "/result_digest")),
    ),
    ("population", "move_cell"): _patch_contract(
        target_schema="input_population_manifest",
        mutation_relation="DATA_INPUT",
        artifact_relation="BASELINE_ACCEPTS_MUTANT_REJECTS",
        shapes=(
            ("REPLACE", "/result_digest"),
            ("REPLACE", "/source_canonical_order/0/manifest_index"),
            ("REPLACE", "/source_canonical_order/1/manifest_index"),
        ),
    ),
    ("population", "replace_manifest_index_or_input_digest"): _patch_contract(
        target_schema="input_population_manifest",
        mutation_relation="DATA_INPUT",
        artifact_relation="BASELINE_ACCEPTS_MUTANT_REJECTS",
        shapes=(
            ("REPLACE", "/object_canonical_order/0/input_digest"),
            ("REPLACE", "/result_digest"),
        ),
    ),
    ("population", "resign_all_derived_surfaces"): _patch_contract(
        target_schema="input_population_manifest",
        mutation_relation="DATA_INPUT",
        artifact_relation="BASELINE_ACCEPTS_MUTANT_REJECTS",
        shapes=(
            ("REPLACE", "/manifest_root"),
            ("REPLACE", "/result_digest"),
            ("REPLACE", "/source_canonical_order/0/input_digest"),
            ("REPLACE", "/source_keyset_digest"),
        ),
    ),
    **{
        ("encoding_error", operator): _patch_contract(
            target_schema="decision_vector_production_input",
            mutation_relation="DATA_INPUT",
            artifact_relation="BASELINE_ACCEPTS_MUTANT_REJECTS",
            shapes=(
                ("REPLACE", "/receipt/outcome_bytes_hex"),
                ("REPLACE", "/receipt/result_digest"),
            ),
        )
        for operator in ("bit_flip", "nonzero_padding", "wrong_endian")
    },
    ("encoding_error", "C_null_topology"): _patch_contract(
        target_schema="decision_vector_production_input",
        mutation_relation="DATA_INPUT",
        artifact_relation="BASELINE_ACCEPTS_MUTANT_REJECTS",
        shapes=(
            ("REMOVE", "/details_by_manifest_index/0"),
            ("REPLACE", "/receipt_detail_count"),
            ("REPLACE", "/receipt_detail_root"),
            ("REPLACE", "/receipt_result_digest"),
        ),
    ),
    ("encoding_error", "orphan_or_N_detail"): _patch_contract(
        target_schema="decision_vector_production_input",
        mutation_relation="DATA_INPUT",
        artifact_relation="BASELINE_ACCEPTS_MUTANT_REJECTS",
        shapes=(("ADD", "/cells/2/detail/author_note"),),
    ),
    ("encoding_error", "valid_ambiguity_to_E"): _patch_contract(
        target_schema="decision_vector_production_input",
        mutation_relation="DATA_INPUT",
        artifact_relation="BASELINE_ACCEPTS_MUTANT_REJECTS",
        shapes=(
            ("REMOVE", "/cells/1/detail/candidate_proof_ids"),
            ("REMOVE", "/cells/1/detail/graph_digest"),
            ("REMOVE", "/cells/1/detail/limitations"),
            ("ADD", "/cells/1/detail/malformed_input_key"),
            ("ADD", "/cells/1/detail/typed_error_code"),
            ("REPLACE", "/cells/1/outcome"),
        ),
    ),
    ("authority", "replace_B_commitment"): _patch_contract(
        target_schema="formal_transaction_authority_input",
        mutation_relation="CONTROL_FAULT",
        artifact_relation="BASELINE_ACCEPTS_MUTANT_REJECTS",
        shapes=(
            ("REPLACE", "/canonical_serializer_identity"),
            ("REPLACE", "/result_digest"),
        ),
    ),
    ("authority", "change_I_B_A_P_parent_or_path"): _patch_contract(
        target_schema="formal_transaction_authority_input",
        mutation_relation="CONTROL_FAULT",
        artifact_relation="BASELINE_ACCEPTS_MUTANT_REJECTS",
        shapes=(("REPLACE", "/preformal_audit_path"),),
    ),
    ("authority", "feed_preview_vector_into_formal_compiler"): _patch_contract(
        target_schema="formal_compiler_input_envelope",
        mutation_relation="CONTROL_FAULT",
        artifact_relation="BASELINE_ACCEPTS_MUTANT_REJECTS",
        shapes=(("ADD", "/preview_vector"),),
    ),
    ("event", "copy_material_role_across_shared_subject"): _patch_contract(
        target_schema="event_argument_graph",
        mutation_relation="STRUCTURAL_OUTPUT",
        artifact_relation="BASELINE_ACCEPTS_MUTANT_REJECTS",
        shapes=(("REPLACE", "/copied_role_edge"),),
    ),
    ("event", "different_owner_or_period"): _patch_contract(
        target_schema="event_argument_graph",
        mutation_relation="STRUCTURAL_OUTPUT",
        artifact_relation="BASELINE_ACCEPTS_MUTANT_REJECTS",
        shapes=(("REPLACE", "/assertion_owner"),),
    ),
    ("event", "known_to_nonce_predicate"): _patch_contract(
        target_schema="structural_raw_text_input",
        mutation_relation="DATA_INPUT",
        artifact_relation="BASELINE_PROVED_MUTANT_DEGRADES",
        shapes=(("REPLACE", "/raw_text"),),
    ),
    ("event", "object_list_to_event"): _patch_contract(
        target_schema="event_argument_graph",
        mutation_relation="STRUCTURAL_OUTPUT",
        artifact_relation="BASELINE_ACCEPTS_MUTANT_REJECTS",
        shapes=(("ADD", "/events/1"),),
    ),
    **{
        ("price", operator): _patch_contract(
            target_schema="price_production_input",
            mutation_relation="DATA_INPUT",
            artifact_relation="BASELINE_PROVED_MUTANT_DEGRADES",
            shapes=(("REPLACE", "/raw_text"),),
        )
        for operator in (
            "known_to_nonce_higher_head_or_link",
            "direct_product_to_service_contract",
            "multi_head_or_multi_price",
        )
    },
    ("price", "path_rebind"): _patch_contract(
        target_schema="price_production_input",
        mutation_relation="STRUCTURAL_OUTPUT",
        artifact_relation="BASELINE_ACCEPTS_MUTANT_REJECTS",
        shapes=(("REPLACE", "/product_mention_ids/0"),),
    ),
    ("transformation", "event_node_role_period_head_or_path_add_delete_rebind"): _patch_contract(
        target_schema="graph_transformation_input",
        mutation_relation="STRUCTURAL_OUTPUT",
        artifact_relation="BASELINE_PROVED_MUTANT_DEGRADES",
        shapes=(("REPLACE", "/quantity_destination_node_id"),),
    ),
    ("transformation", "common_mode_wrong_graph"): _patch_contract(
        target_schema="graph_transformation_input",
        mutation_relation="CONTROL_FAULT",
        artifact_relation="BASELINE_PROVED_MUTANT_DEGRADES",
        shapes=(
            ("REPLACE", "/compiled_graph_valid"),
            ("REPLACE", "/source_graph_valid"),
        ),
    ),
    ("transaction", "kill_at_each_write_flush_manifest_marker_rename_boundary"): _patch_contract(
        target_schema="transaction_control_input",
        mutation_relation="CONTROL_FAULT",
        artifact_relation="FILESYSTEM_INVARIANT_OR_BOUNDED_DELTA",
        shapes=(("REPLACE", "/boundary_hook"),),
    ),
    ("transaction", "collision"): _patch_contract(
        target_schema="transaction_control_input",
        mutation_relation="CONTROL_FAULT",
        artifact_relation="FILESYSTEM_INVARIANT_OR_BOUNDED_DELTA",
        shapes=(("REPLACE", "/publish_ordinal"),),
    ),
    ("transaction", "partial_staging"): _patch_contract(
        target_schema="transaction_control_input",
        mutation_relation="CONTROL_FAULT",
        artifact_relation="FILESYSTEM_INVARIANT_OR_BOUNDED_DELTA",
        shapes=(("REPLACE", "/boundary_hook"),),
    ),
    ("privacy_route", "inject_private_ID_text_or_locator"): _patch_contract(
        target_schema="public_projection_input",
        mutation_relation="DATA_INPUT",
        artifact_relation="BASELINE_ACCEPTS_MUTANT_REJECTS",
        shapes=(
            ("REPLACE", "/result_digest"),
            ("ADD", "/target_lane_rows/0/locator"),
            ("ADD", "/target_lane_rows/0/source_record_id"),
            ("ADD", "/target_lane_rows/0/text"),
        ),
    ),
    ("privacy_route", "route_omission_or_rebind"): _patch_contract(
        target_schema="reconciliation_projection_input",
        mutation_relation="DATA_INPUT",
        artifact_relation="BASELINE_ACCEPTS_MUTANT_REJECTS",
        shapes=(
            ("REPLACE", "/receipt_binding_root"),
            ("REPLACE", "/result_digest"),
            ("REPLACE", "/route_registry_digest"),
            ("REPLACE", "/target_lane_rows/0/route_disposition"),
            ("REPLACE", "/target_lane_rows/1/route_disposition"),
        ),
    ),
    ("positive_protection", "direct_price_structure_damage"): _patch_contract(
        target_schema="target_graph_view",
        mutation_relation="STRUCTURAL_OUTPUT",
        artifact_relation="BASELINE_PROVED_MUTANT_DEGRADES",
        shapes=(("REPLACE", "/price_path_proof"),),
    ),
    ("positive_protection", "object_list_structure_damage"): _patch_contract(
        target_schema="structural_raw_text_input",
        mutation_relation="DATA_INPUT",
        artifact_relation="BASELINE_PROVED_MUTANT_DEGRADES",
        shapes=(("REPLACE", "/raw_text"),),
    ),
    ("positive_protection", "supplier_family_structure_damage"): _patch_contract(
        target_schema="target_graph_view",
        mutation_relation="STRUCTURAL_OUTPUT",
        artifact_relation="BASELINE_PROVED_MUTANT_DEGRADES",
        shapes=(("REMOVE", "/typed_target_bridge_edges/0"),),
    ),
    ("positive_protection", "irrelevant_surface_substitution"): _patch_contract(
        target_schema="metamorphic_raw_text_input",
        mutation_relation="METAMORPHIC_INPUT",
        artifact_relation="SEMANTIC_SIGNATURE_PRESERVED",
        shapes=(("REPLACE", "/raw_text"),),
    ),
}


def _production_mutation_patch_contract(
    *, family: str, operator: str, variant: str
) -> Mapping[str, Any]:
    contract = _PATCH_CONTRACT_BY_OPERATOR.get((family, operator))
    require(
        contract is not None,
        f"R14_mutation_patch_contract_missing:{family}:{operator}",
    )
    if operator == "kill_at_each_write_flush_manifest_marker_rename_boundary":
        require(
            variant in TRANSACTION_HARD_EXIT_BOUNDARIES,
            "R14_mutation_patch_contract_boundary_unknown",
        )
    else:
        require(variant == "default", "R14_mutation_patch_contract_variant_invalid")
    return contract


def _production_mutation_contract(
    *, family: str, operator: str, variant: str
) -> dict[str, str]:
    raw = _PRODUCTION_MUTATION_CONTRACT_BY_OPERATOR.get((family, operator))
    require(raw is not None, f"R14_mutation_production_handler_missing:{family}:{operator}")
    if (
        family == "transaction"
        and operator == "kill_at_each_write_flush_manifest_marker_rename_boundary"
    ):
        require(
            variant in TRANSACTION_HARD_EXIT_BOUNDARIES,
            "R14_mutation_transaction_boundary_unknown",
        )
    else:
        require(variant == "default", "R14_mutation_unexpected_operator_variant")
    oracle, source_path, failure_code_prefix = raw
    return {
        "production_oracle": oracle,
        "production_entry_path": source_path,
        "expected_failure_code_prefix": failure_code_prefix,
    }


def _handler_dependency_sources(
    *, root: Path, production_entry_path: str
) -> tuple[Mapping[str, Any], ...]:
    from .dell_report_transaction_r14 import R14_IMPLEMENTATION_EXACT_PATHS

    root = root.resolve(strict=True)
    relative_paths = tuple(
        sorted(
            set(
                (
                    *_HANDLER_DEPENDENCY_PATHS,
                    *R14_IMPLEMENTATION_EXACT_PATHS,
                    production_entry_path,
                )
            )
        )
    )
    rows: list[Mapping[str, Any]] = []
    for relative_path in relative_paths:
        path = (root / relative_path).resolve(strict=True)
        require(
            path.is_file() and path.is_relative_to(root),
            "R14_mutation_handler_dependency_path_invalid",
        )
        payload = path.read_bytes()
        rows.append(
            {
                "path": relative_path,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    return tuple(rows)


def _handler_dependency_root(rows: Sequence[Mapping[str, Any]]) -> str:
    return domain_rows_digest(
        b"FIN_IA_R14_MUTATION_HANDLER_DEPENDENCY_SOURCES_V1\0",
        (canonical_json_bytes(row) for row in rows),
    )


def _validate_manifest_source_bindings_against_git_r14(
    *,
    manifest: Mapping[str, Any],
    repository_root: Path,
    implementation_commit: str,
    implementation_tree: str,
) -> str:
    root = repository_root.resolve(strict=True)
    require((root / ".git").exists(), "R14_mutation_source_git_repository_missing")
    require(
        bool(_HEX40.fullmatch(implementation_commit))
        and bool(_HEX40.fullmatch(implementation_tree)),
        "R14_mutation_source_git_identity_invalid",
    )
    actual_tree = subprocess.run(
        ["git", "rev-parse", f"{implementation_commit}^{{tree}}"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    require(
        actual_tree == implementation_tree,
        "R14_mutation_source_git_tree_mismatch",
    )
    git_rows: list[Mapping[str, Any]] = []
    for expected in manifest.get("handler_source_rows") or ():
        relative_path = str(expected["path"])
        completed = subprocess.run(
            ["git", "show", f"{implementation_commit}:{relative_path}"],
            cwd=root,
            check=False,
            capture_output=True,
            text=False,
        )
        require(
            completed.returncode == 0,
            f"R14_mutation_source_git_blob_missing:{relative_path}",
        )
        payload = completed.stdout
        git_rows.append(
            {
                "path": relative_path,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    require(
        git_rows == manifest.get("handler_source_rows")
        and _handler_dependency_root(git_rows)
        == manifest.get("handler_source_root"),
        "R14_mutation_source_git_blob_binding_mismatch",
    )
    return _handler_dependency_root(git_rows)


def _json_pointer_escape(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _exact_mutation_changes(
    before: Any,
    after: Any,
    *,
    pointer: str = "",
) -> list[dict[str, Any]]:
    if type(before) is type(after) and isinstance(before, Mapping):
        rows: list[dict[str, Any]] = []
        before_keys = {str(key) for key in before}
        after_keys = {str(key) for key in after}
        for key in sorted(before_keys | after_keys):
            child_pointer = f"{pointer}/{_json_pointer_escape(key)}"
            if key not in before_keys:
                rows.append(
                    {
                        "operation": "ADD",
                        "json_pointer": child_pointer,
                        "before_value_digest": _MISSING_VALUE_DIGEST,
                        "after_value_digest": canonical_digest(after[key]),
                    }
                )
            elif key not in after_keys:
                rows.append(
                    {
                        "operation": "REMOVE",
                        "json_pointer": child_pointer,
                        "before_value_digest": canonical_digest(before[key]),
                        "after_value_digest": _MISSING_VALUE_DIGEST,
                    }
                )
            else:
                rows.extend(
                    _exact_mutation_changes(
                        before[key],
                        after[key],
                        pointer=child_pointer,
                    )
                )
        return rows
    if type(before) is type(after) and isinstance(before, (list, tuple)):
        rows = []
        shared = min(len(before), len(after))
        for index in range(shared):
            rows.extend(
                _exact_mutation_changes(
                    before[index],
                    after[index],
                    pointer=f"{pointer}/{index}",
                )
            )
        for index in range(shared, len(before)):
            rows.append(
                {
                    "operation": "REMOVE",
                    "json_pointer": f"{pointer}/{index}",
                    "before_value_digest": canonical_digest(before[index]),
                    "after_value_digest": _MISSING_VALUE_DIGEST,
                }
            )
        for index in range(shared, len(after)):
            rows.append(
                {
                    "operation": "ADD",
                    "json_pointer": f"{pointer}/{index}",
                    "before_value_digest": _MISSING_VALUE_DIGEST,
                    "after_value_digest": canonical_digest(after[index]),
                }
            )
        return rows
    if before == after and type(before) is type(after):
        return []
    return [
        {
            "operation": "REPLACE",
            "json_pointer": pointer or "/",
            "before_value_digest": canonical_digest(before),
            "after_value_digest": canonical_digest(after),
        }
    ]


def _build_exact_mutation_patch_r14(
    *, target_schema: str, before_input: Any, after_input: Any
) -> dict[str, Any]:
    before_bytes = canonical_json_bytes(before_input)
    after_bytes = canonical_json_bytes(after_input)
    changes = _exact_mutation_changes(before_input, after_input)
    require(changes, "R14_mutation_patch_has_no_control_change")
    require(
        len({row["json_pointer"] for row in changes}) == len(changes),
        "R14_mutation_patch_pointer_not_unique",
    )
    body = {
        "schema_version": EXACT_MUTATION_PATCH_SCHEMA,
        "target_schema": require_identifier(
            target_schema, field="mutation_patch_target_schema"
        ),
        "before_input_sha256": hashlib.sha256(before_bytes).hexdigest(),
        "after_input_sha256": hashlib.sha256(after_bytes).hexdigest(),
        "change_count": len(changes),
        "changes": changes,
    }
    return with_result_digest(body)


def _validate_exact_mutation_patch_r14(
    value: Mapping[str, Any],
    *,
    before_input: Any,
    after_input: Any,
    expected_contract: Mapping[str, Any],
) -> None:
    validate_result_digest(value, code="R14_mutation_patch")
    require(
        set(value)
        == {
            "schema_version",
            "target_schema",
            "before_input_sha256",
            "after_input_sha256",
            "change_count",
            "changes",
            "result_digest",
        }
        and value.get("schema_version") == EXACT_MUTATION_PATCH_SCHEMA,
        "R14_mutation_patch_schema_invalid",
    )
    expected = _build_exact_mutation_patch_r14(
        target_schema=str(value.get("target_schema") or ""),
        before_input=before_input,
        after_input=after_input,
    )
    validate_result_digest(expected_contract, code="R14_mutation_patch_contract")
    require(
        expected_contract.get("schema_version")
        == MUTATION_PATCH_CONTRACT_SCHEMA
        and value == expected
        and value.get("target_schema")
        == expected_contract.get("target_schema")
        and value.get("change_count")
        == expected_contract.get("exact_change_count")
        and [
            {
                "operation": row["operation"],
                "json_pointer": row["json_pointer"],
            }
            for row in value.get("changes") or ()
        ]
        == expected_contract.get("exact_change_shapes"),
        "R14_mutation_patch_actual_diff_or_contract_mismatch",
    )


def _bound_case_payload(
    *, row: Mapping[str, Any], root: Path, node_id: str
) -> dict[str, Any]:
    del node_id
    production_contract = _production_mutation_contract(
        family=str(row["family"]),
        operator=str(row["operator_id"]),
        variant=str(row["operator_variant"]),
    )
    consumer_test_path = root / _INJECTED_FIXTURE_CONSUMER_NODE.split("::", 1)[0]
    require(
        consumer_test_path.is_file(),
        f"R14_mutation_test_node_missing:{_INJECTED_FIXTURE_CONSUMER_NODE}",
    )
    consumer_source_sha256 = hashlib.sha256(consumer_test_path.read_bytes()).hexdigest()
    dependency_sources = _handler_dependency_sources(
        root=root,
        production_entry_path=production_contract["production_entry_path"],
    )
    dependency_root = _handler_dependency_root(dependency_sources)
    require(
        dependency_root == row.get("handler_source_root"),
        "R14_mutation_payload_source_differs_from_frozen_manifest",
    )
    production_entry_source_sha256 = next(
        row["sha256"]
        for row in dependency_sources
        if row["path"] == production_contract["production_entry_path"]
    )
    body = {
        "protocol": MUTATION_EXECUTION_PROTOCOL,
        "case_id": row["case_id"],
        "family": row["family"],
        "operator_id": row["operator_id"],
        "operator_variant": row["operator_variant"],
        "manifest_row_digest": row["row_digest"],
        "manifest_fixture_digest": row["fixture_digest"],
        "target_layer": row["target_layer"],
        "oracle_expectation_type": row["oracle_expectation_type"],
        "expected_oracle": row["expected_typed_failure_or_oracle"],
        "production_mutation_node_id": _INJECTED_FIXTURE_CONSUMER_NODE,
        "production_mutation_source_sha256": consumer_source_sha256,
        "handler_dependency_sources": list(dependency_sources),
        "handler_dependency_root": dependency_root,
        "production_entry_source_sha256": production_entry_source_sha256,
        "mutation_patch_contract": row["mutation_patch_contract"],
        "mutation_patch_contract_digest": row[
            "mutation_patch_contract_digest"
        ],
        **production_contract,
    }
    return {**body, "payload_digest": canonical_digest(body)}


def _execute_bound_case_worker(payload: Mapping[str, Any], *, root: Path) -> dict[str, Any]:
    body = dict(payload)
    payload_digest = body.pop("payload_digest", None)
    require(payload_digest == canonical_digest(body), "R14_mutation_worker_payload_digest_invalid")
    require(body.get("protocol") == MUTATION_EXECUTION_PROTOCOL, "R14_mutation_worker_protocol_invalid")
    operator = str(body["operator_id"])
    variant = str(body["operator_variant"])
    expected_production_contract = _production_mutation_contract(
        family=str(body["family"]),
        operator=operator,
        variant=variant,
    )
    expected_patch_contract = _production_mutation_patch_contract(
        family=str(body["family"]),
        operator=operator,
        variant=variant,
    )
    require(
        all(body.get(key) == value for key, value in expected_production_contract.items()),
        "R14_mutation_worker_production_contract_rebind",
    )
    require(
        body.get("mutation_patch_contract") == expected_patch_contract
        and body.get("mutation_patch_contract_digest")
        == expected_patch_contract.get("result_digest"),
        "R14_mutation_worker_patch_contract_rebind",
    )
    production_node_id = str(body.get("production_mutation_node_id") or "")
    production_path = root / production_node_id.split("::", 1)[0]
    require(
        production_node_id == _INJECTED_FIXTURE_CONSUMER_NODE
        and production_path.is_file()
        and hashlib.sha256(production_path.read_bytes()).hexdigest()
        == body.get("production_mutation_source_sha256"),
        "R14_mutation_worker_production_node_rebind",
    )
    production_entry_relative_path = str(body.get("production_entry_path") or "")
    production_entry_path = root / production_entry_relative_path
    expected_dependency_sources = _handler_dependency_sources(
        root=root,
        production_entry_path=production_entry_relative_path,
    )
    expected_dependency_root = _handler_dependency_root(
        expected_dependency_sources
    )
    require(
        production_entry_path.is_file()
        and body.get("handler_dependency_sources")
        == list(expected_dependency_sources)
        and body.get("handler_dependency_root") == expected_dependency_root
        and body.get("production_entry_source_sha256")
        == hashlib.sha256(production_entry_path.read_bytes()).hexdigest(),
        "R14_mutation_worker_handler_dependency_rebind",
    )
    environment = dict(os.environ)
    environment["FIN_IA_R14_MUTATION_CASE_ID"] = str(body["case_id"])
    environment["FIN_IA_R14_MUTATION_OPERATOR"] = operator
    environment["FIN_IA_R14_MUTATION_VARIANT"] = variant
    environment["FIN_IA_R14_MUTATION_PAYLOAD_DIGEST"] = str(payload_digest)
    source_root = str(root / "src")
    environment["PYTHONPATH"] = (
        source_root
        if not environment.get("PYTHONPATH")
        else source_root + os.pathsep + environment["PYTHONPATH"]
    )
    command = (
        sys.executable,
        "-m",
        "pytest",
        "-q",
        production_node_id,
    )
    started = time.perf_counter_ns()
    with tempfile.TemporaryDirectory(prefix="fin-ia-r14-mut-") as temp_directory:
        payload_path = Path(temp_directory) / "bound-mutation-payload.json"
        observation_path = Path(temp_directory) / "actual-production-observation.json"
        payload_path.write_bytes(canonical_json_bytes(payload))
        environment["FIN_IA_R14_MUTATION_PAYLOAD_PATH"] = str(payload_path)
        environment["FIN_IA_R14_MUTATION_OBSERVATION_PATH"] = str(observation_path)
        completed = subprocess.run(
            command,
            cwd=root,
            env=environment,
            check=False,
            capture_output=True,
            text=False,
        )
        require(
            list(
                _handler_dependency_sources(
                    root=root,
                    production_entry_path=production_entry_relative_path,
                )
            )
            == body.get("handler_dependency_sources"),
            "R14_mutation_worker_source_binding_changed_during_execution",
        )
        actual_observation = (
            json.loads(observation_path.read_text(encoding="utf-8"))
            if observation_path.is_file()
            else None
        )
    duration_ms = max(0, (time.perf_counter_ns() - started) // 1_000_000)
    observation_body = dict(actual_observation or {})
    observation_row_digest = observation_body.pop("row_digest", None)
    mutation_patch = (
        actual_observation.get("mutation_patch")
        if isinstance(actual_observation, dict)
        else None
    )
    mutation_patch_is_bound = False
    if isinstance(actual_observation, dict) and isinstance(mutation_patch, dict):
        try:
            _validate_exact_mutation_patch_r14(
                mutation_patch,
                before_input=actual_observation.get("mutation_input_before"),
                after_input=actual_observation.get("mutation_input_after"),
                expected_contract=expected_patch_contract,
            )
            mutation_patch_is_bound = True
        except (TypeError, ValueError):
            mutation_patch_is_bound = False
    observation_is_bound = (
        isinstance(actual_observation, dict)
        and completed.returncode == 0
        and observation_row_digest == canonical_digest(observation_body)
        and actual_observation.get("protocol")
        == ACTUAL_MUTATION_OBSERVATION_PROTOCOL
        and actual_observation.get("case_id") == body["case_id"]
        and actual_observation.get("family") == body["family"]
        and actual_observation.get("operator_id") == operator
        and actual_observation.get("operator_variant") == variant
        and actual_observation.get("payload_digest") == payload_digest
        and actual_observation.get("production_oracle") == body["production_oracle"]
        and actual_observation.get("production_entry_path")
        == production_entry_relative_path
        and actual_observation.get("production_entry_source_sha256")
        == body.get("production_entry_source_sha256")
        and actual_observation.get("handler_dependency_sources")
        == body.get("handler_dependency_sources")
        and actual_observation.get("handler_dependency_root")
        == expected_dependency_root
        and mutation_patch_is_bound
        and actual_observation.get("mutation_after_input_sha256")
        == mutation_patch.get("after_input_sha256")
        and actual_observation.get("mutation_patch_contract_digest")
        == body.get("mutation_patch_contract_digest")
        and bool(
            re.fullmatch(
                r"[0-9a-f]{64}",
                str(actual_observation.get("production_mutation_spec_digest") or ""),
            )
        )
        and bool(
            re.fullmatch(
                r"[0-9a-f]{64}",
                str(actual_observation.get("before_artifact_digest") or ""),
            )
        )
        and bool(
            re.fullmatch(
                r"[0-9a-f]{64}",
                str(actual_observation.get("after_artifact_digest") or ""),
            )
        )
        and actual_observation.get("production_mutation_spec_digest")
        == canonical_digest(
            {
                "case_id": body["case_id"],
                "family": body["family"],
                "operator_id": operator,
                "operator_variant": variant,
                "production_oracle": body["production_oracle"],
                "production_entry_path": production_entry_relative_path,
                "before_artifact_digest": actual_observation.get(
                    "before_artifact_digest"
                ),
                "after_artifact_digest": actual_observation.get(
                    "after_artifact_digest"
                ),
                "handler_dependency_root": expected_dependency_root,
                "mutation_patch_digest": mutation_patch.get("result_digest"),
                "mutation_after_input_sha256": mutation_patch.get(
                    "after_input_sha256"
                ),
                "mutation_patch_contract_digest": body.get(
                    "mutation_patch_contract_digest"
                ),
            }
        )
    )
    actual_status = (
        str(actual_observation.get("oracle_status"))
        if observation_is_bound
        else "UNEXECUTED"
    )
    killed_is_bound = (
        actual_status == "KILLED"
        and actual_observation.get("oracle_outcome_type")
        == body["oracle_expectation_type"]
        and actual_observation.get("observation_layer") == body["target_layer"]
        and str(actual_observation.get("observed_failure_code") or "").startswith(
            str(body["expected_failure_code_prefix"])
        )
    )
    survived_is_bound = (
        actual_status == "SURVIVED"
        and actual_observation.get("oracle_outcome_type") == "none"
        and actual_observation.get("observation_layer") == "none"
        and actual_observation.get("observed_failure_code") == "none"
    )
    observation_is_bound = observation_is_bound and (
        killed_is_bound or survived_is_bound
    )
    before_digest = (
        str(actual_observation.get("before_artifact_digest"))
        if isinstance(actual_observation, dict)
        else "0" * 64
    )
    after_digest = (
        str(actual_observation.get("after_artifact_digest"))
        if isinstance(actual_observation, dict)
        else "0" * 64
    )
    if observation_is_bound:
        require_sha256(before_digest, field="mutation_actual_before_artifact")
        require_sha256(after_digest, field="mutation_actual_after_artifact")
    worker_status = actual_status if observation_is_bound else "UNEXECUTED"
    receipt = {
        "protocol": MUTATION_EXECUTION_PROTOCOL,
        "case_id": body["case_id"],
        "operator_id": operator,
        "operator_variant": variant,
        "payload_digest": payload_digest,
        "manifest_row_digest": body["manifest_row_digest"],
        "manifest_fixture_digest": body["manifest_fixture_digest"],
        "before_artifact_digest": before_digest,
        "after_artifact_digest": after_digest,
        "production_mutation_node_id": production_node_id,
        "production_mutation_source_sha256": body[
            "production_mutation_source_sha256"
        ],
        "handler_dependency_sources": body["handler_dependency_sources"],
        "handler_dependency_root": body["handler_dependency_root"],
        "production_observation_row_digest": (
            str(observation_row_digest) if observation_row_digest else "0" * 64
        ),
        "production_oracle": (
            str(actual_observation.get("production_oracle"))
            if isinstance(actual_observation, dict)
            else "none"
        ),
        "production_entry_path": (
            str(actual_observation.get("production_entry_path"))
            if observation_is_bound
            else production_entry_relative_path
        ),
        "production_entry_source_sha256": (
            str(actual_observation.get("production_entry_source_sha256"))
            if observation_is_bound
            else str(body["production_entry_source_sha256"])
        ),
        "production_mutation_spec_digest": (
            str(actual_observation.get("production_mutation_spec_digest"))
            if observation_is_bound
            else "0" * 64
        ),
        "mutation_after_input_sha256": (
            str(actual_observation.get("mutation_after_input_sha256"))
            if observation_is_bound
            else "0" * 64
        ),
        "mutation_patch": (
            mutation_patch if observation_is_bound else {}
        ),
        "mutation_patch_contract_digest": (
            str(actual_observation.get("mutation_patch_contract_digest"))
            if observation_is_bound
            else "0" * 64
        ),
        "mutation_input_before": (
            actual_observation.get("mutation_input_before")
            if observation_is_bound
            else None
        ),
        "mutation_input_after": (
            actual_observation.get("mutation_input_after")
            if observation_is_bound
            else None
        ),
        "oracle_outcome_type": (
            str(actual_observation.get("oracle_outcome_type"))
            if isinstance(actual_observation, dict)
            else "none"
        ),
        "oracle_status": worker_status,
        "observation_layer": (
            str(actual_observation["observation_layer"])
            if observation_is_bound
            else "none"
        ),
        "observed_failure_code": (
            str(actual_observation["observed_failure_code"])
            if observation_is_bound
            else "none"
        ),
        "pytest_returncode": completed.returncode,
        "pytest_stdout_sha256": hashlib.sha256(completed.stdout).hexdigest(),
        "pytest_stderr_sha256": hashlib.sha256(completed.stderr).hexdigest(),
        "duration_ms": int(duration_ms),
    }
    return {**receipt, "row_digest": canonical_digest(receipt)}


def _run_bound_case_subprocess(*, payload: Mapping[str, Any], root: Path) -> dict[str, Any]:
    environment = dict(os.environ)
    source_root = str(root / "src")
    environment["PYTHONPATH"] = (
        source_root
        if not environment.get("PYTHONPATH")
        else source_root + os.pathsep + environment["PYTHONPATH"]
    )
    command = (
        sys.executable,
        "-c",
        (
            "import sys;sys.path.insert(0,sys.argv.pop(1));"
            "from retrieval.dell_report_mutation_oracle_r14 import _main;"
            "raise SystemExit(_main(sys.argv))"
        ),
        source_root,
        "--execute-bound-case",
        str(root),
    )
    completed = subprocess.run(
        command,
        cwd=root,
        env=environment,
        input=canonical_json_bytes(payload),
        check=False,
        capture_output=True,
        text=False,
    )
    require(completed.returncode == 0, "R14_mutation_worker_process_failed")
    try:
        parsed = json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("R14_mutation_worker_output_invalid") from exc
    require(isinstance(parsed, dict), "R14_mutation_worker_output_invalid")
    return parsed


def execute_critical_mutation_suite_r14(
    *,
    manifest: Mapping[str, Any],
    requirement_manifest: Mapping[str, Any],
    repository_root: Path,
) -> MutationExecutionReportR14:
    """Execute each frozen mutant against its exact operator-specific node.

    A baseline suite PASS is never copied across the denominator.  Every row
    launches its own isolated worker with the complete operator/variant and
    executable before/after fixture on stdin.  The worker independently
    rebuilds the transition, binds the exact oracle source bytes, runs only
    that oracle, and returns a machine-readable observation.  Only that bound
    observation (never a bare pytest return code) can mint KILLED.
    """
    validate_critical_mutation_manifest_r14(
        manifest, requirement_manifest=requirement_manifest
    )
    root = repository_root.resolve(strict=True)
    _required_operator_registry(requirement_manifest)
    group_receipts: list[Mapping[str, Any]] = []
    observations: list[Mapping[str, Any]] = []
    for row in manifest["case_rows"]:
        operator = str(row["operator_id"])
        variant = str(row["operator_variant"])
        payload = _bound_case_payload(
            row=row,
            root=root,
            node_id=_INJECTED_FIXTURE_CONSUMER_NODE,
        )
        started = time.perf_counter_ns()
        worker = _run_bound_case_subprocess(payload=payload, root=root)
        duration_ms = max(0, (time.perf_counter_ns() - started) // 1_000_000)
        worker_body = dict(worker)
        worker_row_digest = worker_body.pop("row_digest", None)
        require(
            worker_row_digest == canonical_digest(worker_body)
            and worker.get("protocol") == MUTATION_EXECUTION_PROTOCOL
            and worker.get("case_id") == row["case_id"]
            and worker.get("operator_id") == operator
            and worker.get("operator_variant") == variant
            and worker.get("payload_digest") == payload["payload_digest"]
            and worker.get("manifest_row_digest") == row["row_digest"]
            and worker.get("production_mutation_node_id")
            == _INJECTED_FIXTURE_CONSUMER_NODE
            and worker.get("production_mutation_source_sha256")
            == payload["production_mutation_source_sha256"]
            and worker.get("handler_dependency_sources")
            == payload["handler_dependency_sources"]
            and worker.get("handler_dependency_root")
            == payload["handler_dependency_root"]
            and worker.get("mutation_patch_contract_digest")
            == payload["mutation_patch_contract_digest"]
            and worker.get("production_oracle")
            in {payload["production_oracle"], "none"}
            and worker.get("production_entry_path")
            == payload["production_entry_path"],
            "R14_mutation_worker_observation_rebind",
        )
        if worker.get("oracle_status") == "KILLED":
            require_sha256(
                worker.get("before_artifact_digest"),
                field="mutation_actual_before_artifact",
            )
            require_sha256(
                worker.get("after_artifact_digest"),
                field="mutation_actual_after_artifact",
            )
        receipt = {
            "group": str(row["case_id"]),
            "case_id": row["case_id"],
            "operator_id": operator,
            "operator_variant": variant,
            "node_ids": [_INJECTED_FIXTURE_CONSUMER_NODE],
            "protocol": MUTATION_EXECUTION_PROTOCOL,
            "payload_digest": payload["payload_digest"],
            "command_digest": canonical_digest(
                [
                    "retrieval.dell_report_mutation_oracle_r14",
                    "--execute-bound-case",
                    _INJECTED_FIXTURE_CONSUMER_NODE,
                    payload["payload_digest"],
                ]
            ),
            "production_mutation_source_sha256": payload[
                "production_mutation_source_sha256"
            ],
            "handler_dependency_sources": payload[
                "handler_dependency_sources"
            ],
            "handler_dependency_root": payload["handler_dependency_root"],
            "manifest_fixture_digest": row["fixture_digest"],
            "baseline_fixture_digest": worker["before_artifact_digest"],
            "mutated_fixture_digest": worker["after_artifact_digest"],
            "worker_observation_row_digest": worker_row_digest,
            "production_observation_row_digest": worker[
                "production_observation_row_digest"
            ],
            "production_oracle": worker["production_oracle"],
            "production_entry_path": worker["production_entry_path"],
            "production_entry_source_sha256": worker[
                "production_entry_source_sha256"
            ],
            "production_mutation_spec_digest": worker[
                "production_mutation_spec_digest"
            ],
            "mutation_after_input_sha256": worker[
                "mutation_after_input_sha256"
            ],
            "mutation_patch": worker["mutation_patch"],
            "mutation_patch_contract_digest": worker[
                "mutation_patch_contract_digest"
            ],
            "mutation_input_before": worker["mutation_input_before"],
            "mutation_input_after": worker["mutation_input_after"],
            "mutation_input_pair_root": canonical_digest(
                {
                    "before_input_sha256": worker["mutation_patch"].get(
                        "before_input_sha256"
                    ),
                    "after_input_sha256": worker["mutation_patch"].get(
                        "after_input_sha256"
                    ),
                    "mutation_patch_digest": worker["mutation_patch"].get(
                        "result_digest"
                    ),
                    "mutation_patch_contract_digest": worker[
                        "mutation_patch_contract_digest"
                    ],
                }
            ),
            "oracle_outcome_type": worker["oracle_outcome_type"],
            "oracle_status": worker["oracle_status"],
            "observation_layer": worker["observation_layer"],
            "observed_failure_code": worker["observed_failure_code"],
            "returncode": worker["pytest_returncode"],
            "stdout_sha256": worker["pytest_stdout_sha256"],
            "stderr_sha256": worker["pytest_stderr_sha256"],
            "duration_ms": int(duration_ms),
            "verdict": worker["oracle_status"],
        }
        sealed_receipt = {
            **receipt,
            "row_digest": canonical_digest(receipt),
        }
        group_receipts.append(sealed_receipt)
        killed = sealed_receipt["verdict"] == "KILLED"
        observation = {
            "case_id": row["case_id"],
            "observed_verdict": sealed_receipt["verdict"],
            "oracle_outcome_type": (
                row["oracle_expectation_type"] if killed else "none"
            ),
            "observation_layer": row["target_layer"] if killed else "none",
            "observed_failure_code": (
                str(sealed_receipt["observed_failure_code"])
                if killed
                else "none"
            ),
            "duration_ms": sealed_receipt["duration_ms"],
            "execution_group": row["case_id"],
            "execution_group_row_digest": sealed_receipt["row_digest"],
            "case_execution_root": _case_execution_root_from_group_r14(
                group=sealed_receipt,
                manifest_row=row,
            ),
        }
        _validate_observation_group_binding_r14(
            observation=observation,
            group=sealed_receipt,
            manifest_row=row,
        )
        observations.append(observation)
    ordered_groups = tuple(
        sorted(group_receipts, key=lambda value: str(value["case_id"]))
    )
    execution_root = domain_rows_digest(
        b"FIN_IA_R14_CRITICAL_MUTATION_EXECUTION_V1\0",
        (canonical_json_bytes(row) for row in (*ordered_groups, *observations)),
    )
    return MutationExecutionReportR14._mint(
        observations=tuple(observations),
        execution_group_receipts=ordered_groups,
        execution_root=execution_root,
        seal=_EXECUTION_SEAL,
    )


def _required_operator_registry(
    requirement_manifest: Mapping[str, Any],
) -> dict[str, tuple[str, ...]]:
    raw = requirement_manifest.get("critical_operator_families")
    require(isinstance(raw, dict), "R14_mutation_requirement_registry_missing")
    require(set(raw) == set(_FAMILY_CONTRACT), "R14_mutation_family_registry_invalid")
    registry: dict[str, tuple[str, ...]] = {}
    for family, operators in raw.items():
        values = tuple(str(row) for row in operators)
        require(
            bool(values)
            and len(values) == len(set(values))
            and all(bool(require_identifier(row, field="mutation_operator")) for row in values),
            f"R14_mutation_operator_registry_invalid:{family}",
        )
        registry[str(family)] = values
    return registry


def build_default_critical_mutation_manifest_r14(
    *,
    requirement_manifest: Mapping[str, Any],
    author_seed: str,
    generator_identity: str,
) -> dict[str, Any]:
    seed = require_identifier(author_seed, field="mutation_author_seed")
    generator = require_identifier(generator_identity, field="mutation_generator")
    registry = _required_operator_registry(requirement_manifest)
    repository_root = Path(__file__).resolve().parents[2]
    handler_source_rows = _handler_dependency_sources(
        root=repository_root,
        production_entry_path="src/retrieval/dell_report_mutation_oracle_r14.py",
    )
    handler_source_root = _handler_dependency_root(handler_source_rows)
    positive_controls = tuple(requirement_manifest.get("positive_controls") or ())
    require(bool(positive_controls), "R14_mutation_positive_controls_missing")
    rows: list[dict[str, Any]] = []
    for family in sorted(registry):
        finding_id, target_layer, severity = _FAMILY_CONTRACT[family]
        for operator_id in registry[family]:
            variants = (
                TRANSACTION_HARD_EXIT_BOUNDARIES
                if family == "transaction"
                and operator_id
                == "kill_at_each_write_flush_manifest_marker_rename_boundary"
                else ("default",)
            )
            for variant in variants:
                case_id = f"R14-MUT::{family}::{operator_id}::{variant}"
                production_contract = _production_mutation_contract(
                    family=family,
                    operator=operator_id,
                    variant=variant,
                )
                mutation_patch_contract = _production_mutation_patch_contract(
                    family=family,
                    operator=operator_id,
                    variant=variant,
                )
                mutation_patch_contract_digest = mutation_patch_contract[
                    "result_digest"
                ]
                oracle_expectation_type = _operator_oracle_kind(
                    family,
                    operator_id,
                )
                fixture_digest = canonical_digest(
                    {
                        "case_id": case_id,
                        "family": family,
                        "operator_id": operator_id,
                        "operator_variant": variant,
                        "fixture_contract": (
                            "actual_production_baseline_then_exact_operator_mutation_v1"
                        ),
                        "production_handler_node": _INJECTED_FIXTURE_CONSUMER_NODE,
                        "handler_source_root": handler_source_root,
                        "mutation_patch_contract_digest": (
                            mutation_patch_contract_digest
                        ),
                        **production_contract,
                    }
                )
                body = {
                    "case_id": case_id,
                    "requirement_or_finding_id": finding_id,
                    "family": family,
                    "operator_id": operator_id,
                    "operator_version": MUTATION_GENERATOR_VERSION,
                    "operator_variant": variant,
                    "fixture_digest": fixture_digest,
                    "target_layer": target_layer,
                    "oracle_expectation_type": oracle_expectation_type,
                    "expected_typed_failure_or_oracle": {
                        "MUTANT_REJECTED": f"mutant_rejected_at::{target_layer}",
                        "MUTATION_DETECTED_OR_DEGRADED": (
                            f"mutation_detected_or_degraded_at::{target_layer}"
                        ),
                        "INVARIANT_PROTECTED": (
                            f"invariant_protected_at::{target_layer}"
                        ),
                    }[oracle_expectation_type],
                    "severity": severity,
                    "critical": True,
                    "seed": seed,
                    "generator_identity": generator,
                    "handler_source_root": handler_source_root,
                    "mutation_patch_contract": dict(mutation_patch_contract),
                    "mutation_patch_contract_digest": (
                        mutation_patch_contract_digest
                    ),
                }
                rows.append({**body, "row_digest": canonical_digest(body)})
    rows.sort(key=lambda row: row["case_id"])
    body = {
        "schema_version": CRITICAL_MUTATION_MANIFEST_SCHEMA,
        "requirement_manifest_result_digest": requirement_manifest.get(
            "result_digest"
        ),
        "author_seed": seed,
        "generator_identity": generator,
        "generator_version": MUTATION_GENERATOR_VERSION,
        "operator_registry_digest": canonical_digest(
            {family: list(values) for family, values in sorted(registry.items())}
        ),
        "handler_source_rows": list(handler_source_rows),
        "handler_source_root": handler_source_root,
        "case_rows": rows,
        "case_count": len(rows),
        "critical_case_count": len(rows),
        "case_keyset_root": domain_rows_digest(
            b"FIN_IA_R14_CRITICAL_MUTATION_MANIFEST_V1\0",
            (canonical_json_bytes(row) for row in rows),
        ),
        "frozen_before_execution": True,
    }
    output = with_result_digest(body)
    validate_critical_mutation_manifest_r14(
        output, requirement_manifest=requirement_manifest
    )
    return output


def validate_critical_mutation_manifest_r14(
    value: Mapping[str, Any], *, requirement_manifest: Mapping[str, Any]
) -> None:
    validate_result_digest(value, code="R14_mutation_manifest")
    require(
        set(value)
        == {
            "schema_version",
            "requirement_manifest_result_digest",
            "author_seed",
            "generator_identity",
            "generator_version",
            "operator_registry_digest",
            "handler_source_rows",
            "handler_source_root",
            "case_rows",
            "case_count",
            "critical_case_count",
            "case_keyset_root",
            "frozen_before_execution",
            "result_digest",
        },
        "R14_mutation_manifest_keyset_invalid",
    )
    require(
        value.get("schema_version") == CRITICAL_MUTATION_MANIFEST_SCHEMA
        and value.get("generator_version") == MUTATION_GENERATOR_VERSION
        and value.get("frozen_before_execution") is True
        and value.get("requirement_manifest_result_digest")
        == requirement_manifest.get("result_digest"),
        "R14_mutation_manifest_identity_invalid",
    )
    from .dell_report_transaction_r14 import R14_IMPLEMENTATION_EXACT_PATHS

    handler_source_rows = list(value.get("handler_source_rows") or ())
    require(
        all(
            isinstance(row, Mapping)
            and set(row) == {"path", "bytes", "sha256"}
            and type(row.get("bytes")) is int
            and row["bytes"] >= 0
            and bool(require_sha256(row.get("sha256"), field="mutation_source"))
            for row in handler_source_rows
        )
        and [str(row["path"]) for row in handler_source_rows]
        == list(R14_IMPLEMENTATION_EXACT_PATHS)
        and value.get("handler_source_root")
        == _handler_dependency_root(handler_source_rows),
        "R14_mutation_manifest_handler_source_binding_invalid",
    )
    registry = _required_operator_registry(requirement_manifest)
    require(
        value.get("operator_registry_digest")
        == canonical_digest(
            {family: list(values) for family, values in sorted(registry.items())}
        ),
        "R14_mutation_manifest_operator_registry_digest_invalid",
    )
    rows = list(value.get("case_rows") or ())
    case_ids: list[str] = []
    covered: set[tuple[str, str]] = set()
    for row in rows:
        require(
            set(row)
            == {
                "case_id",
                "requirement_or_finding_id",
                "family",
                "operator_id",
                "operator_version",
                "operator_variant",
                "fixture_digest",
                "target_layer",
                "oracle_expectation_type",
                "expected_typed_failure_or_oracle",
                "severity",
                "critical",
                "seed",
                "generator_identity",
                "handler_source_root",
                "mutation_patch_contract",
                "mutation_patch_contract_digest",
                "row_digest",
            },
            "R14_mutation_manifest_row_keyset_invalid",
        )
        body = dict(row)
        row_digest = body.pop("row_digest")
        require(row_digest == canonical_digest(body), "R14_mutation_manifest_row_digest_invalid")
        family = str(row["family"])
        operator = str(row["operator_id"])
        require(
            family in registry
            and operator in registry[family]
            and row.get("critical") is True
            and row.get("operator_version") == MUTATION_GENERATOR_VERSION
            and row.get("seed") == value.get("author_seed")
            and row.get("generator_identity") == value.get("generator_identity")
            and row.get("handler_source_root") == value.get("handler_source_root"),
            "R14_mutation_manifest_row_contract_invalid",
        )
        expectation_type = _operator_oracle_kind(family, operator)
        production_contract = _production_mutation_contract(
            family=family,
            operator=operator,
            variant=str(row["operator_variant"]),
        )
        mutation_patch_contract = _production_mutation_patch_contract(
            family=family,
            operator=operator,
            variant=str(row["operator_variant"]),
        )
        require(
            row.get("mutation_patch_contract") == mutation_patch_contract
            and row.get("mutation_patch_contract_digest")
            == mutation_patch_contract.get("result_digest"),
            "R14_mutation_manifest_patch_contract_invalid",
        )
        expected_oracle = {
            "MUTANT_REJECTED": f"mutant_rejected_at::{row['target_layer']}",
            "MUTATION_DETECTED_OR_DEGRADED": (
                f"mutation_detected_or_degraded_at::{row['target_layer']}"
            ),
            "INVARIANT_PROTECTED": f"invariant_protected_at::{row['target_layer']}",
        }[expectation_type]
        require(
            row.get("oracle_expectation_type") == expectation_type
            and row.get("expected_typed_failure_or_oracle") == expected_oracle
            and row.get("fixture_digest")
            == canonical_digest(
                {
                    "case_id": row["case_id"],
                    "family": family,
                    "operator_id": operator,
                    "operator_variant": row["operator_variant"],
                    "fixture_contract": (
                        "actual_production_baseline_then_exact_operator_mutation_v1"
                    ),
                    "production_handler_node": _INJECTED_FIXTURE_CONSUMER_NODE,
                    "handler_source_root": value.get("handler_source_root"),
                    "mutation_patch_contract_digest": row.get(
                        "mutation_patch_contract_digest"
                    ),
                    **production_contract,
                }
            ),
            "R14_mutation_manifest_oracle_or_fixture_contract_invalid",
        )
        case_ids.append(str(row["case_id"]))
        covered.add((family, operator))
    required = {
        (family, operator)
        for family, operators in registry.items()
        for operator in operators
    }
    require(
        case_ids == sorted(set(case_ids))
        and covered == required
        and value.get("case_count") == len(rows)
        and value.get("critical_case_count") == len(rows),
        "R14_mutation_manifest_denominator_invalid",
    )
    require(
        value.get("case_keyset_root")
        == domain_rows_digest(
            b"FIN_IA_R14_CRITICAL_MUTATION_MANIFEST_V1\0",
            (canonical_json_bytes(row) for row in rows),
        ),
        "R14_mutation_manifest_keyset_root_invalid",
    )


def build_critical_mutation_handler_matrix_r14(
    *,
    manifest: Mapping[str, Any],
    requirement_manifest: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    """Return the frozen 55-row production-handler/oracle matrix.

    The matrix is deliberately derived from the validated denominator rather
    than a second case list.  Each row identifies the exact worker handler,
    production entry point, typed outcome, observation layer and concrete
    failure-code contract that a worker observation must satisfy.
    """

    validate_critical_mutation_manifest_r14(
        manifest,
        requirement_manifest=requirement_manifest,
    )
    matrix: list[Mapping[str, Any]] = []
    for row in manifest["case_rows"]:
        family = str(row["family"])
        operator = str(row["operator_id"])
        variant = str(row["operator_variant"])
        contract = _production_mutation_contract(
            family=family,
            operator=operator,
            variant=variant,
        )
        failure_code = contract["expected_failure_code_prefix"]
        match_mode = "prefix"
        if failure_code.startswith("TransactionOracle::"):
            if operator == "kill_at_each_write_flush_manifest_marker_rename_boundary":
                failure_code += variant
            match_mode = "exact"
        elif not failure_code.endswith(("R14_", "TransformationOracle::")):
            match_mode = "exact"
        body = {
            "case_id": row["case_id"],
            "family": family,
            "operator_id": operator,
            "operator_variant": variant,
            "production_handler_node": _INJECTED_FIXTURE_CONSUMER_NODE,
            "production_oracle": contract["production_oracle"],
            "production_entry_path": contract["production_entry_path"],
            "handler_source_root": row["handler_source_root"],
            "mutation_patch_contract_digest": row[
                "mutation_patch_contract_digest"
            ],
            "oracle_outcome_type": row["oracle_expectation_type"],
            "observation_layer": row["target_layer"],
            "failure_code_match_mode": match_mode,
            "expected_failure_code": failure_code,
            "manifest_row_digest": row["row_digest"],
        }
        matrix.append({**body, "row_digest": canonical_digest(body)})
    return tuple(matrix)


def _production_mutation_spec_digest_from_group_r14(
    *, group: Mapping[str, Any], manifest_row: Mapping[str, Any]
) -> str:
    mutation_patch = group.get("mutation_patch") or {}
    return canonical_digest(
        {
            "case_id": manifest_row["case_id"],
            "family": manifest_row["family"],
            "operator_id": manifest_row["operator_id"],
            "operator_variant": manifest_row["operator_variant"],
            "production_oracle": group["production_oracle"],
            "production_entry_path": group["production_entry_path"],
            "before_artifact_digest": group["baseline_fixture_digest"],
            "after_artifact_digest": group["mutated_fixture_digest"],
            "handler_dependency_root": group["handler_dependency_root"],
            "mutation_patch_digest": mutation_patch.get("result_digest"),
            "mutation_after_input_sha256": group[
                "mutation_after_input_sha256"
            ],
            "mutation_patch_contract_digest": group[
                "mutation_patch_contract_digest"
            ],
        }
    )


def _case_execution_root_from_group_r14(
    *, group: Mapping[str, Any], manifest_row: Mapping[str, Any]
) -> str:
    mutation_patch = group.get("mutation_patch") or {}
    return canonical_digest(
        {
            "manifest_row_digest": manifest_row["row_digest"],
            "execution_group_row_digest": group["row_digest"],
            "baseline_fixture_digest": group["baseline_fixture_digest"],
            "mutated_fixture_digest": group["mutated_fixture_digest"],
            "production_observation_row_digest": group[
                "production_observation_row_digest"
            ],
            "production_mutation_spec_digest": group[
                "production_mutation_spec_digest"
            ],
            "handler_dependency_root": group["handler_dependency_root"],
            "mutation_patch_digest": mutation_patch.get(
                "result_digest", "0" * 64
            ),
            "mutation_patch_contract_digest": group[
                "mutation_patch_contract_digest"
            ],
            "mutation_input_pair_root": group["mutation_input_pair_root"],
            "mutation_after_input_sha256": group[
                "mutation_after_input_sha256"
            ],
            "oracle_expectation_type": manifest_row["oracle_expectation_type"],
            "expected_oracle": manifest_row[
                "expected_typed_failure_or_oracle"
            ],
        }
    )


def _validate_observation_group_binding_r14(
    *,
    observation: Mapping[str, Any],
    group: Mapping[str, Any],
    manifest_row: Mapping[str, Any],
) -> None:
    case_id = manifest_row["case_id"]
    require(
        observation.get("case_id") == case_id
        and observation.get("execution_group") == case_id
        and observation.get("execution_group_row_digest")
        == group.get("row_digest")
        and observation.get("observed_verdict") == group.get("verdict")
        and observation.get("oracle_outcome_type")
        == group.get("oracle_outcome_type")
        and observation.get("observation_layer")
        == group.get("observation_layer")
        and observation.get("observed_failure_code")
        == group.get("observed_failure_code")
        and observation.get("duration_ms") == group.get("duration_ms")
        and observation.get("case_execution_root")
        == _case_execution_root_from_group_r14(
            group=group,
            manifest_row=manifest_row,
        ),
        "R14_mutation_observation_group_binding_invalid",
    )


def _validate_execution_group_receipts_r14(
    receipts: Sequence[Mapping[str, Any]], *, manifest: Mapping[str, Any]
) -> None:
    expected_rows = {str(row["case_id"]): row for row in manifest["case_rows"]}
    source_rows_by_path = {
        str(row["path"]): row for row in manifest["handler_source_rows"]
    }
    consumer_source_path = _INJECTED_FIXTURE_CONSUMER_NODE.split("::", 1)[0]
    require(
        len(receipts) == len(expected_rows),
        "R14_mutation_execution_group_denominator_invalid",
    )
    seen: set[str] = set()
    required_keys = {
        "group",
        "case_id",
        "operator_id",
        "operator_variant",
        "node_ids",
        "protocol",
        "payload_digest",
        "command_digest",
        "production_mutation_source_sha256",
        "handler_dependency_sources",
        "handler_dependency_root",
        "manifest_fixture_digest",
        "baseline_fixture_digest",
        "mutated_fixture_digest",
        "worker_observation_row_digest",
        "production_observation_row_digest",
        "production_oracle",
        "production_entry_path",
        "production_entry_source_sha256",
        "production_mutation_spec_digest",
        "mutation_after_input_sha256",
        "mutation_patch",
        "mutation_patch_contract_digest",
        "mutation_input_before",
        "mutation_input_after",
        "mutation_input_pair_root",
        "oracle_outcome_type",
        "oracle_status",
        "observation_layer",
        "observed_failure_code",
        "returncode",
        "stdout_sha256",
        "stderr_sha256",
        "duration_ms",
        "verdict",
        "row_digest",
    }
    for raw in receipts:
        require(isinstance(raw, Mapping) and set(raw) == required_keys, "R14_mutation_execution_group_schema_invalid")
        row = dict(raw)
        row_digest = row.pop("row_digest")
        require(row_digest == canonical_digest(row), "R14_mutation_execution_group_digest_invalid")
        case_id = str(raw["case_id"])
        require(case_id in expected_rows and case_id not in seen, "R14_mutation_execution_group_keyset_invalid")
        seen.add(case_id)
        expected = expected_rows[case_id]
        family = str(expected["family"])
        operator = str(expected["operator_id"])
        variant = str(expected["operator_variant"])
        production_contract = _production_mutation_contract(
            family=family,
            operator=operator,
            variant=variant,
        )
        require(
            raw.get("group") == case_id
            and raw.get("operator_id") == operator
            and raw.get("operator_variant") == variant
            and raw.get("node_ids") == [_INJECTED_FIXTURE_CONSUMER_NODE]
            and raw.get("protocol") == MUTATION_EXECUTION_PROTOCOL
            and raw.get("manifest_fixture_digest") == expected["fixture_digest"]
            and raw.get("handler_dependency_sources")
            == manifest.get("handler_source_rows")
            and raw.get("handler_dependency_root")
            == manifest.get("handler_source_root")
            == expected.get("handler_source_root")
            and raw.get("handler_dependency_root")
            == _handler_dependency_root(raw["handler_dependency_sources"])
            and raw.get("production_entry_path")
            == production_contract["production_entry_path"]
            and raw.get("production_mutation_source_sha256")
            == source_rows_by_path[consumer_source_path]["sha256"]
            and raw.get("production_entry_source_sha256")
            == source_rows_by_path[production_contract["production_entry_path"]][
                "sha256"
            ]
            and raw.get("command_digest")
            == canonical_digest(
                [
                    "retrieval.dell_report_mutation_oracle_r14",
                    "--execute-bound-case",
                    _INJECTED_FIXTURE_CONSUMER_NODE,
                    raw.get("payload_digest"),
                ]
            )
            and (
                raw.get("verdict") == "UNEXECUTED"
                or (
                    raw.get("production_oracle")
                    == production_contract["production_oracle"]
                    and bool(
                        require_identifier(
                            raw.get("production_oracle"),
                            field="mutation_production_oracle",
                        )
                    )
                )
            ),
            "R14_mutation_execution_group_binding_invalid",
        )
        for key in (
            "payload_digest",
            "command_digest",
            "production_mutation_source_sha256",
            "handler_dependency_root",
            "production_entry_source_sha256",
            "production_mutation_spec_digest",
            "mutation_after_input_sha256",
            "mutation_patch_contract_digest",
            "mutation_input_pair_root",
            "manifest_fixture_digest",
            "baseline_fixture_digest",
            "mutated_fixture_digest",
            "worker_observation_row_digest",
            "production_observation_row_digest",
            "stdout_sha256",
            "stderr_sha256",
        ):
            require_sha256(raw.get(key), field=f"mutation_execution_{key}")
        verdict = raw.get("verdict")
        require(
            verdict in {"KILLED", "SURVIVED", "UNEXECUTED"}
            and raw.get("oracle_status") == verdict
            and type(raw.get("returncode")) is int
            and type(raw.get("duration_ms")) is int
            and raw["duration_ms"] >= 0,
            "R14_mutation_execution_observation_invalid",
        )
        mutation_patch = raw.get("mutation_patch")
        if verdict == "UNEXECUTED":
            require(
                mutation_patch == {}
                and raw.get("mutation_after_input_sha256") == "0" * 64,
                "R14_mutation_execution_unexecuted_patch_invalid",
            )
        else:
            patch_contract = expected["mutation_patch_contract"]
            _validate_exact_mutation_patch_r14(
                mutation_patch,
                before_input=raw.get("mutation_input_before"),
                after_input=raw.get("mutation_input_after"),
                expected_contract=patch_contract,
            )
            require(
                isinstance(mutation_patch, Mapping)
                and mutation_patch.get("schema_version")
                == EXACT_MUTATION_PATCH_SCHEMA
                and mutation_patch.get("result_digest")
                and mutation_patch.get("change_count", 0) > 0
                and raw.get("mutation_after_input_sha256")
                == mutation_patch.get("after_input_sha256")
                and raw.get("mutation_patch_contract_digest")
                == expected.get("mutation_patch_contract_digest")
                and raw.get("mutation_input_pair_root")
                == canonical_digest(
                    {
                        "before_input_sha256": mutation_patch.get(
                            "before_input_sha256"
                        ),
                        "after_input_sha256": mutation_patch.get(
                            "after_input_sha256"
                        ),
                        "mutation_patch_digest": mutation_patch.get(
                            "result_digest"
                        ),
                        "mutation_patch_contract_digest": expected.get(
                            "mutation_patch_contract_digest"
                        ),
                    }
                ),
                "R14_mutation_execution_patch_binding_invalid",
            )
            require(
                raw.get("production_mutation_spec_digest")
                == _production_mutation_spec_digest_from_group_r14(
                    group=raw,
                    manifest_row=expected,
                ),
                "R14_mutation_execution_production_spec_binding_invalid",
            )
        if verdict == "KILLED":
            require(
                raw.get("returncode") == 0
                and raw.get("oracle_outcome_type")
                == expected["oracle_expectation_type"]
                and raw.get("observation_layer") == expected["target_layer"]
                and str(raw.get("observed_failure_code") or "").startswith(
                    production_contract["expected_failure_code_prefix"]
                ),
                "R14_mutation_execution_kill_semantics_invalid",
            )
        elif verdict == "SURVIVED":
            require(
                raw.get("returncode") == 0
                and raw.get("oracle_outcome_type") == "none"
                and raw.get("observation_layer") == "none"
                and raw.get("observed_failure_code") == "none",
                "R14_mutation_execution_survivor_semantics_invalid",
            )
        else:
            require(
                raw.get("oracle_outcome_type") == "none"
                and raw.get("observation_layer") == "none"
                and raw.get("observed_failure_code") == "none",
                "R14_mutation_execution_unexecuted_semantics_invalid",
            )
    require(seen == set(expected_rows), "R14_mutation_execution_group_keyset_invalid")


def build_critical_mutation_kill_receipt_r14(
    *,
    manifest: Mapping[str, Any],
    requirement_manifest: Mapping[str, Any],
    execution_report: MutationExecutionReportR14,
    repository_root: Path,
    implementation_commit: str,
    implementation_tree: str,
    test_identity: str,
) -> dict[str, Any]:
    validate_critical_mutation_manifest_r14(
        manifest, requirement_manifest=requirement_manifest
    )
    require(
        bool(_HEX40.fullmatch(implementation_commit))
        and bool(_HEX40.fullmatch(implementation_tree)),
        "R14_mutation_kill_git_identity_invalid",
    )
    implementation_source_root = _validate_manifest_source_bindings_against_git_r14(
        manifest=manifest,
        repository_root=repository_root,
        implementation_commit=implementation_commit,
        implementation_tree=implementation_tree,
    )
    require(
        isinstance(execution_report, MutationExecutionReportR14)
        and execution_report._seal is _EXECUTION_SEAL,
        "R14_mutation_execution_report_not_minted",
    )
    _validate_execution_group_receipts_r14(
        execution_report.execution_group_receipts,
        manifest=manifest,
    )
    groups_by_case = {
        str(row["case_id"]): row
        for row in execution_report.execution_group_receipts
    }
    manifest_by_id = {row["case_id"]: row for row in manifest["case_rows"]}
    observation_by_id: dict[str, Mapping[str, Any]] = {}
    for raw in execution_report.observations:
        row = dict(raw)
        require(
            set(row)
            == {
                "case_id",
                "observed_verdict",
                "oracle_outcome_type",
                "observation_layer",
                "observed_failure_code",
                "duration_ms",
                "execution_group",
                "execution_group_row_digest",
                "case_execution_root",
            },
            "R14_mutation_kill_observation_keyset_invalid",
        )
        case_id = str(row["case_id"])
        require(
            case_id in manifest_by_id
            and case_id in groups_by_case
            and case_id not in observation_by_id,
            "R14_mutation_kill_duplicate_or_unknown_observation",
        )
        _validate_observation_group_binding_r14(
            observation=row,
            group=groups_by_case[case_id],
            manifest_row=manifest_by_id[case_id],
        )
        observation_by_id[case_id] = row
    require(
        set(observation_by_id) == set(manifest_by_id),
        "R14_mutation_kill_keyset_not_manifest_exact",
    )
    require(
        execution_report.execution_root
        == domain_rows_digest(
            b"FIN_IA_R14_CRITICAL_MUTATION_EXECUTION_V1\0",
            (
                canonical_json_bytes(row)
                for row in (
                    *execution_report.execution_group_receipts,
                    *execution_report.observations,
                )
            ),
        ),
        "R14_mutation_execution_report_root_invalid",
    )
    rows: list[dict[str, Any]] = []
    for case_id in sorted(manifest_by_id):
        expected = manifest_by_id[case_id]
        observed = observation_by_id[case_id]
        verdict = str(observed["observed_verdict"])
        require(
            verdict in {"KILLED", "SURVIVED", "UNEXECUTED", "EXCLUDED"}
            and isinstance(observed["duration_ms"], int)
            and observed["duration_ms"] >= 0,
            "R14_mutation_kill_observation_invalid",
        )
        if verdict == "KILLED":
            require(
                observed["oracle_outcome_type"]
                == expected["oracle_expectation_type"]
                and observed["observation_layer"] == expected["target_layer"]
                and bool(
                    require_identifier(
                        observed["observed_failure_code"],
                        field="mutation_failure_code",
                    )
                ),
                "R14_mutation_kill_first_layer_or_code_invalid",
            )
        body = {
            **observed,
            "manifest_row_digest": expected["row_digest"],
            "implementation_commit": implementation_commit,
            "implementation_tree": implementation_tree,
            "test_identity": require_identifier(
                test_identity, field="mutation_test_identity"
            ),
        }
        rows.append({**body, "row_digest": canonical_digest(body)})
    counts = Counter(row["observed_verdict"] for row in rows)
    killed = int(counts.get("KILLED", 0))
    denominator = len(rows)
    body = {
        "schema_version": CRITICAL_MUTATION_KILL_RECEIPT_SCHEMA,
        "mutation_manifest_result_digest": manifest["result_digest"],
        "mutation_manifest_keyset_root": manifest["case_keyset_root"],
        "implementation_source_root": implementation_source_root,
        "implementation_source_binding_status": "GIT_I_BLOBS_VERIFIED",
        "implementation_commit": implementation_commit,
        "implementation_tree": implementation_tree,
        "test_identity": test_identity,
        "execution_root": execution_report.execution_root,
        "execution_group_receipts": list(execution_report.execution_group_receipts),
        "observation_rows": rows,
        "denominator": denominator,
        "killed": killed,
        "survived": int(counts.get("SURVIVED", 0)),
        "unexecuted": int(counts.get("UNEXECUTED", 0)),
        "excluded": int(counts.get("EXCLUDED", 0)),
        "kill_rate_numerator": killed,
        "kill_rate_denominator": denominator,
        "status": "PASS_100_PERCENT_KILLED" if killed == denominator else "FAIL_MUTANTS_REMAIN",
        "observation_root": domain_rows_digest(
            b"FIN_IA_R14_CRITICAL_MUTATION_KILLS_V1\0",
            (canonical_json_bytes(row) for row in rows),
        ),
    }
    output = with_result_digest(body)
    validate_critical_mutation_kill_receipt_r14(output, manifest=manifest)
    return output


def validate_critical_mutation_kill_receipt_r14(
    value: Mapping[str, Any], *, manifest: Mapping[str, Any]
) -> None:
    validate_result_digest(value, code="R14_mutation_kill_receipt")
    require(
        set(value)
        == {
            "schema_version",
            "mutation_manifest_result_digest",
            "mutation_manifest_keyset_root",
            "implementation_source_root",
            "implementation_source_binding_status",
            "implementation_commit",
            "implementation_tree",
            "test_identity",
            "execution_root",
            "execution_group_receipts",
            "observation_rows",
            "denominator",
            "killed",
            "survived",
            "unexecuted",
            "excluded",
            "kill_rate_numerator",
            "kill_rate_denominator",
            "status",
            "observation_root",
            "result_digest",
        },
        "R14_mutation_kill_receipt_schema_invalid",
    )
    require(
        value.get("schema_version") == CRITICAL_MUTATION_KILL_RECEIPT_SCHEMA
        and value.get("mutation_manifest_result_digest") == manifest.get("result_digest")
        and value.get("mutation_manifest_keyset_root") == manifest.get("case_keyset_root")
        and value.get("implementation_source_root")
        == manifest.get("handler_source_root")
        and value.get("implementation_source_binding_status")
        == "GIT_I_BLOBS_VERIFIED",
        "R14_mutation_kill_receipt_binding_invalid",
    )
    require(
        bool(_HEX40.fullmatch(str(value.get("implementation_commit") or "")))
        and bool(_HEX40.fullmatch(str(value.get("implementation_tree") or "")))
        and bool(require_identifier(value.get("test_identity"), field="mutation_test_identity")),
        "R14_mutation_kill_receipt_identity_invalid",
    )
    group_receipts = list(value.get("execution_group_receipts") or ())
    _validate_execution_group_receipts_r14(group_receipts, manifest=manifest)
    groups_by_case = {
        str(group["case_id"]): group for group in group_receipts
    }
    rows = list(value.get("observation_rows") or ())
    manifest_rows = list(manifest.get("case_rows") or ())
    require(
        [row.get("case_id") for row in rows]
        == [row.get("case_id") for row in manifest_rows],
        "R14_mutation_kill_receipt_keyset_invalid",
    )
    for row, expected in zip(rows, manifest_rows):
        require(
            isinstance(row, dict)
            and set(row)
            == {
                "case_id",
                "observed_verdict",
                "oracle_outcome_type",
                "observation_layer",
                "observed_failure_code",
                "duration_ms",
                "manifest_row_digest",
                "implementation_commit",
                "implementation_tree",
                "test_identity",
                "execution_group",
                "execution_group_row_digest",
                "case_execution_root",
                "row_digest",
            },
            "R14_mutation_kill_receipt_row_schema_invalid",
        )
        _validate_observation_group_binding_r14(
            observation=row,
            group=groups_by_case[str(expected["case_id"])],
            manifest_row=expected,
        )
        body = dict(row)
        row_digest = body.pop("row_digest")
        require(
            row_digest == canonical_digest(body)
            and row.get("manifest_row_digest") == expected.get("row_digest")
            and row.get("implementation_commit") == value.get("implementation_commit")
            and row.get("implementation_tree") == value.get("implementation_tree")
            and row.get("test_identity") == value.get("test_identity")
            and bool(require_sha256(row.get("execution_group_row_digest"), field="mutation_execution_group"))
            and bool(require_sha256(row.get("case_execution_root"), field="mutation_case_execution"))
            and type(row.get("duration_ms")) is int
            and row["duration_ms"] >= 0,
            "R14_mutation_kill_receipt_row_binding_invalid",
        )
        verdict = row.get("observed_verdict")
        require(
            verdict in {"KILLED", "SURVIVED", "UNEXECUTED", "EXCLUDED"},
            "R14_mutation_kill_receipt_verdict_invalid",
        )
        if verdict == "KILLED":
            require(
                row.get("oracle_outcome_type")
                == expected.get("oracle_expectation_type")
                and row.get("observation_layer") == expected.get("target_layer")
                and bool(
                    require_identifier(
                        row.get("observed_failure_code"),
                        field="mutation_failure_code",
                    )
                ),
                "R14_mutation_kill_receipt_first_layer_invalid",
            )
        else:
            require(
                row.get("oracle_outcome_type") == "none"
                and row.get("observation_layer") == "none"
                and row.get("observed_failure_code") == "none",
                "R14_mutation_kill_receipt_nonkill_semantics_invalid",
            )
    counts = Counter(row.get("observed_verdict") for row in rows)
    group_counts = Counter(group.get("verdict") for group in group_receipts)
    denominator = len(rows)
    require(
        counts == group_counts
        and value.get("denominator") == denominator
        and value.get("killed") == int(counts.get("KILLED", 0))
        and value.get("survived") == int(counts.get("SURVIVED", 0))
        and value.get("unexecuted") == int(counts.get("UNEXECUTED", 0))
        and value.get("excluded") == int(counts.get("EXCLUDED", 0))
        and value.get("kill_rate_numerator") == value.get("killed")
        and value.get("kill_rate_denominator") == denominator,
        "R14_mutation_kill_receipt_counts_invalid",
    )
    expected_status = (
        "PASS_100_PERCENT_KILLED"
        if denominator > 0 and counts == Counter({"KILLED": denominator})
        else "FAIL_MUTANTS_REMAIN"
    )
    require(value.get("status") == expected_status, "R14_mutation_kill_receipt_status_invalid")
    require(
        bool(require_sha256(value.get("execution_root"), field="mutation_execution_root"))
        and isinstance(value.get("execution_group_receipts"), list)
        and bool(value["execution_group_receipts"])
        and value.get("execution_root")
        == domain_rows_digest(
            b"FIN_IA_R14_CRITICAL_MUTATION_EXECUTION_V1\0",
            (
                canonical_json_bytes(row)
                for row in (
                    *value["execution_group_receipts"],
                    *[
                        {
                            key: row[key]
                            for key in (
                                "case_id",
                                "observed_verdict",
                                "oracle_outcome_type",
                                "observation_layer",
                                "observed_failure_code",
                                "duration_ms",
                                "execution_group",
                                "execution_group_row_digest",
                                "case_execution_root",
                            )
                        }
                        for row in rows
                    ],
                )
            ),
        ),
        "R14_mutation_execution_root_invalid",
    )
    require(
        value.get("observation_root")
        == domain_rows_digest(
            b"FIN_IA_R14_CRITICAL_MUTATION_KILLS_V1\0",
            (canonical_json_bytes(row) for row in rows),
        ),
        "R14_mutation_kill_receipt_root_invalid",
    )


def _main(argv: Sequence[str]) -> int:
    if len(argv) != 3 or argv[1] != "--execute-bound-case":
        return 2
    root = Path(argv[2]).resolve(strict=True)
    payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    require(isinstance(payload, dict), "R14_mutation_worker_payload_invalid")
    receipt = _execute_bound_case_worker(payload, root=root)
    sys.stdout.buffer.write(canonical_json_bytes(receipt))
    return 0


__all__ = [
    "CRITICAL_MUTATION_KILL_RECEIPT_SCHEMA",
    "CRITICAL_MUTATION_MANIFEST_SCHEMA",
    "MUTATION_GENERATOR_VERSION",
    "MUTATION_EXECUTION_PROTOCOL",
    "TRANSACTION_HARD_EXIT_BOUNDARIES",
    "MutationExecutionReportR14",
    "build_critical_mutation_kill_receipt_r14",
    "build_default_critical_mutation_manifest_r14",
    "execute_critical_mutation_suite_r14",
    "validate_critical_mutation_kill_receipt_r14",
    "validate_critical_mutation_manifest_r14",
]


if __name__ == "__main__":  # pragma: no cover - exercised through subprocess
    raise SystemExit(_main(sys.argv))
