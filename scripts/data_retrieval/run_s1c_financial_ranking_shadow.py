from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from retrieval.contracts import (  # noqa: E402
    load_evidence_request,
    load_financial_research_kernel,
)
from retrieval.hybrid_candidate_runtime import (  # noqa: E402
    LocalQwenHybridCandidateRuntime,
)
from retrieval.query_atom_shadow import load_query_atoms  # noqa: E402
from retrieval.query_plan import canonical_digest  # noqa: E402
from retrieval.route_compiler import (  # noqa: E402
    load_query_object_fact_route_policy,
)


AUTHORITY_SCHEMA_VERSION = (
    "fin_ia_s1c_financial_ranking_shadow_authority_v1_0"
)
RESULT_SCHEMA_VERSION = "fin_ia_s1c_financial_ranking_shadow_result_v1_0"


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


def _sha256_lf(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def _validate_authority(authority: Mapping[str, Any]) -> dict[str, Path]:
    if authority.get("schema_version") != AUTHORITY_SCHEMA_VERSION:
        raise ValueError("financial_ranking_shadow_authority_schema_invalid")
    if authority.get("status") != (
        "pre_registered_zero_network_local_embedding_shadow_not_runtime_promotion"
    ):
        raise ValueError("financial_ranking_shadow_authority_status_invalid")
    permissions = authority.get("authority")
    if permissions != {
        "network_calls_authorized": False,
        "generation_model_calls_authorized": False,
        "local_embedding_inference_authorized": True,
        "runtime_promotion_authorized": False,
        "candidate_is_not_evidence": True,
        "numeric_authority": False,
        "s1_complete_claimed": False,
    }:
        raise ValueError("financial_ranking_shadow_authority_invalid")
    bindings = authority["bound_inputs"]
    paths = {
        key: _resolve(bindings[f"{key}_ref"])
        for key in ("runtime_policy", "qrels", "kernel", "route_policy")
    }
    for key, path in paths.items():
        if _sha256_lf(path) != str(bindings[f"{key}_sha256_lf"]):
            raise ValueError(f"financial_ranking_shadow_binding_drift:{key}")
    return paths


def _judgement(atom: Any, object_id: str) -> str:
    if object_id in atom.positive_object_ids:
        return "positive"
    if object_id in atom.hard_negative_object_ids:
        return "hard_negative"
    if object_id in atom.unjudged_object_ids:
        return "unjudged"
    return "unlabelled"


def _hard_boundary_violations(
    candidates: Sequence[Mapping[str, Any]],
    request: Any,
) -> int:
    target = request.target_entities[0]
    as_of = request.research_as_of
    accepted_sources = {value.upper() for value in request.acceptable_sources}
    fiscal_years = set(request.period.fiscal_years)
    count = 0
    for candidate in candidates:
        if str(candidate["ticker"]).upper() != target:
            count += 1
        if date.fromisoformat(str(candidate["publication_date"])) > as_of:
            count += 1
        if str(candidate["source_type"]).upper() not in accepted_sources:
            count += 1
        if fiscal_years and candidate.get("fiscal_year") not in fiscal_years:
            count += 1
    return count


def _route_row(
    result: Mapping[str, Any],
    *,
    atom: Any,
    request: Any,
    top_k: int,
) -> dict[str, Any]:
    candidates = list(result["candidates"])
    positive_ranks = [
        index
        for index, candidate in enumerate(candidates, start=1)
        if str(candidate["compiled_object_id"]) in atom.positive_object_ids
    ]
    hard_negative_top5 = sum(
        str(candidate["compiled_object_id"]) in atom.hard_negative_object_ids
        for candidate in candidates[:5]
    )
    parser_fragments_top5 = sum(
        str(candidate.get("model_text") or "").lstrip().startswith("-based ")
        for candidate in candidates[:5]
    )
    authority_violations = sum(
        candidate.get("candidate_not_evidence") is not True
        or candidate.get("numeric_authority") is not False
        for candidate in candidates
    )
    return {
        "positive_target_available": bool(atom.positive_object_ids),
        "best_positive_rank": min(positive_ranks, default=None),
        "positive_target_in_top_k": bool(
            positive_ranks and min(positive_ranks) <= top_k
        ),
        "reciprocal_rank": (
            round(1.0 / min(positive_ranks), 12) if positive_ranks else 0.0
        ),
        "hard_negative_in_top5_count": hard_negative_top5,
        "known_parser_fragment_in_top5_count": parser_fragments_top5,
        "hard_boundary_violation_count": _hard_boundary_violations(
            candidates, request
        ),
        "candidate_authority_violation_count": authority_violations,
        "top_candidates": [
            {
                "rank": index,
                "compiled_object_id": str(candidate["compiled_object_id"]),
                "judgement": _judgement(atom, str(candidate["compiled_object_id"])),
                "ticker": str(candidate["ticker"]),
                "publication_date": str(candidate["publication_date"]),
                "source_type": str(candidate["source_type"]),
                "object_kind": str(candidate["object_kind"]),
                "text_excerpt": str(candidate["model_text"])[:280],
                "financial_ranking": candidate.get("financial_ranking"),
            }
            for index, candidate in enumerate(candidates[:top_k], start=1)
        ],
    }


def _aggregate(rows: Sequence[Mapping[str, Any]], route: str) -> dict[str, Any]:
    route_rows = [row[route] for row in rows]
    positive_rows = [row for row in route_rows if row["positive_target_available"]]
    return {
        "positive_atom_count": len(positive_rows),
        "positive_target_in_top10_count": sum(
            row["positive_target_in_top_k"] for row in positive_rows
        ),
        "positive_target_in_top10_rate": round(
            sum(row["positive_target_in_top_k"] for row in positive_rows)
            / len(positive_rows),
            6,
        )
        if positive_rows
        else None,
        "mean_reciprocal_rank": round(
            sum(float(row["reciprocal_rank"]) for row in positive_rows)
            / len(positive_rows),
            6,
        )
        if positive_rows
        else None,
        "hard_negative_in_top5_count": sum(
            int(row["hard_negative_in_top5_count"]) for row in route_rows
        ),
        "known_parser_fragment_in_top5_count": sum(
            int(row["known_parser_fragment_in_top5_count"]) for row in route_rows
        ),
        "hard_boundary_violation_count": sum(
            int(row["hard_boundary_violation_count"]) for row in route_rows
        ),
        "candidate_authority_violation_count": sum(
            int(row["candidate_authority_violation_count"]) for row in route_rows
        ),
    }


def run(authority_path: Path) -> dict[str, Any]:
    authority = _read_json(authority_path)
    paths = _validate_authority(authority)
    kernel = load_financial_research_kernel(_read_json(paths["kernel"]))
    route_policy = load_query_object_fact_route_policy(
        _read_json(paths["route_policy"]), kernel
    )
    atoms = load_query_atoms(_read_json(paths["qrels"]))
    requests = [
        load_evidence_request(atom.request_payload, kernel) for atom in atoms
    ]
    runtime = LocalQwenHybridCandidateRuntime.from_policy(
        ROOT, _read_json(paths["runtime_policy"])
    )
    comparisons = runtime.compare_financial_ranking(
        requests,
        kernel=kernel,
        route_policy=route_policy,
    )
    top_k = int(authority["comparison"]["top_k"])
    rows: list[dict[str, Any]] = []
    for atom, request, comparison in zip(atoms, requests, comparisons):
        rows.append(
            {
                "atom_id": atom.atom_id,
                "case_key": request.case_key,
                "target_entity": request.target_entities[0],
                "facet_id": request.requested_facet_ids[0],
                "legacy": _route_row(
                    comparison["legacy"],
                    atom=atom,
                    request=request,
                    top_k=top_k,
                ),
                "financial": _route_row(
                    comparison["financial"],
                    atom=atom,
                    request=request,
                    top_k=top_k,
                ),
            }
        )
    legacy = _aggregate(rows, "legacy")
    financial = _aggregate(rows, "financial")
    gates = authority["decision_gates"]
    gate_results = {
        "hard_filter_boundary": financial["hard_boundary_violation_count"]
        <= int(gates["hard_filter_violation_maximum"]),
        "positive_target_in_top10_not_worse": financial[
            "positive_target_in_top10_count"
        ]
        >= legacy["positive_target_in_top10_count"],
        "mean_reciprocal_rank_not_worse": financial["mean_reciprocal_rank"]
        >= legacy["mean_reciprocal_rank"],
        "hard_negative_in_top5_not_worse": financial[
            "hard_negative_in_top5_count"
        ]
        <= legacy["hard_negative_in_top5_count"],
        "known_parser_fragment_in_top5": financial[
            "known_parser_fragment_in_top5_count"
        ]
        <= int(gates["known_parser_fragment_in_top5_maximum"]),
        "candidate_authority_boundary": financial[
            "candidate_authority_violation_count"
        ]
        <= int(gates["candidate_authority_violation_maximum"]),
    }
    decision = (
        "development_cases_pass_holdout_proof_required_before_runtime_promotion"
        if all(gate_results.values())
        else "development_cases_failed_keep_legacy_runtime_and_disposition_root_cause"
    )
    unsigned = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "completed_zero_network_local_embedding_shadow",
        "recorded_at": "2026-08-13",
        "experiment_id": str(authority["experiment_id"]),
        "authority_ref": _relative(authority_path),
        "authority_sha256_lf": _sha256_lf(authority_path),
        "summary": {"legacy": legacy, "financial": financial},
        "gate_results": gate_results,
        "decision": decision,
        "rows": rows,
        "authority": dict(authority["authority"]),
    }
    return {**unsigned, "result_digest": canonical_digest(unsigned)}


def _compact(result: Mapping[str, Any], full_path: Path) -> dict[str, Any]:
    return {
        "schema_version": "fin_ia_s1c_financial_ranking_shadow_summary_v1_0",
        "status": result["status"],
        "recorded_at": result["recorded_at"],
        "experiment_id": result["experiment_id"],
        "authority_ref": result["authority_ref"],
        "authority_sha256_lf": result["authority_sha256_lf"],
        "full_result_ref": _relative(full_path),
        "full_result_sha256_lf": _sha256_lf(full_path),
        "summary": result["summary"],
        "gate_results": result["gate_results"],
        "decision": result["decision"],
        "result_digest": result["result_digest"],
        "authority": result["authority"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--authority",
        default="configs/retrieval/fin_ia_0_1_3_s1c_financial_ranking_shadow_authority_v1_0.json",
    )
    parser.add_argument(
        "--full-output-root",
        default="data/workbench_private/fin_0_1_3_s1c_financial_ranking_shadow/v1",
    )
    parser.add_argument(
        "--summary-output",
        default="configs/retrieval/fin_ia_0_1_3_s1c_financial_ranking_shadow_result_v1_0.json",
    )
    args = parser.parse_args()
    result = run(_resolve(args.authority))
    full_root = _resolve(args.full_output_root)
    full_path = full_root / f"full_result_{result['result_digest']}.json"
    _write_json(full_path, result)
    summary = _compact(result, full_path)
    summary_path = _resolve(args.summary_output)
    _write_json(summary_path, summary)
    print(
        json.dumps(
            {
                "summary_output": _relative(summary_path),
                "full_output": _relative(full_path),
                "summary": result["summary"],
                "gate_results": result["gate_results"],
                "decision": result["decision"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
