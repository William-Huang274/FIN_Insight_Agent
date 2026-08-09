from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import sys
import time
from typing import Any, Callable, Iterable, Mapping, Sequence

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.project_os_preflight import run_project_os_preflight
from sec_agent.s1_internal_candidate_ceiling import canonical_observation_digest
from sec_agent.s1_internal_qrels_owner_acceptance import (
    validate_internal_qrels_owner_acceptance,
)


RUN_SCOPE = "S1_INTERNAL_BGE_FUSION_AND_RERANK_EVALUATION"
POLICY_SCHEMA = "fin_ia_0_1_3_s1_internal_bge_fusion_evaluation_policy_v1_0"
RESULT_SCHEMA = "fin_ia_0_1_3_s1_internal_bge_fusion_evaluation_result_v1_0"
POLICY_SCHEMA_V1_1 = (
    "fin_ia_0_1_3_s1_internal_bge_fusion_evaluation_policy_v1_1"
)
RESULT_SCHEMA_V1_1 = (
    "fin_ia_0_1_3_s1_internal_bge_fusion_evaluation_result_v1_1"
)
EVENT_FORMS = {"8-K", "6-K"}
VECTOR_KIND_SUFFIXES = {
    "narrative_chunk",
    "table_chunk",
    "paraphrase_context",
    "relationship_context",
}


class S1InternalBGEFusionEvaluationError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S1InternalBGEFusionEvaluationError(code)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "internal_bge_fusion_json_object_required")
    return value


def _normalized_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _digest_valid(value: Mapping[str, Any], field: str) -> bool:
    body = dict(value)
    supplied = str(body.pop(field, ""))
    return bool(supplied) and supplied == canonical_digest(body)


def load_internal_bge_fusion_evaluation_policy(
    path: str | Path, *, repo_root: str | Path
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    policy = _read_json(Path(path))
    schema_pair = (
        policy.get("schema_version"),
        policy.get("result_schema"),
    )
    _require(
        schema_pair
        in {
            (POLICY_SCHEMA, RESULT_SCHEMA),
            (POLICY_SCHEMA_V1_1, RESULT_SCHEMA_V1_1),
        }
        and policy.get("run_scope") == RUN_SCOPE
        and policy.get("binding_hash_profile")
        == "sha256_utf8_lf_normalized_v1",
        "internal_bge_fusion_policy_identity_invalid",
    )
    immutable = dict(policy.get("immutable_inputs") or {})
    stems = [
        "owner_qrels_acceptance",
        "research_qrels",
        "sparse_candidate_observation",
        "query_facet_proof",
        "query_facet_policy",
        "dense_resource_qualification",
        "milvus_runtime",
    ]
    if policy.get("schema_version") == POLICY_SCHEMA_V1_1:
        stems.extend(("invalidated_attempt_r1", "post_run_identity_audit"))
    for stem in stems:
        ref = str(immutable.get(f"{stem}_ref") or "")
        supplied = str(immutable.get(f"{stem}_sha256") or "")
        target = root / ref
        _require(
            bool(ref)
            and target.is_file()
            and _normalized_sha256(target) == supplied,
            f"internal_bge_fusion_policy_binding_invalid:{stem}",
        )
    candidate = dict(policy.get("candidate_contract") or {})
    _require(
        candidate.get("bundle_count") == 18
        and candidate.get("candidate_budget_per_bundle") == 24
        and candidate.get("qrels_loaded_after_candidate_generation") is True
        and candidate.get("target_identity_may_enter_query_or_retrieval") is False
        and candidate.get("candidate_state") == "candidate_only_not_evidence"
        and candidate.get("milvus_fiscal_year_field_authority")
        == "reporting_fiscal_years",
        "internal_bge_fusion_candidate_contract_invalid",
    )
    if policy.get("schema_version") == POLICY_SCHEMA_V1_1:
        identity = dict(candidate.get("identity_canonicalization") or {})
        replacement = dict(policy.get("replacement_authority") or {})
        _require(
            identity.get("vector_base_rule")
            == "strip_only_final_known_vector_kind_suffix"
            and set(identity.get("known_vector_kind_suffixes") or [])
            == VECTOR_KIND_SUFFIXES
            and identity.get("namespace_prefix_is_never_evidence_identity") is True
            and identity.get("cross_document_merge_forbidden") is True,
            "internal_bge_fusion_identity_contract_invalid",
        )
        _require(
            replacement.get("invalidated_attempt_id")
            == "20260809_three_case_s1_internal_ranking_bge_m3_sparse_dense_facet_fusion_owner_qrels_v1_r1"
            and replacement.get("maximum_replacement_executions") == 1
            and replacement.get("automatic_retry") is False
            and replacement.get("reason")
            == "candidate_identity_namespace_prefix_collapse",
            "internal_bge_fusion_replacement_authority_invalid",
        )
    ranking = dict(policy.get("ranking_contract") or {})
    expected_slots = {
        "issuer_results_and_management_commentary",
        "regulatory_risk_and_financial_reconciliation",
        "customer_demand_and_deployment_validation",
        "supply_chain_capacity_and_counterevidence",
    }
    _require(
        int(ranking.get("rrf_k") or 0) == 60
        and set(ranking.get("facet_aware_route_weights") or {}) == expected_slots
        and ranking.get("route_order_must_not_change_output") is True,
        "internal_bge_fusion_ranking_contract_invalid",
    )
    hard = dict(policy.get("hard_boundaries") or {})
    _require(
        all(
            int(hard.get(key, -1)) == 0
            for key in (
                "network",
                "provider",
                "llm_model",
                "document_fetch",
                "rerank",
                "evidence_promotion",
            )
        )
        and int(hard.get("maximum_embedding_vectors") or -1) == 36
        and int(hard.get("maximum_milvus_searches") or -1) == 36
        and hard.get("may_download_model_or_reranker") is False
        and hard.get("may_mutate_milvus_or_sparse_assets") is False
        and hard.get("may_promote_candidate_to_evidence") is False
        and hard.get("may_close_current_quarter_sql_or_external_release_blocker")
        is False,
        "internal_bge_fusion_hard_boundary_invalid",
    )
    return policy


def _base_vector_evidence_id(candidate: Mapping[str, Any]) -> str:
    vector_id = str(candidate.get("vector_id") or "").strip()
    if not vector_id or "::" not in vector_id:
        return vector_id
    prefix, suffix = vector_id.rsplit("::", 1)
    declared_kind = str(candidate.get("vector_kind") or "").strip()
    if suffix in VECTOR_KIND_SUFFIXES or (
        declared_kind in VECTOR_KIND_SUFFIXES and suffix == declared_kind
    ):
        return prefix
    return vector_id


def _candidate_aliases(candidate: Mapping[str, Any]) -> set[str]:
    aliases = {
        str(candidate.get(key) or "").strip()
        for key in (
            "candidate_id",
            "source_key",
            "source_evidence_id",
            "evidence_id",
            "vector_id",
        )
    }
    vector_base = _base_vector_evidence_id(candidate)
    if vector_base:
        aliases.add(vector_base)
    return {item for item in aliases if item}


def _candidate_key(candidate: Mapping[str, Any]) -> str:
    aliases = _candidate_aliases(candidate)
    _require(bool(aliases), "internal_bge_fusion_candidate_identity_missing")
    preferred = (
        str(candidate.get("source_evidence_id") or "").strip()
        or str(candidate.get("evidence_id") or "").strip()
        or str(candidate.get("source_key") or "").strip()
        or str(candidate.get("candidate_id") or "").strip()
        or _base_vector_evidence_id(candidate)
    )
    return preferred or min(aliases)


def _metadata_record(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "candidate_key": _candidate_key(candidate),
        "aliases": sorted(_candidate_aliases(candidate)),
        "candidate_id": str(candidate.get("candidate_id") or ""),
        "source_key": str(candidate.get("source_key") or ""),
        "source_evidence_id": str(candidate.get("source_evidence_id") or ""),
        "evidence_id": str(candidate.get("evidence_id") or ""),
        "vector_id": str(candidate.get("vector_id") or ""),
        "case_key": str(candidate.get("case_key") or ""),
        "evidence_slot_id": str(candidate.get("evidence_slot_id") or ""),
        "ticker": str(candidate.get("ticker") or ""),
        "fiscal_year": candidate.get("fiscal_year"),
        "form_type": str(candidate.get("form_type") or ""),
        "source_tier": str(candidate.get("source_tier") or ""),
        "published_at": str(candidate.get("published_at") or ""),
        "source_url": str(candidate.get("source_url") or ""),
        "preview": str(candidate.get("preview") or "")[:240],
    }


def _component_groups(candidates: Sequence[Mapping[str, Any]]) -> list[list[int]]:
    parents = list(range(len(candidates)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        a, b = find(left), find(right)
        if a != b:
            parents[max(a, b)] = min(a, b)

    alias_owner: dict[str, int] = {}
    for index, candidate in enumerate(candidates):
        for alias in sorted(_candidate_aliases(candidate)):
            if alias in alias_owner:
                union(index, alias_owner[alias])
            else:
                alias_owner[alias] = index
    groups: dict[int, list[int]] = defaultdict(list)
    for index in range(len(candidates)):
        groups[find(index)].append(index)
    return [groups[key] for key in sorted(groups)]


def merge_ranked_lanes(
    *,
    lanes: Mapping[str, Sequence[Mapping[str, Any]]],
    weights: Mapping[str, float],
    rrf_k: int,
    top_k: int,
) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for lane_name in sorted(lanes):
        _require(lane_name in weights, "internal_bge_fusion_lane_weight_missing")
        for ordinal, source in enumerate(lanes[lane_name], start=1):
            item = dict(source)
            item["_lane"] = lane_name
            item["_rank"] = int(source.get("rank") or source.get("route_rank") or ordinal)
            flattened.append(item)
    if not flattened:
        return []
    out: list[dict[str, Any]] = []
    for indexes in _component_groups(flattened):
        members = [flattened[index] for index in indexes]
        aliases = sorted(
            {alias for member in members for alias in _candidate_aliases(member)}
        )
        lane_ranks: dict[str, int] = {}
        for member in members:
            lane = str(member["_lane"])
            lane_ranks[lane] = min(
                lane_ranks.get(lane, 10**9), int(member["_rank"])
            )
        score = sum(
            float(weights[lane]) / (float(rrf_k) + rank)
            for lane, rank in lane_ranks.items()
        )
        candidates = sorted(
            members,
            key=lambda member: (
                -sum(
                    bool(member.get(field))
                    for field in (
                        "source_url",
                        "published_at",
                        "source_evidence_id",
                        "evidence_id",
                        "preview",
                    )
                ),
                canonical_digest(
                    {key: value for key, value in member.items() if not key.startswith("_")}
                ),
            ),
        )
        metadata = _metadata_record(candidates[0])
        canonical_keys = sorted({_candidate_key(member) for member in members})
        metadata.update(
            {
                "candidate_key": canonical_keys[0],
                "aliases": aliases,
                "route_ranks": dict(sorted(lane_ranks.items())),
                "score": round(score, 12),
            }
        )
        out.append(metadata)
    out.sort(key=lambda item: (-float(item["score"]), str(item["candidate_key"])))
    for rank, item in enumerate(out[:top_k], start=1):
        item["rank"] = rank
    return out[:top_k]


def _normalize_form_type(value: Any) -> str:
    return str(value or "").strip().upper().replace("FORM ", "")


def _milvus_in_clause(field: str, values: Iterable[Any]) -> str:
    encoded = ", ".join(json.dumps(value, ensure_ascii=False) for value in values)
    return f"{field} in [{encoded}]"


def _milvus_filter(request: Mapping[str, Any]) -> str:
    typed = dict(request.get("typed_filters") or {})
    _require(
        typed.get("typed_filter_required") is True
        and typed.get("allow_relaxed_identity_period_or_relationship_fallback")
        is False
        and typed.get("years") == typed.get("reporting_fiscal_years"),
        "internal_bge_fusion_dense_typed_filter_invalid",
    )
    clauses = [
        _milvus_in_clause(
            "ticker", [str(item).upper() for item in typed.get("tickers") or []]
        ),
        "fiscal_year in ["
        + ", ".join(str(int(item)) for item in typed.get("years") or [])
        + "]",
        _milvus_in_clause(
            "form_type",
            [_normalize_form_type(item) for item in typed.get("filing_types") or []],
        ),
        _milvus_in_clause(
            "source_tier", [str(item) for item in typed.get("source_tiers") or []]
        ),
        _milvus_in_clause(
            "vector_kind", [str(item) for item in typed.get("vector_kinds") or []]
        ),
    ]
    _require(
        all(not clause.endswith("[]") for clause in clauses),
        "internal_bge_fusion_dense_filter_empty",
    )
    return " and ".join(clauses)


def _search_dense(
    *,
    client: Any,
    collection_name: str,
    vector: Sequence[float],
    request: Mapping[str, Any],
    top_k: int,
) -> list[dict[str, Any]]:
    output_fields = [
        "vector_id",
        "evidence_id",
        "ticker",
        "fiscal_year",
        "form_type",
        "source_tier",
        "vector_kind",
        "object_type",
        "preview",
        "vector_role",
        "semantic_scope",
        "intent_tags",
        "relationship_role",
    ]
    results = client.search(
        collection_name=collection_name,
        data=[[float(item) for item in vector]],
        anns_field="embedding",
        limit=top_k,
        filter=_milvus_filter(request),
        output_fields=output_fields,
    )
    hits: list[dict[str, Any]] = []
    for rank, hit in enumerate(results[0] if results else [], start=1):
        entity = dict(hit.get("entity") or {})
        entity.update(
            {
                "rank": rank,
                "raw_dense_score": float(hit.get("distance") or 0.0),
                "case_key": str(request.get("case_key") or ""),
                "evidence_slot_id": str(request.get("evidence_slot_id") or ""),
            }
        )
        hits.append(entity)
    return hits


def _validate_bound_inputs(
    *, policy: Mapping[str, Any], repo_root: Path
) -> dict[str, dict[str, Any]]:
    refs = dict(policy["immutable_inputs"])
    owner = _read_json(repo_root / str(refs["owner_qrels_acceptance_ref"]))
    validate_internal_qrels_owner_acceptance(owner)
    _require(
        (owner.get("owner_decision") or {}).get("ranking_entry_eligible") is True,
        "internal_bge_fusion_owner_acceptance_missing",
    )
    observation = _read_json(
        repo_root / str(refs["sparse_candidate_observation_ref"])
    )
    _require(
        observation.get("result_digest")
        == canonical_observation_digest(observation),
        "internal_bge_fusion_sparse_observation_digest_invalid",
    )
    query_proof = _read_json(repo_root / str(refs["query_facet_proof_ref"]))
    _require(
        _digest_valid(query_proof, "proof_digest")
        and query_proof.get("schema_version")
        == "fin_ia_0_1_3_s1_internal_query_facet_integration_zero_call_proof_v1_2",
        "internal_bge_fusion_query_proof_invalid",
    )
    resource = _read_json(
        repo_root / str(refs["dense_resource_qualification_ref"])
    )
    _require(
        _digest_valid(resource, "result_digest")
        and (resource.get("resource_qualification") or {})
        .get("bge_m3", {})
        .get("status")
        == "qualified_successor_locator_not_yet_bound",
        "internal_bge_fusion_resource_qualification_invalid",
    )
    runtime = _read_json(repo_root / str(refs["milvus_runtime_ref"]))
    out = {
        "owner": owner,
        "observation": observation,
        "query_proof": query_proof,
        "resource": resource,
        "runtime": runtime,
    }
    if policy.get("schema_version") == POLICY_SCHEMA_V1_1:
        invalidated = _read_json(
            repo_root / str(refs["invalidated_attempt_r1_ref"])
        )
        audit = _read_json(repo_root / str(refs["post_run_identity_audit_ref"]))
        _require(
            _digest_valid(invalidated, "result_digest")
            and invalidated.get("attempt_id")
            == (policy.get("replacement_authority") or {}).get(
                "invalidated_attempt_id"
            )
            and _digest_valid(audit, "audit_digest")
            and audit.get("status")
            == "attempt_invalidated_for_adoption_identity_canonicalization_defect"
            and (audit.get("disposition") or {}).get("replacement_eligible") is True,
            "internal_bge_fusion_replacement_audit_invalid",
        )
        out.update({"invalidated_attempt_r1": invalidated, "identity_audit": audit})
    return out


def _sparse_lanes_by_bundle(
    observation: Mapping[str, Any], *, allowed_routes: set[str]
) -> tuple[
    dict[str, dict[str, list[dict[str, Any]]]],
    list[dict[str, Any]],
]:
    lanes: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(dict)
    typed_gaps: list[dict[str, Any]] = []
    for terminal in observation.get("route_terminals") or []:
        route = str(terminal.get("route_id") or "")
        if route not in allowed_routes:
            continue
        bundle_id = str(terminal.get("bundle_id") or "")
        candidates = [dict(item) for item in terminal.get("candidates") or []]
        if terminal.get("status") == "completed_typed_gap":
            _require(
                bool(bundle_id)
                and not candidates
                and int(terminal.get("candidate_count") or 0) == 0
                and bool(terminal.get("typed_gaps") or []),
                "internal_bge_fusion_sparse_typed_gap_invalid",
            )
            typed_gaps.append(
                {
                    "bundle_id": bundle_id,
                    "route_id": route,
                    "terminal_digest": str(terminal.get("terminal_digest") or ""),
                    "typed_gaps": [dict(item) for item in terminal["typed_gaps"]],
                }
            )
            continue
        _require(
            terminal.get("status") == "completed_with_candidates"
            and bool(bundle_id)
            and bool(candidates),
            "internal_bge_fusion_sparse_terminal_invalid",
        )
        lanes[bundle_id][route] = candidates
    _require(len(lanes) == 18, "internal_bge_fusion_sparse_bundle_count_invalid")
    return dict(lanes), sorted(
        typed_gaps,
        key=lambda item: (str(item["bundle_id"]), str(item["route_id"])),
    )


def _dense_requests_by_bundle(
    query_proof: Mapping[str, Any]
) -> dict[str, dict[str, Any]]:
    requests = {
        str(item["bundle_id"]): dict(item)
        for item in query_proof.get("requests") or []
        if item.get("route_id") == "internal_milvus_dense"
    }
    _require(len(requests) == 18, "internal_bge_fusion_dense_request_count_invalid")
    for request in requests.values():
        _require(
            len(request.get("query_texts") or []) == 1
            and len(request.get("alternate_language_query_texts") or []) == 1
            and request.get("candidate_state") == "candidate_only_not_evidence",
            "internal_bge_fusion_dense_query_shape_invalid",
        )
        _milvus_filter(request)
    return requests


def _default_model_factory(path: str, device: str) -> Any:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(path, device=device, local_files_only=True)


def _default_client_factory(*, dependency_dir: str, uri: str) -> Any:
    if dependency_dir not in sys.path:
        sys.path.insert(0, dependency_dir)
    from pymilvus import MilvusClient

    return MilvusClient(uri=uri)


def _device() -> str:
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def _as_matrix(value: Any) -> list[list[float]]:
    matrix = value.tolist() if hasattr(value, "tolist") else value
    return [[float(item) for item in row] for row in matrix]


def _ranking_signature(rankings: Mapping[str, Sequence[Mapping[str, Any]]]) -> str:
    return canonical_digest(
        {
            key: [str(item.get("candidate_key") or "") for item in value]
            for key, value in sorted(rankings.items())
        }
    )


def _target_aliases(row: Mapping[str, Any]) -> set[str]:
    selected = dict(row.get("selected_candidate") or {})
    return _candidate_aliases(selected)


def _row_rank(
    row: Mapping[str, Any], ranking: Sequence[Mapping[str, Any]]
) -> int | None:
    target = _target_aliases(row)
    for item in ranking:
        if target.intersection(set(item.get("aliases") or [])):
            return int(item["rank"])
    return None


def _false_promotions(
    row: Mapping[str, Any], ranking: Sequence[Mapping[str, Any]]
) -> dict[str, int]:
    owner = str(row.get("evidence_owner_ticker") or "")
    case_key = str(row.get("case_key") or "")
    reporting = {int(item) for item in row.get("reporting_fiscal_years") or []}
    filing = {int(item) for item in row.get("index_filing_calendar_years") or []}
    counts = {
        "wrong_evidence_owner_ticker": 0,
        "wrong_reporting_period": 0,
        "cross_case_binding": 0,
    }
    for item in ranking[:10]:
        ticker = str(item.get("ticker") or "")
        if ticker and ticker != owner:
            counts["wrong_evidence_owner_ticker"] += 1
        candidate_case = str(item.get("case_key") or "")
        if candidate_case and candidate_case != case_key:
            counts["cross_case_binding"] += 1
        year = item.get("fiscal_year")
        if year not in (None, ""):
            allowed = filing if _normalize_form_type(item.get("form_type")) in EVENT_FORMS else reporting
            if allowed and int(year) not in allowed:
                counts["wrong_reporting_period"] += 1
    return counts


def score_rankings(
    *,
    qrels_rows: Sequence[Mapping[str, Any]],
    rankings: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    ranks = [_row_rank(row, rankings.get(str(row["bundle_id"]), [])) for row in qrels_rows]
    total = len(ranks)
    _require(total == 18, "internal_bge_fusion_scoring_target_count_invalid")
    metrics = {
        f"recall_at_{cutoff}": round(
            sum(rank is not None and rank <= cutoff for rank in ranks) / total, 8
        )
        for cutoff in (1, 5, 10, 24)
    }
    metrics["mrr_at_10"] = round(
        sum((1.0 / rank) if rank is not None and rank <= 10 else 0.0 for rank in ranks)
        / total,
        8,
    )
    metrics["ndcg_at_10"] = round(
        sum(
            (1.0 / math.log2(rank + 1))
            if rank is not None and rank <= 10
            else 0.0
            for rank in ranks
        )
        / total,
        8,
    )
    false = {
        "wrong_evidence_owner_ticker": 0,
        "wrong_reporting_period": 0,
        "cross_case_binding": 0,
    }
    rows = []
    for row, rank in zip(qrels_rows, ranks):
        local_false = _false_promotions(
            row, rankings.get(str(row["bundle_id"]), [])
        )
        for key, value in local_false.items():
            false[key] += value
        rows.append(
            {
                "bundle_id": str(row["bundle_id"]),
                "case_key": str(row["case_key"]),
                "evidence_slot_id": str(row["evidence_slot_id"]),
                "evidence_owner_ticker": str(row["evidence_owner_ticker"]),
                "selected_target_rank": rank,
                "selected_target_in_top_10": rank is not None and rank <= 10,
                "false_promotions_top_10": local_false,
            }
        )
    return {
        "metrics": metrics,
        "selected_target_ranks": rows,
        "false_promotions_top_10": false,
    }


def _cohort_metrics(
    *,
    qrels_rows: Sequence[Mapping[str, Any]],
    rankings: Mapping[str, Sequence[Mapping[str, Any]]],
    field: str,
) -> dict[str, Any]:
    out = {}
    for value in sorted({str(row[field]) for row in qrels_rows}):
        local = [row for row in qrels_rows if str(row[field]) == value]
        ranks = [_row_rank(row, rankings.get(str(row["bundle_id"]), [])) for row in local]
        out[value] = {
            "targets": len(local),
            "recall_at_10": round(
                sum(rank is not None and rank <= 10 for rank in ranks) / len(local),
                8,
            ),
            "mrr_at_10": round(
                sum(
                    (1.0 / rank) if rank is not None and rank <= 10 else 0.0
                    for rank in ranks
                )
                / len(local),
                8,
            ),
        }
    return out


def _qrels_after_candidate_generation(
    *, policy: Mapping[str, Any], repo_root: Path, owner: Mapping[str, Any]
) -> dict[str, Any]:
    ref = str(policy["immutable_inputs"]["research_qrels_ref"])
    qrels = _read_json(repo_root / ref)
    _require(
        _digest_valid(qrels, "review_digest")
        and qrels.get("review_digest")
        == (owner.get("source_qrels") or {}).get("review_digest"),
        "internal_bge_fusion_qrels_digest_invalid",
    )
    accepted = list((owner.get("source_qrels") or {}).get("accepted_qrel_digests") or [])
    rows = list(qrels.get("qrels") or [])
    _require(
        len(rows) == 18
        and accepted == [str(row.get("qrel_digest") or "") for row in rows],
        "internal_bge_fusion_owner_qrel_binding_invalid",
    )
    return qrels


def execute_internal_bge_fusion_evaluation(
    *,
    policy: Mapping[str, Any],
    repo_root: str | Path,
    model_factory: Callable[[str, str], Any] | None = None,
    client_factory: Callable[..., Any] | None = None,
    progress: Callable[[str], None] | None = None,
    execution_kind: str = "local_real_embedding",
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    started = time.perf_counter()
    progress = progress or (lambda _: None)
    if execution_kind == "local_real_embedding":
        _require(
            policy.get("schema_version") == POLICY_SCHEMA_V1_1,
            "internal_bge_fusion_r1_policy_invalidated_for_real_execution",
        )
    preflight = run_project_os_preflight(root, run_scope=RUN_SCOPE)
    _require(preflight.get("status") == "pass", "internal_bge_fusion_preflight_blocked")
    inputs = _validate_bound_inputs(policy=policy, repo_root=root)
    candidate_contract = dict(policy["candidate_contract"])
    ranking_contract = dict(policy["ranking_contract"])
    budget = int(candidate_contract["candidate_budget_per_bundle"])
    rrf_k = int(ranking_contract["rrf_k"])
    sparse_lanes, sparse_typed_gaps = _sparse_lanes_by_bundle(
        inputs["observation"],
        allowed_routes=set(candidate_contract["sparse_routes"]),
    )
    dense_requests = _dense_requests_by_bundle(inputs["query_proof"])
    ordered_bundle_ids = sorted(dense_requests)
    query_rows = []
    for bundle_id in ordered_bundle_ids:
        request = dense_requests[bundle_id]
        query_rows.extend(
            [
                (bundle_id, "dense_en", str(request["query_texts"][0])),
                (
                    bundle_id,
                    "dense_zh",
                    str(request["alternate_language_query_texts"][0]),
                ),
            ]
        )
    _require(len(query_rows) == 36, "internal_bge_fusion_embedding_budget_invalid")
    resources = dict(policy["resource_bindings"])
    model_path = Path(str(resources["embedding_model"]))
    _require(model_path.is_dir(), "internal_bge_fusion_embedding_model_missing")
    device = _device()
    progress(f"loading_bge_m3:{device}")
    model_started = time.perf_counter()
    model = (model_factory or _default_model_factory)(str(model_path), device)
    model_load_ms = round((time.perf_counter() - model_started) * 1000, 3)
    progress("encoding_36_queries")
    embedding_started = time.perf_counter()
    encoded = model.encode(
        [row[2] for row in query_rows],
        batch_size=int(resources["embedding_batch_size"]),
        normalize_embeddings=bool(resources["normalize_embeddings"]),
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    matrix = _as_matrix(encoded)
    embedding_ms = round((time.perf_counter() - embedding_started) * 1000, 3)
    expected_dim = int(resources["expected_embedding_dim"])
    _require(
        len(matrix) == 36 and all(len(row) == expected_dim for row in matrix),
        "internal_bge_fusion_embedding_dimension_invalid",
    )
    runtime = inputs["runtime"]
    client = (client_factory or _default_client_factory)(
        dependency_dir=str(resources["milvus_dependencies_dir"]),
        uri=str(runtime["db_path"]),
    )
    collection = str(runtime["collection_name"])
    dense_lanes: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(dict)
    search_started = time.perf_counter()
    progress("searching_milvus_36_queries")
    client.load_collection(collection_name=collection)
    try:
        for index, (bundle_id, lane, _) in enumerate(query_rows):
            request = dense_requests[bundle_id]
            dense_lanes[bundle_id][lane] = _search_dense(
                client=client,
                collection_name=collection,
                vector=matrix[index],
                request=request,
                top_k=budget,
            )
    finally:
        client.release_collection(collection_name=collection)
    search_ms = round((time.perf_counter() - search_started) * 1000, 3)
    progress("building_sparse_dense_and_fusion_rankings")
    sparse_rankings: dict[str, list[dict[str, Any]]] = {}
    dense_rankings: dict[str, list[dict[str, Any]]] = {}
    fusion_rankings: dict[str, list[dict[str, Any]]] = {}
    sparse_reverse: dict[str, list[dict[str, Any]]] = {}
    fusion_reverse: dict[str, list[dict[str, Any]]] = {}
    for bundle_id in ordered_bundle_ids:
        request = dense_requests[bundle_id]
        slot = str(request["evidence_slot_id"])
        sparse_rankings[bundle_id] = merge_ranked_lanes(
            lanes=sparse_lanes[bundle_id],
            weights=ranking_contract["sparse_baseline_weights"],
            rrf_k=rrf_k,
            top_k=budget,
        )
        dense_rankings[bundle_id] = merge_ranked_lanes(
            lanes=dense_lanes[bundle_id],
            weights=ranking_contract["dense_baseline_weights"],
            rrf_k=rrf_k,
            top_k=budget,
        )
        combined_lanes = {**sparse_lanes[bundle_id], **dense_lanes[bundle_id]}
        fusion_rankings[bundle_id] = merge_ranked_lanes(
            lanes=combined_lanes,
            weights=ranking_contract["facet_aware_route_weights"][slot],
            rrf_k=rrf_k,
            top_k=budget,
        )
        sparse_reverse[bundle_id] = merge_ranked_lanes(
            lanes={key: list(reversed(value)) for key, value in reversed(list(sparse_lanes[bundle_id].items()))},
            weights=ranking_contract["sparse_baseline_weights"],
            rrf_k=rrf_k,
            top_k=budget,
        )
        fusion_reverse[bundle_id] = merge_ranked_lanes(
            lanes={key: list(reversed(value)) for key, value in reversed(list(combined_lanes.items()))},
            weights=ranking_contract["facet_aware_route_weights"][slot],
            rrf_k=rrf_k,
            top_k=budget,
        )
    stability = {
        "sparse_route_and_candidate_order_reversal": (
            _ranking_signature(sparse_rankings) == _ranking_signature(sparse_reverse)
        ),
        "fusion_route_and_candidate_order_reversal": (
            _ranking_signature(fusion_rankings) == _ranking_signature(fusion_reverse)
        ),
    }
    candidate_generation = {
        "bundle_ids": ordered_bundle_ids,
        "sparse_rankings": sparse_rankings,
        "dense_rankings": dense_rankings,
        "fusion_rankings": fusion_rankings,
        "stability": stability,
    }
    candidate_generation_digest = canonical_digest(candidate_generation)
    progress("loading_owner_qrels_after_candidate_generation_terminal")
    qrels = _qrels_after_candidate_generation(
        policy=policy, repo_root=root, owner=inputs["owner"]
    )
    rows = list(qrels["qrels"])
    evaluations = {
        "sparse_rrf": score_rankings(qrels_rows=rows, rankings=sparse_rankings),
        "dense_bilingual_rrf": score_rankings(qrels_rows=rows, rankings=dense_rankings),
        "facet_aware_fusion": score_rankings(qrels_rows=rows, rankings=fusion_rankings),
    }
    cohorts = {
        approach: {
            "case_key": _cohort_metrics(
                qrels_rows=rows, rankings=rankings, field="case_key"
            ),
            "evidence_slot_id": _cohort_metrics(
                qrels_rows=rows, rankings=rankings, field="evidence_slot_id"
            ),
        }
        for approach, rankings in (
            ("sparse_rrf", sparse_rankings),
            ("dense_bilingual_rrf", dense_rankings),
            ("facet_aware_fusion", fusion_rankings),
        )
    }
    sparse_metrics = evaluations["sparse_rrf"]["metrics"]
    fusion_metrics = evaluations["facet_aware_fusion"]["metrics"]
    false_total = sum(
        evaluations["facet_aware_fusion"]["false_promotions_top_10"].values()
    )
    adoption_checks = {
        "fusion_recall_at_10_not_below_sparse": (
            fusion_metrics["recall_at_10"] >= sparse_metrics["recall_at_10"]
        ),
        "fusion_mrr_at_10_within_0_02_of_sparse": (
            fusion_metrics["mrr_at_10"] + 0.02 >= sparse_metrics["mrr_at_10"]
        ),
        "fusion_false_promotion_count_zero": false_total == 0,
        "deterministic_stability_pass": all(stability.values()),
    }
    adopt = all(adoption_checks.values())
    elapsed = round((time.perf_counter() - started) * 1000, 3)
    body: dict[str, Any] = {
        "schema_version": str(policy["result_schema"]),
        "contract_ref": str(policy["contract_ref"]),
        "run_scope": RUN_SCOPE,
        "attempt_id": str(policy["attempt_id"]),
        "status": "terminal_succeeded_local_ranking_evaluation",
        "execution_kind": execution_kind,
        "project_os_preflight": {
            "status": preflight["status"],
            "run_scope": preflight["run_scope"],
            "open_full_chain_blocker_count": preflight[
                "open_full_chain_blocker_count"
            ],
        },
        "policy_digest": canonical_digest(policy),
        "owner_qrels_decision_digest": str(inputs["owner"]["decision_digest"]),
        "research_qrels_review_digest": str(qrels["review_digest"]),
        "supersession": (
            {
                "invalidated_attempt_id": policy["replacement_authority"][
                    "invalidated_attempt_id"
                ],
                "post_run_identity_audit_digest": inputs["identity_audit"][
                    "audit_digest"
                ],
            }
            if policy.get("schema_version") == POLICY_SCHEMA_V1_1
            else None
        ),
        "candidate_generation": {
            "status": "terminal_before_qrels_load",
            "digest": candidate_generation_digest,
            "qrels_loaded_after_candidate_generation": True,
            "bundle_count": len(ordered_bundle_ids),
            "candidate_budget_per_bundle": budget,
            "identity_canonicalization": (
                dict(candidate_contract["identity_canonicalization"])
                if policy.get("schema_version") == POLICY_SCHEMA_V1_1
                else {
                    "historical_policy": "v1_0",
                    "runtime_algorithm": "final_known_vector_kind_suffix_only",
                }
            ),
            "preserved_sparse_typed_gaps": sparse_typed_gaps,
            "rankings": candidate_generation,
        },
        "evaluation": evaluations,
        "cohort_evaluation": cohorts,
        "adoption_decision": {
            "checks": adoption_checks,
            "decision": (
                "adopt_facet_aware_fusion_for_downstream_candidate_selection"
                if adopt
                else "retain_sparse_baseline_and_open_dense_or_fusion_repair"
            ),
            "fusion_adopted": adopt,
            "dense_route_role": "semantic_supplement_not_exact_value_authority",
            "reranker": "not_executed_optional_resource_absent",
        },
        "runtime_efficiency": {
            "device": device,
            "model_load_ms": model_load_ms,
            "embedding_ms": embedding_ms,
            "milvus_search_ms": search_ms,
            "wall_time_ms": elapsed,
            "embedding_vectors": len(matrix),
            "embedding_dim": expected_dim,
            "milvus_searches": len(query_rows),
        },
        "observed_calls": {
            "network": 0,
            "provider": 0,
            "llm_model": 0,
            "document_fetch": 0,
            "embedding_batches": 1,
            "embedding_vectors": len(matrix),
            "milvus_searches": len(query_rows),
            "rerank": 0,
            "evidence_promotion": 0,
        },
        "preserved_boundaries": {
            "candidates_promoted_to_evidence": False,
            "current_quarter_exact_sql": "0_of_6_open",
            "external_official_required_slot_coverage": "4_of_12_open_release_blocker",
            "downstream_utilization_proven": False,
            "product_acceptance": False,
            "release": "not_qualified",
        },
        "known_boundary": (
            "This run measures selected-target retrieval on the Owner-reviewed 18-row "
            "set. It does not make every unlabelled candidate irrelevant, promote "
            "Evidence, execute a reranker, refresh current-quarter SQL, close external "
            "coverage, prove downstream research use, or accept release."
        ),
    }
    return validate_internal_bge_fusion_evaluation_result(
        {**body, "result_digest": canonical_digest(body)}
    )


def validate_internal_bge_fusion_evaluation_result(
    value: Mapping[str, Any]
) -> dict[str, Any]:
    body = dict(value)
    supplied = str(body.pop("result_digest", ""))
    _require(
        value.get("schema_version") in {RESULT_SCHEMA, RESULT_SCHEMA_V1_1}
        and supplied == canonical_digest(body),
        "internal_bge_fusion_result_digest_invalid",
    )
    observed = dict(value.get("observed_calls") or {})
    boundary = dict(value.get("preserved_boundaries") or {})
    generation = dict(value.get("candidate_generation") or {})
    _require(
        value.get("status") == "terminal_succeeded_local_ranking_evaluation"
        and generation.get("status") == "terminal_before_qrels_load"
        and generation.get("qrels_loaded_after_candidate_generation") is True
        and generation.get("bundle_count") == 18
        and observed.get("embedding_vectors") == 36
        and observed.get("milvus_searches") == 36
        and all(
            int(observed.get(key, -1)) == 0
            for key in (
                "network",
                "provider",
                "llm_model",
                "document_fetch",
                "rerank",
                "evidence_promotion",
            )
        )
        and boundary.get("candidates_promoted_to_evidence") is False
        and boundary.get("current_quarter_exact_sql") == "0_of_6_open"
        and boundary.get("external_official_required_slot_coverage")
        == "4_of_12_open_release_blocker"
        and boundary.get("release") == "not_qualified",
        "internal_bge_fusion_result_boundary_invalid",
    )
    return dict(value)


__all__ = [
    "POLICY_SCHEMA",
    "POLICY_SCHEMA_V1_1",
    "RESULT_SCHEMA",
    "RESULT_SCHEMA_V1_1",
    "RUN_SCOPE",
    "S1InternalBGEFusionEvaluationError",
    "execute_internal_bge_fusion_evaluation",
    "load_internal_bge_fusion_evaluation_policy",
    "merge_ranked_lanes",
    "score_rankings",
    "validate_internal_bge_fusion_evaluation_result",
]
