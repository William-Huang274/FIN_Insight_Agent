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
DELL_DIRECT_SOURCE_CAPTURE_SUCCESSOR_PLAN_SCHEMA_VERSION = (
    "fin_ia_s1_dell_direct_source_capture_successor_plan_v1_0"
)

_STATUS = "approved_exact_once_direct_original_capture_plan"
_SUCCESSOR_STATUS = "approved_failed_route_direct_source_successor"
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


def validate_dell_direct_source_capture_successor_plan(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate one failed-route-only successor without weakening R1."""

    value = deepcopy(dict(payload))
    _validate_digest(value)
    expected_fields = {
        "schema_version",
        "plan_id",
        "status",
        "recorded_at",
        "case_key",
        "research_as_of",
        "predecessor_plan_binding",
        "predecessor_terminal_binding",
        "failed_route_binding",
        "replacement_source_registry",
        "replacement_direct_source",
        "execution_budget",
        "token_budget_basis",
        "authority",
        "plan_digest",
    }
    predecessor_plan = value.get("predecessor_plan_binding")
    predecessor_terminal = value.get("predecessor_terminal_binding")
    failed = value.get("failed_route_binding")
    registry = value.get("replacement_source_registry")
    replacement = value.get("replacement_direct_source")
    budget = value.get("execution_budget")
    token_basis = value.get("token_budget_basis")
    replacement_url = str(
        replacement.get("canonical_url") if isinstance(replacement, Mapping) else ""
    )
    replacement_host = str(urlsplit(replacement_url).hostname or "").lower()
    replacement_allowed_hosts = (
        {
            str(registry.get("host") or "").lower(),
            *(
                str(host).lower()
                for host in registry.get("safe_host_aliases") or ()
            ),
        }
        if isinstance(registry, Mapping)
        else set()
    )
    _require(
        set(value) == expected_fields
        and value.get("schema_version")
        == DELL_DIRECT_SOURCE_CAPTURE_SUCCESSOR_PLAN_SCHEMA_VERSION
        and value.get("status") == _SUCCESSOR_STATUS
        and str(value.get("plan_id") or "")
        and str(value.get("case_key") or "").upper() == "DELL"
        and _valid_date(value.get("recorded_at"))
        and _valid_date(value.get("research_as_of"))
        and isinstance(predecessor_plan, Mapping)
        and str(predecessor_plan.get("ref") or "")
        and len(str(predecessor_plan.get("sha256") or "")) == 64
        and len(str(predecessor_plan.get("plan_digest") or "")) == 64
        and isinstance(predecessor_terminal, Mapping)
        and str(predecessor_terminal.get("ref") or "")
        and len(str(predecessor_terminal.get("sha256") or "")) == 64
        and len(str(predecessor_terminal.get("result_digest") or "")) == 64
        and str(predecessor_terminal.get("attempt_id") or "")
        and isinstance(failed, Mapping)
        and str(failed.get("direct_source_id") or "")
        and str(failed.get("canonical_url") or "").startswith("https://")
        and str(failed.get("failure_code") or "")
        and len(str(failed.get("locator_digest") or "")) == 64
        and isinstance(registry, Mapping)
        and str(registry.get("source_family_id") or "").lower()
        == str(registry.get("host") or "").lower()
        and str(registry.get("speaker_ticker") or "").upper() == "DELL"
        and str(registry.get("source_class") or "")
        == "issuer_regulator_or_government_primary"
        and replacement_host in replacement_allowed_hosts
        and isinstance(replacement, Mapping)
        and str(replacement.get("direct_source_id") or "")
        and str(replacement.get("direct_source_id") or "")
        != str(failed.get("direct_source_id") or "")
        and str(replacement.get("query_unit_id") or "")
        == "DELL-DIRECT-CURRENT-RELATIONSHIP"
        and str(replacement.get("source_family_id") or "").lower()
        == str(registry.get("source_family_id") or "").lower()
        and replacement_url.startswith("https://")
        and replacement_url != str(failed.get("canonical_url") or "")
        and str(replacement.get("title") or "")
        and _valid_date(replacement.get("provider_date_telemetry"))
        and isinstance(budget, Mapping)
        and budget.get("provider_call_ceiling") == 0
        and budget.get("fresh_original_fetch_ceiling") == 1
        and budget.get("expected_unchanged_locator_count") == 4
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
        and value.get("authority") == _AUTHORITY,
        "direct_source_capture_successor_plan_shape_invalid",
    )
    return value


def compile_dell_direct_source_capture_successor(
    *,
    successor_plan: Mapping[str, Any],
    predecessor_plan: Mapping[str, Any],
    predecessor_terminal: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Replace exactly one failed R1 locator and preserve every other route."""

    successor = validate_dell_direct_source_capture_successor_plan(successor_plan)
    predecessor = validate_dell_direct_source_capture_plan(predecessor_plan)
    terminal = deepcopy(dict(predecessor_terminal))
    terminal_body = deepcopy(terminal)
    terminal_digest = str(terminal_body.pop("result_digest", ""))
    _require(
        terminal_digest == canonical_digest(terminal_body)
        and terminal_digest
        == str(successor["predecessor_terminal_binding"]["result_digest"])
        and str(terminal.get("attempt_id") or "")
        == str(successor["predecessor_terminal_binding"]["attempt_id"])
        and str(terminal.get("plan_binding", {}).get("plan_digest") or "")
        == str(predecessor["plan_digest"])
        == str(successor["predecessor_plan_binding"]["plan_digest"])
        and str(successor["research_as_of"]) == str(predecessor["research_as_of"]),
        "direct_source_capture_successor_predecessor_binding_invalid",
    )

    failed = dict(successor["failed_route_binding"])
    old_sources = [dict(row) for row in predecessor["direct_sources"]]
    old_source = next(
        (
            row
            for row in old_sources
            if str(row.get("direct_source_id") or "")
            == str(failed["direct_source_id"])
        ),
        None,
    )
    old_receipts = list(
        (terminal.get("original_compilation_result") or {}).get("route_receipts")
        or ()
    )
    failed_receipt = next(
        (
            dict(row)
            for row in old_receipts
            if str(row.get("canonical_url") or "")
            == str(failed["canonical_url"])
        ),
        None,
    )
    old_shortlist = list((terminal.get("fetch_shortlist") or {}).get("selected") or ())
    failed_locator = next(
        (
            dict(row)
            for row in old_shortlist
            if str(row.get("direct_source_id") or "")
            == str(failed["direct_source_id"])
        ),
        None,
    )
    _require(
        old_source is not None
        and failed_receipt is not None
        and failed_locator is not None
        and str(old_source.get("canonical_url") or "")
        == str(failed["canonical_url"])
        and str(failed_receipt.get("capture_failure_code") or "")
        == str(failed["failure_code"])
        and str(failed_locator.get("locator_digest") or "")
        == str(failed["locator_digest"]),
        "direct_source_capture_successor_failed_route_binding_invalid",
    )

    replacement = deepcopy(dict(successor["replacement_direct_source"]))
    effective = deepcopy(predecessor)
    effective["plan_id"] = str(successor["plan_id"]) + "::EFFECTIVE"
    effective["recorded_at"] = successor["recorded_at"]
    effective["purpose"] = (
        "Reuse every successful immutable R1 capture and replace only the bound "
        "Dell newsroom HTTP 403 with the same issuer's official investor-relations PDF."
    )
    effective["token_budget_basis"] = deepcopy(successor["token_budget_basis"])
    effective["source_registry"].append(
        deepcopy(dict(successor["replacement_source_registry"]))
    )
    effective["direct_sources"] = [
        replacement
        if str(row.get("direct_source_id") or "")
        == str(failed["direct_source_id"])
        else row
        for row in old_sources
    ]
    effective_body = deepcopy(effective)
    effective_body.pop("plan_digest", None)
    effective["plan_digest"] = canonical_digest(effective_body)
    effective = validate_dell_direct_source_capture_plan(effective)

    old_urls = {str(row["canonical_url"]) for row in old_sources}
    new_urls = {
        str(row["canonical_url"]) for row in effective["direct_sources"]
    }
    unchanged = sorted(old_urls & new_urls)
    added = sorted(new_urls - old_urls)
    retired = sorted(old_urls - new_urls)
    budget = successor["execution_budget"]
    _require(
        len(unchanged) == int(budget["expected_unchanged_locator_count"])
        and len(added) == int(budget["fresh_original_fetch_ceiling"])
        and len(retired) == 1
        and retired == [str(failed["canonical_url"])]
        and added == [str(replacement["canonical_url"])],
        "direct_source_capture_successor_locator_delta_invalid",
    )
    delta_body = {
        "schema_version": "fin_ia_s1_dell_direct_source_locator_delta_receipt_v1_0",
        "case_key": "DELL",
        "successor_plan_digest": successor["plan_digest"],
        "predecessor_plan_digest": predecessor["plan_digest"],
        "unchanged_urls": unchanged,
        "retired_failed_urls": retired,
        "fresh_urls": added,
        "expected_fresh_network_routes": 1,
        "provider_calls": 0,
        "model_calls": 0,
    }
    return effective, {
        **delta_body,
        "receipt_digest": canonical_digest(delta_body),
    }


__all__ = [
    "DELL_DIRECT_SOURCE_CAPTURE_PLAN_SCHEMA_VERSION",
    "DELL_DIRECT_SOURCE_CAPTURE_SUCCESSOR_PLAN_SCHEMA_VERSION",
    "DELL_DIRECT_SOURCE_SHORTLIST_SCHEMA_VERSION",
    "DirectSourceCaptureError",
    "compile_dell_direct_source_capture_successor",
    "compile_dell_direct_source_shortlist",
    "validate_dell_direct_source_capture_plan",
    "validate_dell_direct_source_capture_successor_plan",
]
