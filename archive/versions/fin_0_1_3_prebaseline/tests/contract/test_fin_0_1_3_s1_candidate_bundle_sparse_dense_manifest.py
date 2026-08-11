from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_candidate_bundle_index_manifest import (  # noqa: E402
    CandidateBundleIndexManifestError,
    compile_candidate_bundle_index_manifest,
    execute_fake_sparse_dense_build,
    load_candidate_bundle_index_policy,
    materialize_candidate_bundle_index_zero_call_proof,
    validate_candidate_bundle_index_specs,
    validate_candidate_bundle_index_zero_call_proof,
)


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_candidate_bundle_sparse_dense_manifest_r4_policy_v1_0.json"
)
RESULT_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s1_candidate_bundle_sparse_dense_manifest_"
    "r4_zero_call_proof_v1_0.json"
)
PROOF_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s1_candidate_bundle_sparse_dense_manifest_"
    "r4_clean_independent_proof_v1_0.json"
)
R3_RESULT_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s1_candidate_bundle_sparse_dense_manifest_"
    "zero_call_proof_v1_0.json"
)
R3_RUNTIME_ROOT = ROOT / (
    "data/workbench_private/"
    "fin_0_1_3_s1_candidate_bundle_sparse_dense_manifest/zero-call-r3"
)
R4_RUNTIME_ROOT = ROOT / (
    "data/workbench_private/"
    "fin_0_1_3_s1_candidate_bundle_sparse_dense_manifest/zero-call-r4"
)


def _policy() -> dict:
    return load_candidate_bundle_index_policy(POLICY_PATH, repo_root=ROOT)


def _private_manifest(result_path: Path, runtime_root: Path) -> dict:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    ref = result["private_manifest"]
    path = runtime_root / "objects" / Path(ref["object_key"])
    assert __import__("hashlib").sha256(path.read_bytes()).hexdigest() == ref["digest"]
    return json.loads(path.read_text(encoding="utf-8"))


def test_policy_binds_r9_result_clean_proof_and_attempt_lineage() -> None:
    policy = _policy()
    artifacts = {
        row["artifact_id"]: row for row in policy["locked_artifacts"]
    }
    assert policy["attempt_id"].endswith("_r4")
    assert policy["predecessor_failure_refs"] == [
        "configs/releases/fin_ia_0_1_3_s1_candidate_bundle_sparse_dense_manifest_zero_call_r1_failure_v1_0.json",
        "configs/releases/fin_ia_0_1_3_s1_candidate_bundle_sparse_dense_manifest_zero_call_r2_failure_v1_0.json",
        "configs/releases/fin_ia_0_1_3_s1_candidate_bundle_sparse_dense_manifest_zero_call_r3_business_audit_failure_v1_0.json",
    ]
    assert artifacts["held_out_reparse_result"]["path"].endswith(
        "successor_r9_result_v1_0.json"
    )
    assert artifacts["held_out_clean_proof"]["path"].endswith(
        "successor_r9_clean_independent_proof_v1_0.json"
    )
    assert policy["private_object_inputs"][
        "held_out_reparse_runtime_root_ref"
    ].endswith("/zero-call-r9")


def test_manifest_uses_six_case_selected_candidate_bundles_without_answer_labels() -> None:
    policy = _policy()
    specs, quarantine, summary = compile_candidate_bundle_index_manifest(
        policy=policy,
        repo_root=ROOT,
    )
    validate_candidate_bundle_index_specs(specs, policy=policy)
    assert len(specs) == len({row["vector_id"] for row in specs}) == 93
    assert Counter(row["case_key"] for row in specs) == {
        "DELL": 15,
        "MU": 16,
        "NVDA": 14,
        "ORCL": 19,
        "ASML": 10,
        "ANET": 19,
    }
    assert all(
        row["selection_basis"] == "reviewed_candidate_qualification"
        for row in specs
        if row["case_key"] in {"DELL", "MU", "NVDA"}
    )
    assert all(
        row["selection_basis"] == "strict_structured_metric_policy"
        and row["object_type"] == "metric"
        and row["table_path"]
        and row["currency_unit_authority"]
        and (
            row["metric_period"] in row["table_path"]["column_label"]
            or row["metric_period"] == row["source_reporting_period_end"][:4]
        )
        and row["metric_period_role"]
        in {"instant", "qtd", "ytd", "annual", "ttm"}
        and row["metric_unit"]
        == row["currency_unit_authority"]["canonical_unit"]
        for row in specs
        if row["case_key"] in {"ORCL", "ASML", "ANET"}
    )
    assert len(quarantine) == 19
    assert all(row["object_type"] == "claim" for row in quarantine)
    assert summary["qrels_or_gold_selection_inputs"] == 0
    assert all(
        "business_meaning_zh" not in row["vector_text"]
        and "content_limitation_zh" not in row["vector_text"]
        for row in specs
    )


def test_fake_sparse_and_dense_build_terminalize_the_same_manifest() -> None:
    policy = _policy()
    specs, _, _ = compile_candidate_bundle_index_manifest(
        policy=policy,
        repo_root=ROOT,
    )
    result = execute_fake_sparse_dense_build(specs, policy=policy)
    assert result == {
        "batch_count_each": 3,
        "sparse_inserted_specs": 93,
        "dense_inserted_specs": 93,
        "fake_embedding_vectors": 93,
        "fake_embedding_dimension": 1024,
        "terminal_count_each": 93,
    }
    with pytest.raises(
        CandidateBundleIndexManifestError,
        match="candidate_bundle_index_sparse_partial_insert",
    ):
        execute_fake_sparse_dense_build(specs, policy=policy, sparse_partial=True)
    with pytest.raises(
        CandidateBundleIndexManifestError,
        match="candidate_bundle_index_dense_partial_insert",
    ):
        execute_fake_sparse_dense_build(specs, policy=policy, dense_partial=True)


def test_r4_manifest_preserves_known_cases_and_only_carries_reviewed_role_changes() -> None:
    if not RESULT_PATH.exists():
        pytest.skip("R4 manifest result not materialized")
    r3 = _private_manifest(R3_RESULT_PATH, R3_RUNTIME_ROOT)
    r4 = _private_manifest(RESULT_PATH, R4_RUNTIME_ROOT)
    known = {"DELL", "MU", "NVDA"}
    known_identity = lambda rows: {
        (
            row["case_key"],
            row["target_id"],
            row["object_type"],
            tuple(row["slot_ids"]),
            row["vector_text_sha256"],
        )
        for row in rows
        if row["case_key"] in known
    }
    assert known_identity(r3["specs"]) == known_identity(r4["specs"])
    held_out = [
        row for row in r4["specs"] if row["case_key"] not in known
    ]
    assert len(held_out) == 48
    assert Counter(row["metric_period_role"] for row in held_out) == {
        "instant": 18,
        "qtd": 10,
        "ytd": 8,
        "annual": 12,
    }
    role_by_coordinate = {
        (
            row["case_key"],
            row["table_path"]["row_label"],
            row["table_path"]["column_label"],
        ): row["metric_period_role"]
        for row in held_out
    }
    assert role_by_coordinate[
        (
            "ORCL",
            "$ 1,250 , 5.50 %, due September 2064",
            "Amount 2026",
        )
    ] == "instant"
    assert role_by_coordinate[
        (
            "ORCL",
            "Cash and cash equivalents at beginning of period",
            "Year Ended May 31, 2026",
        )
    ] == "instant"
    assert role_by_coordinate[
        ("ORCL", "Cash, cash equivalents and trade receivables, net", "2026")
    ] == "instant"
    assert role_by_coordinate[
        ("ORCL", "Total deferred revenues", "2026")
    ] == "instant"
    assert r3["summary"]["quarantine_digest"] == r4["summary"][
        "quarantine_digest"
    ]


def test_automatic_claim_and_lineage_mutations_fail_closed() -> None:
    policy = _policy()
    specs, _, _ = compile_candidate_bundle_index_manifest(
        policy=policy,
        repo_root=ROOT,
    )
    held_out_index = next(
        index
        for index, row in enumerate(specs)
        if row["case_key"] in {"ORCL", "ASML", "ANET"}
    )
    mutated = deepcopy(specs)
    body = dict(mutated[held_out_index])
    body.pop("spec_digest")
    body["object_type"] = "claim"
    body["selection_basis"] = "automatic_narrative_claim"
    body["table_path"] = None
    body["currency_unit_authority"] = None
    from sec_agent.canonical_runtime.models import canonical_digest

    mutated[held_out_index] = {**body, "spec_digest": canonical_digest(body)}
    with pytest.raises(
        CandidateBundleIndexManifestError,
        match="candidate_bundle_index_automatic_narrative_admission_forbidden",
    ):
        validate_candidate_bundle_index_specs(mutated, policy=policy)

    drifted = deepcopy(specs)
    body = dict(drifted[0])
    body.pop("spec_digest")
    body["source_content_digest"] = "0" * 64
    drifted[0] = {**body, "spec_digest": canonical_digest(body)}
    with pytest.raises(
        CandidateBundleIndexManifestError,
        match="candidate_bundle_index_source_or_child_lineage_invalid",
    ):
        validate_candidate_bundle_index_specs(drifted, policy=policy)


def test_zero_call_materialization_is_content_addressed_and_not_real_build(
    tmp_path: Path,
) -> None:
    result = materialize_candidate_bundle_index_zero_call_proof(
        policy=_policy(),
        repo_root=ROOT,
        output_runtime_root=tmp_path,
    )
    validate_candidate_bundle_index_zero_call_proof(result)
    assert result["selection_summary"]["primary_spec_count"] == 93
    assert result["selection_summary"]["narrative_review_queue_count"] == 19
    assert result["fake_build"]["terminal_count_each"] == 93
    assert result["mutation_proof"]["scenario_count"] == 15
    assert result["mutation_proof"]["all_failed_closed"] is True
    assert result["execution_gate"]["ubuntu_real_build_authorized"] is False
    assert all(value == 0 for value in result["observed_calls"].values())
    object_path = tmp_path / "objects" / Path(result["private_manifest"]["object_key"])
    assert object_path.is_file()
    assert result["private_manifest"]["digest"] == __import__("hashlib").sha256(
        object_path.read_bytes()
    ).hexdigest()


def test_committed_zero_call_result_is_digest_bound() -> None:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    validate_candidate_bundle_index_zero_call_proof(result)
    mutated = deepcopy(result)
    mutated["execution_gate"]["ubuntu_real_build_authorized"] = True
    with pytest.raises(
        CandidateBundleIndexManifestError,
        match="candidate_bundle_index_zero_call_proof_invalid",
    ):
        validate_candidate_bundle_index_zero_call_proof(mutated)


def test_r4_clean_proof_reexecutes_r9_and_manifest_without_calls() -> None:
    if not PROOF_PATH.exists():
        pytest.skip("R4 clean independent proof not materialized")
    payload = json.loads(PROOF_PATH.read_text(encoding="utf-8"))
    body = dict(payload)
    digest = body.pop("result_digest")
    from sec_agent.canonical_runtime.models import canonical_digest

    assert canonical_digest(body) == digest
    assert payload["source_commit"] == "0db3c40a832aea46c2576ba48abe0ec599b4ff37"
    assert payload["source_result_digest"] == (
        "d84b7ef21bac98d90567c70300fd45b55daac74089ae45b813d70c994c98e7a1"
    )
    assert payload["upstream_reparse_result_digest"] == (
        "caee03a519403b3dbcf6b15bd3cf9969482596771a09e8277bc094cb016c7f3e"
    )
    assert len(payload["proof_runs"]) == 2
    for run in payload["proof_runs"]:
        assert run["matches_committed_result"] is True
        assert run["selection_summary"]["primary_spec_count"] == 93
        assert run["fake_build"]["terminal_count_each"] == 93
        assert run["manifest_mutations_passed"] == [15, 15]
        assert all(
            value == 0
            for layer in run["observed_calls"].values()
            for value in layer.values()
        )
    acceptance = payload["stage_acceptance"]
    assert acceptance["clean_independent_reproof"] is True
    assert acceptance["ubuntu_real_build_authority_decision_admitted"] is True
    assert acceptance["real_embedding_or_index_build"] is False
