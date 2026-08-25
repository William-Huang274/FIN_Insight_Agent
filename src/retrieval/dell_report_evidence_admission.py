from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from .query_plan import canonical_digest


PROGRAM_SCHEMA_VERSION = "fin_ia_dell_report_evidence_admission_program_v1_0"
PRIVATE_PACKET_SCHEMA_VERSION = (
    "fin_ia_dell_report_evidence_admission_private_packet_v1_0"
)
PUBLIC_MANIFEST_SCHEMA_VERSION = (
    "fin_ia_dell_report_evidence_admission_public_manifest_v1_0"
)


class DellReportEvidenceAdmissionError(ValueError):
    """Raised when the DELL report-use admission packet loses identity or scope."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DellReportEvidenceAdmissionError(code)


def _mapping(value: Any, code: str) -> dict[str, Any]:
    _require(isinstance(value, Mapping), code)
    return dict(value)


def _sequence(value: Any, code: str) -> list[Any]:
    _require(
        isinstance(value, Sequence) and not isinstance(value, (str, bytes)),
        code,
    )
    return list(value)


def _unique_by(
    rows: Iterable[Mapping[str, Any]], field: str, *, code: str
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for raw in rows:
        row = dict(raw)
        key = str(row.get(field) or "")
        _require(key and key not in indexed, code)
        indexed[key] = row
    return indexed


def _validate_self_digest(payload: Mapping[str, Any], field: str, code: str) -> None:
    body = {key: value for key, value in payload.items() if key != field}
    _require(canonical_digest(body) == payload.get(field), code)


def validate_dell_report_evidence_admission_program(
    program: Mapping[str, Any],
) -> dict[str, Any]:
    parsed = dict(program)
    _require(
        parsed.get("schema_version") == PROGRAM_SCHEMA_VERSION,
        "dell_report_admission_program_schema_invalid",
    )
    _validate_self_digest(
        parsed,
        "program_digest",
        "dell_report_admission_program_digest_invalid",
    )
    expected = _mapping(
        parsed.get("expected_scope"),
        "dell_report_admission_expected_scope_missing",
    )
    _require(
        expected
        == {
            "request_count": 8,
            "candidate_review_item_count": 18,
            "all_human_required_item_count": 16,
            "blocked_request_count": 4,
            "blocked_request_human_item_count": 8,
        },
        "dell_report_admission_expected_scope_invalid",
    )
    blocked = _sequence(
        parsed.get("readiness_blocker_request_ids"),
        "dell_report_admission_blocker_requests_invalid",
    )
    _require(
        len(blocked) == 4 and len(set(str(item) for item in blocked)) == 4,
        "dell_report_admission_blocker_request_count_invalid",
    )
    policies = _sequence(
        parsed.get("item_claim_use_policies"),
        "dell_report_admission_claim_use_policies_invalid",
    )
    policy_by_ref = _unique_by(
        (_mapping(row, "dell_report_admission_claim_use_policy_invalid") for row in policies),
        "review_item_ref",
        code="dell_report_admission_claim_use_policy_duplicate",
    )
    _require(
        len(policy_by_ref) == 16,
        "dell_report_admission_claim_use_policy_count_invalid",
    )
    allowed_effects = {
        "support_if_admitted",
        "limit_if_admitted",
        "support_and_limit_if_admitted",
        "context_only_or_reject_if_no_material_use",
    }
    for ref, policy in policy_by_ref.items():
        _require(
            len(str(policy.get("review_item_digest") or "")) == 64,
            f"dell_report_admission_policy_item_digest_invalid:{ref}",
        )
        _require(
            policy.get("proposed_report_effect") in allowed_effects,
            f"dell_report_admission_policy_effect_invalid:{ref}",
        )
        claim_refs = [str(item) for item in policy.get("report_claim_refs") or []]
        _require(
            claim_refs and len(claim_refs) == len(set(claim_refs)),
            f"dell_report_admission_policy_claim_refs_invalid:{ref}",
        )
        _require(
            bool(str(policy.get("alignment_hypothesis") or "").strip())
            and bool(str(policy.get("forbidden_inference") or "").strip()),
            f"dell_report_admission_policy_quality_fields_missing:{ref}",
        )
    return parsed


def _validate_input_bindings(
    *,
    program: Mapping[str, Any],
    payloads: Mapping[str, Mapping[str, Any]],
    sha256_by_ref: Mapping[str, str],
) -> None:
    bindings = _mapping(
        program.get("input_bindings"),
        "dell_report_admission_input_bindings_missing",
    )
    required = {
        "G1_independent_audit",
        "G1_crosswalk_public",
        "current_readiness_public",
        "current_readiness_private",
        "R17_private_report",
        "immutable_execution_program",
    }
    _require(
        set(bindings) == required,
        "dell_report_admission_input_binding_set_invalid",
    )
    for name, raw_binding in bindings.items():
        binding = _mapping(
            raw_binding,
            f"dell_report_admission_input_binding_invalid:{name}",
        )
        ref = str(binding.get("ref") or "")
        _require(
            sha256_by_ref.get(ref) == binding.get("sha256"),
            f"dell_report_admission_input_sha256_mismatch:{name}",
        )
        digest_field = binding.get("digest_field")
        if digest_field is None:
            continue
        payload = _mapping(
            payloads.get(name),
            f"dell_report_admission_input_payload_missing:{name}",
        )
        _require(
            payload.get(str(digest_field)) == binding.get("digest"),
            f"dell_report_admission_input_digest_mismatch:{name}",
        )


def _collect_report_claim_refs(value: Any) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key == "source_claim_refs":
                if isinstance(item, str):
                    refs.add(item)
                elif isinstance(item, Sequence):
                    refs.update(str(ref) for ref in item if str(ref))
            else:
                refs.update(_collect_report_claim_refs(item))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for item in value:
            refs.update(_collect_report_claim_refs(item))
    return refs


def _citation_right(source: Mapping[str, Any]) -> dict[str, Any]:
    license_scope = str(source.get("license_scope") or "")
    _require(
        license_scope.startswith("public"),
        "dell_report_admission_source_license_not_public",
    )
    redistributable = bool(source.get("redistributable"))
    return {
        "license_scope": license_scope,
        "citation_locator_allowed": True,
        "bounded_quote_review_allowed": True,
        "full_text_redistribution_allowed": redistributable,
        "public_artifact_excerpt_allowed": False,
        "required_publication_surface": [
            "publisher_or_owner",
            "title_or_source_type",
            "publication_date",
            "period",
            "section_or_table",
            "locator",
        ],
    }


def _compile_item(
    *,
    item: Mapping[str, Any],
    request: Mapping[str, Any],
    policy: Mapping[str, Any],
    readiness_state: str,
    in_blocker_subset: bool,
) -> dict[str, Any]:
    ref = str(item.get("review_item_ref") or "")
    _validate_self_digest(
        item,
        "review_item_digest",
        f"dell_report_admission_predecessor_item_digest_invalid:{ref}",
    )
    _require(
        item.get("review_item_digest") == policy.get("review_item_digest"),
        f"dell_report_admission_policy_item_digest_mismatch:{ref}",
    )
    _require(
        item.get("human_review_required") is True
        and item.get("decision_state") == "needs_human_review",
        f"dell_report_admission_item_not_human_pending:{ref}",
    )
    _require(
        item.get("candidate_is_not_evidence") is True
        and item.get("candidate_text_promoted") is False
        and item.get("new_evidence_created") is False,
        f"dell_report_admission_candidate_authority_invalid:{ref}",
    )
    role = _mapping(
        item.get("advisory_evidence_role"),
        f"dell_report_admission_advisory_role_missing:{ref}",
    )
    _require(
        role.get("advisory_only") is True,
        f"dell_report_admission_model_role_not_advisory:{ref}",
    )
    source = _mapping(
        item.get("source"),
        f"dell_report_admission_source_missing:{ref}",
    )
    excerpt = " ".join(str(source.get("bounded_excerpt") or "").split())
    _require(
        bool(excerpt) and len(excerpt) <= 1200,
        f"dell_report_admission_excerpt_invalid:{ref}",
    )
    _require(
        str(source.get("source_url") or "").startswith(("https://", "http://")),
        f"dell_report_admission_source_url_invalid:{ref}",
    )
    requirement_alignment = {
        "request_id": request["request_id"],
        "slot_id": request["slot_id"],
        "facet_id": request["facet_id"],
        "business_question_zh": request["business_question_zh"],
        "predecessor_requirement_contexts": list(
            item.get("requirement_contexts") or []
        ),
        "alignment_state": "qualified_human_validation_pending",
        "alignment_hypothesis": policy["alignment_hypothesis"],
        "forbidden_inference": policy["forbidden_inference"],
    }
    report_claim_use = {
        "proposed_report_effect": policy["proposed_report_effect"],
        "report_claim_refs": sorted(str(ref) for ref in policy["report_claim_refs"]),
        "material_report_use_required_for_acceptance": True,
        "citation_padding_forbidden": True,
        "qualified_human_may_reject_or_rebind": True,
        "decision_authority": "qualified_human_only",
    }
    source_identity = {
        "source_record_id": item["source_record_id"],
        "compiled_object_id": item["compiled_object_id"],
        "source_lineage_digest": item["source_lineage_digest"],
        "surface_digest": source["surface_digest"],
        "source_owner_ticker": item["evidence_owner_ticker"],
        "research_subject_ticker": item["subject_ticker"],
        "company": source.get("company"),
        "source_type": source.get("source_type"),
        "source_tier": source.get("source_tier"),
        "publication_date": source.get("publication_date"),
        "reporting_period_end": source.get("period_end"),
        "section": source.get("section"),
        "subsection": source.get("subsection"),
        "source_url": source.get("source_url"),
    }
    body: dict[str, Any] = {
        "review_item_ref": ref,
        "predecessor_review_item_digest": item["review_item_digest"],
        "request_id": request["request_id"],
        "readiness_state": readiness_state,
        "scope_membership": {
            "all_human_required_decision_set": True,
            "four_request_readiness_blocker_subset": in_blocker_subset,
        },
        "candidate_state": "candidate_not_evidence_qualified_human_pending",
        "source_identity": source_identity,
        "bounded_excerpt_private_review_only": excerpt,
        "citation_and_redistribution_rights": _citation_right(source),
        "retrieval_route": {
            "route_membership": sorted(str(route) for route in item.get("route_membership") or []),
            "rank_trace_advisory_only": dict(item.get("rank_trace") or {}),
            "rank_or_embedding_score_is_admission_reason": False,
        },
        "advisory_evidence_role": role,
        "requirement_alignment": requirement_alignment,
        "report_claim_use": report_claim_use,
        "numeric_authority": False,
        "evidence_promotion_authorized": False,
        "decision_prefilled": False,
    }
    return {**body, "packet_item_digest": canonical_digest(body)}


def compile_dell_report_evidence_admission_packet(
    *,
    program: Mapping[str, Any],
    input_payloads: Mapping[str, Mapping[str, Any]],
    input_sha256_by_ref: Mapping[str, str],
    private_output_ref: str,
    recorded_at: str,
    prepared_from_commit: str,
) -> dict[str, dict[str, Any]]:
    """Freeze DELL's sixteen human decisions without issuing any decision."""

    parsed_program = validate_dell_report_evidence_admission_program(program)
    _validate_input_bindings(
        program=parsed_program,
        payloads=input_payloads,
        sha256_by_ref=input_sha256_by_ref,
    )
    audit = _mapping(
        input_payloads.get("G1_independent_audit"),
        "dell_report_admission_G1_audit_missing",
    )
    _require(
        bool(_mapping(audit.get("verdicts"), "dell_report_admission_G1_verdicts_missing").get("G1_crosswalk_pass"))
        and bool(_mapping(audit.get("authority"), "dell_report_admission_G1_authority_missing").get("independent_crosswalk_G1_pass")),
        "dell_report_admission_G1_not_passed",
    )
    readiness_public = _mapping(
        input_payloads.get("current_readiness_public"),
        "dell_report_admission_readiness_public_missing",
    )
    readiness_private = _mapping(
        input_payloads.get("current_readiness_private"),
        "dell_report_admission_readiness_private_missing",
    )
    packet = _mapping(
        readiness_private.get("candidate_review_packet"),
        "dell_report_admission_predecessor_packet_missing",
    )
    _validate_self_digest(
        packet,
        "review_packet_digest",
        "dell_report_admission_predecessor_packet_digest_invalid",
    )
    expected = parsed_program["expected_scope"]
    _require(
        packet.get("request_count") == expected["request_count"]
        and packet.get("review_item_count") == expected["candidate_review_item_count"]
        and packet.get("human_review_required_count")
        == expected["all_human_required_item_count"],
        "dell_report_admission_predecessor_scope_counts_invalid",
    )
    public_request_by_id = _unique_by(
        (
            _mapping(row, "dell_report_admission_public_request_invalid")
            for row in _sequence(
                readiness_public.get("requests"),
                "dell_report_admission_public_requests_invalid",
            )
        ),
        "request_id",
        code="dell_report_admission_public_request_duplicate",
    )
    private_request_by_id = _unique_by(
        (
            _mapping(row, "dell_report_admission_private_request_invalid")
            for row in _sequence(
                packet.get("requests"),
                "dell_report_admission_private_requests_invalid",
            )
        ),
        "request_id",
        code="dell_report_admission_private_request_duplicate",
    )
    _require(
        set(public_request_by_id) == set(private_request_by_id),
        "dell_report_admission_request_sets_differ",
    )
    blocked_ids = set(str(item) for item in parsed_program["readiness_blocker_request_ids"])
    actual_blocked = {
        request_id
        for request_id, request in public_request_by_id.items()
        if request.get("readiness_state") == "blocked_by_evidence_admission"
    }
    _require(
        actual_blocked == blocked_ids,
        "dell_report_admission_blocker_request_set_mismatch",
    )
    policy_by_ref = _unique_by(
        parsed_program["item_claim_use_policies"],
        "review_item_ref",
        code="dell_report_admission_claim_use_policy_duplicate",
    )
    r17 = _mapping(
        input_payloads.get("R17_private_report"),
        "dell_report_admission_R17_missing",
    )
    report_claim_refs = _collect_report_claim_refs(r17.get("trusted_report"))
    _require(report_claim_refs, "dell_report_admission_R17_claim_refs_missing")

    requests: list[dict[str, Any]] = []
    all_refs: set[str] = set()
    all_digests: set[str] = set()
    blocker_item_count = 0
    for request_id in sorted(private_request_by_id):
        request = private_request_by_id[request_id]
        readiness_state = str(public_request_by_id[request_id].get("readiness_state") or "")
        in_blocker_subset = request_id in blocked_ids
        human_items = [
            _mapping(item, "dell_report_admission_review_item_invalid")
            for item in request.get("review_items") or []
            if _mapping(item, "dell_report_admission_review_item_invalid").get(
                "human_review_required"
            )
            is True
        ]
        _require(
            len(human_items) == request.get("human_review_required_count"),
            f"dell_report_admission_request_human_count_invalid:{request_id}",
        )
        compiled_items: list[dict[str, Any]] = []
        for item in human_items:
            ref = str(item.get("review_item_ref") or "")
            _require(
                ref not in all_refs and item.get("review_item_digest") not in all_digests,
                f"dell_report_admission_item_identity_duplicate:{ref}",
            )
            _require(
                ref in policy_by_ref,
                f"dell_report_admission_claim_use_policy_missing:{ref}",
            )
            policy_claims = set(
                str(claim_ref)
                for claim_ref in policy_by_ref[ref].get("report_claim_refs") or []
            )
            _require(
                policy_claims.issubset(report_claim_refs),
                f"dell_report_admission_unknown_R17_claim_ref:{ref}",
            )
            compiled_items.append(
                _compile_item(
                    item=item,
                    request=request,
                    policy=policy_by_ref[ref],
                    readiness_state=readiness_state,
                    in_blocker_subset=in_blocker_subset,
                )
            )
            all_refs.add(ref)
            all_digests.add(str(item["review_item_digest"]))
        if in_blocker_subset:
            blocker_item_count += len(compiled_items)
        request_body: dict[str, Any] = {
            "request_id": request_id,
            "readiness_state": readiness_state,
            "business_question_zh": request["business_question_zh"],
            "slot_id": request["slot_id"],
            "facet_id": request["facet_id"],
            "all_human_required_decision_set": True,
            "four_request_readiness_blocker_subset": in_blocker_subset,
            "human_item_count": len(compiled_items),
            "items": sorted(compiled_items, key=lambda row: row["review_item_ref"]),
        }
        requests.append(
            {**request_body, "request_packet_digest": canonical_digest(request_body)}
        )
    _require(
        len(all_refs) == expected["all_human_required_item_count"],
        "dell_report_admission_all_human_item_count_invalid",
    )
    _require(
        set(policy_by_ref) == all_refs,
        "dell_report_admission_policy_item_set_mismatch",
    )
    _require(
        blocker_item_count == expected["blocked_request_human_item_count"],
        "dell_report_admission_blocker_item_count_invalid",
    )

    decision_schema = {
        "decision_authority": "qualified_human_only",
        "allowed_decisions": [
            "accept_existing",
            "rebind",
            "accept_new",
            "reject",
            "defer",
        ],
        "required_fields": [
            "review_item_ref",
            "predecessor_review_item_digest",
            "decision",
            "reason",
            "evidence_role",
            "report_claim_use",
            "period",
            "polarity",
            "authority",
            "license_and_citation_right",
            "reviewer_identity",
            "reviewed_at",
        ],
        "accept_new_requires_exact_source_passage_and_evidence_gate": True,
        "defer_remains_blocking": True,
        "model_or_harness_generated_decision_forbidden": True,
    }
    scope_reconciliation = {
        "frozen_program_wording": "four_requests_sixteen_human_items",
        "actual_predecessor_scope": {
            "all_human_required_decision_set": {
                "request_count": 8,
                "human_item_count": 16,
                "required_for_G2": True,
            },
            "four_request_readiness_blocker_subset": {
                "request_count": 4,
                "human_item_count": 8,
                "request_ids": sorted(blocked_ids),
                "changes_four_blocked_readiness_states": True,
            },
        },
        "false_interpretation_rejected": "four_requests_each_with_four_human_items",
        "immutable_execution_program_rewritten": False,
    }
    packet_content: dict[str, Any] = {
        "case_key": "DELL",
        "research_as_of": "2026-08-06",
        "scope_reconciliation": scope_reconciliation,
        "qualified_human_decision_schema": decision_schema,
        "requests": requests,
    }
    admission_packet_digest = canonical_digest(packet_content)
    full_body: dict[str, Any] = {
        "schema_version": PRIVATE_PACKET_SCHEMA_VERSION,
        "status": "packet_frozen_qualified_human_decisions_pending",
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "program_digest": parsed_program["program_digest"],
        "input_bindings": parsed_program["input_bindings"],
        **packet_content,
        "admission_packet_digest": admission_packet_digest,
        "counts": {
            "request_count": len(requests),
            "all_human_required_item_count": len(all_refs),
            "blocked_request_count": len(blocked_ids),
            "blocked_request_human_item_count": blocker_item_count,
            "qualified_human_decision_count": 0,
        },
        "execution": {
            "network_calls": 0,
            "provider_calls": 0,
            "model_calls": 0,
            "embedding_calls": 0,
            "reranker_calls": 0,
            "candidate_promotions": 0,
            "evidence_promotions": 0,
        },
        "authority": {
            "qualified_human_decisions_complete": False,
            "G2_pass": False,
            "S1_pass": False,
            "S2_pass": False,
            "S3_pass": False,
            "report_quality_pass": False,
            "product_acceptance": False,
            "publication": False,
            "release_ready": False,
        },
        "known_boundary": (
            "This artifact freezes review work only. Every one of the sixteen "
            "human-required items still needs an authorized qualified-human "
            "decision. The eight-item blocker subset explains four current "
            "readiness blocks but does not replace the full G2 decision set."
        ),
    }
    full = {**full_body, "full_result_digest": canonical_digest(full_body)}
    public_items: list[dict[str, Any]] = []
    for request in requests:
        for item in request["items"]:
            public_items.append(
                {
                    "review_item_ref": item["review_item_ref"],
                    "predecessor_review_item_digest": item[
                        "predecessor_review_item_digest"
                    ],
                    "request_id": item["request_id"],
                    "four_request_readiness_blocker_subset": item[
                        "scope_membership"
                    ]["four_request_readiness_blocker_subset"],
                    "source_identity_digest": canonical_digest(
                        item["source_identity"]
                    ),
                    "report_claim_use": item["report_claim_use"],
                    "packet_item_digest": item["packet_item_digest"],
                    "decision_state": "qualified_human_pending",
                }
            )
    public_body: dict[str, Any] = {
        "schema_version": PUBLIC_MANIFEST_SCHEMA_VERSION,
        "status": "packet_frozen_qualified_human_decisions_pending",
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "case_key": "DELL",
        "research_as_of": "2026-08-06",
        "program_digest": parsed_program["program_digest"],
        "scope_reconciliation": scope_reconciliation,
        "counts": full["counts"],
        "items": sorted(public_items, key=lambda row: row["review_item_ref"]),
        "admission_packet_digest": admission_packet_digest,
        "private_full_result_ref": private_output_ref,
        "execution": full["execution"],
        "authority": full["authority"],
        "known_boundary": full["known_boundary"],
    }
    public = {**public_body, "result_digest": canonical_digest(public_body)}
    serialized_public = str(public).casefold()
    _require(
        "bounded_excerpt_private_review_only" not in serialized_public
        and "source_url" not in serialized_public,
        "dell_report_admission_public_projection_leaks_private_source",
    )
    return {"private": full, "public": public}


__all__ = [
    "DellReportEvidenceAdmissionError",
    "PRIVATE_PACKET_SCHEMA_VERSION",
    "PROGRAM_SCHEMA_VERSION",
    "PUBLIC_MANIFEST_SCHEMA_VERSION",
    "compile_dell_report_evidence_admission_packet",
    "validate_dell_report_evidence_admission_program",
]
