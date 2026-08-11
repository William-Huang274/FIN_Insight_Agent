from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.s1_dell_targeted_source_supplement import (  # noqa: E402
    AUTHORITY_SCHEMA,
    CONTRACT_REF,
    RUN_SCOPE,
    canonical_digest,
    file_sha256,
    load_dell_targeted_source_policy,
    validate_dell_targeted_source_authority,
    validate_dell_targeted_source_clean_proof,
)


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_dell_targeted_source_supplement_policy_v1_0.json"
)
PROOF_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s1_dell_targeted_source_supplement_clean_proof_v1_0.json"
)
RUNNER_PATH = ROOT / (
    "scripts/releases/"
    "run_fin_ia_0_1_3_s1_dell_targeted_source_supplement.py"
)
DEFAULT_OUTPUT = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s1_dell_targeted_source_supplement_authority_v1_0.json"
)


class IssueAuthorityError(RuntimeError):
    pass


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _require_clean_synced() -> str:
    if _git("status", "--porcelain", "--untracked-files=all"):
        raise IssueAuthorityError("issue_authority_requires_clean_worktree")
    head = _git("rev-parse", "HEAD")
    if head != _git("rev-parse", "@{upstream}"):
        raise IssueAuthorityError("issue_authority_requires_synced_head")
    return head


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--hours", type=int, default=24)
    args = parser.parse_args()
    if args.output.exists():
        raise IssueAuthorityError("issue_authority_output_already_exists")
    head = _require_clean_synced()
    policy = load_dell_targeted_source_policy(POLICY_PATH, repo_root=ROOT)
    proof = json.loads(PROOF_PATH.read_text(encoding="utf-8"))
    validate_dell_targeted_source_clean_proof(proof)
    project_os = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    if project_os.get("status") != "pass":
        raise IssueAuthorityError(
            "issue_authority_project_os_blocked:"
            + json.dumps(project_os.get("errors") or [], ensure_ascii=False)
        )
    issued = datetime.now(timezone.utc).replace(microsecond=0)
    expires = issued + timedelta(hours=args.hours)
    nonce = uuid4().hex
    run_id = "fin013_s1_dell_targeted_source_" + canonical_digest(
        {
            "implementation_commit": head,
            "policy_digest": canonical_digest(policy),
            "proof_digest": proof["proof_digest"],
            "nonce": nonce,
        }
    )[:20]
    binding_paths = (
        POLICY_PATH,
        PROOF_PATH,
        RUNNER_PATH,
        ROOT / "src/sec_agent/s1_dell_targeted_source_supplement.py",
        ROOT / "src/sec_agent/official_source_attempt_program.py",
        ROOT / "src/sec_agent/canonical_runtime/object_store.py",
        ROOT / "src/sec_agent/shared_admission_ledger.py",
    )
    body = {
        "schema_version": AUTHORITY_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "run_scope": RUN_SCOPE,
        "status": "issued_unconsumed",
        "issued_at": issued.isoformat().replace("+00:00", "Z"),
        "expires_at": expires.isoformat().replace("+00:00", "Z"),
        "implementation_commit": head,
        "user_authority": (
            "annotation_1_owner_approved_targeted_source_supplement_then_one_report_comparison"
        ),
        "admission_id": "admission::" + run_id,
        "run_id": run_id,
        "attempt_id": run_id + "::attempt_1",
        "maximum_executions": 1,
        "automatic_execution": False,
        "automatic_retry": False,
        "business_artifact_promotion": False,
        "evidence_promotion_mode": "local_deterministic_adjudication_only",
        "model_calls_allowed": 0,
        "policy_digest": canonical_digest(policy),
        "clean_proof_digest": proof["proof_digest"],
        "budget": policy["budget"],
        "synthetic_dns_proxy_allowance": (
            "host_allowlisted_https_only_for_desktop_proxy_range_198.18.0.0/15"
        ),
        "file_bindings": {
            _relative(path): file_sha256(path) for path in binding_paths
        },
        "project_os_preflight": {
            "status": project_os["status"],
            "run_scope": project_os["run_scope"],
            "open_full_chain_blocker_count": project_os[
                "open_full_chain_blocker_count"
            ],
        },
        "known_boundary": (
            "This admission authorizes exactly four public official source attempts, "
            "capture-first parsing and deterministic Evidence Pack materialization. "
            "It authorizes no model call, retry, recommendation, product promotion or release."
        ),
    }
    authority = {**body, "authority_digest": canonical_digest(body)}
    validate_dell_targeted_source_authority(
        authority,
        policy=policy,
        repo_root=ROOT,
        observed_at=body["issued_at"],
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(authority, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(authority, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
