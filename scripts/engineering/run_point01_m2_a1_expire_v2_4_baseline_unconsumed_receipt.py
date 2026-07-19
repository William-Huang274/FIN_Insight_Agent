"""Append the sole allowed terminal state for the expired v2.4 JIT receipt.

This utility is deliberately hard-bound to RC-P38-024's incident receipt.  It
cannot register, consume, renew, or mutate any other authority object.  The
only persistent write is the append-only ``EXPIRED_UNCONSUMED`` event plus the
receipt row's terminal state; the original receipt payload remains untouched.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
ADMISSION_PATH = ROOT / "data/manifests/point01_m2_a1_external_package_admission_v2_4_baseline_jit.json"
RECEIPT_PATH = ROOT / "data/manifests/point01_m2_a1_single_use_execution_receipt_v2_4_baseline_jit.json"
INCIDENT_PATH = ROOT / "data/manifests/point01_m2_a1_v2_4_baseline_jit_dispatch_incident.json"
OUTPUT_PATH = ROOT / "data/manifests/point01_m2_a1_v2_4_baseline_jit_expired_unconsumed_terminal.json"
PACKAGE_DIGEST = "615a73da64eff69a56a13b42d6c59c892820f15c4de7dc3a2be3c425d2aee68e"
ADMISSION_DIGEST = "1906d86bb5a419cceaa3a83cf27ef5ca5cd85e23b263a6818db322d22c7f054c"
RECEIPT_DIGEST = "596fcf570a7abc1d4344ec6db354a4670e1c8a59e48f97396d5bf27c2401b870"
INCIDENT_DIGEST = "a59076a127c0b76902dc362aee94980427660fbc695b47e9c94fd73228cb9a18"
RECEIPT_ID = "point01-m2-a1-v2-4-baseline-fe9658d04ca515924c568123"
SCENARIO_ID = "p01-baseline-separated-input"
NAMESPACE = Path("D:/temp/FIN_Insight_Agent/point01_m2_a1_exact_admitted_runs_v2_4")


def _load(path: Path) -> Mapping[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, Mapping):
        raise RuntimeError(f"m2_a1_expiry_terminal_mapping_required:{path}")
    return loaded


def main() -> int:
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from sec_agent.canonical_runtime.m2_a1_execution_receipt import (
        M2A1ExternalPackageAdmission,
        M2A1ReceiptLedger,
    )
    from sec_agent.canonical_runtime.models import canonical_digest

    admission_payload = _load(ADMISSION_PATH)
    receipt_payload = _load(RECEIPT_PATH)
    incident = _load(INCIDENT_PATH)
    if (
        admission_payload.get("admission_digest") != ADMISSION_DIGEST
        or receipt_payload.get("receipt_digest") != RECEIPT_DIGEST
        or receipt_payload.get("receipt_id") != RECEIPT_ID
        or incident.get("incident_digest") != INCIDENT_DIGEST
        or incident.get("admission_digest") != ADMISSION_DIGEST
        or incident.get("receipt_digest") != RECEIPT_DIGEST
        or incident.get("package_digest") != PACKAGE_DIGEST
    ):
        raise RuntimeError("m2_a1_expiry_terminal_exact_historical_binding_mismatch")
    admission = M2A1ExternalPackageAdmission.model_validate(admission_payload)
    run_id = hashlib.sha256(f"{PACKAGE_DIGEST}:{ADMISSION_DIGEST}:{RECEIPT_ID}".encode("utf-8")).hexdigest()
    authority_root = NAMESPACE / run_id / "authority"
    ledger = M2A1ReceiptLedger.open_existing(
        authority_root / "m2_a1_execution_receipts.sqlite",
        approved_authority_root=authority_root,
    )
    terminal = ledger.expire_unconsumed_exact(
        RECEIPT_ID,
        admission=admission,
        executable_package_digest=PACKAGE_DIGEST,
        scenario_id=SCENARIO_ID,
    )
    payload = {
        "schema_version": "finsight_point01_m2_a1_v2_4_expired_unconsumed_terminal_v1",
        "status": terminal["terminal_status"],
        "incident_digest": INCIDENT_DIGEST,
        "package_digest": PACKAGE_DIGEST,
        "admission_digest": ADMISSION_DIGEST,
        "receipt_id": RECEIPT_ID,
        "receipt_digest": terminal["receipt_digest"],
        "terminal_event_digest": terminal["terminal_event_digest"],
        "forbidden_actions": ["consume", "renew", "replay", "delete", "payload_overwrite", "expiry_mutation"],
        "runtime_output_actual_oracle_reviewer": {"runtime": 0, "output": 0, "actual": 0, "oracle": 0, "reviewer": 0},
        "terminal_write_scope": "one_exact_existing_authority_ledger_only",
    }
    payload["expired_terminal_digest"] = canonical_digest(payload)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "expired_terminal_digest": payload["expired_terminal_digest"], "receipt_id": RECEIPT_ID}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
