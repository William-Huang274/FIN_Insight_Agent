from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from .dell_report_decision_vector_r14 import validate_decision_vector_receipt_r14
from .dell_report_decision_vector_rebuilder_r14 import rebuild_decision_vector_r14
from .dell_report_population_manifest_r14 import validate_population_commitment_r14
from .dell_report_r14_common import (
    TARGET_IDS,
    canonical_digest,
    canonical_json_bytes,
    domain_rows_digest,
    require,
    require_identifier,
    require_sha256,
    sha256_bytes,
    validate_result_digest,
    with_result_digest,
)
from .dell_report_transformation_r14 import (
    validate_graph_transformation_receipt_r14,
)
from .dell_report_delta_r14 import validate_r13_to_r14_delta_receipt_r14
from .dell_report_mutation_oracle_r14 import (
    _validate_manifest_source_bindings_against_git_r14,
    validate_critical_mutation_kill_receipt_r14,
    validate_critical_mutation_manifest_r14,
)
from .dell_report_program_contract_r14 import validate_full_program_receipt_r14
from .dell_report_property_oracle_r14 import (
    validate_author_property_manifest_r14,
    validate_author_property_receipt_r14,
)
from .dell_report_resource_gate_r14 import (
    FROZEN_HARD_LIMIT_MS,
    FROZEN_HARD_MEMORY_LIMIT_BYTES,
    FROZEN_WARNING_LIMIT_MS,
    validate_performance_receipt_r14,
    validate_resource_gate_receipt_r14,
)


RECONCILIATION_SCHEMA_VERSION = "fin_ia_dell_03B_R14_reconciliation_summary_v1_0"
PREFORMAL_COMMITMENT_SCHEMA_VERSION = (
    "fin_ia_dell_03B_R14_preformal_decision_commitment_v1_0"
)
PUBLIC_PROJECTION_SCHEMA_VERSION = "fin_ia_dell_03B_R14_public_projection_v1_0"
_HEX40 = re.compile(r"[0-9a-f]{40}")
PRIVATE_PROGRAM_ARTIFACT_PATH = "private/result.json"
PUBLIC_PROGRAM_ARTIFACT_PATH = "public/result.json"
PRIVATE_PROGRAM_ARTIFACT_SCHEMA = (
    "fin_ia_dell_03B_R14_private_full_program_material_v1_0"
)
PUBLIC_PROGRAM_ARTIFACT_SCHEMA = (
    "fin_ia_dell_03B_R14_public_program_summary_v1_0"
)
_PUBLIC_PROJECTION_KEYS = frozenset(
    {
        "schema_version",
        "commitment_result_digest",
        "target_lane_rows",
        "aggregate_outcome_counts",
        "aggregate_candidate_ceiling",
        "transformation_status_counts",
        "transformation_non_vacuous_count",
        "privacy_contract",
        "result_digest",
    }
)
_PUBLIC_PROJECTION_ROW_KEYS = frozenset(
    {
        "target_id",
        "lane",
        "expected_length",
        "outcome_counts",
        "candidate_ceiling",
        "route_disposition",
    }
)
_PUBLIC_PROJECTION_PRIVACY_CONTRACT = {
    "contains_raw_text": False,
    "contains_model_text": False,
    "contains_private_locator": False,
    "contains_source_or_object_ID_rows": False,
    "contains_decision_details": False,
    "creates_reader_citation": False,
}
_PUBLIC_ROUTE_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")


def recompute_program_artifact_semantic_root_r14(
    *, relative_path: str, payload: bytes
) -> str:
    require(
        relative_path
        in {PRIVATE_PROGRAM_ARTIFACT_PATH, PUBLIC_PROGRAM_ARTIFACT_PATH},
        f"R14_program_artifact_path_not_registered:{relative_path}",
    )
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        require(False, f"R14_program_artifact_json_invalid:{relative_path}:{exc}")
    require(
        isinstance(value, dict) and canonical_json_bytes(value) == payload,
        f"R14_program_artifact_not_canonical:{relative_path}",
    )
    validate_result_digest(value, code="R14_program_artifact")
    if relative_path == PRIVATE_PROGRAM_ARTIFACT_PATH:
        require(
            set(value)
            == {
                "schema_version",
                "program_receipt_result_digest",
                "private_material",
                "private_material_root",
                "model_provider_calls",
                "result_digest",
            }
            and value.get("schema_version") == PRIVATE_PROGRAM_ARTIFACT_SCHEMA
            and bool(
                require_sha256(
                    value.get("program_receipt_result_digest"),
                    field="private_artifact_program_receipt",
                )
            )
            and bool(
                require_sha256(
                    value.get("private_material_root"),
                    field="private_artifact_material",
                )
            )
            and isinstance(value.get("private_material"), dict)
            and value.get("private_material_root")
            == canonical_digest(value["private_material"])
            and value.get("model_provider_calls") == 0,
            "R14_private_program_artifact_schema_invalid",
        )
    else:
        privacy = value.get("privacy_contract")
        require(
            set(value)
            == {
                "schema_version",
                "program_receipt_result_digest",
                "aggregate_outcome_counts",
                "aggregate_candidate_ceiling",
                "privacy_contract",
                "model_provider_calls",
                "result_digest",
            }
            and value.get("schema_version") == PUBLIC_PROGRAM_ARTIFACT_SCHEMA
            and bool(
                require_sha256(
                    value.get("program_receipt_result_digest"),
                    field="public_artifact_program_receipt",
                )
            )
            and isinstance(value.get("aggregate_outcome_counts"), dict)
            and type(value.get("aggregate_candidate_ceiling")) is int
            and value["aggregate_candidate_ceiling"] >= 0
            and privacy
            == {
                "contains_raw_text": False,
                "contains_model_text": False,
                "contains_private_locator": False,
                "contains_source_or_object_ID_rows": False,
                "contains_decision_details": False,
                "creates_reader_citation": False,
            }
            and value.get("model_provider_calls") == 0,
            "R14_public_program_artifact_schema_or_privacy_invalid",
        )
    return canonical_digest(value)


def build_planned_program_artifact_contracts_r14(
    *,
    payloads: Mapping[str, bytes],
    program_receipt: Mapping[str, Any],
    reconciliation: Mapping[str, Any],
) -> list[dict[str, Any]]:
    require(
        set(payloads)
        == {PRIVATE_PROGRAM_ARTIFACT_PATH, PUBLIC_PROGRAM_ARTIFACT_PATH}
        and all(isinstance(value, bytes) for value in payloads.values()),
        "R14_program_artifact_registry_or_bytes_invalid",
    )
    rows: list[dict[str, Any]] = []
    parsed: dict[str, Mapping[str, Any]] = {}
    for path in sorted(payloads):
        payload = payloads[path]
        semantic_root = recompute_program_artifact_semantic_root_r14(
            relative_path=path, payload=payload
        )
        value = json.loads(payload.decode("utf-8"))
        parsed[path] = value
        rows.append(
            {
                "relative_path": path,
                "exact_bytes": len(payload),
                "sha256": sha256_bytes(payload),
                "semantic_root": semantic_root,
            }
        )
    private = parsed[PRIVATE_PROGRAM_ARTIFACT_PATH]
    public = parsed[PUBLIC_PROGRAM_ARTIFACT_PATH]
    require(
        private.get("program_receipt_result_digest")
        == program_receipt.get("result_digest")
        and public.get("program_receipt_result_digest")
        == program_receipt.get("result_digest")
        and public.get("aggregate_outcome_counts")
        == reconciliation.get("aggregate_outcome_counts")
        and public.get("aggregate_candidate_ceiling")
        == reconciliation.get("aggregate_candidate_ceiling"),
        "R14_program_artifact_material_binding_invalid",
    )
    return rows


def _binding_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return str(row.get("target_id") or ""), str(row.get("lane") or "")


def build_reconciliation_summary_r14(
    *,
    manifest: Mapping[str, Any],
    receipts: Sequence[Mapping[str, Any]],
    details_by_target_lane: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]],
    transformation_receipts: Sequence[Mapping[str, Any]],
    route_registry: Mapping[str, str],
) -> dict[str, Any]:
    expected_keys = {
        (target_id, lane)
        for target_id in TARGET_IDS
        for lane in ("source", "compiled")
    }
    by_key: dict[tuple[str, str], Mapping[str, Any]] = {}
    rebuilds: dict[tuple[str, str], Mapping[str, Any]] = {}
    for receipt in receipts:
        validate_decision_vector_receipt_r14(receipt)
        key = _binding_key(receipt)
        require(key not in by_key, f"R14_reconciliation_duplicate_receipt:{key}")
        require(
            receipt.get("manifest_result_digest") == manifest.get("result_digest"),
            f"R14_reconciliation_manifest_mismatch:{key}",
        )
        details = details_by_target_lane.get(key)
        require(details is not None, f"R14_reconciliation_details_missing:{key}")
        rebuilt = rebuild_decision_vector_r14(
            manifest=manifest, receipt=receipt, details=details
        )
        by_key[key] = receipt
        rebuilds[key] = rebuilt
    require(set(by_key) == expected_keys, "R14_reconciliation_receipt_population_invalid")
    require(
        set(details_by_target_lane) == expected_keys,
        "R14_reconciliation_detail_population_invalid",
    )
    require(
        set(route_registry) == set(TARGET_IDS)
        and all(bool(require_identifier(value, field="route_disposition")) for value in route_registry.values()),
        "R14_reconciliation_route_registry_invalid",
    )

    rows: list[dict[str, Any]] = []
    aggregate_counts = Counter()
    for key in sorted(expected_keys):
        receipt = by_key[key]
        counts = dict(receipt["outcome_counts"])
        aggregate_counts.update(counts)
        rows.append(
            {
                "target_id": key[0],
                "lane": key[1],
                "expected_length": receipt["expected_length"],
                "outcome_counts": counts,
                "candidate_ceiling": int(counts["C"]) + int(counts["P"]),
                "vector_root": receipt["vector_root"],
                "detail_root": receipt["detail_root"],
                "receipt_result_digest": receipt["result_digest"],
                "outcome_keyset_root": rebuilds[key]["outcome_keyset_root"],
                "route_disposition": route_registry[key[0]],
            }
        )

    source_entries = {
        int(row["manifest_index"]): row
        for row in manifest.get("source_canonical_order") or ()
    }
    object_entries = {
        int(row["manifest_index"]): row
        for row in manifest.get("object_canonical_order") or ()
    }
    transformation_by_compiled_index: dict[int, Mapping[str, Any]] = {}
    for row in transformation_receipts:
        validate_graph_transformation_receipt_r14(row)
        source_index = int(row["source_manifest_index"])
        compiled_index = int(row["compiled_manifest_index"])
        require(
            compiled_index not in transformation_by_compiled_index,
            "R14_reconciliation_duplicate_transformation_binding",
        )
        source_entry = source_entries.get(source_index)
        object_entry = object_entries.get(compiled_index)
        require(
            source_entry is not None
            and object_entry is not None
            and row.get("source_record_id")
            == source_entry.get("source_record_id")
            == object_entry.get("primary_source_record_id")
            and row.get("compiled_object_id")
            == object_entry.get("compiled_object_id")
            and row.get("source_input_digest") == source_entry.get("input_digest")
            and row.get("source_slice_mode")
            == object_entry.get("source_slice_mode")
            and row.get("source_slice_digest")
            == object_entry.get("source_slice_digest")
            and row.get("source_slice_binding_digest")
            == object_entry.get("source_slice_binding_digest")
            and row.get("compiled_input_digest") == object_entry.get("input_digest")
            and row.get("canonical_source_family_id")
            == source_entry.get("canonical_source_family_id")
            == object_entry.get("canonical_source_family_id")
            and row.get("compiled_lineage_source_record_ids")
            == object_entry.get("lineage_source_record_ids")
            and row.get("compiled_lineage_source_keyset_digest")
            == object_entry.get("lineage_source_keyset_digest"),
            "R14_reconciliation_transformation_population_rebind",
        )
        transformation_by_compiled_index[compiled_index] = row
    require(
        set(transformation_by_compiled_index) == set(object_entries),
        "R14_reconciliation_transformation_population_invalid",
    )
    require(
        [int(row["compiled_manifest_index"]) for row in transformation_receipts]
        == sorted(object_entries),
        "R14_reconciliation_transformation_order_invalid",
    )
    transformation_status_counts = Counter(
        str(row.get("status") or "MISSING") for row in transformation_receipts
    )
    transformation_non_vacuous = sum(
        bool(row.get("coverage", {}).get("non_vacuous"))
        for row in transformation_receipts
    )
    transformation_root = domain_rows_digest(
        b"FIN_IA_R14_TRANSFORMATION_RECEIPTS_V1\0",
        (
            canonical_json_bytes(
                {
                    "result_digest": require_sha256(
                        row.get("result_digest"), field="transformation_receipt"
                    ),
                    "source_manifest_index": row["source_manifest_index"],
                    "compiled_manifest_index": row["compiled_manifest_index"],
                    "source_record_id": row["source_record_id"],
                    "compiled_object_id": row["compiled_object_id"],
                    "source_input_digest": row["source_input_digest"],
                    "source_slice_mode": row["source_slice_mode"],
                    "source_slice_digest": row["source_slice_digest"],
                    "source_slice_binding_digest": row[
                        "source_slice_binding_digest"
                    ],
                    "compiled_input_digest": row["compiled_input_digest"],
                    "canonical_source_family_id": row[
                        "canonical_source_family_id"
                    ],
                    "compiled_lineage_source_record_ids": row[
                        "compiled_lineage_source_record_ids"
                    ],
                    "compiled_lineage_source_keyset_digest": row[
                        "compiled_lineage_source_keyset_digest"
                    ],
                    "status": row.get("status"),
                    "non_vacuous": bool(row.get("coverage", {}).get("non_vacuous")),
                }
            )
            for row in transformation_receipts
        ),
    )
    body = {
        "schema_version": RECONCILIATION_SCHEMA_VERSION,
        "manifest_result_digest": require_sha256(
            manifest.get("result_digest"), field="manifest_result_digest"
        ),
        "manifest_root": require_sha256(manifest.get("manifest_root"), field="manifest_root"),
        "target_lane_rows": rows,
        "aggregate_outcome_counts": {
            key: int(aggregate_counts.get(key, 0)) for key in ("C", "P", "N", "E")
        },
        "aggregate_candidate_ceiling": int(aggregate_counts.get("C", 0))
        + int(aggregate_counts.get("P", 0)),
        "receipt_binding_root": domain_rows_digest(
            b"FIN_IA_R14_RECONCILIATION_BINDINGS_V1\0",
            (canonical_json_bytes(row) for row in rows),
        ),
        "transformation_root": transformation_root,
        "transformation_status_counts": dict(sorted(transformation_status_counts.items())),
        "transformation_non_vacuous_count": transformation_non_vacuous,
        "route_registry_digest": canonical_digest(dict(sorted(route_registry.items()))),
    }
    output = with_result_digest(body)
    validate_reconciliation_summary_r14(output)
    return output


def validate_reconciliation_summary_r14(value: Mapping[str, Any]) -> None:
    validate_result_digest(value, code="R14_reconciliation")
    require(
        set(value)
        == {
            "schema_version",
            "manifest_result_digest",
            "manifest_root",
            "target_lane_rows",
            "aggregate_outcome_counts",
            "aggregate_candidate_ceiling",
            "receipt_binding_root",
            "transformation_root",
            "transformation_status_counts",
            "transformation_non_vacuous_count",
            "route_registry_digest",
            "result_digest",
        },
        "R14_reconciliation_keyset_invalid",
    )
    require(
        value.get("schema_version") == RECONCILIATION_SCHEMA_VERSION,
        "R14_reconciliation_schema_invalid",
    )
    rows = list(value.get("target_lane_rows") or ())
    require(
        [_binding_key(row) for row in rows]
        == sorted(
            (target_id, lane)
            for target_id in TARGET_IDS
            for lane in ("source", "compiled")
        ),
        "R14_reconciliation_rows_invalid",
    )
    counts = Counter()
    route_registry: dict[str, str] = {}
    for row in rows:
        require(
            set(row)
            == {
                "target_id",
                "lane",
                "expected_length",
                "outcome_counts",
                "candidate_ceiling",
                "vector_root",
                "detail_root",
                "receipt_result_digest",
                "outcome_keyset_root",
                "route_disposition",
            },
            "R14_reconciliation_row_keyset_invalid",
        )
        row_counts = row["outcome_counts"]
        require(
            set(row_counts) == {"C", "P", "N", "E"}
            and all(
                isinstance(row_counts[key], int) and row_counts[key] >= 0
                for key in ("C", "P", "N", "E")
            )
            and sum(row_counts.values()) == int(row["expected_length"]),
            "R14_reconciliation_row_counts_invalid",
        )
        for field in (
            "vector_root",
            "detail_root",
            "receipt_result_digest",
            "outcome_keyset_root",
        ):
            require_sha256(row.get(field), field=f"reconciliation_{field}")
        route = require_identifier(
            row.get("route_disposition"), field="route_disposition"
        )
        prior = route_registry.setdefault(str(row["target_id"]), route)
        require(prior == route, "R14_reconciliation_target_route_conflict")
        counts.update(row["outcome_counts"])
        require(
            int(row["candidate_ceiling"])
            == int(row["outcome_counts"]["C"]) + int(row["outcome_counts"]["P"]),
            "R14_reconciliation_candidate_ceiling_invalid",
        )
    require(
        {key: int(counts.get(key, 0)) for key in ("C", "P", "N", "E")}
        == value.get("aggregate_outcome_counts"),
        "R14_reconciliation_aggregate_counts_invalid",
    )
    aggregate_candidate_ceiling = int(counts.get("C", 0)) + int(
        counts.get("P", 0)
    )
    require(
        value.get("aggregate_candidate_ceiling") == aggregate_candidate_ceiling,
        "R14_reconciliation_aggregate_candidate_ceiling_invalid",
    )
    require(
        value.get("receipt_binding_root")
        == domain_rows_digest(
            b"FIN_IA_R14_RECONCILIATION_BINDINGS_V1\0",
            (canonical_json_bytes(row) for row in rows),
        ),
        "R14_reconciliation_receipt_binding_root_invalid",
    )
    require(
        value.get("route_registry_digest")
        == canonical_digest(dict(sorted(route_registry.items()))),
        "R14_reconciliation_route_registry_digest_invalid",
    )
    require_sha256(value.get("manifest_result_digest"), field="manifest_result_digest")
    require_sha256(value.get("manifest_root"), field="manifest_root")
    require_sha256(value.get("transformation_root"), field="transformation_root")
    status_counts = value.get("transformation_status_counts")
    require(
        isinstance(status_counts, dict)
        and all(
            bool(require_identifier(key, field="transformation_status"))
            and isinstance(count, int)
            and count >= 0
            for key, count in status_counts.items()
        )
        and isinstance(value.get("transformation_non_vacuous_count"), int)
        and 0
        <= int(value["transformation_non_vacuous_count"])
        <= sum(status_counts.values()),
        "R14_reconciliation_transformation_summary_invalid",
    )


_FORMAL_COMPARE_CONTRACT = (
    "population_manifest_result_digest",
    "population_manifest_root",
    "population_commitment_result_digest",
    "reconciliation_result_digest",
    "program_receipt_result_digest",
    "package_root",
    "event_root",
    "receipt_binding_root",
    "coverage_root",
    "family_root",
    "rank_root",
    "route_registry_digest",
    "transformation_root",
    "vector_bindings",
    "aggregate_outcome_counts",
    "aggregate_candidate_ceiling",
    "r13_delta_receipt_result_digest",
    "r13_delta_root",
    "performance_receipt_result_digest",
    "performance_status",
    "peak_memory_bytes",
    "elapsed_ms",
    "performance_warning_limit_ms",
    "performance_hard_limit_ms",
    "performance_hard_memory_limit_bytes",
    "resource_gate_receipt_result_digest",
    "resource_gate_status",
    "required_free_bytes",
    "observed_free_bytes",
    "durability_probe_receipt_digest",
    "resource_planned_artifact_root",
    "resource_stage_bytes",
    "planned_artifacts",
    "planned_artifact_total_bytes",
    "private_artifact_contract_root",
    "public_artifact_contract_root",
    "critical_mutation_manifest_sha256",
    "critical_mutation_manifest_root",
    "critical_mutation_kill_receipt_sha256",
    "critical_mutation_execution_root",
    "critical_mutation_observation_root",
    "critical_mutation_status",
    "property_manifest_sha256",
    "property_matrix_root",
    "property_receipt_sha256",
    "property_result_root",
    "property_status",
    "model_provider_calls",
)


def formal_compare_contract_r14() -> tuple[str, ...]:
    return _FORMAL_COMPARE_CONTRACT


def _artifact_contract_root(rows: Sequence[Mapping[str, Any]], *, domain: bytes) -> str:
    return domain_rows_digest(domain, (canonical_json_bytes(row) for row in rows))


def validate_preformal_decision_commitment_r14(value: Mapping[str, Any]) -> None:
    validate_result_digest(value, code="R14_preformal_commitment")
    required = {
        "schema_version", "implementation_commit", "implementation_tree",
        "implementation_parent", "population_manifest_result_digest",
        "population_manifest_root", "population_commitment_result_digest",
        "parser_version", "target_topology_digest", "transformation_version",
        "vector_bindings", "receipt_binding_root", "reconciliation_result_digest",
        "program_receipt_result_digest", "package_root", "event_root",
        "coverage_root", "family_root", "rank_root", "aggregate_outcome_counts",
        "aggregate_candidate_ceiling", "transformation_root", "route_registry_digest",
        "r13_delta_receipt_result_digest", "r13_delta_root",
        "performance_receipt_result_digest", "performance_status",
        "peak_memory_bytes", "elapsed_ms", "performance_warning_limit_ms",
        "performance_hard_limit_ms", "performance_hard_memory_limit_bytes",
        "resource_gate_receipt_result_digest",
        "resource_gate_status", "required_free_bytes", "observed_free_bytes",
        "durability_probe_receipt_digest", "resource_planned_artifact_root",
        "resource_stage_bytes",
        "canonical_serializer_identity", "planned_artifacts",
        "planned_artifact_bytes", "planned_artifact_total_bytes",
        "private_artifact_contract_root", "public_artifact_contract_root",
        "critical_mutation_manifest_sha256", "critical_mutation_manifest_root",
        "critical_mutation_kill_receipt_sha256", "critical_mutation_execution_root",
        "critical_mutation_observation_root", "critical_mutation_status",
        "property_manifest_sha256", "property_operator_version", "property_seed",
        "property_matrix_root", "property_receipt_sha256", "property_result_root",
        "property_status", "formal_compare_contract",
        "preview_output_is_compiler_input", "model_provider_calls", "result_digest",
    }
    require(set(value) == required, "R14_preformal_commitment_keyset_invalid")
    require(
        value.get("schema_version") == PREFORMAL_COMMITMENT_SCHEMA_VERSION
        and all(
            bool(_HEX40.fullmatch(str(value.get(field) or "")))
            for field in ("implementation_commit", "implementation_tree", "implementation_parent")
        ),
        "R14_preformal_commitment_git_identity_invalid",
    )
    sha_fields = required - {
        "schema_version", "implementation_commit", "implementation_tree",
        "implementation_parent", "parser_version", "transformation_version",
        "vector_bindings", "aggregate_outcome_counts", "aggregate_candidate_ceiling",
        "performance_status", "peak_memory_bytes", "elapsed_ms",
        "performance_warning_limit_ms", "performance_hard_limit_ms",
        "performance_hard_memory_limit_bytes", "resource_gate_status",
        "required_free_bytes", "observed_free_bytes", "canonical_serializer_identity",
        "resource_stage_bytes",
        "planned_artifacts", "planned_artifact_bytes", "planned_artifact_total_bytes",
        "critical_mutation_status", "property_operator_version", "property_seed",
        "property_status", "formal_compare_contract", "preview_output_is_compiler_input",
        "model_provider_calls", "result_digest",
    }
    for field in sha_fields:
        require_sha256(value.get(field), field=f"preformal_{field}")
    bindings = list(value.get("vector_bindings") or ())
    require(
        [_binding_key(row) for row in bindings]
        == sorted((target_id, lane) for target_id in TARGET_IDS for lane in ("source", "compiled")),
        "R14_preformal_commitment_vector_bindings_invalid",
    )
    planned_rows = list(value.get("planned_artifacts") or ())
    paths: list[str] = []
    for row in planned_rows:
        require(
            isinstance(row, dict)
            and set(row) == {"relative_path", "exact_bytes", "sha256", "semantic_root"}
            and isinstance(row.get("relative_path"), str)
            and type(row.get("exact_bytes")) is int and row["exact_bytes"] >= 0,
            "R14_preformal_commitment_planned_artifact_row_invalid",
        )
        require_sha256(row.get("sha256"), field="preformal_planned_artifact_sha256")
        require_sha256(row.get("semantic_root"), field="preformal_planned_artifact_root")
        paths.append(row["relative_path"])
    private_rows = [row for row in planned_rows if not row["relative_path"].startswith("public/")]
    public_rows = [row for row in planned_rows if row["relative_path"].startswith("public/")]
    planned = value.get("planned_artifact_bytes")
    require(
        paths == sorted(set(paths)) and bool(private_rows) and bool(public_rows)
        and planned == {row["relative_path"]: row["exact_bytes"] for row in planned_rows}
        and value.get("planned_artifact_total_bytes") == sum(planned.values())
        and value.get("private_artifact_contract_root")
        == _artifact_contract_root(private_rows, domain=b"FIN_IA_R14_PRIVATE_ARTIFACT_CONTRACT_V1\0")
        and value.get("public_artifact_contract_root")
        == _artifact_contract_root(public_rows, domain=b"FIN_IA_R14_PUBLIC_ARTIFACT_CONTRACT_V1\0"),
        "R14_preformal_commitment_planned_bytes_invalid",
    )
    require(
        value.get("performance_status") in {"PASS", "PASS_WITH_WARNING"}
        and value.get("performance_warning_limit_ms")
        == FROZEN_WARNING_LIMIT_MS
        and value.get("performance_hard_limit_ms") == FROZEN_HARD_LIMIT_MS
        and value.get("performance_hard_memory_limit_bytes")
        == FROZEN_HARD_MEMORY_LIMIT_BYTES
        and type(value.get("resource_stage_bytes")) is int
        and 0 <= value["resource_stage_bytes"] <= value["required_free_bytes"]
        and value.get("resource_gate_status") == "PASS"
        and value.get("critical_mutation_status") == "PASS_100_PERCENT_KILLED"
        and value.get("property_status") == "PASS"
        and value.get("formal_compare_contract") == list(_FORMAL_COMPARE_CONTRACT)
        and value.get("preview_output_is_compiler_input") is False
        and value.get("model_provider_calls") == 0,
        "R14_preformal_commitment_authority_boundary_invalid",
    )


def build_preformal_decision_commitment_r14(
    *,
    repository_root: Path,
    implementation_commit: str,
    implementation_tree: str,
    implementation_parent: str,
    population_commitment: Mapping[str, Any],
    reconciliation: Mapping[str, Any],
    program_receipt: Mapping[str, Any],
    r13_delta_receipt: Mapping[str, Any],
    performance_receipt: Mapping[str, Any],
    resource_gate_receipt: Mapping[str, Any],
    mutation_manifest: Mapping[str, Any],
    mutation_kill_receipt: Mapping[str, Any],
    property_manifest: Mapping[str, Any],
    property_receipt: Mapping[str, Any],
    requirement_manifest: Mapping[str, Any],
    parser_version: str,
    target_topology_digest: str,
    transformation_version: str,
    canonical_serializer_identity: str,
    planned_artifact_payloads: Mapping[str, bytes],
) -> dict[str, Any]:
    validate_reconciliation_summary_r14(reconciliation)
    validate_population_commitment_r14(population_commitment)
    validate_full_program_receipt_r14(program_receipt)
    validate_r13_to_r14_delta_receipt_r14(r13_delta_receipt)
    validate_performance_receipt_r14(performance_receipt)
    validate_resource_gate_receipt_r14(resource_gate_receipt)
    validate_critical_mutation_manifest_r14(
        mutation_manifest, requirement_manifest=requirement_manifest
    )
    validate_critical_mutation_kill_receipt_r14(
        mutation_kill_receipt, manifest=mutation_manifest
    )
    validate_author_property_manifest_r14(
        property_manifest, requirement_manifest=requirement_manifest
    )
    validate_author_property_receipt_r14(property_receipt, manifest=property_manifest)
    require(
        all(bool(_HEX40.fullmatch(value)) for value in (implementation_commit, implementation_tree, implementation_parent)),
        "R14_preformal_implementation_git_identity_invalid",
    )
    require(
        mutation_kill_receipt.get("implementation_commit")
        == implementation_commit
        and mutation_kill_receipt.get("implementation_tree")
        == implementation_tree,
        "R14_preformal_mutation_git_identity_rebind",
    )
    mutation_source_root = _validate_manifest_source_bindings_against_git_r14(
        manifest=mutation_manifest,
        repository_root=repository_root,
        implementation_commit=implementation_commit,
        implementation_tree=implementation_tree,
    )
    require(
        mutation_source_root
        == mutation_kill_receipt.get("implementation_source_root"),
        "R14_preformal_mutation_git_source_binding_invalid",
    )
    program_counts = program_receipt.get("source_compiled_input_counts") or {}
    require(
        population_commitment.get("manifest_result_digest") == reconciliation.get("manifest_result_digest")
        and population_commitment.get("manifest_root") == reconciliation.get("manifest_root")
        and program_receipt.get("manifest_result_digest") == reconciliation.get("manifest_result_digest")
        and program_receipt.get("binding_root") == reconciliation.get("receipt_binding_root")
        and program_receipt.get("transformation_root") == reconciliation.get("transformation_root")
        and r13_delta_receipt.get("r14_program_receipt_result_digest") == program_receipt.get("result_digest")
        and performance_receipt.get("status") in {"PASS", "PASS_WITH_WARNING"}
        and resource_gate_receipt.get("status") == "PASS"
        and mutation_kill_receipt.get("status") == "PASS_100_PERCENT_KILLED"
        and property_receipt.get("status") == "PASS"
        and mutation_kill_receipt.get("implementation_commit")
        == implementation_commit
        and mutation_kill_receipt.get("implementation_tree")
        == implementation_tree
        and property_receipt.get("implementation_commit")
        == implementation_commit
        and property_receipt.get("implementation_tree") == implementation_tree
        and performance_receipt.get("source_input_count")
        == program_counts.get("source")
        and performance_receipt.get("compiled_input_count")
        == program_counts.get("compiled")
        and performance_receipt.get("logical_decision_count")
        == program_receipt.get("logical_decision_count")
        and performance_receipt.get("warning_limit_ms")
        == FROZEN_WARNING_LIMIT_MS
        and performance_receipt.get("hard_limit_ms") == FROZEN_HARD_LIMIT_MS
        and performance_receipt.get("hard_memory_limit_bytes")
        == FROZEN_HARD_MEMORY_LIMIT_BYTES
        and performance_receipt.get("model_provider_calls") == 0,
        "R14_preformal_evidence_binding_or_gate_failed",
    )
    require(
        resource_gate_receipt.get("implementation_commit")
        == implementation_commit
        and resource_gate_receipt.get("implementation_tree")
        == implementation_tree
        and resource_gate_receipt.get("population_manifest_result_digest")
        == reconciliation.get("manifest_result_digest")
        and resource_gate_receipt.get("program_receipt_result_digest")
        == program_receipt.get("result_digest")
        and resource_gate_receipt.get("performance_receipt_result_digest")
        == performance_receipt.get("result_digest"),
        "R14_preformal_resource_identity_binding_failed",
    )
    require(
        reconciliation.get("transformation_status_counts")
        == {"PASS_PRESERVATION": int(population_commitment["compiled_objects"]["count"])},
        "R14_preformal_transformation_gate_failed",
    )
    planned_artifacts = build_planned_program_artifact_contracts_r14(
        payloads=planned_artifact_payloads,
        program_receipt=program_receipt,
        reconciliation=reconciliation,
    )
    planned_artifact_root = domain_rows_digest(
        b"FIN_IA_R14_RESOURCE_ARTIFACTS_V1\0",
        (canonical_json_bytes(row) for row in planned_artifacts),
    )
    require(
        resource_gate_receipt.get("planned_artifact_root")
        == planned_artifact_root
        and resource_gate_receipt.get("planned_artifact_count")
        == len(planned_artifacts)
        and resource_gate_receipt.get("stage_bytes")
        == sum(row["exact_bytes"] for row in planned_artifacts)
        and resource_gate_receipt.get("durability_probe_receipt_digest"),
        "R14_preformal_resource_artifact_or_capability_binding_failed",
    )
    rows = [
        {
            "target_id": row["target_id"], "lane": row["lane"],
            "vector_root": row["vector_root"], "detail_root": row["detail_root"],
            "outcome_counts": dict(row["outcome_counts"]),
            "receipt_result_digest": row["receipt_result_digest"],
        }
        for row in reconciliation["target_lane_rows"]
    ]
    private_rows = [row for row in planned_artifacts if not row["relative_path"].startswith("public/")]
    public_rows = [row for row in planned_artifacts if row["relative_path"].startswith("public/")]
    body = {
        "schema_version": PREFORMAL_COMMITMENT_SCHEMA_VERSION,
        "implementation_commit": implementation_commit,
        "implementation_tree": implementation_tree,
        "implementation_parent": implementation_parent,
        "population_manifest_result_digest": reconciliation["manifest_result_digest"],
        "population_manifest_root": reconciliation["manifest_root"],
        "population_commitment_result_digest": population_commitment["result_digest"],
        "parser_version": require_identifier(parser_version, field="parser_version"),
        "target_topology_digest": require_sha256(target_topology_digest, field="target_topology"),
        "transformation_version": require_identifier(transformation_version, field="transformation_version"),
        "vector_bindings": rows,
        "receipt_binding_root": reconciliation["receipt_binding_root"],
        "reconciliation_result_digest": reconciliation["result_digest"],
        "program_receipt_result_digest": program_receipt["result_digest"],
        "package_root": program_receipt["package_root"],
        "event_root": program_receipt["event_root"],
        "coverage_root": program_receipt["coverage_root"],
        "family_root": program_receipt["family_root"],
        "rank_root": program_receipt["rank_root"],
        "aggregate_outcome_counts": dict(reconciliation["aggregate_outcome_counts"]),
        "aggregate_candidate_ceiling": reconciliation["aggregate_candidate_ceiling"],
        "transformation_root": reconciliation["transformation_root"],
        "route_registry_digest": reconciliation["route_registry_digest"],
        "r13_delta_receipt_result_digest": r13_delta_receipt["result_digest"],
        "r13_delta_root": r13_delta_receipt["dimension_root"],
        "performance_receipt_result_digest": performance_receipt["result_digest"],
        "performance_status": performance_receipt["status"],
        "peak_memory_bytes": performance_receipt["peak_memory_bytes"],
        "elapsed_ms": performance_receipt["elapsed_ms"],
        "performance_warning_limit_ms": performance_receipt["warning_limit_ms"],
        "performance_hard_limit_ms": performance_receipt["hard_limit_ms"],
        "performance_hard_memory_limit_bytes": performance_receipt[
            "hard_memory_limit_bytes"
        ],
        "resource_gate_receipt_result_digest": resource_gate_receipt["result_digest"],
        "resource_gate_status": resource_gate_receipt["status"],
        "required_free_bytes": resource_gate_receipt["required_free_bytes"],
        "observed_free_bytes": resource_gate_receipt["observed_free_bytes"],
        "durability_probe_receipt_digest": resource_gate_receipt[
            "durability_probe_receipt_digest"
        ],
        "resource_planned_artifact_root": resource_gate_receipt[
            "planned_artifact_root"
        ],
        "resource_stage_bytes": resource_gate_receipt["stage_bytes"],
        "canonical_serializer_identity": require_identifier(canonical_serializer_identity, field="canonical_serializer_identity"),
        "planned_artifacts": planned_artifacts,
        "planned_artifact_bytes": {row["relative_path"]: row["exact_bytes"] for row in planned_artifacts},
        "planned_artifact_total_bytes": sum(row["exact_bytes"] for row in planned_artifacts),
        "private_artifact_contract_root": _artifact_contract_root(private_rows, domain=b"FIN_IA_R14_PRIVATE_ARTIFACT_CONTRACT_V1\0"),
        "public_artifact_contract_root": _artifact_contract_root(public_rows, domain=b"FIN_IA_R14_PUBLIC_ARTIFACT_CONTRACT_V1\0"),
        "critical_mutation_manifest_sha256": sha256_bytes(canonical_json_bytes(mutation_manifest)),
        "critical_mutation_manifest_root": mutation_manifest["case_keyset_root"],
        "critical_mutation_kill_receipt_sha256": sha256_bytes(canonical_json_bytes(mutation_kill_receipt)),
        "critical_mutation_execution_root": mutation_kill_receipt["execution_root"],
        "critical_mutation_observation_root": mutation_kill_receipt["observation_root"],
        "critical_mutation_status": mutation_kill_receipt["status"],
        "property_manifest_sha256": sha256_bytes(canonical_json_bytes(property_manifest)),
        "property_operator_version": property_manifest["operator_version"],
        "property_seed": property_manifest["author_seed"],
        "property_matrix_root": property_manifest["case_root"],
        "property_receipt_sha256": sha256_bytes(canonical_json_bytes(property_receipt)),
        "property_result_root": property_receipt["result_root"],
        "property_status": property_receipt["status"],
        "formal_compare_contract": list(_FORMAL_COMPARE_CONTRACT),
        "preview_output_is_compiler_input": False,
        "model_provider_calls": 0,
    }
    output = with_result_digest(body)
    validate_preformal_decision_commitment_r14(output)
    return output


def validate_public_reconciliation_projection_r14(
    value: Mapping[str, Any],
    *,
    reconciliation: Mapping[str, Any],
    commitment: Mapping[str, Any],
) -> None:
    """Validate the exact publication surface against its private bindings."""
    require(
        isinstance(value, Mapping),
        "R14_public_projection_not_mapping",
    )
    try:
        canonical_value = json.loads(canonical_json_bytes(value).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        require(False, f"R14_public_projection_not_canonical:{type(exc).__name__}")
    require(
        canonical_value == value,
        "R14_public_projection_not_canonical_value",
    )
    validate_result_digest(value, code="R14_public_projection")
    require(
        set(value) == _PUBLIC_PROJECTION_KEYS,
        "R14_public_projection_keyset_invalid",
    )
    require(
        value.get("schema_version") == PUBLIC_PROJECTION_SCHEMA_VERSION,
        "R14_public_projection_schema_invalid",
    )
    validate_reconciliation_summary_r14(reconciliation)
    validate_preformal_decision_commitment_r14(commitment)
    require(
        commitment.get("reconciliation_result_digest")
        == reconciliation.get("result_digest")
        and value.get("commitment_result_digest") == commitment.get("result_digest"),
        "R14_public_projection_commitment_binding_invalid",
    )
    for field in (
        "receipt_binding_root",
        "transformation_root",
        "route_registry_digest",
        "aggregate_outcome_counts",
        "aggregate_candidate_ceiling",
    ):
        require(
            commitment.get(field) == reconciliation.get(field),
            f"R14_public_projection_commitment_mismatch:{field}",
        )

    rows = value.get("target_lane_rows")
    require(
        isinstance(rows, list),
        "R14_public_projection_rows_not_list",
    )
    aggregate_counts = Counter()
    for row in rows:
        require(
            isinstance(row, dict) and set(row) == _PUBLIC_PROJECTION_ROW_KEYS,
            "R14_public_projection_row_keyset_invalid",
        )
        route = row.get("route_disposition")
        require(
            isinstance(route, str),
            "R14_public_projection_route_not_string",
        )
        require(
            "/" not in route and "\\" not in route and "://" not in route,
            "R14_public_projection_private_locator_detected",
        )
        require(
            bool(_PUBLIC_ROUTE_TOKEN.fullmatch(route)),
            "R14_public_projection_raw_text_detected",
        )
        row_counts = row.get("outcome_counts")
        require(
            isinstance(row_counts, dict)
            and set(row_counts) == {"C", "P", "N", "E"}
            and all(type(row_counts[key]) is int and row_counts[key] >= 0 for key in row_counts)
            and type(row.get("expected_length")) is int
            and row["expected_length"] == sum(row_counts.values())
            and type(row.get("candidate_ceiling")) is int
            and row["candidate_ceiling"] == row_counts["C"] + row_counts["P"],
            "R14_public_projection_row_aggregate_invalid",
        )
        aggregate_counts.update(row_counts)
    expected_rows = [
        {
            "target_id": row["target_id"],
            "lane": row["lane"],
            "expected_length": row["expected_length"],
            "outcome_counts": dict(row["outcome_counts"]),
            "candidate_ceiling": row["candidate_ceiling"],
            "route_disposition": row["route_disposition"],
        }
        for row in reconciliation["target_lane_rows"]
    ]
    require(
        rows == expected_rows,
        "R14_public_projection_rows_binding_invalid",
    )
    recomputed_aggregate = {
        key: int(aggregate_counts.get(key, 0)) for key in ("C", "P", "N", "E")
    }
    published_aggregate = value.get("aggregate_outcome_counts")
    require(
        isinstance(published_aggregate, dict)
        and set(published_aggregate) == {"C", "P", "N", "E"}
        and all(type(published_aggregate[key]) is int for key in published_aggregate)
        and published_aggregate == recomputed_aggregate
        == reconciliation.get("aggregate_outcome_counts")
        and type(value.get("aggregate_candidate_ceiling")) is int
        and value.get("aggregate_candidate_ceiling")
        == recomputed_aggregate["C"] + recomputed_aggregate["P"]
        == reconciliation.get("aggregate_candidate_ceiling"),
        "R14_public_projection_aggregate_binding_invalid",
    )
    transformation_counts = value.get("transformation_status_counts")
    require(
        isinstance(transformation_counts, dict)
        and all(
            isinstance(key, str)
            and bool(key)
            and type(count) is int
            and count >= 0
            for key, count in transformation_counts.items()
        )
        and transformation_counts
        == reconciliation.get("transformation_status_counts")
        and type(value.get("transformation_non_vacuous_count")) is int
        and value.get("transformation_non_vacuous_count")
        == reconciliation.get("transformation_non_vacuous_count"),
        "R14_public_projection_transformation_binding_invalid",
    )
    privacy = value.get("privacy_contract")
    require(
        isinstance(privacy, dict)
        and set(privacy) == set(_PUBLIC_PROJECTION_PRIVACY_CONTRACT)
        and all(type(privacy[key]) is bool and privacy[key] is False for key in privacy)
        and privacy == _PUBLIC_PROJECTION_PRIVACY_CONTRACT,
        "R14_public_projection_privacy_contract_invalid",
    )


def project_public_reconciliation_r14(
    *, reconciliation: Mapping[str, Any], commitment: Mapping[str, Any]
) -> dict[str, Any]:
    validate_reconciliation_summary_r14(reconciliation)
    validate_preformal_decision_commitment_r14(commitment)
    require(
        commitment.get("reconciliation_result_digest")
        == reconciliation.get("result_digest"),
        "R14_projector_commitment_mismatch:reconciliation_result_digest",
    )
    for field in (
        "receipt_binding_root",
        "transformation_root",
        "route_registry_digest",
        "aggregate_outcome_counts",
        "aggregate_candidate_ceiling",
    ):
        require(
            commitment.get(field) == reconciliation.get(field),
            f"R14_projector_commitment_mismatch:{field}",
        )
    safe_rows = [
        {
            "target_id": row["target_id"],
            "lane": row["lane"],
            "expected_length": row["expected_length"],
            "outcome_counts": dict(row["outcome_counts"]),
            "candidate_ceiling": row["candidate_ceiling"],
            "route_disposition": row["route_disposition"],
        }
        for row in reconciliation["target_lane_rows"]
    ]
    body = {
        "schema_version": PUBLIC_PROJECTION_SCHEMA_VERSION,
        "commitment_result_digest": commitment["result_digest"],
        "target_lane_rows": safe_rows,
        "aggregate_outcome_counts": dict(reconciliation["aggregate_outcome_counts"]),
        "aggregate_candidate_ceiling": reconciliation["aggregate_candidate_ceiling"],
        "transformation_status_counts": dict(
            reconciliation["transformation_status_counts"]
        ),
        "transformation_non_vacuous_count": reconciliation[
            "transformation_non_vacuous_count"
        ],
        "privacy_contract": dict(_PUBLIC_PROJECTION_PRIVACY_CONTRACT),
    }
    output = with_result_digest(body)
    validate_public_reconciliation_projection_r14(
        output,
        reconciliation=reconciliation,
        commitment=commitment,
    )
    return output


__all__ = [
    "PRIVATE_PROGRAM_ARTIFACT_PATH",
    "PRIVATE_PROGRAM_ARTIFACT_SCHEMA",
    "PREFORMAL_COMMITMENT_SCHEMA_VERSION",
    "PUBLIC_PROGRAM_ARTIFACT_PATH",
    "PUBLIC_PROGRAM_ARTIFACT_SCHEMA",
    "PUBLIC_PROJECTION_SCHEMA_VERSION",
    "RECONCILIATION_SCHEMA_VERSION",
    "build_planned_program_artifact_contracts_r14",
    "build_preformal_decision_commitment_r14",
    "build_reconciliation_summary_r14",
    "formal_compare_contract_r14",
    "project_public_reconciliation_r14",
    "recompute_program_artifact_semantic_root_r14",
    "validate_preformal_decision_commitment_r14",
    "validate_public_reconciliation_projection_r14",
    "validate_reconciliation_summary_r14",
]
