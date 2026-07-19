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

from sec_agent.r53_r60_product_acceptance_b04_gate import (  # noqa: E402
    P24_DEFECT_CLOSEOUT_STATUSES,
    P24_DELIVERABLE_DECISION_STATUSES,
    P24_REAL_HUMAN_REVIEWER_ROLES,
    P24_REVIEWER_EVIDENCE_TYPES,
    append_real_reviewer_acceptance_evidence,
    get_product_acceptance_evidence_status,
)


def _csv_values(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _optional(payload: dict[str, Any], key: str, value: Any) -> None:
    if value not in (None, "", []):
        payload[key] = value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Record real-human B04 product acceptance evidence for R53-R60 P24.",
    )
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")
    parser.add_argument("--evidence-type", required=True, choices=sorted(P24_REVIEWER_EVIDENCE_TYPES))
    parser.add_argument("--reviewer-role", required=True, choices=sorted(P24_REAL_HUMAN_REVIEWER_ROLES))
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--status", default="complete")
    parser.add_argument("--task-id", default="")
    parser.add_argument("--case-id", default="")
    parser.add_argument("--decision-status", choices=sorted(P24_DELIVERABLE_DECISION_STATUSES), default=None)
    parser.add_argument("--deliverable-ref", default="")
    parser.add_argument("--artifact-ref-id", default="")
    parser.add_argument("--artifact-ref-ids", default="", help="Comma-separated artifact refs for audit_replay.")
    parser.add_argument("--review-comment", default="")
    parser.add_argument("--closeout-status", choices=sorted(P24_DEFECT_CLOSEOUT_STATUSES), default=None)
    parser.add_argument("--source-id", default="")
    parser.add_argument("--covered-source-ids", default="", help="Comma-separated defect source ids.")
    parser.add_argument("--repair-ref", default="")
    parser.add_argument("--regression-case-id", default="")
    parser.add_argument("--typed-gap-id", default="")
    parser.add_argument("--visual-decision", default="")
    parser.add_argument("--browser-screenshot-refs", default="", help="Comma-separated screenshot refs.")
    parser.add_argument("--trace-ref", default="")
    parser.add_argument("--review-comment-ref", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    payload: dict[str, Any] = {
        "evidence_type": args.evidence_type,
        "reviewer_role": args.reviewer_role,
        "session_id": args.session_id,
        "status": args.status,
        "action_source": "real_human",
    }
    _optional(payload, "task_id", args.task_id)
    _optional(payload, "case_id", args.case_id)
    _optional(payload, "decision_status", args.decision_status)
    _optional(payload, "deliverable_ref", args.deliverable_ref)
    _optional(payload, "artifact_ref_id", args.artifact_ref_id)
    _optional(payload, "artifact_ref_ids", _csv_values(args.artifact_ref_ids))
    _optional(payload, "review_comment", args.review_comment)
    _optional(payload, "closeout_status", args.closeout_status)
    _optional(payload, "source_id", args.source_id)
    _optional(payload, "covered_source_ids", _csv_values(args.covered_source_ids))
    _optional(payload, "repair_ref", args.repair_ref)
    _optional(payload, "regression_case_id", args.regression_case_id)
    _optional(payload, "typed_gap_id", args.typed_gap_id)
    _optional(payload, "visual_decision", args.visual_decision)
    _optional(payload, "browser_screenshot_refs", _csv_values(args.browser_screenshot_refs))
    _optional(payload, "trace_ref", args.trace_ref)
    _optional(payload, "review_comment_ref", args.review_comment_ref)

    result = append_real_reviewer_acceptance_evidence(root, payload)
    result["evidence_status"] = get_product_acceptance_evidence_status(root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
