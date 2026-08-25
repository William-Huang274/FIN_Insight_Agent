from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from collections import deque
import hashlib
import json
from pathlib import Path

import pytest

from retrieval.contracts import load_financial_research_kernel
from retrieval.query_plan import canonical_digest
from retrieval.route_compiler import load_query_object_fact_route_policy


ROOT = Path(__file__).resolve().parents[1]


def _runner():
    path = (
        ROOT
        / "scripts"
        / "data_retrieval"
        / "materialize_s1_abbreviation_claim_repair_successor.py"
    )
    spec = spec_from_file_location("abbreviation_claim_repair", path)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _promotion_runner():
    path = (
        ROOT
        / "scripts"
        / "data_retrieval"
        / "promote_s1_abbreviation_claim_repair_to_current_runtime.py"
    )
    spec = spec_from_file_location("abbreviation_claim_repair_promotion", path)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _sha256(relative: str) -> str:
    digest = hashlib.sha256()
    with (ROOT / relative).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _jsonl_tail(relative: str, count: int) -> list[dict]:
    rows: deque[dict] = deque(maxlen=count)
    with (ROOT / relative).open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return list(rows)


def test_R39_keeps_preregistered_v1_compiler_byte_immutable() -> None:
    preregistration = _json(
        "eval_sets/fin_0_1_3_s1/qualification_preregistration_v1_0.json"
    )
    binding = next(
        row
        for row in preregistration["bound_configuration"]
        if row["ref"] == "src/retrieval/object_view_compiler.py"
    )
    assert _sha256(binding["ref"]) == binding["sha256"]


def test_R39_route_successor_enables_only_receipted_v2_segmentation() -> None:
    runner = _runner()
    predecessor = _json(
        "configs/retrieval/"
        "fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_5.json"
    )
    successor = runner.build_successor_route_policy(predecessor)
    compiler = successor["object_compiler"]
    assert compiler["claim_segmentation_mode"] == (
        "sentence_with_wrapped_line_reflow_v2"
    )
    assert compiler["claim_overflow_policy"] == (
        "emit_typed_diagnostic_and_fail_qualification"
    )
    assert successor["authority"] == predecessor["authority"]
    assert successor["candidate_routes"] == predecessor["candidate_routes"]
    kernel = load_financial_research_kernel(
        _json(
            "configs/retrieval/"
            "fin_ia_0_1_3_s1_financial_research_kernel_v1_5.json"
        )
    )
    load_query_object_fact_route_policy(successor, kernel)


def test_R39_real_factory_sentence_compiles_as_one_non_authoritative_object() -> None:
    runner = _runner()
    source_path = (
        ROOT
        / "data/workbench_private/fin_0_1_3_s1b_current_financial_object_store/"
        "v5/records.jsonl"
    )
    source_rows = [
        json.loads(line)
        for line in source_path.read_text(encoding="utf-8").splitlines()[-2:]
        if line.strip()
    ]
    family_rows = []
    objects_path = (
        ROOT
        / "data/workbench_private/fin_0_1_3_s1c_compiled_financial_object_views/"
        "v8/objects.jsonl"
    )
    with objects_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if runner.TARGET_PAGE_ID not in line:
                continue
            row = json.loads(line)
            lineage = (
                (row.get("base_object_view") or {}).get("source_lineage") or {}
            )
            if lineage.get("source_page_record_id") == runner.TARGET_PAGE_ID:
                family_rows.append(row)
    predecessor = _json(
        "configs/retrieval/"
        "fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_5.json"
    )
    kernel = load_financial_research_kernel(
        _json(
            "configs/retrieval/"
            "fin_ia_0_1_3_s1_financial_research_kernel_v1_5.json"
        )
    )
    policy = load_query_object_fact_route_policy(
        runner.build_successor_route_policy(predecessor), kernel
    )
    candidate, diagnostics = runner._compile_repair_object(
        source_rows=source_rows,
        base_objects=family_rows,
        route_policy=policy,
    )
    assert candidate["model_text"] == runner.TARGET_SENTENCE
    assert candidate["base_object_view"]["focus_binding"] == {
        "char_end": 1183,
        "char_start": 1087,
        "mode": "offset_bound_text",
    }
    assert candidate["candidate_not_evidence"] is True
    assert candidate["numeric_authority"] is False
    assert candidate["evidence_promoted"] is False
    assert diagnostics == []


def test_R39_materialized_successor_is_one_exact_append() -> None:
    runner = _runner()
    result = _json(
        "configs/retrieval/"
        "fin_ia_0_1_3_s1_abbreviation_claim_repair_successor_result_v1_0.json"
    )
    body = dict(result)
    assert body.pop("result_digest") == canonical_digest(body)
    assert result["summary"]["base_source_record_count"] == 1888
    assert result["summary"]["successor_source_record_count"] == 1888
    assert result["summary"]["base_object_count"] == 34198
    assert result["summary"]["appended_object_count"] == 1
    assert result["summary"]["successor_object_count"] == 34199
    appended = _jsonl_tail(result["outputs"]["objects_ref"], 1)[0]
    assert appended["compiled_object_id"] == result["summary"][
        "appended_compiled_object_id"
    ]
    assert appended["model_text"] == runner.TARGET_SENTENCE
    assert appended["candidate_not_evidence"] is True
    assert appended["numeric_authority"] is False
    assert _sha256(result["outputs"]["objects_ref"]) == result["outputs"][
        "objects_sha256"
    ]


def test_R39_embedding_and_current_binding_cover_34199_without_authority_gain() -> None:
    embedding = _json(
        "configs/retrieval/"
        "fin_ia_0_1_3_s1c_qwen_embedding_cache_successor_result_v1_3.json"
    )
    assert embedding["runtime"]["base_object_count_reused"] == 34198
    assert embedding["runtime"]["new_object_count_embedded"] == 1
    assert embedding["runtime"]["device"] == "cuda:0"
    assert embedding["runtime"]["parameter_dtype"] == "torch.float16"
    assert embedding["runtime"]["cpu_fallback_count"] == 0
    assert embedding["outputs"]["object_count"] == 34199

    registry = _json(
        "configs/runtime/"
        "fin_ia_0_1_3_clean_baseline_runtime_resource_registry_v1_0.json"
    )
    receipt = _json(
        "configs/runtime/"
        "fin_ia_0_1_3_current_s1_runtime_binding_receipt_v1_15.json"
    )
    assert registry["registry_id"].endswith("R39")
    assert receipt["registry_binding"]["registry_id"].endswith("R39")
    assert receipt["source_object_index_lineage"]["source_record_count"] == 1888
    assert receipt["source_object_index_lineage"]["compiled_object_count"] == 34199
    assert receipt["embedding_index"]["object_count"] == 34199
    assert receipt["acceptance"]["s1_qualified_stable"] is False


def test_R39_failed_R1_is_digest_valid_and_successful_promotion_is_not_replayable() -> None:
    failure = _json(
        "configs/audits/"
        "fin_ia_0_1_3_r39_abbreviation_runtime_promotion_R1_failure_assessment_v1_0.json"
    )
    body = dict(failure)
    assert body.pop("result_digest") == canonical_digest(body)
    assert failure["outputs_created"] == []
    assert failure["authority"]["predecessor_registry_mutated"] is False
    with pytest.raises(FileExistsError, match="runtime_successor_exists"):
        _promotion_runner()._require_new_outputs()
