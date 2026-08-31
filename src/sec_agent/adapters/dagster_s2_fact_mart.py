from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from dagster import Definitions, Failure, Field, job, op
from filelock import FileLock, Timeout


BUILDER_MODULE = "scripts.data_retrieval.build_s2_company_financial_fact_mart"
BUILDER_RELATIVE_PATH = Path("scripts/data_retrieval/build_s2_company_financial_fact_mart.py")
DEFAULT_TIMEOUT_SECONDS = 900
MAX_TIMEOUT_SECONDS = 900
CHILD_ENV_ALLOWLIST = frozenset(
    {
        "COMSPEC",
        "HOME",
        "LANG",
        "LC_ALL",
        "LOCALAPPDATA",
        "PATH",
        "PATHEXT",
        "PYTHONHOME",
        "PYTHONIOENCODING",
        "PYTHONPATH",
        "PYTHONUTF8",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "TZ",
        "USERPROFILE",
        "VIRTUAL_ENV",
        "WINDIR",
    }
)
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_child_environment() -> dict[str, str]:
    """Pass only interpreter/runtime settings; the local builder needs no secrets."""

    return {key: value for key, value in os.environ.items() if key in CHILD_ENV_ALLOWLIST}


def resolve_repository_root() -> Path:
    configured = os.environ.get("FINSIGHT_REPOSITORY_ROOT")
    root = Path(configured).resolve() if configured else Path.cwd().resolve()
    if not (root / BUILDER_RELATIVE_PATH).is_file():
        raise Failure(
            description="FINSIGHT_REPOSITORY_ROOT does not contain the existing S2 builder.",
            metadata={"repository_root": str(root), "builder": str(BUILDER_RELATIVE_PATH)},
        )
    return root


def _resolve_within(*, path: Path, root: Path, label: str) -> Path:
    approved_root = root.resolve()
    candidate = (approved_root / path).resolve() if not path.is_absolute() else path.resolve()
    try:
        candidate.relative_to(approved_root)
    except ValueError as exc:
        raise Failure(
            description=f"{label} must stay inside its approved root.",
            metadata={label: str(candidate), "approved_root": str(approved_root)},
        ) from exc
    return candidate


def resolve_execution_paths(
    *,
    policy_path: Path,
    sqlite_path: Path,
    result_path: Path,
    repository_root: Path,
    policy_root: Path | None = None,
    output_root: Path | None = None,
) -> tuple[Path, Path, Path, Path]:
    configured_policy_root = policy_root or Path(
        os.environ.get(
            "FINSIGHT_S2_POLICY_ROOT",
            str(repository_root / "configs" / "financial_facts"),
        )
    )
    configured_output_root = output_root
    if configured_output_root is None:
        output_value = os.environ.get("FINSIGHT_S2_OUTPUT_ROOT")
        if not output_value:
            raise Failure(
                description="FINSIGHT_S2_OUTPUT_ROOT is required for the Dagster shadow adapter."
            )
        configured_output_root = Path(output_value)

    approved_policy_root = configured_policy_root.resolve()
    approved_output_root = configured_output_root.resolve()
    if not approved_policy_root.is_dir():
        raise Failure(
            description="Approved S2 policy root is not an existing directory.",
            metadata={"policy_root": str(approved_policy_root)},
        )
    if not approved_output_root.is_dir():
        raise Failure(
            description="Approved S2 output root is not an existing directory.",
            metadata={"output_root": str(approved_output_root)},
        )

    resolved_policy = _resolve_within(
        path=policy_path,
        root=approved_policy_root,
        label="policy_path",
    )
    resolved_sqlite = _resolve_within(
        path=sqlite_path,
        root=approved_output_root,
        label="sqlite_path",
    )
    resolved_result = _resolve_within(
        path=result_path,
        root=approved_output_root,
        label="result_path",
    )
    if not resolved_policy.is_file():
        raise Failure(
            description="S2 policy path is not an existing file.",
            metadata={"policy_path": str(resolved_policy)},
        )
    if resolved_sqlite.suffix.lower() not in {".sqlite", ".sqlite3"}:
        raise Failure(description="S2 shadow sqlite_path must use .sqlite or .sqlite3.")
    if resolved_result.suffix.lower() != ".json":
        raise Failure(description="S2 shadow result_path must use .json.")
    if resolved_sqlite == resolved_result:
        raise Failure(description="S2 shadow sqlite and result paths must be distinct.")
    if not resolved_sqlite.parent.is_dir() or not resolved_result.parent.is_dir():
        raise Failure(description="S2 shadow output parent directories must already exist.")
    return resolved_policy, resolved_sqlite, resolved_result, approved_output_root


def _require_fresh_outputs(*, sqlite_path: Path, result_path: Path) -> None:
    existing = [str(path) for path in (sqlite_path, result_path) if path.exists()]
    if existing:
        raise Failure(
            description="S2 shadow outputs must be fresh and attempt-scoped.",
            metadata={"existing_outputs": existing},
        )


def create_run_scoped_output_paths(
    *,
    run_id: str,
    output_root: Path | None = None,
) -> tuple[Path, Path, Path]:
    """Allocate one native-Dagster-run directory without overwriting evidence."""

    if not RUN_ID_PATTERN.fullmatch(run_id) or run_id in {".", ".."}:
        raise Failure(description="Dagster run_id is not safe for an output directory.")
    configured_root = output_root
    if configured_root is None:
        value = os.environ.get("FINSIGHT_S2_OUTPUT_ROOT")
        if not value:
            raise Failure(
                description="FINSIGHT_S2_OUTPUT_ROOT is required for run-scoped outputs."
            )
        configured_root = Path(value)
    approved_root = configured_root.resolve()
    if not approved_root.is_dir():
        raise Failure(description="Approved S2 output root is not an existing directory.")
    run_root = _resolve_within(
        path=Path(run_id),
        root=approved_root,
        label="run_output_root",
    )
    try:
        run_root.mkdir(exist_ok=False)
    except FileExistsError as exc:
        raise Failure(
            description="Dagster run-scoped output directory already exists.",
            metadata={"run_output_root": str(run_root)},
        ) from exc
    return (
        run_root / "company-financial-facts.sqlite",
        run_root / "company-financial-facts-result.json",
        approved_root,
    )


def execute_existing_s2_fact_mart_entrypoint(
    *,
    policy_path: Path,
    sqlite_path: Path,
    result_path: Path,
    repository_root: Path | None = None,
    policy_root: Path | None = None,
    output_root: Path | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Invoke the existing FIN materializer without copying its business logic."""

    root = repository_root.resolve() if repository_root else resolve_repository_root()
    if not (root / BUILDER_RELATIVE_PATH).is_file():
        raise Failure(
            description="Repository root does not contain the existing S2 builder.",
            metadata={"repository_root": str(root), "builder": str(BUILDER_RELATIVE_PATH)},
        )
    if not 1 <= timeout_seconds <= MAX_TIMEOUT_SECONDS:
        raise Failure(
            description=(
                "S2 shadow timeout_seconds must be between 1 and "
                f"{MAX_TIMEOUT_SECONDS}."
            )
        )
    policy, sqlite, result, approved_output_root = resolve_execution_paths(
        policy_path=policy_path,
        sqlite_path=sqlite_path,
        result_path=result_path,
        repository_root=root,
        policy_root=policy_root,
        output_root=output_root,
    )

    # One lock per approved output root deliberately serializes every local
    # materialization.  Pair-specific locks would miss runs that share only
    # the SQLite or only the JSON path and still race on the builder's `.tmp`.
    lock_path = approved_output_root / ".finsight-s2-shadow.lock"
    try:
        with FileLock(lock_path, timeout=0):
            _require_fresh_outputs(sqlite_path=sqlite, result_path=result)
            try:
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        BUILDER_MODULE,
                        "--policy",
                        str(policy),
                        "--sqlite",
                        str(sqlite),
                        "--output",
                        str(result),
                    ],
                    cwd=root,
                    check=False,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout_seconds,
                    env=build_child_environment(),
                )
            except subprocess.TimeoutExpired as exc:
                raise Failure(
                    description="Existing S2 company fact-mart entrypoint timed out.",
                    metadata={"timeout_seconds": timeout_seconds},
                ) from exc
    except Timeout as exc:
        raise Failure(
            description="Another S2 shadow run owns the same output target.",
            metadata={"lock_path": str(lock_path)},
        ) from exc

    if completed.returncode != 0:
        raise Failure(
            description="Existing S2 company fact-mart entrypoint failed.",
            metadata={
                "returncode": completed.returncode,
                "stdout_tail": completed.stdout[-4000:],
                "stderr_tail": completed.stderr[-4000:],
            },
        )
    if not result.is_file():
        raise Failure(description="Existing S2 entrypoint did not create its result object.")
    if not sqlite.is_file():
        raise Failure(description="Existing S2 entrypoint did not create its SQLite object.")
    payload = json.loads(result.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise Failure(description="S2 company fact-mart result must be a JSON object.")
    claimed_digest = payload.get("result_digest")
    unsigned = {key: value for key, value in payload.items() if key != "result_digest"}
    if not isinstance(claimed_digest, str) or claimed_digest != canonical_digest(unsigned):
        raise Failure(description="S2 company fact-mart result_digest is invalid.")
    storage = payload.get("storage")
    claimed_sqlite_digest = storage.get("sqlite_sha256") if isinstance(storage, dict) else None
    if (
        not isinstance(claimed_sqlite_digest, str)
        or claimed_sqlite_digest != sha256_file(sqlite)
    ):
        raise Failure(description="S2 company fact-mart SQLite digest is invalid.")
    return payload


@op(
    name="materialize_existing_s2_company_fact_mart",
    config_schema={
        "policy_path": str,
        "timeout_seconds": Field(int, default_value=DEFAULT_TIMEOUT_SECONDS),
    },
)
def materialize_existing_s2_company_fact_mart(context) -> dict[str, Any]:
    config = context.op_config
    sqlite_path, result_path, output_root = create_run_scoped_output_paths(
        run_id=context.run_id,
    )
    return execute_existing_s2_fact_mart_entrypoint(
        policy_path=Path(config["policy_path"]),
        sqlite_path=sqlite_path,
        result_path=result_path,
        output_root=output_root,
        timeout_seconds=int(config["timeout_seconds"]),
    )


@job(name="fin013_s2_fact_mart_shadow")
def s2_company_fact_mart_shadow() -> None:
    materialize_existing_s2_company_fact_mart()


defs = Definitions(jobs=[s2_company_fact_mart_shadow])


__all__ = [
    "BUILDER_MODULE",
    "BUILDER_RELATIVE_PATH",
    "CHILD_ENV_ALLOWLIST",
    "DEFAULT_TIMEOUT_SECONDS",
    "MAX_TIMEOUT_SECONDS",
    "build_child_environment",
    "canonical_digest",
    "create_run_scoped_output_paths",
    "defs",
    "execute_existing_s2_fact_mart_entrypoint",
    "resolve_execution_paths",
    "resolve_repository_root",
    "sha256_file",
    "s2_company_fact_mart_shadow",
]
