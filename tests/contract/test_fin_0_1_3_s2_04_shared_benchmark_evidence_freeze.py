from __future__ import annotations

from copy import deepcopy

import pytest

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest
from sec_agent.s2_shared_benchmark_evidence import (
    SharedBenchmarkEvidenceError,
    compile_shared_benchmark_evidence_freeze,
    validate_shared_benchmark_evidence_freeze,
)


def _redigest(row: dict, key: str) -> None:
    row[key] = canonical_digest({name: value for name, value in row.items() if name != key})


def _redigest_visible_and_manifest(bundle: dict) -> None:
    visible = bundle["visible_pack"]
    _redigest(visible, "pack_digest")
    blind = bundle["blind_inputs"]
    blind["shared_pack_digest"] = visible["pack_digest"]
    _redigest(blind, "blind_input_digest")
    hidden = bundle["hidden_scoring"]
    hidden["shared_pack_digest"] = visible["pack_digest"]
    hidden["blind_input_digest"] = blind["blind_input_digest"]
    _redigest(hidden, "hidden_scoring_digest")
    manifest = bundle["manifest"]
    manifest["shared_pack_digest"] = visible["pack_digest"]
    manifest["blind_input_digest"] = blind["blind_input_digest"]
    manifest["hidden_scoring_digest"] = hidden["hidden_scoring_digest"]
    _redigest(manifest, "manifest_digest")


def test_s2_04_freeze_is_deterministic_and_complete() -> None:
    first = compile_shared_benchmark_evidence_freeze()
    second = compile_shared_benchmark_evidence_freeze()
    assert first == second
    assert first["manifest"]["observed_counts"] == {
        "sources": 10,
        "cases": 3,
        "evidence_items": 33,
        "derived_numeric": 12,
        "explicit_gaps": 12,
        "hidden_targets": 12,
    }
    assert first["manifest"]["fairness"] == {
        "same_objective_as_of_source_authority": True,
        "gold_reasoning_visible_to_model": False,
        "hidden_scores_visible_to_model": False,
        "external_tools_enabled": False,
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "mcp_calls": 0,
    }
    assert all("/model_visible/" in path for path in first["manifest"]["artifact_refs"]["model_visible"])
    assert "/evaluator_only/" in first["manifest"]["artifact_refs"]["evaluator_only"]


def test_blind_inputs_exactly_match_visible_evidence_without_hidden_objects() -> None:
    bundle = compile_shared_benchmark_evidence_freeze()
    visible_cases = bundle["visible_pack"]["cases"]
    blind_cases = bundle["blind_inputs"]["cases"]
    for visible, blind in zip(visible_cases, blind_cases, strict=True):
        assert visible["case_key"] == blind["case_key"]
        assert visible["evidence_items"] == blind["evidence_items"]
        assert visible["derived_numeric"] == blind["derived_numeric"]
        assert visible["explicit_gaps"] == blind["explicit_gaps"]
    blind_text = str(bundle["blind_inputs"])
    assert "expected_thesis" not in blind_text
    assert "strongest_counter_thesis" not in blind_text
    assert "required_insights" not in blind_text
    assert "gold_candidate" not in blind_text


@pytest.mark.parametrize("mutation", ["future_source", "cross_case", "hidden_key", "hidden_phrase", "missing_hidden_evidence", "cross_case_hidden_evidence", "numeric_recompute", "digest_tamper"])
def test_s2_04_mutations_fail_closed(mutation: str) -> None:
    bundle = deepcopy(compile_shared_benchmark_evidence_freeze())
    if mutation == "future_source":
        source = bundle["visible_pack"]["source_registry"][0]
        source["published_on"] = "2026-08-07"
        _redigest(source, "source_digest")
        _redigest_visible_and_manifest(bundle)
    elif mutation == "cross_case":
        evidence = bundle["visible_pack"]["cases"][0]["evidence_items"][0]
        evidence["evidence_id"] = "MU_E99"
        _redigest(evidence, "evidence_digest")
        case = bundle["visible_pack"]["cases"][0]
        _redigest(case, "case_evidence_digest")
        bundle["blind_inputs"]["cases"][0]["evidence_items"] = deepcopy(case["evidence_items"])
        _redigest(bundle["blind_inputs"]["cases"][0], "model_visible_digest")
        _redigest_visible_and_manifest(bundle)
    elif mutation == "hidden_key":
        bundle["blind_inputs"]["cases"][0]["expected_thesis"] = "leak"
        _redigest(bundle["blind_inputs"]["cases"][0], "model_visible_digest")
        _redigest(bundle["blind_inputs"], "blind_input_digest")
        bundle["hidden_scoring"]["blind_input_digest"] = bundle["blind_inputs"]["blind_input_digest"]
        _redigest(bundle["hidden_scoring"], "hidden_scoring_digest")
        bundle["manifest"]["blind_input_digest"] = bundle["blind_inputs"]["blind_input_digest"]
        bundle["manifest"]["hidden_scoring_digest"] = bundle["hidden_scoring"]["hidden_scoring_digest"]
        _redigest(bundle["manifest"], "manifest_digest")
    elif mutation == "hidden_phrase":
        bundle["blind_inputs"]["cases"][0]["instructions"].append("业务需求强与当前风险回报未必强必须同时成立并被裁决。")
        _redigest(bundle["blind_inputs"]["cases"][0], "model_visible_digest")
        _redigest(bundle["blind_inputs"], "blind_input_digest")
        bundle["hidden_scoring"]["blind_input_digest"] = bundle["blind_inputs"]["blind_input_digest"]
        _redigest(bundle["hidden_scoring"], "hidden_scoring_digest")
        bundle["manifest"]["blind_input_digest"] = bundle["blind_inputs"]["blind_input_digest"]
        bundle["manifest"]["hidden_scoring_digest"] = bundle["hidden_scoring"]["hidden_scoring_digest"]
        _redigest(bundle["manifest"], "manifest_digest")
    elif mutation == "missing_hidden_evidence":
        target = bundle["hidden_scoring"]["cases"][0]["required_insights"][0]
        target["evidence_ids"] = ["DELL_E404"]
        _redigest(bundle["hidden_scoring"]["cases"][0], "hidden_case_digest")
        _redigest(bundle["hidden_scoring"], "hidden_scoring_digest")
        bundle["manifest"]["hidden_scoring_digest"] = bundle["hidden_scoring"]["hidden_scoring_digest"]
        _redigest(bundle["manifest"], "manifest_digest")
    elif mutation == "cross_case_hidden_evidence":
        target = bundle["hidden_scoring"]["cases"][0]["required_insights"][0]
        target["evidence_ids"] = ["MU_E01"]
        _redigest(bundle["hidden_scoring"]["cases"][0], "hidden_case_digest")
        _redigest(bundle["hidden_scoring"], "hidden_scoring_digest")
        bundle["manifest"]["hidden_scoring_digest"] = bundle["hidden_scoring"]["hidden_scoring_digest"]
        _redigest(bundle["manifest"], "manifest_digest")
    elif mutation == "numeric_recompute":
        case = bundle["visible_pack"]["cases"][0]
        case["derived_numeric"][0]["value"] = "99.99"
        _redigest(case, "case_evidence_digest")
        bundle["blind_inputs"]["cases"][0]["derived_numeric"] = deepcopy(case["derived_numeric"])
        _redigest(bundle["blind_inputs"]["cases"][0], "model_visible_digest")
        _redigest_visible_and_manifest(bundle)
    else:
        bundle["visible_pack"]["pack_digest"] = "0" * 64
    with pytest.raises(SharedBenchmarkEvidenceError):
        validate_shared_benchmark_evidence_freeze(bundle)
