from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.langgraph_orchestrator import _lead_targeted_repair_context_claims
from sec_agent.official_issuer_repair import execute_official_issuer_repair_plan


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke scoped public web gap repair without LLM calls.")
    parser.add_argument("--mode", choices=["fixture", "live", "all"], default="fixture")
    parser.add_argument("--output-dir", default="reports/quality/public_web_gap_repair_smoke/latest")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {"schema_version": "public_web_gap_repair_smoke_v0_1", "runs": {}}

    if args.mode in {"fixture", "all"}:
        report["runs"]["fixture"] = _run_fixture()
    if args.mode in {"live", "all"}:
        report["runs"]["live"] = _run_live()

    summary = {
        key: {
            "status": run.get("execution", {}).get("status"),
            "attempted_count": run.get("execution", {}).get("attempted_count"),
            "success_count": run.get("execution", {}).get("success_count"),
            "bounded_gap_count": run.get("execution", {}).get("bounded_gap_count"),
            "claim_types": sorted({claim.get("claim_type") for claim in run.get("claims", []) if isinstance(claim, dict)}),
        }
        for key, run in report["runs"].items()
        if isinstance(run, dict)
    }
    report["summary"] = summary
    (output_dir / "public_web_gap_repair_smoke.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def _run_fixture() -> dict[str, Any]:
    plan = {
        "schema_version": "finsight_targeted_repair_plan_v0_1",
        "status": "ready",
        "repairs": [
            {
                "repair_id": "repair:fixture:product",
                "dimension": "product_and_production",
                "repair_type": "product_surface",
                "route": "official_product_surface_repair",
                "ticker": "ASML",
                "web_search_allowed": True,
                "web_scope_policy_ids": ["official_product_surface_only"],
                "allowed_source_classes": ["company_product_page"],
                "company_domains": ["asml.com"],
                "official_product_urls": ["https://www.asml.com/en/products"],
                "official_product_surfaces": ["EUV lithography systems", "DUV lithography systems"],
                "official_metric_leads": ["net bookings", "backlog"],
                "not_found_gap": {"gap_type": "bounded_gap_after_official_product_surface_probe"},
            }
        ],
    }

    def fake_fetch(url: str) -> tuple[int, str, str]:
        return 200, "text/html", "<title>ASML products</title><meta name='description' content='EUV and DUV lithography systems.'>"

    execution = execute_official_issuer_repair_plan(plan, fetch=fake_fetch, max_probes_per_issuer=3)
    return {"execution": _compact_execution(execution), "claims": _lead_targeted_repair_context_claims(execution)}


def _run_live() -> dict[str, Any]:
    plan = {
        "schema_version": "finsight_targeted_repair_plan_v0_1",
        "status": "ready",
        "repairs": [
            {
                "repair_id": "repair:live:asml_product",
                "dimension": "product_and_production",
                "repair_type": "product_surface",
                "route": "official_product_surface_repair",
                "ticker": "ASML",
                "web_search_allowed": True,
                "web_scope_policy_ids": ["official_product_surface_only"],
                "allowed_source_classes": ["company_product_page"],
                "company_domains": ["asml.com"],
                "official_product_urls": ["https://www.asml.com/en/products"],
                "official_product_surfaces": ["EUV lithography systems", "DUV lithography systems"],
                "official_metric_leads": ["net bookings", "backlog", "systems revenue"],
                "not_found_gap": {"gap_type": "bounded_gap_after_official_product_surface_probe"},
            },
            {
                "repair_id": "repair:live:asml_sec",
                "dimension": "fundamentals",
                "repair_type": "issuer_official",
                "route": "official_issuer_disclosure_repair",
                "ticker": "ASML",
                "web_search_allowed": True,
                "web_scope_policy_ids": ["company_ir_local_exchange_regulator_sec_fpi_only"],
                "allowed_source_classes": ["government_dataset_endpoint", "company_ir_material"],
                "target_forms": ["20-F", "6-K"],
                "not_found_gap": {"gap_type": "bounded_gap_after_official_issuer_source_probe"},
            },
        ],
    }
    execution = execute_official_issuer_repair_plan(plan, max_probes_per_issuer=2)
    return {"execution": _compact_execution(execution), "claims": _lead_targeted_repair_context_claims(execution)}


def _compact_execution(execution: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": execution.get("schema_version"),
        "status": execution.get("status"),
        "attempted_count": execution.get("attempted_count"),
        "success_count": execution.get("success_count"),
        "bounded_gap_count": execution.get("bounded_gap_count"),
        "context_rows": [
            {
                "evidence_ref": row.get("evidence_ref"),
                "ticker": row.get("ticker"),
                "repair_type": row.get("repair_type"),
                "source_class": row.get("source_class"),
                "source_title": row.get("source_title"),
                "url": row.get("url"),
                "context_only": row.get("context_only"),
                "exact_value_authority": row.get("exact_value_authority"),
                "claim_boundary": row.get("claim_boundary"),
            }
            for row in execution.get("context_rows", [])
            if isinstance(row, dict)
        ],
        "source_gaps": execution.get("source_gaps", []),
        "tool_observations": execution.get("tool_observations", []),
    }


if __name__ == "__main__":
    main()
