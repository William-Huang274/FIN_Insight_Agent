from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

from sec_agent.relationship_graph import query_relationship_graph  # noqa: E402
from sec_agent.multi_agent_contracts import validate_economic_link_map  # noqa: E402
from sec_agent.universe_relationship_llm import (  # noqa: E402
    UniverseRelationshipLLMConfig,
    route_universe_relationship_llm,
)


DEFAULT_ACTIVATION_SUMMARY = (
    REPO_ROOT
    / "eval"
    / "sec_cases"
    / "outputs"
    / "multi_agent_activation_diagnostic"
    / "20260601_fin_agent_s1_research_lead_quality_gate_deepseek_v0_1"
    / "activation_diagnostic.json"
)
DEFAULT_OUTPUT_DIR = REPO_ROOT / "eval" / "sec_cases" / "outputs" / "multi_agent_universe_relationship_diagnostic"
DEFAULT_SECTOR_DEPTH_PACK = REPO_ROOT / "configs" / "sector_depth_packs_v0_2.yaml"
SUMMARY_SCHEMA_VERSION = "sec_agent_universe_relationship_diagnostic_v0.1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run S2 Universe / Relationship gate from a passed S1 activation artifact.")
    parser.add_argument("--activation-summary", type=Path, default=DEFAULT_ACTIVATION_SUMMARY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--relationship-graph-path", type=Path, default=None)
    parser.add_argument("--sector-depth-pack-path", type=Path, default=DEFAULT_SECTOR_DEPTH_PACK)
    parser.add_argument("--llm-backend", default=os.environ.get("LLM_BACKEND", "deepseek"))
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", "https://api.deepseek.com"))
    parser.add_argument("--chat-completions-path", default=os.environ.get("CHAT_COMPLETIONS_PATH", "/chat/completions"))
    parser.add_argument("--model", default=os.environ.get("MODEL_NAME", "deepseek-v4-pro"))
    parser.add_argument("--api-key-env", default=os.environ.get("API_KEY_ENV", "DEEPSEEK_API_KEY"))
    parser.add_argument("--temperature", type=float, default=float(os.environ.get("UNIVERSE_TEMPERATURE", "0")))
    parser.add_argument("--max-tokens", type=int, default=int(os.environ.get("UNIVERSE_MAX_TOKENS", "4200")))
    parser.add_argument("--timeout-s", type=int, default=int(os.environ.get("UNIVERSE_TIMEOUT_S", "180")))
    parser.add_argument("--max-repair-attempts", type=int, default=int(os.environ.get("UNIVERSE_MAX_REPAIR_ATTEMPTS", "2")))
    parser.add_argument("--input-max-relationships", type=int, default=int(os.environ.get("UNIVERSE_INPUT_MAX_RELATIONSHIPS", "8")))
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    activation_summary = _read_json(args.activation_summary)
    cases = _selected_cases(_universe_cases(activation_summary), args.case_id)
    run_id = args.run_id or _default_run_id()
    output_dir = args.output_dir / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    config = UniverseRelationshipLLMConfig(
        llm_backend=args.llm_backend,
        base_url=args.base_url,
        chat_completions_path=args.chat_completions_path,
        model=args.model,
        api_key_env=args.api_key_env,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        timeout_s=args.timeout_s,
        max_repair_attempts=args.max_repair_attempts,
        input_max_relationships=args.input_max_relationships,
        require_economic_link_map=True,
    )

    started = time.time()
    scores: list[dict[str, Any]] = []
    for ordinal, case in enumerate(cases, start=1):
        case_started = time.time()
        case_dir = output_dir / str(case.get("case_id") or f"case_{ordinal}")
        case_dir.mkdir(parents=True, exist_ok=True)
        lookup = query_relationship_graph(
            focus_tickers=_string_list((case.get("activation_plan") or {}).get("focus_tickers")),
            search_scope_tickers=_string_list((case.get("activation_plan") or {}).get("search_scope_tickers")),
            user_query=str(case.get("prompt") or ""),
            relationship_graph_path=args.relationship_graph_path,
            sector_depth_pack_path=args.sector_depth_pack_path,
            expected_pack_ids=_string_list(case.get("expected_relationship_pack_ids")),
        )
        route = route_universe_relationship_llm(
            {
                "user_query": case.get("prompt") or "",
                "activation_plan": case.get("activation_plan") or {},
                "relationship_lookup": lookup,
                "source_inventory": _source_inventory_from_case(case, lookup),
            },
            config=config,
        )
        score = _score_case(
            case,
            lookup=lookup,
            route=route,
            elapsed_sec=round(time.time() - case_started, 4),
            ordinal=ordinal,
            total=len(cases),
        )
        (case_dir / "relationship_lookup.json").write_text(json.dumps(lookup, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (case_dir / "universe_relationship_result.json").write_text(json.dumps(route, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (case_dir / "universe_relationship_case_score.json").write_text(json.dumps(score, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        scores.append(score)

    summary = _aggregate(
        run_id=run_id,
        args=args,
        activation_summary=activation_summary,
        cases=cases,
        scores=scores,
        elapsed_sec=round(time.time() - started, 4),
        output_dir=output_dir,
    )
    summary_path = output_dir / "universe_relationship_diagnostic.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_stdout_summary(summary, summary_path), ensure_ascii=False, indent=2))
    if args.strict and summary["gate_status"] != "pass":
        return 1
    return 0


def _universe_cases(activation_summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    cases = []
    for case in activation_summary.get("cases") or []:
        if not isinstance(case, Mapping):
            continue
        activation = case.get("activation_plan") if isinstance(case.get("activation_plan"), Mapping) else {}
        if "universe_relationship" in _string_list(activation.get("activate_agents")):
            cases.append(dict(case))
    return cases


def _selected_cases(cases: list[dict[str, Any]], selected_ids: list[str]) -> list[dict[str, Any]]:
    if not selected_ids:
        return cases
    selected = {str(item) for item in selected_ids}
    return [case for case in cases if str(case.get("case_id") or "") in selected]


def _score_case(
    case: Mapping[str, Any],
    *,
    lookup: Mapping[str, Any],
    route: Mapping[str, Any],
    elapsed_sec: float,
    ordinal: int,
    total: int,
) -> dict[str, Any]:
    plan = route.get("universe_relationship_plan") if isinstance(route.get("universe_relationship_plan"), Mapping) else {}
    validation = route.get("universe_relationship_validation") if isinstance(route.get("universe_relationship_validation"), Mapping) else {}
    relationships = [row for row in plan.get("relationships") or [] if isinstance(row, Mapping)]
    lookup_relationships = [row for row in lookup.get("relationships") or [] if isinstance(row, Mapping)]
    economic_link_validation = validate_economic_link_map(
        plan.get("economic_link_map") if isinstance(plan.get("economic_link_map"), Mapping) else {},
        known_evidence_refs={ref for row in relationships for ref in _string_list(row.get("evidence_refs"))},
        allowed_tickers=set(_string_list(plan.get("included_tickers"))),
    )
    economic_link_map = economic_link_validation.get("economic_link_map") if isinstance(economic_link_validation.get("economic_link_map"), Mapping) else {}
    checks = {
        "activation_requires_universe": True,
        "relationship_lookup_has_rows": bool(lookup_relationships),
        "llm_route_pass": route.get("status") == "pass",
        "fallback_not_used": route.get("status") != "fallback" and not bool((route.get("routing_trace") or {}).get("fallback_used")),
        "validation_pass": validation.get("status") == "pass",
        "plan_relationships_present": bool(relationships),
        "relationship_refs_present": all(_string_list(row.get("evidence_refs")) for row in relationships),
        "relationship_scope_only": all(str(row.get("claim_scope") or "") == "scope_or_hypothesis_only" for row in relationships),
        "financial_fact_policy_preserved": str(plan.get("source_family") or "") == "relationship_graph",
        "economic_link_map_pass": economic_link_validation.get("status") == "pass",
        "economic_entities_present": bool(economic_link_map.get("entities")),
        "economic_links_present": bool(economic_link_map.get("links")),
        "economic_mechanisms_present": bool(economic_link_map.get("mechanisms")),
        "investment_implications_present": bool(economic_link_map.get("investment_implications")),
    }
    return {
        "case_id": case.get("case_id"),
        "ordinal": ordinal,
        "total": total,
        "prompt": case.get("prompt"),
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "elapsed_sec": elapsed_sec,
        "lookup_status": lookup.get("status"),
        "lookup_relationship_count": len(lookup_relationships),
        "plan_relationship_count": len(relationships),
        "included_tickers": _string_list(plan.get("included_tickers")),
        "relationship_refs": sorted({ref for row in relationships for ref in _string_list(row.get("evidence_refs"))}),
        "economic_link_map_stats": {
            "entity_count": len([row for row in economic_link_map.get("entities") or [] if isinstance(row, Mapping)]),
            "link_count": len([row for row in economic_link_map.get("links") or [] if isinstance(row, Mapping)]),
            "mechanism_count": len([row for row in economic_link_map.get("mechanisms") or [] if isinstance(row, Mapping)]),
            "investment_implication_count": len([row for row in economic_link_map.get("investment_implications") or [] if isinstance(row, Mapping)]),
        },
        "economic_link_map_validation": economic_link_validation,
        "source_gaps": lookup.get("source_gaps") or [],
        "route_status": route.get("status"),
        "failure_reason": route.get("failure_reason") or "",
        "routing_trace": route.get("routing_trace") or {},
        "model_diagnostics": route.get("model_diagnostics") or {},
    }


def _aggregate(
    *,
    run_id: str,
    args: argparse.Namespace,
    activation_summary: Mapping[str, Any],
    cases: list[Mapping[str, Any]],
    scores: list[Mapping[str, Any]],
    elapsed_sec: float,
    output_dir: Path,
) -> dict[str, Any]:
    total = len(scores)
    pass_count = sum(1 for score in scores if score.get("status") == "pass")
    check_counts: dict[str, int] = {}
    for score in scores:
        checks = score.get("checks") if isinstance(score.get("checks"), Mapping) else {}
        for name, value in checks.items():
            if value:
                check_counts[name] = check_counts.get(name, 0) + 1
    token_total = sum(int((score.get("model_diagnostics") or {}).get("total_tokens") or 0) for score in scores)
    latency_total = sum(int((score.get("model_diagnostics") or {}).get("latency_ms") or 0) for score in scores)
    gate_pass = total > 0 and pass_count == total
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "run_id": run_id,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_sec": elapsed_sec,
        "gate_status": "pass" if gate_pass else "fail",
        "diagnostic_only": True,
        "activation_summary": str(args.activation_summary.resolve()),
        "activation_run_id": str(activation_summary.get("run_id") or ""),
        "output_dir": str(output_dir.resolve()),
        "model_config": {
            "llm_backend": args.llm_backend,
            "base_url": args.base_url,
            "chat_completions_path": args.chat_completions_path,
            "model": args.model,
            "api_key_env": args.api_key_env,
            "api_key_saved": False,
            "temperature": args.temperature,
            "max_tokens": args.max_tokens,
            "timeout_s": args.timeout_s,
            "max_repair_attempts": args.max_repair_attempts,
        },
        "metrics": {
            "case_count": total,
            "pass_count": pass_count,
            "check_counts": dict(sorted(check_counts.items())),
            "total_latency_ms": latency_total,
            "total_tokens": token_total,
            "fallback_count": sum(1 for score in scores if not ((score.get("checks") or {}).get("fallback_not_used"))),
            "lookup_relationship_count": sum(int(score.get("lookup_relationship_count") or 0) for score in scores),
            "plan_relationship_count": sum(int(score.get("plan_relationship_count") or 0) for score in scores),
        },
        "cases": [dict(score) for score in scores],
    }


def _source_inventory_from_case(case: Mapping[str, Any], lookup: Mapping[str, Any]) -> dict[str, Any]:
    activation = case.get("activation_plan") if isinstance(case.get("activation_plan"), Mapping) else {}
    lookup_tickers: list[str] = []
    for row in lookup.get("relationships") or []:
        if not isinstance(row, Mapping):
            continue
        lookup_tickers.extend(_string_list([row.get("ticker"), row.get("related_ticker")]))
    return {
        "available_tickers": _unique_strings(
            [
                *_string_list(activation.get("search_scope_tickers")),
                *_string_list(activation.get("focus_tickers")),
                *lookup_tickers,
            ]
        ),
        "available_source_families": _string_list(activation.get("allowed_source_families")),
    }


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).upper().strip() if _looks_like_ticker(item) else str(item).strip() for item in value if str(item).strip()]


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _looks_like_ticker(value: Any) -> bool:
    text = str(value or "")
    return text.isascii() and 1 <= len(text) <= 8 and text.replace(".", "").isalpha()


def _default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_fin_agent_s2_universe_relationship_gate_deepseek_v0_1")


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _stdout_summary(summary: Mapping[str, Any], summary_path: Path) -> dict[str, Any]:
    return {
        "schema_version": summary.get("schema_version"),
        "run_id": summary.get("run_id"),
        "gate_status": summary.get("gate_status"),
        "diagnostic_only": summary.get("diagnostic_only"),
        "summary_path": str(summary_path),
        "metrics": summary.get("metrics") or {},
        "failures": [
            {"case_id": case.get("case_id"), "checks": case.get("checks"), "failure_reason": case.get("failure_reason")}
            for case in summary.get("cases") or []
            if isinstance(case, Mapping) and case.get("status") != "pass"
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())
