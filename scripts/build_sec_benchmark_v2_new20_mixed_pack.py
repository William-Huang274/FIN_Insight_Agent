from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]


ORIGINAL_NONTRAP_CASE_IDS = [
    "AAPL_PRODUCT_SERVICES_REVENUE_GM_2023_2025_001",
    "AMD_SEGMENT_MIX_2023_2025_001",
    "ADBE_DIGITAL_MEDIA_ARR_REVENUE_GROWTH_2023_2025_001",
    "SNOW_NRR_RPO_GROWTH_2023_2025_001",
    "AMZN_AWS_NUMERIC_2023_2025_001",
    "AMZN_GOOGL_CLOUD_PROFITABILITY_COMPARISON_2023_2025_001",
    "MSFT_CLOUD_AI_MARGIN_PROXY_2023_2025_001",
    "NVDA_DATACENTER_2023_2025_001",
    "CAPEX_FCF_TABLE_2023_2025_DIAG_001",
    "SEMICONDUCTOR_DURABILITY_2023_2025_DIAG_001",
    "SUBSCRIPTION_VISIBILITY_COMPARISON_2023_2025_DIAG_001",
    "AAPL_SERVICES_REGULATORY_RISK_2025_001",
    "AMZN_ADS_SUBSCRIPTION_AWS_MIX_2023_2025_001",
    "NVDA_INVENTORY_SUPPLY_CONSTRAINT_RISK_2023_2025_001",
    "ADBE_REVENUE_DEFERRED_REVENUE_TABLE_2023_2025_001",
    "MSFT_OPERATING_CASH_FLOW_CAPEX_TABLE_2023_2025_001",
]

TRAP_CASE_IDS = [
    "MSFT_YOUTUBE_REVENUE_TRAP_001",
    "MSFT_AZURE_GROSS_MARGIN_NOT_FOUND_2023_2025_001",
    "GOOGL_AWS_OPERATING_INCOME_TRAP_2023_2025_001",
    "NVDA_CUDA_SOFTWARE_REVENUE_NOT_FOUND_2023_2025_001",
]


NEWCO_RUBRIC_CASES: dict[str, dict[str, Any]] = {
    "AVGO_PRODUCT_SUBSCRIPTION_REVENUE_MIX_2023_2025_001": {
        "min_required_coverage_ratio": 1.0,
        "dimensions": [
            {
                "id": "products_and_subscription_services_separated",
                "description": "必须区分 Products 与 Subscriptions and services 收入。",
                "all_of_any": [["Products"], ["Subscriptions and services", "subscriptions"], ["收入", "revenue"]],
            },
            {
                "id": "subscription_services_not_arr_or_pure_saas",
                "description": "必须说明 Subscriptions and services 不能直接等同于 ARR 或纯订阅软件收入。",
                "all_of_any": [
                    ["Subscriptions and services", "subscriptions"],
                    ["ARR", "SaaS", "订阅式软件", "recurring"],
                    ["不", "不能", "not", "不同", "不等同"],
                ],
            },
        ],
        "forbidden_claims": [
            {
                "id": "subscription_services_as_arr",
                "description": "不得把 Broadcom subscriptions and services 直接写成 ARR。",
                "patterns": ["Subscriptions and services equals ARR", "Broadcom ARR", "等同于 ARR"],
                "allow_if_any_near": ["不", "不能", "not", "different", "不同", "未披露"],
            }
        ],
    },
    "CSCO_PRODUCT_SERVICE_RPO_VISIBILITY_2023_2025_001": {
        "min_required_coverage_ratio": 1.0,
        "dimensions": [
            {
                "id": "product_services_rpo_separated",
                "description": "必须区分 Product revenue、Services revenue 和 RPO。",
                "all_of_any": [["Product"], ["Services", "Service"], ["RPO", "remaining performance obligations"]],
            },
            {
                "id": "rpo_not_recognized_revenue",
                "description": "必须说明 RPO 是可见性/履约义务指标，不是已确认收入。",
                "all_of_any": [["RPO", "remaining performance obligations"], ["revenue", "收入"], ["不", "不能", "not", "不同"]],
            },
        ],
        "forbidden_claims": [
            {
                "id": "rpo_equals_revenue",
                "description": "不得把 RPO 等同于收入。",
                "patterns": ["RPO equals revenue", "RPO is revenue", "RPO 等同于收入"],
                "allow_if_any_near": ["不", "不能", "not", "different", "不同"],
            }
        ],
    },
    "INTC_REVENUE_GROSS_PROFIT_FOUNDRY_RISK_2023_2025_001": {
        "min_required_coverage_ratio": 1.0,
        "dimensions": [
            {
                "id": "net_revenue_and_gross_profit_separated",
                "description": "必须区分 consolidated net revenue 和 gross profit。",
                "all_of_any": [["net revenue", "Net revenue", "收入"], ["gross profit", "Gross profit", "毛利"]],
            },
            {
                "id": "gross_profit_not_foundry_profitability",
                "description": "必须说明合并 gross profit 不是 Intel Foundry 独立盈利能力。",
                "all_of_any": [["gross profit", "毛利"], ["Foundry", "foundry", "该业务"], ["不", "不能", "not", "无法"]],
            },
        ],
        "forbidden_claims": [
            {
                "id": "revenue_proves_ai_demand",
                "description": "不得声称收入本身证明 AI 需求耐久。",
                "patterns": ["revenue proves durable AI demand", "收入证明 AI 需求耐久"],
                "allow_if_any_near": ["不", "不能", "not", "无法"],
            }
        ],
    },
    "QCOM_HANDSETS_AUTOMOTIVE_REVENUE_MIX_2023_2025_001": {
        "min_required_coverage_ratio": 1.0,
        "dimensions": [
            {
                "id": "handsets_and_automotive_separated",
                "description": "必须区分 Handsets 和 Automotive 收入。",
                "all_of_any": [["Handsets"], ["Automotive"], ["收入", "revenue"]],
            },
            {
                "id": "business_lines_not_total_company_or_share",
                "description": "必须说明业务线收入不是总公司收入或市场份额证明。",
                "all_of_any": [["Handsets", "Automotive"], ["total", "company", "market share", "市场份额"], ["不", "不能", "not", "区分"]],
            },
        ],
        "forbidden_claims": [
            {
                "id": "market_share_from_revenue",
                "description": "不得从收入直接推断市场份额。",
                "patterns": ["market share", "市场份额"],
                "allow_if_any_near": ["不", "不能", "not", "未披露"],
            }
        ],
    },
    "TXN_ANALOG_EMBEDDED_REVENUE_MIX_2023_2025_001": {
        "min_required_coverage_ratio": 1.0,
        "dimensions": [
            {
                "id": "analog_and_embedded_separated",
                "description": "必须区分 Analog 和 Embedded Processing 收入。",
                "all_of_any": [["Analog"], ["Embedded Processing", "Embedded"], ["收入", "revenue"]],
            },
            {
                "id": "revenue_not_durable_demand_proof",
                "description": "必须说明 segment revenue 不能单独证明 durable demand。",
                "all_of_any": [["revenue", "收入"], ["durable", "耐久", "demand", "需求"], ["不", "不能", "not", "不证明"]],
            },
        ],
        "forbidden_claims": [
            {
                "id": "no_cyclicality_from_revenue",
                "description": "不得声称收入证明没有周期性。",
                "patterns": ["no cyclicality", "周期性不存在"],
                "allow_if_any_near": ["不", "不能", "not"],
            }
        ],
    },
    "AMAT_SEMICONDUCTOR_SYSTEMS_SERVICES_REVENUE_MIX_2023_2025_001": {
        "min_required_coverage_ratio": 1.0,
        "dimensions": [
            {
                "id": "systems_and_services_separated",
                "description": "必须区分 Semiconductor Systems 和 Applied Global Services 收入。",
                "all_of_any": [["Semiconductor Systems"], ["Applied Global Services"], ["收入", "revenue"]],
            },
            {
                "id": "backlog_not_recognized_revenue",
                "description": "必须说明 backlog/orders 不能替代 recognized revenue。",
                "all_of_any": [["backlog", "orders", "订单"], ["revenue", "收入"], ["不", "不能", "not", "不同"]],
            },
        ],
        "forbidden_claims": [
            {
                "id": "backlog_equals_revenue",
                "description": "不得把 backlog 等同于收入。",
                "patterns": ["backlog equals revenue", "backlog is revenue", "订单等同于收入"],
                "allow_if_any_near": ["不", "不能", "not", "different", "不同"],
            }
        ],
    },
    "MU_DRAM_NAND_REVENUE_CYCLE_2023_2025_001": {
        "min_required_coverage_ratio": 1.0,
        "dimensions": [
            {
                "id": "dram_and_nand_separated",
                "description": "必须区分 DRAM 和 NAND 收入。",
                "all_of_any": [["DRAM"], ["NAND"], ["收入", "revenue"]],
            },
            {
                "id": "memory_cycle_caveat",
                "description": "必须说明内存行业周期性限制收入趋势解释。",
                "all_of_any": [["memory", "DRAM", "NAND", "内存"], ["cycle", "cyclical", "周期"], ["风险", "限制", "caveat"]],
            },
        ],
        "forbidden_claims": [
            {
                "id": "ai_demand_proven_by_revenue",
                "description": "不得声称收入证明 AI 需求。",
                "patterns": ["revenue proves AI demand", "收入证明 AI 需求"],
                "allow_if_any_near": ["不", "不能", "not", "无法"],
            }
        ],
    },
    "INTU_SMALL_BUSINESS_CONSUMER_CREDIT_KARMA_MIX_2023_2025_001": {
        "min_required_coverage_ratio": 1.0,
        "dimensions": [
            {
                "id": "three_segments_separated",
                "description": "必须区分 Small Business/Global Business Solutions、Consumer 和 Credit Karma。",
                "all_of_any": [["Small Business", "Global Business Solutions"], ["Consumer"], ["Credit Karma"]],
            },
            {
                "id": "segment_revenue_not_all_arr",
                "description": "必须说明 segment revenue 不能全部视为 ARR 或订阅收入。",
                "all_of_any": [["segment", "Small Business", "Consumer", "Credit Karma"], ["ARR", "subscription", "订阅"], ["不", "不能", "not", "并非"]],
            },
        ],
        "forbidden_claims": [
            {
                "id": "all_segments_are_arr",
                "description": "不得把全部 Intuit segment revenue 写成 ARR。",
                "patterns": ["all Intuit revenue is ARR", "全部是 ARR", "全部是订阅收入"],
                "allow_if_any_near": ["不", "不能", "not", "并非"],
            }
        ],
    },
    "ADP_EMPLOYER_PEO_REVENUE_CLIENT_FUNDS_2023_2025_001": {
        "min_required_coverage_ratio": 1.0,
        "dimensions": [
            {
                "id": "employer_peo_client_funds_separated",
                "description": "必须区分 Employer Services、PEO Services 和 client-funds interest。",
                "all_of_any": [
                    ["Employer Services", "雇主服务"],
                    ["PEO Services", "PEO 服务", "专业雇主组织"],
                    ["client funds", "funds held for clients", "客户资金"],
                ],
            },
            {
                "id": "client_funds_interest_not_core_service_revenue",
                "description": "必须说明 client-funds interest 应与核心服务收入分开。",
                "all_of_any": [["interest", "利息"], ["client funds", "funds held for clients", "客户资金"], ["separate", "区分", "不", "not"]],
            },
        ],
        "forbidden_claims": [
            {
                "id": "client_interest_as_subscription",
                "description": "不得把客户资金利息写成订阅收入。",
                "patterns": ["client funds interest is subscription revenue", "客户资金利息是订阅收入"],
                "allow_if_any_near": ["不", "不能", "not", "不同"],
            }
        ],
    },
    "CRWD_ARR_SUBSCRIPTION_GROSS_PROFIT_2023_2025_001": {
        "min_required_coverage_ratio": 1.0,
        "dimensions": [
            {
                "id": "arr_and_subscription_gross_profit_separated",
                "description": "必须区分 ARR 和 subscription gross profit。",
                "all_of_any": [["ARR", "Annual recurring revenue"], ["subscription gross profit", "Subscription gross profit", "毛利"]],
            },
            {
                "id": "arr_not_revenue_or_profit",
                "description": "必须说明 ARR 不是 recognized revenue 或 gross profit。",
                "all_of_any": [["ARR", "Annual recurring revenue"], ["revenue", "gross profit", "收入", "毛利"], ["不", "不能", "not", "不同"]],
            },
        ],
        "forbidden_claims": [
            {
                "id": "arr_equals_revenue",
                "description": "不得把 ARR 等同于 recognized revenue。",
                "patterns": ["ARR is revenue", "ARR equals revenue", "ARR 等同于收入"],
                "allow_if_any_near": ["不", "不能", "not", "不同"],
            }
        ],
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the v2 new20 mixed SEC benchmark pack.")
    parser.add_argument("--full40-cases-path", default="eval/sec_cases/test_cases_v2_full40_seed.jsonl")
    parser.add_argument("--newco-cases-path", default="eval/sec_cases/test_cases_v2_new20_newco_seed.jsonl")
    parser.add_argument("--output-cases-path", default="eval/sec_cases/test_cases_v2_new20_mixed_seed.jsonl")
    parser.add_argument("--approval-path", default="reports/quality/sec_benchmark_v2_new20_mixed_review_approval.json")
    parser.add_argument("--rubric-path", default="eval/sec_cases/abstract_judgment_rubric_v0_1.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    full40 = _index_by_case_id(_read_jsonl(REPO_ROOT / args.full40_cases_path))
    newco = _index_by_case_id(_read_jsonl(REPO_ROOT / args.newco_cases_path))

    mixed_cases: list[dict[str, Any]] = []
    for case_id in ORIGINAL_NONTRAP_CASE_IDS:
        mixed_cases.append(_mixed_case(full40[case_id], "original_company_regression"))
    for case_id, case in newco.items():
        mixed_cases.append(_mixed_case(case, "new_company_reviewed_slice"))
    for case_id in TRAP_CASE_IDS:
        mixed_cases.append(_mixed_case(full40[case_id], "trap_regression"))

    approved_case_ids = ORIGINAL_NONTRAP_CASE_IDS + list(newco.keys())
    approval = _approval_payload(
        mixed_cases=mixed_cases,
        approved_case_ids=approved_case_ids,
        trap_case_ids=TRAP_CASE_IDS,
        output_cases_path=args.output_cases_path,
    )

    output_cases_path = REPO_ROOT / args.output_cases_path
    output_cases_path.parent.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output_cases_path, mixed_cases)

    approval_path = REPO_ROOT / args.approval_path
    approval_path.parent.mkdir(parents=True, exist_ok=True)
    approval_path.write_text(json.dumps(approval, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    rubric_path = REPO_ROOT / args.rubric_path
    rubric = _read_json(rubric_path)
    rubric.setdefault("cases", {}).update(NEWCO_RUBRIC_CASES)
    rubric_path.write_text(json.dumps(rubric, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "output_cases_path": str(output_cases_path),
                "approval_path": str(approval_path),
                "rubric_path": str(rubric_path),
                "case_count": len(mixed_cases),
                "approved_case_count": len(approved_case_ids),
                "trap_case_count": len(TRAP_CASE_IDS),
                "newco_rubric_case_count": len(NEWCO_RUBRIC_CASES),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _mixed_case(case: dict[str, Any], role: str) -> dict[str, Any]:
    copy = dict(case)
    copy["origin"] = "v2_new20_mixed_from_full40_and_newco"
    copy["case_family"] = "v2_new20_mixed"
    copy["mixed_pack_role"] = role
    if role == "new_company_reviewed_slice":
        copy["reviewed_asset_status"] = "reviewed_gold_available"
        copy["gold_context_status"] = "needs_annotation"
    return copy


def _approval_payload(
    *,
    mixed_cases: list[dict[str, Any]],
    approved_case_ids: list[str],
    trap_case_ids: list[str],
    output_cases_path: str,
) -> dict[str, Any]:
    now = datetime.now().isoformat(timespec="seconds")
    return {
        "schema_version": "sec_gold_manual_review_v0.2",
        "created_at": now,
        "review_scope": {
            "gold_context_dir": "eval/sec_cases/reviewed_gold_context",
            "gold_facts_dir": "eval/sec_cases/reviewed_gold_facts",
            "mixed_manifest": output_cases_path,
            "case_count": len(mixed_cases),
            "approved_reviewed_case_ids": approved_case_ids,
            "pipeline_only_trap_case_ids": trap_case_ids,
            "seed_needs_review_case_ids": [],
        },
        "gate": {
            "status": "approved_for_case_filtered_mixed_benchmark",
            "approved_case_ids": approved_case_ids,
            "trap_case_ids": trap_case_ids,
        },
        "review_decision": {
            "overall_status": "approved_for_mainline_scored_benchmark",
            "allowed_next_step": "new20_mixed_gold_gate_then_ledger_and_cloud_pipeline",
            "blocked_next_step": "broader_generalization_claim_until_more_companies_and_cases_are_reviewed",
            "reason": (
                "The mixed pack combines 16 original-company reviewed regression cases, "
                "10 reviewed new-company cases, and 4 approved pipeline traps. It is intended "
                "to verify that the 20-company corpus does not regress the prior route while "
                "adding new-company coverage."
            ),
        },
        "case_reviews": [
            _case_review(case_id, "approved_for_gold_context_mode")
            for case_id in approved_case_ids
        ]
        + [
            _case_review(case_id, "approved_for_pipeline_trap_smoke")
            for case_id in trap_case_ids
        ],
    }


def _case_review(case_id: str, decision: str) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "decision": decision,
        "mainline_status": "can_enter_new20_mixed_scored_pipeline",
        "evidence_assessment": "Reviewed artifact already exists and is reused under the mixed 20-company benchmark route.",
        "fact_assessment": "Reviewed facts are expected to be validated by the mainline gold gate and ledger-unit gate.",
        "required_fix": "No pre-inference fix required for this mixed-pack build step.",
    }


def _index_by_case_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("case_id") or ""): row for row in rows}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


if __name__ == "__main__":
    main()
