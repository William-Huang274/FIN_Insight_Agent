from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


DEFAULT_ALLOW_NEAR_NEGATIONS = (
    "not",
    "do not",
    "does not",
    "cannot",
    "no direct",
    "未",
    "并未",
    "未证明",
    "未将",
    "没有",
    "并没有",
    "不能",
    "无法",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate manifest-native required_caveats and disallowed_claims for SEC benchmark answers."
    )
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--cases-path", default="eval/sec_cases/test_cases_v1.jsonl")
    parser.add_argument("--output-path", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = _resolve(args.run_dir)
    cases = {str(row.get("case_id") or ""): row for row in _read_jsonl(_resolve(args.cases_path))}
    rows = _read_jsonl(run_dir / "agent_outputs.jsonl")
    case_results = [_validate_agent_row(row, cases.get(str(row.get("case_id") or ""), {})) for row in rows]
    failures = Counter(
        failure.get("type")
        for result in case_results
        for failure in result.get("failures") or []
    )
    warnings = Counter(
        warning.get("type")
        for result in case_results
        for warning in result.get("warnings") or []
    )
    fail_by_case = Counter(result.get("case_id") for result in case_results if result.get("status") == "fail")
    checked = [result for result in case_results if result.get("status") != "skipped"]
    report = {
        "schema_version": "sec_benchmark_caveat_claim_gate_v0.1",
        "run_dir": str(run_dir.resolve()),
        "cases_path": str(_resolve(args.cases_path).resolve()),
        "can_enter_gate": not failures,
        "summary": {
            "case_count": len(case_results),
            "checked_case_count": len(checked),
            "pass_count": sum(result.get("status") == "pass" for result in case_results),
            "fail_count": sum(result.get("status") == "fail" for result in case_results),
            "skip_count": sum(result.get("status") == "skipped" for result in case_results),
            "required_caveat_count": sum(int(result.get("required_caveat_count") or 0) for result in checked),
            "covered_required_caveat_count": sum(
                int(result.get("covered_required_caveat_count") or 0) for result in checked
            ),
            "disallowed_claim_count": sum(int(result.get("disallowed_claim_count") or 0) for result in checked),
            "disallowed_claim_violation_count": sum(
                int(result.get("disallowed_claim_violation_count") or 0) for result in checked
            ),
            "failure_types": dict(sorted(failures.items())),
            "warning_types": dict(sorted(warnings.items())),
            "fail_by_case": dict(sorted(fail_by_case.items())),
        },
        "case_results": case_results,
    }
    output_path = _resolve(args.output_path) if args.output_path else run_dir / "caveat_claim_gate.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output_path": str(output_path), "can_enter_gate": report["can_enter_gate"], **report["summary"]}, ensure_ascii=False, indent=2))


def _validate_agent_row(row: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    case_id = str(row.get("case_id") or "")
    mode = str(row.get("mode") or "")
    answer_status = str(row.get("answer_status") or "")
    required_caveats = [_normalize_required_caveat(item) for item in case.get("required_caveats") or []]
    disallowed_claims = [_normalize_disallowed_claim(item) for item in case.get("disallowed_claims") or []]
    required_caveats = [item for item in required_caveats if item]
    disallowed_claims = [item for item in disallowed_claims if item]
    if not required_caveats and not disallowed_claims:
        return _skipped_result(case_id, mode, answer_status, "no_required_caveats_or_disallowed_claims")
    if str(row.get("status") or "") != "answered" or not isinstance(row.get("answer"), dict):
        return _skipped_result(case_id, mode, answer_status, "agent_output_not_answered_or_answer_not_object")

    answer = row.get("answer") or {}
    text_blocks = _answer_text_blocks(answer, row.get("claims") or [], row.get("limitations") or [])
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    caveat_results = []
    for caveat in required_caveats:
        result = _evaluate_required_caveat(caveat, text_blocks)
        caveat_results.append(result)
        if caveat.get("required", True) and not result["passed"]:
            failures.append(
                {
                    "type": "missing_caveat",
                    "caveat_id": result["caveat_id"],
                    "description": result["description"],
                    "where": result["where"],
                    "missing_groups": result["missing_groups"],
                }
            )

    disallowed_results = []
    for claim in disallowed_claims:
        result = _evaluate_disallowed_claim(claim, text_blocks["answer"])
        disallowed_results.append(result)
        for violation in result["violations"]:
            failures.append(
                {
                    "type": str(claim.get("failure_type") or "disallowed_claim"),
                    "claim_id": result["claim_id"],
                    "description": result["description"],
                    "pattern": violation["pattern"],
                    "near_text": violation["near_text"],
                }
            )

    return {
        "case_id": case_id,
        "mode": mode,
        "answer_status": answer_status,
        "status": "fail" if failures else "pass",
        "required_caveat_count": sum(1 for item in caveat_results if item.get("required", True)),
        "covered_required_caveat_count": sum(
            1 for item in caveat_results if item.get("required", True) and item.get("passed")
        ),
        "disallowed_claim_count": len(disallowed_results),
        "disallowed_claim_violation_count": sum(len(item.get("violations") or []) for item in disallowed_results),
        "required_caveat_results": caveat_results,
        "disallowed_claim_results": disallowed_results,
        "failures": failures,
        "warnings": warnings,
    }


def _normalize_required_caveat(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        caveat = dict(item)
    else:
        text = str(item or "").strip()
        caveat = {"id": _slug(text), "description": text, "match_any": [text]} if text else {}
    if caveat and not caveat.get("all_of_any") and caveat.get("match_any"):
        caveat["all_of_any"] = [caveat.get("match_any") or []]
    return caveat


def _normalize_disallowed_claim(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        claim = dict(item)
    else:
        text = str(item or "").strip()
        claim = {"id": _slug(text), "description": text, "patterns": [text]} if text else {}
    if claim and not claim.get("patterns") and claim.get("match_any"):
        claim["patterns"] = claim.get("match_any") or []
    return claim


def _evaluate_required_caveat(caveat: dict[str, Any], text_blocks: dict[str, str]) -> dict[str, Any]:
    where = str(caveat.get("where") or "caveats")
    text = text_blocks.get(where, text_blocks["caveats"])
    missing_groups = []
    matched_groups = []
    for group in caveat.get("all_of_any") or []:
        patterns = [str(item) for item in group]
        matched = [pattern for pattern in patterns if _pattern_matches(pattern, text)]
        if matched:
            matched_groups.append({"patterns": patterns, "matched": matched})
        else:
            missing_groups.append(patterns)
    return {
        "caveat_id": str(caveat.get("id") or ""),
        "description": str(caveat.get("description") or ""),
        "where": where,
        "required": bool(caveat.get("required", True)),
        "passed": not missing_groups,
        "missing_groups": missing_groups,
        "matched_groups": matched_groups,
    }


def _evaluate_disallowed_claim(claim: dict[str, Any], text: str) -> dict[str, Any]:
    patterns = [str(pattern) for pattern in claim.get("patterns") or []]
    allow_any = [str(pattern) for pattern in claim.get("allow_if_any") or []]
    allow_near = [str(pattern) for pattern in claim.get("allow_if_any_near") or []]
    if allow_near:
        allow_near = list(dict.fromkeys([*allow_near, *DEFAULT_ALLOW_NEAR_NEGATIONS]))
    window = int(claim.get("near_window_chars", 80) or 80)
    violations = []
    for pattern in patterns:
        for match in _pattern_finditer(pattern, text):
            if allow_any and any(_pattern_matches(allow, text) for allow in allow_any):
                continue
            near_text = text[max(0, match.start() - window) : min(len(text), match.end() + window)]
            if allow_near and any(_pattern_matches(allow, near_text) for allow in allow_near):
                continue
            violations.append({"pattern": pattern, "near_text": near_text})
    return {
        "claim_id": str(claim.get("id") or ""),
        "description": str(claim.get("description") or ""),
        "violation_count": len(violations),
        "violations": violations,
    }


def _answer_text_blocks(answer: dict[str, Any], claims: list[Any], outer_limitations: list[Any]) -> dict[str, str]:
    summary = str(answer.get("summary") or "")
    driver_texts = []
    caveat_texts = []
    for driver in answer.get("decision_drivers") or []:
        if not isinstance(driver, dict):
            continue
        driver_texts.append(
            " ".join(str(driver.get(key) or "") for key in ("driver_claim", "why_it_matters", "conclusion_strength", "caveat"))
        )
        caveat_texts.append(str(driver.get("caveat") or ""))
    key_point_texts = [str(item.get("point") or "") for item in answer.get("key_points") or [] if isinstance(item, dict)]
    limitations = [str(item) for item in answer.get("limitations") or []]
    limitations.extend(str(item) for item in outer_limitations or [])
    not_found = [str(item) for item in answer.get("not_found") or []]
    claim_texts = [str(item.get("claim") or "") for item in claims if isinstance(item, dict)]
    answer_text = "\n".join(
        part
        for part in [
            summary,
            "\n".join(driver_texts),
            "\n".join(key_point_texts),
            "\n".join(not_found),
            "\n".join(limitations),
            "\n".join(claim_texts),
        ]
        if part
    )
    caveat_text = "\n".join(part for part in [*caveat_texts, *not_found, *limitations] if part)
    return {
        "answer": answer_text,
        "summary": summary,
        "drivers": "\n".join(driver_texts),
        "key_points": "\n".join(key_point_texts),
        "caveats": caveat_text,
        "limitations": "\n".join(limitations),
        "not_found": "\n".join(not_found),
    }


def _pattern_matches(pattern: str, text: str) -> bool:
    if pattern.startswith("re:"):
        return re.search(pattern[3:], text, flags=re.IGNORECASE) is not None
    return pattern.lower() in text.lower()


def _pattern_finditer(pattern: str, text: str) -> list[re.Match[str]]:
    if pattern.startswith("re:"):
        return list(re.finditer(pattern[3:], text, flags=re.IGNORECASE))
    return list(re.finditer(re.escape(pattern), text, flags=re.IGNORECASE))


def _slug(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower()
    return slug[:80] or "item"


def _skipped_result(case_id: str, mode: str, answer_status: str, reason: str) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "mode": mode,
        "answer_status": answer_status,
        "status": "skipped",
        "reason": reason,
        "required_caveat_count": 0,
        "covered_required_caveat_count": 0,
        "disallowed_claim_count": 0,
        "disallowed_claim_violation_count": 0,
        "required_caveat_results": [],
        "disallowed_claim_results": [],
        "failures": [],
        "warnings": [],
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _resolve(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


if __name__ == "__main__":
    main()
