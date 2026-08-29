from __future__ import annotations

from dataclasses import dataclass, replace
from collections import Counter
import json
from pathlib import Path
import time
from typing import Any, Callable, Mapping, Sequence

import psutil

from .dell_report_decision_vector_r14 import build_decision_vector_receipt_r14
from .dell_report_population_manifest_r14 import (
    build_population_commitment_r14,
    validate_input_population_manifest_r14,
)
from .dell_report_population_rebuilder_r14 import rebuild_input_population_r14
from .dell_report_r14_common import (
    TARGET_IDS,
    DellReportR14ContractError,
    canonical_digest,
    canonical_json_bytes,
    domain_rows_digest,
    require,
    sha256_bytes,
    with_result_digest,
)
from .dell_report_program_contract_r14 import (
    RUNNER_VERSION,
    validate_full_program_receipt_r14,
)
from .dell_report_reconciliation_r14 import (
    PRIVATE_PROGRAM_ARTIFACT_PATH,
    PRIVATE_PROGRAM_ARTIFACT_SCHEMA,
    PUBLIC_PROGRAM_ARTIFACT_PATH,
    PUBLIC_PROGRAM_ARTIFACT_SCHEMA,
    build_reconciliation_summary_r14,
    build_planned_program_artifact_contracts_r14,
    recompute_program_artifact_semantic_root_r14,
    validate_preformal_decision_commitment_r14,
)
from .dell_report_resource_gate_r14 import build_performance_receipt_r14
from .dell_report_r14_contracts import R14ContractBundle
from .dell_report_structural_graph_r14 import (
    build_event_argument_graph_r14,
    build_price_attachment_graph_r14,
)
from .dell_report_target_compiler_r14 import (
    TargetDecisionR14,
    build_target_graph_view_r14,
    compile_target_decisions_r14,
)
from .dell_report_transformation_r14 import (
    build_graph_transformation_receipt_from_inventories_r14,
    build_transformation_inventory_r14,
)
from .dell_report_transaction_r14 import (
    CommittedAttemptR14,
    FormalTransactionAuthorityR14,
    load_committed_attempt_replay_material_r14,
)


PARSER_VERSION = "R14_structural_graph_parser_v1"
PRICE_GRAPH_VERSION = "R14_price_attachment_graph_v1"
_FORMAL_RECOMPUTED_OUTPUT_FIELDS = frozenset(
    {
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
        "planned_artifacts",
        "planned_artifact_total_bytes",
        "private_artifact_contract_root",
        "public_artifact_contract_root",
        "model_provider_calls",
    }
)
_FORMAL_COMPILER_INPUT_ENVELOPE_KEYS = frozenset(
    {
        "manifest",
        "source_rows",
        "object_rows",
        "bundle",
        "route_registry",
        "preformal_commitment",
        "bound_preformal_evidence",
    }
)


@dataclass(frozen=True)
class CompiledInputR14:
    input_digest: str
    graph_digest: str
    price_graph_digest: str
    target_view_digest: str
    target_view: Any
    decisions: tuple[TargetDecisionR14, ...]


@dataclass(frozen=True)
class CompiledLaneR14:
    lane: str
    manifest_result_digest: str
    receipts: tuple[Mapping[str, Any], ...]
    details_by_target: Mapping[str, tuple[Mapping[str, Any], ...]]
    compiled_input_count: int
    compiled_by_identity: Mapping[str, CompiledInputR14]
    graph_rows: tuple[Mapping[str, str], ...]
    model_provider_calls: int = 0


@dataclass(frozen=True)
class FullProgramResultR14:
    manifest_result_digest: str
    source_lane: CompiledLaneR14
    compiled_lane: CompiledLaneR14
    transformation_receipts: tuple[Mapping[str, Any], ...]
    reconciliation: Mapping[str, Any]
    program_receipt: Mapping[str, Any]
    model_provider_calls: int = 0


@dataclass(frozen=True)
class FormalCompilerInputEnvelopeR14:
    """Preflighted raw-only inputs consumed by the formal compiler.

    This is intentionally not serializable output from preview. The formal
    entrypoint constructs this value only after validating the exact keyset of
    the caller-supplied production envelope.
    """

    manifest: Mapping[str, Any]
    source_rows: Sequence[Mapping[str, Any]]
    object_rows: Sequence[Mapping[str, Any]]
    bundle: R14ContractBundle
    route_registry: Mapping[str, str]
    preformal_commitment: Mapping[str, Any]
    bound_preformal_evidence: Mapping[str, Any]


def build_formal_compiler_input_envelope_r14(
    *,
    manifest: Mapping[str, Any],
    source_rows: Sequence[Mapping[str, Any]],
    object_rows: Sequence[Mapping[str, Any]],
    bundle: R14ContractBundle,
    route_registry: Mapping[str, str],
    preformal_commitment: Mapping[str, Any],
    bound_preformal_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the only accepted production input envelope for formal."""
    envelope: dict[str, Any] = {
        "manifest": manifest,
        "source_rows": source_rows,
        "object_rows": object_rows,
        "bundle": bundle,
        "route_registry": route_registry,
        "preformal_commitment": preformal_commitment,
        "bound_preformal_evidence": bound_preformal_evidence,
    }
    preflight_formal_compiler_input_envelope_r14(envelope)
    return envelope


def preflight_formal_compiler_input_envelope_r14(
    value: Mapping[str, Any],
) -> FormalCompilerInputEnvelopeR14:
    """Fail closed unless ``value`` is the exact raw-only formal envelope."""
    require(
        isinstance(value, Mapping),
        "R14_formal_compiler_input_envelope_not_mapping",
    )
    string_keys = {key for key in value if isinstance(key, str)}
    require(
        len(string_keys) == len(value),
        "R14_formal_compiler_input_envelope_non_string_key",
    )
    forbidden_preview_keys = sorted(
        key for key in string_keys if key.casefold().startswith("preview")
    )
    require(
        not forbidden_preview_keys,
        "R14_formal_compiler_input_envelope_forbidden_preview_input:"
        + ",".join(forbidden_preview_keys),
    )
    require(
        string_keys == _FORMAL_COMPILER_INPUT_ENVELOPE_KEYS,
        "R14_formal_compiler_input_envelope_keyset_invalid",
    )
    manifest = value["manifest"]
    source_rows = value["source_rows"]
    object_rows = value["object_rows"]
    bundle = value["bundle"]
    route_registry = value["route_registry"]
    preformal_commitment = value["preformal_commitment"]
    bound_preformal_evidence = value["bound_preformal_evidence"]
    require(
        isinstance(manifest, Mapping),
        "R14_formal_compiler_input_envelope_manifest_invalid",
    )
    require(
        isinstance(source_rows, Sequence)
        and not isinstance(source_rows, (str, bytes, bytearray))
        and all(isinstance(row, Mapping) for row in source_rows),
        "R14_formal_compiler_input_envelope_source_rows_invalid",
    )
    require(
        isinstance(object_rows, Sequence)
        and not isinstance(object_rows, (str, bytes, bytearray))
        and all(isinstance(row, Mapping) for row in object_rows),
        "R14_formal_compiler_input_envelope_object_rows_invalid",
    )
    require(
        isinstance(bundle, R14ContractBundle),
        "R14_formal_compiler_input_envelope_bundle_invalid",
    )
    require(
        isinstance(route_registry, Mapping)
        and set(route_registry) == set(TARGET_IDS)
        and all(
            isinstance(target_id, str)
            and isinstance(route, str)
            and bool(route.strip())
            for target_id, route in route_registry.items()
        ),
        "R14_formal_compiler_input_envelope_route_registry_invalid",
    )
    require(
        isinstance(preformal_commitment, Mapping),
        "R14_formal_compiler_input_envelope_commitment_invalid",
    )
    require(
        isinstance(bound_preformal_evidence, Mapping),
        "R14_formal_compiler_input_envelope_evidence_invalid",
    )
    validate_input_population_manifest_r14(manifest)
    validate_preformal_decision_commitment_r14(preformal_commitment)
    return FormalCompilerInputEnvelopeR14(
        manifest=manifest,
        source_rows=source_rows,
        object_rows=object_rows,
        bundle=bundle,
        route_registry=route_registry,
        preformal_commitment=preformal_commitment,
        bound_preformal_evidence=bound_preformal_evidence,
    )


def _compiled_input_private_material_r14(
    value: CompiledInputR14,
) -> dict[str, Any]:
    return {
        "input_digest": value.input_digest,
        "graph_digest": value.graph_digest,
        "price_graph_digest": value.price_graph_digest,
        "target_view_digest": value.target_view_digest,
        "target_view": value.target_view.as_dict(),
        "decisions": [row.as_dict() for row in value.decisions],
    }


def _compiled_lane_private_material_r14(
    value: CompiledLaneR14,
) -> dict[str, Any]:
    return {
        "lane": value.lane,
        "manifest_result_digest": value.manifest_result_digest,
        "receipts": [dict(row) for row in value.receipts],
        "details_by_target": {
            target_id: [dict(row) for row in value.details_by_target[target_id]]
            for target_id in sorted(value.details_by_target)
        },
        "compiled_input_count": value.compiled_input_count,
        "compiled_by_identity": [
            {
                "identity": identity,
                "compiled": _compiled_input_private_material_r14(
                    value.compiled_by_identity[identity]
                ),
            }
            for identity in sorted(value.compiled_by_identity)
        ],
        "graph_rows": [dict(row) for row in value.graph_rows],
        "model_provider_calls": value.model_provider_calls,
    }


def full_program_private_material_r14(
    value: FullProgramResultR14,
) -> dict[str, Any]:
    """Canonical complete private result used by preview, formal and replay."""
    return {
        "schema_version": "fin_ia_dell_03B_R14_full_program_private_material_v1_0",
        "manifest_result_digest": value.manifest_result_digest,
        "source_lane": _compiled_lane_private_material_r14(value.source_lane),
        "compiled_lane": _compiled_lane_private_material_r14(value.compiled_lane),
        "transformation_receipts": [
            dict(row) for row in value.transformation_receipts
        ],
        "reconciliation": dict(value.reconciliation),
        "program_receipt": dict(value.program_receipt),
        "model_provider_calls": value.model_provider_calls,
    }


def build_program_artifact_payloads_r14(
    value: FullProgramResultR14,
) -> dict[str, bytes]:
    material = full_program_private_material_r14(value)
    private = with_result_digest(
        {
            "schema_version": PRIVATE_PROGRAM_ARTIFACT_SCHEMA,
            "program_receipt_result_digest": value.program_receipt[
                "result_digest"
            ],
            "private_material": material,
            "private_material_root": canonical_digest(material),
            "model_provider_calls": value.model_provider_calls,
        }
    )
    public = with_result_digest(
        {
            "schema_version": PUBLIC_PROGRAM_ARTIFACT_SCHEMA,
            "program_receipt_result_digest": value.program_receipt[
                "result_digest"
            ],
            "aggregate_outcome_counts": dict(
                value.reconciliation["aggregate_outcome_counts"]
            ),
            "aggregate_candidate_ceiling": value.reconciliation[
                "aggregate_candidate_ceiling"
            ],
            "privacy_contract": {
                "contains_raw_text": False,
                "contains_model_text": False,
                "contains_private_locator": False,
                "contains_source_or_object_ID_rows": False,
                "contains_decision_details": False,
                "creates_reader_citation": False,
            },
            "model_provider_calls": value.model_provider_calls,
        }
    )
    payloads = {
        PRIVATE_PROGRAM_ARTIFACT_PATH: canonical_json_bytes(private),
        PUBLIC_PROGRAM_ARTIFACT_PATH: canonical_json_bytes(public),
    }
    build_planned_program_artifact_contracts_r14(
        payloads=payloads,
        program_receipt=value.program_receipt,
        reconciliation=value.reconciliation,
    )
    return payloads


def bind_preformal_evidence_for_formal_r14(
    commitment: Mapping[str, Any],
) -> dict[str, Any]:
    """Extract the exact B-bound non-output receipts used by formal.

    The commitment itself must first have been loaded from the verified B
    commit by the authority preflight.  Formal then recomputes every output
    field and compares these remaining immutable evidence fields as one closed
    keyset rather than silently omitting them.
    """
    validate_preformal_decision_commitment_r14(commitment)
    return {
        field: commitment[field]
        for field in commitment["formal_compare_contract"]
        if field not in _FORMAL_RECOMPUTED_OUTPUT_FIELDS
    }


def compile_input_text_r14(
    *, text: str, input_digest: str, bundle: R14ContractBundle
) -> CompiledInputR14:
    event_graph = build_event_argument_graph_r14(text=text, bundle=bundle)
    price_graph = build_price_attachment_graph_r14(graph=event_graph, bundle=bundle)
    view = build_target_graph_view_r14(
        event_graph=event_graph, price_graph=price_graph
    )
    decisions = compile_target_decisions_r14(
        view=view, topology_contract=bundle.topology
    )
    require(
        tuple(row.target_id for row in decisions) == TARGET_IDS,
        "R14_runner_target_population_invalid",
    )
    return CompiledInputR14(
        input_digest=input_digest,
        graph_digest=event_graph.graph_digest,
        price_graph_digest=price_graph.graph_digest,
        target_view_digest=view.view_digest,
        target_view=view,
        decisions=decisions,
    )


def _row_identity(row: Mapping[str, Any], *, lane: str) -> str:
    field = "evidence_id" if lane == "source" else "compiled_object_id"
    value = str(row.get(field) or "").strip()
    require(bool(value), f"R14_runner_{lane}_identity_missing")
    return value


def _row_text(row: Mapping[str, Any], *, lane: str) -> str:
    field = "text" if lane == "source" else "model_text"
    value = row.get(field)
    require(isinstance(value, str), f"R14_runner_{lane}_text_not_string")
    return value


def _decision_cell(
    *,
    entry: Mapping[str, Any],
    target_id: str,
    lane: str,
    compiled: CompiledInputR14,
    topology_digest: str,
) -> dict[str, Any]:
    decision = next(row for row in compiled.decisions if row.target_id == target_id)
    if decision.outcome == "C":
        detail: dict[str, Any] = {
            "accepted_event_ids": list(decision.event_ids),
            "target_topology_digest": topology_digest,
            "package_digest": decision.decision_digest,
        }
    elif decision.outcome == "P":
        require(decision.proof_ids, "R14_runner_partial_without_candidate_proof")
        detail = {
            "candidate_proof_ids": list(decision.proof_ids),
            "limitations": list(
                sorted(set((*decision.missing_roles, *decision.reason_codes)))
            ),
            "graph_digest": compiled.target_view_digest,
        }
    else:
        require(decision.outcome == "N", "R14_runner_unexpected_compiler_outcome")
        detail = {}
    return {
        "manifest_index": entry["manifest_index"],
        "input_digest": entry["input_digest"],
        "target_id": target_id,
        "lane": lane,
        "outcome": decision.outcome,
        "detail": detail,
    }


def compile_manifest_lane_r14(
    *,
    manifest: Mapping[str, Any],
    raw_rows: Sequence[Mapping[str, Any]],
    lane: str,
    bundle: R14ContractBundle,
    pre_registered_malformed_input_digests: Sequence[str] = (),
    retain_compiled_inputs: bool = True,
    compiled_observer: Callable[
        [str, Mapping[str, Any], CompiledInputR14], None
    ]
    | None = None,
) -> CompiledLaneR14:
    """Compile one full manifest lane without reading any preview result."""
    validate_input_population_manifest_r14(manifest)
    require(lane in {"source", "compiled"}, "R14_runner_lane_invalid")
    entry_key = (
        "source_canonical_order" if lane == "source" else "object_canonical_order"
    )
    identity_key = "source_record_id" if lane == "source" else "compiled_object_id"
    entries = list(manifest[entry_key])
    raw_by_id: dict[str, Mapping[str, Any]] = {}
    for raw in raw_rows:
        row_id = _row_identity(raw, lane=lane)
        require(row_id not in raw_by_id, f"R14_runner_{lane}_duplicate:{row_id}")
        raw_by_id[row_id] = raw
    require(
        set(raw_by_id) == {str(row[identity_key]) for row in entries},
        f"R14_runner_{lane}_raw_population_mismatch",
    )
    malformed = set(pre_registered_malformed_input_digests)
    cells_by_target: dict[str, list[dict[str, Any]]] = {
        target_id: [] for target_id in TARGET_IDS
    }
    compiled_by_identity: dict[str, CompiledInputR14] = {}
    graph_rows: list[Mapping[str, str]] = []
    compiled_text_cache: dict[str, CompiledInputR14] = {}
    text_field = "text" if lane == "source" else "model_text"
    text_key_counts = Counter(
        sha256_bytes(value.encode("utf-8"))
        for raw in raw_rows
        for value in [raw.get(text_field)]
        if isinstance(value, str)
    )
    topology_digest = str(bundle.topology["result_digest"])
    for entry in entries:
        raw = raw_by_id[str(entry[identity_key])]
        require(
            canonical_digest(dict(raw)) == entry["input_digest"],
            f"R14_runner_{lane}_input_digest_mismatch:{entry['manifest_index']}",
        )
        try:
            text_value = _row_text(raw, lane=lane)
            text_key = sha256_bytes(text_value.encode("utf-8"))
            cached = compiled_text_cache.get(text_key)
            if cached is None:
                compiled = compile_input_text_r14(
                    text=text_value,
                    input_digest=str(entry["input_digest"]),
                    bundle=bundle,
                )
                if text_key_counts[text_key] > 1:
                    compiled_text_cache[text_key] = compiled
            else:
                compiled = replace(
                    cached,
                    input_digest=str(entry["input_digest"]),
                )
        except DellReportR14ContractError as exc:
            require(
                entry["input_digest"] in malformed,
                f"R14_runner_unregistered_typed_error:{entry['manifest_index']}:{exc}",
            )
            for target_id in TARGET_IDS:
                cells_by_target[target_id].append(
                    {
                        "manifest_index": entry["manifest_index"],
                        "input_digest": entry["input_digest"],
                        "target_id": target_id,
                        "lane": lane,
                        "outcome": "E",
                        "detail": {
                            "malformed_input_key": entry["input_digest"],
                            "typed_error_code": str(exc),
                        },
                    }
                )
            continue
        identity = str(entry[identity_key])
        graph_rows.append(
            {
                "identity": identity,
                "input_digest": compiled.input_digest,
                "event_graph_digest": compiled.graph_digest,
                "price_graph_digest": compiled.price_graph_digest,
                "target_view_digest": compiled.target_view_digest,
            }
        )
        if compiled_observer is not None:
            compiled_observer(identity, entry, compiled)
        if retain_compiled_inputs:
            compiled_by_identity[identity] = compiled
        for target_id in TARGET_IDS:
            cells_by_target[target_id].append(
                _decision_cell(
                    entry=entry,
                    target_id=target_id,
                    lane=lane,
                    compiled=compiled,
                    topology_digest=topology_digest,
                )
            )

    receipts: list[Mapping[str, Any]] = []
    details_by_target: dict[str, tuple[Mapping[str, Any], ...]] = {}
    for target_id in TARGET_IDS:
        receipt, details = build_decision_vector_receipt_r14(
            manifest=manifest,
            target_id=target_id,
            lane=lane,
            cells=cells_by_target[target_id],
            parser_version=PARSER_VERSION,
            target_topology_digest=topology_digest,
            price_graph_version=PRICE_GRAPH_VERSION,
            pre_registered_malformed_keys=tuple(sorted(malformed)),
        )
        receipts.append(receipt)
        details_by_target[target_id] = details
    return CompiledLaneR14(
        lane=lane,
        manifest_result_digest=str(manifest["result_digest"]),
        receipts=tuple(receipts),
        details_by_target=details_by_target,
        compiled_input_count=len(entries),
        compiled_by_identity=compiled_by_identity,
        graph_rows=tuple(graph_rows),
    )


def _extraction_receipt_digest(
    *, lane: str, identity: str, compiled: CompiledInputR14
) -> str:
    return canonical_digest(
        {
            "schema_version": "fin_ia_dell_03B_R14_extraction_gate_receipt_v1_0",
            "lane": lane,
            "identity": identity,
            "input_digest": compiled.input_digest,
            "event_graph_digest": compiled.graph_digest,
            "price_graph_digest": compiled.price_graph_digest,
            "target_view_digest": compiled.target_view_digest,
            "status": "PASS_RECOMPUTED_FROM_RAW_INPUT",
        }
    )


def _compile_bound_source_slice_r14(
    *,
    source_row: Mapping[str, Any],
    source_entry: Mapping[str, Any],
    object_row: Mapping[str, Any],
    object_entry: Mapping[str, Any],
    bundle: R14ContractBundle,
) -> CompiledInputR14:
    object_id = str(object_entry["compiled_object_id"])
    base = dict(object_row.get("base_object_view") or {})
    focus = dict(base.get("focus_binding") or {})
    mode = str(focus.get("mode") or "")
    surface_text = base.get("surface_text")
    require(
        canonical_digest(dict(source_row)) == source_entry["input_digest"]
        == object_entry["source_record_input_digest"]
        and str(base.get("source_record_id") or "")
        == source_entry["source_record_id"]
        == object_entry["primary_source_record_id"]
        and isinstance(surface_text, str)
        and canonical_digest(surface_text) == object_entry["source_slice_digest"]
        and mode == object_entry["source_slice_mode"],
        f"R14_runner_source_slice_binding_mismatch:{object_id}",
    )
    if mode == "parent_context":
        context = focus.get("parent_context")
        context_fields = (
            "ticker",
            "company",
            "source_type",
            "source_tier",
            "publication_date",
            "period_end",
            "fiscal_year",
            "section",
            "subsection",
        )
        source_metadata = dict(source_row.get("metadata") or {})
        projected_context: dict[str, Any] = {}
        if isinstance(context, dict):
            for key in context:
                if (
                    key == "fiscal_year"
                    and source_metadata.get("reported_fiscal_year") is not None
                ):
                    projected_context[key] = source_metadata[
                        "reported_fiscal_year"
                    ]
                elif (
                    key == "period_end"
                    and source_metadata.get("reported_period_end") is not None
                ):
                    projected_context[key] = source_metadata[
                        "reported_period_end"
                    ]
                else:
                    projected_context[key] = (
                        source_row[key]
                        if key in source_row
                        else source_metadata.get(key)
                    )
        require(
            set(focus) == {"mode", "parent_context"}
            and isinstance(context, dict)
            and set(context).issubset(context_fields)
            and context == projected_context
            and surface_text
            == "\n".join(
                f"{key}: {context[key]}"
                for key in context_fields
                if key in context
                and context[key] is not None
                and context[key] != ""
            ),
            f"R14_runner_source_slice_parent_context_mismatch:{object_id}",
        )
    else:
        start = focus.get("char_start")
        end = focus.get("char_end")
        source_text = source_row.get("text")
        require(
            mode in {"balanced_table", "exact_text", "offset_bound_text"}
            and type(start) is int
            and type(end) is int
            and isinstance(source_text, str)
            and 0 <= start <= end <= len(source_text)
            and source_text[start:end] == surface_text,
            f"R14_runner_source_slice_offset_mismatch:{object_id}",
        )
    expected_binding = canonical_digest(
        {
            "source_record_id": object_entry["primary_source_record_id"],
            "source_record_input_digest": object_entry[
                "source_record_input_digest"
            ],
            "source_slice_mode": object_entry["source_slice_mode"],
            "source_slice_digest": object_entry["source_slice_digest"],
            "object_metadata_digest": object_entry["metadata_digest"],
        }
    )
    require(
        object_entry["source_slice_binding_digest"] == expected_binding,
        f"R14_runner_source_slice_commitment_mismatch:{object_id}",
    )
    return compile_input_text_r14(
        text=surface_text,
        input_digest=str(object_entry["source_slice_digest"]),
        bundle=bundle,
    )


def _program_receipt_r14(
    *,
    manifest: Mapping[str, Any],
    source_lane: CompiledLaneR14,
    compiled_lane: CompiledLaneR14,
    transformation_receipts: Sequence[Mapping[str, Any]],
    reconciliation: Mapping[str, Any],
) -> dict[str, Any]:
    package_rows: list[Mapping[str, Any]] = []
    rank_rows: list[Mapping[str, Any]] = []
    for lane in (source_lane, compiled_lane):
        for target_id in sorted(lane.details_by_target):
            for detail in lane.details_by_target[target_id]:
                package_rows.append(
                    {
                        "lane": lane.lane,
                        "target_id": target_id,
                        "detail_digest": canonical_digest(detail),
                    }
                )
            receipt = next(
                row for row in lane.receipts if row["target_id"] == target_id
            )
            rank_rows.append(
                {
                    "lane": lane.lane,
                    "target_id": target_id,
                    "vector_root": receipt["vector_root"],
                    "outcome_counts": dict(receipt["outcome_counts"]),
                }
            )
    coverage_rows = [
        {
            "target_id": row["target_id"],
            "lane": row["lane"],
            "expected_length": row["expected_length"],
            "vector_root": row["vector_root"],
            "detail_root": row["detail_root"],
        }
        for row in reconciliation["target_lane_rows"]
    ]
    family_rows = [
        {
            "lane": "source",
            "manifest_index": row["manifest_index"],
            "canonical_source_family_id": row["canonical_source_family_id"],
        }
        for row in manifest["source_canonical_order"]
    ]
    event_rows = sorted(
        [*source_lane.graph_rows, *compiled_lane.graph_rows],
        key=lambda row: (row["input_digest"], row["identity"]),
    )
    body = {
        "schema_version": "fin_ia_dell_03B_R14_full_program_receipt_v1_0",
        "runner_version": RUNNER_VERSION,
        "manifest_result_digest": manifest["result_digest"],
        "source_compiled_input_counts": {
            "source": source_lane.compiled_input_count,
            "compiled": compiled_lane.compiled_input_count,
        },
        "logical_decision_count": sum(
            int(row["expected_length"])
            for row in reconciliation["target_lane_rows"]
        ),
        "package_root": domain_rows_digest(
            b"FIN_IA_R14_PROGRAM_PACKAGES_V1\0",
            (canonical_json_bytes(row) for row in package_rows),
        ),
        "event_root": domain_rows_digest(
            b"FIN_IA_R14_PROGRAM_EVENTS_V1\0",
            (canonical_json_bytes(row) for row in event_rows),
        ),
        "binding_root": reconciliation["receipt_binding_root"],
        "coverage_root": domain_rows_digest(
            b"FIN_IA_R14_PROGRAM_COVERAGE_V1\0",
            (canonical_json_bytes(row) for row in coverage_rows),
        ),
        "family_root": domain_rows_digest(
            b"FIN_IA_R14_PROGRAM_FAMILIES_V1\0",
            (canonical_json_bytes(row) for row in family_rows),
        ),
        "rank_root": domain_rows_digest(
            b"FIN_IA_R14_PROGRAM_RANKS_V1\0",
            (canonical_json_bytes(row) for row in rank_rows),
        ),
        "route_root": reconciliation["route_registry_digest"],
        "transformation_root": reconciliation["transformation_root"],
        "candidate_ceiling": reconciliation["aggregate_candidate_ceiling"],
        "family_count": len(
            {row["canonical_source_family_id"] for row in family_rows}
        ),
        "rank_summary": rank_rows,
        "route_summary": [
            {
                "target_id": row["target_id"],
                "lane": row["lane"],
                "route_disposition": row["route_disposition"],
            }
            for row in reconciliation["target_lane_rows"]
        ],
        "transformation_count": len(transformation_receipts),
        "model_provider_calls": 0,
    }
    output = with_result_digest(body)
    validate_full_program_receipt_r14(output)
    return output


def build_full_program_r14(
    *,
    manifest: Mapping[str, Any],
    source_rows: Sequence[Mapping[str, Any]],
    object_rows: Sequence[Mapping[str, Any]],
    bundle: R14ContractBundle,
    route_registry: Mapping[str, str],
) -> FullProgramResultR14:
    """Run both full lanes and exact source-to-object preservation in one call."""
    validate_input_population_manifest_r14(manifest)
    independent_population = rebuild_input_population_r14(
        source_rows=source_rows,
        object_rows=object_rows,
    )
    independently_rebuilt_fields = (
        "target_ids",
        "source_canonical_order",
        "object_canonical_order",
        "parent_document_receipts",
        "canonical_source_family_count",
        "expected_lane_counts",
        "source_keyset_digest",
        "object_keyset_digest",
        "parent_document_receipt_root",
        "canonical_family_occurrence_digest",
        "target_cross_product_digest",
        "manifest_root",
    )
    require(
        all(
            manifest.get(field) == independent_population.get(field)
            for field in independently_rebuilt_fields
        ),
        "R14_runner_independent_population_rebuild_mismatch",
    )
    source_lane = compile_manifest_lane_r14(
        manifest=manifest,
        raw_rows=source_rows,
        lane="source",
        bundle=bundle,
        retain_compiled_inputs=False,
    )
    source_entry_by_id = {
        row["source_record_id"]: row for row in manifest["source_canonical_order"]
    }
    source_raw_by_id = {_row_identity(row, lane="source"): row for row in source_rows}
    object_raw_by_id = {
        _row_identity(row, lane="compiled"): row for row in object_rows
    }
    source_slice_counts = Counter(
        canonical_digest(str((row.get("base_object_view") or {}).get("surface_text")))
        for row in object_rows
    )
    source_slice_cache: dict[str, CompiledInputR14] = {}
    transformations: list[Mapping[str, Any]] = []

    def observe_compiled(
        object_id: str, entry: Mapping[str, Any], object_compiled: CompiledInputR14
    ) -> None:
        source_id = str(entry["primary_source_record_id"])
        source_entry = source_entry_by_id[source_id]
        object_raw = object_raw_by_id[object_id]
        slice_key = str(entry["source_slice_digest"])
        source_slice_compiled = source_slice_cache.get(slice_key)
        if source_slice_compiled is None:
            source_slice_compiled = _compile_bound_source_slice_r14(
                source_row=source_raw_by_id[source_id],
                source_entry=source_entry,
                object_row=object_raw,
                object_entry=entry,
                bundle=bundle,
            )
            if source_slice_counts[slice_key] > 1:
                source_slice_cache[slice_key] = source_slice_compiled
        transformations.append(
            build_graph_transformation_receipt_from_inventories_r14(
                source_inventory_receipt=(
                    build_transformation_inventory_r14(
                        source_slice_compiled.target_view
                    )
                ),
                compiled_inventory_receipt=build_transformation_inventory_r14(
                    object_compiled.target_view
                ),
                source_manifest_index=source_entry["manifest_index"],
                compiled_manifest_index=entry["manifest_index"],
                source_record_id=source_id,
                compiled_object_id=object_id,
                source_input_digest=source_entry["input_digest"],
                source_slice_mode=entry["source_slice_mode"],
                source_slice_digest=entry["source_slice_digest"],
                source_slice_binding_digest=entry[
                    "source_slice_binding_digest"
                ],
                compiled_input_digest=entry["input_digest"],
                canonical_source_family_id=entry["canonical_source_family_id"],
                compiled_lineage_source_record_ids=tuple(entry["lineage_source_record_ids"]),
                compiled_lineage_source_keyset_digest=entry["lineage_source_keyset_digest"],
                source_extraction_receipt_digest=(
                    _extraction_receipt_digest(
                        lane="source_slice",
                        identity=f"{source_id}::{object_id}",
                        compiled=source_slice_compiled,
                    )
                ),
                compiled_extraction_receipt_digest=_extraction_receipt_digest(
                    lane="compiled", identity=object_id, compiled=object_compiled
                ),
                source_extraction_passed=True,
                compiled_extraction_passed=True,
            )
        )

    compiled_lane = compile_manifest_lane_r14(
        manifest=manifest,
        raw_rows=object_rows,
        lane="compiled",
        bundle=bundle,
        retain_compiled_inputs=False,
        compiled_observer=observe_compiled,
    )
    require(
        len(source_lane.graph_rows)
        == len(manifest["source_canonical_order"])
        and len(compiled_lane.graph_rows)
        == len(manifest["object_canonical_order"]),
        "R14_full_program_malformed_or_missing_compiled_input",
    )
    details = {
        **{
            (target_id, "source"): rows
            for target_id, rows in source_lane.details_by_target.items()
        },
        **{
            (target_id, "compiled"): rows
            for target_id, rows in compiled_lane.details_by_target.items()
        },
    }
    reconciliation = build_reconciliation_summary_r14(
        manifest=manifest,
        receipts=(*source_lane.receipts, *compiled_lane.receipts),
        details_by_target_lane=details,
        transformation_receipts=transformations,
        route_registry=route_registry,
    )
    program_receipt = _program_receipt_r14(
        manifest=manifest,
        source_lane=source_lane,
        compiled_lane=compiled_lane,
        transformation_receipts=transformations,
        reconciliation=reconciliation,
    )
    return FullProgramResultR14(
        manifest_result_digest=str(manifest["result_digest"]),
        source_lane=source_lane,
        compiled_lane=compiled_lane,
        transformation_receipts=tuple(transformations),
        reconciliation=reconciliation,
        program_receipt=program_receipt,
    )


def run_formal_recompute_and_compare_r14(
    *,
    input_envelope: Mapping[str, Any] | None = None,
    **formal_inputs: Any,
) -> FullProgramResultR14:
    """Consume one exact raw-only envelope, then compare committed outputs.

    Existing keyword callers are accepted as a migration shim, but those
    keywords are first collected into the same exact-key envelope. Supplying
    an explicit envelope and parallel keyword inputs is always rejected.
    """
    require(
        input_envelope is None or not formal_inputs,
        "R14_formal_compiler_input_envelope_mixed_call_invalid",
    )
    envelope = preflight_formal_compiler_input_envelope_r14(
        formal_inputs if input_envelope is None else input_envelope
    )
    result = build_full_program_r14(
        manifest=envelope.manifest,
        source_rows=envelope.source_rows,
        object_rows=envelope.object_rows,
        bundle=envelope.bundle,
        route_registry=envelope.route_registry,
    )
    reconciliation = result.reconciliation
    program_receipt = result.program_receipt
    actual_bindings = [
        {
            "target_id": row["target_id"],
            "lane": row["lane"],
            "vector_root": row["vector_root"],
            "detail_root": row["detail_root"],
            "outcome_counts": dict(row["outcome_counts"]),
            "receipt_result_digest": row["receipt_result_digest"],
        }
        for row in reconciliation["target_lane_rows"]
    ]
    artifact_payloads = build_program_artifact_payloads_r14(result)
    artifact_rows = build_planned_program_artifact_contracts_r14(
        payloads=artifact_payloads,
        program_receipt=program_receipt,
        reconciliation=reconciliation,
    )
    private_rows = [
        row for row in artifact_rows if not row["relative_path"].startswith("public/")
    ]
    public_rows = [
        row for row in artifact_rows if row["relative_path"].startswith("public/")
    ]
    manifest_bytes = canonical_json_bytes(envelope.manifest)
    population_commitment = build_population_commitment_r14(
        envelope.manifest,
        private_sha256=sha256_bytes(manifest_bytes),
        private_bytes=len(manifest_bytes),
    )
    recomputed = {
        "population_manifest_result_digest": result.manifest_result_digest,
        "population_manifest_root": envelope.manifest["manifest_root"],
        "population_commitment_result_digest": population_commitment[
            "result_digest"
        ],
        "reconciliation_result_digest": reconciliation["result_digest"],
        "program_receipt_result_digest": program_receipt["result_digest"],
        "package_root": program_receipt["package_root"],
        "event_root": program_receipt["event_root"],
        "receipt_binding_root": reconciliation["receipt_binding_root"],
        "coverage_root": program_receipt["coverage_root"],
        "family_root": program_receipt["family_root"],
        "rank_root": program_receipt["rank_root"],
        "route_registry_digest": reconciliation["route_registry_digest"],
        "transformation_root": reconciliation["transformation_root"],
        "vector_bindings": actual_bindings,
        "aggregate_outcome_counts": dict(
            reconciliation["aggregate_outcome_counts"]
        ),
        "aggregate_candidate_ceiling": reconciliation[
            "aggregate_candidate_ceiling"
        ],
        "planned_artifacts": artifact_rows,
        "planned_artifact_total_bytes": sum(
            row["exact_bytes"] for row in artifact_rows
        ),
        "private_artifact_contract_root": domain_rows_digest(
            b"FIN_IA_R14_PRIVATE_ARTIFACT_CONTRACT_V1\0",
            (canonical_json_bytes(row) for row in private_rows),
        ),
        "public_artifact_contract_root": domain_rows_digest(
            b"FIN_IA_R14_PUBLIC_ARTIFACT_CONTRACT_V1\0",
            (canonical_json_bytes(row) for row in public_rows),
        ),
        "model_provider_calls": result.model_provider_calls,
    }
    evidence_fields = tuple(
        field
        for field in envelope.preformal_commitment["formal_compare_contract"]
        if field not in _FORMAL_RECOMPUTED_OUTPUT_FIELDS
    )
    require(
        set(envelope.bound_preformal_evidence) == set(evidence_fields),
        "R14_formal_bound_preformal_evidence_keyset_invalid",
    )
    recomputed.update(dict(envelope.bound_preformal_evidence))
    for field in envelope.preformal_commitment["formal_compare_contract"]:
        require(
            recomputed[field] == envelope.preformal_commitment[field],
            f"R14_formal_commitment_mismatch:{field}",
        )
    return result


def run_measured_full_program_r14(
    *,
    warning_limit_ms: int,
    hard_limit_ms: int,
    hard_memory_limit_bytes: int,
    **program_kwargs: Any,
) -> tuple[FullProgramResultR14, Mapping[str, Any]]:
    process = psutil.Process()
    started = time.perf_counter_ns()
    result = build_full_program_r14(**program_kwargs)
    elapsed_ms = max(0, (time.perf_counter_ns() - started) // 1_000_000)
    memory = process.memory_info()
    peak_memory_bytes = int(getattr(memory, "peak_wset", memory.rss))
    counts = result.program_receipt["source_compiled_input_counts"]
    receipt = build_performance_receipt_r14(
        source_input_count=int(counts["source"]),
        compiled_input_count=int(counts["compiled"]),
        logical_decision_count=int(result.program_receipt["logical_decision_count"]),
        elapsed_ms=int(elapsed_ms),
        peak_memory_bytes=int(peak_memory_bytes),
        warning_limit_ms=warning_limit_ms,
        hard_limit_ms=hard_limit_ms,
        hard_memory_limit_bytes=hard_memory_limit_bytes,
    )
    require(
        receipt["status"] != "FAIL_HARD_LIMIT",
        "R14_full_program_performance_hard_limit_exceeded",
    )
    return result, receipt


def replay_full_program_exact_r14(
    *,
    repository_root: Path,
    committed_attempt: CommittedAttemptR14,
    formal_authority: FormalTransactionAuthorityR14,
    formal_policy: Mapping[str, Any],
    manifest: Mapping[str, Any],
    source_rows: Sequence[Mapping[str, Any]],
    object_rows: Sequence[Mapping[str, Any]],
    bundle: R14ContractBundle,
    route_registry: Mapping[str, str],
) -> Mapping[str, Any]:
    """Recompute once and compare with one immutable committed transaction."""
    committed_artifacts, replay_binding = (
        load_committed_attempt_replay_material_r14(
            repository_root=repository_root,
            committed_attempt=committed_attempt,
            authority=formal_authority,
            formal_policy=formal_policy,
        )
    )
    recomputed = build_full_program_r14(
        manifest=manifest,
        source_rows=source_rows,
        object_rows=object_rows,
        bundle=bundle,
        route_registry=route_registry,
    )
    recomputed_material = full_program_private_material_r14(recomputed)
    recomputed_material_bytes = canonical_json_bytes(recomputed_material)
    recomputed_artifacts = build_program_artifact_payloads_r14(recomputed)
    require(
        set(recomputed_artifacts)
        == set(committed_artifacts)
        == {PRIVATE_PROGRAM_ARTIFACT_PATH, PUBLIC_PROGRAM_ARTIFACT_PATH},
        "R14_replay_artifact_pathset_mismatch",
    )
    recomputed_contracts = build_planned_program_artifact_contracts_r14(
        payloads=recomputed_artifacts,
        program_receipt=recomputed.program_receipt,
        reconciliation=recomputed.reconciliation,
    )
    recomputed_by_path = {
        row["relative_path"]: row for row in recomputed_contracts
    }
    committed_by_path = {
        row["relative_path"]: row
        for row in replay_binding["artifact_contracts"]
    }
    require(
        tuple(sorted(recomputed_by_path))
        == tuple(sorted(committed_by_path))
        == formal_authority.expected_artifact_paths,
        "R14_replay_artifact_contract_pathset_mismatch",
    )
    for relative_path in formal_authority.expected_artifact_paths:
        current_payload = recomputed_artifacts[relative_path]
        committed_payload = committed_artifacts[relative_path]
        try:
            committed_value = json.loads(committed_payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            require(
                False,
                f"R14_replay_committed_artifact_JSON_invalid:{relative_path}:{exc}",
            )
        require(
            isinstance(committed_value, dict)
            and canonical_json_bytes(committed_value) == committed_payload,
            f"R14_replay_committed_artifact_not_canonical:{relative_path}",
        )
        current_semantic_root = recompute_program_artifact_semantic_root_r14(
            relative_path=relative_path,
            payload=current_payload,
        )
        committed_semantic_root = recompute_program_artifact_semantic_root_r14(
            relative_path=relative_path,
            payload=committed_payload,
        )
        authority_contract = dict(
            formal_authority.expected_artifact_contracts[relative_path]
        )
        require(
            current_payload == committed_payload,
            f"R14_replay_canonical_bytes_mismatch:{relative_path}",
        )
        require(
            len(current_payload)
            == len(committed_payload)
            == recomputed_by_path[relative_path]["exact_bytes"]
            == committed_by_path[relative_path]["exact_bytes"]
            == authority_contract["exact_bytes"],
            f"R14_replay_size_mismatch:{relative_path}",
        )
        require(
            sha256_bytes(current_payload)
            == sha256_bytes(committed_payload)
            == recomputed_by_path[relative_path]["sha256"]
            == committed_by_path[relative_path]["sha256"]
            == authority_contract["sha256"],
            f"R14_replay_SHA256_mismatch:{relative_path}",
        )
        require(
            current_semantic_root
            == committed_semantic_root
            == recomputed_by_path[relative_path]["semantic_root"]
            == committed_by_path[relative_path]["semantic_root"]
            == authority_contract["semantic_root"],
            f"R14_replay_semantic_root_mismatch:{relative_path}",
        )

    committed_private = json.loads(
        committed_artifacts[PRIVATE_PROGRAM_ARTIFACT_PATH].decode("utf-8")
    )
    require(
        committed_private.get("private_material") == recomputed_material
        and committed_private.get("private_material_root")
        == canonical_digest(recomputed_material),
        "R14_replay_private_material_root_mismatch",
    )
    return with_result_digest(
        {
            "schema_version": "fin_ia_dell_03B_R14_exact_replay_receipt_v1_1",
            "program_receipt_result_digest": recomputed.program_receipt[
                "result_digest"
            ],
            "committed_attempt_id": replay_binding["attempt_id"],
            "committed_transaction_manifest_result_digest": replay_binding[
                "transaction_manifest_result_digest"
            ],
            "committed_marker_result_digest": replay_binding[
                "committed_marker_result_digest"
            ],
            "committed_bundle_root": replay_binding["transaction_bundle_root"],
            "committed_sidecar_root": replay_binding["sidecar_root"],
            "policy_commit": replay_binding["policy_commit"],
            "policy_result_digest": replay_binding["policy_result_digest"],
            "authority_evidence_digest": replay_binding[
                "authority_evidence_digest"
            ],
            "replay_binding_result_digest": replay_binding["result_digest"],
            "private_material_bytes": len(recomputed_material_bytes),
            "private_material_sha256": sha256_bytes(recomputed_material_bytes),
            "private_material_root": canonical_digest(recomputed_material),
            "artifact_contracts": recomputed_contracts,
            "recomputed_program_count": 1,
            "exact_bytes_equal": True,
            "model_provider_calls": 0,
        }
    )


__all__ = [
    "CompiledInputR14",
    "CompiledLaneR14",
    "FormalCompilerInputEnvelopeR14",
    "FullProgramResultR14",
    "PARSER_VERSION",
    "PRICE_GRAPH_VERSION",
    "RUNNER_VERSION",
    "build_full_program_r14",
    "build_formal_compiler_input_envelope_r14",
    "build_program_artifact_payloads_r14",
    "bind_preformal_evidence_for_formal_r14",
    "compile_input_text_r14",
    "compile_manifest_lane_r14",
    "full_program_private_material_r14",
    "preflight_formal_compiler_input_envelope_r14",
    "replay_full_program_exact_r14",
    "run_measured_full_program_r14",
    "run_formal_recompute_and_compare_r14",
    "validate_full_program_receipt_r14",
]
