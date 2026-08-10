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
from sec_agent.s2_fixed_pack_capture_reuse_successor import (  # noqa: E402
    compile_successor_case_input,
    load_predecessor_import_bundle,
    load_successor_contract,
)
from sec_agent.s2_fixed_pack_capture_reuse_successor_live import (  # noqa: E402
    RUN_SCOPE,
    issue_successor_authority,
    validate_clean_proof,
)
from sec_agent.s2_fixed_pack_capture_reuse_successor_runtime import (  # noqa: E402
    issue_successor_admission,
)
from sec_agent.s2_fixed_pack_research import (  # noqa: E402
    compile_six_case_model_inputs,
    load_fixed_pack_contract,
    load_fixed_pack_profile,
    load_frozen_local_packs,
)


BASE_CONTRACT_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s2_fixed_pack_research_contract_v1_0.json"
)
SUCCESSOR_CONTRACT_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s2_dell_fixed_pack_capture_reuse_successor_contract_v1_0.json"
)
PROFILE_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s2_deepseek_v4_pro_fixed_pack_profile_v1_0.json"
)
PROOF_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s2_dell_capture_reuse_successor_clean_independent_proof_v1_0.json"
)
OUTPUT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s2_dell_capture_reuse_successor_authority_v1_0.json"
)
RUNTIME_PATH = ROOT / "src/sec_agent/s2_fixed_pack_capture_reuse_successor_runtime.py"
LIVE_RUNNER_PATH = ROOT / (
    "scripts/releases/run_fin_ia_0_1_3_s2_dell_capture_reuse_successor.py"
)
IMPLEMENTATION_REFS = (
    "configs/runtime/fin_ia_project_os_run_scope_registry_v1_0.json",
    "configs/runtime/fin_ia_0_1_3_s2_fixed_pack_research_contract_v1_0.json",
    "configs/runtime/fin_ia_0_1_3_s2_dell_fixed_pack_capture_reuse_successor_contract_v1_0.json",
    "configs/runtime/fin_ia_0_1_3_s2_deepseek_v4_pro_fixed_pack_profile_v1_0.json",
    "configs/releases/fin_ia_0_1_3_s2_dell_capture_reuse_successor_clean_independent_proof_v1_0.json",
    "src/sec_agent/s2_fixed_pack_research.py",
    "src/sec_agent/s2_fixed_pack_research_runtime.py",
    "src/sec_agent/s2_fixed_pack_capture_reuse_successor.py",
    "src/sec_agent/s2_fixed_pack_capture_reuse_successor_runtime.py",
    "src/sec_agent/s2_fixed_pack_capture_reuse_successor_live.py",
    "scripts/releases/run_fin_ia_0_1_3_s2_dell_capture_reuse_successor.py",
    "scripts/releases/issue_fin_ia_0_1_3_s2_dell_capture_reuse_successor_authority.py",
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
        raise RuntimeError("fixed_pack_successor_authority_requires_clean_worktree")
    head = _git("rev-parse", "HEAD")
    if head != _git("rev-parse", "@{upstream}"):
        raise RuntimeError("fixed_pack_successor_authority_requires_synced_branch")
    return head


def _load_material() -> dict:
    base_contract = load_fixed_pack_contract(BASE_CONTRACT_PATH, repo_root=ROOT)
    profile = load_fixed_pack_profile(PROFILE_PATH)
    packs = load_frozen_local_packs(contract=base_contract, repo_root=ROOT)
    inputs, _compilation = compile_six_case_model_inputs(
        contract=base_contract,
        profile=profile,
        packs=packs,
    )
    base = next(row for row in inputs if row["case_key"] == "DELL")
    successor_contract = load_successor_contract(
        SUCCESSOR_CONTRACT_PATH, repo_root=ROOT
    )
    return {
        "profile": profile,
        "successor_case_input": compile_successor_case_input(
            base_case_input=base,
            contract=successor_contract,
            profile=profile,
        ),
        "predecessor_bundle": load_predecessor_import_bundle(
            contract=successor_contract,
            repo_root=ROOT,
        ),
    }


def main() -> int:
    if OUTPUT_PATH.exists():
        raise RuntimeError("fixed_pack_successor_authority_already_exists")
    head = _clean_synced_head()
    proof = json.loads(PROOF_PATH.read_text(encoding="utf-8"))
    validate_clean_proof(proof)
    material = _load_material()
    profile = material["profile"]
    env_name = str(profile["api_key_env"])
    if not os.environ.get(env_name, "").strip():
        raise RuntimeError("fixed_pack_successor_authority_credential_missing")
    preflight = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    if preflight.get("status") != "pass":
        raise RuntimeError(
            "fixed_pack_successor_authority_project_os_blocked:"
            + json.dumps(preflight.get("errors") or [], ensure_ascii=False)
        )
    now = datetime.now(timezone.utc).replace(microsecond=0)
    issued_at = now.isoformat().replace("+00:00", "Z")
    admission = issue_successor_admission(
        case_input=material["successor_case_input"],
        predecessor_bundle=material["predecessor_bundle"],
        profile=profile,
        execution_git_commit=head,
        runtime_sha256=file_sha256(RUNTIME_PATH),
        runner_sha256=file_sha256(LIVE_RUNNER_PATH),
        successor_contract_sha256=file_sha256(SUCCESSOR_CONTRACT_PATH),
        base_contract_sha256=file_sha256(BASE_CONTRACT_PATH),
        profile_sha256=file_sha256(PROFILE_PATH),
        issued_at=issued_at,
        expires_at=(now + timedelta(hours=4)).isoformat().replace("+00:00", "Z"),
        run_nonce=uuid.uuid4().hex,
        credential_present=True,
        execution_mode="live",
    )
    bindings = [
        {"ref": ref, "sha256": file_sha256(ROOT / ref)}
        for ref in IMPLEMENTATION_REFS
    ]
    authority = issue_successor_authority(
        admission=admission,
        clean_proof=proof,
        implementation_commit=head,
        implementation_bindings=bindings,
        project_os_preflight=preflight,
        user_authority=(
            "User authorized the frozen sequence: reuse the five immutable successful "
            "captures, authorize only the remaining eight calls, bind deterministic "
            "numeric aliases and formula traces, then run one successor exact-live."
        ),
        recorded_at=issued_at,
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
                "imported_usable_nodes": 5,
                "successor_provider_calls": 8,
                "combined_provider_attempts": 14,
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
