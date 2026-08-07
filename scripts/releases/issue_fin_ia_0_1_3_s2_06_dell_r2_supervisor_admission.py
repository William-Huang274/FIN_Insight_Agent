from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import secrets
import sys


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from fin_ia_0_1_3_s2_06_dell_r2_supervisor_execution_support import (  # noqa: E402
    SUPERVISOR_ROOT,
    compile_governed_admission,
    load_case_material,
    validate_repository,
)


AUTHORITY_ROOT = SUPERVISOR_ROOT / "authorities" / "DELL_R2"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Issue one FIN 0.1.3 S2-06 DELL R2 Supervisor admission"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    head = validate_repository()
    material = load_case_material("DELL")
    credential_env = str(material["policy"]["provider"]["api_key_env"])
    credential_present = bool(os.environ.get(credential_env, "").strip())
    if not credential_present:
        raise RuntimeError("s2_06_dell_r2_supervisor_credential_absent")
    issued = datetime.now(timezone.utc).replace(microsecond=0)
    expires = issued + timedelta(hours=4)
    nonce = secrets.token_hex(10)
    corrected_run_id = "fin013_s2_06_supervised_dell_r2_" + nonce
    corrected_attempt_id = corrected_run_id + "_attempt_1"
    admission = compile_governed_admission(
        material=material,
        corrected_run_id=corrected_run_id,
        corrected_attempt_id=corrected_attempt_id,
        admission_id="fin013-s2-06-dell-r2-supervisor-" + secrets.token_hex(16),
        issued_at=issued.isoformat().replace("+00:00", "Z"),
        expires_at=expires.isoformat().replace("+00:00", "Z"),
        credential_present=True,
        execution_git_commit=head,
    )
    output = {
        "status": "dry_run_ready_not_issued" if args.dry_run else "issued_unconsumed",
        "case_key": "DELL",
        "replacement_attempt": "R2",
        "corrected_run_id": corrected_run_id,
        "corrected_attempt_id": corrected_attempt_id,
        "admission_digest": admission["admission_digest"],
        "execution_git_commit": head,
        "supervisor_plan_schema_version": (
            admission["governance_binding"]["supervisor_plan_schema_version"]
        ),
        "expected_provider_calls": material["capacity"]["provider_calls"],
        "provider_call_ceiling": material["capacity"]["provider_call_ceiling"],
        "retry_count": 0,
        "fallback_count": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "credential_present": True,
        "credential_value_persisted": False,
        "issued_at": admission["issued_at"],
        "expires_at": admission["expires_at"],
    }
    if not args.dry_run:
        AUTHORITY_ROOT.mkdir(parents=True, exist_ok=True)
        if list(AUTHORITY_ROOT.glob("*.json")):
            raise RuntimeError("s2_06_dell_r2_supervisor_admission_already_exists")
        path = AUTHORITY_ROOT / (corrected_run_id + ".json")
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(admission, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        try:
            os.chmod(AUTHORITY_ROOT, 0o700)
            os.chmod(path, 0o600)
        except OSError:
            pass
        output["admission_ref"] = path.relative_to(ROOT).as_posix()
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
