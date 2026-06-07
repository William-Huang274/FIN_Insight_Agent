from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DOWNLOAD_SCRIPT = REPO_ROOT / "scripts" / "industry" / "10_download_industry_source_snapshot.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge provider-specific industry source snapshots.")
    parser.add_argument("--input-dir", action="append", required=True, help="Snapshot directory to merge. Can be repeated.")
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--output-root", default="data/processed_private/industry_data")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    helper = load_download_helper()
    input_dirs = [Path(item) for item in args.input_dir]
    output_dir = Path(args.output_root) / args.snapshot_id
    output_dir.mkdir(parents=True, exist_ok=True)

    observations: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    source_snapshots: list[dict[str, Any]] = []
    seen_observations: set[tuple[Any, ...]] = set()
    seen_evidence_ids: set[str] = set()

    for input_dir in input_dirs:
        metadata_path = input_dir / "industry_snapshot_metadata.json"
        metadata = read_json(metadata_path) if metadata_path.exists() else {}
        source_snapshots.append(
            {
                "snapshot_id": metadata.get("snapshot_id") or input_dir.name,
                "path": str(input_dir),
                "observation_count": metadata.get("observation_count"),
                "evidence_row_count": metadata.get("evidence_row_count"),
                "failure_count": metadata.get("failure_count"),
            }
        )
        failures.extend(metadata.get("failures") or [])

        for row in read_jsonl(input_dir / "industry_observations.jsonl"):
            key = (
                row.get("provider"),
                row.get("dataset_id"),
                row.get("series_id"),
                row.get("observation_date"),
                row.get("value"),
            )
            if key in seen_observations:
                continue
            seen_observations.add(key)
            observations.append(row)

        for row in read_jsonl(input_dir / "industry_evidence_rows.jsonl"):
            evidence_id = str(row.get("evidence_id") or "")
            if evidence_id and evidence_id in seen_evidence_ids:
                continue
            if evidence_id:
                seen_evidence_ids.add(evidence_id)
            evidence_rows.append(row)

    observations.sort(key=lambda row: (str(row.get("source_family") or ""), str(row.get("series_id") or ""), str(row.get("observation_date") or "")))
    evidence_rows.sort(key=lambda row: str(row.get("evidence_id") or ""))

    observations_path = output_dir / "industry_observations.jsonl"
    evidence_path = output_dir / "industry_evidence_rows.jsonl"
    metadata_path = output_dir / "industry_snapshot_metadata.json"
    duckdb_path = output_dir / "industry_snapshot.duckdb"
    helper.write_jsonl(observations_path, observations)
    helper.write_jsonl(evidence_path, evidence_rows)
    duckdb_summary = helper.write_duckdb(duckdb_path, observations, evidence_rows)

    metadata = {
        "schema_version": "industry_source_snapshot_v0.2",
        "snapshot_id": args.snapshot_id,
        "as_of_date": args.as_of_date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_snapshots": source_snapshots,
        "observation_count": len(observations),
        "evidence_row_count": len(evidence_rows),
        "failure_count": len(failures),
        "failures": failures,
        "outputs": {
            "observations": str(observations_path),
            "evidence_rows": str(evidence_path),
            "duckdb": str(duckdb_path),
            "metadata": str(metadata_path),
        },
        "duckdb": duckdb_summary,
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    return 0


def load_download_helper() -> Any:
    spec = importlib.util.spec_from_file_location("industry_download_snapshot_helper", DOWNLOAD_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


if __name__ == "__main__":
    raise SystemExit(main())
