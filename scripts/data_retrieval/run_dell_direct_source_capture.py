from __future__ import annotations

import argparse
from copy import deepcopy
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
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from ingestion.official_source_capture import capture_plan  # noqa: E402
from retrieval.direct_source_capture import (  # noqa: E402
    compile_dell_direct_source_shortlist,
    validate_dell_direct_source_capture_plan,
)
from retrieval.query_plan import canonical_digest  # noqa: E402
from scripts.data_retrieval.run_dell_external_source_ladder import (  # noqa: E402
    _compile_original_capture_plan,
    compile_captured_originals,
)


PLAN = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1_dell_direct_source_capture_plan_v1_0.json"
)
DEFAULT_PRIVATE_ROOT = (
    ROOT
    / "data"
    / "workbench_private"
    / "fin_0_1_3_s1_dell_direct_source_capture"
)
DEFAULT_PUBLIC = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1_dell_direct_source_capture_result_v1_0.json"
)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"dell_direct_source_json_not_mapping:{path.name}")
    return value


def _write_new(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


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
    if status:
        raise RuntimeError("dell_direct_source_capture_clean_worktree_required")


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
    plan = validate_dell_direct_source_capture_plan(_read_json(plan_path))
    attempt_root = private_root / attempt_id
    if attempt_root.exists() or public_output.exists():
        raise RuntimeError("dell_direct_source_attempt_or_output_already_exists")

    prepared_from_commit = _head()
    recorded_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    effective_plan_path = attempt_root / "effective_plan.json"
    _write_new(effective_plan_path, plan)
    shortlist = compile_dell_direct_source_shortlist(plan)
    shortlist_path = attempt_root / "fetch_shortlist.json"
    _write_new(shortlist_path, shortlist)
    original_plan = _compile_original_capture_plan(
        plan=plan,
        shortlist=shortlist,
    )
    original_plan_path = attempt_root / "original_capture_plan.json"
    _write_new(original_plan_path, original_plan)
    capture_result = capture_plan(
        original_plan,
        output_root=attempt_root / "original_capture",
        attempt_id="original-r1",
    )
    original_result = compile_captured_originals(
        plan=plan,
        shortlist=shortlist,
        capture_result=capture_result,
    )
    original_result_path = attempt_root / "original_compilation_result.json"
    _write_new(original_result_path, original_result)

    program_path = (ROOT / str(plan["program_ref"])).resolve()
    source_use_policy_path = (
        ROOT / str(plan["source_use_policy_ref"])
    ).resolve()
    if not program_path.is_file() or not source_use_policy_path.is_file():
        raise RuntimeError("dell_direct_source_bound_contract_missing")
    private_body = {
        "schema_version": (
            "fin_ia_s1_dell_direct_source_capture_private_result_v1_0"
        ),
        "status": "dell_external_source_ladder_exact_once_complete",
        "execution_mode": "pre_reviewed_direct_locator_zero_provider_calls",
        "attempt_id": attempt_id,
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "plan_binding": {
            "ref": _relative(plan_path),
            "sha256": _sha256(plan_path),
            "plan_digest": str(plan["plan_digest"]),
            "effective_plan_ref": _relative(effective_plan_path),
            "effective_plan_sha256": _sha256(effective_plan_path),
        },
        "program_binding": {
            "ref": _relative(program_path),
            "sha256": _sha256(program_path),
        },
        "source_use_policy_binding": {
            "ref": _relative(source_use_policy_path),
            "sha256": _sha256(source_use_policy_path),
        },
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
            "original_fetch_routes": len(shortlist["selected"]),
            "network_attempts_lower_bound": int(
                capture_result.get("network_attempts_lower_bound") or 0
            ),
            "network_attempts_upper_bound": int(
                capture_result.get("network_attempts_upper_bound") or 0
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

    compilation_summary = dict(original_result.get("summary") or {})
    public_body = {
        "schema_version": (
            "fin_ia_s1_dell_direct_source_capture_result_v1_0"
        ),
        "status": "dell_direct_source_capture_exact_once_complete",
        "case_key": "DELL",
        "research_as_of": str(plan["research_as_of"]),
        "attempt_id": attempt_id,
        "recorded_at": recorded_at,
        "prepared_from_commit": prepared_from_commit,
        "plan_id": str(plan["plan_id"]),
        "plan_digest": str(plan["plan_digest"]),
        "private_terminal_ref": _relative(private_result_path),
        "private_terminal_sha256": _sha256(private_result_path),
        "private_terminal_result_digest": str(private_result["result_digest"]),
        "observed_counts": deepcopy(private_result["observed_counts"]),
        "original_compilation_summary": compilation_summary,
        "route_receipts": deepcopy(
            list(original_result.get("route_receipts") or ())
        ),
        "authority": deepcopy(dict(plan["authority"])),
        "known_boundary": (
            "This result binds reviewed direct locators to immutable original "
            "captures and candidate-only proposals. It records zero provider, "
            "model and generation calls. It does not make a locator or proposal "
            "Evidence, close a public-information gap, prove Dell company-wide "
            "shipments or ASP, or qualify S1."
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
            "Capture reviewed Dell direct-source URLs exactly once without "
            "provider search, then compile candidate-only originals."
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
