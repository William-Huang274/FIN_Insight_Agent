from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import shutil
from typing import Any, Callable

import pytest

import sec_agent.runtime_resource_registry as registry_module
from sec_agent.research_skills import SKILL_FILES
from sec_agent.runtime_resource_registry import (
    DEFAULT_RUNTIME_RESOURCE_REGISTRY_REF,
    RuntimeResourceRegistryError,
    assert_no_unregistered_runtime_resource_literals,
    detect_repo_relative_runtime_resource_literals,
    load_runtime_resource_registry,
    read_registered_runtime_json,
    registered_runtime_resource,
)
from sec_agent.test_resource import repository_test_resource


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_RESOURCE_BUNDLE_ID = "runtime_resource_registry"
REGISTRY_PATH = repository_test_resource(
    ROOT,
    RUNTIME_RESOURCE_BUNDLE_ID,
    DEFAULT_RUNTIME_RESOURCE_REGISTRY_REF,
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _copy_closure(destination: Path) -> dict[str, Any]:
    registry = _load(REGISTRY_PATH)
    refs = {
        DEFAULT_RUNTIME_RESOURCE_REGISTRY_REF,
        *registry["detector_python_refs"],
        *(row["repo_relative_path"] for row in registry["resources"]),
    }
    for ref in refs:
        target = destination / ref
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(
            repository_test_resource(
                ROOT,
                RUNTIME_RESOURCE_BUNDLE_ID,
                ref,
            ),
            target,
        )
    return registry


def _assert_code(root: Path, expected: str) -> None:
    with pytest.raises(RuntimeResourceRegistryError) as failure:
        load_runtime_resource_registry(root)
    assert failure.value.code.startswith(expected)


def test_registry_is_one_validated_authority_for_all_declared_consumers() -> None:
    registry = load_runtime_resource_registry(ROOT)
    assert len(registry.resources) == 29
    assert sum(row.bytes for row in registry.resources) == 323829
    assert registry.resource_canonical_digest == (
        "d2126d8c5e8c94c1d435ba0b9cada37e70ee6bd5e7d38a6233ed0db2e19079a4"
    )
    assert registry.package_paths()[0].as_posix().startswith("configs/")
    assert all(row.required for row in registry.resources)
    assert all(row.consumer_ids for row in registry.resources)


def test_static_detector_finds_no_direct_unregistered_runtime_literal() -> None:
    registry = load_runtime_resource_registry(ROOT)
    detected = detect_repo_relative_runtime_resource_literals(ROOT, registry)
    assert len(detected) == 28
    assert set(detected).issubset(registry.by_path())
    assert assert_no_unregistered_runtime_resource_literals(ROOT) == detected


def test_research_skill_registry_and_resource_ids_have_exact_parity() -> None:
    registry = load_runtime_resource_registry(ROOT)
    expected = {
        f"src/sec_agent/prompts/skills/{filename}": (
            f"research_skill.{skill_id}"
        )
        for skill_id, filename in SKILL_FILES.items()
    }
    observed = {
        row.repo_relative_path: row.resource_id
        for row in registry.resources
        if row.classification == "prompt_skill_instruction"
    }
    assert observed == expected
    assert len(observed) == len(SKILL_FILES) == 16


def test_registered_json_reader_uses_resource_id_not_caller_path() -> None:
    payload = read_registered_runtime_json(
        ROOT,
        "fin_0_1_2.common_runtime_contract_family_binding",
    )
    assert payload["schema_version"] == (
        "fin_ia_0_1_2_common_runtime_contract_family_binding_v1_0"
    )
    with pytest.raises(RuntimeResourceRegistryError) as failure:
        registered_runtime_resource(ROOT, "unknown.runtime.resource")
    assert failure.value.code == (
        "runtime_resource_registry_unknown_resource_id:unknown.runtime.resource"
    )


@pytest.mark.parametrize(
    ("mutator", "expected"),
    [
        (
            lambda root, value: (root / value["resources"][0]["repo_relative_path"]).unlink(),
            "runtime_resource_registry_required_resource_missing",
        ),
        (
            lambda root, value: (root / value["resources"][0]["repo_relative_path"]).write_bytes(b"drift"),
            "runtime_resource_registry_digest_or_bytes_drift",
        ),
        (
            lambda root, value: value["resources"].append(
                {**deepcopy(value["resources"][0]), "resource_id": "zz.duplicate.path"}
            ),
            "runtime_resource_registry_duplicate_resource_path",
        ),
        (
            lambda root, value: value.update(resources=list(reversed(value["resources"]))),
            "runtime_resource_registry_resource_order_invalid",
        ),
        (
            lambda root, value: value.update(
                schema_version="fin_ia_0_1_2_runtime_resource_registry_v1_0"
            ),
            "runtime_resource_registry_schema_invalid",
        ),
        (
            lambda root, value: value["resources"][0].update(
                repo_relative_path="../outside.json"
            ),
            "runtime_resource_registry_path_forbidden",
        ),
    ],
)
def test_missing_duplicate_drift_permutation_cross_version_and_traversal_fail_closed(
    tmp_path: Path,
    mutator: Callable[[Path, dict[str, Any]], Any],
    expected: str,
) -> None:
    registry = _copy_closure(tmp_path)
    mutator(tmp_path, registry)
    if expected not in {
        "runtime_resource_registry_required_resource_missing",
        "runtime_resource_registry_digest_or_bytes_drift",
    }:
        _write(tmp_path / DEFAULT_RUNTIME_RESOURCE_REGISTRY_REF, registry)
    _assert_code(tmp_path, expected)


def test_duplicate_json_key_fails_before_any_resource_is_read(tmp_path: Path) -> None:
    _copy_closure(tmp_path)
    path = tmp_path / DEFAULT_RUNTIME_RESOURCE_REGISTRY_REF
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace(
            '  "status": "tracked_typed_runtime_resource_authority",',
            '  "status": "tracked_typed_runtime_resource_authority",\n'
            '  "status": "tracked_typed_runtime_resource_authority",',
            1,
        ),
        encoding="utf-8",
    )
    _assert_code(tmp_path, "runtime_resource_registry_duplicate_json_key")


def test_new_unregistered_literal_is_a_deterministic_detector_failure(
    tmp_path: Path,
) -> None:
    registry = _copy_closure(tmp_path)
    source = tmp_path / registry["detector_python_refs"][0]
    source.write_text(
        source.read_text(encoding="utf-8")
        + '\nUNREGISTERED_RUNTIME_RESOURCE = "configs/runtime/not_registered.json"\n',
        encoding="utf-8",
    )
    with pytest.raises(RuntimeResourceRegistryError) as failure:
        assert_no_unregistered_runtime_resource_literals(tmp_path)
    assert failure.value.code == (
        "runtime_resource_registry_unregistered_literal:"
        "configs/runtime/not_registered.json"
    )


def test_frozen_skill_mapping_compatibility_adapter_drift_fails_closed(
    tmp_path: Path,
) -> None:
    _copy_closure(tmp_path)
    source = tmp_path / "src/sec_agent/research_skills.py"
    source.write_text(
        source.read_text(encoding="utf-8").replace(
            '"investment_research_workflow":',
            '"investment_research_workflow_changed":',
            1,
        ),
        encoding="utf-8",
    )
    _assert_code(
        tmp_path,
        "runtime_resource_registry_compatibility_adapter_drift",
    )


def test_resolved_symlink_escape_guard_fails_without_OS_symlink_privilege(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = _copy_closure(tmp_path)
    relative = Path(registry["resources"][0]["repo_relative_path"])
    target = tmp_path / relative
    outside = tmp_path.parent / "outside-resource.json"
    outside.write_text("{}", encoding="utf-8")
    original_resolve = Path.resolve

    def guarded_resolve(path: Path, *args: Any, **kwargs: Any) -> Path:
        if path == target:
            return original_resolve(outside, *args, **kwargs)
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", guarded_resolve)
    with pytest.raises(RuntimeResourceRegistryError) as failure:
        registry_module._repo_relative_path(
            tmp_path,
            relative.as_posix(),
            missing_code="not_reached",
        )
    assert failure.value.code == "runtime_resource_registry_symlink_escape"
