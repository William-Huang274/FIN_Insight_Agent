from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path
import shutil

import pytest

from sec_agent.research.current_dynamic_writer import (
    CURRENT_DYNAMIC_WRITER_RUN_SCOPE,
    CurrentDynamicWriterError,
    expected_current_dynamic_writer_budget,
    validate_r10_protected_writer_draft,
)
from sec_agent.research.multi_agent_report_authority import (
    protected_report_draft_tool,
    render_protected_report,
)
from sec_agent.project_os_preflight import (
    _validate_current_dynamic_writer_decision,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/research/run_s3_current_dynamic_writer_zero_call.py"
SPEC = importlib.util.spec_from_file_location("current_dynamic_writer_zero", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
ZERO = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ZERO)


@pytest.fixture(scope="module")
def bundle():
    return ZERO.build_zero_call_bundle()


def test_R10_writer_zero_call_compiles_complete_protected_frontier(bundle) -> None:
    zero = bundle["zero"]
    catalog = bundle["catalog"]
    protection = bundle["protection"]
    assert zero["run_scope_id"] == CURRENT_DYNAMIC_WRITER_RUN_SCOPE
    assert zero["execution_budget"] == expected_current_dynamic_writer_budget()
    assert len(zero["checks"]) == 17
    assert all(zero["checks"].values())
    assert zero["execution"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "new_S1_S2_requests": 0,
        "new_retrieval_rounds": 0,
        "candidate_promotions": 0,
        "writer_called": False,
    }
    assert catalog["writer_protection_projection"]["forbidden_claim_refs"] == (
        protection["forbidden_claim_refs"]
    )
    assert catalog["writer_protection_projection"][
        "forbidden_authority_refs"
    ] == protection["forbidden_authority_refs"]
    tool_text = str(protected_report_draft_tool(authority_catalog=catalog))
    assert all(ref not in tool_text for ref in protection["forbidden_claim_refs"])
    assert all(
        ref not in tool_text for ref in protection["forbidden_authority_refs"]
    )


def test_R10_writer_positive_draft_validates_and_renders(bundle) -> None:
    catalog = bundle["catalog"]
    protection = bundle["protection"]
    payload = ZERO._positive_payload(catalog, protection)
    trusted = validate_r10_protected_writer_draft(
        payload,
        authority_catalog=catalog,
        protection=protection,
    )
    rendered = render_protected_report(trusted, authority_catalog=catalog)
    assert trusted["writer_protection_receipt"][
        "global_forbidden_surface_pass"
    ] is True
    assert rendered["status"] == "multi_agent_protected_report_rendered"


@pytest.mark.parametrize(
    "text",
    [
        "Revenue improved by eighty-eight percent in the quarter.",
        "Revenue improved by the second sequential step in the quarter.",
        "收入同比提高百分之八十八。",
        "本期涉及三家客户。",
    ],
)
def test_R10_writer_rejects_spelled_out_numeric_and_ordinal_surfaces(
    bundle, text: str
) -> None:
    catalog = bundle["catalog"]
    protection = bundle["protection"]
    payload = deepcopy(ZERO._positive_payload(catalog, protection))
    payload["sections"][1]["clauses"][0]["model_text"] = text
    with pytest.raises(
        CurrentDynamicWriterError,
        match="current_dynamic_writer_protected_surface_forbidden",
    ):
        validate_r10_protected_writer_draft(
            payload,
            authority_catalog=catalog,
            protection=protection,
        )


def test_R10_writer_cash_and_cohort_protections_are_conditional(bundle) -> None:
    catalog = bundle["catalog"]
    protection = bundle["protection"]
    payload = deepcopy(ZERO._positive_payload(catalog, protection))
    payload["executive_thesis"][0]["model_text"] = (
        "Demand is strong under the reviewed evidence."
    )
    with pytest.raises(
        CurrentDynamicWriterError,
        match="current_dynamic_writer_conditional_protection_invalid",
    ):
        validate_r10_protected_writer_draft(
            payload,
            authority_catalog=catalog,
            protection=protection,
        )

    payload = deepcopy(ZERO._positive_payload(catalog, protection))
    payload["sections"][3]["clauses"][0]["model_text"] = (
        "The balance-sheet movement indicates working-capital pressure."
    )
    with pytest.raises(
        CurrentDynamicWriterError,
        match="current_dynamic_writer_conditional_protection_invalid",
    ):
        validate_r10_protected_writer_draft(
            payload,
            authority_catalog=catalog,
            protection=protection,
        )


def test_R10_writer_rejects_spelled_numeric_surface_in_heading(bundle) -> None:
    catalog = bundle["catalog"]
    protection = bundle["protection"]
    payload = deepcopy(ZERO._positive_payload(catalog, protection))
    payload["sections"][0]["heading"] = "Three demand signals"
    with pytest.raises(
        CurrentDynamicWriterError,
        match="current_dynamic_writer_protected_surface_forbidden",
    ):
        validate_r10_protected_writer_draft(
            payload,
            authority_catalog=catalog,
            protection=protection,
        )


def test_R10_writer_scope_decision_passes_project_os_validator_without_live_calls(
    bundle,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generated = {
        ZERO.SOURCE_BOUND_REVIEW_REF: bundle["review"],
        ZERO.SOURCE_BOUND_PROGRAM_REF: bundle["program"],
        ZERO.WRITER_AUTHORITY_CATALOG_REF: bundle["catalog"],
        ZERO.WRITER_PROTECTION_REF: bundle["protection"],
        ZERO.ZERO_CALL_RESULT_REF: bundle["zero"],
    }
    original_path = ZERO._path

    def routed_path(ref: str) -> Path:
        if ref in generated:
            return (tmp_path / ref).resolve()
        return original_path(ref)

    monkeypatch.setattr(ZERO, "_path", routed_path)
    for ref, value in generated.items():
        ZERO._write_new(ref, value)
    decision = ZERO._build_scope_decision()

    all_bindings = [
        *decision["bound_inputs"].values(),
        *decision["implementation_bindings"],
        *bundle["zero"]["source_bindings"].values(),
    ]
    for binding in all_bindings:
        ref = str(binding["ref"])
        target = (tmp_path / ref).resolve()
        if target.is_file():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / ref, target)

    projection = _validate_current_dynamic_writer_decision(
        root=tmp_path,
        decision=decision,
    )
    assert projection["current_dynamic_multi_agent_protected_writer"] is True
    assert projection["execution_limits"] == expected_current_dynamic_writer_budget()
    assert projection["clean_proof_status"] == (
        "R10_bound_protected_writer_zero_call_proven"
    )

    mutated = deepcopy(decision)
    mutated["implementation_bindings"][0]["sha256"] = "0" * 64
    mutated_body = deepcopy(mutated)
    mutated_body.pop("decision_digest")
    mutated["decision_digest"] = ZERO.canonical_digest(mutated_body)
    with pytest.raises(ValueError, match="nested_binding_sha_drift"):
        _validate_current_dynamic_writer_decision(
            root=tmp_path,
            decision=mutated,
        )
