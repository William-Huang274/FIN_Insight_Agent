from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


SCHEMA_VERSION = "fin_ia_0_1_2_s4_t07_a_nvda_reviewer_packet_contract_v1_0"
ENTRY_REF = (
    "configs/releases/fin_ia_0_1_2_s4_t07_exact_qualified_human_review_"
    "nvda_r3_entry_identity_and_scope_decision_v1_0.json"
)
PROJECTION_REF = (
    "configs/releases/fin_ia_0_1_2_s4_t06_a_current_product_projection_"
    "manifest_v1_0.json"
)
EXACT_RESULT_REF = (
    ".codex_runtime/fin012-s4-t05d-nvda-post-transfer-agent-exact-live-r1/"
    "execution-result.json"
)
DEFAULT_OUTPUT = ROOT / (
    "configs/releases/fin_ia_0_1_2_s4_t07_a_nvda_exact_reviewer_packet_"
    "contract_v1_0.json"
)
DEFAULT_REGISTRY_OUTPUT = ROOT / (
    "configs/runtime/fin_ia_0_1_2_s4_t07_a_nvda_reviewer_packet_"
    "runtime_resource_registry_v1_0.json"
)
RESOURCE_ID = "fin_0_1_2.s4.t07_a.nvda_reviewer_packet_contract"
CONSUMER_REF = (
    "apps/workbench/backend/application/fin_0_1_2_s4_t07_reviewer_packet.py"
)
EXPECTED_ENTRY_DIGEST = (
    "974eea932ec755eba88e32389b13142b4e192578a32b8b5a883bf1d7aac00068"
)


class T07AReviewerPacketError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise T07AReviewerPacketError(code)


def _load(relative: str) -> dict[str, Any]:
    value = json.loads((ROOT / relative).read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "t07_a_json_object_required")
    return value


def _forbidden_surface_walk(value: Any) -> None:
    forbidden = {
        "authorization",
        "capture_objects",
        "credential",
        "cookie",
        "object_key",
        "provider_output",
        "raw_provider_response",
        "request_headers",
        "response_headers",
    }
    safe_negative_boundaries = {"raw_capture_product_exposure"}
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).lower()
            _require(
                normalized not in forbidden
                and (
                    not normalized.startswith("raw_")
                    or (
                        normalized in safe_negative_boundaries
                        and item is False
                    )
                )
                and "private_reasoning" not in normalized,
                "t07_a_forbidden_reviewer_surface",
            )
            _forbidden_surface_walk(item)
    elif isinstance(value, list):
        for item in value:
            _forbidden_surface_walk(item)
    elif isinstance(value, str):
        normalized = value.replace("\\", "/").lower()
        _require(
            ".codex_runtime" not in normalized
            and "restricted-provider-captures" not in normalized,
            "t07_a_forbidden_runtime_reference",
        )


def build_contract() -> dict[str, Any]:
    entry = _load(ENTRY_REF)
    projection = _load(PROJECTION_REF)
    exact = _load(EXACT_RESULT_REF)
    _require(
        entry.get("decision_digest") == EXPECTED_ENTRY_DIGEST,
        "t07_a_entry_digest_invalid",
    )
    case = next(
        (row for row in projection.get("cases", []) if row.get("case_key") == "NVDA"),
        None,
    )
    _require(isinstance(case, Mapping), "t07_a_nvda_projection_missing")
    judgment = next(
        (
            row.get("payload")
            for row in exact.get("artifacts", [])
            if row.get("artifact_type") == "bounded_agent_judgment"
        ),
        None,
    )
    _require(isinstance(judgment, Mapping), "t07_a_judgment_artifact_missing")
    lead = judgment.get("cross_cell_lead")
    _require(isinstance(lead, Mapping), "t07_a_cross_cell_lead_missing")
    _require(
        len(lead.get("cross_cell_dependencies", [])) == 1
        and len(lead.get("conflict_adjudications", [])) == 2
        and len(lead.get("remaining_gaps", [])) == 4,
        "t07_a_cross_cell_lead_shape_invalid",
    )
    views = case.get("views") or {}
    view_digests = {
        name: view.get("view_digest") for name, view in views.items()
    }
    body: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "T07_A_exact_reviewer_packet_contract_ready",
        "authority": {
            "entry_decision_ref": ENTRY_REF,
            "entry_decision_digest": EXPECTED_ENTRY_DIGEST,
            "user_security_scope_choice": "A",
            "user_instruction": "接受",
            "T07_A_implementation_authorized": True,
            "T07_B_implementation_authorized": True,
            "T07_C_human_action_authorized_for_automation": False,
        },
        "exact_binding": {
            "case_key": "NVDA",
            "projection_manifest_digest": projection.get("manifest_digest"),
            "case_projection_digest": case.get("case_projection_digest"),
            "view_digests": view_digests,
            "judgment_artifact_digest": canonical_digest(judgment),
            "cross_cell_lead_digest": judgment.get("cross_cell_lead_digest"),
        },
        "safe_cross_cell_lead": deepcopy(dict(lead)),
        "review_checklist": [
            {
                "check_id": "authority_and_citation",
                "required_surfaces": ["evidence", "workpaper", "trace"],
                "instruction": "Confirm each material claim is tied to approved evidence and a visible citation lineage.",
            },
            {
                "check_id": "numeric_scope_unit_period",
                "required_surfaces": ["numeric", "workpaper", "report"],
                "instruction": "Confirm every financial number preserves entity, period, unit, currency and scope.",
            },
            {
                "check_id": "inference_and_counterevidence",
                "required_surfaces": ["workpaper", "quality"],
                "instruction": "Inspect epistemic states, counterevidence, unresolved conflicts and bounded dependencies.",
            },
            {
                "check_id": "gaps_and_what_would_change",
                "required_surfaces": ["gaps", "workpaper", "quality"],
                "instruction": "Confirm typed gaps and what-would-change tasks are explicit and not represented as facts.",
            },
            {
                "check_id": "final_delivery_fidelity",
                "required_surfaces": ["report", "quality"],
                "instruction": "Confirm the final delivery does not overstate the evidence or hide deferred quality findings.",
            },
        ],
        "hard_boundaries": {
            "model_provider_network_financial_source_calls": 0,
            "raw_capture_product_exposure": False,
            "mutable_business_truth_write": False,
            "qualified_human_review_executed": False,
            "authenticated_reviewer_session_established": False,
            "automation_or_Codex_may_sign_human_acceptance": False,
            "NVDA_R3": False,
            "release_qualified": False,
        },
    }
    body["contract_digest"] = canonical_digest(body)
    validate_contract(body)
    return body


def validate_contract(contract: Mapping[str, Any]) -> None:
    digest_body = {
        key: value for key, value in contract.items() if key != "contract_digest"
    }
    _require(
        contract.get("schema_version") == SCHEMA_VERSION
        and contract.get("contract_digest") == canonical_digest(digest_body),
        "t07_a_contract_identity_or_digest_invalid",
    )
    authority = contract.get("authority") or {}
    binding = contract.get("exact_binding") or {}
    boundaries = contract.get("hard_boundaries") or {}
    lead = contract.get("safe_cross_cell_lead") or {}
    _require(
        authority.get("user_security_scope_choice") == "A"
        and authority.get("T07_A_implementation_authorized") is True
        and authority.get("T07_B_implementation_authorized") is True
        and authority.get("T07_C_human_action_authorized_for_automation") is False,
        "t07_a_authority_invalid",
    )
    _require(
        binding.get("case_key") == "NVDA"
        and len(binding.get("view_digests") or {}) == 10
        and binding.get("cross_cell_lead_digest")
        == canonical_digest(lead),
        "t07_a_exact_binding_invalid",
    )
    _require(
        len(lead.get("cross_cell_dependencies", [])) == 1
        and len(lead.get("conflict_adjudications", [])) == 2
        and len(lead.get("remaining_gaps", [])) == 4,
        "t07_a_lead_content_invalid",
    )
    _require(
        boundaries.get("model_provider_network_financial_source_calls") == 0
        and boundaries.get("raw_capture_product_exposure") is False
        and boundaries.get("mutable_business_truth_write") is False
        and boundaries.get("qualified_human_review_executed") is False
        and boundaries.get("authenticated_reviewer_session_established") is False
        and boundaries.get("automation_or_Codex_may_sign_human_acceptance") is False
        and boundaries.get("NVDA_R3") is False,
        "t07_a_hard_boundary_invalid",
    )
    _forbidden_surface_walk(contract)


def _registry(contract_path: Path) -> dict[str, Any]:
    payload = contract_path.read_bytes()
    row = {
        "resource_id": RESOURCE_ID,
        "repo_relative_path": contract_path.relative_to(ROOT).as_posix(),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
        "classification": "current_product_exact_reviewer_packet_contract",
        "consumer_ids": ["apps.workbench.current_product_reviewer_packet.service"],
        "load_phase": "S4_T07_A_exact_reviewer_packet",
        "required": True,
        "source_owner": (
            "apps.workbench.backend.application.fin_0_1_2_s4_t07_reviewer_packet"
        ),
    }
    canonical_rows = json.dumps(
        [row], ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return {
        "schema_version": "fin_ia_0_1_3_runtime_resource_registry_v1_0",
        "registry_id": "FIN-0.1.2-S4-T07-A-NVDA-REVIEWER-PACKET-REGISTRY-R1",
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
        _require(DEFAULT_OUTPUT.read_text(encoding="utf-8") == rendered, "t07_a_contract_drift")
        expected_registry = json.dumps(_registry(DEFAULT_OUTPUT), ensure_ascii=False, indent=2) + "\n"
        _require(
            DEFAULT_REGISTRY_OUTPUT.read_text(encoding="utf-8") == expected_registry,
            "t07_a_registry_drift",
        )
        return 0
    DEFAULT_OUTPUT.write_text(rendered, encoding="utf-8")
    registry = _registry(DEFAULT_OUTPUT)
    DEFAULT_REGISTRY_OUTPUT.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
