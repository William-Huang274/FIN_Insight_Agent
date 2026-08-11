from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.official_source_attempt_program import UrllibOfficialSourceTransport  # noqa: E402
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.s1_08_candidate_generation_runtime import load_source_catalog  # noqa: E402
from sec_agent.s1_08_r3_successor import (  # noqa: E402
    DellSearchR3Admission,
    R3AuthorityInputs,
    execute_dell_search_r3,
    project_os_preflight_passed,
    sha256_file,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger  # noqa: E402


CATALOG_PATH = REPO_ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_current_source_catalog_relationship_budget_policy_v3_0.json"
DECISION_PATH = REPO_ROOT / "configs/releases/fin_ia_0_1_3_s1_08_v3_dell_r3_fresh_live_authority_decision_v1_0.json"
V3_PROOF_PATH = REPO_ROOT / "configs/releases/fin_ia_0_1_3_s1_08_v3_clean_independent_zero_call_proof_result_v1_0.json"
R2_RESULT_PATH = REPO_ROOT / "configs/releases/fin_ia_0_1_3_s1_08_dell_current_search_r2_result_v1_0.json"
R2_QUALITY_PATH = REPO_ROOT / "configs/releases/fin_ia_0_1_3_s1_08_dell_current_search_r2_source_quality_evaluation_v1_0.json"
PREDECESSOR_PREFLIGHT_PATH = REPO_ROOT / "configs/releases/fin_ia_0_1_3_s1_08_v3_dell_r3_successor_clean_zero_call_preflight_v1_1.json"
SUCCESSOR_PREFLIGHT_PATH = REPO_ROOT / "configs/releases/fin_ia_0_1_3_s1_08_v3_dell_r3_successor_clean_zero_call_preflight_v1_2.json"
DEFAULT_OUTPUT = REPO_ROOT / "configs/releases/fin_ia_0_1_3_s1_08_v3_dell_current_search_r3_result_v1_0.json"
RUNTIME_PATH = REPO_ROOT / "src/sec_agent/s1_08_r3_successor.py"
RUN_SCOPE = "S1_08_V3_DELL_R3_EXACT_LIVE_ISSUANCE_AND_EXECUTION"
RESEARCH_OBJECTIVE = (
    "Evaluate Dell AI infrastructure demand durability, value and profit capture, "
    "supply-chain constraints, customer deployment evidence, counterevidence and "
    "what would change the investment judgment as of 2026-08-06."
)
EMAIL_RE = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.IGNORECASE)
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
PROVEN_RUNTIME_TREE_PATHS = (
    "src",
    "scripts",
    "configs/runtime",
    "pyproject.toml",
    "requirements*.txt",
)


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True).strip()


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _v3_implementation_bindings(proof: dict) -> dict[str, str]:
    return dict((proof.get("source_bindings") or {}).get("implementation_files") or {})


def _verify_v3_implementation_bindings(proof: dict) -> dict[str, str]:
    bindings = _v3_implementation_bindings(proof)
    if not bindings:
        raise SystemExit("S1-08 R3 requires v3 implementation source bindings")
    observed = {ref: sha256_file(REPO_ROOT / ref) for ref in bindings}
    if observed != bindings:
        raise SystemExit("S1-08 R3 v3 implementation source drift detected")
    return observed


def _assert_proven_source_ancestry_and_runtime_tree(
    *,
    proven_source_commit: str,
    execution_commit: str,
) -> None:
    if not COMMIT_RE.fullmatch(proven_source_commit) or not COMMIT_RE.fullmatch(
        execution_commit
    ):
        raise SystemExit("S1-08 R3 requires full Git commit identities")
    try:
        _git("merge-base", "--is-ancestor", proven_source_commit, execution_commit)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            "S1-08 R3 execution commit must descend from the proven source commit"
        ) from exc
    drift = _git(
        "diff",
        "--name-only",
        f"{proven_source_commit}..{execution_commit}",
        "--",
        *PROVEN_RUNTIME_TREE_PATHS,
    )
    if drift:
        raise SystemExit(
            "S1-08 R3 proven Runtime tree drift detected after clean preflight: "
            + drift.replace("\n", ", ")
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run exact-once FIN 0.1.3 S1-08 v3 DELL R3."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if _git("status", "--porcelain"):
        raise SystemExit("S1-08 R3 requires a clean Git worktree")
    if args.output.exists():
        raise SystemExit("S1-08 R3 output already exists; exact-once rerun is forbidden")
    required = (
        CATALOG_PATH,
        DECISION_PATH,
        V3_PROOF_PATH,
        R2_RESULT_PATH,
        R2_QUALITY_PATH,
        SUCCESSOR_PREFLIGHT_PATH,
        PREDECESSOR_PREFLIGHT_PATH,
        RUNTIME_PATH,
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit(f"S1-08 R3 required bound inputs missing: {missing}")
    upstream_delta = _git("rev-list", "--left-right", "--count", "HEAD...@{upstream}")
    if upstream_delta not in {"0\t0", "0 0"}:
        raise SystemExit(f"S1-08 R3 requires a synced branch, got {upstream_delta}")
    contact = str(os.environ.get("FINSIGHT_SEC_CONTACT_EMAIL") or "").strip()
    if not EMAIL_RE.fullmatch(contact):
        raise SystemExit("S1-08 R3 requires a valid runtime SEC contact identity")
    preflight = run_project_os_preflight(REPO_ROOT, run_scope=RUN_SCOPE)
    if not project_os_preflight_passed(preflight):
        raise SystemExit("S1-08 R3 Project OS preflight failed")

    catalog = load_source_catalog(CATALOG_PATH)
    decision = _load(DECISION_PATH)
    proof = _load(V3_PROOF_PATH)
    r2_result = _load(R2_RESULT_PATH)
    r2_quality = _load(R2_QUALITY_PATH)
    successor_preflight = _load(SUCCESSOR_PREFLIGHT_PATH)
    predecessor_preflight_sha = sha256_file(PREDECESSOR_PREFLIGHT_PATH)
    if predecessor_preflight_sha != str(
        (successor_preflight.get("predecessor_preflight") or {}).get("sha256") or ""
    ):
        raise SystemExit("S1-08 R3 predecessor clean proof binding invalid")
    implementation_bindings = _verify_v3_implementation_bindings(proof)
    decision_sha = sha256_file(DECISION_PATH)
    proof_sha = sha256_file(V3_PROOF_PATH)
    r2_result_sha = sha256_file(R2_RESULT_PATH)
    r2_quality_sha = sha256_file(R2_QUALITY_PATH)
    catalog_sha = sha256_file(CATALOG_PATH)
    runtime_sha = sha256_file(RUNTIME_PATH)
    runner_sha = sha256_file(Path(__file__))
    head = _git("rev-parse", "HEAD")
    proven_source_commit = str(successor_preflight.get("source_commit") or "")
    _assert_proven_source_ancestry_and_runtime_tree(
        proven_source_commit=proven_source_commit,
        execution_commit=head,
    )
    branch = _git("branch", "--show-current")
    started = _utc_now()
    bound_inputs = R3AuthorityInputs(
        authority_decision=decision,
        authority_decision_sha256=decision_sha,
        v3_proof=proof,
        v3_proof_sha256=proof_sha,
        r2_result=r2_result,
        r2_result_sha256=r2_result_sha,
        r2_quality_evaluation=r2_quality,
        r2_quality_evaluation_sha256=r2_quality_sha,
        catalog=catalog,
        catalog_sha256=catalog_sha,
        v3_implementation_source_sha256=implementation_bindings,
    )
    admission = DellSearchR3Admission.issue(
        bound_inputs=bound_inputs,
        successor_preflight=successor_preflight,
        successor_runtime_sha256=runtime_sha,
        successor_runner_sha256=runner_sha,
        implementation_commit=proven_source_commit,
        run_nonce=f"dell-current-search-r3-{started:%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex}",
        issued_at=_iso(started),
        expires_at=_iso(started + timedelta(hours=2)),
    )
    runtime_root = (
        REPO_ROOT
        / ".codex_runtime/fin013_s1_08_v3_dell_current_search_r3"
        / admission.admission_id
    )
    ledger = SharedAdmissionConsumptionLedger(
        REPO_ROOT / ".codex_runtime/shared/fin013_s1_08_admissions.sqlite3"
    )
    # This only enables Codex's synthetic proxy range. Resolution and every source
    # network side effect remain after the shared exact-once reservation.
    os.environ["FINSIGHT_ALLOW_SYNTHETIC_DNS"] = "1"
    result = execute_dell_search_r3(
        admission=admission,
        bound_inputs=bound_inputs,
        catalog_path=CATALOG_PATH,
        successor_preflight=successor_preflight,
        successor_runtime_sha256=runtime_sha,
        successor_runner_sha256=runner_sha,
        runtime_root=runtime_root,
        shared_admission_ledger=ledger,
        transport=UrllibOfficialSourceTransport(),
        implementation_commit=proven_source_commit,
        research_objective=RESEARCH_OBJECTIVE,
        observed_at=_iso(started),
        market_snapshot=None,
    )
    payload = {
        "schema_version": "fin_ia_0_1_3_s1_08_v3_dell_current_search_r3_result_v1_0",
        "status": result["status"],
        "git": {"branch": branch, "commit": head, "clean_and_synced_at_start": True},
        "proven_source_commit": proven_source_commit,
        "project_os_preflight": {
            "status": "pass",
            "run_scope": RUN_SCOPE,
            "open_full_chain_blocker_count": 0,
        },
        "runtime_identity": {
            "SEC_contact_configured": True,
            "SEC_contact_plaintext_persisted": False,
            "synthetic_dns_allowlist_enabled": True,
        },
        "result": result,
        "known_boundary": (
            "This R3 measures DELL v3 live candidate generation only. It does not "
            "admit ranking, MU/NVDA, DeepSeek, S3, report quality or release."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "phase": result["phase"],
                "code": result["code"],
                "network_calls": result["observed_counts"]["network_calls"],
                "output": str(args.output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
