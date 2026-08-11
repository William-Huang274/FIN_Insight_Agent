from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.application.bounded_agent_executor import (
    DeepSeekS3ThreeCellNodeExecutor,
    S3ThreeCellBoundedAgentExecutor,
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V8_REF,
)
from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4_REF,
    research_profile_for_ref,
)
from scripts.releases.run_fin_ia_0_1_2_s3_t03_nvda_quarantined_collect_all_diagnostic import (
    _request_from_messages,
    _source_interactions,
)
from sec_agent.canonical_runtime.models import canonical_digest


def test_v8_materializes_truth_from_natural_failed_lead_body() -> None:
    source = _source_interactions()["research_lead"]
    captured_request = _request_from_messages(source["messages"])
    specialists = captured_request["analysis_input"]["specialist_outputs"]
    digests = {
        str(row["program_cell_id"]): canonical_digest(row)
        for row in specialists
    }
    profile = research_profile_for_ref(
        S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4_REF
    )
    surface = S3ThreeCellBoundedAgentExecutor._derive_scoped_identity_surface(
        specialists
    )
    heads = DeepSeekS3ThreeCellNodeExecutor._derive_research_lead_cell_heads(
        specialists,
        digests,
        research_profile=profile,
    )
    alias_table = S3ThreeCellBoundedAgentExecutor._compact_scoped_alias_table(
        specialists,
        surface,
    )
    capacity = DeepSeekS3ThreeCellNodeExecutor._research_lead_v5_capacity_envelope(
        alias_table=alias_table,
        cell_heads=heads,
        research_profile=profile,
    )
    segment = json.loads(source["assistant_output_text"])
    for row in segment["conflict_adjudications"]:
        row.pop("fact_presence_summary", None)

    lead, findings = (
        DeepSeekS3ThreeCellNodeExecutor._assemble_research_lead_v8_output(
            segment,
            specialists,
            surface,
            cell_heads=heads,
            research_profile=profile,
            capacity=capacity,
        )
    )
    assert findings == []
    S3ThreeCellBoundedAgentExecutor._validate_lead_output(
        lead,
        digests,
        specialist_outputs=specialists,
        scoped_identity_surface=surface,
    )

    dependency = next(
        row
        for row in lead["cross_cell_dependencies"]
        if [ref["local_id"] for ref in row["claim_ids"]]
        == ["value_and_profit_capture:local_claim:001"]
    )
    assert "cannot_infer" in dependency["statement"]
    assert "有直接支撑事实" not in dependency["statement"]

    conflict = next(
        row
        for row in lead["conflict_adjudications"]
        if [ref["local_id"] for ref in row["involved_claim_ids"]]
        == [
            "demand_authenticity_and_sustainability:local_claim:001",
            "value_and_profit_capture:local_claim:001",
        ]
    )
    assert conflict["fact_presence_summary"] == "no_facts_present"
    assert conflict["resolution_status"] == "unresolved"
    assert "有直接支撑事实" not in conflict["statement"]


def test_v8_request_omits_runtime_owned_fact_presence_field() -> None:
    source = _source_interactions()["research_lead"]
    captured_request = _request_from_messages(source["messages"])
    specialists = captured_request["analysis_input"]["specialist_outputs"]
    digests = {
        str(row["program_cell_id"]): canonical_digest(row)
        for row in specialists
    }
    profile = research_profile_for_ref(
        S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4_REF
    )
    surface = S3ThreeCellBoundedAgentExecutor._derive_scoped_identity_surface(
        specialists
    )
    heads = DeepSeekS3ThreeCellNodeExecutor._derive_research_lead_cell_heads(
        specialists,
        digests,
        research_profile=profile,
    )
    alias_table = S3ThreeCellBoundedAgentExecutor._compact_scoped_alias_table(
        specialists,
        surface,
    )
    capacity = DeepSeekS3ThreeCellNodeExecutor._research_lead_v5_capacity_envelope(
        alias_table=alias_table,
        cell_heads=heads,
        research_profile=profile,
    )
    _, request, binding = DeepSeekS3ThreeCellNodeExecutor._research_lead_v8_request(
        {
            "input_digest": captured_request["analysis_input"]["input_digest"],
            "lead_contract": captured_request["analysis_input"]["lead_contract"],
            "specialist_outputs": specialists,
            "scoped_identity_surface": surface,
        },
        heads,
        research_profile=profile,
        capacity=capacity,
    )

    assert (
        request["research_lead_transport_ref"]
        == S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V8_REF
    )
    assert "fact_presence_summary" not in request["required_output_schema"][
        "conflict_adjudications"
    ][0]
    assert request["output_constraints"]["provider_emits_fact_presence_summary"] is False
    assert binding["research_lead_transport_ref"] == (
        S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V8_REF
    )
