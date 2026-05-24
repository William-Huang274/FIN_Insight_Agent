from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from run_query_contract_planner import _planner_package, _read_json, _read_jsonl, _sanitize_contract


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize Query Contract planner outputs against eval metadata.")
    parser.add_argument(
        "--input",
        default="reports/query_contracts/sec_tech_10k_expanded_v0_2_complex6_qwen9b_query_contracts_raw.json",
    )
    parser.add_argument(
        "--output",
        default="reports/query_contracts/sec_tech_10k_expanded_v0_2_complex6_qwen9b_query_contracts.json",
    )
    parser.add_argument("--eval-path", default="eval_sets/sec_tech_10k_expanded_eval_v0_2.jsonl")
    parser.add_argument(
        "--grouped-pool-path",
        default="reports/evidence_pool/sec_tech_10k_expanded_v0_2_cell_vllm_calibrated_evidence_pool_grouped.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = _read_json(REPO_ROOT / args.input)
    eval_rows = {str(row.get("query_id")): row for row in _read_jsonl(REPO_ROOT / args.eval_path)}
    grouped = _read_json(REPO_ROOT / args.grouped_pool_path)
    grouped_by_id = {str(query.get("query_id")): query for query in grouped.get("queries") or []}

    note_counts: dict[str, int] = {}
    for row in payload.get("results") or []:
        query_id = str(row.get("query_id") or (row.get("query_contract") or {}).get("query_id") or "")
        eval_row = eval_rows.get(query_id)
        if not eval_row:
            row.setdefault("normalization_notes", []).append("missing_eval_row_skip_normalization")
            note_counts[query_id] = len(row.get("normalization_notes") or [])
            continue
        package = _planner_package(eval_row, grouped_by_id.get(query_id, {}))
        raw_contract = row.get("raw_query_contract") or row.get("query_contract") or row.get("contract") or {}
        normalized, notes = _sanitize_contract(row.get("query_contract") or raw_contract, package)
        row["raw_query_contract"] = raw_contract
        row["query_contract"] = normalized
        row["normalization_notes"] = _merge_notes(row.get("normalization_notes") or [], notes)
        note_counts[query_id] = len(row["normalization_notes"])

    payload["schema_version"] = f"{payload.get('schema_version', 'query_contract_planner_v0.1')}+normalized"
    payload["normalization"] = {
        "normalizer": "scripts/normalize_query_contracts.py",
        "eval_path": str((REPO_ROOT / args.eval_path).resolve()),
        "grouped_pool_path": str((REPO_ROOT / args.grouped_pool_path).resolve()),
        "note_counts": note_counts,
    }
    output_path = REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "query_count": len(payload.get("results") or []),
                "note_counts": note_counts,
                "output": str(output_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _merge_notes(existing: list[Any], added: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for note in [str(item) for item in existing] + added:
        if note and note not in seen:
            merged.append(note)
            seen.add(note)
    return merged


if __name__ == "__main__":
    main()
