from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Gold vs Pipeline scored comparison gate.")
    parser.add_argument("--gold-scored-report", required=True)
    parser.add_argument("--pipeline-scored-report", required=True)
    parser.add_argument("--max-score-drop", type=float, default=0.25, help="Maximum allowed pipeline drop vs gold score_pct.")
    parser.add_argument("--min-overlap-cases", type=int, default=2)
    parser.add_argument("--output-path", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    gold = _read_json(REPO_ROOT / args.gold_scored_report)
    pipeline = _read_json(REPO_ROOT / args.pipeline_scored_report)
    gold_map = {(str(r.get("case_id")), str(r.get("mode"))): r for r in gold.get("results") or []}
    pipe_map = {(str(r.get("case_id")), str(r.get("mode"))): r for r in pipeline.get("results") or []}

    comparable: list[dict[str, Any]] = []
    for (case_id, mode), g in gold_map.items():
        if mode != "gold_context":
            continue
        p = pipe_map.get((case_id, "pipeline_context"))
        if not p:
            continue
        if g.get("score_pct") is None or p.get("score_pct") is None:
            continue
        drop = float(g.get("score_pct")) - float(p.get("score_pct"))
        comparable.append(
            {
                "case_id": case_id,
                "gold_score_pct": g.get("score_pct"),
                "pipeline_score_pct": p.get("score_pct"),
                "score_drop": round(drop, 4),
                "pass": drop <= args.max_score_drop,
            }
        )

    pass_count = sum(1 for r in comparable if r["pass"])
    can_enter = len(comparable) >= args.min_overlap_cases and pass_count == len(comparable)
    report = {
        "schema_version": "sec_benchmark_gold_vs_pipeline_gate_v0.1",
        "gold_scored_report": str((REPO_ROOT / args.gold_scored_report).resolve()),
        "pipeline_scored_report": str((REPO_ROOT / args.pipeline_scored_report).resolve()),
        "max_score_drop": args.max_score_drop,
        "min_overlap_cases": args.min_overlap_cases,
        "comparable_case_count": len(comparable),
        "pass_count": pass_count,
        "fail_count": len(comparable) - pass_count,
        "can_enter_gate": can_enter,
        "results": comparable,
    }
    output_path = Path(args.output_path) if args.output_path else REPO_ROOT / "reports/quality/sec_benchmark_gold_vs_pipeline_gate.json"
    if not output_path.is_absolute():
        output_path = REPO_ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output_path": str(output_path), "can_enter_gate": can_enter, "comparable_case_count": len(comparable)}, ensure_ascii=False, indent=2))


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
