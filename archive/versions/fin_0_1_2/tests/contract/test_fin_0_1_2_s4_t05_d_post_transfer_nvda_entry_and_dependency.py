from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "tests" / "contract")]

from apps.workbench.backend.application.bounded_agent_executor import (  # noqa: E402
    S3ThreeCellBoundedAgentInputPack,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t05_current_case_agent_exact_execution import (  # noqa: E402
    Fin012S4T05CurrentCaseAgentExecutionError,
    prepare_current_case_agent_execution,
)
from scripts.releases.audit_fin_ia_0_1_2_s4_t05_d_post_transfer_nvda_entry_and_dependency import (  # noqa: E402
    AGENT_INPUT_REF,
    DECISION_REF,
    _principal,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


EVIDENCE_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t04_nvda_current_evidence_pack_v1_0.json"
)


def _load(ref: Path) -> dict:
    return json.loads((ROOT / ref).read_text(encoding="utf-8"))


def _recompute_input_digest(value: dict) -> dict:
    value["input_digest"] = canonical_digest(
        {key: row for key, row in value.items() if key != "input_digest"}
    )
    return value


def test_entry_decision_is_content_addressed_and_keeps_live_unstarted() -> None:
    decision = _load(DECISION_REF)
    agent_input = _load(AGENT_INPUT_REF)
    assert decision["decision_digest"] == canonical_digest(
        {key: row for key, row in decision.items() if key != "decision_digest"}
    )
    assert decision["status"] == (
        "pass_search_reuse_and_zero_call_post_transfer_chain_proven_"
        "fresh_live_not_authorized"
    )
    assert decision["authority_boundary"] == {
        "new_source_network_calls": 0,
        "new_model_calls": 0,
        "new_provider_calls": 0,
        "new_admissions": 0,
        "new_exact_live_runs": 0,
        "business_artifacts": 0,
        "fresh_live_authorized": False,
        "post_transfer_NVDA_R2": False,
    }
    assert decision["search_and_evidence_reuse_decision"][
        "second_search_or_source_refresh_required_now"
    ] is False
    assert decision["zero_call_full_chain_reproof"] == {
        "fresh_runtime_roots": 2,
        "normalized_results_equal": True,
        "provider_callbacks": 9,
        "compiled_interactions": 9,
        "local_fact_receipts": 3,
        "provider_output_captures": 9,
        "formal_artifacts": 9,
        "aggregate_estimated_input_tokens": 85614,
        "maximum_single_interaction_estimated_input_tokens": 15678,
        "maximum_input_tokens": 108000,
        "input_token_headroom": 22386,
    }
    assert decision["compiled_post_transfer_input"]["sha256"] == hashlib.sha256(
        (ROOT / AGENT_INPUT_REF).read_bytes()
    ).hexdigest()
    assert agent_input["input_digest"] == canonical_digest(
        {key: row for key, row in agent_input.items() if key != "input_digest"}
    )
    for binding in decision["immutable_bindings"]:
        assert hashlib.sha256((ROOT / binding["ref"]).read_bytes()).hexdigest() == (
            binding["sha256"]
        )


def test_nvda_legacy_lineage_is_accepted_only_with_exact_current_evidence_digest() -> None:
    evidence = _load(EVIDENCE_REF)
    input_value = _load(AGENT_INPUT_REF)
    input_pack = S3ThreeCellBoundedAgentInputPack.model_validate(input_value)
    prepared = prepare_current_case_agent_execution(
        input_pack,
        evidence,
        case_key="NVDA",
        principal=_principal(),
        execution_identity="fin012-s4-t05d-lineage-positive",
    )
    assert prepared.input_digest == input_value["input_digest"]

    changed = deepcopy(input_value)
    changed["lineage"]["T04_financial_pack"]["digest"] = "0" * 64
    changed = _recompute_input_digest(changed)
    with pytest.raises(
        Fin012S4T05CurrentCaseAgentExecutionError,
        match="s4_t05_current_case_agent_exact_input_binding_invalid",
    ):
        prepare_current_case_agent_execution(
            S3ThreeCellBoundedAgentInputPack.model_validate(changed),
            evidence,
            case_key="NVDA",
            principal=_principal(),
            execution_identity="fin012-s4-t05d-lineage-mutated",
        )


def test_nvda_missing_legacy_lineage_slot_fails_before_provider() -> None:
    evidence = _load(EVIDENCE_REF)
    changed = deepcopy(_load(AGENT_INPUT_REF))
    changed["lineage"].pop("T04_financial_pack")
    changed = _recompute_input_digest(changed)
    with pytest.raises(
        Fin012S4T05CurrentCaseAgentExecutionError,
        match="s4_t05_current_case_evidence_lineage_missing",
    ):
        prepare_current_case_agent_execution(
            S3ThreeCellBoundedAgentInputPack.model_validate(changed),
            evidence,
            case_key="NVDA",
            principal=_principal(),
            execution_identity="fin012-s4-t05d-lineage-missing",
        )
