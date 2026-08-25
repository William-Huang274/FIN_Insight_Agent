from __future__ import annotations

import re
from typing import Any, Iterable, Mapping, Sequence

from .dell_report_evidence_admission import (
    EXPECTED_BLOCKED_REQUEST_IDS,
    EXPECTED_CLAIM_USE_SEMANTICS_BY_REF,
    EXPECTED_REVIEW_ITEM_INVENTORY_BY_REQUEST,
    PUBLIC_MANIFEST_SCHEMA_VERSION as ADMISSION_PUBLIC_MANIFEST_SCHEMA_VERSION,
)
from .query_plan import canonical_digest


POLICY_SCHEMA_VERSION = "fin_ia_dell_report_residual_source_policy_v1_1"
PROGRAM_SCHEMA_VERSION = "fin_ia_dell_report_residual_source_ladder_program_v1_1"

ROUTE_FAMILY_IDS = {
    "local_data_object_index_sql",
    "official_issuer_regulator",
    "named_customer",
    "named_supplier",
    "industry_primary",
    "product_procurement_deployment",
    "trusted_context_counter",
}

EXPECTED_POLICY_COMPONENT_DIGESTS = {
    "route_family_policies": "7650f1e54418d5b61220cb9322af6d272bc3c6959280ba23fddafeacb811793a",
    "target_policies": "af41b85eddb18554adcf287c474925970ee206edfae2120c0a771e1f1b2bbce1",
    "non_acquisition_pack_gap_policies": "aeb03d7aee6adb42f3539585b1acbfc850b6cd7e6b4508e8c36d9ae3f916438d",
    "mixed_retrieval_and_ranking_dependency": "dfdf89e17268350874517e67a4223b96f8dd587da6ecc8c0cf93f5f59a6f8bb5",
    "authority": "629c66380fadca736a47fdc26166c2a3312ae03d6d74438f852e706c1ddb95fc",
}

EXPECTED_TARGET_SEMANTICS_BY_ID = {
    "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE": {
        "pack_gap_id": "dell-gap-capacity-release-timing",
        "independent_S2_bridge_gap_id": None,
        "expected_crosswalk_disposition": "source_route_pending",
        "prior_proposition_id": "DELL-PROP-SUPPLY-CHAIN",
        "admission_overlap_request_ids": (),
    },
    "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD": {
        "pack_gap_id": "dell-gap-capacity-utilization-yield",
        "independent_S2_bridge_gap_id": None,
        "expected_crosswalk_disposition": "source_route_pending",
        "prior_proposition_id": "DELL-PROP-SUPPLY-CHAIN",
        "admission_overlap_request_ids": (),
    },
    "DELL-RSQ-03A-TARGET-DEMAND-DURABILITY": {
        "pack_gap_id": "dell-gap-demand-pull-forward-digestion",
        "independent_S2_bridge_gap_id": None,
        "expected_crosswalk_disposition": "source_route_pending",
        "prior_proposition_id": "DELL-PROP-CUSTOMER-DEMAND",
        "admission_overlap_request_ids": (
            "REQ::fb06661b946711fc3b334146",
            "REQ::eb2e808dd2e48b4fe7474223",
        ),
    },
    "DELL-RSQ-03A-TARGET-HBM-SUPPLY": {
        "pack_gap_id": "dell-gap-hbm-supply",
        "independent_S2_bridge_gap_id": None,
        "expected_crosswalk_disposition": "source_route_pending",
        "prior_proposition_id": "DELL-PROP-SUPPLY-CHAIN",
        "admission_overlap_request_ids": (),
    },
    "DELL-RSQ-03A-TARGET-ASP": {
        "pack_gap_id": "dell-gap-pricing-asp",
        "independent_S2_bridge_gap_id": None,
        "expected_crosswalk_disposition": "narrowed",
        "prior_proposition_id": "DELL-PROP-PRICE-CONFIGURATION",
        "admission_overlap_request_ids": (),
    },
    "DELL-RSQ-03A-TARGET-UNITS": {
        "pack_gap_id": "dell-gap-pricing-units",
        "independent_S2_bridge_gap_id": None,
        "expected_crosswalk_disposition": "narrowed",
        "prior_proposition_id": "DELL-PROP-UNIT-VOLUME",
        "admission_overlap_request_ids": (),
    },
    "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH": {
        "pack_gap_id": "dell-gap-supplier-capacity-readthrough",
        "independent_S2_bridge_gap_id": None,
        "expected_crosswalk_disposition": "narrowed",
        "prior_proposition_id": "DELL-PROP-SUPPLY-CHAIN",
        "admission_overlap_request_ids": (),
    },
    "DELL-RSQ-03A-TARGET-WORKING-CAPITAL": {
        "pack_gap_id": "dell-gap-ai-working-capital",
        "independent_S2_bridge_gap_id": None,
        "expected_crosswalk_disposition": "candidate_admission_pending",
        "prior_proposition_id": "DELL-PROP-COUNTEREVIDENCE-WWC",
        "admission_overlap_request_ids": (
            "REQ::c21c10d6e8f13263cf69ffa5",
        ),
    },
    "DELL-RSQ-03A-TARGET-PRODUCT-PROFIT": {
        "pack_gap_id": None,
        "independent_S2_bridge_gap_id": "dell-gap-product-profit-attribution",
        "expected_crosswalk_disposition": None,
        "prior_proposition_id": "DELL-PROP-VALUE-POOL",
        "admission_overlap_request_ids": (
            "REQ::081c06389f9dcb8487886b57",
        ),
    },
}

EXPECTED_HELD_TARGET_IDS = {
    "DELL-RSQ-03A-TARGET-DEMAND-DURABILITY",
    "DELL-RSQ-03A-TARGET-WORKING-CAPITAL",
    "DELL-RSQ-03A-TARGET-PRODUCT-PROFIT",
}

EXPECTED_PRIOR_PROPOSITION_COUNTS = {
    "DELL-PROP-COUNTEREVIDENCE-WWC": (4, 4, 2, 0),
    "DELL-PROP-CUSTOMER-DEMAND": (4, 8, 4, 5),
    "DELL-PROP-PRICE-CONFIGURATION": (10, 7, 1, 1),
    "DELL-PROP-PVM-BRIDGE": (4, 3, 3, 5),
    "DELL-PROP-SUPPLY-CHAIN": (14, 21, 2, 0),
    "DELL-PROP-UNIT-VOLUME": (10, 5, 2, 2),
    "DELL-PROP-VALUE-POOL": (4, 1, 1, 2),
}

EXPECTED_FRESH_QUERY_UNITS_BY_PROPOSITION = {
    "DELL-PROP-PRICE-CONFIGURATION": 6,
    "DELL-PROP-UNIT-VOLUME": 6,
    "DELL-PROP-SUPPLY-CHAIN": 10,
}

EXPECTED_INPUT_BINDINGS = {
    "G1_independent_audit": {
        "ref": "configs/audits/fin_ia_0_1_3_commit_7ba8bb2a_dell_rsq_r3_fresh_final_audit_pass_v1_0.json",
        "sha256": "9429d75f101097da5e48815e8a0fab8ffb8966a38c4f5dd499eb5df1c4b27189",
        "digest_field": "result_digest",
        "digest": "4f28008ea1a15a9813ec0ac22ec5e8219519de9c3195cf6b6928d0c6c1542dd4",
    },
    "G1_crosswalk_public": {
        "ref": "configs/research/evals/fin_ia_0_1_3_dell_report_gap_crosswalk_result_v1_2.json",
        "sha256": "990972fc1acb62696f0bebbc12713e100597271ec562424296cf8d220ff577f5",
        "digest_field": "result_digest",
        "digest": "afc37e760cd88c107365e727d10b53694b299f93c4245cf90110775ec22676e2",
    },
    "G1_crosswalk_private": {
        "ref": "data/workbench_private/fin_0_1_3_report_gap_crosswalk/dell-r3/full_result.json",
        "sha256": "61e627686bae188cfe9f3d58e95cbf230ac4195b855b9fb829975c6dda608880",
        "digest_field": "full_result_digest",
        "digest": "c31a51cf7b2252f94f66cdfff96d0263cb850835ab4d1ea264e1e217085849b9",
    },
    "admission_02A_program": {
        "ref": "configs/retrieval/fin_ia_0_1_3_s1_dell_report_evidence_admission_program_v1_1.json",
        "sha256": "57cac4279186a66ef6c83afd48437c583ea8d61d4b6864be7c5541c5283381c8",
        "digest_field": "program_digest",
        "digest": "0b34d8f68115b1c43af6a9a77af7dba7db883d59ffb2f9d45a59d8c00eafb267",
    },
    "prior_ladder_spec": {
        "ref": "configs/retrieval/fin_ia_0_1_3_s1_dell_external_source_ladder_residual_successor_spec_v1_1.json",
        "sha256": "f7196fa82cf929a839abf7fbde36a34fea2b2096dacbb0701cc532451049772f",
        "digest_field": "spec_digest",
        "digest": "b941e5c843bdc9daf4ab79634b44957cec0387fb9e6023a3c645de37b043ebe0",
    },
    "prior_ladder_result": {
        "ref": "configs/retrieval/fin_ia_0_1_3_s1_dell_external_source_ladder_result_v1_2.json",
        "sha256": "7bde79d13fcf0044df712345c7a5a8ebee0b0cacbbc48e7090500bd9923c3c0f",
        "digest_field": "result_digest",
        "digest": "9aeb7a80e32b51ff4e51d13daf4ad85226a125477adb5704d2be8e601e8fb9ce",
    },
    "immutable_execution_program": {
        "ref": "docs/architecture/research/FIN_0_1_3_DELL_SOURCE_CLOSURE_MODEL_AND_REPORT_QUALITY_EXECUTION_PROGRAM_20260825.zh-CN.md",
        "sha256": "5bbb52691fd183bae5c61c6d6dd1b119544e76ffa2625a42dcb1297bd1ae4f0d",
    },
    "R1_failed_audit": {
        "ref": "configs/audits/fin_ia_0_1_3_commit_581c1d6e_dell_02a_03a_fresh_audit_fail_v1_0.json",
        "sha256": "892e11be5ac74ae1191e19a6012a41b6f44cb66103836e3a4d10e7edd03260e4",
        "digest_field": "result_digest",
        "digest": "061cd35cbf624e8a7f84b379466396e0870f122799627107afc6ae9541d4a3ea",
    },
    "R1_residual_policy": {
        "ref": "configs/retrieval/fin_ia_0_1_3_s1_dell_report_residual_source_ladder_policy_v1_0.json",
        "sha256": "d13c2c5165f3760921f151f8e25b948ef4c2b0a273a9df0fd2f7bf221a850956",
        "digest_field": "policy_digest",
        "digest": "b5a5ca4fac8bd31d3c32957862bee095279b7229465fdad0c9d22b651b3c40a3",
    },
    "R1_residual_program": {
        "ref": "configs/retrieval/fin_ia_0_1_3_s1_dell_report_residual_source_ladder_program_v1_0.json",
        "sha256": "a2caf24d0e2dd8bddc5bbe9d40ffcbdeb82027273a34c92d05b85de006ced90d",
        "digest_field": "program_digest",
        "digest": "eccc6dfbe421ccc30e0ef0ab500da3e52a7808a722f087f6c48fee55a4788ad8",
    },
}

EXPECTED_SUCCESSOR_LINEAGE = {
    "policy_id": "DELL-RSQ-03A-R2",
    "predecessor_attempt": "DELL-RSQ-03A-R1",
    "predecessor_commit": "581c1d6e89f27981298d8fd9379bf53b40dc488c",
    "predecessor_verdict": "FAIL",
    "predecessor_audit_digest": "061cd35cbf624e8a7f84b379466396e0870f122799627107afc6ae9541d4a3ea",
    "same_stage_root_cause_ids": [
        "RC-S1-068-DELL-03A-semantic-authority-and-provenance-not-fail-closed"
    ],
    "predecessor_overwrite_forbidden": True,
    "execution_authority_carried_forward": False,
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


_URL_LIKE_PATTERN = re.compile(
    r"(?i)(?:[a-z][a-z0-9+.-]*://|www\.|\b[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:/[^\s]*)?)"
)


def _contains_url_like_answer_locator(value: str) -> bool:
    lowered = value.casefold()
    return bool(
        _URL_LIKE_PATTERN.search(value)
        or "qrel" in lowered
        or "answer_url" in lowered
        or "answer locator" in lowered
    )


def _validate_zero_execution_authority_surface(
    value: Any,
    *,
    path: str,
) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            child_path = f"{path}.{key}"
            lowered_key = str(key).casefold()
            positive_authority_key = (
                lowered_key in {"current_authority", "authority_granted"}
                or lowered_key.endswith("_authorized")
                or lowered_key.endswith("_authority")
            )
            if (
                isinstance(item, bool)
                and item is True
                and positive_authority_key
                and child_path
                != "policy.authority.03A_policy_compilation_authorized"
            ):
                raise DellReportResidualSourceProgramError(
                    f"dell_report_residual_positive_execution_authority:{child_path}"
                )
            _validate_zero_execution_authority_surface(
                item,
                path=child_path,
            )
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, item in enumerate(value):
            _validate_zero_execution_authority_surface(
                item,
                path=f"{path}[{index}]",
            )


def _expected_admission_item_contracts() -> dict[str, dict[str, Any]]:
    contracts: dict[str, dict[str, Any]] = {}
    for request_id, inventory in EXPECTED_REVIEW_ITEM_INVENTORY_BY_REQUEST.items():
        for review_item_ref, (review_item_digest, human_required) in inventory.items():
            if not human_required:
                continue
            semantics = EXPECTED_CLAIM_USE_SEMANTICS_BY_REF[review_item_ref]
            contracts[review_item_ref] = {
                "request_id": request_id,
                "predecessor_review_item_digest": review_item_digest,
                "four_request_readiness_blocker_subset": (
                    request_id in EXPECTED_BLOCKED_REQUEST_IDS
                ),
                "report_claim_use": {
                    "review_recommendation": semantics["review_recommendation"],
                    "recommendation_is_not_qualified_human_decision": True,
                    "material_use_class": semantics["material_use_class"],
                    "report_claim_refs": sorted(semantics["report_claim_refs"]),
                    "report_surface_paths": list(semantics["report_surface_paths"]),
                    "period_relationship": semantics["period_relationship"],
                    "basis_alignment": semantics["basis_alignment"],
                    "duplicate_of_review_item_ref": semantics[
                        "duplicate_of_review_item_ref"
                    ],
                    "material_report_use_required_for_acceptance_or_rebind": True,
                    "empty_claim_set_means_no_current_report_citation": not bool(
                        semantics["report_claim_refs"]
                    ),
                    "citation_padding_forbidden": True,
                    "qualified_human_may_reject_or_rebind": True,
                    "decision_authority": "qualified_human_only",
                },
                "decision_state": "qualified_human_pending",
            }
    return contracts


def _expected_admission_inventory_digest() -> str:
    items = [
        {
            "request_id": request_id,
            "review_item_ref": review_item_ref,
            "review_item_digest": review_item_digest,
            "human_review_required": human_required,
        }
        for request_id, inventory in EXPECTED_REVIEW_ITEM_INVENTORY_BY_REQUEST.items()
        for review_item_ref, (review_item_digest, human_required) in inventory.items()
    ]
    return canonical_digest(
        {
            "request_count": len(EXPECTED_REVIEW_ITEM_INVENTORY_BY_REQUEST),
            "review_item_count": len(items),
            "human_review_required_count": sum(
                int(item["human_review_required"]) for item in items
            ),
            "items": sorted(
                items,
                key=lambda item: (item["request_id"], item["review_item_ref"]),
            ),
        }
    )


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
    _require(
        parsed.get("input_bindings") == EXPECTED_INPUT_BINDINGS,
        "dell_report_residual_input_binding_contract_drift",
    )
    _require(
        parsed.get("successor_lineage") == EXPECTED_SUCCESSOR_LINEAGE,
        "dell_report_residual_successor_lineage_drift",
    )
    _validate_zero_execution_authority_surface(parsed, path="policy")
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
        set(targets) == set(EXPECTED_TARGET_SEMANTICS_BY_ID),
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
        actual_semantics = {
            "pack_gap_id": target.get("pack_gap_id"),
            "independent_S2_bridge_gap_id": target.get(
                "independent_S2_bridge_gap_id"
            ),
            "expected_crosswalk_disposition": target.get(
                "expected_crosswalk_disposition"
            ),
            "prior_proposition_id": target.get("prior_proposition_id"),
            "admission_overlap_request_ids": tuple(
                str(value)
                for value in target.get("admission_overlap_request_ids") or []
            ),
        }
        _require(
            actual_semantics == EXPECTED_TARGET_SEMANTICS_BY_ID[target_id],
            f"dell_report_residual_target_semantics_drift:{target_id}",
        )
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
    for field, expected_digest in EXPECTED_POLICY_COMPONENT_DIGESTS.items():
        _require(
            canonical_digest(parsed.get(field)) == expected_digest,
            f"dell_report_residual_policy_component_drift:{field}",
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
    required = set(EXPECTED_INPUT_BINDINGS)
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
        _validate_self_digest(
            payload,
            str(digest_field),
            f"dell_report_residual_input_self_digest_invalid:{name}",
        )
    failed_audit = _mapping(
        payloads.get("R1_failed_audit"),
        "dell_report_residual_R1_failed_audit_missing",
    )
    _require(
        failed_audit.get("status")
        == "fail_material_findings_preserved_successor_required"
        and failed_audit.get("severity_counts")
        == {"P0": 1, "P1": 2, "P2": 1, "P3": 0}
        and _mapping(
            failed_audit.get("reviewed_identity"),
            "dell_report_residual_R1_failed_identity_missing",
        ).get("commit")
        == "581c1d6e89f27981298d8fd9379bf53b40dc488c",
        "dell_report_residual_R1_failure_lineage_invalid",
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
    _require(
        not _contains_url_like_answer_locator(query_text),
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
        and admission_manifest_ref
        == (
            "configs/retrieval/"
            "fin_ia_0_1_3_s1_dell_report_evidence_admission_manifest_v1_1.json"
        )
        and admission.get("schema_version")
        == ADMISSION_PUBLIC_MANIFEST_SCHEMA_VERSION
        and admission.get("status")
        == "packet_frozen_qualified_human_decisions_pending",
        "dell_report_residual_admission_manifest_binding_invalid",
    )
    _validate_zero_execution_authority_surface(admission, path="admission")
    admission_lineage = _mapping(
        admission.get("successor_lineage"),
        "dell_report_residual_admission_successor_lineage_missing",
    )
    _require(
        admission_lineage
        == {
            "predecessor_attempt": "DELL-RSQ-02A-R1",
            "predecessor_verdict": "FAIL",
            "predecessor_audit_ref": EXPECTED_INPUT_BINDINGS["R1_failed_audit"][
                "ref"
            ],
            "predecessor_audit_digest": EXPECTED_INPUT_BINDINGS[
                "R1_failed_audit"
            ]["digest"],
            "successor_attempt": "DELL-RSQ-02A-R2",
            "same_stage_root_cause_ids": [
                "RC-S1-066-DELL-02A-nested-population-not-recounted",
                "RC-S1-067-DELL-02A-report-claim-use-semantic-padding",
            ],
            "predecessor_overwritten": False,
        },
        "dell_report_residual_admission_successor_lineage_invalid",
    )
    admission_counts = _mapping(
        admission.get("counts"),
        "dell_report_residual_admission_counts_missing",
    )
    _require(
        admission_counts
        == {
            "request_count": 8,
            "candidate_review_item_count": 18,
            "all_human_required_item_count": 16,
            "blocked_request_count": 4,
            "blocked_request_human_item_count": 8,
            "bounded_or_direct_material_use_candidate_count": 5,
            "recommend_reject_no_current_material_report_use_count": 10,
            "recommend_rebind_duplicate_to_canonical_candidate_count": 1,
            "qualified_human_decision_count": 0,
        }
        and admission.get("execution")
        == {
            "network_calls": 0,
            "provider_calls": 0,
            "model_calls": 0,
            "embedding_calls": 0,
            "reranker_calls": 0,
            "candidate_promotions": 0,
            "evidence_promotions": 0,
        }
        and admission.get("authority")
        == {
            "qualified_human_decisions_complete": False,
            "G2_pass": False,
            "S1_pass": False,
            "S2_pass": False,
            "S3_pass": False,
            "report_quality_pass": False,
            "product_acceptance": False,
            "publication": False,
            "release_ready": False,
        }
        and admission.get("case_key") == "DELL"
        and admission.get("research_as_of") == "2026-08-06"
        and admission.get("private_full_result_ref")
        == (
            "data/workbench_private/fin_0_1_3_dell_report_evidence_admission/"
            "dell-r2/full_result.json"
        )
        and re.fullmatch(
            r"[0-9a-f]{64}", str(admission.get("admission_packet_digest") or "")
        )
        is not None
        and re.fullmatch(r"[0-9a-f]{64}", admission_manifest_sha256) is not None,
        "dell_report_residual_admission_state_invalid",
    )
    inventory_summary = _mapping(
        admission.get("predecessor_review_inventory_summary"),
        "dell_report_residual_admission_inventory_summary_missing",
    )
    _require(
        inventory_summary
        == {
            "request_count": 8,
            "review_item_count": 18,
            "human_review_required_count": 16,
            "inventory_digest": _expected_admission_inventory_digest(),
        },
        "dell_report_residual_admission_inventory_summary_invalid",
    )
    admission_items = _unique_by(
        (
            _mapping(row, "dell_report_residual_admission_item_invalid")
            for row in _sequence(
                admission.get("items"),
                "dell_report_residual_admission_items_invalid",
            )
        ),
        "review_item_ref",
        code="dell_report_residual_admission_item_duplicate",
    )
    expected_admission_items = _expected_admission_item_contracts()
    _require(
        set(admission_items) == set(expected_admission_items),
        "dell_report_residual_admission_manifest_item_set_invalid",
    )
    packet_item_digests: set[str] = set()
    for review_item_ref, row in admission_items.items():
        expected_item = expected_admission_items[review_item_ref]
        actual_item = {
            "request_id": row.get("request_id"),
            "predecessor_review_item_digest": row.get(
                "predecessor_review_item_digest"
            ),
            "four_request_readiness_blocker_subset": row.get(
                "four_request_readiness_blocker_subset"
            ),
            "report_claim_use": _mapping(
                row.get("report_claim_use"),
                f"dell_report_residual_admission_claim_use_missing:{review_item_ref}",
            ),
            "decision_state": row.get("decision_state"),
        }
        _require(
            actual_item == expected_item,
            f"dell_report_residual_admission_item_semantics_drift:{review_item_ref}",
        )
        source_identity_digest = str(row.get("source_identity_digest") or "")
        packet_item_digest = str(row.get("packet_item_digest") or "")
        _require(
            re.fullmatch(r"[0-9a-f]{64}", source_identity_digest) is not None
            and re.fullmatch(r"[0-9a-f]{64}", packet_item_digest) is not None
            and packet_item_digest not in packet_item_digests,
            f"dell_report_residual_admission_item_digest_invalid:{review_item_ref}",
        )
        packet_item_digests.add(packet_item_digest)
    manifest_request_ids = {
        str(row["request_id"]) for row in admission_items.values()
    }
    _require(
        manifest_request_ids == set(EXPECTED_REVIEW_ITEM_INVENTORY_BY_REQUEST),
        "dell_report_residual_admission_request_set_invalid",
    )
    recommendation_counts: dict[str, int] = {}
    for row in admission_items.values():
        claim_use = row["report_claim_use"]
        recommendation = str(claim_use.get("review_recommendation") or "")
        recommendation_counts[recommendation] = (
            recommendation_counts.get(recommendation, 0) + 1
        )
    _require(
        recommendation_counts
        == {
            "consider_bounded_context": 3,
            "consider_definition_boundary": 1,
            "consider_risk_counterevidence": 1,
            "recommend_rebind_duplicate_to_canonical_candidate": 1,
            "recommend_reject_no_current_material_report_use": 10,
        },
        "dell_report_residual_admission_claim_use_partition_invalid",
    )
    prior_spec = _mapping(
        input_payloads.get("prior_ladder_spec"),
        "dell_report_residual_prior_spec_missing",
    )
    prior_result = _mapping(
        input_payloads.get("prior_ladder_result"),
        "dell_report_residual_prior_result_missing",
    )
    prior_provider = _mapping(
        prior_result.get("provider"),
        "dell_report_residual_prior_provider_missing",
    )
    _require(
        {
            key: prior_provider.get(key)
            for key in (
                "query_count",
                "replayed_query_count",
                "fresh_provider_query_count",
                "successful_query_count",
                "failed_query_count",
                "provider_call_count",
                "model_call_count",
                "retry_count",
            )
        }
        == {
            "query_count": 50,
            "replayed_query_count": 28,
            "fresh_provider_query_count": 22,
            "successful_query_count": 50,
            "failed_query_count": 0,
            "provider_call_count": 22,
            "model_call_count": 0,
            "retry_count": 0,
        }
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
    actual_prior_counts = {
        proposition_id: (
            row.get("query_count"),
            row.get("captured_original_count"),
            row.get("compiled_source_object_count"),
            row.get("candidate_proposal_count"),
        )
        for proposition_id, row in prior_by_proposition.items()
    }
    _require(
        actual_prior_counts == EXPECTED_PRIOR_PROPOSITION_COUNTS
        and sum(counts[0] for counts in actual_prior_counts.values()) == 50,
        "dell_report_residual_prior_proposition_counts_invalid",
    )
    fresh_query_units = [
        _mapping(
            row,
            "dell_report_residual_prior_fresh_query_unit_invalid",
        )
        for row in _sequence(
            prior_spec.get("new_query_units"),
            "dell_report_residual_prior_fresh_query_units_invalid",
        )
    ]
    fresh_query_unit_ids = [
        str(row.get("query_unit_id") or "") for row in fresh_query_units
    ]
    _require(
        len(fresh_query_unit_ids) == 22
        and all(fresh_query_unit_ids)
        and len(set(fresh_query_unit_ids)) == 22,
        "dell_report_residual_prior_fresh_query_unit_identity_invalid",
    )
    fresh_counts_by_proposition: dict[str, int] = {}
    for row in fresh_query_units:
        proposition_id = str(row.get("proposition_id") or "")
        fresh_counts_by_proposition[proposition_id] = (
            fresh_counts_by_proposition.get(proposition_id, 0) + 1
        )
    _require(
        fresh_counts_by_proposition
        == EXPECTED_FRESH_QUERY_UNITS_BY_PROPOSITION
        and sum(fresh_counts_by_proposition.values())
        == prior_provider["fresh_provider_query_count"],
        "dell_report_residual_prior_fresh_query_reconciliation_invalid",
    )
    prior_spec_propositions = set(fresh_counts_by_proposition)
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
    held_target_ids: set[str] = set()
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
            held_target_ids.add(target_id)
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
        held_count == 3
        and unoverlapped_count == 6
        and held_target_ids == EXPECTED_HELD_TARGET_IDS,
        "dell_report_residual_admission_partition_invalid",
    )
    expected_pack_target_by_gap = {
        str(contract["pack_gap_id"]): target_id
        for target_id, contract in EXPECTED_TARGET_SEMANTICS_BY_ID.items()
        if contract["pack_gap_id"] is not None
    }
    _require(
        pack_target_by_gap == expected_pack_target_by_gap,
        "dell_report_residual_target_gap_map_invalid",
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
        "program_id": "FIN-0.1.3-S1-DELL-RSQ-03A-R2",
        "status": "route_manifest_frozen_zero_call_execution_not_authorized",
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "case_key": "DELL",
        "research_as_of": "2026-08-06",
        "policy_digest": parsed_policy["policy_digest"],
        "input_bindings": parsed_policy["input_bindings"],
        "successor_lineage": {
            "predecessor_attempt": "DELL-RSQ-03A-R1",
            "predecessor_verdict": "FAIL",
            "predecessor_audit_ref": EXPECTED_INPUT_BINDINGS[
                "R1_failed_audit"
            ]["ref"],
            "predecessor_audit_digest": EXPECTED_INPUT_BINDINGS[
                "R1_failed_audit"
            ]["digest"],
            "successor_attempt": "DELL-RSQ-03A-R2",
            "same_stage_root_cause_ids": EXPECTED_SUCCESSOR_LINEAGE[
                "same_stage_root_cause_ids"
            ],
            "predecessor_overwritten": False,
        },
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
            "prior_total_query_count": prior_provider["query_count"],
            "prior_replayed_query_count": prior_provider[
                "replayed_query_count"
            ],
            "fresh_provider_query_count_already_spent": 22,
            "fresh_query_unit_counts_by_proposition": (
                fresh_counts_by_proposition
            ),
            "all_proposition_counts": {
                proposition_id: {
                    "query_count": counts_tuple[0],
                    "captured_original_count": counts_tuple[1],
                    "compiled_source_object_count": counts_tuple[2],
                    "candidate_proposal_count": counts_tuple[3],
                }
                for proposition_id, counts_tuple in sorted(
                    actual_prior_counts.items()
                )
            },
            "prior_self_digests_recomputed": True,
            "held_target_ids": sorted(held_target_ids),
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
            "This R2 successor is a zero-call route program. It freezes the exact "
            "target-gap-prior-proposition-admission map, reconciles all 50 prior "
            "queries including the 22 fresh units, holds only the three exact "
            "qualified-human overlaps, and authorizes no retrieval, model, "
            "candidate promotion, Evidence promotion, gap closure or report claim."
        ),
    }
    _validate_zero_execution_authority_surface(body, path="program")
    return {**body, "program_digest": canonical_digest(body)}


__all__ = [
    "DellReportResidualSourceProgramError",
    "POLICY_SCHEMA_VERSION",
    "PROGRAM_SCHEMA_VERSION",
    "ROUTE_FAMILY_IDS",
    "compile_dell_report_residual_source_program",
    "validate_dell_report_residual_source_policy",
]
