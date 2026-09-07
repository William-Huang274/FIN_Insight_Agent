from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PREDECESSOR_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_proposition_coverage_execution_program_v1_1.json"
)
OUTPUT_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_proposition_coverage_execution_program_v1_2.json"
)

PUBLIC_WEB_REQUEST_IDS = {
    "REQ::DELL::PRICE_CONFIGURATION::V1",
    "REQ::DELL::UNIT_VOLUME::V1",
    "REQ::DELL::PVM_BRIDGE::V1",
    "REQ::DELL::CUSTOMER_DEMAND_DOWNSTREAM::V1",
    "REQ::DELL::SUPPLY_UPSTREAM_CAPACITY::V1",
    "REQ::DELL::SUPPLY_RELATIONSHIP::V1",
    "REQ::DELL::VALUE_POOL_COUNTERPARTY::V1",
    "REQ::DELL::COUNTER_ECOSYSTEM::V1",
}


def _path(ref: str) -> Path:
    return ROOT / ref


def _read_json(ref: str) -> dict[str, Any]:
    value = json.loads(_path(ref).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{ref}")
    return value


def _sha256(ref: str) -> str:
    return hashlib.sha256(_path(ref).read_bytes()).hexdigest()


def _write_new(ref: str, value: Mapping[str, Any]) -> None:
    path = _path(ref)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def build_successor(predecessor: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(predecessor))
    result["program_id"] = "FIN-0.1.3-S1-DELL-PROPOSITION-COVERAGE-R3"
    result["status"] = (
        "approved_ai_free_stage_owned_vertical_execution_program_with_"
        "official_web_and_relationship_graph"
    )
    result["predecessor"] = {
        "ref": PREDECESSOR_REF,
        "sha256": _sha256(PREDECESSOR_REF),
        "program_id": predecessor.get("program_id"),
    }
    controls = result["controls"]
    controls.update(
        {
            "nonperiodic_source_temporal_binding": (
                "explicit_publication_window_when_fiscal_year_is_null"
            ),
            "typed_relationship_graph_executor": (
                "source_bound_registered_entity_explicit_mention_v1"
            ),
            "relationship_graph_result_or_label_access": False,
            "relationship_graph_grants_relationship_fact_authority": False,
        }
    )
    result["internal_route_contract"] = [
        (
            "typed_relationship_graph_source_bound_explicit_mention"
            if value == "typed_relationship_graph_if_configured"
            else value
        )
        for value in result["internal_route_contract"]
    ]
    requests = {
        str(row.get("request_id") or ""): row
        for row in result.get("evidence_requests") or ()
    }
    if set(requests) != {
        str(row.get("request_id") or "")
        for row in predecessor.get("evidence_requests") or ()
    }:
        raise ValueError("dell_proposition_request_identity_drift")
    if not PUBLIC_WEB_REQUEST_IDS.issubset(requests):
        raise ValueError("dell_proposition_public_web_request_missing")
    for request_id in sorted(PUBLIC_WEB_REQUEST_IDS):
        source_types = list(requests[request_id]["acceptable_sources"])
        if "PUBLIC_WEB" not in source_types:
            source_types.append("PUBLIC_WEB")
        requests[request_id]["acceptable_sources"] = source_types
    result["successor_change"] = {
        "owned_defects": [
            "nonperiodic_official_source_rejected_when_fiscal_year_null",
            "typed_relationship_graph_declared_without_runtime_handler",
            "task_requests_excluded_official_public_web_source_class",
        ],
        "public_web_enabled_request_ids": sorted(PUBLIC_WEB_REQUEST_IDS),
        "historical_material_outside_request_period_remains_ineligible": True,
        "candidate_is_not_evidence": True,
        "numeric_authority": False,
        "current_bilateral_relationship_not_inferred_from_historical_mention": True,
    }
    return result


def main() -> int:
    successor = build_successor(_read_json(PREDECESSOR_REF))
    _write_new(OUTPUT_REF, successor)
    print(
        json.dumps(
            {
                "status": "dell_proposition_program_successor_materialized",
                "output_ref": OUTPUT_REF,
                "program_id": successor["program_id"],
                "public_web_enabled_request_count": len(PUBLIC_WEB_REQUEST_IDS),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
