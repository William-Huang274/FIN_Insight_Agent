from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


SCHEMA_VERSION = "fin_ia_0_1_2_s4_t07_b_reviewer_session_contract_v1_0"
T07_A_REF = (
    "configs/releases/fin_ia_0_1_2_s4_t07_a_nvda_exact_reviewer_packet_"
    "contract_v1_0.json"
)
DEFAULT_OUTPUT = ROOT / (
    "configs/releases/fin_ia_0_1_2_s4_t07_b_bounded_internal_reviewer_"
    "session_contract_v1_0.json"
)
DEFAULT_REGISTRY_OUTPUT = ROOT / (
    "configs/runtime/fin_ia_0_1_2_s4_t07_b_reviewer_session_"
    "runtime_resource_registry_v1_0.json"
)
RESOURCE_ID = "fin_0_1_2.s4.t07_b.reviewer_session_contract"
CONSUMER_REF = (
    "apps/workbench/backend/application/fin_0_1_2_s4_t07_reviewer_session.py"
)


class T07BContractError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise T07BContractError(code)


def build_contract() -> dict[str, Any]:
    predecessor = json.loads((ROOT / T07_A_REF).read_text(encoding="utf-8"))
    binding = predecessor["exact_binding"]
    body: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "T07_B_bounded_internal_reviewer_session_authorized",
        "authority": {
            "user_instruction": "接受",
            "selected_security_option": "A",
            "T07_B_implementation_authorized": True,
            "real_session_issuance_executed": False,
            "T07_C_real_human_action_executed": False,
        },
        "predecessor": {
            "T07_A_ref": T07_A_REF,
            "T07_A_contract_digest": predecessor["contract_digest"],
        },
        "qualified_identity_allowlist": {
            "FIN_OWNER_A": ["qualified_product_owner"],
        },
        "offline_admin_allowlist": ["local_security_admin"],
        "session_policy": {
            "credential_prefix": "finrvw_",
            "minimum_credential_entropy_bytes": 32,
            "credential_returned_once": True,
            "credential_digest_algorithm": "sha256",
            "plaintext_credential_persisted": False,
            "maximum_ttl_seconds": 28800,
            "single_active_session_per_reviewer_case_handoff": True,
            "revocation_supported": True,
            "required_permission": "current_product:qualified_review",
        },
        "exact_scope": {
            "case_key": "NVDA",
            "manifest_digest": binding["projection_manifest_digest"],
            "case_projection_digest": binding["case_projection_digest"],
            "view_digests": binding["view_digests"],
        },
        "decision_policy": {
            "allowed_actions": ["accept_exact_version", "return_for_repair"],
            "single_terminal_decision_per_packet": True,
            "idempotency_required": True,
            "reviewer_note_max_length": 1000,
            "return_requires_exact_surface_reason_and_view_digest": True,
            "accept_establishes_bounded_NVDA_R3_only": True,
        },
        "event_policy": {
            "append_only_hash_chain": True,
            "event_types": [
                "REVIEW_SESSION_ISSUED",
                "REVIEW_SESSION_AUTHENTICATED",
                "REVIEW_SESSION_AUTHENTICATION_REJECTED",
                "REVIEW_SESSION_REVOKED",
                "QUALIFIED_REVIEW_DECISION_RECORDED",
            ],
            "failed_auth_event_is_content_free": True,
        },
        "hard_boundaries": {
            "public_session_issuance_API": False,
            "client_asserted_identity_is_authenticated": False,
            "credential_or_digest_in_business_artifact": False,
            "credential_plaintext_persisted": False,
            "model_provider_network_financial_source_calls": 0,
            "accepted_R2_business_truth_mutation": False,
            "automatic_repair_execution_or_T06_queue_mutation": False,
            "production_OIDC_or_SSO": False,
            "real_human_review_executed": False,
            "NVDA_R3": False,
            "release_qualified": False,
        },
    }
    body["contract_digest"] = canonical_digest(body)
    validate_contract(body)
    return body


def validate_contract(value: Mapping[str, Any]) -> None:
    body = {key: item for key, item in value.items() if key != "contract_digest"}
    policy = value.get("session_policy") or {}
    boundary = value.get("hard_boundaries") or {}
    _require(
        value.get("schema_version") == SCHEMA_VERSION
        and value.get("contract_digest") == canonical_digest(body),
        "t07_b_contract_identity_or_digest_invalid",
    )
    _require(
        value.get("authority", {}).get("selected_security_option") == "A"
        and value.get("qualified_identity_allowlist")
        == {"FIN_OWNER_A": ["qualified_product_owner"]}
        and value.get("offline_admin_allowlist") == ["local_security_admin"],
        "t07_b_authority_or_allowlist_invalid",
    )
    _require(
        policy.get("minimum_credential_entropy_bytes") == 32
        and policy.get("credential_returned_once") is True
        and policy.get("plaintext_credential_persisted") is False
        and policy.get("maximum_ttl_seconds") == 28800,
        "t07_b_session_policy_invalid",
    )
    _require(
        boundary.get("public_session_issuance_API") is False
        and boundary.get("client_asserted_identity_is_authenticated") is False
        and boundary.get("credential_plaintext_persisted") is False
        and boundary.get("model_provider_network_financial_source_calls") == 0
        and boundary.get("automatic_repair_execution_or_T06_queue_mutation") is False
        and boundary.get("real_human_review_executed") is False
        and boundary.get("NVDA_R3") is False,
        "t07_b_hard_boundary_invalid",
    )


def _registry(output: Path) -> dict[str, Any]:
    payload = output.read_bytes()
    row = {
        "resource_id": RESOURCE_ID,
        "repo_relative_path": output.relative_to(ROOT).as_posix(),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
        "classification": "bounded_internal_reviewer_session_contract",
        "consumer_ids": ["apps.workbench.current_product_reviewer_session.service"],
        "load_phase": "S4_T07_B_reviewer_session",
        "required": True,
        "source_owner": (
            "apps.workbench.backend.application.fin_0_1_2_s4_t07_reviewer_session"
        ),
    }
    canonical_rows = json.dumps(
        [row], ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return {
        "schema_version": "fin_ia_0_1_3_runtime_resource_registry_v1_0",
        "registry_id": "FIN-0.1.2-S4-T07-B-REVIEWER-SESSION-REGISTRY-R1",
        "status": "tracked_typed_runtime_resource_authority",
        "policy": {
            "registry_is_source_of_truth": True,
            "static_scanner_is_detector_only": True,
            "direct_unregistered_runtime_read_fails_closed": True,
            "missing_unknown_duplicate_or_digest_drift_fails_closed": True,
            "permutation_or_cross_version_fails_closed": True,
            "ignored_untracked_codex_runtime_and_git_forbidden": True,
            "traversal_and_symlink_escape_forbidden": True,
        },
        "detector_python_refs": [CONSUMER_REF],
        "resource_count": 1,
        "resource_bytes": len(payload),
        "resource_canonical_digest": hashlib.sha256(canonical_rows).hexdigest(),
        "resources": [row],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    contract = build_contract()
    rendered = json.dumps(contract, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        _require(DEFAULT_OUTPUT.read_text(encoding="utf-8") == rendered, "t07_b_contract_drift")
        expected_registry = json.dumps(_registry(DEFAULT_OUTPUT), ensure_ascii=False, indent=2) + "\n"
        _require(DEFAULT_REGISTRY_OUTPUT.read_text(encoding="utf-8") == expected_registry, "t07_b_registry_drift")
        return 0
    DEFAULT_OUTPUT.write_text(rendered, encoding="utf-8")
    DEFAULT_REGISTRY_OUTPUT.write_text(
        json.dumps(_registry(DEFAULT_OUTPUT), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
