from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any, Mapping
from urllib.parse import urlsplit

from .external_source_ladder import source_family_allowed_hosts
from .query_plan import canonical_digest


DELL_DIRECT_SOURCE_CAPTURE_PLAN_SCHEMA_VERSION = (
    "fin_ia_s1_dell_direct_source_capture_plan_v1_0"
)
DELL_DIRECT_SOURCE_SHORTLIST_SCHEMA_VERSION = (
    "fin_ia_s1_dell_direct_source_shortlist_v1_0"
)

_STATUS = "approved_exact_once_direct_original_capture_plan"
_TIERS = {
    "official_subject_regulator_customer_supplier",
    "industry_association_market_tracking",
    "product_procurement_channel_deployment",
    "trusted_context_analyst_counterevidence",
}
_PROPOSITIONS = {
    "DELL-PROP-PRICE-CONFIGURATION",
    "DELL-PROP-UNIT-VOLUME",
    "DELL-PROP-SUPPLY-CHAIN",
}
_AUTHORITY = {
    "direct_locator_is_not_evidence": True,
    "provider_result_is_locator_only": True,
    "provider_calls_authorized": False,
    "original_capture_required": True,
    "candidate_is_not_evidence": True,
    "candidate_decision_and_evidence_gate_required": True,
    "public_information_gap_authorized": False,
    "S1_qualification_authorized": False,
}


class DirectSourceCaptureError(ValueError):
    """A reviewed direct locator lost its scope or capture boundary."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DirectSourceCaptureError(code)


def _valid_date(value: object) -> bool:
    try:
        date.fromisoformat(str(value))
    except ValueError:
        return False
    return True


def _validate_digest(value: Mapping[str, Any]) -> None:
    body = deepcopy(dict(value))
    digest = str(body.pop("plan_digest", ""))
    _require(
        digest == canonical_digest(body),
        "direct_source_capture_plan_digest_invalid",
    )


def validate_dell_direct_source_capture_plan(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    value = deepcopy(dict(payload))
    _validate_digest(value)
    expected_fields = {
        "schema_version",
        "plan_id",
        "status",
        "recorded_at",
        "case_key",
        "research_as_of",
        "program_ref",
        "source_use_policy_ref",
        "purpose",
        "execution_budget",
        "token_budget_basis",
        "query_units",
        "source_registry",
        "direct_sources",
        "candidate_selection_policy",
        "authority",
        "plan_digest",
    }
    budget = value.get("execution_budget")
    token_basis = value.get("token_budget_basis")
    units = value.get("query_units")
    registry = value.get("source_registry")
    sources = value.get("direct_sources")
    policies = value.get("candidate_selection_policy")
    _require(
        set(value) == expected_fields
        and value.get("schema_version")
        == DELL_DIRECT_SOURCE_CAPTURE_PLAN_SCHEMA_VERSION
        and value.get("status") == _STATUS
        and str(value.get("plan_id") or "")
        and str(value.get("case_key") or "").upper() == "DELL"
        and _valid_date(value.get("recorded_at"))
        and _valid_date(value.get("research_as_of"))
        and str(value.get("program_ref") or "")
        and str(value.get("source_use_policy_ref") or "")
        and str(value.get("purpose") or "")
        and isinstance(budget, Mapping)
        and budget.get("provider_call_ceiling") == 0
        and int(budget.get("original_fetch_ceiling") or 0) > 0
        and int(budget.get("original_fetch_timeout_seconds") or 0) > 0
        and int(budget.get("original_fetch_byte_ceiling") or 0) > 0
        and budget.get("retry_ceiling") == 0
        and budget.get("model_call_ceiling") == 0
        and isinstance(token_basis, Mapping)
        and token_basis.get("model_tokens") == 0
        and token_basis.get("cost_and_latency_are_secondary_constraints") is True
        and str(token_basis.get("node_purpose") or "")
        and str(token_basis.get("input_scale_basis") or "")
        and isinstance(token_basis.get("required_outputs"), list)
        and bool(token_basis["required_outputs"])
        and str(token_basis.get("schema_burden") or "")
        and str(token_basis.get("materiality_and_quality_risk") or "")
        and str(token_basis.get("comparable_run_evidence") or "")
        and str(token_basis.get("reasoning_profile") or "")
        and str(token_basis.get("stop_and_truncation_behavior") or "")
        and isinstance(units, list)
        and bool(units)
        and isinstance(registry, list)
        and bool(registry)
        and isinstance(sources, list)
        and bool(sources)
        and len(sources) <= int(budget["original_fetch_ceiling"])
        and isinstance(policies, Mapping)
        and value.get("authority") == _AUTHORITY,
        "direct_source_capture_plan_shape_invalid",
    )

    unit_by_id: dict[str, dict[str, Any]] = {}
    propositions: set[str] = set()
    for raw in units:
        _require(isinstance(raw, Mapping), "direct_source_query_unit_invalid")
        row = dict(raw)
        unit_id = str(row.get("query_unit_id") or "")
        proposition = str(row.get("proposition_id") or "")
        _require(
            unit_id
            and unit_id not in unit_by_id
            and proposition in _PROPOSITIONS
            and str(row.get("tier_id") or "") in _TIERS
            and str(row.get("query") or "")
            and isinstance(row.get("expected_output_ids"), list)
            and bool(row["expected_output_ids"])
            and isinstance(row.get("relationship_directions"), list)
            and bool(row["relationship_directions"])
            and isinstance(row.get("speaker_or_source_targets"), list)
            and bool(row["speaker_or_source_targets"]),
            "direct_source_query_unit_invalid",
        )
        unit_by_id[unit_id] = row
        propositions.add(proposition)
    _require(
        propositions == _PROPOSITIONS and set(policies) == propositions,
        "direct_source_proposition_coverage_invalid",
    )

    registry_by_id: dict[str, dict[str, Any]] = {}
    for raw in registry:
        _require(isinstance(raw, Mapping), "direct_source_registry_invalid")
        row = dict(raw)
        family_id = str(row.get("source_family_id") or "").lower()
        host = str(row.get("host") or "").lower()
        allowed_tiers = {str(item) for item in row.get("allowed_ladder_tiers") or ()}
        _require(
            family_id
            and family_id not in registry_by_id
            and host
            and family_id == host
            and str(row.get("speaker_entity") or "")
            and str(row.get("source_class") or "")
            and str(row.get("source_role") or "")
            and isinstance(row.get("relationship_directions"), list)
            and bool(row["relationship_directions"])
            and allowed_tiers
            and allowed_tiers.issubset(_TIERS),
            "direct_source_registry_invalid",
        )
        source_family_allowed_hosts(row)
        registry_by_id[family_id] = row

    seen_source_ids: set[str] = set()
    seen_urls: set[str] = set()
    covered_units: set[str] = set()
    for raw in sources:
        _require(isinstance(raw, Mapping), "direct_source_locator_invalid")
        row = dict(raw)
        source_id = str(row.get("direct_source_id") or "")
        unit_id = str(row.get("query_unit_id") or "")
        family_id = str(row.get("source_family_id") or "").lower()
        url = str(row.get("canonical_url") or "")
        parsed = urlsplit(url)
        registry_row = registry_by_id.get(family_id)
        unit = unit_by_id.get(unit_id)
        _require(
            source_id
            and source_id not in seen_source_ids
            and unit is not None
            and registry_row is not None
            and parsed.scheme == "https"
            and bool(parsed.hostname)
            and url not in seen_urls
            and str(row.get("title") or "")
            and (
                row.get("provider_date_telemetry") is None
                or _valid_date(row.get("provider_date_telemetry"))
            )
            and (parsed.hostname or "").lower()
            in source_family_allowed_hosts(
                registry_row,
                observed_host=(parsed.hostname or "").lower(),
            )
            and str(unit["tier_id"])
            in {str(item) for item in registry_row["allowed_ladder_tiers"]},
            "direct_source_locator_invalid",
        )
        seen_source_ids.add(source_id)
        seen_urls.add(url)
        covered_units.add(unit_id)
    _require(
        covered_units == set(unit_by_id),
        "direct_source_query_unit_coverage_invalid",
    )

    for proposition, raw in policies.items():
        _require(
            proposition in propositions
            and isinstance(raw, Mapping)
            and isinstance(raw.get("scope_anchor_terms"), list)
            and bool(raw["scope_anchor_terms"])
            and isinstance(raw.get("material_signal_terms"), list)
            and bool(raw["material_signal_terms"])
            and int(raw.get("minimum_scope_anchor_hits") or 0) >= 1
            and int(raw.get("minimum_material_signal_hits") or 0) >= 1
            and 0 <= int(raw.get("context_blocks_before") or 0) <= 2
            and 0 <= int(raw.get("context_blocks_after") or 0) <= 2,
            "direct_source_candidate_policy_invalid",
        )
    return value


def compile_dell_direct_source_shortlist(
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    validated = validate_dell_direct_source_capture_plan(plan)
    units = {
        str(row["query_unit_id"]): row for row in validated["query_units"]
    }
    registry = {
        str(row["source_family_id"]): row
        for row in validated["source_registry"]
    }
    ranks: dict[str, int] = {}
    selected: list[dict[str, Any]] = []
    for raw in validated["direct_sources"]:
        row = dict(raw)
        unit = units[str(row["query_unit_id"])]
        family = registry[str(row["source_family_id"])]
        unit_id = str(unit["query_unit_id"])
        ranks[unit_id] = ranks.get(unit_id, 0) + 1
        url = str(row["canonical_url"])
        locator_body = {
            "query_unit_id": unit_id,
            "proposition_id": str(unit["proposition_id"]),
            "tier_id": str(unit["tier_id"]),
            "expected_output_ids": list(unit["expected_output_ids"]),
            "relationship_directions": list(unit["relationship_directions"]),
            "provider_rank": ranks[unit_id],
            "canonical_url": url,
            "source_domain": str(urlsplit(url).hostname or "").lower(),
            "title": str(row["title"]),
            "passage": "",
            "provider_date_telemetry": row.get("provider_date_telemetry"),
            "provider_score": None,
            "provider_result_is_locator_only": True,
            "candidate_not_evidence": True,
            "writer_citable": False,
            "numeric_authority": "none",
        }
        selected.append(
            {
                **locator_body,
                "locator_digest": canonical_digest(locator_body),
                "source_registry": deepcopy(dict(family)),
                "source_family_id": str(family["source_family_id"]),
                "fetch_status": "approved_for_direct_original_capture",
                "direct_source_id": str(row["direct_source_id"]),
            }
        )
    body = {
        "schema_version": DELL_DIRECT_SOURCE_SHORTLIST_SCHEMA_VERSION,
        "case_key": "DELL",
        "research_as_of": str(validated["research_as_of"]),
        "plan_digest": str(validated["plan_digest"]),
        "selected": selected,
        "rejected": [],
        "summary": {
            "reviewed_direct_locator_count": len(selected),
            "selected_original_fetch_count": len(selected),
            "provider_call_count": 0,
            "provider_result_count": 0,
            "candidate_evidence_promotions": 0,
        },
        "authority": deepcopy(_AUTHORITY),
    }
    return {**body, "shortlist_digest": canonical_digest(body)}


__all__ = [
    "DELL_DIRECT_SOURCE_CAPTURE_PLAN_SCHEMA_VERSION",
    "DELL_DIRECT_SOURCE_SHORTLIST_SCHEMA_VERSION",
    "DirectSourceCaptureError",
    "compile_dell_direct_source_shortlist",
    "validate_dell_direct_source_capture_plan",
]
