from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from retrieval.dell_report_internal_chain_ceiling_r10 import (
    ATTEMPT_ID,
    ATTEMPT_RECEIPT_REF,
    AUTHORITY,
    EXECUTION_CONTRACT,
    EXPECTED_BOUND_INPUT_IDS,
    EXPECTED_IMPLEMENTATION_PATHS,
    MIN_FREE_BYTES_BEFORE_ATTEMPT,
    POLICY_REF,
    POLICY_SCHEMA_VERSION,
    PRIVATE_REF,
    PRIVATE_RESULT_SCHEMA_VERSION,
    PROGRAM_ID,
    PUBLIC_REF,
    RAW_EXECUTION_CAPTURE_REF,
    SEMANTIC_CONTRACT,
    TERMINAL_FAILURE_RECEIPT_REF,
    DellReportInternalChainCeilingR10Error,
    assess_dell_report_internal_chain_r10_packages,
    build_dell_report_internal_chain_ceiling_r10_public_projection,
    validate_dell_report_internal_chain_ceiling_r10_policy,
)
from retrieval.dell_report_predicate_frames_r10 import ASP_TARGET
from retrieval.query_plan import canonical_digest
from scripts.data_retrieval import (
    run_dell_report_internal_chain_ceiling_r10 as r10_runner,
)


ROOT = Path(__file__).resolve().parents[1]


def _redigest(value: dict) -> dict:
    body = dict(value)
    body.pop("result_digest", None)
    value["result_digest"] = canonical_digest(body)
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _metadata() -> dict:
    return {
        "ticker": "DELL",
        "source_type": "PUBLIC_WEB",
        "source_tier": "named_counterparty_or_standards_primary",
        "publication_date": "2025-05-27",
    }


def _source(source_id: str, text: str) -> dict:
    return {
        "evidence_id": source_id,
        "text": text,
        "metadata": {},
        **_metadata(),
    }


def _object(object_id: str, source_id: str, text: str) -> dict:
    return {
        "compiled_object_id": object_id,
        "candidate_not_evidence": True,
        "evidence_promoted": False,
        "numeric_authority": False,
        "lineage_source_record_ids": [source_id],
        "model_text": text,
        "base_object_view": {
            "source_record_id": source_id,
            "focus_binding": {"mode": "parent_context"},
            **_metadata(),
        },
    }


def test_r10_assessment_emits_lossless_complete_frame_transformation() -> None:
    source_id = "SOURCE::DELL::ASP::R10"
    source_rows = [
        _source(
            source_id,
            "Context. Dell offered PowerEdge hardware for USD 15 in FY2026.",
        )
    ]
    object_rows = [
        _object(
            "OBJECT::DELL::ASP::R10",
            source_id,
            "Dell offered PowerEdge hardware for USD 15 in FY2026.",
        )
    ]
    result = assess_dell_report_internal_chain_r10_packages(
        target_id=ASP_TARGET,
        source_rows=source_rows,
        object_rows=object_rows,
    )
    assert result["coverage_gaps"] == []
    assert result["frame_transformation_binding_count"] == 1
    binding = result["frame_transformation_bindings"][0]
    assert binding["binding_accepted"] is True
    assert binding["semantic_signature_equal"] is True
    # The corpus compiler may select an exact sentence slice. Representation
    # equality is valid here; the dedicated transformation tests separately
    # prove that semantically equal bounded windows can differ in representation.
    assert binding["representation_digest_equal"] is True
    assert binding["loss_flags"] == []
    assert binding["addition_flags"] == []


def _r10_projection_fixture() -> dict:
    path = ROOT / (
        "data/workbench_private/fin_0_1_3_s1_dell_03b_internal_chain_"
        "candidate_ceiling/dell-rsq-03b-internal-chain-r9/full_result.json"
    )
    private = json.loads(path.read_text(encoding="utf-8"))
    private["schema_version"] = PRIVATE_RESULT_SCHEMA_VERSION
    private["attempt_id"] = ATTEMPT_ID
    private["status"] = (
        "dell_03B_R10_open_vocabulary_relational_frame_ceiling_executed"
    )
    private["authority"] = {
        "03B_R10_execution_consumed": True,
        "03C_external_capture_authorized": False,
        "03D_4B_embedding_authorized": False,
        "03D_reranker_authorized": False,
        "candidate_decision_authorized": False,
        "evidence_promotion_authorized": False,
        "proved_information_boundary_authorized": False,
        "G3_pass": False,
        "S1_pass": False,
        "S2_pass": False,
        "S3_pass": False,
        "report_quality_pass": False,
        "product_acceptance": False,
        "publication": False,
        "release_ready": False,
    }
    bindings = {
        binding_id: {
            "ref": f"configs/test/{binding_id}.json",
            "sha256": "a" * 64,
            "result_digest": "b" * 64,
        }
        for binding_id in EXPECTED_BOUND_INPUT_IDS | {"R10_policy"}
    }
    bindings["attempt_consumption_receipt"] = {
        "ref": "data/test/attempt.json",
        "sha256": "a" * 64,
        "result_digest": "b" * 64,
    }
    bindings["git_identity"] = {
        "branch": r10_runner.BRANCH,
        "head": "a" * 40,
        "head_tree": "b" * 40,
        "upstream": "a" * 40,
        "implementation_commit": "c" * 40,
        "implementation_tree": "d" * 40,
        "authority_commit_changed_paths": [POLICY_REF],
        "clean": True,
        "upstream_equal": True,
        "authority_parent_exact": True,
    }
    bindings["disk_capacity_preflight"] = {
        "free_bytes": MIN_FREE_BYTES_BEFORE_ATTEMPT,
        "minimum_free_bytes": MIN_FREE_BYTES_BEFORE_ATTEMPT,
    }
    private["input_bindings"] = bindings
    for target in private["target_results"]:
        target["private_frame_transformation_bindings"] = []
        target["private_frame_transformation_summary"] = {
            "complete_transformation_coverage_pass": True
        }
    private["policy_digest"] = "d" * 64
    return _redigest(private)


def test_r10_public_projection_drops_transformation_private_rows() -> None:
    private = _r10_projection_fixture()
    public = build_dell_report_internal_chain_ceiling_r10_public_projection(
        private_result=private,
        private_ref=PRIVATE_REF,
        private_sha256="c" * 64,
    )
    assert public["attempt_id"] == ATTEMPT_ID
    assert "raw_execution_receipt" not in public
    assert all(
        "private_frame_transformation_bindings" not in row
        for row in public["target_results"]
    )


def _binding(path: Path) -> tuple[dict, dict]:
    value = json.loads(path.read_text(encoding="utf-8"))
    row = {
        "ref": path.relative_to(ROOT).as_posix(),
        "sha256": _sha(path),
    }
    if value.get("result_digest"):
        row["result_digest"] = value["result_digest"]
    return row, value


def _r10_policy_fixture() -> tuple[dict, dict[str, dict]]:
    paths = {
        "R9_policy": ROOT / (
            "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_"
            "candidate_ceiling_policy_v1_8.json"
        ),
        "R9_public": ROOT / (
            "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_"
            "candidate_ceiling_result_v1_8.json"
        ),
        "R9_private": ROOT / (
            "data/workbench_private/fin_0_1_3_s1_dell_03b_internal_chain_"
            "candidate_ceiling/dell-rsq-03b-internal-chain-r9/full_result.json"
        ),
        "R9_attempt_receipt": ROOT / (
            "data/workbench_private/fin_0_1_3_s1_dell_03b_internal_chain_"
            "candidate_ceiling/dell-rsq-03b-internal-chain-r9/"
            "attempt_consumption_receipt.json"
        ),
        "R9_raw_execution_capture": ROOT / (
            "data/workbench_private/fin_0_1_3_s1_dell_03b_internal_chain_"
            "candidate_ceiling/dell-rsq-03b-internal-chain-r9/"
            "raw_execution_capture.json"
        ),
        "R9_fresh_audit": ROOT / (
            "configs/audits/fin_ia_0_1_3_commit_6e2189de_dell_03b_"
            "r9_fresh_dual_audit_fail_v1_0.json"
        ),
        "R9_fixed_audit_manifest": ROOT / (
            "configs/audits/fin_ia_0_1_3_commit_6e2189de_dell_03b_"
            "r9_fixed_dual_audit_manifest_v1_0.json"
        ),
    }
    r9_private = json.loads(paths["R9_private"].read_text(encoding="utf-8"))
    inherited = r9_private["input_bindings"]
    for binding_id in (
        "R17_report_audit",
        "R17_report_bundle_carry_forward",
        "execution_program",
        "runtime_registry",
        "runtime_binding_receipt",
    ):
        paths[binding_id] = ROOT / inherited[binding_id]["ref"]
    for binding_id in ("source_records", "compiled_objects"):
        paths[binding_id] = ROOT / inherited[binding_id]["ref"]

    bound_inputs: dict[str, dict] = {}
    values: dict[str, dict] = {}
    for binding_id, path in paths.items():
        if path.suffix == ".jsonl":
            bound_inputs[binding_id] = {
                "ref": path.relative_to(ROOT).as_posix(),
                "sha256": _sha(path),
            }
            values[binding_id] = dict(bound_inputs[binding_id])
        else:
            bound_inputs[binding_id], values[binding_id] = _binding(path)
    assert set(bound_inputs) == EXPECTED_BOUND_INPUT_IDS
    policy = {
        "schema_version": POLICY_SCHEMA_VERSION,
        "status": (
            "same_stage_R10_execution_authorized_after_fresh_R9_audit_failure"
        ),
        "program_id": PROGRAM_ID,
        "attempt_id": ATTEMPT_ID,
        "recorded_at": "2026-08-27",
        "decision_target": "One bounded R10 exact attempt.",
        "owner_basis": "Owner-approved same-stage R10 implementation.",
        "execution_contract": dict(EXECUTION_CONTRACT),
        "semantic_contract": dict(SEMANTIC_CONTRACT),
        "output_contract": {
            "policy_ref": POLICY_REF,
            "private_result_ref": PRIVATE_REF,
            "public_result_ref": PUBLIC_REF,
            "attempt_consumption_receipt_ref": ATTEMPT_RECEIPT_REF,
            "raw_execution_capture_ref": RAW_EXECUTION_CAPTURE_REF,
            "terminal_failure_receipt_ref": TERMINAL_FAILURE_RECEIPT_REF,
            "alternate_output_paths_authorized": False,
            "private_public_same_path_authorized": False,
            "exclusive_create_required": True,
            "atomic_pair_with_rollback_required": True,
            "same_attempt_retry_authorized": False,
            "minimum_free_bytes_before_attempt": MIN_FREE_BYTES_BEFORE_ATTEMPT,
        },
        "bound_inputs": bound_inputs,
        "execution_identity": {
            "branch": r10_runner.BRANCH,
            "implementation_commit": "a" * 40,
            "implementation_tree": "b" * 40,
            "authority_commit_changed_paths": [POLICY_REF],
            "authority_commit_parent_must_equal_implementation_commit": True,
            "HEAD_must_equal_upstream": True,
        },
        "implementation_bindings": [
            {"path": path, "sha256": "a" * 64}
            for path in sorted(EXPECTED_IMPLEMENTATION_PATHS)
        ],
        "TokenBudgetBasis": {
            "node_purpose": "Bounded R10 qualification.",
            "input_scale": "Five requests and six targets.",
            "required_outputs": "Private/public immutable result.",
            "schema_burden": "Typed frames and transformation mappings.",
            "materiality_quality_risk": "False complete financial evidence.",
            "comparable_run_evidence": "R9 and zero-call R10 preview.",
            "reasoning_profile": "Deterministic compiler plus local embedding.",
            "stop_and_truncation": "Fail closed before authority drift.",
        },
        "authority": dict(AUTHORITY),
        "known_boundary": "No downstream authority.",
    }
    _redigest(policy)
    return policy, values


def test_r10_policy_binds_r9_failure_and_r17_14_file_carry_forward() -> None:
    policy, values = _r10_policy_fixture()
    predecessor = validate_dell_report_internal_chain_ceiling_r10_policy(
        policy,
        **values,
    )
    assert predecessor["attempt_id"] == "dell-rsq-03b-internal-chain-r9"


def test_r10_policy_rejects_changed_r17_bundle_population() -> None:
    policy, values = _r10_policy_fixture()
    drift = deepcopy(values)
    drift["R17_report_bundle_carry_forward"] = deepcopy(
        values["R17_report_bundle_carry_forward"]
    )
    drift["R17_report_bundle_carry_forward"][
        "R17_report_quality_bundle"
    ].pop("R17_report_bytes")
    _redigest(drift["R17_report_bundle_carry_forward"])
    # Rebind the deliberately changed in-memory artifact so this test reaches
    # the 14-file population invariant instead of stopping at digest drift.
    policy["bound_inputs"]["R17_report_bundle_carry_forward"][
        "result_digest"
    ] = drift["R17_report_bundle_carry_forward"]["result_digest"]
    _redigest(policy)
    with pytest.raises(
        DellReportInternalChainCeilingR10Error,
        match="R17_14_file_carry_forward_invalid",
    ):
        validate_dell_report_internal_chain_ceiling_r10_policy(
            policy,
            **drift,
        )


def test_r10_runner_requires_explicit_mode() -> None:
    with pytest.raises(SystemExit) as exc_info:
        r10_runner.main([])
    assert exc_info.value.code == 2


def test_r10_formal_fails_before_receipt_when_policy_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    private = tmp_path / "private" / "full_result.json"
    monkeypatch.setattr(r10_runner, "DEFAULT_PRIVATE", private)
    monkeypatch.setattr(r10_runner, "DEFAULT_PUBLIC", tmp_path / "public.json")
    monkeypatch.setattr(
        r10_runner,
        "ATTEMPT_RECEIPT",
        private.with_name("attempt_consumption_receipt.json"),
    )
    monkeypatch.setattr(
        r10_runner,
        "RAW_EXECUTION_CAPTURE",
        private.with_name("raw_execution_capture.json"),
    )
    monkeypatch.setattr(
        r10_runner,
        "TERMINAL_FAILURE_RECEIPT",
        private.with_name("terminal_failure_receipt.json"),
    )
    monkeypatch.setattr(r10_runner, "POLICY", tmp_path / "missing.json")
    monkeypatch.setattr(
        r10_runner,
        "_require_output_disk_capacity",
        lambda: {"free_bytes": 1, "minimum_free_bytes": 1},
    )
    with pytest.raises(FileNotFoundError, match="canonical_policy_missing"):
        r10_runner.run_authorized_formal()
    assert not r10_runner.ATTEMPT_RECEIPT.exists()


def test_r10_raw_capture_precedes_redacted_terminal_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    attempt_dir = tmp_path / "attempt"
    attempt_dir.mkdir()
    raw_path = attempt_dir / "raw_execution_capture.json"
    terminal_path = attempt_dir / "terminal_failure_receipt.json"
    monkeypatch.setattr(r10_runner, "RAW_EXECUTION_CAPTURE", raw_path)
    monkeypatch.setattr(r10_runner, "TERMINAL_FAILURE_RECEIPT", terminal_path)
    execution = {"request_results": [{"request_id": "REQ::DELL::ASP::V1"}]}
    sha = hashlib.sha256(
        r10_runner.base._canonical_json_bytes(execution)
    ).hexdigest()
    r10_runner._write_raw_execution_capture(
        policy={"result_digest": "a" * 64},
        execution=execution,
        execution_sha256=sha,
        recorded_at="2026-08-27T00:00:00+00:00",
    )
    receipt = r10_runner._write_terminal_failure_receipt(
        policy={"result_digest": "a" * 64},
        stage="private_result_compilation",
        exception_type="RuntimeError",
        recorded_at="2026-08-27T00:00:01+00:00",
    )
    assert receipt["exception_message_persisted"] is False
    assert receipt["raw_execution_capture"]["sha256"] == _sha(raw_path)


def test_r10_attempt_receipt_is_exclusive_exact_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    receipt = tmp_path / "attempt" / "attempt_consumption_receipt.json"
    monkeypatch.setattr(r10_runner, "ATTEMPT_RECEIPT", receipt)
    kwargs = {
        "policy": {"result_digest": "a" * 64},
        "git_receipt": {
            "head": "b" * 40,
            "head_tree": "c" * 40,
            "implementation_commit": "d" * 40,
            "implementation_tree": "e" * 40,
        },
        "recorded_at": "2026-08-27T00:00:00+00:00",
    }
    first = r10_runner._write_attempt_consumption_receipt(**kwargs)
    assert json.loads(receipt.read_text(encoding="utf-8")) == first
    with pytest.raises(FileExistsError, match="attempt_already_consumed"):
        r10_runner._write_attempt_consumption_receipt(**kwargs)


def test_r10_atomic_pair_rolls_back_second_publish_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    private = tmp_path / "private" / "full_result.json"
    public = tmp_path / "public" / "result.json"
    monkeypatch.setattr(r10_runner, "DEFAULT_PRIVATE", private)
    monkeypatch.setattr(r10_runner, "DEFAULT_PUBLIC", public)
    real_link = r10_runner.os.link
    calls = 0

    def fail_second(source: Path, destination: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("synthetic_second_publish_failure")
        real_link(source, destination)

    monkeypatch.setattr(r10_runner.os, "link", fail_second)
    with pytest.raises(OSError, match="synthetic_second_publish_failure"):
        r10_runner._publish_atomic_pair(
            private_bytes=b"private",
            public_bytes=b"public",
        )
    assert not private.exists()
    assert not public.exists()
