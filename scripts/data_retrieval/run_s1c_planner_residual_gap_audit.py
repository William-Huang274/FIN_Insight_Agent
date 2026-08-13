from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from apps.workbench.backend.application.research_retrieval_service import (  # noqa: E402
    CURRENT_HYBRID_CANDIDATE_RUNTIME_POLICY_RESOURCE_ID,
    CURRENT_RANKING_COMPARISON_RESOURCE_ID,
    CURRENT_RETRIEVAL_SNAPSHOT_RESOURCE_ID,
    ResearchRetrievalPrincipal,
    ResearchRetrievalService,
)
from retrieval.contracts import load_financial_research_kernel  # noqa: E402
from retrieval.hybrid_candidate_runtime import (  # noqa: E402
    LazyLocalQwenHybridCandidateRuntime,
)
from retrieval.route_compiler import (  # noqa: E402
    load_query_object_fact_route_policy,
)
from sec_agent.research.planning import (  # noqa: E402
    compile_research_objective,
    load_research_planning_policy,
)
from sec_agent.runtime_bridge.paths import resolve_runtime_paths  # noqa: E402
from sec_agent.runtime_resource_registry import (  # noqa: E402
    read_registered_runtime_json,
)


AUTHORITY_SCHEMA_VERSION = (
    "fin_ia_s1c_planner_residual_gap_audit_authority_v1_0"
)
AUTHORITY_SUCCESSOR_SCHEMA_VERSION = (
    "fin_ia_s1c_planner_residual_gap_audit_authority_v1_1"
)
SUMMARY_SCHEMA_VERSION = "fin_ia_s1c_planner_residual_gap_audit_summary_v1_0"


def _resolve(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{path.name}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_digest(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def _validate_authority(authority: Mapping[str, Any]) -> dict[str, Path]:
    schema_version = str(authority.get("schema_version") or "")
    if schema_version not in {
        AUTHORITY_SCHEMA_VERSION,
        AUTHORITY_SUCCESSOR_SCHEMA_VERSION,
    }:
        raise ValueError("planner_residual_gap_authority_schema_invalid")
    expected_status = (
        "zero_network_zero_generation_successor_contract_product_input_audit"
        if schema_version == AUTHORITY_SUCCESSOR_SCHEMA_VERSION
        else "zero_network_zero_generation_saved_planner_product_input_audit"
    )
    if authority.get("status") != expected_status:
        raise ValueError("planner_residual_gap_authority_status_invalid")
    expected_authority = {
        "network_calls_authorized": False,
        "generation_model_calls_authorized": False,
        "local_embedding_inference_authorized": True,
        "candidate_is_not_evidence": True,
        "numeric_authority_remains_s2": True,
        "runtime_promotion_authorized": False,
        "s1d_source_execution_authorized": False,
        "s1_or_s3_complete_claimed": False,
    }
    if authority.get("authority") != expected_authority:
        raise ValueError("planner_residual_gap_authority_invalid")
    bound = authority.get("bound_inputs")
    if not isinstance(bound, Mapping):
        raise ValueError("planner_residual_gap_bound_inputs_invalid")
    paths: dict[str, Path] = {}
    input_keys = ["objective", "planner_atoms", "runtime_registry"]
    if schema_version == AUTHORITY_SUCCESSOR_SCHEMA_VERSION:
        input_keys.extend(["kernel", "route_policy", "planning_policy"])
    if schema_version == AUTHORITY_SUCCESSOR_SCHEMA_VERSION:
        input_keys.append("hybrid_policy")
    for key in input_keys:
        path = _resolve(str(bound.get(f"{key}_ref") or ""))
        if not path.is_file():
            raise ValueError(f"planner_residual_gap_input_missing:{key}")
        if _sha256(path) != str(bound.get(f"{key}_sha256") or ""):
            raise ValueError(f"planner_residual_gap_input_drift:{key}")
        paths[key] = path
    if schema_version == AUTHORITY_SUCCESSOR_SCHEMA_VERSION:
        rebind = authority.get("planner_atom_rebind")
        if not isinstance(rebind, Mapping) or dict(rebind) != {
            "mode": "deterministic_objective_id_rebind_only",
            "source_objective_id": "ROC::c5023a44800a7b8ad60ebaf5",
            "successor_objective_id": "ROC::ae1da4bf36a11142a1d03e15",
            "preserve_atom_bodies_exactly": True,
            "model_rerun_authorized": False,
        }:
            raise ValueError("planner_residual_gap_atom_rebind_invalid")
    return paths


def _successor_service_and_inputs(
    authority: Mapping[str, Any],
    paths: Mapping[str, Path],
) -> tuple[ResearchRetrievalService, dict[str, Any], dict[str, Any], dict[str, Any]]:
    kernel = load_financial_research_kernel(_read_json(paths["kernel"]))
    route_policy = load_query_object_fact_route_policy(
        _read_json(paths["route_policy"]), kernel
    )
    planning_policy = load_research_planning_policy(
        _read_json(paths["planning_policy"]), route_policy
    )
    objective_payload = _read_json(paths["objective"])
    objective = compile_research_objective(
        objective_payload,
        kernel=kernel,
        policy=planning_policy,
    )
    planner_payload = _read_json(paths["planner_atoms"])
    source_objective_id = str(planner_payload.get("objective_id") or "")
    rebind = authority["planner_atom_rebind"]
    if source_objective_id != rebind["source_objective_id"]:
        raise ValueError("planner_residual_gap_atom_source_objective_drift")
    if objective.objective_id != rebind["successor_objective_id"]:
        raise ValueError("planner_residual_gap_atom_successor_objective_drift")
    atom_body_digest_before = _canonical_digest(
        {"atoms": list(planner_payload.get("atoms") or [])}
    )
    planner_payload = dict(planner_payload)
    planner_payload["objective_id"] = objective.objective_id
    atom_body_digest_after = _canonical_digest(
        {"atoms": list(planner_payload.get("atoms") or [])}
    )
    if atom_body_digest_before != atom_body_digest_after:
        raise ValueError("planner_residual_gap_atom_body_drift")
    runtime_paths = resolve_runtime_paths(ROOT)
    hybrid_runtime = LazyLocalQwenHybridCandidateRuntime(
        ROOT,
        _read_json(paths["hybrid_policy"]),
    )
    service = ResearchRetrievalService(
        snapshot=read_registered_runtime_json(
            ROOT, CURRENT_RETRIEVAL_SNAPSHOT_RESOURCE_ID
        ),
        ranking_comparison=read_registered_runtime_json(
            ROOT, CURRENT_RANKING_COMPARISON_RESOURCE_ID
        ),
        kernel=kernel,
        route_policy=route_policy,
        planning_policy=planning_policy,
        hybrid_candidate_runtime=hybrid_runtime,
        company_financial_fact_mart_path=(
            runtime_paths.company_financial_fact_mart_path
        ),
    )
    rebind_record = {
        **dict(rebind),
        "atom_body_digest_before": atom_body_digest_before,
        "atom_body_digest_after": atom_body_digest_after,
        "atom_body_count": len(planner_payload.get("atoms") or []),
    }
    return service, objective_payload, planner_payload, rebind_record


def _candidate_excerpt(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "compiled_object_id": str(candidate.get("compiled_object_id") or ""),
        "source_record_id": str(candidate.get("source_record_id") or ""),
        "ticker": str(candidate.get("ticker") or ""),
        "publication_date": str(candidate.get("publication_date") or ""),
        "source_type": str(candidate.get("source_type") or ""),
        "object_kind": str(candidate.get("object_kind") or ""),
        "route_ranks": dict(candidate.get("route_ranks") or {}),
        "text_excerpt": str(candidate.get("model_text") or "")[:360],
    }


def _request_summary(result: Mapping[str, Any], *, top_k: int) -> dict[str, Any]:
    request = result["request"]
    hybrid = result.get("hybrid_object_retrieval") or {}
    hybrid_candidates = hybrid.get("candidates") or []
    typed_fact_results = result.get("typed_fact_results") or []
    return {
        "request_id": str(request["request_id"]),
        "slot_id": str(result["query_plan"]["lanes"][0]["slot_id"]),
        "facet_id": str(request["requested_facet_ids"][0]),
        "target_entity": str(request["target_entities"][0]),
        "target_entities": list(request["target_entities"]),
        "metric_intents": list(request.get("metric_intents") or []),
        "product_intents": list(request.get("product_intents") or []),
        "snapshot_candidate_count": sum(
            len(row.get("candidates") or []) for row in result.get("lanes") or []
        ),
        "hybrid_candidate_count": len(hybrid_candidates),
        "hybrid_selected_candidate_count_by_owner": dict(
            (hybrid.get("summary") or {}).get(
                "selected_candidate_count_by_owner"
            )
            or {}
        ),
        "hybrid_owner_floor_unmet": list(
            (hybrid.get("summary") or {}).get("owner_floor_unmet") or []
        ),
        "missing_required_source_roles": sorted(
            {
                role
                for row in result.get("lanes") or []
                for role in row.get("missing_required_source_roles") or []
            }
        ),
        "typed_fact_statuses": [
            {
                "metric_id": str(row.get("metric_id") or ""),
                "status": str(row.get("status") or ""),
                "fact_count": len(row.get("facts") or []),
                "typed_gap": row.get("typed_gap"),
            }
            for row in typed_fact_results
        ],
        "typed_gaps": list(result.get("typed_gaps") or []),
        "top_hybrid_candidates": [
            _candidate_excerpt(row) for row in hybrid_candidates[:top_k]
        ],
        "candidate_state": "candidate_not_evidence",
    }


def run(authority_path: Path) -> dict[str, Any]:
    authority = _read_json(authority_path)
    paths = _validate_authority(authority)
    successor = (
        authority.get("schema_version") == AUTHORITY_SUCCESSOR_SCHEMA_VERSION
    )
    if successor:
        service, objective, planner_atoms, rebind_record = (
            _successor_service_and_inputs(authority, paths)
        )
    else:
        service = ResearchRetrievalService.from_runtime_paths(ROOT)
        objective = _read_json(paths["objective"])
        planner_atoms = _read_json(paths["planner_atoms"])
        rebind_record = {
            "mode": "none_original_objective_and_atoms",
            "model_rerun_authorized": False,
        }
    principal = ResearchRetrievalPrincipal(
        mode="current",
        permissions=frozenset({"current_product:read"}),
    )
    projection = service.execute_controlled_plan(
        "DELL", objective, planner_atoms, principal
    )
    top_k = int(authority["audit_contract"]["top_candidates_per_request"])
    request_rows = [
        _request_summary(row, top_k=top_k)
        for row in projection["request_results"]
    ]
    full_body = {
        "schema_version": "fin_ia_s1c_planner_residual_gap_audit_full_v1_0",
        "status": "completed_zero_network_zero_generation_runtime_audit",
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha256(authority_path),
        "projection": projection,
        "planner_atom_rebind": rebind_record,
        "request_summaries": request_rows,
        "known_boundary": (
            "This result preserves candidates and typed facts exactly as returned "
            "by the current runtime. It does not promote a candidate to Evidence, "
            "decide that a weak ranking is a missing source, or authorize S1-D."
        ),
    }
    result_digest = _canonical_digest(full_body)
    output_directory = _resolve(authority["outputs"]["private_output_directory"])
    full_path = output_directory / f"full_result_{result_digest}.json"
    _write_json(full_path, {**full_body, "result_digest": result_digest})
    summary = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "completed_requires_business_residual_gap_adjudication",
        "recorded_at": str(authority["recorded_at"]),
        "audit_id": str(authority["audit_id"]),
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha256(authority_path),
        "full_result_ref": _relative(full_path),
        "full_result_sha256": _sha256(full_path),
        "runtime_summary": dict(projection["summary"]),
        "selection": dict(projection["compiled_plan"]["selection"]),
        "selected_facets": [row["facet_id"] for row in request_rows],
        "deferred_atoms": list(projection["compiled_plan"]["deferred_atoms"]),
        "planner_atom_rebind": rebind_record,
        "request_observations": request_rows,
        "decision": (
            "Do not tune another ranker or enter broad source acquisition. "
            "Adjudicate each request as candidate-selection error, S2 typed-fact "
            "gap, true S1-D source gap, or supported before any source call."
        ),
        "authority": dict(authority["authority"]),
        "result_digest": result_digest,
    }
    summary_path = _resolve(authority["outputs"]["tracked_summary_ref"])
    _write_json(summary_path, summary)
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--authority",
        default=(
            "configs/retrieval/"
            "fin_ia_0_1_3_s1c_planner_residual_gap_audit_authority_v1_0.json"
        ),
    )
    args = parser.parse_args(argv)
    result = run(_resolve(args.authority))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
