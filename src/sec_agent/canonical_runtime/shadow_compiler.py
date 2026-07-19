from __future__ import annotations

from typing import Any, Mapping, Protocol

from .planning_service import CompilerInputContract, DecisionSurfacePlanningService


class ShadowCompilerModelAdapter(Protocol):
    def compile(self, inputs: CompilerInputContract) -> Mapping[str, Any]: ...


class ModelAdapterNotAdmitted(RuntimeError):
    pass


class DeterministicShadowCompiler:
    """M2B compiler: deterministic only; a model adapter is deliberately not invoked here."""

    def __init__(self, planning_service: DecisionSurfacePlanningService):
        self.planning_service = planning_service

    def compile(self, inputs: CompilerInputContract, *, audit_scope: Mapping[str, Any]) -> dict[str, Any]:
        bundle = self.planning_service.compile_deterministic_fixture(inputs, audit_scope=audit_scope)
        validation = self.planning_service.validate_decision_surface_bundle(inputs.case_id, bundle)
        if validation["status"] != "pass":
            raise RuntimeError(f"deterministic_compiler_validation_failed:{validation['errors']}")
        return {"bundle": bundle, "validation": validation, "compiler_mode": "deterministic_shadow", "model_call_count": 0}


def compare_shadow_bundle_with_legacy_objective(bundle: Mapping[str, Any], legacy_payload: Mapping[str, Any]) -> dict[str, Any]:
    """M2D deterministic comparison only; it is not an M3 quality or reviewer decision."""
    legacy_ids = {str(item.get("required_item_id") or "") for item in legacy_payload.get("required_items") or () if isinstance(item, Mapping)}
    cell_count = len(bundle.get("cells") or ())
    return {
        "comparison_status": "deterministic_structural_only",
        "legacy_required_item_count": len(legacy_ids),
        "shadow_cell_count": cell_count,
        "count_parity": len(legacy_ids) == cell_count,
        "planning_authority": "legacy",
        "model_call_count": 0,
        "reviewer_decision": None,
    }


def require_model_adapter_admission(*, feature_flag_enabled: bool, explicit_approval: bool, provider_preflight_passed: bool, budget_preflight_passed: bool) -> None:
    if not (feature_flag_enabled and explicit_approval and provider_preflight_passed and budget_preflight_passed):
        raise ModelAdapterNotAdmitted("model_adapter_shadow_run_not_admitted")
