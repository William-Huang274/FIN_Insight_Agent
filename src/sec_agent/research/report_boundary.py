from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .reviewed_evidence_pack import canonical_digest


REPORT_BOUNDARY_DISPOSITION_SCHEMA_VERSION = (
    "fin_ia_report_boundary_disposition_register_v1_0"
)
EVALUATION_AUTHORITY_SUPERSESSION_SCHEMA_VERSION = (
    "fin_ia_evaluation_authority_supersession_view_v1_0"
)
RESEARCH_METHOD_PARAMETER_REGISTER_SCHEMA_VERSION = (
    "fin_ia_research_method_parameter_register_v1_0"
)
WRITER_SUCCESSOR_INPUT_PROJECTION_SCHEMA_VERSION = (
    "fin_ia_writer_successor_input_projection_v1_0"
)

_OWNER_PLANES = {
    "data_infrastructure_and_tool",
    "harness_control",
    "agent_research_method_and_work_mode",
    "external_information_boundary",
}
_INFORMATION_STATES = {
    "local_source_exists_not_recalled_or_bound",
    "local_candidate_exists_evidence_admission_pending",
    "source_visible_numeric_authority_stale_downstream",
    "report_surface_duplicate_boundary_inventory",
    "agent_stopped_before_material_follow_up",
    "official_or_external_route_not_executed_or_not_terminal",
    "external_source_transport_or_parser_failure",
    "researcher_parameter_unset",
    "open_public_proxy_or_context_not_yet_exhausted",
    "public_non_disclosure_proved",
    "licensed_or_private_data_boundary",
}
_CUSTOMER_DISPOSITIONS = {
    "operations_only_omit_from_customer_report",
    "resolve_before_customer_report",
    "concise_current_run_uncertainty",
    "concise_proved_information_boundary",
}
_TRUE_BOUNDARY_STATES = {
    "public_non_disclosure_proved",
    "licensed_or_private_data_boundary",
}
_METHOD_PARAMETER_STATUSES = {
    "research_lead_or_user_parameter_pending",
    "frozen",
    "not_applicable",
}
_WRITER_WORKPAPER_FIELDS = {
    "agent_id",
    "thesis",
    "mechanism",
    "sourced_claims",
    "alternative_explanations",
    "strongest_counterarguments",
    "what_would_change",
    "confidence",
    "remaining_gap_refs",
    "workpaper_digest",
}


class ReportBoundaryDispositionError(ValueError):
    """Raised when an operational failure is disguised as an information gap."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ReportBoundaryDispositionError(code)


def compile_report_boundary_disposition_register(
    *,
    case_key: str,
    source_report_ref: str,
    source_report_digest: str,
    rows: Sequence[Mapping[str, Any]],
    recorded_at: str,
) -> dict[str, Any]:
    """Separate operations defects, current-run uncertainty and proved gaps.

    This compiler does not hide uncertainty or rewrite report prose.  It decides
    which unresolved statements must return to S1/S2/S3 operations, which may be
    summarized as a current-run limitation, and which have the receipts needed
    to appear as a genuine information boundary in a customer report.
    """

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in rows:
        row = deepcopy(dict(raw))
        boundary_id = str(row.get("boundary_id") or "")
        owner_plane = str(row.get("owner_plane") or "")
        information_state = str(row.get("information_state") or "")
        disposition = str(row.get("customer_surface_disposition") or "")
        true_boundary = row.get("true_information_boundary") is True
        surface_paths = sorted({str(value) for value in row.get("surface_paths") or ()})
        artifact_refs = sorted({str(value) for value in row.get("artifact_refs") or ()})
        _require(
            boundary_id
            and boundary_id not in seen
            and owner_plane in _OWNER_PLANES
            and information_state in _INFORMATION_STATES
            and disposition in _CUSTOMER_DISPOSITIONS
            and surface_paths
            and artifact_refs
            and str(row.get("owner_stage") or "")
            and str(row.get("root_cause_zh") or "")
            and str(row.get("next_action_zh") or ""),
            "report_boundary_disposition_row_invalid",
        )
        _require(
            true_boundary == (information_state in _TRUE_BOUNDARY_STATES),
            "report_boundary_true_information_state_mismatch",
        )
        _require(
            not true_boundary
            or disposition == "concise_proved_information_boundary",
            "report_boundary_proved_gap_customer_disposition_invalid",
        )
        _require(
            information_state not in {
                "local_source_exists_not_recalled_or_bound",
                "local_candidate_exists_evidence_admission_pending",
                "source_visible_numeric_authority_stale_downstream",
                "report_surface_duplicate_boundary_inventory",
                "agent_stopped_before_material_follow_up",
                "researcher_parameter_unset",
            }
            or disposition
            in {
                "operations_only_omit_from_customer_report",
                "resolve_before_customer_report",
            },
            "report_boundary_operational_failure_exposed_as_customer_gap",
        )
        seen.add(boundary_id)
        body = {
            **row,
            "surface_paths": surface_paths,
            "artifact_refs": artifact_refs,
            "customer_report_eligible": disposition
            in {
                "concise_current_run_uncertainty",
                "concise_proved_information_boundary",
            },
        }
        normalized.append({**body, "row_digest": canonical_digest(body)})

    _require(bool(normalized), "report_boundary_disposition_rows_empty")
    customer_rows = [
        row for row in normalized if row["customer_report_eligible"] is True
    ]
    operations_rows = [
        row for row in normalized if row["customer_report_eligible"] is False
    ]
    pre_report_blockers = list(operations_rows)
    payload = {
        "schema_version": REPORT_BOUNDARY_DISPOSITION_SCHEMA_VERSION,
        "status": "report_boundaries_attributed_no_automatic_rewrite",
        "recorded_at": recorded_at,
        "case_key": case_key.upper(),
        "source_report_ref": source_report_ref,
        "source_report_digest": source_report_digest,
        "rows": normalized,
        "customer_boundary_register": customer_rows,
        "operations_remediation_register": operations_rows,
        "pre_report_blockers": pre_report_blockers,
        "summary": {
            "boundary_statement_count": len(normalized),
            "customer_boundary_count": len(customer_rows),
            "operations_remediation_count": len(operations_rows),
            "proved_information_boundary_count": sum(
                row["true_information_boundary"] is True for row in normalized
            ),
            "pre_report_blocker_count": len(pre_report_blockers),
            "customer_report_ready": not pre_report_blockers,
        },
        "authority": {
            "report_prose_rewritten": False,
            "operational_failure_is_not_information_gap": True,
            "current_run_uncertainty_is_not_proved_non_disclosure": True,
            "qualified_human_content_review_required": True,
        },
    }
    return {**payload, "register_digest": canonical_digest(payload)}


def validate_report_boundary_disposition_register(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    value = deepcopy(dict(payload))
    digest = str(value.pop("register_digest", ""))
    _require(
        value.get("schema_version") == REPORT_BOUNDARY_DISPOSITION_SCHEMA_VERSION
        and digest == canonical_digest(value),
        "report_boundary_disposition_register_invalid",
    )
    replay = compile_report_boundary_disposition_register(
        case_key=str(value.get("case_key") or ""),
        source_report_ref=str(value.get("source_report_ref") or ""),
        source_report_digest=str(value.get("source_report_digest") or ""),
        rows=[
            {
                key: deepcopy(item)
                for key, item in row.items()
                if key not in {"customer_report_eligible", "row_digest"}
            }
            for row in value.get("rows") or ()
        ],
        recorded_at=str(value.get("recorded_at") or ""),
    )
    _require(
        replay == payload,
        "report_boundary_disposition_register_replay_drift",
    )
    return deepcopy(dict(payload))


def compile_evaluation_authority_supersession_view(
    *,
    authority_catalog: Mapping[str, Any],
    evaluation: Mapping[str, Any],
    finding_claim_bindings: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    """Remove only evaluator findings formally superseded by later authority.

    The original evaluation remains immutable.  A successor Writer view may
    omit an unresolved-numeric finding only when a proposition-bound claim is
    explicitly identified and the extended authority catalog now grants that
    claim source-bound authority.  Findings without an exact claim binding, and
    semantic model findings, remain active.  This avoids re-running Specialists
    merely because citation/number authority was attached after their analysis.
    """

    catalog = deepcopy(dict(authority_catalog))
    catalog_digest = str(catalog.get("authority_catalog_digest") or "")
    claims = catalog.get("claims")
    _require(
        len(catalog_digest) == 64
        and isinstance(claims, list)
        and bool(claims),
        "evaluation_supersession_catalog_invalid",
    )
    claims_by_ref: dict[str, dict[str, Any]] = {}
    for raw in claims:
        _require(isinstance(raw, Mapping), "evaluation_supersession_claim_invalid")
        claim_ref = str(raw.get("claim_ref") or "")
        _require(
            claim_ref and claim_ref not in claims_by_ref,
            "evaluation_supersession_claim_invalid",
        )
        claims_by_ref[claim_ref] = deepcopy(dict(raw))

    original = deepcopy(dict(evaluation))
    findings = original.get("findings")
    _require(
        isinstance(findings, list) and bool(findings),
        "evaluation_supersession_findings_invalid",
    )
    active: list[dict[str, Any]] = []
    superseded: list[dict[str, Any]] = []
    seen_codes: set[str] = set()
    for raw in findings:
        _require(isinstance(raw, Mapping), "evaluation_supersession_finding_invalid")
        finding = deepcopy(dict(raw))
        code = str(finding.get("finding_code") or "")
        _require(code and code not in seen_codes, "evaluation_supersession_finding_code_invalid")
        seen_codes.add(code)
        bound_claim_refs = sorted(
            {str(ref) for ref in finding_claim_bindings.get(code, ()) if str(ref)}
        )
        if not bound_claim_refs:
            active.append(finding)
            continue
        _require(
            code.startswith("NUM_REF_UNRESOLVED_")
            and all(ref in claims_by_ref for ref in bound_claim_refs),
            "evaluation_supersession_binding_invalid",
        )
        bound_claims = [claims_by_ref[ref] for ref in bound_claim_refs]
        _require(
            all(
                str(claim.get("agent_id") or "")
                == str(finding.get("target_agent_id") or "")
                and bool(claim.get("source_bound_authority_refs"))
                for claim in bound_claims
            ),
            "evaluation_supersession_authority_missing",
        )
        authority_refs = sorted(
            {
                str(ref)
                for claim in bound_claims
                for ref in claim.get("source_bound_authority_refs") or ()
            }
        )
        superseded.append(
            {
                **finding,
                "supersession_status": "superseded_by_source_bound_authority",
                "bound_claim_refs": bound_claim_refs,
                "superseding_authority_refs": authority_refs,
            }
        )

    writer_visible_evaluation = deepcopy(original)
    writer_visible_evaluation["findings"] = active
    writer_visible_evaluation.pop("evaluation_digest", None)
    writer_visible_evaluation["report_may_proceed"] = not any(
        bool(row.get("blocks_report")) for row in active
    )
    writer_visible_evaluation["evaluation_digest"] = canonical_digest(
        writer_visible_evaluation
    )
    body = {
        "schema_version": EVALUATION_AUTHORITY_SUPERSESSION_SCHEMA_VERSION,
        "status": "evaluation_view_refreshed_without_rewriting_original",
        "authority_catalog_digest": catalog_digest,
        "source_evaluation_digest": original.get("evaluation_digest"),
        "writer_visible_evaluation": writer_visible_evaluation,
        "writer_visible_findings": active,
        "superseded_findings": superseded,
        "summary": {
            "original_finding_count": len(findings),
            "writer_visible_finding_count": len(active),
            "superseded_finding_count": len(superseded),
        },
        "authority": {
            "original_evaluation_immutable": True,
            "source_bound_authority_may_supersede_only_bound_numeric_resolution_findings": True,
            "semantic_model_findings_preserved": True,
            "specialist_re_adjudication_required_only_for_semantic_authority_change": True,
        },
    }
    return {**body, "view_digest": canonical_digest(body)}


def compile_research_method_parameter_register(
    *,
    case_key: str,
    research_as_of: str,
    parameters: Sequence[Mapping[str, Any]],
    recorded_at: str,
) -> dict[str, Any]:
    """Separate researcher-owned decision parameters from source gaps."""

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_gap_refs: set[str] = set()
    for raw in parameters:
        row = deepcopy(dict(raw))
        parameter_id = str(row.get("parameter_id") or "")
        gap_ref = str(row.get("source_gap_ref") or "")
        status = str(row.get("status") or "")
        _require(
            parameter_id
            and parameter_id not in seen_ids
            and gap_ref.startswith("GAP::")
            and gap_ref not in seen_gap_refs
            and status in _METHOD_PARAMETER_STATUSES
            and str(row.get("decision_surface") or "")
            and str(row.get("owner") or "")
            and str(row.get("current_basis_zh") or "")
            and row.get("customer_surface_disposition")
            == "omit_from_information_gap_register",
            "research_method_parameter_row_invalid",
        )
        if status == "frozen":
            _require(
                row.get("frozen_value") not in (None, "")
                and str(row.get("frozen_by") or ""),
                "research_method_parameter_frozen_authority_missing",
            )
        else:
            _require(
                row.get("frozen_value") in (None, ""),
                "research_method_parameter_unfrozen_value_present",
            )
        seen_ids.add(parameter_id)
        seen_gap_refs.add(gap_ref)
        normalized.append(row)

    _require(bool(normalized), "research_method_parameter_rows_empty")
    body = {
        "schema_version": RESEARCH_METHOD_PARAMETER_REGISTER_SCHEMA_VERSION,
        "status": "research_method_parameters_separated_from_source_gaps",
        "recorded_at": recorded_at,
        "case_key": case_key.upper(),
        "research_as_of": research_as_of,
        "parameters": sorted(normalized, key=lambda row: str(row["parameter_id"])),
        "summary": {
            "parameter_count": len(normalized),
            "frozen_count": sum(row["status"] == "frozen" for row in normalized),
            "pending_count": sum(
                row["status"] == "research_lead_or_user_parameter_pending"
                for row in normalized
            ),
            "customer_information_gap_count": 0,
        },
        "authority": {
            "research_method_parameter_is_source_disclosure": False,
            "unfrozen_parameter_may_not_be_invented_by_writer": True,
            "parameter_state_may_inform_what_would_change": True,
        },
    }
    return {**body, "register_digest": canonical_digest(body)}


def compile_writer_successor_input_projection(
    *,
    workpapers: Sequence[Mapping[str, Any]],
    authority_catalog: Mapping[str, Any],
    evaluation_supersession_view: Mapping[str, Any],
    research_method_parameter_register: Mapping[str, Any],
) -> dict[str, Any]:
    """Create the canonical Writer view without mutating research artifacts.

    The projection removes only researcher-owned parameter placeholders from the
    customer gap surface and replaces a stale evaluator view only through an
    explicit authority-supersession receipt.  All original workpapers, catalog
    and evaluation digests remain in lineage.
    """

    catalog = deepcopy(dict(authority_catalog))
    catalog_digest = str(catalog.get("authority_catalog_digest") or "")
    unsigned_catalog = {
        key: deepcopy(value)
        for key, value in catalog.items()
        if key != "authority_catalog_digest"
    }
    _require(
        len(catalog_digest) == 64
        and catalog_digest == canonical_digest(unsigned_catalog),
        "writer_projection_authority_catalog_invalid",
    )

    supersession = deepcopy(dict(evaluation_supersession_view))
    supersession_digest = str(supersession.pop("view_digest", ""))
    _require(
        len(supersession_digest) == 64
        and supersession_digest == canonical_digest(supersession)
        and supersession.get("authority_catalog_digest") == catalog_digest,
        "writer_projection_supersession_view_invalid",
    )
    supersession["view_digest"] = supersession_digest

    method_register = deepcopy(dict(research_method_parameter_register))
    method_digest = str(method_register.pop("register_digest", ""))
    _require(
        method_register.get("schema_version")
        == RESEARCH_METHOD_PARAMETER_REGISTER_SCHEMA_VERSION
        and len(method_digest) == 64
        and method_digest == canonical_digest(method_register),
        "writer_projection_method_register_invalid",
    )
    method_register["register_digest"] = method_digest
    _require(
        str((catalog.get("case_identity") or {}).get("case_key") or "").upper()
        == str(method_register.get("case_key") or "").upper()
        and str((catalog.get("case_identity") or {}).get("research_as_of") or "")
        == str(method_register.get("research_as_of") or ""),
        "writer_projection_case_identity_drift",
    )

    method_gap_refs = {
        str(row["source_gap_ref"])
        for row in method_register.get("parameters") or ()
        if row.get("customer_surface_disposition")
        == "omit_from_information_gap_register"
    }
    catalog_gap_refs = {
        str(row.get("gap_ref") or "") for row in catalog.get("gap_authority") or ()
    }
    _require(
        method_gap_refs and method_gap_refs.issubset(catalog_gap_refs),
        "writer_projection_method_gap_ref_unresolved",
    )
    method_finding_codes = {
        str(code)
        for row in method_register.get("parameters") or ()
        for code in row.get("evaluation_finding_codes") or ()
        if str(code)
    }
    method_claim_refs = {
        str(ref)
        for row in method_register.get("parameters") or ()
        for ref in row.get("writer_omitted_claim_refs") or ()
        if str(ref)
    }
    catalog_claims = {
        str(row.get("claim_ref") or ""): deepcopy(dict(row))
        for row in catalog.get("claims") or ()
    }
    _require(
        method_claim_refs.issubset(catalog_claims),
        "writer_projection_method_claim_ref_unresolved",
    )
    method_claim_indexes_by_agent: dict[str, set[int]] = {}
    for ref in method_claim_refs:
        claim = catalog_claims[ref]
        method_claim_indexes_by_agent.setdefault(
            str(claim.get("agent_id") or ""), set()
        ).add(int(claim.get("claim_index")))
    exact_fragment_bindings = [
        deepcopy(dict(binding))
        for row in method_register.get("parameters") or ()
        for binding in row.get("writer_omitted_exact_fragments") or ()
    ]

    projected_workpapers: list[dict[str, Any]] = []
    removed_by_agent: list[dict[str, Any]] = []
    workpaper_projection_receipts: list[dict[str, Any]] = []
    for raw in workpapers:
        source = deepcopy(dict(raw))
        source_digest = str(source.get("workpaper_digest") or "")
        _require(len(source_digest) == 64, "writer_projection_workpaper_digest_invalid")
        row = {
            key: deepcopy(value)
            for key, value in source.items()
            if key in _WRITER_WORKPAPER_FIELDS
        }
        agent_id = str(row.get("agent_id") or "")
        omitted_claim_indexes = method_claim_indexes_by_agent.get(agent_id, set())
        row["sourced_claims"] = [
            deepcopy(dict(claim))
            for index, claim in enumerate(source.get("sourced_claims") or ())
            if index not in omitted_claim_indexes
        ]
        source_gaps = [str(ref) for ref in source.get("remaining_gap_refs") or ()]
        removed = sorted(set(source_gaps) & method_gap_refs)
        row["remaining_gap_refs"] = [
            ref for ref in source_gaps if ref not in method_gap_refs
        ]
        removed_fragments: list[dict[str, str]] = []
        for binding in exact_fragment_bindings:
            if str(binding.get("agent_id") or "") != agent_id:
                continue
            field_name = str(binding.get("field_name") or "")
            exact_text = str(binding.get("exact_text") or "")
            _require(
                field_name in {"thesis", "mechanism"}
                and exact_text
                and isinstance(row.get(field_name), str)
                and str(row[field_name]).count(exact_text) == 1,
                "writer_projection_exact_fragment_binding_invalid",
            )
            row[field_name] = " ".join(
                str(row[field_name]).replace(exact_text, "").split()
            )
            removed_fragments.append(
                {
                    "field_name": field_name,
                    "exact_fragment_digest": canonical_digest(exact_text),
                }
            )
        projection_receipt = {
            "agent_id": agent_id,
            "source_workpaper_digest": source_digest,
            "research_method_gap_refs_omitted": removed,
            "research_method_claim_indexes_omitted": sorted(
                omitted_claim_indexes
            ),
            "research_method_exact_fragments_omitted": removed_fragments,
            "operational_fields_not_exposed": sorted(
                set(source) - _WRITER_WORKPAPER_FIELDS
            ),
            "source_research_artifact_mutated": False,
            "writer_view_method_content_omitted": bool(
                removed or omitted_claim_indexes or removed_fragments
            ),
        }
        row["writer_view_digest"] = canonical_digest(
            {key: value for key, value in row.items() if key != "writer_view_digest"}
        )
        projection_receipt["writer_view_digest"] = row["writer_view_digest"]
        workpaper_projection_receipts.append(projection_receipt)
        projected_workpapers.append(row)
        if removed:
            removed_by_agent.append(
                {"agent_id": str(row.get("agent_id") or ""), "gap_refs": removed}
            )

    projected_catalog = deepcopy(catalog)
    projected_catalog["claims"] = [
        row
        for row in projected_catalog.get("claims") or ()
        if str(row.get("claim_ref") or "") not in method_claim_refs
    ]
    projected_catalog["claim_refs_by_agent"] = {
        str(agent_id): [
            str(ref) for ref in refs if str(ref) not in method_claim_refs
        ]
        for agent_id, refs in (
            projected_catalog.get("claim_refs_by_agent") or {}
        ).items()
    }
    projected_catalog["gap_authority"] = [
        row
        for row in projected_catalog.get("gap_authority") or ()
        if str(row.get("gap_ref") or "") not in method_gap_refs
    ]
    projected_catalog["workpaper_gap_bindings"] = [
        {
            **deepcopy(dict(binding)),
            "gap_refs": [
                str(ref)
                for ref in binding.get("gap_refs") or ()
                if str(ref) not in method_gap_refs
            ],
        }
        for binding in projected_catalog.get("workpaper_gap_bindings") or ()
    ]
    projected_catalog["authority_boundary"] = {
        **deepcopy(dict(projected_catalog.get("authority_boundary") or {})),
        "research_method_parameters_are_customer_information_gaps": False,
        "source_catalog_mutated": False,
    }
    projected_catalog["source_authority_catalog_digest"] = catalog_digest
    projected_catalog.pop("authority_catalog_digest", None)
    projected_catalog["authority_catalog_digest"] = canonical_digest(
        projected_catalog
    )

    visible_evaluation = deepcopy(
        dict(supersession.get("writer_visible_evaluation") or {})
    )
    method_evaluation_findings: list[dict[str, Any]] = []
    writer_findings: list[dict[str, Any]] = []
    for raw in visible_evaluation.get("findings") or ():
        finding = deepcopy(dict(raw))
        if str(finding.get("finding_code") or "") in method_finding_codes:
            finding_gap_refs = {
                str(ref)
                for ref in finding.get("evidence_refs") or ()
                if str(ref).startswith("GAP::")
            }
            _require(
                finding_gap_refs and finding_gap_refs.issubset(method_gap_refs),
                "writer_projection_method_finding_scope_invalid",
            )
            method_evaluation_findings.append(finding)
        else:
            writer_findings.append(finding)
    visible_evaluation["findings"] = writer_findings
    visible_evaluation["report_may_proceed"] = not any(
        bool(row.get("blocks_report")) for row in writer_findings
    )
    visible_evaluation.pop("evaluation_digest", None)
    visible_evaluation["evaluation_digest"] = canonical_digest(visible_evaluation)
    _require(
        visible_evaluation.get("report_may_proceed") is True
        and str(visible_evaluation.get("evaluation_digest") or ""),
        "writer_projection_visible_evaluation_invalid",
    )
    body = {
        "schema_version": WRITER_SUCCESSOR_INPUT_PROJECTION_SCHEMA_VERSION,
        "status": "writer_input_refreshed_without_rewriting_research_artifacts",
        "source_authority_catalog_digest": catalog_digest,
        "source_workpaper_digests": sorted(
            str(row.get("workpaper_digest") or "") for row in workpapers
        ),
        "source_evaluation_digest": supersession.get("source_evaluation_digest"),
        "evaluation_supersession_view_digest": supersession_digest,
        "research_method_parameter_register_digest": method_digest,
        "writer_visible_workpapers": projected_workpapers,
        "workpaper_projection_receipts": workpaper_projection_receipts,
        "writer_visible_evaluation": visible_evaluation,
        "writer_visible_authority_catalog": projected_catalog,
        "research_method_parameters": deepcopy(method_register["parameters"]),
        "research_method_evaluation_findings": method_evaluation_findings,
        "omitted_method_gap_refs_by_agent": removed_by_agent,
        "summary": {
            "source_workpaper_count": len(projected_workpapers),
            "superseded_evaluation_finding_count": len(
                supersession.get("superseded_findings") or ()
            ),
            "omitted_research_method_gap_count": len(method_gap_refs),
            "omitted_research_method_evaluation_finding_count": len(
                method_evaluation_findings
            ),
            "omitted_research_method_claim_count": len(method_claim_refs),
            "writer_visible_gap_count": len(projected_catalog["gap_authority"]),
            "agent_re_adjudication_required": False,
        },
        "authority": {
            "original_workpapers_immutable": True,
            "original_evaluation_immutable": True,
            "original_authority_catalog_immutable": True,
            "binding_only_refresh_is_not_new_research": True,
            "semantic_evidence_change_requires_affected_unit_re_adjudication": True,
        },
    }
    return {**body, "projection_digest": canonical_digest(body)}


__all__ = [
    "EVALUATION_AUTHORITY_SUPERSESSION_SCHEMA_VERSION",
    "REPORT_BOUNDARY_DISPOSITION_SCHEMA_VERSION",
    "RESEARCH_METHOD_PARAMETER_REGISTER_SCHEMA_VERSION",
    "WRITER_SUCCESSOR_INPUT_PROJECTION_SCHEMA_VERSION",
    "ReportBoundaryDispositionError",
    "compile_evaluation_authority_supersession_view",
    "compile_research_method_parameter_register",
    "compile_report_boundary_disposition_register",
    "compile_writer_successor_input_projection",
    "validate_report_boundary_disposition_register",
]
