from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from typing import Any, Mapping

from sec_agent.claim_evidence_ledger import build_evidence_governance_ledgers


GATE_REGISTRY_EVAL_MATRIX_SCHEMA_VERSION = "sec_agent_gate_registry_eval_matrix_v0.1"

GATE_STATUSES = {"pass", "warn", "fail", "not_applicable"}


def build_gate_registry_eval_matrix(state: Mapping[str, Any]) -> dict[str, Any]:
    registry = default_gate_registry()
    registry_by_id = {row["gate_id"]: row for row in registry}
    governance_ledgers = _governance_ledgers(state)
    history: list[dict[str, Any]] = []
    history.extend(_source_boundary_results(state, registry_by_id=registry_by_id))
    history.extend(_citation_span_results(state, registry_by_id=registry_by_id))
    history.extend(_vintage_results(state, registry_by_id=registry_by_id))
    history.extend(_entity_resolution_results(state, registry_by_id=registry_by_id))
    history.extend(_metric_mapping_results(state, registry_by_id=registry_by_id))
    history.extend(_reconciliation_results(state, registry_by_id=registry_by_id))
    history.extend(_claim_results(governance_ledgers.get("claim_evidence_ledger") or {}, registry_by_id=registry_by_id))
    history.extend(_typed_gap_results(governance_ledgers.get("typed_gap_ledger") or {}, registry_by_id=registry_by_id))
    history = _dedupe_results(history)
    eval_matrix = _eval_matrix(registry, history)
    payload = {
        "schema_version": GATE_REGISTRY_EVAL_MATRIX_SCHEMA_VERSION,
        "policy": "per_run_gate_registry_history_eval_matrix_v0_1",
        "run_id": str(state.get("run_id") or ""),
        "gate_count": len(registry),
        "gate_result_count": len(history),
        "gate_registry": registry,
        "gate_history": history,
        "eval_matrix": eval_matrix,
        "summary": {
            "by_gate_id": dict(sorted(Counter(row.get("gate_id") or "unknown" for row in history).items())),
            "by_status": dict(sorted(Counter(row.get("status") or "unknown" for row in history).items())),
            "blocking_fail_count": len(
                [row for row in history if row.get("status") == "fail" and row.get("blocks_claim_fact_layer")]
            ),
            "source_boundary_violation_covered": any(
                row.get("gate_id") == "source_boundary_gate" and row.get("status") == "fail" for row in history
            ),
            "weak_proxy_fallback_covered": any(
                row.get("gate_id") in {"commercial_gap_gate", "source_boundary_gate"}
                and row.get("status") == "fail"
                and "proxy" in str(row.get("reason") or row.get("repair_action") or "").lower()
                for row in history
            ),
            "eval_matrix_gate_count": len(eval_matrix),
        },
    }
    payload["validation"] = validate_gate_registry_eval_matrix(payload)
    return _jsonable(payload)


def validate_gate_registry_eval_matrix(payload: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    registry = [row for row in payload.get("gate_registry") or [] if isinstance(row, Mapping)]
    history = [row for row in payload.get("gate_history") or [] if isinstance(row, Mapping)]
    matrix = [row for row in payload.get("eval_matrix") or [] if isinstance(row, Mapping)]
    registry_ids = [str(row.get("gate_id") or "").strip() for row in registry]
    known_ids = {gate_id for gate_id in registry_ids if gate_id}
    if len(registry_ids) != len(known_ids):
        errors.append({"type": "duplicate_gate_id"})
    for row in registry:
        gate_id = str(row.get("gate_id") or "").strip()
        if not gate_id:
            errors.append({"type": "gate_id_required"})
        if not str(row.get("category") or "").strip():
            errors.append({"type": "gate_category_required", "gate_id": gate_id})
        if not str(row.get("repair_action") or "").strip():
            warnings.append({"type": "gate_repair_action_missing", "gate_id": gate_id})
    seen_result_ids: set[str] = set()
    for index, row in enumerate(history):
        result_id = str(row.get("gate_result_id") or "").strip()
        gate_id = str(row.get("gate_id") or "").strip()
        status = str(row.get("status") or "").strip()
        target = str(row.get("target_object_id") or "").strip()
        if not result_id:
            errors.append({"type": "gate_result_id_required", "index": index})
        elif result_id in seen_result_ids:
            errors.append({"type": "duplicate_gate_result_id", "gate_result_id": result_id})
        seen_result_ids.add(result_id)
        if gate_id not in known_ids:
            errors.append({"type": "unknown_gate_id", "gate_result_id": result_id, "gate_id": gate_id})
        if status not in GATE_STATUSES:
            errors.append({"type": "invalid_gate_status", "gate_result_id": result_id, "status": status})
        if not target:
            errors.append({"type": "target_object_id_required", "gate_result_id": result_id})
        if status == "fail" and not str(row.get("repair_action") or "").strip():
            warnings.append({"type": "failed_gate_without_repair_action", "gate_result_id": result_id})
    matrix_ids = {str(row.get("gate_id") or "").strip() for row in matrix if str(row.get("gate_id") or "").strip()}
    missing_matrix = sorted(known_ids - matrix_ids)
    if missing_matrix:
        errors.append({"type": "eval_matrix_missing_gate_rows", "gate_ids": missing_matrix})
    return {
        "schema_version": "sec_agent_gate_registry_eval_matrix_validation_v0.1",
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
    }


def default_gate_registry() -> list[dict[str, Any]]:
    return [
        _gate("source_boundary_gate", "source_boundary", "hard", ["route", "source_gap"], "block_or_downgrade_to_context"),
        _gate("citation_span_gate", "citation", "hard", ["source_record", "claim"], "repair_citation_or_exclude_fact"),
        _gate("period_alignment_gate", "temporal", "hard", ["vintage_record", "reconciliation_group"], "align_period_or_expose_period_gap"),
        _gate("unit_normalization_gate", "metric_value", "hard", ["reconciliation_group", "typed_gap"], "normalize_unit_or_expose_unit_gap"),
        _gate("numeric_consistency_gate", "metric_value", "hard", ["reconciliation_group"], "resolve_numeric_conflict_or_expose_conflict_gap"),
        _gate("metric_mapping_gate", "ontology", "hard", ["observed_metric", "reconciliation_group"], "repair_metric_alias_or_expose_alias_gap"),
        _gate("segment_mapping_gate", "ontology", "hard", ["reconciliation_group"], "repair_product_segment_binding"),
        _gate("entity_resolution_gate", "entity", "hard", ["entity", "unresolved_reference"], "repair_entity_mapping"),
        _gate("claim_support_gate", "claim", "hard", ["claim"], "add_supporting_evidence_or_expose_gap"),
        _gate("contradiction_gate", "claim", "hard", ["claim"], "preserve_contradiction_do_not_average"),
        _gate("staleness_gate", "temporal", "soft", ["vintage_record", "typed_gap"], "refresh_or_bind_vintage"),
        _gate("commercial_gap_gate", "source_boundary", "hard", ["typed_gap"], "expose_commercial_gap_do_not_proxy"),
    ]


def _gate(gate_id: str, category: str, severity: str, target_types: list[str], repair_action: str) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "category": category,
        "severity": severity,
        "target_types": target_types,
        "blocks_claim_fact_layer": severity == "hard",
        "required_fields": ["target_object_id", "status", "score", "reason", "repair_action", "before_value", "after_value"],
        "repair_action": repair_action,
    }


def _source_boundary_results(state: Mapping[str, Any], *, registry_by_id: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    router = state.get("source_capability_router") if isinstance(state.get("source_capability_router"), Mapping) else {}
    results: list[dict[str, Any]] = []
    for row in router.get("route_decisions") or []:
        if not isinstance(row, Mapping):
            continue
        status = "pass" if row.get("decision_status") == "allowed" else "fail"
        reason = str(row.get("reason") or row.get("decision_status") or "")
        if row.get("context_only") and row.get("exact_value_authority"):
            status = "fail"
            reason = "context_only_source_marked_exact_authority"
        results.append(
            _result(
                registry_by_id,
                "source_boundary_gate",
                target_type="route",
                target_object_id=_first_text(row, "route_id", "retrieval_route"),
                status=status,
                reason=reason,
                repair_action="allow_route" if status == "pass" else "block_or_downgrade_to_context_no_weak_proxy",
                before_value=row.get("retrieval_route"),
                after_value=row.get("decision_status"),
                source_artifact="source_capability_router",
                evidence_refs=[_first_text(row, "evidence_requirement_id", "task_id")],
            )
        )
    return results


def _citation_span_results(state: Mapping[str, Any], *, registry_by_id: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    provenance = state.get("raw_source_provenance_store") if isinstance(state.get("raw_source_provenance_store"), Mapping) else {}
    results = []
    for row in provenance.get("records") or []:
        if not isinstance(row, Mapping):
            continue
        if str(row.get("record_type") or "") == "artifact_ref":
            continue
        citation = row.get("citation_span") if isinstance(row.get("citation_span"), Mapping) else {}
        has_span = bool(citation)
        has_locator = bool(row.get("raw_url") or row.get("local_path") or row.get("document_id"))
        status = "pass" if has_span else ("warn" if has_locator else "fail")
        reason = "citation_span_present" if has_span else ("raw_locator_present_without_span" if has_locator else "source_locator_missing")
        results.append(
            _result(
                registry_by_id,
                "citation_span_gate",
                target_type="source_record",
                target_object_id=_first_text(row, "source_id", "evidence_ref"),
                status=status,
                reason=reason,
                repair_action="citation_ok" if status == "pass" else "repair_citation_span_or_exclude_fact",
                before_value=row.get("evidence_ref"),
                after_value=citation,
                source_artifact="raw_source_provenance_store",
                evidence_refs=[_first_text(row, "evidence_ref")],
            )
        )
    return results


def _vintage_results(state: Mapping[str, Any], *, registry_by_id: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    layer = state.get("asof_vintage_layer") if isinstance(state.get("asof_vintage_layer"), Mapping) else {}
    results: list[dict[str, Any]] = []
    for row in layer.get("records") or []:
        if not isinstance(row, Mapping):
            continue
        target = _first_text(row, "vintage_id", "source_id", "evidence_ref")
        time_basis = str(row.get("time_basis") or "")
        has_anchor = _has_any(row, "fiscal_period_end", "filing_date", "accepted_date", "observation_date", "market_as_of_date", "macro_vintage_date", "retrieved_at", "parser_run_at", "fiscal_year")
        period_status = "pass" if has_anchor and time_basis not in {"", "source_observation"} else ("warn" if has_anchor else "fail")
        results.append(
            _result(
                registry_by_id,
                "period_alignment_gate",
                target_type="vintage_record",
                target_object_id=target,
                status=period_status,
                reason="time_anchor_present" if period_status == "pass" else ("source_observation_only" if has_anchor else "time_anchor_missing"),
                repair_action="period_ok" if period_status == "pass" else "repair_period_or_bind_vintage",
                before_value=row.get("evidence_ref"),
                after_value={"time_basis": time_basis, "fiscal_period_end": row.get("fiscal_period_end")},
                source_artifact="asof_vintage_layer",
                evidence_refs=[_first_text(row, "evidence_ref")],
            )
        )
        source_family = str(row.get("source_family") or "")
        stale_status = "pass"
        reason = "freshness_anchor_present"
        if source_family in {"market_snapshot", "industry_snapshot"} and not _has_any(row, "market_as_of_date", "macro_vintage_date", "observation_date"):
            stale_status = "fail"
            reason = "snapshot_asof_or_vintage_missing"
        elif not _has_any(row, "retrieved_at", "source_updated_at", "filing_date", "accepted_date", "market_as_of_date", "macro_vintage_date"):
            stale_status = "warn"
            reason = "freshness_anchor_missing"
        results.append(
            _result(
                registry_by_id,
                "staleness_gate",
                target_type="vintage_record",
                target_object_id=target,
                status=stale_status,
                reason=reason,
                repair_action="freshness_ok" if stale_status == "pass" else "refresh_or_bind_vintage",
                before_value=row.get("source_id"),
                after_value={"retrieved_at": row.get("retrieved_at"), "source_updated_at": row.get("source_updated_at")},
                source_artifact="asof_vintage_layer",
                evidence_refs=[_first_text(row, "evidence_ref")],
            )
        )
    return results


def _entity_resolution_results(state: Mapping[str, Any], *, registry_by_id: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    master = state.get("entity_security_master") if isinstance(state.get("entity_security_master"), Mapping) else {}
    results: list[dict[str, Any]] = []
    for row in master.get("entities") or []:
        if not isinstance(row, Mapping):
            continue
        confidence = str(row.get("resolution_confidence") or "")
        status = "pass" if confidence in {"high", "medium"} else "warn"
        results.append(
            _result(
                registry_by_id,
                "entity_resolution_gate",
                target_type="entity",
                target_object_id=_first_text(row, "entity_id", "ticker"),
                status=status,
                reason=f"entity_resolution_confidence:{confidence or 'unknown'}",
                repair_action="entity_resolution_ok" if status == "pass" else "review_entity_resolution",
                before_value=row.get("ticker"),
                after_value=row.get("entity_id"),
                source_artifact="entity_security_master",
                evidence_refs=[],
            )
        )
    for row in master.get("unresolved_references") or []:
        if not isinstance(row, Mapping):
            continue
        results.append(
            _result(
                registry_by_id,
                "entity_resolution_gate",
                target_type="unresolved_reference",
                target_object_id=_first_text(row, "reference", "raw_reference") or _stable_id("unresolved_reference", row),
                status="fail",
                reason="entity_reference_unresolved",
                repair_action="repair_entity_mapping",
                before_value=row,
                after_value={},
                source_artifact="entity_security_master",
                evidence_refs=[],
            )
        )
    return results


def _metric_mapping_results(state: Mapping[str, Any], *, registry_by_id: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    ontology = state.get("metric_product_ontology_snapshot") if isinstance(state.get("metric_product_ontology_snapshot"), Mapping) else {}
    results = []
    for row in ontology.get("observed_metric_mappings") or []:
        if not isinstance(row, Mapping):
            continue
        match = str(row.get("match_status") or "")
        status = "pass" if match == "mapped" else "fail"
        results.append(
            _result(
                registry_by_id,
                "metric_mapping_gate",
                target_type="observed_metric",
                target_object_id=_first_text(row, "observed_metric_id", "evidence_ref", "raw_metric_text"),
                status=status,
                reason=f"metric_mapping:{match or 'missing'}",
                repair_action="metric_mapping_ok" if status == "pass" else "repair_metric_alias_or_expose_alias_gap",
                before_value=row.get("raw_metric_text"),
                after_value=row.get("canonical_metric_id"),
                source_artifact="metric_product_ontology_snapshot",
                evidence_refs=[_first_text(row, "evidence_ref")],
            )
        )
    return results


def _reconciliation_results(state: Mapping[str, Any], *, registry_by_id: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    ledger = state.get("reconciliation_ledger") if isinstance(state.get("reconciliation_ledger"), Mapping) else {}
    results: list[dict[str, Any]] = []
    for row in ledger.get("reconciliation_groups") or []:
        if not isinstance(row, Mapping):
            continue
        group_id = _first_text(row, "group_id")
        conflicts = set(str(item) for item in row.get("conflict_types") or [])
        resolution_status = str(row.get("resolution_status") or "")
        candidate_ids = [str(item) for item in row.get("candidate_ids") or [] if str(item)]
        for gate_id, conflict_name in (
            ("unit_normalization_gate", "unit_conflict"),
            ("period_alignment_gate", "period_conflict"),
            ("metric_mapping_gate", "taxonomy_conflict"),
            ("segment_mapping_gate", "segment_conflict"),
        ):
            if conflict_name in conflicts:
                status = "fail"
                reason = conflict_name
                action = "repair_required_before_claim_fact"
            else:
                status = "pass"
                reason = "no_" + conflict_name
                action = "gate_ok"
            results.append(
                _result(
                    registry_by_id,
                    gate_id,
                    target_type="reconciliation_group",
                    target_object_id=group_id,
                    status=status,
                    reason=reason,
                    repair_action=action,
                    before_value=candidate_ids,
                    after_value=row.get("preferred_value") or {},
                    source_artifact="reconciliation_ledger",
                    evidence_refs=candidate_ids,
                )
            )
        numeric_status = "pass" if resolution_status.startswith("resolved") else "fail"
        if "rounding_conflict" in conflicts and resolution_status.startswith("resolved"):
            numeric_status = "warn"
        results.append(
            _result(
                registry_by_id,
                "numeric_consistency_gate",
                target_type="reconciliation_group",
                target_object_id=group_id,
                status=numeric_status,
                reason=resolution_status or "unknown_resolution_status",
                repair_action="numeric_consistency_ok" if numeric_status == "pass" else "resolve_numeric_conflict_or_expose_conflict_gap",
                before_value=candidate_ids,
                after_value=row.get("preferred_value") or {},
                source_artifact="reconciliation_ledger",
                evidence_refs=candidate_ids,
            )
        )
    return results


def _claim_results(claim_ledger: Mapping[str, Any], *, registry_by_id: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for row in claim_ledger.get("claims") or []:
        if not isinstance(row, Mapping):
            continue
        status = str(row.get("claim_status") or "")
        claim_id = _first_text(row, "claim_id")
        support_status = {"supported": "pass", "weakly_supported": "warn", "gap_exposed": "fail"}.get(status, "not_applicable")
        results.append(
            _result(
                registry_by_id,
                "claim_support_gate",
                target_type="claim",
                target_object_id=claim_id,
                status=support_status,
                reason=f"claim_status:{status}",
                repair_action="claim_support_ok" if support_status == "pass" else "add_supporting_evidence_or_expose_gap",
                before_value=row.get("claim_text"),
                after_value=row.get("supporting_evidence_ids") or [],
                source_artifact="claim_evidence_ledger",
                evidence_refs=row.get("supporting_evidence_ids") or [],
            )
        )
        contradiction_status = "fail" if status == "contradicted" else "pass"
        results.append(
            _result(
                registry_by_id,
                "contradiction_gate",
                target_type="claim",
                target_object_id=claim_id,
                status=contradiction_status,
                reason=f"claim_status:{status}",
                repair_action="preserve_contradiction_do_not_average" if contradiction_status == "fail" else "no_contradiction_recorded",
                before_value=row.get("claim_text"),
                after_value=row.get("contradicting_evidence_ids") or [],
                source_artifact="claim_evidence_ledger",
                evidence_refs=row.get("contradicting_evidence_ids") or [],
            )
        )
    return results


def _typed_gap_results(gap_ledger: Mapping[str, Any], *, registry_by_id: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    gate_by_gap = {
        "commercial_gap": "commercial_gap_gate",
        "source_boundary_blocked": "source_boundary_gate",
        "period_gap": "period_alignment_gate",
        "unit_gap": "unit_normalization_gate",
        "alias_gap": "metric_mapping_gate",
        "staleness_gap": "staleness_gate",
        "conflict_gap": "numeric_consistency_gate",
    }
    results = []
    for row in gap_ledger.get("gaps") or []:
        if not isinstance(row, Mapping):
            continue
        gap_type = str(row.get("gap_type") or "")
        gate_id = gate_by_gap.get(gap_type)
        if not gate_id:
            continue
        reason = str(row.get("reason") or row.get("raw_gap_type") or gap_type)
        results.append(
            _result(
                registry_by_id,
                gate_id,
                target_type="typed_gap",
                target_object_id=_first_text(row, "gap_id"),
                status="fail",
                reason=reason,
                repair_action=str(row.get("treatment_action") or "repair_or_expose_gap"),
                before_value=row.get("metric") or row.get("product_or_segment"),
                after_value=row.get("claim_boundary"),
                source_artifact="typed_gap_ledger",
                evidence_refs=row.get("evidence_refs") or [],
            )
        )
    return results


def _eval_matrix(registry: list[Mapping[str, Any]], history: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows_by_gate: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in history:
        rows_by_gate[str(row.get("gate_id") or "")].append(row)
    matrix = []
    for gate in registry:
        gate_id = str(gate.get("gate_id") or "")
        rows = rows_by_gate.get(gate_id, [])
        counts = Counter(str(row.get("status") or "unknown") for row in rows)
        matrix_status = "not_covered"
        if counts.get("fail"):
            matrix_status = "fail"
        elif counts.get("warn"):
            matrix_status = "warn"
        elif counts.get("pass"):
            matrix_status = "pass"
        matrix.append(
            {
                "gate_id": gate_id,
                "category": gate.get("category") or "",
                "severity": gate.get("severity") or "",
                "matrix_status": matrix_status,
                "result_count": len(rows),
                "pass_count": counts.get("pass", 0),
                "warn_count": counts.get("warn", 0),
                "fail_count": counts.get("fail", 0),
                "not_applicable_count": counts.get("not_applicable", 0),
                "blocking_fail_count": len(
                    [row for row in rows if row.get("status") == "fail" and row.get("blocks_claim_fact_layer")]
                ),
                "sample_target_object_ids": [str(row.get("target_object_id") or "") for row in rows[:5]],
            }
        )
    return matrix


def _result(
    registry_by_id: Mapping[str, Mapping[str, Any]],
    gate_id: str,
    *,
    target_type: str,
    target_object_id: str,
    status: str,
    reason: str,
    repair_action: str,
    before_value: Any,
    after_value: Any,
    source_artifact: str,
    evidence_refs: Any,
) -> dict[str, Any]:
    gate = registry_by_id.get(gate_id) if isinstance(registry_by_id.get(gate_id), Mapping) else {}
    normalized_status = status if status in GATE_STATUSES else "fail"
    return {
        "gate_result_id": _stable_id("gate_result", gate_id, target_type, target_object_id, source_artifact, reason),
        "gate_id": gate_id,
        "gate_category": str(gate.get("category") or ""),
        "target_type": target_type,
        "target_object_id": str(target_object_id or ""),
        "status": normalized_status,
        "score": _score(normalized_status),
        "reason": reason,
        "repair_action": repair_action,
        "before_value": _jsonable(before_value),
        "after_value": _jsonable(after_value),
        "source_artifact": source_artifact,
        "evidence_refs": _string_list(evidence_refs),
        "blocks_claim_fact_layer": bool(gate.get("blocks_claim_fact_layer")) and normalized_status == "fail",
    }


def _governance_ledgers(state: Mapping[str, Any]) -> dict[str, Any]:
    claim_ledger = state.get("claim_evidence_ledger") if isinstance(state.get("claim_evidence_ledger"), Mapping) else {}
    gap_ledger = state.get("typed_gap_ledger") if isinstance(state.get("typed_gap_ledger"), Mapping) else {}
    if claim_ledger and gap_ledger:
        return {"claim_evidence_ledger": claim_ledger, "typed_gap_ledger": gap_ledger}
    generated = build_evidence_governance_ledgers(state)
    return {
        "claim_evidence_ledger": claim_ledger or generated.get("claim_evidence_ledger") or {},
        "typed_gap_ledger": gap_ledger or generated.get("typed_gap_ledger") or {},
    }


def _dedupe_results(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        result_id = str(row.get("gate_result_id") or "")
        if result_id and result_id not in by_id:
            by_id[result_id] = row
    return sorted(by_id.values(), key=lambda row: (str(row.get("gate_id") or ""), str(row.get("target_object_id") or "")))


def _score(status: str) -> float:
    return {"pass": 1.0, "warn": 0.5, "not_applicable": 0.0, "fail": 0.0}.get(status, 0.0)


def _has_any(row: Mapping[str, Any], *keys: str) -> bool:
    return any(str(row.get(key) or "").strip() for key in keys)


def _first_text(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            value = next((item for item in value if str(item or "").strip()), "")
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item or "").strip() for item in value if str(item or "").strip()]
    return [str(value).strip()]


def _stable_id(prefix: str, *values: Any) -> str:
    raw = "|".join(str(value or "") for value in values)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(child) for key, child in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return value
