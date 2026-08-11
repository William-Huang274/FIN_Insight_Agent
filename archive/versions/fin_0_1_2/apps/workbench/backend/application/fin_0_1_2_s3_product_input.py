from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
from typing import Any, Mapping

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.runtime_resource_registry import read_registered_runtime_json


FIN_0_1_2_S3_NVDA_EXACT_PRODUCT_INPUT_RESOURCE_ID = (
    "fin_0_1_2.s3.nvda_exact_product_input"
)
FIN_0_1_2_S3_NVDA_EXACT_PRODUCT_INPUT_REF = (
    "configs/releases/fin_ia_0_1_2_s3_nvda_exact_product_input_v1_0.json"
)
FIN_0_1_2_S3_RUNTIME_RESOURCE_REGISTRY_REF = (
    "configs/runtime/fin_ia_0_1_2_s3_runtime_resource_registry_v1_0.json"
)


def _repository_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / FIN_0_1_2_S3_RUNTIME_RESOURCE_REGISTRY_REF).is_file():
            return parent
    raise ValueError("fin012_s3_product_input_repository_root_not_found")


def _validate_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    expected = {
        "schema_version",
        "contract_ref",
        "status",
        "case",
        "materialization",
        "lineage",
        "nonpromotion_boundary",
        "manifest_digest",
    }
    normalized = dict(payload)
    if (
        set(normalized) != expected
        or normalized.get("schema_version")
        != "fin_ia_0_1_2_s3_exact_product_input_manifest_v1_0"
        or normalized.get("contract_ref")
        != "fin_0_1_2.s3.nvda_exact_product_input:v1"
        or normalized.get("status")
        != "tracked_current_S3_exact_input_not_executed"
    ):
        raise ValueError("fin012_s3_product_input_manifest_invalid")
    digest = normalized.pop("manifest_digest", None)
    if digest != canonical_digest(normalized):
        raise ValueError("fin012_s3_product_input_manifest_digest_mismatch")
    normalized["manifest_digest"] = digest
    case = normalized.get("case")
    materialization = normalized.get("materialization")
    boundary = normalized.get("nonpromotion_boundary")
    if (
        not isinstance(case, Mapping)
        or case.get("company") != "NVDA"
        or not isinstance(materialization, Mapping)
        or any(
            re.fullmatch(r"[0-9a-f]{64}", str(materialization.get(key) or ""))
            is None
            for key in ("input_head_digest", "source_digest", "input_digest")
        )
        or not isinstance(boundary, Mapping)
        or boundary.get("paid_execution_authorized") is not False
        or boundary.get("historical_artifacts_promoted_as_current") is not False
        or boundary.get("exact_input_must_be_recompiled_and_digest_matched_before_T03")
        is not True
    ):
        raise ValueError("fin012_s3_product_input_boundary_invalid")
    return normalized


@lru_cache(maxsize=1)
def load_fin_0_1_2_s3_nvda_exact_product_input_manifest() -> dict[str, Any]:
    payload = read_registered_runtime_json(
        _repository_root(),
        FIN_0_1_2_S3_NVDA_EXACT_PRODUCT_INPUT_RESOURCE_ID,
        registry_ref=FIN_0_1_2_S3_RUNTIME_RESOURCE_REGISTRY_REF,
    )
    return _validate_manifest(payload)


def assert_fin_0_1_2_s3_exact_input_matches_manifest(
    input_pack: Any,
    *,
    source_digest: str,
) -> dict[str, Any]:
    manifest = load_fin_0_1_2_s3_nvda_exact_product_input_manifest()
    case = manifest["case"]
    materialization = manifest["materialization"]
    observed = (
        input_pack.model_dump(mode="json")
        if hasattr(input_pack, "model_dump")
        else dict(input_pack)
    )
    if (
        observed.get("case_id") != case["case_id"]
        or observed.get("case_version") != case["case_version"]
        or observed.get("company") != case["company"]
        or observed.get("as_of") != case["as_of"]
        or observed.get("query") != case["query"]
        or observed.get("decision_surface_contract_ref")
        != case["decision_surface_contract_ref"]
        or observed.get("input_head_digest")
        != materialization["input_head_digest"]
        or observed.get("input_digest") != materialization["input_digest"]
        or observed.get("lineage") != manifest["lineage"]
        or source_digest != materialization["source_digest"]
    ):
        raise ValueError("fin012_s3_exact_product_input_manifest_mismatch")
    return {
        "contract_ref": manifest["contract_ref"],
        "manifest_digest": manifest["manifest_digest"],
        "source_digest": source_digest,
        "input_digest": observed["input_digest"],
        "paid_execution_authorized": False,
    }
