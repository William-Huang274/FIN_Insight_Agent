from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


TEST_EXECUTION_CONTRACT_REGISTRY_SCHEMA = (
    "fin_ia_test_execution_contract_registry_v1_0"
)

PHASE_CONTRACT = (
    ("contract_compile", "host_before_attempt", True),
    ("host_preflight", "clean_synced_repository_with_git", True),
    (
        "disposable_current_gate",
        "two_git_free_content_addressed_disposables",
        True,
    ),
    ("historical_audit", "host_read_only_after_current_gate", False),
    ("post_run_attestation", "host_read_only_closeout", True),
)

DEPENDENCY_RESOLVER_TYPES = frozenset(
    {
        "python_import_closure",
        "runtime_resource_registry_closure",
        "reference_role_repository_closure",
        "current_projection_binding_and_source_paths_closure",
        "immutable_event_root_closure",
        "tracked_fixture_prefix",
    }
)


class TestExecutionContractError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _canonical_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            dict(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _mapping(value: Any, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TestExecutionContractError(code)
    return value


def _nonempty_string(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TestExecutionContractError(code)
    return value.strip()


def _string_tuple(
    value: Any,
    code: str,
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise TestExecutionContractError(code)
    rows = tuple(_nonempty_string(item, code) for item in value)
    if not allow_empty and not rows:
        raise TestExecutionContractError(f"{code}_empty")
    if len(rows) != len(set(rows)):
        raise TestExecutionContractError(f"{code}_duplicate")
    return rows


def _strict_json(path: Path) -> dict[str, Any]:
    def object_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, value in pairs:
            if key in output:
                raise TestExecutionContractError(
                    f"test_execution_contract_duplicate_json_key:{key}"
                )
            output[key] = value
        return output

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=object_hook,
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise TestExecutionContractError(
            "test_execution_contract_registry_read_failed"
        ) from exc
    if not isinstance(value, dict):
        raise TestExecutionContractError(
            "test_execution_contract_registry_root_invalid"
        )
    return value


@dataclass(frozen=True)
class TestExecutionPhase:
    phase: str
    location: str
    gates_current_candidate: bool


@dataclass(frozen=True)
class TestDependencyBundle:
    bundle_id: str
    resolver_type: str
    configuration: Mapping[str, Any]


@dataclass(frozen=True)
class TestModuleExecution:
    test_path: str
    phase: str
    dependency_bundle_ids: tuple[str, ...]
    assertion_surfaces: tuple[str, ...]


@dataclass(frozen=True)
class CompiledTestExecutionContract:
    registry_id: str
    contract_id: str
    registry_ref: str
    registry_digest: str
    phases: tuple[TestExecutionPhase, ...]
    dependency_bundles: tuple[TestDependencyBundle, ...]
    test_modules: tuple[TestModuleExecution, ...]
    execution_plan_digest: str

    @property
    def phase_by_id(self) -> dict[str, TestExecutionPhase]:
        return {row.phase: row for row in self.phases}

    @property
    def bundle_by_id(self) -> dict[str, TestDependencyBundle]:
        return {row.bundle_id: row for row in self.dependency_bundles}

    @property
    def module_by_path(self) -> dict[str, TestModuleExecution]:
        return {row.test_path: row for row in self.test_modules}

    def test_paths(self, phase: str | None = None) -> tuple[str, ...]:
        if phase is not None and phase not in self.phase_by_id:
            raise TestExecutionContractError(
                f"test_execution_contract_unknown_phase:{phase}"
            )
        return tuple(
            row.test_path
            for row in self.test_modules
            if phase is None or row.phase == phase
        )

    def membership(self, nodeid: str) -> dict[str, Any]:
        path = nodeid.split("::", 1)[0].replace("\\", "/")
        module = self.module_by_path.get(path)
        if module is None:
            raise TestExecutionContractError(
                f"test_execution_contract_unregistered_test:{path}"
            )
        phase = self.phase_by_id[module.phase]
        return {
            "phase": phase.phase,
            "location": phase.location,
            "gates_current_candidate": phase.gates_current_candidate,
            "dependency_bundle_ids": list(module.dependency_bundle_ids),
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "fin_ia_compiled_test_execution_plan_v1_0",
            "registry_id": self.registry_id,
            "contract_id": self.contract_id,
            "registry_ref": self.registry_ref,
            "registry_digest": self.registry_digest,
            "execution_plan_digest": self.execution_plan_digest,
            "phases": [
                {
                    "phase": row.phase,
                    "location": row.location,
                    "gates_current_candidate": row.gates_current_candidate,
                    "selected_test_paths": list(self.test_paths(row.phase)),
                }
                for row in self.phases
            ],
            "dependency_bundles": [
                {
                    "bundle_id": row.bundle_id,
                    "resolver_type": row.resolver_type,
                }
                for row in self.dependency_bundles
            ],
        }


def compile_test_execution_contract_registry(
    registry: Mapping[str, Any],
    *,
    registry_ref: str,
) -> CompiledTestExecutionContract:
    expected_top_level = {
        "schema_version",
        "registry_id",
        "contract_id",
        "status",
        "phases",
        "dependency_bundles",
        "test_modules",
        "policies",
    }
    if set(registry) != expected_top_level:
        raise TestExecutionContractError(
            "test_execution_contract_registry_surface_invalid"
        )
    if registry.get("schema_version") != TEST_EXECUTION_CONTRACT_REGISTRY_SCHEMA:
        raise TestExecutionContractError(
            "test_execution_contract_registry_schema_invalid"
        )
    registry_id = _nonempty_string(
        registry.get("registry_id"),
        "test_execution_contract_registry_id_invalid",
    )
    contract_id = _nonempty_string(
        registry.get("contract_id"),
        "test_execution_contract_id_invalid",
    )
    if registry.get("status") != "current_selected_engineering_candidate":
        raise TestExecutionContractError(
            "test_execution_contract_registry_status_invalid"
        )

    raw_phases = registry.get("phases")
    if not isinstance(raw_phases, list):
        raise TestExecutionContractError(
            "test_execution_contract_phases_invalid"
        )
    phases: list[TestExecutionPhase] = []
    for index, expected in enumerate(PHASE_CONTRACT):
        if index >= len(raw_phases):
            raise TestExecutionContractError(
                "test_execution_contract_phase_missing"
            )
        row = _mapping(
            raw_phases[index], "test_execution_contract_phase_invalid"
        )
        if set(row) != {
            "phase",
            "location",
            "gates_current_candidate",
        }:
            raise TestExecutionContractError(
                "test_execution_contract_phase_surface_invalid"
            )
        observed = (
            row.get("phase"),
            row.get("location"),
            row.get("gates_current_candidate"),
        )
        if observed != expected:
            raise TestExecutionContractError(
                "test_execution_contract_phase_order_or_boundary_invalid"
            )
        phases.append(TestExecutionPhase(*expected))
    if len(raw_phases) != len(PHASE_CONTRACT):
        raise TestExecutionContractError(
            "test_execution_contract_unknown_or_duplicate_phase"
        )

    raw_bundles = registry.get("dependency_bundles")
    if not isinstance(raw_bundles, list) or not raw_bundles:
        raise TestExecutionContractError(
            "test_execution_contract_dependency_bundles_invalid"
        )
    bundles: list[TestDependencyBundle] = []
    bundle_ids: list[str] = []
    for value in raw_bundles:
        row = _mapping(
            value, "test_execution_contract_dependency_bundle_invalid"
        )
        if set(row) != {"bundle_id", "resolver_type", "configuration"}:
            raise TestExecutionContractError(
                "test_execution_contract_dependency_bundle_surface_invalid"
            )
        bundle_id = _nonempty_string(
            row.get("bundle_id"),
            "test_execution_contract_dependency_bundle_id_invalid",
        )
        resolver_type = _nonempty_string(
            row.get("resolver_type"),
            "test_execution_contract_dependency_resolver_invalid",
        )
        if resolver_type not in DEPENDENCY_RESOLVER_TYPES:
            raise TestExecutionContractError(
                f"test_execution_contract_dependency_resolver_unknown:{resolver_type}"
            )
        configuration = _mapping(
            row.get("configuration"),
            "test_execution_contract_dependency_configuration_invalid",
        )
        bundle_ids.append(bundle_id)
        bundles.append(
            TestDependencyBundle(bundle_id, resolver_type, configuration)
        )
    if len(bundle_ids) != len(set(bundle_ids)):
        raise TestExecutionContractError(
            "test_execution_contract_dependency_bundle_duplicate"
        )
    if bundle_ids != sorted(bundle_ids):
        raise TestExecutionContractError(
            "test_execution_contract_dependency_bundle_order_invalid"
        )
    if {row.resolver_type for row in bundles} != DEPENDENCY_RESOLVER_TYPES:
        raise TestExecutionContractError(
            "test_execution_contract_dependency_resolver_surface_incomplete"
        )

    raw_modules = registry.get("test_modules")
    if not isinstance(raw_modules, list) or not raw_modules:
        raise TestExecutionContractError(
            "test_execution_contract_test_modules_invalid"
        )
    modules: list[TestModuleExecution] = []
    test_paths: list[str] = []
    phase_ids = {row.phase for row in phases}
    known_bundles = set(bundle_ids)
    for value in raw_modules:
        row = _mapping(
            value, "test_execution_contract_test_module_invalid"
        )
        if set(row) != {
            "test_path",
            "phase",
            "dependency_bundle_ids",
            "assertion_surfaces",
        }:
            raise TestExecutionContractError(
                "test_execution_contract_test_module_surface_invalid"
            )
        test_path = _nonempty_string(
            row.get("test_path"),
            "test_execution_contract_test_path_invalid",
        ).replace("\\", "/")
        if (
            not test_path.startswith("tests/")
            or not test_path.endswith(".py")
            or ".." in Path(test_path).parts
        ):
            raise TestExecutionContractError(
                "test_execution_contract_test_path_invalid"
            )
        phase = _nonempty_string(
            row.get("phase"),
            "test_execution_contract_test_phase_invalid",
        )
        if phase not in phase_ids:
            raise TestExecutionContractError(
                f"test_execution_contract_test_phase_unknown:{phase}"
            )
        bundle_refs = _string_tuple(
            row.get("dependency_bundle_ids"),
            "test_execution_contract_test_dependency_bundles_invalid",
        )
        unknown = set(bundle_refs) - known_bundles
        if unknown:
            raise TestExecutionContractError(
                "test_execution_contract_test_dependency_bundle_unknown:"
                + sorted(unknown)[0]
            )
        surfaces = _string_tuple(
            row.get("assertion_surfaces"),
            "test_execution_contract_assertion_surfaces_invalid",
        )
        test_paths.append(test_path)
        modules.append(
            TestModuleExecution(test_path, phase, bundle_refs, surfaces)
        )
    if len(test_paths) != len(set(test_paths)):
        raise TestExecutionContractError(
            "test_execution_contract_test_module_duplicate_or_mixed_phase"
        )
    if test_paths != sorted(test_paths):
        raise TestExecutionContractError(
            "test_execution_contract_test_module_order_invalid"
        )

    policies = _mapping(
        registry.get("policies"),
        "test_execution_contract_policies_invalid",
    )
    required_policies = {
        "one_selected_module_one_phase": True,
        "phase_derives_gating_role": True,
        "pytest_markers_are_mirrors_only": True,
        "direct_nonpython_repository_reads_require_typed_helper": True,
        "repository_shaped_direct_read_without_bundle_fails": True,
        "per_observed_file_exception_list_forbidden": True,
        "git_and_codex_runtime_packaging_forbidden": True,
        "historical_findings_gate_current_candidate": False,
        "pytest_basetemp_under_disposable_temporary_root": True,
    }
    if set(policies) != set(required_policies) or any(
        policies.get(key) is not expected
        for key, expected in required_policies.items()
    ):
        raise TestExecutionContractError(
            "test_execution_contract_policy_boundary_invalid"
        )

    registry_digest = _canonical_digest(registry)
    plan_surface = {
        "contract_id": contract_id,
        "registry_digest": registry_digest,
        "phases": [row.__dict__ for row in phases],
        "bundles": [
            {
                "bundle_id": row.bundle_id,
                "resolver_type": row.resolver_type,
                "configuration": dict(row.configuration),
            }
            for row in bundles
        ],
        "modules": [
            {
                "test_path": row.test_path,
                "phase": row.phase,
                "dependency_bundle_ids": list(row.dependency_bundle_ids),
                "assertion_surfaces": list(row.assertion_surfaces),
            }
            for row in modules
        ],
    }
    return CompiledTestExecutionContract(
        registry_id=registry_id,
        contract_id=contract_id,
        registry_ref=registry_ref,
        registry_digest=registry_digest,
        phases=tuple(phases),
        dependency_bundles=tuple(bundles),
        test_modules=tuple(modules),
        execution_plan_digest=_canonical_digest(plan_surface),
    )


def load_test_execution_contract_registry(
    repository_root: Path,
    registry_ref: str,
) -> CompiledTestExecutionContract:
    root = repository_root.resolve()
    relative = Path(registry_ref.replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts:
        raise TestExecutionContractError(
            "test_execution_contract_registry_path_forbidden"
        )
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise TestExecutionContractError(
            "test_execution_contract_registry_path_escape"
        ) from exc
    if not path.is_file():
        raise TestExecutionContractError(
            "test_execution_contract_registry_missing"
        )
    return compile_test_execution_contract_registry(
        _strict_json(path),
        registry_ref=relative.as_posix(),
    )
