from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

import pytest

from sec_agent.hermetic_test_runner import (
    HermeticTestRunnerError,
    compile_repository_inventory,
    validate_host_current_program_projection,
)
from sec_agent.runtime_contract_governance import (
    validate_active_test_suite_manifest,
)
from sec_agent.reference_role_registry import (
    REFERENCE_ROLE_IDS,
    ReferenceRoleRegistryError,
    collect_reference_roles,
    load_reference_role_registry,
)


ROOT = Path(__file__).resolve().parents[2]
REGISTRY_REF = (
    "configs/runtime/fin_ia_0_1_3_reference_role_registry_v1_0.json"
)
MANIFEST_REF = (
    "configs/releases/fin_ia_0_1_3_s0_active_test_suite_manifest_v1_2.json"
)
CURRENT_MANIFEST_REF = (
    "configs/releases/fin_ia_0_1_2_s0_current_active_test_suite_manifest_v2_0.json"
)
IMPLEMENTATION_REF = (
    "configs/releases/fin_ia_0_1_3_s0_reference_role_taxonomy_registry_and_"
    "collect_all_compiler_minimum_zero_call_implementation_v1_0.json"
)
PROJECTION_REF = (
    "configs/runtime/fin_ia_0_1_3_current_program_projection_v1_5.json"
)
NEXT_ACTION = (
    "FIN-0.1.3-S0-REFERENCE-ROLE-TAXONOMY-AND-CURRENT-RUNTIME-HOST-"
    "ZERO-CALL-ENGINEERING-PROOF-AUTHORITY-DECISION"
)


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _write_json(path: Path, value: dict[str, Any]) -> None:
    _write(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _git(repository: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repository,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init", "--quiet")
    _write(repository / ".gitignore", ".codex_runtime/\n")
    _write(repository / "runner.py", "RUNNER = True\n")
    _write(repository / "tests/pass.py", "def test_pass():\n    assert True\n")
    _write_json(repository / "configs/target.json", {"value": 1})
    _write_json(repository / "configs/seed.json", {"binding_ref": "semantic:v1"})
    registry_ref = "configs/reference_roles.json"
    shutil.copyfile(ROOT / REGISTRY_REF, repository / registry_ref)
    _git(
        repository,
        "add",
        ".gitignore",
        "runner.py",
        "tests/pass.py",
        "configs/target.json",
        "configs/seed.json",
        registry_ref,
    )
    _git(
        repository,
        "-c",
        "user.name=FIN Test",
        "-c",
        "user.email=fin-test@example.invalid",
        "commit",
        "--quiet",
        "-m",
        "fixture",
    )
    return repository


def _manifest() -> dict[str, Any]:
    return {
        "manifest_id": "reference-role-v2-fixture",
        "suites": [{"selected": True, "test_paths": ["tests/pass.py"]}],
        "hermetic_package_policy": {
            "repository_inventory": "tracked_plus_typed_role_closure",
            "required_runner_files": ["runner.py"],
            "repository_seed_paths": ["configs/seed.json"],
            "repository_prefixes": [],
            "external_read_only_bindings": [],
            "repository_reference_policy": {
                "schema_version": "fin_ia_hermetic_repository_reference_policy_v2_0",
                "tracked_repository_paths_allowed": True,
                "explicit_allowlist": [],
                "reference_role_registry_ref": "configs/reference_roles.json",
                "forbidden_prefixes": [".codex_runtime"],
                "untracked_or_ignored_reference_behavior": "fail_closed",
                "unknown_reference_behavior": "fail_closed",
                "traversal_or_symlink_escape_behavior": "fail_closed",
                "semantic_or_external_reference_behavior": "observe_not_package",
            },
        },
    }


def test_registry_has_exact_six_roles_and_field_rule_beats_path_shape() -> None:
    registry = load_reference_role_registry(ROOT, REGISTRY_REF)
    assert registry.roles == REFERENCE_ROLE_IDS
    observation = registry.classify(
        document_ref="fixture.json",
        json_pointer="/followup_ref",
        field="followup_ref",
        value="official quarterly cohort/definition bridge",
    )
    assert observation.role == "semantic_followup"
    assert observation.rule_id == "r010_semantic_followup_field"
    root_file = registry.classify(
        document_ref="fixture.json",
        json_pointer="/unowned_ref",
        field="unowned_ref",
        value="mystery.json",
    )
    assert root_file.role is None
    assert root_file.rule_id is None


@pytest.mark.parametrize(
    ("field", "value", "role"),
    [
        ("ref", "configs/example.json", "repository_resource"),
        ("verification_ref", "verification.json", "package_relative_audit"),
        ("content_ref", "fixture://case/evidence", "external_content"),
        ("runtime_ref", ".codex_runtime/run/result.json", "restricted_runtime_audit"),
        ("model_run_ref", "reports/model_runs/run.json", "model_run_report"),
        ("contract_ref", "fin_0_1_3.contract:v1", "semantic_followup"),
    ],
)
def test_registry_classifies_each_required_role(
    field: str,
    value: str,
    role: str,
) -> None:
    registry = load_reference_role_registry(ROOT, REGISTRY_REF)
    assert registry.classify(
        document_ref="fixture.json",
        json_pointer=f"/{field}",
        field=field,
        value=value,
    ).role == role


def test_collect_all_failure_contains_every_unknown_in_stable_order() -> None:
    registry = load_reference_role_registry(ROOT, REGISTRY_REF)
    documents = [
        (
            "z.json",
            {
                "unknown_ref": "mystery/one.bin",
                "known_ref": "configs/known.json",
            },
        ),
        ("a.json", {"other_ref": "unowned/two.dat"}),
    ]
    first = collect_reference_roles(registry, documents)
    second = collect_reference_roles(registry, reversed(documents))
    assert len(first.unknowns) == 2
    assert first.observation_digest == second.observation_digest
    envelope = first.failure_envelope()
    assert envelope["code"] == "hermetic_repository_reference_roles_unknown"
    assert envelope["unknown_count"] == 2
    assert [row["document_ref"] for row in envelope["unknown_observations"]] == [
        "a.json",
        "z.json",
    ]
    assert envelope["business_promotable"] is False


def test_registry_duplicate_version_and_order_mutations_fail_closed(
    tmp_path: Path,
) -> None:
    duplicate = tmp_path / "duplicate.json"
    _write(duplicate, '{"schema_version":"a","schema_version":"b"}\n')
    with pytest.raises(
        ReferenceRoleRegistryError,
        match="reference_role_registry_duplicate_json_key",
    ):
        load_reference_role_registry(tmp_path, "duplicate.json")

    source = json.loads((ROOT / REGISTRY_REF).read_text(encoding="utf-8"))
    source["schema_version"] = "future_or_stale"
    _write_json(tmp_path / "wrong-version.json", source)
    with pytest.raises(
        ReferenceRoleRegistryError,
        match="reference_role_registry_schema_invalid",
    ):
        load_reference_role_registry(tmp_path, "wrong-version.json")

    source["schema_version"] = "fin_ia_0_1_3_reference_role_registry_v1_0"
    source["value_rules"] = list(reversed(source["value_rules"]))
    _write_json(tmp_path / "permuted.json", source)
    with pytest.raises(
        ReferenceRoleRegistryError,
        match="reference_role_registry_rule_order_invalid",
    ):
        load_reference_role_registry(tmp_path, "permuted.json")


def test_v2_compiler_packages_repository_role_and_reports_role_counts(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    _write_json(
        repository / "configs/seed.json",
        {
            "repository_ref": "configs/target.json",
            "followup_ref": "official cohort/definition bridge",
            "runtime_result_ref": ".codex_runtime/run/result.json",
            "model_run_ref": "reports/model_runs/run.json",
            "verification_ref": "verification.json",
            "content_ref": "fixture://case/evidence",
        },
    )
    _git(repository, "add", "configs/seed.json")
    inventory = compile_repository_inventory(repository, _manifest())
    assert Path("configs/target.json") in inventory.paths
    assert inventory.reference_role_report is not None
    report = inventory.reference_role_report.as_dict()
    assert report["unknown_count"] == 0
    assert report["role_counts"] == {
        "repository_resource": 1,
        "package_relative_audit": 1,
        "external_content": 1,
        "restricted_runtime_audit": 1,
        "model_run_report": 1,
        "semantic_followup": 1,
        "unknown": 0,
    }


def test_v2_compiler_collects_all_unknowns_and_rejects_field_exceptions(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    _write_json(
        repository / "configs/seed.json",
        {
            "first_ref": "unknown/one.bin",
            "second_ref": "unknown/two.dat",
        },
    )
    _git(repository, "add", "configs/seed.json")
    with pytest.raises(
        HermeticTestRunnerError,
        match="hermetic_repository_reference_roles_unknown",
    ) as captured:
        compile_repository_inventory(repository, _manifest())
    assert captured.value.failure_envelope is not None
    assert captured.value.failure_envelope["unknown_count"] == 2

    manifest = deepcopy(_manifest())
    manifest["hermetic_package_policy"]["repository_reference_policy"][
        "non_repository_reference_fields"
    ] = []
    with pytest.raises(
        HermeticTestRunnerError,
        match="hermetic_repository_reference_policy_v2_surface_invalid",
    ):
        compile_repository_inventory(repository, manifest)


def test_current_active_manifest_uses_v2_without_field_exceptions() -> None:
    manifest = json.loads((ROOT / MANIFEST_REF).read_text(encoding="utf-8"))
    validate_active_test_suite_manifest(manifest)
    policy = manifest["hermetic_package_policy"]["repository_reference_policy"]
    assert policy["schema_version"] == (
        "fin_ia_hermetic_repository_reference_policy_v2_0"
    )
    assert policy["reference_role_registry_ref"] == REGISTRY_REF
    assert "non_repository_reference_fields" not in policy
    assert manifest["fixed_budget"]["v2_implementation_bundles"] == [1, 1]
    assert manifest["fixed_budget"]["v2_host_engineering_proof_runs"] == [0, 1]
    assert manifest["fixed_budget"][
        "v2_formal_two_disposable_proof_packages"
    ] == [0, 1]
    assert manifest["next_action_on_implementation_pass"] == NEXT_ACTION


def test_current_full_repository_closure_has_no_unknown_reference_roles() -> None:
    manifest = json.loads(
        (ROOT / CURRENT_MANIFEST_REF).read_text(encoding="utf-8")
    )
    inventory = compile_repository_inventory(ROOT, manifest)
    assert inventory.reference_role_report is not None
    report = inventory.reference_role_report.as_dict()
    assert report["unknown_count"] == 0
    assert report["observation_count"] > 0
    assert report["observation_count"] == sum(report["role_counts"].values())
    assert set(report["role_counts"]) == {*REFERENCE_ROLE_IDS, "unknown"}
    assert len(report["observation_digest"]) == 64


def test_implementation_record_binds_exact_sources_and_zero_call_truth() -> None:
    record = json.loads((ROOT / IMPLEMENTATION_REF).read_text(encoding="utf-8"))
    assert record["status"] == (
        "engineering_pass_reference_role_implementation_complete_"
        "host_proof_authority_pending"
    )
    binding_roles = set()
    for binding in record["source_bindings"]:
        binding_roles.add(binding["role"])
        assert (ROOT / binding["ref"]).is_file()
        assert len(binding["sha256"]) == 64
        int(binding["sha256"], 16)
    assert binding_roles == {
        "current_v2_active_suite_manifest",
        "single_reference_role_source_of_truth",
        "v1_compatible_v2_closure_compiler",
        "registry_loader_classifier_collect_all_and_typed_failure",
        "positive_negative_mutation_and_full_closure_contract",
    }
    assert record["reference_role_result"]["required_roles"] == list(
        REFERENCE_ROLE_IDS
    )
    assert record["reference_role_result"]["unknown_count"] == 0
    assert record["observed_v2_implementation_host_formal"] == [1, 0, 0]
    assert record["old_T03_truth"]["rerun_or_reinterpretation"] is False
    assert record["next_action"] == NEXT_ACTION


def test_current_projection_binds_implementation_without_proof_inflation() -> None:
    projection = json.loads((ROOT / PROJECTION_REF).read_text(encoding="utf-8"))
    assert validate_host_current_program_projection(
        ROOT,
        PROJECTION_REF,
    ) == Path(PROJECTION_REF)
    assert projection["expectations"]["current_next_action"] == NEXT_ACTION
    assert projection["expectations"][
        "FIN_0_1_3_S0_v2_observed_implementation_host_formal"
    ] == [1, 0, 0]
    assert projection["expectations"]["FIN_0_1_3_S1_entry_authorized"] is False
    assert projection["expectations"]["FIN_0_1_release_qualified"] is False
    assert projection["package_governance"][
        "implementation_is_host_or_formal_proof_authority"
    ] is False
