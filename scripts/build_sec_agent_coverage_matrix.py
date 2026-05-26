from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
import sys

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.coverage_matrix import build_coverage_matrix  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build deterministic SEC Agent evidence coverage matrix.")
    parser.add_argument("--run-dir", default="", help="Interactive run directory. Supplies default artifact paths.")
    parser.add_argument("--case-path", default="")
    parser.add_argument("--query-contract-path", default="")
    parser.add_argument("--trace-logs-path", default="")
    parser.add_argument("--ledger-path", default="")
    parser.add_argument("--output-path", default="")
    parser.add_argument("--summary-path", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = _resolve(args.run_dir) if args.run_dir else None
    case_path = _path_arg(args.case_path, run_dir, "case.jsonl")
    query_contract_path = _path_arg(args.query_contract_path, run_dir, "query_contract.json")
    trace_logs_path = _path_arg(args.trace_logs_path, run_dir, "trace/trace_logs.jsonl")
    ledger_path = _path_arg(args.ledger_path, run_dir, "runtime_exact_value_ledger.json")
    output_path = _path_arg(args.output_path, run_dir, "runtime_evidence_coverage_matrix.json")
    summary_path = _path_arg(args.summary_path, run_dir, "runtime_evidence_coverage_matrix_summary.json")

    case = _read_jsonl(case_path)[0] if case_path.exists() else {}
    query_contract = _read_json(query_contract_path)
    trace = _read_jsonl(trace_logs_path)[0]
    ledger = _read_json(ledger_path) if ledger_path.exists() else {"rows": []}
    coverage = build_coverage_matrix(
        case=case,
        query_contract=query_contract,
        context_rows=trace.get("context_rows") or [],
        ledger_rows=ledger.get("rows") or [],
        run_id=case.get("case_id") or "",
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "schema_version": "sec_agent_evidence_coverage_matrix_summary_v0.1",
        "coverage_matrix_path": str(output_path.resolve()),
        "summary": coverage.get("summary") or {},
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def _path_arg(value: str, run_dir: Path | None, default_relative: str) -> Path:
    if value:
        return _resolve(value)
    if not run_dir:
        raise SystemExit(f"Missing --{default_relative.replace('/', '-')} or --run-dir")
    return run_dir / default_relative


def _resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else REPO_ROOT / p


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


if __name__ == "__main__":
    main()
