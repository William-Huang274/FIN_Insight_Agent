from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
SCRIPT_ROOT = ROOT / "scripts" / "data_retrieval"
for import_root in (SRC_ROOT, SCRIPT_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from promote_s1_reviewed_public_pdf_to_current_runtime import (  # noqa: E402
    REGISTRY_REF,
    _read_json,
    _refresh_registry_aggregate,
    _sha256_file,
    _with_resource,
    _write_json,
)
from retrieval.contracts import load_financial_research_kernel  # noqa: E402
from retrieval.current_runtime_binding import (  # noqa: E402
    build_current_s1_runtime_binding_receipt,
    canonical_digest,
    load_current_s1_runtime_binding_policy,
    validate_current_s1_runtime_binding_receipt,
)
from retrieval.route_compiler import (  # noqa: E402
    load_query_object_fact_route_policy,
)
from sec_agent.runtime_resource_registry import (  # noqa: E402
    load_runtime_resource_registry,
)


RECORDED_AT = "2026-08-26"
PREDECESSOR_REGISTRY_ID = (
    "FIN-0.1.3-CURRENT-PRODUCT-RUNTIME-RESOURCE-REGISTRY-R38"
)
REGISTRY_ID = "FIN-0.1.3-CURRENT-PRODUCT-RUNTIME-RESOURCE-REGISTRY-R39"
KERNEL_REF = (
    "configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_5.json"
)
REPAIR_RESULT_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_abbreviation_claim_repair_successor_result_v1_0.json"
)
EMBEDDING_RESULT_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1c_qwen_embedding_cache_successor_result_v1_3.json"
)
OBJECTS_REF = (
    "data/workbench_private/fin_0_1_3_s1c_compiled_financial_object_views/"
    "v9/objects.jsonl"
)
EMBEDDING_MANIFEST_REF = (
    "data/workbench_private/fin_0_1_3_s1c_hybrid_candidate_runtime/"
    "model_cache_v9/qwen3_embedding_0_6b_v1/manifest.json"
)
EMBEDDING_DENSE_REF = (
    "data/workbench_private/fin_0_1_3_s1c_hybrid_candidate_runtime/"
    "model_cache_v9/qwen3_embedding_0_6b_v1/dense.float16.npy"
)
ROUTE_PREDECESSOR_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_5.json"
)
ROUTE_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_6.json"
)
HYBRID_PREDECESSOR_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1c_hybrid_candidate_runtime_policy_v1_8.json"
)
HYBRID_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1c_hybrid_candidate_runtime_policy_v1_9.json"
)
BINDING_PREDECESSOR_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_current_product_runtime_binding_policy_v1_13.json"
)
BINDING_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_current_product_runtime_binding_policy_v1_14.json"
)
RECEIPT_REF = (
    "configs/runtime/fin_ia_0_1_3_current_s1_runtime_binding_receipt_v1_15.json"
)


def _path(ref: str) -> Path:
    return ROOT / ref


def _validated_digest(value: Mapping[str, Any], code: str) -> str:
    body = deepcopy(dict(value))
    result_digest = str(body.pop("result_digest", ""))
    if not result_digest or result_digest != canonical_digest(body):
        raise ValueError(code)
    return result_digest


def build_hybrid_policy(
    predecessor: Mapping[str, Any],
    repair_result: Mapping[str, Any],
    embedding_result: Mapping[str, Any],
) -> dict[str, Any]:
    value = deepcopy(dict(predecessor))
    value["object_store"] = {
        "objects_ref": OBJECTS_REF,
        "objects_sha256": repair_result["outputs"]["objects_sha256"],
    }
    value["qwen_embedding"]["dense_cache_ref"] = EMBEDDING_DENSE_REF
    value["qwen_embedding"]["cache_manifest_ref"] = EMBEDDING_MANIFEST_REF
    if (
        set(value) != set(predecessor)
        or embedding_result["runtime"]["device"] != "cuda:0"
        or embedding_result["runtime"]["parameter_dtype"] != "torch.float16"
        or embedding_result["runtime"]["cpu_fallback_count"] != 0
        or embedding_result["runtime"]["new_object_count_embedded"] != 1
        or embedding_result["outputs"]["object_count"] != 34199
    ):
        raise ValueError("abbreviation_repair_hybrid_successor_contract_invalid")
    return value


def build_binding_policy(predecessor: Mapping[str, Any]) -> dict[str, Any]:
    value = deepcopy(dict(predecessor))
    value["policy_id"] = (
        "FIN-0.1.3-S1-CURRENT-PRODUCT-RUNTIME-BINDING-V1.14"
    )
    assets = value["assets"]
    assets["object_compiler_result"]["ref"] = REPAIR_RESULT_REF
    assets["hybrid_runtime_policy"]["ref"] = HYBRID_REF
    assets["route_policy"]["ref"] = ROUTE_REF
    value["successor_change"] = {
        "runtime_registry_id": REGISTRY_ID,
        "predecessor_registry_id": PREDECESSOR_REGISTRY_ID,
        "local_abbreviation_claim_loss_repaired": True,
        "source_record_population_changed": False,
        "compiled_object_append_count": 1,
        "historical_R38_immutable": True,
        "S1_qualification_claimed": False,
        "evidence_authority_changed": False,
        "numeric_authority_changed": False,
    }
    return load_current_s1_runtime_binding_policy(value)


def _validate_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    repair = _read_json(REPAIR_RESULT_REF)
    embedding = _read_json(EMBEDDING_RESULT_REF)
    route = _read_json(ROUTE_REF)
    _validated_digest(repair, "abbreviation_repair_result_digest_drift")
    summary = repair.get("summary") or {}
    if (
        summary.get("base_source_record_count") != 1888
        or summary.get("successor_source_record_count") != 1888
        or summary.get("base_object_count") != 34198
        or summary.get("appended_object_count") != 1
        or summary.get("successor_object_count") != 34199
        or repair.get("authority", {}).get("candidate_is_not_evidence") is not True
        or repair.get("authority", {}).get("numeric_authority") is not False
    ):
        raise ValueError("abbreviation_repair_result_population_invalid")
    if (
        repair["outputs"]["objects_ref"] != OBJECTS_REF
        or repair["outputs"]["objects_sha256"] != _sha256_file(OBJECTS_REF)
        or embedding["outputs"]["dense_cache_ref"] != EMBEDDING_DENSE_REF
        or embedding["outputs"]["cache_manifest_ref"]
        != EMBEDDING_MANIFEST_REF
        or embedding["inputs"]["successor_objects_ref"] != OBJECTS_REF
        or embedding["inputs"]["successor_objects_sha256"]
        != repair["outputs"]["objects_sha256"]
    ):
        raise ValueError("abbreviation_repair_artifact_binding_drift")
    kernel = load_financial_research_kernel(_read_json(KERNEL_REF))
    loaded_route = load_query_object_fact_route_policy(route, kernel)
    if loaded_route.object_compiler.get("claim_segmentation_mode") != (
        "sentence_with_wrapped_line_reflow_v2"
    ):
        raise ValueError("abbreviation_repair_route_mode_invalid")
    return repair, embedding, route


def _require_new_outputs() -> None:
    for ref in (HYBRID_REF, BINDING_REF, RECEIPT_REF):
        path = _path(ref)
        if path.exists() or path.with_suffix(path.suffix + ".tmp").exists():
            raise FileExistsError(
                f"abbreviation_repair_runtime_successor_exists:{ref}"
            )


def main() -> int:
    _require_new_outputs()
    registry = deepcopy(_read_json(REGISTRY_REF))
    if registry.get("registry_id") != PREDECESSOR_REGISTRY_ID:
        raise ValueError("abbreviation_repair_runtime_R38_predecessor_required")
    repair, embedding, route = _validate_inputs()
    hybrid = build_hybrid_policy(
        _read_json(HYBRID_PREDECESSOR_REF), repair, embedding
    )
    binding = build_binding_policy(_read_json(BINDING_PREDECESSOR_REF))

    # The registry helper deliberately re-reads each referenced file before it
    # accepts a resource binding.  Publish the two immutable successor policies
    # first; the shared current registry remains untouched until all bindings
    # and the receipt have validated.
    _write_json(HYBRID_REF, hybrid)
    _write_json(BINDING_REF, binding)

    registry["registry_id"] = REGISTRY_ID
    for resource_id, ref, payload in (
        (
            "application.config.current_query_object_fact_route_policy",
            ROUTE_REF,
            route,
        ),
        (
            "application.config.current_hybrid_candidate_runtime_policy",
            HYBRID_REF,
            hybrid,
        ),
        (
            "application.config.current_s1_runtime_binding_policy",
            BINDING_REF,
            binding,
        ),
    ):
        _with_resource(
            registry,
            resource_id=resource_id,
            ref=ref,
            payload=payload,
        )
    _refresh_registry_aggregate(registry)

    receipt = build_current_s1_runtime_binding_receipt(
        ROOT,
        binding,
        payload_overrides={"runtime_registry": registry},
    )
    _write_json(RECEIPT_REF, receipt)
    _with_resource(
        registry,
        resource_id="application.result.current_s1_runtime_binding_receipt",
        ref=RECEIPT_REF,
        payload=receipt,
    )
    _refresh_registry_aggregate(registry)
    _write_json(REGISTRY_REF, registry)

    load_runtime_resource_registry(ROOT)
    validate_current_s1_runtime_binding_receipt(
        receipt,
        binding,
        repository_root=ROOT,
    )
    print(
        json.dumps(
            {
                "status": "current_abbreviation_claim_repair_promoted",
                "recorded_at": RECORDED_AT,
                "registry_id": REGISTRY_ID,
                "source_record_count": receipt[
                    "source_object_index_lineage"
                ]["source_record_count"],
                "compiled_object_count": receipt[
                    "source_object_index_lineage"
                ]["compiled_object_count"],
                "embedding_object_count": receipt["embedding_index"][
                    "object_count"
                ],
                "appended_object_count": 1,
                "source_mutations": 0,
                "evidence_promotions": 0,
                "numeric_authority_changes": 0,
                "network_calls": 0,
                "provider_calls": 0,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
