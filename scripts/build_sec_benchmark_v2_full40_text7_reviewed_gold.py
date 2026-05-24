from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


CANDIDATE_CONTEXT_DIR = REPO_ROOT / "eval" / "sec_cases" / "full40_review_candidates_context"
REVIEWED_CONTEXT_DIR = REPO_ROOT / "eval" / "sec_cases" / "reviewed_gold_context"
REVIEWED_FACTS_DIR = REPO_ROOT / "eval" / "sec_cases" / "reviewed_gold_facts"
QUALITY_DIR = REPO_ROOT / "reports" / "quality"

TEXT7_CASE_IDS = [
    "AAPL_SERVICES_REGULATORY_RISK_2025_001",
    "ADBE_DIGITAL_MEDIA_AI_STRATEGY_2025_001",
    "AMZN_AWS_AI_CAPEX_CONTEXT_2025_001",
    "GOOGL_SEARCH_YOUTUBE_CLOUD_ROLE_2025_001",
    "MSFT_AI_CAPEX_CLOUD_RISK_2025_001",
    "PANW_PLATFORMIZATION_CONTEXT_2025_001",
    "NVDA_INVENTORY_SUPPLY_CONSTRAINT_RISK_2023_2025_001",
]

SELECTED_EVIDENCE_IDS = {
    "AAPL_SERVICES_REGULATORY_RISK_2025_001": [
        "AAPL_2025_10K_ITEM1A_BLOCK_0004_CHUNK_0001",
        "AAPL_2025_10K_ITEM1_BLOCK_0005_PART_01_OF_02",
        "AAPL_2025_10K_ITEM1A_BLOCK_0007_CHUNK_0001",
        "AAPL_2025_10K_ITEM1A_BLOCK_0011_PART_01_OF_02",
        "AAPL_2025_10K_ITEM8_BLOCK_0013_CHUNK_0001",
    ],
    "ADBE_DIGITAL_MEDIA_AI_STRATEGY_2025_001": [
        "ADBE_2025_10K_ITEM7_BLOCK_0004_PART_01_OF_03",
        "ADBE_2025_10K_ITEM7_BLOCK_0004_PART_02_OF_03",
        "ADBE_2025_10K_ITEM7_BLOCK_0006_PART_01_OF_02",
        "ADBE_2025_10K_ITEM8_BLOCK_0002_PART_01_OF_06",
    ],
    "AMZN_AWS_AI_CAPEX_CONTEXT_2025_001": [
        "AMZN_2025_10K_ITEM8_BLOCK_0011_PART_01_OF_02",
        "AMZN_2025_10K_ITEM8_BLOCK_0011_PART_02_OF_02",
        "AMZN_2025_10K_ITEM7_BLOCK_0005_PART_01_OF_03",
        "AMZN_2025_10K_ITEM8_BLOCK_0002_PART_09_OF_10",
    ],
    "GOOGL_SEARCH_YOUTUBE_CLOUD_ROLE_2025_001": [
        "GOOGL_2025_10K_ITEM1_BLOCK_0001_PART_01_OF_03",
        "GOOGL_2025_10K_ITEM1_BLOCK_0001_PART_02_OF_03",
        "GOOGL_2025_10K_ITEM1_BLOCK_0001_PART_03_OF_03",
        "GOOGL_2025_10K_ITEM7_BLOCK_0007_CHUNK_0001",
        "GOOGL_2025_10K_ITEM8_BLOCK_0017_CHUNK_0001",
    ],
    "MSFT_AI_CAPEX_CLOUD_RISK_2025_001": [
        "MSFT_2025_10K_ITEM7_BLOCK_0003_CHUNK_0001",
        "MSFT_2025_10K_ITEM7_BLOCK_0004_CHUNK_0001",
        "MSFT_2025_10K_ITEM7_BLOCK_0005_PART_01_OF_02",
        "MSFT_2025_10K_ITEM7_BLOCK_0005_PART_02_OF_02",
        "MSFT_2025_10K_ITEM8_BLOCK_0022_PART_01_OF_04",
    ],
    "PANW_PLATFORMIZATION_CONTEXT_2025_001": [
        "PANW_2025_10K_ITEM1_BLOCK_0001_CHUNK_0001",
        "PANW_2025_10K_ITEM1_BLOCK_0004_CHUNK_0001",
        "PANW_2025_10K_ITEM1_BLOCK_0007_CHUNK_0001",
        "PANW_2025_10K_ITEM7_BLOCK_0021_CHUNK_0001",
        "PANW_2025_10K_ITEM1A_BLOCK_0005_CHUNK_0001",
    ],
    "NVDA_INVENTORY_SUPPLY_CONSTRAINT_RISK_2023_2025_001": [
        "NVDA_2023_10K_ITEM1A_BLOCK_0004_PART_01_OF_02",
        "NVDA_2023_10K_ITEM1A_BLOCK_0004_PART_02_OF_02",
        "NVDA_2023_10K_ITEM1A_BLOCK_0010_PART_02_OF_02",
        "NVDA_2024_10K_ITEM7_BLOCK_0002_PART_01_OF_04",
        "NVDA_2024_10K_ITEM7_BLOCK_0002_PART_02_OF_04",
        "NVDA_2024_10K_ITEM1A_BLOCK_0004_PART_01_OF_04",
        "NVDA_2024_10K_ITEM7_BLOCK_0002_PART_04_OF_04",
        "NVDA_2025_10K_ITEM1A_BLOCK_0004_PART_01_OF_03",
        "NVDA_2025_10K_ITEM1_BLOCK_0005_PART_02_OF_03",
        "NVDA_2025_10K_ITEM7_BLOCK_0001_PART_02_OF_04",
    ],
}

CAVEAT_NOTES = {
    "AAPL_SERVICES_REGULATORY_RISK_2025_001": "Text-only reviewed context. Do not quantify App Store, Services margin, or regulatory impact unless a reviewed numeric fact is added.",
    "ADBE_DIGITAL_MEDIA_AI_STRATEGY_2025_001": "Text-only reviewed context. Digital Media, AI strategy, ARR, and subscription references are qualitative unless exact reviewed facts are cited from another approved case.",
    "AMZN_AWS_AI_CAPEX_CONTEXT_2025_001": "Text-only reviewed context. AWS segment and AI/capex context must not be used to infer advertising profitability or product-level AI revenue.",
    "GOOGL_SEARCH_YOUTUBE_CLOUD_ROLE_2025_001": "Text-only reviewed context. Search, YouTube, and Google Cloud must remain separate from AWS, Azure, and non-Alphabet cloud metrics.",
    "MSFT_AI_CAPEX_CLOUD_RISK_2025_001": "Text-only reviewed context. Microsoft Cloud and Azure references must not be treated as exact Azure gross margin or Azure-only revenue unless separately reviewed.",
    "PANW_PLATFORMIZATION_CONTEXT_2025_001": "Text-only reviewed context. Billings, RPO, deferred revenue, and recognized revenue remain separate visibility/revenue concepts.",
    "NVDA_INVENTORY_SUPPLY_CONSTRAINT_RISK_2023_2025_001": "Text-only reviewed context. Demand, supply, export-control, inventory, and product-transition risks must not be converted into exact product revenue or market-share claims.",
}


def main() -> None:
    REVIEWED_CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
    REVIEWED_FACTS_DIR.mkdir(parents=True, exist_ok=True)
    QUALITY_DIR.mkdir(parents=True, exist_ok=True)
    summaries = []
    for case_id in TEXT7_CASE_IDS:
        rows = _selected_context_rows(case_id)
        rows.append(_review_note_context(case_id, rows[0], CAVEAT_NOTES[case_id]))
        _write_jsonl(REVIEWED_CONTEXT_DIR / f"{case_id}.jsonl", rows)
        facts_payload = {
            "schema_version": "sec_gold_facts_reviewed_v0.1",
            "case_id": case_id,
            "benchmark_version": "sec_benchmark_v2_full40",
            "review_status": "reviewed_approved_text_only_case",
            "review_scope": {
                "source_policy": "SEC_ONLY",
                "allowed_filing_types": ["10-K"],
                "numeric_fact_policy": "no_target_numeric_facts_approved",
                "source_basis": "compact reviewed text rows selected from full40 review candidates",
            },
            "facts": [],
        }
        (REVIEWED_FACTS_DIR / f"{case_id}.json").write_text(json.dumps(facts_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summaries.append(
            {
                "case_id": case_id,
                "context_row_count": len(rows),
                "fact_count": 0,
                "context_path": str(REVIEWED_CONTEXT_DIR / f"{case_id}.jsonl"),
                "facts_path": str(REVIEWED_FACTS_DIR / f"{case_id}.json"),
            }
        )
    _write_approval(summaries)
    build_report_path = QUALITY_DIR / "sec_benchmark_v2_full40_text7_reviewed_gold_build_report.json"
    build_report = {
        "schema_version": "sec_v2_full40_text7_reviewed_gold_build_report_v0.1",
        "reviewed_case_ids": TEXT7_CASE_IDS,
        "cases": summaries,
        "approval_path": str(QUALITY_DIR / "sec_benchmark_v2_full40_text7_reviewed_gold_partial_approval.json"),
    }
    build_report_path.write_text(json.dumps(build_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "reviewed_case_count": len(TEXT7_CASE_IDS),
                "total_context_row_count": sum(int(item["context_row_count"]) for item in summaries),
                "build_report_path": str(build_report_path),
                "approval_path": str(QUALITY_DIR / "sec_benchmark_v2_full40_text7_reviewed_gold_partial_approval.json"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _selected_context_rows(case_id: str) -> list[dict[str, Any]]:
    candidate_path = CANDIDATE_CONTEXT_DIR / f"{case_id}.jsonl"
    candidates = _read_jsonl(candidate_path)
    by_evidence_id = {str(row.get("evidence_id") or row.get("source_evidence_id") or ""): row for row in candidates}
    rows = []
    missing = []
    for evidence_id in SELECTED_EVIDENCE_IDS[case_id]:
        row = by_evidence_id.get(evidence_id)
        if not row:
            missing.append(evidence_id)
            continue
        reviewed = dict(row)
        reviewed["schema_version"] = "sec_gold_context_reviewed_v0.1"
        reviewed["review_status"] = "reviewed_keep"
        reviewed["gold_role"] = _gold_role(reviewed)
        reviewed["review_note"] = "Promoted from full40 review candidate after compact text relevance review."
        rows.append(reviewed)
    if missing:
        raise SystemExit(f"Missing selected evidence rows for {case_id}: {missing}")
    return rows


def _review_note_context(case_id: str, anchor_row: dict[str, Any], text: str) -> dict[str, Any]:
    return {
        "schema_version": "sec_gold_context_reviewed_v0.1",
        "case_id": case_id,
        "review_status": "reviewed_keep",
        "gold_role": "caveat",
        "source_kind": "reviewed_source_policy_note",
        "source_evidence_id": f"REVIEW_NOTE_{case_id}",
        "ticker": anchor_row.get("ticker"),
        "fiscal_year": anchor_row.get("fiscal_year"),
        "source_type": "review_note",
        "section": "review_note",
        "text": text,
        "review_note": "Manual review caveat for full40 text seed promotion.",
    }


def _gold_role(row: dict[str, Any]) -> str:
    section = str(row.get("section") or "").lower()
    if "risk" in section:
        return "caveat"
    if "management" in section or "financial" in section:
        return "support"
    return "core"


def _write_approval(summaries: list[dict[str, Any]]) -> None:
    path = QUALITY_DIR / "sec_benchmark_v2_full40_text7_reviewed_gold_partial_approval.json"
    payload = {
        "schema_version": "sec_gold_manual_review_v0.2",
        "review_scope": {
            "gold_context_dir": "eval/sec_cases/reviewed_gold_context",
            "gold_facts_dir": "eval/sec_cases/reviewed_gold_facts",
            "case_count": len(TEXT7_CASE_IDS),
            "reviewed_case_ids": TEXT7_CASE_IDS,
        },
        "review_decision": {
            "overall_status": "partial_approved_for_mainline_scored_benchmark",
            "allowed_next_step": "case_filtered_full40_text7_gold_gate",
            "blocked_next_step": "full40_mainline_scored_test_until_all_gates_pass",
            "reason": "Seven text-only seed cases are promoted with compact reviewed SEC context and no target numeric facts.",
        },
        "case_reviews": [
            {
                "case_id": item["case_id"],
                "decision": "approved_for_gold_context_mode",
                "mainline_status": "can_enter_case_filtered_scored_gold_context_smoke",
                "evidence_assessment": f"Reviewed text-only evidence built for {item['case_id']} with {item['context_row_count']} compact context rows.",
                "fact_assessment": "No target numeric facts are approved for this text-only case.",
                "required_fix": "Before full40 promotion, run caveat/claim, abstract-judgment, answer-vs-Judgment-Plan, and unsupported-claim gates.",
            }
            for item in summaries
        ],
        "gate": {
            "can_enter_full_mainline_scored_test": False,
            "can_enter_case_filtered_gold_context_scored_smoke": True,
            "approved_case_ids": TEXT7_CASE_IDS,
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


if __name__ == "__main__":
    main()
