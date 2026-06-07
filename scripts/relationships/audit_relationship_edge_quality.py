from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from sec_agent.relationships.edge_schema import validate_relationship_edge

DEFAULT_VERIFIED = REPO_ROOT / "data" / "staging" / "relationships" / "full238_relationship_edges_verified_v0_1.jsonl"
DEFAULT_OUTPUT = REPO_ROOT / "eval" / "relationship_edges" / "full238_relationship_edge_quality_v0_1.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit relationship edge quality gate.")
    parser.add_argument("--edges-path", type=Path, default=DEFAULT_VERIFIED)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--min-verified-edges", type=int, default=1)
    parser.add_argument("--allow-zero", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows = _load_jsonl(_resolve(args.edges_path))
    summary = audit_relationship_edges(rows, min_verified_edges=args.min_verified_edges, allow_zero=args.allow_zero)
    output = _resolve(args.summary_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "pass" else 1


def audit_relationship_edges(
    rows: list[Mapping[str, Any]],
    *,
    min_verified_edges: int = 1,
    allow_zero: bool = False,
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    relation_counts: Counter[str] = Counter()
    confidence_counts: Counter[str] = Counter()
    for index, row in enumerate(rows):
        result = validate_relationship_edge(row, strict=True)
        edge = result["edge"]
        relation_counts[edge.get("relation_type") or "unknown"] += 1
        confidence_counts[edge.get("confidence") or "unknown"] += 1
        if result["status"] != "pass":
            errors.append({"type": "edge_contract_failed", "index": index, "edge_id": edge.get("edge_id"), "errors": result["errors"]})
        if edge.get("verifier_status") != "verified":
            errors.append({"type": "edge_not_verified", "index": index, "edge_id": edge.get("edge_id")})
        if edge.get("relation_type") == "sector_exposure" and edge.get("relationship_type") in {"customer", "supplier"}:
            errors.append({"type": "sector_exposure_customer_supplier_contamination", "index": index, "edge_id": edge.get("edge_id")})
    if not allow_zero and len(rows) < min_verified_edges:
        errors.append({"type": "verified_edge_count_below_minimum", "actual": len(rows), "minimum": min_verified_edges})
    return {
        "schema_version": "fin_agent_relationship_edge_quality_audit_v0.1",
        "status": "fail" if errors else "pass",
        "edge_count": len(rows),
        "relation_type_counts": dict(sorted(relation_counts.items())),
        "confidence_counts": dict(sorted(confidence_counts.items())),
        "errors": errors[:200],
    }


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
