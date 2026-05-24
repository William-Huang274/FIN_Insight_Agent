from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the v2 combined40 SEC benchmark pack.")
    parser.add_argument("--new20-mixed-cases-path", default="eval/sec_cases/test_cases_v2_new20_mixed_seed.jsonl")
    parser.add_argument("--cross-industry-cases-path", default="eval/sec_cases/test_cases_v2_cross_industry10_seed.jsonl")
    parser.add_argument("--new20-approval-path", default="reports/quality/sec_benchmark_v2_new20_mixed_review_approval.json")
    parser.add_argument("--cross-industry-approval-path", default="reports/quality/sec_benchmark_v2_cross_industry10_review_approval.json")
    parser.add_argument("--output-cases-path", default="eval/sec_cases/test_cases_v2_combined40_seed.jsonl")
    parser.add_argument("--approval-path", default="reports/quality/sec_benchmark_v2_combined40_review_approval.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    new20_cases = _read_jsonl(_resolve(args.new20_mixed_cases_path))
    cross_cases = _read_jsonl(_resolve(args.cross_industry_cases_path))
    new20_approval = _read_json(_resolve(args.new20_approval_path))
    cross_approval = _read_json(_resolve(args.cross_industry_approval_path))

    mixed_cases = []
    for case in new20_cases:
        mixed_cases.append(_combined_case(case, source_role=str(case.get("mixed_pack_role") or "new20_mixed_regression")))
    for case in cross_cases:
        mixed_cases.append(_combined_case(case, source_role="cross_industry_reviewed_slice"))

    _assert_unique_case_ids(mixed_cases)

    new20_approved = _approval_ids(new20_approval)
    cross_approved = _approval_ids(cross_approval)
    trap_case_ids = _trap_ids(new20_approval)
    approved_case_ids = new20_approved + cross_approved

    output_cases_path = _resolve(args.output_cases_path)
    output_cases_path.parent.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output_cases_path, mixed_cases)

    approval = _approval_payload(
        mixed_cases=mixed_cases,
        approved_case_ids=approved_case_ids,
        trap_case_ids=trap_case_ids,
        output_cases_path=args.output_cases_path,
    )
    approval_path = _resolve(args.approval_path)
    approval_path.parent.mkdir(parents=True, exist_ok=True)
    approval_path.write_text(json.dumps(approval, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "output_cases_path": str(output_cases_path),
                "approval_path": str(approval_path),
                "case_count": len(mixed_cases),
                "approved_case_count": len(approved_case_ids),
                "trap_case_count": len(trap_case_ids),
                "new20_case_count": len(new20_cases),
                "cross_industry_case_count": len(cross_cases),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _combined_case(case: dict[str, Any], *, source_role: str) -> dict[str, Any]:
    copy = dict(case)
    copy["origin"] = "v2_combined40_from_new20_mixed_and_cross_industry10"
    copy["case_family"] = "v2_combined40"
    copy["combined_pack_role"] = source_role
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
            "allowed_next_step": "combined40_gold_gate_then_ledger_and_cloud_pipeline",
            "blocked_next_step": "broader_generalization_claim_without_combined_cloud_post_gates",
            "reason": (
                "The combined40 pack merges the already-passed new20 mixed regression pack "
                "with the cross-industry10 reviewed slice. It is intended to test whether "
                "the expanded 30-company corpus preserves old regression behavior while "
                "adding bank, payments, pharma, industrial, consumer, and energy cases."
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
        "mainline_status": "can_enter_combined40_scored_pipeline",
        "evidence_assessment": "Reviewed artifact already exists and is reused under the combined40 benchmark route.",
        "fact_assessment": "Reviewed facts are validated by the mainline gold gate and ledger-unit gate.",
        "required_fix": "No pre-inference fix required for this combined-pack build step.",
    }


def _approval_ids(approval: dict[str, Any]) -> list[str]:
    gate = approval.get("gate") or {}
    review_scope = approval.get("review_scope") or {}
    ids = gate.get("approved_case_ids") or review_scope.get("reviewed_case_ids") or []
    return [str(case_id) for case_id in ids]


def _trap_ids(approval: dict[str, Any]) -> list[str]:
    gate = approval.get("gate") or {}
    review_scope = approval.get("review_scope") or {}
    ids = gate.get("trap_case_ids") or review_scope.get("pipeline_only_trap_case_ids") or []
    return [str(case_id) for case_id in ids]


def _assert_unique_case_ids(cases: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    duplicates: list[str] = []
    for case in cases:
        case_id = str(case.get("case_id") or "")
        if case_id in seen:
            duplicates.append(case_id)
        seen.add(case_id)
    if duplicates:
        raise SystemExit(f"Duplicate case_id values in combined pack: {sorted(duplicates)}")


def _resolve(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return REPO_ROOT / candidate


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


if __name__ == "__main__":
    main()
