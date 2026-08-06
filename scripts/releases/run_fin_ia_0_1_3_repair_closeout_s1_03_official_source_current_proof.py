from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.official_source_attempt_program import (
    OfficialSourceExecutionAuthority,
    UrllibOfficialSourceTransport,
    compile_official_source_attempt_program,
    load_official_source_policy,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


DEFAULT_POLICY = ROOT / (
    "configs/runtime/fin_ia_0_1_3_repair_closeout_"
    "official_source_attempt_policy_v1_0.json"
)


def _utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--shared-ledger", type=Path, required=True)
    parser.add_argument("--result-output", type=Path, required=True)
    parser.add_argument("--run-nonce", required=True)
    args = parser.parse_args()

    policy = load_official_source_policy(args.policy)
    issued = datetime.now(timezone.utc)
    observed_at = _utc(issued)
    authority = OfficialSourceExecutionAuthority.issue(
        policy=policy,
        run_nonce=args.run_nonce,
        issued_at=observed_at,
        expires_at=_utc(issued + timedelta(minutes=30)),
    )
    ledger = SharedAdmissionConsumptionLedger(args.shared_ledger)
    result = compile_official_source_attempt_program(
        policy=policy,
        runtime_root=args.runtime_root,
        transport=UrllibOfficialSourceTransport(),
        authority=authority,
        shared_admission_ledger=ledger,
        observed_at=observed_at,
    )
    receipt = ledger.read(authority.admission_digest).as_dict()
    output = {
        "authority": authority.as_dict(),
        "result": result,
        "shared_admission_receipt": receipt,
    }
    args.result_output.parent.mkdir(parents=True, exist_ok=True)
    args.result_output.write_text(
        json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "authority": authority.as_dict(),
                "counts": result["observed_counts"],
                "case_summaries": [
                    {"case_key": row["case_key"], **row["summary"]}
                    for row in result["case_results"]
                ],
                "receipt_state": receipt["state"],
                "program_digest": result["program_digest"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
