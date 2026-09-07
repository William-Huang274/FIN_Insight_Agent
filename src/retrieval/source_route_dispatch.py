from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
import re
from typing import Any, Mapping, Sequence

from .query_plan import canonical_digest


SOURCE_ROUTE_POLICY_SCHEMA_VERSION = "fin_ia_s1_source_route_portfolio_policy_v1_0"
SOURCE_ROUTE_TRUTH_SCHEMA_VERSION = "fin_ia_s1_source_route_execution_truth_v1_0"
SOURCE_ROUTE_ATTEMPT_SCHEMA_VERSION = "fin_ia_s1_source_route_attempt_receipt_v1_0"
SOURCE_NON_DISCLOSURE_SCHEMA_VERSION = "fin_ia_s1_source_non_disclosure_receipt_v1_0"

_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_ROUTE_KINDS = {
    "local_snapshot",
    "official_primary",
    "official_ir",
    "structured_market",
    "industry_primary_or_licensed",
    "diagnostic_discovery",
    "operator_fallback",
}
_CAPABILITY_STATES = {
    "available",
    "available_when_exact_route_registered",
    "not_configured",
    "manual_only",
    "diagnostic_only",
}
_ATTEMPT_STATES = {
    "terminal_sources_captured",
    "terminal_no_eligible_source",
    "transport_failure",
    "provider_quota_failure",
    "parser_failure",
    "cancelled",
}
class SourceRouteDispatchError(ValueError):
    """Raised when source-route truth would otherwise become ambiguous."""


def candidate_coverage_state_from_hybrid_result(
    hybrid_result: Mapping[str, Any] | None,
) -> str:
    """Return the material requirement state used to schedule source routes.

    Candidate counts are deliberately insufficient here: the result is complete
    only when every material requirement receipt says so.  Missing receipts mean
    that coverage was never evaluated, not that the local snapshot was complete.
    """

    if hybrid_result is None:
        return "not_evaluated"
    material = hybrid_result.get("material_evidence")
    if not isinstance(material, Mapping):
        return "not_evaluated"
    selection = material.get("selection")
    if not isinstance(selection, Mapping):
        return "not_evaluated"
    receipts = selection.get("requirement_receipts")
    if not isinstance(receipts, list) or not receipts:
        return "not_evaluated"
    return (
        "complete"
        if all(
            isinstance(row, Mapping) and row.get("complete") is True
            for row in receipts
        )
        else "incomplete"
    )


def collect_source_route_candidate_rows(
    request_result: Mapping[str, Any],
    hybrid_result: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], ...]:
    """Collect one stable candidate row per local object across retrieval lanes."""

    values: list[Mapping[str, Any]] = [
        candidate
        for lane in request_result.get("lanes") or ()
        if isinstance(lane, Mapping)
        for candidate in lane.get("candidates") or ()
        if isinstance(candidate, Mapping)
    ]
    active_hybrid = hybrid_result
    if active_hybrid is None:
        embedded = request_result.get("hybrid_object_retrieval")
        active_hybrid = embedded if isinstance(embedded, Mapping) else None
    if active_hybrid is not None:
        values.extend(
            candidate
            for candidate in (
                active_hybrid.get("candidate_decision_seed")
                or active_hybrid.get("candidates")
                or ()
            )
            if isinstance(candidate, Mapping)
        )
    rows: dict[str, dict[str, Any]] = {}
    for raw in values:
        value = deepcopy(dict(raw))
        identity = next(
            (
                str(value.get(field) or "")
                for field in (
                    "source_record_id",
                    "compiled_object_id",
                    "candidate_id",
                    "evidence_id",
                )
                if str(value.get(field) or "")
            ),
            canonical_digest(value),
        )
        rows.setdefault(identity, value)
    return tuple(rows[key] for key in sorted(rows))


def compile_product_projection_source_route_successor(
    *,
    product_projection: Mapping[str, Any],
    policy: SourceRoutePortfolioPolicy | Mapping[str, Any],
    research_sufficiency_by_request: Mapping[str, str] | None = None,
    registered_intake_routes: Sequence[Mapping[str, Any]] = (),
    intake_attempts: Sequence[Mapping[str, Any]] = (),
    route_attempt_receipts: Sequence[Mapping[str, Any]] = (),
    non_disclosure_receipts: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Attach source-route truth to an immutable zero-call product replay."""

    raw_requests = product_projection.get("request_results")
    _require(
        isinstance(raw_requests, list) and bool(raw_requests),
        "source_route_product_projection_requests_invalid",
    )
    request_rows: list[dict[str, Any]] = []
    state_counts: Counter[str] = Counter()
    coverage_counts: Counter[str] = Counter()
    for raw in raw_requests:
        _require(isinstance(raw, Mapping), "source_route_product_request_invalid")
        request_result = deepcopy(dict(raw))
        request_id = str(
            (request_result.get("request") or {}).get("request_id") or ""
        )
        research_sufficiency_state = str(
            (research_sufficiency_by_request or {}).get(
                request_id, "not_evaluated"
            )
        )
        hybrid = request_result.get("hybrid_object_retrieval")
        active_hybrid = hybrid if isinstance(hybrid, Mapping) else None
        truth = compile_source_route_execution_truth(
            request=request_result.get("request") or {},
            query_plan=request_result.get("query_plan") or {},
            policy=policy,
            local_candidate_rows=collect_source_route_candidate_rows(
                request_result, active_hybrid
            ),
            candidate_coverage_state=(
                candidate_coverage_state_from_hybrid_result(active_hybrid)
            ),
            research_sufficiency_state=research_sufficiency_state,
            registered_intake_routes=registered_intake_routes,
            intake_attempts=intake_attempts,
            route_attempt_receipts=route_attempt_receipts,
            non_disclosure_receipts=non_disclosure_receipts,
        )
        request_result["source_route_execution_truth"] = truth
        request_rows.append(request_result)
        coverage_counts[truth["candidate_coverage_state"]] += 1
        state_counts.update(truth["summary"]["route_execution_state_counts"])
    body = deepcopy(dict(product_projection))
    body.pop("projection_digest", None)
    body["request_results"] = request_rows
    summary = deepcopy(dict(body.get("summary") or {}))
    summary["source_route_execution"] = {
        "request_count": len(request_rows),
        "candidate_coverage_state_counts": dict(sorted(coverage_counts.items())),
        "supplement_route_required_request_count": sum(
            row["source_route_execution_truth"]["supplement_route_required"]
            for row in request_rows
        ),
        "official_or_external_supplement_route_exhausted_request_count": sum(
            row["source_route_execution_truth"]["summary"][
                "official_or_external_supplement_route_exhausted"
            ]
            for row in request_rows
        ),
        "public_information_gap_eligible_request_count": sum(
            row["source_route_execution_truth"]["summary"][
                "all_requirements_public_information_gap_eligible"
            ]
            for row in request_rows
        ),
        "route_execution_state_counts": dict(sorted(state_counts.items())),
        "network_calls": 0,
        "model_calls": 0,
        "vector_calls": 0,
    }
    body["summary"] = summary
    return {**body, "projection_digest": canonical_digest(body)}


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise SourceRouteDispatchError(code)


def _strings(value: Any, code: str, *, allow_star: bool = False) -> tuple[str, ...]:
    _require(isinstance(value, list) and bool(value), code)
    rows = tuple(str(item).strip() for item in value)
    _require(
        all(rows)
        and len(rows) == len(set(rows))
        and ("*" not in rows or (allow_star and rows == ("*",))),
        code,
    )
    return rows


@dataclass(frozen=True)
class SourceRouteSpec:
    route_id: str
    route_kind: str
    capability_state: str
    route_tier: str
    executor_id: str
    case_scope: tuple[str, ...]
    source_types: tuple[str, ...]
    source_roles: tuple[str, ...]
    capture_required: bool
    exhaustion_authority: bool
    exact_registry_required: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "route_kind": self.route_kind,
            "capability_state": self.capability_state,
            "route_tier": self.route_tier,
            "executor_id": self.executor_id,
            "case_scope": list(self.case_scope),
            "source_types": list(self.source_types),
            "source_roles": list(self.source_roles),
            "capture_required": self.capture_required,
            "exhaustion_authority": self.exhaustion_authority,
            "exact_registry_required": self.exact_registry_required,
        }


@dataclass(frozen=True)
class SourceRoutePortfolioPolicy:
    policy_id: str
    routes: tuple[SourceRouteSpec, ...]


def load_source_route_portfolio_policy(
    payload: Mapping[str, Any],
) -> SourceRoutePortfolioPolicy:
    _require(
        payload.get("schema_version") == SOURCE_ROUTE_POLICY_SCHEMA_VERSION,
        "source_route_policy_schema_invalid",
    )
    _require(
        payload.get("status") == "active_provider_neutral_source_route_portfolio",
        "source_route_policy_status_invalid",
    )
    policy = payload.get("policy")
    _require(
        isinstance(policy, Mapping)
        and policy.get("local_first") is True
        and policy.get("candidate_is_not_evidence") is True
        and policy.get("diagnostic_provider_cannot_prove_exhaustion") is True
        and policy.get("transport_failure_is_not_no_result") is True
        and policy.get("public_gap_requires_non_disclosure_adjudication") is True,
        "source_route_policy_controls_invalid",
    )
    raw_routes = payload.get("routes")
    _require(isinstance(raw_routes, list) and bool(raw_routes), "source_route_policy_routes_invalid")
    routes: list[SourceRouteSpec] = []
    seen: set[str] = set()
    for raw in raw_routes:
        _require(isinstance(raw, Mapping), "source_route_policy_route_invalid")
        route_id = str(raw.get("route_id") or "").strip()
        route_kind = str(raw.get("route_kind") or "").strip()
        capability_state = str(raw.get("capability_state") or "").strip()
        route_tier = str(raw.get("route_tier") or "").strip()
        executor_id = str(raw.get("executor_id") or "").strip()
        capture_required = raw.get("capture_required")
        exhaustion_authority = raw.get("exhaustion_authority")
        exact_registry_required = raw.get("exact_registry_required")
        _require(
            route_id
            and route_id not in seen
            and route_kind in _ROUTE_KINDS
            and capability_state in _CAPABILITY_STATES
            and route_tier in {"production", "diagnostic", "manual"}
            and executor_id
            and type(capture_required) is bool
            and type(exhaustion_authority) is bool
            and type(exact_registry_required) is bool,
            "source_route_policy_route_invalid",
        )
        if route_tier != "production" or route_kind in {
            "local_snapshot",
            "diagnostic_discovery",
            "operator_fallback",
        }:
            _require(not exhaustion_authority, "source_route_exhaustion_authority_invalid")
        if exhaustion_authority:
            _require(capture_required, "source_route_exhaustion_without_capture_invalid")
        if exact_registry_required:
            _require(
                capability_state == "available_when_exact_route_registered",
                "source_route_exact_registry_state_invalid",
            )
        routes.append(
            SourceRouteSpec(
                route_id=route_id,
                route_kind=route_kind,
                capability_state=capability_state,
                route_tier=route_tier,
                executor_id=executor_id,
                case_scope=tuple(value.upper() for value in _strings(raw.get("case_scope"), "source_route_case_scope_invalid", allow_star=True)),
                source_types=tuple(value.upper() for value in _strings(raw.get("source_types"), "source_route_source_types_invalid")),
                source_roles=_strings(raw.get("source_roles"), "source_route_source_roles_invalid"),
                capture_required=capture_required,
                exhaustion_authority=exhaustion_authority,
                exact_registry_required=exact_registry_required,
            )
        )
        seen.add(route_id)
    _require(
        sum(row.route_kind == "local_snapshot" for row in routes) == 1,
        "source_route_local_snapshot_count_invalid",
    )
    return SourceRoutePortfolioPolicy(
        policy_id=str(payload.get("policy_id") or "").strip(),
        routes=tuple(routes),
    )


def validate_source_route_attempt_receipt(payload: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(payload)
    digest = str(value.pop("attempt_digest", ""))
    state = str(value.get("status") or "")
    request_capture = str(value.get("request_capture_digest") or "")
    response_capture = str(value.get("response_capture_digest") or "")
    candidate_count = value.get("eligible_source_count")
    _require(
        value.get("schema_version") == SOURCE_ROUTE_ATTEMPT_SCHEMA_VERSION
        and str(value.get("attempt_id") or "")
        and str(value.get("route_id") or "")
        and str(value.get("requirement_id") or "")
        and state in _ATTEMPT_STATES
        and type(value.get("terminal")) is bool
        and type(candidate_count) is int
        and candidate_count >= 0
        and _HEX_64.fullmatch(digest) is not None
        and digest == canonical_digest(value),
        "source_route_attempt_receipt_invalid",
    )
    if state.startswith("terminal_"):
        _require(
            value["terminal"] is True
            and _HEX_64.fullmatch(request_capture) is not None
            and _HEX_64.fullmatch(response_capture) is not None,
            "source_route_terminal_capture_invalid",
        )
    else:
        _require(value["terminal"] is False, "source_route_failure_terminal_invalid")
    _require(
        (state == "terminal_no_eligible_source" and candidate_count == 0)
        or (state == "terminal_sources_captured" and candidate_count > 0)
        or not state.startswith("terminal_"),
        "source_route_terminal_count_invalid",
    )
    return {**value, "attempt_digest": digest}


def validate_source_non_disclosure_receipt(payload: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(payload)
    digest = str(value.pop("receipt_digest", ""))
    captures = value.get("reviewed_source_capture_digests")
    _require(
        value.get("schema_version") == SOURCE_NON_DISCLOSURE_SCHEMA_VERSION
        and str(value.get("requirement_id") or "")
        and value.get("adjudication_state") == "confirmed_non_disclosure"
        and isinstance(captures, list)
        and bool(captures)
        and all(_HEX_64.fullmatch(str(item)) for item in captures)
        and len(captures) == len(set(captures))
        and str(value.get("adjudicator_class") or "")
        in {"deterministic_source_contract", "qualified_human"}
        and _HEX_64.fullmatch(digest) is not None
        and digest == canonical_digest(value),
        "source_non_disclosure_receipt_invalid",
    )
    return {**value, "receipt_digest": digest}


def compile_source_route_execution_truth(
    *,
    request: Mapping[str, Any],
    query_plan: Mapping[str, Any],
    policy: SourceRoutePortfolioPolicy | Mapping[str, Any],
    local_candidate_rows: Sequence[Mapping[str, Any]] = (),
    candidate_coverage_state: str = "not_evaluated",
    research_sufficiency_state: str = "not_evaluated",
    registered_intake_routes: Sequence[Mapping[str, Any]] = (),
    intake_attempts: Sequence[Mapping[str, Any]] = (),
    route_attempt_receipts: Sequence[Mapping[str, Any]] = (),
    non_disclosure_receipts: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Compile request-bound source acquisition truth without performing I/O.

    Local retrieval, official-source acquisition, diagnostic web discovery and
    human upload remain separate.  A transport failure, an unconfigured route,
    or a diagnostic provider can never be re-labelled as public non-disclosure.
    """

    loaded = (
        load_source_route_portfolio_policy(policy)
        if isinstance(policy, Mapping)
        else policy
    )
    _require(
        candidate_coverage_state in {"complete", "incomplete", "not_evaluated"},
        "source_route_candidate_coverage_state_invalid",
    )
    _require(
        research_sufficiency_state
        in {"sufficient", "material_gap", "not_evaluated"},
        "source_route_research_sufficiency_state_invalid",
    )
    request_id = str(request.get("request_id") or "")
    case_key = str(request.get("case_key") or "").upper()
    subject = str(request.get("subject_ticker") or "").upper()
    _require(request_id and case_key and subject, "source_route_request_identity_invalid")
    _require(
        str(query_plan.get("case_key") or "").upper() == case_key
        and str(query_plan.get("subject_ticker") or "").upper() == subject
        and str(query_plan.get("research_as_of") or "")
        == str(request.get("research_as_of") or ""),
        "source_route_query_plan_identity_mismatch",
    )
    attempts = [validate_source_route_attempt_receipt(row) for row in route_attempt_receipts]
    non_disclosures = {
        str(row["requirement_id"]): row
        for row in (
            validate_source_non_disclosure_receipt(value)
            for value in non_disclosure_receipts
        )
    }
    _require(
        len(non_disclosures) == len(non_disclosure_receipts),
        "source_non_disclosure_receipt_duplicate",
    )
    registered = [_normalize_registered_route(row) for row in registered_intake_routes]
    intake = [_normalize_intake_attempt(row) for row in intake_attempts]
    candidates = [dict(row) for row in local_candidate_rows]
    supplement_trigger_reasons = []
    if candidate_coverage_state == "incomplete":
        supplement_trigger_reasons.append("candidate_coverage_incomplete")
    if research_sufficiency_state == "material_gap":
        supplement_trigger_reasons.append("material_research_gap")
    supplement_required = bool(supplement_trigger_reasons)
    requirements: list[dict[str, Any]] = []
    for raw_lane in query_plan.get("lanes") or ():
        _require(isinstance(raw_lane, Mapping), "source_route_query_lane_invalid")
        lane_id = str(raw_lane.get("lane_id") or "")
        source_types = tuple(str(value).upper() for value in raw_lane.get("source_types") or ())
        roles = tuple(str(value) for value in raw_lane.get("required_source_roles") or ())
        owners = raw_lane.get("owner_queries") or ()
        _require(lane_id and source_types and roles and owners, "source_route_query_lane_invalid")
        for owner_row in owners:
            _require(isinstance(owner_row, Mapping), "source_route_owner_query_invalid")
            owner = str(owner_row.get("evidence_owner_ticker") or "").upper()
            direction = str(owner_row.get("relationship_direction") or "")
            role = _role_for_owner(
                subject_ticker=subject,
                owner_ticker=owner,
                required_roles=roles,
            )
            identity = {
                "request_id": request_id,
                "lane_id": lane_id,
                "evidence_owner_ticker": owner,
                "relationship_direction": direction,
                "required_source_role": role,
                "source_types": list(source_types),
            }
            requirement_id = f"SRQ::{canonical_digest(identity)[:24]}"
            local_matches = [
                row
                for row in candidates
                if _candidate_owner(row) == owner
                and _candidate_source_type(row) in set(source_types)
            ]
            route_rows = [
                _project_route(
                    route=route,
                    evidence_owner_ticker=owner,
                    source_types=source_types,
                    source_role=role,
                    requirement_id=requirement_id,
                    local_matches=local_matches,
                    registered_routes=registered,
                    intake_attempts=intake,
                    route_attempts=attempts,
                    candidate_coverage_state=candidate_coverage_state,
                    supplement_required=supplement_required,
                )
                for route in loaded.routes
                if _route_applies(route, case_key, source_types, role)
            ]
            _require(
                any(row["route_kind"] == "local_snapshot" for row in route_rows),
                "source_route_local_route_missing",
            )
            production = [
                row
                for row in route_rows
                if row["supplement_required_for_current_gap"]
                and row["route_tier"] == "production"
                and row["exhaustion_authority"]
            ]
            all_terminal = bool(production) and all(
                row["terminal_for_gap_evaluation"] for row in production
            )
            disclosure = non_disclosures.get(requirement_id)
            public_gap = bool(all_terminal and disclosure is not None)
            requirements.append(
                {
                    "requirement_id": requirement_id,
                    **identity,
                    "candidate_coverage_state": candidate_coverage_state,
                    "research_sufficiency_state": research_sufficiency_state,
                    "supplement_trigger_reasons": list(
                        supplement_trigger_reasons
                    ),
                    "local_candidate_count": len(local_matches),
                    "local_candidate_source_types": sorted(
                        {_candidate_source_type(row) for row in local_matches}
                    ),
                    "source_routes": route_rows,
                    "required_production_supplement_route_count": len(production),
                    "required_production_supplement_routes_terminal": all_terminal,
                    "source_non_disclosure_adjudicated": disclosure is not None,
                    "source_non_disclosure_receipt_digest": (
                        disclosure.get("receipt_digest") if disclosure else None
                    ),
                    "public_information_gap_eligible": public_gap,
                }
            )
    _require(bool(requirements), "source_route_requirements_empty")
    state_counts = Counter(
        row["execution_state"]
        for requirement in requirements
        for row in requirement["source_routes"]
    )
    all_required_terminal = bool(supplement_required) and all(
        requirement["required_production_supplement_routes_terminal"]
        for requirement in requirements
    )
    body = {
        "schema_version": SOURCE_ROUTE_TRUTH_SCHEMA_VERSION,
        "status": "source_route_truth_compiled_public_gap_not_inferred",
        "policy_id": loaded.policy_id,
        "request_id": request_id,
        "case_key": case_key,
        "research_as_of": request.get("research_as_of"),
        "candidate_coverage_state": candidate_coverage_state,
        "research_sufficiency_state": research_sufficiency_state,
        "supplement_route_required": supplement_required,
        "supplement_trigger_reasons": supplement_trigger_reasons,
        "requirements": requirements,
        "summary": {
            "requirement_count": len(requirements),
            "route_execution_state_counts": dict(sorted(state_counts.items())),
            "required_production_supplement_routes_terminal": all_required_terminal,
            "official_or_external_supplement_route_exhausted": all_required_terminal,
            "all_requirements_public_information_gap_eligible": all(
                row["public_information_gap_eligible"] for row in requirements
            ),
            "public_information_gap_authority": False,
        },
        "authority": {
            "candidate_is_not_evidence": True,
            "numeric_authority": False,
            "source_capture_is_not_evidence": True,
            "diagnostic_route_has_gap_authority": False,
            "transport_failure_has_non_disclosure_authority": False,
        },
        "known_boundary": (
            "This projection records which local, official, market, industry, "
            "diagnostic and manual source routes are applicable and which actually "
            "reached a capture-bound terminal state. It does not execute a network "
            "request, promote Evidence, grant NumericFact authority, or infer public "
            "non-disclosure from an empty result, provider failure or missing adapter."
        ),
    }
    return {**body, "projection_digest": canonical_digest(body)}


def _role_for_owner(
    *, subject_ticker: str, owner_ticker: str, required_roles: Sequence[str]
) -> str:
    values = tuple(required_roles)
    if len(values) == 1:
        return values[0]
    if owner_ticker == subject_ticker and "issuer_disclosure" in values:
        return "issuer_disclosure"
    for role in ("related_entity_context", "related_entity_disclosure"):
        if owner_ticker != subject_ticker and role in values:
            return role
    if "point_in_time_market" in values:
        return "point_in_time_market"
    raise SourceRouteDispatchError("source_route_owner_role_ambiguous")


def _route_applies(
    route: SourceRouteSpec,
    case_key: str,
    source_types: Sequence[str],
    source_role: str,
) -> bool:
    return (
        (route.case_scope == ("*",) or case_key in route.case_scope)
        and bool(set(route.source_types).intersection(source_types))
        and source_role in route.source_roles
    )


def _project_route(
    *,
    route: SourceRouteSpec,
    evidence_owner_ticker: str,
    source_types: Sequence[str],
    source_role: str,
    requirement_id: str,
    local_matches: Sequence[Mapping[str, Any]],
    registered_routes: Sequence[Mapping[str, Any]],
    intake_attempts: Sequence[Mapping[str, Any]],
    route_attempts: Sequence[Mapping[str, Any]],
    candidate_coverage_state: str,
    supplement_required: bool,
) -> dict[str, Any]:
    matched_types = sorted(set(route.source_types).intersection(source_types))
    base = {
        **route.as_dict(),
        "matched_source_types": matched_types,
        "required_source_role": source_role,
        "supplement_required_for_current_gap": bool(
            supplement_required and route.route_kind != "local_snapshot"
        ),
        "terminal_for_gap_evaluation": False,
        "route_exhausted": False,
        "attempt_refs": [],
        "capture_digests": [],
    }
    if route.route_kind == "local_snapshot":
        return {
            **base,
            "execution_state": "executed_local_snapshot",
            "eligible_source_count": len(local_matches),
            "terminal_for_gap_evaluation": True,
        }
    if not supplement_required and candidate_coverage_state == "complete":
        return {
            **base,
            "execution_state": "not_required_local_candidate_set_complete",
            "eligible_source_count": 0,
        }
    if not supplement_required and candidate_coverage_state == "not_evaluated":
        return {
            **base,
            "execution_state": "not_scheduled_candidate_coverage_not_evaluated",
            "eligible_source_count": 0,
        }
    if route.exact_registry_required:
        exact = [
            row
            for row in registered_routes
            if row["case_key"] == evidence_owner_ticker
            and row["document_type"] in set(matched_types)
        ]
        if not exact:
            return {
                **base,
                "execution_state": "not_executed_no_registered_exact_route",
                "eligible_source_count": 0,
            }
        exact_ids = {row["route_id"] for row in exact}
        observed = [row for row in intake_attempts if row["route_id"] in exact_ids]
        captured = [row for row in observed if row["status"] == "captured_ready_for_parse"]
        failures = [row for row in observed if row["status"] == "acquisition_failed"]
        if captured:
            digests = sorted(
                {row["raw_object_sha256"] for row in captured if row["raw_object_sha256"]}
            )
            return {
                **base,
                "execution_state": "executed_exact_official_source_captured",
                "eligible_source_count": len(digests),
                "terminal_for_gap_evaluation": True,
                "route_exhausted": True,
                "attempt_refs": sorted(row["attempt_id"] for row in captured),
                "capture_digests": digests,
                "registered_route_ids": sorted(exact_ids),
            }
        if failures:
            return {
                **base,
                "execution_state": "executed_transport_failure_not_exhausted",
                "eligible_source_count": 0,
                "attempt_refs": sorted(row["attempt_id"] for row in failures),
                "registered_route_ids": sorted(exact_ids),
            }
        return {
            **base,
            "execution_state": "available_registered_exact_route_not_executed",
            "eligible_source_count": 0,
            "registered_route_ids": sorted(exact_ids),
        }
    observed = [
        row
        for row in route_attempts
        if row["route_id"] == route.route_id
        and row["requirement_id"] == requirement_id
    ]
    if observed:
        terminal = [row for row in observed if row["terminal"] is True]
        if terminal and route.route_tier == "production" and route.exhaustion_authority:
            latest = terminal[-1]
            capture_digests = sorted(
                {
                    str(latest["request_capture_digest"]),
                    str(latest["response_capture_digest"]),
                }
            )
            return {
                **base,
                "execution_state": str(latest["status"]),
                "eligible_source_count": int(latest["eligible_source_count"]),
                "terminal_for_gap_evaluation": True,
                "route_exhausted": True,
                "attempt_refs": [str(latest["attempt_id"])],
                "capture_digests": capture_digests,
            }
        return {
            **base,
            "execution_state": "executed_nonterminal_or_non_authoritative",
            "eligible_source_count": 0,
            "attempt_refs": [str(row["attempt_id"]) for row in observed],
        }
    state = {
        "available": "available_not_executed",
        "not_configured": "not_executed_not_configured",
        "manual_only": "not_executed_manual_fallback",
        "diagnostic_only": "not_executed_diagnostic_only",
        "available_when_exact_route_registered": "not_executed_no_registered_exact_route",
    }[route.capability_state]
    return {**base, "execution_state": state, "eligible_source_count": 0}


def _normalize_registered_route(value: Mapping[str, Any]) -> dict[str, str]:
    route_id = str(value.get("route_id") or "")
    case_key = str(value.get("case_key") or "").upper()
    document_type = str(value.get("document_type") or "").upper()
    _require(route_id and case_key and document_type, "source_route_registered_route_invalid")
    return {
        "route_id": route_id,
        "case_key": case_key,
        "document_type": document_type,
    }


def _normalize_intake_attempt(value: Mapping[str, Any]) -> dict[str, Any]:
    attempt_id = str(value.get("attempt_id") or "")
    route_id = str(value.get("route_id") or "")
    status = str(value.get("status") or "")
    digest = str(value.get("raw_object_sha256") or "")
    _require(
        attempt_id
        and route_id
        and status in {"captured_ready_for_parse", "captured_rejected", "acquisition_failed"}
        and (not digest or _HEX_64.fullmatch(digest) is not None),
        "source_route_intake_attempt_invalid",
    )
    return {
        "attempt_id": attempt_id,
        "route_id": route_id,
        "status": status,
        "raw_object_sha256": digest or None,
    }


def _candidate_owner(value: Mapping[str, Any]) -> str:
    return str(
        value.get("evidence_owner_ticker")
        or value.get("ticker")
        or value.get("source_ticker")
        or ""
    ).upper()


def _candidate_source_type(value: Mapping[str, Any]) -> str:
    return str(value.get("source_type") or value.get("form_type") or "").upper()


__all__ = [
    "SOURCE_NON_DISCLOSURE_SCHEMA_VERSION",
    "SOURCE_ROUTE_ATTEMPT_SCHEMA_VERSION",
    "SOURCE_ROUTE_POLICY_SCHEMA_VERSION",
    "SOURCE_ROUTE_TRUTH_SCHEMA_VERSION",
    "SourceRouteDispatchError",
    "SourceRoutePortfolioPolicy",
    "candidate_coverage_state_from_hybrid_result",
    "collect_source_route_candidate_rows",
    "compile_source_route_execution_truth",
    "compile_product_projection_source_route_successor",
    "load_source_route_portfolio_policy",
    "validate_source_non_disclosure_receipt",
    "validate_source_route_attempt_receipt",
]
