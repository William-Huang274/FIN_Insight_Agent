from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from rank_bm25 import BM25Okapi

from .query_plan import canonical_digest
from .text import evidence_search_text, tokenize


RANKING_QREL_SCHEMA_VERSION = "fin_ia_s1c_requalified_ranking_qrels_v1_0"
RANKING_RESULT_SCHEMA_VERSION = "fin_ia_s1c_same_object_ranking_comparison_v1_0"

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
_QUERY_STOPWORDS = {
    "the",
    "and",
    "or",
    "of",
    "to",
    "for",
    "in",
    "on",
    "about",
    "what",
    "did",
    "own",
    "evidence",
    "owner",
    "disclosed",
    "results",
    "fy2026",
    "fy2027",
    "2026",
    "2027",
}


class RankingComparisonError(ValueError):
    """Raised when a same-object ranking comparison cannot fail closed."""


@dataclass(frozen=True)
class RankingQuery:
    qrel_id: str
    source_qrel_digest: str
    case_key: str
    subject_ticker: str
    evidence_slot_id: str
    evidence_owner_ticker: str
    relationship_direction: str
    sparse_query_texts: tuple[str, ...]
    semantic_query_texts: tuple[str, ...]
    publication_date_lte: str
    reporting_fiscal_years: tuple[int, ...]
    form_types: tuple[str, ...]
    source_tiers: tuple[str, ...]
    target_current_source_record_ids: tuple[str, ...]
    target_mapping_state: str
    relevance_grade: int

    def query_text(self, route: str) -> str:
        values = (
            self.semantic_query_texts
            if route == "dense_bge_m3"
            else self.sparse_query_texts
        )
        return "\n".join(values)


def load_ranking_queries(payload: Mapping[str, Any]) -> tuple[RankingQuery, ...]:
    """Load evaluation-only labels without exposing them to candidate scoring."""

    if payload.get("schema_version") != RANKING_QREL_SCHEMA_VERSION:
        raise RankingComparisonError("s1c_qrel_schema_invalid")
    policy = payload.get("policy")
    if not (
        isinstance(policy, Mapping)
        and policy.get("labels_joined_after_candidate_generation") is True
        and policy.get("target_ids_forbidden_from_query_text") is True
        and policy.get("candidate_is_not_evidence") is True
    ):
        raise RankingComparisonError("s1c_qrel_policy_invalid")
    rows = payload.get("qrels")
    if not isinstance(rows, list) or not rows:
        raise RankingComparisonError("s1c_qrels_missing")
    queries: list[RankingQuery] = []
    for raw in rows:
        if not isinstance(raw, Mapping):
            raise RankingComparisonError("s1c_qrel_row_invalid")
        query = RankingQuery(
            qrel_id=str(raw.get("qrel_id") or ""),
            source_qrel_digest=str(raw.get("source_qrel_digest") or ""),
            case_key=str(raw.get("case_key") or "").upper(),
            subject_ticker=str(raw.get("subject_ticker") or "").upper(),
            evidence_slot_id=str(raw.get("evidence_slot_id") or ""),
            evidence_owner_ticker=str(
                raw.get("evidence_owner_ticker") or ""
            ).upper(),
            relationship_direction=str(raw.get("relationship_direction") or ""),
            sparse_query_texts=_strings(raw.get("sparse_query_texts")),
            semantic_query_texts=_strings(raw.get("semantic_query_texts")),
            publication_date_lte=str(raw.get("publication_date_lte") or ""),
            reporting_fiscal_years=tuple(
                int(value) for value in raw.get("reporting_fiscal_years") or ()
            ),
            form_types=tuple(
                str(value).upper() for value in raw.get("form_types") or ()
            ),
            source_tiers=_strings(raw.get("source_tiers")),
            target_current_source_record_ids=_strings(
                raw.get("target_current_source_record_ids"), allow_empty=True
            ),
            target_mapping_state=str(raw.get("target_mapping_state") or ""),
            relevance_grade=int(raw.get("relevance_grade") or 0),
        )
        if not (
            query.qrel_id
            and query.source_qrel_digest
            and query.case_key
            and query.subject_ticker
            and query.evidence_slot_id
            and query.evidence_owner_ticker
            and query.relationship_direction
            and query.publication_date_lte
            and query.form_types
            and query.source_tiers
            and query.relevance_grade in {1, 2, 3}
            and query.target_mapping_state in {"mapped_current_child", "typed_target_gap"}
        ):
            raise RankingComparisonError("s1c_qrel_row_incomplete")
        date.fromisoformat(query.publication_date_lte)
        joined_query = query.query_text("sparse_bm25").casefold() + "\n" + query.query_text(
            "dense_bge_m3"
        ).casefold()
        if any(
            target.casefold() in joined_query
            for target in query.target_current_source_record_ids
        ):
            raise RankingComparisonError("s1c_gold_target_leaked_into_query")
        queries.append(query)
    if len({query.qrel_id for query in queries}) != len(queries):
        raise RankingComparisonError("s1c_qrel_id_duplicate")
    return tuple(queries)


def build_document_text(record: Mapping[str, Any]) -> str:
    """One provider-neutral text projection shared by every ranking route."""

    return evidence_search_text(dict(record))


def eligible_records(
    records: Sequence[Mapping[str, Any]],
    query: RankingQuery,
) -> tuple[list[Mapping[str, Any]], dict[str, int]]:
    eligible: list[Mapping[str, Any]] = []
    excluded: Counter[str] = Counter()
    as_of = date.fromisoformat(query.publication_date_lte)
    for record in records:
        reason = _exclusion_reason(record, query, as_of)
        if reason:
            excluded[reason] += 1
        else:
            eligible.append(record)
    return eligible, dict(sorted(excluded.items()))


def rank_sparse(
    records: Sequence[Mapping[str, Any]],
    query: RankingQuery,
) -> list[dict[str, Any]]:
    eligible, _ = eligible_records(records, query)
    query_tokens = tokenize(query.query_text("sparse_bm25"))
    if not eligible or not query_tokens:
        return []
    tokenized = [tokenize(build_document_text(record)) for record in eligible]
    index = BM25Okapi(tokenized)
    scores = index.get_scores(query_tokens)
    rows = [
        _score_row(record, float(score), matched=_matched_terms(query_tokens, tokens))
        for record, tokens, score in zip(eligible, tokenized, scores)
    ]
    return _stable_rank(rows, score_key="score")


def rank_dense(
    records: Sequence[Mapping[str, Any]],
    query: RankingQuery,
    *,
    embedding_by_record_id: Mapping[str, np.ndarray],
    query_embedding: np.ndarray,
) -> list[dict[str, Any]]:
    eligible, _ = eligible_records(records, query)
    rows: list[dict[str, Any]] = []
    for record in eligible:
        record_id = str(record.get("evidence_id") or "")
        embedding = embedding_by_record_id.get(record_id)
        if embedding is None:
            raise RankingComparisonError(f"s1c_dense_embedding_missing:{record_id}")
        score = float(np.dot(query_embedding, embedding))
        rows.append(_score_row(record, score, matched=[]))
    return _stable_rank(rows, score_key="score")


def reciprocal_rank_fusion(
    sparse: Sequence[Mapping[str, Any]],
    dense: Sequence[Mapping[str, Any]],
    *,
    rrf_k: int = 60,
) -> list[dict[str, Any]]:
    if rrf_k <= 0:
        raise RankingComparisonError("s1c_rrf_k_invalid")
    by_id: dict[str, dict[str, Any]] = {}
    for route, rows in (("sparse_rank", sparse), ("dense_rank", dense)):
        for rank, raw in enumerate(rows, start=1):
            record_id = str(raw["source_record_id"])
            row = by_id.setdefault(record_id, dict(raw))
            row[route] = rank
            row.setdefault("sparse_rank", None)
            row.setdefault("dense_rank", None)
    for row in by_id.values():
        row["score"] = sum(
            1.0 / (rrf_k + int(row[key]))
            for key in ("sparse_rank", "dense_rank")
            if row.get(key) is not None
        )
    return _stable_rank(list(by_id.values()), score_key="score")


def deterministic_financial_rerank(
    fused: Sequence[Mapping[str, Any]],
    query: RankingQuery,
    records_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Apply qrel-free financial role guards to a fused candidate list.

    This is deliberately not called a neural reranker. It consumes only query
    contract fields and candidate content; target identities and relevance labels
    are not accepted by the function.
    """

    rows: list[dict[str, Any]] = []
    for raw in fused:
        record_id = str(raw["source_record_id"])
        record = records_by_id[record_id]
        signal, reasons = _financial_role_signal(record, query)
        row = dict(raw)
        row["fusion_score"] = float(raw["score"])
        row["business_role_adjustment"] = signal
        row["business_role_reasons"] = reasons
        row["score"] = float(raw["score"]) + signal
        rows.append(row)
    return _stable_rank(rows, score_key="score")


def compare_ranking_routes(
    records: Sequence[Mapping[str, Any]],
    queries: Sequence[RankingQuery],
    *,
    embedding_by_record_id: Mapping[str, np.ndarray],
    query_embeddings: Mapping[str, np.ndarray],
    top_k: int = 10,
    candidate_pool: int = 24,
    rrf_k: int = 60,
) -> dict[str, Any]:
    if top_k <= 0 or candidate_pool < top_k:
        raise RankingComparisonError("s1c_ranking_budget_invalid")
    records_by_id = {
        str(record.get("evidence_id") or ""): record for record in records
    }
    query_results: list[dict[str, Any]] = []
    for query in queries:
        eligible, exclusions = eligible_records(records, query)
        sparse = rank_sparse(records, query)
        dense = rank_dense(
            records,
            query,
            embedding_by_record_id=embedding_by_record_id,
            query_embedding=query_embeddings[query.qrel_id],
        )
        fusion = reciprocal_rank_fusion(sparse, dense, rrf_k=rrf_k)
        reranked = deterministic_financial_rerank(
            fusion[:candidate_pool], query, records_by_id
        )
        route_rows = {
            "sparse_bm25": sparse[:candidate_pool],
            "dense_bge_m3": dense[:candidate_pool],
            "fusion_rrf_1_1": fusion[:candidate_pool],
            "typed_financial_rerank": reranked[:candidate_pool],
        }
        routes: dict[str, Any] = {}
        for route_id, rows in route_rows.items():
            rank = _target_rank(rows, query.target_current_source_record_ids)
            routes[route_id] = {
                "target_rank": rank,
                "target_in_top_k": rank is not None and rank <= top_k,
                "candidates": [
                    _candidate_projection(
                        row,
                        records_by_id[str(row["source_record_id"])],
                        rank=index,
                        query=query,
                    )
                    for index, row in enumerate(rows[:top_k], start=1)
                ],
            }
        query_results.append(
            {
                "qrel_id": query.qrel_id,
                "case_key": query.case_key,
                "subject_ticker": query.subject_ticker,
                "evidence_slot_id": query.evidence_slot_id,
                "evidence_owner_ticker": query.evidence_owner_ticker,
                "relationship_direction": query.relationship_direction,
                "target_mapping_state": query.target_mapping_state,
                "target_current_source_record_ids": list(
                    query.target_current_source_record_ids
                ),
                "relevance_grade": query.relevance_grade,
                "eligible_records": len(eligible),
                "exclusion_counts": exclusions,
                "labels_joined_after_candidate_generation": True,
                "routes": routes,
            }
        )
    route_metrics = {
        route_id: _route_metrics(query_results, route_id, top_k)
        for route_id in (
            "sparse_bm25",
            "dense_bge_m3",
            "fusion_rrf_1_1",
            "typed_financial_rerank",
        )
    }
    unsigned = {
        "schema_version": RANKING_RESULT_SCHEMA_VERSION,
        "candidate_state": "candidate_not_evidence",
        "same_object_population_count": len(records),
        "query_count": len(query_results),
        "top_k": top_k,
        "candidate_pool": candidate_pool,
        "rrf": {"weights": {"sparse": 1, "dense": 1}, "k": rrf_k},
        "routes": route_metrics,
        "queries": query_results,
    }
    return {**unsigned, "comparison_digest": canonical_digest(unsigned)}


def sanitized_workbench_projection(result: Mapping[str, Any]) -> dict[str, Any]:
    """Remove every qrel/target identity before a product consumer sees the eval."""

    cases: dict[str, dict[str, Any]] = {}
    for raw in result.get("queries") or ():
        case_key = str(raw["case_key"])
        case = cases.setdefault(case_key, {"case_key": case_key, "queries": []})
        if len(case["queries"]) >= 3:
            continue
        route_projection = {}
        for route_id, route in raw["routes"].items():
            candidates = []
            for candidate in route["candidates"][:1]:
                clean = dict(candidate)
                clean.pop("business_diagnostic_code", None)
                candidates.append(clean)
            route_projection[route_id] = {"candidates": candidates}
        case["queries"].append(
            {
                "query_id": (
                    f"s1c_{case_key.lower()}_query_"
                    f"{len(case['queries']) + 1:02d}"
                ),
                "evidence_slot_id": str(raw["evidence_slot_id"]),
                "evidence_owner_ticker": str(raw["evidence_owner_ticker"]),
                "routes": route_projection,
            }
        )
    body = {
        "schema_version": "fin_ia_s1c_ranking_workbench_projection_v1_0",
        "candidate_state": "candidate_not_evidence",
        "same_object_population_count": int(
            result["same_object_population_count"]
        ),
        "route_summaries": {
            route_id: {
                key: value
                for key, value in metrics.items()
                if key not in {"matched_qrel_ids", "missed_qrel_ids"}
            }
            for route_id, metrics in result.get("routes", {}).items()
        },
        "cases": [cases[key] for key in sorted(cases)],
        "known_boundary": (
            "This is a bounded sanitized ranking diagnostic showing three queries "
            "per case and one candidate per route over frozen candidates. "
            "It contains no qrel target identity, does not promote Evidence and "
            "does not establish S1 or product acceptance."
        ),
    }
    return {**body, "projection_digest": canonical_digest(body)}


def _strings(value: object, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise RankingComparisonError("s1c_string_list_invalid")
    output = tuple(str(item).strip() for item in value if str(item).strip())
    if not output and not allow_empty:
        raise RankingComparisonError("s1c_string_list_empty")
    return output


def _date(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value or ""))
    except ValueError:
        return None


def _exclusion_reason(
    record: Mapping[str, Any], query: RankingQuery, as_of: date
) -> str | None:
    if str(record.get("ticker") or "").upper() != query.evidence_owner_ticker:
        return "outside_evidence_owner_scope"
    if str(record.get("source_type") or "").upper() not in set(query.form_types):
        return "source_type_not_allowed"
    source_tier = str(record.get("source_tier") or "")
    if source_tier not in set(query.source_tiers):
        return "source_tier_not_allowed"
    publication = _date(record.get("publication_date"))
    if publication is None:
        return "publication_date_missing_or_invalid"
    if publication > as_of:
        return "published_after_research_as_of"
    fiscal_year = record.get("fiscal_year")
    if (
        query.reporting_fiscal_years
        and fiscal_year not in (None, "")
        and int(fiscal_year) not in set(query.reporting_fiscal_years)
    ):
        return "reporting_period_outside_query_scope"
    heading = " ".join(
        str(record.get(key) or "") for key in ("section", "subsection")
    ).casefold()
    text = re.sub(r"\s+", " ", str(record.get("text") or "")).strip().casefold()
    if len(text) < 100:
        return "too_short_for_research_candidate"
    if any(value in heading for value in _BOILERPLATE_HEADINGS):
        return "boilerplate_or_navigation"
    if (
        sum(value in text for value in _BOILERPLATE_PHRASES) >= 2
        and len(text) < 1600
    ):
        return "boilerplate_or_navigation"
    return None


def _matched_terms(query_tokens: Iterable[str], document_tokens: Iterable[str]) -> list[str]:
    query_set = {token for token in query_tokens if token not in _QUERY_STOPWORDS}
    return sorted(query_set & set(document_tokens))[:20]


def _score_row(
    record: Mapping[str, Any],
    score: float,
    *,
    matched: list[str],
) -> dict[str, Any]:
    return {
        "source_record_id": str(record.get("evidence_id") or ""),
        "score": score,
        "matched_terms": matched,
    }


def _stable_rank(rows: list[dict[str, Any]], *, score_key: str) -> list[dict[str, Any]]:
    rows.sort(
        key=lambda row: (
            -float(row[score_key]),
            str(row.get("source_record_id") or ""),
        )
    )
    return rows


def _financial_role_signal(
    record: Mapping[str, Any], query: RankingQuery
) -> tuple[float, list[str]]:
    text = build_document_text(record).casefold()
    heading = " ".join(
        str(record.get(key) or "") for key in ("section", "subsection")
    ).casefold()
    reasons: list[str] = []
    adjustment = 0.0
    slot_terms = {
        "customer_demand_and_deployment_validation": (
            "demand",
            "deployment",
            "capital expenditure",
            "capacity expansion",
            "orders",
            "backlog",
            "ai infrastructure",
        ),
        "issuer_results_and_management_commentary": (
            "revenue",
            "gross margin",
            "earnings",
            "orders",
            "guidance",
            "results",
        ),
        "regulatory_risk_and_financial_reconciliation": (
            "inventory",
            "purchase commitments",
            "working capital",
            "cash flow",
            "revenue recognition",
            "export controls",
            "regulatory",
        ),
        "supply_chain_capacity_and_counterevidence": (
            "capacity",
            "supply",
            "ramp",
            "yield",
            "production",
            "utilization",
            "hbm",
            "cowos",
        ),
    }.get(query.evidence_slot_id, ())
    hits = sum(term in text for term in slot_terms)
    if hits:
        adjustment += min(0.018, hits * 0.003)
        reasons.append(f"slot_mechanism_hits={hits}")
    else:
        adjustment -= 0.018
        reasons.append("slot_mechanism_missing")
    if any(value in heading for value in ("management's discussion", "results")):
        adjustment += 0.004
        reasons.append("management_or_results_heading")
    risk_heading = "risk factor" in heading
    if risk_heading and query.evidence_slot_id in {
        "customer_demand_and_deployment_validation",
        "issuer_results_and_management_commentary",
    }:
        adjustment -= 0.02
        reasons.append("risk_text_not_direct_demand_or_results")
    fiscal_year = record.get("fiscal_year")
    if fiscal_year not in (None, "") and int(fiscal_year) in set(
        query.reporting_fiscal_years
    ):
        adjustment += 0.004
        reasons.append("reporting_period_match")
    return adjustment, reasons


def _target_rank(
    rows: Sequence[Mapping[str, Any]], target_ids: Sequence[str]
) -> int | None:
    target_set = set(target_ids)
    if not target_set:
        return None
    for rank, row in enumerate(rows, start=1):
        if str(row["source_record_id"]) in target_set:
            return rank
    return None


def _candidate_projection(
    score_row: Mapping[str, Any],
    record: Mapping[str, Any],
    *,
    rank: int,
    query: RankingQuery,
) -> dict[str, Any]:
    text = re.sub(r"\s+", " ", str(record.get("text") or "")).strip()
    return {
        "candidate_state": "candidate_not_evidence",
        "rank": rank,
        "source_record_id": str(record.get("evidence_id") or ""),
        "evidence_owner_ticker": str(record.get("ticker") or ""),
        "source_type": str(record.get("source_type") or ""),
        "source_tier": str(record.get("source_tier") or ""),
        "publication_date": str(record.get("publication_date") or ""),
        "fiscal_year": record.get("fiscal_year"),
        "period_end": str(record.get("period_end") or ""),
        "section": str(record.get("section") or ""),
        "subsection": str(record.get("subsection") or ""),
        "source_url": str(record.get("source_url") or ""),
        "score": round(float(score_row["score"]), 8),
        "matched_terms": list(score_row.get("matched_terms") or ()),
        "business_role_reasons": list(
            score_row.get("business_role_reasons") or ()
        ),
        "business_diagnostic_code": _business_diagnostic_code(record, query),
        "excerpt": text[:700],
    }


def _business_diagnostic_code(
    record: Mapping[str, Any], query: RankingQuery
) -> str:
    owner = str(record.get("ticker") or "").upper()
    if owner != query.evidence_owner_ticker:
        return "wrong_evidence_owner"
    publication = _date(record.get("publication_date"))
    if publication is None or publication > date.fromisoformat(
        query.publication_date_lte
    ):
        return "wrong_or_missing_period"
    text = build_document_text(record).casefold()
    heading = " ".join(
        str(record.get(key) or "") for key in ("section", "subsection")
    ).casefold()
    if query.evidence_slot_id == "customer_demand_and_deployment_validation":
        if not any(
            term in text
            for term in (
                "demand",
                "deployment",
                "capital expenditure",
                "orders",
                "backlog",
                "capacity",
            )
        ):
            return "topic_co_mention_without_demand_mechanism"
    elif query.evidence_slot_id == "issuer_results_and_management_commentary":
        if "risk factor" in heading:
            return "risk_disclosure_substituted_for_results"
        if not any(
            term in text
            for term in ("revenue", "margin", "earnings", "orders", "guidance")
        ):
            return "generic_company_text_substituted_for_results"
    elif query.evidence_slot_id == "regulatory_risk_and_financial_reconciliation":
        if "risk factor" in heading and not any(
            term in text
            for term in (
                "inventory",
                "purchase commitment",
                "working capital",
                "cash flow",
                "revenue recognition",
            )
        ):
            return "risk_disclosure_substituted_for_financial_mechanism"
    elif query.evidence_slot_id == "supply_chain_capacity_and_counterevidence":
        if not any(
            term in text
            for term in (
                "capacity",
                "supply",
                "ramp",
                "yield",
                "production",
                "utilization",
                "hbm",
                "cowos",
            )
        ):
            return "topic_co_mention_without_supply_mechanism"
    return "no_automatic_business_error_detected"


def _route_metrics(
    query_results: Sequence[Mapping[str, Any]], route_id: str, top_k: int
) -> dict[str, Any]:
    total = len(query_results)
    mapped = [
        row for row in query_results if row["target_mapping_state"] == "mapped_current_child"
    ]
    matched = [
        row
        for row in mapped
        if row["routes"][route_id]["target_in_top_k"] is True
    ]
    reciprocal = [
        1.0 / int(row["routes"][route_id]["target_rank"])
        if row["routes"][route_id]["target_rank"] is not None
        else 0.0
        for row in mapped
    ]
    errors = Counter(
        candidate["business_diagnostic_code"]
        for row in query_results
        for candidate in row["routes"][route_id]["candidates"][:3]
        if candidate["business_diagnostic_code"]
        != "no_automatic_business_error_detected"
    )
    return {
        "qrel_count": total,
        "mapped_current_target_count": len(mapped),
        "typed_target_gap_count": total - len(mapped),
        f"recall_at_{top_k}_all_qrels": round(len(matched) / total, 6),
        f"recall_at_{top_k}_mapped_targets": round(
            len(matched) / len(mapped), 6
        )
        if mapped
        else 0.0,
        "mrr_mapped_targets": round(sum(reciprocal) / len(mapped), 6)
        if mapped
        else 0.0,
        "matched_qrel_ids": [str(row["qrel_id"]) for row in matched],
        "missed_qrel_ids": [
            str(row["qrel_id"])
            for row in mapped
            if row not in matched
        ],
        "automatic_business_error_counts_in_top3": dict(sorted(errors.items())),
    }


__all__ = [
    "RANKING_QREL_SCHEMA_VERSION",
    "RANKING_RESULT_SCHEMA_VERSION",
    "RankingComparisonError",
    "RankingQuery",
    "build_document_text",
    "compare_ranking_routes",
    "deterministic_financial_rerank",
    "eligible_records",
    "load_ranking_queries",
    "rank_dense",
    "rank_sparse",
    "reciprocal_rank_fusion",
    "sanitized_workbench_projection",
]
