from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from sec_agent.canonical_runtime import canonical_digest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/research/materialize_s3_R17_reversal_gate_successor.py"
SPEC = importlib.util.spec_from_file_location("s3_r17_reversal_gate", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)
DECISION_PATH = ROOT / RUNNER.DEFAULT_DECISION
PUBLIC_PATH = (
    ROOT
    / "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_R10_protected_writer_"
    "R17_reversal_gate_successor_candidate_result_v1_0.json"
)
PROVENANCE_CORRECTION_PATH = (
    ROOT
    / "configs/research/evals/"
    "fin_ia_0_1_3_s3_R16_editorial_provenance_correction_v1_0.json"
)


def _required_R16_private_path() -> Path:
    decision = json.loads(DECISION_PATH.read_text(encoding="utf-8"))
    return ROOT / decision["source_bindings"]["R16_private_full_result"]["ref"]


def test_R17_decision_binds_scope_and_implementations() -> None:
    decision = json.loads(DECISION_PATH.read_text(encoding="utf-8"))
    unsigned = {
        key: value for key, value in decision.items() if key != "decision_digest"
    }

    assert decision["decision_digest"] == canonical_digest(unsigned)
    assert sorted(RUNNER._REPLACEMENTS) == sorted(
        decision["change_boundary"]["allowed_changed_model_text_paths"]
    )
    assert decision["change_boundary"]["one_off_threshold_breach_is_insufficient"] is True
    assert decision["change_boundary"]["persistent_below_threshold_evidence_is_insufficient"] is True
    assert decision["implementation_bindings"] == RUNNER._implementation_refs()
    assert decision["execution_budget"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "new_evidence_items": 0,
        "candidate_promotions": 0,
    }


def test_R17_reversal_gate_requires_explicit_conjunction() -> None:
    section = RUNNER._REPLACEMENTS["sections[5].clauses[5].model_text"]
    wwc = RUNNER._REPLACEMENTS["what_would_change[5].model_text"]

    assert RUNNER.reversal_gate_is_conjunctive(section, wwc) is True
    assert "persist or breach" not in section
    assert "persistent, and evaluated as breaching" in section
    assert "persistent, and evaluated as breaching" in wwc

    one_off_breach = section.replace("persistent, and ", "one-off and ")
    persistent_below = section.replace(
        "evaluated as breaching", "evaluated as remaining below"
    )
    assert RUNNER.reversal_gate_is_conjunctive(one_off_breach, wwc) is False
    assert RUNNER.reversal_gate_is_conjunctive(persistent_below, wwc) is False
    assert RUNNER.reversal_gate_is_conjunctive(
        section.replace("persistent, and evaluated", "persistent or evaluated"),
        wwc,
    ) is False


def test_R17_compile_preserves_authority_and_reference_boundaries() -> None:
    predecessor_private = _required_R16_private_path()
    if not predecessor_private.is_file():
        pytest.skip("private R16 predecessor is not present in this checkout")
    public = RUNNER.compile_successor()["public"]

    assert public["edit_receipt"]["changed_model_text_paths"] == [
        "sections[5].clauses[5].model_text",
        "what_would_change[5].model_text",
    ]
    assert public["edit_receipt"]["reference_projection_unchanged"] is True
    assert public["edit_receipt"]["remaining_gaps_unchanged"] is True
    assert public["edit_receipt"]["topology_unchanged"] is True
    assert public["local_validation"]["reversal_gate_conjunction_proved"] is True
    assert public["implementation_refs"] == RUNNER._implementation_refs()
    assert public["execution"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "new_evidence_items": 0,
        "candidate_promotions": 0,
    }
    assert public["acceptance"]["fresh_independent_post_writer_review_pass"] is False
    assert public["acceptance"]["S3_pass"] is False


def test_R17_compile_guard_skips_when_R16_private_is_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing = tmp_path / "absent-R16-private.json"
    monkeypatch.setattr(
        sys.modules[__name__],
        "_required_R16_private_path",
        lambda: missing,
    )

    with pytest.raises(pytest.skip.Exception):
        test_R17_compile_preserves_authority_and_reference_boundaries()


def test_R17_public_receipt_is_clean_checkout_revalidatable() -> None:
    public = json.loads(PUBLIC_PATH.read_text(encoding="utf-8"))
    unsigned = {key: value for key, value in public.items() if key != "result_digest"}

    assert public["result_digest"] == canonical_digest(unsigned)
    assert public["implementation_refs"] == RUNNER._implementation_refs()
    private_path = ROOT / public["private_full_result_ref"]
    if not private_path.is_file():
        pytest.skip("private R17 materialization is not present in this checkout")
    private = json.loads(private_path.read_text(encoding="utf-8"))
    assert hashlib.sha256(private_path.read_bytes()).hexdigest() == public[
        "private_full_result_sha256"
    ]
    assert private["full_result_digest"] == public["private_full_result_digest"]
    assert private["implementation_refs"] == public["implementation_refs"]


def test_R16_editorial_author_provenance_correction_is_append_only() -> None:
    correction = json.loads(
        PROVENANCE_CORRECTION_PATH.read_text(encoding="utf-8")
    )
    unsigned = {
        key: value for key, value in correction.items() if key != "receipt_digest"
    }

    assert correction["receipt_digest"] == canonical_digest(unsigned)
    assert correction["corrected_paths"] == [
        "sections[4].clauses[4].model_text",
        "sections[5].clauses[1].model_text",
        "what_would_change[1].model_text",
    ]
    attribution = correction["corrected_attribution"]
    assert attribution["exact_wording_author"] == "current_Codex"
    assert attribution["exact_owner_wording_receipt_present"] is False
    assert all(
        value is False
        for value in correction["content_or_authority_change"].values()
    )
    for key, value in correction["bound_predecessors"].items():
        if not key.endswith("_ref"):
            continue
        sha_key = key.removesuffix("_ref") + "_sha256"
        path = ROOT / value
        assert hashlib.sha256(path.read_bytes()).hexdigest() == correction[
            "bound_predecessors"
        ][sha_key]
