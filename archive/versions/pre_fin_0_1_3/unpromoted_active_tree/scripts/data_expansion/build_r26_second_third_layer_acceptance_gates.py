from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.layer_acceptance_gates import (  # noqa: E402
    build_combined_layer_acceptance_gate,
    build_second_layer_acceptance_gate,
    build_third_layer_acceptance_gate,
    load_json,
    load_jsonl,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build R26 deterministic acceptance gates for second and third data layers.")
    parser.add_argument("--company-count", type=int, default=603)
    parser.add_argument(
        "--product-graph-summary",
        type=Path,
        default=REPO_ROOT / "data/manifests/product_relationship_graph_summary_v0_1.json",
    )
    parser.add_argument(
        "--product-slots",
        type=Path,
        default=REPO_ROOT / "data/manifests/company_product_slots_v0_1.jsonl",
    )
    parser.add_argument(
        "--product-graph-edges",
        type=Path,
        default=REPO_ROOT / "data/manifests/product_relationship_graph_edges_v0_1.jsonl",
    )
    parser.add_argument(
        "--product-kpi-diagnostic-summary",
        type=Path,
        default=REPO_ROOT / "data/manifests/product_kpi_deep_gap_diagnostic_summary_v0_1.json",
    )
    parser.add_argument(
        "--product-kpi-closeout",
        type=Path,
        default=REPO_ROOT / "data/manifests/product_kpi_exact_slot_closeout_v0_1.jsonl",
    )
    parser.add_argument(
        "--r17-product-family-evidence-rows",
        type=Path,
        default=REPO_ROOT / "data/manifests/r17_product_family_evidence_runtime_rows_v0_1.jsonl",
    )
    parser.add_argument(
        "--r17-product-family-evidence-summary",
        type=Path,
        default=REPO_ROOT / "data/manifests/r17_product_family_evidence_summary_v0_1.json",
    )
    parser.add_argument(
        "--sec-financial-statement-summary",
        type=Path,
        default=REPO_ROOT / "data/manifests/sec_financial_statement_metric_runtime_summary_v0_1.json",
    )
    parser.add_argument(
        "--non-us-l1-financial-summary",
        type=Path,
        default=REPO_ROOT / "data/manifests/non_us_l1_financial_statement_metric_runtime_summary_v0_1.json",
    )
    parser.add_argument(
        "--capital-context-summary",
        type=Path,
        default=REPO_ROOT / "data/manifests/capital_funding_ownership_context_summary_v0_1.json",
    )
    parser.add_argument(
        "--sec-capital-event-summary",
        type=Path,
        default=REPO_ROOT / "data/manifests/sec_capital_market_event_context_summary_v0_1.json",
    )
    parser.add_argument(
        "--sec-capital-event-rows",
        type=Path,
        default=REPO_ROOT / "data/manifests/sec_capital_market_event_context_rows_v0_1.jsonl",
    )
    parser.add_argument(
        "--r18-registry-summary",
        type=Path,
        default=REPO_ROOT / "data/manifests/r18_source_route_registry_v2_summary.json",
    )
    parser.add_argument(
        "--r18-authority-mart-summary",
        type=Path,
        default=REPO_ROOT / "data/manifests/r18_source_authority_data_mart_summary_v0_1.json",
    )
    parser.add_argument(
        "--output-second-layer",
        type=Path,
        default=REPO_ROOT / "data/manifests/r26_second_layer_acceptance_gate_summary_v0_1.json",
    )
    parser.add_argument(
        "--output-third-layer",
        type=Path,
        default=REPO_ROOT / "data/manifests/r26_third_layer_acceptance_gate_summary_v0_1.json",
    )
    parser.add_argument(
        "--output-combined",
        type=Path,
        default=REPO_ROOT / "data/manifests/r26_second_third_layer_acceptance_gate_summary_v0_1.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    second_layer = build_second_layer_acceptance_gate(
        product_graph_summary=load_json(args.product_graph_summary),
        product_slots=load_jsonl(args.product_slots),
        product_graph_edges=load_jsonl(args.product_graph_edges),
        product_kpi_diagnostic_summary=load_json(args.product_kpi_diagnostic_summary),
        product_kpi_closeout_rows=load_jsonl(args.product_kpi_closeout),
        r17_product_family_evidence_rows=load_jsonl(args.r17_product_family_evidence_rows),
        r17_product_family_evidence_summary=load_json(args.r17_product_family_evidence_summary),
        company_count=args.company_count,
    )
    third_layer = build_third_layer_acceptance_gate(
        sec_financial_statement_summary=load_json(args.sec_financial_statement_summary),
        non_us_l1_financial_summary=load_json(args.non_us_l1_financial_summary),
        capital_context_summary=load_json(args.capital_context_summary),
        sec_capital_event_summary=load_json(args.sec_capital_event_summary),
        sec_capital_event_rows=load_jsonl(args.sec_capital_event_rows),
        r18_registry_summary=load_json(args.r18_registry_summary),
        r18_authority_mart_summary=load_json(args.r18_authority_mart_summary),
        company_count=args.company_count,
    )
    combined = build_combined_layer_acceptance_gate(second_layer_gate=second_layer, third_layer_gate=third_layer)

    for path, payload in (
        (args.output_second_layer, second_layer),
        (args.output_third_layer, third_layer),
        (args.output_combined, combined),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({"second_layer": second_layer["status"], "third_layer": third_layer["status"], "combined": combined["status"]}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if combined.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
