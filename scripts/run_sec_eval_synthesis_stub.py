from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stub synthesis backend for SEC benchmark runner.")
    parser.add_argument("--input", required=True, help="Path to synthesis input JSON.")
    parser.add_argument("--output", required=True, help="Path to synthesis output JSON.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    case = input_payload.get("case") or {}
    context_rows = input_payload.get("context_rows") or []
    mode = str(input_payload.get("mode") or "")
    answer = {
        "summary": f"stub synthesis for {case.get('case_id')} in {mode}",
        "context_row_count": len(context_rows),
        "first_source_kind": (context_rows[0].get("source_kind") if context_rows else None),
    }
    output_payload = {
        "status": "answered_stub",
        "answer_status": "answered_stub",
        "answer": answer,
        "limitations": ["stub backend only; no model synthesis performed"],
        "claim_status": "not_run_stub",
        "claims": [],
        "unsupported_claim_count": 0,
        "score_status": "not_scored_stub",
        "score_total": None,
        "scores": None,
        "failure_types": [],
        "score_notes": [],
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
