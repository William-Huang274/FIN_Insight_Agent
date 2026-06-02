from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

from sec_agent.research_lead_llm import ResearchLeadLLMConfig, route_research_lead_activation_llm  # noqa: E402


DEFAULT_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "multi_agent_activation_cases_v0_1.jsonl"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "eval" / "sec_cases" / "outputs" / "multi_agent_activation_diagnostic"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Research Lead LLM activation routing diagnostics.")
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
    parser.add_argument("--temperature", type=float, default=float(os.environ.get("TEMPERATURE", "0")))
    parser.add_argument("--max-tokens", type=int, default=int(os.environ.get("RESEARCH_LEAD_MAX_TOKENS", "2400")))
    parser.add_argument("--timeout-s", type=int, default=int(os.environ.get("RESEARCH_LEAD_TIMEOUT_S", "180")))
    parser.add_argument("--max-repair-attempts", type=int, default=int(os.environ.get("RESEARCH_LEAD_MAX_REPAIR_ATTEMPTS", "2")))
    parser.add_argument(
        "--allow-deterministic-fallback",
        action="store_true",
        help="Explicitly return deterministic fallback plans if LLM validation fails.",
    )
    parser.add_argument(
        "--require-evidence-requirements",
        action="store_true",
        help="Require Research Lead LLM output to include a valid EvidenceRequirementPlan.",
    )
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

    config = ResearchLeadLLMConfig(
        llm_backend=args.llm_backend,
        base_url=args.base_url,
        chat_completions_path=args.chat_completions_path,
        model=args.model,
        api_key_env=args.api_key_env,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        timeout_s=args.timeout_s,
        max_repair_attempts=args.max_repair_attempts,
        allow_deterministic_fallback=args.allow_deterministic_fallback,
        require_evidence_requirements=args.require_evidence_requirements,
    )

    started = time.time()
    cases: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        case_started = time.time()
        request = {
            "prompt": row.get("prompt") or row.get("user_query") or "",
            "focus_tickers": row.get("focus_tickers") or [],
            "search_scope_tickers": row.get("search_scope_tickers") or [],
            "source_inventory": row.get("source_inventory") or {},
            "context": row.get("context") or {},
        }
        route_result = route_research_lead_activation_llm(request, config=config)
        cases.append(
            _evaluate_case(
                row=row,
                route_result=route_result,
                elapsed_sec=round(time.time() - case_started, 4),
                ordinal=index,
                total=len(rows),
                require_evidence_requirements=bool(args.require_evidence_requirements),
            )
        )

    summary = _summarize(
        run_id=run_id,
        args=args,
        rows=rows,
        cases=cases,
        elapsed_sec=round(time.time() - started, 4),
    )
    output_path = output_dir / "activation_diagnostic.json"
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
    require_evidence_requirements: bool,
) -> dict[str, Any]:
    plan = route_result.get("activation_plan") if isinstance(route_result.get("activation_plan"), dict) else {}
    evidence_plan = route_result.get("evidence_requirement_plan") if isinstance(route_result.get("evidence_requirement_plan"), dict) else {}
    evidence_validation = (
        evidence_plan.get("multi_agent_evidence_requirement_validation")
        if isinstance(evidence_plan.get("multi_agent_evidence_requirement_validation"), dict)
        else {}
    )
    active = set(plan.get("activate_agents") or [])
    required_agents = set(row.get("required_agents") or [])
    forbidden_agents = set(row.get("forbidden_agents") or [])
    forbidden_hits = sorted(forbidden_agents & active)
    expected_mode = str(row.get("expected_execution_mode") or "")
    max_tool_calls_lte = row.get("max_tool_calls_total_lte")
    try:
        max_tool_calls = int(plan.get("max_tool_calls_total"))
    except (TypeError, ValueError):
        max_tool_calls = -1
    budget_pass = max_tool_calls_lte is None or (max_tool_calls >= 0 and max_tool_calls <= int(max_tool_calls_lte))
    checks = {
        "llm_route_pass": route_result.get("status") == "pass",
        "validation_pass": (route_result.get("validation") or {}).get("status") == "pass",
        "mode_match": plan.get("execution_mode") == expected_mode,
        "required_agents_present": required_agents <= active,
        "forbidden_agents_absent": not forbidden_hits,
        "budget_lte": budget_pass,
        "evidence_requirement_validation_pass": (
            not require_evidence_requirements
            or evidence_validation.get("status") == "pass"
        ),
    }
    hard_checks = {
        key: checks[key]
        for key in (
            "llm_route_pass",
            "validation_pass",
            "mode_match",
            "required_agents_present",
            "forbidden_agents_absent",
            "evidence_requirement_validation_pass",
        )
    }
    return {
        "case_id": row.get("case_id"),
        "category": row.get("category") or "",
        "industry": row.get("industry") or "",
        "difficulty": row.get("difficulty") or "",
        "question_layer": row.get("question_layer") or "",
        "expected_relationship_pack_ids": row.get("expected_relationship_pack_ids") or [],
        "allowed_cross_sector_relationship_pack_ids": row.get("allowed_cross_sector_relationship_pack_ids") or [],
        "expected_tool_names": row.get("expected_tool_names") or [],
        "require_runtime_ledger_rows": bool(row.get("require_runtime_ledger_rows")),
        "require_universe_llm_pass": bool(row.get("require_universe_llm_pass")),
        "ordinal": ordinal,
        "total": total,
        "prompt": row.get("prompt"),
        "expected_execution_mode": expected_mode,
        "actual_execution_mode": plan.get("execution_mode"),
        "status": "pass" if all(hard_checks.values()) else "fail",
        "checks": checks,
        "hard_checks": hard_checks,
        "missing_required_agents": sorted(required_agents - active),
        "forbidden_agent_hits": forbidden_hits,
        "elapsed_sec": elapsed_sec,
        "route_status": route_result.get("status"),
        "failure_reason": route_result.get("failure_reason") or "",
        "activation_plan": plan,
        "validation": route_result.get("validation") or {},
        "routing_trace": route_result.get("routing_trace") or {},
        "evidence_requirement_plan": evidence_plan,
        "evidence_requirement_validation": evidence_validation,
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
    all_checks_pass_count = sum(1 for case in cases if all(case["checks"].values()))
    mode_correct_count = sum(1 for case in cases if case["checks"]["mode_match"])
    forbidden_activation_count = sum(len(case["forbidden_agent_hits"]) for case in cases)
    validation_pass_count = sum(1 for case in cases if case["checks"]["validation_pass"])
    llm_route_pass_count = sum(1 for case in cases if case["checks"]["llm_route_pass"])
    required_agent_pass_count = sum(1 for case in cases if case["checks"]["required_agents_present"])
    budget_pass_count = sum(1 for case in cases if case["checks"]["budget_lte"])
    evidence_requirement_pass_count = sum(1 for case in cases if case["checks"]["evidence_requirement_validation_pass"])
    gate_pass = (
        total == len(rows)
        and total > 0
        and pass_count == total
        and mode_correct_count == total
        and validation_pass_count == total
        and llm_route_pass_count == total
        and required_agent_pass_count == total
        and forbidden_activation_count == 0
        and evidence_requirement_pass_count == total
    )
    return {
        "schema_version": "sec_agent_research_lead_activation_diagnostic_v0.1",
        "run_id": run_id,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_sec": elapsed_sec,
        "gate_status": "pass" if gate_pass else "fail",
        "diagnostic_only": True,
        "fixture": str(Path(args.fixture).resolve()),
        "output_contract": {
            "raw_llm_response_saved": False,
            "api_key_saved": False,
            "activation_plan_saved": True,
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
            "allow_deterministic_fallback": args.allow_deterministic_fallback,
            "require_evidence_requirements": args.require_evidence_requirements,
        },
        "metrics": {
            "case_count": total,
            "pass_count": pass_count,
            "all_checks_pass_count": all_checks_pass_count,
            "mode_correct_count": mode_correct_count,
            "validation_pass_count": validation_pass_count,
            "llm_route_pass_count": llm_route_pass_count,
            "required_agent_pass_count": required_agent_pass_count,
            "budget_pass_count": budget_pass_count,
            "evidence_requirement_pass_count": evidence_requirement_pass_count,
            "forbidden_activation_count": forbidden_activation_count,
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
                "checks": case["checks"],
                "actual_execution_mode": case["actual_execution_mode"],
                "failure_reason": case["failure_reason"],
                "forbidden_agent_hits": case["forbidden_agent_hits"],
                "missing_required_agents": case["missing_required_agents"],
            }
            for case in summary["cases"]
            if case["status"] != "pass"
        ],
        "diagnostic_warnings": [
            {
                "case_id": case["case_id"],
                "checks": case["checks"],
                "actual_execution_mode": case["actual_execution_mode"],
            }
            for case in summary["cases"]
            if case["status"] == "pass" and not all(case["checks"].values())
        ],
    }


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
    return f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_multi_agent_research_lead_activation_{safe_model}_v0_1"


def re_safe(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_") or "model"


if __name__ == "__main__":
    raise SystemExit(main())
