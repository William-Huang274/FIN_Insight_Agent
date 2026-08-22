from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from financial_facts import execute_typed_fact_request
from retrieval.contracts import (
    FinancialResearchKernel,
    RetrievalContractError,
    load_evidence_request,
    load_financial_research_kernel,
)
from retrieval.query_plan import compile_query_facet_plan_for_request
from retrieval.evidence_set_coverage import EvidenceSetCoverageError
from retrieval.hybrid_candidate_runtime import (
    HybridCandidateRuntimeError,
    LazyLocalQwenHybridCandidateRuntime,
)
from retrieval.current_runtime_binding import (
    CurrentS1RuntimeBindingError,
    project_request_route_execution_truth,
    validate_current_s1_runtime_binding_receipt,
)
from retrieval.candidate_ceiling_provenance import (
    CandidateCeilingProvenanceError,
    build_candidate_ceiling_provenance,
)
from retrieval.material_evidence_runtime import (
    MaterialEvidenceRuntimeError,
    compile_material_requirement_plan_from_runtime_input,
)
from retrieval.route_compiler import (
    QueryObjectFactRoutePolicy,
    compile_retrieval_execution_plan,
    load_query_object_fact_route_policy,
)
from retrieval.artifact_spine import ArtifactSpinePolicy
from retrieval.vertical_slice import (
    load_s1_vs1_vertical_slice_result,
    project_s1_vs1_case,
)
from retrieval.supplement_vertical import (
    SupplementVerticalError,
    project_capture_bound_supplement_lineage,
    resolve_supplement_successor_binding,
    validate_supplement_vertical_resource,
)
from retrieval.product_evidence_successor import (
    ProductEvidenceSuccessorError,
    project_current_product_evidence_successor_lineage,
)
from retrieval.source_route_dispatch import (
    SourceRouteDispatchError,
    SourceRoutePortfolioPolicy,
    candidate_coverage_state_from_hybrid_result,
    collect_source_route_candidate_rows,
    compile_source_route_execution_truth,
    load_source_route_portfolio_policy,
)
from ingestion.source_intake import SourceIntakePolicy, SourceIntakeStore
from sec_agent.runtime_resource_registry import read_registered_runtime_json
from sec_agent.research.reviewed_evidence_pack import canonical_digest
from sec_agent.research.planning import (
    ResearchPlanningError,
    ResearchPlanningPolicy,
    compile_research_objective,
    compile_research_plan,
    load_research_planning_policy,
)
from sec_agent.research.material_scope import (
    ResearchMaterialScopeError,
    compile_research_material_scope,
)
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
CURRENT_RESEARCH_PLANNING_POLICY_RESOURCE_ID = (
    "application.config.current_research_planning_policy"
)
CURRENT_HYBRID_CANDIDATE_RUNTIME_POLICY_RESOURCE_ID = (
    "application.config.current_hybrid_candidate_runtime_policy"
)
CURRENT_MATERIAL_SCOPE_POLICY_RESOURCE_ID = (
    "application.config.current_research_material_scope_policy"
)
CURRENT_MATERIAL_RUNTIME_POLICY_RESOURCE_ID = (
    "application.config.current_product_material_evidence_runtime_policy"
)
CURRENT_FINANCIAL_INTENT_ONTOLOGY_RESOURCE_ID = (
    "application.config.current_financial_intent_ontology"
)
CURRENT_RETRIEVAL_NEED_POLICY_RESOURCE_ID = (
    "application.config.current_retrieval_need_policy"
)
CURRENT_S1_ARTIFACT_SPINE_POLICY_RESOURCE_ID = (
    "application.config.current_s1_artifact_spine_policy"
)
CURRENT_S1_VS1_VERTICAL_SLICE_RESOURCE_ID = (
    "application.result.current_s1_vs1_vertical_slice"
)
CURRENT_S1_VS4_SUPPLEMENT_VERTICAL_RESOURCE_ID = (
    "application.result.current_s1_vs4_supplement_vertical"
)
CURRENT_S1_RUNTIME_BINDING_POLICY_RESOURCE_ID = (
    "application.config.current_s1_runtime_binding_policy"
)
CURRENT_S1_RUNTIME_BINDING_RECEIPT_RESOURCE_ID = (
    "application.result.current_s1_runtime_binding_receipt"
)
CURRENT_RESEARCH_EVIDENCE_PACK_RESULT_RESOURCE_ID = (
    "application.result.current_research_local_evidence_packs"
)
CURRENT_S1_PRODUCT_READINESS_CATALOG_RESOURCE_ID = (
    "application.config.current_s1_product_readiness_catalog"
)
CURRENT_S1_SOURCE_ROUTE_PORTFOLIO_RESOURCE_ID = (
    "application.config.current_s1_source_route_portfolio"
)
CURRENT_SOURCE_INTAKE_POLICY_RESOURCE_ID = (
    "application.config.current_source_intake_policy"
)
EXPECTED_SCHEMA = "fin_ia_current_retrieval_snapshot_v1_0"
EXPECTED_RANKING_SCHEMA = "fin_ia_s1c_ranking_workbench_projection_v1_0"
RETRIEVAL_PROJECTION_SCHEMA = "fin_ia_research_retrieval_projection_v1_0"
REQUEST_RETRIEVAL_PROJECTION_SCHEMA = (
    "fin_ia_request_scoped_retrieval_projection_v1_2"
)
CURRENT_RUNTIME_REQUEST_BATCH_PROJECTION_SCHEMA = (
    "fin_ia_current_runtime_request_batch_projection_v1_0"
)
RESEARCH_PLAN_EXECUTION_PROJECTION_SCHEMA = (
    "fin_ia_controlled_research_plan_execution_projection_v1_0"
)
RESEARCH_PLAN_MATERIAL_EXECUTION_PROJECTION_SCHEMA = (
    "fin_ia_controlled_research_plan_execution_projection_v1_1"
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
        planning_policy: ResearchPlanningPolicy | Mapping[str, Any] | None = None,
        hybrid_candidate_runtime: Any | None = None,
        hybrid_candidate_policy: Mapping[str, Any] | None = None,
        material_scope_policy: Mapping[str, Any] | None = None,
        material_runtime_policy: Mapping[str, Any] | None = None,
        financial_intent_ontology: Mapping[str, Any] | None = None,
        retrieval_need_policy: Mapping[str, Any] | None = None,
        runtime_binding_policy: Mapping[str, Any] | None = None,
        runtime_binding_receipt: Mapping[str, Any] | None = None,
        runtime_binding_repository_root: str | Path | None = None,
        company_financial_fact_mart_path: str | Path | None = None,
        s1_vertical_slice: Mapping[str, Any] | None = None,
        s1_supplement_vertical: Mapping[str, Any] | None = None,
        artifact_spine_policy: Mapping[str, Any] | None = None,
        current_evidence_pack_result: Mapping[str, Any] | None = None,
        product_readiness_results: Mapping[
            str, Mapping[str, Any]
        ] | None = None,
        source_route_policy: SourceRoutePortfolioPolicy | Mapping[str, Any] | None = None,
        source_intake_policy: SourceIntakePolicy | Mapping[str, Any] | None = None,
        source_intake_attempts: tuple[Mapping[str, Any], ...] = (),
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
        if planning_policy is not None and self._route_policy is None:
            raise ResearchRetrievalServiceError(
                "research_planning_policy_without_route_policy", 503
            )
        self._planning_policy = (
            load_research_planning_policy(planning_policy, self._route_policy)
            if isinstance(planning_policy, Mapping)
            and self._route_policy is not None
            else planning_policy
        )
        self._hybrid_candidate_runtime = hybrid_candidate_runtime
        self._hybrid_candidate_contract: dict[str, Any] | None = None
        if hybrid_candidate_policy is not None:
            contract = hybrid_candidate_policy.get("candidate_contract")
            if not isinstance(contract, Mapping):
                raise ResearchRetrievalServiceError(
                    "hybrid_candidate_contract_invalid", 503
                )
            self._hybrid_candidate_contract = dict(contract)
        material_contracts = (
            material_scope_policy,
            material_runtime_policy,
            financial_intent_ontology,
            retrieval_need_policy,
        )
        if any(value is not None for value in material_contracts) and not all(
            value is not None for value in material_contracts
        ):
            raise ResearchRetrievalServiceError(
                "research_material_runtime_contract_binding_incomplete", 503
            )
        self._material_scope_policy = (
            deepcopy(dict(material_scope_policy))
            if material_scope_policy is not None
            else None
        )
        self._material_runtime_policy = (
            deepcopy(dict(material_runtime_policy))
            if material_runtime_policy is not None
            else None
        )
        self._financial_intent_ontology = (
            deepcopy(dict(financial_intent_ontology))
            if financial_intent_ontology is not None
            else None
        )
        self._retrieval_need_policy = (
            deepcopy(dict(retrieval_need_policy))
            if retrieval_need_policy is not None
            else None
        )
        if (runtime_binding_policy is None) != (runtime_binding_receipt is None):
            raise ResearchRetrievalServiceError(
                "research_runtime_binding_contract_incomplete", 503
            )
        self._runtime_binding_receipt: dict[str, Any] | None = None
        if (
            runtime_binding_policy is not None
            and runtime_binding_receipt is not None
        ):
            if self._hybrid_candidate_contract is None:
                raise ResearchRetrievalServiceError(
                    "research_runtime_binding_candidate_contract_missing", 503
                )
            try:
                self._runtime_binding_receipt = (
                    validate_current_s1_runtime_binding_receipt(
                        runtime_binding_receipt,
                        runtime_binding_policy,
                        repository_root=runtime_binding_repository_root,
                    )
                )
            except CurrentS1RuntimeBindingError as exc:
                raise ResearchRetrievalServiceError(
                    "research_runtime_binding_invalid",
                    503,
                    typed_reason=str(exc),
                ) from exc
        self._company_financial_fact_mart_path = (
            Path(company_financial_fact_mart_path).resolve()
            if company_financial_fact_mart_path is not None
            else None
        )
        if (s1_vertical_slice is None) != (artifact_spine_policy is None):
            raise ResearchRetrievalServiceError(
                "research_retrieval_vertical_slice_policy_binding_invalid", 503
            )
        self._s1_vertical_slice = None
        if s1_vertical_slice is not None and artifact_spine_policy is not None:
            try:
                self._s1_vertical_slice = load_s1_vs1_vertical_slice_result(
                    s1_vertical_slice,
                    policy=ArtifactSpinePolicy.model_validate(
                        artifact_spine_policy
                    ),
                )
            except (ValueError, TypeError) as exc:
                raise ResearchRetrievalServiceError(
                    "research_retrieval_vertical_slice_invalid", 503
                ) from exc
        try:
            self._s1_supplement_vertical = (
                validate_supplement_vertical_resource(s1_supplement_vertical)
                if s1_supplement_vertical is not None
                else None
            )
        except SupplementVerticalError as exc:
            raise ResearchRetrievalServiceError(
                "research_retrieval_supplement_vertical_invalid",
                503,
                supplement_reason=str(exc),
            ) from exc
        if (
            self._s1_supplement_vertical is not None
            and self._s1_vertical_slice is None
        ):
            raise ResearchRetrievalServiceError(
                "research_retrieval_supplement_without_base_vertical", 503
            )
        if (current_evidence_pack_result is None) != (
            product_readiness_results is None
        ):
            raise ResearchRetrievalServiceError(
                "research_retrieval_product_successor_binding_incomplete", 503
            )
        self._current_evidence_pack_result = (
            deepcopy(dict(current_evidence_pack_result))
            if current_evidence_pack_result is not None
            else None
        )
        self._product_readiness_results = {
            str(case_key).strip().upper(): deepcopy(dict(value))
            for case_key, value in (product_readiness_results or {}).items()
        }
        self._source_route_policy = (
            load_source_route_portfolio_policy(source_route_policy)
            if isinstance(source_route_policy, Mapping)
            else source_route_policy
        )
        self._source_intake_policy = (
            SourceIntakePolicy.from_mapping(source_intake_policy)
            if isinstance(source_intake_policy, Mapping)
            else source_intake_policy
        )
        self._source_intake_attempts = tuple(
            deepcopy(dict(row)) for row in source_intake_attempts
        )
        if (self._source_route_policy is None) != (self._source_intake_policy is None):
            raise ResearchRetrievalServiceError(
                "research_source_route_contract_binding_incomplete", 503
            )

    @classmethod
    def from_runtime_paths(
        cls,
        repository_root: str | Path,
        runtime_paths: RuntimePathRegistry | None = None,
        hybrid_candidate_runtime: Any | None = None,
        *,
        load_s1_vertical_slice: bool = True,
    ) -> "ResearchRetrievalService":
        paths = runtime_paths or resolve_runtime_paths(repository_root)
        hybrid_candidate_policy = read_registered_runtime_json(
            repository_root,
            CURRENT_HYBRID_CANDIDATE_RUNTIME_POLICY_RESOURCE_ID,
        )
        active_hybrid_runtime = hybrid_candidate_runtime
        if active_hybrid_runtime is None:
            active_hybrid_runtime = LazyLocalQwenHybridCandidateRuntime(
                repository_root,
                hybrid_candidate_policy,
            )
        product_readiness_catalog = read_registered_runtime_json(
            repository_root,
            CURRENT_S1_PRODUCT_READINESS_CATALOG_RESOURCE_ID,
        )
        product_readiness_results = {
            str(case_key).strip().upper(): read_registered_runtime_json(
                repository_root, str(resource_id)
            )
            for case_key, resource_id in dict(
                product_readiness_catalog.get("case_resource_ids") or {}
            ).items()
        }
        source_intake_policy_payload = read_registered_runtime_json(
            repository_root,
            CURRENT_SOURCE_INTAKE_POLICY_RESOURCE_ID,
        )
        source_intake_policy = SourceIntakePolicy.from_mapping(
            source_intake_policy_payload
        )
        source_intake_attempts = tuple(
            SourceIntakeStore(
                paths.workbench_private_root / "source_intake",
                source_intake_policy,
            ).list_attempts(limit=1000)
        )
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
            planning_policy=read_registered_runtime_json(
                repository_root,
                CURRENT_RESEARCH_PLANNING_POLICY_RESOURCE_ID,
            ),
            hybrid_candidate_runtime=active_hybrid_runtime,
            hybrid_candidate_policy=hybrid_candidate_policy,
            material_scope_policy=read_registered_runtime_json(
                repository_root,
                CURRENT_MATERIAL_SCOPE_POLICY_RESOURCE_ID,
            ),
            material_runtime_policy=read_registered_runtime_json(
                repository_root,
                CURRENT_MATERIAL_RUNTIME_POLICY_RESOURCE_ID,
            ),
            financial_intent_ontology=read_registered_runtime_json(
                repository_root,
                CURRENT_FINANCIAL_INTENT_ONTOLOGY_RESOURCE_ID,
            ),
            retrieval_need_policy=read_registered_runtime_json(
                repository_root,
                CURRENT_RETRIEVAL_NEED_POLICY_RESOURCE_ID,
            ),
            runtime_binding_policy=read_registered_runtime_json(
                repository_root,
                CURRENT_S1_RUNTIME_BINDING_POLICY_RESOURCE_ID,
            ),
            runtime_binding_receipt=read_registered_runtime_json(
                repository_root,
                CURRENT_S1_RUNTIME_BINDING_RECEIPT_RESOURCE_ID,
            ),
            runtime_binding_repository_root=repository_root,
            company_financial_fact_mart_path=(
                paths.company_financial_fact_mart_path
            ),
            s1_vertical_slice=(
                read_registered_runtime_json(
                    repository_root,
                    CURRENT_S1_VS1_VERTICAL_SLICE_RESOURCE_ID,
                )
                if load_s1_vertical_slice
                else None
            ),
            s1_supplement_vertical=(
                read_registered_runtime_json(
                    repository_root,
                    CURRENT_S1_VS4_SUPPLEMENT_VERTICAL_RESOURCE_ID,
                )
                if load_s1_vertical_slice
                else None
            ),
            artifact_spine_policy=(
                read_registered_runtime_json(
                    repository_root,
                    CURRENT_S1_ARTIFACT_SPINE_POLICY_RESOURCE_ID,
                )
                if load_s1_vertical_slice
                else None
            ),
            current_evidence_pack_result=read_registered_runtime_json(
                repository_root,
                CURRENT_RESEARCH_EVIDENCE_PACK_RESULT_RESOURCE_ID,
            ),
            product_readiness_results=product_readiness_results,
            source_route_policy=read_registered_runtime_json(
                repository_root,
                CURRENT_S1_SOURCE_ROUTE_PORTFOLIO_RESOURCE_ID,
            ),
            source_intake_policy=source_intake_policy,
            source_intake_attempts=source_intake_attempts,
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
        if self._s1_vertical_slice is not None:
            body["canonical_spine"] = self._canonical_spine_for_case(key)
        return {**body, "projection_digest": canonical_digest(body)}

    def _canonical_spine_for_case(self, case_key: str) -> dict[str, Any] | None:
        if self._s1_vertical_slice is None:
            return None
        base_projection = project_s1_vs1_case(
            self._s1_vertical_slice, case_key=case_key
        )
        successor_binding = resolve_supplement_successor_binding(
            self._s1_supplement_vertical, case_key=case_key
        )
        if base_projection is None and successor_binding is None:
            return None
        binding = dict(
            base_projection.get("pack_binding") or {}
            if base_projection is not None
            else {}
        )
        artifact_digest = str(binding.get("artifact_digest") or "")
        pack_payload_digest = str(binding.get("pack_payload_digest") or "")
        if successor_binding is not None:
            artifact_digest = successor_binding["artifact_digest"]
            pack_payload_digest = successor_binding["pack_payload_digest"]
        try:
            historical_projection = project_capture_bound_supplement_lineage(
                base_projection=base_projection,
                supplement_summary=self._s1_supplement_vertical,
                case_key=case_key,
                artifact_digest=artifact_digest,
                pack_payload_digest=pack_payload_digest,
            )
        except SupplementVerticalError as exc:
            raise ResearchRetrievalServiceError(
                "research_retrieval_supplement_pack_binding_drift",
                503,
                supplement_reason=str(exc),
            ) from exc
        if self._current_evidence_pack_result is None:
            return historical_projection
        try:
            successor = project_current_product_evidence_successor_lineage(
                historical_projection=historical_projection,
                current_result=self._current_evidence_pack_result,
                product_readiness=self._product_readiness_results.get(case_key)
                or {},
                case_key=case_key,
            )
        except ProductEvidenceSuccessorError as exc:
            raise ResearchRetrievalServiceError(
                "research_retrieval_product_successor_lineage_invalid",
                503,
                successor_reason=str(exc),
            ) from exc
        return successor if successor is not None else historical_projection

    def execute_controlled_plan(
        self,
        case_key: str,
        objective_payload: Mapping[str, Any],
        planner_payload: Mapping[str, Any],
        principal: ResearchRetrievalPrincipal,
        *,
        material_scope_payload: Mapping[str, Any] | None = None,
        planning_policy: ResearchPlanningPolicy | None = None,
    ) -> dict[str, Any]:
        """Compile bounded S3 atoms and execute their S1/S2 sibling requests."""

        self._require_read(principal)
        active_planning_policy = planning_policy or self._planning_policy
        if (
            self._kernel is None
            or self._route_policy is None
            or active_planning_policy is None
        ):
            raise ResearchRetrievalServiceError(
                "controlled_research_planning_contract_unavailable", 503
            )
        try:
            objective = compile_research_objective(
                objective_payload,
                kernel=self._kernel,
                policy=active_planning_policy,
            )
            compiled = compile_research_plan(
                planner_payload,
                objective=objective,
                kernel=self._kernel,
                route_policy=self._route_policy,
                planning_policy=active_planning_policy,
            )
        except ResearchPlanningError as exc:
            raise ResearchRetrievalServiceError(str(exc), 422) from exc
        key = str(case_key).strip().upper()
        if key != objective.case_key:
            raise ResearchRetrievalServiceError(
                "research_objective_route_case_mismatch",
                422,
                route_case_key=key,
                objective_case_key=objective.case_key,
            )

        request_results = [
            self.execute_request(key, request.as_dict(), principal)
            for request in compiled.evidence_requests
        ]
        material_runtime_inputs: dict[str, dict[str, Any]] = {}
        material_scope_projection: dict[str, Any] | None = None
        if self._material_runtime_policy is not None:
            fallback_receipts: list[dict[str, Any]] = []
            required_scope_ids: list[str] = []
            try:
                for request, result in zip(
                    compiled.evidence_requests, request_results
                ):
                    runtime_input = {
                        "evidence_request": request.as_dict(),
                        "retrieval_execution_plan": deepcopy(
                            result["execution_plan"]
                        ),
                    }
                    _, receipt = (
                        compile_material_requirement_plan_from_runtime_input(
                            runtime_input=runtime_input,
                            policy=self._material_runtime_policy,
                            ontology=self._financial_intent_ontology,
                        )
                    )
                    material_runtime_inputs[request.request_id] = runtime_input
                    fallback_receipts.append(receipt)
                    if receipt[
                        "explicit_blueprint_required_for_full_product_scope"
                    ]:
                        required_scope_ids.append(request.request_id)
            except (MaterialEvidenceRuntimeError, EvidenceSetCoverageError) as exc:
                raise ResearchRetrievalServiceError(
                    "research_material_runtime_compilation_failed",
                    503,
                    typed_reason=str(exc),
                ) from exc

            scope_compilation: dict[str, Any] | None = None
            if material_scope_payload is not None:
                if not required_scope_ids:
                    raise ResearchRetrievalServiceError(
                        "research_material_scope_not_required", 422
                    )
                try:
                    scope_compilation = compile_research_material_scope(
                        material_scope_payload,
                        research_plan_digest=compiled.plan_digest,
                        requests=compiled.evidence_requests,
                        required_request_ids=required_scope_ids,
                        policy=self._material_scope_policy,
                        material_runtime_policy=self._material_runtime_policy,
                        intent_ontology=self._financial_intent_ontology,
                    )
                except ResearchMaterialScopeError as exc:
                    raise ResearchRetrievalServiceError(str(exc), 422) from exc
                for row in scope_compilation["request_scopes"]:
                    material_runtime_inputs[row["request_id"]][
                        "research_blueprint"
                    ] = deepcopy(row["research_blueprint"])
            material_scope_projection = {
                "mode": (
                    "explicit_request_visible_scope_compiled"
                    if scope_compilation is not None
                    else "deterministic_scope_ready"
                    if not required_scope_ids
                    else "explicit_scope_required"
                ),
                "research_plan_digest": compiled.plan_digest,
                "required_request_ids": required_scope_ids,
                "fallback_compiler_receipts": fallback_receipts,
                "scope_compilation": scope_compilation,
                "candidate_or_reference_inputs_read": False,
                "generation_model_calls_in_endpoint": 0,
                "candidate_is_not_evidence": True,
                "numeric_authority": False,
            }
        hybrid_results: tuple[dict[str, Any], ...] = ()
        if self._hybrid_candidate_runtime is not None:
            try:
                hybrid_kwargs: dict[str, Any] = {}
                if material_runtime_inputs:
                    hybrid_kwargs = {
                        "material_runtime_inputs": material_runtime_inputs,
                        "material_runtime_policy": self._material_runtime_policy,
                        "intent_ontology": self._financial_intent_ontology,
                        "retrieval_need_policy": self._retrieval_need_policy,
                    }
                hybrid_results = self._hybrid_candidate_runtime.retrieve_many(
                    compiled.evidence_requests,
                    kernel=self._kernel,
                    route_policy=self._route_policy,
                    **hybrid_kwargs,
                )
            except HybridCandidateRuntimeError as exc:
                raise ResearchRetrievalServiceError(
                    "hybrid_candidate_runtime_unavailable",
                    503,
                    typed_reason=str(exc),
                ) from exc
            if len(hybrid_results) != len(request_results):
                raise ResearchRetrievalServiceError(
                    "hybrid_candidate_result_count_invalid", 503
                )
            enriched_results: list[dict[str, Any]] = []
            for result, hybrid in zip(request_results, hybrid_results):
                route_truth = (
                    project_request_route_execution_truth(
                        execution_plan=result.get("execution_plan"),
                        binding_receipt=self._runtime_binding_receipt,
                        hybrid_result=hybrid,
                    )
                    if self._runtime_binding_receipt is not None
                    else None
                )
                enriched = {
                    **result,
                    "hybrid_object_retrieval": hybrid,
                    "route_execution_truth": route_truth,
                }
                enriched["source_route_execution_truth"] = (
                    self._source_route_projection(enriched, hybrid_result=hybrid)
                )
                enriched["candidate_ceiling_provenance"] = (
                    self._candidate_ceiling_projection(
                        result=enriched,
                        route_execution_truth=route_truth,
                        hybrid_result=hybrid,
                    )
                )
                enriched_results.append(enriched)
            request_results = enriched_results
        candidate_ids = {
            str(candidate["source_record_id"])
            for result in request_results
            for lane in result["lanes"]
            for candidate in lane["candidates"]
        }
        facts = [
            fact
            for result in request_results
            for fact_result in result["typed_fact_results"]
            for fact in fact_result.get("facts", ())
        ]
        body = {
            "schema_version": (
                RESEARCH_PLAN_MATERIAL_EXECUTION_PROJECTION_SCHEMA
                if material_scope_projection is not None
                else RESEARCH_PLAN_EXECUTION_PROJECTION_SCHEMA
            ),
            "status": "controlled_research_plan_zero_call_executed",
            "product_mode": "current",
            "case_key": key,
            "objective": objective.as_dict(),
            "compiled_plan": compiled.as_dict(),
            "summary": {
                "proposed_atom_count": len(compiled.proposed_atoms),
                "selected_atom_count": len(compiled.planner_atoms),
                "deferred_atom_count": len(compiled.deferred_atoms),
                "execution_request_budget": (
                    objective.budget.max_evidence_requests
                ),
                "evidence_request_count": len(request_results),
                "required_slot_count": len(objective.required_slot_ids),
                "compiled_lane_count": sum(
                    result["summary"]["compiled_lane_count"]
                    for result in request_results
                ),
                "nonempty_lane_count": sum(
                    result["summary"]["nonempty_lane_count"]
                    for result in request_results
                ),
                "unique_narrative_candidates": len(candidate_ids),
                "typed_fact_request_count": sum(
                    result["summary"]["typed_fact_request_count"]
                    for result in request_results
                ),
                "typed_fact_resolved_count": sum(
                    result["summary"]["typed_fact_resolved_count"]
                    for result in request_results
                ),
                "typed_fact_gap_count": sum(
                    result["summary"]["typed_fact_gap_count"]
                    for result in request_results
                ),
                "typed_fact_conflict_count": sum(
                    result["summary"]["typed_fact_conflict_count"]
                    for result in request_results
                ),
                "numeric_fact_count": len(facts),
                "hybrid_candidate_runtime": (
                    "bm25_plus_qwen_local_embedding"
                    if hybrid_results
                    else "not_configured"
                ),
                "hybrid_selected_candidate_count": sum(
                    row["summary"]["selected_count"]
                    for row in hybrid_results
                ),
                "material_scope_required_request_count": (
                    len(material_scope_projection["required_request_ids"])
                    if material_scope_projection is not None
                    else 0
                ),
                "material_scope_ready_request_count": sum(
                    row["summary"].get("material_scope_ready") is True
                    for row in hybrid_results
                ),
                "material_set_complete_request_count": sum(
                    row["summary"].get("material_set_complete") is True
                    for row in hybrid_results
                ),
                "local_embedding_inference_batches": 1 if hybrid_results else 0,
                "network_calls": 0,
                "model_calls": 0,
                "generation_model_calls": 0,
            },
            "material_scope": material_scope_projection,
            "request_results": request_results,
            "known_boundary": (
                "This projection proves deterministic user-objective binding, "
                "bounded planner-atom proposal validation, deterministic local "
                "execution selection, S1 narrative candidate lookup "
                "and S2 source-bound NumericFact execution. When configured, the "
                "provisional S1 path also returns a hard-filtered BM25 plus local "
                "Qwen embedding candidate union; those rows remain candidates. "
                "When the material contracts are configured, each request compiles "
                "a request-visible material set and reserves matching candidates "
                "before source quota and output truncation. Composite or novel "
                "product scope remains explicitly unresolved until a candidate-blind "
                "natural material-scope payload is compiled. "
                "All valid proposed atoms and stable defer reasons remain auditable; "
                "only the execution-budget selection becomes EvidenceRequests. "
                "Planner atoms are supplied as controlled input in this zero-call "
                "proof; no natural "
                "language model planning, candidate-to-Evidence promotion, research "
                "judgment, report writing or S3 product acceptance is claimed."
            ),
        }
        return {**body, "projection_digest": canonical_digest(body)}

    def execute_request(
        self,
        case_key: str,
        payload: Mapping[str, Any],
        principal: ResearchRetrievalPrincipal,
        *,
        allow_current_hybrid_only_lanes: bool = False,
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
                if allow_current_hybrid_only_lanes:
                    lanes.append(
                        {
                            "lane": lane.as_dict(),
                            "candidate_state": "candidate_not_evidence",
                            "candidates": [],
                            "missing_required_source_roles": [],
                            "snapshot_exclusion_counts": {},
                            "request_exclusion_counts": {},
                            "snapshot_state": (
                                "not_applicable_current_hybrid_successor_lane"
                            ),
                        }
                    )
                    continue
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
                if allow_current_hybrid_only_lanes:
                    lanes.append(
                        {
                            "lane": lane.as_dict(),
                            "candidate_state": "candidate_not_evidence",
                            "candidates": [],
                            "missing_required_source_roles": [],
                            "snapshot_exclusion_counts": {},
                            "request_exclusion_counts": {},
                            "snapshot_state": (
                                "legacy_contract_not_applicable_to_current_"
                                "hybrid_successor_lane"
                            ),
                        }
                    )
                    continue
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
            "runtime_binding": self._runtime_binding_projection(),
            "route_execution_truth": (
                project_request_route_execution_truth(
                    execution_plan=(
                        execution_plan.as_dict()
                        if execution_plan is not None
                        else None
                    ),
                    binding_receipt=self._runtime_binding_receipt,
                )
                if self._runtime_binding_receipt is not None
                else None
            ),
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
        body["source_route_execution_truth"] = self._source_route_projection(body)
        body["candidate_ceiling_provenance"] = (
            self._candidate_ceiling_projection(
                result=body,
                route_execution_truth=body.get("route_execution_truth"),
                hybrid_result=None,
            )
        )
        return {**body, "projection_digest": canonical_digest(body)}

    def execute_current_runtime_requests(
        self,
        case_key: str,
        payloads: Sequence[Mapping[str, Any]],
        principal: ResearchRetrievalPrincipal,
        *,
        material_requirement_blueprints: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Execute typed requests through the mounted S1/S2 product runtime.

        ``execute_request`` intentionally preserves the immutable snapshot-only
        product surface.  This successor is the direct EvidenceRequest entry for
        AI-free audits and dynamic research agents: it keeps the same S2 exact
        fact execution, then runs the currently bound BM25 + local Qwen candidate
        runtime and projects route truth.  Ranked rows remain candidates; this
        method never promotes Evidence or grants numeric authority.
        """

        self._require_read(principal)
        if self._kernel is None or self._route_policy is None:
            raise ResearchRetrievalServiceError(
                "current_runtime_request_contract_unavailable", 503
            )
        if self._hybrid_candidate_runtime is None:
            raise ResearchRetrievalServiceError(
                "current_runtime_hybrid_candidate_runtime_unavailable", 503
            )
        if not payloads:
            raise ResearchRetrievalServiceError(
                "current_runtime_requests_missing", 422
            )
        if len(payloads) > 64:
            raise ResearchRetrievalServiceError(
                "current_runtime_request_batch_too_large", 422,
                request_count=len(payloads),
            )

        key = str(case_key).strip().upper()
        requests = []
        request_results = []
        seen_request_ids: set[str] = set()
        try:
            for payload in payloads:
                request = load_evidence_request(payload, self._kernel)
                if request.case_key != key:
                    raise ResearchRetrievalServiceError(
                        "evidence_request_route_case_mismatch",
                        422,
                        route_case_key=key,
                        request_case_key=request.case_key,
                    )
                if request.request_id in seen_request_ids:
                    raise ResearchRetrievalServiceError(
                        "current_runtime_request_id_duplicate",
                        422,
                        request_id=request.request_id,
                    )
                seen_request_ids.add(request.request_id)
                requests.append(request)
                request_results.append(
                    self.execute_request(
                        key,
                        request.as_dict(),
                        principal,
                        allow_current_hybrid_only_lanes=True,
                    )
                )
        except RetrievalContractError as exc:
            raise ResearchRetrievalServiceError(str(exc), 422) from exc

        material_runtime_inputs: dict[str, dict[str, Any]] = {}
        material_receipts: list[dict[str, Any]] = []
        blueprint_by_request = {
            str(request_id): deepcopy(dict(blueprint))
            for request_id, blueprint in (
                material_requirement_blueprints or {}
            ).items()
        }
        unknown_blueprint_ids = set(blueprint_by_request) - seen_request_ids
        if unknown_blueprint_ids:
            raise ResearchRetrievalServiceError(
                "current_runtime_material_blueprint_request_unknown",
                422,
                request_ids=sorted(unknown_blueprint_ids),
            )
        if self._material_runtime_policy is not None:
            try:
                for request, result in zip(requests, request_results):
                    runtime_input = {
                        "evidence_request": request.as_dict(),
                        "retrieval_execution_plan": deepcopy(
                            result["execution_plan"]
                        ),
                    }
                    blueprint = blueprint_by_request.get(request.request_id)
                    if blueprint is not None:
                        runtime_input["material_requirement_blueprint"] = blueprint
                    _, receipt = compile_material_requirement_plan_from_runtime_input(
                        runtime_input=runtime_input,
                        policy=self._material_runtime_policy,
                        ontology=self._financial_intent_ontology,
                    )
                    material_runtime_inputs[request.request_id] = runtime_input
                    material_receipts.append(receipt)
            except (MaterialEvidenceRuntimeError, EvidenceSetCoverageError) as exc:
                raise ResearchRetrievalServiceError(
                    "current_runtime_material_compilation_failed",
                    503,
                    typed_reason=str(exc),
                ) from exc

        try:
            hybrid_kwargs: dict[str, Any] = {}
            if material_runtime_inputs:
                hybrid_kwargs = {
                    "material_runtime_inputs": material_runtime_inputs,
                    "material_runtime_policy": self._material_runtime_policy,
                    "intent_ontology": self._financial_intent_ontology,
                    "retrieval_need_policy": self._retrieval_need_policy,
                }
            hybrid_results = self._hybrid_candidate_runtime.retrieve_many(
                requests,
                kernel=self._kernel,
                route_policy=self._route_policy,
                **hybrid_kwargs,
            )
        except HybridCandidateRuntimeError as exc:
            raise ResearchRetrievalServiceError(
                "hybrid_candidate_runtime_unavailable",
                503,
                typed_reason=str(exc),
            ) from exc
        if len(hybrid_results) != len(request_results):
            raise ResearchRetrievalServiceError(
                "hybrid_candidate_result_count_invalid", 503
            )

        enriched_results: list[dict[str, Any]] = []
        for result, hybrid in zip(request_results, hybrid_results):
            route_truth = (
                project_request_route_execution_truth(
                    execution_plan=result.get("execution_plan"),
                    binding_receipt=self._runtime_binding_receipt,
                    hybrid_result=hybrid,
                )
                if self._runtime_binding_receipt is not None
                else None
            )
            enriched = {
                **result,
                "execution_mode": "current_s2_snapshot_bm25_qwen_runtime",
                "hybrid_object_retrieval": hybrid,
                "route_execution_truth": route_truth,
            }
            enriched["source_route_execution_truth"] = (
                self._source_route_projection(enriched, hybrid_result=hybrid)
            )
            enriched["candidate_ceiling_provenance"] = (
                self._candidate_ceiling_projection(
                    result=enriched,
                    route_execution_truth=route_truth,
                    hybrid_result=hybrid,
                )
            )
            enriched_results.append(enriched)

        candidate_ids = {
            str(row.get("compiled_object_id") or "")
            for hybrid in hybrid_results
            for row in hybrid.get("candidate_decision_seed") or ()
            if str(row.get("compiled_object_id") or "")
        }
        fact_count = sum(
            len(result.get("facts") or ())
            for request_result in request_results
            for result in request_result.get("typed_fact_results") or ()
        )
        body = {
            "schema_version": CURRENT_RUNTIME_REQUEST_BATCH_PROJECTION_SCHEMA,
            "status": "current_runtime_request_batch_zero_call_executed",
            "product_mode": "current",
            "case_key": key,
            "summary": {
                "request_count": len(enriched_results),
                "compiled_lane_count": sum(
                    row["summary"]["compiled_lane_count"]
                    for row in request_results
                ),
                "snapshot_nonempty_lane_count": sum(
                    row["summary"]["nonempty_lane_count"]
                    for row in request_results
                ),
                "hybrid_selected_candidate_count": sum(
                    int(hybrid["summary"].get("selected_count") or 0)
                    for hybrid in hybrid_results
                ),
                "hybrid_union_candidate_count": len(candidate_ids),
                "typed_fact_resolved_count": sum(
                    row["summary"]["typed_fact_resolved_count"]
                    for row in request_results
                ),
                "typed_fact_gap_count": sum(
                    row["summary"]["typed_fact_gap_count"]
                    for row in request_results
                ),
                "typed_fact_conflict_count": sum(
                    row["summary"]["typed_fact_conflict_count"]
                    for row in request_results
                ),
                "numeric_fact_count": fact_count,
                "material_scope_required_request_count": sum(
                    receipt.get(
                        "explicit_blueprint_required_for_full_product_scope"
                    )
                    is True
                    for receipt in material_receipts
                ),
                "material_scope_ready_request_count": sum(
                    hybrid["summary"].get("material_scope_ready") is True
                    for hybrid in hybrid_results
                ),
                "material_set_complete_request_count": sum(
                    hybrid["summary"].get("material_set_complete") is True
                    for hybrid in hybrid_results
                ),
                "local_embedding_inference_batches": 1,
                "network_calls": 0,
                "model_calls": 0,
                "generation_model_calls": 0,
            },
            "material_compilation_receipts": material_receipts,
            "material_scope": {
                "mode": (
                    "explicit_program_blueprint_compiled"
                    if blueprint_by_request
                    else "deterministic_runtime_fallback"
                ),
                "research_plan_digest": canonical_digest(
                    {
                        "case_key": key,
                        "requests": [request.as_dict() for request in requests],
                        "material_requirement_blueprints": blueprint_by_request,
                    }
                ),
                "scope_compilation": {
                    "request_ids": sorted(blueprint_by_request),
                    "compilation_digest": canonical_digest(
                        {
                            "case_key": key,
                            "material_requirement_blueprints": blueprint_by_request,
                        }
                    ),
                    "candidate_or_reference_inputs_read": False,
                    "generation_model_calls": 0,
                },
            },
            "request_results": enriched_results,
            "known_boundary": (
                "This is the canonical direct EvidenceRequest execution surface for "
                "the mounted current S1/S2 runtime. It executes source-bound S2 "
                "facts, the immutable snapshot lane and the bound BM25 plus local "
                "Qwen candidate runtime. Candidate rank never grants Evidence or "
                "numeric authority. External source acquisition, CandidateDecision, "
                "Evidence admission and S1/S3 acceptance remain separate gates."
            ),
        }
        return {**body, "projection_digest": canonical_digest(body)}

    def _source_route_projection(
        self,
        result: Mapping[str, Any],
        *,
        hybrid_result: Mapping[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if self._source_route_policy is None or self._source_intake_policy is None:
            return None
        candidate_rows = collect_source_route_candidate_rows(
            result, hybrid_result
        )
        request = dict(result.get("request") or {})
        case_key = str(request.get("case_key") or "").upper()
        request_id = str(request.get("request_id") or "")
        research_sufficiency_state = "not_evaluated"
        readiness = self._product_readiness_results.get(case_key) or {}
        for current in readiness.get("requests") or ():
            if str(current.get("request_id") or "") != request_id:
                continue
            current_state = str(current.get("readiness_state") or "")
            if current_state == "ready_for_current_scope":
                research_sufficiency_state = "sufficient"
            elif current_state == "partial_with_material_gaps":
                research_sufficiency_state = "material_gap"
            break
        try:
            return compile_source_route_execution_truth(
                request=request,
                query_plan=result["query_plan"],
                policy=self._source_route_policy,
                local_candidate_rows=candidate_rows,
                candidate_coverage_state=(
                    candidate_coverage_state_from_hybrid_result(hybrid_result)
                ),
                research_sufficiency_state=research_sufficiency_state,
                registered_intake_routes=[
                    route.public_projection()
                    for route in self._source_intake_policy.routes.values()
                ],
                intake_attempts=self._source_intake_attempts,
            )
        except SourceRouteDispatchError as exc:
            raise ResearchRetrievalServiceError(
                "research_source_route_projection_invalid",
                503,
                typed_reason=str(exc),
            ) from exc

    def _candidate_ceiling_projection(
        self,
        *,
        result: Mapping[str, Any],
        route_execution_truth: Mapping[str, Any] | None,
        hybrid_result: Mapping[str, Any] | None,
    ) -> dict[str, Any] | None:
        if (
            self._runtime_binding_receipt is None
            or self._hybrid_candidate_contract is None
            or route_execution_truth is None
        ):
            return None
        try:
            return build_candidate_ceiling_provenance(
                request=result["request"],
                request_digest=str(result["request_digest"]),
                static_summary=result["summary"],
                static_lanes=result["lanes"],
                route_execution_truth=route_execution_truth,
                runtime_binding_receipt=self._runtime_binding_receipt,
                candidate_contract=self._hybrid_candidate_contract,
                hybrid_result=hybrid_result,
            )
        except CandidateCeilingProvenanceError as exc:
            raise ResearchRetrievalServiceError(
                "research_candidate_ceiling_provenance_invalid",
                503,
                typed_reason=str(exc),
            ) from exc

    def _runtime_binding_projection(self) -> dict[str, Any] | None:
        if self._runtime_binding_receipt is None:
            return None
        receipt = self._runtime_binding_receipt
        lineage = receipt["source_object_index_lineage"]
        return {
            "status": receipt["status"],
            "result_digest": receipt["result_digest"],
            "source_record_count": lineage["source_record_count"],
            "compiled_object_count": lineage["compiled_object_count"],
            "all_source_records_lineage_bound": lineage[
                "all_source_records_lineage_bound"
            ],
            "unavailable_routes": receipt["route_execution_truth"][
                "unavailable_routes"
            ],
            "product_pack_readiness_producer_registered": receipt[
                "acceptance"
            ]["product_pack_readiness_producer_registered"],
            "s1_qualified_stable": receipt["acceptance"][
                "s1_qualified_stable"
            ],
        }

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
    "CURRENT_S1_ARTIFACT_SPINE_POLICY_RESOURCE_ID",
    "CURRENT_S1_RUNTIME_BINDING_POLICY_RESOURCE_ID",
    "CURRENT_S1_RUNTIME_BINDING_RECEIPT_RESOURCE_ID",
    "CURRENT_S1_VS1_VERTICAL_SLICE_RESOURCE_ID",
    "CURRENT_RETRIEVAL_SNAPSHOT_RESOURCE_ID",
    "ResearchRetrievalPrincipal",
    "ResearchRetrievalService",
    "ResearchRetrievalServiceError",
    "RETRIEVAL_PROJECTION_SCHEMA",
    "REQUEST_RETRIEVAL_PROJECTION_SCHEMA",
]
