from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


NUMBER_PATTERNS = [
    re.compile(
        r"\$\s*\(?\d[\d,]*(?:\.\d+)?\)?"
        r"(?:\s*[（(]?\s*(?:百万美元|十亿美元|亿美元|万美元|美元|million|billion)\s*[）)]?)?",
        re.I,
    ),
    re.compile(
        r"\d[\d,]*(?:\.\d+)?\s*"
        r"(?:%|[（(]?\s*(?:百万美元|十亿美元|亿美元|万美元|美元|million|billion)\s*[）)]?)",
        re.I,
    ),
    re.compile(r"\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b"),
    re.compile(r"\b\d+(?:\.\d+)?\s*%"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate SEC benchmark answer prose exact values against the case Exact-Value Ledger."
    )
    parser.add_argument("--run-dir", required=True)
    parser.add_argument(
        "--ledger-path",
        default="reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json",
    )
    parser.add_argument("--output-path", default="")
    parser.add_argument(
        "--require-metric-id-support",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Require each exact value hit to have inline or sibling metric_id support.",
    )
    parser.add_argument(
        "--metric-id-window",
        type=int,
        default=240,
        help="Character window around a value hit used for inline metric_id support.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = _resolve(args.run_dir)
    ledger = _read_json(_resolve(args.ledger_path))
    rows_by_case: dict[str, list[dict[str, Any]]] = {}
    for row in ledger.get("rows") or []:
        rows_by_case.setdefault(str(row.get("case_id") or ""), []).append(row)

    agent_rows = _read_jsonl(run_dir / "agent_outputs.jsonl")
    case_results = [
        _validate_agent_row(
            agent,
            rows_by_case.get(str(agent.get("case_id") or ""), []),
            require_metric_id_support=args.require_metric_id_support,
            metric_id_window=args.metric_id_window,
        )
        for agent in agent_rows
    ]
    failure_counts = Counter(
        failure.get("type")
        for result in case_results
        for failure in result.get("failures") or []
    )
    fail_by_case = Counter(
        result.get("case_id")
        for result in case_results
        if result.get("status") == "fail"
    )
    report = {
        "schema_version": "sec_benchmark_answer_ledger_gate_v0.1",
        "run_dir": str(run_dir.resolve()),
        "ledger_path": str(_resolve(args.ledger_path).resolve()),
        "require_metric_id_support": bool(args.require_metric_id_support),
        "metric_id_window": args.metric_id_window,
        "can_enter_gate": not failure_counts,
        "summary": {
            "case_count": len(case_results),
            "pass_count": sum(result.get("status") == "pass" for result in case_results),
            "fail_count": sum(result.get("status") == "fail" for result in case_results),
            "skip_count": sum(result.get("status") == "skipped" for result in case_results),
            "exact_value_hit_count": sum(int(result.get("exact_value_hit_count") or 0) for result in case_results),
            "failure_types": dict(sorted(failure_counts.items())),
            "fail_by_case": dict(sorted(fail_by_case.items())),
        },
        "case_results": case_results,
    }
    output_path = _resolve(args.output_path) if args.output_path else run_dir / "answer_ledger_gate.json"
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


def _validate_agent_row(
    agent: dict[str, Any],
    ledger_rows: list[dict[str, Any]],
    *,
    require_metric_id_support: bool,
    metric_id_window: int,
) -> dict[str, Any]:
    case_id = str(agent.get("case_id") or "")
    mode = str(agent.get("mode") or "")
    if str(agent.get("status") or "") != "answered" or not isinstance(agent.get("answer"), dict):
        return {
            "case_id": case_id,
            "mode": mode,
            "status": "skipped",
            "reason": "agent_output_not_answered_or_answer_not_object",
            "exact_value_hit_count": 0,
            "failures": [],
            "hits": [],
        }
    row_matchers = [_row_matcher(row) for row in ledger_rows]
    failures: list[dict[str, Any]] = []
    hits: list[dict[str, Any]] = []
    for location in _answer_locations(agent.get("answer") or {}):
        for hit in _exact_value_hits(location["text"]):
            matched_rows = [matcher["row"] for matcher in row_matchers if _hit_matches_row(hit["text"], matcher)]
            supported_rows = [
                row
                for row in matched_rows
                if _metric_id_supported(
                    text=location["text"],
                    span=hit["span"],
                    row=row,
                    sibling_metric_ids=location["metric_ids"],
                    window=metric_id_window,
                )
            ]
            hit_report = {
                "location": location["location"],
                "value": hit["text"],
                "span": hit["span"],
                "matched_metric_ids": [row.get("metric_id") for row in matched_rows],
                "supported_metric_ids": [row.get("metric_id") for row in supported_rows],
            }
            if not matched_rows:
                failure = {
                    "type": "exact_value_not_in_case_ledger",
                    "location": location["location"],
                    "value": hit["text"],
                    "near_text": _near_text(location["text"], hit["span"]),
                }
                failures.append(failure)
                hit_report["status"] = "fail"
                hit_report["failure_type"] = failure["type"]
            elif require_metric_id_support and not supported_rows:
                failure = {
                    "type": "exact_value_missing_metric_id_support",
                    "location": location["location"],
                    "value": hit["text"],
                    "matched_metric_ids": [row.get("metric_id") for row in matched_rows],
                    "near_text": _near_text(location["text"], hit["span"]),
                }
                failures.append(failure)
                hit_report["status"] = "fail"
                hit_report["failure_type"] = failure["type"]
            else:
                hit_report["status"] = "pass"
            hits.append(hit_report)
    return {
        "case_id": case_id,
        "mode": mode,
        "status": "fail" if failures else "pass",
        "answer_status": agent.get("answer_status"),
        "ledger_row_count": len(ledger_rows),
        "exact_value_hit_count": len(hits),
        "failures": failures,
        "hits": hits,
    }


def _answer_locations(answer: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [{"location": "summary", "text": str(answer.get("summary") or ""), "metric_ids": []}]
    for index, item in enumerate(answer.get("decision_drivers") or [], start=1):
        if not isinstance(item, dict):
            continue
        metric_ids = _string_list(item.get("supporting_metric_ids"))
        for key in ("driver_claim", "why_it_matters", "caveat"):
            rows.append(
                {
                    "location": f"decision_drivers[{index}].{key}",
                    "text": str(item.get(key) or ""),
                    "metric_ids": metric_ids,
                }
            )
    for index, item in enumerate(answer.get("key_points") or [], start=1):
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "location": f"key_points[{index}].point",
                "text": str(item.get("point") or ""),
                "metric_ids": _string_list(item.get("metric_ids")),
            }
        )
    for key in ("not_found", "limitations"):
        for index, item in enumerate(answer.get(key) or [], start=1):
            rows.append({"location": f"{key}[{index}]", "text": str(item or ""), "metric_ids": []})
    for location in _memo_answer_locations(answer):
        rows.append(location)
    return rows


def _memo_answer_locations(answer: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        {"location": "direct_answer", "text": str(answer.get("direct_answer") or ""), "metric_ids": []},
        {"location": "investment_thesis", "text": str(answer.get("investment_thesis") or ""), "metric_ids": []},
    ]
    memo_list_specs = {
        "what_changed": ("claim",),
        "why_it_matters": ("insight", "business_implication"),
        "peer_readthrough": ("peer_or_group", "role", "readthrough", "caveat"),
        "counterarguments": ("claim", "why_it_could_weaken_thesis"),
    }
    for field, text_keys in memo_list_specs.items():
        for index, item in enumerate(answer.get(field) or [], start=1):
            if not isinstance(item, dict):
                continue
            rows.append(
                {
                    "location": f"{field}[{index}]",
                    "text": " ".join(str(item.get(key) or "") for key in text_keys),
                    "metric_ids": _string_list(item.get("metric_ids")),
                }
            )
    for index, item in enumerate(answer.get("watch_items") or [], start=1):
        if isinstance(item, dict):
            rows.append(
                {
                    "location": f"watch_items[{index}]",
                    "text": " ".join(str(item.get(key) or "") for key in ("item", "why_it_matters", "source_to_watch", "metric_family")),
                    "metric_ids": [],
                }
            )
    for index, item in enumerate(answer.get("source_limitations") or [], start=1):
        rows.append({"location": f"source_limitations[{index}]", "text": str(item or ""), "metric_ids": []})
    return [row for row in rows if str(row.get("text") or "").strip()]


def _exact_value_hits(text: str) -> list[dict[str, Any]]:
    matches = []
    occupied: list[tuple[int, int]] = []
    for pattern in NUMBER_PATTERNS:
        for match in pattern.finditer(text):
            start, end = match.span()
            value = match.group(0).strip()
            if not value or _overlaps((start, end), occupied):
                continue
            occupied.append((start, end))
            matches.append({"text": value, "span": [start, end]})
    return sorted(matches, key=lambda item: item["span"])


def _row_matcher(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "row": row,
        "value": _to_float(row.get("value")),
        "unit": str(row.get("unit") or ""),
        "raw_norm": _compact(row.get("raw_value_text")),
        "display_norm": _compact(row.get("display_value_zh")),
    }


def _hit_matches_row(hit_text: str, matcher: dict[str, Any]) -> bool:
    hit_norm = _compact(hit_text)
    if hit_norm and hit_norm in {matcher["raw_norm"], matcher["display_norm"]}:
        return True
    if matcher["raw_norm"] and matcher["raw_norm"] in hit_norm:
        row_unit = str(matcher.get("unit") or "")
        if row_unit == "usd_millions" and any(token in hit_norm for token in ("百万美元", "million")):
            return True
        if row_unit == "usd_billions" and any(token in hit_norm for token in ("十亿美元", "billion")):
            return True
        if row_unit == "percent" and "%" in hit_norm:
            return True
    parsed = _parse_hit_value(hit_text)
    row_value = matcher.get("value")
    row_unit = str(matcher.get("unit") or "")
    if parsed is None or row_value is None:
        return False
    if parsed["unit"] == "unitless":
        return _near(parsed["value"], row_value)
    if row_unit == parsed["unit"]:
        return _near(parsed["value"], row_value)
    if row_unit == "usd_millions" and parsed["unit"] == "usd_billions":
        return _near(parsed["value"] * 1000.0, row_value)
    if row_unit == "usd_billions" and parsed["unit"] == "usd_millions":
        return _near(parsed["value"] / 1000.0, row_value)
    if row_unit == "usd_millions" and parsed["unit"] == "usd_hundred_millions":
        return _near(parsed["value"] * 100.0, row_value)
    if row_unit == "usd_billions" and parsed["unit"] == "usd_hundred_millions":
        return _near(parsed["value"] / 10.0, row_value)
    return False


def _parse_hit_value(text: str) -> dict[str, Any] | None:
    match = re.search(r"\d[\d,]*(?:\.\d+)?", text)
    if not match:
        return None
    value = float(match.group(0).replace(",", ""))
    lower = text.lower()
    if "%" in text:
        unit = "percent"
    elif "百万美元" in text or "million" in lower:
        unit = "usd_millions"
    elif "十亿美元" in text or "billion" in lower:
        unit = "usd_billions"
    elif "亿美元" in text or re.search(r"(?<!十)亿", text):
        unit = "usd_hundred_millions"
    elif "万美元" in text:
        unit = "usd_ten_thousands"
    else:
        unit = "unitless"
    return {"value": value, "unit": unit}


def _metric_id_supported(
    *,
    text: str,
    span: list[int],
    row: dict[str, Any],
    sibling_metric_ids: list[str],
    window: int,
) -> bool:
    metric_id = str(row.get("metric_id") or "")
    if not metric_id:
        return False
    if metric_id in sibling_metric_ids:
        return True
    start, end = span
    near = text[max(0, start - window) : min(len(text), end + window)]
    return metric_id in near


def _near_text(text: str, span: list[int], window: int = 120) -> str:
    start, end = span
    return text[max(0, start - window) : min(len(text), end + window)]


def _overlaps(span: tuple[int, int], occupied: list[tuple[int, int]]) -> bool:
    start, end = span
    return any(start < other_end and other_start < end for other_start, other_end in occupied)


def _compact(value: Any) -> str:
    text = str(value or "").lower()
    text = text.replace(",", "").replace(" ", "")
    return re.sub(r"[()\[\]{}（）]", "", text)


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _to_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _near(left: float, right: float, tolerance: float = 1e-6) -> bool:
    return abs(left - right) <= tolerance


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _resolve(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


if __name__ == "__main__":
    main()
