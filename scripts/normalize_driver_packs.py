from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_driver_pack_planner import _normalize_pack  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize model-generated Decision Driver Evidence Packs.")
    parser.add_argument(
        "--input",
        default="reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_driver_packs_qwen9b.json",
    )
    parser.add_argument(
        "--candidate-path",
        default="reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_driver_pack_candidates.json",
    )
    parser.add_argument(
        "--output",
        default="reports/evidence_packs/sec_tech_10k_expanded_v0_2_complex6_driver_packs_qwen9b_normalized.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = _read_json(REPO_ROOT / args.input)
    candidates = _read_json(REPO_ROOT / args.candidate_path)
    candidate_by_query = {str(row.get("query_id")): row for row in candidates.get("queries") or []}
    results = []
    for row in payload.get("results") or []:
        query_id = str(row.get("query_id") or "")
        candidate = candidate_by_query.get(query_id)
        if not candidate:
            results.append(row)
            continue
        parse_status = str(row.get("parse_status") or "unknown")
        pack = row.get("driver_pack") or {}
        normalized = dict(row)
        normalized["normalization_status"] = "normalized_v0.1"
        normalized["driver_pack"] = _normalize_pack(pack, candidate, parse_status=parse_status)
        results.append(normalized)

    report = dict(payload)
    report["schema_version"] = f"{payload.get('schema_version', 'driver_pack_planner')}_normalized_v0.1"
    report["partial"] = False
    report["summary"] = {
        **(payload.get("summary") or {}),
        "query_count": len(results),
        "parse_status_counts": dict(Counter(str(row.get("parse_status")) for row in results)),
        "normalization_status_counts": dict(Counter(str(row.get("normalization_status")) for row in results)),
        "driver_count": sum(len((row.get("driver_pack") or {}).get("decision_drivers") or []) for row in results),
    }
    report["results"] = results
    output_path = REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output_path),
                "queries": len(results),
                "parse_status_counts": report["summary"]["parse_status_counts"],
                "normalization_status_counts": report["summary"]["normalization_status_counts"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
