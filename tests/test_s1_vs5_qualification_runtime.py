from __future__ import annotations

import hashlib
import json
from pathlib import Path

from retrieval.evaluation_assets import (
    EvaluationInput,
    EvaluationReference,
    load_qualification_preregistration,
)
from retrieval.qualification_runtime import load_qualification_runtime_bundle


ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "eval_sets/fin_0_1_3_s1/qualification_preregistration_v1_0.json"
OVERLAY = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1_vs5_qualification_runtime_overlay_v1_0.json"
)
RESULT = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1_vs5_qualification_runtime_inputs_result_v1_0.json"
)
REFERENCE_RESULT = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1_vs5_qualification_references_result_v1_0.json"
)
COMPILED_RESULT = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1_vs5_qualification_compiled_objects_result_v1_0.json"
)
CUDA_PREFLIGHT = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1_vs5_cuda_preflight_result_v1_0.json"
)
REVIEW_PACKET_RESULT = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1_vs5_qualification_review_packet_result_v1_0.json"
)


def _bundle():
    return load_qualification_runtime_bundle(
        repo_root=ROOT,
        preregistration=load_qualification_preregistration(PREREG),
        overlay_path=OVERLAY,
    )


def test_vs5_runtime_overlay_covers_all_new_cases_without_base_case_replacement() -> None:
    bundle = _bundle()
    assert set(bundle.kernel.cases) == {
        "DELL",
        "MU",
        "NVDA",
        "COST",
        "JPM",
        "CAT",
        "NVO",
        "SHEL",
        "0700.HK",
    }
    assert {row for row in bundle.kernel.industry_packs} >= {
        "membership_retail",
        "diversified_banking",
        "industrial_machinery",
        "biopharma",
        "integrated_energy",
        "internet_platform",
    }
    assert all(
        "ANNUAL_REPORT" in slot.source_types for slot in bundle.kernel.slots
    )


def test_vs5_runtime_inputs_are_split_safe_label_free_and_complete() -> None:
    bundle = _bundle()
    assert {key: len(value) for key, value in bundle.inputs_by_split.items()} == {
        "valid_temporal": 5,
        "test_frozen": 10,
        "holdout_heterogeneous": 15,
    }
    rows = [row for values in bundle.inputs_by_split.values() for row in values]
    assert len(rows) == 30
    assert len({row.example_id for row in rows}) == 30
    assert all(row.runtime_input["authority"]["references_visible_to_runtime"] is False for row in rows)
    assert all(row.runtime_input["authority"]["candidate_is_not_evidence"] is True for row in rows)
    assert all(row.runtime_input["authority"]["numeric_fact_authority"] is False for row in rows)
    serialized = json.dumps(
        [row.model_dump(mode="json") for row in rows], ensure_ascii=False
    ).casefold()
    for forbidden in (
        '"gold"',
        '"label"',
        '"expected_outcome"',
        '"hard_negative"',
        '"target_source_record_ids"',
    ):
        assert forbidden not in serialized


def test_materialized_vs5_runtime_input_files_validate_against_contract() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    assert result["summary"] == {
        "candidate_is_not_evidence": True,
        "case_count": 6,
        "example_count": 30,
        "generation_model_calls": 0,
        "learned_vector_calls": 0,
        "network_calls": 0,
        "numeric_fact_authority": False,
        "references_present_in_runtime_inputs": False,
        "split_count": 3,
    }
    for binding in result["outputs"]:
        path = ROOT / binding["ref"]
        rows = [
            EvaluationInput.model_validate_json(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(rows) == binding["example_count"]
        assert all(row.split == binding["split"] for row in rows)


def test_vs5_learned_runtime_is_cuda_fp16_without_cpu_fallback() -> None:
    overlay = json.loads(OVERLAY.read_text(encoding="utf-8"))
    authority = overlay["authority"]
    assert authority["learned_vector_device"] == "cuda"
    assert authority["learned_vector_precision"] == "fp16"
    assert authority["cpu_vector_fallback_allowed"] is False
    assert set(overlay["token_budget_basis"]) == {
        "bge_embedding",
        "qwen_embedding",
        "bge_reranker",
        "qwen_reranker",
    }


def test_vs5_evaluator_references_are_split_bound_and_runtime_invisible() -> None:
    result = json.loads(REFERENCE_RESULT.read_text(encoding="utf-8"))
    assert result["summary"]["example_count"] == 30
    assert result["summary"]["positive_binding_count"] == 130
    assert result["summary"]["coverage_finding_counts"] == {
        "parser_object_failure": 4,
        "source_plan_coverage_failure": 4,
        "source_review_complete": 21,
        "source_review_partial": 1,
    }
    assert result["authority"] == {
        "candidate_is_evidence": False,
        "numeric_fact_authority": False,
        "owner_or_qualified_human_review_pending": True,
        "qualification_execution_authorized": False,
        "runtime_visible": False,
    }

    references: list[EvaluationReference] = []
    for binding in result["outputs"]:
        path = ROOT / binding["ref"]
        assert "/references/" in path.as_posix()
        rows = [
            EvaluationReference.model_validate_json(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(rows) == binding["example_count"]
        assert all(row.split == binding["split"] for row in rows)
        references.extend(rows)

    assert len(references) == 30
    assert len({row.example_id for row in references}) == 30
    assert all(row.review_state == "qualification_blinded" for row in references)
    assert all(
        row.expected_outcome["authority_boundary"]["runtime_may_read_reference"]
        is False
        for row in references
    )
    assert all(
        row.expected_outcome["authority_boundary"]["public_information_gap_declared"]
        is False
        for row in references
    )


def test_vs5_reference_objects_exist_are_case_bound_and_keep_owning_failure() -> None:
    compiled_result = json.loads(COMPILED_RESULT.read_text(encoding="utf-8"))
    object_path = ROOT / compiled_result["output_binding"]["objects_ref"]
    objects = {
        row["compiled_object_id"]: row
        for row in (
            json.loads(line)
            for line in object_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }
    reference_result = json.loads(REFERENCE_RESULT.read_text(encoding="utf-8"))
    references: list[EvaluationReference] = []
    for binding in reference_result["outputs"]:
        references.extend(
            EvaluationReference.model_validate_json(line)
            for line in (ROOT / binding["ref"]).read_text(encoding="utf-8").splitlines()
            if line.strip()
        )

    findings: dict[str, set[str]] = {}
    for reference in references:
        expected = reference.expected_outcome
        case_key = expected["case_key"]
        for candidate in expected["positive_candidates"]:
            value = objects[candidate["compiled_object_id"]]
            assert value["base_object_view"]["ticker"].upper() == case_key.upper()
            assert candidate["candidate_not_evidence"] is True
            assert candidate["numeric_authority"] is False
        findings[reference.example_id] = {
            value["failure_class"] for value in expected["coverage_findings"]
        }

    for proposition in (
        "JPM_NET_INTEREST_INCOME",
        "JPM_CREDIT_QUALITY",
        "JPM_CAPITAL_LIQUIDITY",
        "JPM_FEE_AND_MARKETS_MIX",
    ):
        assert findings[f"VS5::JPM::{proposition}"] == {"parser_object_failure"}
    assert any(
        "source_plan_coverage_failure" in values for values in findings.values()
    )


def test_vs5_cuda_preflight_binds_fp16_models_and_forbids_cpu_fallback() -> None:
    value = json.loads(CUDA_PREFLIGHT.read_text(encoding="utf-8"))
    receipt = value["cuda_execution_receipt"]
    assert value["status"] == "cuda_fp16_eligible_not_execution_authority"
    assert receipt["execution_device"].startswith("cuda:")
    assert receipt["embedding_precision"] == "fp16"
    assert receipt["reranker_precision"] == "fp16"
    assert receipt["fp16_smoke_device"].startswith("cuda:")
    assert receipt["fp16_smoke_dtype"] == "float16"
    assert receipt["cpu_fallback_allowed"] is False
    assert value["execution_contract"]["cpu_vector_fallback_allowed"] is False
    assert value["execution_contract"]["models_loaded_during_preflight"] is False
    assert value["execution_contract"]["vectors_computed_during_preflight"] is False
    assert value["authority"]["valid_temporal_execution_authorized"] is False
    assert value["authority"]["hidden_split_execution_authorized"] is False
    assert {
        key: model["model_digest"] for key, model in value["models"].items()
    } == {
        "bge_embedding": "d6d4a7fc2980e5bde67c1cd013ef87d1a8709464ba982d61a28653070e440cd5",
        "qwen_embedding": "4a3dd5cbc715bf1031d9d10ed6c7f43ff38f2ac5bc19b7fbcdc21787c68be76c",
        "bge_reranker": "80b469d6bddb1e240987d002aae27658be43f83ec3dbbe3ee94ecb4b9301b994",
        "qwen_reranker": "9fa9d067824c3aae0aeee7a773cbb42fac95a06c981ab72e075294bb10845ad2",
    }
    for binding in value["bound_inputs"].values():
        path = ROOT / binding["ref"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == binding["sha256"]


def test_vs5_source_review_packet_is_evaluator_only_and_not_gold() -> None:
    value = json.loads(REVIEW_PACKET_RESULT.read_text(encoding="utf-8"))
    assert value["status"] == "evaluator_only_source_review_packet_materialized_not_gold"
    assert value["summary"] == {
        "example_count": 30,
        "learned_vector_calls": 0,
        "model_calls": 0,
        "network_calls": 0,
        "per_example_limit": 60,
        "references_created": 0,
        "review_candidate_count": 1476,
    }
    assert value["authority"] == {
        "final_gold": False,
        "qualification_execution_authorized": False,
        "runtime_visible": False,
    }
    packet_path = ROOT / value["private_output"]["ref"]
    assert packet_path.is_file()
    assert hashlib.sha256(packet_path.read_bytes()).hexdigest() == value[
        "private_output"
    ]["sha256"]
