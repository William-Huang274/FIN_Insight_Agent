from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
import uuid


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.s3_dell_value_profit_repair_canary import (  # noqa: E402
    _normalized_text_sha256,
    compile_repair_canary_material,
    load_repair_canary_policy,
)
from sec_agent.s3_dell_value_profit_repair_canary_live import (  # noqa: E402
    LIVE_SCOPE,
    credential_presence_only,
    issue_live_canary_admission,
    validate_live_canary_issuance,
)


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s3_dell_value_profit_current_pack_"
    "repair_canary_policy_v1_0.json"
)
DECISION_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s3_dell_value_profit_repair_canary_"
    "live_value_cost_risk_authority_decision_v1_0.json"
)
PROOF_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s3_dell_value_profit_current_pack_repair_canary_"
    "clean_independent_proof_v1_0.json"
)
OUTPUT_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s3_dell_value_profit_repair_canary_"
    "live_admission_issuance_v1_0.json"
)
SOURCE_REFS = (
    "configs/runtime/fin_ia_project_os_run_scope_registry_v1_0.json",
    "configs/runtime/fin_ia_0_1_3_s3_dell_value_profit_current_pack_repair_canary_policy_v1_0.json",
    "configs/runtime/fin_ia_0_1_3_s2_deepseek_v4_pro_fixed_pack_profile_v1_0.json",
    "configs/releases/fin_ia_0_1_3_s3_dell_value_profit_current_pack_repair_canary_minimum_zero_call_implementation_v1_0.json",
    "configs/releases/fin_ia_0_1_3_s3_dell_value_profit_current_pack_repair_canary_clean_independent_proof_v1_0.json",
    "configs/releases/fin_ia_0_1_3_s3_dell_value_profit_repair_canary_live_value_cost_risk_authority_decision_v1_0.json",
    "src/sec_agent/s3_dell_value_profit_repair_canary.py",
    "src/sec_agent/s3_dell_value_profit_repair_canary_live.py",
    "scripts/releases/issue_fin_ia_0_1_3_s3_dell_value_profit_repair_canary_live_admission.py",
    "scripts/releases/run_fin_ia_0_1_3_s3_dell_value_profit_repair_canary_live.py",
)


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
        raise RuntimeError("s3_live_canary_issuance_requires_clean_worktree")
    head = _git("rev-parse", "HEAD")
    if head != _git("rev-parse", "@{upstream}"):
        raise RuntimeError("s3_live_canary_issuance_requires_synced_head")
    return head


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("s3_live_canary_issuance_json_invalid")
    return value


def main() -> int:
    if OUTPUT_PATH.exists():
        raise RuntimeError("s3_live_canary_issuance_already_exists")
    head = _require_clean_synced()
    policy = load_repair_canary_policy(POLICY_PATH, repo_root=ROOT)
    material = compile_repair_canary_material(policy=policy, repo_root=ROOT)
    decision = _load(DECISION_PATH)
    proof = _load(PROOF_PATH)
    preflight = run_project_os_preflight(ROOT, run_scope=LIVE_SCOPE)
    if preflight.get("status") != "pass":
        raise RuntimeError(
            "s3_live_canary_issuance_project_os_blocked:"
            + json.dumps(preflight.get("errors") or [], ensure_ascii=False)
        )
    credential = credential_presence_only(profile=material["profile"])
    if credential["credential_present"] is not True:
        raise RuntimeError("s3_live_canary_issuance_credential_missing")
    source_bindings = [
        {
            "ref": ref,
            "normalized_text_sha256": _normalized_text_sha256(ROOT / ref),
        }
        for ref in SOURCE_REFS
    ]
    now = datetime.now(timezone.utc).replace(microsecond=0)
    issued_at = now.isoformat().replace("+00:00", "Z")
    expires_at = (now + timedelta(hours=24)).isoformat().replace("+00:00", "Z")
    issuance = issue_live_canary_admission(
        decision=decision,
        clean_proof=proof,
        material=material,
        implementation_commit=head,
        source_bindings=source_bindings,
        project_os_preflight=preflight,
        credential_preflight=credential,
        issued_at=issued_at,
        expires_at=expires_at,
        run_nonce=uuid.uuid4().hex,
        user_authority=(
            "User authorized the approved six-step sequence and allowed bounded "
            "blocker repairs within it. This record issues one fresh admission but "
            "does not authorize or start the Provider call."
        ),
    )
    validate_live_canary_issuance(
        issuance,
        decision=decision,
        clean_proof=proof,
        material=material,
        project_os_preflight=preflight,
        repo_root=ROOT,
        observed_at=issued_at,
    )
    temporary = OUTPUT_PATH.with_suffix(OUTPUT_PATH.suffix + ".tmp")
    temporary.write_text(
        json.dumps(issuance, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(OUTPUT_PATH)
    print(
        json.dumps(
            {
                "status": issuance["status"],
                "run_scope": LIVE_SCOPE,
                "run_id": issuance["admission"]["run_id"],
                "admission_digest": issuance["admission"]["admission_digest"],
                "credential_present": True,
                "credential_value_read_output_or_persisted": False,
                "provider_calls": 0,
                "model_calls": 0,
                "execution_authorized": False,
                "issuance_digest": issuance["issuance_digest"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
