from __future__ import annotations

from collections import defaultdict
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from pydantic import Field

from sec_agent.canonical_runtime.models import StrictModel, canonical_digest
from sec_agent.financial_research_generalization_contract import (
    CompiledCaseResearchContract,
    DeterministicEvidencePackEvaluator,
    FinancialCandidate,
    FinancialResearchGeneralizationContract,
    TypedResidualGap,
    compile_case_research_contract,
    load_financial_research_contract,
)


RUN_SCOPE = "S1_DELL_FINANCIAL_SOURCE_OBJECT_AND_EVIDENCE_PACK_VERTICAL_SLICE"
POLICY_SCHEMA = "fin_ia_0_1_3_s1_financial_source_object_vertical_policy_v1_0"
POLICY_AMENDMENT_SCHEMA = (
    "fin_ia_0_1_3_s1_financial_source_object_vertical_policy_amendment_v1_0"
)
RESULT_SCHEMA = "fin_ia_0_1_3_s1_dell_financial_source_object_vertical_result_v1_0"


class FinancialSourceObjectVerticalError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class LocalRetrievalAsset(StrictModel):
    asset_id: str
    retriever_kind: str
    index_ref: str
    source_records_ref: str


class FinancialQueryLane(StrictModel):
    lane_id: str
    asset_id: str
    slot_id: str
    facet_focus: tuple[str, ...]
    evidence_owner_entity_key: str
    evidence_owner_ticker: str
    relationship_direction: str
    query_texts: tuple[str, ...]
    filters: dict[str, Any]
    candidate_budget: int = Field(default=10, ge=1, le=24)


class ReviewedCandidateBinding(StrictModel):
    qualification_id: str
    lane_id: str
    target_id: str
    source_record_id: str
    slot_id: str
    analysis_period_id: str
    source_reporting_period_id: str
    evidence_owner_entity_key: str
    evidence_owner_ticker: str
    relationship_direction: str
    facet_ids: tuple[str, ...]
    authority_tier: str
    candidate_role: str
    source_excerpt: str
    target_excerpt: str
    business_meaning_zh: str
    content_limitation_zh: str
    semantic_claim_key: str | None = None
    polarity: str = "neutral"


class DeclaredResidualGap(StrictModel):
    gap_id: str
    slot_id: str
    facet_id: str
    gap_code: str
    attempted_lane_ids: tuple[str, ...]
    business_reason_zh: str
    supplement_direction_zh: str


class HierarchyFinding(StrictModel):
    finding_id: str
    code: str
    affected_ref: str
    business_effect_zh: str
    required_object_boundary_zh: str


class FinancialSourceObjectVerticalPolicy(StrictModel):
    schema_version: str
    contract_ref: str
    run_scope: str
    recorded_at: str
    case_key: str
    generalization_contract_ref: str
    generalization_contract_sha256: str
    assets: tuple[LocalRetrievalAsset, ...]
    query_lanes: tuple[FinancialQueryLane, ...]
    reviewed_candidate_bindings: tuple[ReviewedCandidateBinding, ...]
    declared_residual_gaps: tuple[DeclaredResidualGap, ...]
    hierarchy_findings: tuple[HierarchyFinding, ...]
    hard_boundaries: dict[str, Any]


class ReviewedCandidateBindingPatch(StrictModel):
    qualification_id: str
    replacement_source_excerpt: str | None = None
    replacement_target_excerpt: str | None = None
    additional_facet_ids: tuple[str, ...] = ()


class FinancialSourceObjectVerticalPolicyAmendment(StrictModel):
    schema_version: str
    contract_ref: str
    recorded_at: str
    base_policy_ref: str
    base_policy_sha256: str
    binding_patches: tuple[ReviewedCandidateBindingPatch, ...]
    appended_residual_gaps: tuple[DeclaredResidualGap, ...]
    correction_reason_zh: str


def normalized_sha256(path: str | Path) -> str:
    return hashlib.sha256(
        Path(path).read_text(encoding="utf-8").replace("\r\n", "\n").encode("utf-8")
    ).hexdigest()


def load_financial_source_object_vertical_policy(
    path: str | Path,
    *,
    repo_root: str | Path,
) -> tuple[
    FinancialSourceObjectVerticalPolicy,
    FinancialResearchGeneralizationContract,
    CompiledCaseResearchContract,
]:
    root = Path(repo_root).resolve()
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    try:
        policy = FinancialSourceObjectVerticalPolicy.model_validate(payload)
    except Exception as exc:
        raise FinancialSourceObjectVerticalError("vertical_policy_shape_invalid") from exc
    contract_path = _resolve(root, policy.generalization_contract_ref)
    if normalized_sha256(contract_path) != policy.generalization_contract_sha256:
        raise FinancialSourceObjectVerticalError(
            "vertical_generalization_contract_digest_mismatch"
        )
    contract = load_financial_research_contract(contract_path)
    compiled = compile_case_research_contract(contract, policy.case_key)
    validate_financial_source_object_vertical_policy(policy, compiled=compiled)
    return policy, contract, compiled


def load_amended_financial_source_object_vertical_policy(
    path: str | Path,
    *,
    repo_root: str | Path,
) -> tuple[
    FinancialSourceObjectVerticalPolicy,
    FinancialResearchGeneralizationContract,
    CompiledCaseResearchContract,
    FinancialSourceObjectVerticalPolicyAmendment,
]:
    root = Path(repo_root).resolve()
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    try:
        amendment = FinancialSourceObjectVerticalPolicyAmendment.model_validate(payload)
    except Exception as exc:
        raise FinancialSourceObjectVerticalError(
            "vertical_policy_amendment_shape_invalid"
        ) from exc
    if amendment.schema_version != POLICY_AMENDMENT_SCHEMA:
        raise FinancialSourceObjectVerticalError(
            "vertical_policy_amendment_identity_invalid"
        )
    base_path = _resolve(root, amendment.base_policy_ref)
    if normalized_sha256(base_path) != amendment.base_policy_sha256:
        raise FinancialSourceObjectVerticalError(
            "vertical_policy_amendment_base_digest_mismatch"
        )
    policy, contract, compiled = load_financial_source_object_vertical_policy(
        base_path,
        repo_root=root,
    )
    patches = {row.qualification_id: row for row in amendment.binding_patches}
    if len(patches) != len(amendment.binding_patches):
        raise FinancialSourceObjectVerticalError(
            "vertical_policy_amendment_patch_identity_invalid"
        )
    known = {row.qualification_id for row in policy.reviewed_candidate_bindings}
    if set(patches) - known:
        raise FinancialSourceObjectVerticalError(
            "vertical_policy_amendment_target_unknown"
        )
    amended_bindings: list[ReviewedCandidateBinding] = []
    for binding in policy.reviewed_candidate_bindings:
        patch = patches.get(binding.qualification_id)
        if patch is None:
            amended_bindings.append(binding)
            continue
        amended_bindings.append(
            binding.model_copy(
                update={
                    "source_excerpt": (
                        patch.replacement_source_excerpt
                        if patch.replacement_source_excerpt is not None
                        else binding.source_excerpt
                    ),
                    "target_excerpt": (
                        patch.replacement_target_excerpt
                        if patch.replacement_target_excerpt is not None
                        else binding.target_excerpt
                    ),
                    "facet_ids": _ordered_unique(
                        binding.facet_ids + patch.additional_facet_ids
                    ),
                }
            )
        )
    effective = policy.model_copy(
        update={
            "contract_ref": amendment.contract_ref,
            "recorded_at": amendment.recorded_at,
            "reviewed_candidate_bindings": tuple(amended_bindings),
            "declared_residual_gaps": (
                policy.declared_residual_gaps + amendment.appended_residual_gaps
            ),
        }
    )
    validate_financial_source_object_vertical_policy(effective, compiled=compiled)
    return effective, contract, compiled, amendment


def validate_financial_source_object_vertical_policy(
    policy: FinancialSourceObjectVerticalPolicy,
    *,
    compiled: CompiledCaseResearchContract,
) -> None:
    if (
        policy.schema_version != POLICY_SCHEMA
        or policy.run_scope != RUN_SCOPE
        or policy.case_key != compiled.case_key
    ):
        raise FinancialSourceObjectVerticalError("vertical_policy_identity_invalid")
    assets = {row.asset_id: row for row in policy.assets}
    if len(assets) != len(policy.assets) or not assets:
        raise FinancialSourceObjectVerticalError("vertical_asset_identity_invalid")
    if any(
        row.retriever_kind not in {"parent_bm25", "object_bm25"}
        or not row.index_ref
        or not row.source_records_ref
        for row in policy.assets
    ):
        raise FinancialSourceObjectVerticalError("vertical_asset_contract_invalid")
    requirements = {row.slot_id: row for row in compiled.slot_requirements}
    lanes = {row.lane_id: row for row in policy.query_lanes}
    if len(lanes) != len(policy.query_lanes) or not lanes:
        raise FinancialSourceObjectVerticalError("vertical_lane_identity_invalid")
    for lane in policy.query_lanes:
        requirement = requirements.get(lane.slot_id)
        if (
            lane.asset_id not in assets
            or requirement is None
            or not lane.query_texts
            or not lane.facet_focus
            or set(lane.facet_focus)
            - set(requirement.required_facets + requirement.optional_facets)
        ):
            raise FinancialSourceObjectVerticalError("vertical_lane_contract_invalid")
    qualification_ids: set[str] = set()
    allowed_relationships = {
        (row.evidence_owner_entity_key, row.direction, slot_id)
        for row in compiled.relationships
        for slot_id in row.allowed_slot_ids
    }
    for row in policy.reviewed_candidate_bindings:
        lane = lanes.get(row.lane_id)
        requirement = requirements.get(row.slot_id)
        if (
            row.qualification_id in qualification_ids
            or lane is None
            or requirement is None
            or lane.slot_id != row.slot_id
            or lane.evidence_owner_entity_key != row.evidence_owner_entity_key
            or lane.evidence_owner_ticker != row.evidence_owner_ticker
            or lane.relationship_direction != row.relationship_direction
            or row.analysis_period_id not in set(compiled.accepted_period_ids)
            or not row.source_reporting_period_id
            or not row.source_excerpt
            or not row.target_excerpt
            or not row.facet_ids
            or set(row.facet_ids)
            - set(requirement.required_facets + requirement.optional_facets)
        ):
            raise FinancialSourceObjectVerticalError(
                "vertical_candidate_binding_invalid"
            )
        relationship_key = (
            row.evidence_owner_entity_key,
            row.relationship_direction,
            row.slot_id,
        )
        self_disclosure = (
            row.evidence_owner_entity_key == compiled.subject_entity_key
            and row.relationship_direction == "subject_self_disclosure"
        )
        if not self_disclosure and relationship_key not in allowed_relationships:
            raise FinancialSourceObjectVerticalError(
                "vertical_relationship_binding_missing_or_reversed"
            )
        if any(row.target_id.casefold() in query.casefold() for query in lane.query_texts):
            raise FinancialSourceObjectVerticalError(
                "vertical_query_contains_review_target_id"
            )
        qualification_ids.add(row.qualification_id)
    gap_ids: set[str] = set()
    for gap in policy.declared_residual_gaps:
        requirement = requirements.get(gap.slot_id)
        if (
            gap.gap_id in gap_ids
            or requirement is None
            or gap.facet_id not in set(requirement.required_facets)
            or gap.gap_code not in set(requirement.typed_gap_codes)
            or set(gap.attempted_lane_ids) - set(lanes)
        ):
            raise FinancialSourceObjectVerticalError("vertical_gap_contract_invalid")
        gap_ids.add(gap.gap_id)
    required_zero = {
        "network",
        "provider",
        "model",
        "embedding",
        "rerank",
        "evidence_promotion",
    }
    if any(int(policy.hard_boundaries.get(key, -1)) != 0 for key in required_zero):
        raise FinancialSourceObjectVerticalError("vertical_zero_call_boundary_invalid")
    if policy.hard_boundaries.get("qrels_loaded_after_candidate_generation") is not True:
        raise FinancialSourceObjectVerticalError(
            "vertical_candidate_generation_order_invalid"
        )


def execute_financial_source_object_vertical(
    *,
    policy: FinancialSourceObjectVerticalPolicy,
    compiled: CompiledCaseResearchContract,
    repo_root: str | Path,
    retriever_factories: Mapping[str, Callable[[str | Path], Any]] | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    assets = {row.asset_id: row for row in policy.assets}
    source_records = _load_bound_source_records(
        policy=policy,
        assets=assets,
        repo_root=root,
    )
    factories = dict(retriever_factories or _default_retriever_factories())
    retrievers: dict[str, Any] = {}
    lane_results: list[dict[str, Any]] = []
    try:
        for lane in policy.query_lanes:
            asset = assets[lane.asset_id]
            retriever = retrievers.get(asset.asset_id)
            if retriever is None:
                factory = factories.get(asset.retriever_kind)
                if factory is None:
                    raise FinancialSourceObjectVerticalError(
                        "vertical_retriever_factory_missing"
                    )
                retriever = factory(_resolve(root, asset.index_ref))
                retrievers[asset.asset_id] = retriever
            lane_results.append(_execute_lane(lane, retriever=retriever))
    finally:
        for retriever in retrievers.values():
            close = getattr(retriever, "close", None)
            if callable(close):
                close()

    # Candidate generation is complete before the reviewed target bindings are read.
    lane_index = {row["lane_id"]: row for row in lane_results}
    qualified, qualification_rows = _qualify_reviewed_candidates(
        policy=policy,
        compiled=compiled,
        source_records=source_records,
        lane_index=lane_index,
    )
    declared_gaps = tuple(
        TypedResidualGap(
            gap_id=row.gap_id,
            case_key=compiled.case_key,
            slot_id=row.slot_id,
            facet_id=row.facet_id,
            gap_code=row.gap_code,
            attempted_route_refs=row.attempted_lane_ids,
        )
        for row in policy.declared_residual_gaps
    )
    evaluation = DeterministicEvidencePackEvaluator().evaluate(
        compiled,
        qualified,
        declared_gaps,
    )
    retrieval_misses = [
        row for row in qualification_rows if row["qualification_status"] != "qualified"
    ]
    contract_rejections = list(evaluation.rejected_candidates)
    result_status = (
        "engineering_pass_product_pack_incomplete"
        if not retrieval_misses
        and not contract_rejections
        and evaluation.status == "incomplete_not_admitted"
        else (
            "engineering_pass_candidate_pack_ready_for_evidence_gate"
            if not retrieval_misses
            and not contract_rejections
            and evaluation.status == "candidate_complete_pending_evidence_gate"
            else "engineering_blocked_candidate_retrieval_content_or_contract_failure"
        )
    )
    source_bundles = _source_bundle_summaries(
        policy=policy,
        source_records=source_records,
        qualification_rows=qualification_rows,
    )
    public_lane_results = _public_lane_results(lane_results)
    body = {
        "schema_version": RESULT_SCHEMA,
        "contract_ref": policy.contract_ref,
        "run_scope": policy.run_scope,
        "recorded_at": policy.recorded_at,
        "case_key": compiled.case_key,
        "status": result_status,
        "compiled_case_digest": compiled.compiled_digest,
        "compiled_core_fingerprint": compiled.core_fingerprint,
        "query_lane_results": public_lane_results,
        "source_object_bundles": source_bundles,
        "candidate_qualifications": qualification_rows,
        "candidate_pack_evaluation": evaluation.model_dump(mode="json"),
        "declared_residual_gap_business": [
            row.model_dump(mode="json") for row in policy.declared_residual_gaps
        ],
        "hierarchy_findings": [
            row.model_dump(mode="json") for row in policy.hierarchy_findings
        ],
        "observed_counts": {
            "source_records": len(source_records),
            "query_lanes": len(public_lane_results),
            "retrieved_candidate_rows": sum(
                len(row["candidates"]) for row in public_lane_results
            ),
            "reviewed_candidate_bindings": len(policy.reviewed_candidate_bindings),
            "qualified_candidates": len(qualified),
            "reviewed_candidate_misses": len(retrieval_misses),
            "candidate_contract_rejections": len(contract_rejections),
            "declared_residual_gaps": len(declared_gaps),
        },
        "observed_calls": {
            "network": 0,
            "provider": 0,
            "model": 0,
            "embedding": 0,
            "rerank": 0,
            "evidence_promotion": 0,
        },
        "stage_acceptance": {
            "generic_contract_bound": True,
            "financial_source_inventory_materialized": bool(source_records),
            "parent_child_object_hierarchy_observed": bool(source_bundles),
            "typed_query_lanes_executed": len(public_lane_results)
            == len(policy.query_lanes),
            "multi_candidate_pack_evaluated": True,
            "reviewed_candidate_recall_complete": not retrieval_misses,
            "candidate_contract_valid": not contract_rejections,
            "dell_local_evidence_pack_complete": evaluation.status
            == "candidate_complete_pending_evidence_gate",
            "evidence_promotion_admitted": False,
            "sparse_dense_rebuild_admitted": False,
            "external_supplement_admitted": False,
            "model_synthesis_admitted": False,
        },
        "known_boundary": (
            "This is a zero-network, zero-model DELL local vertical. Qualified rows remain "
            "candidates, not Evidence. Declared gaps are the only permitted handoff to later "
            "external supplement; this result does not admit sparse/dense rebuild or model synthesis."
        ),
    }
    return {**body, "result_digest": canonical_digest(body)}


def _execute_lane(lane: FinancialQueryLane, *, retriever: Any) -> dict[str, Any]:
    query_results = [
        retriever.search(
            query,
            top_k=lane.candidate_budget,
            filters=dict(lane.filters),
        )
        for query in lane.query_texts
    ]
    seen: set[str] = set()
    candidates: list[dict[str, Any]] = []
    positions = [0 for _ in query_results]
    while len(candidates) < lane.candidate_budget:
        progressed = False
        for query_index, rows in enumerate(query_results):
            while positions[query_index] < len(rows):
                row = rows[positions[query_index]]
                positions[query_index] += 1
                progressed = True
                target_id = str(
                    row.get("object_id")
                    or row.get("evidence_id")
                    or (row.get("record") or {}).get("object_id")
                    or (row.get("record") or {}).get("evidence_id")
                    or ""
                )
                if not target_id or target_id in seen:
                    continue
                seen.add(target_id)
                record = dict(row.get("record") or {})
                preview = str(
                    row.get("preview")
                    or row.get("text_preview")
                    or record.get("preview")
                    or record.get("claim_text")
                    or record.get("text")
                    or ""
                )
                candidates.append(
                    {
                        "target_id": target_id,
                        "route_rank": len(candidates) + 1,
                        "matched_query_index": query_index,
                        "score": round(float(row.get("score") or 0.0), 8),
                        "object_type": str(record.get("object_type") or "source_segment"),
                        "source_record_id": str(
                            record.get("source_evidence_id")
                            or record.get("evidence_id")
                            or target_id
                        ),
                        "ticker": str(record.get("ticker") or ""),
                        "fiscal_year": record.get("fiscal_year"),
                        "form_type": str(
                            record.get("form_type") or record.get("source_type") or ""
                        ),
                        "section": str(record.get("section") or ""),
                        "subsection": str(record.get("subsection") or ""),
                        "preview": _clip(preview),
                        "target_content": _target_content(record, preview),
                    }
                )
                break
            if len(candidates) >= lane.candidate_budget:
                break
        if not progressed:
            break
    body = {
        "lane_id": lane.lane_id,
        "slot_id": lane.slot_id,
        "facet_focus": list(lane.facet_focus),
        "asset_id": lane.asset_id,
        "evidence_owner_entity_key": lane.evidence_owner_entity_key,
        "evidence_owner_ticker": lane.evidence_owner_ticker,
        "relationship_direction": lane.relationship_direction,
        "query_count": len(lane.query_texts),
        "candidate_budget": lane.candidate_budget,
        "candidates": candidates,
        "status": "completed_with_candidates" if candidates else "completed_typed_gap",
    }
    return {**body, "lane_digest": canonical_digest(body)}


def _public_lane_results(
    lane_results: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Remove private qualification text after target matching is complete.

    The result artifact is an audit index, not a second copy of the source corpus.
    Full source text remains content-addressed in the bound source records.
    """
    public_rows: list[dict[str, Any]] = []
    for lane in lane_results:
        public_candidates = [
            {key: value for key, value in dict(candidate).items() if key != "target_content"}
            for candidate in lane.get("candidates", [])
        ]
        body = {
            key: value
            for key, value in dict(lane).items()
            if key not in {"candidates", "lane_digest"}
        }
        body["candidates"] = public_candidates
        public_rows.append({**body, "lane_digest": canonical_digest(body)})
    return public_rows


def _qualify_reviewed_candidates(
    *,
    policy: FinancialSourceObjectVerticalPolicy,
    compiled: CompiledCaseResearchContract,
    source_records: Mapping[str, Mapping[str, Any]],
    lane_index: Mapping[str, Mapping[str, Any]],
) -> tuple[list[FinancialCandidate], list[dict[str, Any]]]:
    qualified: list[FinancialCandidate] = []
    rows: list[dict[str, Any]] = []
    for binding in policy.reviewed_candidate_bindings:
        lane = lane_index[binding.lane_id]
        targets = {
            str(row["target_id"]): row for row in lane.get("candidates", [])
        }
        target = targets.get(binding.target_id)
        source = source_records.get(binding.source_record_id)
        status = "qualified"
        codes: list[str] = []
        if target is None:
            status = "retrieval_target_missing"
            codes.append("reviewed_target_not_in_candidate_pool")
        if source is None:
            status = "source_record_missing"
            codes.append("bound_parent_source_record_missing")
        if source is not None:
            if str(source.get("ticker") or "") != binding.evidence_owner_ticker:
                status = "source_identity_mismatch"
                codes.append("source_owner_ticker_mismatch")
            publication = str(
                source.get("publication_date")
                or source.get("published_at")
                or ""
            )
            try:
                publication_date = date.fromisoformat(publication)
                research_as_of_date = date.fromisoformat(compiled.as_of_date)
            except ValueError:
                publication_date = None
                research_as_of_date = None
            if (
                publication_date is None
                or research_as_of_date is None
                or publication_date > research_as_of_date
            ):
                status = "source_period_mismatch"
                codes.append("source_publication_after_research_as_of")
            if _normalise(binding.source_excerpt) not in _normalise(
                str(source.get("text") or "")
            ):
                status = "source_content_mismatch"
                codes.append("reviewed_source_excerpt_not_found")
        if target is not None and _normalise(binding.target_excerpt) not in _normalise(
            str(target.get("target_content") or "")
        ):
            status = "target_content_mismatch"
            codes.append("reviewed_target_excerpt_not_found")
        source_digest = (
            hashlib.sha256(
                str(source.get("text") or "").encode("utf-8")
            ).hexdigest()
            if source is not None
            else ""
        )
        candidate_id = "financial_candidate_" + canonical_digest(
            {
                "qualification_id": binding.qualification_id,
                "target_id": binding.target_id,
                "source_digest": source_digest,
            }
        )[:24]
        if status == "qualified" and source is not None and target is not None:
            source_url = str(source.get("source_url") or "")
            metadata = dict(source.get("metadata") or {})
            canonical_source_id = str(
                source.get("accession_number")
                or metadata.get("accession_number")
                or source_url
                or binding.source_record_id
            )
            candidate = FinancialCandidate(
                candidate_id=candidate_id,
                case_key=compiled.case_key,
                slot_id=binding.slot_id,
                subject_entity_key=compiled.subject_entity_key,
                evidence_owner_entity_key=binding.evidence_owner_entity_key,
                relationship_direction=binding.relationship_direction,
                period_id=binding.analysis_period_id,
                facet_ids=binding.facet_ids,
                source_family=f"author:{binding.evidence_owner_entity_key}",
                canonical_source_id=canonical_source_id,
                authority_tier=binding.authority_tier,
                candidate_role=binding.candidate_role,
                citation_ref=f"{source_url}#{binding.source_record_id}",
                lineage_ref=f"source-record:{binding.source_record_id}:sha256:{source_digest}",
                candidate_state="qualified_candidate",
                semantic_claim_key=binding.semantic_claim_key,
                polarity=binding.polarity,
            )
            qualified.append(candidate)
        rows.append(
            {
                "qualification_id": binding.qualification_id,
                "candidate_id": candidate_id,
                "qualification_status": status,
                "finding_codes": codes,
                "lane_id": binding.lane_id,
                "target_id": binding.target_id,
                "target_rank": None if target is None else int(target["route_rank"]),
                "source_record_id": binding.source_record_id,
                "slot_id": binding.slot_id,
                "facet_ids": list(binding.facet_ids),
                "period_binding": {
                    "research_as_of_date": compiled.as_of_date,
                    "analysis_period_id": binding.analysis_period_id,
                    "source_reporting_period_id": binding.source_reporting_period_id,
                    "source_period_end": ""
                    if source is None
                    else str(source.get("period_end") or ""),
                    "source_publication_date": ""
                    if source is None
                    else str(
                        source.get("publication_date")
                        or source.get("published_at")
                        or ""
                    ),
                    "relationship_valid_as_of": compiled.as_of_date,
                },
                "source_content_digest": source_digest,
                "business_meaning_zh": binding.business_meaning_zh,
                "content_limitation_zh": binding.content_limitation_zh,
                "candidate_state": "candidate_only_not_evidence",
            }
        )
    return qualified, rows


def _load_bound_source_records(
    *,
    policy: FinancialSourceObjectVerticalPolicy,
    assets: Mapping[str, LocalRetrievalAsset],
    repo_root: Path,
) -> dict[str, dict[str, Any]]:
    wanted_by_path: dict[Path, set[str]] = defaultdict(set)
    lane_assets = {row.lane_id: row.asset_id for row in policy.query_lanes}
    for binding in policy.reviewed_candidate_bindings:
        asset = assets[lane_assets[binding.lane_id]]
        wanted_by_path[_resolve(repo_root, asset.source_records_ref)].add(
            binding.source_record_id
        )
    found: dict[str, dict[str, Any]] = {}
    for path, wanted in wanted_by_path.items():
        if not path.is_file():
            raise FinancialSourceObjectVerticalError("vertical_source_records_missing")
        remaining = set(wanted)
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not remaining:
                    break
                if not any(source_id in line for source_id in remaining):
                    continue
                row = json.loads(line)
                source_id = str(row.get("evidence_id") or "")
                if source_id in remaining:
                    found[source_id] = row
                    remaining.remove(source_id)
        if remaining:
            raise FinancialSourceObjectVerticalError(
                "vertical_bound_source_record_not_found"
            )
    return found


def _source_bundle_summaries(
    *,
    policy: FinancialSourceObjectVerticalPolicy,
    source_records: Mapping[str, Mapping[str, Any]],
    qualification_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_source: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in qualification_rows:
        by_source[str(row["source_record_id"])].append(row)
    summaries: list[dict[str, Any]] = []
    for source_id in sorted(by_source):
        source = source_records[source_id]
        rows = by_source[source_id]
        child_ids = sorted(
            {
                str(row["target_id"])
                for row in rows
                if str(row["target_id"]) != source_id
            }
        )
        metadata = dict(source.get("metadata") or {})
        summaries.append(
            {
                "source_record_id": source_id,
                "ticker": str(source.get("ticker") or ""),
                "source_type": str(
                    source.get("form_type") or source.get("source_type") or ""
                ),
                "source_tier": str(source.get("source_tier") or ""),
                "source_url": str(source.get("source_url") or ""),
                "publication_date": str(
                    source.get("publication_date") or source.get("published_at") or ""
                ),
                "period_end": str(source.get("period_end") or ""),
                "reported_fiscal_year": metadata.get("reported_fiscal_year"),
                "reported_fiscal_period": metadata.get("reported_fiscal_period"),
                "parent_source_present": True,
                "child_object_ids": child_ids,
                "child_object_count": len(child_ids),
                "content_digest": hashlib.sha256(
                    str(source.get("text") or "").encode("utf-8")
                ).hexdigest(),
                "candidate_state": "candidate_only_not_evidence",
            }
        )
    return summaries


def _target_content(record: Mapping[str, Any], preview: str) -> str:
    values = [
        preview,
        str(record.get("claim_text") or ""),
        str(record.get("text") or ""),
        str(record.get("title") or ""),
        str(record.get("text_before") or ""),
        str(record.get("text_after") or ""),
    ]
    return " ".join(value for value in values if value)


def _default_retriever_factories() -> dict[str, Callable[[str | Path], Any]]:
    from retrieval.bm25_retriever import BM25Retriever
    from retrieval.object_bm25_retriever import ObjectBM25Retriever

    return {
        "parent_bm25": BM25Retriever,
        "object_bm25": ObjectBM25Retriever,
    }


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _normalise(value: str) -> str:
    return " ".join(value.split()).casefold()


def _clip(value: str, limit: int = 700) -> str:
    return " ".join(value.split())[:limit]


def _ordered_unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


__all__ = [
    "FinancialSourceObjectVerticalError",
    "FinancialSourceObjectVerticalPolicy",
    "FinancialSourceObjectVerticalPolicyAmendment",
    "POLICY_AMENDMENT_SCHEMA",
    "POLICY_SCHEMA",
    "RESULT_SCHEMA",
    "RUN_SCOPE",
    "execute_financial_source_object_vertical",
    "load_amended_financial_source_object_vertical_policy",
    "load_financial_source_object_vertical_policy",
    "normalized_sha256",
    "validate_financial_source_object_vertical_policy",
]
