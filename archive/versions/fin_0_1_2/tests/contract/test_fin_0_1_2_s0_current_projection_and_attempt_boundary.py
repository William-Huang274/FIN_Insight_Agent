from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from sec_agent.hermetic_test_runner import (
    CURRENT_PROGRAM_PROJECTION_SCHEMA,
    HermeticTestRunnerError,
    validate_host_current_program_projection,
)
from sec_agent.runtime_contract_governance import (
    ProofClass,
    validate_active_test_suite_manifest,
)
from sec_agent.reference_role_registry import (
    CURRENT_REFERENCE_ROLE_REGISTRY_SCHEMA,
    REFERENCE_ROLE_IDS,
    load_reference_role_registry,
)


ROOT = Path(__file__).resolve().parents[2]
PROJECTION_REF = Path(
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_0.json"
)
MANIFEST_REF = Path(
    "configs/releases/fin_ia_0_1_2_s0_current_active_test_suite_manifest_v2_0.json"
)
ATTEMPT_CONTRACT_REF = Path(
    "configs/runtime/fin_ia_s0_qualification_attempt_contract_v1_0.json"
)
CURRENT_REFERENCE_ROLE_REGISTRY_REF = Path(
    "configs/runtime/fin_ia_current_reference_role_registry_v2_0.json"
)
LEGACY_PROJECTION_REF = Path(
    "configs/runtime/fin_ia_0_1_3_current_program_projection_v1_5.json"
)


def _load(root: Path, path: Path) -> dict:
    return json.loads((root / path).read_text(encoding="utf-8"))


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _current_fixture(tmp_path: Path) -> tuple[Path, Path, dict]:
    repository = tmp_path / "repository"
    decision_ref = Path("state/decision.json")
    decision = {"decision_id": "fixture-authority"}
    _write_json(repository / decision_ref, decision)
    decision_sha = hashlib.sha256(
        (repository / decision_ref).read_bytes()
    ).hexdigest()
    source_paths = {
        "program_backlog": "state/program.json",
        "context_pack": "state/context.md",
        "capability_ledger": "state/capability.jsonl",
        "root_cause_ledger": "state/issues.jsonl",
    }
    for value in source_paths.values():
        path = repository / value
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
    projection = {
        "schema_version": CURRENT_PROGRAM_PROJECTION_SCHEMA,
        "projection_id": "fixture-current-projection",
        "recorded_at": "2026-08-02T00:00:00+08:00",
        "status": "fixture_current_S0_repair",
        "lifecycle_state": "in_progress",
        "decision_binding": {
            "ref": decision_ref.as_posix(),
            "sha256": decision_sha,
            "binding_role": "current_authority",
        },
        "current_truth": {
            "product_version": "FIN_0_1_2",
            "stage": "S0",
            "active_slice": "fixture_S0",
            "current_next_action": "fixture-next",
            "current_stage_status": "repair_in_progress",
            "open_issue_ids": ["RC-fixture"],
            "release_qualified": False,
        },
        "source_paths": source_paths,
        "historical_projection_policy": {
            "immutable_event_files_remain_valid_for_historical_facts": True,
            "historical_files_may_own_current_next_or_backlog_tail": False,
            "superseded_projection_deleted_or_rewritten": False,
        },
        "execution_authority": {
            "planning_and_read_only_audit_complete": True,
            "focused_s0_repair_authorized": True,
            "clean_environment_acceptance_authorized": False,
            "credential_model_provider_network_business_authorized": False,
        },
    }
    projection_ref = Path("state/current.json")
    _write_json(repository / projection_ref, projection)
    return repository, projection_ref, projection


def test_current_projection_is_self_contained_and_version_neutral() -> None:
    projection = _load(ROOT, PROJECTION_REF)
    assert projection["schema_version"] == CURRENT_PROGRAM_PROJECTION_SCHEMA
    assert projection["current_truth"]["product_version"] == "FIN_0_1_2"
    assert projection["current_truth"]["stage"] == "S0"
    assert projection["execution_authority"] == {
        "planning_and_read_only_audit_complete": True,
        "focused_s0_repair_authorized": True,
        "clean_environment_acceptance_authorized": False,
        "credential_model_provider_network_business_authorized": False,
    }
    assert validate_host_current_program_projection(
        ROOT,
        PROJECTION_REF.as_posix(),
    ) == PROJECTION_REF


def test_legacy_projection_is_an_event_and_does_not_own_today() -> None:
    legacy = _load(ROOT, LEGACY_PROJECTION_REF)
    assert legacy["schema_version"] != CURRENT_PROGRAM_PROJECTION_SCHEMA
    assert validate_host_current_program_projection(
        ROOT,
        LEGACY_PROJECTION_REF.as_posix(),
    ) == LEGACY_PROJECTION_REF


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (
            lambda value: value["current_truth"].update(
                {"attempt_id": "attempt-must-not-live-here"}
            ),
            "current_projection_attempt_state_forbidden",
        ),
        (
            lambda value: value.update({"lifecycle_state": "authorized_pending"}),
            "current_projection_lifecycle_state_invalid",
        ),
        (
            lambda value: value["decision_binding"].update({"sha256": "0" * 64}),
            "current_projection_decision_binding_drift",
        ),
        (
            lambda value: value["historical_projection_policy"].update(
                {"historical_files_may_own_current_next_or_backlog_tail": True}
            ),
            "current_projection_history_policy_invalid",
        ),
    ],
)
def test_current_projection_mutations_fail_closed(
    tmp_path: Path,
    mutation,
    code: str,
) -> None:
    repository, projection_ref, projection = _current_fixture(tmp_path)
    mutated = copy.deepcopy(projection)
    mutation(mutated)
    _write_json(repository / projection_ref, mutated)
    with pytest.raises(HermeticTestRunnerError, match=code):
        validate_host_current_program_projection(
            repository,
            projection_ref.as_posix(),
        )


def test_attempt_contract_is_small_immutable_and_separate() -> None:
    contract = _load(ROOT, ATTEMPT_CONTRACT_REF)
    assert contract["attempt_states"] == [
        "planned",
        "running",
        "passed",
        "failed",
    ]
    assert contract["transition_rules"]["terminal_is_immutable"] is True
    assert contract["transition_rules"]["same_attempt_retry_allowed"] is False
    assert (
        contract["transition_rules"]["attempt_failure_creates_product_version"]
        is False
    )
    assert not any(
        contract["current_projection_boundary"].values()
    )


def test_current_manifest_uses_reusable_assets_without_proof_control_plane() -> None:
    manifest = _load(ROOT, MANIFEST_REF)
    validate_active_test_suite_manifest(manifest)
    selected = [row for row in manifest["suites"] if row["selected"]]
    assert {row["proof_class"] for row in selected} == {
        item.value for item in ProofClass
    }
    policy = manifest["hermetic_package_policy"]
    assert policy["host_current_program_projection_ref"] == PROJECTION_REF.as_posix()
    assert policy["runtime_resource_registry_ref"].endswith(
        "runtime_resource_registry_v1_0.json"
    )
    assert policy["semantic_parity_contract_ref"].endswith(
        "typed_environment_semantic_parity_v1_0.json"
    )
    assert policy["repository_reference_policy"][
        "reference_role_registry_ref"
    ].endswith("current_reference_role_registry_v2_0.json")
    selected_paths = {
        path
        for row in selected
        for path in row["test_paths"]
    }
    assert not any("proof_control_plane" in path for path in selected_paths)
    assert manifest["fixed_budget"]["model_calls"] == 0
    assert manifest["fixed_budget"]["provider_calls"] == 0


def test_current_reference_role_registry_uses_version_neutral_schema() -> None:
    document = _load(ROOT, CURRENT_REFERENCE_ROLE_REGISTRY_REF)
    assert document["schema_version"] == CURRENT_REFERENCE_ROLE_REGISTRY_SCHEMA
    registry = load_reference_role_registry(
        ROOT,
        CURRENT_REFERENCE_ROLE_REGISTRY_REF.as_posix(),
    )
    assert registry.roles == REFERENCE_ROLE_IDS
