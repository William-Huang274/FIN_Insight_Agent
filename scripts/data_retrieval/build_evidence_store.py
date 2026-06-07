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

from evidence import build_evidence_from_chunk  # noqa: E402
from ingestion import SecFilingChunk  # noqa: E402


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
    parser.add_argument("--progress-every", type=int, default=50000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    chunks_path = REPO_ROOT / args.chunks
    output_path = REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_output_path = output_path.with_suffix(output_path.suffix + ".tmp")

    input_chunks = 0
    evidence_objects = 0
    evidence_type_counts: Counter[str] = Counter()
    source_type_counts: Counter[str] = Counter()
    source_tier_counts: Counter[str] = Counter()
    period_type_counts: Counter[str] = Counter()
    table_evidence = 0

    with chunks_path.open("r", encoding="utf-8") as input_handle, tmp_output_path.open("w", encoding="utf-8") as output_handle:
        for line_number, line in enumerate(input_handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                chunk = SecFilingChunk.model_validate_json(stripped)
            except ValueError as exc:
                raise ValueError(f"Invalid SEC chunk JSONL at {chunks_path}:{line_number}") from exc
            evidence = build_evidence_from_chunk(chunk)
            output_handle.write(evidence.to_jsonl_line())
            output_handle.write("\n")
            input_chunks += 1
            evidence_objects += 1
            evidence_type_counts[evidence.evidence_type] += 1
            source_type_counts[evidence.source_type] += 1
            source_tier_counts[evidence.source_tier] += 1
            period_type_counts[str(evidence.period_type or "unknown")] += 1
            if evidence.metadata.get("contains_table"):
                table_evidence += 1
            if args.progress_every and input_chunks % args.progress_every == 0:
                print(json.dumps({"progress": input_chunks}, ensure_ascii=False), file=sys.stderr)
    tmp_output_path.replace(output_path)
    summary = {
        "input_chunks": input_chunks,
        "output": str(output_path),
        "evidence_objects": evidence_objects,
        "evidence_type_counts": dict(sorted(evidence_type_counts.items())),
        "source_type_counts": dict(sorted(source_type_counts.items())),
        "source_tier_counts": dict(sorted(source_tier_counts.items())),
        "period_type_counts": dict(sorted(period_type_counts.items())),
        "table_evidence": table_evidence,
        "streaming": True,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
