from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.s1_six_case_local_evidence_pack import file_sha256  # noqa: E402
from sec_agent.s2_fixed_pack_live import (  # noqa: E402
    RUN_SCOPE,
    issue_dell_canary_authority,
    load_dell_fixed_pack_material,
    validate_clean_proof,
)
from sec_agent.s2_fixed_pack_research_runtime import issue_case_admission  # noqa: E402


CONTRACT_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s2_fixed_pack_research_contract_v1_0.json"
)
PROFILE_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s2_deepseek_v4_pro_fixed_pack_profile_v1_0.json"
)
PROOF_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s2_fixed_pack_successor_clean_independent_proof_v1_1.json"
)
OUTPUT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s2_fixed_pack_dell_canary_authority_v1_0.json"
)
RUNTIME_PATH = ROOT / "src/sec_agent/s2_fixed_pack_research_runtime.py"
LIVE_RUNNER_PATH = ROOT / (
    "scripts/releases/run_fin_ia_0_1_3_s2_fixed_pack_dell_canary.py"
)
IMPLEMENTATION_REFS = (
    "configs/runtime/fin_ia_project_os_run_scope_registry_v1_0.json",
    "configs/runtime/fin_ia_0_1_3_s2_fixed_pack_research_contract_v1_0.json",
    "configs/runtime/fin_ia_0_1_3_s2_deepseek_v4_pro_fixed_pack_profile_v1_0.json",
    "configs/releases/fin_ia_0_1_3_s2_fixed_pack_successor_clean_independent_proof_v1_1.json",
    "src/sec_agent/s2_fixed_pack_research.py",
    "src/sec_agent/s2_fixed_pack_research_runtime.py",
    "src/sec_agent/s2_fixed_pack_live.py",
    "scripts/releases/run_fin_ia_0_1_3_s2_fixed_pack_dell_canary.py",
    "scripts/releases/issue_fin_ia_0_1_3_s2_fixed_pack_dell_canary_authority.py",
)


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _clean_synced_head() -> str:
    if _git("status", "--porcelain", "--untracked-files=all"):
        raise RuntimeError("fixed_pack_dell_authority_requires_clean_worktree")
    head = _git("rev-parse", "HEAD")
    if head != _git("rev-parse", "@{upstream}"):
        raise RuntimeError("fixed_pack_dell_authority_requires_synced_branch")
    return head


def main() -> int:
    if OUTPUT_PATH.exists():
        raise RuntimeError("fixed_pack_dell_authority_already_exists")
    head = _clean_synced_head()
    proof = json.loads(PROOF_PATH.read_text(encoding="utf-8"))
    validate_clean_proof(proof)
    material = load_dell_fixed_pack_material(
        repo_root=ROOT,
        contract_path=CONTRACT_PATH,
        profile_path=PROFILE_PATH,
    )
    profile = material["profile"]
    env_name = str(profile["api_key_env"])
    credential_present = bool(os.environ.get(env_name, "").strip())
    if not credential_present:
        raise RuntimeError("fixed_pack_dell_authority_credential_missing")
    preflight = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    if preflight.get("status") != "pass":
        raise RuntimeError(
            "fixed_pack_dell_authority_project_os_blocked:"
            + json.dumps(preflight.get("errors") or [], ensure_ascii=False)
        )
    now = datetime.now(timezone.utc).replace(microsecond=0)
    admission = issue_case_admission(
        case_input=material["case_input"],
        profile=profile,
        execution_git_commit=head,
        runner_sha256=file_sha256(RUNTIME_PATH),
        contract_sha256=file_sha256(CONTRACT_PATH),
        profile_sha256=file_sha256(PROFILE_PATH),
        issued_at=now.isoformat().replace("+00:00", "Z"),
        expires_at=(now + timedelta(hours=4)).isoformat().replace("+00:00", "Z"),
        run_nonce=uuid.uuid4().hex,
        credential_present=True,
        execution_mode="live",
    )
    bindings = [
        {"ref": ref, "sha256": file_sha256(ROOT / ref)}
        for ref in IMPLEMENTATION_REFS
    ]
    authority = issue_dell_canary_authority(
        admission=admission,
        clean_proof=proof,
        implementation_commit=head,
        implementation_bindings=bindings,
        project_os_preflight=preflight,
        user_authority=(
            "User approved execution of steps 1-5 without stepwise reapproval. "
            "This issuance is narrowed to one DELL fixed-pack canary after clean proof."
        ),
        recorded_at=now.isoformat().replace("+00:00", "Z"),
    )
    temporary = OUTPUT_PATH.with_suffix(OUTPUT_PATH.suffix + ".tmp")
    temporary.write_text(
        json.dumps(authority, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(OUTPUT_PATH)
    print(
        json.dumps(
            {
                "status": authority["status"],
                "case_key": authority["case_key"],
                "run_id": authority["admission"]["run_id"],
                "provider_calls": authority["execution_ceiling"]["provider_calls"],
                "credential_present": True,
                "credential_value_read_or_persisted": False,
                "authority_digest": authority["authority_digest"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
