"""Read-only compatibility gate for the repaired M6.3/M6.5 table parser.

The gate accepts either the tracked sanitized structural fixture or a reviewer-
provided local filing path.  It never fetches a document, creates a runtime
store, or writes raw source content.  Parsed output is reported for independent
post-run review; no expected numeric value is supplied to the parser.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.canonical_runtime.bounded_sec_document_execution import (
    BoundedSecDocumentExecutionPolicy,
    SecDocumentParseError,
    extract_approved_table_value,
)


POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m6_3_5_positive_sec_document_pilot_policy_v1_0.json"
DEFAULT_FIXTURE = ROOT / "tests/fixtures/point01_m6_3_5_nvda_10k_actual_shape_sanitized.html"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m6_3_5_actual_shape_parser_gate_result_v1_0.json"


def _policy() -> BoundedSecDocumentExecutionPolicy:
    raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    return BoundedSecDocumentExecutionPolicy.model_validate(
        {field: raw[field] for field in BoundedSecDocumentExecutionPolicy.model_fields}
    )


def build_result(*, source_path: Path, source_kind: str) -> dict[str, Any]:
    body = source_path.read_text(encoding="utf-8")
    policy = _policy()
    try:
        extracted = extract_approved_table_value(html=body, selector=policy.target_table_selector)
        result: dict[str, Any] = {
            "result_version": "finsight_point01_m6_3_5_actual_shape_parser_gate_result_v1_0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "pass",
            "source_kind": source_kind,
            "source_document_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            "raw_source_persisted": False,
            "reviewer_blind_oracle_runtime_input": False,
            "external_call_count": 0,
            "store_write_count": 0,
            "parser_execution_count": 1,
            "post_parse_output": extracted.model_dump(mode="json"),
        }
    except (OSError, SecDocumentParseError, ValueError) as exc:
        result = {
            "result_version": "finsight_point01_m6_3_5_actual_shape_parser_gate_result_v1_0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "fail_closed",
            "source_kind": source_kind,
            "raw_source_persisted": False,
            "reviewer_blind_oracle_runtime_input": False,
            "external_call_count": 0,
            "store_write_count": 0,
            "parser_execution_count": 1,
            "error": str(exc),
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the M6.3/M6.5 actual-shape parser compatibility gate without network access.")
    parser.add_argument("--source", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--source-kind", choices=("sanitized_fixture", "reviewer_local_read_only"), default="sanitized_fixture")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    source_path = args.source if args.source.is_absolute() else ROOT / args.source
    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    result = build_result(source_path=source_path, source_kind=args.source_kind)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(output_path), "external_call_count": 0}, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
