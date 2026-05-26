from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from evidence.schema import read_evidence_jsonl  # noqa: E402
from evidence.structured_extractor import extract_structured_objects  # noqa: E402
from evidence.structured_objects import (  # noqa: E402
    ClaimObject,
    MetricObject,
    TableObject,
    write_structured_jsonl,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build TableObject, MetricObject, and ClaimObject JSONL from EvidenceObject JSONL."
    )
    parser.add_argument(
        "--evidence-path",
        default="data/processed_private/evidence_objects/sec_tech_10k_evidence.jsonl",
    )
    parser.add_argument(
        "--output-dir",
        default="data/processed_private/structured_objects",
    )
    parser.add_argument("--prefix", default="sec_tech_10k")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    evidence_path = REPO_ROOT / args.evidence_path
    output_dir = REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    evidence_objects = read_evidence_jsonl(evidence_path)
    tables: list[TableObject] = []
    metrics: list[MetricObject] = []
    claims: list[ClaimObject] = []

    per_ticker = defaultdict(lambda: {"tables": 0, "metrics": 0, "claims": 0})
    evidence_with_tables = 0
    for evidence in evidence_objects:
        result = extract_structured_objects(evidence)
        tables.extend(result.tables)
        metrics.extend(result.metrics)
        claims.extend(result.claims)
        if result.tables:
            evidence_with_tables += 1
        per_ticker[evidence.ticker]["tables"] += len(result.tables)
        per_ticker[evidence.ticker]["metrics"] += len(result.metrics)
        per_ticker[evidence.ticker]["claims"] += len(result.claims)

    table_path = output_dir / f"{args.prefix}_tables.jsonl"
    metric_path = output_dir / f"{args.prefix}_metrics.jsonl"
    claim_path = output_dir / f"{args.prefix}_claims.jsonl"
    summary_path = output_dir / f"{args.prefix}_structured_summary.json"

    write_structured_jsonl(tables, table_path)
    write_structured_jsonl(metrics, metric_path)
    write_structured_jsonl(claims, claim_path)

    summary = {
        "input_evidence_path": str(evidence_path),
        "evidence_count": len(evidence_objects),
        "evidence_with_tables": evidence_with_tables,
        "table_count": len(tables),
        "metric_count": len(metrics),
        "claim_count": len(claims),
        "metric_method_counts": dict(Counter(metric.extraction_method for metric in metrics)),
        "claim_type_counts": dict(Counter(claim.claim_type for claim in claims)),
        "top_metric_names": Counter(metric.metric_name for metric in metrics).most_common(30),
        "per_ticker": dict(sorted(per_ticker.items())),
        "outputs": {
            "tables": str(table_path),
            "metrics": str(metric_path),
            "claims": str(claim_path),
            "summary": str(summary_path),
        },
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
