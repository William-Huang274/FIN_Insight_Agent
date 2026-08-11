from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.product_intelligence_depth import (  # noqa: E402
    DEFAULT_AI_SEMIS_ROUTE_GATE_JSONL,
    DEFAULT_PRODUCT_INTELLIGENCE_PACK_JSONL,
    build_ai_semis_product_evidence_packs,
    load_source_rows_by_layer,
)


DEFAULT_OUTPUT_PACKS = REPO_ROOT / "data" / "manifests" / "ai_semis_product_evidence_pack_v0_2.jsonl"
DEFAULT_OUTPUT_GATE = REPO_ROOT / "data" / "manifests" / "ai_semis_product_depth_gate_v0_2.json"
DEFAULT_OUTPUT_GAP_QUEUE = REPO_ROOT / "data" / "manifests" / "ai_semis_product_depth_gap_queue_v0_2.jsonl"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build AI/Semis ProductEvidencePack v0.2 by joining ProductIntelligenceGraph packs with "
            "parser-backed L2/L3 source rows. Route-only rows remain repair instructions, not evidence."
        )
    )
    parser.add_argument("--route-gate", type=Path, default=REPO_ROOT / DEFAULT_AI_SEMIS_ROUTE_GATE_JSONL)
    parser.add_argument("--product-intelligence-packs", type=Path, default=REPO_ROOT / DEFAULT_PRODUCT_INTELLIGENCE_PACK_JSONL)
    parser.add_argument("--output-packs", type=Path, default=DEFAULT_OUTPUT_PACKS)
    parser.add_argument("--output-gate", type=Path, default=DEFAULT_OUTPUT_GATE)
    parser.add_argument("--output-gap-queue", type=Path, default=DEFAULT_OUTPUT_GAP_QUEUE)
    parser.add_argument("--max-examples-per-layer", type=int, default=8)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    route_rows = _load_jsonl(args.route_gate)
    pig_rows = _load_jsonl(args.product_intelligence_packs)
    source_rows_by_layer = load_source_rows_by_layer(REPO_ROOT)
    packs, gate, gap_queue = build_ai_semis_product_evidence_packs(
        route_gate_rows=route_rows,
        product_intelligence_pack_rows=pig_rows,
        source_rows_by_layer=source_rows_by_layer,
        generated_at=generated_at,
        max_examples_per_layer=args.max_examples_per_layer,
    )
    _write_jsonl(args.output_packs, packs)
    _write_json(args.output_gate, gate)
    _write_jsonl(args.output_gap_queue, gap_queue)
    print(json.dumps(gate, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and gate.get("status") != "pass":
        return 1
    return 0


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
