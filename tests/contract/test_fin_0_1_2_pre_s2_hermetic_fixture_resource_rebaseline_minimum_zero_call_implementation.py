from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from sec_agent.hermetic_test_runner import (
    HermeticTestRunnerError,
    _load_semantic_parity_contract,
    _semantic_text_projection,
    build_content_addressed_package,
    discover_repository_paths,
    read_object,
    run_hermetic_active_suite,
    validate_runtime_resource_inventory,
)
from sec_agent.runtime_contract_governance import (
    validate_active_test_suite_manifest,
)
from fin_0_1_2_realistic_fixture_support import (
    EXPECTED_SOURCE_INPUT_DIGEST,
    MU_FIXTURE,
    RealisticFixtureContractError,
    load_mu_realistic_fixture_document,
    load_mu_realistic_input_and_admission,
)
from test_fin_0_1_2_s1_bounded_production_consumer_migration import (
    _fin012_runtime,
)


RESOURCE_INVENTORY_REF = (
    "configs/runtime/"
    "fin_ia_0_1_2_runtime_nonpython_resource_inventory_v1_0.json"
)
RESOURCE_INVENTORY = ROOT / RESOURCE_INVENTORY_REF
PARITY_CONTRACT_REF = (
    "configs/runtime/"
    "fin_ia_0_1_2_hermetic_semantic_parity_projection_v1_0.json"
)
PARITY_CONTRACT = ROOT / PARITY_CONTRACT_REF
OLD_MU_HELPER_MODULE = (
    "test_fin_0_1_s4_t06_mu_research_lead_fact_presence_"
    "local_materialization_zero_call_implementation"
)
ACTIVE_MU_OWNER_MODULES = (
    ROOT
    / "tests/contract/"
    "test_fin_0_1_s4_t06_mu_case_runtime_mandatory_material_truth_"
    "identity_safety_closure_zero_call_implementation.py",
    ROOT
    / "tests/contract/"
    "test_fin_0_1_s4_t06_mu_current_case_aware_delivery_identity_"
    "boundary_zero_call_implementation.py",
)
IMPLEMENTATION_RECORD = ROOT / (
    "configs/releases/fin_ia_0_1_2_pre_s2_hermetic_fixture_resource_"
    "rebaseline_minimum_zero_call_implementation_v1_0.json"
)
T03_MANIFEST = ROOT / (
    "configs/releases/fin_ia_0_1_2_pre_s2_t03_replacement_"
    "hermetic_proof_manifest_v1_0.json"
)
PROGRAM_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
S4_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
CONTEXT = ROOT / "docs/project_os/current_context_pack.zh-CN.md"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_strict(path: Path) -> dict[str, Any]:
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_strict_object,
    )


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _resource_fixture_repository(tmp_path: Path) -> tuple[Path, Path]:
    repository = tmp_path / "repository"
    inventory = json.loads(RESOURCE_INVENTORY.read_text(encoding="utf-8"))
    refs = [inventory["registry_ref"], *(row["path"] for row in inventory["resources"])]
    for ref in refs:
        source = ROOT / ref
        target = repository / ref
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    inventory_path = repository / RESOURCE_INVENTORY_REF
    _write_json(inventory_path, inventory)
    return repository, inventory_path


def _semantic_contract() -> dict[str, Any]:
    manifest = {
        "hermetic_package_policy": {
            "semantic_parity_contract_ref": PARITY_CONTRACT_REF,
        }
    }
    contract, _, _ = _load_semantic_parity_contract(ROOT, manifest)
    assert contract is not None
    return contract


def _mini_manifest(*, test_path: str) -> dict[str, Any]:
    suites = []
    surface_by_class = {
        "immutable_event": "event_status",
        "current_projection": "current_next_action",
        "current_runtime": "current_code_digest",
        "historical_audit": "historical_output_digest",
        "release_gate": "release_gate_truth",
    }
    for proof_class, gates in (
        ("immutable_event", False),
        ("current_projection", True),
        ("current_runtime", True),
        ("historical_audit", False),
        ("release_gate", True),
    ):
        suites.append(
            {
                "suite_id": f"semantic_{proof_class}",
                "proof_class": proof_class,
                "selected": True,
                "gates_current_release": gates,
                "assertion_surfaces": [surface_by_class[proof_class]],
                "test_paths": [test_path],
            }
        )
    return {
        "schema_version": "fin_ia_active_test_suite_manifest_v1_0",
        "manifest_id": "pre-s2-semantic-parity-mini-proof",
        "status": "runner_migrated",
        "historical_failures_are_ignored": False,
        "suites": suites,
        "runner_policy": {
            "manifest_selection_is_authoritative": True,
            "unlisted_historical_test_failure_is_visible_but_not_implicitly_current": True,
            "listed_current_test_failure_is_blocking": True,
            "bulk_relax_historical_assertions_for_green_forbidden": True,
            "runner_migration_completed": True,
        },
        "hermetic_package_policy": {
            "required_runner_files": [
                "src/sec_agent/hermetic_test_capture.py",
                "src/sec_agent/hermetic_test_runner.py",
            ],
            "capture_plugin_path": "src/sec_agent/hermetic_test_capture.py",
            "semantic_parity_contract_ref": PARITY_CONTRACT_REF,
            "external_read_only_bindings": [],
        },
        "next_action": "mini",
    }


def _semantic_mini_repository(
    tmp_path: Path,
    *,
    printed_expression: str,
) -> tuple[Path, Path, tuple[Path, ...]]:
    repository = tmp_path / "repository"
    test_ref = "tests/test_semantic_path.py"
    files = {
        test_ref: (
            "from pathlib import Path\n\n"
            "def test_semantic_path():\n"
            f"    print({printed_expression})\n"
            "    assert True\n"
        ),
        "src/sec_agent/hermetic_test_capture.py": (
            ROOT / "src/sec_agent/hermetic_test_capture.py"
        ).read_text(encoding="utf-8"),
        "src/sec_agent/hermetic_test_runner.py": (
            ROOT / "src/sec_agent/hermetic_test_runner.py"
        ).read_text(encoding="utf-8"),
        PARITY_CONTRACT_REF: PARITY_CONTRACT.read_text(encoding="utf-8"),
    }
    for ref, text in files.items():
        target = repository / ref
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    manifest_path = repository / "manifest.json"
    _write_json(manifest_path, _mini_manifest(test_path=test_ref))
    return repository, manifest_path, tuple(Path(ref) for ref in files)


def test_tracked_MU_fixture_preserves_exact_input_and_nonpromotion_boundary() -> None:
    fixture = load_mu_realistic_fixture_document()
    input_pack, admission = load_mu_realistic_input_and_admission()
    assert _sha256(MU_FIXTURE) == (
        "84e2f2adf08423e6f7f7d2ab688656f2b1f47e83d5e62c24fb7fa25d82679909"
    )
    assert input_pack.company == "MU"
    assert input_pack.input_digest == EXPECTED_SOURCE_INPUT_DIGEST
    assert len(input_pack.cell_inputs) == 3
    assert admission.company == "MU"
    assert fixture["provenance_and_nonpromotion_boundary"][
        "fixture_role"
    ] == "deterministic_zero_call_input_only"
    assert fixture["provenance_and_nonpromotion_boundary"][
        "failed_output_business_promotable"
    ] is False
    serialized = MU_FIXTURE.read_text(encoding="utf-8")
    assert "sk-" not in serialized
    assert '"assistant_output_text"' not in serialized


def test_fixture_duplicate_key_and_content_mutation_fail_closed(
    tmp_path: Path,
) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text(
        '{"schema_version":"a","schema_version":"b"}',
        encoding="utf-8",
    )
    with pytest.raises(
        RealisticFixtureContractError,
        match="realistic_fixture_duplicate_json_key",
    ):
        load_mu_realistic_fixture_document(duplicate)

    mutated = json.loads(MU_FIXTURE.read_text(encoding="utf-8"))
    mutated["input_pack"]["company"] = "NVDA"
    mutation_path = tmp_path / "mutated.json"
    _write_json(mutation_path, mutated)
    with pytest.raises(
        RealisticFixtureContractError,
        match="realistic_fixture_content_digest_invalid",
    ):
        load_mu_realistic_fixture_document(mutation_path)


def test_active_three_case_runtime_reads_no_host_local_MU_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for path in ACTIVE_MU_OWNER_MODULES:
        text = path.read_text(encoding="utf-8")
        assert OLD_MU_HELPER_MODULE not in text
    assert ".codex_runtime" not in (
        ROOT / "tests/contract/fin_0_1_2_realistic_fixture_support.py"
    ).read_text(encoding="utf-8")

    original = Path.read_text

    def guarded_read(path: Path, *args: Any, **kwargs: Any) -> str:
        if ".codex_runtime" in path.as_posix():
            raise AssertionError("active_FIN_0_1_2_proof_read_host_local_runtime")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read)
    for ticker in ("DELL", "MU", "NVDA"):
        input_pack, admission, _ = _fin012_runtime(ticker)
        assert input_pack.company == ticker
        assert admission.company == ticker


def test_runtime_resource_inventory_exactly_matches_registry_and_bytes() -> None:
    paths = validate_runtime_resource_inventory(ROOT, RESOURCE_INVENTORY_REF)
    inventory = json.loads(RESOURCE_INVENTORY.read_text(encoding="utf-8"))
    assert len(paths) == 18
    assert inventory["resource_count"] == 16
    assert inventory["resource_bytes"] == 53382
    assert inventory["resource_canonical_digest"] == (
        "2b704b4c20dafad05097f59bb35740fc2f8a0479a2f55b6bb7d1a1bae15d1e9a"
    )
    assert {path.as_posix() for path in paths} == {
        RESOURCE_INVENTORY_REF,
        inventory["registry_ref"],
        *(row["path"] for row in inventory["resources"]),
    }


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (
            lambda value: value["resources"].pop(),
            "runtime_resource_inventory_missing_resource",
        ),
        (
            lambda value: value["resources"].append(
                deepcopy(value["resources"][0])
            ),
            "runtime_resource_inventory_duplicate_skill",
        ),
        (
            lambda value: value["resources"].append(
                {
                    "skill_id": "unknown_runtime_read",
                    "path": "src/sec_agent/prompts/skills/unknown.md",
                    "bytes": 1,
                    "sha256": "0" * 64,
                }
            ),
            "runtime_resource_inventory_unknown_resource",
        ),
        (
            lambda value: value["resources"][0].update(sha256="0" * 64),
            "runtime_resource_inventory_path_bytes_or_digest_drift",
        ),
    ],
)
def test_runtime_resource_inventory_mutations_fail_before_pytest(
    tmp_path: Path,
    mutation: Any,
    code: str,
) -> None:
    repository, inventory_path = _resource_fixture_repository(tmp_path)
    value = json.loads(inventory_path.read_text(encoding="utf-8"))
    mutation(value)
    _write_json(inventory_path, value)
    with pytest.raises(HermeticTestRunnerError, match=code):
        validate_runtime_resource_inventory(repository, RESOURCE_INVENTORY_REF)


def test_explicit_package_inventory_cannot_omit_runtime_resources(
    tmp_path: Path,
) -> None:
    repository, _ = _resource_fixture_repository(tmp_path)
    manifest = {
        "manifest_id": "resource-inventory-explicit-package",
        "hermetic_package_policy": {
            "required_runner_files": [],
            "runtime_nonpython_resource_inventory_ref": RESOURCE_INVENTORY_REF,
            "external_read_only_bindings": [],
        },
    }
    with pytest.raises(
        HermeticTestRunnerError,
        match="hermetic_explicit_inventory_omits_runtime_resource",
    ):
        build_content_addressed_package(
            repository_root=repository,
            manifest=manifest,
            package_root=tmp_path / "package_missing",
            repository_paths=(Path(RESOURCE_INVENTORY_REF),),
        )
    paths = validate_runtime_resource_inventory(repository, RESOURCE_INVENTORY_REF)
    package = build_content_addressed_package(
        repository_root=repository,
        manifest=manifest,
        package_root=tmp_path / "package_complete",
        repository_paths=paths,
    )
    assert len(package["repository_files"]) == 18


def test_semantic_projection_normalizes_only_exact_roots() -> None:
    contract = _semantic_contract()
    roots_a = {
        "exact_disposable_repository_root": r"C:\temp\runtime_a",
        "exact_disposable_package_root": r"C:\package",
        "exact_hermetic_temporary_parent": r"C:\temp",
    }
    roots_b = {
        "exact_disposable_repository_root": r"D:\other\runtime_b",
        "exact_disposable_package_root": r"D:\package",
        "exact_hermetic_temporary_parent": r"D:\other",
    }
    a = _semantic_text_projection(
        rb"failure L1-NUMERIC at C:\temp\runtime_a\tests\case.py value=10",
        roots=roots_a,
        contract=contract,
    )
    b = _semantic_text_projection(
        rb"failure L1-NUMERIC at D:\other\runtime_b\tests\case.py value=10",
        roots=roots_b,
        contract=contract,
    )
    changed_business_value = _semantic_text_projection(
        rb"failure L1-NUMERIC at D:\other\runtime_b\tests\case.py value=11",
        roots=roots_b,
        contract=contract,
    )
    assert a["normalization_valid"] is True
    assert b["normalization_valid"] is True
    assert a["semantic_sha256"] == b["semantic_sha256"]
    assert a["semantic_sha256"] != changed_business_value["semantic_sha256"]

    unknown = _semantic_text_projection(
        rb"failure at E:\nonallowlisted\financial.txt",
        roots=roots_a,
        contract=contract,
    )
    assert unknown["normalization_valid"] is False
    assert unknown["unknown_absolute_path_count"] == 1


def test_runner_preserves_raw_path_bytes_but_semantic_parity_passes(
    tmp_path: Path,
) -> None:
    repository, manifest_path, paths = _semantic_mini_repository(
        tmp_path,
        printed_expression="Path.cwd().resolve()",
    )
    result = run_hermetic_active_suite(
        repository_root=repository,
        manifest_path=manifest_path,
        output_root=tmp_path / "semantic_package",
        repository_paths=paths,
    )
    assert result["status"] == "pass"
    assert result["raw_disposable_parity"] is False
    assert result["disposable_parity"] is True
    assert result["semantic_normalization_valid"] == [True, True]
    package = Path(result["output_root"])
    assert len(result["semantic_projection_refs"]) == 2
    for ref, digest in zip(
        result["semantic_projection_refs"],
        result["semantic_projection_sha256"],
        strict=True,
    ):
        assert _sha256(package / ref) == digest
    terminal_a = json.loads(
        (package / "runs/disposable_a/terminal_result.json").read_text(
            encoding="utf-8"
        )
    )
    terminal_b = json.loads(
        (package / "runs/disposable_b/terminal_result.json").read_text(
            encoding="utf-8"
        )
    )
    stdout_a = terminal_a["tests"][0]["stdout"]
    stdout_b = terminal_b["tests"][0]["stdout"]
    assert stdout_a["sha256"] != stdout_b["sha256"]
    assert read_object(package, stdout_a) != read_object(package, stdout_b)


def test_runner_fails_closed_on_nonallowlisted_absolute_path(
    tmp_path: Path,
) -> None:
    repository, manifest_path, paths = _semantic_mini_repository(
        tmp_path,
        printed_expression="r'C:\\nonallowlisted\\financial.txt'",
    )
    result = run_hermetic_active_suite(
        repository_root=repository,
        manifest_path=manifest_path,
        output_root=tmp_path / "semantic_unknown_path_package",
        repository_paths=paths,
    )
    assert result["status"] == "failed"
    assert result["disposable_parity"] is False
    assert result["semantic_normalization_valid"] == [False, False]
    assert all(
        count >= 1
        for count in result["semantic_unknown_absolute_path_count"]
    )


def test_T02_record_binds_current_code_and_advances_only_to_T03() -> None:
    record = _load_strict(IMPLEMENTATION_RECORD)
    program = _load_strict(PROGRAM_BACKLOG)
    s4 = _load_strict(S4_BACKLOG)
    record_sha = _sha256(IMPLEMENTATION_RECORD)

    assert record["status"] == (
        "pass_T02_minimum_zero_call_implementation_full_host_matrix_green_"
        "T03_replacement_proof_ready"
    )
    assert record["tracked_MU_fixture"]["fixture_sha256"] == _sha256(
        ROOT / record["tracked_MU_fixture"]["fixture_ref"]
    )
    assert record["tracked_MU_fixture"]["loader_sha256"] == _sha256(
        ROOT / record["tracked_MU_fixture"]["loader_ref"]
    )
    assert record["tracked_MU_fixture"]["materializer_sha256"] == _sha256(
        ROOT / record["tracked_MU_fixture"]["materializer_ref"]
    )
    assert record["runtime_nonpython_resources"]["inventory_sha256"] == _sha256(
        ROOT / record["runtime_nonpython_resources"]["inventory_ref"]
    )
    assert record["runtime_nonpython_resources"][
        "inventory_generator_sha256"
    ] == _sha256(
        ROOT / record["runtime_nonpython_resources"]["inventory_generator_ref"]
    )
    assert record["semantic_parity"]["contract_sha256"] == _sha256(
        ROOT / record["semantic_parity"]["contract_ref"]
    )
    assert record["semantic_parity"]["runner_sha256"] == _sha256(
        ROOT / record["semantic_parity"]["runner_ref"]
    )
    for binding in record["active_owner_bindings"]:
        assert binding["sha256"] == _sha256(ROOT / binding["ref"])
    assert record["replacement_proof_manifest"]["manifest_sha256"] == (
        _sha256(ROOT / record["replacement_proof_manifest"]["manifest_ref"])
    )
    assert record["replacement_proof_manifest"]["status"] == (
        "ready_unexecuted_after_T02_pass"
    )

    assert record["authority"]["implementation_bundles_consumed"] == 1
    assert record["authority"]["replacement_proof_packages_consumed"] == 0
    assert record["product_truth"]["T02_engineering_status"] == (
        "pass_full_host_matrix_green"
    )
    assert record["product_truth"]["T03_replacement_proof"] == "not_started"
    assert record["product_truth"]["S2_entry"] is False
    assert record["product_truth"]["FIN_0_1_release_qualified"] is False

    assert program["next_action"]["item_id"] == record["next_action"]
    assert program["next_action"][
        "FIN_0_1_2_pre_S2_implementation_sha256"
    ] == record_sha
    assert s4["current_next_action"] == record["next_action"]
    assert s4["FIN_0_1_2_S1_stage_plan"][
        "pre_S2_implementation_sha256"
    ] == record_sha
    assert f"current next=`{record['next_action']}`" in CONTEXT.read_text(
        encoding="utf-8"
    )


def test_T03_manifest_is_runnable_and_binds_all_T02_dependency_contracts() -> None:
    manifest = _load_strict(T03_MANIFEST)
    validate_active_test_suite_manifest(manifest)
    assert manifest["status"] == (
        "PRE_S2_RB_T03_ready_unexecuted_after_T02_pass"
    )
    policy = manifest["hermetic_package_policy"]
    assert policy["runtime_nonpython_resource_inventory_ref"] == (
        RESOURCE_INVENTORY_REF
    )
    assert policy["semantic_parity_contract_ref"] == PARITY_CONTRACT_REF
    assert policy["external_read_only_bindings"] == []
    discovered = set(discover_repository_paths(ROOT, manifest))
    required_resources = set(
        validate_runtime_resource_inventory(ROOT, RESOURCE_INVENTORY_REF)
    )
    assert required_resources.issubset(discovered)
    assert MU_FIXTURE.relative_to(ROOT) in discovered
    assert T03_MANIFEST.relative_to(ROOT) in discovered
    assert manifest["next_action_on_pass"] == (
        "FIN-0.1.2-S2-ENTRY-STAGE-PLAN-AUTHORITY-DECISION"
    )
    assert manifest["next_action_on_failure"] == (
        "FIN-0.1.2-PRE-S2-HONEST-BLOCK-CLOSEOUT-NO-SECOND-PROOF-PACKAGE"
    )
