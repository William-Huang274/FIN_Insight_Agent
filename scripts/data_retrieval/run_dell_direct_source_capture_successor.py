from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path[:0] = [str(ROOT), str(SRC)]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from retrieval.direct_source_capture import (  # noqa: E402
    compile_dell_direct_source_capture_successor,
    compile_dell_direct_source_shortlist,
    validate_dell_direct_source_capture_successor_plan,
)
from retrieval.query_plan import canonical_digest  # noqa: E402
from scripts.data_retrieval.run_dell_direct_source_capture import (  # noqa: E402
    DEFAULT_PRIVATE_ROOT,
    _head,
    _read_json,
    _relative,
    _require_clean,
    _sha256,
    _write_new,
)
from scripts.data_retrieval.run_dell_external_source_ladder import (  # noqa: E402
    _compile_original_capture_plan,
    compile_captured_originals,
    execute_original_capture_successor,
)


PLAN = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1_dell_direct_source_capture_successor_plan_v1_0.json"
)
DEFAULT_PUBLIC = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1_dell_direct_source_capture_successor_result_v1_0.json"
)


def _bound_path(ref: str) -> Path:
    path = Path(ref)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _validate_file_binding(path: Path, expected_sha256: str, code: str) -> None:
    if not path.is_file() or _sha256(path) != expected_sha256:
        raise RuntimeError(code)


def run(
    *,
    attempt_id: str,
    plan_path: Path = PLAN,
    private_root: Path = DEFAULT_PRIVATE_ROOT,
    public_output: Path = DEFAULT_PUBLIC,
) -> dict[str, Any]:
    _require_clean()
    plan_path = plan_path.resolve()
    private_root = private_root.resolve()
    public_output = public_output.resolve()
    plan = validate_dell_direct_source_capture_successor_plan(
        _read_json(plan_path)
    )
    attempt_root = private_root / attempt_id
    if attempt_root.exists() or public_output.exists():
        raise RuntimeError(
            "dell_direct_source_successor_attempt_or_output_already_exists"
        )

    predecessor_plan_binding = dict(plan["predecessor_plan_binding"])
    predecessor_terminal_binding = dict(plan["predecessor_terminal_binding"])
    predecessor_plan_path = _bound_path(str(predecessor_plan_binding["ref"]))
    predecessor_terminal_path = _bound_path(
        str(predecessor_terminal_binding["ref"])
    )
    _validate_file_binding(
        predecessor_plan_path,
        str(predecessor_plan_binding["sha256"]),
        "dell_direct_source_successor_predecessor_plan_file_invalid",
    )
    _validate_file_binding(
        predecessor_terminal_path,
        str(predecessor_terminal_binding["sha256"]),
        "dell_direct_source_successor_predecessor_terminal_file_invalid",
    )
    predecessor_plan = _read_json(predecessor_plan_path)
    predecessor_terminal = _read_json(predecessor_terminal_path)
    effective_plan, locator_delta = compile_dell_direct_source_capture_successor(
        successor_plan=plan,
        predecessor_plan=predecessor_plan,
        predecessor_terminal=predecessor_terminal,
    )

    prepared_from_commit = _head()
    recorded_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    effective_plan_path = attempt_root / "effective_plan.json"
    _write_new(effective_plan_path, effective_plan)
    locator_delta_path = attempt_root / "locator_delta_receipt.json"
    _write_new(locator_delta_path, locator_delta)
    shortlist = compile_dell_direct_source_shortlist(effective_plan)
    shortlist_path = attempt_root / "fetch_shortlist.json"
    _write_new(shortlist_path, shortlist)
    original_plan = _compile_original_capture_plan(
        plan=effective_plan,
        shortlist=shortlist,
    )
    original_plan_path = attempt_root / "original_capture_plan.json"
    _write_new(original_plan_path, original_plan)
    capture_result, reuse_receipt = execute_original_capture_successor(
        plan=effective_plan,
        shortlist=shortlist,
        attempt_root=attempt_root,
        predecessor_plan=predecessor_plan,
        predecessor_private_result=predecessor_terminal,
    )
    if (
        int(capture_result.get("fresh_network_routes") or 0) != 1
        or int(capture_result.get("predecessor_captures_reused") or 0) != 4
    ):
        raise RuntimeError(
            "dell_direct_source_successor_execution_scope_invalid"
        )
    capture_reuse_receipt_path = attempt_root / "capture_reuse_receipt.json"
    _write_new(capture_reuse_receipt_path, reuse_receipt)
    original_result = compile_captured_originals(
        plan=effective_plan,
        shortlist=shortlist,
        capture_result=capture_result,
    )
    original_result_path = attempt_root / "original_compilation_result.json"
    _write_new(original_result_path, original_result)

    program_path = _bound_path(str(effective_plan["program_ref"]))
    source_use_policy_path = _bound_path(
        str(effective_plan["source_use_policy_ref"])
    )
    if not program_path.is_file() or not source_use_policy_path.is_file():
        raise RuntimeError("dell_direct_source_successor_contract_missing")
    private_body = {
        "schema_version": (
            "fin_ia_s1_dell_direct_source_capture_successor_private_result_v1_0"
        ),
        "status": "dell_external_source_ladder_exact_once_complete",
        "execution_mode": (
            "failed_route_only_direct_original_successor_zero_provider_calls"
        ),
        "attempt_id": attempt_id,
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "successor_plan_binding": {
            "ref": _relative(plan_path),
            "sha256": _sha256(plan_path),
            "plan_digest": str(plan["plan_digest"]),
        },
        "plan_binding": {
            "ref": _relative(effective_plan_path),
            "sha256": _sha256(effective_plan_path),
            "plan_digest": str(effective_plan["plan_digest"]),
        },
        "predecessor_binding": {
            "plan_ref": _relative(predecessor_plan_path),
            "plan_sha256": _sha256(predecessor_plan_path),
            "plan_digest": str(predecessor_plan["plan_digest"]),
            "terminal_ref": _relative(predecessor_terminal_path),
            "terminal_sha256": _sha256(predecessor_terminal_path),
            "terminal_result_digest": str(
                predecessor_terminal["result_digest"]
            ),
            "attempt_id": str(predecessor_terminal["attempt_id"]),
        },
        "program_binding": {
            "ref": _relative(program_path),
            "sha256": _sha256(program_path),
        },
        "source_use_policy_binding": {
            "ref": _relative(source_use_policy_path),
            "sha256": _sha256(source_use_policy_path),
        },
        "locator_delta_receipt": locator_delta,
        "capture_reuse_receipt": reuse_receipt,
        "fetch_shortlist": shortlist,
        "original_capture_plan": original_plan,
        "original_capture_result": capture_result,
        "original_compilation_result": original_result,
        "observed_counts": {
            "provider_calls": 0,
            "provider_retries": 0,
            "model_calls": 0,
            "generation_calls": 0,
            "direct_locator_count": len(shortlist["selected"]),
            "predecessor_captures_reused": int(
                capture_result["predecessor_captures_reused"]
            ),
            "fresh_original_fetch_routes": int(
                capture_result["fresh_network_routes"]
            ),
            "network_attempts_lower_bound": int(
                capture_result["fresh_network_attempts_lower_bound"]
            ),
            "network_attempts_upper_bound": int(
                capture_result["fresh_network_attempts_upper_bound"]
            ),
            "candidate_evidence_promotions": 0,
        },
        "authority": deepcopy(dict(plan["authority"])),
    }
    private_result = {
        **private_body,
        "result_digest": canonical_digest(private_body),
    }
    private_result_path = attempt_root / "terminal_result.json"
    _write_new(private_result_path, private_result)

    public_body: dict[str, Any] = {
        "schema_version": (
            "fin_ia_s1_dell_direct_source_capture_successor_result_v1_0"
        ),
        "status": "dell_direct_source_capture_successor_exact_once_complete",
        "case_key": "DELL",
        "research_as_of": str(plan["research_as_of"]),
        "attempt_id": attempt_id,
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "successor_plan_id": str(plan["plan_id"]),
        "successor_plan_digest": str(plan["plan_digest"]),
        "effective_plan_digest": str(effective_plan["plan_digest"]),
        "predecessor_terminal_result_digest": str(
            predecessor_terminal["result_digest"]
        ),
        "private_terminal_ref": _relative(private_result_path),
        "private_terminal_sha256": _sha256(private_result_path),
        "private_terminal_result_digest": str(private_result["result_digest"]),
        "locator_delta_receipt": locator_delta,
        "capture_reuse_receipt_digest": str(reuse_receipt["receipt_digest"]),
        "observed_counts": deepcopy(private_result["observed_counts"]),
        "original_compilation_summary": deepcopy(
            dict(original_result.get("summary") or {})
        ),
        "route_receipts": deepcopy(
            list(original_result.get("route_receipts") or ())
        ),
        "authority": deepcopy(dict(plan["authority"])),
        "known_boundary": (
            "This successor preserves the failed R1 Dell newsroom HTTP 403, "
            "reuses four immutable successful captures and performs exactly one "
            "fresh request to the issuer's official investor-relations PDF. "
            "Compiled text remains candidate-only until exhaustive CandidateDecision "
            "and Evidence Gate; no company ASP, units, allocation or S1 qualification "
            "is created here."
        ),
    }
    public_result = {
        **public_body,
        "result_digest": canonical_digest(public_body),
    }
    _write_new(public_output, public_result)
    return public_result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Reuse successful Dell direct captures and execute exactly one "
            "failed-route official-source successor."
        )
    )
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--plan", type=Path, default=PLAN)
    parser.add_argument("--private-root", type=Path, default=DEFAULT_PRIVATE_ROOT)
    parser.add_argument("--public-output", type=Path, default=DEFAULT_PUBLIC)
    args = parser.parse_args(argv)
    result = run(
        attempt_id=str(args.attempt_id),
        plan_path=args.plan,
        private_root=args.private_root,
        public_output=args.public_output,
    )
    print(json.dumps(result["observed_counts"], ensure_ascii=False, indent=2))
    print(
        json.dumps(
            result["original_compilation_summary"],
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"result_digest={result['result_digest']}")
    print(f"output={args.public_output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
