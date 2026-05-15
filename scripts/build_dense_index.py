from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from indexing.build_dense_index import build_dense_index  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build dense embedding index from EvidenceObject JSONL.")
    parser.add_argument(
        "--evidence",
        default="data/processed_private/evidence_objects/sec_tech_10k_evidence.jsonl",
    )
    parser.add_argument("--output-dir", default="data/indexes/dense/sec_tech_10k")
    parser.add_argument("--model", default="sentence-transformers/all-MiniLM-L6-v2")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--device", help="Optional sentence-transformers device, e.g. cuda or cpu.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metadata = build_dense_index(
        evidence_path=REPO_ROOT / args.evidence,
        output_dir=REPO_ROOT / args.output_dir,
        model_name=args.model,
        batch_size=args.batch_size,
        device=args.device,
    )
    print(json.dumps(metadata, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
