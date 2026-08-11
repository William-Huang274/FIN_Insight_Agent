from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.bounded_agent_executor import (
    S3ThreeCellBoundedAgentInputPack,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t05_b_current_product_identity import (
    compile_current_product_case_identity,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t05_three_case_transfer import (
    Fin012S4T05TransferError,
    validate_transfer_evidence_pack,
)
from sec_agent.canonical_runtime.models import canonical_digest


EVIDENCE_PACK_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t05_b_dell_current_evidence_pack_v1_0.json"
)
AGENT_INPUT_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t05_b_dell_agent_exact_input_v1_0.json"
)
RESULT_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t05_b_dell_current_evidence_and_"
    "agent_exact_input_zero_call_materialization_v1_0.json"
)
PROJECTION_REF = Path(
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_55.json"
)


def _load(ref: Path) -> dict[str, object]:
    return json.loads((ROOT / ref).read_text(encoding="utf-8"))


def _sha256(ref: str) -> str:
    return hashlib.sha256((ROOT / ref).read_bytes()).hexdigest()


def test_tracked_dell_current_evidence_and_agent_input_are_closed_and_bound() -> None:
    pack = validate_transfer_evidence_pack(_load(EVIDENCE_PACK_REF), case_key="DELL")
    agent_payload = _load(AGENT_INPUT_REF)
    agent = S3ThreeCellBoundedAgentInputPack.model_validate(agent_payload)
    result = _load(RESULT_REF)

    assert result["materialization_digest"] == canonical_digest(
        {key: value for key, value in result.items() if key != "materialization_digest"}
    )
    for binding in result["immutable_bindings"]:
        assert _sha256(binding["ref"]) == binding["sha256"]
    assert _sha256(result["compiled_outputs"]["evidence_pack_ref"]) == (
        result["compiled_outputs"]["evidence_pack_sha256"]
    )
    assert _sha256(result["compiled_outputs"]["agent_exact_input_ref"]) == (
        result["compiled_outputs"]["agent_exact_input_sha256"]
    )

    assert agent.input_digest == canonical_digest(
        {key: value for key, value in agent_payload.items() if key != "input_digest"}
    )
    expected_case_id = compile_current_product_case_identity(
        "DELL",
        t01_entry_digest=pack["t01_entry_digest"],
        evidence_pack_digest=pack["evidence_pack_digest"],
    )
    assert agent.case_id == expected_case_id
    assert "oracle" not in agent.case_id
    assert agent.lineage["S4_T04_source_grounded_input"]["digest"] == (
        pack["evidence_pack_digest"]
    )

    pack_evidence_refs = {row["evidence_ref"] for row in pack["evidence_rows"]}
    pack_numeric_refs = {row["numeric_ref"] for row in pack["numeric_rows"]}
    agent_evidence_refs: set[str] = set()
    agent_numeric_refs: set[str] = set()
    cell_counts: dict[str, int] = {}
    for cell in agent_payload["cell_inputs"]:
        authority = cell["authority_refs"]
        evidence_refs = set(authority["accepted_evidence_refs"])
        numeric_refs = set(authority["numeric_refs"])
        agent_evidence_refs.update(evidence_refs)
        agent_numeric_refs.update(numeric_refs)
        cell_counts[cell["program_cell_id"]] = len(evidence_refs)
    assert agent_evidence_refs == pack_evidence_refs
    assert agent_numeric_refs == pack_numeric_refs
    assert cell_counts == {
        "demand_authenticity_and_sustainability": 6,
        "value_and_profit_capture": 3,
        "bottleneck_counterevidence_and_what_would_change": 6,
    }
    assert {row["metric_family"] for row in pack["numeric_rows"]} == {
        "revenue",
        "gross_profit",
        "operating_income",
    }
    assert len(pack["typed_gaps"]) == 3

    assert agent.hard_boundaries["source_network_calls_allowed"] is False
    assert agent.hard_boundaries["external_tool_calls_allowed"] is False
    assert agent.hard_boundaries["live_business_case_head_writes_allowed"] is False
    assert agent.s4_case_runtime["paid_execution_authorized"] is False
    assert result["observed_new_counts"] == {
        "admissions": 0,
        "business_artifacts": 0,
        "business_runs": 0,
        "local_retrieval_or_tool_invocations": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "source_network_calls": 0,
    }
    assert result["stage_acceptance"] == {
        "DELL_current_R2": False,
        "MU_current_R2": False,
        "S4_T05_B_DELL_Agent_live": "not_started",
        "S4_T05_B_DELL_Evidence_and_Agent_input": "engineering_pass_zero_call",
        "S4_T05_B_DELL_Search": "pass_live_current_candidate_pack_ready",
        "post_transfer_NVDA_R2": False,
    }
    projection = _load(PROJECTION_REF)
    assert projection["sequence_after_projection"] == "v2_54"
    assert projection["current_truth"]["S4_T05_B_DELL_Evidence_and_Agent_input"] == (
        "engineering_pass_zero_call"
    )
    assert projection["current_truth"]["DELL_current_R2"] is False
    assert projection["current_truth"]["current_next_action"] == result["next_action"]
    assert projection["T05_B_DELL_compiled_current_surface"][
        "materialization_sha256"
    ] == _sha256(str(RESULT_REF).replace("\\", "/"))


def test_tracked_pack_identity_and_numeric_mutations_fail_closed() -> None:
    pack = _load(EVIDENCE_PACK_REF)
    mutations = []
    cross_case = deepcopy(pack)
    cross_case["evidence_rows"][0]["entity_ref"] = "MU"
    mutations.append(cross_case)
    numeric = deepcopy(pack)
    numeric["numeric_rows"][0]["value"] = "1"
    mutations.append(numeric)
    for changed in mutations:
        changed["evidence_pack_digest"] = canonical_digest(
            {key: value for key, value in changed.items() if key != "evidence_pack_digest"}
        )
        with pytest.raises(Exception):
            validate_transfer_evidence_pack(changed, case_key="DELL")


def test_t05_b_current_product_identity_is_stable_distinct_and_fail_closed() -> None:
    identities = {
        case_key: compile_current_product_case_identity(
            case_key,
            t01_entry_digest="1" * 64,
            evidence_pack_digest="2" * 64,
        )
        for case_key in ("DELL", "MU", "NVDA")
    }
    assert len(set(identities.values())) == 3
    for case_key, identity in identities.items():
        assert identity.startswith(
            f"fin012-s4-t05-{case_key.lower()}-current-evidence-"
        )
        assert "oracle" not in identity
        assert identity == compile_current_product_case_identity(
            case_key,
            t01_entry_digest="1" * 64,
            evidence_pack_digest="2" * 64,
        )
    with pytest.raises(
        Fin012S4T05TransferError,
        match="s4_t05_b_current_case_identity_digest_invalid",
    ):
        compile_current_product_case_identity(
            "DELL",
            t01_entry_digest="invalid",
            evidence_pack_digest="2" * 64,
        )
