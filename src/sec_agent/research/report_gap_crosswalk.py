from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any, Mapping, Sequence

from sec_agent.canonical_runtime import canonical_digest


BASELINE_SCHEMA_VERSION = "fin_ia_dell_source_report_quality_baseline_manifest_v1_0"
BASELINE_VERIFICATION_SCHEMA_VERSION = (
    "fin_ia_dell_source_report_quality_baseline_verification_v1_0"
)
EVALUATION_PROTOCOL_SCHEMA_VERSION = (
    "fin_ia_dell_source_report_quality_evaluation_protocol_v1_0"
)
EXECUTION_AUTHORITY_TEMPLATE_SCHEMA_VERSION = (
    "fin_ia_dell_source_report_quality_execution_authority_template_v1_0"
)
CROSSWALK_PROGRAM_SCHEMA_VERSION = "fin_ia_dell_report_gap_crosswalk_program_v1_0"
CROSSWALK_CONTENT_SCHEMA_VERSION = "fin_ia_report_gap_crosswalk_content_v1_1"
AUDIT_PROJECTION_SCHEMA_VERSION = "fin_ia_report_gap_crosswalk_audit_projection_v1_1"
MODEL_PROJECTION_SCHEMA_VERSION = "fin_ia_report_gap_crosswalk_model_projection_v1_1"
READER_PROJECTION_SCHEMA_VERSION = "fin_ia_report_gap_crosswalk_reader_projection_v1_1"

FROZEN_BASELINE_MANIFEST_DIGEST = (
    "3faebbd9a53639c5e1dba4479d212bb8f0fccb255eb1391fbf59fdc55690dd14"
)
FROZEN_EVALUATION_PROTOCOL_DIGEST = (
    "5e377dc03044112b3b3187b8936f218d533a1c0d33e634f3416222ae6afba1a1"
)
FROZEN_EXECUTION_AUTHORITY_TEMPLATE_DIGEST = (
    "08307e0f12c3d0c0dba8c750bb75c2c42d02e0453b9062975313967a0c4ffbf4"
)
FROZEN_CROSSWALK_PROGRAM_DIGEST = (
    "95f9826cf25eaf86c1f77969ce4e45577c0b7756ac86385debe9237a745130ae"
)
FROZEN_BASELINE_VERIFICATION_DIGEST = (
    "f3a3c4a68cf5c33a0d358f520ef881d3602eec4fd6d76f5651965090f475d7fc"
)

RESEARCH_DISPOSITIONS = frozenset(
    {
        "candidate_admission_pending",
        "source_route_pending",
        "narrowed",
        "closed",
        "proved_information_boundary",
        "S2_numeric_or_bridge_gap",
        "S3_method_parameter",
    }
)
TECHNICAL_CHAIN_STATES = frozenset(
    {"technical_chain_closed", "technical_chain_not_evaluated"}
)
UNIT_SELECTION_STATES = frozenset(
    {"selected_by_unit", "not_selected_by_unit"}
)
SOURCE_OR_METHOD_TYPES = frozenset(
    {"source_evidence_boundary", "research_method_parameter", "numeric_or_bridge_boundary"}
)

EXPECTED_BASELINE_COUNTS = {
    "pack_evidence_items": 55,
    "pack_residual_gaps": 14,
    "pack_closed_gaps": 0,
    "pack_narrowed_gaps": 3,
    "dynamic_unit_gap_refs": 9,
    "writer_gap_groups": 4,
    "writer_gap_refs": 10,
    "S2_bridge_gaps": 4,
    "product_readiness_requests": 8,
    "product_readiness_blocked_by_evidence_admission": 4,
    "candidate_review_items": 18,
    "candidate_human_review_required_items": 16,
}
EXPECTED_CROSSWALK_COUNTS = {
    "pack_gaps": 14,
    "dynamic_unit_gaps": 9,
    "writer_groups": 4,
    "writer_gap_refs": 10,
    "S2_bridge_gaps": 4,
    "pack_gaps_not_selected_by_unit": 5,
    "pack_gaps_not_referenced_by_writer": 4,
}
EXPECTED_NARROWED_GAP_IDS = frozenset(
    {
        "dell-gap-pricing-asp",
        "dell-gap-pricing-units",
        "dell-gap-supplier-capacity-readthrough",
    }
)

REQUIRED_BASELINE_BINDINGS = frozenset(
    {
        "R17_private_full_result",
        "R17_public_candidate",
        "R4_current_pack",
        "R38_private_full_result",
        "product_readiness_public",
        "product_readiness_private",
        "S2_product_bridge_public",
        "S2_product_bridge_private",
        "report_quality_rubric",
        "execution_program",
    }
)
REQUIRED_BASELINE_VERIFICATION_BINDINGS = frozenset(
    {
        "predecessor_baseline_manifest",
        "R4_successor_result",
        "R4_evidence_gate_result",
        "R1_failed_public_result",
    }
)
REQUIRED_PACKET_COMPONENTS = frozenset(
    {
        "immutable_candidate_seal",
        "L1_financial_truth_result",
        "L2_evidence_authority_result",
        "claim_source_matrix",
        "report_gap_crosswalk_14_9_4",
        "numeric_bridge",
        "strongest_counter_thesis",
        "what_would_change_register",
        "reader_citation_appendix",
        "final_render",
        "baseline_comparison",
    }
)
REQUIRED_AUTHORITY_NODES = frozenset(
    {
        "external_source_retrieval",
        "embedding_0_6b_baseline",
        "embedding_4b_challenger",
        "reranker_baseline",
        "reranker_challenger",
        "dynamic_research_agent",
        "writer",
        "shadow_model_evaluator",
    }
)
TOKEN_BUDGET_BASIS_FIELDS = frozenset(
    {
        "node_purpose",
        "input_scale",
        "required_outputs",
        "schema_burden",
        "materiality_and_quality_risk",
        "comparable_run_evidence",
        "reasoning_profile",
        "stop_and_truncation_behavior",
    }
)

_HEX_64 = re.compile(r"\b[0-9a-fA-F]{64}\b")
_HEX_40_FULL = re.compile(r"^[0-9a-f]{40}$")


class ReportGapCrosswalkError(ValueError):
    """Raised when a report-gap baseline or crosswalk cannot be trusted."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ReportGapCrosswalkError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _sequence(value: object, code: str) -> Sequence[Any]:
    _require(
        isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)),
        code,
    )
    return value


def _text(value: object, code: str) -> str:
    result = str(value or "").strip()
    _require(bool(result), code)
    return result


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _self_digest(value: Mapping[str, Any], field: str, code: str) -> None:
    supplied = _text(value.get(field), code)
    unsigned = {key: item for key, item in value.items() if key != field}
    _require(supplied == canonical_digest(unsigned), code)


def _path_value(value: object, path: Sequence[object], code: str) -> object:
    current = value
    for step in path:
        if isinstance(step, int):
            items = _sequence(current, code)
            _require(0 <= step < len(items), code)
            current = items[step]
        else:
            mapping = _mapping(current, code)
            key = str(step)
            _require(key in mapping, code)
            current = mapping[key]
    return current


def _unique_by(
    rows: Sequence[Any], field: str, *, code: str
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for raw in rows:
        row = _mapping(raw, code)
        key = _text(row.get(field), code)
        _require(key not in result, code)
        result[key] = row
    return result


def _validate_bound_input(
    binding_key: str,
    raw_binding: object,
    *,
    source_bytes_by_ref: Mapping[str, bytes],
    git_blob_by_source_ref: Mapping[str, str],
    git_blob_by_commit_ref: Mapping[str, str],
) -> Mapping[str, Any] | None:
    binding = _mapping(raw_binding, "baseline_input_binding_invalid")
    content_type = binding.get("content_type")
    common_fields = {
        "ref",
        "sha256",
        "git_tracking",
        "git_blob",
        "git_commit",
        "content_type",
    }
    json_fields = common_fields | {
        "schema_version",
        "status",
        "identity_checks",
        "canonical_digest_field",
        "canonical_digest",
    }
    _require(
        set(binding) == (json_fields if content_type == "application/json" else common_fields),
        f"baseline_input_binding_fields_invalid:{binding_key}",
    )
    ref = _text(binding.get("ref"), "baseline_input_ref_invalid")
    _require(ref in source_bytes_by_ref, f"baseline_input_missing:{binding_key}")
    payload = source_bytes_by_ref[ref]
    _require(
        _sha256_bytes(payload) == binding.get("sha256"),
        f"baseline_input_sha256_mismatch:{binding_key}",
    )
    tracking = binding.get("git_tracking")
    _require(
        tracking in {"tracked", "private_workbench_ignored"},
        f"baseline_input_tracking_invalid:{binding_key}",
    )
    if tracking == "tracked":
        git_blob = str(binding.get("git_blob") or "")
        git_commit = str(binding.get("git_commit") or "")
        _require(
            bool(_HEX_40_FULL.fullmatch(git_blob))
            and bool(_HEX_40_FULL.fullmatch(git_commit)),
            f"baseline_input_git_identity_invalid:{binding_key}",
        )
        _require(
            ref in git_blob_by_source_ref
            and git_blob_by_source_ref[ref] == git_blob,
            f"baseline_input_git_blob_bytes_mismatch:{binding_key}",
        )
        commit_ref = f"{git_commit}:{ref}"
        _require(
            commit_ref in git_blob_by_commit_ref,
            f"baseline_input_git_commit_path_missing:{binding_key}",
        )
        _require(
            git_blob_by_commit_ref[commit_ref] == git_blob,
            f"baseline_input_git_commit_path_mismatch:{binding_key}",
        )
    else:
        _require(
            binding.get("git_blob") is None and binding.get("git_commit") is None,
            f"baseline_private_git_identity_invalid:{binding_key}",
        )
    _require(
        content_type in {"application/json", "text/markdown"},
        f"baseline_input_content_type_invalid:{binding_key}",
    )
    if content_type == "text/markdown":
        try:
            markdown = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ReportGapCrosswalkError(
                f"baseline_markdown_utf8_invalid:{binding_key}"
            ) from exc
        _require(bool(markdown.strip()), f"baseline_markdown_empty:{binding_key}")
        return None
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReportGapCrosswalkError(f"baseline_json_invalid:{binding_key}") from exc
    document = _mapping(value, f"baseline_json_object_required:{binding_key}")
    _require(
        document.get("schema_version") == binding.get("schema_version")
        and document.get("status") == binding.get("status"),
        f"baseline_json_identity_invalid:{binding_key}",
    )
    identity_checks = _sequence(
        binding.get("identity_checks"),
        f"baseline_identity_checks_invalid:{binding_key}",
    )
    for raw_check in identity_checks:
        check = _mapping(raw_check, f"baseline_identity_check_invalid:{binding_key}")
        _require(
            set(check) == {"path", "expected"},
            f"baseline_identity_check_fields_invalid:{binding_key}",
        )
        path = _sequence(
            check.get("path"), f"baseline_identity_path_invalid:{binding_key}"
        )
        _require(
            _path_value(document, path, f"baseline_identity_path_missing:{binding_key}")
            == check.get("expected"),
            f"baseline_identity_value_invalid:{binding_key}",
        )
    digest_field = _text(
        binding.get("canonical_digest_field"),
        f"baseline_canonical_digest_field_invalid:{binding_key}",
    )
    supplied = document.get(digest_field)
    _require(
        supplied == binding.get("canonical_digest"),
        f"baseline_canonical_digest_binding_invalid:{binding_key}",
    )
    _require(
        supplied
        == canonical_digest(
            {key: item for key, item in document.items() if key != digest_field}
        ),
        f"baseline_canonical_digest_recompute_invalid:{binding_key}",
    )
    return document


def _recompute_baseline_counts(parsed: Mapping[str, Mapping[str, Any]]) -> dict[str, int]:
    pack = parsed["R4_current_pack"]
    r4_result = parsed["R4_successor_result"]
    evidence_gate = parsed["R4_evidence_gate_result"]
    dynamic = parsed["R38_private_full_result"]
    writer = parsed["R17_private_full_result"]
    readiness_public = parsed["product_readiness_public"]
    readiness_private = parsed["product_readiness_private"]
    bridge_private = parsed["S2_product_bridge_private"]

    evidence_items = _unique_by(
        _sequence(pack.get("evidence_items"), "baseline_pack_evidence_items_invalid"),
        "target_id",
        code="baseline_pack_evidence_item_duplicate_or_invalid",
    )
    pack_gaps = _unique_by(
        _sequence(pack.get("residual_gaps"), "baseline_pack_gaps_invalid"),
        "gap_id",
        code="baseline_pack_gap_duplicate_or_invalid",
    )
    observed = _mapping(pack.get("observed_counts"), "baseline_pack_observed_counts_invalid")
    _require(
        observed.get("accepted_evidence_items") == len(evidence_items)
        and observed.get("residual_gaps") == len(pack_gaps),
        "baseline_pack_observed_counts_mismatch",
    )

    coverage = _mapping(r4_result.get("coverage_delta"), "baseline_R4_coverage_invalid")
    narrowed = set(
        _sequence(
            evidence_gate.get("gap_ids_narrowed"),
            "baseline_R4_narrowed_gap_ids_invalid",
        )
    )
    satisfied = set(
        _sequence(
            evidence_gate.get("gap_ids_satisfied"),
            "baseline_R4_satisfied_gap_ids_invalid",
        )
    )
    _require(
        len(narrowed)
        == len(evidence_gate.get("gap_ids_narrowed") or [])
        and len(satisfied) == len(evidence_gate.get("gap_ids_satisfied") or [])
        and narrowed.issubset(pack_gaps)
        and satisfied.issubset(pack_gaps),
        "baseline_R4_gap_disposition_set_invalid",
    )
    _require(
        coverage.get("successor_evidence_count") == len(evidence_items)
        and coverage.get("residual_gap_count_after") == len(pack_gaps)
        and coverage.get("gap_narrowed_count") == len(narrowed)
        and coverage.get("gap_closed_count") == len(satisfied),
        "baseline_R4_coverage_recompute_mismatch",
    )
    _require(
        r4_result.get("successor_pack_payload_digest") == pack.get("pack_payload_digest")
        and r4_result.get("evidence_result_digest") == evidence_gate.get("result_digest")
        and _path_value(
            pack,
            ["successor_lineage", "evidence_result_digest"],
            "baseline_R4_pack_lineage_missing",
        )
        == evidence_gate.get("result_digest"),
        "baseline_R4_lineage_mismatch",
    )

    dynamic_cards = _unique_by(
        _sequence(
            _path_value(
                dynamic,
                ["workpaper_context", "cell_analysis_view", "cell", "residual_gap_cards"],
                "baseline_dynamic_gap_cards_missing",
            ),
            "baseline_dynamic_gap_cards_invalid",
        ),
        "gap_ref",
        code="baseline_dynamic_gap_ref_duplicate_or_invalid",
    )
    writer_groups = _sequence(
        _path_value(
            writer,
            ["candidate_draft", "remaining_gaps"],
            "baseline_writer_gap_groups_missing",
        ),
        "baseline_writer_gap_groups_invalid",
    )
    writer_refs: list[str] = []
    for raw_group in writer_groups:
        group = _mapping(raw_group, "baseline_writer_gap_group_invalid")
        refs = [
            str(item)
            for item in _sequence(
                group.get("gap_refs"), "baseline_writer_gap_refs_invalid"
            )
        ]
        _require(len(refs) == len(set(refs)), "baseline_writer_gap_ref_duplicate")
        writer_refs.extend(refs)
    _require(
        len(writer_refs) == len(set(writer_refs)),
        "baseline_writer_gap_ref_reused_across_groups",
    )

    public_requests = _unique_by(
        _sequence(readiness_public.get("requests"), "baseline_public_requests_invalid"),
        "request_id",
        code="baseline_public_request_duplicate_or_invalid",
    )
    private_readiness = _mapping(
        readiness_private.get("pack_readiness"), "baseline_private_readiness_invalid"
    )
    private_requests = _unique_by(
        _sequence(private_readiness.get("requests"), "baseline_private_requests_invalid"),
        "request_id",
        code="baseline_private_request_duplicate_or_invalid",
    )
    _require(
        set(public_requests) == set(private_requests)
        and all(
            public_requests[key].get("readiness_state")
            == private_requests[key].get("readiness_state")
            for key in public_requests
        ),
        "baseline_public_private_readiness_mismatch",
    )
    public_packet = _mapping(
        readiness_public.get("candidate_review_packet_summary"),
        "baseline_public_review_packet_invalid",
    )
    private_packet = _mapping(
        readiness_private.get("candidate_review_packet"),
        "baseline_private_review_packet_invalid",
    )
    _require(
        public_packet.get("review_item_count") == private_packet.get("review_item_count")
        and public_packet.get("human_review_required_count")
        == private_packet.get("human_review_required_count"),
        "baseline_public_private_review_packet_mismatch",
    )

    bridge_receipts = _unique_by(
        _sequence(
            _path_value(
                bridge_private,
                ["product_value_bridge", "bridge_gap_receipts"],
                "baseline_S2_bridge_receipts_missing",
            ),
            "baseline_S2_bridge_receipts_invalid",
        ),
        "gap_id",
        code="baseline_S2_bridge_gap_duplicate_or_invalid",
    )
    return {
        "pack_evidence_items": len(evidence_items),
        "pack_residual_gaps": len(pack_gaps),
        "pack_closed_gaps": len(satisfied),
        "pack_narrowed_gaps": len(narrowed),
        "dynamic_unit_gap_refs": len(dynamic_cards),
        "writer_gap_groups": len(writer_groups),
        "writer_gap_refs": len(writer_refs),
        "S2_bridge_gaps": len(bridge_receipts),
        "product_readiness_requests": len(public_requests),
        "product_readiness_blocked_by_evidence_admission": sum(
            row.get("readiness_state") == "blocked_by_evidence_admission"
            for row in public_requests.values()
        ),
        "candidate_review_items": int(public_packet.get("review_item_count", -1)),
        "candidate_human_review_required_items": int(
            public_packet.get("human_review_required_count", -1)
        ),
    }


def validate_program_baseline_manifest(
    manifest: Mapping[str, Any],
    *,
    verification: Mapping[str, Any],
    source_bytes_by_ref: Mapping[str, bytes],
    git_blob_by_source_ref: Mapping[str, str],
    git_blob_by_commit_ref: Mapping[str, str],
) -> dict[str, Any]:
    """Validate the immutable predecessor manifest and return parsed JSON inputs."""

    _self_digest(manifest, "manifest_digest", "baseline_manifest_digest_invalid")
    _require(
        manifest.get("schema_version") == BASELINE_SCHEMA_VERSION
        and manifest.get("status") == "baseline_frozen_calls_not_authorized"
        and manifest.get("case_key") == "DELL"
        and manifest.get("research_as_of") == "2026-08-06",
        "baseline_manifest_identity_invalid",
    )
    bindings = _mapping(
        manifest.get("input_bindings"), "baseline_input_bindings_invalid"
    )
    _require(
        set(bindings) == REQUIRED_BASELINE_BINDINGS,
        "baseline_input_binding_set_invalid",
    )
    parsed: dict[str, Mapping[str, Any]] = {}
    for binding_key, raw_binding in bindings.items():
        document = _validate_bound_input(
            binding_key,
            raw_binding,
            source_bytes_by_ref=source_bytes_by_ref,
            git_blob_by_source_ref=git_blob_by_source_ref,
            git_blob_by_commit_ref=git_blob_by_commit_ref,
        )
        if document is not None:
            parsed[binding_key] = document

    _self_digest(
        verification,
        "verification_digest",
        "baseline_verification_digest_invalid",
    )
    _require(
        verification.get("schema_version") == BASELINE_VERIFICATION_SCHEMA_VERSION
        and verification.get("status")
        == "R1_failed_audit_correction_inputs_frozen_calls_not_authorized"
        and verification.get("case_key") == "DELL"
        and verification.get("research_as_of") == "2026-08-06",
        "baseline_verification_identity_invalid",
    )
    verification_bindings = _mapping(
        verification.get("input_bindings"), "baseline_verification_bindings_invalid"
    )
    _require(
        set(verification_bindings) == REQUIRED_BASELINE_VERIFICATION_BINDINGS,
        "baseline_verification_binding_set_invalid",
    )
    verification_parsed: dict[str, Mapping[str, Any]] = {}
    for binding_key, raw_binding in verification_bindings.items():
        document = _validate_bound_input(
            binding_key,
            raw_binding,
            source_bytes_by_ref=source_bytes_by_ref,
            git_blob_by_source_ref=git_blob_by_source_ref,
            git_blob_by_commit_ref=git_blob_by_commit_ref,
        )
        _require(document is not None, f"baseline_verification_json_required:{binding_key}")
        verification_parsed[binding_key] = document
    _require(
        verification_parsed["predecessor_baseline_manifest"] == manifest,
        "baseline_verification_predecessor_manifest_mismatch",
    )
    parsed.update(
        {
            key: value
            for key, value in verification_parsed.items()
            if key != "predecessor_baseline_manifest"
        }
    )

    frozen_counts = _mapping(
        manifest.get("frozen_counts"), "baseline_frozen_counts_invalid"
    )
    actual_counts = _recompute_baseline_counts(parsed)
    _require(actual_counts == frozen_counts, "baseline_frozen_counts_actual_mismatch")
    _require(frozen_counts == EXPECTED_BASELINE_COUNTS, "baseline_frozen_counts_mismatch")
    _require(
        verification.get("expected_counts") == actual_counts,
        "baseline_verification_expected_counts_mismatch",
    )
    evidence_gate = parsed["R4_evidence_gate_result"]
    _require(
        set(verification.get("expected_narrowed_gap_ids") or [])
        == set(evidence_gate.get("gap_ids_narrowed") or [])
        == EXPECTED_NARROWED_GAP_IDS
        and verification.get("expected_satisfied_gap_ids") == []
        and evidence_gate.get("gap_ids_satisfied") == [],
        "baseline_verification_gap_disposition_mismatch",
    )
    model_authorities = _mapping(
        manifest.get("future_model_node_authorities"),
        "baseline_model_authorities_invalid",
    )
    _require(
        set(model_authorities) == REQUIRED_AUTHORITY_NODES,
        "baseline_model_authority_node_set_invalid",
    )
    _require(
        all(value == "not_authorized" for value in model_authorities.values()),
        "baseline_model_authority_granted",
    )
    report_baseline = _mapping(
        manifest.get("frozen_R17_report_quality_baseline"),
        "baseline_report_quality_invalid",
    )
    _require(
        report_baseline.get("severity_counts")
        == {"P0": 0, "P1": 1, "P2": 2, "P3": 1}
        and report_baseline.get("engineering_and_evidence_pipeline_verdict")
        == "PASS_BOUNDED"
        and report_baseline.get("report_research_quality_verdict")
        == "OPEN_NOT_ASSESSABLE"
        and report_baseline.get("formal_eight_dimension_score") is None
        and report_baseline.get("author_diagnostic_score_reusable") is False
        and report_baseline.get("qualified_human_product_verdict")
        == "FALSE_NOT_GRANTED",
        "baseline_report_quality_state_invalid",
    )
    r1_failure = _mapping(
        verification.get("R1_independent_audit_failure"),
        "baseline_verification_R1_failure_invalid",
    )
    _require(
        r1_failure
        == {
            "review_target_commit": "4cce5d51d6a138391b9627698bec9de171ec4470",
            "review_target_tree": "f9104073f1d023fefa463974999e228a8f14dfd7",
            "finding_counts": {"P0": 1, "P1": 2, "P2": 1, "P3": 0},
            "finding_codes": [
                "baseline_trust_seal_not_fail_closed",
                "projection_digest_not_deterministic_projection_proof",
                "quality_protocol_not_fully_frozen",
                "technical_and_unit_state_axes_conflated",
            ],
            "engineering_and_evidence_pipeline_verdict": "FAIL",
            "crosswalk_research_quality_verdict": "FAIL",
            "report_research_quality_verdict": "OPEN_NOT_ASSESSABLE",
            "qualified_human_product_verdict": "FALSE_NOT_GRANTED",
            "G1_pass": False,
        },
        "baseline_verification_R1_failure_contract_mismatch",
    )
    r1_result = parsed["R1_failed_public_result"]
    _require(
        r1_result.get("result_digest")
        == "09686edf180371f8676abb85b8cda90991bcab144d2e62a06923a3229a2b520c"
        and _path_value(
            r1_result,
            ["acceptance", "G1_pass"],
            "baseline_verification_R1_acceptance_missing",
        )
        is False,
        "baseline_verification_R1_result_mismatch",
    )
    _require(
        manifest.get("manifest_digest") == FROZEN_BASELINE_MANIFEST_DIGEST,
        "baseline_manifest_not_frozen",
    )
    _require(
        verification.get("verification_digest")
        == FROZEN_BASELINE_VERIFICATION_DIGEST,
        "baseline_verification_not_frozen",
    )
    return dict(parsed)


def validate_evaluation_protocol(
    protocol: Mapping[str, Any], baseline_manifest: Mapping[str, Any]
) -> None:
    _self_digest(protocol, "protocol_digest", "evaluation_protocol_digest_invalid")
    _require(
        set(protocol)
        == {
            "schema_version",
            "status",
            "evaluation_cycle_id",
            "case_key",
            "research_as_of",
            "baseline_manifest_binding",
            "immutable_target_contract",
            "formal_scoring_prerequisites",
            "eight_dimension_thresholds",
            "finding_severity_contract",
            "separate_verdicts",
            "reason_ref_schema",
            "report_quality_required_surfaces",
            "scoring_authority",
            "frozen_R17_baseline",
            "known_boundary",
            "protocol_digest",
        },
        "evaluation_protocol_fields_invalid",
    )
    _require(
        protocol.get("schema_version") == EVALUATION_PROTOCOL_SCHEMA_VERSION
        and protocol.get("status") == "preregistered_before_successor_candidate"
        and protocol.get("evaluation_cycle_id")
        == "FIN_0_1_3_DELL_SOURCE_REPORT_QUALITY_CYCLE_1"
        and protocol.get("case_key") == "DELL"
        and protocol.get("research_as_of") == "2026-08-06",
        "evaluation_protocol_identity_invalid",
    )
    baseline_binding = _mapping(
        protocol.get("baseline_manifest_binding"),
        "evaluation_protocol_baseline_binding_invalid",
    )
    _require(
        baseline_binding
        == {
            "ref": (
                "configs/research/evals/"
                "fin_ia_0_1_3_dell_source_report_quality_program_baseline_manifest_v1_0.json"
            ),
            "sha256": "4bf0fa0e07d27fd3edcbaaea4a8b3002cfe4c0e227b8214c217666350ad4edc0",
            "manifest_digest": FROZEN_BASELINE_MANIFEST_DIGEST,
        }
        and baseline_binding.get("manifest_digest")
        == baseline_manifest.get("manifest_digest"),
        "evaluation_protocol_baseline_digest_mismatch",
    )
    _require(
        protocol.get("immutable_target_contract")
        == {
            "candidate_status_at_preregistration": "not_created",
            "candidate_must_receive_new_run_id": True,
            "candidate_private_public_and_rendered_sha_required": True,
            "candidate_document_model_digest_required": True,
            "implementation_commit_and_tree_required": True,
            "reviewer_packet_digest_required": True,
            "target_mutation_during_review_invalidates_review": True,
            "rubric_change_after_candidate_requires_new_cycle": True,
            "R17_must_remain_immutable": True,
        },
        "evaluation_protocol_immutable_target_contract_invalid",
    )
    prerequisites = _mapping(
        protocol.get("formal_scoring_prerequisites"),
        "evaluation_protocol_prerequisites_invalid",
    )
    _require(
        prerequisites
        == {
            "L1_financial_truth_must_pass": True,
            "L2_evidence_authority_must_pass": True,
            "missing_component_disposition": "not_assessable",
            "required_packet_components": [
                "immutable_candidate_seal",
                "L1_financial_truth_result",
                "L2_evidence_authority_result",
                "claim_source_matrix",
                "report_gap_crosswalk_14_9_4",
                "numeric_bridge",
                "strongest_counter_thesis",
                "what_would_change_register",
                "reader_citation_appendix",
                "final_render",
                "baseline_comparison",
            ],
        }
        and set(prerequisites["required_packet_components"])
        == REQUIRED_PACKET_COMPONENTS,
        "evaluation_protocol_prerequisite_contract_invalid",
    )
    thresholds = _mapping(
        protocol.get("eight_dimension_thresholds"),
        "evaluation_protocol_thresholds_invalid",
    )
    _require(
        thresholds
        == {
            "dimensions": [
                "Q1_company_and_question_specificity",
                "Q2_evidence_to_conclusion_reasoning",
                "Q3_financial_and_numeric_interpretation",
                "Q4_causal_mechanism_and_industry_logic",
                "Q5_cross_cell_synthesis_and_conflict_adjudication",
                "Q6_counter_thesis_risk_and_gap_discipline",
                "Q7_what_would_change_actionability",
                "Q8_writing_and_senior_decision_utility",
            ],
            "score_minimum_each": 0,
            "score_maximum_each": 4,
            "total_minimum": 24,
            "maximum_total": 32,
            "Q1_through_Q7_minimum_each": 2,
            "Q1_Q2_Q3_Q8_minimum_each": 3,
            "dimensions_at_or_above_3_minimum": 4,
            "DELL_MU_NVDA_must_pass_individually": True,
        },
        "evaluation_protocol_threshold_contract_invalid",
    )
    severities = _mapping(
        protocol.get("finding_severity_contract"),
        "evaluation_protocol_severity_invalid",
    )
    _require(
        severities
        == {
            "P0": {
                "meaning": (
                    "Identity, integrity, material financial truth or evidence-authority "
                    "failure that invalidates the target."
                ),
                "blocks": ["evaluation", "product", "publication", "release"],
            },
            "P1": {
                "meaning": "Material research, citation, thesis or decision-utility failure.",
                "blocks": ["report_quality", "product", "publication", "release"],
            },
            "P2": {
                "meaning": (
                    "Substantive completeness or actionability weakness requiring repair "
                    "before product acceptance."
                ),
                "blocks": ["report_quality", "product"],
            },
            "P3": {
                "meaning": (
                    "Non-material usability or editorial weakness retained for explicit "
                    "disposition."
                ),
                "blocks": [],
            },
        },
        "evaluation_protocol_severity_set_invalid",
    )
    verdicts = _mapping(
        protocol.get("separate_verdicts"),
        "evaluation_protocol_verdicts_invalid",
    )
    _require(
        verdicts
        == {
            "engineering_and_evidence_pipeline_verdict": {
                "allowed": ["PASS", "PASS_BOUNDED", "FAIL", "OPEN_NOT_ASSESSABLE"],
                "cannot_grant": [
                    "report_quality",
                    "qualified_human",
                    "product",
                    "publication",
                    "release",
                ],
            },
            "report_research_quality_verdict": {
                "allowed": ["PASS", "FAIL", "OPEN_NOT_ASSESSABLE"],
                "cannot_grant": ["qualified_human", "product", "publication", "release"],
            },
            "qualified_human_product_verdict": {
                "allowed": ["ACCEPT", "RETURN", "FALSE_NOT_GRANTED"],
                "reviewer_must_be_qualified_human": True,
            },
        },
        "evaluation_protocol_verdict_set_invalid",
    )
    _require(
        protocol.get("reason_ref_schema")
        == {
            "required_per_finding": [
                "finding_id",
                "severity",
                "finding_code",
                "reason",
                "impact",
                "earliest_responsible_stage",
                "reason_refs",
            ],
            "allowed_reason_ref_types": [
                "claim_id",
                "evidence_id",
                "numeric_fact_id",
                "numeric_relation_id",
                "typed_gap_id",
                "writer_group_id",
                "what_would_change_id",
                "citation_id",
                "section_path",
                "render_location",
                "source_binding_digest",
            ],
            "dimension_score_requires_reason_refs": True,
            "summary_only_reason_invalid": True,
        },
        "evaluation_protocol_reason_ref_schema_invalid",
    )
    _require(
        protocol.get("report_quality_required_surfaces")
        == {
            "claim_source_matrix": True,
            "report_gap_crosswalk_14_9_4": True,
            "units_share_ASP_mix_PVM_profit_working_capital_bridge": True,
            "strongest_counter_thesis": True,
            "adjudicated_cross_cell_dependency_or_conflict": True,
            "operational_what_would_change": True,
            "reader_citation_appendix": True,
            "bilingual_semantic_equivalence": True,
            "final_render": True,
            "single_primary_boundary_register": True,
        },
        "evaluation_protocol_report_surfaces_invalid",
    )
    authority = _mapping(
        protocol.get("scoring_authority"),
        "evaluation_protocol_scoring_authority_invalid",
    )
    _require(
        authority
        == {
            "model_self_score_formal": False,
            "LLM_as_judge_formal": False,
            "author_can_formally_score_own_candidate": False,
            "author_separated_content_reviewer_required": True,
            "qualified_human_required_for_product_acceptance": True,
            "shadow_model_score_must_be_physically_separate": True,
            "reviewer_identity_and_time_required": True,
        },
        "evaluation_protocol_scoring_authority_granted",
    )
    _require(
        protocol.get("frozen_R17_baseline")
        == baseline_manifest.get("frozen_R17_report_quality_baseline"),
        "evaluation_protocol_R17_baseline_mismatch",
    )
    _require(
        protocol.get("known_boundary")
        == (
            "This protocol freezes how a future immutable successor is evaluated. It is "
            "not a reviewer verdict, a model authority, a qualified-human decision or "
            "permission to create the candidate."
        ),
        "evaluation_protocol_known_boundary_invalid",
    )
    _require(
        protocol.get("protocol_digest") == FROZEN_EVALUATION_PROTOCOL_DIGEST,
        "evaluation_protocol_not_frozen",
    )


def validate_execution_authority_template(
    template: Mapping[str, Any], baseline_manifest: Mapping[str, Any]
) -> None:
    _self_digest(
        template,
        "template_digest",
        "execution_authority_template_digest_invalid",
    )
    _require(
        template.get("schema_version") == EXECUTION_AUTHORITY_TEMPLATE_SCHEMA_VERSION
        and template.get("status") == "template_only_all_calls_not_authorized"
        and template.get("case_key") == "DELL",
        "execution_authority_template_identity_invalid",
    )
    binding = _mapping(
        template.get("baseline_manifest_binding"),
        "execution_authority_baseline_binding_invalid",
    )
    _require(
        binding.get("manifest_digest") == baseline_manifest.get("manifest_digest"),
        "execution_authority_baseline_digest_mismatch",
    )
    nodes = _mapping(template.get("node_templates"), "execution_authority_nodes_invalid")
    _require(set(nodes) == REQUIRED_AUTHORITY_NODES, "execution_authority_node_set_invalid")
    for node_id, raw_node in nodes.items():
        node = _mapping(raw_node, f"execution_authority_node_invalid:{node_id}")
        _require(
            node.get("authority_status") == "not_authorized"
            and node.get("attempt_id") is None
            and node.get("model_calls_authorized") is False
            and node.get("provider_calls_authorized") is False
            and node.get("network_calls_authorized") is False,
            f"execution_authority_node_granted:{node_id}",
        )
        basis = _mapping(
            node.get("TokenBudgetBasis"),
            f"execution_authority_token_basis_invalid:{node_id}",
        )
        _require(
            set(basis) == TOKEN_BUDGET_BASIS_FIELDS
            and all(value is None for value in basis.values()),
            f"execution_authority_token_basis_not_template:{node_id}",
        )
        execution = _mapping(
            node.get("execution_contract"),
            f"execution_authority_contract_invalid:{node_id}",
        )
        _require(
            set(execution)
            == {
                "input_digests",
                "maximum_logical_nodes",
                "maximum_provider_routes",
                "maximum_network_routes",
                "retry_policy",
                "fallback_policy",
                "capture_first",
                "exclusive_create",
                "failure_disposition",
            },
            f"execution_authority_contract_fields_invalid:{node_id}",
        )
    split = _mapping(template.get("evaluation_split_contract"), "split_contract_invalid")
    _require(
        split.get("valid_test_holdout_isolation_required") is True
        and split.get("expected_label_visible_to_implementer") is False
        and split.get("label_exposure_invalidates_blind_claim") is True,
        "split_contract_authority_invalid",
    )
    _require(
        template.get("template_digest")
        == FROZEN_EXECUTION_AUTHORITY_TEMPLATE_DIGEST,
        "execution_authority_template_not_frozen",
    )


def validate_crosswalk_program(
    program: Mapping[str, Any],
    *,
    baseline_manifest: Mapping[str, Any],
    evaluation_protocol: Mapping[str, Any],
    authority_template: Mapping[str, Any],
) -> None:
    _self_digest(program, "program_digest", "crosswalk_program_digest_invalid")
    _require(
        program.get("schema_version") == CROSSWALK_PROGRAM_SCHEMA_VERSION
        and program.get("status") == "approved_zero_call_crosswalk_materialization"
        and program.get("case_key") == "DELL"
        and program.get("research_as_of") == "2026-08-06",
        "crosswalk_program_identity_invalid",
    )
    bindings = _mapping(program.get("governance_bindings"), "crosswalk_governance_invalid")
    _require(
        bindings.get("baseline_manifest_digest") == baseline_manifest.get("manifest_digest")
        and bindings.get("evaluation_protocol_digest")
        == evaluation_protocol.get("protocol_digest")
        and bindings.get("execution_authority_template_digest")
        == authority_template.get("template_digest"),
        "crosswalk_governance_digest_mismatch",
    )
    _require(
        program.get("expected_counts") == EXPECTED_CROSSWALK_COUNTS,
        "crosswalk_expected_counts_invalid",
    )
    gap_policies = _unique_by(
        _sequence(program.get("gap_policies"), "crosswalk_gap_policies_invalid"),
        "gap_id",
        code="crosswalk_gap_policy_duplicate_or_invalid",
    )
    _require(len(gap_policies) == 14, "crosswalk_gap_policy_count_invalid")
    for gap_id, policy in gap_policies.items():
        _require(
            policy.get("research_disposition") in RESEARCH_DISPOSITIONS
            and policy.get("source_or_method_type") in SOURCE_OR_METHOD_TYPES,
            f"crosswalk_gap_policy_enum_invalid:{gap_id}",
        )
        for field in (
            "stage_owner",
            "reader_label_zh",
            "reader_label_en",
            "why_it_matters_en",
            "what_evidence_would_change_en",
            "report_placement",
            "company_vs_industry_boundary",
            "numeric_authority_boundary",
            "next_legal_action",
            "stop_boundary",
        ):
            _text(policy.get(field), f"crosswalk_gap_policy_field_missing:{gap_id}:{field}")
        _require(
            policy.get("research_disposition") != "closed"
            and policy.get("closure_receipt") is None,
            f"crosswalk_gap_policy_false_closure:{gap_id}",
        )
    _require(
        sum(
            policy.get("research_disposition") == "narrowed"
            for policy in gap_policies.values()
        )
        == baseline_manifest["frozen_counts"]["pack_narrowed_gaps"],
        "crosswalk_narrowed_count_invalid",
    )
    _require(
        set(program.get("expected_narrowed_gap_ids") or [])
        == {
            gap_id
            for gap_id, policy in gap_policies.items()
            if policy.get("research_disposition") == "narrowed"
        },
        "crosswalk_narrowed_gap_set_invalid",
    )
    _require(
        len(set(program.get("expected_pack_gaps_not_selected_by_unit") or [])) == 5
        and set(program.get("expected_pack_gaps_not_selected_by_unit") or []).issubset(
            gap_policies
        )
        and len(set(program.get("expected_pack_gaps_not_referenced_by_writer") or []))
        == 4
        and set(
            program.get("expected_pack_gaps_not_referenced_by_writer") or []
        ).issubset(gap_policies),
        "crosswalk_expected_gap_subsets_invalid",
    )
    writer_policies = _unique_by(
        _sequence(
            program.get("writer_group_policies"),
            "crosswalk_writer_group_policies_invalid",
        ),
        "writer_group_id",
        code="crosswalk_writer_group_policy_duplicate_or_invalid",
    )
    _require(len(writer_policies) == 4, "crosswalk_writer_group_policy_count_invalid")
    for group_id, policy in writer_policies.items():
        expected = _sequence(
            policy.get("expected_pack_gap_ids"),
            f"crosswalk_writer_group_expected_gaps_invalid:{group_id}",
        )
        _require(
            bool(expected)
            and len(set(expected)) == len(expected)
            and set(expected).issubset(gap_policies),
            f"crosswalk_writer_group_expected_gaps_invalid:{group_id}",
        )
        for field in ("reader_label_zh", "reader_label_en", "report_placement"):
            _text(policy.get(field), f"crosswalk_writer_group_field_missing:{group_id}:{field}")
    bridge_policy = _mapping(
        program.get("independent_S2_bridge_gap_policy"),
        "crosswalk_bridge_policy_invalid",
    )
    _require(
        bridge_policy.get("gap_id") == "dell-gap-product-profit-attribution"
        and bridge_policy.get("must_not_be_pack_gap") is True,
        "crosswalk_independent_bridge_policy_invalid",
    )
    _require(
        program.get("program_digest") == FROZEN_CROSSWALK_PROGRAM_DIGEST,
        "crosswalk_program_not_frozen",
    )


def _case_and_as_of_checks(
    *,
    pack: Mapping[str, Any],
    dynamic: Mapping[str, Any],
    writer: Mapping[str, Any],
    readiness_public: Mapping[str, Any],
    readiness_private: Mapping[str, Any],
    bridge_public: Mapping[str, Any],
) -> None:
    identities = {
        "pack": (pack.get("case_key"), pack.get("research_as_of")),
        "dynamic": (
            _path_value(
                dynamic,
                ["workpaper_context", "case_identity", "case_key"],
                "crosswalk_dynamic_case_missing",
            ),
            _path_value(
                dynamic,
                ["workpaper_context", "case_identity", "research_as_of"],
                "crosswalk_dynamic_as_of_missing",
            ),
        ),
        "writer": (writer.get("case_key"), "2026-08-06"),
        "readiness_public": (readiness_public.get("case_key"), "2026-08-06"),
        "readiness_private": (readiness_private.get("case_key"), "2026-08-06"),
        "bridge_public": (
            bridge_public.get("case_key"),
            bridge_public.get("research_as_of"),
        ),
    }
    _require(
        all(case == "DELL" for case, _ in identities.values()),
        "crosswalk_case_identity_mismatch",
    )
    _require(
        all(as_of == "2026-08-06" for _, as_of in identities.values()),
        "crosswalk_research_as_of_mismatch",
    )


def _contains_forbidden_projection_value(value: object, *, reader: bool) -> bool:
    if isinstance(value, Mapping):
        return any(
            _contains_forbidden_projection_value(item, reader=reader)
            for key, item in value.items()
            if key != "crosswalk_content_digest"
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(
            _contains_forbidden_projection_value(item, reader=reader) for item in value
        )
    if not isinstance(value, str):
        return False
    lowered = value.lower()
    common = (
        "data/workbench_private" in lowered
        or "\\workbench_private\\" in lowered
        or bool(_HEX_64.search(value))
        or "expected_close" in lowered
        or "should_close" in lowered
    )
    reader_only = reader and ("GAP::" in value or "EV::" in value or "NUM::" in value)
    return common or reader_only


def _content_from_audit_projection(audit: Mapping[str, Any]) -> dict[str, Any]:
    _require(
        set(audit)
        == {
            "schema_version",
            "case_key",
            "research_as_of",
            "crosswalk_content_digest",
            "counts",
            "pack_gap_entries",
            "writer_groups",
            "S2_bridge_gap_entries",
            "authority",
        }
        and audit.get("schema_version") == AUDIT_PROJECTION_SCHEMA_VERSION
        and audit.get("case_key") == "DELL"
        and audit.get("research_as_of") == "2026-08-06",
        "crosswalk_audit_projection_contract_invalid",
    )
    pack_rows = [
        dict(_mapping(row, "crosswalk_audit_pack_row_invalid"))
        for row in _sequence(
            audit.get("pack_gap_entries"), "crosswalk_audit_pack_rows_invalid"
        )
    ]
    pack_row_fields = {
        "gap_id",
        "facet_id",
        "gap_code",
        "slot_id",
        "stage_owner",
        "source_or_method_type",
        "research_disposition",
        "next_legal_action",
        "unit_selection_state",
        "technical_chain_state",
        "dynamic_gap_ref",
        "writer_group_id",
        "writer_gap_refs",
        "reader_label_zh",
        "reader_label_en",
        "why_it_matters_zh",
        "why_it_matters_en",
        "what_evidence_would_change_zh",
        "what_evidence_would_change_en",
        "report_placement",
        "company_vs_industry_boundary",
        "numeric_authority_boundary",
        "stop_boundary",
        "candidate_admission_request_ids",
        "public_information_gap_authority",
        "closed",
        "closure_receipt",
        "status_basis",
    }
    pack_ids: set[str] = set()
    pack_facets: set[str] = set()
    pack_writer_refs: set[str] = set()
    for row in pack_rows:
        gap_id = _text(row.get("gap_id"), "crosswalk_audit_gap_id_invalid")
        facet_id = _text(row.get("facet_id"), "crosswalk_audit_facet_id_invalid")
        _require(
            set(row) == pack_row_fields
            and gap_id not in pack_ids
            and facet_id not in pack_facets,
            "crosswalk_audit_pack_row_contract_invalid",
        )
        pack_ids.add(gap_id)
        pack_facets.add(facet_id)
        unit_state = row.get("unit_selection_state")
        technical_state = row.get("technical_chain_state")
        _require(
            unit_state in UNIT_SELECTION_STATES
            and technical_state in TECHNICAL_CHAIN_STATES,
            "crosswalk_audit_state_enum_invalid",
        )
        _require(
            (unit_state == "selected_by_unit" and technical_state == "technical_chain_closed")
            or (
                unit_state == "not_selected_by_unit"
                and technical_state == "technical_chain_not_evaluated"
            ),
            "crosswalk_audit_state_axes_combination_invalid",
        )
        _require(
            (
                unit_state == "selected_by_unit"
                and bool(row.get("dynamic_gap_ref"))
            )
            or (
                unit_state == "not_selected_by_unit"
                and row.get("dynamic_gap_ref") is None
            ),
            "crosswalk_audit_dynamic_ref_state_mismatch",
        )
        _require(
            row.get("research_disposition") in RESEARCH_DISPOSITIONS
            and row.get("source_or_method_type") in SOURCE_OR_METHOD_TYPES,
            "crosswalk_audit_research_enum_invalid",
        )
        _require(
            row.get("public_information_gap_authority") is False
            and row.get("closed") is False
            and row.get("closure_receipt") is None,
            "crosswalk_audit_false_closure",
        )
        refs = [
            str(item)
            for item in _sequence(
                row.get("writer_gap_refs"), "crosswalk_audit_writer_refs_invalid"
            )
        ]
        _require(
            len(refs) == len(set(refs))
            and not (pack_writer_refs & set(refs)),
            "crosswalk_audit_writer_ref_duplicate",
        )
        pack_writer_refs.update(refs)

    writer_rows = [
        dict(_mapping(row, "crosswalk_audit_writer_group_invalid"))
        for row in _sequence(
            audit.get("writer_groups"), "crosswalk_audit_writer_groups_invalid"
        )
    ]
    writer_fields = {
        "writer_group_id",
        "reader_label_zh",
        "reader_label_en",
        "report_placement",
        "pack_gap_ids",
        "writer_gap_refs",
        "writer_model_text",
    }
    writer_ids: set[str] = set()
    writer_refs: set[str] = set()
    writer_pack_ids: set[str] = set()
    for row in writer_rows:
        group_id = _text(
            row.get("writer_group_id"), "crosswalk_audit_writer_group_id_invalid"
        )
        group_pack_ids = set(
            str(item)
            for item in _sequence(
                row.get("pack_gap_ids"), "crosswalk_audit_writer_pack_ids_invalid"
            )
        )
        group_refs = set(
            str(item)
            for item in _sequence(
                row.get("writer_gap_refs"), "crosswalk_audit_writer_refs_invalid"
            )
        )
        _require(
            set(row) == writer_fields
            and group_id not in writer_ids
            and group_pack_ids
            and group_pack_ids.issubset(pack_ids)
            and not (writer_pack_ids & group_pack_ids)
            and group_refs
            and not (writer_refs & group_refs),
            "crosswalk_audit_writer_group_contract_invalid",
        )
        writer_ids.add(group_id)
        writer_pack_ids.update(group_pack_ids)
        writer_refs.update(group_refs)
        for gap_id in group_pack_ids:
            pack_row = next(row for row in pack_rows if row["gap_id"] == gap_id)
            _require(
                pack_row.get("writer_group_id") == group_id,
                "crosswalk_audit_writer_group_membership_mismatch",
            )
    _require(
        writer_refs == pack_writer_refs,
        "crosswalk_audit_writer_ref_projection_mismatch",
    )
    for row in pack_rows:
        group_id = row.get("writer_group_id")
        _require(
            group_id is None or group_id in writer_ids,
            "crosswalk_audit_pack_writer_group_unknown",
        )
        if group_id is None:
            _require(
                row.get("writer_gap_refs") == [],
                "crosswalk_audit_unreferenced_pack_gap_has_writer_refs",
            )
    for group in writer_rows:
        member_refs = {
            ref
            for row in pack_rows
            if row.get("writer_group_id") == group["writer_group_id"]
            for ref in row["writer_gap_refs"]
        }
        _require(
            member_refs == set(group["writer_gap_refs"]),
            "crosswalk_audit_writer_group_ref_membership_mismatch",
        )

    bridge_rows = [
        dict(_mapping(row, "crosswalk_audit_bridge_row_invalid"))
        for row in _sequence(
            audit.get("S2_bridge_gap_entries"), "crosswalk_audit_bridge_rows_invalid"
        )
    ]
    bridge_fields = {
        "gap_id",
        "pack_gap_id",
        "stage_owner",
        "reader_label_zh",
        "reader_label_en",
        "report_placement",
        "current_value_state",
        "closed",
        "public_information_gap_authority",
    }
    bridge_by_id = _unique_by(
        bridge_rows,
        "gap_id",
        code="crosswalk_audit_bridge_gap_duplicate_or_invalid",
    )
    _require(
        set(bridge_by_id)
        == {
            "dell-gap-pricing-asp",
            "dell-gap-pricing-units",
            "dell-gap-price-volume-mix-bridge",
            "dell-gap-product-profit-attribution",
        },
        "crosswalk_audit_bridge_gap_set_invalid",
    )
    for gap_id, row in bridge_by_id.items():
        _require(
            set(row) == bridge_fields
            and row.get("current_value_state") == "null_until_authorized_inputs"
            and row.get("closed") is False
            and row.get("public_information_gap_authority") is False
            and (
                (gap_id in pack_ids and row.get("pack_gap_id") == gap_id)
                or (
                    gap_id == "dell-gap-product-profit-attribution"
                    and row.get("pack_gap_id") is None
                )
            ),
            "crosswalk_audit_bridge_row_contract_invalid",
        )

    derived_counts = {
        "pack_gaps": len(pack_rows),
        "dynamic_unit_gaps": sum(
            row["unit_selection_state"] == "selected_by_unit" for row in pack_rows
        ),
        "writer_groups": len(writer_rows),
        "writer_gap_refs": len(writer_refs),
        "S2_bridge_gaps": len(bridge_rows),
        "pack_gaps_not_selected_by_unit": sum(
            row["unit_selection_state"] == "not_selected_by_unit" for row in pack_rows
        ),
        "pack_gaps_not_referenced_by_writer": sum(
            row["writer_group_id"] is None for row in pack_rows
        ),
    }
    _require(
        audit.get("counts") == derived_counts == EXPECTED_CROSSWALK_COUNTS,
        "crosswalk_audit_counts_recompute_mismatch",
    )
    _require(
        [row["gap_id"] for row in pack_rows] == sorted(pack_ids)
        and [row["writer_group_id"] for row in writer_rows] == sorted(writer_ids)
        and [row["gap_id"] for row in bridge_rows] == sorted(bridge_by_id),
        "crosswalk_audit_canonical_order_invalid",
    )
    return {
        "schema_version": CROSSWALK_CONTENT_SCHEMA_VERSION,
        "case_key": "DELL",
        "research_as_of": "2026-08-06",
        "counts": deepcopy(derived_counts),
        "pack_gap_entries": deepcopy(pack_rows),
        "writer_groups": deepcopy(writer_rows),
        "S2_bridge_gap_entries": deepcopy(bridge_rows),
    }


def _build_audit_projection(
    content: Mapping[str, Any], content_digest: str
) -> dict[str, Any]:
    return {
        "schema_version": AUDIT_PROJECTION_SCHEMA_VERSION,
        "case_key": "DELL",
        "research_as_of": "2026-08-06",
        "crosswalk_content_digest": content_digest,
        "counts": deepcopy(content["counts"]),
        "pack_gap_entries": deepcopy(content["pack_gap_entries"]),
        "writer_groups": deepcopy(content["writer_groups"]),
        "S2_bridge_gap_entries": deepcopy(content["S2_bridge_gap_entries"]),
        "authority": {
            "gap_closed_count": 0,
            "proved_information_boundary_count": 0,
            "model_calls_authorized": False,
            "source_calls_authorized": False,
            "G1_independent_review_pass": False,
        },
    }


def _build_model_projection(
    content: Mapping[str, Any], content_digest: str
) -> dict[str, Any]:
    return {
        "schema_version": MODEL_PROJECTION_SCHEMA_VERSION,
        "case_key": "DELL",
        "research_as_of": "2026-08-06",
        "crosswalk_content_digest": content_digest,
        "counts": deepcopy(content["counts"]),
        "authority": {
            "candidate_is_not_evidence": True,
            "not_selected_does_not_mean_closed": True,
            "method_parameter_is_not_company_disclosure": True,
            "industry_context_is_not_company_exact_fact": True,
            "numeric_values_may_not_be_created": True,
            "gap_closure_authorized": False,
        },
        "gap_boundaries": [
            {
                "facet_id": row["facet_id"],
                "research_disposition": row["research_disposition"],
                "next_legal_action": row["next_legal_action"],
                "stage_owner": row["stage_owner"],
                "unit_selection_state": row["unit_selection_state"],
                "technical_chain_state": row["technical_chain_state"],
                "source_or_method_type": row["source_or_method_type"],
                "company_vs_industry_boundary": row["company_vs_industry_boundary"],
                "numeric_authority_boundary": row["numeric_authority_boundary"],
                "why_it_matters_zh": row["why_it_matters_zh"],
                "what_evidence_would_change_zh": row["what_evidence_would_change_zh"],
                "stop_boundary": row["stop_boundary"],
            }
            for row in content["pack_gap_entries"]
        ],
        "writer_theme_index": [
            {
                "theme": row["reader_label_en"],
                "report_placement": row["report_placement"],
                "boundary_count": len(row["pack_gap_ids"]),
            }
            for row in content["writer_groups"]
        ],
        "S2_bridge_boundaries": [
            {
                "label": row["reader_label_en"],
                "stage_owner": row["stage_owner"],
                "current_value_state": row["current_value_state"],
            }
            for row in content["S2_bridge_gap_entries"]
        ],
    }


def _build_reader_projection(
    content: Mapping[str, Any], content_digest: str
) -> dict[str, Any]:
    return {
        "schema_version": READER_PROJECTION_SCHEMA_VERSION,
        "case_key": "DELL",
        "research_as_of": "2026-08-06",
        "crosswalk_content_digest": content_digest,
        "summary_uncertainty_zh": (
            "当前 14 项材料边界均未关闭；动态单元只选择其中 9 项，报告将 10 个引用聚合成 4 个主题，"
            "这些层级变化不代表缺口减少。"
        ),
        "summary_uncertainty_en": (
            "All 14 source-pack boundaries remain open. The dynamic unit selected nine, "
            "while the report grouped ten references into four themes; those layer changes "
            "do not mean that gaps were eliminated."
        ),
        "report_theme_index": [
            {
                "label_zh": row["reader_label_zh"],
                "label_en": row["reader_label_en"],
                "report_placement": row["report_placement"],
                "boundary_count": len(row["pack_gap_ids"]),
            }
            for row in content["writer_groups"]
        ],
        "boundary_register": [
            {
                "label_zh": row["reader_label_zh"],
                "label_en": row["reader_label_en"],
                "current_disposition": row["research_disposition"],
                "why_it_matters_zh": row["why_it_matters_zh"],
                "why_it_matters_en": row["why_it_matters_en"],
                "what_evidence_would_change_zh": row["what_evidence_would_change_zh"],
                "what_evidence_would_change_en": row["what_evidence_would_change_en"],
                "report_placement": row["report_placement"],
                "selected_by_current_dynamic_unit": (
                    row["unit_selection_state"] == "selected_by_unit"
                ),
            }
            for row in content["pack_gap_entries"]
        ],
        "S2_bridge_register": [
            {
                "label_zh": row["reader_label_zh"],
                "label_en": row["reader_label_en"],
                "current_value_state": row["current_value_state"],
                "report_placement": row["report_placement"],
            }
            for row in content["S2_bridge_gap_entries"]
        ],
        "reader_source_status": (
            "Current internal lineage is bound; publication-ready title, publisher, date, "
            "section and locator surfaces remain pending the reader citation appendix."
        ),
    }


def validate_crosswalk_projections(compiled: Mapping[str, Any]) -> None:
    _require(
        set(compiled)
        == {
            "crosswalk_content_digest",
            "audit_projection",
            "model_visible_projection",
            "reader_visible_projection",
        },
        "crosswalk_compiled_projection_fields_invalid",
    )
    content_digest = _text(
        compiled.get("crosswalk_content_digest"), "crosswalk_content_digest_missing"
    )
    audit = _mapping(compiled.get("audit_projection"), "crosswalk_audit_projection_missing")
    model = _mapping(
        compiled.get("model_visible_projection"), "crosswalk_model_projection_missing"
    )
    reader = _mapping(
        compiled.get("reader_visible_projection"), "crosswalk_reader_projection_missing"
    )
    _require(
        not _contains_forbidden_projection_value(model, reader=False),
        "crosswalk_model_projection_private_leakage",
    )
    _require(
        not _contains_forbidden_projection_value(reader, reader=True),
        "crosswalk_reader_projection_lineage_leakage",
    )
    content = _content_from_audit_projection(audit)
    recomputed_digest = canonical_digest(content)
    _require(
        content_digest == recomputed_digest,
        "crosswalk_content_digest_recompute_mismatch",
    )
    _require(
        dict(audit) == _build_audit_projection(content, recomputed_digest),
        "crosswalk_audit_projection_not_deterministic",
    )
    bridge_rows = _sequence(
        reader.get("S2_bridge_register"), "crosswalk_reader_bridge_register_invalid"
    )
    null_labels = {
        row.get("label_en")
        for row in bridge_rows
        if row.get("current_value_state") == "null_until_authorized_inputs"
    }
    _require(
        "Price-volume-mix bridge" in null_labels,
        "crosswalk_reader_PVM_null_boundary_hidden",
    )
    _require(
        "AI-server product-profit attribution" in null_labels,
        "crosswalk_reader_product_profit_null_boundary_hidden",
    )
    _require(
        dict(model) == _build_model_projection(content, recomputed_digest),
        "crosswalk_model_projection_not_deterministic",
    )
    _require(
        dict(reader) == _build_reader_projection(content, recomputed_digest),
        "crosswalk_reader_projection_not_deterministic",
    )


def compile_report_gap_crosswalk(
    *,
    baseline_manifest: Mapping[str, Any],
    evaluation_protocol: Mapping[str, Any],
    authority_template: Mapping[str, Any],
    program: Mapping[str, Any],
    pack: Mapping[str, Any],
    R4_successor_result: Mapping[str, Any],
    R4_evidence_gate_result: Mapping[str, Any],
    dynamic_full_result: Mapping[str, Any],
    writer_full_result: Mapping[str, Any],
    readiness_public_result: Mapping[str, Any],
    readiness_private_result: Mapping[str, Any],
    bridge_public_result: Mapping[str, Any],
    bridge_private_result: Mapping[str, Any],
) -> dict[str, Any]:
    """Compile the 14/9/4 crosswalk without granting source or model authority."""

    validate_evaluation_protocol(evaluation_protocol, baseline_manifest)
    validate_execution_authority_template(authority_template, baseline_manifest)
    validate_crosswalk_program(
        program,
        baseline_manifest=baseline_manifest,
        evaluation_protocol=evaluation_protocol,
        authority_template=authority_template,
    )
    _case_and_as_of_checks(
        pack=pack,
        dynamic=dynamic_full_result,
        writer=writer_full_result,
        readiness_public=readiness_public_result,
        readiness_private=readiness_private_result,
        bridge_public=bridge_public_result,
    )
    _require(
        R4_successor_result.get("case_key") == "DELL"
        and R4_successor_result.get("research_as_of") == "2026-08-06"
        and R4_evidence_gate_result.get("consumer_case_key") == "DELL"
        and R4_evidence_gate_result.get("research_as_of") == "2026-08-06",
        "crosswalk_R4_case_identity_mismatch",
    )
    _require(
        set(R4_evidence_gate_result.get("gap_ids_narrowed") or [])
        == set(program.get("expected_narrowed_gap_ids") or [])
        == EXPECTED_NARROWED_GAP_IDS
        and R4_evidence_gate_result.get("gap_ids_satisfied") == []
        and _path_value(
            R4_successor_result,
            ["coverage_delta", "gap_narrowed_count"],
            "crosswalk_R4_narrowed_count_missing",
        )
        == len(EXPECTED_NARROWED_GAP_IDS)
        and _path_value(
            R4_successor_result,
            ["coverage_delta", "gap_closed_count"],
            "crosswalk_R4_closed_count_missing",
        )
        == 0,
        "crosswalk_R4_gap_disposition_mismatch",
    )

    pack_gaps = _unique_by(
        _sequence(pack.get("residual_gaps"), "crosswalk_pack_gaps_invalid"),
        "gap_id",
        code="crosswalk_pack_gap_duplicate_or_invalid",
    )
    _require(len(pack_gaps) == 14, "crosswalk_pack_gap_count_invalid")
    pack_facets: dict[str, str] = {}
    for gap_id, gap in pack_gaps.items():
        facet = _text(gap.get("facet_id"), f"crosswalk_pack_facet_missing:{gap_id}")
        _require(facet not in pack_facets, "crosswalk_pack_facet_ambiguous")
        pack_facets[facet] = gap_id

    policies = _unique_by(
        _sequence(program.get("gap_policies"), "crosswalk_gap_policies_invalid"),
        "gap_id",
        code="crosswalk_gap_policy_duplicate_or_invalid",
    )
    _require(set(policies) == set(pack_gaps), "crosswalk_gap_policy_pack_set_mismatch")

    readiness = _mapping(
        readiness_private_result.get("pack_readiness"),
        "crosswalk_private_readiness_missing",
    )
    receipts = _unique_by(
        _sequence(
            readiness.get("declared_pack_gap_receipts"),
            "crosswalk_gap_receipts_invalid",
        ),
        "gap_id",
        code="crosswalk_gap_receipt_duplicate_or_invalid",
    )
    _require(set(receipts) == set(pack_gaps), "crosswalk_gap_receipt_set_mismatch")
    _require(
        all(
            receipt.get("eligible_as_true_public_information_gap") is False
            for receipt in receipts.values()
        ),
        "crosswalk_false_public_information_gap_authority",
    )

    dynamic_cards = _sequence(
        _path_value(
            dynamic_full_result,
            ["workpaper_context", "cell_analysis_view", "cell", "residual_gap_cards"],
            "crosswalk_dynamic_gap_cards_missing",
        ),
        "crosswalk_dynamic_gap_cards_invalid",
    )
    dynamic_by_ref = _unique_by(
        dynamic_cards,
        "gap_ref",
        code="crosswalk_dynamic_gap_ref_duplicate_or_invalid",
    )
    _require(len(dynamic_by_ref) == 9, "crosswalk_dynamic_gap_count_invalid")
    dynamic_ref_to_pack: dict[str, str] = {}
    for gap_ref, card in dynamic_by_ref.items():
        facet = _text(card.get("facet_id"), "crosswalk_dynamic_facet_missing")
        _require(facet in pack_facets, "crosswalk_dynamic_facet_unknown")
        pack_gap_id = pack_facets[facet]
        _require(
            pack_gap_id not in dynamic_ref_to_pack.values(),
            "crosswalk_dynamic_pack_mapping_duplicate",
        )
        dynamic_ref_to_pack[gap_ref] = pack_gap_id
    stop_refs = set(
        _sequence(
            _path_value(
                dynamic_full_result,
                ["workpaper_context", "stop_decision", "remaining_gap_refs"],
                "crosswalk_dynamic_stop_refs_missing",
            ),
            "crosswalk_dynamic_stop_refs_invalid",
        )
    )
    _require(stop_refs == set(dynamic_by_ref), "crosswalk_dynamic_stop_ref_set_mismatch")

    writer_groups_raw = _sequence(
        _path_value(
            writer_full_result,
            ["candidate_draft", "remaining_gaps"],
            "crosswalk_writer_remaining_gaps_missing",
        ),
        "crosswalk_writer_remaining_gaps_invalid",
    )
    _require(len(writer_groups_raw) == 4, "crosswalk_writer_group_count_invalid")
    overrides = _mapping(
        program.get("writer_gap_ref_overrides"),
        "crosswalk_writer_gap_ref_overrides_invalid",
    )
    _require(
        set(overrides).isdisjoint(dynamic_ref_to_pack),
        "crosswalk_writer_override_masks_dynamic_ref",
    )
    writer_ref_to_pack = dict(dynamic_ref_to_pack)
    writer_ref_to_pack.update({str(key): str(value) for key, value in overrides.items()})
    _require(
        set(writer_ref_to_pack.values()).issubset(pack_gaps),
        "crosswalk_writer_override_unknown_pack_gap",
    )

    writer_policy_rows = _sequence(
        program.get("writer_group_policies"),
        "crosswalk_writer_group_policies_invalid",
    )
    writer_policy_by_gap_set: dict[frozenset[str], Mapping[str, Any]] = {}
    for raw_policy in writer_policy_rows:
        policy = _mapping(raw_policy, "crosswalk_writer_group_policy_invalid")
        key = frozenset(str(item) for item in policy["expected_pack_gap_ids"])
        _require(key not in writer_policy_by_gap_set, "crosswalk_writer_group_policy_ambiguous")
        writer_policy_by_gap_set[key] = policy

    writer_groups: list[dict[str, Any]] = []
    seen_writer_refs: set[str] = set()
    writer_pack_membership: dict[str, str] = {}
    for raw_group in writer_groups_raw:
        group = _mapping(raw_group, "crosswalk_writer_group_invalid")
        refs = [str(item) for item in _sequence(group.get("gap_refs"), "crosswalk_writer_refs_invalid")]
        _require(refs and len(set(refs)) == len(refs), "crosswalk_writer_group_ref_duplicate")
        _require(not (seen_writer_refs & set(refs)), "crosswalk_writer_ref_reused_across_groups")
        _require(set(refs).issubset(writer_ref_to_pack), "crosswalk_writer_unknown_gap_ref")
        seen_writer_refs.update(refs)
        mapped_ids = frozenset(writer_ref_to_pack[ref] for ref in refs)
        _require(
            mapped_ids in writer_policy_by_gap_set,
            "crosswalk_writer_group_semantic_mapping_missing",
        )
        policy = writer_policy_by_gap_set[mapped_ids]
        group_id = str(policy["writer_group_id"])
        for gap_id in mapped_ids:
            _require(gap_id not in writer_pack_membership, "crosswalk_pack_gap_in_multiple_writer_groups")
            writer_pack_membership[gap_id] = group_id
        writer_groups.append(
            {
                "writer_group_id": group_id,
                "reader_label_zh": policy["reader_label_zh"],
                "reader_label_en": policy["reader_label_en"],
                "report_placement": policy["report_placement"],
                "pack_gap_ids": sorted(mapped_ids),
                "writer_gap_refs": sorted(refs),
                "writer_model_text": _text(
                    group.get("model_text"), "crosswalk_writer_model_text_missing"
                ),
            }
        )
    _require(len(seen_writer_refs) == 10, "crosswalk_writer_gap_ref_count_invalid")
    _require(
        set(overrides) == seen_writer_refs - set(dynamic_ref_to_pack),
        "crosswalk_writer_override_set_invalid",
    )
    _require(
        set(pack_gaps) - set(writer_pack_membership)
        == set(program.get("expected_pack_gaps_not_referenced_by_writer") or []),
        "crosswalk_not_writer_referenced_gap_set_mismatch",
    )

    public_requests = _unique_by(
        _sequence(readiness_public_result.get("requests"), "crosswalk_public_requests_invalid"),
        "request_id",
        code="crosswalk_public_request_duplicate_or_invalid",
    )
    dynamic_pack_ids = set(dynamic_ref_to_pack.values())
    _require(
        set(pack_gaps) - dynamic_pack_ids
        == set(program.get("expected_pack_gaps_not_selected_by_unit") or []),
        "crosswalk_not_selected_gap_set_mismatch",
    )
    dynamic_pack_to_ref = {value: key for key, value in dynamic_ref_to_pack.items()}
    pack_entries: list[dict[str, Any]] = []
    for gap_id in sorted(pack_gaps):
        gap = pack_gaps[gap_id]
        policy = policies[gap_id]
        receipt = receipts[gap_id]
        selected = gap_id in dynamic_pack_ids
        admission_request_ids = [
            str(item) for item in policy.get("candidate_admission_request_ids") or []
        ]
        for request_id in admission_request_ids:
            _require(
                request_id in public_requests
                and public_requests[request_id].get("readiness_state")
                == "blocked_by_evidence_admission",
                f"crosswalk_candidate_admission_request_invalid:{gap_id}",
            )
        if policy.get("research_disposition") == "candidate_admission_pending":
            _require(admission_request_ids, f"crosswalk_candidate_admission_basis_missing:{gap_id}")
        if policy.get("research_disposition") in {"source_route_pending", "narrowed"}:
            blockers = set(receipt.get("blockers") or [])
            _require(
                "official_or_external_supplement_route_not_exhausted" in blockers,
                f"crosswalk_source_route_basis_missing:{gap_id}",
            )
        if policy.get("research_disposition") == "S3_method_parameter":
            _require(
                gap.get("gap_code") == "threshold_not_observable",
                f"crosswalk_method_parameter_basis_invalid:{gap_id}",
            )
        pack_entries.append(
            {
                "gap_id": gap_id,
                "facet_id": gap["facet_id"],
                "gap_code": gap["gap_code"],
                "slot_id": gap["slot_id"],
                "stage_owner": policy["stage_owner"],
                "source_or_method_type": policy["source_or_method_type"],
                "research_disposition": policy["research_disposition"],
                "next_legal_action": policy["next_legal_action"],
                "unit_selection_state": (
                    "selected_by_unit" if selected else "not_selected_by_unit"
                ),
                "technical_chain_state": (
                    "technical_chain_closed"
                    if selected
                    else "technical_chain_not_evaluated"
                ),
                "dynamic_gap_ref": dynamic_pack_to_ref.get(gap_id),
                "writer_group_id": writer_pack_membership.get(gap_id),
                "writer_gap_refs": sorted(
                    ref for ref, mapped in writer_ref_to_pack.items() if mapped == gap_id and ref in seen_writer_refs
                ),
                "reader_label_zh": policy["reader_label_zh"],
                "reader_label_en": policy["reader_label_en"],
                "why_it_matters_zh": gap["business_reason_zh"],
                "why_it_matters_en": policy["why_it_matters_en"],
                "what_evidence_would_change_zh": gap["supplement_direction_zh"],
                "what_evidence_would_change_en": policy[
                    "what_evidence_would_change_en"
                ],
                "report_placement": policy["report_placement"],
                "company_vs_industry_boundary": policy[
                    "company_vs_industry_boundary"
                ],
                "numeric_authority_boundary": policy["numeric_authority_boundary"],
                "stop_boundary": policy["stop_boundary"],
                "candidate_admission_request_ids": sorted(admission_request_ids),
                "public_information_gap_authority": False,
                "closed": False,
                "closure_receipt": None,
                "status_basis": {
                    "readiness_receipt_digest": receipt["receipt_digest"],
                    "earliest_responsible_layer": receipt[
                        "earliest_responsible_layer"
                    ],
                },
            }
        )

    bridge = _mapping(
        bridge_private_result.get("product_value_bridge"),
        "crosswalk_product_bridge_missing",
    )
    bridge_receipts = _unique_by(
        _sequence(bridge.get("bridge_gap_receipts"), "crosswalk_bridge_receipts_invalid"),
        "gap_id",
        code="crosswalk_bridge_gap_duplicate_or_invalid",
    )
    expected_bridge_ids = {
        "dell-gap-pricing-asp",
        "dell-gap-pricing-units",
        "dell-gap-price-volume-mix-bridge",
        "dell-gap-product-profit-attribution",
    }
    _require(set(bridge_receipts) == expected_bridge_ids, "crosswalk_bridge_gap_set_invalid")
    _require(
        "dell-gap-product-profit-attribution" not in pack_gaps,
        "crosswalk_bridge_gap_masquerades_as_pack_gap",
    )
    _require(
        all(receipt.get("closed") is False for receipt in bridge_receipts.values()),
        "crosswalk_bridge_gap_false_closure",
    )
    pvm = _mapping(bridge.get("pvm_bridge"), "crosswalk_PVM_bridge_missing")
    _require(
        all(
            pvm.get(field) is None
            for field in ("price_effect_value", "volume_effect_value", "mix_effect_value")
        ),
        "crosswalk_PVM_null_invariant_invalid",
    )
    profit = _mapping(
        bridge.get("product_profit_bridge"), "crosswalk_product_profit_bridge_missing"
    )
    _require(
        profit.get("implied_product_operating_profit_value") is None,
        "crosswalk_product_profit_null_invariant_invalid",
    )
    independent_policy = _mapping(
        program.get("independent_S2_bridge_gap_policy"),
        "crosswalk_independent_bridge_policy_invalid",
    )
    entry_by_id = {row["gap_id"]: row for row in pack_entries}
    bridge_entries: list[dict[str, Any]] = []
    for gap_id in sorted(bridge_receipts):
        if gap_id in entry_by_id:
            source = entry_by_id[gap_id]
            label_zh = source["reader_label_zh"]
            label_en = source["reader_label_en"]
            placement = source["report_placement"]
        else:
            label_zh = independent_policy["reader_label_zh"]
            label_en = independent_policy["reader_label_en"]
            placement = independent_policy["report_placement"]
        bridge_entries.append(
            {
                "gap_id": gap_id,
                "pack_gap_id": gap_id if gap_id in pack_gaps else None,
                "stage_owner": bridge_receipts[gap_id]["owning_stage"],
                "reader_label_zh": label_zh,
                "reader_label_en": label_en,
                "report_placement": placement,
                "current_value_state": "null_until_authorized_inputs",
                "closed": False,
                "public_information_gap_authority": False,
            }
        )

    counts = {
        "pack_gaps": len(pack_entries),
        "dynamic_unit_gaps": len(dynamic_by_ref),
        "writer_groups": len(writer_groups),
        "writer_gap_refs": len(seen_writer_refs),
        "S2_bridge_gaps": len(bridge_entries),
        "pack_gaps_not_selected_by_unit": sum(
            row["unit_selection_state"] == "not_selected_by_unit" for row in pack_entries
        ),
        "pack_gaps_not_referenced_by_writer": sum(
            row["writer_group_id"] is None for row in pack_entries
        ),
    }
    _require(counts == program.get("expected_counts"), "crosswalk_compiled_counts_invalid")

    content = {
        "schema_version": CROSSWALK_CONTENT_SCHEMA_VERSION,
        "case_key": "DELL",
        "research_as_of": "2026-08-06",
        "counts": counts,
        "pack_gap_entries": sorted(pack_entries, key=lambda row: row["gap_id"]),
        "writer_groups": sorted(writer_groups, key=lambda row: row["writer_group_id"]),
        "S2_bridge_gap_entries": sorted(bridge_entries, key=lambda row: row["gap_id"]),
    }
    content_digest = canonical_digest(content)
    audit_projection = _build_audit_projection(content, content_digest)
    model_projection = _build_model_projection(content, content_digest)
    reader_projection = _build_reader_projection(content, content_digest)
    result = {
        "crosswalk_content_digest": content_digest,
        "audit_projection": audit_projection,
        "model_visible_projection": model_projection,
        "reader_visible_projection": reader_projection,
    }
    validate_crosswalk_projections(result)
    return result


__all__ = [
    "AUDIT_PROJECTION_SCHEMA_VERSION",
    "BASELINE_SCHEMA_VERSION",
    "BASELINE_VERIFICATION_SCHEMA_VERSION",
    "CROSSWALK_CONTENT_SCHEMA_VERSION",
    "CROSSWALK_PROGRAM_SCHEMA_VERSION",
    "EVALUATION_PROTOCOL_SCHEMA_VERSION",
    "EXECUTION_AUTHORITY_TEMPLATE_SCHEMA_VERSION",
    "MODEL_PROJECTION_SCHEMA_VERSION",
    "READER_PROJECTION_SCHEMA_VERSION",
    "ReportGapCrosswalkError",
    "compile_report_gap_crosswalk",
    "validate_crosswalk_program",
    "validate_crosswalk_projections",
    "validate_evaluation_protocol",
    "validate_execution_authority_template",
    "validate_program_baseline_manifest",
]
