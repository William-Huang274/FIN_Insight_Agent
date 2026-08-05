from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.runtime_resource_registry import read_registered_runtime_json

from .fin_0_1_2_s4_t06_current_product_projection import (
    CURRENT_PRODUCT_READ_PERMISSION,
    CurrentProductPrincipal,
    CurrentProductProjectionService,
)
from .fin_0_1_2_s4_t06_current_review_control import (
    CurrentProductReviewControlService,
    CurrentReviewControlPrincipal,
)


T07_A_REVIEWER_PACKET_REGISTRY_REF = (
    "configs/runtime/fin_ia_0_1_2_s4_t07_a_nvda_reviewer_packet_"
    "runtime_resource_registry_v1_0.json"
)
T07_A_REVIEWER_PACKET_RESOURCE_ID = (
    "fin_0_1_2.s4.t07_a.nvda_reviewer_packet_contract"
)
T07_A_REVIEWER_PACKET_SCHEMA = (
    "fin_ia_0_1_2_s4_t07_a_nvda_reviewer_packet_contract_v1_0"
)
T07_A_REVIEWER_PACKET_API_SCHEMA = (
    "fin_ia_0_1_2_s4_t07_a_nvda_reviewer_packet_api_v1_0"
)


class CurrentProductReviewerPacketError(RuntimeError):
    def __init__(self, error_code: str, status_code: int = 409, **detail: Any):
        super().__init__(error_code)
        self.error_code = error_code
        self.status_code = status_code
        self.detail = {"reason": error_code, **detail}


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CurrentProductReviewerPacketError(code)


class CurrentProductReviewerPacketService:
    """Build the exact NVDA T07 packet without model, source, or write calls."""

    def __init__(
        self,
        projection: CurrentProductProjectionService,
        review_control: CurrentProductReviewControlService,
        contract: Mapping[str, Any],
    ) -> None:
        self._projection = projection
        self._review_control = review_control
        self._contract = deepcopy(dict(contract))
        self._validate_contract()

    @classmethod
    def from_repository(
        cls,
        repository_root: str | Path,
        projection: CurrentProductProjectionService,
        review_control: CurrentProductReviewControlService,
    ) -> "CurrentProductReviewerPacketService":
        contract = read_registered_runtime_json(
            repository_root,
            T07_A_REVIEWER_PACKET_RESOURCE_ID,
            registry_ref=T07_A_REVIEWER_PACKET_REGISTRY_REF,
        )
        return cls(projection, review_control, contract)

    def get_packet(
        self, case_key: str, principal: CurrentProductPrincipal
    ) -> dict[str, Any]:
        if principal.mode != "current" or CURRENT_PRODUCT_READ_PERMISSION not in principal.permissions:
            raise CurrentProductReviewerPacketError(
                "current_product_read_permission_required", 403
            )
        normalized = str(case_key).upper()
        if normalized != "NVDA":
            raise CurrentProductReviewerPacketError(
                "t07_reviewer_packet_only_available_for_nvda", 404,
                case_key=case_key,
            )
        surfaces = {
            name: self._projection.get_surface(normalized, name, principal)
            for name in self._contract["exact_binding"]["view_digests"]
        }
        binding = self._contract["exact_binding"]
        _require(
            self._projection.manifest_digest
            == binding["projection_manifest_digest"]
            and all(
                surfaces[name]["view_digest"] == digest
                for name, digest in binding["view_digests"].items()
            ),
            "t07_reviewer_packet_projection_binding_drift",
        )
        review_state = self._review_control.get_state(
            normalized,
            CurrentReviewControlPrincipal(
                mode="current",
                actor_id="",
                permissions=frozenset({CURRENT_PRODUCT_READ_PERMISSION}),
            ),
        )
        handoff = review_state["T07_handoff"]
        _require(
            handoff["status"] == "ready_for_qualified_review"
            and handoff["open_return_request_ids"] == [],
            "t07_reviewer_packet_handoff_not_ready",
        )

        evidence = deepcopy(surfaces["evidence"]["data"])
        numeric = deepcopy(surfaces["numeric"]["data"])
        product_gaps = deepcopy(surfaces["gaps"]["data"])
        workpaper = deepcopy(surfaces["workpaper"]["data"])
        lead = deepcopy(self._contract["safe_cross_cell_lead"])
        quality = deepcopy(surfaces["quality"]["data"])
        burden = {
            "evidence_rows": len(evidence["rows"]),
            "numeric_rows": len(numeric["rows"]),
            "research_cells": len(workpaper["cells"]),
            "claims": sum(
                len(cell.get("judgment_layer", [])) for cell in workpaper["cells"]
            ),
            "what_would_change_items": sum(
                len(cell.get("what_would_change", [])) for cell in workpaper["cells"]
            ),
            "typed_product_gaps": len(product_gaps["rows"]),
            "cross_cell_dependencies": len(lead["cross_cell_dependencies"]),
            "unresolved_conflicts": len(lead["conflict_adjudications"]),
            "lead_remaining_gaps": len(lead["remaining_gaps"]),
            "checklist_items": len(self._contract["review_checklist"]),
            "measured_human_review_duration_seconds": None,
        }
        packet_body = {
            "schema_version": T07_A_REVIEWER_PACKET_API_SCHEMA,
            "projection_mode": "current",
            "status": "ready_for_authenticated_qualified_human_review",
            "case_key": normalized,
            "exact_binding": {
                **deepcopy(binding),
                "review_control_replay_digest": review_state["replay_digest"],
                "T07_handoff_digest": handoff["handoff_digest"],
            },
            "review_checklist": [
                {**deepcopy(row), "review_status": "pending_human_review"}
                for row in self._contract["review_checklist"]
            ],
            "review_burden": burden,
            "sections": {
                "case": deepcopy(surfaces["case"]["data"]),
                "run": deepcopy(surfaces["run"]["data"]),
                "evidence": evidence,
                "numeric": numeric,
                "graph": deepcopy(surfaces["graph"]["data"]),
                "typed_product_gaps": product_gaps,
                "workpaper": workpaper,
                "cross_cell_lead": lead,
                "final_report": deepcopy(surfaces["report"]["data"]),
                "audit_trace": deepcopy(surfaces["trace"]["data"]),
                "quality": quality,
            },
            "decision_boundary": {
                "authenticated_reviewer_session_required": True,
                "authenticated_reviewer_session_established": False,
                "qualified_human_review_executed": False,
                "review_decision": None,
                "NVDA_R3": False,
            },
            "hard_boundaries": deepcopy(self._contract["hard_boundaries"]),
        }
        return {**packet_body, "packet_digest": canonical_digest(packet_body)}

    def _validate_contract(self) -> None:
        body = {
            key: value
            for key, value in self._contract.items()
            if key != "contract_digest"
        }
        binding = self._contract.get("exact_binding") or {}
        boundaries = self._contract.get("hard_boundaries") or {}
        _require(
            self._contract.get("schema_version") == T07_A_REVIEWER_PACKET_SCHEMA
            and self._contract.get("contract_digest") == canonical_digest(body),
            "t07_reviewer_packet_contract_invalid",
        )
        _require(
            binding.get("case_key") == "NVDA"
            and len(binding.get("view_digests") or {}) == 10
            and binding.get("cross_cell_lead_digest")
            == canonical_digest(self._contract.get("safe_cross_cell_lead") or {}),
            "t07_reviewer_packet_contract_binding_invalid",
        )
        _require(
            boundaries.get("model_provider_network_financial_source_calls") == 0
            and boundaries.get("raw_capture_product_exposure") is False
            and boundaries.get("mutable_business_truth_write") is False
            and boundaries.get("qualified_human_review_executed") is False
            and boundaries.get("NVDA_R3") is False,
            "t07_reviewer_packet_contract_boundary_invalid",
        )
