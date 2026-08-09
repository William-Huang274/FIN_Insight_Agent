from __future__ import annotations

from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from sec_agent.canonical_runtime.models import StrictModel, canonical_digest
from sec_agent.financial_research_generalization_contract import (
    CompiledCaseResearchContract,
    compile_external_case_profile,
)
from sec_agent.financial_research_held_out_profile_registry import (
    HeldOutProfileSelectionPolicy,
    load_held_out_profile_selection_policy,
)
from sec_agent.financial_research_source_object_vertical import (
    FinancialQueryLane,
    LocalRetrievalAsset,
    normalized_sha256,
)


HELD_OUT_CANDIDATE_POLICY_SCHEMA = (
    "fin_ia_0_1_3_s1_three_held_out_candidate_generation_policy_v1_0"
)
HELD_OUT_CANDIDATE_RESULT_SCHEMA = (
    "fin_ia_0_1_3_s1_three_held_out_candidate_generation_result_v1_0"
)
HELD_OUT_CANDIDATE_RUN_SCOPE = (
    "S1_THREE_HELD_OUT_GOLD_BLIND_LOCAL_CANDIDATE_GENERATION"
)


class HeldOutCandidateGenerationError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class LockedCandidateArtifact(StrictModel):
    artifact_id: str
    path: str
    normalized_sha256: str
    role: str


class CurrentnessRequirement(StrictModel):
    required_period_end_on_or_after: str
    accepted_form_types: tuple[str, ...]
    missing_current_source_is_typed_gap: bool


class HeldOutCandidateCasePlan(StrictModel):
    case_key: str
    assets: tuple[LocalRetrievalAsset, ...]
    query_lanes: tuple[FinancialQueryLane, ...]
    currentness_requirement: CurrentnessRequirement


class HeldOutCandidateGenerationPolicy(StrictModel):
    schema_version: str
    contract_ref: str
    run_scope: str
    recorded_at: str
    attempt_id: str
    selection_policy_ref: str
    selection_policy_sha256: str
    expected_core_fingerprint: str
    locked_artifacts: tuple[LockedCandidateArtifact, ...]
    case_plans: tuple[HeldOutCandidateCasePlan, ...]
    hard_boundaries: dict[str, Any]


def load_held_out_candidate_generation_policy(
    path: str | Path,
    *,
    repo_root: str | Path,
) -> tuple[HeldOutCandidateGenerationPolicy, HeldOutProfileSelectionPolicy, Any]:
    root = Path(repo_root).resolve()
    try:
        policy = HeldOutCandidateGenerationPolicy.model_validate(
            json.loads(Path(path).read_text(encoding="utf-8"))
        )
    except Exception as exc:
        raise HeldOutCandidateGenerationError(
            "held_out_candidate_policy_shape_invalid"
        ) from exc
    if (
        policy.schema_version != HELD_OUT_CANDIDATE_POLICY_SCHEMA
        or policy.run_scope != HELD_OUT_CANDIDATE_RUN_SCOPE
    ):
        raise HeldOutCandidateGenerationError(
            "held_out_candidate_policy_identity_invalid"
        )
    _validate_zero_call_boundary(policy.hard_boundaries)
    _validate_locked_artifacts(policy, repo_root=root)
    selection_path = _resolve(root, policy.selection_policy_ref)
    if normalized_sha256(selection_path) != policy.selection_policy_sha256:
        raise HeldOutCandidateGenerationError(
            "held_out_candidate_selection_digest_mismatch"
        )
    selection, _base_contract, extended_contract = (
        load_held_out_profile_selection_policy(selection_path, repo_root=root)
    )
    _validate_case_plans(
        policy,
        selection=selection,
        extended_contract=extended_contract,
        repo_root=root,
    )
    return policy, selection, extended_contract


def execute_held_out_candidate_generation(
    *,
    policy: HeldOutCandidateGenerationPolicy,
    selection: HeldOutProfileSelectionPolicy,
    extended_contract: Any,
    repo_root: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    before = _locked_digest_map(policy, repo_root=root)
    selections = {row.profile.case_key: row for row in selection.selections}
    case_results: list[dict[str, Any]] = []
    for plan in policy.case_plans:
        selected = selections[plan.case_key]
        compiled = compile_external_case_profile(
            extended_contract,
            selected.profile,
        )
        case_results.append(
            _execute_case(
                plan,
                compiled=compiled,
                repo_root=root,
            )
        )
    after = _locked_digest_map(policy, repo_root=root)
    locked_unchanged = before == after
    lanes_terminal = all(
        row["stage_acceptance"]["all_query_lanes_terminal"]
        for row in case_results
    )
    identity_clean = all(
        row["stage_acceptance"]["candidate_identity_filters_hold"]
        for row in case_results
    )
    status = (
        "gold_blind_candidate_generation_complete_review_required"
        if locked_unchanged and lanes_terminal and identity_clean
        else "candidate_generation_blocked_or_identity_contaminated"
    )
    body = {
        "schema_version": HELD_OUT_CANDIDATE_RESULT_SCHEMA,
        "contract_ref": policy.contract_ref,
        "run_scope": policy.run_scope,
        "recorded_at": policy.recorded_at,
        "attempt_id": policy.attempt_id,
        "status": status,
        "selection_policy_ref": policy.selection_policy_ref,
        "selection_policy_sha256": policy.selection_policy_sha256,
        "expected_core_fingerprint": policy.expected_core_fingerprint,
        "locked_artifacts_before": before,
        "locked_artifacts_after": after,
        "case_results": case_results,
        "observed_calls": {
            "network": 0,
            "provider": 0,
            "model": 0,
            "embedding": 0,
            "rerank": 0,
            "evidence_promotion": 0,
            "local_sparse_retrieval": sum(
                row["observed_counts"]["query_count"] for row in case_results
            ),
        },
        "stage_acceptance": {
            "selection_remained_frozen": locked_unchanged,
            "gold_blind_queries_executed": lanes_terminal,
            "candidate_identity_filters_hold": identity_clean,
            "candidate_review_started": False,
            "held_out_generalization_complete": False,
            "sparse_dense_rebuild_admitted": False,
            "external_supplement_admitted": False,
            "model_synthesis_admitted": False,
        },
        "known_boundary": (
            "This result terminalizes Gold-blind local sparse candidate generation only. "
            "Candidate text is an audit preview backed by immutable local source references; "
            "it is not Evidence. Current-period absence is preserved as a source-currentness "
            "finding. No qrels, Gold mart, target identifier, network source, embedding, reranker, "
            "model or Evidence promotion participated."
        ),
    }
    return {**body, "result_digest": canonical_digest(body)}


def _execute_case(
    plan: HeldOutCandidateCasePlan,
    *,
    compiled: CompiledCaseResearchContract,
    repo_root: Path,
) -> dict[str, Any]:
    factories = _retriever_factories()
    assets = {row.asset_id: row for row in plan.assets}
    retrievers: dict[str, Any] = {}
    lane_results: list[dict[str, Any]] = []
    try:
        for lane in plan.query_lanes:
            asset = assets[lane.asset_id]
            if lane.asset_id not in retrievers:
                retrievers[lane.asset_id] = factories[asset.retriever_kind](
                    _resolve(repo_root, asset.index_ref)
                )
            lane_results.append(
                _execute_lane(
                    lane,
                    asset=asset,
                    retriever=retrievers[lane.asset_id],
                )
            )
    finally:
        for retriever in retrievers.values():
            _close_retriever(retriever)

    candidates = [
        candidate
        for lane in lane_results
        for candidate in lane["candidates"]
    ]
    unique_candidate_refs = {
        (row["asset_id"], row["target_id"]) for row in candidates
    }
    subject_ticker = next(
        lane.evidence_owner_ticker
        for lane in plan.query_lanes
        if lane.evidence_owner_entity_key == compiled.subject_entity_key
    )
    subject_candidates = [
        row for row in candidates if row["ticker"] == subject_ticker
    ]
    cutoff = date.fromisoformat(
        plan.currentness_requirement.required_period_end_on_or_after
    )
    accepted_forms = set(plan.currentness_requirement.accepted_form_types)
    current_subject = [
        row
        for row in subject_candidates
        if _parse_date(row.get("period_end")) >= cutoff
        and row.get("form_type") in accepted_forms
    ]
    wrong_ticker = [
        row
        for lane in lane_results
        for row in lane["candidates"]
        if row["ticker"] != lane["evidence_owner_ticker"]
    ]
    slot_counts = Counter(
        lane["slot_id"]
        for lane in lane_results
        if lane["candidates"]
    )
    required_slots = {
        row.slot_id for row in compiled.slot_requirements if row.required
    }
    terminal = len(lane_results) == len(plan.query_lanes)
    body = {
        "case_key": plan.case_key,
        "compiled_case_digest": compiled.compiled_digest,
        "compiled_core_fingerprint": compiled.core_fingerprint,
        "subject_ticker": subject_ticker,
        "currentness_requirement": plan.currentness_requirement.model_dump(
            mode="json"
        ),
        "query_lane_results": lane_results,
        "candidate_period_histogram": _histogram(candidates, "fiscal_year"),
        "candidate_form_histogram": _histogram(candidates, "form_type"),
        "candidate_object_type_histogram": _histogram(candidates, "object_type"),
        "current_subject_candidate_refs": [
            f"{row['asset_id']}::{row['target_id']}" for row in current_subject
        ],
        "source_currentness_status": (
            "current_period_candidate_observed"
            if current_subject
            else "typed_current_source_gap"
        ),
        "candidate_bearing_required_slots": sorted(
            required_slots & set(slot_counts)
        ),
        "zero_candidate_required_slots": sorted(
            required_slots - set(slot_counts)
        ),
        "observed_counts": {
            "query_lanes": len(lane_results),
            "query_count": sum(row["query_count"] for row in lane_results),
            "candidate_rows": len(candidates),
            "unique_candidate_refs": len(unique_candidate_refs),
            "wrong_ticker_candidates": len(wrong_ticker),
            "subject_candidate_rows": len(subject_candidates),
            "current_subject_candidate_rows": len(current_subject),
            "required_slots_with_candidates": len(required_slots & set(slot_counts)),
            "required_slots_without_candidates": len(required_slots - set(slot_counts)),
        },
        "stage_acceptance": {
            "all_query_lanes_terminal": terminal,
            "candidate_identity_filters_hold": not wrong_ticker,
            "all_required_slots_have_candidate_pool": not (
                required_slots - set(slot_counts)
            ),
            "current_period_source_available": bool(current_subject),
            "candidate_quality_review_complete": False,
            "candidate_pack_complete": False,
        },
    }
    return {**body, "case_result_digest": canonical_digest(body)}


def _execute_lane(
    lane: FinancialQueryLane,
    *,
    asset: LocalRetrievalAsset,
    retriever: Any,
) -> dict[str, Any]:
    query_results = [
        retriever.search(
            query,
            top_k=lane.candidate_budget,
            filters=dict(lane.filters),
        )
        for query in lane.query_texts
    ]
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    positions = [0 for _ in query_results]
    while len(candidates) < lane.candidate_budget:
        progressed = False
        for query_index, rows in enumerate(query_results):
            while positions[query_index] < len(rows):
                row = rows[positions[query_index]]
                positions[query_index] += 1
                progressed = True
                record = dict(row.get("record") or {})
                target_id = str(
                    row.get("object_id")
                    or row.get("evidence_id")
                    or record.get("object_id")
                    or record.get("evidence_id")
                    or ""
                )
                if not target_id or target_id in seen:
                    continue
                seen.add(target_id)
                metadata = (
                    dict(record.get("metadata") or {})
                    if isinstance(record.get("metadata"), Mapping)
                    else {}
                )
                preview = str(
                    row.get("preview")
                    or row.get("text_preview")
                    or record.get("preview")
                    or record.get("claim_text")
                    or record.get("text")
                    or ""
                )
                source_record_id = str(
                    record.get("source_evidence_id")
                    or record.get("evidence_id")
                    or target_id
                )
                candidate = {
                    "asset_id": asset.asset_id,
                    "source_records_ref": asset.source_records_ref,
                    "target_id": target_id,
                    "source_record_id": source_record_id,
                    "route_rank": len(candidates) + 1,
                    "matched_query_index": query_index,
                    "score": round(float(row.get("score") or 0.0), 8),
                    "object_type": str(
                        record.get("object_type") or "source_segment"
                    ),
                    "ticker": str(record.get("ticker") or ""),
                    "fiscal_year": record.get("fiscal_year"),
                    "fiscal_period": str(
                        record.get("fiscal_period")
                        or metadata.get("reported_fiscal_period")
                        or ""
                    ),
                    "form_type": str(
                        record.get("form_type")
                        or record.get("source_type")
                        or metadata.get("form_type")
                        or ""
                    ),
                    "section": str(record.get("section") or ""),
                    "subsection": str(record.get("subsection") or ""),
                    "publication_date": str(
                        record.get("publication_date")
                        or record.get("published_at")
                        or metadata.get("filing_date")
                        or ""
                    ),
                    "period_end": str(
                        record.get("period_end")
                        or metadata.get("period_end")
                        or ""
                    ),
                    "source_locator": str(
                        record.get("source_url")
                        or metadata.get("source_url")
                        or source_record_id
                    ),
                    "preview": _clip(preview),
                    "source_record_digest": canonical_digest(record),
                    "candidate_state": "candidate_only_not_evidence",
                }
                candidates.append(candidate)
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
        "query_texts": list(lane.query_texts),
        "filters": dict(lane.filters),
        "query_count": len(lane.query_texts),
        "candidate_budget": lane.candidate_budget,
        "candidates": candidates,
        "status": (
            "completed_with_candidates"
            if candidates
            else "completed_typed_zero_result"
        ),
    }
    return {**body, "lane_digest": canonical_digest(body)}


def _validate_case_plans(
    policy: HeldOutCandidateGenerationPolicy,
    *,
    selection: HeldOutProfileSelectionPolicy,
    extended_contract: Any,
    repo_root: Path,
) -> None:
    selected = {row.profile.case_key: row for row in selection.selections}
    if tuple(row.case_key for row in policy.case_plans) != tuple(selected):
        raise HeldOutCandidateGenerationError(
            "held_out_candidate_case_order_or_identity_invalid"
        )
    serialized = json.dumps(policy.model_dump(mode="json"), ensure_ascii=False)
    forbidden_patterns = (
        r"(?i)qrels",
        r"(?i)gold[_ -]?(?:fact|target|answer)",
        r"(?i)target_id",
        r"(?i)accession_number",
        r"https?://",
        r"\b\d{10}-\d{2}-\d{6}\b",
    )
    if any(re.search(pattern, serialized) for pattern in forbidden_patterns):
        raise HeldOutCandidateGenerationError(
            "held_out_candidate_answer_or_locator_leakage"
        )
    for plan in policy.case_plans:
        compiled = compile_external_case_profile(
            extended_contract,
            selected[plan.case_key].profile,
        )
        if compiled.core_fingerprint != policy.expected_core_fingerprint:
            raise HeldOutCandidateGenerationError(
                "held_out_candidate_core_fingerprint_mismatch"
            )
        _validate_case_plan(plan, compiled=compiled, repo_root=repo_root)


def _validate_case_plan(
    plan: HeldOutCandidateCasePlan,
    *,
    compiled: CompiledCaseResearchContract,
    repo_root: Path,
) -> None:
    assets = {row.asset_id: row for row in plan.assets}
    if len(assets) != len(plan.assets) or not assets:
        raise HeldOutCandidateGenerationError(
            "held_out_candidate_asset_identity_invalid"
        )
    if any(
        row.retriever_kind not in {"parent_bm25", "object_bm25"}
        or not _resolve(repo_root, row.index_ref).exists()
        or not _resolve(repo_root, row.source_records_ref).exists()
        for row in plan.assets
    ):
        raise HeldOutCandidateGenerationError(
            "held_out_candidate_asset_missing_or_kind_invalid"
        )
    lane_ids = tuple(row.lane_id for row in plan.query_lanes)
    if not lane_ids or len(lane_ids) != len(set(lane_ids)):
        raise HeldOutCandidateGenerationError(
            "held_out_candidate_lane_identity_invalid"
        )
    requirements = {row.slot_id: row for row in compiled.slot_requirements}
    relationships = {
        (row.evidence_owner_entity_key, row.direction, slot_id)
        for row in compiled.relationships
        for slot_id in row.allowed_slot_ids
    }
    subject_required_slots: set[str] = set()
    for lane in plan.query_lanes:
        requirement = requirements.get(lane.slot_id)
        if (
            requirement is None
            or lane.asset_id not in assets
            or not lane.query_texts
            or any(not value.strip() for value in lane.query_texts)
            or set(lane.facet_focus)
            - set(requirement.required_facets + requirement.optional_facets)
            or str(lane.filters.get("ticker") or "")
            != lane.evidence_owner_ticker
        ):
            raise HeldOutCandidateGenerationError(
                "held_out_candidate_lane_contract_invalid"
            )
        if lane.evidence_owner_entity_key == compiled.subject_entity_key:
            if lane.relationship_direction != "subject_self_disclosure":
                raise HeldOutCandidateGenerationError(
                    "held_out_candidate_subject_direction_invalid"
                )
            if requirement.required:
                subject_required_slots.add(lane.slot_id)
        elif (
            lane.evidence_owner_entity_key,
            lane.relationship_direction,
            lane.slot_id,
        ) not in relationships:
            raise HeldOutCandidateGenerationError(
                "held_out_candidate_relationship_missing_or_reversed"
            )
    expected_required_slots = {
        row.slot_id for row in compiled.slot_requirements if row.required
    }
    if subject_required_slots != expected_required_slots:
        raise HeldOutCandidateGenerationError(
            "held_out_candidate_required_subject_slot_missing"
        )
    currentness = plan.currentness_requirement
    try:
        date.fromisoformat(currentness.required_period_end_on_or_after)
    except ValueError as exc:
        raise HeldOutCandidateGenerationError(
            "held_out_candidate_currentness_date_invalid"
        ) from exc
    if (
        not currentness.accepted_form_types
        or not currentness.missing_current_source_is_typed_gap
    ):
        raise HeldOutCandidateGenerationError(
            "held_out_candidate_currentness_boundary_invalid"
        )


def _validate_zero_call_boundary(boundary: Mapping[str, Any]) -> None:
    required_zero = {
        "network",
        "provider",
        "model",
        "embedding",
        "rerank",
        "evidence_promotion",
    }
    if any(int(boundary.get(key, -1)) != 0 for key in required_zero):
        raise HeldOutCandidateGenerationError(
            "held_out_candidate_zero_call_boundary_invalid"
        )
    if (
        boundary.get("selection_must_remain_frozen") is not True
        or boundary.get("candidate_generation_before_review") is not True
        or boundary.get("answer_or_target_locator_allowed") is not False
        or boundary.get("core_modification_allowed") is not False
    ):
        raise HeldOutCandidateGenerationError(
            "held_out_candidate_order_or_authority_boundary_invalid"
        )


def _validate_locked_artifacts(
    policy: HeldOutCandidateGenerationPolicy,
    *,
    repo_root: Path,
) -> None:
    identities = tuple(row.artifact_id for row in policy.locked_artifacts)
    if len(identities) < 4 or len(identities) != len(set(identities)):
        raise HeldOutCandidateGenerationError(
            "held_out_candidate_locked_artifact_identity_invalid"
        )
    expected = {
        row.artifact_id: row.normalized_sha256 for row in policy.locked_artifacts
    }
    if _locked_digest_map(policy, repo_root=repo_root) != expected:
        raise HeldOutCandidateGenerationError(
            "held_out_candidate_locked_artifact_digest_mismatch"
        )


def _locked_digest_map(
    policy: HeldOutCandidateGenerationPolicy,
    *,
    repo_root: Path,
) -> dict[str, str]:
    return {
        row.artifact_id: normalized_sha256(_resolve(repo_root, row.path))
        for row in policy.locked_artifacts
    }


def _retriever_factories() -> dict[str, Any]:
    from retrieval.bm25_retriever import BM25Retriever
    from retrieval.object_bm25_retriever import ObjectBM25Retriever

    return {
        "parent_bm25": BM25Retriever,
        "object_bm25": ObjectBM25Retriever,
    }


def _close_retriever(retriever: Any) -> None:
    for name in ("_sqlite_fts_con", "_record_store_con"):
        connection = getattr(retriever, name, None)
        if connection is not None:
            connection.close()
            setattr(retriever, name, None)


def _histogram(rows: Sequence[Mapping[str, Any]], field: str) -> dict[str, int]:
    return dict(
        sorted(
            Counter(str(row.get(field) or "unknown") for row in rows).items()
        )
    )


def _parse_date(value: Any) -> date:
    try:
        return date.fromisoformat(str(value or ""))
    except ValueError:
        return date.min


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _clip(value: str, limit: int = 700) -> str:
    return " ".join(value.split())[:limit]


__all__ = [
    "HELD_OUT_CANDIDATE_POLICY_SCHEMA",
    "HELD_OUT_CANDIDATE_RESULT_SCHEMA",
    "HELD_OUT_CANDIDATE_RUN_SCOPE",
    "HeldOutCandidateGenerationError",
    "HeldOutCandidateGenerationPolicy",
    "execute_held_out_candidate_generation",
    "load_held_out_candidate_generation_policy",
]
