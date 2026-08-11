from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

from sec_agent.specialist_llm import SpecialistLLMConfig, route_specialist_memolet_llm  # noqa: E402


DEFAULT_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "multi_agent_specialist_memolet_cases_v0_1.jsonl"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "eval" / "sec_cases" / "outputs" / "multi_agent_specialist_memolet_diagnostic"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Specialist Analyst LLM memolet diagnostics.")
    parser.add_argument("--fixture", default=str(DEFAULT_FIXTURE))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--run-id", default="")
    parser.add_argument("--case-id", action="append", default=[], help="Run only selected case_id values. Repeatable.")
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--llm-backend", default=os.environ.get("LLM_BACKEND", "deepseek"))
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", "https://api.deepseek.com"))
    parser.add_argument("--chat-completions-path", default=os.environ.get("CHAT_COMPLETIONS_PATH", "/chat/completions"))
    parser.add_argument("--model", default=os.environ.get("MODEL_NAME", "deepseek-v4-pro"))
    parser.add_argument("--api-key-env", default=os.environ.get("API_KEY_ENV", "DEEPSEEK_API_KEY"))
    parser.add_argument("--temperature", type=float, default=float(os.environ.get("SPECIALIST_TEMPERATURE", "0")))
    parser.add_argument("--max-tokens", type=int, default=int(os.environ.get("SPECIALIST_MAX_TOKENS", "1400")))
    parser.add_argument("--timeout-s", type=int, default=int(os.environ.get("SPECIALIST_TIMEOUT_S", "180")))
    parser.add_argument("--max-repair-attempts", type=int, default=int(os.environ.get("SPECIALIST_MAX_REPAIR_ATTEMPTS", "2")))
    parser.add_argument("--strict", action="store_true", help="Exit non-zero unless all fixture gates pass.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows = _read_jsonl(Path(args.fixture))
    if args.case_id:
        selected = {str(case_id) for case_id in args.case_id}
        rows = [row for row in rows if str(row.get("case_id") or "") in selected]
    if args.max_cases > 0:
        rows = rows[: args.max_cases]

    run_id = args.run_id or _default_run_id(args)
    output_dir = Path(args.output_dir) / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    config = SpecialistLLMConfig(
        llm_backend=args.llm_backend,
        base_url=args.base_url,
        chat_completions_path=args.chat_completions_path,
        model=args.model,
        api_key_env=args.api_key_env,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        timeout_s=args.timeout_s,
        max_repair_attempts=args.max_repair_attempts,
    )

    started = time.time()
    cases: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        case_started = time.time()
        request = {
            "agent_id": row.get("agent_id"),
            "user_query": row.get("user_query") or "",
            "bounded_evidence_rows": row.get("bounded_evidence_rows") or [],
            "coverage_summary": row.get("coverage_summary") or {},
            "source_boundaries": row.get("source_boundaries") or {},
            "known_evidence_refs": row.get("known_evidence_refs") or [],
        }
        route_result = route_specialist_memolet_llm(
            str(row.get("agent_id") or ""),
            request,
            config=config,
            known_evidence_refs=set(row.get("known_evidence_refs") or []),
        )
        cases.append(
            _evaluate_case(
                row=row,
                route_result=route_result,
                elapsed_sec=round(time.time() - case_started, 4),
                ordinal=index,
                total=len(rows),
                max_repair_attempts=args.max_repair_attempts,
            )
        )

    summary = _summarize(
        run_id=run_id,
        args=args,
        rows=rows,
        cases=cases,
        elapsed_sec=round(time.time() - started, 4),
    )
    output_path = output_dir / "specialist_memolet_diagnostic.json"
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_stdout_summary(summary, output_path), ensure_ascii=False, indent=2))
    if args.strict and summary["gate_status"] != "pass":
        return 1
    return 0


def _evaluate_case(
    *,
    row: dict[str, Any],
    route_result: dict[str, Any],
    elapsed_sec: float,
    ordinal: int,
    total: int,
    max_repair_attempts: int,
) -> dict[str, Any]:
    memolet = route_result.get("memolet") if isinstance(route_result.get("memolet"), dict) else {}
    validation = route_result.get("validation") if isinstance(route_result.get("validation"), dict) else {}
    observations = memolet.get("observations") if isinstance(memolet.get("observations"), list) else []
    unsupported = memolet.get("unsupported_claims") if isinstance(memolet.get("unsupported_claims"), list) else []
    conflicts = memolet.get("conflicts") if isinstance(memolet.get("conflicts"), list) else []
    known_refs = set(str(item) for item in row.get("known_evidence_refs") or [])
    observed_refs = {
        str(ref)
        for observation in observations
        if isinstance(observation, dict) and not observation.get("unsupported")
        for ref in observation.get("evidence_refs") or []
    }
    unknown_refs = sorted(observed_refs - known_refs)
    min_observations = int(row.get("expected_min_observations") or 0)
    expect_unsupported_or_conflict = bool(row.get("expect_unsupported_or_conflict"))
    tool_call_count = _tool_call_count(route_result)
    checks = {
        "llm_route_pass": route_result.get("status") == "pass",
        "validation_pass": validation.get("status") == "pass",
        "agent_id_match": memolet.get("agent_id") == row.get("agent_id"),
        "min_observations": len(observations) >= min_observations,
        "evidence_refs_known": not unknown_refs,
        "forbidden_direct_tool_call_absent": tool_call_count == 0,
        "expected_unsupported_or_conflict": (bool(unsupported or conflicts) if expect_unsupported_or_conflict else True),
        "repair_budget_lte": int((route_result.get("routing_trace") or {}).get("repair_attempts") or 0)
        <= int(max_repair_attempts),
    }
    return {
        "case_id": row.get("case_id"),
        "agent_id": row.get("agent_id"),
        "ordinal": ordinal,
        "total": total,
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "elapsed_sec": elapsed_sec,
        "unknown_evidence_refs": unknown_refs,
        "supported_observation_count": len(observations),
        "unsupported_claim_count": len(unsupported),
        "conflict_count": len(conflicts),
        "tool_call_count": tool_call_count,
        "route_status": route_result.get("status"),
        "failure_reason": route_result.get("failure_reason") or "",
        "memolet": memolet,
        "validation": validation,
        "routing_trace": route_result.get("routing_trace") or {},
        "model_diagnostics": route_result.get("model_diagnostics") or {},
    }


def _summarize(
    *,
    run_id: str,
    args: argparse.Namespace,
    rows: list[dict[str, Any]],
    cases: list[dict[str, Any]],
    elapsed_sec: float,
) -> dict[str, Any]:
    total = len(cases)
    pass_count = sum(1 for case in cases if case["status"] == "pass")
    validation_pass_count = sum(1 for case in cases if case["checks"]["validation_pass"])
    llm_route_pass_count = sum(1 for case in cases if case["checks"]["llm_route_pass"])
    evidence_refs_known_count = sum(1 for case in cases if case["checks"]["evidence_refs_known"])
    unsupported_expected_count = sum(1 for row in rows if row.get("expect_unsupported_or_conflict"))
    unsupported_expected_pass_count = sum(
        1
        for case, row in zip(cases, rows)
        if not row.get("expect_unsupported_or_conflict") or case["checks"]["expected_unsupported_or_conflict"]
    )
    forbidden_tool_call_count = sum(int(case["tool_call_count"]) for case in cases)
    gate_pass = (
        total == len(rows)
        and total > 0
        and pass_count == total
        and validation_pass_count == total
        and llm_route_pass_count == total
        and evidence_refs_known_count == total
        and unsupported_expected_pass_count == total
        and forbidden_tool_call_count == 0
    )
    return {
        "schema_version": "sec_agent_specialist_memolet_diagnostic_v0.1",
        "run_id": run_id,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_sec": elapsed_sec,
        "gate_status": "pass" if gate_pass else "fail",
        "diagnostic_only": True,
        "fixture": str(Path(args.fixture).resolve()),
        "output_contract": {
            "raw_llm_response_saved": False,
            "api_key_saved": False,
            "memolet_saved": True,
            "validation_summary_saved": True,
        },
        "model_config": {
            "llm_backend": args.llm_backend,
            "base_url": args.base_url,
            "chat_completions_path": args.chat_completions_path,
            "model": args.model,
            "api_key_env": args.api_key_env,
            "api_key_present": bool(args.api_key_env and os.environ.get(str(args.api_key_env))),
            "temperature": args.temperature,
            "max_tokens": args.max_tokens,
            "timeout_s": args.timeout_s,
            "max_repair_attempts": args.max_repair_attempts,
        },
        "metrics": {
            "case_count": total,
            "pass_count": pass_count,
            "validation_pass_count": validation_pass_count,
            "llm_route_pass_count": llm_route_pass_count,
            "evidence_refs_known_count": evidence_refs_known_count,
            "unsupported_expected_count": unsupported_expected_count,
            "unsupported_expected_pass_count": unsupported_expected_pass_count,
            "forbidden_tool_call_count": forbidden_tool_call_count,
            "total_latency_ms": _sum_case_model_metric(cases, "latency_ms"),
            "total_tokens": _sum_case_model_metric(cases, "total_tokens"),
        },
        "cases": cases,
    }


def _stdout_summary(summary: dict[str, Any], output_path: Path) -> dict[str, Any]:
    return {
        "run_id": summary["run_id"],
        "gate_status": summary["gate_status"],
        "diagnostic_only": summary["diagnostic_only"],
        "output_path": str(output_path.resolve()),
        "metrics": summary["metrics"],
        "failures": [
            {
                "case_id": case["case_id"],
                "agent_id": case["agent_id"],
                "checks": case["checks"],
                "failure_reason": case["failure_reason"],
                "unknown_evidence_refs": case["unknown_evidence_refs"],
            }
            for case in summary["cases"]
            if case["status"] != "pass"
        ],
    }


def _tool_call_count(route_result: dict[str, Any]) -> int:
    diagnostics = route_result.get("model_diagnostics") if isinstance(route_result.get("model_diagnostics"), dict) else {}
    calls = diagnostics.get("calls") if isinstance(diagnostics.get("calls"), list) else []
    return sum(int(call.get("tool_call_count") or 0) for call in calls if isinstance(call, dict))


def _sum_case_model_metric(cases: list[dict[str, Any]], metric: str) -> int | None:
    values: list[int] = []
    for case in cases:
        value = (case.get("model_diagnostics") or {}).get(metric)
        if value is not None:
            values.append(int(value))
    if not values:
        return None
    return sum(values)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _default_run_id(args: argparse.Namespace) -> str:
    safe_model = re_safe(str(args.model or "model"))
    return f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_multi_agent_specialist_memolet_{safe_model}_v0_1"


def re_safe(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_") or "model"


if __name__ == "__main__":
    raise SystemExit(main())
