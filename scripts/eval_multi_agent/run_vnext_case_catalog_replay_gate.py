from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.eval_case_catalog import expand_case_catalog, load_case_catalog  # noqa: E402
from sec_agent.langgraph_orchestrator import make_multi_agent_smoke_state  # noqa: E402
from sec_agent.workbench.job_runner import build_eval_command  # noqa: E402


DEFAULT_CATALOG_PATH = REPO_ROOT / "tests" / "fixtures" / "fin_agent_vnext_50_case_catalog_v0_1.json"
SUBSET_EVAL_ID = {
    "r12_successor_12": "agent_graph_vnext_r12_successor_12",
    "broader_release_20": "agent_graph_vnext_broader_release_20",
    "load_mix_15": "agent_graph_vnext_load_mix_15",
}
REQUIRED_DIMENSIONS = {
    "fundamentals",
    "product_and_production",
    "capital_and_financing",
    "industry_supply_chain",
    "competition_and_market_position",
    "risk_and_counterevidence",
}
R12_REQUIRED_SPECIALISTS = {
    "fundamental_analyst",
    "product_technology_analyst",
    "industry_supply_chain_analyst",
    "market_valuation_analyst",
    "risk_counterevidence_analyst",
}
R12_REQUIRED_OPERATORS = {
    "universe_relationship",
    "sec_operator",
    "eight_k_operator",
    "market_operator",
    "industry_operator",
}
R12_REQUIRED_TOOLS = {
    "relationship_graph_lookup",
    "sec_search_filings",
    "market_get_snapshot",
    "industry_get_snapshot",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate vNext catalog subset replay readiness without model calls.")
    parser.add_argument("--catalog-path", type=Path, default=DEFAULT_CATALOG_PATH)
    parser.add_argument("--subset", default="r12_successor_12", choices=sorted(SUBSET_EVAL_ID))
    parser.add_argument("--output-path", type=Path, default=REPO_ROOT / "reports" / "quality" / "r12_case_catalog_replay_gate.json")
    parser.add_argument("--expanded-cases-path", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_gate(
        catalog_path=args.catalog_path,
        subset=args.subset,
        output_path=args.output_path,
        expanded_cases_path=args.expanded_cases_path,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    if args.strict and report["status"] != "pass":
        return 1
    return 0


def run_gate(
    *,
    catalog_path: Path,
    subset: str,
    output_path: Path | None = None,
    expanded_cases_path: Path | None = None,
) -> dict[str, Any]:
    catalog = load_case_catalog(catalog_path)
    cases = expand_case_catalog(catalog, subset=subset)
    case_checks = [_validate_case(case, subset=subset) for case in cases]
    workbench_check = _validate_workbench_command(subset=subset)
    failures = [
        {"case_id": check["case_id"], "failed_checks": check["failed_checks"]}
        for check in case_checks
        if check["failed_checks"]
    ]
    if workbench_check["failed_checks"]:
        failures.append({"case_id": "__workbench_command__", "failed_checks": workbench_check["failed_checks"]})

    report = {
        "schema_version": "fin_agent_vnext_case_catalog_replay_gate_v0_1",
        "catalog_path": str(catalog_path.resolve()),
        "catalog_id": str(catalog.get("catalog_id") or ""),
        "catalog_schema_version": str(catalog.get("schema_version") or ""),
        "subset": subset,
        "status": "pass" if not failures and cases else "fail",
        "case_count": len(cases),
        "family_counts": dict(Counter(str(case.get("catalog_case_family") or "") for case in cases)),
        "mode_counts": dict(Counter(str(case.get("expected_execution_mode") or "") for case in cases)),
        "category_counts": dict(Counter(str(case.get("category") or "") for case in cases)),
        "case_ids": [str(case.get("case_id") or "") for case in cases],
        "case_checks": case_checks,
        "workbench_command_check": workbench_check,
        "failures": failures,
    }
    if expanded_cases_path:
        expanded_cases_path.parent.mkdir(parents=True, exist_ok=True)
        _write_jsonl(expanded_cases_path, cases)
        report["expanded_cases_path"] = str(expanded_cases_path.resolve())
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def _validate_case(case: Mapping[str, Any], *, subset: str) -> dict[str, Any]:
    query_contract = _query_contract_projection(case)
    smoke_state = make_multi_agent_smoke_state(
        user_query=str(case.get("prompt") or ""),
        output_dir=Path("replay_gate_no_write"),
        query_contract=query_contract,
        focus_tickers=_list(case.get("focus_tickers")),
        search_scope_tickers=_list(case.get("search_scope_tickers")),
    )
    checks = {
        "case_id_present": bool(str(case.get("case_id") or "").strip()),
        "prompt_present": bool(str(case.get("prompt") or "").strip()),
        "focus_inside_search_scope": set(_list(case.get("focus_tickers"))) <= set(_list(case.get("search_scope_tickers"))),
        "catalog_metadata_present": all(
            str(case.get(key) or "").strip()
            for key in ("catalog_id", "catalog_schema_version", "catalog_case_family", "catalog_ordinal")
        ),
        "subset_membership_present": subset in set(_list(case.get("catalog_release_subsets"))),
        "source_inventory_present": bool(_list(case.get("source_inventory_companies"))),
        "run_audit_required": bool(case.get("require_run_audit_store")),
        "vnext_contract_required": bool(case.get("require_vnext_contract")),
        "milvus_contract_required": bool(case.get("require_milvus_runtime_contract")),
        "response_language_required": str(case.get("response_language") or "") == "zh-CN",
        "query_contract_tickers_match_search_scope": set(query_contract.get("tickers") or [])
        == set(_list(case.get("search_scope_tickers"))),
        "query_contract_focus_tickers_match": set(query_contract.get("focus_tickers") or [])
        == set(_list(case.get("focus_tickers"))),
        "query_contract_source_tiers_present": bool(query_contract.get("source_tiers")),
        "query_contract_metric_families_present": bool(query_contract.get("metric_families")),
        "smoke_state_query_contract_preserved": _query_contract_preserved(
            expected=query_contract,
            actual=smoke_state.get("query_contract") if isinstance(smoke_state.get("query_contract"), Mapping) else {},
        ),
        "smoke_state_selected_tickers_cover_focus": set(_list(case.get("focus_tickers")))
        <= set(_list(smoke_state.get("selected_tickers"))),
        "smoke_state_trace_initialized": isinstance(smoke_state.get("node_trace"), list)
        and isinstance(smoke_state.get("agent_trace"), list),
    }
    if subset == "r12_successor_12":
        checks.update(
            {
                "family_is_l3": case.get("catalog_case_family") == "L3_deep_research",
                "category_is_sector_depth": case.get("category") == "sector_depth",
                "mode_is_deep_research": case.get("expected_execution_mode") == "deep_research",
                "dimensions_cover_full_six": REQUIRED_DIMENSIONS <= set(_list(case.get("required_dimension_ids"))),
                "required_specialists_present": R12_REQUIRED_SPECIALISTS <= set(_list(case.get("expected_specialist_agents"))),
                "required_operators_present": R12_REQUIRED_OPERATORS <= set(_list(case.get("expected_operator_agents"))),
                "required_tools_present": R12_REQUIRED_TOOLS <= set(_list(case.get("expected_tool_names"))),
                "relationship_pack_present": bool(_list(case.get("expected_relationship_pack_ids"))),
                "memo_depth_gates_required": all(
                    bool(case.get(key))
                    for key in (
                        "require_rendered_memo_claims",
                        "require_rendered_evidence_refs",
                        "require_dimension_memo_surface",
                        "require_analyst_depth_gate",
                    )
                ),
                "real_retrieval_and_specialist_quality_required": bool(case.get("require_real_retrieval_pass"))
                and bool(case.get("require_real_evidence_quality_pass")),
            }
        )
    failed = sorted(key for key, ok in checks.items() if not ok)
    return {
        "case_id": str(case.get("case_id") or ""),
        "query_contract_summary": {
            "ticker_count": len(query_contract.get("tickers") or []),
            "focus_ticker_count": len(query_contract.get("focus_tickers") or []),
            "source_tier_count": len(query_contract.get("source_tiers") or []),
            "metric_family_count": len(query_contract.get("metric_families") or []),
            "evidence_requirement_count": len(query_contract.get("evidence_requirements") or []),
        },
        "checks": checks,
        "failed_checks": failed,
    }


def _query_contract_projection(case: Mapping[str, Any]) -> dict[str, Any]:
    focus = _list(case.get("focus_tickers"))
    tickers = _list(case.get("search_scope_tickers")) or focus
    metric_families = _list(case.get("metric_families")) or ["revenue", "capex", "margin"]
    source_tiers = _list(case.get("source_tiers")) or ["primary_sec_filing"]
    dimensions = _list(case.get("required_dimension_ids"))
    return {
        "schema_version": "fin_agent_vnext_case_catalog_replay_query_contract_v0_1",
        "tickers": tickers,
        "focus_tickers": focus or tickers[:2],
        "source_tiers": source_tiers,
        "metric_families": metric_families,
        "years": [2026],
        "filing_types": ["10-Q", "8-K"],
        "response_language": str(case.get("response_language") or "zh-CN"),
        "evidence_requirements": [
            {
                "task_id": f"{case.get('case_id')}_{dimension}",
                "dimension_id": dimension,
                "source_tiers": source_tiers,
                "metric_families": metric_families,
            }
            for dimension in dimensions
        ],
    }


def _query_contract_preserved(*, expected: Mapping[str, Any], actual: Mapping[str, Any]) -> bool:
    for key, value in expected.items():
        if actual.get(key) != value:
            return False
    return True


def _validate_workbench_command(*, subset: str) -> dict[str, Any]:
    eval_id = SUBSET_EVAL_ID[subset]
    spec = build_eval_command(repo_root=REPO_ROOT, eval_id=eval_id, job_id=f"{subset}_replay_gate")
    args = [str(arg) for arg in spec.args]
    checks = {
        "eval_id_supported": spec.label == f"eval:{eval_id}",
        "catalog_path_arg_present": "--case-catalog-path" in args
        and "tests/fixtures/fin_agent_vnext_50_case_catalog_v0_1.json" in args,
        "subset_arg_present": "--case-subset" in args and args[args.index("--case-subset") + 1] == subset,
        "summary_output_present": "--summary-output-path" in args,
        "run_audit_db_present": "--run-audit-db-path" in args,
        "strict_enabled": "--strict" in args,
        "secret_not_in_args": not any(arg.startswith("sk-") for arg in args),
    }
    return {
        "eval_id": eval_id,
        "args_digest": {
            "script": args[2] if len(args) > 2 else "",
            "case_subset": args[args.index("--case-subset") + 1] if "--case-subset" in args else "",
            "bge_device": args[args.index("--bge-device") + 1] if "--bge-device" in args else "",
            "strict": "--strict" in args,
        },
        "checks": checks,
        "failed_checks": sorted(key for key, ok in checks.items() if not ok),
    }


def _list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item)]
    return [str(value)]


def _write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
