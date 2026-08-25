from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from .query_plan import canonical_digest


POLICY_SCHEMA_VERSION = "fin_ia_dell_report_residual_source_policy_v1_0"
PROGRAM_SCHEMA_VERSION = "fin_ia_dell_report_residual_source_ladder_program_v1_0"

ROUTE_FAMILY_IDS = {
    "local_data_object_index_sql",
    "official_issuer_regulator",
    "named_customer",
    "named_supplier",
    "industry_primary",
    "product_procurement_deployment",
    "trusted_context_counter",
}


class DellReportResidualSourceProgramError(ValueError):
    """Raised when the report-material residual route program is not bounded."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DellReportResidualSourceProgramError(code)


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
    result: dict[str, dict[str, Any]] = {}
    for raw in rows:
        row = dict(raw)
        key = str(row.get(field) or "")
        _require(key and key not in result, code)
        result[key] = row
    return result


def _validate_self_digest(payload: Mapping[str, Any], field: str, code: str) -> None:
    body = {key: value for key, value in payload.items() if key != field}
    _require(canonical_digest(body) == payload.get(field), code)


def validate_dell_report_residual_source_policy(
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    parsed = dict(policy)
    _require(
        parsed.get("schema_version") == POLICY_SCHEMA_VERSION,
        "dell_report_residual_policy_schema_invalid",
    )
    _validate_self_digest(
        parsed,
        "policy_digest",
        "dell_report_residual_policy_digest_invalid",
    )
    expected = _mapping(
        parsed.get("expected_counts"),
        "dell_report_residual_expected_counts_missing",
    )
    _require(
        expected
        == {
            "crosswalk_pack_gap_count": 14,
            "pack_gap_acquisition_target_count": 8,
            "independent_S2_acquisition_target_count": 1,
            "total_acquisition_target_count": 9,
            "currently_unoverlapped_target_count": 6,
            "admission_held_target_count": 3,
            "non_acquisition_pack_gap_count": 6,
            "route_family_count": 7,
            "compiled_route_contract_count": 63,
        },
        "dell_report_residual_expected_counts_invalid",
    )
    route_policies = _unique_by(
        (
            _mapping(row, "dell_report_residual_route_policy_invalid")
            for row in _sequence(
                parsed.get("route_family_policies"),
                "dell_report_residual_route_policies_invalid",
            )
        ),
        "route_family_id",
        code="dell_report_residual_route_policy_duplicate",
    )
    _require(
        set(route_policies) == ROUTE_FAMILY_IDS,
        "dell_report_residual_route_family_set_invalid",
    )
    for route_id, route in route_policies.items():
        _require(
            isinstance(route.get("max_attempts"), int)
            and 0 < route["max_attempts"] <= 3,
            f"dell_report_residual_route_attempt_budget_invalid:{route_id}",
        )
        for field in ("capture_policy", "fallback", "stop_condition", "source_role"):
            _require(
                bool(str(route.get(field) or "").strip()),
                f"dell_report_residual_route_field_missing:{route_id}:{field}",
            )
    targets = _unique_by(
        (
            _mapping(row, "dell_report_residual_target_invalid")
            for row in _sequence(
                parsed.get("target_policies"),
                "dell_report_residual_targets_invalid",
            )
        ),
        "target_id",
        code="dell_report_residual_target_duplicate",
    )
    _require(
        len(targets) == 9,
        "dell_report_residual_target_count_invalid",
    )
    pack_gap_ids = [str(target.get("pack_gap_id") or "") for target in targets.values()]
    _require(
        sum(bool(gap_id) for gap_id in pack_gap_ids) == 8
        and len({gap_id for gap_id in pack_gap_ids if gap_id}) == 8,
        "dell_report_residual_pack_target_set_invalid",
    )
    independent = [
        target
        for target in targets.values()
        if target.get("independent_S2_bridge_gap_id")
    ]
    _require(
        len(independent) == 1
        and independent[0]["independent_S2_bridge_gap_id"]
        == "dell-gap-product-profit-attribution",
        "dell_report_residual_independent_S2_target_invalid",
    )
    for target_id, target in targets.items():
        for field in (
            "target_proposition",
            "subject",
            "owner_scope",
            "time_scope",
            "desired_evidence_role",
            "forbidden_inference",
            "prior_proposition_id",
        ):
            _require(
                bool(str(target.get(field) or "").strip()),
                f"dell_report_residual_target_field_missing:{target_id}:{field}",
            )
        query_terms = [str(item) for item in target.get("query_terms") or []]
        _require(
            len(query_terms) >= 3 and len(query_terms) == len(set(query_terms)),
            f"dell_report_residual_query_terms_invalid:{target_id}",
        )
        mandatory = set(str(item) for item in target.get("mandatory_route_families") or [])
        _require(
            {"local_data_object_index_sql", "official_issuer_regulator"}.issubset(
                mandatory
            )
            and mandatory.issubset(ROUTE_FAMILY_IDS),
            f"dell_report_residual_mandatory_routes_invalid:{target_id}",
        )
        owners = _mapping(
            target.get("route_owner_terms"),
            f"dell_report_residual_route_owner_terms_missing:{target_id}",
        )
        _require(
            set(owners) == ROUTE_FAMILY_IDS
            and all(str(value).strip() for value in owners.values()),
            f"dell_report_residual_route_owner_terms_invalid:{target_id}",
        )
    non_acquisition = _mapping(
        parsed.get("non_acquisition_pack_gap_policies"),
        "dell_report_residual_non_acquisition_policies_missing",
    )
    _require(
        len(non_acquisition) == 6
        and not (set(non_acquisition) & {gap for gap in pack_gap_ids if gap}),
        "dell_report_residual_non_acquisition_set_invalid",
    )
    return parsed


def _validate_input_bindings(
    *,
    policy: Mapping[str, Any],
    payloads: Mapping[str, Mapping[str, Any]],
    sha256_by_ref: Mapping[str, str],
) -> None:
    bindings = _mapping(
        policy.get("input_bindings"),
        "dell_report_residual_input_bindings_missing",
    )
    required = {
        "G1_independent_audit",
        "G1_crosswalk_public",
        "G1_crosswalk_private",
        "admission_02A_program",
        "prior_ladder_spec",
        "prior_ladder_result",
        "immutable_execution_program",
    }
    _require(
        set(bindings) == required,
        "dell_report_residual_input_binding_set_invalid",
    )
    for name, raw_binding in bindings.items():
        binding = _mapping(
            raw_binding,
            f"dell_report_residual_input_binding_invalid:{name}",
        )
        ref = str(binding.get("ref") or "")
        _require(
            sha256_by_ref.get(ref) == binding.get("sha256"),
            f"dell_report_residual_input_sha256_mismatch:{name}",
        )
        digest_field = binding.get("digest_field")
        if digest_field is None:
            continue
        payload = _mapping(
            payloads.get(name),
            f"dell_report_residual_input_payload_missing:{name}",
        )
        _require(
            payload.get(str(digest_field)) == binding.get("digest"),
            f"dell_report_residual_input_digest_mismatch:{name}",
        )


def _compile_route(
    *,
    target: Mapping[str, Any],
    route: Mapping[str, Any],
    currently_held: bool,
) -> dict[str, Any]:
    target_id = str(target["target_id"])
    route_id = str(route["route_family_id"])
    owner_terms = str(target["route_owner_terms"][route_id])
    query_text = " ".join(
        [
            owner_terms,
            *[str(term) for term in target["query_terms"]],
            str(target["time_scope"]),
        ]
    )
    lowered = query_text.casefold()
    _require(
        "http://" not in lowered
        and "https://" not in lowered
        and "qrel" not in lowered
        and "answer_url" not in lowered,
        f"dell_report_residual_query_leaks_answer:{target_id}:{route_id}",
    )
    query_contract = {
        "target_proposition": target["target_proposition"],
        "subject": target["subject"],
        "owner_scope": target["owner_scope"],
        "time_scope": target["time_scope"],
        "source_role": route["source_role"],
        "forbidden_inference": target["forbidden_inference"],
        "locator_query_template": query_text,
        "answer_URL_or_qrel_seeded": False,
    }
    body: dict[str, Any] = {
        "route_contract_id": f"{target_id}::{route_id}",
        "target_id": target_id,
        "route_family_id": route_id,
        "mandatory_for_target": route_id in target["mandatory_route_families"],
        "max_attempts": route["max_attempts"],
        "capture_policy": route["capture_policy"],
        "fallback": route["fallback"],
        "stop_condition": route["stop_condition"],
        "query_contract": query_contract,
        "current_execution_state": (
            "held_by_qualified_human_admission"
            if currently_held
            else "planned_not_authorized"
        ),
        "network_execution_authorized": False,
        "provider_execution_authorized": False,
    }
    return {**body, "route_contract_digest": canonical_digest(body)}


def compile_dell_report_residual_source_program(
    *,
    policy: Mapping[str, Any],
    input_payloads: Mapping[str, Mapping[str, Any]],
    input_sha256_by_ref: Mapping[str, str],
    admission_manifest: Mapping[str, Any],
    admission_manifest_ref: str,
    admission_manifest_sha256: str,
    recorded_at: str,
    prepared_from_commit: str,
) -> dict[str, Any]:
    """Compile the zero-call residual route manifest after 02A packet freeze."""

    parsed_policy = validate_dell_report_residual_source_policy(policy)
    _validate_input_bindings(
        policy=parsed_policy,
        payloads=input_payloads,
        sha256_by_ref=input_sha256_by_ref,
    )
    audit = _mapping(
        input_payloads.get("G1_independent_audit"),
        "dell_report_residual_G1_audit_missing",
    )
    _require(
        bool(_mapping(audit.get("verdicts"), "dell_report_residual_G1_verdicts_missing").get("G1_crosswalk_pass")),
        "dell_report_residual_G1_not_passed",
    )
    crosswalk_public = _mapping(
        input_payloads.get("G1_crosswalk_public"),
        "dell_report_residual_crosswalk_public_missing",
    )
    crosswalk_private = _mapping(
        input_payloads.get("G1_crosswalk_private"),
        "dell_report_residual_crosswalk_private_missing",
    )
    content_digest = str(crosswalk_private.get("crosswalk_content_digest") or "")
    _require(
        content_digest
        and content_digest == crosswalk_public.get("crosswalk_content_digest")
        and content_digest
        == audit.get("reviewed_artifacts", {}).get("crosswalk_content_digest"),
        "dell_report_residual_crosswalk_content_binding_mismatch",
    )
    audit_projection = _mapping(
        crosswalk_private.get("audit_projection"),
        "dell_report_residual_crosswalk_audit_projection_missing",
    )
    pack_gaps = _unique_by(
        (
            _mapping(row, "dell_report_residual_crosswalk_gap_invalid")
            for row in _sequence(
                audit_projection.get("pack_gap_entries"),
                "dell_report_residual_crosswalk_gaps_invalid",
            )
        ),
        "gap_id",
        code="dell_report_residual_crosswalk_gap_duplicate",
    )
    _require(
        len(pack_gaps) == 14,
        "dell_report_residual_crosswalk_gap_count_invalid",
    )
    admission_program = _mapping(
        input_payloads.get("admission_02A_program"),
        "dell_report_residual_admission_program_missing",
    )
    admission = dict(admission_manifest)
    _validate_self_digest(
        admission,
        "result_digest",
        "dell_report_residual_admission_manifest_digest_invalid",
    )
    _require(
        admission.get("program_digest") == admission_program.get("program_digest")
        and admission.get("admission_packet_digest")
        and len(admission_manifest_sha256) == 64
        and admission.get("status")
        == "packet_frozen_qualified_human_decisions_pending",
        "dell_report_residual_admission_manifest_binding_invalid",
    )
    admission_counts = _mapping(
        admission.get("counts"),
        "dell_report_residual_admission_counts_missing",
    )
    _require(
        admission_counts.get("all_human_required_item_count") == 16
        and admission_counts.get("blocked_request_human_item_count") == 8
        and admission_counts.get("qualified_human_decision_count") == 0
        and admission.get("authority", {}).get("G2_pass") is False,
        "dell_report_residual_admission_state_invalid",
    )
    admission_request_ids = {
        str(policy_row.get("review_item_ref")): str(policy_row.get("request_id") or "")
        for policy_row in admission.get("items") or []
    }
    manifest_request_ids = {
        str(row.get("request_id") or "") for row in admission.get("items") or []
    }
    _require(
        len(admission_request_ids) == 16 and len(manifest_request_ids) == 8,
        "dell_report_residual_admission_manifest_item_set_invalid",
    )
    prior_spec = _mapping(
        input_payloads.get("prior_ladder_spec"),
        "dell_report_residual_prior_spec_missing",
    )
    prior_result = _mapping(
        input_payloads.get("prior_ladder_result"),
        "dell_report_residual_prior_result_missing",
    )
    _require(
        prior_result.get("provider", {}).get("fresh_provider_query_count") == 22
        and prior_result.get("status")
        == "dell_external_ladder_successor_executed_candidate_decision_pending",
        "dell_report_residual_prior_execution_state_invalid",
    )
    prior_by_proposition = _unique_by(
        (
            _mapping(row, "dell_report_residual_prior_proposition_invalid")
            for row in prior_result.get("propositions") or []
        ),
        "proposition_id",
        code="dell_report_residual_prior_proposition_duplicate",
    )
    prior_spec_propositions = {
        str(row.get("proposition_id") or "")
        for row in prior_spec.get("new_query_units") or []
    }
    _require(
        prior_spec_propositions
        == {
            "DELL-PROP-PRICE-CONFIGURATION",
            "DELL-PROP-SUPPLY-CHAIN",
            "DELL-PROP-UNIT-VOLUME",
        }
        and prior_spec_propositions.issubset(prior_by_proposition),
        "dell_report_residual_prior_spec_result_propositions_mismatch",
    )

    route_policy_by_id = _unique_by(
        parsed_policy["route_family_policies"],
        "route_family_id",
        code="dell_report_residual_route_policy_duplicate",
    )
    target_by_id = _unique_by(
        parsed_policy["target_policies"],
        "target_id",
        code="dell_report_residual_target_duplicate",
    )
    route_targets: list[dict[str, Any]] = []
    pack_target_by_gap: dict[str, str] = {}
    held_count = 0
    unoverlapped_count = 0
    for target_id in sorted(target_by_id):
        target = target_by_id[target_id]
        pack_gap_id = str(target.get("pack_gap_id") or "")
        if pack_gap_id:
            _require(
                pack_gap_id in pack_gaps
                and pack_gaps[pack_gap_id].get("research_disposition")
                == target.get("expected_crosswalk_disposition"),
                f"dell_report_residual_target_crosswalk_mismatch:{target_id}",
            )
            pack_target_by_gap[pack_gap_id] = target_id
        overlaps = sorted(
            str(item) for item in target.get("admission_overlap_request_ids") or []
        )
        _require(
            set(overlaps).issubset(manifest_request_ids),
            f"dell_report_residual_admission_overlap_unknown:{target_id}",
        )
        currently_held = bool(overlaps)
        if currently_held:
            held_count += 1
        else:
            unoverlapped_count += 1
        prior_id = str(target["prior_proposition_id"])
        _require(
            prior_id in prior_by_proposition,
            f"dell_report_residual_prior_proposition_missing:{target_id}",
        )
        route_contracts = [
            _compile_route(
                target=target,
                route=route_policy_by_id[route_id],
                currently_held=currently_held,
            )
            for route_id in sorted(route_policy_by_id)
        ]
        target_body: dict[str, Any] = {
            "target_id": target_id,
            "pack_gap_id": target.get("pack_gap_id"),
            "independent_S2_bridge_gap_id": target.get(
                "independent_S2_bridge_gap_id"
            ),
            "report_placement": target["report_placement"],
            "target_proposition": target["target_proposition"],
            "admission_overlap_request_ids": overlaps,
            "current_route_state": (
                "held_by_qualified_human_admission"
                if currently_held
                else "planned_for_03B_internal_chain_then_bounded_03C_if_needed"
            ),
            "predecessor_ladder": {
                "prior_proposition_id": prior_id,
                "prior_query_count": prior_by_proposition[prior_id]["query_count"],
                "prior_captured_original_count": prior_by_proposition[prior_id][
                    "captured_original_count"
                ],
                "prior_compiled_source_object_count": prior_by_proposition[prior_id][
                    "compiled_source_object_count"
                ],
                "prior_candidate_proposal_count": prior_by_proposition[prior_id][
                    "candidate_proposal_count"
                ],
                "reconcile_before_any_new_locator_call": True,
                "repeat_predecessor_query_forbidden": True,
            },
            "route_contracts": route_contracts,
            "max_attempts_total_if_later_authorized": sum(
                route["max_attempts"] for route in route_contracts
            ),
            "current_network_authority": False,
            "current_provider_authority": False,
        }
        route_targets.append(
            {**target_body, "target_program_digest": canonical_digest(target_body)}
        )
    _require(
        held_count == 3 and unoverlapped_count == 6,
        "dell_report_residual_admission_partition_invalid",
    )
    non_acquisition = parsed_policy["non_acquisition_pack_gap_policies"]
    _require(
        set(pack_target_by_gap) | set(non_acquisition) == set(pack_gaps)
        and not (set(pack_target_by_gap) & set(non_acquisition)),
        "dell_report_residual_crosswalk_gap_partition_invalid",
    )
    gap_register: list[dict[str, Any]] = []
    for gap_id in sorted(pack_gaps):
        gap = pack_gaps[gap_id]
        if gap_id in pack_target_by_gap:
            target_id = pack_target_by_gap[gap_id]
            target_program = next(
                row for row in route_targets if row["target_id"] == target_id
            )
            disposition = {
                "program_disposition": "acquisition_route_manifest",
                "target_id": target_id,
                "current_route_state": target_program["current_route_state"],
                "execution_eligible_now": False,
            }
        else:
            policy_row = _mapping(
                non_acquisition[gap_id],
                f"dell_report_residual_non_acquisition_policy_invalid:{gap_id}",
            )
            _require(
                gap.get("research_disposition")
                == policy_row.get("expected_crosswalk_disposition"),
                f"dell_report_residual_non_acquisition_crosswalk_mismatch:{gap_id}",
            )
            disposition = {
                "program_disposition": policy_row["program_disposition"],
                "target_id": None,
                "current_route_state": policy_row["current_route_state"],
                "execution_eligible_now": False,
            }
        gap_register.append(
            {
                "gap_id": gap_id,
                "crosswalk_research_disposition": gap["research_disposition"],
                "stage_owner": gap["stage_owner"],
                "report_placement": gap["report_placement"],
                **disposition,
            }
        )
    gap_register.append(
        {
            "gap_id": "dell-gap-product-profit-attribution",
            "crosswalk_research_disposition": "independent_S2_bridge_gap",
            "stage_owner": "S1_S2_boundary",
            "report_placement": "pricing_mix_and_value_capture",
            "program_disposition": "acquisition_route_manifest",
            "target_id": "DELL-RSQ-03A-TARGET-PRODUCT-PROFIT",
            "current_route_state": "held_by_qualified_human_admission",
            "execution_eligible_now": False,
        }
    )
    expected = parsed_policy["expected_counts"]
    counts = {
        "crosswalk_pack_gap_count": len(pack_gaps),
        "pack_gap_acquisition_target_count": len(pack_target_by_gap),
        "independent_S2_acquisition_target_count": 1,
        "total_acquisition_target_count": len(route_targets),
        "currently_unoverlapped_target_count": unoverlapped_count,
        "admission_held_target_count": held_count,
        "non_acquisition_pack_gap_count": len(non_acquisition),
        "route_family_count": len(route_policy_by_id),
        "compiled_route_contract_count": sum(
            len(target["route_contracts"]) for target in route_targets
        ),
    }
    _require(counts == expected, "dell_report_residual_compiled_counts_invalid")
    dynamic_admission_binding = {
        "ref": admission_manifest_ref,
        "sha256": admission_manifest_sha256,
        "digest_field": "result_digest",
        "digest": admission.get("result_digest"),
        "admission_packet_digest": admission.get("admission_packet_digest"),
    }
    body: dict[str, Any] = {
        "schema_version": PROGRAM_SCHEMA_VERSION,
        "program_id": "FIN-0.1.3-S1-DELL-RSQ-03A",
        "status": "route_manifest_frozen_zero_call_execution_not_authorized",
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "case_key": "DELL",
        "research_as_of": "2026-08-06",
        "policy_digest": parsed_policy["policy_digest"],
        "input_bindings": parsed_policy["input_bindings"],
        "admission_02A_manifest_binding": dynamic_admission_binding,
        "crosswalk_content_digest": content_digest,
        "counts": counts,
        "gap_disposition_register": gap_register,
        "route_family_registry": [
            route_policy_by_id[route_id] for route_id in sorted(route_policy_by_id)
        ],
        "route_targets": route_targets,
        "prior_ladder_reconciliation": {
            "prior_spec_digest": prior_spec["spec_digest"],
            "prior_result_digest": prior_result["result_digest"],
            "fresh_provider_query_count_already_spent": 22,
            "candidate_decision_pending": True,
            "repeat_old_query_units_as_fresh_calls": False,
            "new_route_requires_proved_uncovered_residual": True,
        },
        "mixed_retrieval_and_ranking_dependency": parsed_policy[
            "mixed_retrieval_and_ranking_dependency"
        ],
        "execution": {
            "network_calls": 0,
            "provider_calls": 0,
            "model_calls": 0,
            "embedding_calls": 0,
            "reranker_calls": 0,
            "captures": 0,
            "candidate_promotions": 0,
            "evidence_promotions": 0,
            "gap_closures": 0,
        },
        "authority": {
            "03A_route_program_frozen": True,
            "03B_internal_chain_execution_authorized": False,
            "03C_external_capture_execution_authorized": False,
            "03D_embedding_challenger_authorized": False,
            "03D_reranker_authorized": False,
            "candidate_decision_authorized": False,
            "evidence_promotion_authorized": False,
            "proved_information_boundary_authorized": False,
            "G3_pass": False,
            "S1_pass": False,
            "report_quality_pass": False,
            "product_acceptance": False,
            "publication": False,
            "release_ready": False,
        },
        "known_boundary": (
            "This is a zero-call route program. It reconciles the prior 22 fresh "
            "provider queries, holds three propositions that overlap undecided "
            "qualified-human admission, and authorizes no retrieval, model, "
            "candidate promotion, Evidence promotion, gap closure or report claim."
        ),
    }
    return {**body, "program_digest": canonical_digest(body)}


__all__ = [
    "DellReportResidualSourceProgramError",
    "POLICY_SCHEMA_VERSION",
    "PROGRAM_SCHEMA_VERSION",
    "ROUTE_FAMILY_IDS",
    "compile_dell_report_residual_source_program",
    "validate_dell_report_residual_source_policy",
]
