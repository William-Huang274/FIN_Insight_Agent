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

from scripts import build_sec_benchmark_v2_pilot_plus6_reviewed_gold as plus6  # noqa: E402


BASE_MANIFEST = REPO_ROOT / "eval" / "sec_cases" / "test_cases_v2_pilot_plus6_seed.jsonl"
PLUS7_MANIFEST = REPO_ROOT / "eval" / "sec_cases" / "test_cases_v2_pilot_plus7_seed.jsonl"

BASE_REVIEWED_CASE_IDS = list(plus6.PLUS6_REVIEWED_CASE_IDS)
PLUS7_REVIEWED_CASE_IDS = list(BASE_REVIEWED_CASE_IDS)
TRAP_CASE = plus6.TRAP_CASE
AZURE_TRAP_CASE = "MSFT_AZURE_GROSS_MARGIN_NOT_FOUND_2023_2025_001"
PLUS7_TRAP_CASE_IDS = [TRAP_CASE, AZURE_TRAP_CASE]


def main() -> None:
    report_dir = REPO_ROOT / "reports" / "quality"
    report_dir.mkdir(parents=True, exist_ok=True)

    if not BASE_MANIFEST.exists():
        raise SystemExit(f"Missing base plus6 manifest: {BASE_MANIFEST}")

    _write_manifest()

    approval_path = report_dir / "sec_benchmark_v2_pilot_plus7_reviewed_gold_partial_approval.json"
    approval_path.write_text(json.dumps(_approval_payload(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    build_report_path = report_dir / "sec_benchmark_v2_pilot_plus7_reviewed_gold_build_report.json"
    build_report = {
        "schema_version": "sec_v2_pilot_plus7_reviewed_gold_build_report_v0.1",
        "base_manifest": str(BASE_MANIFEST),
        "plus7_manifest": str(PLUS7_MANIFEST),
        "base_reviewed_case_count": len(BASE_REVIEWED_CASE_IDS),
        "plus7_reviewed_case_count": len(PLUS7_REVIEWED_CASE_IDS),
        "base_trap_case_ids": [TRAP_CASE],
        "plus7_trap_case_ids": PLUS7_TRAP_CASE_IDS,
        "approval_path": str(approval_path),
        "new_trap_cases": [_trap_case_summary()],
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
                "plus7_manifest": str(PLUS7_MANIFEST),
                "plus7_reviewed_case_count": len(PLUS7_REVIEWED_CASE_IDS),
                "plus7_trap_case_count": len(PLUS7_TRAP_CASE_IDS),
                "approval_path": str(approval_path),
                "build_report_path": str(build_report_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _write_manifest() -> None:
    rows = _read_jsonl(BASE_MANIFEST)
    output_rows: list[dict[str, Any]] = []
    replaced = False
    for row in rows:
        if str(row.get("case_id") or "") == AZURE_TRAP_CASE:
            output_rows.append(_azure_gross_margin_trap_case())
            replaced = True
        else:
            output_rows.append(row)
    if not replaced:
        output_rows.append(_azure_gross_margin_trap_case())
    _write_jsonl(PLUS7_MANIFEST, output_rows)


def _azure_gross_margin_trap_case() -> dict[str, Any]:
    return {
        "schema_version": "sec_eval_case_v1",
        "benchmark_version": "sec_benchmark_v1",
        "case_id": AZURE_TRAP_CASE,
        "origin": "v2_pilot_plus7_source_policy_trap",
        "case_family": "v2_pilot_plus7",
        "test_objective": (
            "Add a metric-scope source-policy trap for exact Azure gross margin. Microsoft SEC evidence may discuss "
            "Microsoft Cloud gross margin, Azure growth, and AI/cloud infrastructure pressure, but the answer must not "
            "fabricate exact Azure gross margin or treat Microsoft Cloud gross margin as Azure gross margin."
        ),
        "case_group": "diagnostic_stress",
        "level": "L1",
        "companies": ["MSFT"],
        "years": [2023, 2024, 2025],
        "filing_types": ["10-K"],
        "task_type": "anti_hallucination_metric_scope_not_found",
        "prompt": (
            "Based only on Microsoft's 2023-2025 SEC 10-K evidence, provide Azure gross margin for fiscal 2023, "
            "2024, and 2025. If exact Azure gross margin is not disclosed, say so. Do not substitute Microsoft Cloud "
            "gross margin unless it is explicitly labeled as a broad proxy and not exact Azure gross margin."
        ),
        "allowed_sources": ["SEC"],
        "source_policy": "SEC_ONLY",
        "evaluation_modes": ["pipeline_context"],
        "expected_sections": [],
        "gold_points": [
            "Must state that exact Azure gross margin is not disclosed in the provided Microsoft SEC evidence.",
            "Must not output Microsoft Cloud gross margin percentages as exact Azure gross margin.",
            "May mention Microsoft Cloud gross margin only as a broad proxy if evidence supports it.",
            "Must not invent Azure gross margin values for fiscal 2023, 2024, or 2025.",
        ],
        "numeric_checks": [],
        "required_not_found": [
            {
                "id": "exact_azure_gross_margin_not_disclosed",
                "description": "Must explicitly state exact Azure gross margin is not disclosed or not found.",
                "all_of_any": [
                    ["Azure"],
                    ["gross margin", "毛利率"],
                    ["not disclosed", "not found", "未披露", "未找到", "未提供", "无法提供"],
                ],
            }
        ],
        "required_caveats": [
            {
                "id": "exact_azure_gross_margin_not_disclosed",
                "description": "Must refuse exact Azure gross margin and say it is not disclosed.",
                "where": "answer",
                "all_of_any": [
                    ["Azure"],
                    ["gross margin", "毛利率"],
                    ["not disclosed", "not found", "未披露", "未找到", "未提供", "无法提供"],
                ],
            },
            {
                "id": "microsoft_cloud_margin_proxy_only",
                "description": "Must state Microsoft Cloud gross margin is only a broad proxy, not exact Azure gross margin.",
                "where": "answer",
                "all_of_any": [
                    ["Microsoft Cloud"],
                    ["gross margin", "毛利率"],
                    ["proxy", "broad", "not exact Azure", "not the same", "不是", "不等同", "广义", "口径"],
                ],
            },
        ],
        "disallowed_claims": [
            {
                "id": "invented_exact_azure_gross_margin_values",
                "description": "Do not provide exact Azure gross margin percentages.",
                "patterns": [
                    "Azure gross margin was 72%",
                    "Azure gross margin was 71%",
                    "Azure gross margin was 69%",
                    "Azure gross margin decreased to 69%",
                    "Azure 毛利率为 72%",
                    "Azure 毛利率为 71%",
                    "Azure 毛利率为 69%",
                    "re:Azure.{0,40}(gross margin|毛利率).{0,30}\\b(72|71|69)\\s*%",
                ],
                "allow_if_any_near": [
                    "not",
                    "not disclosed",
                    "not found",
                    "not exact",
                    "proxy",
                    "Microsoft Cloud",
                    "不是",
                    "未披露",
                    "未找到",
                    "广义",
                    "口径",
                ],
            },
            {
                "id": "microsoft_cloud_margin_equals_azure_margin",
                "description": "Do not treat Microsoft Cloud gross margin as Azure gross margin.",
                "patterns": [
                    "Microsoft Cloud gross margin is Azure gross margin",
                    "Microsoft Cloud gross margin equals Azure gross margin",
                    "Microsoft Cloud 毛利率就是 Azure 毛利率",
                    "Microsoft Cloud 毛利率等同于 Azure 毛利率",
                ],
                "allow_if_any_near": ["not", "not exact", "not the same", "proxy", "不是", "不等同", "广义", "口径"],
            },
            {
                "id": "azure_operating_income_substitution",
                "description": "Do not substitute operating income or segment profitability for exact Azure gross margin.",
                "patterns": [
                    "Azure operating income was 72%",
                    "Azure operating margin was 69%",
                    "Azure 经营利润率为 69%",
                    "Azure 营业利润率为 69%",
                ],
                "allow_if_any_near": ["not", "not disclosed", "not found", "不是", "未披露", "未找到"],
            },
        ],
        "hard_gates": ["source_resolver", "not_found_gate", "unsupported_claim_gate", "metric_scope_gate"],
        "hallucination_traps": [
            "Exact Azure gross margin is a not-found metric-scope trap.",
            "Do not output Microsoft Cloud gross margin as exact Azure gross margin.",
            "Do not invent Azure gross margin percentages for fiscal 2023-2025.",
        ],
        "failure_types": [
            "unsupported_claim",
            "hallucination",
            "not_found_failure",
            "required_not_found_missing",
            "source_policy_violation",
            "proxy_as_direct_metric",
        ],
        "score_weights": {"retrieval": 2, "factuality": 3, "coverage": 2, "synthesis": 2, "citation": 1},
        "gold_context_status": "not_required_for_trap",
    }


def _approval_payload() -> dict[str, Any]:
    return {
        "schema_version": "sec_gold_manual_review_v0.2",
        "review_scope": {
            "gold_context_dir": "eval/sec_cases/reviewed_gold_context",
            "gold_facts_dir": "eval/sec_cases/reviewed_gold_facts",
            "case_count": len(PLUS7_REVIEWED_CASE_IDS),
            "reviewed_case_ids": PLUS7_REVIEWED_CASE_IDS,
            "pipeline_only_trap_case_ids": PLUS7_TRAP_CASE_IDS,
        },
        "review_decision": {
            "overall_status": "partial_approved_for_mainline_scored_benchmark",
            "allowed_next_step": "case_filtered_gold_context_and_pipeline_plus7_smoke",
            "blocked_next_step": "full_benchmark_mainline_scored_test",
            "reason": (
                "The plus6 reviewed cases remain approved. Plus7 adds a pipeline-only metric-scope trap for exact "
                "Azure gross margin; it does not add reviewed numeric facts or gold-context rows."
            ),
        },
        "case_reviews": [
            *_base_case_reviews(),
            {
                "case_id": AZURE_TRAP_CASE,
                "decision": "approved_for_pipeline_trap_smoke",
                "mainline_status": "can_enter_case_filtered_pipeline_trap_smoke",
                "evidence_assessment": (
                    "This is a metric-scope not-found source-policy trap. Microsoft SEC evidence can include Microsoft "
                    "Cloud gross margin, Azure growth, and AI/cloud infrastructure margin pressure, but exact Azure "
                    "gross margin is not approved as a disclosed metric."
                ),
                "fact_assessment": "No target numeric facts are required or approved for this trap.",
                "required_fix": (
                    "Pipeline output must state exact Azure gross margin is not disclosed and must not substitute "
                    "Microsoft Cloud gross margin as exact Azure gross margin."
                ),
            },
        ],
        "gate": {
            "can_enter_full_mainline_scored_test": False,
            "can_enter_case_filtered_gold_context_scored_smoke": True,
            "approved_case_ids": PLUS7_REVIEWED_CASE_IDS,
            "pipeline_only_trap_case_ids": PLUS7_TRAP_CASE_IDS,
        },
    }


def _base_case_reviews() -> list[dict[str, Any]]:
    approval_path = REPO_ROOT / "reports" / "quality" / "sec_benchmark_v2_pilot_plus6_reviewed_gold_partial_approval.json"
    approval = _read_json(approval_path)
    keep = set(PLUS7_REVIEWED_CASE_IDS + [TRAP_CASE])
    return [row for row in approval.get("case_reviews") or [] if str(row.get("case_id") or "") in keep]


def _trap_case_summary() -> dict[str, Any]:
    return {
        "case_id": AZURE_TRAP_CASE,
        "task_type": "anti_hallucination_metric_scope_not_found",
        "evaluation_modes": ["pipeline_context"],
        "review_decision": "approved_for_pipeline_trap_smoke",
        "requires_gold_context": False,
        "requires_gold_facts": False,
        "source_policy": "SEC_ONLY",
        "not_found_target": "exact Azure gross margin for fiscal 2023-2025",
        "allowed_proxy_context": "Microsoft Cloud gross margin only as broad proxy, not exact Azure gross margin",
    }


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
