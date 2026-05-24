from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from scripts import build_sec_benchmark_v2_pilot_plus7_reviewed_gold as plus7  # noqa: E402


SOURCE_MANIFEST = REPO_ROOT / "eval" / "sec_cases" / "test_cases_v1.jsonl"
BASE_MANIFEST = REPO_ROOT / "eval" / "sec_cases" / "test_cases_v2_pilot_plus7_seed.jsonl"
PLUS8_MANIFEST = REPO_ROOT / "eval" / "sec_cases" / "test_cases_v2_pilot_plus8_seed.jsonl"

NVDA_CASE = "NVDA_DATACENTER_2023_2025_001"
SNOW_CASE = "SNOW_RISK_2023_2025_001"
TEXT_HEAVY_CASE_IDS = [NVDA_CASE, SNOW_CASE]

BASE_REVIEWED_CASE_IDS = list(plus7.PLUS7_REVIEWED_CASE_IDS)
PLUS8_REVIEWED_CASE_IDS = [*BASE_REVIEWED_CASE_IDS, *TEXT_HEAVY_CASE_IDS]
PLUS8_TRAP_CASE_IDS = list(plus7.PLUS7_TRAP_CASE_IDS)


def main() -> None:
    reviewed_context_dir = REPO_ROOT / "eval" / "sec_cases" / "reviewed_gold_context"
    reviewed_facts_dir = REPO_ROOT / "eval" / "sec_cases" / "reviewed_gold_facts"
    report_dir = REPO_ROOT / "reports" / "quality"
    report_dir.mkdir(parents=True, exist_ok=True)

    if not BASE_MANIFEST.exists():
        raise SystemExit(f"Missing base plus7 manifest: {BASE_MANIFEST}")

    _assert_reviewed_artifacts_exist(reviewed_context_dir, reviewed_facts_dir)
    _write_manifest()
    case_summaries = [_text_case_summary(case_id, reviewed_context_dir, reviewed_facts_dir) for case_id in TEXT_HEAVY_CASE_IDS]

    approval_path = report_dir / "sec_benchmark_v2_pilot_plus8_reviewed_gold_partial_approval.json"
    approval_path.write_text(json.dumps(_approval_payload(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    build_report_path = report_dir / "sec_benchmark_v2_pilot_plus8_reviewed_gold_build_report.json"
    build_report = {
        "schema_version": "sec_v2_pilot_plus8_reviewed_gold_build_report_v0.1",
        "base_manifest": str(BASE_MANIFEST),
        "plus8_manifest": str(PLUS8_MANIFEST),
        "base_reviewed_case_count": len(BASE_REVIEWED_CASE_IDS),
        "plus8_reviewed_case_count": len(PLUS8_REVIEWED_CASE_IDS),
        "trap_case_ids": PLUS8_TRAP_CASE_IDS,
        "approval_path": str(approval_path),
        "new_cases": case_summaries,
        "bge_m3_policy": {
            "final_context_selector": "BAAI/bge-reranker-v2-m3",
            "bm25_role": "candidate_generator_only",
            "bm25_only_allowed": False,
        },
    }
    build_report_path.write_text(json.dumps(build_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "plus8_manifest": str(PLUS8_MANIFEST),
                "plus8_reviewed_case_count": len(PLUS8_REVIEWED_CASE_IDS),
                "plus8_trap_case_count": len(PLUS8_TRAP_CASE_IDS),
                "new_cases": case_summaries,
                "approval_path": str(approval_path),
                "build_report_path": str(build_report_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _assert_reviewed_artifacts_exist(reviewed_context_dir: Path, reviewed_facts_dir: Path) -> None:
    missing = []
    for case_id in TEXT_HEAVY_CASE_IDS:
        missing.extend(
            path
            for path in [
                reviewed_context_dir / f"{case_id}.jsonl",
                reviewed_facts_dir / f"{case_id}.json",
            ]
            if not path.exists()
        )
    if missing:
        raise SystemExit("Missing reviewed text-heavy artifacts: " + ", ".join(str(path) for path in missing))


def _write_manifest() -> None:
    rows = _read_jsonl(BASE_MANIFEST)
    replacements = {NVDA_CASE: _nvda_manifest_case(), SNOW_CASE: _snow_manifest_case()}
    seen: set[str] = set()
    output_rows: list[dict[str, Any]] = []
    for row in rows:
        case_id = str(row.get("case_id") or "")
        if case_id in replacements:
            output_rows.append(replacements[case_id])
            seen.add(case_id)
        else:
            output_rows.append(row)
    for case_id in TEXT_HEAVY_CASE_IDS:
        if case_id not in seen:
            output_rows.append(replacements[case_id])
    _write_jsonl(PLUS8_MANIFEST, output_rows)


def _nvda_manifest_case() -> dict[str, Any]:
    case = dict(_source_case(NVDA_CASE))
    case.update(
        {
            "origin": "v2_pilot_plus8_reviewed_text_expansion",
            "case_family": "v2_pilot_plus8",
            "test_objective": (
                "Promote the reviewed NVIDIA text-heavy data-center driver case into v2 to test SEC-only "
                "year-specific qualitative support, risk calibration, named-fact support, and no-ledger numeric restraint."
            ),
            "required_caveats": [
                {
                    "id": "nvda_no_product_level_revenue_quantification",
                    "description": "Must state product-level or architecture-level revenue is not quantified by the approved text context.",
                    "where": "caveats",
                    "all_of_any": [
                        ["产品级", "product-level", "architecture-level", "GPU", "Hopper", "Blackwell"],
                        ["未披露", "无法量化", "未提供精确数值", "no exact", "not disclosed"],
                    ],
                },
                {
                    "id": "nvda_risk_calibration",
                    "description": "Must mention a supported risk such as export controls, supply chain, demand forecast, product transition, inventory, or customer concentration.",
                    "where": "answer",
                    "all_of_any": [
                        ["出口管制", "export control", "供应链", "supply chain", "客户集中", "customer concentration", "需求预测", "demand forecast", "库存", "inventory", "产品过渡", "product transition"],
                        ["风险", "uncertainty", "不确定", "pressure", "限制", "影响"],
                    ],
                },
                {
                    "id": "nvda_year_specific_disclosure",
                    "description": "Must distinguish 2023, 2024, and 2025 rather than collapsing the three years into one narrative.",
                    "where": "answer",
                    "all_of_any": [["2023"], ["2024"], ["2025"]],
                },
            ],
            "disallowed_claims": [
                {
                    "id": "nvda_external_market_or_stock_claim",
                    "description": "Do not use stock price, market sentiment, or news as SEC-only evidence.",
                    "patterns": ["股价上涨", "股价下跌", "market sentiment", "news reports", "新闻报道"],
                    "allow_if_any_near": ["不使用", "不能使用", "not used", "SEC-only", "非 SEC"],
                },
                {
                    "id": "nvda_invented_product_revenue",
                    "description": "Do not invent exact GPU, Hopper, Blackwell, or AI product revenue.",
                    "patterns": [
                        "re:(GPU|Hopper|Blackwell|AI 产品|AI product).{0,30}(收入|revenue).{0,20}(\\$|\\d)",
                    ],
                    "allow_if_any_near": ["未披露", "无法量化", "not disclosed", "not quantified", "not found"],
                },
                {
                    "id": "nvda_market_share_claim",
                    "description": "Do not infer market share from the SEC text context.",
                    "patterns": ["market share", "市场份额"],
                    "allow_if_any_near": ["未披露", "does not prove", "不证明", "不能"],
                },
            ],
            "hard_gates": _dedupe(
                [
                    *[str(item) for item in case.get("hard_gates") or []],
                    "named_fact_support_gate",
                    "abstract_judgment_gate",
                    "unsupported_claim_gate",
                ]
            ),
            "hallucination_traps": _dedupe(
                [
                    *[str(item) for item in case.get("hallucination_traps") or []],
                    "Do not invent exact GPU, Hopper, Blackwell, or AI product revenue.",
                    "Do not use stock price, news, or market-share claims as SEC evidence.",
                    "Do not collapse 2023-2025 into a single undated narrative.",
                ]
            ),
            "failure_types": _dedupe(
                [
                    *[str(item) for item in case.get("failure_types") or []],
                    "source_policy_violation",
                    "missing_caveat",
                ]
            ),
        }
    )
    return case


def _snow_manifest_case() -> dict[str, Any]:
    case = dict(_source_case(SNOW_CASE))
    case.update(
        {
            "origin": "v2_pilot_plus8_reviewed_text_expansion",
            "case_family": "v2_pilot_plus8",
            "test_objective": (
                "Promote the reviewed Snowflake text-heavy consumption-risk case into v2 to test consumption-model "
                "risk language, repeated-disclosure calibration, and no-ledger not-found discipline."
            ),
            "required_caveats": [
                {
                    "id": "snow_consumption_model_not_subscription_model",
                    "description": "Must state Snowflake recognizes product revenue based on platform consumption rather than ordinary ratable subscription timing.",
                    "where": "answer",
                    "all_of_any": [
                        ["Snowflake", "SNOW"],
                        ["消耗量", "消费模式", "consumption-based", "consumption based"],
                        ["not ratably", "not subscription", "不是普通订阅", "不同于订阅"],
                    ],
                },
                {
                    "id": "snow_usage_timing_or_forecast_risk",
                    "description": "Must mention customer consumption timing, usage variability, or forecast uncertainty.",
                    "where": "answer",
                    "all_of_any": [
                        ["客户", "customer", "用量", "consumption", "usage"],
                        ["时点", "timing", "波动", "variability", "预测", "forecast"],
                    ],
                },
                {
                    "id": "snow_repeated_risk_language_or_year_change",
                    "description": "Must distinguish the three years or explicitly say the risk language is largely repeated.",
                    "where": "answer",
                    "all_of_any": [
                        ["2023", "2024", "2025", "三年"],
                        ["重复", "一致", "未发生实质性变化", "repeated", "largely similar"],
                    ],
                },
                {
                    "id": "snow_no_customer_count_or_retention_quantification",
                    "description": "Must say customer count, NRR, or retention trend is not quantified in this text-only risk case if discussed.",
                    "where": "caveats",
                    "all_of_any": [
                        ["客户数", "客户数量", "NRR", "净收入留存率", "retention"],
                        ["未披露", "无法量化", "未提供精确数值", "not disclosed", "not quantified"],
                    ],
                },
            ],
            "disallowed_claims": [
                {
                    "id": "snow_invented_customer_or_retention_number",
                    "description": "Do not invent customer counts, NRR, or retention-rate values.",
                    "patterns": ["re:(客户数|客户数量|NRR|净收入留存率|retention rate).{0,20}\\d"],
                    "allow_if_any_near": ["未披露", "无法量化", "未提供", "not found", "not disclosed"],
                },
                {
                    "id": "snow_non_sec_market_commentary",
                    "description": "Do not use non-SEC market commentary or analyst target-price claims.",
                    "patterns": ["target price", "目标价", "market sentiment", "市场情绪", "新闻报道"],
                    "allow_if_any_near": ["不使用", "不能使用", "SEC-only", "非 SEC"],
                },
                {
                    "id": "snow_subscription_model_misclassification",
                    "description": "Do not describe Snowflake's product revenue as ordinary ratable subscription revenue.",
                    "patterns": ["ordinary subscription revenue", "ratably over the contract term", "普通订阅收入", "按合同期直线确认"],
                    "allow_if_any_near": ["not", "not ratably", "不是", "不同于", "并非"],
                },
            ],
            "hard_gates": _dedupe(
                [
                    *[str(item) for item in case.get("hard_gates") or []],
                    "abstract_judgment_gate",
                    "unsupported_claim_gate",
                ]
            ),
            "hallucination_traps": _dedupe(
                [
                    *[str(item) for item in case.get("hallucination_traps") or []],
                    "Do not invent customer counts, NRR, or retention-rate values.",
                    "Do not treat Snowflake's consumption model as ordinary ratable subscription revenue.",
                    "Do not use non-SEC market commentary.",
                ]
            ),
            "failure_types": _dedupe(
                [
                    *[str(item) for item in case.get("failure_types") or []],
                    "source_policy_violation",
                    "missing_caveat",
                ]
            ),
        }
    )
    return case


def _source_case(case_id: str) -> dict[str, Any]:
    for row in _read_jsonl(SOURCE_MANIFEST):
        if str(row.get("case_id") or "") == case_id:
            return row
    raise SystemExit(f"Missing source case in {SOURCE_MANIFEST}: {case_id}")


def _text_case_summary(case_id: str, reviewed_context_dir: Path, reviewed_facts_dir: Path) -> dict[str, Any]:
    facts_path = reviewed_facts_dir / f"{case_id}.json"
    context_path = reviewed_context_dir / f"{case_id}.jsonl"
    facts_payload = _read_json(facts_path)
    context_rows = _read_jsonl(context_path)
    return {
        "case_id": case_id,
        "fact_count": len([fact for fact in facts_payload.get("facts") or [] if str(fact.get("review_status") or "") == "reviewed_keep"]),
        "context_row_count": len(context_rows),
        "context_path": str(context_path),
        "facts_path": str(facts_path),
        "reuse_policy": "reuse_existing_reviewed_v1_text_gold_context_with_v2_manifest_contract",
        "numeric_fact_policy": facts_payload.get("review_scope", {}).get("numeric_fact_policy"),
        "context_years": sorted({int(row.get("fiscal_year")) for row in context_rows if _is_int_like(row.get("fiscal_year"))}),
        "context_sections": sorted({str(row.get("section") or "") for row in context_rows if row.get("section")}),
    }


def _approval_payload() -> dict[str, Any]:
    return {
        "schema_version": "sec_gold_manual_review_v0.2",
        "review_scope": {
            "gold_context_dir": "eval/sec_cases/reviewed_gold_context",
            "gold_facts_dir": "eval/sec_cases/reviewed_gold_facts",
            "case_count": len(PLUS8_REVIEWED_CASE_IDS),
            "reviewed_case_ids": PLUS8_REVIEWED_CASE_IDS,
            "pipeline_only_trap_case_ids": PLUS8_TRAP_CASE_IDS,
        },
        "review_decision": {
            "overall_status": "partial_approved_for_mainline_scored_benchmark",
            "allowed_next_step": "case_filtered_gold_context_and_pipeline_plus8_smoke",
            "blocked_next_step": "full_benchmark_mainline_scored_test",
            "reason": (
                "The plus7 reviewed and trap cases remain approved. Plus8 adds two reviewed text-heavy "
                "cases with no exact-value target facts: NVIDIA data-center qualitative drivers and Snowflake "
                "consumption-model risk."
            ),
        },
        "case_reviews": [
            *_base_case_reviews(),
            {
                "case_id": NVDA_CASE,
                "decision": "approved_for_gold_context_mode",
                "mainline_status": "can_enter_case_filtered_scored_gold_context_smoke",
                "evidence_assessment": (
                    "Reviewed context contains 12 NVIDIA SEC text rows covering 2023-2025 data-center driver "
                    "language, AI/accelerated-computing demand, export-control and supply/customer-concentration "
                    "risk language."
                ),
                "fact_assessment": (
                    "No target numeric facts are approved for this text-summary case; exact product-level or "
                    "architecture-level revenue claims remain unsupported unless separately reviewed into a ledger."
                ),
                "required_fix": (
                    "Pipeline output must separate 2023, 2024, and 2025, cite text support, and keep precise "
                    "product/market-share/stock claims out of the answer."
                ),
            },
            {
                "case_id": SNOW_CASE,
                "decision": "approved_for_gold_context_mode",
                "mainline_status": "can_enter_case_filtered_scored_gold_context_smoke",
                "evidence_assessment": (
                    "Reviewed context contains 9 Snowflake SEC text rows covering 2023-2025 consumption-based "
                    "revenue mechanics, usage timing risk, efficiency-related consumption risk, and analyst or "
                    "market-interpretation risk."
                ),
                "fact_assessment": (
                    "No target numeric facts are approved for this text-summary case; customer counts, NRR, and "
                    "retention-rate values must be treated as not found unless supported by another reviewed case."
                ),
                "required_fix": (
                    "Pipeline output must identify the consumption model, calibrate repeated risk language, and "
                    "avoid inventing customer, retention, or non-SEC market commentary."
                ),
            },
        ],
        "gate": {
            "can_enter_full_mainline_scored_test": False,
            "can_enter_case_filtered_gold_context_scored_smoke": True,
            "approved_case_ids": PLUS8_REVIEWED_CASE_IDS,
            "pipeline_only_trap_case_ids": PLUS8_TRAP_CASE_IDS,
        },
    }


def _base_case_reviews() -> list[dict[str, Any]]:
    approval_path = REPO_ROOT / "reports" / "quality" / "sec_benchmark_v2_pilot_plus7_reviewed_gold_partial_approval.json"
    approval = _read_json(approval_path)
    keep = set(BASE_REVIEWED_CASE_IDS + PLUS8_TRAP_CASE_IDS)
    return [row for row in approval.get("case_reviews") or [] if str(row.get("case_id") or "") in keep]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            output.append(item)
    return output


def _is_int_like(value: Any) -> bool:
    try:
        int(value)
    except (TypeError, ValueError):
        return False
    return True


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
