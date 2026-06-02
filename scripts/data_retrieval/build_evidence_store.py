from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from evidence import build_evidence_from_chunks, write_evidence_jsonl  # noqa: E402
from ingestion import read_chunks_jsonl  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert SEC filing chunks into unified EvidenceObject JSONL."
    )
    parser.add_argument(
        "--chunks",
        default="data/processed_private/chunks/sec_tech_10k_chunks.jsonl",
        help="Input chunks JSONL.",
    )
    parser.add_argument(
        "--output",
        default="data/processed_private/evidence_objects/sec_tech_10k_evidence.jsonl",
        help="Output EvidenceObject JSONL.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    chunks = read_chunks_jsonl(REPO_ROOT / args.chunks)
    evidence_objects = build_evidence_from_chunks(chunks)
    write_evidence_jsonl(evidence_objects, REPO_ROOT / args.output)

    summary = {
        "input_chunks": len(chunks),
        "output": str(REPO_ROOT / args.output),
        "evidence_objects": len(evidence_objects),
        "evidence_type_counts": dict(
            sorted(Counter(obj.evidence_type for obj in evidence_objects).items())
        ),
        "source_type_counts": dict(
            sorted(Counter(obj.source_type for obj in evidence_objects).items())
        ),
        "source_tier_counts": dict(
            sorted(Counter(obj.source_tier for obj in evidence_objects).items())
        ),
        "period_type_counts": dict(
            sorted(Counter(str(obj.period_type or "unknown") for obj in evidence_objects).items())
        ),
        "table_evidence": sum(
            1 for obj in evidence_objects if obj.metadata.get("contains_table")
        ),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
