from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import sec_agent.hermetic_test_runner as hermetic_runner
from sec_agent.hermetic_test_runner import (
    CLEAN_ENVIRONMENT_EXECUTION_NEXT,
    HermeticTestRunnerError,
    _validate_clean_environment_qualification_authority,
    run_hermetic_active_suite,
    validate_host_current_program_projection,
)
from sec_agent.runtime_contract_governance import (
    ContractGovernanceError,
    validate_active_test_suite_manifest,
)


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_REF = Path(
    "configs/releases/"
    "fin_ia_0_1_2_s0_current_active_test_suite_manifest_v2_1.json"
)
PRE_AUTHORITY_MANIFEST_REF = Path(
    "configs/releases/"
    "fin_ia_0_1_2_s0_current_active_test_suite_manifest_v2_0.json"
)
PROJECTION_REF = Path(
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_1.json"
)
AUTHORITY_REF = Path(
    "configs/releases/"
    "fin_ia_0_1_2_s0_fresh_clean_environment_qualification_"
    "authority_decision_v1_0.json"
)
OUTPUT_ROOT = Path(
    "D:/FIN_Insight_Agent_recovery/qualifications/"
    "fin_0_1_2_s0_clean_environment_qualification_"
    "20260802T080750Z_head_56732cd9_r1"
)
ENGINEERING_BASE_HEAD = "56732cd9eaab81d8d8f1ffa020f6e5536c06e6e1"


def _load(path: Path) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _clean_git_output(_root: Path, *args: str) -> bytes:
    if args == ("rev-parse", "--abbrev-ref", "HEAD"):
        return b"codex/layered-data-source-expansion\n"
    if args in (("rev-parse", "HEAD"), ("rev-parse", "@{u}")):
        return (ENGINEERING_BASE_HEAD + "\n").encode("ascii")
    if args == ("status", "--porcelain"):
        return b""
    if args == (
        "merge-base",
        "--is-ancestor",
        ENGINEERING_BASE_HEAD,
        ENGINEERING_BASE_HEAD,
    ):
        return b""
    raise AssertionError(f"unexpected git command: {args!r}")


def test_authority_decision_is_bound_but_has_not_consumed_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _load(MANIFEST_REF)
    authority = _load(AUTHORITY_REF)
    projection = _load(PROJECTION_REF)
    validate_active_test_suite_manifest(manifest)
    assert validate_host_current_program_projection(
        ROOT, PROJECTION_REF.as_posix()
    ) == PROJECTION_REF
    assert authority["observed_counts"][
        "clean_environment_qualification_attempts_started"
    ] == 0
    assert projection["current_truth"]["current_next_action"] == (
        CLEAN_ENVIRONMENT_EXECUTION_NEXT
    )
    assert projection["execution_authority"][
        "clean_environment_acceptance_authorized"
    ] is True
    assert not OUTPUT_ROOT.exists()
    assert not OUTPUT_ROOT.with_name(OUTPUT_ROOT.name + ".failed").exists()
    assert not OUTPUT_ROOT.with_name(OUTPUT_ROOT.name + ".partial").exists()

    monkeypatch.setattr(hermetic_runner, "_git_output", _clean_git_output)
    metadata = _validate_clean_environment_qualification_authority(
        repository_root=ROOT,
        manifest_path=ROOT / MANIFEST_REF,
        manifest=manifest,
        output_root=OUTPUT_ROOT,
    )
    assert metadata["attempt_id"].endswith("20260802_r1")
    assert metadata["git_head"] == ENGINEERING_BASE_HEAD


def test_pre_authority_manifest_cannot_start_real_qualification(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "must_not_exist"
    with pytest.raises(
        HermeticTestRunnerError,
        match="clean_environment_qualification_authority_missing",
    ):
        run_hermetic_active_suite(
            repository_root=ROOT,
            manifest_path=ROOT / PRE_AUTHORITY_MANIFEST_REF,
            output_root=output_root,
        )
    assert not output_root.exists()
    assert not output_root.with_name(output_root.name + ".partial").exists()


def test_authority_is_exactly_bound_to_manifest_projection_and_output_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _load(MANIFEST_REF)
    monkeypatch.setattr(hermetic_runner, "_git_output", _clean_git_output)

    wrong_output = OUTPUT_ROOT.with_name(OUTPUT_ROOT.name + "_wrong")
    with pytest.raises(
        HermeticTestRunnerError,
        match="clean_environment_qualification_output_root_mismatch",
    ):
        _validate_clean_environment_qualification_authority(
            repository_root=ROOT,
            manifest_path=ROOT / MANIFEST_REF,
            manifest=manifest,
            output_root=wrong_output,
        )

    mutated = copy.deepcopy(manifest)
    mutated["fixed_budget"]["automatic_retries_or_replacements"] = 1
    with pytest.raises(
        HermeticTestRunnerError,
        match="clean_environment_qualification_manifest_projection_drift",
    ):
        _validate_clean_environment_qualification_authority(
            repository_root=ROOT,
            manifest_path=ROOT / MANIFEST_REF,
            manifest=mutated,
            output_root=OUTPUT_ROOT,
        )


def test_manifest_authority_shape_fails_closed() -> None:
    manifest = _load(MANIFEST_REF)
    missing_binding = copy.deepcopy(manifest)
    missing_binding.pop("clean_environment_qualification_authority_binding")
    with pytest.raises(
        ContractGovernanceError,
        match="test_manifest_clean_environment_authority_binding_missing",
    ):
        validate_active_test_suite_manifest(missing_binding)

    invalid_digest = copy.deepcopy(manifest)
    invalid_digest["clean_environment_qualification_authority_binding"][
        "sha256"
    ] = "not-a-digest"
    with pytest.raises(
        ContractGovernanceError,
        match="test_manifest_clean_environment_authority_digest_invalid",
    ):
        validate_active_test_suite_manifest(invalid_digest)
