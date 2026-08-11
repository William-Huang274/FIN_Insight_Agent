from __future__ import annotations

from collections import defaultdict
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import pickle
import re
import sys
import time
from typing import Any, Callable, Mapping, Sequence

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.financial_research_generalization_contract import (
    compile_case_research_contract,
    compile_external_case_profile,
    load_financial_research_contract,
)
from sec_agent.financial_research_held_out_profile_registry import (
    load_held_out_profile_selection_policy,
)
from sec_agent.s1_candidate_bundle_physical_index import (
    LocalBgeM3Embedder,
    inspect_physical_store_artifact,
    tokenize_candidate_text,
)


RUN_SCOPE = "S1_INTERNAL_SPARSE_DENSE_FUSION_BUSINESS_EXPLAINED_SUCCESSOR"
POLICY_SCHEMA = (
    "fin_ia_0_1_3_s1_candidate_bundle_retrieval_evaluation_policy_v1_0"
)
RESULT_SCHEMA = (
    "fin_ia_0_1_3_s1_candidate_bundle_retrieval_evaluation_result_v1_0"
)
IMPLEMENTATION_PROOF_SCHEMA = (
    "fin_ia_0_1_3_s1_candidate_bundle_retrieval_evaluation_implementation_proof_v1_0"
)
AUTHORITY_SCHEMA = (
    "fin_ia_0_1_3_s1_candidate_bundle_retrieval_evaluation_authority_v1_0"
)
CASES = ("DELL", "MU", "NVDA", "ORCL", "ASML", "ANET")
KNOWN_CASES = ("DELL", "MU", "NVDA")
OWNER_SUITE = "known_three_case_owner_qrels18"
SLOT_SUITE = "six_case_canonical_slot_labels54"


class CandidateBundleRetrievalEvaluationError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CandidateBundleRetrievalEvaluationError(code)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "candidate_bundle_retrieval_json_object_required")
    return value


def normalized_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _digest_valid(value: Mapping[str, Any], field: str) -> bool:
    body = dict(value)
    supplied = str(body.pop(field, ""))
    return bool(supplied) and supplied == canonical_digest(body)


def load_candidate_bundle_retrieval_evaluation_policy(
    path: str | Path,
    *,
    repo_root: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    policy = _read_json(Path(path))
    _require(
        policy.get("schema_version") == POLICY_SCHEMA
        and policy.get("result_schema") == RESULT_SCHEMA
        and policy.get("authority_schema") == AUTHORITY_SCHEMA
        and policy.get("run_scope") == RUN_SCOPE
        and policy.get("binding_hash_profile") == "sha256_utf8_lf_normalized_v1",
        "candidate_bundle_retrieval_policy_identity_invalid",
    )
    immutable = dict(policy.get("immutable_inputs") or {})
    stems = (
        "physical_result",
        "execution_plan",
        "generalization_contract",
        "held_out_profile_policy",
        "known_case_query_facet_proof",
        "owner_qrels",
        "owner_acceptance",
        "physical_build_policy",
    )
    for stem in stems:
        ref = str(immutable.get(f"{stem}_ref") or "")
        target = root / ref
        _require(
            bool(ref)
            and target.is_file()
            and normalized_sha256(target) == immutable.get(f"{stem}_sha256"),
            f"candidate_bundle_retrieval_input_binding_invalid:{stem}",
        )
    evaluation = dict(policy.get("evaluation_contract") or {})
    ranking = dict(policy.get("ranking_contract") or {})
    runtime = dict(policy.get("runtime_contract") or {})
    ceiling = dict(policy.get("execution_ceiling") or {})
    _require(
        tuple(evaluation.get("cases") or ()) == CASES
        and len(evaluation.get("required_slot_ids") or []) == 8
        and evaluation.get("optional_slot_ids")
        == ["capital_allocation_and_valuation"]
        and int(evaluation.get("known_owner_qrel_rows") or 0) == 18
        and int(evaluation.get("canonical_slot_bundles") or 0) == 54
        and int(evaluation.get("total_query_bundles") or 0) == 72
        and evaluation.get("candidate_generation_before_label_load") is True
        and evaluation.get("gold_or_target_identity_may_enter_query") is False,
        "candidate_bundle_retrieval_evaluation_contract_invalid",
    )
    _require(
        int(ranking.get("top_k") or 0) == 10
        and int(ranking.get("rrf_k") or 0) == 60
        and ranking.get("case_filter_required") is True
        and ranking.get("slot_filter_for_sparse_or_dense_forbidden") is True
        and ranking.get("route_order_must_not_change_output") is True
        and ranking.get("weight_tuning_against_result_forbidden") is True
        and ranking.get("fusion_weights")
        == {"object_bm25": 1.0, "bge_m3_dense": 1.0},
        "candidate_bundle_retrieval_ranking_contract_invalid",
    )
    _require(
        str(runtime.get("python_executable") or "").startswith("/home/william/")
        and str(runtime.get("embedding_model_linux_ref") or "").startswith("/mnt/d/")
        and runtime.get("embedding_device") == "cpu"
        and int(runtime.get("embedding_dimension") or 0) == 1024
        and int(runtime.get("embedding_batch_size") or 0) == 8
        and runtime.get("normalize_embeddings") is True
        and runtime.get("evaluation_required_packages")
        == {"pydantic": "2.13.4"},
        "candidate_bundle_retrieval_runtime_contract_invalid",
    )
    _require(
        ceiling.get("maximum_executions") == 1
        and ceiling.get("automatic_retry") is False
        and ceiling.get("embedding_model_loads") == 1
        and ceiling.get("embedding_encode_invocations") == 1
        and ceiling.get("embedding_vectors") == 72
        and ceiling.get("object_bm25_queries") == 72
        and ceiling.get("milvus_search_invocations") == 6
        and ceiling.get("milvus_query_vectors") == 72
        and all(
            int(ceiling.get(key, -1)) == 0
            for key in (
                "network",
                "provider",
                "llm_model",
                "document_fetch",
                "rerank",
                "evidence_promotion",
            )
        ),
        "candidate_bundle_retrieval_execution_ceiling_invalid",
    )
    physical = _read_json(root / immutable["physical_result_ref"])
    _require(
        _digest_valid(physical, "result_digest")
        and physical.get("status")
        == "terminal_succeeded_physical_sparse_dense_build"
        and (physical.get("build") or {})
        .get("physical_store_artifact", {})
        .get("artifact_digest")
        == policy["physical_index_binding"]["expected_artifact_digest"],
        "candidate_bundle_retrieval_physical_result_invalid",
    )
    plan = _read_json(root / immutable["execution_plan_ref"])
    _require(
        _digest_valid(plan, "plan_digest")
        and "step_2" in str(plan.get("status") or ""),
        "candidate_bundle_retrieval_execution_plan_invalid",
    )
    owner = _read_json(root / immutable["owner_acceptance_ref"])
    _require(
        (owner.get("owner_decision") or {}).get("ranking_entry_eligible") is True,
        "candidate_bundle_retrieval_owner_qrels_not_accepted",
    )
    return policy


def inspect_candidate_bundle_retrieval_environment(
    policy: Mapping[str, Any],
    *,
    repo_root: str | Path,
) -> dict[str, Any]:
    from sec_agent.s1_candidate_bundle_physical_index import file_sha256

    root = Path(repo_root).resolve()
    binding = dict(policy["physical_index_binding"])
    runtime = dict(policy["runtime_contract"])
    build_policy = _read_json(
        root / policy["immutable_inputs"]["physical_build_policy_ref"]
    )
    physical_root = Path(binding["final_root"])
    dense_db = (
        physical_root
        / binding["dense_subdir"]
        / binding["milvus_db_filename"]
    )
    sparse_root = physical_root / binding["sparse_subdir"]
    artifact = inspect_physical_store_artifact(
        dense_db,
        contract=build_policy["index_contract"]["physical_store_artifact"],
        expected_count=int(binding["expected_candidate_count"]),
        embedding_dimension=int(runtime["embedding_dimension"]),
    )
    model_root = Path(runtime["embedding_model_linux_ref"])
    model_files = []
    for expected in build_policy["runtime_contract"]["required_model_files"]:
        target = model_root / str(expected["path"])
        model_files.append(
            {
                "path": str(expected["path"]),
                "present": target.is_file(),
                "bytes": target.stat().st_size if target.is_file() else 0,
                "sha256": file_sha256(target) if target.is_file() else "",
            }
        )
    expected_packages = {
        **build_policy["runtime_contract"]["required_packages"],
        **runtime["evaluation_required_packages"],
    }
    packages = {
        name: importlib.metadata.version(name)
        for name in expected_packages
    }
    expected_files = build_policy["runtime_contract"]["required_model_files"]
    qualified = bool(
        str(Path(sys.executable)) == str(Path(runtime["python_executable"]))
        and artifact["artifact_digest"] == binding["expected_artifact_digest"]
        and all(
            (sparse_root / name).is_file()
            for name in ("records.slim.jsonl", "bm25.pkl", "metadata.json")
        )
        and packages == expected_packages
        and all(
            observed["present"]
            and observed["bytes"] == expected["bytes"]
            and observed["sha256"] == expected["sha256"]
            for observed, expected in zip(model_files, expected_files, strict=True)
        )
    )
    return {
        "qualified": qualified,
        "python_executable": str(Path(sys.executable)),
        "packages": packages,
        "model_root": str(model_root),
        "model_files": model_files,
        "physical_root": str(physical_root),
        "physical_artifact_digest": artifact["artifact_digest"],
        "sparse_files_present": all(
            (sparse_root / name).is_file()
            for name in ("records.slim.jsonl", "bm25.pkl", "metadata.json")
        ),
        "observed_calls": {
            "network": 0,
            "provider": 0,
            "llm_model": 0,
            "embedding_model_loads": 0,
            "vector_search": 0,
            "rerank": 0,
            "evidence_promotion": 0,
        },
    }


def validate_candidate_bundle_retrieval_evaluation_authority(
    authority: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    body = {key: value for key, value in authority.items() if key != "authority_digest"}
    implementation = dict(authority.get("implementation") or {})
    environment = dict(authority.get("environment_qualification") or {})
    _require(
        authority.get("schema_version") == AUTHORITY_SCHEMA
        and authority.get("status") == "issued_unconsumed"
        and authority.get("run_scope") == RUN_SCOPE
        and authority.get("attempt_id") == policy.get("attempt_id")
        and authority.get("policy_digest") == canonical_digest(policy)
        and authority.get("execution_ceiling") == policy.get("execution_ceiling")
        and int(authority.get("maximum_executions") or 0) == 1
        and authority.get("automatic_retry") is False
        and canonical_digest(body) == str(authority.get("authority_digest") or "")
        and implementation.get("clean") is True
        and implementation.get("synced") is True
        and int(implementation.get("ahead") or 0) == 0
        and int(implementation.get("behind") or 0) == 0
        and re.fullmatch(r"[0-9a-f]{40}", str(implementation.get("commit") or ""))
        is not None
        and bool(implementation.get("bindings"))
        and re.fullmatch(
            r"[0-9a-f]{64}",
            str(implementation.get("implementation_proof_digest") or ""),
        )
        is not None
        and environment.get("qualified") is True
        and environment.get("physical_artifact_digest")
        == policy["physical_index_binding"]["expected_artifact_digest"]
        and environment.get("sparse_files_present") is True
        and all(
            int(value) == 0
            for value in dict(environment.get("observed_calls") or {}).values()
        )
        and (authority.get("project_os_preflight") or {}).get("status") == "pass",
        "candidate_bundle_retrieval_authority_invalid",
    )
    if repo_root is not None:
        root = Path(repo_root).resolve()
        for binding in implementation["bindings"]:
            ref = str(binding.get("ref") or "")
            target = root / ref
            _require(
                bool(ref)
                and target.is_file()
                and normalized_sha256(target) == str(binding.get("sha256") or ""),
                "candidate_bundle_retrieval_authority_binding_drift",
            )
    return dict(authority)


def _dedupe_terms(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = re.sub(r"\s+", " ", str(value or "").strip())
        marker = text.casefold()
        if text and marker not in seen:
            seen.add(marker)
            out.append(text)
    return out


def _period_text(value: str) -> str:
    return re.sub(r"_+", " ", value).strip()


def _bundle(
    *,
    suite_id: str,
    case_key: str,
    research_slot_id: str,
    query_text: str,
    required: bool,
    expected_owner_ticker: str = "",
    expected_relationship_direction: str = "",
    reporting_years: Sequence[int] = (),
) -> dict[str, Any]:
    body = {
        "suite_id": suite_id,
        "case_key": case_key,
        "research_slot_id": research_slot_id,
        "query_text": query_text,
        "required": bool(required),
        "expected_owner_ticker": expected_owner_ticker,
        "expected_relationship_direction": expected_relationship_direction,
        "reporting_years": [int(item) for item in reporting_years],
        "candidate_state": "candidate_only_not_evidence",
        "target_identity_in_query": False,
    }
    digest = canonical_digest(body)
    return {
        **body,
        "bundle_id": f"candidate_bundle_retrieval_{digest[:24]}",
        "bundle_digest": digest,
    }


def compile_query_bundles(
    policy: Mapping[str, Any],
    *,
    repo_root: str | Path,
) -> list[dict[str, Any]]:
    root = Path(repo_root).resolve()
    refs = dict(policy["immutable_inputs"])
    proof = _read_json(root / refs["known_case_query_facet_proof_ref"])
    _require(
        _digest_valid(proof, "proof_digest")
        and int(proof.get("bilingual_bundle_count") or 0) == 18,
        "candidate_bundle_retrieval_query_facet_proof_invalid",
    )
    requests_by_bundle: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for request in proof.get("requests") or []:
        requests_by_bundle[str(request["bundle_id"])][str(request["route_id"])] = dict(
            request
        )
    owner_bundles: list[dict[str, Any]] = []
    for source in proof.get("bundles") or []:
        route_map = requests_by_bundle[str(source["bundle_id"])]
        _require(
            {"internal_object_bm25", "internal_bm25", "internal_milvus_dense"}
            <= set(route_map),
            "candidate_bundle_retrieval_known_route_missing",
        )
        sparse_terms = list(route_map["internal_object_bm25"].get("query_texts") or [])
        sparse_terms += list(route_map["internal_bm25"].get("query_texts") or [])
        dense_terms = list(route_map["internal_milvus_dense"].get("query_texts") or [])
        query_text = " | ".join(_dedupe_terms(sparse_terms + dense_terms))
        _require(bool(query_text), "candidate_bundle_retrieval_known_query_empty")
        owner_bundles.append(
            _bundle(
                suite_id=OWNER_SUITE,
                case_key=str(source["case_key"]),
                research_slot_id=str(source["evidence_slot_id"]),
                query_text=query_text,
                required=True,
                expected_owner_ticker=str(source["evidence_owner_ticker"]),
                expected_relationship_direction=str(
                    source.get("relationship_direction") or ""
                ),
                reporting_years=source.get("reporting_fiscal_years") or [],
            )
        )

    base = load_financial_research_contract(root / refs["generalization_contract_ref"])
    held_policy, held_base, extended = load_held_out_profile_selection_policy(
        root / refs["held_out_profile_policy_ref"], repo_root=root
    )
    _require(
        base.model_dump(mode="json") == held_base.model_dump(mode="json"),
        "candidate_bundle_retrieval_generalization_contract_drift",
    )
    known_profiles = {row.case_key: row for row in base.case_profiles}
    held_profiles = {row.profile.case_key: row.profile for row in held_policy.selections}
    held_selections = {row.profile.case_key: row for row in held_policy.selections}
    packs = {row.pack_ref: row for row in extended.industry_packs}
    slot_bundles: list[dict[str, Any]] = []
    for case_key in CASES:
        if case_key in known_profiles:
            profile = known_profiles[case_key]
            compiled = compile_case_research_contract(base, case_key)
        else:
            profile = held_profiles[case_key]
            compiled = compile_external_case_profile(extended, profile)
        pack = packs[profile.industry_pack_ref]
        extension_by_slot = {row.slot_id: row for row in pack.slot_extensions}
        aliases = _dedupe_terms([case_key, *profile.subject_aliases])
        periods = [_period_text(item) for item in profile.accepted_period_ids[:2]]
        for requirement in compiled.slot_requirements:
            extension = extension_by_slot.get(requirement.slot_id)
            query_atoms = list(extension.query_atoms) if extension else []
            generic_facets = [item.replace("_", " ") for item in requirement.required_facets[:6]]
            terms = _dedupe_terms(
                [
                    *aliases[:3],
                    *periods,
                    requirement.slot_id.replace("_", " "),
                    *query_atoms,
                    *generic_facets,
                ]
            )
            query_text = " ".join(terms)
            _require(
                bool(query_text)
                and "::" not in query_text
                and "http://" not in query_text
                and "https://" not in query_text,
                "candidate_bundle_retrieval_slot_query_leakage",
            )
            years = sorted(
                {
                    int(match.group(1))
                    for value in profile.accepted_period_ids
                    for match in [re.search(r"FY(\d{4})", value)]
                    if match
                }
            )
            slot_bundles.append(
                _bundle(
                    suite_id=SLOT_SUITE,
                    case_key=case_key,
                    research_slot_id=requirement.slot_id,
                    query_text=query_text,
                    required=requirement.required,
                    reporting_years=years,
                )
            )
    bundles = owner_bundles + slot_bundles
    _require(
        len(owner_bundles) == 18
        and len(slot_bundles) == 54
        and len(bundles) == 72
        and len({row["bundle_id"] for row in bundles}) == 72
        and {row["case_key"] for row in slot_bundles} == set(CASES),
        "candidate_bundle_retrieval_compiled_bundle_count_invalid",
    )
    return bundles


def load_sparse_records(path: str | Path) -> list[dict[str, Any]]:
    records = [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    _require(
        records and all(isinstance(row, dict) for row in records),
        "candidate_bundle_retrieval_sparse_records_invalid",
    )
    return records


def validate_candidate_records(
    records: Sequence[Mapping[str, Any]],
    *,
    expected_case_counts: Mapping[str, int],
) -> list[dict[str, Any]]:
    ids = [str(row.get("object_id") or "") for row in records]
    counts = {case: sum(str(row.get("ticker")) == case for row in records) for case in CASES}
    _require(
        len(records) == sum(int(value) for value in expected_case_counts.values())
        and all(ids)
        and len(ids) == len(set(ids))
        and counts == {key: int(value) for key, value in expected_case_counts.items()},
        "candidate_bundle_retrieval_population_identity_invalid",
    )
    out: list[dict[str, Any]] = []
    for source in records:
        row = dict(source)
        metadata = dict(row.get("metadata") or {})
        _require(
            row.get("ticker") in CASES
            and metadata.get("candidate_state")
            == "bundle_candidate_only_not_evidence"
            and isinstance(metadata.get("slot_ids"), list)
            and bool(row.get("search_text"))
            and bool(metadata.get("target_id")),
            "candidate_bundle_retrieval_record_contract_invalid",
        )
        row["metadata"] = metadata
        out.append(row)
    return out


def _candidate_projection(record: Mapping[str, Any], *, rank: int, score: float) -> dict[str, Any]:
    metadata = dict(record.get("metadata") or {})
    return {
        "vector_id": str(record["object_id"]),
        "rank": int(rank),
        "score": round(float(score), 12),
        "case_key": str(record["ticker"]),
        "source_record_id": str(record.get("source_evidence_id") or ""),
        "target_id": str(metadata.get("target_id") or ""),
        "object_type": str(record.get("object_type") or ""),
        "slot_ids": list(metadata.get("slot_ids") or []),
        "facet_ids": list(metadata.get("facet_ids") or []),
        "fiscal_year": record.get("fiscal_year"),
        "period_end": str(record.get("period_end") or ""),
        "source_locator": str(metadata.get("source_locator") or ""),
        "preview": str(record.get("preview") or "")[:600],
    }


def rank_object_bm25(
    *,
    records: Sequence[Mapping[str, Any]],
    bm25: Any,
    bundles: Sequence[Mapping[str, Any]],
    top_k: int,
) -> dict[str, list[dict[str, Any]]]:
    rankings: dict[str, list[dict[str, Any]]] = {}
    for bundle in bundles:
        scores = bm25.get_scores(tokenize_candidate_text(str(bundle["query_text"])))
        _require(
            len(scores) == len(records),
            "candidate_bundle_retrieval_bm25_score_shape_invalid",
        )
        ranked = sorted(
            (
                (index, float(score))
                for index, score in enumerate(scores)
                if str(records[index].get("ticker")) == bundle["case_key"]
                and float(score) > 0.0
            ),
            key=lambda item: (-item[1], str(records[item[0]]["object_id"])),
        )[:top_k]
        rankings[str(bundle["bundle_id"])] = [
            _candidate_projection(records[index], rank=rank, score=score)
            for rank, (index, score) in enumerate(ranked, start=1)
        ]
    return rankings


def _dense_candidate_projection(hit: Mapping[str, Any], *, rank: int) -> dict[str, Any]:
    entity = dict(hit.get("entity") or {})
    slots = json.loads(str(entity.get("slot_ids_json") or "[]"))
    facets = json.loads(str(entity.get("facet_ids_json") or "[]"))
    return {
        "vector_id": str(entity.get("vector_id") or hit.get("id") or ""),
        "rank": int(rank),
        "score": round(float(hit.get("distance") or 0.0), 12),
        "case_key": str(entity.get("case_key") or ""),
        "source_record_id": "",
        "target_id": str(entity.get("target_id") or ""),
        "object_type": str(entity.get("object_type") or ""),
        "slot_ids": list(slots),
        "facet_ids": list(facets),
        "fiscal_year": int(str(entity.get("source_reporting_period_end") or "0000")[:4] or 0),
        "period_end": str(entity.get("source_reporting_period_end") or ""),
        "source_locator": str(entity.get("source_locator") or ""),
        "preview": str(entity.get("preview") or "")[:600],
    }


def candidate_business_metadata_from_specs(
    specs: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    metadata = {
        str(spec["vector_id"]): {
            "source_record_id": str(spec.get("source_record_id") or ""),
            "evidence_owner_ticker": str(spec.get("evidence_owner_ticker") or ""),
            "relationship_directions": list(spec.get("relationship_directions") or []),
            "source_type": str(spec.get("source_type") or ""),
            "publication_date": str(spec.get("publication_date") or ""),
        }
        for spec in specs
    }
    _require(
        len(metadata) == len(specs) and all(metadata),
        "candidate_bundle_retrieval_business_metadata_identity_invalid",
    )
    return metadata


def enrich_rankings_with_business_metadata(
    rankings: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    business_metadata: Mapping[str, Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    enriched: dict[str, list[dict[str, Any]]] = {}
    for bundle_id, ranking in rankings.items():
        enriched[bundle_id] = []
        for source in ranking:
            vector_id = str(source.get("vector_id") or "")
            metadata = business_metadata.get(vector_id)
            _require(
                metadata is not None,
                "candidate_bundle_retrieval_business_metadata_missing",
            )
            enriched[bundle_id].append({**dict(source), **dict(metadata)})
    return enriched


def rank_dense_bge_m3(
    *,
    bundles: Sequence[Mapping[str, Any]],
    embedder: Any,
    client: Any,
    collection_name: str,
    top_k: int,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, int]]:
    vectors = embedder.encode([str(row["query_text"]) for row in bundles])
    _require(
        len(vectors) == len(bundles),
        "candidate_bundle_retrieval_dense_embedding_count_invalid",
    )
    indexed = list(zip(bundles, vectors))
    rankings: dict[str, list[dict[str, Any]]] = {}
    calls = 0
    searched_vectors = 0
    output_fields = [
        "vector_id",
        "case_key",
        "target_id",
        "object_type",
        "quality_tier",
        "candidate_state",
        "slot_ids_json",
        "facet_ids_json",
        "source_reporting_period_end",
        "source_locator",
        "spec_digest",
        "vector_text_sha256",
        "preview",
    ]
    for case_key in CASES:
        group = [(bundle, vector) for bundle, vector in indexed if bundle["case_key"] == case_key]
        results = client.search(
            collection_name=collection_name,
            data=[vector for _bundle_row, vector in group],
            anns_field="embedding",
            limit=top_k,
            filter=f'case_key == "{case_key}"',
            output_fields=output_fields,
        )
        calls += 1
        searched_vectors += len(group)
        _require(
            len(results) == len(group),
            "candidate_bundle_retrieval_dense_search_shape_invalid",
        )
        for (bundle, _vector), hits in zip(group, results):
            projected = [
                _dense_candidate_projection(hit, rank=rank)
                for rank, hit in enumerate(hits, start=1)
            ]
            _require(
                all(row["case_key"] == case_key and row["vector_id"] for row in projected),
                "candidate_bundle_retrieval_dense_cross_case_or_identity_invalid",
            )
            rankings[str(bundle["bundle_id"])] = projected
    return rankings, {"search_invocations": calls, "query_vectors": searched_vectors}


def fuse_rankings(
    *,
    sparse: Mapping[str, Sequence[Mapping[str, Any]]],
    dense: Mapping[str, Sequence[Mapping[str, Any]]],
    rrf_k: int,
    top_k: int,
) -> dict[str, list[dict[str, Any]]]:
    _require(set(sparse) == set(dense), "candidate_bundle_retrieval_fusion_bundle_drift")
    output: dict[str, list[dict[str, Any]]] = {}
    for bundle_id in sorted(sparse):
        by_id: dict[str, dict[str, Any]] = {}
        contributions: dict[str, float] = defaultdict(float)
        route_ranks: dict[str, dict[str, int]] = defaultdict(dict)
        for lane_name, ranking in (("object_bm25", sparse[bundle_id]), ("bge_m3_dense", dense[bundle_id])):
            for ordinal, source in enumerate(ranking, start=1):
                vector_id = str(source.get("vector_id") or "")
                _require(bool(vector_id), "candidate_bundle_retrieval_fusion_identity_missing")
                rank = int(source.get("rank") or ordinal)
                contributions[vector_id] += 1.0 / (float(rrf_k) + rank)
                route_ranks[vector_id][lane_name] = rank
                by_id.setdefault(vector_id, dict(source))
        rows = sorted(by_id.values(), key=lambda row: (-contributions[row["vector_id"]], row["vector_id"]))[:top_k]
        output[bundle_id] = []
        for rank, source in enumerate(rows, start=1):
            row = dict(source)
            row.update(
                {
                    "rank": rank,
                    "score": round(contributions[row["vector_id"]], 12),
                    "route_ranks": dict(sorted(route_ranks[row["vector_id"]].items())),
                }
            )
            output[bundle_id].append(row)
    return output


def _target_matches_record(target: str, record: Mapping[str, Any]) -> bool:
    metadata = dict(record.get("metadata") or {})
    target_id = str(metadata.get("target_id") or "")
    source_record = str(record.get("source_evidence_id") or "")
    return bool(
        target
        and (
            source_record == target
            or target_id == target
            or target_id.startswith(target + "_")
        )
    )


def load_labels_after_candidate_generation(
    *,
    policy: Mapping[str, Any],
    repo_root: str | Path,
    records: Sequence[Mapping[str, Any]],
    bundles: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    root = Path(repo_root).resolve()
    refs = dict(policy["immutable_inputs"])
    qrels = _read_json(root / refs["owner_qrels_ref"])
    _require(
        int(qrels.get("target_count") or 0) == 18
        and len(qrels.get("qrels") or []) == 18,
        "candidate_bundle_retrieval_owner_qrels_shape_invalid",
    )
    labels: dict[str, dict[str, Any]] = {}
    owner_bundles = [row for row in bundles if row["suite_id"] == OWNER_SUITE]
    by_key = {
        (row["case_key"], row["research_slot_id"], row["expected_owner_ticker"]): row
        for row in owner_bundles
    }
    for qrel in qrels["qrels"]:
        key = (
            str(qrel["case_key"]),
            str(qrel["evidence_slot_id"]),
            str(qrel["evidence_owner_ticker"]),
        )
        bundle = by_key.get(key)
        _require(bundle is not None, "candidate_bundle_retrieval_owner_query_binding_missing")
        selected = dict(qrel.get("selected_candidate") or {})
        target = str(
            selected.get("source_key")
            or selected.get("source_evidence_id")
            or selected.get("evidence_id")
            or ""
        )
        relevant = sorted(
            str(record["object_id"])
            for record in records
            if str(record.get("ticker")) == qrel["case_key"]
            and _target_matches_record(target, record)
        )
        labels[str(bundle["bundle_id"])] = {
            "label_source": "owner_reviewed_qrels_v1_3",
            "owner_reviewed": True,
            "relevant_vector_ids": relevant,
            "target_reference": target,
            "target_identity_exposed_to_query": False,
        }
    for bundle in (row for row in bundles if row["suite_id"] == SLOT_SUITE):
        relevant = sorted(
            str(record["object_id"])
            for record in records
            if str(record.get("ticker")) == bundle["case_key"]
            and bundle["research_slot_id"]
            in (record.get("metadata") or {}).get("slot_ids", [])
        )
        labels[str(bundle["bundle_id"])] = {
            "label_source": "frozen_candidate_manifest_slot_metadata_diagnostic",
            "owner_reviewed": False,
            "relevant_vector_ids": relevant,
            "target_reference": "",
            "target_identity_exposed_to_query": False,
        }
    _require(
        len(labels) == len(bundles) == 72,
        "candidate_bundle_retrieval_label_count_invalid",
    )
    return labels


def score_ranking(
    ranking: Sequence[Mapping[str, Any]],
    relevant_ids: Sequence[str],
    *,
    top_k: int,
) -> dict[str, Any]:
    relevant = set(relevant_ids)
    ids = [str(row.get("vector_id") or "") for row in ranking[:top_k]]
    hits = [index + 1 for index, value in enumerate(ids) if value in relevant]
    recall = len(set(ids) & relevant) / len(relevant) if relevant else None
    precision = len(set(ids) & relevant) / top_k if relevant else None
    mrr = 1.0 / hits[0] if hits else (0.0 if relevant else None)
    dcg = sum(1.0 / math.log2(rank + 1) for rank in hits)
    ideal = sum(1.0 / math.log2(rank + 1) for rank in range(1, min(len(relevant), top_k) + 1))
    return {
        "candidate_ceiling": len(relevant),
        "relevant_retrieved": len(set(ids) & relevant),
        "recall_at_10": round(recall, 8) if recall is not None else None,
        "precision_at_10": round(precision, 8) if precision is not None else None,
        "mrr_at_10": round(mrr, 8) if mrr is not None else None,
        "ndcg_at_10": round(dcg / ideal, 8) if ideal else None,
        "first_relevant_rank": hits[0] if hits else None,
    }


def _source_prefix(value: str) -> str:
    first = re.split(r"::|_", value.upper(), maxsplit=1)[0]
    return first.strip()


def attribute_ranking_error(
    *,
    bundle: Mapping[str, Any],
    label: Mapping[str, Any],
    ranking: Sequence[Mapping[str, Any]],
) -> dict[str, Any] | None:
    relevant = set(label.get("relevant_vector_ids") or [])
    if not relevant:
        return {
            "error_class": (
                "owner_target_absent_from_93_population"
                if bundle["suite_id"] == OWNER_SUITE
                else "required_candidate_slot_absent_from_93_population"
                if bundle["required"]
                else "optional_candidate_slot_absent_from_93_population"
            ),
            "business_explanation": (
                "The frozen index has no eligible object for this research target; ranking cannot recover content that is absent upstream."
            ),
            "observed_top_candidate": None,
        }
    first_relevant = next(
        (index for index, row in enumerate(ranking, start=1) if row.get("vector_id") in relevant),
        None,
    )
    if first_relevant == 1:
        return None
    top = dict(ranking[0]) if ranking else None
    if top is None:
        error_class = "typed_zero_result_despite_candidate_ceiling"
        explanation = "Eligible candidates exist, but this retrieval lane returned no positive-scoring result."
    elif bundle["suite_id"] == OWNER_SUITE and bundle.get("expected_owner_ticker"):
        observed_owner = str(top.get("evidence_owner_ticker") or "").upper()
        if not observed_owner:
            observed_owner = _source_prefix(
                str(top.get("target_id") or top.get("source_record_id") or "")
            )
        if observed_owner and observed_owner != str(bundle["expected_owner_ticker"]).upper():
            error_class = "wrong_counterparty_or_relationship_direction"
            explanation = "The result is stored under the case but comes from a different disclosure owner than this relationship query requires."
        elif (
            bundle.get("expected_relationship_direction")
            and top.get("relationship_directions")
            and bundle["expected_relationship_direction"]
            not in set(top["relationship_directions"])
        ):
            error_class = "wrong_counterparty_or_relationship_direction"
            explanation = "The disclosure owner is plausible, but the stored economic relationship points in a different direction than the research question."
        else:
            years = set(int(value) for value in bundle.get("reporting_years") or [])
            observed_year = int(top.get("fiscal_year") or 0)
            if years and observed_year and observed_year not in years:
                error_class = "wrong_reporting_period"
                explanation = "The result has the right disclosure owner but comes from a different reporting period."
            else:
                error_class = "adjacent_or_generic_content_ranked_before_target"
                explanation = "A related object is ranked before the precise target, so the researcher sees adjacent context before the required fact."
    elif bundle["research_slot_id"] not in set(top.get("slot_ids") or []):
        error_class = "same_case_wrong_research_slot"
        explanation = "The result belongs to the same research case but answers a different financial question."
    else:
        years = set(int(value) for value in bundle.get("reporting_years") or [])
        observed_year = int(top.get("fiscal_year") or 0)
        if years and observed_year and observed_year not in years:
            error_class = "wrong_reporting_period"
            explanation = "The result is topically related but comes from a different reporting period."
        else:
            error_class = "adjacent_or_generic_content_ranked_before_target"
            explanation = "A related or generic object is ranked before a more decision-useful object for the same slot."
    return {
        "error_class": error_class,
        "business_explanation": explanation,
        "first_relevant_rank": first_relevant,
        "observed_top_candidate": top,
    }


def _aggregate_rows(rows: Sequence[Mapping[str, Any]], method: str) -> dict[str, Any]:
    scored = [row["methods"][method] for row in rows if row["methods"][method]["candidate_ceiling"] > 0]
    if not scored:
        return {
            "scored_bundle_count": 0,
            "zero_ceiling_bundle_count": len(rows),
            "macro_recall_at_10": None,
            "macro_mrr_at_10": None,
            "macro_ndcg_at_10": None,
        }
    return {
        "scored_bundle_count": len(scored),
        "zero_ceiling_bundle_count": len(rows) - len(scored),
        "macro_recall_at_10": round(sum(row["recall_at_10"] for row in scored) / len(scored), 8),
        "macro_mrr_at_10": round(sum(row["mrr_at_10"] for row in scored) / len(scored), 8),
        "macro_ndcg_at_10": round(sum(row["ndcg_at_10"] for row in scored) / len(scored), 8),
        "target_weighted_recall_at_10": round(
            sum(row["relevant_retrieved"] for row in scored)
            / sum(row["candidate_ceiling"] for row in scored),
            8,
        ),
    }


def evaluate_rankings(
    *,
    bundles: Sequence[Mapping[str, Any]],
    labels: Mapping[str, Mapping[str, Any]],
    sparse: Mapping[str, Sequence[Mapping[str, Any]]],
    dense: Mapping[str, Sequence[Mapping[str, Any]]],
    fusion: Mapping[str, Sequence[Mapping[str, Any]]],
    top_k: int,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for bundle in bundles:
        bundle_id = str(bundle["bundle_id"])
        label = dict(labels[bundle_id])
        relevant = list(label["relevant_vector_ids"])
        exact = [
            {"vector_id": vector_id, "rank": rank, "score": 1.0}
            for rank, vector_id in enumerate(relevant[:top_k], start=1)
        ]
        methods = {
            "typed_exact_ceiling": score_ranking(exact, relevant, top_k=top_k),
            "object_bm25": score_ranking(sparse[bundle_id], relevant, top_k=top_k),
            "bge_m3_dense": score_ranking(dense[bundle_id], relevant, top_k=top_k),
            "fusion": score_ranking(fusion[bundle_id], relevant, top_k=top_k),
        }
        errors = {
            method: value
            for method, ranking in (
                ("object_bm25", sparse[bundle_id]),
                ("bge_m3_dense", dense[bundle_id]),
                ("fusion", fusion[bundle_id]),
            )
            for value in [attribute_ranking_error(bundle=bundle, label=label, ranking=ranking)]
            if value is not None
        }
        rows.append(
            {
                "bundle": dict(bundle),
                "label": label,
                "methods": methods,
                "errors": errors,
                "top_candidates": {
                    "object_bm25": list(sparse[bundle_id])[:3],
                    "bge_m3_dense": list(dense[bundle_id])[:3],
                    "fusion": list(fusion[bundle_id])[:3],
                },
            }
        )
    methods = ("typed_exact_ceiling", "object_bm25", "bge_m3_dense", "fusion")
    aggregate = {
        suite: {
            method: _aggregate_rows(
                [row for row in rows if row["bundle"]["suite_id"] == suite], method
            )
            for method in methods
        }
        for suite in (OWNER_SUITE, SLOT_SUITE)
    }
    by_case = {
        case: {
            method: _aggregate_rows(
                [row for row in rows if row["bundle"]["case_key"] == case], method
            )
            for method in methods
        }
        for case in CASES
    }
    required_slot_rows = [
        row
        for row in rows
        if row["bundle"]["suite_id"] == SLOT_SUITE and row["bundle"]["required"]
    ]
    coverage = {
        "required_slots_total": len(required_slot_rows),
        "required_slots_with_candidate": sum(
            row["methods"]["typed_exact_ceiling"]["candidate_ceiling"] > 0
            for row in required_slot_rows
        ),
        "required_slots_without_candidate": sum(
            row["methods"]["typed_exact_ceiling"]["candidate_ceiling"] == 0
            for row in required_slot_rows
        ),
        "by_case": {
            case: {
                "required_slots": 8,
                "with_candidate": sum(
                    row["methods"]["typed_exact_ceiling"]["candidate_ceiling"] > 0
                    for row in required_slot_rows
                    if row["bundle"]["case_key"] == case
                ),
            }
            for case in CASES
        },
    }
    sparse_owner = aggregate[OWNER_SUITE]["object_bm25"]
    dense_owner = aggregate[OWNER_SUITE]["bge_m3_dense"]
    fusion_owner = aggregate[OWNER_SUITE]["fusion"]
    sparse_slots = aggregate[SLOT_SUITE]["object_bm25"]
    dense_slots = aggregate[SLOT_SUITE]["bge_m3_dense"]
    fusion_slots = aggregate[SLOT_SUITE]["fusion"]

    def improves(candidate: Mapping[str, Any], baseline: Mapping[str, Any]) -> bool:
        return bool(
            candidate.get("macro_recall_at_10") is not None
            and (
                candidate["macro_recall_at_10"] > baseline["macro_recall_at_10"]
                or (
                    candidate["macro_recall_at_10"] == baseline["macro_recall_at_10"]
                    and candidate["macro_mrr_at_10"] > baseline["macro_mrr_at_10"]
                )
            )
        )

    adoption = {
        "object_bm25_retained_as_baseline": True,
        "bge_m3_dense_has_declared_suite_gain": improves(dense_owner, sparse_owner)
        or improves(dense_slots, sparse_slots),
        "fusion_has_declared_suite_gain": improves(fusion_owner, sparse_owner)
        or improves(fusion_slots, sparse_slots),
        "weight_tuning_performed": False,
        "reranker_used": False,
    }
    return {
        "bundle_rows": rows,
        "aggregate": aggregate,
        "by_case": by_case,
        "candidate_ceiling": coverage,
        "adoption": adoption,
    }


def materialize_candidate_bundle_retrieval_implementation_proof(
    *,
    policy: Mapping[str, Any],
    repo_root: str | Path,
) -> dict[str, Any]:
    """Exercise the complete evaluator shape without loading BGE or Milvus.

    The proof deliberately uses the real frozen 93-object population and the real
    ObjectBM25 implementation.  Its synthetic dense lane only proves deterministic
    fusion/evaluation plumbing; it is never reported as a retrieval-quality result.
    """
    from rank_bm25 import BM25Okapi

    from sec_agent.s1_candidate_bundle_physical_index import (
        candidate_spec_to_sparse_record,
        load_bound_private_manifest,
        load_physical_index_policy,
    )

    root = Path(repo_root).resolve()
    build_policy_path = root / policy["immutable_inputs"]["physical_build_policy_ref"]
    build_policy = load_physical_index_policy(build_policy_path, repo_root=root)
    _manifest, specs = load_bound_private_manifest(build_policy, repo_root=root)
    records = validate_candidate_records(
        [candidate_spec_to_sparse_record(spec) for spec in specs],
        expected_case_counts=policy["physical_index_binding"]["expected_case_counts"],
    )
    bundles = compile_query_bundles(policy, repo_root=root)
    bm25 = BM25Okapi(
        [tokenize_candidate_text(str(record["search_text"])) for record in records]
    )
    sparse = rank_object_bm25(
        records=records,
        bm25=bm25,
        bundles=bundles,
        top_k=int(policy["ranking_contract"]["top_k"]),
    )
    business_metadata = candidate_business_metadata_from_specs(specs)
    sparse = enrich_rankings_with_business_metadata(
        sparse, business_metadata=business_metadata
    )
    # This lane is intentionally derived before labels are loaded.  It tests the
    # exact 72-bundle evaluation/fusion shape, not semantic dense quality.
    dense = {
        bundle_id: [
            {**dict(row), "score": round(1.0 / int(row["rank"]), 12)}
            for row in reversed(ranking)
        ]
        for bundle_id, ranking in sparse.items()
    }
    dense = enrich_rankings_with_business_metadata(
        dense, business_metadata=business_metadata
    )
    fusion = fuse_rankings(
        sparse=sparse,
        dense=dense,
        rrf_k=int(policy["ranking_contract"]["rrf_k"]),
        top_k=int(policy["ranking_contract"]["top_k"]),
    )
    candidate_generation_digest = canonical_digest(
        {"bundles": bundles, "sparse": sparse, "dense": dense, "fusion": fusion}
    )
    labels = load_labels_after_candidate_generation(
        policy=policy,
        repo_root=root,
        records=records,
        bundles=bundles,
    )
    evaluation = evaluate_rankings(
        bundles=bundles,
        labels=labels,
        sparse=sparse,
        dense=dense,
        fusion=fusion,
        top_k=int(policy["ranking_contract"]["top_k"]),
    )

    mutations: list[dict[str, Any]] = []
    duplicate = [dict(row) for row in records] + [dict(records[0])]
    try:
        validate_candidate_records(
            duplicate,
            expected_case_counts=policy["physical_index_binding"]["expected_case_counts"],
        )
    except CandidateBundleRetrievalEvaluationError as exc:
        mutations.append(
            {
                "mutation": "duplicate_candidate",
                "status": "rejected",
                "code": exc.code,
            }
        )
    else:
        raise CandidateBundleRetrievalEvaluationError(
            "candidate_bundle_retrieval_duplicate_mutation_not_rejected"
        )

    contaminated = [dict(row) for row in records]
    contaminated[0] = {**contaminated[0], "ticker": "MU"}
    try:
        validate_candidate_records(
            contaminated,
            expected_case_counts=policy["physical_index_binding"]["expected_case_counts"],
        )
    except CandidateBundleRetrievalEvaluationError as exc:
        mutations.append(
            {
                "mutation": "cross_case_population_contamination",
                "status": "rejected",
                "code": exc.code,
            }
        )
    else:
        raise CandidateBundleRetrievalEvaluationError(
            "candidate_bundle_retrieval_cross_case_mutation_not_rejected"
        )

    first_bundle = str(bundles[0]["bundle_id"])
    reversed_sparse = {
        key: list(reversed(value)) if key == first_bundle else list(value)
        for key, value in sparse.items()
    }
    reversed_dense = {
        key: list(reversed(value)) if key == first_bundle else list(value)
        for key, value in dense.items()
    }
    stable_fusion = fuse_rankings(
        sparse=reversed_sparse,
        dense=reversed_dense,
        rrf_k=int(policy["ranking_contract"]["rrf_k"]),
        top_k=int(policy["ranking_contract"]["top_k"]),
    )
    _require(
        stable_fusion == fusion,
        "candidate_bundle_retrieval_fusion_order_mutation_unstable",
    )
    mutations.append(
        {
            "mutation": "candidate_iteration_order_reversal",
            "status": "same_output",
            "digest": canonical_digest(stable_fusion),
        }
    )

    coverage = evaluation["candidate_ceiling"]
    _require(
        coverage["required_slots_total"] == 48
        and coverage["required_slots_with_candidate"] == 36
        and coverage["by_case"]
        == {
            "DELL": {"required_slots": 8, "with_candidate": 8},
            "MU": {"required_slots": 8, "with_candidate": 8},
            "NVDA": {"required_slots": 8, "with_candidate": 8},
            "ORCL": {"required_slots": 8, "with_candidate": 5},
            "ASML": {"required_slots": 8, "with_candidate": 3},
            "ANET": {"required_slots": 8, "with_candidate": 4},
        },
        "candidate_bundle_retrieval_candidate_ceiling_unexpected",
    )
    owner_rows = [
        row
        for row in evaluation["bundle_rows"]
        if row["bundle"]["suite_id"] == OWNER_SUITE
    ]
    _require(
        sum(row["methods"]["typed_exact_ceiling"]["candidate_ceiling"] > 0 for row in owner_rows)
        == 16,
        "candidate_bundle_retrieval_owner_target_ceiling_unexpected",
    )
    body = {
        "schema_version": IMPLEMENTATION_PROOF_SCHEMA,
        "contract_ref": policy["contract_ref"],
        "run_scope": policy["run_scope"],
        "attempt_id": policy["attempt_id"],
        "recorded_at": policy["recorded_at"],
        "status": "pass_zero_model_full_shape_implementation_proof",
        "bindings": {
            "policy_digest": canonical_digest(policy),
            "candidate_count": len(records),
            "candidate_digest": canonical_digest(records),
            "query_bundle_count": len(bundles),
            "query_bundle_digest": canonical_digest(bundles),
        },
        "candidate_generation": {
            "completed_before_label_load": True,
            "candidate_generation_digest": candidate_generation_digest,
            "gold_or_target_identity_in_query_count": 0,
        },
        "business_ceiling": coverage,
        "owner_target_ceiling": {
            "total": 18,
            "present": 16,
            "absent": 2,
        },
        "mutation_receipts": mutations,
        "observed_calls": {
            "network": 0,
            "provider": 0,
            "llm_model": 0,
            "embedding_model_loads": 0,
            "milvus_search_invocations": 0,
            "rerank": 0,
            "evidence_promotion": 0,
        },
        "stage_acceptance": {
            "query_compiler": True,
            "population_validation": True,
            "object_bm25_full_shape": True,
            "dense_contract_unit_proven": True,
            "fusion_stability": True,
            "label_separation": True,
            "business_error_attribution": True,
            "real_dense_quality_measured": False,
            "exact_execution_authority_eligible": True,
        },
        "known_boundary": (
            "The synthetic dense lane proves evaluator shape only. It does not measure "
            "BGE-M3 quality, Evidence usefulness, external supplementation, DeepSeek "
            "research quality, Workbench behavior or release readiness."
        ),
    }
    return {**body, "proof_digest": canonical_digest(body)}


def _default_client_factory(uri: str) -> Any:
    from pymilvus import MilvusClient

    return MilvusClient(uri=uri)


def execute_candidate_bundle_retrieval_evaluation(
    *,
    policy: Mapping[str, Any],
    repo_root: str | Path,
    output_path: str | Path | None = None,
    embedder_factory: Callable[..., Any] = LocalBgeM3Embedder,
    client_factory: Callable[[str], Any] = _default_client_factory,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    if output_path is not None:
        _require(
            not Path(output_path).exists(),
            "candidate_bundle_retrieval_result_preexists",
        )
    started = time.perf_counter()
    binding = dict(policy["physical_index_binding"])
    runtime = dict(policy["runtime_contract"])
    physical_root = Path(binding["final_root"])
    sparse_root = physical_root / binding["sparse_subdir"]
    dense_db = physical_root / binding["dense_subdir"] / binding["milvus_db_filename"]
    build_policy = _read_json(root / policy["immutable_inputs"]["physical_build_policy_ref"])
    artifact = inspect_physical_store_artifact(
        dense_db,
        contract=build_policy["index_contract"]["physical_store_artifact"],
        expected_count=int(binding["expected_candidate_count"]),
        embedding_dimension=int(runtime["embedding_dimension"]),
    )
    _require(
        artifact["artifact_digest"] == binding["expected_artifact_digest"],
        "candidate_bundle_retrieval_physical_artifact_drift",
    )
    records = validate_candidate_records(
        load_sparse_records(sparse_root / "records.slim.jsonl"),
        expected_case_counts=binding["expected_case_counts"],
    )
    _require(
        canonical_digest(records) == binding["expected_sparse_record_digest"],
        "candidate_bundle_retrieval_sparse_record_digest_drift",
    )
    bundles = compile_query_bundles(policy, repo_root=root)
    with (sparse_root / "bm25.pkl").open("rb") as handle:
        bm25 = pickle.load(handle)
    top_k = int(policy["ranking_contract"]["top_k"])
    sparse = rank_object_bm25(records=records, bm25=bm25, bundles=bundles, top_k=top_k)
    embedder = embedder_factory(
        model_path=runtime["embedding_model_linux_ref"],
        expected_dimension=int(runtime["embedding_dimension"]),
        batch_size=int(runtime["embedding_batch_size"]),
        normalize=bool(runtime["normalize_embeddings"]),
        device=runtime["embedding_device"],
    )
    client = client_factory(str(dense_db))
    collection_loaded = False
    try:
        load_collection = getattr(client, "load_collection", None)
        if callable(load_collection):
            load_collection(collection_name=binding["collection_name"])
            collection_loaded = True
        dense, dense_calls = rank_dense_bge_m3(
            bundles=bundles,
            embedder=embedder,
            client=client,
            collection_name=binding["collection_name"],
            top_k=top_k,
        )
    finally:
        release_collection = getattr(client, "release_collection", None)
        if collection_loaded and callable(release_collection):
            release_collection(collection_name=binding["collection_name"])
        close = getattr(client, "close", None)
        if callable(close):
            close()
    from sec_agent.s1_candidate_bundle_physical_index import (
        load_bound_private_manifest,
        load_physical_index_policy,
    )

    manifest_policy = load_physical_index_policy(
        root / policy["immutable_inputs"]["physical_build_policy_ref"],
        repo_root=root,
    )
    _manifest, specs = load_bound_private_manifest(manifest_policy, repo_root=root)
    business_metadata = candidate_business_metadata_from_specs(specs)
    sparse = enrich_rankings_with_business_metadata(
        sparse, business_metadata=business_metadata
    )
    dense = enrich_rankings_with_business_metadata(
        dense, business_metadata=business_metadata
    )
    fusion = fuse_rankings(
        sparse=sparse,
        dense=dense,
        rrf_k=int(policy["ranking_contract"]["rrf_k"]),
        top_k=top_k,
    )
    candidate_generation_digest = canonical_digest(
        {
            "bundles": bundles,
            "sparse": sparse,
            "dense": dense,
            "fusion": fusion,
        }
    )
    labels = load_labels_after_candidate_generation(
        policy=policy,
        repo_root=root,
        records=records,
        bundles=bundles,
    )
    evaluation = evaluate_rankings(
        bundles=bundles,
        labels=labels,
        sparse=sparse,
        dense=dense,
        fusion=fusion,
        top_k=top_k,
    )
    ceiling = dict(policy["execution_ceiling"])
    observed_calls = {
        "embedding_model_loads": 1,
        "embedding_encode_invocations": int(getattr(embedder, "calls", 0)),
        "embedding_vectors": int(getattr(embedder, "vectors", 0)),
        "object_bm25_queries": len(bundles),
        "milvus_search_invocations": dense_calls["search_invocations"],
        "milvus_query_vectors": dense_calls["query_vectors"],
        "network": 0,
        "provider": 0,
        "llm_model": 0,
        "document_fetch": 0,
        "rerank": 0,
        "evidence_promotion": 0,
    }
    _require(
        all(observed_calls[key] == int(ceiling[key]) for key in observed_calls),
        "candidate_bundle_retrieval_call_ceiling_or_shape_invalid",
    )
    body = {
        "schema_version": RESULT_SCHEMA,
        "contract_ref": policy["contract_ref"],
        "run_scope": policy["run_scope"],
        "attempt_id": policy["attempt_id"],
        "recorded_at": policy["recorded_at"],
        "status": "terminal_succeeded_six_case_retrieval_business_evaluation",
        "physical_binding": {
            "candidate_count": len(records),
            "artifact_digest": artifact["artifact_digest"],
            "sparse_record_digest": canonical_digest(records),
            "case_counts": dict(binding["expected_case_counts"]),
        },
        "query_compilation": {
            "bundle_count": len(bundles),
            "owner_qrel_suite_bundles": sum(row["suite_id"] == OWNER_SUITE for row in bundles),
            "canonical_slot_suite_bundles": sum(row["suite_id"] == SLOT_SUITE for row in bundles),
            "bundle_digest": canonical_digest(bundles),
            "gold_or_target_identity_in_query_count": 0,
        },
        "candidate_generation": {
            "completed_before_label_load": True,
            "candidate_generation_digest": candidate_generation_digest,
            "qrels_or_labels_used_to_change_query_or_ranking": False,
        },
        "evaluation": evaluation,
        "observed_calls": observed_calls,
        "resource": {
            "embedding_model_load_ms": round(float(getattr(embedder, "load_ms", 0.0)), 3),
            "embedding_ms": round(float(getattr(embedder, "embedding_ms", 0.0)), 3),
            "wall_time_ms": round((time.perf_counter() - started) * 1000, 3),
        },
        "stage_acceptance": {
            "physical_population_reverified": True,
            "candidate_ceiling_measured": True,
            "retrieval_measurement_terminal": True,
            "business_content_quality_accepted": False,
            "evidence_pack_assembly_admitted_with_typed_gaps": True,
            "evidence_pack": False,
            "external_residual_supplement": False,
            "deepseek_research": False,
            "release": False,
        },
        "known_boundary": policy["known_boundary"],
    }
    result = {**body, "result_digest": canonical_digest(body)}
    validate_candidate_bundle_retrieval_evaluation_result(result, policy=policy)
    if output_path is not None:
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".tmp")
        temporary.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(target)
    return result


def materialize_candidate_bundle_retrieval_terminal_result(
    *,
    policy: Mapping[str, Any],
    authority: Mapping[str, Any],
    repo_root: str | Path,
    output_path: str | Path,
    embedder_factory: Callable[..., Any] = LocalBgeM3Embedder,
    client_factory: Callable[[str], Any] = _default_client_factory,
) -> dict[str, Any]:
    output = Path(output_path)
    _require(
        not output.exists(),
        "candidate_bundle_retrieval_terminal_result_preexists",
    )
    validate_candidate_bundle_retrieval_evaluation_authority(
        authority,
        policy=policy,
        repo_root=repo_root,
    )
    started = time.perf_counter()
    try:
        result = execute_candidate_bundle_retrieval_evaluation(
            policy=policy,
            repo_root=repo_root,
            embedder_factory=embedder_factory,
            client_factory=client_factory,
        )
        success_body = {
            key: value for key, value in result.items() if key != "result_digest"
        }
        success_body["authority_digest"] = authority["authority_digest"]
        result = {**success_body, "result_digest": canonical_digest(success_body)}
        validate_candidate_bundle_retrieval_evaluation_result(result, policy=policy)
    except Exception as exc:  # terminal envelope must survive unexpected local failures
        code = (
            exc.code
            if isinstance(exc, CandidateBundleRetrievalEvaluationError)
            else f"unexpected_{type(exc).__name__}"
        )
        failure_body = {
            "schema_version": RESULT_SCHEMA,
            "contract_ref": policy["contract_ref"],
            "run_scope": policy["run_scope"],
            "attempt_id": policy["attempt_id"],
            "recorded_at": policy["recorded_at"],
            "status": "terminal_failed_six_case_retrieval_business_evaluation",
            "authority_digest": authority["authority_digest"],
            "failure": {
                "phase": "local_sparse_dense_fusion_evaluation",
                "code": code,
                "exception_type": type(exc).__name__,
                "message": str(exc)[:2000],
                "automatic_retry": False,
            },
            "resource": {
                "wall_time_ms": round((time.perf_counter() - started) * 1000, 3)
            },
            "stage_acceptance": {
                "retrieval_measurement_terminal": False,
                "business_content_quality_accepted": False,
                "evidence_pack": False,
                "external_residual_supplement": False,
                "deepseek_research": False,
                "release": False,
            },
            "known_boundary": policy["known_boundary"],
        }
        result = {**failure_body, "result_digest": canonical_digest(failure_body)}
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)
    return result


def validate_candidate_bundle_retrieval_evaluation_result(
    result: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    _require(
        result.get("schema_version") == RESULT_SCHEMA
        and result.get("status")
        == "terminal_succeeded_six_case_retrieval_business_evaluation"
        and result.get("attempt_id") == policy.get("attempt_id")
        and _digest_valid(result, "result_digest")
        and (result.get("query_compilation") or {}).get("bundle_count") == 72
        and (result.get("candidate_generation") or {}).get("completed_before_label_load")
        is True
        and len((result.get("evaluation") or {}).get("bundle_rows") or []) == 72
        and (result.get("stage_acceptance") or {}).get("retrieval_measurement_terminal")
        is True
        and (result.get("stage_acceptance") or {}).get("business_content_quality_accepted")
        is False,
        "candidate_bundle_retrieval_terminal_result_invalid",
    )
    return dict(result)


__all__ = [
    "AUTHORITY_SCHEMA",
    "CASES",
    "CandidateBundleRetrievalEvaluationError",
    "OWNER_SUITE",
    "POLICY_SCHEMA",
    "RESULT_SCHEMA",
    "IMPLEMENTATION_PROOF_SCHEMA",
    "RUN_SCOPE",
    "SLOT_SUITE",
    "attribute_ranking_error",
    "candidate_business_metadata_from_specs",
    "compile_query_bundles",
    "evaluate_rankings",
    "enrich_rankings_with_business_metadata",
    "execute_candidate_bundle_retrieval_evaluation",
    "fuse_rankings",
    "load_candidate_bundle_retrieval_evaluation_policy",
    "load_labels_after_candidate_generation",
    "materialize_candidate_bundle_retrieval_implementation_proof",
    "materialize_candidate_bundle_retrieval_terminal_result",
    "rank_dense_bge_m3",
    "rank_object_bm25",
    "score_ranking",
    "inspect_candidate_bundle_retrieval_environment",
    "validate_candidate_bundle_retrieval_evaluation_authority",
    "validate_candidate_bundle_retrieval_evaluation_result",
    "validate_candidate_records",
]
