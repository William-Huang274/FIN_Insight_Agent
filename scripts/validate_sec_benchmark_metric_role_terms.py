from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import validate_sec_benchmark_answer_ledger as answer_ledger  # noqa: E402


RULES: dict[str, list[dict[str, Any]]] = {
    "rpo": [
        {
            "type": "rpo_mislabeled_as_recurring_revenue",
            "patterns": [
                r"预测.{0,6}经常性收入",
                r"经常性收入.{0,6}RPO",
                r"RPO.{0,8}预测数据",
                r"RPO.{0,8}预测的",
            ],
            "guidance": "RPO must be described as remaining performance obligations / 剩余履约义务, not forecast recurring revenue.",
        }
    ],
    "billings": [
        {
            "type": "billings_mislabeled_as_revenue",
            "patterns": [
                r"账单收入",
                r"Billings\s*收入",
                r"收入[（(]\s*Billings\s*[）)]",
                r"billings\s+revenue",
            ],
            "guidance": "Billings must stay separate from revenue; use Billings / 账单额 / 开票额.",
        }
    ],
    "services_revenue": [
        {
            "type": "services_revenue_overclaims_recurring_quality",
            "patterns": [
                r"经常性收入特征",
                r"可持续.{0,8}经常性收入",
                r"服务业务.{0,24}订阅收入",
            ],
            "guidance": "Services revenue and gross margin do not by themselves prove subscription or recurring revenue quality.",
            "skip_if_family_present": ["subscription_revenue", "arr_or_recurring_proxy"],
        }
    ],
}


NEGATION_PATTERN = re.compile(r"(不|不能|无法|未能|并非|不是|不等于).{0,12}$")
INLINE_SEPARATION_PATTERN = re.compile(r"(不等于|不同于|区别于|不能.{0,4}等同|不可.{0,4}等同|不是|并非)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate that answer prose does not relabel ledger metrics into incompatible financial concepts."
    )
    parser.add_argument("--run-dir", required=True)
    parser.add_argument(
        "--ledger-path",
        default="reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json",
    )
    parser.add_argument("--output-path", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = _resolve(args.run_dir)
    ledger = _read_json(_resolve(args.ledger_path))
    rows_by_case: dict[str, list[dict[str, Any]]] = {}
    for row in ledger.get("rows") or []:
        rows_by_case.setdefault(str(row.get("case_id") or ""), []).append(row)

    results = [
        _validate_agent_row(agent, rows_by_case.get(str(agent.get("case_id") or ""), []))
        for agent in _read_jsonl(run_dir / "agent_outputs.jsonl")
    ]
    failure_counts = Counter(
        failure.get("type")
        for result in results
        for failure in result.get("failures") or []
    )
    fail_by_case = Counter(result.get("case_id") for result in results if result.get("status") == "fail")
    report = {
        "schema_version": "sec_benchmark_metric_role_term_gate_v0.1",
        "run_dir": str(run_dir.resolve()),
        "ledger_path": str(_resolve(args.ledger_path).resolve()),
        "can_enter_gate": not failure_counts,
        "summary": {
            "case_count": len(results),
            "pass_count": sum(result.get("status") == "pass" for result in results),
            "fail_count": sum(result.get("status") == "fail" for result in results),
            "skip_count": sum(result.get("status") == "skipped" for result in results),
            "failure_types": dict(sorted(failure_counts.items())),
            "fail_by_case": dict(sorted(fail_by_case.items())),
        },
        "case_results": results,
    }
    output_path = _resolve(args.output_path) if args.output_path else run_dir / "metric_role_term_gate.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output_path": str(output_path),
                "can_enter_gate": report["can_enter_gate"],
                **report["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _validate_agent_row(agent: dict[str, Any], ledger_rows: list[dict[str, Any]]) -> dict[str, Any]:
    case_id = str(agent.get("case_id") or "")
    mode = str(agent.get("mode") or "")
    if str(agent.get("status") or "") != "answered" or not isinstance(agent.get("answer"), dict):
        return {
            "case_id": case_id,
            "mode": mode,
            "status": "skipped",
            "reason": "agent_output_not_answered_or_answer_not_object",
            "families": [],
            "failures": [],
        }
    families = {str(row.get("metric_family") or "") for row in ledger_rows if row.get("metric_family")}
    failures: list[dict[str, Any]] = []
    locations = answer_ledger._answer_locations(agent.get("answer") or {})
    for family in sorted(families):
        for rule in RULES.get(family, []):
            skipped_by_family = set(rule.get("skip_if_family_present") or []) & families
            if skipped_by_family:
                continue
            for location in locations:
                text = str(location.get("text") or "")
                for pattern in rule.get("patterns") or []:
                    for match in re.finditer(pattern, text, flags=re.I):
                        if _is_negated(text, match.start()) or INLINE_SEPARATION_PATTERN.search(match.group(0)):
                            continue
                        failures.append(
                            {
                                "type": rule["type"],
                                "metric_family": family,
                                "location": location.get("location"),
                                "matched_text": match.group(0),
                                "near_text": _near_text(text, match.span()),
                                "guidance": rule.get("guidance"),
                            }
                        )
    return {
        "case_id": case_id,
        "mode": mode,
        "status": "fail" if failures else "pass",
        "answer_status": agent.get("answer_status"),
        "families": sorted(families),
        "failures": failures,
    }


def _is_negated(text: str, start: int) -> bool:
    prefix = text[max(0, start - 16) : start]
    return bool(NEGATION_PATTERN.search(prefix))


def _near_text(text: str, span: tuple[int, int], window: int = 120) -> str:
    start, end = span
    return text[max(0, start - window) : min(len(text), end + window)]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _resolve(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


if __name__ == "__main__":
    main()
