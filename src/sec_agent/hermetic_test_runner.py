from __future__ import annotations

import ast
from collections import Counter
from dataclasses import dataclass
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Iterable, Mapping, Sequence

from sec_agent.runtime_contract_governance import (
    ContractGovernanceError,
    validate_active_test_suite_manifest,
)


RUNNER_SCHEMA = "fin_ia_hermetic_active_suite_runner_v1_0"
PACKAGE_SCHEMA = "fin_ia_hermetic_source_package_manifest_v1_0"
TERMINAL_SCHEMA = "fin_ia_hermetic_active_suite_terminal_result_v1_0"
VERIFICATION_SCHEMA = "fin_ia_hermetic_active_suite_verification_v1_0"
RUNTIME_RESOURCE_INVENTORY_SCHEMA = (
    "fin_ia_0_1_2_runtime_nonpython_resource_inventory_v1_0"
)
SEMANTIC_PARITY_SCHEMA = (
    "fin_ia_0_1_2_hermetic_semantic_parity_projection_v1_0"
)

_CREDENTIAL_ENV_NAMES = frozenset(
    {
        "OPENAI_API_KEY",
        "DEEPSEEK_API_KEY",
        "ANTHROPIC_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
        "EDINET_API_KEY",
    }
)


class HermeticTestRunnerError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise HermeticTestRunnerError(
                    f"hermetic_json_duplicate_key:{key}"
                )
            result[key] = item
        return result

    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=strict_object,
    )
    if not isinstance(value, dict):
        raise HermeticTestRunnerError("hermetic_json_root_not_object")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


@dataclass(frozen=True)
class ObjectRef:
    sha256: str
    bytes: int
    ref: str

    def as_dict(self) -> dict[str, Any]:
        return {"sha256": self.sha256, "bytes": self.bytes, "ref": self.ref}


class ContentAddressedStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def put_bytes(self, value: bytes) -> ObjectRef:
        digest = _sha256_bytes(value)
        relative = Path("objects") / "sha256" / digest[:2] / digest
        target = self.root / relative
        if target.exists():
            if _sha256_file(target) != digest:
                raise HermeticTestRunnerError("content_store_existing_object_corrupt")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + ".tmp")
            temporary.write_bytes(value)
            if _sha256_file(temporary) != digest:
                raise HermeticTestRunnerError("content_store_write_readback_mismatch")
            temporary.replace(target)
        return ObjectRef(digest, len(value), relative.as_posix())

    def put_file(self, path: Path) -> ObjectRef:
        return self.put_bytes(path.read_bytes())


def _safe_relative_path(repository_root: Path, value: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise HermeticTestRunnerError("hermetic_package_path_outside_repository")
    resolved = (repository_root / relative).resolve()
    try:
        resolved.relative_to(repository_root.resolve())
    except ValueError as exc:
        raise HermeticTestRunnerError(
            "hermetic_package_path_outside_repository"
        ) from exc
    if not resolved.is_file():
        raise HermeticTestRunnerError("hermetic_package_file_missing")
    return Path(*relative.parts)


def _git_output(repository_root: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", *args],
        cwd=repository_root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise HermeticTestRunnerError("hermetic_git_inventory_failed")
    return completed.stdout


def _repository_ref_strings(value: Any) -> Iterable[str]:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if isinstance(item, str) and (key == "ref" or key.endswith("_ref")):
                yield item
            else:
                yield from _repository_ref_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _repository_ref_strings(item)


def _literal_string_mapping(
    path: Path,
    variable_name: str,
) -> dict[str, str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        raise HermeticTestRunnerError(
            "runtime_resource_registry_parse_failed"
        ) from exc
    candidate: ast.AST | None = None
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == variable_name:
                candidate = node.value
                break
        if isinstance(node, ast.Assign):
            if any(
                isinstance(target, ast.Name) and target.id == variable_name
                for target in node.targets
            ):
                candidate = node.value
                break
    if candidate is None:
        raise HermeticTestRunnerError(
            "runtime_resource_registry_mapping_missing"
        )
    try:
        value = ast.literal_eval(candidate)
    except (ValueError, TypeError) as exc:
        raise HermeticTestRunnerError(
            "runtime_resource_registry_mapping_not_literal"
        ) from exc
    if (
        not isinstance(value, dict)
        or not value
        or not all(
            isinstance(key, str)
            and key.strip()
            and isinstance(item, str)
            and item.strip()
            for key, item in value.items()
        )
    ):
        raise HermeticTestRunnerError(
            "runtime_resource_registry_mapping_invalid"
        )
    if len(set(value.values())) != len(value):
        raise HermeticTestRunnerError(
            "runtime_resource_registry_duplicate_path"
        )
    return {str(key): str(item) for key, item in value.items()}


def validate_runtime_resource_inventory(
    repository_root: Path,
    inventory_ref: str,
) -> tuple[Path, ...]:
    repository_root = repository_root.resolve()
    inventory_path = _safe_relative_path(repository_root, inventory_ref)
    inventory = _load_json(repository_root / inventory_path)
    expected_top_level = {
        "schema_version",
        "inventory_id",
        "status",
        "registry_ref",
        "registry_mapping_name",
        "registry_source_sha256",
        "resource_root",
        "resource_count",
        "resource_bytes",
        "resource_canonical_digest",
        "resources",
        "package_contract",
    }
    if set(inventory) != expected_top_level:
        raise HermeticTestRunnerError(
            "runtime_resource_inventory_top_level_invalid"
        )
    if inventory["schema_version"] != RUNTIME_RESOURCE_INVENTORY_SCHEMA:
        raise HermeticTestRunnerError("runtime_resource_inventory_schema_invalid")
    if inventory["status"] != "tracked_exact_runtime_resource_inventory":
        raise HermeticTestRunnerError("runtime_resource_inventory_status_invalid")
    registry_path = _safe_relative_path(
        repository_root,
        str(inventory["registry_ref"]),
    )
    registry_full_path = repository_root / registry_path
    if _sha256_file(registry_full_path) != inventory["registry_source_sha256"]:
        raise HermeticTestRunnerError(
            "runtime_resource_registry_source_digest_mismatch"
        )
    mapping_name = str(inventory["registry_mapping_name"])
    registry = _literal_string_mapping(registry_full_path, mapping_name)
    resource_root = str(inventory["resource_root"]).strip().replace("\\", "/")
    if not resource_root or resource_root.startswith("/") or ".." in Path(resource_root).parts:
        raise HermeticTestRunnerError("runtime_resource_root_invalid")
    rows = inventory["resources"]
    if not isinstance(rows, list):
        raise HermeticTestRunnerError("runtime_resource_inventory_rows_invalid")
    skill_ids: list[str] = []
    paths: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != {
            "skill_id",
            "path",
            "bytes",
            "sha256",
        }:
            raise HermeticTestRunnerError(
                "runtime_resource_inventory_row_invalid"
            )
        skill_ids.append(str(row["skill_id"]))
        paths.append(str(row["path"]).replace("\\", "/"))
    if len(set(skill_ids)) != len(skill_ids):
        raise HermeticTestRunnerError(
            "runtime_resource_inventory_duplicate_skill"
        )
    if len(set(paths)) != len(paths):
        raise HermeticTestRunnerError(
            "runtime_resource_inventory_duplicate_path"
        )
    if set(skill_ids) - set(registry):
        raise HermeticTestRunnerError(
            "runtime_resource_inventory_unknown_resource"
        )
    if set(registry) - set(skill_ids):
        raise HermeticTestRunnerError(
            "runtime_resource_inventory_missing_resource"
        )
    expected_rows: list[dict[str, Any]] = []
    resource_paths: list[Path] = []
    for skill_id, filename in sorted(registry.items()):
        expected_path = f"{resource_root}/{filename}"
        relative = _safe_relative_path(repository_root, expected_path)
        value = (repository_root / relative).read_bytes()
        expected_rows.append(
            {
                "skill_id": skill_id,
                "path": relative.as_posix(),
                "bytes": len(value),
                "sha256": _sha256_bytes(value),
            }
        )
        resource_paths.append(relative)
    if rows != expected_rows:
        raise HermeticTestRunnerError(
            "runtime_resource_inventory_path_bytes_or_digest_drift"
        )
    canonical_rows = json.dumps(
        expected_rows,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if (
        inventory["resource_count"] != len(expected_rows)
        or inventory["resource_bytes"]
        != sum(int(row["bytes"]) for row in expected_rows)
        or inventory["resource_canonical_digest"]
        != _sha256_bytes(canonical_rows)
    ):
        raise HermeticTestRunnerError(
            "runtime_resource_inventory_aggregate_drift"
        )
    package_contract = inventory["package_contract"]
    if not isinstance(package_contract, Mapping) or any(
        package_contract.get(key) is not expected
        for key, expected in {
            "registry_mapping_is_source_of_truth": True,
            "directory_glob_is_authority": False,
            "missing_resource_fails_before_pytest": True,
            "duplicate_skill_or_path_fails_before_pytest": True,
            "path_or_hash_drift_fails_before_pytest": True,
            "unknown_inventory_resource_fails_before_pytest": True,
        }.items()
    ):
        raise HermeticTestRunnerError(
            "runtime_resource_inventory_package_contract_invalid"
        )
    return tuple(
        sorted(
            {inventory_path, registry_path, *resource_paths},
            key=lambda item: item.as_posix(),
        )
    )


def _policy_contract_paths(
    repository_root: Path,
    policy: Mapping[str, Any],
) -> tuple[Path, ...]:
    paths: set[Path] = set()
    inventory_ref = policy.get("runtime_nonpython_resource_inventory_ref")
    if inventory_ref is not None:
        if not isinstance(inventory_ref, str) or not inventory_ref.strip():
            raise HermeticTestRunnerError(
                "runtime_resource_inventory_ref_invalid"
            )
        paths.update(
            validate_runtime_resource_inventory(
                repository_root,
                inventory_ref,
            )
        )
    parity_ref = policy.get("semantic_parity_contract_ref")
    if parity_ref is not None:
        if not isinstance(parity_ref, str) or not parity_ref.strip():
            raise HermeticTestRunnerError("semantic_parity_contract_ref_invalid")
        paths.add(_safe_relative_path(repository_root, parity_ref))
    return tuple(sorted(paths, key=lambda item: item.as_posix()))


def discover_repository_paths(
    repository_root: Path,
    manifest: Mapping[str, Any],
) -> tuple[Path, ...]:
    raw = _git_output(repository_root, "ls-files", "-z")
    tracked = {
        item.decode("utf-8").replace("\\", "/")
        for item in raw.split(b"\0")
        if item
    }
    policy = manifest["hermetic_package_policy"]
    values = set(str(item) for item in policy["required_runner_files"])
    values.update(str(item) for item in policy.get("repository_seed_paths", []))
    values.update(_selected_test_paths(manifest))
    values.update(
        path.as_posix()
        for path in _policy_contract_paths(repository_root, policy)
    )
    for prefix_row in policy.get("repository_prefixes", []):
        if not isinstance(prefix_row, Mapping):
            raise HermeticTestRunnerError("hermetic_repository_prefix_invalid")
        prefix = str(prefix_row.get("path", "")).strip().replace("\\", "/").rstrip("/")
        suffixes = prefix_row.get("suffixes")
        if not prefix or not isinstance(suffixes, list) or not all(
            isinstance(item, str) for item in suffixes
        ):
            raise HermeticTestRunnerError("hermetic_repository_prefix_incomplete")
        values.update(
            path
            for path in tracked
            if path.startswith(prefix + "/")
            and any(path.endswith(suffix) for suffix in suffixes)
        )

    pending = list(values)
    while pending:
        value = pending.pop()
        relative = _safe_relative_path(repository_root, value)
        if relative.suffix.lower() != ".json":
            continue
        document = _load_json(repository_root / relative)
        for ref in _repository_ref_strings(document):
            normalized = ref.replace("\\", "/")
            if normalized in values:
                continue
            candidate = Path(normalized)
            if candidate.is_absolute() or ".." in candidate.parts:
                continue
            if (repository_root / candidate).is_file():
                values.add(normalized)
                pending.append(normalized)

    paths = {_safe_relative_path(repository_root, value) for value in values}
    return tuple(sorted(paths, key=lambda item: item.as_posix()))


def _resolve_external_dependencies(
    repository_root: Path,
    package_policy: Mapping[str, Any],
) -> list[tuple[str, Path, str]]:
    resolved: list[tuple[str, Path, str]] = []
    rows = package_policy.get("external_read_only_bindings", [])
    if not isinstance(rows, list):
        raise HermeticTestRunnerError("hermetic_external_bindings_invalid")
    for row in rows:
        if not isinstance(row, Mapping):
            raise HermeticTestRunnerError("hermetic_external_binding_invalid")
        binding_id = str(row.get("binding_id", "")).strip()
        manifest_ref = str(row.get("binding_manifest", "")).strip()
        object_field = str(row.get("binding_object_field", "")).strip()
        files = row.get("files")
        if not binding_id or not manifest_ref or not object_field or not isinstance(files, list):
            raise HermeticTestRunnerError("hermetic_external_binding_incomplete")
        binding_manifest = _load_json(repository_root / _safe_relative_path(repository_root, manifest_ref))
        binding = binding_manifest.get(object_field)
        if not isinstance(binding, Mapping):
            raise HermeticTestRunnerError("hermetic_external_binding_object_missing")
        root_value = binding.get("path")
        if not isinstance(root_value, str) or not root_value.strip():
            raise HermeticTestRunnerError("hermetic_external_binding_path_missing")
        external_root = Path(root_value)
        for file_row in files:
            if not isinstance(file_row, Mapping):
                raise HermeticTestRunnerError("hermetic_external_file_binding_invalid")
            relative = str(file_row.get("relative_path", "")).strip()
            digest_field = str(file_row.get("sha256_field", "")).strip()
            expected = binding.get(digest_field)
            path = external_root / relative
            if not relative or not digest_field or not isinstance(expected, str):
                raise HermeticTestRunnerError("hermetic_external_file_binding_incomplete")
            if not path.is_file() or _sha256_file(path) != expected:
                raise HermeticTestRunnerError("hermetic_external_dependency_digest_mismatch")
            resolved.append((f"{binding_id}:{relative}", path, expected))
    return resolved


def _python_environment_inventory() -> dict[str, Any]:
    site_paths = sorted(
        {
            str(Path(value).resolve())
            for value in sys.path
            if value
            and Path(value).is_dir()
            and (
                "site-packages" in value.lower()
                or "dist-packages" in value.lower()
            )
        }
    )
    distributions = sorted(
        {
            (
                str(distribution.metadata.get("Name", "unknown")),
                str(distribution.version),
            )
            for distribution in importlib.metadata.distributions()
        },
        key=lambda item: (item[0].lower(), item[1]),
    )
    return {
        "python_executable": str(Path(sys.executable).resolve()),
        "python_version": sys.version,
        "site_paths": site_paths,
        "installed_distributions": [
            {"name": name, "version": version}
            for name, version in distributions
        ],
    }


def build_content_addressed_package(
    *,
    repository_root: Path,
    manifest: Mapping[str, Any],
    package_root: Path,
    repository_paths: Sequence[Path] | None = None,
) -> dict[str, Any]:
    repository_root = repository_root.resolve()
    package_policy = manifest.get("hermetic_package_policy")
    if not isinstance(package_policy, Mapping):
        raise HermeticTestRunnerError("hermetic_package_policy_missing")
    required = package_policy.get("required_runner_files")
    if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
        raise HermeticTestRunnerError("hermetic_required_runner_files_invalid")
    policy_contract_paths = _policy_contract_paths(
        repository_root,
        package_policy,
    )
    paths = (
        discover_repository_paths(repository_root, manifest)
        if repository_paths is None
        else tuple(
            sorted(
                {_safe_relative_path(repository_root, item.as_posix()) for item in repository_paths},
                key=lambda item: item.as_posix(),
            )
        )
    )
    if repository_paths is not None and not set(policy_contract_paths).issubset(
        set(paths)
    ):
        raise HermeticTestRunnerError(
            "hermetic_explicit_inventory_omits_runtime_resource_or_parity_contract"
        )
    store = ContentAddressedStore(package_root)
    entries = []
    for relative in paths:
        ref = store.put_file(repository_root / relative)
        entries.append({"path": relative.as_posix(), **ref.as_dict()})

    external_entries = []
    for dependency_id, path, expected in _resolve_external_dependencies(
        repository_root, package_policy
    ):
        ref = store.put_file(path)
        if ref.sha256 != expected:
            raise HermeticTestRunnerError("hermetic_external_dependency_package_mismatch")
        external_entries.append({"dependency_id": dependency_id, **ref.as_dict()})

    if repository_paths is None:
        git_head = _git_output(repository_root, "rev-parse", "HEAD").decode("ascii").strip()
        status = _git_output(repository_root, "status", "--short").decode("utf-8").splitlines()
        inventory_source = str(package_policy["repository_inventory"])
    else:
        git_head = "explicit_fixture_inventory_no_git_head"
        status = []
        inventory_source = "explicit_fixture_inventory"
    payload = {
        "schema_version": PACKAGE_SCHEMA,
        "runner_schema": RUNNER_SCHEMA,
        "active_manifest_id": manifest["manifest_id"],
        "active_manifest_digest": _sha256_bytes(_canonical_bytes(manifest)),
        "git_head": git_head,
        "worktree_status": status,
        "inventory_source": inventory_source,
        "python_environment": _python_environment_inventory(),
        "repository_files": entries,
        "external_read_only_dependencies": external_entries,
        "credential_environment_names_removed": sorted(_CREDENTIAL_ENV_NAMES),
    }
    payload["semantic_digest"] = _sha256_bytes(_canonical_bytes(payload))
    _write_json(package_root / "package_manifest.json", payload)
    return payload


def _materialize_package(
    package_root: Path,
    package_manifest: Mapping[str, Any],
    destination: Path,
) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    for row in package_manifest["repository_files"]:
        source = package_root / str(row["ref"])
        target = destination / str(row["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if _sha256_file(target) != row["sha256"]:
            raise HermeticTestRunnerError("hermetic_materialized_file_digest_mismatch")


def _selected_test_paths(manifest: Mapping[str, Any]) -> tuple[str, ...]:
    paths = {
        str(path)
        for suite in manifest["suites"]
        if suite["selected"]
        for path in suite["test_paths"]
    }
    return tuple(sorted(paths))


def _suite_memberships(
    manifest: Mapping[str, Any], nodeid: str
) -> list[dict[str, Any]]:
    path = nodeid.split("::", 1)[0].replace("\\", "/")
    return [
        {
            "suite_id": suite["suite_id"],
            "proof_class": suite["proof_class"],
            "gates_current_release": suite["gates_current_release"],
        }
        for suite in manifest["suites"]
        if suite["selected"]
        and path in {str(item).replace("\\", "/") for item in suite["test_paths"]}
    ]


def _objectize_raw_capture(
    *,
    raw: Mapping[str, Any],
    manifest: Mapping[str, Any],
    store: ContentAddressedStore,
) -> list[dict[str, Any]]:
    results = []
    tests = raw.get("tests")
    if not isinstance(tests, list):
        raise HermeticTestRunnerError("hermetic_raw_test_capture_invalid")
    for row in tests:
        if not isinstance(row, Mapping):
            raise HermeticTestRunnerError("hermetic_raw_test_row_invalid")
        memberships = _suite_memberships(manifest, str(row["nodeid"]))
        if not memberships:
            raise HermeticTestRunnerError("hermetic_test_without_manifest_membership")
        stdout = store.put_bytes(str(row.get("stdout", "")).encode("utf-8"))
        stderr = store.put_bytes(str(row.get("stderr", "")).encode("utf-8"))
        detail = store.put_bytes(str(row.get("detail", "")).encode("utf-8"))
        phases = [
            {"phase": item["phase"], "outcome": item["outcome"]}
            for item in row.get("phases", [])
        ]
        results.append(
            {
                "nodeid": row["nodeid"],
                "outcome": row["outcome"],
                "phase_outcomes": phases,
                "suite_memberships": memberships,
                "gates_current_release": any(
                    item["gates_current_release"] for item in memberships
                ),
                "stdout": stdout.as_dict(),
                "stderr": stderr.as_dict(),
                "detail": detail.as_dict(),
            }
        )
    return sorted(results, key=lambda item: str(item["nodeid"]))


_BOOTSTRAP = r"""
import importlib.util
import json
import os
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
plugin_path = root / sys.argv[2]
test_paths = json.loads(sys.argv[3])
site_paths = json.loads(sys.argv[4])
for value in reversed(site_paths):
    sys.path.insert(0, value)
sys.path.insert(0, str(root / "src"))
sys.path.insert(0, str(root))
import pytest
spec = importlib.util.spec_from_file_location("fin_ia_hermetic_capture_plugin", plugin_path)
if spec is None or spec.loader is None:
    raise RuntimeError("capture plugin cannot be loaded")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)
args = [*test_paths, "-p", "no:terminal", "--capture=fd"]
raise SystemExit(pytest.main(args, plugins=[plugin]))
"""


def run_disposable_once(
    *,
    run_id: str,
    package_root: Path,
    package_manifest: Mapping[str, Any],
    manifest: Mapping[str, Any],
    store: ContentAddressedStore,
    disposable_parent: Path,
) -> dict[str, Any]:
    runtime_root = disposable_parent / f"runtime_{run_id}"
    _materialize_package(package_root, package_manifest, runtime_root)
    raw_capture = runtime_root / ".hermetic" / "raw_capture.json"
    raw_capture.parent.mkdir(parents=True, exist_ok=True)
    plugin_path = manifest["hermetic_package_policy"]["capture_plugin_path"]
    env = os.environ.copy()
    for name in _CREDENTIAL_ENV_NAMES:
        env.pop(name, None)
    env.pop("PYTEST_ADDOPTS", None)
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["FIN_0_1_2_HERMETIC_CAPTURE_PATH"] = str(raw_capture)
    command = [
        sys.executable,
        "-I",
        "-c",
        _BOOTSTRAP,
        str(runtime_root),
        str(plugin_path),
        json.dumps(list(_selected_test_paths(manifest))),
        json.dumps(package_manifest["python_environment"]["site_paths"]),
    ]
    completed = subprocess.run(
        command,
        cwd=runtime_root,
        env=env,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    process_stdout = store.put_bytes(completed.stdout)
    process_stderr = store.put_bytes(completed.stderr)
    if not raw_capture.is_file():
        raise HermeticTestRunnerError("hermetic_pytest_capture_not_materialized")
    raw = _load_json(raw_capture)
    tests = _objectize_raw_capture(raw=raw, manifest=manifest, store=store)
    collection_errors = raw.get("collection_errors", [])
    collection_ref = store.put_bytes(
        json.dumps(collection_errors, ensure_ascii=False, sort_keys=True).encode("utf-8")
    )
    counts = Counter(str(row["outcome"]) for row in tests)
    gating_failures = [
        row
        for row in tests
        if row["gates_current_release"] and row["outcome"] != "passed"
    ]
    historical_findings = [
        row
        for row in tests
        if not row["gates_current_release"] and row["outcome"] != "passed"
    ]
    current_gate_all_green = not gating_failures and not collection_errors
    status = (
        "pass_current_gate_all_green"
        if current_gate_all_green and not historical_findings
        else "pass_current_gate_with_historical_findings"
        if current_gate_all_green
        else "failed_current_gate"
    )
    result = {
        "schema_version": TERMINAL_SCHEMA,
        "run_id": run_id,
        "status": status,
        "pytest_exit_code": int(completed.returncode),
        "captured_session_exit_code": int(raw["session_exit_code"]),
        "selected_test_paths": list(_selected_test_paths(manifest)),
        "test_counts": dict(sorted(counts.items())),
        "tests": tests,
        "collection_errors": collection_errors,
        "collection_errors_ref": collection_ref.as_dict(),
        "process_stdout": process_stdout.as_dict(),
        "process_stderr": process_stderr.as_dict(),
        "current_gate_all_green": current_gate_all_green,
        "gating_failure_nodeids": [row["nodeid"] for row in gating_failures],
        "historical_finding_nodeids": [row["nodeid"] for row in historical_findings],
        "credential_environment_removed": sorted(_CREDENTIAL_ENV_NAMES),
        "semantic_normalization_roots": {
            "exact_disposable_repository_root": str(runtime_root.resolve()),
            "exact_disposable_package_root": str(package_root.resolve()),
            "exact_hermetic_temporary_parent": str(disposable_parent.resolve()),
        },
    }
    _write_json(package_root / "runs" / run_id / "terminal_result.json", result)
    return result


def _raw_parity_projection(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": result["status"],
        "pytest_exit_code": result["pytest_exit_code"],
        "captured_session_exit_code": result["captured_session_exit_code"],
        "selected_test_paths": result["selected_test_paths"],
        "test_counts": result["test_counts"],
        "tests": [
            {
                "nodeid": row["nodeid"],
                "outcome": row["outcome"],
                "phase_outcomes": row["phase_outcomes"],
                "suite_memberships": row["suite_memberships"],
                "gates_current_release": row["gates_current_release"],
                "stdout_sha256": row["stdout"]["sha256"],
                "stderr_sha256": row["stderr"]["sha256"],
                "detail_sha256": row["detail"]["sha256"],
            }
            for row in result["tests"]
        ],
        "collection_errors_sha256": result["collection_errors_ref"]["sha256"],
        "process_stdout_sha256": result["process_stdout"]["sha256"],
        "process_stderr_sha256": result["process_stderr"]["sha256"],
        "current_gate_all_green": result["current_gate_all_green"],
        "gating_failure_nodeids": result["gating_failure_nodeids"],
        "historical_finding_nodeids": result["historical_finding_nodeids"],
    }


def _load_semantic_parity_contract(
    repository_root: Path,
    manifest: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, str | None, str | None]:
    policy = manifest["hermetic_package_policy"]
    contract_ref = policy.get("semantic_parity_contract_ref")
    if contract_ref is None:
        return None, None, None
    if not isinstance(contract_ref, str) or not contract_ref.strip():
        raise HermeticTestRunnerError("semantic_parity_contract_ref_invalid")
    relative = _safe_relative_path(repository_root, contract_ref)
    contract = _load_json(repository_root / relative)
    if set(contract) != {
        "schema_version",
        "contract_id",
        "status",
        "raw_evidence",
        "normalization",
        "semantic_projection",
    }:
        raise HermeticTestRunnerError("semantic_parity_contract_top_level_invalid")
    if contract["schema_version"] != SEMANTIC_PARITY_SCHEMA:
        raise HermeticTestRunnerError("semantic_parity_contract_schema_invalid")
    if contract["status"] != "raw_preserving_allowlisted_root_normalization":
        raise HermeticTestRunnerError("semantic_parity_contract_status_invalid")
    raw_evidence = contract["raw_evidence"]
    if not isinstance(raw_evidence, Mapping) or any(
        raw_evidence.get(key) is not expected
        for key, expected in {
            "content_addressed_refs_retained": True,
            "raw_detail_stdout_stderr_hashes_rewritten": False,
            "raw_terminal_result_retained": True,
            "semantic_hash_is_separate_index_only": True,
        }.items()
    ):
        raise HermeticTestRunnerError(
            "semantic_parity_raw_evidence_contract_invalid"
        )
    normalization = contract["normalization"]
    if not isinstance(normalization, Mapping):
        raise HermeticTestRunnerError("semantic_parity_normalization_invalid")
    expected_roots = [
        {
            "root_id": "exact_disposable_repository_root",
            "placeholder": "<DISPOSABLE_REPOSITORY_ROOT>",
        },
        {
            "root_id": "exact_disposable_package_root",
            "placeholder": "<DISPOSABLE_PACKAGE_ROOT>",
        },
        {
            "root_id": "exact_hermetic_temporary_parent",
            "placeholder": "<HERMETIC_TEMPORARY_PARENT>",
        },
    ]
    if normalization.get("allowed_roots") != expected_roots:
        raise HermeticTestRunnerError(
            "semantic_parity_allowed_roots_invalid"
        )
    for key, expected in {
        "derive_native_and_posix_separator_variants_from_exact_roots": True,
        "replace_longest_exact_literal_first": True,
        "substring_or_fuzzy_path_matching_allowed": False,
        "unknown_absolute_path_behavior": "fail_closed_and_keep_parity_false",
    }.items():
        if normalization.get(key) != expected:
            raise HermeticTestRunnerError(
                "semantic_parity_normalization_rule_invalid"
            )
    patterns = normalization.get("unknown_absolute_path_patterns")
    if not isinstance(patterns, list) or len(patterns) != 2:
        raise HermeticTestRunnerError(
            "semantic_parity_absolute_path_patterns_invalid"
        )
    try:
        for pattern in patterns:
            re.compile(str(pattern))
    except re.error as exc:
        raise HermeticTestRunnerError(
            "semantic_parity_absolute_path_pattern_compile_failed"
        ) from exc
    projection = contract["semantic_projection"]
    if not isinstance(projection, Mapping):
        raise HermeticTestRunnerError("semantic_parity_projection_invalid")
    significant = set(projection.get("comparison_significant_fields", []))
    if not {
        "business_values",
        "nodeids",
        "failure_codes",
        "relative_paths",
        "non_allowlisted_absolute_paths",
    }.issubset(significant):
        raise HermeticTestRunnerError(
            "semantic_parity_comparison_significance_incomplete"
        )
    if (
        projection.get(
            "semantic_parity_requires_both_normalization_valid_and_digest_equal"
        )
        is not True
        or projection.get("normalization_findings_are_business_promotable")
        is not False
    ):
        raise HermeticTestRunnerError(
            "semantic_parity_projection_gate_invalid"
        )
    return (
        contract,
        relative.as_posix(),
        _sha256_bytes(_canonical_bytes(contract)),
    )


def _semantic_text_projection(
    value: bytes,
    *,
    roots: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        normalized = value.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HermeticTestRunnerError(
            "semantic_parity_content_not_utf8"
        ) from exc
    allowed_rows = contract["normalization"]["allowed_roots"]
    expected_root_ids = {str(row["root_id"]) for row in allowed_rows}
    if set(roots) != expected_root_ids:
        raise HermeticTestRunnerError(
            "semantic_parity_runtime_roots_incomplete"
        )
    replacements: list[tuple[str, str]] = []
    for row in allowed_rows:
        root_id = str(row["root_id"])
        placeholder = str(row["placeholder"])
        root = str(roots[root_id]).strip()
        if not root:
            raise HermeticTestRunnerError(
                "semantic_parity_runtime_root_empty"
            )
        variants = {root, root.replace("\\", "/"), root.replace("/", "\\")}
        replacements.extend(
            (variant, placeholder)
            for variant in variants
            if variant
        )
    for literal, placeholder in sorted(
        set(replacements),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        normalized = normalized.replace(literal, placeholder)
    unknown_paths: set[str] = set()
    for pattern in contract["normalization"]["unknown_absolute_path_patterns"]:
        unknown_paths.update(
            match.group(0)
            for match in re.finditer(str(pattern), normalized)
        )
    normalized_bytes = normalized.encode("utf-8")
    return {
        "semantic_sha256": _sha256_bytes(normalized_bytes),
        "semantic_bytes": len(normalized_bytes),
        "normalization_valid": not unknown_paths,
        "unknown_absolute_path_count": len(unknown_paths),
        "unknown_absolute_path_digests": sorted(
            _sha256_bytes(path.encode("utf-8"))
            for path in unknown_paths
        ),
    }


def _semantic_ref_projection(
    package_root: Path,
    ref: Mapping[str, Any],
    *,
    roots: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    return _semantic_text_projection(
        read_object(package_root, ref),
        roots=roots,
        contract=contract,
    )


def _semantic_parity_projection(
    result: Mapping[str, Any],
    *,
    package_root: Path,
    contract: Mapping[str, Any],
    contract_digest: str,
) -> dict[str, Any]:
    roots = result["semantic_normalization_roots"]
    normalized_rows: list[dict[str, Any]] = []
    all_content: list[dict[str, Any]] = []
    for row in result["tests"]:
        stdout = _semantic_ref_projection(
            package_root,
            row["stdout"],
            roots=roots,
            contract=contract,
        )
        stderr = _semantic_ref_projection(
            package_root,
            row["stderr"],
            roots=roots,
            contract=contract,
        )
        detail = _semantic_ref_projection(
            package_root,
            row["detail"],
            roots=roots,
            contract=contract,
        )
        all_content.extend((stdout, stderr, detail))
        normalized_rows.append(
            {
                "nodeid": row["nodeid"],
                "outcome": row["outcome"],
                "phase_outcomes": row["phase_outcomes"],
                "suite_memberships": row["suite_memberships"],
                "gates_current_release": row["gates_current_release"],
                "stdout_semantic_sha256": stdout["semantic_sha256"],
                "stderr_semantic_sha256": stderr["semantic_sha256"],
                "detail_semantic_sha256": detail["semantic_sha256"],
            }
        )
    collection_errors = _semantic_ref_projection(
        package_root,
        result["collection_errors_ref"],
        roots=roots,
        contract=contract,
    )
    process_stdout = _semantic_ref_projection(
        package_root,
        result["process_stdout"],
        roots=roots,
        contract=contract,
    )
    process_stderr = _semantic_ref_projection(
        package_root,
        result["process_stderr"],
        roots=roots,
        contract=contract,
    )
    all_content.extend((collection_errors, process_stdout, process_stderr))
    unknown_digests = sorted(
        {
            digest
            for projection in all_content
            for digest in projection["unknown_absolute_path_digests"]
        }
    )
    return {
        "semantic_parity_contract_digest": contract_digest,
        "status": result["status"],
        "pytest_exit_code": result["pytest_exit_code"],
        "captured_session_exit_code": result["captured_session_exit_code"],
        "selected_test_paths": result["selected_test_paths"],
        "test_counts": result["test_counts"],
        "tests": normalized_rows,
        "collection_errors_semantic_sha256": collection_errors[
            "semantic_sha256"
        ],
        "process_stdout_semantic_sha256": process_stdout[
            "semantic_sha256"
        ],
        "process_stderr_semantic_sha256": process_stderr[
            "semantic_sha256"
        ],
        "current_gate_all_green": result["current_gate_all_green"],
        "gating_failure_nodeids": result["gating_failure_nodeids"],
        "historical_finding_nodeids": result["historical_finding_nodeids"],
        "normalization_valid": all(
            projection["normalization_valid"]
            for projection in all_content
        ),
        "unknown_absolute_path_count": sum(
            int(projection["unknown_absolute_path_count"])
            for projection in all_content
        ),
        "unknown_absolute_path_digests": unknown_digests,
    }


def run_hermetic_active_suite(
    *,
    repository_root: Path,
    manifest_path: Path,
    output_root: Path,
    repository_paths: Sequence[Path] | None = None,
) -> dict[str, Any]:
    repository_root = repository_root.resolve()
    output_root = output_root.resolve()
    if output_root.exists():
        raise HermeticTestRunnerError("hermetic_output_root_already_exists")
    manifest = _load_json(manifest_path)
    try:
        validate_active_test_suite_manifest(manifest)
    except ContractGovernanceError as exc:
        raise HermeticTestRunnerError(f"hermetic_manifest_invalid:{exc.code}") from exc
    (
        semantic_contract,
        semantic_contract_ref,
        semantic_contract_digest,
    ) = _load_semantic_parity_contract(repository_root, manifest)
    staging = output_root.with_name(output_root.name + ".partial")
    if staging.exists():
        raise HermeticTestRunnerError("hermetic_output_staging_root_already_exists")
    staging.mkdir(parents=True)
    try:
        package_manifest = build_content_addressed_package(
            repository_root=repository_root,
            manifest=manifest,
            package_root=staging,
            repository_paths=repository_paths,
        )
        store = ContentAddressedStore(staging)
        with tempfile.TemporaryDirectory(prefix="fin_0_1_2_hermetic_active_suite_") as temporary:
            disposable_parent = Path(temporary)
            run_a = run_disposable_once(
                run_id="disposable_a",
                package_root=staging,
                package_manifest=package_manifest,
                manifest=manifest,
                store=store,
                disposable_parent=disposable_parent,
            )
            run_b = run_disposable_once(
                run_id="disposable_b",
                package_root=staging,
                package_manifest=package_manifest,
                manifest=manifest,
                store=store,
                disposable_parent=disposable_parent,
            )
        raw_projection_a = _raw_parity_projection(run_a)
        raw_projection_b = _raw_parity_projection(run_b)
        raw_parity_a = _sha256_bytes(_canonical_bytes(raw_projection_a))
        raw_parity_b = _sha256_bytes(_canonical_bytes(raw_projection_b))
        raw_parity = raw_parity_a == raw_parity_b
        if semantic_contract is None:
            projection_a = raw_projection_a
            projection_b = raw_projection_b
            normalization_valid_a = True
            normalization_valid_b = True
            unknown_absolute_path_count = [0, 0]
        else:
            assert semantic_contract_digest is not None
            projection_a = _semantic_parity_projection(
                run_a,
                package_root=staging,
                contract=semantic_contract,
                contract_digest=semantic_contract_digest,
            )
            projection_b = _semantic_parity_projection(
                run_b,
                package_root=staging,
                contract=semantic_contract,
                contract_digest=semantic_contract_digest,
            )
            normalization_valid_a = bool(
                projection_a["normalization_valid"]
            )
            normalization_valid_b = bool(
                projection_b["normalization_valid"]
            )
            unknown_absolute_path_count = [
                int(projection_a["unknown_absolute_path_count"]),
                int(projection_b["unknown_absolute_path_count"]),
            ]
        semantic_projection_refs: list[str] = []
        semantic_projection_sha256: list[str] = []
        if semantic_contract is not None:
            for run_id, projection in (
                ("disposable_a", projection_a),
                ("disposable_b", projection_b),
            ):
                relative = Path("runs") / run_id / (
                    "semantic_parity_projection.json"
                )
                _write_json(staging / relative, projection)
                semantic_projection_refs.append(relative.as_posix())
                semantic_projection_sha256.append(
                    _sha256_file(staging / relative)
                )
        parity_a = _sha256_bytes(_canonical_bytes(projection_a))
        parity_b = _sha256_bytes(_canonical_bytes(projection_b))
        parity = (
            normalization_valid_a
            and normalization_valid_b
            and parity_a == parity_b
        )
        repository_readback = [
            {
                "path": row["path"],
                "sha256": _sha256_file(repository_root / row["path"]),
            }
            for row in package_manifest["repository_files"]
        ]
        repository_unchanged = all(
            row["sha256"] == package_manifest["repository_files"][index]["sha256"]
            for index, row in enumerate(repository_readback)
        )
        passed = (
            parity
            and repository_unchanged
            and bool(run_a["current_gate_all_green"])
            and bool(run_b["current_gate_all_green"])
        )
        verification = {
            "schema_version": VERIFICATION_SCHEMA,
            "status": "pass" if passed else "failed",
            "package_manifest_ref": "package_manifest.json",
            "package_manifest_sha256": _sha256_file(staging / "package_manifest.json"),
            "package_semantic_digest": package_manifest["semantic_digest"],
            "repository_file_count": len(package_manifest["repository_files"]),
            "external_dependency_count": len(package_manifest["external_read_only_dependencies"]),
            "disposable_runtime_count": 2,
            "disposable_parity": parity,
            "raw_disposable_parity": raw_parity,
            "parity_digest_a": parity_a,
            "parity_digest_b": parity_b,
            "raw_parity_digest_a": raw_parity_a,
            "raw_parity_digest_b": raw_parity_b,
            "semantic_parity_contract_ref": semantic_contract_ref,
            "semantic_parity_contract_digest": semantic_contract_digest,
            "semantic_normalization_valid": [
                normalization_valid_a,
                normalization_valid_b,
            ],
            "semantic_unknown_absolute_path_count": (
                unknown_absolute_path_count
            ),
            "semantic_projection_refs": semantic_projection_refs,
            "semantic_projection_sha256": semantic_projection_sha256,
            "repository_unchanged_during_run": repository_unchanged,
            "current_active_suite_all_green": bool(
                run_a["current_gate_all_green"]
                and run_b["current_gate_all_green"]
            ),
            "test_counts": run_a["test_counts"],
            "historical_finding_nodeids": run_a["historical_finding_nodeids"],
            "complete_per_test_stdout_stderr_content_addressed": True,
            "process_stdout_stderr_content_addressed": True,
            "failed_output_business_promotable": False,
            "credential_environment_removed": sorted(_CREDENTIAL_ENV_NAMES),
        }
        _write_json(staging / "verification.json", verification)
        staging.replace(output_root)
        return {**verification, "output_root": output_root.as_posix()}
    except BaseException:
        # Preserve a failed package for audit.  It is new output and is never
        # promoted as a passing package.
        failure_root = output_root.with_name(output_root.name + ".failed")
        if not failure_root.exists() and staging.exists():
            staging.replace(failure_root)
        raise


def read_object(package_root: Path, ref: Mapping[str, Any]) -> bytes:
    path = package_root / str(ref["ref"])
    value = path.read_bytes()
    if len(value) != ref["bytes"] or _sha256_bytes(value) != ref["sha256"]:
        raise HermeticTestRunnerError("hermetic_object_readback_mismatch")
    return value
