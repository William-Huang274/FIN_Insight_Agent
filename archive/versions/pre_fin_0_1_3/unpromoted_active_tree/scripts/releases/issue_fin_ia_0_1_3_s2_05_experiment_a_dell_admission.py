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

from sec_agent.s2_same_evidence_experiment_runtime import (  # noqa: E402
    POLICY_REF,
    issue_case_admission,
    load_frozen_blind_inputs,
    load_runtime_policy,
)


DECISION_REF = (
    "configs/releases/"
    "fin_ia_0_1_3_s2_05_experiment_a_fresh_admission_authority_decision_v1_0.json"
)
EXPECTED_DECISION_DIGEST = (
    "94418ea11cbc63ac5f459fb58839f63e496846c0bfbf855907f8055a4dbec17a"
)
RUNNER_REF = "src/sec_agent/s2_same_evidence_experiment_runtime.py"
DEFAULT_AUTHORITY_ROOT = (
    ROOT / ".codex_runtime" / "fin013_s2_05" / "authorities" / "DELL"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Issue the single authorized FIN 0.1.3 S2-05 DELL admission"
    )
    parser.add_argument("--authority-root", type=Path, default=DEFAULT_AUTHORITY_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    decision = _read_json(ROOT / DECISION_REF)
    _validate_decision(decision)
    _validate_repository(decision)
    _validate_frozen_bindings(decision)

    policy = load_runtime_policy(ROOT)
    blind = load_frozen_blind_inputs(ROOT, policy)
    case_input = next(row for row in blind["cases"] if row["case_key"] == "DELL")
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
        "case_key": "DELL",
        "run_id": admission["run_id"],
        "admission_digest": admission["admission_digest"],
        "execution_git_commit": admission["execution_git_commit"],
        "issued_at": admission["issued_at"],
        "expires_at": admission["expires_at"],
        "provider_calls": 0,
        "network_calls": 0,
        "credential_value_persisted": False,
    }
    if not args.dry_run:
        authority_root = args.authority_root.resolve()
        expected_parent = DEFAULT_AUTHORITY_ROOT.parent.resolve()
        if authority_root.parent != expected_parent or authority_root.name != "DELL":
            raise RuntimeError("experiment_a_authority_root_invalid")
        authority_root.mkdir(parents=True, exist_ok=True)
        existing = list(authority_root.glob("*.json"))
        if existing:
            raise RuntimeError("experiment_a_DELL_admission_already_exists")
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


def _validate_decision(decision: dict[str, Any]) -> None:
    authority = decision.get("authority") or {}
    storage = decision.get("admission_storage_boundary") or {}
    if (
        decision.get("decision_digest") != EXPECTED_DECISION_DIGEST
        or decision.get("status")
        != "DELL_admission_issuance_authorized_not_issued_execution_not_authorized"
        or authority.get("admission_issuance_authorized") is not True
        or authority.get("maximum_new_admissions") != 1
        or authority.get("authorized_case") != "DELL"
        or storage.get("required_root")
        != ".codex_runtime/fin013_s2_05/authorities/DELL"
    ):
        raise RuntimeError("experiment_a_admission_authority_decision_invalid")


def _validate_repository(decision: dict[str, Any]) -> None:
    if _git("status", "--porcelain"):
        raise RuntimeError("experiment_a_admission_repository_not_clean")
    head = _git("rev-parse", "HEAD")
    audited = str(decision["audited_repository_state"]["head"])
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", audited, head],
        cwd=ROOT,
        check=False,
    )
    if ancestor.returncode != 0:
        raise RuntimeError("experiment_a_admission_head_not_descendant")
    upstream = _git("rev-parse", "--abbrev-ref", "@{upstream}")
    counts = _git("rev-list", "--left-right", "--count", f"{upstream}...HEAD")
    if counts.split() != ["0", "0"]:
        raise RuntimeError("experiment_a_admission_repository_not_synced")


def _validate_frozen_bindings(decision: dict[str, Any]) -> None:
    for binding in decision["frozen_bindings"].values():
        ref = binding.get("ref")
        expected = binding.get("sha256")
        if not ref or not expected or _sha256(ROOT / str(ref)) != expected:
            raise RuntimeError("experiment_a_admission_frozen_binding_mismatch")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("experiment_a_admission_decision_json_invalid")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


if __name__ == "__main__":
    raise SystemExit(main())
