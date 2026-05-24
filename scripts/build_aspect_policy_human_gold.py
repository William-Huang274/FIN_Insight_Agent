from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


LABEL_RULESET_VERSION = "codex_financial_evidence_protocol_v0.1"

# Manual finance-review overrides for selected policy candidates. Rows not
# listed here were reviewed as citation-grade direct evidence under v0.1.
MANUAL_OVERRIDES: dict[tuple[str, str, str, str], tuple[str, str]] = {
    (
        "agent_daily_aapl_services_2025",
        "services_net_sales",
        "services_net_sales__aspect_03",
        "AAPL_2025_10K_ITEM8_BLOCK_0003_CHUNK_0001_TABLE_4AA6D197",
    ): (
        "partial",
        "Shows Services net sales and App Store accounting context, but does not state that App Store drove the 2025 Services net sales increase.",
    ),
    (
        "agent_daily_snow_visibility_2025",
        "consumption_visibility_risk",
        "consumption_visibility_risk__aspect_03",
        "SNOW_2025_10K_ITEM7_BLOCK_0006_PART_02_OF_02_CLAIM_627505A5",
    ): (
        "partial",
        "Explains consumption-based recognition and limited visibility, but does not explicitly state customer consumption fluctuates.",
    ),
    (
        "agent_deep_adbe_arr_rpo_subscription_quality_2025",
        "arr_growth",
        "arr_growth__aspect_03",
        "ADBE_2025_10K_ITEM7_BLOCK_0004_PART_02_OF_03_CLAIM_8CDADC04",
    ): (
        "partial",
        "States ARR amount and growth, but not the definition as annual value of subscription contracts.",
    ),
    (
        "agent_deep_adbe_arr_rpo_subscription_quality_2025",
        "arr_growth",
        "arr_growth__aspect_03",
        "ADBE_2025_10K_ITEM7_BLOCK_0004_PART_02_OF_03_METRIC_SENT_9FE29729",
    ): (
        "partial",
        "Metric object supports ARR growth, but does not define ARR as annual subscription contract value.",
    ),
    (
        "agent_deep_adbe_arr_rpo_subscription_quality_2025",
        "contract_caveats",
        "contract_caveats__aspect_03",
        "ADBE_2025_10K_ITEM8_BLOCK_0002_PART_03_OF_06_CLAIM_490684D3",
    ): (
        "partial",
        "Related to usage-based royalties and variable consideration, but not the full RPO exclusion statement.",
    ),
    (
        "agent_deep_nvda_datacenter_durability_2025",
        "cloud_customer_demand_context",
        "cloud_customer_demand_context__aspect_03",
        "NVDA_2025_10K_ITEM1_BLOCK_0001_PART_01_OF_03_CLAIM_C7979D16",
    ): (
        "partial",
        "Supports CSP demand context, but does not state industry-standard servers from every major cloud provider.",
    ),
    (
        "agent_deep_nvda_datacenter_durability_2025",
        "supply_capacity_risk",
        "supply_capacity_risk__aspect_04",
        "NVDA_2025_10K_ITEM1A_BLOCK_0004_PART_02_OF_03_CLAIM_F6709B28",
    ): (
        "partial",
        "Related to new product complexity and delays, but weaker than the explicit product-transition demand risk claim.",
    ),
    (
        "agent_deep_nvda_datacenter_durability_2025",
        "third_party_manufacturing_risk",
        "third_party_manufacturing_risk__aspect_01",
        "NVDA_2025_10K_ITEM1A_BLOCK_0004_PART_03_OF_03_CLAIM_B585330A",
    ): (
        "partial",
        "Shows concentrated suppliers, foundries, and contract manufacturers, but not dependency or reduced control over supplier output.",
    ),
    (
        "agent_deep_nvda_datacenter_durability_2025",
        "third_party_manufacturing_risk",
        "third_party_manufacturing_risk__aspect_03",
        "NVDA_2025_10K_ITEM1A_BLOCK_0004_PART_03_OF_03_CLAIM_BEEED6B3",
    ): (
        "partial",
        "Supports foundry dependency, but does not mention contract manufacturers specifically.",
    ),
    (
        "agent_deep_nvda_datacenter_durability_2025",
        "third_party_manufacturing_risk",
        "third_party_manufacturing_risk__aspect_04",
        "NVDA_2025_10K_ITEM1A_BLOCK_0004_PART_03_OF_03_CLAIM_29CC8B8B",
    ): (
        "partial",
        "Shows reduced control over quantity and delivery schedules, but not an explicit lack of guaranteed supply.",
    ),
    (
        "agent_research_amzn_aws_capex_fcf_2025",
        "fcf_capex_pressure",
        "fcf_capex_pressure__aspect_01",
        "AMZN_2025_10K_ITEM7_BLOCK_0002_PART_01_OF_02_CLAIM_C515B2D9",
    ): (
        "partial",
        "Shows infrastructure spending can pressure short-term free cash flow, but not the full FCF driver definition.",
    ),
    (
        "agent_research_amzn_aws_capex_fcf_2025",
        "fcf_capex_pressure",
        "fcf_capex_pressure__aspect_03",
        "AMZN_2025_10K_ITEM1A_BLOCK_0006_PART_01_OF_02_CLAIM_9F4BF869",
    ): (
        "partial",
        "Shows AI/ML adoption and infrastructure scaling, but not that technology and infrastructure spending supports AI/ML and pressures FCF.",
    ),
    (
        "agent_research_msft_googl_cloud_ai_capex_2025",
        "googl_cloud_growth_profitability",
        "googl_cloud_growth_profitability__aspect_03",
        "GOOGL_2025_10K_ITEM8_BLOCK_0017_CHUNK_0001_TABLE_E769DDFE",
    ): (
        "partial",
        "Table gives Google Cloud revenue, income, and expense amounts, but not the stated operating-income driver sentence.",
    ),
    (
        "agent_research_msft_googl_cloud_ai_capex_2025",
        "msft_ai_capex_margin_pressure",
        "msft_ai_capex_margin_pressure__aspect_03",
        "MSFT_2025_10K_ITEM7_BLOCK_0005_PART_02_OF_02_CLAIM_684F129C",
    ): (
        "partial",
        "Shows AI infrastructure margin pressure, but not capital expenditures to support cloud offerings and AI infrastructure training.",
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a human-reviewed gold subset for aspect precision-gate calibration."
    )
    parser.add_argument(
        "--predictions-path",
        default="reports/verifier/sec_tech_10k_qwen35_4b_aspect_compact_full730.jsonl",
    )
    parser.add_argument(
        "--pool-path",
        default="reports/evidence_pool/sec_tech_10k_bge_top10_aspect_evidence_pool.jsonl",
    )
    parser.add_argument(
        "--output-path",
        default="eval_sets/sec_tech_10k_aspect_policy_human_gold_v0_1.jsonl",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    predictions = list(_read_jsonl(REPO_ROOT / args.predictions_path))
    pool = _pool_map(REPO_ROOT / args.pool_path)
    selected = _selected_policy_rows(predictions)

    rows = []
    for key, row in sorted(selected.items()):
        object_key = (row["query_id"], row["facet"], row["aspect_id"], row["object_id"])
        pool_row = pool[object_key]
        human_label, notes = _manual_label(row)
        rows.append(
            {
                "schema_version": "aspect_policy_human_gold_v0.1",
                "label_status": "codex_manual_finance_review_needs_user_spot_check",
                "review_ruleset_version": LABEL_RULESET_VERSION,
                "reviewer": "codex_manual_finance_review",
                "reviewed_at": "2026-05-16",
                "query_id": row["query_id"],
                "mode": row.get("mode"),
                "ticker": row.get("ticker"),
                "fiscal_year": row.get("fiscal_year"),
                "facet": row["facet"],
                "aspect_id": row["aspect_id"],
                "aspect": row.get("aspect"),
                "object_id": row["object_id"],
                "object_type": row.get("object_type"),
                "source_evidence_id": row.get("source_evidence_id"),
                "section": row.get("section"),
                "subsection": row.get("subsection"),
                "pool_rank": row.get("pool_rank"),
                "rerank_score": row.get("rerank_score"),
                "verifier_label": row.get("verifier_label"),
                "verifier_confidence": row.get("verifier_confidence"),
                "weak_aspect_reference_label": row.get("aspect_reference_label"),
                "selected_by_policies": sorted(row["selected_by_policies"]),
                "human_label": human_label,
                "evidence_role": _evidence_role(human_label),
                "human_notes": notes,
                "preview": row.get("preview"),
                "object_text": pool_row.get("object_text"),
            }
        )

    output_path = REPO_ROOT / args.output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")

    report = {
        "mode": "aspect_policy_human_gold_build",
        "output_path": str(output_path),
        "reviewed_rows": len(rows),
        "manual_override_rows": sum(
            _key(row) in MANUAL_OVERRIDES
            for row in rows
        ),
        "label_counts": _counts(row["human_label"] for row in rows),
        "policy_counts": _policy_counts(rows),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


def _selected_policy_rows(predictions: list[dict[str, Any]]) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    by_aspect: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in predictions:
        if row.get("verifier_label") == "direct":
            by_aspect[(row["query_id"], row["facet"], row["aspect_id"])].append(row)

    selected: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for rows in by_aspect.values():
        policies = {
            "qwen_direct_highest_confidence": _best(
                rows,
                sort_key=lambda row: (
                    float(row.get("verifier_confidence") or 0.0),
                    float(row.get("rerank_score") or 0.0),
                    -int(row.get("pool_rank") or 999),
                ),
            ),
            "qwen_direct_highest_rerank": _best(
                rows,
                sort_key=lambda row: (
                    float(row.get("rerank_score") or 0.0),
                    float(row.get("verifier_confidence") or 0.0),
                    -int(row.get("pool_rank") or 999),
                ),
            ),
            "qwen_direct_highest_rerank_conf90": _best(
                [
                    row
                    for row in rows
                    if float(row.get("verifier_confidence") or 0.0) >= 0.90
                ],
                sort_key=lambda row: (
                    float(row.get("rerank_score") or 0.0),
                    float(row.get("verifier_confidence") or 0.0),
                    -int(row.get("pool_rank") or 999),
                ),
            ),
        }
        for policy, row in policies.items():
            if row is None:
                continue
            selected_key = (row["query_id"], row["facet"], row["aspect_id"], row["object_id"])
            if selected_key not in selected:
                selected[selected_key] = dict(row)
                selected[selected_key]["selected_by_policies"] = set()
            selected[selected_key]["selected_by_policies"].add(policy)
    return selected


def _manual_label(row: dict[str, Any]) -> tuple[str, str]:
    key = _key(row)
    if key in MANUAL_OVERRIDES:
        return MANUAL_OVERRIDES[key]
    return (
        "direct",
        "Citation-grade under the v0.1 financial evidence protocol: same company/period and directly supports the aspect.",
    )


def _evidence_role(label: str) -> str:
    if label == "direct":
        return "citation"
    if label == "partial":
        return "background"
    return "reject"


def _best(rows: list[dict[str, Any]], *, sort_key: Any) -> dict[str, Any] | None:
    return max(rows, key=sort_key) if rows else None


def _pool_map(path: Path) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    return {
        (row["query_id"], row["facet"], row["aspect_id"], row["object_id"]): row
        for row in _read_jsonl(path)
    }


def _policy_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for policy in row["selected_by_policies"]:
            counts[policy] = counts.get(policy, 0) + 1
    return dict(sorted(counts.items()))


def _counts(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[str(value)] = counts.get(str(value), 0) + 1
    return dict(sorted(counts.items()))


def _key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (row["query_id"], row["facet"], row["aspect_id"], row["object_id"])


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    input_path = Path(path)
    rows = []
    with input_path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                rows.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {input_path}:{line_number}") from exc
    return rows


if __name__ == "__main__":
    main()
