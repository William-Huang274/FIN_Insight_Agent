from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score SEC benchmark run outputs.")
    parser.add_argument("--cases-path", default="eval/sec_cases/test_cases_v1.jsonl")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output-path", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cases = {str(row.get("case_id")): row for row in _read_jsonl(REPO_ROOT / args.cases_path)}
    run_dir = REPO_ROOT / args.run_dir
    agent_rows = _read_jsonl(run_dir / "agent_outputs.jsonl")
    claim_rows = {(str(r.get("case_id")), str(r.get("mode"))): r for r in _read_jsonl(run_dir / "claim_verification.jsonl")}
    score_rows = {(str(r.get("case_id")), str(r.get("mode"))): r for r in _read_jsonl(run_dir / "scores.jsonl")}

    results: list[dict[str, Any]] = []
    for agent in agent_rows:
        case_id = str(agent.get("case_id"))
        mode = str(agent.get("mode"))
        case = cases.get(case_id, {})
        claim = claim_rows.get((case_id, mode), {})
        score_row = score_rows.get((case_id, mode), {})
        result = _score_one(case, agent, claim, score_row)
        results.append(result)

    summary = _summary(results)
    report = {
        "schema_version": "sec_benchmark_scored_report_v0.1",
        "cases_path": str((REPO_ROOT / args.cases_path).resolve()),
        "run_dir": str(run_dir.resolve()),
        "summary": summary,
        "results": results,
    }
    output_path = Path(args.output_path) if args.output_path else (run_dir / "scored_report.json")
    if not output_path.is_absolute():
        output_path = REPO_ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output_path": str(output_path),
                "run_count": summary["run_count"],
                "scored_count": summary["scored_count"],
                "mean_score": summary["mean_score"],
                "failure_type_counts": summary["failure_type_counts"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _score_one(case: dict[str, Any], agent: dict[str, Any], claim: dict[str, Any], score_row: dict[str, Any]) -> dict[str, Any]:
    case_id = str(agent.get("case_id"))
    mode = str(agent.get("mode"))
    task_type = str(case.get("task_type") or "")
    score_weights = case.get("score_weights") or {"retrieval": 2, "factuality": 3, "coverage": 2, "synthesis": 2, "citation": 1}
    max_points = sum(float(v) for v in score_weights.values())

    if str(agent.get("status")) == "skipped":
        return {
            "case_id": case_id,
            "mode": mode,
            "task_type": task_type,
            "status": "not_scored",
            "score_total": None,
            "score_pct": None,
            "dimension_scores": None,
            "failure_types": score_row.get("failure_types") or ["not_scored"],
            "notes": list(score_row.get("notes") or []),
        }

    if score_row.get("score_total") is not None:
        total = float(score_row.get("score_total"))
        return {
            "case_id": case_id,
            "mode": mode,
            "task_type": task_type,
            "status": "scored_from_backend",
            "score_total": round(total, 4),
            "score_pct": round(total / max_points, 4) if max_points else 0.0,
            "dimension_scores": score_row.get("scores"),
            "failure_types": score_row.get("failure_types") or [],
            "notes": list(score_row.get("notes") or []),
        }

    # Fallback rubric when synthesis backend does not provide score.
    retrieval = float(score_weights.get("retrieval", 2))
    factuality = float(score_weights.get("factuality", 3))
    coverage = float(score_weights.get("coverage", 2))
    synthesis = float(score_weights.get("synthesis", 2))
    citation = float(score_weights.get("citation", 1))

    answer_present = agent.get("answer") is not None
    unsupported_count = claim.get("unsupported_claim_count")
    if unsupported_count is None:
        unsupported_count = 0

    retrieval_score = retrieval if answer_present else 0.0
    factuality_score = max(0.0, factuality - min(factuality, float(unsupported_count) * 1.5))
    text = json.dumps(agent.get("answer") or {}, ensure_ascii=False).lower()
    gold_points = [str(p).lower() for p in case.get("gold_points") or []]
    hit_count = sum(1 for point in gold_points if any(token in text for token in _point_tokens(point)))
    coverage_ratio = (hit_count / len(gold_points)) if gold_points else 0.0
    coverage_score = round(coverage * coverage_ratio, 4)
    synthesis_score = synthesis if answer_present and len(text) > 80 else (synthesis * 0.4 if answer_present else 0.0)
    citation_score = citation if str(claim.get("status") or "").startswith("pass") else 0.0

    failure_types = list(score_row.get("failure_types") or [])
    if not answer_present:
        failure_types.append("format_failure")
    if unsupported_count:
        failure_types.append("unsupported_claim")
    if coverage_ratio < 0.5:
        failure_types.append("missing_required_point")
    if citation_score == 0.0:
        failure_types.append("citation_missing")
    if answer_present and synthesis_score < synthesis * 0.6:
        failure_types.append("weak_synthesis")

    if task_type.startswith("anti_hallucination"):
        if unsupported_count == 0 and answer_present:
            # Trap case answered without unsupported flags: penalize hard.
            factuality_score = 0.0
            failure_types.append("hallucination")

    total = retrieval_score + factuality_score + coverage_score + synthesis_score + citation_score
    return {
        "case_id": case_id,
        "mode": mode,
        "task_type": task_type,
        "status": "scored_fallback",
        "score_total": round(total, 4),
        "score_pct": round(total / max_points, 4) if max_points else 0.0,
        "dimension_scores": {
            "retrieval": round(retrieval_score, 4),
            "factuality": round(factuality_score, 4),
            "coverage": round(coverage_score, 4),
            "synthesis": round(synthesis_score, 4),
            "citation": round(citation_score, 4),
        },
        "failure_types": sorted(set(failure_types)),
        "notes": list(score_row.get("notes") or []),
    }


def _point_tokens(point: str) -> list[str]:
    tokens = [token.strip() for token in point.replace("/", " ").replace("-", " ").split() if len(token.strip()) >= 4]
    return tokens[:6] or [point]


def _summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [row for row in results if row.get("score_total") is not None]
    failure_counts = Counter(
        failure
        for row in results
        for failure in row.get("failure_types") or []
    )
    return {
        "run_count": len(results),
        "scored_count": len(scored),
        "mean_score": round(sum(float(row.get("score_total") or 0.0) for row in scored) / len(scored), 4) if scored else None,
        "mean_score_pct": round(sum(float(row.get("score_pct") or 0.0) for row in scored) / len(scored), 4) if scored else None,
        "failure_type_counts": dict(sorted(failure_counts.items())),
        "status_counts": dict(sorted(Counter(str(row.get("status")) for row in results).items())),
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    main()
