from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from sec_agent.canonical_runtime.models import canonical_digest


RUN_SCOPE = "S1_INTERNAL_CANDIDATE_CEILING_AND_QRELS_GATE"
CORPUS_REFRESH_SCOPE = "S1_INTERNAL_CURRENT_CORPUS_AND_INDEX_REFRESH"
ALLOWED_RUN_SCOPES = {RUN_SCOPE, CORPUS_REFRESH_SCOPE}
EXECUTED_ROUTES = (
    "internal_sql_exact",
    "internal_object_bm25",
    "internal_bm25",
    "internal_relationship_graph",
)
QUALIFICATION_ONLY_ROUTES = ("internal_milvus_dense",)


class S1InternalCandidateCeilingError(RuntimeError):
    pass


def _normalized_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise S1InternalCandidateCeilingError(
            f"internal_candidate_ceiling_json_invalid:{path}"
        ) from exc
    if not isinstance(value, dict):
        raise S1InternalCandidateCeilingError(
            f"internal_candidate_ceiling_json_object_required:{path}"
        )
    return value


def load_internal_candidate_ceiling_policy(
    path: str | Path,
    *,
    repo_root: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    policy = _read_json(Path(path))
    if policy.get("run_scope") not in ALLOWED_RUN_SCOPES:
        raise S1InternalCandidateCeilingError(
            "internal_candidate_ceiling_policy_scope_invalid"
        )
    refs = policy.get("immutable_inputs")
    if not isinstance(refs, dict):
        raise S1InternalCandidateCeilingError(
            "internal_candidate_ceiling_policy_inputs_missing"
        )
    for stem in (
        "integration_proof",
        "progression_plan",
        "retrieval_config",
        "milvus_runtime",
    ):
        ref = str(refs.get(f"{stem}_ref") or "")
        supplied = str(refs.get(f"{stem}_sha256") or "")
        target = root / ref
        if not ref or not target.is_file() or _normalized_sha256(target) != supplied:
            raise S1InternalCandidateCeilingError(
                f"internal_candidate_ceiling_policy_binding_invalid:{stem}"
            )
    for ordinal, manifest in enumerate(
        _as_list((policy.get("local_assets") or {}).get("document_lineage_manifests"))
    ):
        if not isinstance(manifest, Mapping):
            raise S1InternalCandidateCeilingError(
                f"internal_candidate_ceiling_lineage_manifest_invalid:{ordinal}"
            )
        ref = str(manifest.get("path") or "")
        supplied = str(manifest.get("sha256") or "")
        target = root / ref
        if not ref or not target.is_file() or _normalized_sha256(target) != supplied:
            raise S1InternalCandidateCeilingError(
                f"internal_candidate_ceiling_lineage_manifest_binding_invalid:{ordinal}"
            )
    if any(int(policy.get("hard_boundaries", {}).get(name, -1)) != 0 for name in (
        "network",
        "provider",
        "model",
        "document_fetch",
        "embedding",
        "rerank",
        "evidence_promotion",
    )):
        raise S1InternalCandidateCeilingError(
            "internal_candidate_ceiling_external_or_ranking_authority_invalid"
        )
    return policy


def load_bound_integration_proof(
    policy: Mapping[str, Any], *, repo_root: str | Path
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    refs = policy["immutable_inputs"]
    proof = _read_json(root / str(refs["integration_proof_ref"]))
    body = dict(proof)
    supplied = str(body.pop("proof_digest", ""))
    if supplied != canonical_digest(body):
        raise S1InternalCandidateCeilingError(
            "internal_candidate_ceiling_integration_proof_digest_invalid"
        )
    if (
        proof.get("status") != "zero_call_engineering_pass"
        or int(proof.get("bilingual_bundle_count") or 0) != 18
        or int(proof.get("physical_request_count") or 0) != 90
        or proof.get("stage_acceptance", {}).get("internal_query_facet_projection")
        is not True
        or proof.get("stage_acceptance", {}).get("internal_route_execution")
        is not False
    ):
        raise S1InternalCandidateCeilingError(
            "internal_candidate_ceiling_integration_proof_state_invalid"
        )
    return proof


def _ro_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        f"file:{path.resolve().as_posix()}?mode=ro", uri=True
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def _clip(value: Any, limit: int = 600) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]


def _without_elapsed(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _without_elapsed(item)
            for key, item in value.items()
            if str(key) != "elapsed_ms"
        }
    if isinstance(value, list):
        return [_without_elapsed(item) for item in value]
    if isinstance(value, tuple):
        return [_without_elapsed(item) for item in value]
    return value


def canonical_observation_digest(value: Mapping[str, Any]) -> str:
    body = dict(value)
    body.pop("result_digest", None)
    return canonical_digest(_without_elapsed(body))


def milvus_lite_storage_exists(path: str | Path) -> bool:
    target = Path(path)
    return target.is_file() or target.is_dir()


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [] if value in (None, "") else [value]


def _candidate(
    *,
    request: Mapping[str, Any],
    source_key: str,
    route_rank: int,
    score: float | None,
    query_indexes: Sequence[int],
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    body = {
        "request_id": str(request["request_id"]),
        "request_digest": str(request["request_digest"]),
        "bundle_id": str(request["bundle_id"]),
        "case_key": str(request["case_key"]),
        "evidence_slot_id": str(request["evidence_slot_id"]),
        "subject_entity_key": str(request["subject_entity_key"]),
        "subject_ticker": str(request["subject_ticker"]),
        "evidence_owner_entity_key": str(request["evidence_owner_entity_key"]),
        "evidence_owner_ticker": str(request["evidence_owner_ticker"]),
        "relationship_direction": str(request["relationship_direction"]),
        "route_id": str(request["route_id"]),
        "source_key": source_key,
        "route_rank": int(route_rank),
        "score": None if score is None else round(float(score), 8),
        "matched_query_indexes": sorted({int(item) for item in query_indexes}),
        "candidate_state": "candidate_only_not_evidence",
        **dict(payload),
    }
    digest = canonical_digest(body)
    return {
        "candidate_id": f"internal_candidate_{digest[:24]}",
        "candidate_digest": digest,
        **body,
    }


def deterministic_round_robin_dedupe(
    query_results: Sequence[Sequence[Mapping[str, Any]]],
    *,
    key_fn: Callable[[Mapping[str, Any]], str],
    budget: int,
) -> list[tuple[Mapping[str, Any], tuple[int, ...]]]:
    if budget <= 0:
        return []
    positions = [0 for _ in query_results]
    selected: list[Mapping[str, Any]] = []
    indexes_by_key: dict[str, set[int]] = {}
    row_by_key: dict[str, Mapping[str, Any]] = {}
    while len(selected) < budget:
        progressed = False
        for query_index, rows in enumerate(query_results):
            while positions[query_index] < len(rows):
                row = rows[positions[query_index]]
                positions[query_index] += 1
                progressed = True
                key = key_fn(row)
                if not key:
                    continue
                indexes_by_key.setdefault(key, set()).add(query_index)
                if key in row_by_key:
                    continue
                row_by_key[key] = row
                selected.append(row)
                break
            if len(selected) >= budget:
                break
        if not progressed:
            break
    for query_index, rows in enumerate(query_results):
        for row in rows:
            key = key_fn(row)
            if key in row_by_key:
                indexes_by_key[key].add(query_index)
    return [
        (row, tuple(sorted(indexes_by_key[key_fn(row)]))) for row in selected
    ]


def _route_gap(
    request: Mapping[str, Any],
    *,
    code: str,
    detail: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    body = {
        "request_id": str(request["request_id"]),
        "bundle_id": str(request["bundle_id"]),
        "case_key": str(request["case_key"]),
        "evidence_slot_id": str(request["evidence_slot_id"]),
        "evidence_owner_ticker": str(request["evidence_owner_ticker"]),
        "route_id": str(request["route_id"]),
        "gap_code": code,
        "detail": dict(detail or {}),
        "source_exhaustion_proven": False,
        "candidate_state": "typed_gap_not_evidence",
    }
    return {**body, "gap_digest": canonical_digest(body)}


def execute_sql_exact_request(
    request: Mapping[str, Any], *, database: Path
) -> dict[str, Any]:
    filters = dict(request.get("typed_filters") or {})
    ticker = str(filters.get("ticker") or request["evidence_owner_ticker"])
    years = [
        int(item)
        for item in _as_list(
            filters.get("reporting_fiscal_years", filters.get("fiscal_years"))
        )
    ]
    metrics = [str(item) for item in _as_list(filters.get("metric_families"))]
    budget = int(request.get("candidate_budget") or 12)
    started = time.perf_counter()
    with _ro_connection(database) as connection:
        clauses = [
            "ticker = ?",
            "can_enter_evidence_bundle = 1",
            "exact_value_authority = 1",
        ]
        params: list[Any] = [ticker]
        if years:
            clauses.append(
                f"CAST(NULLIF(fiscal_year, '') AS INTEGER) IN ({','.join('?' for _ in years)})"
            )
            params.extend(years)
        if metrics:
            clauses.append(f"metric_family IN ({','.join('?' for _ in metrics)})")
            params.extend(metrics)
        as_of = str(filters.get("publication_date_on_or_before") or "")
        if as_of:
            clauses.append("(published_at = '' OR published_at IS NULL OR published_at <= ?)")
            params.append(as_of)
        rows = connection.execute(
            "SELECT gold_row_id,ticker,metric_family,metric_name,value,unit,period,"
            "fiscal_year,authority_mode,claim_boundary,citation_url,citation_span,"
            "evidence_ref,source_url,published_at,period_role,period_start,period_end "
            "FROM gold_fact_signal_mart WHERE "
            + " AND ".join(clauses)
            + " ORDER BY CAST(NULLIF(fiscal_year, '') AS INTEGER) DESC, "
            "CASE WHEN published_at = '' OR published_at IS NULL THEN 1 ELSE 0 END, "
            "published_at DESC, metric_family, gold_row_id LIMIT ?",
            [*params, budget],
        ).fetchall()
        latest = connection.execute(
            "SELECT MAX(CAST(NULLIF(fiscal_year, '') AS INTEGER)) "
            "FROM gold_fact_signal_mart WHERE ticker = ? AND can_enter_evidence_bundle = 1",
            (ticker,),
        ).fetchone()[0]
    candidates = [
        _candidate(
            request=request,
            source_key=str(row["gold_row_id"]),
            route_rank=index,
            score=None,
            query_indexes=(),
            payload={
                "ticker": str(row["ticker"] or ""),
                "fiscal_year": row["fiscal_year"],
                "period": str(row["period"] or ""),
                "period_role": str(row["period_role"] or ""),
                "period_start": str(row["period_start"] or ""),
                "period_end": str(row["period_end"] or ""),
                "published_at": str(row["published_at"] or ""),
                "metric_family": str(row["metric_family"] or ""),
                "metric_name": str(row["metric_name"] or ""),
                "value": str(row["value"] or ""),
                "unit": str(row["unit"] or ""),
                "authority_mode": str(row["authority_mode"] or ""),
                "source_url": str(row["source_url"] or row["citation_url"] or ""),
                "evidence_ref": str(row["evidence_ref"] or ""),
                "preview": _clip(row["citation_span"] or row["claim_boundary"]),
                "strict_identity_filter_applied": True,
                "strict_period_filter_applied": bool(years),
                "exact_value_authority": True,
            },
        )
        for index, row in enumerate(rows, start=1)
    ]
    gaps = []
    if not candidates:
        gaps.append(
            _route_gap(
                request,
                code=(
                    "internal_exact_period_coverage_absent"
                    if latest is not None and years and int(latest) < min(years)
                    else "internal_exact_candidate_absent"
                ),
                detail={"requested_fiscal_years": years, "latest_available_fiscal_year": latest},
            )
        )
    return _route_terminal(request, candidates, gaps, started=started)


def _record_publication_date(record: Mapping[str, Any]) -> str:
    metadata = record.get("metadata")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    return str(
        record.get("publication_date")
        or record.get("published_at")
        or metadata.get("filing_date")
        or ""
    )


def _normalise_accession(value: Any) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits if len(digits) == 18 else ""


def _normalise_form_type(value: Any) -> str:
    text = str(value or "").strip().upper().replace("_", "-")
    compact = text.replace("-", "")
    return {
        "10K": "10-K",
        "10Q": "10-Q",
        "8K": "8-K",
        "20F": "20-F",
        "40F": "40-F",
        "6K": "6-K",
    }.get(compact, text)


def load_document_lineage_lookup(
    policy: Mapping[str, Any], *, repo_root: str | Path
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    manifests = _as_list(
        (policy.get("local_assets") or {}).get("document_lineage_manifests")
    )
    documents: dict[tuple[str, str, int, str, str], dict[str, Any]] = {}
    manifest_counts: dict[str, int] = {}
    for manifest in manifests:
        ref = str(manifest["path"])
        count = 0
        with (root / ref).open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise S1InternalCandidateCeilingError(
                        f"internal_candidate_ceiling_lineage_manifest_json_invalid:"
                        f"{ref}:{line_number}"
                    ) from exc
                metadata = dict(row.get("metadata") or {})
                ticker = str(row.get("ticker") or metadata.get("ticker") or "").upper()
                form_type = _normalise_form_type(
                    row.get("form_type")
                    or row.get("source_type")
                    or metadata.get("form_type")
                )
                fiscal_year = int(
                    row.get("fiscal_year") or metadata.get("fiscal_year") or 0
                )
                accession = _normalise_accession(
                    row.get("accession_number")
                    or metadata.get("accession_number")
                )
                source_url = str(
                    row.get("filing_url")
                    or row.get("source_url")
                    or metadata.get("filing_url")
                    or metadata.get("source_url")
                    or ""
                )
                published_at = str(
                    row.get("filing_date")
                    or row.get("published_at")
                    or metadata.get("filing_date")
                    or metadata.get("published_at")
                    or ""
                )
                if not ticker or not form_type or not fiscal_year:
                    continue
                key = (ticker, form_type, fiscal_year, accession, source_url)
                documents[key] = {
                    "ticker": ticker,
                    "form_type": form_type,
                    "fiscal_year": fiscal_year,
                    "accession_number": accession,
                    "source_url": source_url,
                    "published_at": published_at,
                    "report_date": str(
                        row.get("report_date")
                        or row.get("period_end")
                        or metadata.get("report_date")
                        or metadata.get("period_end")
                        or ""
                    ),
                    "manifest_ref": ref,
                }
                count += 1
        manifest_counts[ref] = count
    by_accession: dict[str, list[dict[str, Any]]] = {}
    by_ticker_year_form: dict[tuple[str, int, str], list[dict[str, Any]]] = {}
    for document in documents.values():
        accession = str(document["accession_number"])
        if accession:
            by_accession.setdefault(accession, []).append(document)
        key = (
            str(document["ticker"]),
            int(document["fiscal_year"]),
            str(document["form_type"]),
        )
        by_ticker_year_form.setdefault(key, []).append(document)
    return {
        "by_accession": by_accession,
        "by_ticker_year_form": by_ticker_year_form,
        "manifest_counts": manifest_counts,
        "document_count": len(documents),
    }


def _record_accession_candidates(record: Mapping[str, Any]) -> list[str]:
    metadata = dict(record.get("metadata") or {})
    values = [
        record.get("accession_number"),
        metadata.get("accession_number"),
        record.get("source_evidence_id"),
        record.get("object_id"),
    ]
    accessions: list[str] = []
    for value in values:
        direct = _normalise_accession(value)
        if direct and direct not in accessions:
            accessions.append(direct)
        for match in re.findall(r"(?<!\d)\d{18}(?!\d)", str(value or "")):
            normalised = _normalise_accession(match)
            if normalised and normalised not in accessions:
                accessions.append(normalised)
    return accessions


def resolve_document_lineage(
    record: Mapping[str, Any], *, lookup: Mapping[str, Any] | None
) -> dict[str, Any]:
    if not lookup:
        return {}
    for accession in _record_accession_candidates(record):
        matches = list((lookup.get("by_accession") or {}).get(accession) or [])
        if len(matches) == 1:
            return {**dict(matches[0]), "resolution_method": "exact_accession"}
    ticker = str(record.get("ticker") or "").upper()
    fiscal_year = int(record.get("fiscal_year") or 0)
    form_type = _normalise_form_type(
        record.get("form_type") or record.get("source_type")
    )
    matches = list(
        (lookup.get("by_ticker_year_form") or {}).get(
            (ticker, fiscal_year, form_type)
        )
        or []
    )
    if len(matches) == 1:
        return {
            **dict(matches[0]),
            "resolution_method": "unique_ticker_reporting_year_form",
        }
    period_end = str(record.get("period_end") or "")
    if period_end:
        period_matches = [
            item
            for item in matches
            if str(item.get("report_date") or item.get("period_end") or "")
            == period_end
        ]
        if len(period_matches) == 1:
            return {
                **dict(period_matches[0]),
                "resolution_method": "ticker_reporting_year_form_period_end",
            }
    return {}


def _document_temporal_filter_partitions(
    *,
    filters: Mapping[str, Any],
    base_filters: Mapping[str, Any],
    temporal_filter_policy: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    policy = dict(temporal_filter_policy or {})
    mode = str(policy.get("mode") or "legacy_filing_calendar_year_v1")
    if mode == "legacy_filing_calendar_year_v1":
        years = [
            int(item)
            for item in _as_list(
                filters.get(
                    "index_filing_calendar_years", filters.get("fiscal_years")
                )
            )
        ]
        route_filters = dict(base_filters)
        if years:
            route_filters["fiscal_year"] = years
        return [
            {
                "partition_id": "legacy_filing_calendar_year",
                "year_authority": "index_filing_calendar_years",
                "filters": route_filters,
            }
        ]
    if mode != "form_semantic_partition_v1":
        raise S1InternalCandidateCeilingError(
            f"internal_candidate_ceiling_temporal_filter_mode_invalid:{mode}"
        )
    reporting_forms = {
        str(item).upper()
        for item in _as_list(policy.get("reporting_period_forms"))
    }
    event_forms = {
        str(item).upper()
        for item in _as_list(policy.get("filing_calendar_event_forms"))
    }
    if not reporting_forms or not event_forms or reporting_forms & event_forms:
        raise S1InternalCandidateCeilingError(
            "internal_candidate_ceiling_temporal_form_policy_invalid"
        )
    requested_forms = {
        str(item).upper() for item in _as_list(base_filters.get("form_type"))
    }
    unknown_forms = requested_forms - reporting_forms - event_forms
    if unknown_forms:
        raise S1InternalCandidateCeilingError(
            "internal_candidate_ceiling_temporal_form_unclassified:"
            + ",".join(sorted(unknown_forms))
        )
    reporting_years = [
        int(item)
        for item in _as_list(
            filters.get("reporting_fiscal_years", filters.get("fiscal_years"))
        )
    ]
    filing_years = [
        int(item)
        for item in _as_list(
            filters.get(
                "index_filing_calendar_years", filters.get("fiscal_years")
            )
        )
    ]
    partitions: list[dict[str, Any]] = []
    for partition_id, authority, forms, years in (
        (
            "periodic_reporting_fiscal_year",
            "reporting_fiscal_years",
            requested_forms & reporting_forms,
            reporting_years,
        ),
        (
            "event_filing_calendar_year",
            "index_filing_calendar_years",
            requested_forms & event_forms,
            filing_years,
        ),
    ):
        if not forms:
            continue
        route_filters = {
            **dict(base_filters),
            "form_type": sorted(forms),
        }
        if years:
            route_filters["fiscal_year"] = years
        partitions.append(
            {
                "partition_id": partition_id,
                "year_authority": authority,
                "filters": route_filters,
            }
        )
    if not partitions:
        raise S1InternalCandidateCeilingError(
            "internal_candidate_ceiling_temporal_filter_partitions_empty"
        )
    return partitions


def _execute_lexical_request(
    request: Mapping[str, Any],
    *,
    retriever: Any,
    object_route: bool,
    temporal_filter_policy: Mapping[str, Any] | None = None,
    document_lineage_lookup: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    filters = dict(request.get("typed_filters") or {})
    base_filters: dict[str, Any] = {
        "ticker": str(request["evidence_owner_ticker"]),
        "form_type": [str(item) for item in _as_list(filters.get("form_types"))],
    }
    if object_route:
        base_filters["object_type"] = [
            str(item) for item in _as_list(filters.get("object_types"))
        ]
    base_filters = {
        key: value for key, value in base_filters.items() if value not in ([], "")
    }
    filter_partitions = _document_temporal_filter_partitions(
        filters=filters,
        base_filters=base_filters,
        temporal_filter_policy=temporal_filter_policy,
    )
    budget = int(request.get("candidate_budget") or 24)
    query_texts = [str(item) for item in _as_list(request.get("query_texts"))]
    search_lanes = [
        {
            "partition_id": str(partition["partition_id"]),
            "filters": dict(partition["filters"]),
            "query_index": query_index,
            "query": query,
        }
        for partition in filter_partitions
        for query_index, query in enumerate(query_texts)
    ]
    query_results = [
        retriever.search(
            str(lane["query"]), top_k=budget, filters=dict(lane["filters"])
        )
        for lane in search_lanes
    ]
    key_field = "object_id" if object_route else "evidence_id"
    merged = deterministic_round_robin_dedupe(
        query_results,
        key_fn=lambda row: str(
            row.get(key_field)
            or (row.get("record") or {}).get(key_field)
            or (row.get("record") or {}).get("source_evidence_id")
            or ""
        ),
        budget=budget,
    )
    candidates: list[dict[str, Any]] = []
    future_rejected = 0
    as_of = str(filters.get("publication_date_on_or_before") or "")
    for rank, (row, query_indexes) in enumerate(merged, start=1):
        record = dict(row.get("record") or {})
        lineage = (
            resolve_document_lineage(record, lookup=document_lineage_lookup)
            if object_route
            else {}
        )
        published_at = _record_publication_date(record) or str(
            lineage.get("published_at") or ""
        )
        if as_of and published_at and published_at > as_of:
            future_rejected += 1
            continue
        source_key = str(
            row.get(key_field)
            or record.get(key_field)
            or record.get("source_evidence_id")
            or ""
        )
        preview = row.get("preview") if object_route else row.get("text_preview")
        preview = preview or record.get("preview") or record.get("text")
        candidates.append(
            _candidate(
                request=request,
                source_key=source_key,
                route_rank=len(candidates) + 1,
                score=float(row.get("score") or 0.0),
                query_indexes=query_indexes,
                payload={
                    "ticker": str(row.get("ticker") or record.get("ticker") or ""),
                    "fiscal_year": row.get("fiscal_year") or record.get("fiscal_year"),
                    "form_type": str(
                        record.get("form_type")
                        or record.get("source_type")
                        or ""
                    ),
                    "source_tier": str(record.get("source_tier") or ""),
                    "object_type": str(row.get("object_type") or record.get("object_type") or ""),
                    "source_evidence_id": str(record.get("source_evidence_id") or ""),
                    "section": str(row.get("section") or record.get("section") or ""),
                    "subsection": str(row.get("subsection") or record.get("subsection") or ""),
                    "published_at": published_at,
                    "source_url": str(
                        record.get("source_url") or lineage.get("source_url") or ""
                    ),
                    "source_accession_number": str(
                        record.get("accession_number")
                        or lineage.get("accession_number")
                        or ""
                    ),
                    "lineage_resolution_method": str(
                        lineage.get("resolution_method") or ""
                    ),
                    "lineage_manifest_ref": str(lineage.get("manifest_ref") or ""),
                    "preview": _clip(preview),
                    "temporal_filter_partition_ids": sorted(
                        {
                            str(search_lanes[index]["partition_id"])
                            for index in query_indexes
                        }
                    ),
                    "strict_identity_filter_applied": True,
                    "strict_period_filter_applied": any(
                        bool(search_lanes[index]["filters"].get("fiscal_year"))
                        for index in query_indexes
                    ),
                    "exact_value_authority": False,
                },
            )
        )
    gaps = []
    if not candidates:
        gaps.append(
            _route_gap(
                request,
                code=(
                    "internal_object_or_lexical_index_identity_period_absent"
                    if not any(query_results)
                    else "internal_object_or_lexical_candidates_rejected"
                ),
                detail={
                    "filter_partitions": filter_partitions,
                    "query_count": len(query_texts),
                    "search_lane_count": len(search_lanes),
                    "future_candidate_rejections": future_rejected,
                },
            )
        )
    terminal = _route_terminal(request, candidates, gaps, started=started)
    terminal["query_count"] = len(query_texts)
    terminal["search_lane_count"] = len(search_lanes)
    terminal["temporal_filter_partitions"] = filter_partitions
    terminal["raw_query_result_count"] = sum(len(rows) for rows in query_results)
    terminal["future_candidate_rejections"] = future_rejected
    return terminal


def execute_object_bm25_request(
    request: Mapping[str, Any],
    *,
    retriever: Any,
    temporal_filter_policy: Mapping[str, Any] | None = None,
    document_lineage_lookup: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return _execute_lexical_request(
        request,
        retriever=retriever,
        object_route=True,
        temporal_filter_policy=temporal_filter_policy,
        document_lineage_lookup=document_lineage_lookup,
    )


def execute_bm25_request(
    request: Mapping[str, Any],
    *,
    retriever: Any,
    temporal_filter_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return _execute_lexical_request(
        request,
        retriever=retriever,
        object_route=False,
        temporal_filter_policy=temporal_filter_policy,
    )


def execute_graph_request(
    request: Mapping[str, Any], *, database: Path
) -> dict[str, Any]:
    started = time.perf_counter()
    filters = dict(request.get("typed_filters") or {})
    allowed_roles = [str(item) for item in _as_list(filters.get("allowed_source_roles"))]
    budget = int(request.get("candidate_budget") or 12)
    owner = str(request["evidence_owner_ticker"])
    if not allowed_roles:
        raise S1InternalCandidateCeilingError(
            "internal_candidate_ceiling_graph_roles_missing"
        )
    placeholders = ",".join("?" for _ in allowed_roles)
    query = f"""
        SELECT e.graph_edge_id,e.from_node_id,e.to_node_id,e.edge_type,
               e.authority_mode,e.source_role,e.claim_boundary,e.confidence,
               from_node.ticker AS owner_ticker,from_node.label AS owner_label,
               to_node.ticker AS target_ticker,to_node.label AS target_label,
               support.citation_url,support.citation_span,support.evidence_ref
        FROM research_graph_edges e
        JOIN research_graph_nodes from_node ON from_node.graph_node_id=e.from_node_id
        LEFT JOIN research_graph_nodes to_node ON to_node.graph_node_id=e.to_node_id
        LEFT JOIN research_graph_evidence_support support ON support.support_id=(
            SELECT s.support_id FROM research_graph_evidence_support s
            WHERE s.graph_edge_id=e.graph_edge_id AND s.can_enter_evidence_bundle=1
            ORDER BY CASE WHEN s.citation_url<>'' THEN 0 ELSE 1 END,s.support_id LIMIT 1
        )
        WHERE e.from_node_id=? AND e.can_enter_evidence_bundle=1
          AND e.source_role IN ({placeholders})
        ORDER BY CASE WHEN support.citation_url<>'' THEN 0 ELSE 1 END,
                 e.source_role,e.edge_type,e.graph_edge_id LIMIT ?
    """
    with _ro_connection(database) as connection:
        rows = connection.execute(
            query, [f"company:{owner}", *allowed_roles, budget]
        ).fetchall()
        inventory = connection.execute(
            "SELECT COUNT(*) FROM research_graph_edges "
            "WHERE from_node_id=? AND can_enter_evidence_bundle=1",
            (f"company:{owner}",),
        ).fetchone()[0]
    candidates = [
        _candidate(
            request=request,
            source_key=str(row["graph_edge_id"]),
            route_rank=index,
            score=float(row["confidence"] or 0.0),
            query_indexes=(),
            payload={
                "ticker": str(row["owner_ticker"] or owner),
                "target_ticker": str(row["target_ticker"] or ""),
                "target_label": str(row["target_label"] or ""),
                "edge_type": str(row["edge_type"] or ""),
                "source_role": str(row["source_role"] or ""),
                "authority_mode": str(row["authority_mode"] or ""),
                "evidence_ref": str(row["evidence_ref"] or ""),
                "source_url": str(row["citation_url"] or ""),
                "published_at": "",
                "preview": _clip(row["citation_span"] or row["claim_boundary"]),
                "strict_identity_filter_applied": True,
                "strict_relationship_role_filter_applied": True,
                "strict_period_filter_applied": False,
                "period_match_state": "unavailable_in_graph_index",
                "exact_value_authority": False,
            },
        )
        for index, row in enumerate(rows, start=1)
    ]
    gaps = []
    if not candidates:
        gaps.append(
            _route_gap(
                request,
                code=(
                    "internal_graph_required_role_absent"
                    if inventory
                    else "internal_graph_owner_node_or_edges_absent"
                ),
                detail={
                    "owner_total_eligible_edge_count": int(inventory),
                    "allowed_source_roles": allowed_roles,
                    "period_filter_available": False,
                },
            )
        )
    terminal = _route_terminal(request, candidates, gaps, started=started)
    terminal["owner_total_eligible_edge_count"] = int(inventory)
    terminal["period_filter_available"] = False
    return terminal


def _route_terminal(
    request: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    gaps: Sequence[Mapping[str, Any]],
    *,
    started: float,
) -> dict[str, Any]:
    body = {
        "request_id": str(request["request_id"]),
        "request_digest": str(request["request_digest"]),
        "bundle_id": str(request["bundle_id"]),
        "case_key": str(request["case_key"]),
        "evidence_slot_id": str(request["evidence_slot_id"]),
        "evidence_owner_ticker": str(request["evidence_owner_ticker"]),
        "route_id": str(request["route_id"]),
        "status": "completed_with_candidates" if candidates else "completed_typed_gap",
        "candidate_count": len(candidates),
        "candidates": [dict(item) for item in candidates],
        "typed_gaps": [dict(item) for item in gaps],
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "embedding_calls": 0,
        "rerank_calls": 0,
        "evidence_promotion_calls": 0,
    }
    digest_body = dict(body)
    digest_body.pop("elapsed_ms")
    body["terminal_digest"] = canonical_digest(digest_body)
    return body


def qualify_local_assets(
    *,
    policy: Mapping[str, Any],
    repo_root: str | Path,
    document_lineage_lookup: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    assets = dict(policy.get("local_assets") or {})
    bm25_dir = root / str(assets["bm25_index_dir"])
    object_dir = root / str(assets["object_bm25_index_dir"])
    gold_path = root / str(assets["gold_sqlite"])
    graph_path = root / str(assets["relationship_graph_sqlite"])
    milvus_cfg = _read_json(
        root / str(policy["immutable_inputs"]["milvus_runtime_ref"])
    )
    checks: dict[str, Any] = {}

    bm25_meta = _read_json(bm25_dir / "metadata.json")
    checks["bm25"] = {
        "status": "qualified" if (bm25_dir / "bm25.pkl").is_file() and (bm25_dir / "records.jsonl").is_file() else "unavailable",
        "record_count": int(bm25_meta.get("records") or 0),
        "metadata_digest": canonical_digest(bm25_meta),
    }
    object_meta = _read_json(object_dir / "metadata.json")
    checks["object_bm25"] = {
        "status": "qualified" if (object_dir / "records.sqlite").is_file() else "unavailable",
        "record_count": int(object_meta.get("records") or 0),
        "metadata_digest": canonical_digest(object_meta),
    }
    with _ro_connection(gold_path) as connection:
        gold_count = int(connection.execute("SELECT COUNT(*) FROM gold_fact_signal_mart").fetchone()[0])
    checks["gold_sql"] = {"status": "qualified", "record_count": gold_count}
    with _ro_connection(graph_path) as connection:
        graph_counts = {
            "nodes": int(connection.execute("SELECT COUNT(*) FROM research_graph_nodes").fetchone()[0]),
            "edges": int(connection.execute("SELECT COUNT(*) FROM research_graph_edges").fetchone()[0]),
            "support": int(connection.execute("SELECT COUNT(*) FROM research_graph_evidence_support").fetchone()[0]),
        }
    checks["relationship_graph"] = {"status": "qualified", **graph_counts}
    lineage = (
        dict(document_lineage_lookup)
        if document_lineage_lookup is not None
        else load_document_lineage_lookup(policy, repo_root=root)
    )
    checks["document_lineage"] = {
        "status": "qualified" if lineage.get("document_count") else "not_configured",
        "document_count": int(lineage.get("document_count") or 0),
        "manifest_counts": dict(lineage.get("manifest_counts") or {}),
    }

    milvus_db = Path(str(milvus_cfg.get("db_path") or ""))
    deps = Path(str(assets.get("milvus_dependencies_dir") or ""))
    configured_model = Path(str(milvus_cfg.get("embedding_model") or ""))
    fallback_models = [Path(str(item)) for item in _as_list(assets.get("local_embedding_model_candidates"))]
    model_candidates = []
    for path in [configured_model, *fallback_models]:
        config_path = path / "config.json"
        hidden_size = None
        if config_path.is_file():
            try:
                hidden_size = json.loads(config_path.read_text(encoding="utf-8")).get("hidden_size")
            except (OSError, json.JSONDecodeError):
                hidden_size = None
        model_candidates.append(
            {
                "path": path.as_posix(),
                "exists": path.is_dir(),
                "hidden_size": hidden_size,
                "is_configured": path == configured_model,
            }
        )
    milvus_check: dict[str, Any] = {
        "status": "unavailable",
        "db_exists": milvus_lite_storage_exists(milvus_db),
        "db_storage_kind": (
            "directory" if milvus_db.is_dir() else "file" if milvus_db.is_file() else "absent"
        ),
        "dependencies_exist": deps.is_dir(),
        "configured_embedding_model_exists": configured_model.is_dir(),
        "embedding_model_candidates": model_candidates,
        "semantic_execution_admitted": False,
    }
    if milvus_lite_storage_exists(milvus_db) and deps.is_dir():
        if str(deps) not in sys.path:
            sys.path.insert(0, str(deps))
        try:
            from pymilvus import MilvusClient  # type: ignore

            client = MilvusClient(uri=str(milvus_db))
            collection = str(milvus_cfg.get("collection_name") or "")
            collections = list(client.list_collections())
            description = client.describe_collection(collection)
            fields = {
                str(item.get("name") or ""): dict(item)
                for item in description.get("fields", [])
            }
            stats = dict(client.get_collection_stats(collection))
            required_fields = set(
                policy.get("resource_qualification", {}).get(
                    "required_milvus_fields", []
                )
            )
            embedding_dim = int(
                fields.get("embedding", {}).get("params", {}).get("dim") or 0
            )
            ticker_presence = {}
            loaded_for_qualification = False
            try:
                client.load_collection(collection_name=collection)
                loaded_for_qualification = True
                for ticker in ("DELL", "MSFT", "MU", "NVDA", "TSM"):
                    rows = client.query(
                        collection_name=collection,
                        filter=f'ticker == "{ticker}"',
                        output_fields=[
                            "vector_id",
                            "ticker",
                            "fiscal_year",
                            "vector_kind",
                        ],
                        limit=1,
                    )
                    ticker_presence[ticker] = bool(rows)
            finally:
                if loaded_for_qualification:
                    try:
                        client.release_collection(collection_name=collection)
                    except Exception:
                        pass
            collection_ok = (
                collection in collections
                and required_fields.issubset(fields)
                and embedding_dim
                == int(policy["resource_qualification"]["expected_embedding_dim"])
                and int(stats.get("row_count") or 0)
                == int(milvus_cfg.get("vector_count") or 0)
            )
            milvus_check.update(
                {
                    "status": "collection_qualified_model_locator_blocked" if collection_ok and not configured_model.is_dir() else "qualified" if collection_ok else "schema_or_count_failed",
                    "collection_name": collection,
                    "collection_present": collection in collections,
                    "row_count": int(stats.get("row_count") or 0),
                    "field_names": sorted(fields),
                    "embedding_dim": embedding_dim,
                    "required_fields_present": required_fields.issubset(fields),
                    "ticker_presence": ticker_presence,
                    "semantic_execution_admitted": False,
                }
            )
        except Exception as exc:  # resource qualification must terminalize
            milvus_check.update(
                {
                    "status": "qualification_error",
                    "error_type": type(exc).__name__,
                    "error": _clip(exc, 300),
                    "semantic_execution_admitted": False,
                }
            )
    checks["milvus_dense"] = milvus_check
    return checks


def execute_internal_candidate_inventory(
    *,
    policy: Mapping[str, Any],
    integration_proof: Mapping[str, Any],
    repo_root: str | Path,
    bm25_factory: Callable[[str | Path], Any] | None = None,
    object_bm25_factory: Callable[[str | Path], Any] | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    assets = dict(policy["local_assets"])
    requests = [dict(item) for item in integration_proof.get("requests", [])]
    if len(requests) != 90:
        raise S1InternalCandidateCeilingError(
            "internal_candidate_ceiling_request_count_invalid"
        )
    request_ids = [str(item.get("request_id") or "") for item in requests]
    if len(request_ids) != len(set(request_ids)) or any(not item for item in request_ids):
        raise S1InternalCandidateCeilingError(
            "internal_candidate_ceiling_request_identity_invalid"
        )
    if bm25_factory is None or object_bm25_factory is None:
        from retrieval.bm25_retriever import BM25Retriever
        from retrieval.object_bm25_retriever import ObjectBM25Retriever

        bm25_factory = bm25_factory or BM25Retriever
        object_bm25_factory = object_bm25_factory or ObjectBM25Retriever
    bm25 = bm25_factory(root / str(assets["bm25_index_dir"]))
    object_bm25 = object_bm25_factory(root / str(assets["object_bm25_index_dir"]))
    gold = root / str(assets["gold_sqlite"])
    graph = root / str(assets["relationship_graph_sqlite"])
    document_lineage_lookup = load_document_lineage_lookup(policy, repo_root=root)
    temporal_filter_policy = dict(
        policy.get("execution_contract", {}).get("document_temporal_filter")
        or {}
    )
    terminals: list[dict[str, Any]] = []
    started = time.perf_counter()
    try:
        for request in requests:
            route = str(request.get("route_id") or "")
            if route == "internal_sql_exact":
                terminal = execute_sql_exact_request(request, database=gold)
            elif route == "internal_object_bm25":
                terminal = execute_object_bm25_request(
                    request,
                    retriever=object_bm25,
                    temporal_filter_policy=temporal_filter_policy,
                    document_lineage_lookup=document_lineage_lookup,
                )
            elif route == "internal_bm25":
                terminal = execute_bm25_request(
                    request,
                    retriever=bm25,
                    temporal_filter_policy=temporal_filter_policy,
                )
            elif route == "internal_relationship_graph":
                terminal = execute_graph_request(request, database=graph)
            elif route == "internal_milvus_dense":
                terminal = {
                    "request_id": str(request["request_id"]),
                    "request_digest": str(request["request_digest"]),
                    "bundle_id": str(request["bundle_id"]),
                    "case_key": str(request["case_key"]),
                    "evidence_slot_id": str(request["evidence_slot_id"]),
                    "evidence_owner_ticker": str(request["evidence_owner_ticker"]),
                    "route_id": route,
                    "status": "qualification_only_embedding_not_admitted",
                    "candidate_count": 0,
                    "candidates": [],
                    "typed_gaps": [],
                    "embedding_calls": 0,
                    "rerank_calls": 0,
                    "evidence_promotion_calls": 0,
                }
                terminal["terminal_digest"] = canonical_digest(terminal)
            else:
                raise S1InternalCandidateCeilingError(
                    f"internal_candidate_ceiling_unknown_route:{route}"
                )
            terminals.append(terminal)
    finally:
        for retriever in (object_bm25, bm25):
            close = getattr(retriever, "close", None)
            if callable(close):
                close()
    asset_qualification = qualify_local_assets(
        policy=policy,
        repo_root=root,
        document_lineage_lookup=document_lineage_lookup,
    )
    route_counts = Counter(str(item["route_id"]) for item in terminals)
    candidate_counts = Counter()
    gap_counts = Counter()
    for terminal in terminals:
        candidate_counts[str(terminal["route_id"])] += int(
            terminal.get("candidate_count") or 0
        )
        for gap in terminal.get("typed_gaps", []):
            gap_counts[str(gap.get("gap_code") or "unknown")] += 1
    bundle_summaries = []
    for bundle in integration_proof.get("bundles", []):
        local = [
            terminal
            for terminal in terminals
            if terminal["bundle_id"] == bundle["bundle_id"]
        ]
        bundle_summaries.append(
            {
                "bundle_id": str(bundle["bundle_id"]),
                "case_key": str(bundle["case_key"]),
                "evidence_slot_id": str(bundle["evidence_slot_id"]),
                "subject_ticker": str(bundle["subject_ticker"]),
                "evidence_owner_ticker": str(bundle["evidence_owner_ticker"]),
                "requested_reporting_fiscal_years": list(
                    bundle.get("reporting_fiscal_years")
                    or bundle.get("fiscal_years")
                    or []
                ),
                "requested_index_filing_calendar_years": list(
                    bundle.get("index_filing_calendar_years")
                    or bundle.get("fiscal_years")
                    or []
                ),
                "route_status": {
                    terminal["route_id"]: terminal["status"] for terminal in local
                },
                "route_candidate_counts": {
                    terminal["route_id"]: int(terminal.get("candidate_count") or 0)
                    for terminal in local
                },
                "strict_executed_route_candidate_present": any(
                    int(terminal.get("candidate_count") or 0) > 0
                    for terminal in local
                    if terminal["route_id"] in EXECUTED_ROUTES
                ),
            }
        )
    body = {
        "schema_version": str(
            policy.get("observation_schema")
            or "fin_ia_0_1_3_s1_internal_candidate_inventory_observation_v1_0"
        ),
        "contract_ref": str(policy["contract_ref"]),
        "run_scope": str(policy.get("run_scope") or RUN_SCOPE),
        "status": "completed_candidate_inventory_qrels_pending",
        "integration_proof_digest": str(integration_proof["proof_digest"]),
        "resource_qualification": asset_qualification,
        "route_terminals": terminals,
        "bundle_summaries": bundle_summaries,
        "observed_counts": {
            "bundles": len(bundle_summaries),
            "physical_request_terminals": len(terminals),
            "executed_local_route_requests": sum(
                route_counts[route] for route in EXECUTED_ROUTES
            ),
            "dense_qualification_only_requests": sum(
                route_counts[route] for route in QUALIFICATION_ONLY_ROUTES
            ),
            "candidate_counts_by_route": dict(sorted(candidate_counts.items())),
            "typed_gap_counts": dict(sorted(gap_counts.items())),
            "network": 0,
            "provider": 0,
            "model": 0,
            "document_fetch": 0,
            "embedding": 0,
            "rerank": 0,
            "evidence_promotion": 0,
        },
        "qrels_state": "agent_curated_pending_owner_review_not_yet_materialized",
        "candidate_ceiling_proven": False,
        "BGE_fusion_rerank_admitted": False,
        "external_product_coverage_closed": False,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "known_boundary": "This observation executes bounded read-only exact, ObjectBM25, BM25 and Graph candidate generation and qualifies Milvus metadata only. Candidate identities are saved for qrels curation, but no owner-reviewed qrels, semantic embedding, fusion, reranking, Evidence promotion, downstream utilization, external coverage or release claim is established.",
    }
    return {**body, "result_digest": canonical_observation_digest(body)}
