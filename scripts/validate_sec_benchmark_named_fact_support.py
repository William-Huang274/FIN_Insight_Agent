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


GENERIC_NAMED_TOKENS = {
    "AI",
    "API",
    "APIs",
    "ARR",
    "CSP",
    "CSPs",
    "CPU",
    "Compute",
    "Exact-Value Ledger",
    "GAAP",
    "GPU",
    "GPUs",
    "HPC",
    "ASIC",
    "ASICs",
    "Foundry",
    "IoT",
    "IDM",
    "IT",
    "JSON",
    "KPI",
    "MD",
    "Net",
    "Networking",
    "RPO",
    "Product",
    "Recurring Revenue",
    "SEC",
    "SDK",
    "SDKs",
    "Semiconductor",
    "Semiconductor solutions",
}

TOKEN_ALIASES = {
    "AWS": ["Amazon Web Services"],
    "Azure": ["Microsoft Azure"],
    "GCP": ["Google Cloud Platform"],
    "RPO": ["remaining performance obligations"],
}

COMPANY_TOKEN_ALIASES = {
    "Alphabet": "GOOGL",
    "Adobe": "ADBE",
    "Advanced Micro Devices": "AMD",
    "Apple": "AAPL",
    "Applied Materials": "AMAT",
    "AWS": "AMZN",
    "Microsoft": "MSFT",
    "Microsoft Azure": "MSFT",
    "Amazon": "AMZN",
    "Broadcom": "AVGO",
    "Cisco": "CSCO",
    "CrowdStrike": "CRWD",
    "Google": "GOOGL",
    "Google Cloud": "GOOGL",
    "Intel": "INTC",
    "Intuit": "INTU",
    "Meta": "META",
    "Facebook": "META",
    "Micron": "MU",
    "NVIDIA": "NVDA",
    "Qualcomm": "QCOM",
    "Snowflake": "SNOW",
    "Palo Alto": "PANW",
}

LEDGER_METRIC_TERMS = {
    "arr",
    "billings",
    "cloud",
    "gross",
    "income",
    "margin",
    "net",
    "operating",
    "revenue",
    "rpo",
    "sales",
    "services",
    "subscription",
    "total",
}

LEDGER_METRIC_TERMS_ZH = {
    "收入",
    "销售",
    "经营利润",
    "营业利润",
    "运营利润",
    "亏损",
    "资本支出",
    "毛利",
    "毛利率",
    "账单额",
    "递延收入",
    "剩余履约义务",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate answer named facts against cited SEC evidence text."
    )
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--cases-path", default="eval/sec_cases/test_cases_v1.jsonl")
    parser.add_argument("--output-path", default="")
    parser.add_argument(
        "--strict-summary",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Fail summary named facts against the union of cited evidence IDs. Default records summary misses as warnings.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = _resolve(args.run_dir)
    case_task_types = _case_task_types(_resolve(args.cases_path))
    traces_by_case = _traces_by_case(run_dir / "trace_logs.jsonl")
    agent_rows = _read_jsonl(run_dir / "agent_outputs.jsonl")
    case_results = [
        _validate_agent_row(
            agent,
            traces_by_case.get(str(agent.get("case_id") or ""), {}),
            case_task_types.get(str(agent.get("case_id") or ""), ""),
            strict_summary=bool(args.strict_summary),
        )
        for agent in agent_rows
    ]
    failure_counts = Counter(
        failure.get("type")
        for result in case_results
        for failure in result.get("failures") or []
    )
    warning_counts = Counter(
        warning.get("type")
        for result in case_results
        for warning in result.get("warnings") or []
    )
    fail_by_case = Counter(
        result.get("case_id")
        for result in case_results
        if result.get("status") == "fail"
    )
    report = {
        "schema_version": "sec_benchmark_named_fact_support_gate_v0.1",
        "run_dir": str(run_dir.resolve()),
        "strict_summary": bool(args.strict_summary),
        "can_enter_gate": not failure_counts,
        "summary": {
            "case_count": len(case_results),
            "pass_count": sum(result.get("status") == "pass" for result in case_results),
            "fail_count": sum(result.get("status") == "fail" for result in case_results),
            "skip_count": sum(result.get("status") == "skipped" for result in case_results),
            "checked_location_count": sum(int(result.get("checked_location_count") or 0) for result in case_results),
            "named_token_count": sum(int(result.get("named_token_count") or 0) for result in case_results),
            "unsupported_token_count": sum(len(result.get("failures") or []) for result in case_results),
            "warning_count": sum(len(result.get("warnings") or []) for result in case_results),
            "failure_types": dict(sorted(failure_counts.items())),
            "warning_types": dict(sorted(warning_counts.items())),
            "fail_by_case": dict(sorted(fail_by_case.items())),
        },
        "case_results": case_results,
    }
    output_path = _resolve(args.output_path) if args.output_path else run_dir / "named_fact_support_gate.json"
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
    trace: dict[str, Any],
    task_type: str,
    *,
    strict_summary: bool,
) -> dict[str, Any]:
    case_id = str(agent.get("case_id") or "")
    mode = str(agent.get("mode") or "")
    answer_status = str(agent.get("answer_status") or "")
    if str(task_type).startswith("anti_hallucination") or answer_status.startswith("answered_contract_fallback"):
        return _skipped_result(case_id, mode, answer_status, "trap_or_contract_fallback")
    if str(agent.get("status") or "") != "answered" or not isinstance(agent.get("answer"), dict):
        return _skipped_result(case_id, mode, answer_status, "agent_output_not_answered_or_answer_not_object")

    evidence_text_by_id = _evidence_text_by_id(trace)
    ignored_tokens = _case_ignored_tokens(trace)
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    checked_locations = 0
    named_token_count = 0

    for location in _answer_locations(agent.get("answer") or {}, agent.get("claims") or []):
        tokens = [
            token
            for token in _named_tokens(location["text"])
            if token not in ignored_tokens and token.upper() not in ignored_tokens
        ]
        if not tokens:
            continue
        checked_locations += 1
        named_token_count += len(tokens)
        evidence_ids = _string_list(location.get("evidence_ids"))
        metric_ids = _string_list(location.get("metric_ids"))
        cited_text = "\n".join(evidence_text_by_id.get(evidence_id, "") for evidence_id in evidence_ids)
        for token in tokens:
            if _token_supported(token, cited_text):
                continue
            if _token_supported_by_metric_ids(token, metric_ids, location["text"]):
                continue
            issue = {
                "type": "named_fact_not_supported_by_cited_evidence",
                "location": location["location"],
                "token": token,
                "evidence_ids": evidence_ids,
                "metric_ids": metric_ids,
                "near_text": _near_token_text(location["text"], token),
            }
            if location.get("summary_location") and not strict_summary:
                warnings.append({**issue, "type": "summary_named_fact_not_supported_by_cited_evidence"})
            else:
                failures.append(issue)
    return {
        "case_id": case_id,
        "mode": mode,
        "status": "fail" if failures else "pass",
        "answer_status": answer_status,
        "checked_location_count": checked_locations,
        "named_token_count": named_token_count,
        "failures": failures,
        "warnings": warnings,
    }


def _answer_locations(answer: dict[str, Any], claims: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    union_ids: list[str] = []
    union_metric_ids: list[str] = []
    for item in answer.get("decision_drivers") or []:
        if isinstance(item, dict):
            union_ids.extend(_string_list(item.get("supporting_evidence_ids")))
            union_metric_ids.extend(_string_list(item.get("supporting_metric_ids")))
    for item in answer.get("key_points") or []:
        if isinstance(item, dict):
            union_ids.extend(_string_list(item.get("evidence_ids")))
            union_metric_ids.extend(_string_list(item.get("metric_ids")))
    for claim in claims:
        if isinstance(claim, dict):
            union_ids.extend(_string_list(claim.get("evidence_ids")))
            union_metric_ids.extend(_string_list(claim.get("metric_ids")))
    rows.append(
        {
            "location": "summary",
            "text": str(answer.get("summary") or ""),
            "evidence_ids": list(dict.fromkeys(union_ids)),
            "metric_ids": list(dict.fromkeys(union_metric_ids)),
            "summary_location": True,
        }
    )
    for index, item in enumerate(answer.get("decision_drivers") or [], start=1):
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "location": f"decision_drivers[{index}]",
                "text": " ".join(str(item.get(key) or "") for key in ("driver_claim", "why_it_matters", "caveat")),
                "evidence_ids": _string_list(item.get("supporting_evidence_ids")),
                "metric_ids": _string_list(item.get("supporting_metric_ids")),
                "summary_location": False,
            }
        )
    for index, item in enumerate(answer.get("key_points") or [], start=1):
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "location": f"key_points[{index}]",
                "text": str(item.get("point") or ""),
                "evidence_ids": _string_list(item.get("evidence_ids")),
                "metric_ids": _string_list(item.get("metric_ids")),
                "summary_location": False,
            }
        )
    rows.extend(_memo_answer_locations(answer, union_ids, union_metric_ids))
    return rows


def _memo_answer_locations(answer: dict[str, Any], union_ids: list[str], union_metric_ids: list[str]) -> list[dict[str, Any]]:
    rows = []
    summary_ids = list(dict.fromkeys(union_ids))
    summary_metric_ids = list(dict.fromkeys(union_metric_ids))
    for key in ("direct_answer", "investment_thesis"):
        text = str(answer.get(key) or "")
        if text.strip():
            rows.append(
                {
                    "location": key,
                    "text": text,
                    "evidence_ids": summary_ids,
                    "metric_ids": summary_metric_ids,
                    "summary_location": True,
                }
            )
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
            text = " ".join(str(item.get(key) or "") for key in text_keys)
            if not text.strip():
                continue
            rows.append(
                {
                    "location": f"{field}[{index}]",
                    "text": text,
                    "evidence_ids": _string_list(item.get("evidence_ids")),
                    "metric_ids": _string_list(item.get("metric_ids")),
                    "summary_location": False,
                }
            )
    for index, item in enumerate(answer.get("watch_items") or [], start=1):
        if not isinstance(item, dict):
            continue
        text = " ".join(str(item.get(key) or "") for key in ("item", "why_it_matters", "source_to_watch", "metric_family"))
        if text.strip():
            rows.append(
                {
                    "location": f"watch_items[{index}]",
                    "text": text,
                    "evidence_ids": summary_ids,
                    "metric_ids": summary_metric_ids,
                    "summary_location": False,
                }
            )
    return rows


def _evidence_text_by_id(trace: dict[str, Any]) -> dict[str, str]:
    rows: dict[str, str] = {}
    for item in trace.get("context_rows") or []:
        text = "\n".join(str(item.get(key) or "") for key in ("text", "preview", "text_preview"))
        for key in ("evidence_id", "source_evidence_id", "object_id"):
            evidence_id = str(item.get(key) or "")
            if not evidence_id:
                continue
            rows[evidence_id] = "\n".join(part for part in (rows.get(evidence_id), text) if part)
    return rows


def _case_ignored_tokens(trace: dict[str, Any]) -> set[str]:
    ignored = set(GENERIC_NAMED_TOKENS)
    for row in trace.get("context_rows") or []:
        ticker = str(row.get("ticker") or "").strip()
        if ticker:
            ignored.add(ticker)
            ignored.add(ticker.upper())
            for company, company_ticker in COMPANY_TOKEN_ALIASES.items():
                if company_ticker == ticker.upper():
                    ignored.add(company)
                    ignored.add(company.upper())
    return ignored


def _named_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    pattern = r"\b[A-Z][A-Za-z0-9&.-]{1,}(?:\s+[A-Z][A-Za-z0-9&.-]{1,}){0,3}\b"
    for match in re.finditer(pattern, str(text or "")):
        token = match.group(0).strip(" .,:;()[]{}")
        if not token or token in GENERIC_NAMED_TOKENS:
            continue
        if all(part in GENERIC_NAMED_TOKENS for part in token.split()):
            continue
        if re.fullmatch(r"\d+-?K", token):
            continue
        tokens.append(token)
    return list(dict.fromkeys(tokens))


def _token_supported(token: str, evidence_text: str) -> bool:
    if not token:
        return True
    candidates = [token, *TOKEN_ALIASES.get(token, [])]
    evidence_norm = _norm_text(evidence_text)
    for candidate in candidates:
        candidate_norm = _norm_text(candidate)
        if candidate_norm and re.search(rf"(?<![a-z0-9]){re.escape(candidate_norm)}(?![a-z0-9])", evidence_norm):
            return True
    return False


def _token_supported_by_metric_ids(token: str, metric_ids: list[str], text: str) -> bool:
    """Allow ledger-backed company metric labels without citation text.

    This keeps the gate focused on unsupported named facts. A phrase such as
    "Adobe Total subscription revenue" can be supported by an ADBE ledger
    metric_id, while product/partner/regulatory names still need evidence_ids.
    """
    if not token or not metric_ids:
        return False
    token_norm = _norm_text(token)
    text_norm = _norm_text(text)
    metric_id_norms = [_norm_text(metric_id) for metric_id in metric_ids]
    token_parts = set(token_norm.split())
    text_parts = set(text_norm.split())
    if not token_parts:
        return False
    if any(token_norm and re.search(rf"(?<![a-z0-9]){re.escape(token_norm)}(?![a-z0-9])", metric_norm) for metric_norm in metric_id_norms):
        return True
    if any(token_norm == _norm_text(ticker) and any(_norm_text(ticker) in metric_norm for metric_norm in metric_id_norms) for ticker in COMPANY_TOKEN_ALIASES.values()):
        return True
    has_metric_term = bool((token_parts | text_parts) & LEDGER_METRIC_TERMS) or any(
        term in str(text or "") for term in LEDGER_METRIC_TERMS_ZH
    )
    if not has_metric_term:
        return False
    for company, ticker in COMPANY_TOKEN_ALIASES.items():
        company_norm = _norm_text(company)
        ticker_norm = _norm_text(ticker)
        if company_norm not in token_norm:
            continue
        if any(ticker_norm in metric_norm for metric_norm in metric_id_norms):
            return True
    return False


def _near_token_text(text: str, token: str, window: int = 100) -> str:
    lower = str(text or "").lower()
    index = lower.find(str(token or "").lower())
    if index < 0:
        return str(text or "")[: window * 2]
    return str(text or "")[max(0, index - window) : min(len(str(text or "")), index + len(token) + window)]


def _norm_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _skipped_result(case_id: str, mode: str, answer_status: str, reason: str) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "mode": mode,
        "status": "skipped",
        "answer_status": answer_status,
        "reason": reason,
        "checked_location_count": 0,
        "named_token_count": 0,
        "failures": [],
        "warnings": [],
    }


def _traces_by_case(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    return {
        str(row.get("case_id") or ""): row
        for row in _read_jsonl(path)
        if str(row.get("case_id") or "")
    }


def _case_task_types(cases_path: Path) -> dict[str, str]:
    if not cases_path.exists():
        return {}
    return {str(row.get("case_id") or ""): str(row.get("task_type") or "") for row in _read_jsonl(cases_path)}


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _resolve(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


if __name__ == "__main__":
    main()
