from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path[:0] = [str(ROOT), str(SRC)]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Keep the formal result readable. Model weights still load locally on CUDA;
# this only suppresses per-tensor progress output.
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")

from apps.workbench.backend.application.research_retrieval_service import (  # noqa: E402
    ResearchRetrievalPrincipal,
    ResearchRetrievalService,
)
from retrieval.query_plan import canonical_digest  # noqa: E402
from sec_agent.runtime_resource_registry import (  # noqa: E402
    load_runtime_resource_registry,
)


PROGRAM = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1_dell_proposition_coverage_execution_program_v1_1.json"
)
DEFAULT_PRIVATE_ROOT = (
    ROOT
    / "data"
    / "workbench_private"
    / "fin_0_1_3_s1_dell_proposition_coverage"
)
DEFAULT_PUBLIC = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1_dell_proposition_internal_execution_result_v1_0.json"
)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"dell_proposition_json_not_mapping:{path.name}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _write_new(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip().lower()


def _require_clean() -> None:
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if status:
        raise RuntimeError("dell_proposition_internal_clean_worktree_required")


def _route_states(request_result: Mapping[str, Any]) -> Counter[str]:
    states: Counter[str] = Counter()
    truth = request_result.get("route_execution_truth")
    if not isinstance(truth, Mapping):
        return states
    for family in ("narrative_route_requests", "typed_fact_route_requests"):
        for request in truth.get(family) or ():
            if not isinstance(request, Mapping):
                continue
            for route in request.get("routes") or ():
                if isinstance(route, Mapping):
                    state = str(route.get("execution_state") or "unknown")
                    states[state] += 1
    return states


def _program_material_blueprints(
    program: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Expand the Owner-reviewed program scope into explicit AI-free blueprints.

    The generic fallback must keep unfamiliar natural product intents unclassified.
    This program is different: every listed intent was deliberately frozen as a
    material axis for the seven DELL propositions.  The expansion stays local to
    this execution program and uses the same public MaterialRequirement contract
    that a later ResearchBlueprint or PlanDelta must submit.
    """

    contract = program.get("material_scope_blueprint")
    if not isinstance(contract, Mapping) or contract.get("mode") != (
        "explicit_all_visible_product_intents_hard_material_axes"
    ):
        raise ValueError("dell_proposition_material_scope_blueprint_missing")
    roles_by_request = contract.get("required_roles_by_request")
    if not isinstance(roles_by_request, Mapping):
        raise ValueError("dell_proposition_material_scope_roles_missing")
    metric_binding_roles = {
        str(value) for value in contract.get("metric_binding_roles") or ()
    }
    requests = {
        str(row.get("request_id") or ""): dict(row)
        for row in program.get("evidence_requests") or ()
        if isinstance(row, Mapping)
    }
    if not requests or set(roles_by_request) != set(requests):
        raise ValueError("dell_proposition_material_scope_request_set_invalid")
    result: dict[str, dict[str, Any]] = {}
    for request_id, request in requests.items():
        facets = [str(value) for value in request.get("requested_facet_ids") or ()]
        products = [str(value) for value in request.get("product_intents") or ()]
        metrics = [str(value) for value in request.get("metric_intents") or ()]
        entities = [str(value) for value in request.get("target_entities") or ()]
        roles = [str(value) for value in roles_by_request.get(request_id) or ()]
        if (
            len(facets) != 1
            or not products
            or not entities
            or not roles
            or len(roles) != len(set(roles))
        ):
            raise ValueError(
                f"dell_proposition_material_scope_request_invalid:{request_id}"
            )
        result[request_id] = {
            "material_requirements": [
                {
                    "facet_id": facets[0],
                    "role": role,
                    "metric_ids": metrics if role in metric_binding_roles else [],
                    "product_ids": products,
                    "target_entities": entities,
                    "period_mode": "any",
                    "fiscal_years": [],
                    "minimum_candidates": 1,
                    "coverage_mode": "collective_axes",
                    "metric_coverage_mode": "retrieval_context_only",
                    "product_coverage_mode": "all_of",
                }
                for role in roles
            ]
        }
    return result


def _request_public_row(request_result: Mapping[str, Any]) -> dict[str, Any]:
    request = dict(request_result.get("request") or {})
    hybrid = dict(request_result.get("hybrid_object_retrieval") or {})
    hybrid_summary = dict(hybrid.get("summary") or {})
    source_truth = dict(request_result.get("source_route_execution_truth") or {})
    source_summary = dict(source_truth.get("summary") or {})
    ceiling = dict(request_result.get("candidate_ceiling_provenance") or {})
    summary = dict(request_result.get("summary") or {})
    material = dict(hybrid.get("material_evidence") or {})
    selection = dict(material.get("selection") or {})
    requirement_receipts = [
        row
        for row in selection.get("requirement_receipts") or ()
        if isinstance(row, Mapping)
    ]
    route_states = _route_states(request_result)
    return {
        "request_id": request.get("request_id"),
        "cell_id": request.get("cell_id"),
        "requested_facet_ids": list(request.get("requested_facet_ids") or ()),
        "target_entities": list(request.get("target_entities") or ()),
        "snapshot": {
            "compiled_lane_count": int(summary.get("compiled_lane_count") or 0),
            "nonempty_lane_count": int(summary.get("nonempty_lane_count") or 0),
        },
        "hybrid_candidate_runtime": {
            key: hybrid_summary.get(key)
            for key in (
                "eligible_object_count",
                "bm25_first_stage_count",
                "qwen_first_stage_count",
                "typed_relationship_graph_requested",
                "typed_relationship_graph_executed",
                "typed_relationship_graph_first_stage_count",
                "union_count_before_source_quota",
                "selected_count",
                "selected_both_routes",
                "selected_bm25_only",
                "selected_qwen_only",
                "selected_typed_relationship_graph",
                "selected_typed_relationship_graph_only",
                "selected_candidate_count_by_owner",
                "owner_floor_unmet",
                "material_scope_ready",
                "material_set_complete",
            )
        },
        "material_requirements": {
            "requirement_count": len(requirement_receipts),
            "complete_count": sum(
                row.get("complete") is True for row in requirement_receipts
            ),
            "unmet_requirement_ids": list(
                selection.get("unmet_requirement_ids") or ()
            ),
        },
        "s2": {
            "resolved_count": int(summary.get("typed_fact_resolved_count") or 0),
            "typed_gap_count": int(summary.get("typed_fact_gap_count") or 0),
            "typed_conflict_count": int(
                summary.get("typed_fact_conflict_count") or 0
            ),
        },
        "local_route_execution_state_counts": dict(sorted(route_states.items())),
        "source_route": {
            "candidate_coverage_state": source_truth.get(
                "candidate_coverage_state"
            ),
            "supplement_route_required": source_truth.get(
                "supplement_route_required"
            ),
            "route_execution_state_counts": dict(
                source_summary.get("route_execution_state_counts") or {}
            ),
            "official_or_external_supplement_route_exhausted": source_summary.get(
                "official_or_external_supplement_route_exhausted"
            ),
            "public_information_gap_eligible": source_summary.get(
                "all_requirements_public_information_gap_eligible"
            ),
        },
        "candidate_ceiling": {
            "earliest_observed_limitation": ceiling.get(
                "earliest_observed_limitation"
            ),
            "public_information_gap_eligible": (
                dict(ceiling.get("gap_eligibility") or {}).get(
                    "public_information_gap_eligible"
                )
            ),
        },
    }


def build_public_projection(
    *,
    program: Mapping[str, Any],
    execution: Mapping[str, Any],
    private_ref: str,
    private_sha256: str,
    recorded_at: str,
    prepared_from_commit: str,
) -> dict[str, Any]:
    request_rows = [
        _request_public_row(row)
        for row in execution.get("request_results") or ()
        if isinstance(row, Mapping)
    ]
    by_id = {row["request_id"]: row for row in request_rows}
    propositions = []
    for proposition in program.get("propositions") or ():
        request_ids = list(proposition.get("request_ids") or ())
        rows = [by_id[request_id] for request_id in request_ids]
        propositions.append(
            {
                "proposition_id": proposition.get("proposition_id"),
                "business_question_zh": proposition.get("business_question_zh"),
                "request_ids": request_ids,
                "selected_candidate_count": sum(
                    int(
                        row["hybrid_candidate_runtime"].get("selected_count") or 0
                    )
                    for row in rows
                ),
                "material_scope_ready_request_count": sum(
                    row["hybrid_candidate_runtime"].get("material_scope_ready")
                    is True
                    for row in rows
                ),
                "material_set_complete_request_count": sum(
                    row["hybrid_candidate_runtime"].get("material_set_complete")
                    is True
                    for row in rows
                ),
                "source_supplement_required_request_count": sum(
                    row["source_route"].get("supplement_route_required") is True
                    for row in rows
                ),
                "typed_fact_resolved_count": sum(
                    int(row["s2"].get("resolved_count") or 0) for row in rows
                ),
                "typed_fact_gap_count": sum(
                    int(row["s2"].get("typed_gap_count") or 0) for row in rows
                ),
                "internal_coverage_state": (
                    "material_candidate_complete"
                    if all(
                        row["hybrid_candidate_runtime"].get("material_set_complete")
                        is True
                        for row in rows
                    )
                    else "external_or_review_successor_required"
                ),
            }
        )
    summary = dict(execution.get("summary") or {})
    body = {
        "schema_version": "fin_ia_s1_dell_proposition_internal_execution_result_v1_0",
        "status": "dell_proposition_ai_free_internal_execution_materialized",
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "case_key": "DELL",
        "research_as_of": program.get("research_as_of"),
        "program_id": program.get("program_id"),
        "summary": summary,
        "propositions": propositions,
        "requests": request_rows,
        "private_execution_ref": private_ref,
        "private_execution_sha256": private_sha256,
        "authority": {
            "candidate_decision_complete": False,
            "evidence_promotion_authorized": False,
            "numeric_authority_granted_by_text_retrieval": False,
            "public_information_gap_authorized": False,
            "evidence_pack_readiness_authorized": False,
            "dynamic_single_unit_authorized": False,
        },
        "known_boundary": (
            "This result proves only the AI-free internal S1/S2 route execution for "
            "the seven DELL proposition families. Ranked rows remain candidates. "
            "External source exhaustion, CandidateDecision, Evidence Gate, current "
            "Pack promotion, S2 successor compilation and dynamic research remain "
            "separate successor gates."
        ),
    }
    return {**body, "result_digest": canonical_digest(body)}


def run(
    *,
    attempt_id: str,
    private_output: Path,
    public_output: Path,
    program_path: Path = PROGRAM,
) -> dict[str, Any]:
    _require_clean()
    program = _read_json(program_path)
    service = ResearchRetrievalService.from_runtime_paths(ROOT)
    principal = ResearchRetrievalPrincipal(
        mode="current", permissions=frozenset({"current_product:read"})
    )
    execution = service.execute_current_runtime_requests(
        "DELL",
        program["evidence_requests"],
        principal,
        material_requirement_blueprints=_program_material_blueprints(program),
    )
    recorded_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    prepared_from_commit = _head()
    registry = load_runtime_resource_registry(ROOT)
    private_body = {
        "schema_version": "fin_ia_s1_dell_proposition_internal_execution_private_v1_0",
        "status": "dell_proposition_ai_free_internal_execution_complete",
        "attempt_id": attempt_id,
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "program_binding": {
            "ref": _relative(program_path),
            "sha256": _sha256(program_path),
            "program_id": program.get("program_id"),
        },
        "runtime_registry_binding": {
            "registry_id": registry.registry_id,
            "resource_canonical_digest": registry.resource_canonical_digest,
        },
        "product_projection": execution,
    }
    private_result = {
        **private_body,
        "result_digest": canonical_digest(private_body),
    }
    _write_new(private_output, private_result)
    public_result = build_public_projection(
        program=program,
        execution=execution,
        private_ref=_relative(private_output),
        private_sha256=_sha256(private_output),
        recorded_at=recorded_at,
        prepared_from_commit=prepared_from_commit,
    )
    _write_new(public_output, public_result)
    return public_result


def _resolve(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run and materialize the AI-free DELL proposition coverage batch."
    )
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--program", default=str(PROGRAM))
    parser.add_argument("--private-output")
    parser.add_argument("--public-output", default=str(DEFAULT_PUBLIC))
    args = parser.parse_args(argv)
    private_output = (
        _resolve(args.private_output)
        if args.private_output
        else DEFAULT_PRIVATE_ROOT / args.attempt_id / "internal_runtime_result.json"
    )
    result = run(
        attempt_id=args.attempt_id,
        private_output=private_output,
        public_output=_resolve(args.public_output),
        program_path=_resolve(args.program),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
