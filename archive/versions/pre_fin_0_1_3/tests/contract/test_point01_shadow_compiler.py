from __future__ import annotations

import pytest

from sec_agent.canonical_runtime.planning_service import DecisionSurfacePlanningService
from sec_agent.canonical_runtime.shadow_compiler import DeterministicShadowCompiler, ModelAdapterNotAdmitted, compare_shadow_bundle_with_legacy_objective, require_model_adapter_admission
from test_point01_decision_surface_planning import _input, _scope


pytestmark = pytest.mark.fast_contract


def test_m2_deterministic_compiler_and_structural_comparison_are_model_free() -> None:
    result = DeterministicShadowCompiler(DecisionSurfacePlanningService(None)).compile(_input(), audit_scope=_scope())  # type: ignore[arg-type]
    assert result["validation"]["status"] == "pass"
    assert result["model_call_count"] == 0
    comparison = compare_shadow_bundle_with_legacy_objective(result["bundle"], {"required_items": [{"required_item_id": "demand"}]})
    assert comparison["count_parity"] is True
    with pytest.raises(ModelAdapterNotAdmitted):
        require_model_adapter_admission(feature_flag_enabled=True, explicit_approval=True, provider_preflight_passed=False, budget_preflight_passed=True)
