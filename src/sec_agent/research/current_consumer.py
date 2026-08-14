from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, localcontext
import json
import re
from typing import Any, Mapping, Sequence

from .reviewed_evidence_pack import canonical_digest
from .research_context import (
    ResearchContextError,
    bind_research_context_to_cells,
    compile_evidence_request_route_catalog,
    compile_graph_context_packs,
    load_research_context_contract,
)


CURRENT_RESEARCH_CONSUMER_POLICY_SCHEMA_VERSION = (
    "fin_ia_current_research_consumer_policy_v1_2"
)
CURRENT_RESEARCH_INPUT_SCHEMA_VERSION = "fin_ia_current_research_input_v1_1"
CURRENT_RESEARCH_JUDGMENT_SCHEMA_VERSION = (
    "fin_ia_current_research_judgment_payload_v1_2"
)
CURRENT_RESEARCH_DELIVERABLE_SCHEMA_VERSION = (
    "fin_ia_current_research_deliverable_v1_2"
)

_AUTHORITY = {
    "model_sees_source_visible_facts_and_authoritative_numeric_facts": True,
    "model_owns_judgment_mechanism_counterargument_and_wwc": True,
    "harness_owns_identity_period_unit_exact_numeric_surface_and_citations": True,
    "harness_may_not_invent_research_judgment": True,
    "candidates_and_rejected_items_forbidden": True,
    "residual_gaps_remain_visible": True,
    "source_policy_domains_remain_separate": True,
    "qualified_human_review_required": True,
    "model_must_cite_injected_method_and_graph_context_when_available": True,
}
_MODEL_TEXT_FIELDS = (
    "thesis_atom",
    "mechanism_atom",
    "counterargument_atom",
)
_DIGIT_OR_FINANCIAL_SURFACE = re.compile(
    r"[0-9０-９]|[$€£¥￥]|%|％|\b(?:USD|CNY|EUR|JPY|bps?)\b",
    re.IGNORECASE,
)
_VERBAL_NUMERIC_SURFACE = re.compile(
    r"(?:百分之[零一二两三四五六七八九十百千万亿点]+|"
    r"[零一二两三四五六七八九十百千万亿]+位数|"
    r"(?:个|两|双|多)位数|"
    r"[零一二两三四五六七八九十百千万亿点]+个基点)"
)
_ALIAS_IN_PROSE = re.compile(
    r"\b(?:EV|NUM|REL|GAP|METHOD|GRAPH)::[A-Z0-9:_-]{4,96}\b"
)
_YEAR_OVER_YEAR_SURFACE = re.compile(
    r"同比|较上年同期|year[- ]over[- ]year|\byoy\b|prior[- ]year quarter",
    re.IGNORECASE,
)


class CurrentResearchConsumerError(ValueError):
    """Fail-closed error at the reviewed Evidence/NumericFact consumer boundary."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CurrentResearchConsumerError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _unique_strings(
    value: object,
    code: str,
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    _require(isinstance(value, list), code)
    rows = tuple(str(item).strip() for item in value)
    _require(
        (allow_empty or bool(rows))
        and all(rows)
        and len(rows) == len(set(rows)),
        code,
    )
    return rows


def _alias(prefix: str, identity: Mapping[str, Any]) -> str:
    return f"{prefix}::{canonical_digest(identity)[:16].upper()}"


def load_current_research_consumer_policy(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    expected = {
        "schema_version",
        "status",
        "reviewed_source_policy",
        "cell_contracts",
        "numeric_fact_selection",
        "model_input_contract",
        "model_output_contract",
        "research_context_contract",
        "authority",
    }
    _require(set(payload) == expected, "research_consumer_policy_fields_invalid")
    _require(
        payload.get("schema_version")
        == CURRENT_RESEARCH_CONSUMER_POLICY_SCHEMA_VERSION,
        "research_consumer_policy_schema_invalid",
    )
    _require(
        payload.get("status")
        == "provider_neutral_reviewed_evidence_numeric_relation_and_context_consumer",
        "research_consumer_policy_status_invalid",
    )
    source_policy = _mapping(
        payload.get("reviewed_source_policy"),
        "research_consumer_source_policy_invalid",
    )
    _require(
        set(source_policy)
        == {
            "allowed_source_types",
            "allowed_source_tiers",
            "earnings_call_transcript_constraints",
        },
        "research_consumer_source_policy_invalid",
    )
    source_types = _unique_strings(
        source_policy.get("allowed_source_types"),
        "research_consumer_source_types_invalid",
    )
    source_tiers = _unique_strings(
        source_policy.get("allowed_source_tiers"),
        "research_consumer_source_tiers_invalid",
    )
    transcript = _mapping(
        source_policy.get("earnings_call_transcript_constraints"),
        "research_consumer_transcript_policy_invalid",
    )
    _require(
        dict(transcript)
        == {
            "required_source_tier": "official_hosted_management_call_transcript",
            "reviewed_pack_only": True,
            "open_retrieval_source_type_expansion": False,
            "automatic_numeric_fact_promotion": False,
        }
        and "EARNINGS_CALL_TRANSCRIPT" in source_types
        and "official_hosted_management_call_transcript" in source_tiers,
        "research_consumer_transcript_policy_invalid",
    )
    raw_cells = payload.get("cell_contracts")
    _require(
        isinstance(raw_cells, list) and len(raw_cells) == 5,
        "research_consumer_cell_contracts_invalid",
    )
    cell_ids: set[str] = set()
    primary_slots: set[str] = set()
    cells: list[dict[str, Any]] = []
    cell_fields = {
        "cell_id",
        "title_zh",
        "primary_slot_id",
        "supplemental_context_slot_ids",
        "maximum_evidence_items",
        "maximum_numeric_facts",
    }
    for raw in raw_cells:
        row = _mapping(raw, "research_consumer_cell_contract_invalid")
        _require(
            set(row) == cell_fields,
            "research_consumer_cell_contract_invalid",
        )
        cell_id = str(row.get("cell_id") or "").strip()
        title = str(row.get("title_zh") or "").strip()
        primary = str(row.get("primary_slot_id") or "").strip()
        supplemental = _unique_strings(
            row.get("supplemental_context_slot_ids"),
            "research_consumer_supplemental_slots_invalid",
            allow_empty=True,
        )
        max_evidence = int(row.get("maximum_evidence_items") or 0)
        max_numeric = int(row.get("maximum_numeric_facts") or 0)
        _require(
            cell_id
            and title
            and primary
            and cell_id not in cell_ids
            and primary not in primary_slots
            and primary not in supplemental
            and 1 <= max_evidence <= 20
            and 0 <= max_numeric <= 20,
            "research_consumer_cell_contract_invalid",
        )
        cell_ids.add(cell_id)
        primary_slots.add(primary)
        cells.append(
            {
                **dict(row),
                "supplemental_context_slot_ids": list(supplemental),
            }
        )
    numeric_selection = _mapping(
        payload.get("numeric_fact_selection"),
        "research_consumer_numeric_selection_policy_invalid",
    )
    _require(
        dict(numeric_selection)
        == {
            "strategy": "latest_period_and_same_basis_comparable_per_metric",
            "maximum_non_instant_periods_per_metric": 2,
            "deduplicate_request_identity": True,
            "preserve_source_request_and_period_role_lineage": True,
            "same_fiscal_period_comparison_required_for_year_over_year_language": True,
        },
        "research_consumer_numeric_selection_policy_invalid",
    )
    model_input = _mapping(
        payload.get("model_input_contract"),
        "research_consumer_model_input_policy_invalid",
    )
    _require(
        set(model_input)
        == {
            "maximum_user_message_chars",
            "maximum_evidence_excerpt_chars",
            "internal_ids_digests_request_lineage_and_citation_urls_hidden",
            "exact_source_visible_facts_and_numeric_values_preserved",
        }
        and 10000 <= int(model_input["maximum_user_message_chars"]) <= 80000
        and 400 <= int(model_input["maximum_evidence_excerpt_chars"]) <= 1600
        and model_input[
            "internal_ids_digests_request_lineage_and_citation_urls_hidden"
        ]
        is True
        and model_input["exact_source_visible_facts_and_numeric_values_preserved"]
        is True,
        "research_consumer_model_input_policy_invalid",
    )
    output = _mapping(
        payload.get("model_output_contract"),
        "research_consumer_model_output_policy_invalid",
    )
    output_fields = {
        "payload_schema_version",
        "model_owned_top_level_fields",
        "model_owned_cell_fields",
        "harness_injected_envelope_fields",
        "harness_injected_cell_fields",
        "allowed_judgment_statuses",
        "allowed_confidence_bases",
        "allowed_evidence_use_roles",
        "allowed_inference_authorities",
        "allowed_wwc_directions",
        "maximum_atom_chars",
        "maximum_wwc_observable_chars",
        "maximum_wwc_horizon_chars",
        "maximum_wwc_evidence_route_chars",
        "digits_currency_units_dates_and_citations_forbidden_in_model_prose",
        "structured_refs_required",
    }
    _require(
        set(output) == output_fields,
        "research_consumer_model_output_policy_invalid",
    )
    statuses = _unique_strings(
        output.get("allowed_judgment_statuses"),
        "research_consumer_judgment_statuses_invalid",
    )
    confidence = _unique_strings(
        output.get("allowed_confidence_bases"),
        "research_consumer_confidence_bases_invalid",
    )
    directions = _unique_strings(
        output.get("allowed_wwc_directions"),
        "research_consumer_wwc_directions_invalid",
    )
    evidence_use_roles = _unique_strings(
        output.get("allowed_evidence_use_roles"),
        "research_consumer_evidence_use_roles_invalid",
    )
    inference_authorities = _unique_strings(
        output.get("allowed_inference_authorities"),
        "research_consumer_inference_authorities_invalid",
    )
    model_top_fields = _unique_strings(
        output.get("model_owned_top_level_fields"),
        "research_consumer_model_top_fields_invalid",
    )
    model_cell_fields = _unique_strings(
        output.get("model_owned_cell_fields"),
        "research_consumer_model_cell_fields_invalid",
    )
    harness_envelope_fields = _unique_strings(
        output.get("harness_injected_envelope_fields"),
        "research_consumer_harness_envelope_fields_invalid",
    )
    harness_cell_fields = _unique_strings(
        output.get("harness_injected_cell_fields"),
        "research_consumer_harness_cell_fields_invalid",
    )
    _require(
        output.get("payload_schema_version")
        == CURRENT_RESEARCH_JUDGMENT_SCHEMA_VERSION
        and set(model_top_fields) == {"cells"}
        and set(model_cell_fields)
        == {
            "cell_id",
            "judgment_status",
            "confidence_basis",
            "inference_authority",
            "evidence_uses",
            "numeric_refs",
            "numeric_relation_refs",
            "method_step_refs",
            "graph_edge_refs",
            "thesis_atom",
            "mechanism_atom",
            "counterargument_atom",
            "what_would_change",
        }
        and set(harness_envelope_fields)
        == {"schema_version", "research_input_digest"}
        and set(harness_cell_fields)
        == {"remaining_gap_refs", "context_consumption_receipt"}
        and set(statuses)
        == {"supported", "bounded_support", "mixed", "insufficient_evidence"}
        and set(evidence_use_roles) == {"support", "limit", "context"}
        and set(inference_authorities)
        == {"directly_supported", "bounded_inference", "not_inferable"}
        and bool(confidence)
        and bool(directions)
        and 80 <= int(output["maximum_atom_chars"]) <= 1000
        and 40 <= int(output["maximum_wwc_observable_chars"]) <= 600
        and 20 <= int(output["maximum_wwc_horizon_chars"]) <= 240
        and 40 <= int(output["maximum_wwc_evidence_route_chars"]) <= 400
        and output["digits_currency_units_dates_and_citations_forbidden_in_model_prose"]
        is True
        and output["structured_refs_required"] is True,
        "research_consumer_model_output_policy_invalid",
    )
    _require(
        isinstance(payload.get("authority"), Mapping)
        and dict(payload["authority"]) == _AUTHORITY,
        "research_consumer_authority_invalid",
    )
    try:
        context_contract = load_research_context_contract(
            _mapping(
                payload.get("research_context_contract"),
                "research_context_contract_invalid",
            )
        )
    except ResearchContextError as exc:
        raise CurrentResearchConsumerError(exc.code) from exc
    return {
        **deepcopy(dict(payload)),
        "reviewed_source_policy": {
            **deepcopy(dict(source_policy)),
            "allowed_source_types": list(source_types),
            "allowed_source_tiers": list(source_tiers),
        },
        "cell_contracts": cells,
        "model_output_contract": {
            **deepcopy(dict(output)),
            "allowed_judgment_statuses": list(statuses),
            "allowed_confidence_bases": list(confidence),
            "allowed_evidence_use_roles": list(evidence_use_roles),
            "allowed_inference_authorities": list(inference_authorities),
            "allowed_wwc_directions": list(directions),
        },
        "research_context_contract": context_contract,
    }


def _evidence_card(item: Mapping[str, Any], *, case_key: str) -> dict[str, Any]:
    source = _mapping(
        item.get("source"), "research_consumer_evidence_source_missing"
    )
    bindings = item.get("slot_bindings")
    _require(
        str(item.get("case_key") or "").upper() == case_key
        and
        item.get("writer_citable") is True
        and item.get("causal_attribution_authorized") is False
        and item.get("disposition")
        in {
            "accepted_direct_source_evidence",
            "accepted_bounded_context_evidence",
        }
        and isinstance(bindings, list)
        and bool(bindings),
        "research_consumer_evidence_boundary_invalid",
    )
    source_ticker = str(source.get("evidence_owner_ticker") or "").strip().upper()
    _require(source_ticker, "research_consumer_evidence_owner_missing")
    alias = _alias(
        "EV",
        {
            "case_key": case_key,
            "target_id": item.get("target_id"),
            "evidence_item_digest": item.get("evidence_item_digest"),
        },
    )
    slot_rows = []
    for raw in bindings:
        binding = _mapping(
            raw, "research_consumer_evidence_slot_binding_invalid"
        )
        slot_id = str(binding.get("slot_id") or "").strip()
        business = str(binding.get("business_meaning_zh") or "").strip()
        boundary = str(binding.get("claim_boundary_zh") or "").strip()
        facets = _unique_strings(
            binding.get("facet_ids"),
            "research_consumer_evidence_facets_invalid",
        )
        _require(
            slot_id and business and boundary,
            "research_consumer_evidence_slot_binding_invalid",
        )
        slot_rows.append(
            {
                "slot_id": slot_id,
                "facet_ids": list(facets),
                "business_meaning_zh": business,
                "claim_boundary_zh": boundary,
            }
        )
    return {
        "evidence_ref": alias,
        "target_id": str(item.get("target_id") or ""),
        "source_record_id": str(item.get("source_record_id") or ""),
        "evidence_role": str(item.get("evidence_role") or ""),
        "evidence_owner_ticker": source_ticker,
        "source_type": str(source.get("source_type") or ""),
        "source_tier": str(source.get("source_tier") or ""),
        "source_url": str(source.get("source_url") or ""),
        "publication_date": str(item.get("publication_date") or ""),
        "source_reporting_period_end": str(
            item.get("source_reporting_period_end") or ""
        ),
        "research_as_of": str(item.get("research_as_of") or ""),
        "relationship_directions": list(
            item.get("relationship_directions") or ()
        ),
        "slot_bindings": slot_rows,
        "numeric_use_boundary": str(item.get("numeric_use_boundary") or ""),
        "source_visible_fact_excerpt": str(
            source.get("reviewed_source_excerpt") or ""
        ).strip(),
        "excerpt_truncated": bool(source.get("excerpt_truncated")),
        "evidence_item_digest": str(item.get("evidence_item_digest") or ""),
        "source_text_digest": str(source.get("source_text_digest") or ""),
    }


def _validate_evidence_source(
    card: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    research_as_of: str,
) -> None:
    source_policy = policy["reviewed_source_policy"]
    _require(
        card.get("source_type") in set(source_policy["allowed_source_types"])
        and card.get("source_tier") in set(source_policy["allowed_source_tiers"]),
        "research_consumer_reviewed_source_not_allowed",
    )
    _require(
        str(card.get("publication_date") or "") <= research_as_of
        and str(card.get("research_as_of") or "") == research_as_of,
        "research_consumer_evidence_temporal_boundary_invalid",
    )
    _require(
        card.get("evidence_owner_ticker")
        and card.get("source_visible_fact_excerpt")
        and card.get("source_url"),
        "research_consumer_evidence_source_incomplete",
    )
    if card.get("source_type") == "EARNINGS_CALL_TRANSCRIPT":
        transcript = source_policy["earnings_call_transcript_constraints"]
        _require(
            card.get("source_tier") == transcript["required_source_tier"]
            and str(card.get("source_url") or "").startswith("https://"),
            "research_consumer_transcript_source_invalid",
        )


def _numeric_signature(fact: Mapping[str, Any]) -> dict[str, Any]:
    # A first-quarter observation can legitimately be exposed by the S2 mart as
    # both ``quarter_discrete`` and ``fiscal_ytd``.  Those rows have the same
    # company, metric, period boundary, value and source authority.  Keeping the
    # request/period-role labels in the semantic identity would make one
    # economic fact look like multiple independent facts to the model.  The
    # labels remain lineage below, but do not split the S3 fact card.
    return {
        "ticker": fact.get("ticker"),
        "metric_id": fact.get("metric_id"),
        "value_decimal": fact.get("value_decimal"),
        "unit": fact.get("unit"),
        "period_start": fact.get("period_start"),
        "period_end": fact.get("period_end"),
        "fiscal_year": fact.get("fiscal_year"),
        "fiscal_period": fact.get("fiscal_period"),
        "research_as_of": fact.get("research_as_of"),
        "authority_mode": fact.get("authority_mode"),
        "source_observation_ids": sorted(fact.get("source_observation_ids") or ()),
        "source_digests": sorted(fact.get("source_digests") or ()),
    }


def _numeric_cards(
    controlled_plan: Mapping[str, Any],
    *,
    case_key: str,
    research_as_of: str,
    allowed_tickers: set[str],
) -> tuple[list[dict[str, Any]], dict[str, set[str]]]:
    grouped: dict[str, dict[str, Any]] = {}
    slots_by_alias: dict[str, set[str]] = {}
    for result in controlled_plan.get("request_results") or ():
        query_plan = _mapping(
            result.get("query_plan"), "research_consumer_query_plan_missing"
        )
        lanes = query_plan.get("lanes")
        _require(
            isinstance(lanes, list) and bool(lanes),
            "research_consumer_query_plan_lanes_missing",
        )
        slot_ids = {
            str(lane.get("slot_id") or "")
            for lane in lanes
            if isinstance(lane, Mapping)
        }
        _require(
            "" not in slot_ids,
            "research_consumer_query_plan_slot_invalid",
        )
        request_id = str(
            _mapping(
                result.get("request"), "research_consumer_request_missing"
            ).get("request_id")
            or ""
        )
        for execution in result.get("typed_fact_results") or ():
            for raw_fact in execution.get("facts") or ():
                fact = _mapping(raw_fact, "research_consumer_numeric_fact_invalid")
                _require(
                    fact.get("schema_version") == "fin_ia_numeric_fact_v1_0"
                    and fact.get("numeric_fact_authority") is True
                    and str(fact.get("ticker") or "").upper()
                    in allowed_tickers
                    and str(fact.get("research_as_of") or "") == research_as_of,
                    "research_consumer_numeric_fact_boundary_invalid",
                )
                signature = _numeric_signature(fact)
                alias = _alias("NUM", signature)
                slots_by_alias.setdefault(alias, set()).update(slot_ids)
                if alias not in grouped:
                    grouped[alias] = {
                        "numeric_ref": alias,
                        **signature,
                        "unit_family": fact.get("unit_family"),
                        "accession_numbers": list(
                            fact.get("accession_numbers") or ()
                        ),
                        "accepted_at": fact.get("accepted_at"),
                        "citation_urls": list(fact.get("citation_urls") or ()),
                        "formula_trace": deepcopy(fact.get("formula_trace")),
                        "source_period_roles": [],
                        "source_numeric_fact_ids": [],
                        "source_fact_request_ids": [],
                    }
                grouped[alias]["source_period_roles"].append(
                    str(fact.get("period_role") or "")
                )
                grouped[alias]["source_numeric_fact_ids"].append(
                    str(fact.get("numeric_fact_id") or "")
                )
                grouped[alias]["source_fact_request_ids"].append(request_id)
    cards = []
    for alias in sorted(grouped):
        row = grouped[alias]
        row["source_numeric_fact_ids"] = sorted(
            set(row["source_numeric_fact_ids"])
        )
        row["source_period_roles"] = sorted(set(row["source_period_roles"]))
        row["source_fact_request_ids"] = sorted(
            set(row["source_fact_request_ids"])
        )
        row["eligible_slot_ids"] = sorted(slots_by_alias[alias])
        cards.append(row)
    return cards, slots_by_alias


def _select_numeric_cards(
    cards: Sequence[Mapping[str, Any]],
    *,
    policy: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selection = policy["numeric_fact_selection"]
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for card in cards:
        groups.setdefault(
            (str(card.get("ticker") or ""), str(card.get("metric_id") or "")),
            [],
        ).append(card)
    selected_refs: set[str] = set()
    decisions: list[dict[str, Any]] = []
    for (ticker, metric_id), rows in sorted(groups.items()):
        instant = [
            row for row in rows if "instant" in set(row["source_period_roles"])
        ]
        quarter = [
            row
            for row in rows
            if "quarter_discrete" in set(row["source_period_roles"])
        ]
        fiscal_year = [
            row
            for row in rows
            if "fiscal_year" in set(row["source_period_roles"])
        ]
        fallback_ytd = [
            row
            for row in rows
            if "fiscal_ytd" in set(row["source_period_roles"])
        ]
        chosen: list[Mapping[str, Any]] = []
        if instant:
            chosen.append(max(instant, key=lambda row: str(row["period_end"])))
        else:
            if quarter:
                current = max(quarter, key=lambda row: str(row["period_end"]))
                chosen.append(current)
                comparable = [
                    row
                    for row in quarter
                    if row.get("fiscal_period") == current.get("fiscal_period")
                    and isinstance(current.get("fiscal_year"), int)
                    and row.get("fiscal_year") == int(current["fiscal_year"]) - 1
                ]
                if comparable:
                    chosen.append(
                        max(comparable, key=lambda row: str(row["period_end"]))
                    )
            if not quarter and fallback_ytd:
                current = max(
                    fallback_ytd, key=lambda row: str(row["period_end"])
                )
                chosen.append(current)
                comparable = [
                    row
                    for row in fallback_ytd
                    if row.get("fiscal_period") == current.get("fiscal_period")
                    and isinstance(current.get("fiscal_year"), int)
                    and row.get("fiscal_year") == int(current["fiscal_year"]) - 1
                ]
                if comparable:
                    chosen.append(
                        max(comparable, key=lambda row: str(row["period_end"]))
                    )
            if fiscal_year and len(chosen) < int(
                selection["maximum_non_instant_periods_per_metric"]
            ):
                annual = max(fiscal_year, key=lambda row: str(row["period_end"]))
                if annual.get("numeric_ref") not in {
                    row.get("numeric_ref") for row in chosen
                }:
                    chosen.append(annual)
        maximum = int(selection["maximum_non_instant_periods_per_metric"])
        if not instant:
            chosen = chosen[:maximum]
        refs = [str(row["numeric_ref"]) for row in chosen]
        selected_refs.update(refs)
        decisions.append(
            {
                "ticker": ticker,
                "metric_id": metric_id,
                "available_semantic_fact_count": len(rows),
                "selected_numeric_refs": refs,
                "omitted_semantic_fact_count": len(rows) - len(refs),
            }
        )
    selected = [deepcopy(dict(row)) for row in cards if row["numeric_ref"] in selected_refs]
    selected.sort(key=lambda row: str(row["numeric_ref"]))
    return selected, {
        "strategy": selection["strategy"],
        "semantic_unique_fact_count_before_period_selection": len(cards),
        "model_visible_numeric_fact_count": len(selected),
        "omitted_but_preserved_in_controlled_plan_count": len(cards) - len(selected),
        "decisions": decisions,
    }


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _numeric_relation_cards(
    cards: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str], list[Mapping[str, Any]]] = {}
    for card in cards:
        roles = set(card.get("source_period_roles") or ())
        comparable_role = next(
            (
                role
                for role in ("quarter_discrete", "fiscal_ytd")
                if role in roles
            ),
            None,
        )
        fiscal_period = str(card.get("fiscal_period") or "")
        if comparable_role and fiscal_period:
            groups.setdefault(
                (
                    str(card.get("ticker") or ""),
                    str(card.get("metric_id") or ""),
                    comparable_role,
                    fiscal_period,
                ),
                [],
            ).append(card)
    output: list[dict[str, Any]] = []
    for (ticker, metric_id, period_role, fiscal_period), rows in sorted(
        groups.items()
    ):
        by_year = {
            int(row["fiscal_year"]): row
            for row in rows
            if isinstance(row.get("fiscal_year"), int)
        }
        if len(by_year) < 2:
            continue
        current_year = max(by_year)
        if current_year - 1 not in by_year:
            continue
        current = by_year[current_year]
        prior = by_year[current_year - 1]
        if current.get("unit") != prior.get("unit"):
            continue
        current_value = Decimal(str(current["value_decimal"]))
        prior_value = Decimal(str(prior["value_decimal"]))
        absolute_change = current_value - prior_value
        percent_change = None
        if prior_value != 0:
            with localcontext() as context:
                context.prec = 34
                percent_change = absolute_change / prior_value * Decimal("100")
        direction = (
            "increase"
            if absolute_change > 0
            else "decrease" if absolute_change < 0 else "unchanged"
        )
        identity = {
            "ticker": ticker,
            "metric_id": metric_id,
            "period_role": period_role,
            "fiscal_period": fiscal_period,
            "current_numeric_ref": current["numeric_ref"],
            "comparison_numeric_ref": prior["numeric_ref"],
        }
        row = {
            "numeric_relation_ref": _alias("REL", identity),
            "relation_type": (
                "same_fiscal_quarter_year_over_year"
                if period_role == "quarter_discrete"
                else "same_fiscal_ytd_year_over_year"
            ),
            **identity,
            "unit": current["unit"],
            "current_period_start": current["period_start"],
            "current_period_end": current["period_end"],
            "comparison_period_start": prior["period_start"],
            "comparison_period_end": prior["period_end"],
            "direction": direction,
            "absolute_change_decimal": _decimal_text(absolute_change),
            "percent_change_decimal": (
                _decimal_text(percent_change) if percent_change is not None else None
            ),
            "percentage_point_change_decimal": (
                _decimal_text(absolute_change)
                if str(current.get("unit")) == "percent"
                else None
            ),
            "authority_mode": "deterministically_compiled_same_basis_relation",
        }
        output.append(row)
    return output


def _gap_cards(
    evidence_pack: Mapping[str, Any],
) -> list[dict[str, Any]]:
    output = []
    for raw in evidence_pack.get("residual_gaps") or ():
        row = _mapping(raw, "research_consumer_gap_invalid")
        slot_id = str(row.get("slot_id") or "").strip()
        gap_code = str(row.get("gap_code") or "").strip()
        _require(slot_id and gap_code, "research_consumer_gap_invalid")
        identity = {
            "gap_id": row.get("gap_id"),
            "slot_id": slot_id,
            "facet_id": row.get("facet_id"),
            "gap_code": gap_code,
        }
        output.append(
            {
                "gap_ref": _alias("GAP", identity),
                "slot_id": slot_id,
                "facet_id": str(row.get("facet_id") or ""),
                "gap_code": gap_code,
                "business_reason_zh": str(
                    row.get("business_reason_zh") or ""
                ),
                "supplement_direction_zh": str(
                    row.get("supplement_direction_zh") or ""
                ),
            }
        )
    return sorted(output, key=lambda row: row["gap_ref"])


def compile_current_research_input(
    *,
    policy: Mapping[str, Any],
    evidence_pack: Mapping[str, Any],
    controlled_plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Compile only reviewed Evidence and authoritative NumericFacts for S3."""

    policy = load_current_research_consumer_policy(policy)
    objective = _mapping(
        controlled_plan.get("objective"), "research_consumer_objective_missing"
    )
    case_key = str(objective.get("case_key") or "").strip().upper()
    research_as_of = str(objective.get("research_as_of") or "")
    _require(
        controlled_plan.get("status")
        == "controlled_research_plan_zero_call_executed"
        and case_key
        and evidence_pack.get("case_key") == case_key
        and research_as_of,
        "research_consumer_input_boundary_invalid",
    )
    rejected_items = evidence_pack.get("rejected_items") or []
    _require(
        isinstance(rejected_items, list)
        and all(
            isinstance(row, Mapping) and row.get("writer_citable") is False
            for row in rejected_items
        ),
        "research_consumer_rejected_item_boundary_invalid",
    )
    consumer_contract = _mapping(
        evidence_pack.get("consumer_contract"),
        "research_consumer_pack_contract_missing",
    )
    _require(
        consumer_contract.get("writer_may_consume_only_writer_citable_items")
        is True
        and consumer_contract.get("rejected_items_must_not_enter_prompt") is True
        and consumer_contract.get("residual_gaps_must_remain_visible") is True
        and consumer_contract.get(
            "exact_numeric_surface_must_be_source_visible_or_typed"
        )
        is True,
        "research_consumer_pack_contract_invalid",
    )
    evidence_cards = [
        _evidence_card(row, case_key=case_key)
        for row in evidence_pack.get("evidence_items") or ()
    ]
    _require(evidence_cards, "research_consumer_evidence_missing")
    for card in evidence_cards:
        _validate_evidence_source(
            card,
            policy=policy,
            research_as_of=research_as_of,
        )
    evidence_refs = [row["evidence_ref"] for row in evidence_cards]
    _require(
        len(evidence_refs) == len(set(evidence_refs)),
        "research_consumer_evidence_alias_collision",
    )
    allowed_numeric_tickers = {
        str(ticker).upper()
        for request in controlled_plan.get("compiled_plan", {}).get(
            "evidence_requests", ()
        )
        for ticker in request.get("target_entities", ())
    }
    allowed_numeric_tickers.add(case_key)
    all_numeric_cards, _ = _numeric_cards(
        controlled_plan,
        case_key=case_key,
        research_as_of=research_as_of,
        allowed_tickers=allowed_numeric_tickers,
    )
    numeric_cards, numeric_selection_summary = _select_numeric_cards(
        all_numeric_cards,
        policy=policy,
    )
    numeric_relation_cards = _numeric_relation_cards(numeric_cards)
    gap_cards = _gap_cards(evidence_pack)
    proposed = controlled_plan.get("compiled_plan", {}).get("planner_atoms") or []
    facet_to_atom = {
        str(row.get("facet_id") or ""): deepcopy(dict(row))
        for row in proposed
        if isinstance(row, Mapping)
    }
    selected_facets_by_slot: dict[str, list[str]] = {}
    for result in controlled_plan.get("request_results") or ():
        request = _mapping(
            result.get("request"), "research_consumer_request_missing"
        )
        for lane in result.get("query_plan", {}).get("lanes") or ():
            slot_id = str(lane.get("slot_id") or "")
            for facet_id in request.get("requested_facet_ids") or ():
                selected_facets_by_slot.setdefault(slot_id, []).append(
                    str(facet_id)
                )
    cells = []
    for contract in policy["cell_contracts"]:
        eligible_slots = {
            contract["primary_slot_id"],
            *contract["supplemental_context_slot_ids"],
        }
        cell_evidence = [
            row
            for row in evidence_cards
            if any(
                binding["slot_id"] in eligible_slots
                for binding in row["slot_bindings"]
            )
        ]
        cell_numeric = [
            row
            for row in numeric_cards
            if eligible_slots.intersection(row["eligible_slot_ids"])
        ]
        cell_numeric_refs = {row["numeric_ref"] for row in cell_numeric}
        cell_numeric_relations = [
            row
            for row in numeric_relation_cards
            if {
                row["current_numeric_ref"],
                row["comparison_numeric_ref"],
            }.issubset(cell_numeric_refs)
        ]
        cell_gaps = [
            row for row in gap_cards if row["slot_id"] in eligible_slots
        ]
        _require(
            len(cell_evidence) <= int(contract["maximum_evidence_items"])
            and len(cell_numeric) <= int(contract["maximum_numeric_facts"]),
            "research_consumer_cell_capacity_exceeded",
        )
        facets = sorted(
            {
                facet
                for slot_id in eligible_slots
                for facet in selected_facets_by_slot.get(slot_id, [])
            }
        )
        cells.append(
            {
                "cell_id": contract["cell_id"],
                "title_zh": contract["title_zh"],
                "primary_slot_id": contract["primary_slot_id"],
                "supplemental_context_slot_ids": list(
                    contract["supplemental_context_slot_ids"]
                ),
                "selected_planner_facets": facets,
                "planner_atoms": [facet_to_atom[facet] for facet in facets],
                "allowed_evidence_refs": [
                    row["evidence_ref"] for row in cell_evidence
                ],
                "allowed_numeric_refs": [
                    row["numeric_ref"] for row in cell_numeric
                ],
                "allowed_numeric_relation_refs": [
                    row["numeric_relation_ref"] for row in cell_numeric_relations
                ],
                "visible_gap_refs": [row["gap_ref"] for row in cell_gaps],
            }
        )
    visible_evidence_refs = {
        ref for cell in cells for ref in cell["allowed_evidence_refs"]
    }
    visible_numeric_refs = {
        ref for cell in cells for ref in cell["allowed_numeric_refs"]
    }
    visible_gap_refs = {ref for cell in cells for ref in cell["visible_gap_refs"]}
    visible_numeric_relation_refs = {
        ref for cell in cells for ref in cell["allowed_numeric_relation_refs"]
    }
    evidence_cards = [
        row for row in evidence_cards if row["evidence_ref"] in visible_evidence_refs
    ]
    numeric_cards = [
        row for row in numeric_cards if row["numeric_ref"] in visible_numeric_refs
    ]
    gap_cards = [row for row in gap_cards if row["gap_ref"] in visible_gap_refs]
    numeric_relation_cards = [
        row
        for row in numeric_relation_cards
        if row["numeric_relation_ref"] in visible_numeric_relation_refs
    ]
    case_identity = {
        "case_key": case_key,
        "subject_ticker": objective.get("subject_ticker"),
        "subject_legal_name": objective.get("subject_legal_name"),
        "research_as_of": research_as_of,
    }
    try:
        route_catalog = compile_evidence_request_route_catalog(
            context_contract=policy["research_context_contract"],
            controlled_plan=controlled_plan,
            gap_cards=gap_cards,
            objective=objective,
        )
        graph_packs = compile_graph_context_packs(
            context_contract=policy["research_context_contract"],
            case_identity=case_identity,
            cells=cells,
            evidence_cards=evidence_cards,
            numeric_cards=numeric_cards,
        )
        cells, context_receipts = bind_research_context_to_cells(
            context_contract=policy["research_context_contract"],
            cells=cells,
            graph_packs=graph_packs,
        )
    except ResearchContextError as exc:
        raise CurrentResearchConsumerError(exc.code) from exc
    unsigned = {
        "schema_version": CURRENT_RESEARCH_INPUT_SCHEMA_VERSION,
        "status": "current_reviewed_research_input_compiled",
        "case_identity": case_identity,
        "objective": deepcopy(dict(objective)),
        "plan_digest": controlled_plan.get("compiled_plan", {}).get(
            "plan_digest"
        ),
        "evidence_pack_binding": {
            "artifact_digest": evidence_pack.get("artifact_digest"),
            "pack_payload_digest": evidence_pack.get("pack_payload_digest"),
            "projection_digest": evidence_pack.get("projection_digest"),
        },
        "cells": cells,
        "evidence_cards": evidence_cards,
        "numeric_fact_cards": numeric_cards,
        "numeric_relation_cards": numeric_relation_cards,
        "residual_gap_cards": gap_cards,
        "evidence_request_route_catalog": route_catalog,
        "research_context_receipts": context_receipts,
        "input_selection_summary": {
            "reviewed_pack_evidence_count": len(
                evidence_pack.get("evidence_items") or ()
            ),
            "model_visible_evidence_count": len(evidence_cards),
            "reviewed_pack_gap_count": len(
                evidence_pack.get("residual_gaps") or ()
            ),
            "model_visible_gap_count": len(gap_cards),
            "model_visible_numeric_relation_count": len(numeric_relation_cards),
            "controlled_plan_numeric_fact_count_before_semantic_dedup": int(
                controlled_plan.get("summary", {}).get("numeric_fact_count") or 0
            ),
            **numeric_selection_summary,
        },
        "model_output_contract": deepcopy(policy["model_output_contract"]),
        "model_input_contract": deepcopy(policy["model_input_contract"]),
        "authority": deepcopy(policy["authority"]),
        "known_boundary": (
            "Only reviewed writer-citable Evidence, authoritative NumericFacts "
            "and declared residual gaps enter this S3 input. Retrieval candidates "
            "and rejected items are absent. Transcript Evidence is already reviewed "
            "material; it does not expand the S1 open-retrieval source whitelist or "
            "become S2 numeric authority."
        ),
    }
    return {**unsigned, "research_input_digest": canonical_digest(unsigned)}


def compile_current_research_messages(
    research_input: Mapping[str, Any],
    *,
    required_cell_ids: Sequence[str] | None = None,
    submission_transport: str = "json",
) -> tuple[dict[str, str], ...]:
    """Compile a bounded payload contract with explicit enums and authority.

    Source-visible facts are emitted once in an immutable catalog.  Each cell
    receives only a local interpretation view over those facts.  This preserves
    the cell boundary without duplicating long source excerpts for every use.
    """

    _require(
        submission_transport in {"json", "final_tool"},
        "research_consumer_submission_transport_invalid",
    )
    input_contract = research_input["model_input_contract"]
    maximum_excerpt = int(input_contract["maximum_evidence_excerpt_chars"])
    evidence_by_ref = {
        row["evidence_ref"]: row for row in research_input["evidence_cards"]
    }
    numeric_by_ref = {
        row["numeric_ref"]: row
        for row in research_input["numeric_fact_cards"]
    }
    numeric_relation_by_ref = {
        row["numeric_relation_ref"]: row
        for row in research_input["numeric_relation_cards"]
    }
    gap_by_ref = {
        row["gap_ref"]: row for row in research_input["residual_gap_cards"]
    }

    def visible_evidence_fact(ref: str) -> dict[str, Any]:
        row = evidence_by_ref[ref]
        excerpt = str(row["source_visible_fact_excerpt"])
        return {
            "evidence_ref": ref,
            "evidence_owner_ticker": row["evidence_owner_ticker"],
            "source_type": row["source_type"],
            "source_tier": row["source_tier"],
            "publication_date": row["publication_date"],
            "source_reporting_period_end": row[
                "source_reporting_period_end"
            ],
            "relationship_directions": row["relationship_directions"],
            "source_visible_fact_excerpt": excerpt[:maximum_excerpt],
            "excerpt_truncated": (
                bool(row["excerpt_truncated"])
                or len(excerpt) > maximum_excerpt
            ),
        }

    def visible_cell_evidence(
        ref: str, *, slot_ids: set[str]
    ) -> dict[str, Any]:
        row = evidence_by_ref[ref]
        bindings = [
            binding
            for binding in row["slot_bindings"]
            if binding["slot_id"] in slot_ids
        ]
        _require(
            bool(bindings),
            "research_consumer_cell_evidence_binding_missing",
        )
        return {
            "evidence_ref": ref,
            "business_meanings_zh": [
                binding["business_meaning_zh"] for binding in bindings
            ],
            "claim_boundaries_zh": [
                binding["claim_boundary_zh"] for binding in bindings
            ],
            "numeric_use_boundary": row["numeric_use_boundary"],
        }

    def visible_numeric(ref: str) -> dict[str, Any]:
        row = numeric_by_ref[ref]
        formula = row.get("formula_trace")
        visible_formula = None
        if isinstance(formula, Mapping):
            visible_formula = {
                key: deepcopy(formula[key])
                for key in ("formula", "operation", "input_metrics")
                if key in formula
            }
        return {
            key: deepcopy(row[key])
            for key in (
                "numeric_ref",
                "ticker",
                "metric_id",
                "value_decimal",
                "unit",
                "period_start",
                "period_end",
                "fiscal_year",
                "fiscal_period",
                "authority_mode",
            )
        } | {"formula_trace": visible_formula}

    all_cell_ids = [str(cell["cell_id"]) for cell in research_input["cells"]]
    selected_cell_ids = (
        tuple(all_cell_ids)
        if required_cell_ids is None
        else tuple(str(value) for value in required_cell_ids)
    )
    _require(
        bool(selected_cell_ids)
        and len(selected_cell_ids) == len(set(selected_cell_ids))
        and set(selected_cell_ids).issubset(all_cell_ids),
        "research_consumer_required_cell_scope_invalid",
    )
    selected_cell_id_set = set(selected_cell_ids)
    selected_cells = [
        cell
        for cell in research_input["cells"]
        if cell["cell_id"] in selected_cell_id_set
    ]
    visible_cells = []
    selected_evidence_refs: set[str] = set()
    selected_numeric_refs: set[str] = set()
    selected_numeric_relation_refs: set[str] = set()
    route_decisions = {
        row["gap_ref"]: row
        for row in research_input["evidence_request_route_catalog"][
            "gap_route_decisions"
        ]
    }
    for cell in selected_cells:
        slot_ids = {
            cell["primary_slot_id"],
            *cell["supplemental_context_slot_ids"],
        }
        selected_evidence_refs.update(cell["allowed_evidence_refs"])
        selected_numeric_refs.update(cell["allowed_numeric_refs"])
        selected_numeric_relation_refs.update(
            cell["allowed_numeric_relation_refs"]
        )
        method_pack = deepcopy(cell.get("role_method_pack"))
        graph_pack = deepcopy(cell["graph_context_pack"])
        visible_cells.append(
            {
                "cell_id": cell["cell_id"],
                "title_zh": cell["title_zh"],
                "selected_planner_facets": cell["selected_planner_facets"],
                "research_intents": sorted(
                    {
                        intent
                        for atom in cell["planner_atoms"]
                        for intent in atom.get("product_intents", ())
                    }
                ),
                "cell_evidence_views": [
                    visible_cell_evidence(ref, slot_ids=slot_ids)
                    for ref in cell["allowed_evidence_refs"]
                ],
                "allowed_numeric_refs": cell["allowed_numeric_refs"],
                "allowed_numeric_relation_refs": cell[
                    "allowed_numeric_relation_refs"
                ],
                "role_method_pack": method_pack,
                "graph_context_pack": graph_pack,
                "context_consumption_contract": deepcopy(
                    cell["context_consumption_contract"]
                ),
                "residual_gap_cards": [
                    {
                        **deepcopy(gap_by_ref[ref]),
                        "route_decision": deepcopy(route_decisions[ref]),
                    }
                    for ref in cell["visible_gap_refs"]
                ],
            }
        )
    contract = research_input["model_output_contract"]
    cell_payload_shape = {
        "cell_id": "one required cell_id",
        "judgment_status": "one listed judgment status",
        "confidence_basis": "one listed confidence basis",
        "inference_authority": (
            "directly_supported, bounded_inference or not_inferable"
        ),
        "evidence_uses": [
            {
                "evidence_ref": "one EV ref from this cell only",
                "use_role": "support, limit or context",
            }
        ],
        "numeric_refs": ["zero or more NUM refs from this cell only"],
        "numeric_relation_refs": [
            "zero or more REL refs from this cell; required for explicit year-over-year language"
        ],
        "method_step_refs": [
            "method steps actually used from this cell's RoleMethodPack"
        ],
        "graph_edge_refs": [
            "current GraphContextPack edges actually used; these remain context-only"
        ],
        "thesis_atom": "company-specific conclusion without digits",
        "mechanism_atom": "economic mechanism without digits",
        "counterargument_atom": "strongest bounded alternative without digits",
        "what_would_change": {
            "observable": "observable variable without digits",
            "direction": "one listed direction",
            "time_horizon": "bounded non-numeric horizon such as 后续披露期",
            "evidence_route": "where to verify it without a citation",
            "threshold_numeric_ref": (
                None if submission_transport == "json" else ""
            ),
        },
    }
    visible = {
        "case_identity": research_input["case_identity"],
        "research_question": research_input["objective"]["raw_question"],
        "evidence_fact_catalog": [
            visible_evidence_fact(row["evidence_ref"])
            for row in research_input["evidence_cards"]
            if row["evidence_ref"] in selected_evidence_refs
        ],
        "numeric_fact_catalog": [
            visible_numeric(row["numeric_ref"])
            for row in research_input["numeric_fact_cards"]
            if row["numeric_ref"] in selected_numeric_refs
        ],
        "numeric_relation_catalog": [
            deepcopy(row)
            for row in research_input["numeric_relation_cards"]
            if row["numeric_relation_ref"] in selected_numeric_relation_refs
        ],
        "cells": visible_cells,
        "research_context_injection_receipt": deepcopy(
            research_input["research_context_receipts"]
        ),
        "output_contract": {
            "schema_version": contract["payload_schema_version"],
            "required_cell_ids": [
                cell["cell_id"] for cell in selected_cells
            ],
            "allowed_judgment_statuses": contract[
                "allowed_judgment_statuses"
            ],
            "allowed_confidence_bases": contract[
                "allowed_confidence_bases"
            ],
            "allowed_evidence_use_roles": contract[
                "allowed_evidence_use_roles"
            ],
            "allowed_inference_authorities": contract[
                "allowed_inference_authorities"
            ],
            "allowed_wwc_directions": contract["allowed_wwc_directions"],
            "payload_shape": (
                {"cells": [cell_payload_shape]}
                if submission_transport == "json"
                else {"submit_research_judgment_arguments": cell_payload_shape}
            ),
        }
        | (
            {"submission_transport": "final_tool"}
            if submission_transport == "final_tool"
            else {}
        ),
        "rules": [
            (
                "Return one exact JSON object with only a cells field and no Markdown or commentary; the harness injects schema and input identity."
                if submission_transport == "json"
                else "Call the sole submit_research_judgment tool exactly once with the required cell fields; do not return a free-form answer."
            ),
            "Use every cell exactly once and only refs printed in that cell's local views or allowed numeric refs; use the immutable catalogs only to read the bound fact behind a local ref.",
            "List each Evidence ref at most once; use support for what it proves, limit for how it constrains the conclusion, and context only for bounded background.",
            "Cite the RoleMethodPack steps and current GraphContextPack edges actually used. A graph edge supplies scope/context only and never replaces reviewed Evidence.",
            "Residual gaps shown in each cell are authoritative and will be injected by the harness; do not repeat them in the payload, and do not write a conclusion that silently closes them.",
            "directly_supported permits only conclusions explicitly stated by current subject evidence; bounded_inference must use cautious language and preserve limiting Evidence or respect visible residual gaps; not_inferable must not assert the unavailable mechanism.",
            "Do not attribute group, segment, balance-sheet or upstream results to AI or Dell without direct subject-bound evidence; contemporaneous movement is not causation.",
            "Do not repeat or alter identities, dates, exact numbers, units, currencies or citations in prose; select structured refs instead.",
            "Use year-over-year or prior-year-quarter language only when selecting a same-basis REL ref and both of its NumericFact endpoints.",
            "Submit an EvidenceRequest only through a source class and route shown as requestable; an unavailable industry, commercial or market route must remain a typed gap.",
            "Do not infer an undisclosed threshold or claim a supply constraint is easing without directly bound allocation and timing evidence.",
        ],
    }
    user_content = json.dumps(
        visible,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    _require(
        len(user_content) <= int(input_contract["maximum_user_message_chars"]),
        "research_consumer_model_input_capacity_exceeded",
    )
    return (
        {
            "role": "system",
            "content": (
                "You are a financial research synthesis node. Separate direct "
                "evidence from bounded inference, preserve limiting evidence "
                "and declared gaps, and never turn contemporaneous movement "
                "into unsupported product or causal attribution."
            ),
        },
        {"role": "user", "content": user_content},
    )


def parse_current_research_output(content: str) -> dict[str, Any]:
    """Parse the model-owned payload; the harness owns the outer envelope."""

    value = _parse_exact_json_object(content)
    _require(
        set(value) == {"cells"} and isinstance(value.get("cells"), list),
        "research_consumer_payload_envelope_invalid",
    )
    return value


def _parse_exact_json_object(content: str) -> dict[str, Any]:
    text = str(content or "").strip()
    _require(bool(text), "research_consumer_output_empty")
    _require(
        not text.startswith("```") and not text.endswith("```"),
        "research_consumer_output_not_exact_json",
    )
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CurrentResearchConsumerError(
            "research_consumer_output_json_invalid"
        ) from exc
    _require(isinstance(value, dict), "research_consumer_output_not_object")
    return value


def _validate_model_text(
    value: object,
    *,
    maximum: int,
    code: str,
    minimum: int = 12,
) -> str:
    text = str(value or "").strip()
    _require(
        minimum <= len(text) <= maximum
        and not _DIGIT_OR_FINANCIAL_SURFACE.search(text)
        and not _VERBAL_NUMERIC_SURFACE.search(text)
        and not _ALIAS_IN_PROSE.search(text)
        and "http://" not in text.casefold()
        and "https://" not in text.casefold(),
        code,
    )
    return text


def validate_current_research_output(
    payload: Mapping[str, Any],
    *,
    research_input: Mapping[str, Any],
    required_cell_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Validate a model-owned payload and inject the local trusted envelope."""

    contract = research_input["model_output_contract"]
    _require(
        set(payload) == set(contract["model_owned_top_level_fields"])
        and isinstance(payload.get("cells"), list),
        "research_consumer_payload_envelope_invalid",
    )
    all_input_cells = {
        str(row["cell_id"]): row for row in research_input["cells"]
    }
    selected_cell_ids = (
        tuple(all_input_cells)
        if required_cell_ids is None
        else tuple(str(value) for value in required_cell_ids)
    )
    _require(
        bool(selected_cell_ids)
        and len(selected_cell_ids) == len(set(selected_cell_ids))
        and set(selected_cell_ids).issubset(all_input_cells),
        "research_consumer_required_cell_scope_invalid",
    )
    input_cells = {
        cell_id: all_input_cells[cell_id] for cell_id in selected_cell_ids
    }
    relation_by_ref = {
        str(row["numeric_relation_ref"]): row
        for row in research_input["numeric_relation_cards"]
    }
    raw_cells = payload["cells"]
    output_cells = {
        str(row.get("cell_id") or ""): row
        for row in raw_cells
        if isinstance(row, Mapping)
    }
    _require(
        len(output_cells) == len(raw_cells)
        and set(output_cells) == set(input_cells),
        "research_consumer_output_cell_coverage_invalid",
    )
    cell_fields = set(contract["model_owned_cell_fields"])
    use_roles = set(contract["allowed_evidence_use_roles"])
    inference_authorities = set(contract["allowed_inference_authorities"])
    validated = []
    for cell_id in input_cells:
        raw = output_cells[cell_id]
        _require(
            set(raw) == cell_fields,
            "research_consumer_output_cell_fields_invalid",
        )
        status = str(raw.get("judgment_status") or "")
        confidence = str(raw.get("confidence_basis") or "")
        inference = str(raw.get("inference_authority") or "")
        _require(
            status in set(contract["allowed_judgment_statuses"])
            and confidence in set(contract["allowed_confidence_bases"])
            and inference in inference_authorities,
            "research_consumer_output_enum_invalid",
        )
        raw_uses = raw.get("evidence_uses")
        _require(
            isinstance(raw_uses, list),
            "research_consumer_evidence_uses_invalid",
        )
        evidence_uses = []
        seen_evidence: set[str] = set()
        for raw_use in raw_uses:
            use = _mapping(
                raw_use, "research_consumer_evidence_use_invalid"
            )
            ref = str(use.get("evidence_ref") or "")
            role = str(use.get("use_role") or "")
            _require(
                set(use) == {"evidence_ref", "use_role"}
                and ref in set(input_cells[cell_id]["allowed_evidence_refs"])
                and ref not in seen_evidence
                and role in use_roles,
                "research_consumer_evidence_use_invalid",
            )
            seen_evidence.add(ref)
            evidence_uses.append({"evidence_ref": ref, "use_role": role})
        numeric = _unique_strings(
            raw.get("numeric_refs"),
            "research_consumer_numeric_refs_invalid",
            allow_empty=True,
        )
        numeric_relations = _unique_strings(
            raw.get("numeric_relation_refs"),
            "research_consumer_numeric_relation_refs_invalid",
            allow_empty=True,
        )
        method_steps = _unique_strings(
            raw.get("method_step_refs"),
            "research_consumer_method_step_refs_invalid",
            allow_empty=True,
        )
        graph_edges = _unique_strings(
            raw.get("graph_edge_refs"),
            "research_consumer_graph_edge_refs_invalid",
            allow_empty=True,
        )
        gaps = tuple(input_cells[cell_id]["visible_gap_refs"])
        _require(
            set(numeric).issubset(
                input_cells[cell_id]["allowed_numeric_refs"]
            ),
            "research_consumer_output_ref_boundary_invalid",
        )
        _require(
            set(numeric_relations).issubset(
                input_cells[cell_id]["allowed_numeric_relation_refs"]
            )
            and all(
                {
                    relation_by_ref[ref]["current_numeric_ref"],
                    relation_by_ref[ref]["comparison_numeric_ref"],
                }.issubset(numeric)
                for ref in numeric_relations
            ),
            "research_consumer_numeric_relation_boundary_invalid",
        )
        method_pack = input_cells[cell_id].get("role_method_pack")
        allowed_method_steps = {
            str(row["method_step_ref"])
            for row in (method_pack or {}).get("method_steps", ())
        }
        allowed_graph_edges = {
            str(row["graph_edge_ref"])
            for row in input_cells[cell_id]["graph_context_pack"]["edges"]
        }
        consumption_contract = input_cells[cell_id][
            "context_consumption_contract"
        ]
        _require(
            set(method_steps).issubset(allowed_method_steps)
            and len(method_steps)
            >= int(consumption_contract["minimum_method_step_refs"]),
            "research_consumer_method_consumption_invalid",
        )
        _require(
            set(graph_edges).issubset(allowed_graph_edges)
            and len(graph_edges)
            >= int(consumption_contract["minimum_graph_edge_refs"]),
            "research_consumer_graph_consumption_invalid",
        )
        supporting = [
            use["evidence_ref"]
            for use in evidence_uses
            if use["use_role"] == "support"
        ]
        limiting = [
            use["evidence_ref"]
            for use in evidence_uses
            if use["use_role"] == "limit"
        ]
        if status in {"supported", "bounded_support", "mixed"}:
            _require(
                bool(supporting),
                "research_consumer_supported_judgment_without_evidence",
            )
        if status == "insufficient_evidence" or inference == "not_inferable":
            _require(
                bool(gaps),
                "research_consumer_insufficient_judgment_without_gap",
            )
        _require(
            (status == "insufficient_evidence")
            == (inference == "not_inferable"),
            "research_consumer_inference_status_mismatch",
        )
        if inference == "bounded_inference":
            _require(
                bool(limiting) or bool(gaps),
                "research_consumer_bounded_inference_without_boundary",
            )
        if status == "mixed":
            _require(
                bool(limiting) or bool(gaps),
                "research_consumer_mixed_judgment_without_boundary",
            )
        validated_text = {
            field: _validate_model_text(
                raw.get(field),
                maximum=int(contract["maximum_atom_chars"]),
                code=f"research_consumer_{field}_invalid",
            )
            for field in _MODEL_TEXT_FIELDS
        }
        if any(_YEAR_OVER_YEAR_SURFACE.search(text) for text in validated_text.values()):
            _require(
                bool(numeric_relations),
                "research_consumer_year_over_year_without_same_basis_relation",
            )
        wwc = _mapping(
            raw.get("what_would_change"),
            "research_consumer_wwc_invalid",
        )
        _require(
            set(wwc)
            == {
                "observable",
                "direction",
                "time_horizon",
                "evidence_route",
                "threshold_numeric_ref",
            }
            and wwc.get("direction") in set(
                contract["allowed_wwc_directions"]
            ),
            "research_consumer_wwc_invalid",
        )
        threshold = wwc.get("threshold_numeric_ref")
        _require(
            threshold is None or threshold in set(numeric),
            "research_consumer_wwc_threshold_ref_invalid",
        )
        validated_wwc = {
            "observable": _validate_model_text(
                wwc.get("observable"),
                maximum=int(contract["maximum_wwc_observable_chars"]),
                code="research_consumer_wwc_observable_invalid",
            ),
            "direction": str(wwc["direction"]),
            "time_horizon": _validate_model_text(
                wwc.get("time_horizon"),
                maximum=int(contract["maximum_wwc_horizon_chars"]),
                code="research_consumer_wwc_horizon_invalid",
                minimum=4,
            ),
            "evidence_route": _validate_model_text(
                wwc.get("evidence_route"),
                maximum=int(contract["maximum_wwc_evidence_route_chars"]),
                code="research_consumer_wwc_evidence_route_invalid",
            ),
            "threshold_numeric_ref": threshold,
        }
        validated.append(
            {
                "cell_id": cell_id,
                "judgment_status": status,
                "confidence_basis": confidence,
                "inference_authority": inference,
                "evidence_uses": evidence_uses,
                "numeric_refs": list(numeric),
                "numeric_relation_refs": list(numeric_relations),
                "method_step_refs": list(method_steps),
                "graph_edge_refs": list(graph_edges),
                "remaining_gap_refs": list(gaps),
                "context_consumption_receipt": {
                    "role_method_pack_id": (
                        method_pack["pack_id"] if method_pack else None
                    ),
                    "role_method_pack_digest": (
                        method_pack["pack_digest"] if method_pack else None
                    ),
                    "consumed_method_step_refs": list(method_steps),
                    "graph_context_digest": input_cells[cell_id][
                        "graph_context_pack"
                    ]["graph_context_digest"],
                    "consumed_graph_edge_refs": list(graph_edges),
                    "consumed_numeric_relation_refs": list(numeric_relations),
                },
                **validated_text,
                "what_would_change": validated_wwc,
            }
        )
    trusted = {
        "schema_version": contract["payload_schema_version"],
        "research_input_digest": research_input["research_input_digest"],
        "cells": validated,
    }
    return {
        **trusted,
        "judgment_output_digest": canonical_digest(trusted),
    }


def compile_current_research_deliverable(
    *,
    research_input: Mapping[str, Any],
    judgment_output: Mapping[str, Any],
    required_cell_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Render a typed evidence-use payload without inventing conclusions."""

    validated = validate_current_research_output(
        judgment_output,
        research_input=research_input,
        required_cell_ids=required_cell_ids,
    )
    evidence = {
        row["evidence_ref"]: row for row in research_input["evidence_cards"]
    }
    numeric = {
        row["numeric_ref"]: row
        for row in research_input["numeric_fact_cards"]
    }
    numeric_relations = {
        row["numeric_relation_ref"]: row
        for row in research_input["numeric_relation_cards"]
    }
    gaps = {
        row["gap_ref"]: row for row in research_input["residual_gap_cards"]
    }
    cell_contracts = {
        row["cell_id"]: row for row in research_input["cells"]
    }
    rendered_cells = []
    for row in validated["cells"]:
        rendered_cells.append(
            {
                **deepcopy(row),
                "title_zh": cell_contracts[row["cell_id"]]["title_zh"],
                "evidence_uses_rendered": [
                    {
                        **deepcopy(use),
                        "evidence": deepcopy(evidence[use["evidence_ref"]]),
                    }
                    for use in row["evidence_uses"]
                ],
                "numeric_facts": [
                    deepcopy(numeric[ref]) for ref in row["numeric_refs"]
                ],
                "numeric_relations": [
                    deepcopy(numeric_relations[ref])
                    for ref in row["numeric_relation_refs"]
                ],
                "remaining_gaps": [
                    deepcopy(gaps[ref])
                    for ref in row["remaining_gap_refs"]
                ],
            }
        )
    unsigned = {
        "schema_version": CURRENT_RESEARCH_DELIVERABLE_SCHEMA_VERSION,
        "status": "structured_workpaper_and_report_preview_compiled",
        "case_identity": deepcopy(research_input["case_identity"]),
        "research_question": research_input["objective"]["raw_question"],
        "research_input_digest": research_input["research_input_digest"],
        "judgment_output_digest": validated["judgment_output_digest"],
        "cells": rendered_cells,
        "rendering_authority": {
            "model_authored_judgment_fields": list(_MODEL_TEXT_FIELDS)
            + [
                "what_would_change",
                "inference_authority",
                "evidence_uses",
            ],
            "harness_rendered_surfaces": [
                "trusted_envelope",
                "case_identity",
                "source_visible_fact_excerpt",
                "numeric_facts",
                "numeric_relations",
                "citations",
                "periods",
                "units",
                "remaining_gaps",
            ],
            "harness_generated_research_conclusion": False,
            "qualified_human_review_required": True,
        },
        "known_boundary": (
            "This is a structured internal workpaper/report preview. Typed "
            "evidence use and inference authority reduce ambiguity but do not "
            "prove natural-model quality, causality, owner acceptance or "
            "release readiness."
        ),
    }
    return {**unsigned, "deliverable_digest": canonical_digest(unsigned)}


__all__ = [
    "CURRENT_RESEARCH_CONSUMER_POLICY_SCHEMA_VERSION",
    "CURRENT_RESEARCH_DELIVERABLE_SCHEMA_VERSION",
    "CURRENT_RESEARCH_INPUT_SCHEMA_VERSION",
    "CURRENT_RESEARCH_JUDGMENT_SCHEMA_VERSION",
    "CurrentResearchConsumerError",
    "compile_current_research_deliverable",
    "compile_current_research_input",
    "compile_current_research_messages",
    "load_current_research_consumer_policy",
    "parse_current_research_output",
    "validate_current_research_output",
]
