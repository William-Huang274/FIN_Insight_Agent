from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from apps.workbench.backend.application.source_intake_service import (  # noqa: E402
    SourceIntakeService,
)
from ingestion.source_intake import SourceIntakePolicy  # noqa: E402
from sec_agent.runtime_bridge.paths import resolve_runtime_paths  # noqa: E402


AUTHORITY_SCHEMA_VERSION = "fin_ia_s1d_source_intake_execution_authority_v1_0"
DEFAULT_AUTHORITY = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1d_source_intake_execution_authority_v1_0.json"
)


class SourceIntakeRunnerError(RuntimeError):
    """Raised when a source-intake live is not exactly bound and authorized."""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the one authorized FIN 0.1.3 S1-D source-intake live."
    )
    parser.add_argument("--authority", type=Path, default=DEFAULT_AUTHORITY)
    args = parser.parse_args()
    authority_path = args.authority.resolve()
    authority = validate_authority(
        json.loads(authority_path.read_text(encoding="utf-8")),
        repository_root=ROOT,
    )
    assert_repository_state(authority, repository_root=ROOT)

    policy_path = ROOT / str(authority["bound_inputs"]["source_intake_policy_ref"])
    runtime_paths = resolve_runtime_paths(ROOT)
    service = SourceIntakeService(
        policy=SourceIntakePolicy.from_path(policy_path),
        private_root=runtime_paths.workbench_private_root / "source_intake",
    )
    attempts: list[dict[str, Any]] = []
    for row in authority["execution_budget"]["route_attempts"]:
        attempts.append(
            service.acquire_automatic(
                route_id=str(row["route_id"]),
                attempt_id=str(row["attempt_id"]),
            )
        )

    complete = all(
        row["status"] == "captured_ready_for_parse" for row in attempts
    )
    result = {
        "schema_version": "fin_ia_s1d_source_intake_execution_result_v1_0",
        "result_id": str(authority["result_contract"]["result_id"]),
        "recorded_at": str(authority["recorded_at"]),
        "status": (
            "source_intake_automatic_capture_complete"
            if complete
            else "source_intake_automatic_capture_incomplete"
        ),
        "authority_ref": authority_path.relative_to(ROOT).as_posix(),
        "execution": {
            "routes": len(attempts),
            "network_attempts_maximum": len(attempts),
            "retries": 0,
            "model_calls": 0,
            "broad_web_search_calls": 0,
            "captured_ready_for_parse": sum(
                row["status"] == "captured_ready_for_parse" for row in attempts
            ),
            "source_promoted_to_evidence": 0,
        },
        "route_results": attempts,
        "boundary": {
            "raw_bytes_are_private": True,
            "captured_source_is_not_evidence": True,
            "parse_authorized": False,
            "evidence_promotion_authorized": False,
            "s3_model_execution_authorized": False,
        },
    }
    result_path = ROOT / str(authority["result_contract"]["public_result_ref"])
    result_path.parent.mkdir(parents=True, exist_ok=True)
    _write_exclusive(result_path, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if complete else 2


def validate_authority(
    payload: Mapping[str, Any],
    *,
    repository_root: Path,
) -> dict[str, Any]:
    value = dict(payload)
    if (
        value.get("schema_version") != AUTHORITY_SCHEMA_VERSION
        or value.get("status")
        != "fresh_bounded_source_intake_automatic_execution_authorized"
    ):
        raise SourceIntakeRunnerError("source_intake_authority_status_invalid")
    clean = value.get("clean_implementation")
    bound = value.get("bound_inputs")
    budget = value.get("execution_budget")
    result = value.get("result_contract")
    if not all(isinstance(row, Mapping) for row in (clean, bound, budget, result)):
        raise SourceIntakeRunnerError("source_intake_authority_shape_invalid")
    assert isinstance(clean, Mapping)
    assert isinstance(bound, Mapping)
    assert isinstance(budget, Mapping)
    assert isinstance(result, Mapping)
    route_attempts = budget.get("route_attempts")
    if not isinstance(route_attempts, list) or len(route_attempts) != 2:
        raise SourceIntakeRunnerError("source_intake_authority_budget_invalid")
    if any(not isinstance(row, Mapping) for row in route_attempts):
        raise SourceIntakeRunnerError("source_intake_authority_budget_invalid")
    route_ids = [str(row.get("route_id") or "") for row in route_attempts]
    attempt_ids = [str(row.get("attempt_id") or "") for row in route_attempts]
    if (
        len(set(route_ids)) != 2
        or len(set(attempt_ids)) != 2
        or any(not item for item in route_ids + attempt_ids)
        or int(budget.get("network_attempts_maximum") or -1) != 2
        or int(budget.get("retries") if budget.get("retries") is not None else -1)
        != 0
        or int(budget.get("model_calls") if budget.get("model_calls") is not None else -1)
        != 0
        or budget.get("credentials") != "forbidden"
    ):
        raise SourceIntakeRunnerError("source_intake_authority_budget_invalid")
    if clean.get("working_tree_required_clean_before_execution") is not True:
        raise SourceIntakeRunnerError("source_intake_authority_clean_tree_not_required")

    policy_ref = str(bound.get("source_intake_policy_ref") or "")
    runner_ref = str(bound.get("runner_ref") or "")
    public_result_ref = str(result.get("public_result_ref") or "")
    for ref in (policy_ref, runner_ref, public_result_ref):
        _safe_repository_path(repository_root, ref)
    _assert_digest(
        repository_root / policy_ref,
        str(bound.get("source_intake_policy_sha256") or ""),
    )
    _assert_digest(
        repository_root / runner_ref,
        str(bound.get("runner_sha256") or ""),
    )
    policy = SourceIntakePolicy.from_path(repository_root / policy_ref)
    if set(route_ids) != set(policy.routes):
        raise SourceIntakeRunnerError("source_intake_authority_routes_not_policy_exact")
    if (repository_root / public_result_ref).exists():
        raise SourceIntakeRunnerError("source_intake_public_result_already_exists")
    return value


def assert_repository_state(
    authority: Mapping[str, Any],
    *,
    repository_root: Path,
) -> None:
    clean = authority["clean_implementation"]
    expected_branch = str(clean["branch"])
    implementation_commit = str(clean["git_commit"])
    if _git(repository_root, "branch", "--show-current") != expected_branch:
        raise SourceIntakeRunnerError("source_intake_repository_branch_mismatch")
    ancestor = subprocess.run(
        [
            "git",
            "merge-base",
            "--is-ancestor",
            implementation_commit,
            "HEAD",
        ],
        cwd=repository_root,
        capture_output=True,
        check=False,
        text=True,
    )
    if ancestor.returncode != 0:
        raise SourceIntakeRunnerError(
            "source_intake_implementation_commit_not_ancestor"
        )
    if _git(repository_root, "status", "--porcelain"):
        raise SourceIntakeRunnerError("source_intake_repository_not_clean")
    upstream = _git(repository_root, "rev-parse", "@{upstream}")
    head = _git(repository_root, "rev-parse", "HEAD")
    if head != upstream:
        raise SourceIntakeRunnerError("source_intake_authority_commit_not_pushed")


def _safe_repository_path(root: Path, value: str) -> Path:
    if not value or Path(value).is_absolute():
        raise SourceIntakeRunnerError("source_intake_authority_path_invalid")
    resolved = (root / value).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise SourceIntakeRunnerError("source_intake_authority_path_invalid") from exc
    return resolved


def _assert_digest(path: Path, expected: str) -> None:
    if not path.is_file() or len(expected) != 64:
        raise SourceIntakeRunnerError("source_intake_authority_digest_binding_invalid")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise SourceIntakeRunnerError("source_intake_authority_digest_mismatch")


def _write_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    body = (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    try:
        with path.open("xb") as handle:
            handle.write(body)
    except FileExistsError as exc:
        raise SourceIntakeRunnerError(
            "source_intake_public_result_already_exists"
        ) from exc


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise SourceIntakeRunnerError("source_intake_repository_state_unavailable")
    return completed.stdout.strip()


if __name__ == "__main__":
    raise SystemExit(main())
