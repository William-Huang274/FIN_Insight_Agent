from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping

from apps.workbench.backend.application.fin_0_1_2_s4_natural_case_entry import (
    S4T01CompiledEntry,
    load_current_fin_0_1_2_s4_t01_case_entry,
)
from sec_agent.runtime_resource_registry import (
    RuntimeResource,
    RuntimeResourceRegistryError,
    load_runtime_resource_registry,
    read_registered_runtime_json,
)


CONTRACT_REF = (
    "fin_0_1_2.S4.three_case_retrieval_evidence_deterministic_readiness:v1"
)
AUTHORITY_SCHEMA = (
    "fin_ia_0_1_2_s4_t02_retrieval_evidence_readiness_authority_v1_0"
)
REGISTRY_REF = (
    "configs/runtime/fin_ia_0_1_2_s4_t02_runtime_resource_registry_v1_0.json"
)
AUTHORITY_RESOURCE_ID = "fin_0_1_2.s4.t02.authority"
INDEX_RESOURCE_ID = "fin_0_1_2.s4.t02.index_snapshot.public_source_summary"
EXPECTED_CASES = ("DELL", "MU", "NVDA")
EXPECTED_CELLS = (
    "bottleneck_counterevidence_and_what_would_change",
    "demand_authenticity_and_sustainability",
    "value_and_profit_capture",
)


class Fin012S4T02ReadinessError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _mapping(value: Any, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise Fin012S4T02ReadinessError(code)
    return value


def _strict_keys(value: Any, expected: set[str], code: str) -> Mapping[str, Any]:
    row = _mapping(value, code)
    if set(row) != expected:
        raise Fin012S4T02ReadinessError(code)
    return row


def _nonblank(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise Fin012S4T02ReadinessError(code)
    return value.strip()


def _string_list(value: Any, code: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise Fin012S4T02ReadinessError(code)
    rows = [_nonblank(item, code) for item in value]
    if rows != list(dict.fromkeys(rows)):
        raise Fin012S4T02ReadinessError(code)
    return rows


def _iso_date(value: Any, code: str) -> str:
    text = _nonblank(value, code)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Fin012S4T02ReadinessError(code) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).date().isoformat()


def _resource_projection(resource: RuntimeResource) -> dict[str, Any]:
    return {
        "resource_id": resource.resource_id,
        "repo_relative_path": resource.repo_relative_path,
        "sha256": resource.sha256,
        "bytes": resource.bytes,
    }


def _normalize_authority(authority: Mapping[str, Any]) -> dict[str, Any]:
    root = _strict_keys(
        authority,
        {
            "schema_version",
            "contract_ref",
            "status",
            "t01_contract_ref",
            "zero_call_budget",
            "candidate_policy",
            "parser_authority_policy",
            "index_snapshot_policy",
            "route_profiles",
            "cases",
            "nonpromotion_boundary",
            "authority_digest",
        },
        "s4_t02_authority_shape_invalid",
    )
    if root["schema_version"] != AUTHORITY_SCHEMA or root["contract_ref"] != CONTRACT_REF:
        raise Fin012S4T02ReadinessError("s4_t02_authority_identity_invalid")
    expected_digest = _digest({key: value for key, value in root.items() if key != "authority_digest"})
    if root["authority_digest"] != expected_digest:
        raise Fin012S4T02ReadinessError("s4_t02_authority_digest_mismatch")

    budget = _mapping(root["zero_call_budget"], "s4_t02_budget_invalid")
    zero_fields = (
        "model_calls",
        "provider_calls",
        "execution_network_calls",
        "source_network_calls",
        "external_tool_calls",
        "retrieval_calls",
        "store_writes",
        "token_budget",
    )
    if any(type(budget.get(field)) is not int or budget[field] != 0 for field in zero_fields):
        raise Fin012S4T02ReadinessError("s4_t02_budget_not_zero_call")
    if budget.get("cost_usd") != 0.0:
        raise Fin012S4T02ReadinessError("s4_t02_budget_cost_not_zero")

    candidate_policy = _mapping(
        root["candidate_policy"], "s4_t02_candidate_policy_invalid"
    )
    request_ceiling = candidate_policy.get("per_request_candidate_ceiling")
    case_ceiling = candidate_policy.get("per_case_candidate_ceiling")
    if (
        type(request_ceiling) is not int
        or request_ceiling < 1
        or type(case_ceiling) is not int
        or case_ceiling != request_ceiling * len(EXPECTED_CELLS)
        or candidate_policy.get("silent_truncation_allowed") is not False
        or candidate_policy.get("candidate_or_graph_hypothesis_is_current_evidence")
        is not False
    ):
        raise Fin012S4T02ReadinessError("s4_t02_candidate_ceiling_invalid")
    _string_list(
        candidate_policy.get("required_metadata"),
        "s4_t02_required_metadata_invalid",
    )

    routes = root["route_profiles"]
    if not isinstance(routes, list):
        raise Fin012S4T02ReadinessError("s4_t02_route_profiles_invalid")
    route_profiles: list[dict[str, Any]] = []
    for raw in routes:
        row = _strict_keys(
            raw,
            {
                "program_cell_id",
                "route_ids",
                "accepted_candidate_roles",
                "empty_candidate_gap_code",
            },
            "s4_t02_route_profile_invalid",
        )
        route_profiles.append(
            {
                "program_cell_id": _nonblank(
                    row["program_cell_id"], "s4_t02_route_cell_invalid"
                ),
                "route_ids": _string_list(
                    row["route_ids"], "s4_t02_route_ids_invalid"
                ),
                "accepted_candidate_roles": _string_list(
                    row["accepted_candidate_roles"],
                    "s4_t02_candidate_roles_invalid",
                ),
                "empty_candidate_gap_code": _nonblank(
                    row["empty_candidate_gap_code"],
                    "s4_t02_empty_gap_code_invalid",
                ),
            }
        )
    if tuple(row["program_cell_id"] for row in route_profiles) != EXPECTED_CELLS:
        raise Fin012S4T02ReadinessError("s4_t02_route_cell_set_invalid")

    cases = root["cases"]
    if not isinstance(cases, list):
        raise Fin012S4T02ReadinessError("s4_t02_cases_invalid")
    normalized_cases: list[dict[str, str]] = []
    for raw in cases:
        row = _strict_keys(
            raw,
            {
                "case_key",
                "expected_as_of",
                "source_mode",
                "source_resource_id",
                "freshness_disposition",
            },
            "s4_t02_case_policy_invalid",
        )
        normalized_cases.append({key: _nonblank(value, "s4_t02_case_policy_invalid") for key, value in row.items()})
    if tuple(row["case_key"] for row in normalized_cases) != EXPECTED_CASES:
        raise Fin012S4T02ReadinessError("s4_t02_case_set_invalid")

    nonpromotion = _mapping(
        root["nonpromotion_boundary"], "s4_t02_nonpromotion_invalid"
    )
    false_fields = (
        "runtime_promotion_authorized",
        "writer_citable",
        "domain_judgment_eligible",
        "persistence_authorized",
        "T03_execution_admission_created",
        "business_artifact_created",
        "NVDA_manifest_is_current_evidence",
        "DELL_MU_historical_rows_are_current_evidence",
    )
    if any(nonpromotion.get(field) is not False for field in false_fields):
        raise Fin012S4T02ReadinessError("s4_t02_false_promotion_boundary_invalid")
    return {
        **dict(root),
        "route_profiles": route_profiles,
        "cases": normalized_cases,
    }


@dataclass(frozen=True)
class RetrievalEvidenceRequest:
    request_id: str
    request_digest: str
    case_key: str
    program_cell_id: str
    objective_digest: str
    target_entity_ref: str
    as_of: str
    route_ids: tuple[str, ...]
    candidate_ceiling: int
    execution_admission: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "request_digest": self.request_digest,
            "case_key": self.case_key,
            "program_cell_id": self.program_cell_id,
            "objective_digest": self.objective_digest,
            "target_entity_ref": self.target_entity_ref,
            "as_of": self.as_of,
            "route_ids": list(self.route_ids),
            "candidate_ceiling": self.candidate_ceiling,
            "execution_admission": self.execution_admission,
        }


@dataclass(frozen=True)
class RetrievalRoutePlan:
    plan_id: str
    plan_digest: str
    request_id: str
    route_ids: tuple[str, ...]
    invocation_statuses: tuple[str, ...]
    planned_external_calls: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "plan_digest": self.plan_digest,
            "request_id": self.request_id,
            "route_ids": list(self.route_ids),
            "invocation_statuses": list(self.invocation_statuses),
            "planned_external_calls": self.planned_external_calls,
        }


@dataclass(frozen=True)
class CandidateQualificationDecision:
    candidate_id: str
    program_cell_id: str
    decision: str
    decision_codes: tuple[str, ...]
    source_snapshot_ref: str | None
    evidence_ref: str | None
    candidate_role: str | None
    citation_digest: str | None
    current_evidence_authorized: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "program_cell_id": self.program_cell_id,
            "decision": self.decision,
            "decision_codes": list(self.decision_codes),
            "source_snapshot_ref": self.source_snapshot_ref,
            "evidence_ref": self.evidence_ref,
            "candidate_role": self.candidate_role,
            "citation_digest": self.citation_digest,
            "current_evidence_authorized": self.current_evidence_authorized,
        }


@dataclass(frozen=True)
class CitationProjection:
    citation_id: str
    citation_digest: str
    candidate_id: str
    source_url: str
    locator: str
    source_snapshot_ref: str
    normalized_locator_snapshot_digest: str
    parser_adapter: str
    authority_scope: str
    writer_citable: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "citation_id": self.citation_id,
            "citation_digest": self.citation_digest,
            "candidate_id": self.candidate_id,
            "source_url": self.source_url,
            "locator": self.locator,
            "source_snapshot_ref": self.source_snapshot_ref,
            "normalized_locator_snapshot_digest": self.normalized_locator_snapshot_digest,
            "parser_adapter": self.parser_adapter,
            "authority_scope": self.authority_scope,
            "writer_citable": self.writer_citable,
        }


@dataclass(frozen=True)
class S4T02CaseReadinessReceipt:
    contract_ref: str
    authority_digest: str
    case_key: str
    t01_entry_digest: str
    source_resource: Mapping[str, Any]
    index_resource: Mapping[str, Any]
    source_freshness_disposition: str
    index_freshness_disposition: str
    request_digests: tuple[str, ...]
    route_plan_digests: tuple[str, ...]
    accepted_candidate_count: int
    rejected_candidate_count: int
    typed_gap_codes: tuple[str, ...]
    citation_count: int
    promoted_evidence_count: int
    observed_counts: Mapping[str, int]
    readiness_digest: str
    T03_authorized: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "contract_ref": self.contract_ref,
            "authority_digest": self.authority_digest,
            "case_key": self.case_key,
            "t01_entry_digest": self.t01_entry_digest,
            "source_resource": dict(self.source_resource),
            "index_resource": dict(self.index_resource),
            "source_freshness_disposition": self.source_freshness_disposition,
            "index_freshness_disposition": self.index_freshness_disposition,
            "request_digests": list(self.request_digests),
            "route_plan_digests": list(self.route_plan_digests),
            "accepted_candidate_count": self.accepted_candidate_count,
            "rejected_candidate_count": self.rejected_candidate_count,
            "typed_gap_codes": list(self.typed_gap_codes),
            "citation_count": self.citation_count,
            "promoted_evidence_count": self.promoted_evidence_count,
            "observed_counts": dict(self.observed_counts),
            "readiness_digest": self.readiness_digest,
            "T03_authorized": self.T03_authorized,
        }


@dataclass(frozen=True)
class S4T02CompiledReadiness:
    case_entry: S4T01CompiledEntry
    evidence_requests: tuple[RetrievalEvidenceRequest, ...]
    route_plans: tuple[RetrievalRoutePlan, ...]
    candidate_decisions: tuple[CandidateQualificationDecision, ...]
    citations: tuple[CitationProjection, ...]
    receipt: S4T02CaseReadinessReceipt

    def as_dict(self) -> dict[str, Any]:
        return {
            "NaturalCaseEntry": self.case_entry.as_dict(),
            "EvidenceRequests": [row.as_dict() for row in self.evidence_requests],
            "RoutePlans": [row.as_dict() for row in self.route_plans],
            "CandidateDecisions": [row.as_dict() for row in self.candidate_decisions],
            "CitationProjections": [row.as_dict() for row in self.citations],
            "S4T02ReadinessReceipt": self.receipt.as_dict(),
        }


def _build_requests_and_plans(
    *, entry: S4T01CompiledEntry, authority: Mapping[str, Any]
) -> tuple[tuple[RetrievalEvidenceRequest, ...], tuple[RetrievalRoutePlan, ...]]:
    profiles = {row["program_cell_id"]: row for row in authority["route_profiles"]}
    ceiling = int(authority["candidate_policy"]["per_request_candidate_ceiling"])
    requests: list[RetrievalEvidenceRequest] = []
    plans: list[RetrievalRoutePlan] = []
    for cell in sorted(entry.request.program_cells, key=lambda row: row["program_cell_id"]):
        cell_id = cell["program_cell_id"]
        if cell_id not in profiles:
            raise Fin012S4T02ReadinessError("s4_t02_case_cell_route_profile_missing")
        profile = profiles[cell_id]
        request_base = {
            "contract_ref": CONTRACT_REF,
            "t01_request_digest": entry.request.request_digest,
            "case_key": entry.request.case_key,
            "program_cell_id": cell_id,
            "objective_digest": _digest({"objective": cell["objective"]}),
            "target_entity_ref": entry.request.canonical_entity_ref,
            "as_of": entry.request.as_of,
            "route_ids": profile["route_ids"],
            "candidate_ceiling": ceiling,
            "execution_admission": "not_admitted",
        }
        request_digest = _digest(request_base)
        request = RetrievalEvidenceRequest(
            request_id=f"evidence_request_fin012_s4_t02_{request_digest[:20]}",
            request_digest=request_digest,
            **{key: value for key, value in request_base.items() if key not in {"contract_ref", "t01_request_digest"}},
        )
        plan_base = {
            "request_id": request.request_id,
            "request_digest": request.request_digest,
            "route_ids": list(request.route_ids),
            "invocation_statuses": ["not_executed"] * len(request.route_ids),
            "planned_external_calls": 0,
            "execution_admission": "not_admitted",
        }
        plan_digest = _digest(plan_base)
        plans.append(
            RetrievalRoutePlan(
                plan_id=f"route_plan_fin012_s4_t02_{plan_digest[:20]}",
                plan_digest=plan_digest,
                request_id=request.request_id,
                route_ids=request.route_ids,
                invocation_statuses=tuple(plan_base["invocation_statuses"]),
                planned_external_calls=0,
            )
        )
        requests.append(request)
    return tuple(requests), tuple(plans)


def _index_disposition(index: Mapping[str, Any], authority: Mapping[str, Any]) -> str:
    policy = _mapping(authority["index_snapshot_policy"], "s4_t02_index_policy_invalid")
    if (
        index.get("snapshot_id") != policy.get("snapshot_id")
        or index.get("as_of_date") != policy.get("as_of_date")
        or index.get("status") != "pass"
        or index.get("failed_source_count") != policy.get("required_failed_source_count")
    ):
        raise Fin012S4T02ReadinessError("s4_t02_index_snapshot_identity_invalid")
    successful = set(_string_list(index.get("successful_sources"), "s4_t02_index_sources_invalid"))
    required = set(_string_list(policy.get("required_successful_sources"), "s4_t02_index_policy_sources_invalid"))
    if not required.issubset(successful):
        raise Fin012S4T02ReadinessError("s4_t02_index_required_route_unreachable")
    return _nonblank(
        policy.get("current_case_evidence_status"),
        "s4_t02_index_disposition_invalid",
    )


def _candidate_role(cell_id: str) -> str:
    return {
        "bottleneck_counterevidence_and_what_would_change": "issuer_counterevidence_statement",
        "demand_authenticity_and_sustainability": "issuer_demand_statement",
        "value_and_profit_capture": "issuer_financial_statement",
    }[cell_id]


def _historical_pack_decisions(
    *,
    entry: S4T01CompiledEntry,
    source: Mapping[str, Any],
    authority: Mapping[str, Any],
) -> tuple[list[CandidateQualificationDecision], list[CitationProjection], set[str]]:
    case_key = entry.request.case_key
    if source.get("case_ticker") != case_key:
        raise Fin012S4T02ReadinessError("s4_t02_source_pack_cross_case_contamination")
    if _iso_date(source.get("as_of"), "s4_t02_source_pack_as_of_invalid") != _iso_date(
        entry.request.as_of, "s4_t02_entry_as_of_invalid"
    ):
        raise Fin012S4T02ReadinessError("s4_t02_source_pack_as_of_mismatch")
    snapshots_raw = source.get("source_snapshots")
    receipts_raw = source.get("route_execution_receipts")
    evidence_rows = source.get("evidence_rows")
    gap_rows = source.get("typed_gaps")
    if not all(isinstance(value, list) for value in (snapshots_raw, receipts_raw, evidence_rows, gap_rows)):
        raise Fin012S4T02ReadinessError("s4_t02_source_pack_collections_invalid")
    snapshots = {
        _nonblank(row.get("source_snapshot_ref"), "s4_t02_source_snapshot_ref_invalid"): _mapping(
            row, "s4_t02_source_snapshot_invalid"
        )
        for row in snapshots_raw
    }
    if len(snapshots) != len(snapshots_raw):
        raise Fin012S4T02ReadinessError("s4_t02_duplicate_source_snapshot_ref")
    receipts_by_snapshot: dict[str, list[Mapping[str, Any]]] = {}
    for raw in receipts_raw:
        row = _mapping(raw, "s4_t02_route_receipt_invalid")
        snapshot_ref = _nonblank(
            row.get("source_snapshot_ref"), "s4_t02_route_receipt_snapshot_invalid"
        )
        receipts_by_snapshot.setdefault(snapshot_ref, []).append(row)

    ceiling = int(authority["candidate_policy"]["per_request_candidate_ceiling"])
    decisions: list[CandidateQualificationDecision] = []
    citations: list[CitationProjection] = []
    typed_gaps: set[str] = set()
    for raw_gap in gap_rows:
        gap = _mapping(raw_gap, "s4_t02_gap_row_invalid")
        for cell_id in _string_list(
            gap.get("program_cell_ids"), "s4_t02_gap_cells_invalid"
        ):
            if cell_id not in EXPECTED_CELLS:
                raise Fin012S4T02ReadinessError("s4_t02_gap_cell_unknown")
        typed_gaps.add(_nonblank(gap.get("gap_code"), "s4_t02_gap_code_invalid"))

    for cell_id in EXPECTED_CELLS:
        rows: list[tuple[str, Mapping[str, Any], Mapping[str, Any]]] = []
        for raw in evidence_rows:
            evidence = _mapping(raw, "s4_t02_evidence_row_invalid")
            if evidence.get("entity_ref") != case_key:
                raise Fin012S4T02ReadinessError(
                    "s4_t02_source_pack_cross_case_contamination"
                )
            cells = _string_list(
                evidence.get("program_cell_ids"), "s4_t02_evidence_cells_invalid"
            )
            if cell_id not in cells:
                continue
            evidence_ref = _nonblank(
                evidence.get("evidence_ref"), "s4_t02_evidence_ref_invalid"
            )
            lineage = _mapping(
                evidence.get("parser_lineage"), "s4_t02_parser_lineage_invalid"
            )
            snapshot_ref = _nonblank(
                lineage.get("source_snapshot_ref"),
                "s4_t02_parser_snapshot_ref_invalid",
            )
            snapshot = snapshots.get(snapshot_ref)
            if snapshot is None:
                decisions.append(
                    CandidateQualificationDecision(
                        candidate_id=evidence_ref,
                        program_cell_id=cell_id,
                        decision="rejected",
                        decision_codes=("source_snapshot_unbound",),
                        source_snapshot_ref=snapshot_ref,
                        evidence_ref=evidence_ref,
                        candidate_role=None,
                        citation_digest=None,
                        current_evidence_authorized=False,
                    )
                )
                continue
            rows.append((evidence_ref, evidence, snapshot))

        rows.sort(key=lambda item: item[0])
        rows.sort(
            key=lambda item: str(item[2].get("published_at") or ""),
            reverse=True,
        )
        for position, (evidence_ref, evidence, snapshot) in enumerate(rows):
            snapshot_ref = str(evidence["parser_lineage"]["source_snapshot_ref"])
            codes: list[str] = []
            source_url = str(evidence.get("source_url") or "").strip()
            locator = str(evidence.get("citation") or "").strip()
            parser_adapter = str(evidence["parser_lineage"].get("adapter") or "").strip()
            snapshot_adapter = str(snapshot.get("retrieval_channel") or "").strip()
            snapshot_digest = str(
                snapshot.get("normalized_locator_snapshot_digest") or ""
            ).strip()
            route_receipts = receipts_by_snapshot.get(snapshot_ref, [])
            if not source_url.startswith("https://"):
                codes.append("citation_url_not_https")
            if not locator:
                codes.append("citation_locator_missing")
            if not parser_adapter or parser_adapter != snapshot_adapter:
                codes.append("parser_authority_mismatch")
            if len(snapshot_digest) != 64:
                codes.append("source_snapshot_digest_invalid")
            if snapshot.get("fetch_status") != "success":
                codes.append("source_snapshot_fetch_not_success")
            if not any(
                row.get("fetch_status") == "success"
                and str(row.get("parser_status") or "").startswith("executed_")
                and str(row.get("route_execution_status") or "").startswith("executed_")
                for row in route_receipts
            ):
                codes.append("route_parser_execution_receipt_missing")
            if position >= ceiling:
                codes.append("candidate_ceiling_exceeded_fixture_only")
            role = _candidate_role(cell_id)
            if codes:
                decisions.append(
                    CandidateQualificationDecision(
                        candidate_id=evidence_ref,
                        program_cell_id=cell_id,
                        decision="rejected",
                        decision_codes=tuple(sorted(set(codes))),
                        source_snapshot_ref=snapshot_ref,
                        evidence_ref=evidence_ref,
                        candidate_role=role,
                        citation_digest=None,
                        current_evidence_authorized=False,
                    )
                )
                continue
            citation_base = {
                "case_key": case_key,
                "program_cell_id": cell_id,
                "candidate_id": evidence_ref,
                "source_url": source_url,
                "locator": locator,
                "source_snapshot_ref": snapshot_ref,
                "normalized_locator_snapshot_digest": snapshot_digest,
                "parser_adapter": parser_adapter,
                "authority_scope": _nonblank(
                    evidence.get("authority_scope"),
                    "s4_t02_authority_scope_invalid",
                ),
                "writer_citable": False,
            }
            citation_digest = _digest(citation_base)
            citations.append(
                CitationProjection(
                    citation_id=f"citation_fin012_s4_t02_{citation_digest[:20]}",
                    citation_digest=citation_digest,
                    **{key: value for key, value in citation_base.items() if key not in {"case_key", "program_cell_id"}},
                )
            )
            decisions.append(
                CandidateQualificationDecision(
                    candidate_id=evidence_ref,
                    program_cell_id=cell_id,
                    decision="historical_fixture_accepted_for_readiness_only",
                    decision_codes=("current_promotion_not_authorized",),
                    source_snapshot_ref=snapshot_ref,
                    evidence_ref=evidence_ref,
                    candidate_role=role,
                    citation_digest=citation_digest,
                    current_evidence_authorized=False,
                )
            )
    return decisions, citations, typed_gaps


def _manifest_only_decisions(
    *, entry: S4T01CompiledEntry, source: Mapping[str, Any], authority: Mapping[str, Any]
) -> tuple[list[CandidateQualificationDecision], list[CitationProjection], set[str]]:
    case = _mapping(source.get("case"), "s4_t02_nvda_manifest_case_invalid")
    if case.get("company") != entry.request.case_key:
        raise Fin012S4T02ReadinessError("s4_t02_nvda_manifest_cross_case")
    if _iso_date(case.get("as_of"), "s4_t02_nvda_manifest_as_of_invalid") != _iso_date(
        entry.request.as_of, "s4_t02_entry_as_of_invalid"
    ):
        raise Fin012S4T02ReadinessError("s4_t02_nvda_manifest_as_of_mismatch")
    boundary = _mapping(
        source.get("nonpromotion_boundary"), "s4_t02_nvda_nonpromotion_invalid"
    )
    if boundary.get("historical_artifacts_promoted_as_current") is not False:
        raise Fin012S4T02ReadinessError("s4_t02_nvda_false_promotion_boundary")
    profiles = {row["program_cell_id"]: row for row in authority["route_profiles"]}
    gaps = {profiles[cell_id]["empty_candidate_gap_code"] for cell_id in EXPECTED_CELLS}
    return [], [], gaps


def compile_fin_0_1_2_s4_t02_case_readiness(
    *,
    authority: Mapping[str, Any],
    resources_by_id: Mapping[str, RuntimeResource],
    case_entry: S4T01CompiledEntry,
    source_payload: Mapping[str, Any],
    index_payload: Mapping[str, Any],
) -> S4T02CompiledReadiness:
    normalized = _normalize_authority(authority)
    case_key = case_entry.request.case_key
    try:
        case_policy = next(row for row in normalized["cases"] if row["case_key"] == case_key)
    except StopIteration as exc:
        raise Fin012S4T02ReadinessError("s4_t02_case_unknown") from exc
    if _iso_date(case_policy["expected_as_of"], "s4_t02_case_expected_as_of_invalid") != _iso_date(
        case_entry.request.as_of, "s4_t02_entry_as_of_invalid"
    ):
        raise Fin012S4T02ReadinessError("s4_t02_t01_case_as_of_drift")
    if case_entry.receipt.T02_authorized is not False:
        raise Fin012S4T02ReadinessError("s4_t02_t01_entry_authority_drift")
    source_resource = resources_by_id.get(case_policy["source_resource_id"])
    index_resource = resources_by_id.get(INDEX_RESOURCE_ID)
    if source_resource is None or index_resource is None:
        raise Fin012S4T02ReadinessError("s4_t02_runtime_resource_missing")
    t01_source = case_entry.snapshot_binding.source_snapshot
    if {
        "repo_relative_path": source_resource.repo_relative_path,
        "sha256": source_resource.sha256,
        "bytes": source_resource.bytes,
    } != {
        "repo_relative_path": t01_source["repo_relative_path"],
        "sha256": t01_source["sha256"],
        "bytes": t01_source["bytes"],
    }:
        raise Fin012S4T02ReadinessError("s4_t02_t01_source_snapshot_binding_drift")
    t01_index = case_entry.snapshot_binding.index_snapshot
    if {
        "repo_relative_path": index_resource.repo_relative_path,
        "sha256": index_resource.sha256,
        "bytes": index_resource.bytes,
    } != {
        "repo_relative_path": t01_index["repo_relative_path"],
        "sha256": t01_index["sha256"],
        "bytes": t01_index["bytes"],
    }:
        raise Fin012S4T02ReadinessError("s4_t02_t01_index_snapshot_binding_drift")

    requests, plans = _build_requests_and_plans(
        entry=case_entry, authority=normalized
    )
    index_disposition = _index_disposition(index_payload, normalized)
    if case_policy["source_mode"] == "historical_source_pack_readiness_fixture":
        decisions, citations, typed_gaps = _historical_pack_decisions(
            entry=case_entry,
            source=source_payload,
            authority=normalized,
        )
    elif case_policy["source_mode"] == "manifest_only_current_search_required":
        decisions, citations, typed_gaps = _manifest_only_decisions(
            entry=case_entry,
            source=source_payload,
            authority=normalized,
        )
    else:
        raise Fin012S4T02ReadinessError("s4_t02_source_mode_invalid")

    decisions = sorted(
        decisions,
        key=lambda row: (row.program_cell_id, row.candidate_id, row.decision),
    )
    citations = sorted(citations, key=lambda row: row.citation_id)
    accepted = sum(
        row.decision == "historical_fixture_accepted_for_readiness_only"
        for row in decisions
    )
    rejected = sum(row.decision == "rejected" for row in decisions)
    ceiling = int(normalized["candidate_policy"]["per_case_candidate_ceiling"])
    if accepted > ceiling:
        raise Fin012S4T02ReadinessError("s4_t02_case_candidate_ceiling_exceeded")
    if len(citations) != accepted:
        raise Fin012S4T02ReadinessError("s4_t02_accepted_candidate_citation_mismatch")
    if any(row.current_evidence_authorized for row in decisions) or any(
        row.writer_citable for row in citations
    ):
        raise Fin012S4T02ReadinessError("s4_t02_false_evidence_promotion")

    receipt_base = {
        "contract_ref": CONTRACT_REF,
        "authority_digest": normalized["authority_digest"],
        "case_key": case_key,
        "t01_entry_digest": case_entry.receipt.entry_digest,
        "source_resource": _resource_projection(source_resource),
        "index_resource": _resource_projection(index_resource),
        "source_freshness_disposition": case_policy["freshness_disposition"],
        "index_freshness_disposition": index_disposition,
        "request_digests": [row.request_digest for row in requests],
        "route_plan_digests": [row.plan_digest for row in plans],
        "accepted_candidate_count": accepted,
        "rejected_candidate_count": rejected,
        "typed_gap_codes": sorted(typed_gaps),
        "citation_count": len(citations),
        "promoted_evidence_count": 0,
        "T03_authorized": False,
        "observed_counts": {
            "model_calls": 0,
            "provider_calls": 0,
            "execution_network_calls": 0,
            "source_network_calls": 0,
            "external_tool_calls": 0,
            "retrieval_calls": 0,
            "store_writes": 0,
            "business_artifacts": 0,
        },
    }
    receipt = S4T02CaseReadinessReceipt(
        **{
            key: value
            for key, value in receipt_base.items()
            if key
            not in {
                "request_digests",
                "route_plan_digests",
                "typed_gap_codes",
            }
        },
        request_digests=tuple(receipt_base["request_digests"]),
        route_plan_digests=tuple(receipt_base["route_plan_digests"]),
        typed_gap_codes=tuple(receipt_base["typed_gap_codes"]),
        readiness_digest=_digest(receipt_base),
    )
    return S4T02CompiledReadiness(
        case_entry=case_entry,
        evidence_requests=requests,
        route_plans=plans,
        candidate_decisions=tuple(decisions),
        citations=tuple(citations),
        receipt=receipt,
    )


def _repository_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / REGISTRY_REF).is_file():
            return parent
    raise Fin012S4T02ReadinessError("s4_t02_repository_root_not_found")


@lru_cache(maxsize=1)
def load_fin_0_1_2_s4_t02_authority_and_resources() -> tuple[
    dict[str, Any], Mapping[str, RuntimeResource]
]:
    root = _repository_root()
    try:
        registry = load_runtime_resource_registry(root, REGISTRY_REF)
        authority = read_registered_runtime_json(
            root,
            AUTHORITY_RESOURCE_ID,
            registry_ref=REGISTRY_REF,
        )
    except RuntimeResourceRegistryError as exc:
        raise Fin012S4T02ReadinessError(
            "s4_t02_runtime_resource_authority_invalid"
        ) from exc
    return authority, registry.by_id()


def load_current_fin_0_1_2_s4_t02_readiness(case_key: str) -> S4T02CompiledReadiness:
    """Current zero-call Runtime consumer; it never invokes retrieval or promotes Evidence."""

    authority, resources = load_fin_0_1_2_s4_t02_authority_and_resources()
    try:
        case_policy = next(
            row for row in authority["cases"] if row.get("case_key") == case_key
        )
    except (KeyError, StopIteration) as exc:
        raise Fin012S4T02ReadinessError("s4_t02_case_unknown") from exc
    root = _repository_root()
    try:
        source = read_registered_runtime_json(
            root,
            case_policy["source_resource_id"],
            registry_ref=REGISTRY_REF,
        )
        index = read_registered_runtime_json(
            root,
            INDEX_RESOURCE_ID,
            registry_ref=REGISTRY_REF,
        )
    except RuntimeResourceRegistryError as exc:
        raise Fin012S4T02ReadinessError("s4_t02_runtime_resource_read_invalid") from exc
    return compile_fin_0_1_2_s4_t02_case_readiness(
        authority=authority,
        resources_by_id=resources,
        case_entry=load_current_fin_0_1_2_s4_t01_case_entry(case_key),
        source_payload=source,
        index_payload=index,
    )


def load_current_fin_0_1_2_s4_t02_three_case_readiness() -> tuple[
    S4T02CompiledReadiness, ...
]:
    return tuple(load_current_fin_0_1_2_s4_t02_readiness(case) for case in EXPECTED_CASES)
