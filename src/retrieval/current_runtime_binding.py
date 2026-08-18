from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .query_plan import canonical_digest


POLICY_SCHEMA_VERSION = "fin_ia_s1_current_runtime_binding_policy_v1_1"
RECEIPT_SCHEMA_VERSION = "fin_ia_s1_current_runtime_binding_receipt_v1_1"


class CurrentS1RuntimeBindingError(ValueError):
    """Fail-closed error for the current S1 product snapshot boundary."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CurrentS1RuntimeBindingError(code)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CurrentS1RuntimeBindingError(
            f"current_s1_runtime_json_invalid:{path.name}"
        ) from exc
    _require(isinstance(value, dict), f"current_s1_runtime_json_invalid:{path.name}")
    return value


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                _require(
                    isinstance(value, dict),
                    f"current_s1_runtime_jsonl_row_invalid:{path.name}:{line_number}",
                )
                yield value
    except CurrentS1RuntimeBindingError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CurrentS1RuntimeBindingError(
            f"current_s1_runtime_jsonl_invalid:{path.name}"
        ) from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolve(root: Path, value: str) -> Path:
    normalized = str(value).strip().replace("\\", "/")
    candidate = Path(normalized)
    _require(
        bool(normalized)
        and not candidate.is_absolute()
        and ".." not in candidate.parts,
        "current_s1_runtime_ref_invalid",
    )
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise CurrentS1RuntimeBindingError(
            "current_s1_runtime_ref_escape"
        ) from exc
    _require(resolved.is_file(), f"current_s1_runtime_asset_missing:{normalized}")
    return resolved


def _asset_binding(root: Path, ref: str) -> dict[str, Any]:
    path = _resolve(root, ref)
    return {
        "ref": path.relative_to(root).as_posix(),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def _registry_rows(registry: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows = registry.get("resources")
    _require(isinstance(rows, list), "current_s1_runtime_registry_rows_invalid")
    output: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        _require(
            isinstance(row, Mapping)
            and bool(str(row.get("resource_id") or ""))
            and str(row.get("resource_id")) not in output,
            "current_s1_runtime_registry_row_invalid",
        )
        output[str(row["resource_id"])] = row
    return output


def _validate_registered_asset(
    *,
    asset: Mapping[str, Any],
    registry_row: Mapping[str, Any],
) -> None:
    _require(
        registry_row.get("repo_relative_path") == asset["ref"]
        and registry_row.get("sha256") == asset["sha256"]
        and registry_row.get("bytes") == asset["bytes"],
        f"current_s1_runtime_registry_binding_drift:{registry_row.get('resource_id')}",
    )


def _source_lineage_summary(
    *,
    source_records_path: Path,
    compiled_objects_path: Path,
) -> dict[str, Any]:
    source_ids: set[str] = set()
    for row in _read_jsonl(source_records_path):
        source_id = str(row.get("evidence_id") or "").strip()
        _require(source_id, "current_s1_runtime_source_record_id_missing")
        _require(
            source_id not in source_ids,
            "current_s1_runtime_source_record_id_duplicate",
        )
        source_ids.add(source_id)

    base_ids: set[str] = set()
    lineage_ids: set[str] = set()
    compiled_ids: set[str] = set()
    kind_counts: dict[str, int] = {}
    compiled_rows = 0
    for row in _read_jsonl(compiled_objects_path):
        compiled_id = str(row.get("compiled_object_id") or "").strip()
        base = row.get("base_object_view")
        _require(
            compiled_id
            and compiled_id not in compiled_ids
            and isinstance(base, Mapping),
            "current_s1_runtime_compiled_object_identity_invalid",
        )
        compiled_ids.add(compiled_id)
        compiled_rows += 1
        source_id = str(base.get("source_record_id") or "").strip()
        _require(source_id, "current_s1_runtime_compiled_source_id_missing")
        base_ids.add(source_id)
        raw_lineage = row.get("lineage_source_record_ids") or (source_id,)
        _require(
            isinstance(raw_lineage, list) and bool(raw_lineage),
            "current_s1_runtime_compiled_lineage_invalid",
        )
        lineage_ids.update(str(value).strip() for value in raw_lineage)
        kind = str(row.get("object_kind") or "").strip()
        _require(kind, "current_s1_runtime_compiled_kind_missing")
        kind_counts[kind] = kind_counts.get(kind, 0) + 1

    missing = sorted(source_ids - lineage_ids)
    unknown = sorted(lineage_ids - source_ids)
    return {
        "source_record_count": len(source_ids),
        "compiled_object_count": compiled_rows,
        "compiled_base_source_record_count": len(base_ids),
        "compiled_lineage_source_record_count": len(lineage_ids),
        "deduplicated_source_records_carried_only_by_lineage": len(
            source_ids - base_ids
        ),
        "compiled_object_kind_counts": dict(sorted(kind_counts.items())),
        "source_records_missing_from_compiled_lineage": missing,
        "compiled_lineage_ids_outside_bound_source_store": unknown,
        "all_source_records_lineage_bound": not missing and not unknown,
    }


def load_current_s1_runtime_binding_policy(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    value = dict(payload)
    _require(
        value.get("schema_version") == POLICY_SCHEMA_VERSION
        and value.get("status") == "current_product_binding_policy",
        "current_s1_runtime_policy_identity_invalid",
    )
    assets = value.get("assets")
    routes = value.get("runtime_route_capabilities")
    required_assets = {
        "runtime_registry",
        "retrieval_snapshot",
        "object_compiler_result",
        "hybrid_runtime_policy",
        "route_policy",
        "s2_fact_mart_result",
        "current_evidence_pack_result",
        "current_reviewed_anchor_catalog",
        "product_readiness_catalog",
        "dell_product_readiness",
        "mu_product_readiness",
        "nvda_product_readiness",
    }
    _require(
        isinstance(assets, Mapping)
        and set(assets) == required_assets
        and all(
            isinstance(row, Mapping) and bool(str(row.get("ref") or ""))
            for row in assets.values()
        ),
        "current_s1_runtime_policy_assets_invalid",
    )
    _require(
        isinstance(routes, list)
        and bool(routes)
        and len(routes)
        == len({str(row.get("declared_route")) for row in routes if isinstance(row, Mapping)}),
        "current_s1_runtime_route_capabilities_invalid",
    )
    allowed_states = {"available", "separate_sibling", "not_configured"}
    for row in routes:
        _require(
            isinstance(row, Mapping)
            and str(row.get("capability_state")) in allowed_states
            and bool(str(row.get("declared_route") or ""))
            and bool(str(row.get("owning_stage") or "")),
            "current_s1_runtime_route_capability_invalid",
        )
    return value


def build_current_s1_runtime_binding_receipt(
    repository_root: str | Path,
    policy_payload: Mapping[str, Any],
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    policy = load_current_s1_runtime_binding_policy(policy_payload)
    assets_policy = policy["assets"]
    assets = {
        asset_id: _asset_binding(root, str(row["ref"]))
        for asset_id, row in assets_policy.items()
    }
    payloads = {
        asset_id: _read_json(root / binding["ref"])
        for asset_id, binding in assets.items()
    }

    registry = payloads["runtime_registry"]
    registry_rows = _registry_rows(registry)
    registered_ids: list[str] = []
    for asset_id, row in assets_policy.items():
        resource_id = str(row.get("registry_resource_id") or "").strip()
        if not resource_id:
            continue
        _require(
            resource_id in registry_rows,
            f"current_s1_runtime_registry_resource_missing:{resource_id}",
        )
        _validate_registered_asset(
            asset=assets[asset_id],
            registry_row=registry_rows[resource_id],
        )
        registered_ids.append(resource_id)

    snapshot = payloads["retrieval_snapshot"]
    compiler = payloads["object_compiler_result"]
    hybrid = payloads["hybrid_runtime_policy"]
    route_policy = payloads["route_policy"]
    s2_result = payloads["s2_fact_mart_result"]
    pack_result = payloads["current_evidence_pack_result"]
    anchor_catalog = payloads["current_reviewed_anchor_catalog"]
    product_readiness_catalog = payloads["product_readiness_catalog"]

    case_readiness_assets = {
        "DELL": "dell_product_readiness",
        "MU": "mu_product_readiness",
        "NVDA": "nvda_product_readiness",
    }
    catalog_resource_ids = product_readiness_catalog.get("case_resource_ids") or {}
    _require(
        product_readiness_catalog.get("schema_version")
        == "fin_ia_current_s1_product_readiness_catalog_v1_0"
        and product_readiness_catalog.get("status")
        == "active_read_only_s1_product_readiness_catalog"
        and product_readiness_catalog.get("published_case_keys")
        == list(case_readiness_assets)
        and set(catalog_resource_ids) == set(case_readiness_assets),
        "current_s1_runtime_product_readiness_catalog_invalid",
    )
    product_readiness: dict[str, dict[str, Any]] = {}
    for case_key, asset_id in case_readiness_assets.items():
        readiness = dict(payloads[asset_id])
        result_digest = str(readiness.pop("result_digest", ""))
        authority = readiness.get("authority") or {}
        _require(
            readiness.get("schema_version")
            == "fin_ia_s1_current_product_readiness_result_v1_0"
            and readiness.get("status")
            == "current_product_pack_readiness_materialized"
            and readiness.get("case_key") == case_key
            and result_digest == canonical_digest(readiness)
            and authority.get("candidate_is_not_evidence") is True
            and authority.get("public_information_gap_authority") is False
            and authority.get("S1_qualification_claimed") is False
            and str(catalog_resource_ids[case_key])
            == str(assets_policy[asset_id].get("registry_resource_id") or ""),
            f"current_s1_runtime_product_readiness_invalid:{case_key}",
        )
        product_readiness[case_key] = {
            "status": str(readiness.get("status") or ""),
            "readiness_state": str(readiness.get("readiness_state") or ""),
            "request_count": int(readiness.get("request_count") or 0),
            "result_digest": result_digest,
            "candidate_is_not_evidence": True,
            "public_information_gap_authority": False,
            "S1_qualification_claimed": False,
        }
    product_consumer = dict(policy.get("product_consumer") or {})
    _require(
        product_consumer.get("product_pack_readiness_producer_registered")
        is True
        and product_consumer.get(
            "product_pack_readiness_workbench_consumer_registered"
        )
        is True,
        "current_s1_runtime_product_readiness_consumer_not_registered",
    )

    source_records = compiler.get("inputs", {}).get("records") or {}
    compiled_objects = compiler.get("output_binding") or {}
    hybrid_objects = hybrid.get("object_store") or {}
    embedding_policy = hybrid.get("qwen_embedding") or {}
    source_records_path = _resolve(root, str(source_records.get("ref") or ""))
    compiled_objects_path = _resolve(
        root, str(compiled_objects.get("objects_ref") or "")
    )
    embedding_manifest_path = _resolve(
        root, str(embedding_policy.get("cache_manifest_ref") or "")
    )
    embedding_dense_path = _resolve(
        root, str(embedding_policy.get("dense_cache_ref") or "")
    )
    embedding_manifest = _read_json(embedding_manifest_path)
    lineage = _source_lineage_summary(
        source_records_path=source_records_path,
        compiled_objects_path=compiled_objects_path,
    )

    source_sha = sha256_file(source_records_path)
    object_sha = sha256_file(compiled_objects_path)
    dense_sha = sha256_file(embedding_dense_path)
    snapshot_source = snapshot.get("source_snapshot") or {}
    compiler_summary = compiler.get("object_compilation_summary") or {}
    _require(
        source_sha
        == str(source_records.get("sha256") or "")
        == str(snapshot_source.get("records_sha256") or ""),
        "current_s1_runtime_source_snapshot_drift",
    )
    _require(
        object_sha
        == str(compiled_objects.get("objects_sha256") or "")
        == str(hybrid_objects.get("objects_sha256") or "")
        == str(embedding_manifest.get("object_sha256") or ""),
        "current_s1_runtime_object_index_drift",
    )
    _require(
        dense_sha == str(embedding_manifest.get("dense_sha256") or ""),
        "current_s1_runtime_dense_cache_drift",
    )
    _require(
        lineage["source_record_count"]
        == int(snapshot_source.get("records") or 0)
        == int(compiler_summary.get("source_record_count") or 0)
        and lineage["compiled_object_count"]
        == int(compiler_summary.get("compiled_object_count") or 0)
        == int(embedding_manifest.get("object_count") or 0),
        "current_s1_runtime_population_count_drift",
    )
    _require(
        lineage["all_source_records_lineage_bound"],
        "current_s1_runtime_source_lineage_incomplete",
    )

    s2_storage = s2_result.get("storage") or {}
    s2_sqlite = _resolve(root, str(s2_storage.get("sqlite_ref") or ""))
    _require(
        sha256_file(s2_sqlite) == str(s2_storage.get("sqlite_sha256") or "")
        and s2_sqlite.stat().st_size == int(s2_storage.get("sqlite_bytes") or 0),
        "current_s1_runtime_s2_mart_drift",
    )

    declared_routes = [str(value) for value in route_policy.get("candidate_routes") or ()]
    capability_rows = {
        str(row["declared_route"]): dict(row)
        for row in policy["runtime_route_capabilities"]
    }
    _require(
        set(declared_routes) == set(capability_rows),
        "current_s1_runtime_route_capability_coverage_drift",
    )
    route_truth = [capability_rows[route] for route in declared_routes]
    unavailable_routes = [
        row["declared_route"]
        for row in route_truth
        if row["capability_state"] == "not_configured"
    ]

    registry_subset = [
        dict(registry_rows[resource_id]) for resource_id in sorted(registered_ids)
    ]
    bindings = {
        **{
            asset_id: binding
            for asset_id, binding in assets.items()
            if asset_id != "runtime_registry"
        },
        "runtime_registry": {
            "ref": assets["runtime_registry"]["ref"],
            "registry_id": str(registry.get("registry_id") or ""),
            "binding_scope": "selected_registered_resources_only_no_self_hash",
        },
        "source_records": _asset_binding(
            root, source_records_path.relative_to(root).as_posix()
        ),
        "compiled_objects": _asset_binding(
            root, compiled_objects_path.relative_to(root).as_posix()
        ),
        "embedding_manifest": _asset_binding(
            root, embedding_manifest_path.relative_to(root).as_posix()
        ),
        "embedding_dense_cache": _asset_binding(
            root, embedding_dense_path.relative_to(root).as_posix()
        ),
        "s2_sqlite": _asset_binding(root, s2_sqlite.relative_to(root).as_posix()),
    }
    body = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "status": "current_product_lineage_bound_with_explicit_open_gates",
        "policy_id": str(policy.get("policy_id") or ""),
        "bindings": bindings,
        "registry_binding": {
            "registry_id": str(registry.get("registry_id") or ""),
            "selected_resource_ids": sorted(registered_ids),
            "selected_resource_digest": canonical_digest(registry_subset),
        },
        "source_object_index_lineage": lineage,
        "embedding_index": {
            "model_id": str(embedding_policy.get("model_id") or ""),
            "model_digest": str(embedding_manifest.get("model_digest") or ""),
            "object_identity_digest": str(
                embedding_manifest.get("object_identity_digest") or ""
            ),
            "object_count": int(embedding_manifest.get("object_count") or 0),
            "dimensions": int(
                embedding_manifest.get("embedding_dimensions") or 0
            ),
            "dtype": str(embedding_manifest.get("dense_dtype") or ""),
            "cuda_only_learned_execution_policy_preserved": True,
        },
        "s2_sibling": {
            "result_status": str(s2_result.get("status") or ""),
            "result_digest": str(s2_result.get("result_digest") or ""),
            "observation_digest": str(s2_storage.get("observation_digest") or ""),
            "observation_count": int(
                (s2_result.get("counts") or {}).get("observations") or 0
            ),
            "database_is_parallel_numeric_authority_not_candidate_route": True,
        },
        "reviewed_evidence": {
            "pack_status": str(pack_result.get("status") or ""),
            "pack_result_digest": str(pack_result.get("result_digest") or ""),
            "anchor_status": str(anchor_catalog.get("status") or ""),
            "anchor_result_digest": str(anchor_catalog.get("result_digest") or ""),
            "candidate_does_not_grant_evidence_or_numeric_authority": True,
        },
        "product_readiness": {
            "catalog_status": str(
                product_readiness_catalog.get("status") or ""
            ),
            "catalog_digest": canonical_digest(product_readiness_catalog),
            "cases": product_readiness,
            "candidate_is_not_evidence": True,
            "public_information_gap_authority": False,
            "s1_qualification_claimed": False,
        },
        "route_execution_truth": {
            "declared_routes": declared_routes,
            "routes": route_truth,
            "unavailable_routes": unavailable_routes,
            "unavailable_route_must_not_be_reported_as_public_information_gap": True,
            "sql_fact_route_is_parallel_sibling_not_candidate_set_member": True,
        },
        "product_consumer": product_consumer,
        "acceptance": {
            "source_to_compiled_lineage_complete": True,
            "compiled_objects_bound_to_current_source_snapshot": True,
            "embedding_cache_bound_to_compiled_objects": True,
            "s2_sqlite_bound_to_typed_fact_result": True,
            "current_pack_and_anchor_catalog_registry_bound": True,
            "declared_route_states_explicit": True,
            "candidate_evidence_numeric_authority_separated": True,
            "product_pack_readiness_producer_registered": True,
            "product_pack_readiness_workbench_consumer_registered": True,
            "workbench_per_object_lineage_drilldown_complete": False,
            "external_blind_qualification_complete": False,
            "s1_qualified_stable": False,
        },
        "known_boundary": (
            "This receipt proves that the current source records, normalized financial "
            "object views, Qwen FP16 index cache, S2 typed fact mart, reviewed Evidence "
            "Pack and reviewed claim anchors are identity-bound. It also makes every "
            "declared candidate-route capability explicit. It does not claim that "
            "unconfigured graph, learned-sparse or multi-vector routes ran; it does not "
            "promote candidates to Evidence or claim S1 qualification. It registers a "
            "digest-bound product PackReadiness producer and request-level Workbench "
            "consumer, but does not complete per-object lineage drilldown, supply natural "
            "scanned-source evidence "
            "or satisfy independent blind qualification."
        ),
    }
    return {**body, "result_digest": canonical_digest(body)}


def validate_current_s1_runtime_binding_receipt(
    payload: Mapping[str, Any],
    policy_payload: Mapping[str, Any],
    *,
    repository_root: str | Path | None = None,
) -> dict[str, Any]:
    value = dict(payload)
    policy = load_current_s1_runtime_binding_policy(policy_payload)
    result_digest = str(value.pop("result_digest", ""))
    _require(
        value.get("schema_version") == RECEIPT_SCHEMA_VERSION
        and value.get("status")
        == "current_product_lineage_bound_with_explicit_open_gates"
        and value.get("policy_id") == policy.get("policy_id")
        and result_digest == canonical_digest(value),
        "current_s1_runtime_receipt_identity_invalid",
    )
    acceptance = value.get("acceptance") or {}
    _require(
        all(
            acceptance.get(key) is True
            for key in (
                "source_to_compiled_lineage_complete",
                "compiled_objects_bound_to_current_source_snapshot",
                "embedding_cache_bound_to_compiled_objects",
                "s2_sqlite_bound_to_typed_fact_result",
                "current_pack_and_anchor_catalog_registry_bound",
                "declared_route_states_explicit",
                "candidate_evidence_numeric_authority_separated",
                "product_pack_readiness_producer_registered",
                "product_pack_readiness_workbench_consumer_registered",
            )
        )
        and acceptance.get("s1_qualified_stable") is False,
        "current_s1_runtime_receipt_acceptance_invalid",
    )
    route_truth = value.get("route_execution_truth") or {}
    policy_routes = [dict(row) for row in policy["runtime_route_capabilities"]]
    _require(
        route_truth.get("routes") == policy_routes
        and route_truth.get("declared_routes")
        == [row["declared_route"] for row in policy_routes]
        and route_truth.get("unavailable_routes")
        == [
            row["declared_route"]
            for row in policy_routes
            if row["capability_state"] == "not_configured"
        ]
        and value.get("product_consumer") == policy.get("product_consumer"),
        "current_s1_runtime_receipt_policy_drift",
    )
    validated = {**value, "result_digest": result_digest}
    if repository_root is not None:
        _require(
            validated
            == build_current_s1_runtime_binding_receipt(
                repository_root,
                policy,
            ),
            "current_s1_runtime_receipt_asset_drift",
        )
    return validated


def project_request_route_execution_truth(
    *,
    execution_plan: Mapping[str, Any] | None,
    binding_receipt: Mapping[str, Any],
    hybrid_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Explain what the product actually ran without turning route gaps into source gaps."""

    capabilities = {
        str(row["declared_route"]): dict(row)
        for row in binding_receipt["route_execution_truth"]["routes"]
    }
    narrative_rows: list[dict[str, Any]] = []
    if execution_plan is not None:
        for request in execution_plan.get("narrative_requests") or ():
            route_rows: list[dict[str, Any]] = []
            for route in request.get("candidate_routes") or ():
                capability = capabilities[str(route)]
                state = str(capability["capability_state"])
                execution_state = (
                    "not_executed_route_unavailable"
                    if state == "not_configured"
                    else "executed"
                    if hybrid_result is not None
                    else "scheduled_in_current_hybrid_runtime"
                )
                route_rows.append(
                    {
                        **capability,
                        "execution_state": execution_state,
                        "public_information_gap_eligible": False,
                    }
                )
            narrative_rows.append(
                {
                    "route_request_id": request.get("route_request_id"),
                    "query_family_id": request.get("query_family_id"),
                    "routes": route_rows,
                }
            )
    facts = [] if execution_plan is None else list(
        execution_plan.get("typed_fact_requests") or ()
    )
    body = {
        "schema_version": "fin_ia_s1_request_route_execution_truth_v1_0",
        "narrative_route_requests": narrative_rows,
        "typed_fact_sibling_requests": facts,
        "hybrid_runtime_result_digest": (
            hybrid_result.get("result_digest") if hybrid_result is not None else None
        ),
        "static_snapshot_filter_executed": True,
        "hybrid_candidate_runtime_executed": hybrid_result is not None,
        "unavailable_or_unexecuted_route_is_not_a_public_information_gap": True,
        "candidate_is_not_evidence": True,
        "numeric_authority_remains_with_s2": True,
    }
    return {**body, "projection_digest": canonical_digest(body)}


__all__ = [
    "CurrentS1RuntimeBindingError",
    "POLICY_SCHEMA_VERSION",
    "RECEIPT_SCHEMA_VERSION",
    "build_current_s1_runtime_binding_receipt",
    "load_current_s1_runtime_binding_policy",
    "project_request_route_execution_truth",
    "sha256_file",
    "validate_current_s1_runtime_binding_receipt",
]
