from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sec_agent.hermetic_test_runner import (  # noqa: E402
    CompiledRepositoryInventory,
    compile_repository_inventory,
)
from sec_agent.runtime_contract_governance import (  # noqa: E402
    validate_active_test_suite_manifest,
)


EXECUTION_SCHEMA = "fin_ia_0_1_3_s0_t03_host_zero_call_proof_execution_v1_0"
VERIFICATION_SCHEMA = (
    "fin_ia_0_1_3_s0_t03_host_zero_call_engineering_proof_verification_v1_0"
)
RAW_CAPTURE_SCHEMA = "fin_ia_pytest_raw_capture_v1_0"
EXPECTED_SCOPE = (
    "FIN-0.1.3-S0-HOST-IMPORT-COLLECT-RESOURCE-MUTATION-AND-THREE-CASE-"
    "FULL-FAKE-ZERO-CALL-PROOF"
)
DEFAULT_EXECUTION_MANIFEST = ROOT / (
    "configs/releases/fin_ia_0_1_3_s0_t03_host_zero_call_engineering_"
    "proof_execution_manifest_v1_0.json"
)
CREDENTIAL_ENV_NAMES = frozenset(
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


class HostProofError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise HostProofError(f"duplicate_json_key:{key}")
        result[key] = value
    return result


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_strict_object,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HostProofError(f"json_read_failed:{path.as_posix()}") from exc
    if not isinstance(value, dict):
        raise HostProofError(f"json_object_required:{path.as_posix()}")
    return value


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
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


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


class ObjectStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def put(self, value: bytes) -> dict[str, Any]:
        digest = _sha256_bytes(value)
        relative = Path("objects") / "sha256" / digest[:2] / digest
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if target.read_bytes() != value:
                raise HostProofError("content_addressed_object_collision")
        else:
            temporary = target.with_suffix(".tmp")
            temporary.write_bytes(value)
            temporary.replace(target)
        return {
            "sha256": digest,
            "bytes": len(value),
            "ref": relative.as_posix(),
        }

    def put_json(self, value: Any) -> dict[str, Any]:
        return self.put(_canonical_bytes(value))

    def assert_readback(self, ref: Mapping[str, Any]) -> None:
        path = self.root / str(ref["ref"])
        value = path.read_bytes()
        if len(value) != int(ref["bytes"]):
            raise HostProofError("content_addressed_object_bytes_mismatch")
        if _sha256_bytes(value) != str(ref["sha256"]):
            raise HostProofError("content_addressed_object_digest_mismatch")


def _run(
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        list(command),
        cwd=cwd,
        env=None if env is None else dict(env),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _git(*args: str) -> bytes:
    completed = _run(["git", *args], cwd=ROOT)
    if completed.returncode != 0:
        raise HostProofError(f"git_command_failed:{args[0]}")
    return completed.stdout


def _git_state() -> dict[str, Any]:
    head = _git("rev-parse", "HEAD").decode("ascii").strip()
    branch = _git("branch", "--show-current").decode("utf-8").strip()
    upstream = _git("rev-parse", "@{upstream}").decode("ascii").strip()
    status = _git("status", "--porcelain=v1", "-z")
    return {
        "head": head,
        "branch": branch,
        "upstream_head": upstream,
        "clean": not status,
        "synced": head == upstream,
        "status_sha256": _sha256_bytes(status),
        "status_bytes": len(status),
    }


def _tracked_snapshot(store: ObjectStore | None = None) -> dict[str, Any]:
    raw = _git("ls-files", "-z")
    paths = sorted(
        item.decode("utf-8").replace("\\", "/")
        for item in raw.split(b"\0")
        if item
    )
    rows = []
    for value in paths:
        path = ROOT / value
        if not path.is_file():
            raise HostProofError(f"tracked_path_not_regular_file:{value}")
        rows.append(
            {
                "path": value,
                "bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    payload = {
        "schema_version": "fin_ia_tracked_repository_readback_v1_0",
        "file_count": len(rows),
        "rows": rows,
    }
    result = {
        "file_count": len(rows),
        "canonical_sha256": _sha256_bytes(_canonical_bytes(payload)),
    }
    if store is not None:
        result["content_ref"] = store.put_json(payload)
    return result


def _selected_test_paths(manifest: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                str(path).replace("\\", "/")
                for suite in manifest["suites"]
                if suite["selected"]
                for path in suite["test_paths"]
            }
        )
    )


def _module_name_from_path(path: Path, base: Path, prefix: tuple[str, ...]) -> str | None:
    relative = path.relative_to(base)
    parts = list(relative.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    full = [*prefix, *parts]
    if not full or not all(part.isidentifier() for part in full):
        return None
    return ".".join(full)


def _discover_importable_modules() -> tuple[tuple[str, ...], tuple[str, ...]]:
    modules: dict[str, str] = {}
    excluded: list[str] = []
    surfaces = (
        (ROOT / "src", tuple()),
        (ROOT / "apps" / "workbench" / "backend", ("apps", "workbench", "backend")),
    )
    for base, prefix in surfaces:
        for path in sorted(base.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            module = _module_name_from_path(path, base, prefix)
            repo_path = path.relative_to(ROOT).as_posix()
            if module is None:
                excluded.append(repo_path)
                continue
            if module in modules and modules[module] != repo_path:
                raise HostProofError(f"duplicate_import_module:{module}")
            modules[module] = repo_path
    return tuple(sorted(modules)), tuple(sorted(excluded))


def _proof_env(network_marker: Path) -> dict[str, str]:
    env = os.environ.copy()
    for name in CREDENTIAL_ENV_NAMES:
        env.pop(name, None)
    env.pop("PYTEST_ADDOPTS", None)
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONHASHSEED"] = "0"
    env["NO_COLOR"] = "1"
    env["FIN_IA_ZERO_CALL_NETWORK_MARKER"] = str(network_marker)
    return env


_NETWORK_GUARD = r"""
import os
from pathlib import Path
import socket

marker = Path(os.environ["FIN_IA_ZERO_CALL_NETWORK_MARKER"])

def _blocked(*args, **kwargs):
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("blocked_socket_attempt\n", encoding="utf-8")
    raise RuntimeError("fin_ia_zero_call_network_attempt_blocked")

socket.socket.connect = _blocked
socket.socket.connect_ex = _blocked
socket.create_connection = _blocked
"""


_IMPORT_BOOTSTRAP = _NETWORK_GUARD + r"""
import contextlib
import importlib
import io
import json
import sys
import traceback

root = Path(sys.argv[1]).resolve()
modules = json.loads(sys.argv[2])
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "src"))
rows = []
for module_name in modules:
    stdout = io.StringIO()
    stderr = io.StringIO()
    detail = ""
    status = "pass"
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            importlib.import_module(module_name)
    except BaseException:
        status = "failed"
        detail = traceback.format_exc()
    rows.append({
        "module": module_name,
        "status": status,
        "stdout": stdout.getvalue(),
        "stderr": stderr.getvalue(),
        "detail": detail,
    })
failures = [row["module"] for row in rows if row["status"] != "pass"]
print(json.dumps({
    "schema_version": "fin_ia_application_import_sweep_v1_0",
    "module_count": len(rows),
    "failure_count": len(failures),
    "failure_modules": failures,
    "rows": rows,
}, ensure_ascii=False, sort_keys=True))
raise SystemExit(0 if not failures else 1)
"""


_COLLECT_BOOTSTRAP = _NETWORK_GUARD + r"""
import json
import sys

root = Path(sys.argv[1]).resolve()
test_paths = json.loads(sys.argv[2])
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "src"))
import pytest
args = [*test_paths, "--collect-only", "-q", "-p", "no:cacheprovider"]
raise SystemExit(pytest.main(args))
"""


_PYTEST_BOOTSTRAP = _NETWORK_GUARD + r"""
import importlib.util
import json
import sys

root = Path(sys.argv[1]).resolve()
plugin_path = root / sys.argv[2]
test_paths = json.loads(sys.argv[3])
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "src"))
import pytest
spec = importlib.util.spec_from_file_location(
    "fin_ia_t03_host_capture_plugin",
    plugin_path,
)
if spec is None or spec.loader is None:
    raise RuntimeError("capture_plugin_cannot_be_loaded")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)
args = [
    *test_paths,
    "-p", "no:terminal",
    "-p", "no:cacheprovider",
    "--capture=fd",
]
raise SystemExit(pytest.main(args, plugins=[plugin]))
"""


def _process_record(
    *,
    process_id: str,
    completed: subprocess.CompletedProcess[bytes],
    store: ObjectStore,
    elapsed_seconds: float,
) -> dict[str, Any]:
    return {
        "process_id": process_id,
        "exit_code": int(completed.returncode),
        "elapsed_seconds": round(elapsed_seconds, 6),
        "stdout": store.put(completed.stdout),
        "stderr": store.put(completed.stderr),
    }


def _execute_process(
    *,
    process_id: str,
    command: Sequence[str],
    env: Mapping[str, str],
    store: ObjectStore,
) -> tuple[subprocess.CompletedProcess[bytes], dict[str, Any]]:
    started = time.monotonic()
    completed = _run(command, cwd=ROOT, env=env)
    elapsed = time.monotonic() - started
    return completed, _process_record(
        process_id=process_id,
        completed=completed,
        store=store,
        elapsed_seconds=elapsed,
    )


def _objectize_import_sweep(
    raw: Mapping[str, Any], store: ObjectStore
) -> dict[str, Any]:
    if raw.get("schema_version") != "fin_ia_application_import_sweep_v1_0":
        raise HostProofError("application_import_sweep_schema_invalid")
    rows = raw.get("rows")
    if not isinstance(rows, list):
        raise HostProofError("application_import_sweep_rows_invalid")
    objectized = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise HostProofError("application_import_sweep_row_invalid")
        objectized.append(
            {
                "module": str(row["module"]),
                "status": str(row["status"]),
                "stdout": store.put(str(row.get("stdout", "")).encode("utf-8")),
                "stderr": store.put(str(row.get("stderr", "")).encode("utf-8")),
                "detail": store.put(str(row.get("detail", "")).encode("utf-8")),
            }
        )
    failures = [row["module"] for row in objectized if row["status"] != "pass"]
    return {
        "module_count": len(objectized),
        "failure_count": len(failures),
        "failure_modules": failures,
        "rows": objectized,
    }


def _memberships(manifest: Mapping[str, Any], nodeid: str) -> list[dict[str, Any]]:
    path = nodeid.split("::", 1)[0].replace("\\", "/")
    rows = []
    for suite in manifest["suites"]:
        if not suite["selected"]:
            continue
        paths = {str(item).replace("\\", "/") for item in suite["test_paths"]}
        if path in paths:
            rows.append(
                {
                    "suite_id": suite["suite_id"],
                    "proof_class": suite["proof_class"],
                    "gates_current_release": bool(suite["gates_current_release"]),
                }
            )
    if not rows:
        raise HostProofError(f"test_without_manifest_membership:{nodeid}")
    return rows


def _terminal_outcome(phases: Sequence[Mapping[str, Any]]) -> str:
    if any(str(row["outcome"]) == "failed" for row in phases):
        return "failed"
    if any(
        str(row["phase"]) == "call" and str(row["outcome"]) == "passed"
        for row in phases
    ):
        return "passed"
    if any(str(row["outcome"]) == "skipped" for row in phases):
        return "skipped"
    return "incomplete"


def _objectize_pytest_capture(
    *,
    raw: Mapping[str, Any],
    manifest: Mapping[str, Any],
    store: ObjectStore,
) -> dict[str, Any]:
    if raw.get("schema_version") != RAW_CAPTURE_SCHEMA:
        raise HostProofError("pytest_raw_capture_schema_invalid")
    raw_rows = raw.get("tests")
    if not isinstance(raw_rows, list):
        raise HostProofError("pytest_raw_capture_rows_invalid")
    tests = []
    for raw_row in raw_rows:
        if not isinstance(raw_row, Mapping):
            raise HostProofError("pytest_raw_capture_row_invalid")
        phases = [
            {
                "phase": str(row["phase"]),
                "outcome": str(row["outcome"]),
                "duration_seconds": float(row.get("duration_seconds", 0.0)),
            }
            for row in raw_row.get("phases", [])
            if isinstance(row, Mapping)
        ]
        nodeid = str(raw_row["nodeid"])
        memberships = _memberships(manifest, nodeid)
        tests.append(
            {
                "nodeid": nodeid,
                "outcome": _terminal_outcome(phases),
                "phase_outcomes": phases,
                "suite_memberships": memberships,
                "gates_current_release": any(
                    row["gates_current_release"] for row in memberships
                ),
                "stdout": store.put(str(raw_row.get("stdout", "")).encode("utf-8")),
                "stderr": store.put(str(raw_row.get("stderr", "")).encode("utf-8")),
                "detail": store.put(str(raw_row.get("detail", "")).encode("utf-8")),
            }
        )
    tests.sort(key=lambda row: row["nodeid"])
    collection_errors = raw.get("collection_errors", [])
    if not isinstance(collection_errors, list):
        raise HostProofError("pytest_collection_errors_invalid")
    objectized_collection_errors = []
    for row in collection_errors:
        if not isinstance(row, Mapping):
            raise HostProofError("pytest_collection_error_row_invalid")
        objectized_collection_errors.append(
            {
                "nodeid": str(row.get("nodeid", "collection")),
                "detail": store.put(str(row.get("detail", "")).encode("utf-8")),
            }
        )
    return {
        "session_exit_code": int(raw["session_exit_code"]),
        "tests": tests,
        "test_counts": dict(sorted(Counter(row["outcome"] for row in tests).items())),
        "collection_errors": objectized_collection_errors,
    }


def _parse_collect_nodeids(stdout: bytes) -> list[str]:
    text = stdout.decode("utf-8", errors="replace")
    return sorted(
        {
            line.strip().replace("\\", "/")
            for line in text.splitlines()
            if "::" in line and not line.lstrip().startswith(("<", "="))
        }
    )


def _validate_execution_manifest(
    manifest: Mapping[str, Any], manifest_path: Path
) -> tuple[dict[str, Any], Path]:
    required = {
        "schema_version",
        "execution_id",
        "status",
        "run_scope",
        "authority",
        "source_bindings",
        "active_suite_manifest_ref",
        "capture_plugin_ref",
        "required_matrix",
        "required_passed_nodeid_fragments",
        "budgets",
        "promotion_boundary",
    }
    if set(manifest) != required:
        raise HostProofError("execution_manifest_top_level_invalid")
    if manifest["schema_version"] != EXECUTION_SCHEMA:
        raise HostProofError("execution_manifest_schema_invalid")
    if manifest["status"] != "ready_unexecuted":
        raise HostProofError("execution_manifest_status_invalid")
    if manifest["run_scope"] != EXPECTED_SCOPE:
        raise HostProofError("execution_manifest_scope_invalid")
    authority = manifest["authority"]
    if not isinstance(authority, Mapping) or authority.get("T03_engineering_proof_authorized") is not True:
        raise HostProofError("execution_manifest_authority_invalid")
    budgets = manifest["budgets"]
    if not isinstance(budgets, Mapping) or any(
        budgets.get(key) != value
        for key, value in {
            "engineering_proof_runs_maximum": 1,
            "engineering_proof_runs_consumed_before_execution": 0,
            "formal_two_disposable_packages_created_or_executed": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "credential_reads_or_probes": 0,
            "business_network_or_source_calls": 0,
            "new_admissions": 0,
            "business_runs": 0,
            "business_artifacts": 0,
        }.items()
    ):
        raise HostProofError("execution_manifest_budget_invalid")
    for binding in manifest["source_bindings"]:
        if not isinstance(binding, Mapping) or set(binding) != {"role", "ref", "sha256"}:
            raise HostProofError("execution_manifest_source_binding_invalid")
        path = ROOT / str(binding["ref"])
        if not path.is_file() or _sha256_file(path) != str(binding["sha256"]):
            raise HostProofError(
                f"execution_manifest_source_binding_drift:{binding.get('role')}"
            )
    active_path = ROOT / str(manifest["active_suite_manifest_ref"])
    active = _load_json(active_path)
    validate_active_test_suite_manifest(active)
    plugin_path = ROOT / str(manifest["capture_plugin_ref"])
    if not plugin_path.is_file():
        raise HostProofError("execution_manifest_capture_plugin_missing")
    if manifest_path.resolve().is_relative_to(ROOT) is False:
        raise HostProofError("execution_manifest_must_be_repository_owned")
    return active, plugin_path


def _project_os_preflight(store: ObjectStore) -> dict[str, Any]:
    command = [
        sys.executable,
        "scripts/eval_multi_agent/run_project_os_full_chain_preflight.py",
        "--project-root",
        ".",
        "--run-scope",
        EXPECTED_SCOPE,
    ]
    completed = _run(command, cwd=ROOT)
    stdout_ref = store.put(completed.stdout)
    stderr_ref = store.put(completed.stderr)
    try:
        payload = json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise HostProofError("project_os_preflight_output_invalid") from exc
    if completed.returncode != 0 or payload.get("status") != "pass":
        raise HostProofError("project_os_preflight_failed")
    if int(payload.get("open_full_chain_blocker_count", -1)) != 0:
        raise HostProofError("project_os_preflight_open_blockers")
    return {
        "exit_code": int(completed.returncode),
        "status": payload["status"],
        "open_full_chain_blocker_count": 0,
        "stdout": stdout_ref,
        "stderr": stderr_ref,
    }


def _inventory_evidence(
    compiled: CompiledRepositoryInventory, store: ObjectStore
) -> dict[str, Any]:
    paths = [path.as_posix() for path in compiled.paths]
    forbidden = [
        value
        for value in paths
        if value == ".git"
        or value.startswith(".git/")
        or value == ".codex_runtime"
        or value.startswith(".codex_runtime/")
    ]
    if forbidden:
        raise HostProofError("compiled_inventory_contains_forbidden_path")
    if compiled.explicit_allowlist_paths:
        raise HostProofError("compiled_inventory_contains_nontracked_allowlist_path")
    payload = {
        "schema_version": "fin_ia_t03_compiled_repository_inventory_v1_0",
        "paths": paths,
        "tracked_paths": list(compiled.tracked_paths),
        "explicit_allowlist_paths": list(compiled.explicit_allowlist_paths),
        "recursive_reference_paths": list(compiled.recursive_reference_paths),
    }
    return {
        **compiled.as_dict(),
        "forbidden_path_count": len(forbidden),
        "ignored_or_untracked_path_count": len(compiled.explicit_allowlist_paths),
        "paths_ref": store.put_json(payload),
    }


def _all_refs(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        if set(value) == {"sha256", "bytes", "ref"}:
            yield value
        else:
            for child in value.values():
                yield from _all_refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from _all_refs(child)


def _execute(
    *,
    execution_manifest_path: Path,
    output_root: Path,
) -> int:
    if output_root.exists() or output_root.with_name(output_root.name + ".partial").exists():
        raise HostProofError("proof_output_root_already_exists")
    if output_root.resolve().is_relative_to(ROOT):
        raise HostProofError("proof_output_root_must_be_outside_repository")

    execution = _load_json(execution_manifest_path)
    active, capture_plugin = _validate_execution_manifest(
        execution,
        execution_manifest_path,
    )
    git_before = _git_state()
    if not git_before["clean"]:
        raise HostProofError("proof_requires_clean_repository")
    if not git_before["synced"]:
        raise HostProofError("proof_requires_synced_upstream")

    staging = output_root.with_name(output_root.name + ".partial")
    staging.mkdir(parents=True)
    store = ObjectStore(staging)
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    errors: list[str] = []
    verification: dict[str, Any] = {
        "schema_version": VERIFICATION_SCHEMA,
        "status": "running",
        "proof_id": execution["execution_id"],
        "run_scope": EXPECTED_SCOPE,
        "started_at_utc": started_at,
        "source": {
            "execution_manifest_ref": execution_manifest_path.relative_to(ROOT).as_posix(),
            "execution_manifest_sha256": _sha256_file(execution_manifest_path),
            "active_suite_manifest_ref": execution["active_suite_manifest_ref"],
            "active_suite_manifest_sha256": _sha256_file(
                ROOT / str(execution["active_suite_manifest_ref"])
            ),
            "git_before": git_before,
        },
        "promotion_boundary": execution["promotion_boundary"],
    }
    _write_json(staging / "execution_started.json", verification)

    try:
        preflight = _project_os_preflight(store)
        tracked_before = _tracked_snapshot(store)
        compiled = compile_repository_inventory(ROOT, active)
        inventory = _inventory_evidence(compiled, store)
        test_paths = _selected_test_paths(active)
        modules, excluded_modules = _discover_importable_modules()

        import_marker = staging / "network_attempt_import.flag"
        import_command = [
            sys.executable,
            "-I",
            "-c",
            _IMPORT_BOOTSTRAP,
            str(ROOT),
            json.dumps(list(modules)),
        ]
        import_completed, import_process = _execute_process(
            process_id="application_import_sweep",
            command=import_command,
            env=_proof_env(import_marker),
            store=store,
        )
        try:
            import_raw = json.loads(import_completed.stdout.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise HostProofError("application_import_sweep_output_invalid") from exc
        imports = _objectize_import_sweep(import_raw, store)
        if import_completed.returncode != 0 or imports["failure_count"] != 0:
            errors.append("application_import_sweep_failed")
        if import_marker.exists():
            errors.append("application_import_sweep_network_attempted")

        collect_marker = staging / "network_attempt_collect.flag"
        collect_command = [
            sys.executable,
            "-I",
            "-c",
            _COLLECT_BOOTSTRAP,
            str(ROOT),
            json.dumps(list(test_paths)),
        ]
        collect_completed, collect_process = _execute_process(
            process_id="active_suite_collect_only",
            command=collect_command,
            env=_proof_env(collect_marker),
            store=store,
        )
        collected_nodeids = _parse_collect_nodeids(collect_completed.stdout)
        if collect_completed.returncode != 0 or not collected_nodeids:
            errors.append("active_suite_collect_only_failed")
        if collect_marker.exists():
            errors.append("active_suite_collect_only_network_attempted")

        run_marker = staging / "network_attempt_pytest.flag"
        raw_capture_path = staging / "raw_pytest_capture.json"
        run_env = _proof_env(run_marker)
        run_env["FIN_0_1_2_HERMETIC_CAPTURE_PATH"] = str(raw_capture_path)
        run_command = [
            sys.executable,
            "-I",
            "-c",
            _PYTEST_BOOTSTRAP,
            str(ROOT),
            capture_plugin.relative_to(ROOT).as_posix(),
            json.dumps(list(test_paths)),
        ]
        run_completed, run_process = _execute_process(
            process_id="active_suite_execute",
            command=run_command,
            env=run_env,
            store=store,
        )
        if not raw_capture_path.is_file():
            raise HostProofError("pytest_raw_capture_not_materialized")
        raw_capture_bytes = raw_capture_path.read_bytes()
        raw_capture_ref = store.put(raw_capture_bytes)
        raw_capture = json.loads(
            raw_capture_bytes.decode("utf-8"),
            object_pairs_hook=_strict_object,
        )
        pytest_result = _objectize_pytest_capture(
            raw=raw_capture,
            manifest=active,
            store=store,
        )
        raw_capture_path.unlink()
        full_nodeids = [row["nodeid"] for row in pytest_result["tests"]]
        if collected_nodeids != full_nodeids:
            errors.append("collect_execute_nodeid_mismatch")
        if run_completed.returncode != 0 or pytest_result["session_exit_code"] != 0:
            errors.append("active_suite_execute_failed")
        if pytest_result["collection_errors"]:
            errors.append("active_suite_execute_collection_error")
        if any(row["outcome"] != "passed" for row in pytest_result["tests"]):
            errors.append("active_suite_not_all_passed")
        if run_marker.exists():
            errors.append("active_suite_execute_network_attempted")

        passed_nodeids = {
            row["nodeid"]
            for row in pytest_result["tests"]
            if row["outcome"] == "passed"
        }
        coverage = {}
        for fragment in execution["required_passed_nodeid_fragments"]:
            matches = sorted(nodeid for nodeid in passed_nodeids if fragment in nodeid)
            coverage[str(fragment)] = matches
            if not matches:
                errors.append(f"required_proof_node_missing:{fragment}")

        tracked_after = _tracked_snapshot(store)
        git_after = _git_state()
        repository_unchanged = (
            tracked_before["canonical_sha256"] == tracked_after["canonical_sha256"]
            and git_before == git_after
        )
        if not repository_unchanged:
            errors.append("repository_changed_during_proof")

        verification.update(
            {
                "status": "pass" if not errors else "failed",
                "completed_at_utc": time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                ),
                "errors": errors,
                "project_os_preflight": preflight,
                "repository_inventory": inventory,
                "application_import_sweep": {
                    **imports,
                    "excluded_nonimportable_python_paths": list(excluded_modules),
                    "process": import_process,
                },
                "active_suite_collect_only": {
                    "selected_test_paths": list(test_paths),
                    "collected_test_count": len(collected_nodeids),
                    "nodeids_ref": store.put_json(collected_nodeids),
                    "process": collect_process,
                },
                "active_suite_execution": {
                    **pytest_result,
                    "raw_capture": raw_capture_ref,
                    "process": run_process,
                    "required_coverage": coverage,
                },
                "network_guard": {
                    "socket_attempts": 0
                    if not any(
                        marker.exists()
                        for marker in (import_marker, collect_marker, run_marker)
                    )
                    else "one_or_more_blocked_attempts",
                    "credential_environment_removed": sorted(CREDENTIAL_ENV_NAMES),
                    "model_calls": 0,
                    "provider_calls": 0,
                    "business_network_or_source_calls": 0,
                    "new_admissions": 0,
                    "business_runs": 0,
                    "business_artifacts": 0,
                },
                "repository_readback": {
                    "before": tracked_before,
                    "after": tracked_after,
                    "git_after": git_after,
                    "unchanged": repository_unchanged,
                },
                "budget": {
                    "engineering_proof_runs_consumed": 1,
                    "formal_two_disposable_packages_created_or_executed": 0,
                },
            }
        )
        for ref in _all_refs(verification):
            store.assert_readback(ref)
        _write_json(staging / "verification.json", verification)
    except BaseException as exc:
        if isinstance(exc, HostProofError):
            code = exc.code
        else:
            code = f"unexpected_{type(exc).__name__}"
        detail_ref = store.put(traceback.format_exc().encode("utf-8"))
        verification.update(
            {
                "status": "failed",
                "completed_at_utc": time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                ),
                "errors": [*errors, code],
                "exception_detail": detail_ref,
                "budget": {
                    "engineering_proof_runs_consumed": 1,
                    "formal_two_disposable_packages_created_or_executed": 0,
                },
            }
        )
        _write_json(staging / "verification.json", verification)

    target = output_root if verification["status"] == "pass" else output_root.with_name(
        output_root.name + ".failed"
    )
    if target.exists():
        raise HostProofError("proof_final_output_root_already_exists")
    staging.replace(target)
    print(json.dumps({
        "status": verification["status"],
        "output_root": target.as_posix(),
        "verification_sha256": _sha256_file(target / "verification.json"),
        "errors": verification.get("errors", []),
    }, ensure_ascii=False, sort_keys=True))
    return 0 if verification["status"] == "pass" else 1


def _validate_only(execution_manifest_path: Path) -> int:
    execution = _load_json(execution_manifest_path)
    active, capture_plugin = _validate_execution_manifest(
        execution,
        execution_manifest_path,
    )
    git_state = _git_state()
    result = {
        "status": "pass" if git_state["clean"] and git_state["synced"] else "failed",
        "run_scope": execution["run_scope"],
        "active_suite_manifest_ref": execution["active_suite_manifest_ref"],
        "selected_test_paths": list(_selected_test_paths(active)),
        "capture_plugin_ref": capture_plugin.relative_to(ROOT).as_posix(),
        "git": git_state,
        "proof_matrix_executed": False,
        "engineering_proof_runs_consumed": 0,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the single FIN 0.1.3 S0-T03 host zero-call engineering proof."
    )
    parser.add_argument(
        "--execution-manifest",
        type=Path,
        default=DEFAULT_EXECUTION_MANIFEST,
    )
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    execution_manifest_path = args.execution_manifest.resolve()
    if args.validate_only:
        if args.output_root is not None:
            raise HostProofError("validate_only_does_not_accept_output_root")
        return _validate_only(execution_manifest_path)
    if args.output_root is None:
        raise HostProofError("output_root_required_for_execution")
    return _execute(
        execution_manifest_path=execution_manifest_path,
        output_root=args.output_root.resolve(),
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HostProofError as exc:
        print(json.dumps({"status": "failed_pre_execution", "error": exc.code}))
        raise SystemExit(2)
