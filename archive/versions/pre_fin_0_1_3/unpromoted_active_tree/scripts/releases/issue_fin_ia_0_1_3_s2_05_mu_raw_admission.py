from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest  # noqa: E402
from sec_agent.s2_same_evidence_experiment_runtime import (  # noqa: E402
    POLICY_REF,
    issue_case_admission,
    load_frozen_blind_inputs,
    load_runtime_policy,
)


DECISION_REF = (
    "configs/releases/"
    "fin_ia_0_1_3_s2_05_mu_raw_experiment_a_authority_v1_0.json"
)
CAMPAIGN_GUARD_REF = (
    "configs/releases/"
    "fin_ia_0_1_3_s2_06_dell_supervision_boundary_and_campaign_disposition_v1_0.json"
)
RUNNER_REF = "src/sec_agent/s2_same_evidence_experiment_runtime.py"
DEFAULT_AUTHORITY_ROOT = (
    ROOT / ".codex_runtime" / "fin013_s2_05" / "authorities" / "MU_RAW"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Issue one MU raw same-evidence Experiment A admission"
    )
    parser.add_argument("--authority-root", type=Path, default=DEFAULT_AUTHORITY_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    decision = _read_json(ROOT / DECISION_REF)
    campaign_guard = _read_json(ROOT / CAMPAIGN_GUARD_REF)
    _validate_decision(decision, campaign_guard)
    _validate_repository(decision)
    _validate_frozen_bindings(decision)

    policy = load_runtime_policy(ROOT)
    blind = load_frozen_blind_inputs(ROOT, policy)
    case_input = next(row for row in blind["cases"] if row["case_key"] == "MU")
    fairness = decision["fairness_guard"]
    if (
        case_input["model_visible_digest"] != fairness["MU_model_visible_digest"]
        or blind["blind_input_digest"] != fairness["frozen_blind_input_digest"]
    ):
        raise RuntimeError("experiment_a_mu_frozen_visible_input_mismatch")

    credential_env = str(policy["provider"]["api_key_env"])
    credential_present = bool(os.environ.get(credential_env, "").strip())
    issued = datetime.now(timezone.utc).replace(microsecond=0)
    expires = issued + timedelta(hours=4)
    admission = issue_case_admission(
        case_input=case_input,
        policy=policy,
        execution_git_commit=_git("rev-parse", "HEAD"),
        runner_sha256=_sha256(ROOT / RUNNER_REF),
        policy_sha256=_sha256(ROOT / POLICY_REF),
        issued_at=issued.isoformat().replace("+00:00", "Z"),
        expires_at=expires.isoformat().replace("+00:00", "Z"),
        run_nonce=secrets.token_hex(32),
        credential_present=credential_present,
    )
    output = {
        "status": "dry_run_ready_not_issued" if args.dry_run else "issued_unconsumed",
        "case_key": "MU",
        "execution_mode": "capture_first_full_chain_then_layered_evaluation",
        "run_id": admission["run_id"],
        "admission_digest": admission["admission_digest"],
        "execution_git_commit": admission["execution_git_commit"],
        "issued_at": admission["issued_at"],
        "expires_at": admission["expires_at"],
        "provider_calls": 0,
        "network_calls": 0,
        "credential_value_persisted": False,
        "DELL_correction_or_hidden_gold_read": False,
    }
    if not args.dry_run:
        authority_root = args.authority_root.resolve()
        if authority_root != DEFAULT_AUTHORITY_ROOT.resolve():
            raise RuntimeError("experiment_a_mu_authority_root_invalid")
        authority_root.mkdir(parents=True, exist_ok=True)
        if list(authority_root.glob("*.json")):
            raise RuntimeError("experiment_a_mu_admission_already_exists")
        admission_path = authority_root / f"{admission['run_id']}.json"
        with admission_path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(admission, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        try:
            os.chmod(authority_root, 0o700)
            os.chmod(admission_path, 0o600)
        except OSError:
            pass
        output["admission_ref"] = admission_path.relative_to(ROOT).as_posix()

    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _validate_decision(decision: dict[str, Any], campaign_guard: dict[str, Any]) -> None:
    body = {key: value for key, value in decision.items() if key != "decision_digest"}
    authority = decision.get("authority") or {}
    fairness = decision.get("fairness_guard") or {}
    storage = decision.get("admission_storage_boundary") or {}
    campaign = campaign_guard.get("campaign_disposition") or {}
    if (
        decision.get("decision_digest") != canonical_digest(body)
        or decision.get("status")
        != "MU_raw_admission_and_execution_authorized_not_issued"
        or authority.get("admission_issuance_authorized") is not True
        or authority.get("admission_consumption_authorized") is not True
        or authority.get("exact_live_execution_authorized") is not True
        or authority.get("maximum_new_admissions") != 1
        or authority.get("authorized_case") != "MU"
        or authority.get("maximum_provider_calls") != 12
        or authority.get("retry_count") != 0
        or authority.get("fallback_count") != 0
        or authority.get("DELL_admission_authorized") is not False
        or authority.get("NVDA_admission_authorized") is not False
        or authority.get("supervisor_correction_authorized") is not False
        or authority.get("business_promotion_authorized") is not False
        or fairness.get("same_model_visible_contract_as_DELL") is not True
        or fairness.get("DELL_correction_visible") is not False
        or fairness.get("hidden_gold_visible") is not False
        or fairness.get("model_visible_contract_changed_after_DELL_raw") is not False
        or campaign.get("DELL_raw_measurement") != "complete_quality_fail"
        or campaign.get("MU_raw_admission_may_be_considered_by_separate_authority") is not True
        or campaign.get("automatic_next_case") is not False
        or storage.get("required_root")
        != ".codex_runtime/fin013_s2_05/authorities/MU_RAW"
    ):
        raise RuntimeError("experiment_a_mu_raw_authority_invalid")


def _validate_repository(decision: dict[str, Any]) -> None:
    if _git("status", "--porcelain"):
        raise RuntimeError("experiment_a_mu_repository_not_clean")
    head = _git("rev-parse", "HEAD")
    audited = str(decision["audited_repository_state"]["head"])
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", audited, head], cwd=ROOT, check=False
    ).returncode != 0:
        raise RuntimeError("experiment_a_mu_head_not_descendant")
    upstream = _git("rev-parse", "--abbrev-ref", "@{upstream}")
    if _git("rev-list", "--left-right", "--count", f"{upstream}...HEAD").split() != ["0", "0"]:
        raise RuntimeError("experiment_a_mu_repository_not_synced")


def _validate_frozen_bindings(decision: dict[str, Any]) -> None:
    for binding in decision["frozen_bindings"].values():
        ref = str(binding.get("ref") or "")
        expected = str(binding.get("sha256") or "")
        if not ref or not expected or _sha256(ROOT / ref) != expected:
            raise RuntimeError("experiment_a_mu_frozen_binding_mismatch")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("experiment_a_mu_decision_json_invalid")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


if __name__ == "__main__":
    raise SystemExit(main())
