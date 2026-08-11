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
from sec_agent.s1_08_r2_successor import (  # noqa: E402
    DellSearchR2Admission,
    execute_dell_search_r2,
    project_os_preflight_passed,
    sha256_file,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger  # noqa: E402


CATALOG_PATH = REPO_ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_current_source_catalog_and_query_revision_policy_v2_0.json"
DECISION_PATH = REPO_ROOT / "configs/releases/fin_ia_0_1_3_s1_08q_h_dell_r2_replacement_authority_decision_v1_1.json"
PROOF_PATH = REPO_ROOT / "configs/releases/fin_ia_0_1_3_s1_08_quality_first_sourcehunter_capture_replay_independent_fresh_proof_v1_0.json"
SUCCESSOR_PREFLIGHT_PATH = REPO_ROOT / "configs/releases/fin_ia_0_1_3_s1_08_dell_r2_successor_clean_zero_call_preflight_v1_1.json"
R1_RESULT_PATH = REPO_ROOT / "configs/releases/fin_ia_0_1_3_s1_08_dell_current_search_canary_result_v1_0.json"
DEFAULT_OUTPUT = REPO_ROOT / "configs/releases/fin_ia_0_1_3_s1_08_dell_current_search_r2_result_v1_0.json"
RUN_SCOPE = "S1_08_DELL_R2_exact_live_issuance_and_execution"
RESEARCH_OBJECTIVE = (
    "Evaluate Dell AI infrastructure demand durability, value and profit capture, "
    "supply-chain constraints, customer deployment evidence, counterevidence and "
    "what would change the investment judgment as of 2026-08-06."
)
EMAIL_RE = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.IGNORECASE)


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True).strip()


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run exact-once FIN 0.1.3 S1-08 DELL R2.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if _git("status", "--porcelain"):
        raise SystemExit("S1-08 R2 requires a clean Git worktree")
    if args.output.exists():
        raise SystemExit("S1-08 R2 output already exists; exact-once rerun is forbidden")
    if not R1_RESULT_PATH.is_file():
        raise SystemExit("S1-08 R2 requires the immutable R1 terminal result")
    upstream_delta = _git("rev-list", "--left-right", "--count", "HEAD...@{upstream}")
    if upstream_delta not in {"0\t0", "0 0"}:
        raise SystemExit(f"S1-08 R2 requires a synced branch, got {upstream_delta}")
    contact = str(os.environ.get("FINSIGHT_SEC_CONTACT_EMAIL") or "").strip()
    if not EMAIL_RE.fullmatch(contact):
        raise SystemExit("S1-08 R2 requires a valid runtime SEC contact identity")
    preflight = run_project_os_preflight(REPO_ROOT, run_scope=RUN_SCOPE)
    if not project_os_preflight_passed(preflight):
        raise SystemExit("S1-08 R2 Project OS preflight failed")

    catalog = load_source_catalog(CATALOG_PATH)
    decision = _load(DECISION_PATH)
    proof = _load(PROOF_PATH)
    successor_preflight = _load(SUCCESSOR_PREFLIGHT_PATH)
    r1_result = _load(R1_RESULT_PATH)
    proof_sha = sha256_file(PROOF_PATH)
    runtime_sha = sha256_file(REPO_ROOT / "src/sec_agent/s1_08_r2_successor.py")
    runner_sha = sha256_file(Path(__file__))
    head = _git("rev-parse", "HEAD")
    branch = _git("branch", "--show-current")
    started = _utc_now()
    admission = DellSearchR2Admission.issue(
        authority_decision=decision,
        independent_proof=proof,
        independent_proof_sha256=proof_sha,
        successor_preflight=successor_preflight,
        successor_runtime_sha256=runtime_sha,
        successor_runner_sha256=runner_sha,
        r1_result=r1_result,
        catalog=catalog,
        implementation_commit=head,
        run_nonce=f"dell-current-search-r2-{started:%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex}",
        issued_at=_iso(started),
        expires_at=_iso(started + timedelta(hours=2)),
    )
    runtime_root = REPO_ROOT / ".codex_runtime/fin013_s1_08_dell_current_search_r2" / admission.admission_id
    ledger = SharedAdmissionConsumptionLedger(
        REPO_ROOT / ".codex_runtime/shared/fin013_s1_08_admissions.sqlite3"
    )
    # Enabling this does not resolve DNS or permit arbitrary private addresses. The
    # transport still accepts only Codex's 198.18.0.0/15 synthetic proxy range and
    # performs resolution after the exact-once reservation inside execute().
    os.environ["FINSIGHT_ALLOW_SYNTHETIC_DNS"] = "1"
    result = execute_dell_search_r2(
        admission=admission,
        authority_decision=decision,
        independent_proof=proof,
        independent_proof_sha256=proof_sha,
        successor_preflight=successor_preflight,
        successor_runtime_sha256=runtime_sha,
        successor_runner_sha256=runner_sha,
        r1_result=r1_result,
        catalog_path=CATALOG_PATH,
        runtime_root=runtime_root,
        shared_admission_ledger=ledger,
        transport=UrllibOfficialSourceTransport(),
        implementation_commit=head,
        research_objective=RESEARCH_OBJECTIVE,
        observed_at=_iso(started),
        market_snapshot=None,
    )
    payload = {
        "schema_version": "fin_ia_0_1_3_s1_08_dell_current_search_r2_result_v1_0",
        "status": result["status"],
        "git": {"branch": branch, "commit": head, "clean_and_synced_at_start": True},
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
            "This R2 measures DELL live candidate generation only. It does not admit "
            "ranking, MU/NVDA, DeepSeek, S3, report quality or release."
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
