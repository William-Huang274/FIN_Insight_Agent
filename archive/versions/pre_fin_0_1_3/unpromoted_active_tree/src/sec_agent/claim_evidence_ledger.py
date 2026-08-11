from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping


CLAIM_EVIDENCE_LEDGER_SCHEMA_VERSION = "sec_agent_claim_evidence_ledger_v0.1"
TYPED_GAP_LEDGER_SCHEMA_VERSION = "sec_agent_typed_gap_ledger_v0.1"

CLAIM_STATUSES = {"supported", "weakly_supported", "contradicted", "gap_exposed"}
TYPED_GAP_TYPES = {
    "not_disclosed",
    "not_found",
    "parser_failed",
    "source_boundary_blocked",
    "period_gap",
    "unit_gap",
    "alias_gap",
    "commercial_gap",
    "conflict_gap",
    "staleness_gap",
    "coverage_gap",
}

GAP_TYPE_ALIASES = {
    "commercial_tracker_gap": "commercial_gap",
    "commercial_market_tracker_gap": "commercial_gap",
    "commercial_market_tracker_gap_after_public_source_check": "commercial_gap",
    "commercial_deferred": "commercial_gap",
    "commercial_data_required": "commercial_gap",
    "public_unavailable_gap": "not_found",
    "source_unavailable": "not_found",
    "exact_value_missing": "not_found",
    "parser_schema_gap": "parser_failed",
    "schema_gap": "parser_failed",
    "region_schema_gap": "parser_failed",
    "source_boundary_violation": "source_boundary_blocked",
    "source_boundary_blocked": "source_boundary_blocked",
    "missing_required_ticker_claim_card": "coverage_gap",
    "source_gap_without_second_pass": "coverage_gap",
    "operator_shard_failed": "coverage_gap",
    "context_available_exact_value_missing": "not_found",
    "conflict": "conflict_gap",
}


def build_evidence_governance_ledgers(state: Mapping[str, Any]) -> dict[str, Any]:
    """Build D1/D2 ledger projections from the current graph state."""
    typed_gap_ledger = build_typed_gap_ledger(state)
    claim_evidence_ledger = build_claim_evidence_ledger(
        state.get("verified_judgment_plan") if isinstance(state.get("verified_judgment_plan"), Mapping) else state.get("judgment_plan"),
        typed_gap_ledger=typed_gap_ledger,
        run_id=str(state.get("run_id") or ""),
        as_of_date=str(state.get("as_of_date") or ""),
    )
    return {
        "claim_evidence_ledger": claim_evidence_ledger,
        "typed_gap_ledger": typed_gap_ledger,
    }


def build_claim_evidence_ledger(
    judgment_plan: Mapping[str, Any] | None,
    *,
    typed_gap_ledger: Mapping[str, Any] | None = None,
    run_id: str = "",
    as_of_date: str = "",
) -> dict[str, Any]:
    judgment = judgment_plan if isinstance(judgment_plan, Mapping) else {}
    gaps = [dict(item) for item in (typed_gap_ledger or {}).get("gaps") or [] if isinstance(item, Mapping)]
    claims: list[dict[str, Any]] = []

    for index, item in enumerate(_mapping_rows(judgment.get("supported_claims")), start=1):
        claims.append(
            _claim_ledger_entry(
                item,
                index=index,
                run_id=run_id,
                as_of_date=as_of_date,
                default_status=_supported_claim_status(item),
                gap_rows=gaps,
            )
        )
    offset = len(claims)
    for index, item in enumerate(_mapping_rows(judgment.get("conflicts")), start=offset + 1):
        claims.append(
            _claim_ledger_entry(
                item,
                index=index,
                run_id=run_id,
                as_of_date=as_of_date,
                default_status="contradicted",
                gap_rows=gaps,
            )
        )
    offset = len(claims)
    for index, item in enumerate(_mapping_rows(judgment.get("unsupported_claims")), start=offset + 1):
        claims.append(
            _claim_ledger_entry(
                item,
                index=index,
                run_id=run_id,
                as_of_date=as_of_date,
                default_status="gap_exposed",
                gap_rows=gaps,
            )
        )

    validation = validate_claim_evidence_ledger({"claims": claims})
    return _sanitize_payload(
        {
            "schema_version": CLAIM_EVIDENCE_LEDGER_SCHEMA_VERSION,
            "policy": "durable_claim_evidence_ledger_projection_v0_1",
            "run_id": run_id,
            "as_of_date": as_of_date or _utc_date(),
            "claim_count": len(claims),
            "claims": claims,
            "summary": {
                "by_claim_status": _count_by_key(claims, "claim_status"),
                "by_claim_type": _count_by_key(claims, "claim_type"),
                "by_source_strength": _count_by_key(claims, "source_strength"),
                "supported_claim_count": len([row for row in claims if row.get("claim_status") == "supported"]),
                "weakly_supported_claim_count": len([row for row in claims if row.get("claim_status") == "weakly_supported"]),
                "contradicted_claim_count": len([row for row in claims if row.get("claim_status") == "contradicted"]),
                "gap_exposed_claim_count": len([row for row in claims if row.get("claim_status") == "gap_exposed"]),
                "memo_writer_eligible_claim_count": len(
                    [
                        row
                        for row in claims
                        if row.get("claim_status") == "supported" and row.get("supporting_evidence_ids")
                    ]
                ),
            },
            "validation": validation,
        }
    )


def validate_claim_evidence_ledger(payload: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    claims = _mapping_rows(payload.get("claims"))
    seen_ids: set[str] = set()
    for index, claim in enumerate(claims):
        claim_id = str(claim.get("claim_id") or "").strip()
        status = str(claim.get("claim_status") or "").strip()
        support_refs = _string_list(claim.get("supporting_evidence_ids"))
        contradict_refs = _string_list(claim.get("contradicting_evidence_ids"))
        if not claim_id:
            errors.append({"type": "claim_id_required", "index": index})
        elif claim_id in seen_ids:
            errors.append({"type": "duplicate_claim_id", "claim_id": claim_id})
        seen_ids.add(claim_id)
        if status not in CLAIM_STATUSES:
            errors.append({"type": "invalid_claim_status", "claim_id": claim_id, "claim_status": status})
        if not str(claim.get("claim_text") or "").strip():
            errors.append({"type": "claim_text_required", "claim_id": claim_id})
        if status == "supported" and not support_refs:
            errors.append({"type": "supported_claim_without_supporting_evidence", "claim_id": claim_id})
        if status == "weakly_supported" and not support_refs:
            warnings.append({"type": "weak_claim_without_supporting_evidence", "claim_id": claim_id})
        if status == "contradicted" and not contradict_refs:
            warnings.append({"type": "contradicted_claim_without_contradicting_evidence", "claim_id": claim_id})
        if not _string_list(claim.get("required_gate_results")):
            warnings.append({"type": "claim_required_gate_results_missing", "claim_id": claim_id})
    return {
        "schema_version": "sec_agent_claim_evidence_ledger_validation_v0.1",
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
    }


def build_typed_gap_ledger(state: Mapping[str, Any]) -> dict[str, Any]:
    rows = _gap_rows_from_state(state)
    visible_primary_tickers = _visible_primary_evidence_tickers_from_state(state)
    focus_tickers = _focus_tickers_from_state(state)
    gaps: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for index, row in enumerate(rows, start=1):
        if _route_scope_gap_is_non_blocking(row, visible_primary_tickers=visible_primary_tickers, focus_tickers=focus_tickers):
            continue
        entry = _typed_gap_entry(row, index=index)
        key = (
            str(entry.get("gap_id") or ""),
            str(entry.get("gap_type") or ""),
            str(entry.get("source_family") or ""),
            str(entry.get("ticker") or ""),
            str(entry.get("metric") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        gaps.append(entry)
    validation = validate_typed_gap_ledger({"gaps": gaps})
    return _sanitize_payload(
        {
            "schema_version": TYPED_GAP_LEDGER_SCHEMA_VERSION,
            "policy": "typed_gap_ledger_no_weak_proxy_fallback_v0_1",
            "gap_count": len(gaps),
            "gaps": gaps,
            "summary": {
                "by_gap_type": _count_by_key(gaps, "gap_type"),
                "by_raw_gap_type": _count_by_key(gaps, "raw_gap_type"),
                "by_source_family": _count_by_key(gaps, "source_family"),
                "by_repairability": _count_by_key(gaps, "repairability"),
                "commercial_gap_count": len([row for row in gaps if row.get("gap_type") == "commercial_gap"]),
                "parser_failed_gap_count": len([row for row in gaps if row.get("gap_type") == "parser_failed"]),
                "source_boundary_blocked_gap_count": len(
                    [row for row in gaps if row.get("gap_type") == "source_boundary_blocked"]
                ),
            },
            "validation": validation,
        }
    )


def validate_typed_gap_ledger(payload: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    gaps = _mapping_rows(payload.get("gaps"))
    seen_ids: set[str] = set()
    for index, gap in enumerate(gaps):
        gap_id = str(gap.get("gap_id") or "").strip()
        gap_type = str(gap.get("gap_type") or "").strip()
        if not gap_id:
            errors.append({"type": "gap_id_required", "index": index})
        elif gap_id in seen_ids:
            warnings.append({"type": "duplicate_gap_id", "gap_id": gap_id})
        seen_ids.add(gap_id)
        if gap_type not in TYPED_GAP_TYPES:
            errors.append({"type": "invalid_gap_type", "gap_id": gap_id, "gap_type": gap_type})
        if gap_type == "commercial_gap" and str(gap.get("treatment_action") or "") != "expose_commercial_gap_do_not_proxy":
            errors.append({"type": "commercial_gap_treatment_policy_invalid", "gap_id": gap_id})
        if not str(gap.get("claim_boundary") or "").strip():
            errors.append({"type": "gap_claim_boundary_required", "gap_id": gap_id})
    return {
        "schema_version": "sec_agent_typed_gap_ledger_validation_v0.1",
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
    }


def normalize_gap_type(value: Any, row: Mapping[str, Any] | None = None) -> str:
    raw = str(value or "").strip().lower()
    normalized = GAP_TYPE_ALIASES.get(raw)
    if normalized:
        return normalized
    text = " ".join([raw, str((row or {}).get("reason") or ""), str((row or {}).get("bounded_reason") or "")]).lower()
    if "commercial" in text or "tracker" in text:
        return "commercial_gap"
    if "not disclosed" in text or "undisclosed" in text:
        return "not_disclosed"
    if "not found" in text or "missing" in text or "unavailable" in text:
        return "not_found"
    if "parser" in text or "schema" in text:
        return "parser_failed"
    if "source boundary" in text or "boundary" in text:
        return "source_boundary_blocked"
    if "period" in text:
        return "period_gap"
    if "unit" in text:
        return "unit_gap"
    if "alias" in text:
        return "alias_gap"
    if "conflict" in text:
        return "conflict_gap"
    if "stale" in text or "old" in text:
        return "staleness_gap"
    return raw if raw in TYPED_GAP_TYPES else "coverage_gap"


def _gap_rows_from_state(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rows.extend(_mapping_rows(state.get("source_gaps")))
    bounded = state.get("bounded_gap_register") if isinstance(state.get("bounded_gap_register"), Mapping) else {}
    rows.extend(_mapping_rows(bounded.get("gaps")))
    fusion = state.get("evidence_fusion_bundle") if isinstance(state.get("evidence_fusion_bundle"), Mapping) else {}
    fusion_bounded = fusion.get("bounded_gap_register") if isinstance(fusion.get("bounded_gap_register"), Mapping) else {}
    rows.extend(_mapping_rows(fusion_bounded.get("gaps")))
    hard_gate = state.get("second_pass_hard_gate") if isinstance(state.get("second_pass_hard_gate"), Mapping) else {}
    rows.extend(_mapping_rows(hard_gate.get("bounded_gap_candidates")))
    quality = state.get("quality_second_pass_report") if isinstance(state.get("quality_second_pass_report"), Mapping) else {}
    rows.extend(_mapping_rows(quality.get("quality_gaps")))
    return rows


def _route_scope_gap_is_non_blocking(
    row: Mapping[str, Any],
    *,
    visible_primary_tickers: set[str],
    focus_tickers: set[str],
) -> bool:
    if not _is_route_scope_gap(row):
        return False
    ticker = str(row.get("ticker") or row.get("company") or "").upper().strip()
    if not ticker:
        return False
    if ticker in visible_primary_tickers:
        return True
    if focus_tickers and ticker not in focus_tickers:
        return True
    return False


def _is_route_scope_gap(row: Mapping[str, Any]) -> bool:
    text = " ".join(
        str(row.get(key) or "")
        for key in (
            "raw_gap_type",
            "gap_type",
            "reason_code",
            "reason",
            "register_source",
            "source",
            "error",
        )
    ).lower()
    return any(
        marker in text
        for marker in (
            "not_in_manifest_for_mcp_route_scope",
            "not_in_manifest",
            "mcp route scope",
            "route_scope",
            "local_or_sec_route_scope_missing",
        )
    )


def _visible_primary_evidence_tickers_from_state(state: Mapping[str, Any]) -> set[str]:
    tickers: set[str] = set()
    candidates: list[Any] = []
    fact_selection = state.get("pre_memo_fact_selection") if isinstance(state.get("pre_memo_fact_selection"), Mapping) else {}
    candidates.extend(fact_selection.get("approved_facts") or [])
    for key in ("verified_judgment_plan", "judgment_plan", "claim_cards"):
        payload = state.get(key) if isinstance(state.get(key), Mapping) else {}
        candidates.extend(payload.get("supported_claims") or [])
    candidates.extend(state.get("runtime_ledger_rows") or [])

    primary_families = {"primary_sec_filing", "company_authored_unaudited_sec_filing"}
    for row in candidates:
        if not isinstance(row, Mapping):
            continue
        families = set(_string_list(row.get("source_families") or row.get("source_family")))
        if families and not (families & primary_families):
            continue
        if not _row_has_evidence_identity(row):
            continue
        tickers.update(_ticker_set_from_row(row))
    return tickers


def _focus_tickers_from_state(state: Mapping[str, Any]) -> set[str]:
    values: list[Any] = []
    for key in ("focus_tickers",):
        values.extend(_string_list(state.get(key)))
    query_contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    for key in ("focus_tickers", "companies", "tickers"):
        values.extend(_string_list(query_contract.get(key)))
    return {str(value).upper().strip() for value in values if str(value).strip()}


def _ticker_set_from_row(row: Mapping[str, Any]) -> set[str]:
    values: list[str] = []
    for key in ("ticker", "company", "ticker_scope", "tickers"):
        values.extend(_string_list(row.get(key)))
    return {value.upper().strip() for value in values if value.strip()}


def _row_has_evidence_identity(row: Mapping[str, Any]) -> bool:
    for key in ("evidence_refs", "refs", "evidence_ref", "source_id", "source_fact_id", "line_item_id", "metric_id"):
        if _string_list(row.get(key)):
            return True
    return False


def _claim_ledger_entry(
    row: Mapping[str, Any],
    *,
    index: int,
    run_id: str,
    as_of_date: str,
    default_status: str,
    gap_rows: list[Mapping[str, Any]],
) -> dict[str, Any]:
    support_refs = _string_list(row.get("supporting_evidence_ids") or row.get("evidence_refs") or row.get("refs"))
    contradict_refs = _string_list(row.get("contradicting_evidence_ids") or row.get("limiting_refs"))
    claim_text = str(row.get("claim_text") or row.get("claim") or row.get("text") or "").strip()
    claim_id = str(row.get("claim_id") or _stable_id("claim", run_id, index, claim_text)).strip()
    status = default_status if default_status in CLAIM_STATUSES else "weakly_supported"
    source_families = _string_list(row.get("source_families") or row.get("source_family"))
    gap_ids = _claim_gap_ids(row, gap_rows)
    return {
        "claim_id": claim_id,
        "run_id": run_id,
        "ticker": _first_or_blank(row.get("ticker") or row.get("ticker_scope") or row.get("tickers")),
        "agent_id": str(row.get("agent_id") or "").strip(),
        "memo_slot": str(row.get("memo_slot") or "").strip(),
        "claim_text": claim_text,
        "claim_type": str(row.get("claim_type") or row.get("type") or "").strip() or "unspecified",
        "claim_status": status,
        "supporting_evidence_ids": support_refs,
        "contradicting_evidence_ids": contradict_refs if status == "contradicted" else contradict_refs,
        "gap_ids": gap_ids,
        "source_families": source_families,
        "source_strength": _claim_source_strength(row, source_families),
        "confidence": _claim_confidence(row),
        "as_of_date": str(row.get("as_of_date") or as_of_date or _utc_date()),
        "required_gate_results": _required_gate_results(row, status=status, supporting_refs=support_refs),
        "metric_scope": _string_list(row.get("metric_scope") or row.get("metric") or row.get("metrics")),
        "materiality": str(row.get("materiality") or "").strip(),
        "direction": str(row.get("direction") or "").strip(),
        "limitations": _string_list(row.get("limitations") or row.get("caveats") or row.get("missing_confirmations")),
        "claim_boundary": _claim_boundary(status=status, source_families=source_families),
    }


def _typed_gap_entry(row: Mapping[str, Any], *, index: int) -> dict[str, Any]:
    raw_gap_type = str(
        row.get("raw_gap_type")
        or row.get("gap_type")
        or row.get("quality_gap_type")
        or row.get("reason_code")
        or row.get("reason")
        or "coverage_gap"
    ).strip()
    gap_type = normalize_gap_type(raw_gap_type, row)
    gap_id = str(row.get("gap_id") or row.get("source_gap_id") or row.get("requirement_id") or "").strip()
    if not gap_id:
        gap_id = _stable_id(
            "gap",
            raw_gap_type,
            row.get("ticker") or row.get("company"),
            row.get("metric") or row.get("metric_family") or row.get("field"),
            row.get("bounded_reason") or row.get("reason"),
            index,
        )
    return {
        "gap_id": gap_id,
        "raw_gap_type": raw_gap_type,
        "gap_type": gap_type,
        "status": str(row.get("status") or row.get("gap_status") or "open").strip() or "open",
        "ticker": str(row.get("ticker") or row.get("company") or "").upper().strip(),
        "metric": str(row.get("metric") or row.get("metric_family") or row.get("field") or "").strip(),
        "product_or_segment": str(row.get("product_or_segment") or row.get("product") or row.get("segment") or "").strip(),
        "source_family": str(row.get("source_family") or row.get("source_tier") or "unknown").strip() or "unknown",
        "affected_claim_ids": _string_list(row.get("affected_claim_ids") or row.get("affected_claims")),
        "evidence_refs": _string_list(row.get("evidence_refs") or row.get("refs")),
        "source_attempts": _string_list(row.get("source_attempts")),
        "commercial_sources_needed": _string_list(row.get("commercial_sources_needed")),
        "repairability": _gap_repairability(gap_type),
        "treatment_action": _gap_treatment_action(gap_type),
        "reason": str(row.get("bounded_reason") or row.get("reason") or row.get("description") or "").strip(),
        "as_of_date": str(row.get("as_of_date") or row.get("source_as_of_date") or _utc_date()),
        "register_source": str(row.get("register_source") or row.get("source") or "").strip(),
        "claim_boundary": _gap_claim_boundary(gap_type),
    }


def _supported_claim_status(row: Mapping[str, Any]) -> str:
    confidence = _claim_confidence(row)
    if confidence in {"low", "unknown"}:
        return "weakly_supported"
    if not _string_list(row.get("supporting_evidence_ids") or row.get("evidence_refs") or row.get("refs")):
        return "weakly_supported"
    return "supported"


def _claim_source_strength(row: Mapping[str, Any], source_families: list[str]) -> str:
    explicit = str(row.get("source_strength") or row.get("evidence_strength") or row.get("authority_tier") or "").strip()
    if explicit.startswith("S"):
        return explicit
    families = set(source_families)
    if families & {"primary_sec_filing", "company_authored_unaudited_sec_filing", "company_product_evidence_graph"}:
        return "S5"
    if families & {"public_source_context", "relationship_graph", "live_public_web_context"}:
        return "S3"
    if families & {"market_snapshot", "industry_snapshot"}:
        return "S2"
    if families & {"milvus_semantic", "run_artifact"}:
        return "S1"
    if explicit:
        return explicit
    return "unknown"


def _claim_confidence(row: Mapping[str, Any]) -> str:
    value = row.get("confidence")
    if isinstance(value, (int, float)):
        if float(value) >= 0.75:
            return "high"
        if float(value) >= 0.4:
            return "medium"
        return "low"
    text = str(value or "").strip().lower()
    return text if text in {"high", "medium", "low", "unknown"} else "unknown"


def _required_gate_results(row: Mapping[str, Any], *, status: str, supporting_refs: list[str]) -> list[str]:
    explicit = _string_list(row.get("required_gate_results") or row.get("gate_results") or row.get("required_gates"))
    if explicit:
        return explicit
    if status in {"supported", "weakly_supported"} and supporting_refs:
        return ["source_boundary_gate:passed_by_judgment", "claim_support_gate:passed_by_judgment"]
    if status == "contradicted":
        return ["contradiction_gate:recorded_by_judgment"]
    return ["gap_exposure_gate:recorded_by_judgment"]


def _claim_gap_ids(row: Mapping[str, Any], gap_rows: list[Mapping[str, Any]]) -> list[str]:
    explicit = _string_list(row.get("gap_ids") or row.get("gap_refs"))
    if explicit:
        return explicit
    tickers = set(_string_list(row.get("ticker") or row.get("ticker_scope") or row.get("tickers")))
    metrics = set(_string_list(row.get("metric") or row.get("metric_scope") or row.get("metrics")))
    if not tickers and not metrics:
        return []
    matches = []
    for gap in gap_rows:
        gap_ticker = str(gap.get("ticker") or "").upper().strip()
        gap_metric = str(gap.get("metric") or "").strip()
        ticker_match = not tickers or gap_ticker in {item.upper() for item in tickers}
        metric_match = not metrics or not gap_metric or gap_metric in metrics
        if ticker_match and metric_match:
            gap_id = str(gap.get("gap_id") or "").strip()
            if gap_id:
                matches.append(gap_id)
    return _dedupe(matches)


def _claim_boundary(*, status: str, source_families: list[str]) -> str:
    if status == "gap_exposed":
        return "gap_exposed_not_supporting_fact"
    if status == "contradicted":
        return "contradiction_preserved_not_averaged"
    if set(source_families) & {"public_source_context", "market_snapshot", "industry_snapshot", "relationship_graph", "live_public_web_context"}:
        return "context_or_hypothesis_only_unless_claim_scope_allows"
    return "verified_claim_card_requires_supporting_evidence_refs"


def _gap_repairability(gap_type: str) -> str:
    if gap_type == "commercial_gap":
        return "commercial_or_user_research_required"
    if gap_type == "not_disclosed":
        return "not_repairable_publicly"
    if gap_type == "source_boundary_blocked":
        return "downgrade_to_context"
    if gap_type in {"parser_failed", "period_gap", "unit_gap", "alias_gap", "conflict_gap"}:
        return "targeted_repair"
    return "retrieval_or_refresh"


def _gap_treatment_action(gap_type: str) -> str:
    return {
        "commercial_gap": "expose_commercial_gap_do_not_proxy",
        "not_disclosed": "expose_bounded_gap_no_parser_repair",
        "not_found": "bounded_retrieval_or_source_expansion",
        "parser_failed": "targeted_parser_repair",
        "source_boundary_blocked": "downgrade_to_context_or_lead",
        "period_gap": "period_alignment_repair",
        "unit_gap": "unit_normalization_repair",
        "alias_gap": "entity_or_metric_alias_repair",
        "conflict_gap": "send_to_reconciliation",
        "staleness_gap": "refresh_or_vintage_gate",
        "coverage_gap": "bounded_coverage_gap",
    }[gap_type]


def _gap_claim_boundary(gap_type: str) -> str:
    if gap_type == "commercial_gap":
        return "commercial_gap_may_be_disclosed_but_never_filled_with_public_proxy"
    if gap_type == "source_boundary_blocked":
        return "blocked_source_may_not_support_claim"
    return "bounded_gap_may_explain_missing_evidence_but_not_support_fact"


def _mapping_rows(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value or [] if isinstance(item, Mapping)]


def _string_list(value: Any) -> list[str]:
    if value is None:
        items: list[Any] = []
    elif isinstance(value, str):
        items = [part.strip() for part in value.split(",") if part.strip()]
    elif isinstance(value, (list, tuple, set)):
        items = list(value)
    else:
        items = [value]
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _first_or_blank(value: Any) -> str:
    items = _string_list(value)
    return items[0].upper() if items else ""


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _count_by_key(rows: list[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "").strip() or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _stable_id(prefix: str, *parts: Any) -> str:
    text = json.dumps([str(part or "") for part in parts], ensure_ascii=False, sort_keys=True)
    return f"{prefix}_" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _utc_date() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _sanitize_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _sanitize_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_payload(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_payload(item) for item in value]
    return value
