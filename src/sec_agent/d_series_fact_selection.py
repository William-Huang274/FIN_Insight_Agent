from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any, Mapping


PRE_MEMO_FACT_SELECTION_SCHEMA_VERSION = "sec_agent_pre_memo_fact_selection_v0.1"


def build_pre_memo_fact_selection(state: Mapping[str, Any]) -> dict[str, Any]:
    """Select memo-eligible base and derived facts after D6/D9/D10 governance."""

    reconciliation = state.get("reconciliation_ledger") if isinstance(state.get("reconciliation_ledger"), Mapping) else {}
    gate_matrix = state.get("gate_registry_eval_matrix") if isinstance(state.get("gate_registry_eval_matrix"), Mapping) else {}
    derived_layer = state.get("derived_metric_layer") if isinstance(state.get("derived_metric_layer"), Mapping) else {}
    typed_gap_ledger = state.get("typed_gap_ledger") if isinstance(state.get("typed_gap_ledger"), Mapping) else {}
    bounded_gap_register = state.get("bounded_gap_register") if isinstance(state.get("bounded_gap_register"), Mapping) else {}

    blocking_gate_index = _blocking_gate_index(gate_matrix)
    approved_facts: list[dict[str, Any]] = []
    rejected_facts: list[dict[str, Any]] = []
    conflict_gap_links: list[dict[str, Any]] = []
    candidates_by_id = _candidate_index(reconciliation)

    for group in _mapping_rows(reconciliation.get("reconciliation_groups")):
        group_id = _text(group.get("group_id"))
        blocking_gates = blocking_gate_index.get(group_id, [])
        status = _text(group.get("resolution_status"))
        preferred = group.get("preferred_value") if isinstance(group.get("preferred_value"), Mapping) else {}
        candidate_ids = _strings(group.get("candidate_ids"))
        base = {
            "selection_id": _stable_id("pre_memo_fact", group_id),
            "reconciliation_group_id": group_id,
            "ticker": _text(group.get("ticker")).upper(),
            "canonical_metric_id": _text(group.get("canonical_metric_id")),
            "product_or_segment": _text(group.get("product_or_segment")),
            "period_key": _text(group.get("period_key")),
            "candidate_ids": candidate_ids,
            "blocking_gate_result_ids": [_text(row.get("gate_result_id")) for row in blocking_gates],
            "source_layer": "reconciliation_ledger",
        }
        if status.startswith("resolved") and preferred and not blocking_gates:
            approved_facts.append(
                {
                    **base,
                    "fact_id": _text(preferred.get("candidate_id")) or group_id,
                    "value": _text(preferred.get("value")),
                    "numeric_value": _text(preferred.get("numeric_value")),
                    "unit": _text(preferred.get("unit")),
                    "source_id": _text(preferred.get("source_id")),
                    "evidence_ref": _text(preferred.get("evidence_ref")),
                    "source_family": _text(preferred.get("source_family")),
                    "resolution_rule": _text(preferred.get("resolution_rule")),
                    "resolution_confidence": _text(preferred.get("confidence")),
                    "selection_status": "approved",
                    "claim_boundary": "resolved_reconciliation_fact_memo_eligible",
                }
            )
        else:
            reason = "blocking_gate_failed" if blocking_gates else status or "missing_resolution"
            rejected_facts.append(
                {
                    **base,
                    "selection_status": "rejected",
                    "reject_reason": reason,
                    "conflict_gap_id": _text(group.get("conflict_gap_id")),
                    "conflict_types": _strings(group.get("conflict_types")),
                    "claim_boundary": "unresolved_or_blocked_reconciliation_group_not_memo_eligible",
                }
            )
        gap_id = _text(group.get("conflict_gap_id"))
        if gap_id:
            conflict_gap_links.append(
                {
                    "gap_id": gap_id,
                    "gap_type": "conflict_gap",
                    "reconciliation_group_id": group_id,
                    "candidate_ids": candidate_ids,
                    "resolution_status": status,
                    "treatment_action": "expose_conflict_gap_until_reconciliation_resolves",
                }
            )

    approved_derived_metrics: list[dict[str, Any]] = []
    rejected_derived_metrics: list[dict[str, Any]] = []
    rejected_fact_ids = {fact_id for row in rejected_facts for fact_id in _strings(row.get("candidate_ids"))}
    for row in _mapping_rows(derived_layer.get("derived_metrics")):
        input_fact_ids = _strings(row.get("input_fact_ids"))
        blocked_inputs = sorted(set(input_fact_ids) & rejected_fact_ids)
        blocking_gates = _strings((row.get("gate_status_detail") or {}).get("blocking_gate_result_ids")) if isinstance(row.get("gate_status_detail"), Mapping) else []
        if _text(row.get("gate_status")) in {"pass", "warn"} and not blocked_inputs and not blocking_gates:
            approved_derived_metrics.append(
                {
                    "derived_metric_id": _text(row.get("derived_metric_id")),
                    "derived_metric_family": _text(row.get("derived_metric_family")),
                    "ticker": _text(row.get("ticker")).upper(),
                    "value": _text(row.get("value")),
                    "unit": _text(row.get("unit")),
                    "period_key": _text(row.get("period_key")),
                    "input_fact_ids": input_fact_ids,
                    "input_reconciliation_group_ids": _strings(row.get("input_reconciliation_group_ids")),
                    "gate_status": _text(row.get("gate_status")),
                    "selection_status": "approved",
                    "source_layer": "derived_metric_layer",
                    "claim_boundary": "derived_metric_memo_eligible_only_with_formula_and_input_lineage",
                }
            )
        else:
            rejected_derived_metrics.append(
                {
                    "derived_metric_id": _text(row.get("derived_metric_id")),
                    "derived_metric_family": _text(row.get("derived_metric_family")),
                    "ticker": _text(row.get("ticker")).upper(),
                    "input_fact_ids": input_fact_ids,
                    "blocked_input_fact_ids": blocked_inputs,
                    "blocking_gate_result_ids": blocking_gates,
                    "gate_status": _text(row.get("gate_status")),
                    "selection_status": "rejected",
                    "reject_reason": "input_gate_blocked" if blocking_gates or blocked_inputs else "nonpassing_gate_status",
                    "source_layer": "derived_metric_layer",
                }
            )

    bounded_gap_links = _bounded_gap_links(typed_gap_ledger, bounded_gap_register, conflict_gap_links)
    payload = {
        "schema_version": PRE_MEMO_FACT_SELECTION_SCHEMA_VERSION,
        "policy": "memo_consumes_only_reconciled_facts_and_gate_passing_derived_metrics_v0_1",
        "run_id": _text(state.get("run_id")),
        "approved_facts": approved_facts,
        "rejected_facts": rejected_facts,
        "approved_derived_metrics": approved_derived_metrics,
        "rejected_derived_metrics": rejected_derived_metrics,
        "bounded_gap_links": bounded_gap_links,
        "blocked_evidence_refs": sorted(
            {
                ref
                for row in rejected_facts
                for candidate_id in _strings(row.get("candidate_ids"))
                for ref in [_text(candidates_by_id.get(candidate_id, {}).get("evidence_ref"))]
                if ref
            }
        ),
        "blocked_candidate_ids": sorted(rejected_fact_ids),
        "blocking_gate_result_ids": sorted(
            {
                gate_id
                for row in [*rejected_facts, *rejected_derived_metrics]
                for gate_id in _strings(row.get("blocking_gate_result_ids"))
            }
        ),
        "summary": {
            "approved_fact_count": len(approved_facts),
            "rejected_fact_count": len(rejected_facts),
            "approved_derived_metric_count": len(approved_derived_metrics),
            "rejected_derived_metric_count": len(rejected_derived_metrics),
            "bounded_gap_link_count": len(bounded_gap_links),
            "blocking_gate_result_count": len(
                {
                    gate_id
                    for row in [*rejected_facts, *rejected_derived_metrics]
                    for gate_id in _strings(row.get("blocking_gate_result_ids"))
                }
            ),
            "by_rejected_fact_reason": dict(sorted(Counter(row.get("reject_reason") or "unknown" for row in rejected_facts).items())),
            "by_bounded_gap_type": dict(sorted(Counter(row.get("gap_type") or "unknown" for row in bounded_gap_links).items())),
        },
    }
    payload["validation"] = validate_pre_memo_fact_selection(payload)
    return payload


def apply_pre_memo_fact_selection_to_judgment(
    judgment_plan: Mapping[str, Any],
    fact_selection: Mapping[str, Any],
) -> dict[str, Any]:
    judgment = dict(judgment_plan or {})
    supported = [dict(row) for row in judgment.get("supported_claims") or [] if isinstance(row, Mapping)]
    unsupported = [dict(row) for row in judgment.get("unsupported_claims") or [] if isinstance(row, Mapping)]
    blocked_refs = set(_strings(fact_selection.get("blocked_evidence_refs")))
    blocked_candidates = set(_strings(fact_selection.get("blocked_candidate_ids")))
    approved_fact_ids = {
        _text(row.get("fact_id"))
        for row in fact_selection.get("approved_facts") or []
        if isinstance(row, Mapping) and _text(row.get("fact_id"))
    }
    approved_derived_ids = {
        _text(row.get("derived_metric_id"))
        for row in fact_selection.get("approved_derived_metrics") or []
        if isinstance(row, Mapping) and _text(row.get("derived_metric_id"))
    }
    filtered_supported: list[dict[str, Any]] = []
    moved_to_unsupported: list[dict[str, Any]] = []
    for claim in supported:
        evidence_refs = set(_strings(claim.get("evidence_refs") or claim.get("supporting_evidence_ids")))
        fact_refs = set(_strings(claim.get("fact_ids") or claim.get("input_fact_ids")))
        derived_refs = set(_strings(claim.get("derived_metric_ids")))
        blocked = sorted((evidence_refs & blocked_refs) | (fact_refs & blocked_candidates))
        unapproved_derived = sorted(derived_refs - approved_derived_ids) if derived_refs else []
        if blocked or unapproved_derived:
            moved = {
                "claim_id": _text(claim.get("claim_id")),
                "agent_id": _text(claim.get("agent_id")),
                "claim": "claim text withheld because pre-memo governance blocked this fact; use bounded gap metadata instead",
                "reason": "blocked_by_pre_memo_fact_selection",
                "blocked_evidence_refs": blocked,
                "unapproved_derived_metric_ids": unapproved_derived,
                "source_claim": claim,
            }
            moved_to_unsupported.append(moved)
            unsupported.append(moved)
        else:
            filtered_supported.append(claim)

    constraints = dict(judgment.get("memo_constraints") or {}) if isinstance(judgment.get("memo_constraints"), Mapping) else {}
    missing_evidence = [dict(row) for row in constraints.get("missing_evidence") or [] if isinstance(row, Mapping)]
    for row in fact_selection.get("bounded_gap_links") or []:
        if not isinstance(row, Mapping):
            continue
        missing_evidence.append(
            {
                "gap_id": _text(row.get("gap_id")),
                "gap_type": _text(row.get("gap_type")),
                "reason": _text(row.get("treatment_action")) or "bounded_gap_not_memo_fact",
                "source_layer": _text(row.get("source_layer")),
            }
        )
    constraints["missing_evidence"] = _dedupe_dicts(missing_evidence)
    if moved_to_unsupported and "pre_memo_fact_selection_blocked_claims" not in constraints.get("blocked_reasons", []):
        constraints["blocked_reasons"] = [*list(constraints.get("blocked_reasons") or []), "pre_memo_fact_selection_blocked_claims"]
    constraints["approved_fact_count"] = len(approved_fact_ids)
    constraints["approved_derived_metric_count"] = len(approved_derived_ids)

    stats = dict(judgment.get("claim_card_stats") or {}) if isinstance(judgment.get("claim_card_stats"), Mapping) else {}
    stats["supported_claim_count"] = len(filtered_supported)
    stats["pre_memo_blocked_claim_count"] = len(moved_to_unsupported)
    stats["approved_fact_count"] = len(approved_fact_ids)
    stats["approved_derived_metric_count"] = len(approved_derived_ids)

    return {
        **judgment,
        "supported_claims": filtered_supported,
        "unsupported_claims": unsupported,
        "memo_constraints": constraints,
        "claim_card_stats": stats,
        "pre_memo_fact_selection": {
            "schema_version": fact_selection.get("schema_version") or PRE_MEMO_FACT_SELECTION_SCHEMA_VERSION,
            "approved_fact_ids": sorted(approved_fact_ids),
            "approved_derived_metric_ids": sorted(approved_derived_ids),
            "blocked_claims": moved_to_unsupported,
            "bounded_gap_links": [dict(row) for row in fact_selection.get("bounded_gap_links") or [] if isinstance(row, Mapping)],
            "summary": dict(fact_selection.get("summary") or {}) if isinstance(fact_selection.get("summary"), Mapping) else {},
        },
        "memo_writer_allowed": bool(judgment.get("memo_writer_allowed", True)) and not (moved_to_unsupported and not filtered_supported),
        "governance_filter_policy": "pre_memo_governance_filtered_claim_cards_v0_1",
    }


def validate_pre_memo_fact_selection(payload: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    approved_ids = set()
    for row in payload.get("approved_facts") or []:
        if not isinstance(row, Mapping):
            continue
        fact_id = _text(row.get("fact_id"))
        if not fact_id:
            errors.append({"type": "approved_fact_id_required"})
        if fact_id in approved_ids:
            errors.append({"type": "duplicate_approved_fact_id", "fact_id": fact_id})
        approved_ids.add(fact_id)
        if _text(row.get("selection_status")) != "approved":
            errors.append({"type": "approved_fact_invalid_status", "fact_id": fact_id})
    for row in payload.get("rejected_facts") or []:
        if not isinstance(row, Mapping):
            continue
        if not _text(row.get("reject_reason")):
            errors.append({"type": "rejected_fact_missing_reason", "selection_id": row.get("selection_id")})
    for row in payload.get("approved_derived_metrics") or []:
        if not isinstance(row, Mapping):
            continue
        if _text(row.get("gate_status")) not in {"pass", "warn"}:
            errors.append({"type": "approved_derived_metric_nonpassing_gate", "derived_metric_id": row.get("derived_metric_id")})
        if not _strings(row.get("input_fact_ids")):
            warnings.append({"type": "approved_derived_metric_missing_input_fact_ids", "derived_metric_id": row.get("derived_metric_id")})
    return {
        "schema_version": "sec_agent_pre_memo_fact_selection_validation_v0.1",
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
    }


def _blocking_gate_index(gate_matrix: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    for row in _mapping_rows(gate_matrix.get("gate_history")):
        if row.get("blocks_claim_fact_layer") and _text(row.get("status")) == "fail":
            index.setdefault(_text(row.get("target_object_id")), []).append(row)
    return index


def _candidate_index(reconciliation: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _text(row.get("candidate_id")): dict(row)
        for row in reconciliation.get("candidates") or []
        if isinstance(row, Mapping) and _text(row.get("candidate_id"))
    }


def _bounded_gap_links(
    typed_gap_ledger: Mapping[str, Any],
    bounded_gap_register: Mapping[str, Any],
    conflict_gap_links: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    for row in _mapping_rows(typed_gap_ledger.get("gaps")):
        gap_type = _text(row.get("gap_type"))
        if gap_type in {"commercial_gap", "conflict_gap", "source_boundary_blocked", "staleness_gap", "period_gap", "unit_gap", "alias_gap"}:
            links.append(
                {
                    "gap_id": _text(row.get("gap_id")),
                    "gap_type": gap_type,
                    "ticker": _text(row.get("ticker")).upper(),
                    "metric": _text(row.get("metric")),
                    "source_layer": "typed_gap_ledger",
                    "treatment_action": _text(row.get("treatment_action")) or "expose_gap_do_not_proxy",
                }
            )
    for row in _mapping_rows(bounded_gap_register.get("gaps")):
        links.append(
            {
                "gap_id": _text(row.get("gap_id")),
                "gap_type": _text(row.get("gap_type")),
                "ticker": _text(row.get("ticker")).upper(),
                "metric": _text(row.get("metric")),
                "source_layer": "bounded_gap_register",
                "treatment_action": _text(row.get("treatment_action")) or _text(row.get("reason")) or "bounded_gap",
            }
        )
    links.extend(conflict_gap_links)
    return _dedupe_dicts([row for row in links if _text(row.get("gap_id"))])


def _mapping_rows(value: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in value or [] if isinstance(row, Mapping)]


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, Mapping):
        return [_text(value)] if _text(value) else []
    if isinstance(value, (list, tuple, set)):
        return [_text(item) for item in value if _text(item)]
    return [_text(value)] if _text(value) else []


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return next((_text(item) for item in value if _text(item)), "")
    return str(value or "").strip()


def _dedupe_dicts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = _stable_id("row", row)
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _stable_id(prefix: str, *parts: Any) -> str:
    payload = "|".join(str(part or "") for part in parts)
    return f"{prefix}:{hashlib.sha1(payload.encode('utf-8')).hexdigest()[:16]}"
