from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any, Mapping, Sequence

from sec_agent.canonical_runtime import canonical_digest


BASELINE_SCHEMA_VERSION = "fin_ia_dell_source_report_quality_baseline_manifest_v1_0"
EVALUATION_PROTOCOL_SCHEMA_VERSION = (
    "fin_ia_dell_source_report_quality_evaluation_protocol_v1_0"
)
EXECUTION_AUTHORITY_TEMPLATE_SCHEMA_VERSION = (
    "fin_ia_dell_source_report_quality_execution_authority_template_v1_0"
)
CROSSWALK_PROGRAM_SCHEMA_VERSION = "fin_ia_dell_report_gap_crosswalk_program_v1_0"
CROSSWALK_CONTENT_SCHEMA_VERSION = "fin_ia_report_gap_crosswalk_content_v1_0"
AUDIT_PROJECTION_SCHEMA_VERSION = "fin_ia_report_gap_crosswalk_audit_projection_v1_0"
MODEL_PROJECTION_SCHEMA_VERSION = "fin_ia_report_gap_crosswalk_model_projection_v1_0"
READER_PROJECTION_SCHEMA_VERSION = "fin_ia_report_gap_crosswalk_reader_projection_v1_0"

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
    {"technical_chain_closed", "not_selected_by_unit"}
)
UNIT_SELECTION_STATES = frozenset(
    {"selected_by_unit", "not_selected_by_unit"}
)
SOURCE_OR_METHOD_TYPES = frozenset(
    {"source_evidence_boundary", "research_method_parameter", "numeric_or_bridge_boundary"}
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


def validate_program_baseline_manifest(
    manifest: Mapping[str, Any],
    *,
    source_bytes_by_ref: Mapping[str, bytes],
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
    parsed: dict[str, Any] = {}
    for binding_key, raw_binding in bindings.items():
        binding = _mapping(raw_binding, "baseline_input_binding_invalid")
        ref = _text(binding.get("ref"), "baseline_input_ref_invalid")
        _require(
            ref in source_bytes_by_ref,
            f"baseline_input_missing:{binding_key}",
        )
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
            _require(
                bool(binding.get("git_blob")) and bool(binding.get("git_commit")),
                f"baseline_input_git_identity_missing:{binding_key}",
            )
        else:
            _require(
                binding.get("git_blob") is None and binding.get("git_commit") is None,
                f"baseline_private_git_identity_invalid:{binding_key}",
            )
        content_type = binding.get("content_type")
        _require(
            content_type in {"application/json", "text/markdown"},
            f"baseline_input_content_type_invalid:{binding_key}",
        )
        if content_type == "text/markdown":
            _require(
                bool(payload.decode("utf-8").strip()),
                f"baseline_markdown_empty:{binding_key}",
            )
            continue
        try:
            value = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ReportGapCrosswalkError(
                f"baseline_json_invalid:{binding_key}"
            ) from exc
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
            path = _sequence(
                check.get("path"), f"baseline_identity_path_invalid:{binding_key}"
            )
            _require(
                _path_value(document, path, f"baseline_identity_path_missing:{binding_key}")
                == check.get("expected"),
                f"baseline_identity_value_invalid:{binding_key}",
            )
        digest_field = binding.get("canonical_digest_field")
        if digest_field is not None:
            digest_field = _text(
                digest_field, f"baseline_canonical_digest_field_invalid:{binding_key}"
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
        parsed[binding_key] = document

    frozen_counts = _mapping(
        manifest.get("frozen_counts"), "baseline_frozen_counts_invalid"
    )
    _require(
        frozen_counts
        == {
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
        },
        "baseline_frozen_counts_mismatch",
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
    return parsed


def validate_evaluation_protocol(
    protocol: Mapping[str, Any], baseline_manifest: Mapping[str, Any]
) -> None:
    _self_digest(protocol, "protocol_digest", "evaluation_protocol_digest_invalid")
    _require(
        protocol.get("schema_version") == EVALUATION_PROTOCOL_SCHEMA_VERSION
        and protocol.get("status") == "preregistered_before_successor_candidate"
        and protocol.get("case_key") == "DELL",
        "evaluation_protocol_identity_invalid",
    )
    baseline_binding = _mapping(
        protocol.get("baseline_manifest_binding"),
        "evaluation_protocol_baseline_binding_invalid",
    )
    _require(
        baseline_binding.get("manifest_digest")
        == baseline_manifest.get("manifest_digest"),
        "evaluation_protocol_baseline_digest_mismatch",
    )
    prerequisites = _mapping(
        protocol.get("formal_scoring_prerequisites"),
        "evaluation_protocol_prerequisites_invalid",
    )
    _require(
        prerequisites.get("L1_financial_truth_must_pass") is True
        and prerequisites.get("L2_evidence_authority_must_pass") is True
        and prerequisites.get("missing_component_disposition") == "not_assessable"
        and set(prerequisites.get("required_packet_components") or [])
        == REQUIRED_PACKET_COMPONENTS,
        "evaluation_protocol_prerequisite_contract_invalid",
    )
    thresholds = _mapping(
        protocol.get("eight_dimension_thresholds"),
        "evaluation_protocol_thresholds_invalid",
    )
    _require(
        thresholds.get("total_minimum") == 24
        and thresholds.get("maximum_total") == 32
        and thresholds.get("Q1_through_Q7_minimum_each") == 2
        and thresholds.get("Q1_Q2_Q3_Q8_minimum_each") == 3
        and thresholds.get("dimensions_at_or_above_3_minimum") == 4,
        "evaluation_protocol_threshold_contract_invalid",
    )
    severities = _mapping(
        protocol.get("finding_severity_contract"),
        "evaluation_protocol_severity_invalid",
    )
    _require(
        set(severities) == {"P0", "P1", "P2", "P3"},
        "evaluation_protocol_severity_set_invalid",
    )
    verdicts = _mapping(
        protocol.get("separate_verdicts"),
        "evaluation_protocol_verdicts_invalid",
    )
    _require(
        set(verdicts)
        == {
            "engineering_and_evidence_pipeline_verdict",
            "report_research_quality_verdict",
            "qualified_human_product_verdict",
        },
        "evaluation_protocol_verdict_set_invalid",
    )
    authority = _mapping(
        protocol.get("scoring_authority"),
        "evaluation_protocol_scoring_authority_invalid",
    )
    _require(
        authority.get("model_self_score_formal") is False
        and authority.get("LLM_as_judge_formal") is False
        and authority.get("author_can_formally_score_own_candidate") is False
        and authority.get("author_separated_content_reviewer_required") is True
        and authority.get("qualified_human_required_for_product_acceptance") is True,
        "evaluation_protocol_scoring_authority_granted",
    )
    _require(
        protocol.get("frozen_R17_baseline")
        == baseline_manifest.get("frozen_R17_report_quality_baseline"),
        "evaluation_protocol_R17_baseline_mismatch",
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
        program.get("expected_counts")
        == {
            "pack_gaps": 14,
            "dynamic_unit_gaps": 9,
            "writer_groups": 4,
            "writer_gap_refs": 10,
            "S2_bridge_gaps": 4,
            "pack_gaps_not_selected_by_unit": 5,
            "pack_gaps_not_referenced_by_writer": 4,
        },
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


def validate_crosswalk_projections(compiled: Mapping[str, Any]) -> None:
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
        audit.get("crosswalk_content_digest")
        == model.get("crosswalk_content_digest")
        == reader.get("crosswalk_content_digest")
        == content_digest,
        "crosswalk_projection_content_digest_mismatch",
    )
    _require(
        set(model)
        == {
            "schema_version",
            "case_key",
            "research_as_of",
            "crosswalk_content_digest",
            "counts",
            "authority",
            "gap_boundaries",
            "writer_theme_index",
            "S2_bridge_boundaries",
        },
        "crosswalk_model_projection_fields_invalid",
    )
    _require(
        set(reader)
        == {
            "schema_version",
            "case_key",
            "research_as_of",
            "crosswalk_content_digest",
            "summary_uncertainty_zh",
            "summary_uncertainty_en",
            "report_theme_index",
            "boundary_register",
            "S2_bridge_register",
            "reader_source_status",
        },
        "crosswalk_reader_projection_fields_invalid",
    )
    _require(
        not _contains_forbidden_projection_value(model, reader=False),
        "crosswalk_model_projection_private_leakage",
    )
    _require(
        not _contains_forbidden_projection_value(reader, reader=True),
        "crosswalk_reader_projection_lineage_leakage",
    )
    boundary_rows = _sequence(
        reader.get("boundary_register"), "crosswalk_reader_boundary_register_invalid"
    )
    labels = [_text(row.get("label_en"), "crosswalk_reader_label_invalid") for row in boundary_rows]
    _require(
        len(boundary_rows) == 14 and len(set(labels)) == 14,
        "crosswalk_reader_boundary_duplicate_or_missing",
    )
    bridge_rows = _sequence(
        reader.get("S2_bridge_register"), "crosswalk_reader_bridge_register_invalid"
    )
    pvm = [row for row in bridge_rows if row.get("label_en") == "Price-volume-mix bridge"]
    _require(
        len(pvm) == 1
        and pvm[0].get("current_value_state") == "null_until_authorized_inputs",
        "crosswalk_reader_PVM_null_boundary_hidden",
    )
    audit_rows = _sequence(audit.get("pack_gap_entries"), "crosswalk_audit_rows_invalid")
    for row in audit_rows:
        if row.get("research_disposition") == "closed":
            _require(
                bool(row.get("closure_receipt")),
                "crosswalk_closed_without_receipt",
            )


def compile_report_gap_crosswalk(
    *,
    baseline_manifest: Mapping[str, Any],
    evaluation_protocol: Mapping[str, Any],
    authority_template: Mapping[str, Any],
    program: Mapping[str, Any],
    pack: Mapping[str, Any],
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
                    "technical_chain_closed" if selected else "not_selected_by_unit"
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
    audit_projection = {
        "schema_version": AUDIT_PROJECTION_SCHEMA_VERSION,
        "case_key": "DELL",
        "research_as_of": "2026-08-06",
        "crosswalk_content_digest": content_digest,
        "counts": counts,
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
    model_projection = {
        "schema_version": MODEL_PROJECTION_SCHEMA_VERSION,
        "case_key": "DELL",
        "research_as_of": "2026-08-06",
        "crosswalk_content_digest": content_digest,
        "counts": counts,
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
                "source_or_method_type": row["source_or_method_type"],
                "company_vs_industry_boundary": row[
                    "company_vs_industry_boundary"
                ],
                "numeric_authority_boundary": row["numeric_authority_boundary"],
                "why_it_matters_zh": row["why_it_matters_zh"],
                "what_evidence_would_change_zh": row[
                    "what_evidence_would_change_zh"
                ],
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
    reader_projection = {
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
                "what_evidence_would_change_zh": row[
                    "what_evidence_would_change_zh"
                ],
                "what_evidence_would_change_en": row[
                    "what_evidence_would_change_en"
                ],
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
