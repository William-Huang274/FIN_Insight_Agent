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
    _with_resource,
    _write_json,
)
from retrieval.current_runtime_binding import (  # noqa: E402
    build_current_s1_runtime_binding_receipt,
    load_current_s1_runtime_binding_policy,
    validate_current_s1_runtime_binding_receipt,
)
from retrieval.material_evidence_runtime import _validate_policy  # noqa: E402
from retrieval.retrieval_need import _validate_policy as _validate_need_policy  # noqa: E402
from sec_agent.research.dynamic_single_unit_loop import (  # noqa: E402
    load_dynamic_single_unit_policy,
)
from sec_agent.runtime_resource_registry import (  # noqa: E402
    load_runtime_resource_registry,
)


RECORDED_AT = "2026-08-25"
PREDECESSOR_REGISTRY_ID = (
    "FIN-0.1.3-CURRENT-PRODUCT-RUNTIME-RESOURCE-REGISTRY-R36"
)
REGISTRY_ID = "FIN-0.1.3-CURRENT-PRODUCT-RUNTIME-RESOURCE-REGISTRY-R37"
NEED_PREDECESSOR_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_vs5_retrieval_need_compiler_policy_v1_2.json"
)
NEED_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_vs5_retrieval_need_compiler_policy_v1_3.json"
)
MATERIAL_PREDECESSOR_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_product_material_evidence_runtime_policy_v1_1.json"
)
MATERIAL_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_product_material_evidence_runtime_policy_v1_2.json"
)
BINDING_PREDECESSOR_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_current_product_runtime_binding_policy_v1_11.json"
)
BINDING_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_current_product_runtime_binding_policy_v1_12.json"
)
RECEIPT_REF = (
    "configs/runtime/fin_ia_0_1_3_current_s1_runtime_binding_receipt_v1_13.json"
)
DYNAMIC_PREDECESSOR_REF = (
    "configs/research/"
    "fin_ia_0_1_3_s3_dell_dynamic_single_unit_loop_policy_v1_4.json"
)
DYNAMIC_REF = (
    "configs/research/"
    "fin_ia_0_1_3_s3_dell_dynamic_single_unit_loop_policy_v1_5.json"
)
INTENT_ONTOLOGY_REF = (
    "configs/retrieval/fin_ia_0_1_3_s1_financial_intent_ontology_v1_4.json"
)


def _build_need_policy(predecessor: Mapping[str, Any]) -> dict[str, Any]:
    value = deepcopy(dict(predecessor))
    value["recorded_at"] = RECORDED_AT
    value["parent_policy_ref"] = NEED_PREDECESSOR_REF
    facets = value["facet_role_cues"]
    facets.update(
        {
            "bounded_unit_volume_context": {
                "lexical": [
                    "systems",
                    "units",
                    "public procurement",
                    "deployment",
                    "orders",
                ],
                "semantic": (
                    "bounded issuer or public-customer unit observation; a "
                    "project count is not company units or market share"
                ),
            },
            "bounded_price_configuration_context": {
                "lexical": [
                    "recommended price",
                    "contract value",
                    "configuration",
                    "bundled services",
                    "product mix",
                ],
                "semantic": (
                    "bounded issuer, technical-study or procurement price and "
                    "configuration context; a bundle is not company ASP"
                ),
            },
            "current_platform_relationship_context": {
                "lexical": [
                    "partnership",
                    "collaboration",
                    "available",
                    "product availability",
                    "platform",
                ],
                "semantic": (
                    "current named platform relationship or product availability; "
                    "public mention is not private allocation authority"
                ),
            },
        }
    )
    value["successor_change"] = {
        "failed_attempt_ref": (
            "configs/research/evals/"
            "fin_ia_0_1_3_s3_dell_r36_reviewed_public_pdf_consumer_zero_call_"
            "R5_failure_assessment_v1_0.json"
        ),
        "root_error": (
            "retrieval_need_facet_policy_missing:"
            "bounded_price_configuration_context"
        ),
        "all_current_request_facets_enumerated": True,
        "candidate_is_not_evidence": True,
        "numeric_authority": False,
    }
    _validate_need_policy(value, intent_ontology=_read_json(INTENT_ONTOLOGY_REF))
    return value


def _build_material_policy(predecessor: Mapping[str, Any]) -> dict[str, Any]:
    value = deepcopy(dict(predecessor))
    value["recorded_at"] = RECORDED_AT
    facets = value["facet_required_roles"]
    facets.update(
        {
            "bounded_unit_volume_context": ["context", "counter"],
            "bounded_price_configuration_context": ["direct", "context"],
            "current_platform_relationship_context": ["context"],
        }
    )
    value["successor_change"] = {
        "failed_attempt_ref": (
            "configs/research/evals/"
            "fin_ia_0_1_3_s3_dell_r36_reviewed_public_pdf_consumer_zero_call_"
            "R5_failure_assessment_v1_0.json"
        ),
        "bounded_context_does_not_become_company_metric": True,
        "candidate_is_not_evidence": True,
        "numeric_fact_authority": False,
    }
    _validate_policy(value)
    return value


def _build_binding_policy(predecessor: Mapping[str, Any]) -> dict[str, Any]:
    value = deepcopy(dict(predecessor))
    value["policy_id"] = "FIN-0.1.3-S1-CURRENT-PRODUCT-RUNTIME-BINDING-V1.12"
    value["successor_change"] = {
        "runtime_registry_id": REGISTRY_ID,
        "retrieval_need_policy_ref": NEED_REF,
        "material_evidence_policy_ref": MATERIAL_REF,
        "failed_attempt_is_immutable": True,
        "S1_qualification_claimed": False,
    }
    return load_current_s1_runtime_binding_policy(value)


def _build_dynamic_policy(predecessor: Mapping[str, Any]) -> dict[str, Any]:
    value = deepcopy(dict(predecessor))
    value["objective"]["objective_id"] = (
        "OBJ::DELL::DYNAMIC-VALUE-CAPTURE-R37-REVIEWED-PUBLIC-PDF-MATERIAL"
    )
    value["authority"][
        "reviewed_public_pdf_facets_require_material_policy_coverage"
    ] = True
    request_basis = value["token_budget_bases"]["request_planning"]
    request_basis["comparable_run_evidence"] = (
        "R36 R5 passed source-route compilation but failed during deterministic "
        "retrieval-need compilation because the bounded price facet was absent "
        "from the current material policies. R37 enumerates all three bounded "
        "facets without changing Evidence or NumericFact authority."
    )
    request_basis["node_purpose"] = (
        "Select proposition-bound S1/S2 research requests from the current R37 "
        "tool catalog without seeing answers."
    )
    return load_dynamic_single_unit_policy(value)


def _require_new_outputs() -> None:
    for ref in (NEED_REF, MATERIAL_REF, BINDING_REF, RECEIPT_REF, DYNAMIC_REF):
        if (ROOT / ref).exists():
            raise FileExistsError(f"material_policy_successor_output_exists:{ref}")


def main() -> int:
    _require_new_outputs()
    registry = deepcopy(_read_json(REGISTRY_REF))
    if registry.get("registry_id") != PREDECESSOR_REGISTRY_ID:
        raise ValueError("material_policy_successor_R36_predecessor_required")

    need = _build_need_policy(_read_json(NEED_PREDECESSOR_REF))
    material = _build_material_policy(_read_json(MATERIAL_PREDECESSOR_REF))
    binding = _build_binding_policy(_read_json(BINDING_PREDECESSOR_REF))
    dynamic = _build_dynamic_policy(_read_json(DYNAMIC_PREDECESSOR_REF))
    _write_json(NEED_REF, need)
    _write_json(MATERIAL_REF, material)
    _write_json(BINDING_REF, binding)
    _write_json(DYNAMIC_REF, dynamic)

    registry["registry_id"] = REGISTRY_ID
    for resource_id, ref, payload in (
        ("application.config.current_retrieval_need_policy", NEED_REF, need),
        (
            "application.config.current_product_material_evidence_runtime_policy",
            MATERIAL_REF,
            material,
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
                "status": "current_reviewed_public_pdf_material_policies_promoted",
                "registry_id": REGISTRY_ID,
                "retrieval_need_policy_ref": NEED_REF,
                "material_evidence_policy_ref": MATERIAL_REF,
                "binding_receipt_ref": RECEIPT_REF,
                "binding_digest": receipt["result_digest"],
                "dynamic_policy_ref": DYNAMIC_REF,
                "natural_model_calls": 0,
                "network_calls": 0,
                "paid_tool_calls": 0,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
