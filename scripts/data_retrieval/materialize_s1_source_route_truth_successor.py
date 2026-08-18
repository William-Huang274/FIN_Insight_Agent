from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path[:0] = [str(ROOT), str(SRC)]

from ingestion.source_intake import SourceIntakePolicy, SourceIntakeStore  # noqa: E402
from retrieval.query_plan import canonical_digest  # noqa: E402
from retrieval.source_route_dispatch import (  # noqa: E402
    compile_product_projection_source_route_successor,
    load_source_route_portfolio_policy,
)


FULL_RESULT_SCHEMA_VERSION = (
    "fin_ia_s1_source_route_truth_replay_successor_full_v1_0"
)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def _resolve(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), f"source_route_truth_json_invalid:{path.name}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip().lower()


def _require_clean() -> None:
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    _require(not status, "source_route_truth_successor_clean_worktree_required")


def _write_new(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _verify_digest(value: Mapping[str, Any], field: str, code: str) -> None:
    body = dict(value)
    digest = str(body.pop(field, ""))
    _require(bool(digest) and digest == canonical_digest(body), code)


def build_source_route_truth_successor(
    *,
    predecessor: Mapping[str, Any],
    source_route_policy: Mapping[str, Any],
    source_intake_policy: SourceIntakePolicy,
    source_intake_attempts: Sequence[Mapping[str, Any]],
    recorded_at: str,
    prepared_from_commit: str,
    source_bindings: Mapping[str, Any],
) -> dict[str, Any]:
    _verify_digest(
        predecessor,
        "result_digest",
        "source_route_truth_predecessor_digest_invalid",
    )
    projection = predecessor.get("product_projection")
    _require(
        isinstance(projection, Mapping),
        "source_route_truth_product_projection_missing",
    )
    _verify_digest(
        projection,
        "projection_digest",
        "source_route_truth_product_projection_digest_invalid",
    )
    loaded_policy = load_source_route_portfolio_policy(source_route_policy)
    successor_projection = compile_product_projection_source_route_successor(
        product_projection=projection,
        policy=loaded_policy,
        registered_intake_routes=[
            route.public_projection()
            for route in source_intake_policy.routes.values()
        ],
        intake_attempts=source_intake_attempts,
    )
    case_key = str(successor_projection.get("case_key") or "").upper()
    _require(bool(case_key), "source_route_truth_case_key_missing")
    attempt_snapshot = [dict(row) for row in source_intake_attempts]
    attempt_snapshot.sort(
        key=lambda row: (
            str(row.get("recorded_at") or ""),
            str(row.get("attempt_id") or ""),
        )
    )
    body = {
        "schema_version": FULL_RESULT_SCHEMA_VERSION,
        "status": "source_route_truth_replay_successor_materialized",
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "case_key": case_key,
        "replay_mode": "immutable_candidate_replay_zero_call_source_truth_successor",
        "source_bindings": dict(source_bindings),
        "source_intake_attempt_snapshot": attempt_snapshot,
        "source_intake_attempt_snapshot_digest": canonical_digest(attempt_snapshot),
        "product_projection": successor_projection,
        "execution_summary": {
            "network_calls": 0,
            "model_calls": 0,
            "vector_calls": 0,
            "replayed_request_count": len(successor_projection["request_results"]),
            "historical_request_projection_digests_preserved": True,
        },
        "authority": {
            "candidate_is_not_evidence": True,
            "source_capture_is_not_evidence": True,
            "numeric_authority": False,
            "public_information_gap_authority": False,
            "product_acceptance_authority": False,
        },
        "known_boundary": (
            "This zero-call successor preserves the immutable candidate replay and "
            "adds request-bound source-route execution truth. It does not execute a "
            "source route, create Evidence or NumericFact, infer non-disclosure, "
            "qualify S1 or authorize publication."
        ),
    }
    return {**body, "result_digest": canonical_digest(body)}


def materialize(
    *,
    predecessor_path: Path,
    source_route_policy_path: Path,
    source_intake_policy_path: Path,
    source_intake_root: Path,
    output_path: Path,
) -> dict[str, Any]:
    _require_clean()
    predecessor = _read_json(predecessor_path)
    source_route_policy = _read_json(source_route_policy_path)
    source_intake_policy = SourceIntakePolicy.from_path(source_intake_policy_path)
    attempts = SourceIntakeStore(
        source_intake_root, source_intake_policy
    ).list_attempts(limit=1000)
    recorded_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    source_bindings = {
        "predecessor_replay": {
            "ref": _relative(predecessor_path),
            "sha256": _sha256(predecessor_path),
            "result_digest": predecessor.get("result_digest"),
        },
        "source_route_portfolio_policy": {
            "ref": _relative(source_route_policy_path),
            "sha256": _sha256(source_route_policy_path),
            "policy_id": source_route_policy.get("policy_id"),
        },
        "source_intake_policy": {
            "ref": _relative(source_intake_policy_path),
            "sha256": _sha256(source_intake_policy_path),
            "policy_id": source_intake_policy.policy_id,
        },
        "source_intake_store": {
            "ref": _relative(source_intake_root),
            "attempt_count": len(attempts),
            "attempt_snapshot_digest": canonical_digest(attempts),
        },
    }
    result = build_source_route_truth_successor(
        predecessor=predecessor,
        source_route_policy=source_route_policy,
        source_intake_policy=source_intake_policy,
        source_intake_attempts=attempts,
        recorded_at=recorded_at,
        prepared_from_commit=_head(),
        source_bindings=source_bindings,
    )
    _write_new(output_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize a zero-call source-route truth successor for an immutable "
            "S1 product candidate replay."
        )
    )
    parser.add_argument("--predecessor", required=True)
    parser.add_argument("--source-route-policy", required=True)
    parser.add_argument("--source-intake-policy", required=True)
    parser.add_argument("--source-intake-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = materialize(
        predecessor_path=_resolve(args.predecessor),
        source_route_policy_path=_resolve(args.source_route_policy),
        source_intake_policy_path=_resolve(args.source_intake_policy),
        source_intake_root=_resolve(args.source_intake_root),
        output_path=_resolve(args.output),
    )
    summary = result["product_projection"]["summary"]["source_route_execution"]
    print(
        json.dumps(
            {
                "case_key": result["case_key"],
                "status": result["status"],
                "result_digest": result["result_digest"],
                "source_route_execution": summary,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
