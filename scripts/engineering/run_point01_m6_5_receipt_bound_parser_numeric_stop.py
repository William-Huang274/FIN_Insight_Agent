"""Persist M6.5's no-parser/no-numeric terminal outcome for the bounded pilot."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.canonical_runtime.facade import RuntimeFacade
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.canonical_runtime.receipt_bound_parser_numeric_stop import (
    ReceiptBoundParserNumericStopError,
    ReceiptBoundParserNumericStopPolicy,
    ReceiptBoundParserNumericStopService,
)
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore


POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m6_5_receipt_bound_parser_numeric_stop_policy_v1_0.json"
M6_2_RUNNER_PATH = ROOT / "scripts/engineering/run_point01_m6_2_real_bounded_sec_metadata_pilot.py"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m6_5_receipt_bound_parser_numeric_stop_result_v1_0.json"
DEFAULT_STORE_ROOT = ROOT / ".tmp_point01_m6_2_real_bounded_sec_metadata_pilot"

SPEC = importlib.util.spec_from_file_location("point01_m6_2_pilot_for_m6_5", M6_2_RUNNER_PATH)
assert SPEC and SPEC.loader
M6_2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M6_2)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _policy() -> ReceiptBoundParserNumericStopPolicy:
    raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    return ReceiptBoundParserNumericStopPolicy.model_validate(
        {field: raw[field] for field in ReceiptBoundParserNumericStopPolicy.model_fields}
    )


def build_result(
    *,
    store_root: Path,
    candidate_bundle_version_ref: str,
    repair_ticket_version_ref: str,
) -> dict[str, Any]:
    policy = _policy()
    fixed_inputs = {
        "configs/engineering_handoff/point01_m6_5_receipt_bound_parser_numeric_stop_policy_v1_0.json": _sha256(POLICY_PATH),
        "scripts/engineering/run_point01_m6_5_receipt_bound_parser_numeric_stop.py": _sha256(Path(__file__).resolve()),
        "src/sec_agent/canonical_runtime/receipt_bound_parser_numeric_stop.py": _sha256(ROOT / "src/sec_agent/canonical_runtime/receipt_bound_parser_numeric_stop.py"),
        "src/sec_agent/canonical_runtime/receipt_bound_repair_ticket.py": _sha256(ROOT / "src/sec_agent/canonical_runtime/receipt_bound_repair_ticket.py"),
        "src/sec_agent/canonical_runtime/receipt_bound_candidate_bundle.py": _sha256(ROOT / "src/sec_agent/canonical_runtime/receipt_bound_candidate_bundle.py"),
    }
    common = {
        "result_version": "finsight_point01_m6_5_receipt_bound_parser_numeric_stop_result_v1_0",
        "scope": "exact_m6_3_m6_4_receipt_chain_to_no_parser_no_numeric_terminal_stop_only",
        "approval_ref": policy.approval_ref,
        "candidate_bundle_version_ref": candidate_bundle_version_ref,
        "repair_ticket_version_ref": repair_ticket_version_ref,
        "fixed_input_sha256": fixed_inputs,
        "authority_boundary": {
            "new_network_or_tool_execution": False,
            "new_external_call_count": 0,
            "repair_attempt_execution": False,
            "fallback_or_retry": False,
            "parser_execution": False,
            "numeric_fact_or_trace_creation": False,
            "evidence_promotion": False,
            "writer_domain_judgment_full_chain": False,
            "business_case_mutation": False,
            "legacy_authority_change": False,
        },
    }
    if not (store_root / "canonical.sqlite").exists():
        return {**common, "status": "fail_closed", "reason": "pilot_store_not_found", "external_call_count": 0, "store_write_count": 0}
    facade = RuntimeFacade(
        SQLiteCanonicalStore(store_root / "canonical.sqlite"),
        FileCanonicalObjectStore(store_root / "objects"),
        M6_2._flags(),
        mode="shadow",
        grants={"point01.shadow.write"},
    )
    request = M6_2._request()
    command = M6_2._command(
        "PERSIST_M6_5_RECEIPT_BOUND_PARSER_NUMERIC_STOP",
        {"work_unit_id": "wu-point01-m6-sec-pilot", "attempt_id": "attempt-point01-m6-sec-pilot-1", "worker_ref": "worker-point01-m6-sec-pilot", "lease_fencing_token": 1},
        idem="persist-receipt-parser-numeric-stop",
        expected=1,
    )
    try:
        result = ReceiptBoundParserNumericStopService(facade=facade, policy=policy).persist(
            command=command,
            request=request,
            candidate_bundle_version_ref=candidate_bundle_version_ref,
            repair_ticket_version_ref=repair_ticket_version_ref,
        )
    except (ReceiptBoundParserNumericStopError, ValueError, RuntimeError) as exc:
        return {
            **common,
            "status": "fail_closed",
            "reason": str(exc),
            "store_identity": facade.store.store_identity(),
            "external_call_count": 0,
            "store_write_count": 0,
        }
    stop = result.version.stop
    return {
        **common,
        "status": "pass",
        "store_identity": facade.store.store_identity(),
        "store_content_fingerprint": facade.store.content_fingerprint(),
        "parser_numeric_stop_version": result.version.model_dump(mode="json"),
        "parser_numeric_stop": stop.model_dump(mode="json"),
        "reused_idempotent_result": result.reused_idempotent_result,
        "external_call_count": 0,
        "store_write_count": 0 if result.reused_idempotent_result else 1,
        "boundary": "No parser, OCR, table read, ParserCandidate, NormalizedNumericFact or NumericProgramTrace was created. This is a durable typed stop, not Evidence, Writer output, Domain Judgment or a full-chain result.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Persist a terminal Point01 M6.5 receipt-bound parser/numeric stop.")
    parser.add_argument("--candidate-bundle-ref", required=True, help="Exact M6.3 CandidateBundle version, for example candidate_bundle_x:v1.")
    parser.add_argument("--repair-ticket-ref", required=True, help="Exact M6.4 RepairTicket version, for example repair_ticket_x:v1.")
    parser.add_argument("--store-root", type=Path, default=DEFAULT_STORE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    store_root = args.store_root if args.store_root.is_absolute() else ROOT / args.store_root
    output = args.output if args.output.is_absolute() else ROOT / args.output
    result = build_result(
        store_root=store_root,
        candidate_bundle_version_ref=args.candidate_bundle_ref,
        repair_ticket_version_ref=args.repair_ticket_ref,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "reason": result.get("reason"), "output": str(output)}, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
