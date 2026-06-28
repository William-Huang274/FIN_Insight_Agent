from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.source_coverage_gate import (  # noqa: E402
    build_source_coverage_matrix,
    write_source_coverage_matrix,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit industry source coverage requirements against source-layer capability and optional runtime rows.")
    parser.add_argument("--source-layer-rows", default="data/manifests/source_layer_capability_audit_v0_1.jsonl")
    parser.add_argument("--observed-rows", action="append", default=[], help="Optional JSONL file with runtime evidence/context rows.")
    parser.add_argument("--specialist-visible-rows", action="append", default=[], help="Optional JSONL file with role-visible rows.")
    parser.add_argument("--industry-schema", action="append", default=[], help="Industry schema to audit. Defaults to all known schemas.")
    parser.add_argument("--phase", choices=["registry", "runtime_case"], default="registry")
    parser.add_argument("--output-summary", default="data/manifests/source_coverage_gate_summary_v0_1.json")
    parser.add_argument("--output-report", default="docs/internal/vnext_20260610/source_coverage_gate.zh-CN.md")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if validation fails. Gaps are reported but do not fail strict mode.")
    parser.add_argument("--require-pass", action="store_true", help="Exit non-zero unless all audited requirements pass.")
    args = parser.parse_args()

    source_layer_rows = _load_jsonl(args.source_layer_rows)
    observed_rows = [row for path in args.observed_rows for row in _load_jsonl(path)]
    specialist_visible_rows = [row for path in args.specialist_visible_rows for row in _load_jsonl(path)]
    payload = build_source_coverage_matrix(
        industry_schemas=args.industry_schema or None,
        phase=args.phase,
        source_layer_capability={"rows": source_layer_rows},
        observed_rows=observed_rows,
        specialist_visible_rows=specialist_visible_rows,
    )
    outputs = write_source_coverage_matrix(
        payload,
        output_summary_path=args.output_summary,
        output_report_path=args.output_report,
    )
    print(json.dumps({"status": payload["status"], "summary": payload["summary"], "outputs": outputs}, ensure_ascii=False, indent=2))
    if args.strict and payload["validation"]["status"] != "pass":
        return 1
    if args.require_pass and payload["status"] != "pass":
        return 1
    return 0


def _load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.exists():
        return []
    rows: list[dict[str, Any]] = []
    with source.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            value = json.loads(text)
            if isinstance(value, dict):
                rows.append(value)
    return rows


if __name__ == "__main__":
    raise SystemExit(main())
