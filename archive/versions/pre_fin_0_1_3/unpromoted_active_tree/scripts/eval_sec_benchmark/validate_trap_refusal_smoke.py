from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate anti-hallucination trap refusal smoke from benchmark outputs.")
    parser.add_argument("--cases-path", default="eval/sec_cases/test_cases_v1.jsonl")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument(
        "--required-mode",
        choices=["pipeline_context", "gold_context", "both"],
        default="pipeline_context",
    )
    parser.add_argument("--output-path", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cases = _read_jsonl(REPO_ROOT / args.cases_path)
    trap_cases = {str(c.get("case_id")): c for c in cases if str(c.get("task_type") or "").startswith("anti_hallucination")}
    run_dir = REPO_ROOT / args.run_dir
    agent_rows = {(str(r.get("case_id")), str(r.get("mode"))): r for r in _read_jsonl(run_dir / "agent_outputs.jsonl")}
    claim_rows = {(str(r.get("case_id")), str(r.get("mode"))): r for r in _read_jsonl(run_dir / "claim_verification.jsonl")}

    results: list[dict[str, Any]] = []
    mode_list = ("gold_context", "pipeline_context") if args.required_mode == "both" else (args.required_mode,)
    for case_id, case in trap_cases.items():
        for mode in mode_list:
            agent = agent_rows.get((case_id, mode))
            claim = claim_rows.get((case_id, mode))
            if not agent:
                results.append({"case_id": case_id, "mode": mode, "status": "fail", "reason": "missing_agent_output"})
                continue
            results.append(_check_trap(case, mode, agent, claim or {}))

    pass_count = sum(r.get("status") == "pass" for r in results)
    report = {
        "schema_version": "sec_benchmark_trap_smoke_report_v0.1",
        "run_dir": str(run_dir.resolve()),
        "trap_case_count": len(trap_cases),
        "result_count": len(results),
        "required_mode": args.required_mode,
        "pass_count": pass_count,
        "fail_count": len(results) - pass_count,
        "pass_rate": round(pass_count / len(results), 4) if results else 0.0,
        "can_enter_gate": pass_count == len(results) and len(results) > 0,
        "results": results,
    }
    output_path = Path(args.output_path) if args.output_path else (run_dir / "trap_smoke_report.json")
    if not output_path.is_absolute():
        output_path = REPO_ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output_path": str(output_path), "can_enter_gate": report["can_enter_gate"], "pass_rate": report["pass_rate"]}, ensure_ascii=False, indent=2))


def _check_trap(case: dict[str, Any], mode: str, agent: dict[str, Any], claim: dict[str, Any]) -> dict[str, Any]:
    answer = agent.get("answer")
    answer_text = json.dumps(answer, ensure_ascii=False).lower() if answer is not None else ""
    unsupported = claim.get("unsupported_claim_count")
    unsupported = 0 if unsupported is None else int(unsupported)
    status = "pass"
    reasons: list[str] = []

    # Trap must refuse/qualify; accepted signals:
    # 1) explicit not_run/skipped with context gap
    # 2) answer includes not found / not disclosed / belongs-to-other-company style message
    # 3) claim verifier flags unsupported claims
    answer_status = str(agent.get("answer_status") or "")
    if answer_status.startswith("not_run_context_not_ready"):
        status = "pass"
    else:
        refusal_markers = ["not found", "cannot find", "not disclosed", "不属于", "未披露", "未找到", "无法", "not available"]
        has_refusal = any(marker in answer_text for marker in refusal_markers)
        if not has_refusal and unsupported == 0:
            status = "fail"
            reasons.append("no_refusal_signal_and_no_unsupported_claim_flag")

    return {
        "case_id": str(case.get("case_id")),
        "mode": mode,
        "status": status,
        "answer_status": answer_status,
        "claim_status": claim.get("status"),
        "unsupported_claim_count": unsupported,
        "reason": "; ".join(reasons) if reasons else "ok",
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    main()
