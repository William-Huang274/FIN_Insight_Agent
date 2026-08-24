from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from sec_agent.canonical_runtime import canonical_digest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/research/materialize_s3_R16_bounded_writer_successor.py"
SPEC = importlib.util.spec_from_file_location("s3_r16_bounded_successor", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)
DECISION_PATH = ROOT / RUNNER.DEFAULT_DECISION
PUBLIC_PATH = (
    ROOT
    / "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_R10_protected_writer_"
    "R16_bounded_successor_candidate_result_v1_0.json"
)


def test_R16_decision_and_replacement_scope_are_digest_bound() -> None:
    decision = json.loads(DECISION_PATH.read_text(encoding="utf-8"))
    unsigned = {
        key: value for key, value in decision.items() if key != "decision_digest"
    }

    assert decision["decision_digest"] == canonical_digest(unsigned)
    assert sorted(RUNNER._REPLACEMENTS) == sorted(
        decision["change_boundary"]["allowed_changed_model_text_paths"]
    )
    assert decision["execution_budget"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "new_evidence_items": 0,
        "candidate_promotions": 0,
    }


def test_R16_material_correction_keeps_distinct_financial_gates() -> None:
    section = RUNNER._REPLACEMENTS["sections[5].clauses[5].model_text"]
    wwc = RUNNER._REPLACEMENTS["what_would_change[5].model_text"]

    for text in (section, wwc):
        assert "material" in text
        assert "AI-linked" in text
        assert "predeclared threshold" in text
        assert "working-capital" in text or "working capital" in text
        assert "reconciled cash-flow bridge" in text
    assert "not interchangeable" in wwc
    assert "would help distinguish" in RUNNER._REPLACEMENTS[
        "sections[5].clauses[1].model_text"
    ]


@pytest.mark.skipif(
    not PUBLIC_PATH.is_file(),
    reason="private R16 materialization is not present in this checkout",
)
def test_R16_materialized_receipt_revalidates_without_authority_expansion() -> None:
    public = json.loads(PUBLIC_PATH.read_text(encoding="utf-8"))
    private_path = ROOT / public["private_full_result_ref"]
    private = json.loads(private_path.read_text(encoding="utf-8"))

    assert hashlib.sha256(private_path.read_bytes()).hexdigest() == public[
        "private_full_result_sha256"
    ]
    assert public["private_full_result_digest"] == private["full_result_digest"]
    assert public["edit_receipt"]["reference_projection_unchanged"] is True
    assert public["edit_receipt"]["remaining_gaps_unchanged"] is True
    assert public["local_validation"] == {
        "surface_finding_count": 0,
        "hard_finding_count": 0,
        "quality_finding_count": 0,
        "protected_contract_pass": True,
    }
    assert public["execution"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "new_evidence_items": 0,
        "candidate_promotions": 0,
    }
    assert public["acceptance"]["independent_post_writer_review_pass"] is False
    assert public["acceptance"]["S3_pass"] is False
