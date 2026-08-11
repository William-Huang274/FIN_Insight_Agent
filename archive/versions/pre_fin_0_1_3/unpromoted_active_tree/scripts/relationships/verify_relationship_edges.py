from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from sec_agent.relationships.relationship_verifier import verify_relationship_edge

DEFAULT_INPUT = REPO_ROOT / "data" / "staging" / "relationships" / "full238_relationship_edge_candidates_v0_1.jsonl"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "staging" / "relationships"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify relationship edge candidates with deterministic contract gates.")
    parser.add_argument("--input-path", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--verified-output", type=Path, default=DEFAULT_OUTPUT_DIR / "full238_relationship_edges_verified_v0_1.jsonl")
    parser.add_argument("--rejected-output", type=Path, default=DEFAULT_OUTPUT_DIR / "full238_relationship_edges_rejected_v0_1.jsonl")
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_OUTPUT_DIR / "full238_relationship_edges_verified_summary_v0_1.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_path = _resolve(args.input_path)
    verified_path = _resolve(args.verified_output)
    rejected_path = _resolve(args.rejected_output)
    summary_path = _resolve(args.summary_output)
    verified_path.parent.mkdir(parents=True, exist_ok=True)
    rejected_path.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    verified = 0
    rejected = 0
    reason_counts: Counter[str] = Counter()
    relation_counts: Counter[str] = Counter()
    with input_path.open("r", encoding="utf-8") as source, verified_path.open("w", encoding="utf-8", newline="\n") as verified_sink, rejected_path.open("w", encoding="utf-8", newline="\n") as rejected_sink:
        for line in source:
            if not line.strip():
                continue
            total += 1
            result = verify_relationship_edge(json.loads(line))
            edge = result["edge"]
            relation_counts[edge.get("relation_type") or "unknown"] += 1
            if result["status"] == "pass":
                verified += 1
                verified_sink.write(json.dumps(edge, ensure_ascii=False, sort_keys=True) + "\n")
            else:
                rejected += 1
                for reason in result.get("reject_reasons") or [edge.get("reject_reason") or "unknown"]:
                    reason_counts[str(reason or "unknown")] += 1
                rejected_sink.write(json.dumps(edge, ensure_ascii=False, sort_keys=True) + "\n")

    summary = {
        "schema_version": "fin_agent_relationship_edge_verification_summary_v0.1",
        "status": "completed",
        "input_path": str(input_path),
        "verified_output": str(verified_path),
        "rejected_output": str(rejected_path),
        "total_candidates": total,
        "verified_count": verified,
        "rejected_count": rejected,
        "verified_rate": (verified / total) if total else 0.0,
        "relation_type_counts": dict(sorted(relation_counts.items())),
        "reject_reason_counts": dict(sorted(reason_counts.items())),
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
