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
from retrieval.source_route_dispatch import (  # noqa: E402
    load_source_route_portfolio_policy,
)
from sec_agent.research.dynamic_single_unit_loop import (  # noqa: E402
    load_dynamic_single_unit_policy,
)
from sec_agent.runtime_resource_registry import (  # noqa: E402
    load_runtime_resource_registry,
)


RECORDED_AT = "2026-08-25"
PREDECESSOR_REGISTRY_ID = (
    "FIN-0.1.3-CURRENT-PRODUCT-RUNTIME-RESOURCE-REGISTRY-R35"
)
REGISTRY_ID = "FIN-0.1.3-CURRENT-PRODUCT-RUNTIME-RESOURCE-REGISTRY-R36"
SOURCE_ROUTE_PREDECESSOR_REF = (
    "configs/retrieval/fin_ia_0_1_3_s1_source_route_portfolio_policy_v1_0.json"
)
SOURCE_ROUTE_REF = (
    "configs/retrieval/fin_ia_0_1_3_s1_source_route_portfolio_policy_v1_1.json"
)
BINDING_PREDECESSOR_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_current_product_runtime_binding_policy_v1_10.json"
)
BINDING_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_current_product_runtime_binding_policy_v1_11.json"
)
RECEIPT_REF = (
    "configs/runtime/fin_ia_0_1_3_current_s1_runtime_binding_receipt_v1_12.json"
)
DYNAMIC_PREDECESSOR_REF = (
    "configs/research/"
    "fin_ia_0_1_3_s3_dell_dynamic_single_unit_loop_policy_v1_3.json"
)
DYNAMIC_REF = (
    "configs/research/"
    "fin_ia_0_1_3_s3_dell_dynamic_single_unit_loop_policy_v1_4.json"
)

PUBLIC_SOURCE_TYPES = ("PUBLIC_WEB", "PUBLIC_PDF")
BOUNDED_PUBLIC_ROLES = (
    "issuer_or_bounded_price_configuration_context",
    "issuer_or_bounded_customer_demand_context",
    "issuer_or_registered_supplier_direct_mention",
)


def _append_unique(values: list[str], additions: tuple[str, ...]) -> list[str]:
    return values + [value for value in additions if value not in values]


def _build_source_route_policy(predecessor: Mapping[str, Any]) -> dict[str, Any]:
    value = deepcopy(dict(predecessor))
    value["policy_id"] = "FIN-0.1.3-S1-SOURCE-ROUTE-PORTFOLIO-V1.1"
    value["recorded_at"] = RECORDED_AT
    routes = value["routes"]
    by_id = {str(row["route_id"]): row for row in routes}
    for route_id in (
        "current_local_snapshot",
        "broad_web_discovery_diagnostic",
        "operator_official_upload",
    ):
        route = by_id[route_id]
        route["source_types"] = _append_unique(
            list(route["source_types"]), PUBLIC_SOURCE_TYPES
        )
        route["source_roles"] = _append_unique(
            list(route["source_roles"]), BOUNDED_PUBLIC_ROLES
        )
    routes.append(
        {
            "route_id": "registered_reviewed_public_document_intake",
            "route_kind": "official_ir",
            "capability_state": "available_when_exact_route_registered",
            "route_tier": "production",
            "executor_id": "source_intake_registered_exact_public_document",
            "case_scope": ["*"],
            "source_types": list(PUBLIC_SOURCE_TYPES),
            "source_roles": list(BOUNDED_PUBLIC_ROLES),
            "capture_required": True,
            "exhaustion_authority": True,
            "exact_registry_required": True,
        }
    )
    value["successor_change"] = {
        "failed_attempt_ref": (
            "configs/research/evals/"
            "fin_ia_0_1_3_s3_dell_r35_reviewed_public_pdf_consumer_zero_call_"
            "R4_failure_assessment_v1_0.json"
        ),
        "root_error": "source_route_local_route_missing",
        "local_snapshot_supports_reviewed_public_web_and_pdf": True,
        "exact_public_document_intake_remains_capture_first": True,
        "diagnostic_route_cannot_prove_exhaustion": True,
        "candidate_is_not_evidence": True,
        "public_information_gap_authority": False,
    }
    load_source_route_portfolio_policy(value)
    return value


def _build_binding_policy(predecessor: Mapping[str, Any]) -> dict[str, Any]:
    value = deepcopy(dict(predecessor))
    value["policy_id"] = "FIN-0.1.3-S1-CURRENT-PRODUCT-RUNTIME-BINDING-V1.11"
    value["successor_change"] = {
        "runtime_registry_id": REGISTRY_ID,
        "source_route_policy_ref": SOURCE_ROUTE_REF,
        "failed_attempt_is_immutable": True,
        "S1_qualification_claimed": False,
    }
    return load_current_s1_runtime_binding_policy(value)


def _build_dynamic_policy(predecessor: Mapping[str, Any]) -> dict[str, Any]:
    value = deepcopy(dict(predecessor))
    value["objective"]["objective_id"] = (
        "OBJ::DELL::DYNAMIC-VALUE-CAPTURE-R36-REVIEWED-PUBLIC-PDF-ROUTE"
    )
    value["authority"][
        "reviewed_public_pdf_requires_current_local_source_route"
    ] = True
    request_basis = value["token_budget_bases"]["request_planning"]
    request_basis["comparable_run_evidence"] = (
        "R35 R4 failed before workpaper compilation with "
        "source_route_local_route_missing. R36 adds only current local, exact "
        "capture-first public-document, diagnostic and manual route declarations "
        "for the three bounded successor roles; it does not change Evidence or "
        "NumericFact authority."
    )
    request_basis["node_purpose"] = (
        "Select proposition-bound S1/S2 research requests from the current R36 "
        "tool catalog without seeing answers."
    )
    return load_dynamic_single_unit_policy(value)


def _require_new_outputs() -> None:
    for ref in (SOURCE_ROUTE_REF, BINDING_REF, RECEIPT_REF, DYNAMIC_REF):
        if (ROOT / ref).exists():
            raise FileExistsError(f"source_route_successor_output_exists:{ref}")


def main() -> int:
    _require_new_outputs()
    registry = deepcopy(_read_json(REGISTRY_REF))
    if registry.get("registry_id") != PREDECESSOR_REGISTRY_ID:
        raise ValueError("source_route_successor_R35_predecessor_required")

    source_route = _build_source_route_policy(
        _read_json(SOURCE_ROUTE_PREDECESSOR_REF)
    )
    binding = _build_binding_policy(_read_json(BINDING_PREDECESSOR_REF))
    dynamic = _build_dynamic_policy(_read_json(DYNAMIC_PREDECESSOR_REF))
    _write_json(SOURCE_ROUTE_REF, source_route)
    _write_json(BINDING_REF, binding)
    _write_json(DYNAMIC_REF, dynamic)

    registry["registry_id"] = REGISTRY_ID
    for resource_id, ref, payload in (
        (
            "application.config.current_s1_source_route_portfolio",
            SOURCE_ROUTE_REF,
            source_route,
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
                "status": "current_reviewed_public_pdf_source_route_promoted",
                "registry_id": REGISTRY_ID,
                "source_route_policy_ref": SOURCE_ROUTE_REF,
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
