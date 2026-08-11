from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sec_agent.canonical_runtime.legacy_objective_adapter import LegacyObjectiveAdapterError, adapt_legacy_research_objective


pytestmark = pytest.mark.fast_contract


def test_adapter_is_deterministic_and_preserves_legacy_as_input_only() -> None:
    payload = {"query": "Assess demand durability", "as_of": datetime(2026, 7, 12, tzinfo=timezone.utc), "universe": ["CRM", "NOW"], "required_items": [{"required_item_id": "demand", "must_answer": "Is demand durable?", "evidence_role": "demand_quality"}]}
    first = adapt_legacy_research_objective(payload, tenant_id="tenant", project_id="project", case_id="case", compiler_policy_ref="policy-v1")
    assert first == adapt_legacy_research_objective(payload, tenant_id="tenant", project_id="project", case_id="case", compiler_policy_ref="policy-v1")
    assert first.required_cells[0].origin_type == "legacy_adapter"
    with pytest.raises(LegacyObjectiveAdapterError, match="missing_required_fields"):
        adapt_legacy_research_objective({}, tenant_id="tenant", project_id="project", case_id="case", compiler_policy_ref="policy-v1")
