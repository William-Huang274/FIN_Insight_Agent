from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from financial_facts.sec_snapshot import (  # noqa: E402
    build_s2_successor_policy_from_sec_snapshot,
    canonical_digest,
    load_sec_snapshot_result_manifest,
    seal_s2_successor_policy_change_receipt,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Bind an immutable SEC snapshot to the existing S2 policy without "
            "changing metrics, qrels, temporal settings, or financial rules."
        )
    )
    parser.add_argument("--baseline-policy", type=Path, required=True)
    parser.add_argument("--snapshot-manifest", type=Path, required=True)
    parser.add_argument(
        "--research-as-of",
        required=True,
        help="Explicit YYYY-MM-DD research cut-off for this current snapshot.",
    )
    parser.add_argument("--output-policy", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    baseline_path = args.baseline_policy.resolve()
    manifest_path = args.snapshot_manifest.resolve()
    output_path = args.output_policy.resolve()
    receipt_path = args.receipt.resolve() if args.receipt else None
    if output_path.exists():
        raise ValueError("sec_snapshot_s2_bridge_output_exists")
    if receipt_path is not None and receipt_path.exists():
        raise ValueError("sec_snapshot_s2_bridge_receipt_exists")
    if receipt_path == output_path:
        raise ValueError("sec_snapshot_s2_bridge_receipt_conflicts_with_policy")

    baseline = _read_json(baseline_path)
    snapshot = load_sec_snapshot_result_manifest(manifest_path)
    successor = build_s2_successor_policy_from_sec_snapshot(
        baseline,
        snapshot,
        snapshot_root=manifest_path.parent,
        research_as_of=args.research_as_of,
    )
    change_receipt = seal_s2_successor_policy_change_receipt(
        baseline,
        successor,
        snapshot_root=manifest_path.parent,
    )
    _atomic_exclusive_write_json(output_path, successor)
    summary = {
        "status": "sec_snapshot_s2_successor_policy_materialized",
        "baseline_policy": str(baseline_path),
        "baseline_policy_sha256": _file_sha256(baseline_path),
        "snapshot_manifest": str(manifest_path),
        "snapshot_manifest_digest": snapshot.manifest_digest,
        "snapshot_attempt_id": snapshot.attempt_id,
        "source_binding_count": len(successor["source_bindings"]),
        "output_policy": str(output_path),
        "output_policy_sha256": _file_sha256(output_path),
        "output_policy_digest": canonical_digest(successor),
        "research_as_of_before": baseline["research_as_of"],
        "research_as_of_after": successor["research_as_of"],
        "policy_change_receipt": change_receipt,
        "baseline_rules_preserved": True,
    }
    if receipt_path is not None:
        _atomic_exclusive_write_json(receipt_path, summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("sec_snapshot_s2_bridge_baseline_object_required")
    return value


def _atomic_exclusive_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            raise ValueError("sec_snapshot_s2_bridge_output_race")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
