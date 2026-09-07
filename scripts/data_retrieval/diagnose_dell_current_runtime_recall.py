from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path[:0] = [str(ROOT), str(SRC)]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")

from apps.workbench.backend.application.research_retrieval_service import (  # noqa: E402
    ResearchRetrievalPrincipal,
    ResearchRetrievalService,
)
from scripts.data_retrieval.run_dell_proposition_coverage_internal import (  # noqa: E402
    _program_material_blueprints,
)


PROGRAM = (
    ROOT
    / "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_proposition_coverage_execution_program_v1_2.json"
)
REQUEST_IDS = {
    "REQ::DELL::PRICE_CONFIGURATION::V1",
    "REQ::DELL::UNIT_VOLUME::V1",
    "REQ::DELL::SUPPLY_UPSTREAM_CAPACITY::V1",
    "REQ::DELL::SUPPLY_RELATIONSHIP::V1",
}
TARGET_OBJECT_IDS = {
    "COBJ::b1aa5ac7cd2f6247322906af",
    "COBJ::81ec542b4e403c70f734cb44",
    "COBJ::8ac139d8ee619d7986ede5ef",
}


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_mapping_required:{path.name}")
    return value


def _project(request_result: Mapping[str, Any]) -> dict[str, Any]:
    hybrid = dict(request_result["hybrid_object_retrieval"])
    summary = dict(hybrid["summary"])
    seed = {
        str(row["compiled_object_id"]): row
        for row in hybrid.get("candidate_decision_seed") or ()
    }
    selected = {
        str(row["compiled_object_id"]): row
        for row in hybrid.get("candidates") or ()
    }
    request_id = str(request_result["request"]["request_id"])
    material_selection = dict(
        ((hybrid.get("material_evidence") or {}).get("selection") or {})
    )
    return {
        "request_id": request_id,
        "schema_version": hybrid["schema_version"],
        "summary": {
            key: summary.get(key)
            for key in (
                "eligible_object_count",
                "bm25_first_stage_count",
                "qwen_first_stage_count",
                "typed_relationship_graph_first_stage_count",
                "global_route_union_count",
                "union_count_before_source_quota",
                "selected_count",
                "selected_candidate_count_by_owner",
                "material_set_complete",
                "grouped_surface_recall_enabled",
                "owner_candidate_union",
            )
        },
        "targets": {
            target_id: {
                "in_union": target_id in seed,
                "in_selected": target_id in selected,
                "rank_trace": (seed.get(target_id) or {}).get("rank_trace"),
                "route_membership": (seed.get(target_id) or {}).get(
                    "route_membership"
                ),
                "material_alignment_state": (seed.get(target_id) or {}).get(
                    "material_alignment_state"
                ),
            }
            for target_id in sorted(TARGET_OBJECT_IDS)
        },
        "selected_public_web": [
            {
                "compiled_object_id": row["compiled_object_id"],
                "ticker": row["ticker"],
                "rank": row["rank"],
                "route_membership": row["route_membership"],
            }
            for row in hybrid.get("candidates") or ()
            if row["source_type"] == "PUBLIC_WEB"
        ],
        "selected_candidate_diagnostics": (
            [
                {
                    "compiled_object_id": row["compiled_object_id"],
                    "ticker": row["ticker"],
                    "source_type": row["source_type"],
                    "rank": row["rank"],
                    "material_reserved": row.get("material_reserved"),
                    "excerpt": " ".join(str(row["model_text"]).split())[:220],
                }
                for row in hybrid.get("candidates") or ()
            ]
            if request_id
            in {
                "REQ::DELL::SUPPLY_UPSTREAM_CAPACITY::V1",
                "REQ::DELL::SUPPLY_RELATIONSHIP::V1",
            }
            else []
        ),
        "material_requirement_receipts": [
            {
                "requirement_id": row.get("requirement_id"),
                "complete": row.get("complete"),
                "selected_candidate_ids": row.get("selected_candidate_ids"),
                "missing_product_ids": row.get("missing_product_ids"),
            }
            for row in material_selection.get("requirement_receipts") or ()
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-id", action="append", default=[])
    args = parser.parse_args(argv)
    requested_ids = set(args.request_id) or REQUEST_IDS
    unknown = requested_ids - REQUEST_IDS
    if unknown:
        raise ValueError(f"unsupported_diagnostic_request_ids:{sorted(unknown)}")
    program = _read(PROGRAM)
    requests = [
        row
        for row in program["evidence_requests"]
        if row["request_id"] in requested_ids
    ]
    blueprints = {
        request_id: value
        for request_id, value in _program_material_blueprints(program).items()
        if request_id in requested_ids
    }
    service = ResearchRetrievalService.from_runtime_paths(ROOT)
    principal = ResearchRetrievalPrincipal(
        mode="current",
        permissions=frozenset({"current_product:read"}),
    )
    execution = service.execute_current_runtime_requests(
        "DELL",
        requests,
        principal,
        material_requirement_blueprints=blueprints,
    )
    print(
        json.dumps(
            {
                "requests": [
                    _project(row) for row in execution["request_results"]
                ],
                "batch_summary": execution["summary"],
                "diagnostic_only": True,
                "files_written": False,
                "generation_model_calls": 0,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
