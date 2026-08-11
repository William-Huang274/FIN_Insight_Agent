from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


DEFAULT_OUTPUT = ROOT / (
    "configs/releases/fin_ia_0_1_2_s4_t07_b_bounded_internal_reviewer_"
    "session_zero_call_implementation_v1_0.json"
)
CONTRACT_REF = (
    "configs/releases/fin_ia_0_1_2_s4_t07_b_bounded_internal_reviewer_"
    "session_contract_v1_0.json"
)
CODE_REFS = [
    "apps/workbench/backend/application/fin_0_1_2_s4_t07_reviewer_session.py",
    "apps/workbench/backend/api/v1/current_product.py",
    "apps/workbench/backend/app.py",
    "apps/workbench/frontend/vite/src/api/currentProduct.ts",
    "apps/workbench/frontend/vite/src/app/CurrentProductWorkbench.tsx",
    "apps/workbench/frontend/vite/src/app/current-product.css",
    "scripts/workbench/manage_fin_0_1_2_t07_reviewer_session.py",
]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_record() -> dict:
    contract = json.loads((ROOT / CONTRACT_REF).read_text(encoding="utf-8"))
    body = {
        "schema_version": "fin_ia_0_1_2_s4_t07_b_bounded_internal_reviewer_session_zero_call_implementation_v1_0",
        "recorded_at": "2026-08-05T23:59:50+08:00",
        "status": "T07_B_engineering_pass_real_issuance_and_T07_C_pending",
        "authority": {
            "user_instruction": "接受",
            "selected_security_option": "A",
            "T07_B_implementation_authorized": True,
            "real_session_issuance_executed": False,
            "real_human_decision_executed": False,
        },
        "contract": {
            "ref": CONTRACT_REF,
            "digest": contract["contract_digest"],
        },
        "implementation_bindings": [
            {"ref": ref, "sha256": _sha(ROOT / ref)} for ref in CODE_REFS
        ],
        "capabilities": {
            "offline_admin_only_session_issuance": True,
            "server_generated_opaque_credential": True,
            "credential_plaintext_returned_once": True,
            "credential_digest_only_persisted": True,
            "qualified_reviewer_identity_and_role_allowlist": True,
            "expiry_and_revocation": True,
            "exact_NVDA_manifest_case_handoff_packet_binding": True,
            "append_only_hash_chained_auth_and_decision_events": True,
            "authenticated_accept_or_return_endpoint": True,
            "public_issuance_endpoint": False,
            "frontend_memory_only_credential": True,
        },
        "verification": {
            "T06_through_T07_B_adjacent_contracts": "46 passed",
            "T07_B_focused_contracts": "7 passed",
            "desktop_and_mobile_browser": "10 passed",
            "typescript_compile": "pass",
            "vite_production_build": "pass_with_existing_chunk_warning",
            "contract_materializer_check": "pass",
            "default_private_store_session_event_decision_counts": [0, 0, 0],
            "secret_scan_plaintext_credentials_found": 0,
            "new_model_provider_network_financial_source_calls": [0, 0, 0, 0],
        },
        "stage_acceptance": {
            "S4_T07_A_engineering": "pass",
            "S4_T07_B_engineering": "pass",
            "authenticated_reviewer_mechanism": "available_not_real_session_issued",
            "qualified_human_review": False,
            "NVDA_R3": False,
            "S4_T07_C": "pending_real_user_action",
            "S4_T08": "not_entered",
            "S5": "not_entered",
            "release": False,
        },
        "hard_boundaries": {
            "test_session_or_Codex_action_counts_as_real_review": False,
            "credential_in_Git_telemetry_capture_artifact_or_worklog": False,
            "accepted_R2_business_truth_mutated": False,
            "production_OIDC_or_SSO_implemented": False,
        },
        "recommended_next": (
            "USER-T07-C-OFFLINE-ISSUE-ONE-FIN-OWNER-A-SESSION-OPEN-EXACT-"
            "NVDA-PACKET-AND-ACCEPT-OR-RETURN"
        ),
    }
    body["record_digest"] = canonical_digest(body)
    return body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = json.dumps(build_record(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if DEFAULT_OUTPUT.read_text(encoding="utf-8") != rendered:
            raise RuntimeError("t07_b_implementation_record_drift")
        return 0
    DEFAULT_OUTPUT.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
