from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


SCHEMA_VERSION = (
    "fin_ia_0_1_2_s4_t07_exact_qualified_human_review_nvda_r3_"
    "entry_identity_and_scope_decision_v1_0"
)
PREDECESSOR_REF = (
    "configs/releases/fin_ia_0_1_2_s4_t06_c_current_review_control_"
    "and_t07_handoff_zero_call_implementation_v1_0.json"
)
CONTRACT_REF = (
    "configs/releases/fin_ia_0_1_2_s4_t06_c_current_review_control_"
    "contract_v1_0.json"
)
API_REF = "apps/workbench/backend/api/v1/current_product.py"
FRONTEND_REF = "apps/workbench/frontend/vite/src/api/currentProduct.ts"
LEGACY_REVIEW_REF = "src/sec_agent/r53_r60_product_acceptance_b04_gate.py"
DEFAULT_OUTPUT = ROOT / (
    "configs/releases/fin_ia_0_1_2_s4_t07_exact_qualified_human_review_"
    "nvda_r3_entry_identity_and_scope_decision_v1_0.json"
)


class S4T07EntryDecisionError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S4T07EntryDecisionError(code)


def _load(path: str) -> dict[str, Any]:
    value = json.loads((ROOT / path).read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "s4_t07_entry_json_object_required")
    return value


def collect_source_observation() -> dict[str, Any]:
    predecessor = _load(PREDECESSOR_REF)
    contract = _load(CONTRACT_REF)
    api_text = (ROOT / API_REF).read_text(encoding="utf-8")
    frontend_text = (ROOT / FRONTEND_REF).read_text(encoding="utf-8")
    legacy_text = (ROOT / LEGACY_REVIEW_REF).read_text(encoding="utf-8")
    observation = {
        "predecessor_record_digest": predecessor.get("record_digest"),
        "predecessor_T07_entered": predecessor.get("T07_handoff_boundary", {}).get(
            "T07_entered"
        ),
        "predecessor_authenticated_reviewer_identity": predecessor.get(
            "T07_handoff_boundary", {}
        ).get("authenticated_reviewer_identity_established"),
        "contract_authenticated_reviewer_identity": contract.get(
            "hard_boundaries", {}
        ).get("authenticated_reviewer_identity"),
        "contract_qualified_human_review": contract.get("hard_boundaries", {}).get(
            "qualified_human_review"
        ),
        "api_principal_from_client_headers_only": all(
            token in api_text
            for token in (
                'Header(alias="X-Fin-Current-Actor")',
                'Header(alias="X-Fin-Case-Permissions")',
                "CurrentReviewControlPrincipal(",
            )
        ),
        "frontend_asserts_current_actor_and_permissions": all(
            token in frontend_text
            for token in (
                'CURRENT_INTERNAL_ACTOR = "current_internal_operator"',
                '"X-Fin-Current-Actor": CURRENT_INTERNAL_ACTOR',
                '"X-Fin-Case-Permissions":',
            )
        ),
        "frontend_has_qualified_review_permission": (
            "current_product:qualified_review" in frontend_text
        ),
        "legacy_real_human_evidence_is_content_validated_self_declaration": all(
            token in legacy_text
            for token in (
                'action_source != "real_human"',
                "reviewer_role not in P24_REAL_HUMAN_REVIEWER_ROLES",
                'if not session_id:',
            )
        ),
        "trusted_identity_provider_or_server_session_found": False,
    }
    return {**observation, "observation_digest": canonical_digest(observation)}


def build_decision(observation: Mapping[str, Any]) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "recorded_at": "2026-08-05T23:59:00+08:00",
        "status": "T07_entry_pass_authenticated_reviewer_identity_blocked",
        "authority": {
            "user_instruction": "继续",
            "entry_and_scope_audit_authorized": True,
            "reviewer_identity_implementation_authorized": False,
            "qualified_review_action_authorized": False,
            "NVDA_R3_decision_authorized": False,
            "model_provider_network_financial_source_calls_authorized": False,
        },
        "predecessor": {
            "T06_C_record_ref": PREDECESSOR_REF,
            "T06_C_record_digest": observation.get("predecessor_record_digest"),
            "T06_pass_closed": True,
            "T07_handoff_ready_only": True,
        },
        "source_observation": dict(observation),
        "earliest_owned_blocker": {
            "issue": "RC-P36-129",
            "layer": "S4_T07_authenticated_reviewer_identity_and_authority_boundary",
            "status": "open_T07_qualified_action_blocker",
            "root_cause": (
                "The current product and historical reviewer paths validate actor, role, "
                "session and permissions supplied by the caller, but no server-trusted "
                "identity or credential binds those claims to a qualified human."
            ),
            "model_or_provider_fault": False,
            "external_boundary": False,
            "blocks": [
                "qualified_human_accept_or_return",
                "NVDA_R3",
                "claiming_authenticated_reviewer_identity",
            ],
            "does_not_block": [
                "zero_call_exact_reviewer_packet",
                "review_burden_measurement",
                "bounded_why_gap_WWC_projection",
                "identity_mechanism_design_and_tests",
            ],
        },
        "identity_disposition_options": [
            {
                "option": "A",
                "name": "bounded_internal_server_issued_review_session",
                "recommendation": "recommended_for_FIN_0_1_2_internal_dogfood",
                "scope": [
                    "admin-only offline session issuance",
                    "server-generated opaque credential returned once",
                    "credential digest only in append-only control store",
                    "qualified reviewer identity and role allowlist",
                    "expiry, revocation, single-session scope and audit events",
                    "exact case, manifest and T07 handoff digest binding",
                    "accept_exact_version or return_for_repair permission",
                ],
                "secret_boundary": (
                    "No plaintext credential, signing key or bearer token may enter Git, "
                    "telemetry, capture, Artifact or worklog."
                ),
                "non_goals": [
                    "production SSO",
                    "enterprise OIDC lifecycle",
                    "multi-tenant IAM",
                    "release or production qualification",
                ],
                "tradeoff": (
                    "Smallest honest internal authentication boundary; still requires a "
                    "later S5 production IAM decision."
                ),
            },
            {
                "option": "B",
                "name": "external_OIDC_or_enterprise_identity_provider",
                "recommendation": "stronger_but_defer_FIN_0_1_2_T07_until_available",
                "tradeoff": (
                    "Best production identity semantics, but it expands infrastructure and "
                    "blocks the current internal dogfood milestone."
                ),
            },
            {
                "option": "C",
                "name": "explicit_chat_owner_decision_only",
                "recommendation": "allowed_as_owner_feedback_not_qualified_product_review",
                "tradeoff": (
                    "Preserves useful human feedback but authenticated reviewer identity, "
                    "qualified review and NVDA R3 must remain false."
                ),
            },
        ],
        "recommended_bounded_T07_sequence": [
            {
                "task": "T07-A",
                "scope": (
                    "NVDA exact reviewer packet, audit replay, burden metrics and bounded "
                    "why/gap/WWC projection; zero external calls"
                ),
                "status": "safe_after_entry_decision",
            },
            {
                "task": "T07-B",
                "scope": (
                    "selected authenticated reviewer session mechanism, append-only decision "
                    "events and negative permission/session mutation"
                ),
                "status": "blocked_user_security_scope_choice",
            },
            {
                "task": "T07-C",
                "scope": (
                    "real qualified reviewer opens exact NVDA packet and explicitly accepts "
                    "or returns; successful acceptance establishes bounded NVDA R3"
                ),
                "status": "blocked_T07_A_and_T07_B_and_real_human_action",
            },
        ],
        "hard_boundaries": {
            "current_header_promoted_to_authenticated_identity": False,
            "legacy_self_declared_role_promoted_to_authenticated_identity": False,
            "automation_or_Codex_may_sign_human_acceptance": False,
            "qualified_human_review_executed": False,
            "NVDA_R3": False,
            "DELL_or_MU_re_review_required_for_T07": False,
            "new_model_provider_network_financial_source_calls": [0, 0, 0, 0],
            "T08_quality_calibration_reentered": False,
            "S5_release_qualification_entered": False,
        },
        "acceptance_boundary": {
            "S4_T06": "pass_closed",
            "S4_T07_entry": "pass",
            "S4_T07_engineering": "not_started",
            "authenticated_reviewer_identity": False,
            "qualified_human_review": False,
            "NVDA_R3": False,
            "S4_T08": "not_entered",
            "S5": "not_entered",
            "release": "not_qualified",
        },
        "security_scope_choice": {
            "status": "user_decision_required_before_T07_B",
            "recommended_option": "A",
            "safe_work_while_pending": ["T07-A"],
        },
        "recommended_next": (
            "FIN-0.1.2-S4-T07-A-NVDA-EXACT-REVIEWER-PACKET-AUDIT-REPLAY-"
            "BURDEN-AND-BOUNDED-EXPLANATION-ZERO-CALL-IMPLEMENTATION"
        ),
    }
    body["decision_digest"] = canonical_digest(body)
    return body


def validate_entry_decision(decision: Mapping[str, Any]) -> None:
    _require(
        decision.get("schema_version") == SCHEMA_VERSION,
        "s4_t07_entry_schema_invalid",
    )
    observation = decision.get("source_observation")
    _require(isinstance(observation, Mapping), "s4_t07_entry_observation_missing")
    observation_body = {
        key: value for key, value in observation.items() if key != "observation_digest"
    }
    _require(
        observation.get("observation_digest") == canonical_digest(observation_body),
        "s4_t07_entry_observation_digest_mismatch",
    )
    _require(
        observation.get("predecessor_record_digest")
        == "c4990c2e188bc03fd071cf3939cbf3e6e68479bb30edf75140d73668298bd41a"
        and observation.get("predecessor_T07_entered") is False
        and observation.get("predecessor_authenticated_reviewer_identity") is False
        and observation.get("contract_authenticated_reviewer_identity") is False
        and observation.get("contract_qualified_human_review") is False,
        "s4_t07_entry_predecessor_boundary_invalid",
    )
    _require(
        observation.get("api_principal_from_client_headers_only") is True
        and observation.get("frontend_asserts_current_actor_and_permissions") is True
        and observation.get("frontend_has_qualified_review_permission") is False
        and observation.get(
            "legacy_real_human_evidence_is_content_validated_self_declaration"
        )
        is True
        and observation.get("trusted_identity_provider_or_server_session_found") is False,
        "s4_t07_entry_identity_observation_invalid",
    )
    authority = decision.get("authority") or {}
    _require(
        authority.get("entry_and_scope_audit_authorized") is True
        and authority.get("reviewer_identity_implementation_authorized") is False
        and authority.get("qualified_review_action_authorized") is False
        and authority.get("NVDA_R3_decision_authorized") is False,
        "s4_t07_entry_authority_invalid",
    )
    blocker = decision.get("earliest_owned_blocker") or {}
    _require(
        blocker.get("issue") == "RC-P36-129"
        and blocker.get("status") == "open_T07_qualified_action_blocker"
        and blocker.get("model_or_provider_fault") is False,
        "s4_t07_entry_blocker_invalid",
    )
    options = decision.get("identity_disposition_options") or []
    _require(
        [row.get("option") for row in options] == ["A", "B", "C"]
        and options[0].get("recommendation")
        == "recommended_for_FIN_0_1_2_internal_dogfood",
        "s4_t07_entry_identity_options_invalid",
    )
    sequence = decision.get("recommended_bounded_T07_sequence") or []
    _require(
        [row.get("task") for row in sequence] == ["T07-A", "T07-B", "T07-C"]
        and sequence[0].get("status") == "safe_after_entry_decision"
        and sequence[1].get("status") == "blocked_user_security_scope_choice",
        "s4_t07_entry_sequence_invalid",
    )
    boundaries = decision.get("hard_boundaries") or {}
    _require(
        boundaries.get("current_header_promoted_to_authenticated_identity") is False
        and boundaries.get("legacy_self_declared_role_promoted_to_authenticated_identity")
        is False
        and boundaries.get("automation_or_Codex_may_sign_human_acceptance") is False
        and boundaries.get("qualified_human_review_executed") is False
        and boundaries.get("NVDA_R3") is False
        and boundaries.get("new_model_provider_network_financial_source_calls")
        == [0, 0, 0, 0],
        "s4_t07_entry_hard_boundary_invalid",
    )
    acceptance = decision.get("acceptance_boundary") or {}
    _require(
        acceptance.get("S4_T06") == "pass_closed"
        and acceptance.get("S4_T07_entry") == "pass"
        and acceptance.get("S4_T07_engineering") == "not_started"
        and acceptance.get("authenticated_reviewer_identity") is False
        and acceptance.get("qualified_human_review") is False
        and acceptance.get("NVDA_R3") is False
        and acceptance.get("release") == "not_qualified",
        "s4_t07_entry_acceptance_boundary_invalid",
    )
    digest_body = {
        key: value for key, value in decision.items() if key != "decision_digest"
    }
    _require(
        decision.get("decision_digest") == canonical_digest(digest_body),
        "s4_t07_entry_decision_digest_mismatch",
    )


def materialize(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    decision = build_decision(collect_source_observation())
    validate_entry_decision(decision)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return decision


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    decision = materialize(args.output)
    print(json.dumps({"status": decision["status"], "decision_digest": decision["decision_digest"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
