from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from rank_bm25 import BM25Okapi

from .contracts import FinancialResearchKernel
from .query_plan import QueryFacetPlan, QueryLane, canonical_digest
from .text import evidence_search_text, tokenize


RETRIEVAL_RESULT_SCHEMA_VERSION = "fin_ia_local_candidate_retrieval_result_v1_0"

_BOILERPLATE_HEADINGS = (
    "conference call information",
    "where to find more information",
    "available information",
    "signatures",
    "exhibits and financial statement schedules",
)
_BOILERPLATE_PHRASES = (
    "may be downloaded from",
    "can be accessed at",
    "archived version will be available",
)
_ROLE_BY_SOURCE_TYPE = {
    "10-K": "issuer_disclosure",
    "10-Q": "issuer_disclosure",
    "8-K": "issuer_disclosure",
    "20-F": "issuer_disclosure",
    "40-F": "issuer_disclosure",
    "6-K": "issuer_disclosure",
    "MARKET_SNAPSHOT": "point_in_time_market",
}


@dataclass(frozen=True)
class CandidateCorpus:
    records: tuple[dict[str, Any], ...]
    records_scanned: int
    invalid_records_excluded: int


def load_candidate_corpus(
    records_path: str | Path,
    *,
    allowed_tickers: Iterable[str],
) -> CandidateCorpus:
    """Load only configured evidence owners from a JSONL evidence store."""

    allowed = {str(value).strip().upper() for value in allowed_tickers}
    records: list[dict[str, Any]] = []
    scanned = 0
    invalid = 0
    with Path(records_path).open("r", encoding="utf-8") as handle:
        for line in handle:
            scanned += 1
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                invalid += 1
                continue
            if not isinstance(raw, dict):
                invalid += 1
                continue
            ticker = str(raw.get("ticker") or "").strip().upper()
            if ticker not in allowed:
                continue
            if not str(raw.get("evidence_id") or "").strip() or not str(
                raw.get("text") or ""
            ).strip():
                invalid += 1
                continue
            records.append(raw)
    return CandidateCorpus(
        records=tuple(records),
        records_scanned=scanned,
        invalid_records_excluded=invalid,
    )


def retrieve_query_plan(
    kernel: FinancialResearchKernel,
    plan: QueryFacetPlan,
    corpus: CandidateCorpus,
    *,
    reviewed_targets_by_slot: Mapping[str, set[str]] | None = None,
) -> dict[str, Any]:
    """Generate candidates first, then attach reviewed labels for evaluation."""

    target_map = reviewed_targets_by_slot or {}
    corpus_by_id = {
        str(record.get("evidence_id") or ""): record for record in corpus.records
    }
    corpus_by_equivalent_id: dict[str, list[dict[str, Any]]] = {}
    for record in corpus.records:
        for equivalent_id in _record_equivalent_ids(record):
            corpus_by_equivalent_id.setdefault(equivalent_id, []).append(record)
    lane_results: list[dict[str, Any]] = []
    all_candidate_ids: set[str] = set()
    hard_failures: list[str] = []
    missing_roles_by_slot: dict[str, list[str]] = {}
    for lane in plan.lanes:
        result = _retrieve_lane(kernel, plan, lane, corpus.records)
        # Labels are deliberately joined only after the terminal candidate pool.
        reviewed_targets = set(target_map.get(lane.slot_id) or ())
        for candidate in result["candidates"]:
            source_record = corpus_by_id[candidate["source_record_id"]]
            candidate["reviewed_pack_match"] = bool(
                _record_equivalent_ids(source_record) & reviewed_targets
            )
        candidate_source_ids = {
            str(candidate["source_record_id"])
            for candidate in result["candidates"]
        }
        candidate_equivalent_ids = {
            equivalent_id
            for source_id in candidate_source_ids
            for equivalent_id in _record_equivalent_ids(corpus_by_id[source_id])
        }
        all_candidate_ids.update(candidate_source_ids)
        matched = sorted(candidate_equivalent_ids & reviewed_targets)
        present = sorted(reviewed_targets & set(corpus_by_equivalent_id))
        eligible_targets: list[str] = []
        excluded_targets: dict[str, str] = {}
        for target_id in present:
            reasons = [
                _candidate_exclusion_reason(record, lane)
                for record in corpus_by_equivalent_id[target_id]
            ]
            if any(reason is None for reason in reasons):
                eligible_targets.append(target_id)
            else:
                excluded_targets[target_id] = str(sorted(set(reasons))[0])
        result["evaluation"] = {
            "reviewed_targets": len(reviewed_targets),
            "reviewed_targets_present_in_source_corpus": len(present),
            "reviewed_targets_eligible_before_scoring": len(eligible_targets),
            "eligible_reviewed_source_record_ids": eligible_targets,
            "reviewed_targets_in_candidate_pool": len(matched),
            "matched_source_record_ids": matched,
            "missing_from_source_corpus": sorted(
                reviewed_targets - set(corpus_by_equivalent_id)
            ),
            "excluded_before_scoring": excluded_targets,
            "labels_joined_after_candidate_generation": True,
        }
        observed_roles = set(result["observed_source_roles"])
        missing_roles = sorted(set(lane.required_source_roles) - observed_roles)
        result["missing_required_source_roles"] = missing_roles
        if missing_roles:
            missing_roles_by_slot[
                f"{lane.slot_id}.{lane.facet_id}"
            ] = missing_roles
        if result["hard_constraint_violations"]:
            hard_failures.extend(result["hard_constraint_violations"])
        lane_results.append(result)

    slot_evaluation: dict[str, dict[str, Any]] = {}
    for slot_id, reviewed_targets in target_map.items():
        slot_candidate_ids = {
            equivalent_id
            for result in lane_results
            if result["lane"]["slot_id"] == slot_id
            for candidate in result["candidates"]
            for equivalent_id in _record_equivalent_ids(
                corpus_by_id[str(candidate["source_record_id"])]
            )
        }
        matched = sorted(slot_candidate_ids & set(reviewed_targets))
        slot_evaluation[slot_id] = {
            "reviewed_targets": len(reviewed_targets),
            "reviewed_targets_in_slot_candidate_pool": len(matched),
            "matched_source_record_ids": matched,
        }
    mapped_target_count = sum(
        int(row["reviewed_targets"]) for row in slot_evaluation.values()
    )
    matched_target_count = sum(
        int(row["reviewed_targets_in_slot_candidate_pool"])
        for row in slot_evaluation.values()
    )
    unsigned = {
        "schema_version": RETRIEVAL_RESULT_SCHEMA_VERSION,
        "status": (
            "typed_local_candidate_retrieval_ready"
            if not hard_failures
            else "typed_local_candidate_retrieval_failed"
        ),
        "case_key": plan.case_key,
        "query_plan_digest": plan.plan_digest,
        "candidate_state": "candidate_not_evidence",
        "lane_results": lane_results,
        "summary": {
            "lane_count": len(lane_results),
            "nonempty_lane_count": sum(bool(row["candidates"]) for row in lane_results),
            "slot_count": len({row["lane"]["slot_id"] for row in lane_results}),
            "unique_candidates": len(all_candidate_ids),
            "mapped_reviewed_targets": mapped_target_count,
            "reviewed_targets_in_candidate_pool": matched_target_count,
            "slots_missing_required_source_roles": missing_roles_by_slot,
            "hard_constraint_failures": hard_failures,
            "slot_evaluation": slot_evaluation,
        },
        "known_boundary": (
            "This result is a local lexical candidate pool. A candidate is not Evidence, "
            "reviewed labels are evaluation-only, missing source roles remain explicit, "
            "and no model, network, dense retrieval or reranker was used."
        ),
    }
    return {**unsigned, "result_digest": canonical_digest(unsigned)}


def _retrieve_lane(
    kernel: FinancialResearchKernel,
    plan: QueryFacetPlan,
    lane: QueryLane,
    records: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    eligible: list[dict[str, Any]] = []
    excluded = Counter()
    owner_set = set(lane.evidence_owner_tickers)
    as_of = date.fromisoformat(lane.publication_date_lte)
    for record in records:
        reason = _candidate_exclusion_reason(record, lane)
        if reason:
            excluded[reason] += 1
            continue
        eligible.append(record)

    candidates: list[dict[str, Any]] = []
    if eligible and lane.owner_queries:
        scored: list[tuple[float, float, dict[str, Any], list[str]]] = []
        for owner_query in lane.owner_queries:
            owner_records = [
                record
                for record in eligible
                if str(record.get("ticker") or "").strip().upper()
                == owner_query.evidence_owner_ticker
            ]
            if not owner_records or not owner_query.lexical_tokens:
                continue
            tokenized = [
                tokenize(evidence_search_text(record)) for record in owner_records
            ]
            index = BM25Okapi(tokenized)
            raw_scores = index.get_scores(list(owner_query.lexical_tokens))
            query_tokens = set(owner_query.lexical_tokens)
            for record, document_tokens, raw_score in zip(
                owner_records, tokenized, raw_scores
            ):
                document_token_set = set(document_tokens)
                matched = sorted(query_tokens & document_token_set)
                matched_anchor_groups = [
                    group
                    for group in owner_query.anchor_token_groups
                    if set(group).issubset(document_token_set)
                ]
                if (
                    not matched
                    or not matched_anchor_groups
                ):
                    continue
                publication = date.fromisoformat(str(record["publication_date"]))
                age_days = (as_of - publication).days
                recency_boost = (
                    0.35 if age_days <= 366 else (0.15 if age_days <= 731 else 0.0)
                )
                subject_boost = (
                    0.25
                    if str(record.get("ticker") or "").upper()
                    == plan.subject_ticker
                    else 0.05
                )
                heading_tokens = set(
                    tokenize(
                        " ".join(
                            str(record.get(key) or "")
                            for key in ("section", "subsection")
                        )
                    )
                )
                heading_matches = len(query_tokens & heading_tokens)
                anchor_boost = min(2.0, 0.55 * len(matched_anchor_groups))
                heading_boost = min(1.0, 0.16 * heading_matches)
                final_score = (
                    float(raw_score)
                    + recency_boost
                    + subject_boost
                    + anchor_boost
                    + heading_boost
                )
                scored.append((final_score, float(raw_score), record, matched))
        scored.sort(
            key=lambda item: (
                -item[0],
                -item[1],
                str(item[2].get("publication_date") or ""),
                str(item[2].get("evidence_id") or ""),
            )
        )
        per_document: Counter[str] = Counter()
        selected_ids: set[str] = set()
        selected_rows: list[tuple[float, float, dict[str, Any], list[str]]] = []
        # Reserve one position for each contract-required source role before
        # score-only filling. Otherwise a large issuer filing can crowd out the
        # single PIT market object even when the facet explicitly requires it.
        for required_role in lane.required_source_roles:
            for row in scored:
                record = row[2]
                record_id = str(record.get("evidence_id") or "")
                if (
                    _source_role_for_record(record, plan) == required_role
                    and record_id not in selected_ids
                ):
                    selected_rows.append(row)
                    selected_ids.add(record_id)
                    break
        # Give each configured evidence owner one fair chance before filling by score.
        for owner in lane.evidence_owner_tickers:
            for row in scored:
                record = row[2]
                record_id = str(record.get("evidence_id") or "")
                if (
                    str(record.get("ticker") or "").strip().upper() == owner
                    and record_id not in selected_ids
                ):
                    selected_rows.append(row)
                    selected_ids.add(record_id)
                    break
        selected_rows.extend(
            row
            for row in scored
            if str(row[2].get("evidence_id") or "") not in selected_ids
        )
        for final_score, raw_score, record, matched in selected_rows:
            document_key = _document_key(record)
            if per_document[document_key] >= kernel.budgets.candidates_per_document:
                excluded["document_diversity_budget"] += 1
                continue
            candidates.append(
                _candidate_projection(
                    kernel,
                    plan,
                    lane,
                    record,
                    matched,
                    raw_score,
                    final_score,
                )
            )
            per_document[document_key] += 1
            if len(candidates) >= lane.candidate_budget:
                break

    hard_constraint_violations: list[str] = []
    for candidate in candidates:
        if candidate["evidence_owner_ticker"] not in owner_set:
            hard_constraint_violations.append(
                f"owner_scope_violation:{lane.slot_id}:{candidate['source_record_id']}"
            )
        if date.fromisoformat(candidate["publication_date"]) > as_of:
            hard_constraint_violations.append(
                f"as_of_violation:{lane.slot_id}:{candidate['source_record_id']}"
            )
    return {
        "lane": lane.as_dict(),
        "eligible_records_before_scoring": len(eligible),
        "exclusion_counts": dict(sorted(excluded.items())),
        "candidates": candidates,
        "observed_source_roles": sorted(
            {str(candidate["source_role"]) for candidate in candidates}
        ),
        "hard_constraint_violations": hard_constraint_violations,
    }


def _candidate_projection(
    kernel: FinancialResearchKernel,
    plan: QueryFacetPlan,
    lane: QueryLane,
    record: Mapping[str, Any],
    matched: list[str],
    raw_score: float,
    final_score: float,
) -> dict[str, Any]:
    owner = str(record.get("ticker") or "").strip().upper()
    source_type = str(record.get("source_type") or "").strip().upper()
    source_role = _source_role_for_record(record, plan)
    text = re.sub(r"\s+", " ", str(record.get("text") or "")).strip()
    temporal = _reporting_temporal_projection(record)
    if owner == plan.subject_ticker:
        relationship = "subject_self_disclosure"
        boundary = "主体公司直接披露候选；仍需 Evidence Gate 核验引用范围与事实口径。"
    else:
        relationship = _relationship_for_owner(kernel, plan.case_key, owner)
        subject_mentioned = any(
            alias.casefold() in text.casefold()
            for alias in kernel.cases[plan.case_key].subject_aliases
        )
        source_role = "related_entity_context"
        boundary = (
            "关联方文本直接提及研究主体，但仍需验证它是否证明具体交易、分配或因果关系。"
            if subject_mentioned
            else "仅是关联方自身披露的行业背景，不证明其与研究主体存在具体采购、供应或分配关系。"
        )
    return {
        "candidate_state": "candidate_not_evidence",
        "source_record_id": str(record.get("evidence_id") or ""),
        "evidence_owner_ticker": owner,
        "subject_ticker": plan.subject_ticker,
        "relationship_direction": relationship,
        "source_role": source_role,
        "subject_mention_state": (
            "not_applicable_subject_self"
            if owner == plan.subject_ticker
            else (
                "direct_subject_mention"
                if subject_mentioned
                else "no_direct_subject_mention"
            )
        ),
        "source_type": source_type,
        "source_tier": str(record.get("source_tier") or ""),
        "publication_date": str(record.get("publication_date") or ""),
        "period_end": temporal["reporting_period_end"],
        "fiscal_year": temporal["reporting_fiscal_year"],
        "temporal_binding": temporal,
        "section": str(record.get("section") or ""),
        "subsection": str(record.get("subsection") or ""),
        "source_url": str(record.get("source_url") or ""),
        "matched_terms": matched[:12],
        "raw_bm25_score": round(raw_score, 6),
        "final_score": round(final_score, 6),
        "selection_reasons_zh": [
            f"披露主体 {owner} 在该 Evidence Slot 允许的 owner 范围内。",
            f"发布日期 {record.get('publication_date')} 不晚于研究截至日 {lane.publication_date_lte}。",
            f"命中查询语义：{'、'.join(matched[:8])}。",
        ],
        "business_boundary_zh": boundary,
        "excerpt": text[: kernel.budgets.excerpt_characters],
        "candidate_digest": canonical_digest(
            {
                "lane_id": lane.lane_id,
                "source_record_id": str(record.get("evidence_id") or ""),
                "score": round(final_score, 6),
            }
        ),
    }


def _reporting_temporal_projection(record: Mapping[str, Any]) -> dict[str, Any]:
    """Project the issuer reporting period without confusing it with filing dates.

    Legacy 8-K earnings objects retain the SEC current-report date at the record
    surface while preserving the earnings period in source-bound metadata.  Product
    retrieval must filter on the latter when it is present.  The original values are
    retained so the normalization remains auditable instead of silently rewriting
    source lineage.
    """

    metadata = record.get("metadata")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    source_fiscal_year = record.get("fiscal_year")
    reported_fiscal_year = metadata.get("reported_fiscal_year")
    try:
        reporting_fiscal_year = int(
            reported_fiscal_year
            if reported_fiscal_year not in (None, "")
            else source_fiscal_year
        )
    except (TypeError, ValueError):
        reporting_fiscal_year = None

    source_period_end = str(record.get("period_end") or "").strip()
    reported_period_end = str(metadata.get("reported_period_end") or "").strip()
    reporting_period_end = (
        reported_period_end
        if _date_or_none(reported_period_end) is not None
        else source_period_end
    )
    return {
        "reporting_fiscal_year": reporting_fiscal_year,
        "reporting_fiscal_year_source": (
            "metadata.reported_fiscal_year"
            if reported_fiscal_year not in (None, "")
            else "source_record.fiscal_year"
        ),
        "reporting_period_end": reporting_period_end,
        "reporting_period_end_source": (
            "metadata.reported_period_end"
            if reported_period_end and _date_or_none(reported_period_end) is not None
            else "source_record.period_end"
        ),
        "source_record_fiscal_year": source_fiscal_year,
        "source_record_period_end": source_period_end,
    }


def _source_role_for_record(
    record: Mapping[str, Any],
    plan: QueryFacetPlan,
) -> str:
    owner = str(record.get("ticker") or "").strip().upper()
    if owner != plan.subject_ticker:
        return "related_entity_context"
    source_type = str(record.get("source_type") or "").strip().upper()
    return _ROLE_BY_SOURCE_TYPE.get(source_type, "other_source")


def _relationship_for_owner(
    kernel: FinancialResearchKernel,
    case_key: str,
    owner_ticker: str,
) -> str:
    for entity in kernel.cases[case_key].related_entities:
        if entity.ticker == owner_ticker:
            return entity.relationship_direction
    return "relationship_unknown"


def _date_or_none(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value or ""))
    except ValueError:
        return None


def _candidate_exclusion_reason(
    record: Mapping[str, Any],
    lane: QueryLane,
) -> str | None:
    ticker = str(record.get("ticker") or "").strip().upper()
    if ticker not in set(lane.evidence_owner_tickers):
        return "outside_evidence_owner_scope"
    source_type = str(record.get("source_type") or "").strip().upper()
    if source_type not in set(lane.source_types):
        return "source_type_not_allowed"
    publication = _date_or_none(record.get("publication_date"))
    if publication is None:
        return "publication_date_missing_or_invalid"
    if publication > date.fromisoformat(lane.publication_date_lte):
        return "published_after_research_as_of"
    return _boilerplate_reason(record)


def _document_key(record: Mapping[str, Any]) -> str:
    metadata = record.get("metadata")
    if isinstance(metadata, Mapping) and metadata.get("accession_number"):
        return str(metadata["accession_number"])
    return str(record.get("source_url") or record.get("evidence_id") or "")


def _record_equivalent_ids(record: Mapping[str, Any]) -> set[str]:
    identifiers = {str(record.get("evidence_id") or "").strip()}
    metadata = record.get("metadata")
    if isinstance(metadata, Mapping):
        aliases = metadata.get("legacy_source_record_ids")
        if isinstance(aliases, list):
            identifiers.update(str(value).strip() for value in aliases)
    return {value for value in identifiers if value}


def _boilerplate_reason(record: Mapping[str, Any]) -> str | None:
    heading = " ".join(
        str(record.get(key) or "") for key in ("section", "subsection")
    ).casefold()
    text = re.sub(r"\s+", " ", str(record.get("text") or "")).strip().casefold()
    if len(text) < 100:
        return "too_short_for_research_candidate"
    if any(value in heading for value in _BOILERPLATE_HEADINGS):
        return "boilerplate_or_navigation"
    phrase_hits = sum(value in text for value in _BOILERPLATE_PHRASES)
    if phrase_hits >= 2 and len(text) < 1600:
        return "boilerplate_or_navigation"
    return None


__all__ = [
    "CandidateCorpus",
    "RETRIEVAL_RESULT_SCHEMA_VERSION",
    "load_candidate_corpus",
    "retrieve_query_plan",
]
