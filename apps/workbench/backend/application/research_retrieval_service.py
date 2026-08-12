from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from financial_facts import execute_typed_fact_request
from retrieval.contracts import (
    FinancialResearchKernel,
    RetrievalContractError,
    load_evidence_request,
    load_financial_research_kernel,
)
from retrieval.query_plan import compile_query_facet_plan_for_request
from retrieval.route_compiler import (
    QueryObjectFactRoutePolicy,
    compile_retrieval_execution_plan,
    load_query_object_fact_route_policy,
)
from sec_agent.runtime_resource_registry import read_registered_runtime_json
from sec_agent.research.reviewed_evidence_pack import canonical_digest
from sec_agent.runtime_bridge.paths import RuntimePathRegistry, resolve_runtime_paths


CURRENT_RETRIEVAL_SNAPSHOT_RESOURCE_ID = (
    "application.result.current_research_retrieval_snapshot"
)
CURRENT_RANKING_COMPARISON_RESOURCE_ID = (
    "application.result.current_s1c_ranking_comparison_projection"
)
CURRENT_RETRIEVAL_KERNEL_RESOURCE_ID = (
    "application.config.current_financial_research_kernel"
)
CURRENT_QUERY_OBJECT_FACT_ROUTE_POLICY_RESOURCE_ID = (
    "application.config.current_query_object_fact_route_policy"
)
EXPECTED_SCHEMA = "fin_ia_current_retrieval_snapshot_v1_0"
EXPECTED_RANKING_SCHEMA = "fin_ia_s1c_ranking_workbench_projection_v1_0"
RETRIEVAL_PROJECTION_SCHEMA = "fin_ia_research_retrieval_projection_v1_0"
REQUEST_RETRIEVAL_PROJECTION_SCHEMA = (
    "fin_ia_request_scoped_retrieval_projection_v1_2"
)


@dataclass(frozen=True)
class ResearchRetrievalPrincipal:
    mode: str
    permissions: frozenset[str]


class ResearchRetrievalServiceError(RuntimeError):
    def __init__(self, error_code: str, status_code: int = 500, **detail: Any):
        super().__init__(error_code)
        self.error_code = error_code
        self.status_code = status_code
        self.detail = {"reason": error_code, **detail}


class ResearchRetrievalService:
    """Read-only product projection of the current S1 retrieval snapshot."""

    def __init__(
        self,
        *,
        snapshot: Mapping[str, Any],
        ranking_comparison: Mapping[str, Any] | None = None,
        kernel: FinancialResearchKernel | Mapping[str, Any] | None = None,
        route_policy: QueryObjectFactRoutePolicy | Mapping[str, Any] | None = None,
        company_financial_fact_mart_path: str | Path | None = None,
    ) -> None:
        self._snapshot = self._validate(snapshot)
        self._cases = {
            str(row["case_key"]): deepcopy(dict(row))
            for row in self._snapshot["cases"]
        }
        self._ranking = (
            self._validate_ranking(ranking_comparison)
            if ranking_comparison is not None
            else None
        )
        self._ranking_cases = (
            {
                str(row["case_key"]): deepcopy(dict(row))
                for row in self._ranking["cases"]
            }
            if self._ranking is not None
            else {}
        )
        self._kernel = (
            load_financial_research_kernel(kernel)
            if isinstance(kernel, Mapping)
            else kernel
        )
        if route_policy is not None and self._kernel is None:
            raise ResearchRetrievalServiceError(
                "research_retrieval_route_policy_without_kernel", 503
            )
        self._route_policy = (
            load_query_object_fact_route_policy(route_policy, self._kernel)
            if isinstance(route_policy, Mapping) and self._kernel is not None
            else route_policy
        )
        self._company_financial_fact_mart_path = (
            Path(company_financial_fact_mart_path).resolve()
            if company_financial_fact_mart_path is not None
            else None
        )

    @classmethod
    def from_runtime_paths(
        cls,
        repository_root: str | Path,
        runtime_paths: RuntimePathRegistry | None = None,
    ) -> "ResearchRetrievalService":
        paths = runtime_paths or resolve_runtime_paths(repository_root)
        return cls(
            snapshot=read_registered_runtime_json(
                repository_root,
                CURRENT_RETRIEVAL_SNAPSHOT_RESOURCE_ID,
            ),
            ranking_comparison=read_registered_runtime_json(
                repository_root,
                CURRENT_RANKING_COMPARISON_RESOURCE_ID,
            ),
            kernel=read_registered_runtime_json(
                repository_root,
                CURRENT_RETRIEVAL_KERNEL_RESOURCE_ID,
            ),
            route_policy=read_registered_runtime_json(
                repository_root,
                CURRENT_QUERY_OBJECT_FACT_ROUTE_POLICY_RESOURCE_ID,
            ),
            company_financial_fact_mart_path=(
                paths.company_financial_fact_mart_path
            ),
        )

    def get_case(
        self,
        case_key: str,
        principal: ResearchRetrievalPrincipal,
    ) -> dict[str, Any]:
        self._require_read(principal)
        key = str(case_key).strip().upper()
        row = self._cases.get(key)
        if row is None:
            raise ResearchRetrievalServiceError(
                "research_retrieval_case_not_found", 404, case_key=case_key
            )
        retrieval = row["retrieval"]
        lanes = []
        for lane in retrieval["lane_results"]:
            lane_contract = lane["lane"]
            candidates = []
            for raw_candidate in lane["candidates"]:
                candidate = deepcopy(dict(raw_candidate))
                candidate.pop("reviewed_pack_match", None)
                candidates.append(candidate)
            lanes.append(
                {
                    "lane_id": lane_contract["lane_id"],
                    "slot_id": lane_contract["slot_id"],
                    "facet_id": lane_contract["facet_id"],
                    "business_question_zh": lane_contract["business_question_zh"],
                    "evidence_owner_tickers": deepcopy(
                        lane_contract["evidence_owner_tickers"]
                    ),
                    "required_source_roles": deepcopy(
                        lane_contract["required_source_roles"]
                    ),
                    "publication_date_lte": lane_contract["publication_date_lte"],
                    "candidates": candidates,
                    "missing_required_source_roles": deepcopy(
                        lane["missing_required_source_roles"]
                    ),
                    "exclusion_counts": deepcopy(lane["exclusion_counts"]),
                }
            )
        raw_summary = retrieval["summary"]
        summary = {
            key: deepcopy(raw_summary[key])
            for key in (
                "lane_count",
                "nonempty_lane_count",
                "slot_count",
                "unique_candidates",
                "slots_missing_required_source_roles",
                "hard_constraint_failures",
            )
        }
        body = {
            "schema_version": RETRIEVAL_PROJECTION_SCHEMA,
            "status": "typed_local_retrieval_snapshot_ready",
            "product_mode": "current",
            "case_key": key,
            "candidate_state": "candidate_not_evidence",
            "query_plan_digest": retrieval["query_plan_digest"],
            "result_digest": retrieval["result_digest"],
            "source_snapshot": deepcopy(self._snapshot["source_snapshot"]),
            "summary": summary,
            "source_gap_summary": deepcopy(row["source_gap_summary"]),
            "business_findings_zh": deepcopy(row["business_findings_zh"]),
            "ranking_comparison": self._ranking_projection_for_case(key),
            "lanes": lanes,
            "known_boundary": str(self._snapshot["known_boundary"]),
        }
        return {**body, "projection_digest": canonical_digest(body)}

    def execute_request(
        self,
        case_key: str,
        payload: Mapping[str, Any],
        principal: ResearchRetrievalPrincipal,
    ) -> dict[str, Any]:
        """Execute a typed request against the immutable current candidate snapshot."""

        self._require_read(principal)
        if self._kernel is None:
            raise ResearchRetrievalServiceError(
                "research_retrieval_kernel_unavailable", 503
            )
        try:
            request = load_evidence_request(payload, self._kernel)
            plan = compile_query_facet_plan_for_request(self._kernel, request)
            execution_plan = (
                compile_retrieval_execution_plan(
                    self._route_policy,
                    request,
                    fact_store_availability={
                        "company_financial_fact_mart": (
                            self._company_fact_mart_available()
                        )
                    },
                )
                if self._route_policy is not None
                else None
            )
        except RetrievalContractError as exc:
            raise ResearchRetrievalServiceError(str(exc), 422) from exc
        key = str(case_key).strip().upper()
        if key != request.case_key:
            raise ResearchRetrievalServiceError(
                "evidence_request_route_case_mismatch",
                422,
                route_case_key=key,
                request_case_key=request.case_key,
            )
        case = self._cases.get(key)
        if case is None:
            raise ResearchRetrievalServiceError(
                "research_retrieval_case_not_found", 404, case_key=case_key
            )
        retrieval = case["retrieval"]
        snapshot_lanes = {
            str(row["lane"]["lane_id"]): row
            for row in retrieval["lane_results"]
        }
        request_payload = request.as_dict()
        request_digest = canonical_digest(request_payload)
        lanes: list[dict[str, Any]] = []
        typed_gaps: list[dict[str, Any]] = (
            [dict(row) for row in execution_plan.typed_gaps]
            if execution_plan is not None
            else []
        )
        typed_fact_results: list[dict[str, Any]] = []
        if execution_plan is not None:
            for fact_request in execution_plan.typed_fact_requests:
                if fact_request.execution_status != "ready_for_typed_fact_executor":
                    continue
                if self._company_financial_fact_mart_path is None:
                    raise ResearchRetrievalServiceError(
                        "company_financial_fact_mart_path_unavailable", 503
                    )
                result = execute_typed_fact_request(
                    self._company_financial_fact_mart_path,
                    fact_request,
                )
                typed_fact_results.append(result.as_dict())
                if result.status == "typed_gap" and result.typed_gap:
                    typed_gaps.append(
                        {
                            **dict(result.typed_gap),
                            "fact_request_id": result.fact_request_id,
                            "metric_id": result.metric_id,
                            "target_entity": result.ticker,
                            "owning_stage": "S2",
                            "disposition": request.clarification_policy,
                        }
                    )
                elif result.status == "typed_conflict":
                    typed_gaps.append(
                        {
                            "gap_code": "typed_fact_conflict",
                            "fact_request_id": result.fact_request_id,
                            "metric_id": result.metric_id,
                            "target_entity": result.ticker,
                            "owning_stage": "S2",
                            "disposition": "fail_closed",
                        }
                    )
        seen_candidates: set[str] = set()
        for lane in plan.lanes:
            snapshot_lane = snapshot_lanes.get(lane.lane_id)
            if snapshot_lane is None:
                raise ResearchRetrievalServiceError(
                    "research_request_snapshot_lane_missing",
                    503,
                    lane_id=lane.lane_id,
                )
            contract = snapshot_lane["lane"]
            if not (
                contract.get("slot_id") == lane.slot_id
                and contract.get("facet_id") == lane.facet_id
                and contract.get("subject_ticker") == lane.subject_ticker
                and contract.get("publication_date_lte")
                == lane.publication_date_lte
                and set(lane.evidence_owner_tickers).issubset(
                    contract.get("evidence_owner_tickers") or ()
                )
                and set(lane.source_types).issubset(
                    contract.get("source_types") or ()
                )
            ):
                raise ResearchRetrievalServiceError(
                    "research_request_snapshot_contract_drift",
                    503,
                    lane_id=lane.lane_id,
                )
            filtered: list[dict[str, Any]] = []
            period_exclusions: dict[str, int] = {}
            for raw_candidate in snapshot_lane["candidates"]:
                candidate = deepcopy(dict(raw_candidate))
                if candidate.get("evidence_owner_ticker") not in set(
                    lane.evidence_owner_tickers
                ):
                    continue
                if candidate.get("source_type") not in set(lane.source_types):
                    continue
                if not self._candidate_matches_period(candidate, request.period):
                    period_exclusions["outside_requested_reporting_period"] = (
                        period_exclusions.get(
                            "outside_requested_reporting_period", 0
                        )
                        + 1
                    )
                    continue
                candidate.pop("reviewed_pack_match", None)
                filtered.append(candidate)
                seen_candidates.add(str(candidate["source_record_id"]))
            observed_roles = {
                str(candidate.get("source_role") or "") for candidate in filtered
            }
            missing_roles = sorted(set(lane.required_source_roles) - observed_roles)
            if not filtered:
                typed_gaps.append(
                    {
                        "gap_code": "request_scoped_candidate_gap",
                        "lane_id": lane.lane_id,
                        "facet_id": lane.facet_id,
                        "disposition": request.clarification_policy,
                    }
                )
            if missing_roles:
                typed_gaps.append(
                    {
                        "gap_code": "request_scoped_source_role_gap",
                        "lane_id": lane.lane_id,
                        "facet_id": lane.facet_id,
                        "missing_source_roles": missing_roles,
                        "disposition": request.clarification_policy,
                    }
                )
            lanes.append(
                {
                    "lane": lane.as_dict(),
                    "candidate_state": "candidate_not_evidence",
                    "candidates": filtered,
                    "missing_required_source_roles": missing_roles,
                    "snapshot_exclusion_counts": deepcopy(
                        snapshot_lane["exclusion_counts"]
                    ),
                    "request_exclusion_counts": period_exclusions,
                }
            )
        body = {
            "schema_version": REQUEST_RETRIEVAL_PROJECTION_SCHEMA,
            "status": "request_scoped_typed_local_retrieval_ready",
            "product_mode": "current",
            "case_key": key,
            "candidate_state": "candidate_not_evidence",
            "execution_mode": "immutable_current_snapshot_filtering",
            "request": request_payload,
            "request_digest": request_digest,
            "query_plan": plan.as_dict(),
            "execution_plan": (
                execution_plan.as_dict() if execution_plan is not None else None
            ),
            "source_snapshot": deepcopy(self._snapshot["source_snapshot"]),
            "summary": {
                "requested_facet_count": len(request.requested_facet_ids),
                "compiled_lane_count": len(lanes),
                "nonempty_lane_count": sum(bool(row["candidates"]) for row in lanes),
                "unique_candidates": len(seen_candidates),
                "typed_gap_count": len(typed_gaps),
                "narrative_route_request_count": (
                    len(execution_plan.narrative_requests)
                    if execution_plan is not None
                    else 0
                ),
                "typed_fact_request_count": (
                    len(execution_plan.typed_fact_requests)
                    if execution_plan is not None
                    else 0
                ),
                "typed_fact_store_ready_count": (
                    sum(
                        row.execution_status == "ready_for_typed_fact_executor"
                        for row in execution_plan.typed_fact_requests
                    )
                    if execution_plan is not None
                    else 0
                ),
                "typed_fact_resolved_count": sum(
                    row["status"] == "resolved" for row in typed_fact_results
                ),
                "typed_fact_gap_count": sum(
                    row["status"] == "typed_gap" for row in typed_fact_results
                ),
                "typed_fact_conflict_count": sum(
                    row["status"] == "typed_conflict"
                    for row in typed_fact_results
                ),
                "network_calls": 0,
                "model_calls": 0,
            },
            "typed_gaps": typed_gaps,
            "typed_fact_results": typed_fact_results,
            "lanes": lanes,
            "known_boundary": (
                "This endpoint consumes a typed EvidenceRequest and selects only "
                "approved facets, owners, source types and reporting periods from the "
                "immutable current candidate snapshot. The successor route compiler "
                "separates narrative retrieval from typed fact requests. When the "
                "source-bound S2 company mart is mounted, exact requests execute as "
                "NumericFact, typed gap or typed conflict; candidate text still cannot "
                "grant numeric authority. This endpoint does not interpret raw user "
                "language, promote narrative Evidence, fetch external sources, or "
                "complete S1/S3 product acceptance."
            ),
        }
        return {**body, "projection_digest": canonical_digest(body)}

    def _company_fact_mart_available(self) -> bool:
        return bool(
            self._company_financial_fact_mart_path is not None
            and self._company_financial_fact_mart_path.is_file()
        )

    @staticmethod
    def _candidate_matches_period(candidate: Mapping[str, Any], period: Any) -> bool:
        raw_period_end = str(candidate.get("period_end") or "")
        if period.start_date is not None and (
            not raw_period_end or raw_period_end < period.start_date.isoformat()
        ):
            return False
        if period.end_date is not None and (
            not raw_period_end or raw_period_end > period.end_date.isoformat()
        ):
            return False
        if period.fiscal_years:
            fiscal_year = candidate.get("fiscal_year")
            if fiscal_year not in set(period.fiscal_years):
                return False
        return True

    def _ranking_projection_for_case(self, case_key: str) -> dict[str, Any] | None:
        if self._ranking is None:
            return None
        case = self._ranking_cases.get(case_key)
        if case is None:
            raise ResearchRetrievalServiceError(
                "research_ranking_case_projection_missing", 503, case_key=case_key
            )
        return {
            "candidate_state": "candidate_not_evidence",
            "same_object_population_count": int(
                self._ranking["same_object_population_count"]
            ),
            "route_summaries": deepcopy(self._ranking["route_summaries"]),
            "queries": deepcopy(case["queries"]),
            "known_boundary": str(self._ranking["known_boundary"]),
            "projection_digest": str(self._ranking["projection_digest"]),
        }

    @staticmethod
    def _validate(snapshot: Mapping[str, Any]) -> dict[str, Any]:
        value = deepcopy(dict(snapshot))
        cases = value.get("cases")
        acceptance = value.get("acceptance")
        if not (
            value.get("schema_version") == EXPECTED_SCHEMA
            and value.get("status")
            in {
                "s1a_typed_local_retrieval_vertical_slice_ready",
                "s1b_current_source_object_retrieval_snapshot_ready_with_typed_gaps",
            }
            and isinstance(cases, list)
            and [row.get("case_key") for row in cases]
            == ["DELL", "MU", "NVDA"]
            and isinstance(acceptance, Mapping)
            and acceptance.get("model_calls") == 0
            and acceptance.get("network_calls") == 0
            and acceptance.get("complete_s1_claimed") is False
            and acceptance.get("evidence_pack_promoted") is False
            and acceptance.get("historical_corpus_sufficient_for_current_product")
            is False
            and str(value.get("known_boundary") or "")
        ):
            raise ResearchRetrievalServiceError(
                "research_retrieval_snapshot_invalid", 503
            )
        for row in cases:
            retrieval = row.get("retrieval")
            if not (
                isinstance(retrieval, Mapping)
                and retrieval.get("candidate_state") == "candidate_not_evidence"
                and not retrieval.get("summary", {}).get("hard_constraint_failures")
                and isinstance(retrieval.get("lane_results"), list)
            ):
                raise ResearchRetrievalServiceError(
                    "research_retrieval_case_snapshot_invalid", 503
                )
        return value

    @staticmethod
    def _require_read(principal: ResearchRetrievalPrincipal) -> None:
        if principal.mode != "current":
            raise ResearchRetrievalServiceError(
                "research_retrieval_current_mode_required", 403
            )
        if "current_product:read" not in principal.permissions:
            raise ResearchRetrievalServiceError(
                "research_retrieval_read_permission_required", 403
            )

    @staticmethod
    def _validate_ranking(value: Mapping[str, Any]) -> dict[str, Any]:
        ranking = deepcopy(dict(value))
        rendered = str(ranking)
        cases = ranking.get("cases")
        if not (
            ranking.get("schema_version") == EXPECTED_RANKING_SCHEMA
            and ranking.get("candidate_state") == "candidate_not_evidence"
            and int(ranking.get("same_object_population_count") or 0) > 0
            and isinstance(ranking.get("route_summaries"), Mapping)
            and isinstance(cases, list)
            and [row.get("case_key") for row in cases] == ["DELL", "MU", "NVDA"]
            and str(ranking.get("known_boundary") or "")
            and str(ranking.get("projection_digest") or "")
            and canonical_digest(
                {
                    key: value
                    for key, value in ranking.items()
                    if key != "projection_digest"
                }
            )
            == ranking.get("projection_digest")
        ):
            raise ResearchRetrievalServiceError(
                "research_ranking_projection_invalid", 503
            )
        for forbidden in (
            "target_current_source_record_ids",
            "target_in_top_k",
            "target_rank",
            "matched_qrel_ids",
            "missed_qrel_ids",
            "business_diagnostic_code",
        ):
            if forbidden in rendered:
                raise ResearchRetrievalServiceError(
                    "research_ranking_projection_contains_eval_identity", 503
                )
        return ranking


__all__ = [
    "CURRENT_QUERY_OBJECT_FACT_ROUTE_POLICY_RESOURCE_ID",
    "CURRENT_RETRIEVAL_KERNEL_RESOURCE_ID",
    "CURRENT_RANKING_COMPARISON_RESOURCE_ID",
    "CURRENT_RETRIEVAL_SNAPSHOT_RESOURCE_ID",
    "ResearchRetrievalPrincipal",
    "ResearchRetrievalService",
    "ResearchRetrievalServiceError",
    "RETRIEVAL_PROJECTION_SCHEMA",
    "REQUEST_RETRIEVAL_PROJECTION_SCHEMA",
]
