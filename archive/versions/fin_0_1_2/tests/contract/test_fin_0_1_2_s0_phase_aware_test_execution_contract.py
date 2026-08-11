from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Callable

import pytest

from sec_agent.hermetic_test_runner import (
    HermeticTestRunnerError,
    _declared_document_repository_paths,
    audit_disposable_test_resource_contract,
    compile_repository_inventory,
    run_hermetic_active_suite,
)
from sec_agent.runtime_contract_governance import (
    validate_active_test_suite_manifest,
)
from sec_agent.test_execution_contract import (
    PHASE_CONTRACT,
    TestExecutionContractError as ExecutionContractError,
    compile_test_execution_contract_registry,
    load_test_execution_contract_registry,
)
from sec_agent.test_resource import (
    RepositoryTestResourceError,
    repository_test_resource,
)


ROOT = Path(__file__).resolve().parents[2]
REGISTRY_REF = (
    "configs/runtime/"
    "fin_ia_0_1_2_s0_test_execution_contract_registry_v1_0.json"
)
MANIFEST_REF = (
    "configs/releases/"
    "fin_ia_0_1_2_s0_current_active_test_suite_manifest_v2_2.json"
)
PROJECTION_REF = (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_3.json"
)
CURRENT_PROJECTION_REF = (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_4.json"
)
IMPLEMENTATION_REF = (
    "configs/releases/fin_ia_0_1_2_s0_phase_aware_test_topology_and_"
    "typed_test_dependency_compiler_minimum_zero_call_implementation_v1_0.json"
)


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _write_json(path: Path, value: dict[str, Any]) -> None:
    _write(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def test_current_registry_compiles_to_one_stable_phase_and_dependency_plan() -> None:
    plan_a = load_test_execution_contract_registry(ROOT, REGISTRY_REF)
    plan_b = load_test_execution_contract_registry(ROOT, REGISTRY_REF)
    assert tuple(
        (row.phase, row.location, row.gates_current_candidate)
        for row in plan_a.phases
    ) == PHASE_CONTRACT
    assert plan_a.execution_plan_digest == plan_b.execution_plan_digest
    assert len(plan_a.execution_plan_digest) == 64
    assert len(plan_a.test_paths("disposable_current_gate")) == 3
    assert len(plan_a.test_paths("historical_audit")) == 4
    assert set(plan_a.test_paths()).isdisjoint(
        {".git", ".codex_runtime"}
    )
    assert all(
        len(row.dependency_bundle_ids) == len(
            set(row.dependency_bundle_ids)
        )
        for row in plan_a.test_modules
    )


@pytest.mark.parametrize(
    ("mutator", "expected"),
    [
        (
            lambda value: value["phases"][0].update(
                phase="unknown_phase"
            ),
            "test_execution_contract_phase_order_or_boundary_invalid",
        ),
        (
            lambda value: value["phases"].append(
                deepcopy(value["phases"][0])
            ),
            "test_execution_contract_unknown_or_duplicate_phase",
        ),
        (
            lambda value: value["test_modules"].append(
                deepcopy(value["test_modules"][0])
            ),
            "test_execution_contract_test_module_duplicate_or_mixed_phase",
        ),
        (
            lambda value: value["test_modules"][0][
                "dependency_bundle_ids"
            ].append("unknown_bundle"),
            "test_execution_contract_test_dependency_bundle_unknown",
        ),
        (
            lambda value: value["phases"][3].update(
                gates_current_candidate=True
            ),
            "test_execution_contract_phase_order_or_boundary_invalid",
        ),
    ],
)
def test_unknown_duplicate_mixed_dependency_and_historical_gate_mutations_fail(
    mutator: Callable[[dict[str, Any]], Any],
    expected: str,
) -> None:
    registry = _json(ROOT / REGISTRY_REF)
    mutator(registry)
    with pytest.raises(ExecutionContractError) as failure:
        compile_test_execution_contract_registry(
            registry,
            registry_ref=REGISTRY_REF,
        )
    assert failure.value.code.startswith(expected)


def test_current_projection_bundle_closes_bindings_and_all_source_paths() -> None:
    projection = _json(ROOT / PROJECTION_REF)
    closure = {
        path.as_posix()
        for path in _declared_document_repository_paths(
            ROOT,
            [PROJECTION_REF],
        )
    }
    assert PROJECTION_REF in closure
    assert projection["decision_binding"]["ref"] in closure
    assert projection["implementation_binding"]["ref"] in closure
    assert set(projection["source_paths"].values()).issubset(closure)
    assert not any(
        path.startswith(".git") or path.startswith(".codex_runtime")
        for path in closure
    )


def test_current_candidate_manifest_uses_typed_closure_without_broad_prefixes() -> None:
    manifest = _json(ROOT / MANIFEST_REF)
    validate_active_test_suite_manifest(manifest)
    policy = manifest["hermetic_package_policy"]
    assert policy["repository_prefixes"] == []
    assert policy["test_execution_contract_registry_ref"] == REGISTRY_REF
    inventory = compile_repository_inventory(ROOT, manifest)
    paths = {path.as_posix() for path in inventory.paths}
    plan = load_test_execution_contract_registry(ROOT, REGISTRY_REF)
    assert set(plan.test_paths("disposable_current_gate")).issubset(paths)
    assert set(plan.test_paths("historical_audit")).isdisjoint(paths)
    assert not any(
        path.startswith(".git/") or path.startswith(".codex_runtime/")
        for path in paths
    )


def test_implementation_result_and_current_projection_keep_formal_boundary() -> None:
    implementation = _json(ROOT / IMPLEMENTATION_REF)
    projection = _json(ROOT / CURRENT_PROJECTION_REF)
    assert implementation["status"] == (
        "pass_engineering_zero_call_formal_clean_qualification_authority_pending"
    )
    assert implementation["engineering_full_chain"]["status"] == "pass"
    assert implementation["engineering_full_chain"][
        "classification"
    ].endswith("not_formal_qualification")
    assert implementation["product_truth"][
        "formal_clean_qualification_attempts_after_disposition"
    ] == [0, 1]
    assert projection["current_truth"]["current_next_action"] == (
        "FIN-0.1.2-S0-PHASE-AWARE-CLEAN-ENVIRONMENT-"
        "QUALIFICATION-AUTHORITY-DECISION"
    )
    assert projection["execution_authority"] == {
        "planning_and_read_only_audit_complete": True,
        "focused_s0_repair_authorized": False,
        "clean_environment_acceptance_authorized": False,
        "credential_model_provider_network_business_authorized": False,
    }


def test_typed_resource_helper_and_static_direct_root_read_fail_closed(
    tmp_path: Path,
) -> None:
    resource = tmp_path / "configs/runtime/resource.json"
    _write(resource, "{}\n")
    assert repository_test_resource(
        tmp_path,
        "runtime_resource_registry",
        "configs/runtime/resource.json",
    ) == resource
    with pytest.raises(RepositoryTestResourceError) as failure:
        repository_test_resource(
            tmp_path,
            "runtime_resource_registry",
            "../outside.json",
        )
    assert failure.value.code == "repository_test_resource_path_forbidden"

    registry = _json(ROOT / REGISTRY_REF)
    registry["test_modules"] = [
        {
            "test_path": "tests/direct_read.py",
            "phase": "disposable_current_gate",
            "dependency_bundle_ids": ["runtime_resource_registry"],
            "assertion_surfaces": ["negative_static_audit"],
        }
    ]
    _write(
        tmp_path / "tests/direct_read.py",
        "from pathlib import Path\n"
        "ROOT = Path(__file__).resolve().parents[1]\n"
        "VALUE = (ROOT / 'configs/runtime/resource.json').read_text()\n",
    )
    plan = compile_test_execution_contract_registry(
        registry,
        registry_ref="configs/registry.json",
    )
    with pytest.raises(HermeticTestRunnerError) as audit_failure:
        audit_disposable_test_resource_contract(
            tmp_path,
            plan,
            {
                "runtime_resource_registry": (
                    Path("configs/runtime/resource.json"),
                )
            },
        )
    assert audit_failure.value.code.startswith(
        "typed_test_resource_direct_root_read_forbidden"
    )


def _synthetic_registry() -> dict[str, Any]:
    bundles = [
        {
            "bundle_id": "current",
            "resolver_type": (
                "current_projection_binding_and_source_paths_closure"
            ),
            "configuration": {
                "policy_field": "host_current_program_projection_ref"
            },
        },
        {
            "bundle_id": "fixtures",
            "resolver_type": "tracked_fixture_prefix",
            "configuration": {"path": "tests/fixtures", "suffixes": [".json"]},
        },
        {
            "bundle_id": "history",
            "resolver_type": "immutable_event_root_closure",
            "configuration": {"roots": ["configs/history.json"]},
        },
        {
            "bundle_id": "python",
            "resolver_type": "python_import_closure",
            "configuration": {"source_roots": ["src", "tests"]},
        },
        {
            "bundle_id": "reference",
            "resolver_type": "reference_role_repository_closure",
            "configuration": {"registry_ref": "configs/reference.json"},
        },
        {
            "bundle_id": "runtime",
            "resolver_type": "runtime_resource_registry_closure",
            "configuration": {
                "registry_ref": "configs/runtime.json",
                "policy_contract_fields": [],
            },
        },
    ]
    modules = [
        {
            "test_path": "tests/current.py",
            "phase": "disposable_current_gate",
            "dependency_bundle_ids": ["python"],
            "assertion_surfaces": ["current_pass"],
        },
        {
            "test_path": "tests/historical.py",
            "phase": "historical_audit",
            "dependency_bundle_ids": ["python"],
            "assertion_surfaces": ["historical_finding"],
        },
        {
            "test_path": "tests/host.py",
            "phase": "host_preflight",
            "dependency_bundle_ids": ["python"],
            "assertion_surfaces": ["host_pass"],
        },
    ]
    return {
        "schema_version": "fin_ia_test_execution_contract_registry_v1_0",
        "registry_id": "SYNTHETIC-REGISTRY",
        "contract_id": "synthetic.phase.contract:v1",
        "status": "current_selected_engineering_candidate",
        "phases": [
            {
                "phase": phase,
                "location": location,
                "gates_current_candidate": gates,
            }
            for phase, location, gates in PHASE_CONTRACT
        ],
        "dependency_bundles": bundles,
        "test_modules": modules,
        "policies": {
            "one_selected_module_one_phase": True,
            "phase_derives_gating_role": True,
            "pytest_markers_are_mirrors_only": True,
            "direct_nonpython_repository_reads_require_typed_helper": True,
            "repository_shaped_direct_read_without_bundle_fails": True,
            "per_observed_file_exception_list_forbidden": True,
            "git_and_codex_runtime_packaging_forbidden": True,
            "historical_findings_gate_current_candidate": False,
            "pytest_basetemp_under_disposable_temporary_root": True,
        },
    }


def _synthetic_manifest() -> dict[str, Any]:
    suites = [
        ("immutable", "immutable_event", False, ["tests/historical.py"]),
        ("projection", "current_projection", True, ["tests/host.py"]),
        ("runtime", "current_runtime", True, ["tests/current.py"]),
        ("audit", "historical_audit", False, ["tests/historical.py"]),
        ("release", "release_gate", True, ["tests/host.py"]),
    ]
    return {
        "schema_version": "fin_ia_active_test_suite_manifest_v1_0",
        "manifest_id": "SYNTHETIC-MANIFEST",
        "status": "engineering_candidate_not_authorized_for_formal_qualification",
        "historical_failures_are_ignored": False,
        "suites": [
            {
                "suite_id": suite_id,
                "proof_class": proof_class,
                "selected": True,
                "gates_current_release": gating,
                "assertion_surfaces": [f"{suite_id}_surface"],
                "test_paths": paths,
            }
            for suite_id, proof_class, gating, paths in suites
        ],
        "runner_policy": {
            "runner_migration_completed": True,
            "manifest_is_clean_environment_authority": False,
        },
        "hermetic_package_policy": {
            "required_runner_files": [
                "src/sec_agent/hermetic_test_capture.py"
            ],
            "capture_plugin_path": "src/sec_agent/hermetic_test_capture.py",
            "test_execution_contract_registry_ref": "configs/registry.json",
            "repository_reference_policy": {
                "schema_version": "fin_ia_hermetic_repository_reference_policy_v1_0"
            },
            "external_read_only_bindings": [],
        },
    }


def test_two_fake_disposables_and_all_phase_results_are_separate(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    _write_json(repository / "configs/registry.json", _synthetic_registry())
    _write_json(repository / "manifest.json", _synthetic_manifest())
    _write(repository / "tests/host.py", "def test_host():\n    assert True\n")
    _write(
        repository / "tests/current.py",
        "def test_current():\n    assert True\n",
    )
    _write(
        repository / "tests/historical.py",
        "def test_historical():\n    assert False, 'preserved finding'\n",
    )
    capture_source = ROOT / "src/sec_agent/hermetic_test_capture.py"
    capture_target = repository / "src/sec_agent/hermetic_test_capture.py"
    _write(capture_target, capture_source.read_text(encoding="utf-8"))
    repository_paths = [
        Path("configs/registry.json"),
        Path("src/sec_agent/hermetic_test_capture.py"),
        Path("tests/current.py"),
        Path("tests/historical.py"),
        Path("tests/host.py"),
    ]
    result = run_hermetic_active_suite(
        repository_root=repository,
        manifest_path=repository / "manifest.json",
        output_root=tmp_path / "output",
        repository_paths=repository_paths,
    )
    assert result["status"] == "pass"
    phases = result["phase_results"]
    assert list(phases) == [
        "contract_compile",
        "host_preflight",
        "disposable_current_gate",
        "historical_audit",
        "post_run_attestation",
    ]
    disposable = phases["disposable_current_gate"]
    assert len(disposable["runs"]) == 2
    assert all(
        run["current_gate_all_green"]
        and run["pytest_basetemp_under_disposable_temporary_root"]
        for run in disposable["runs"]
    )
    assert phases["historical_audit"]["status"] == (
        "pass_non_gating_with_historical_findings"
    )
    assert result["historical_finding_nodeids"] == [
        "tests/historical.py::test_historical"
    ]
    for phase in (
        "contract_compile",
        "host_preflight",
        "historical_audit",
        "post_run_attestation",
    ):
        assert (
            tmp_path / "output" / "runs" / phase / "terminal_result.json"
        ).is_file()
