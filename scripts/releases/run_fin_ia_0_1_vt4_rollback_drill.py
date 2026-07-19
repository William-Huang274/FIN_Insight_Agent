"""Run and verify the local-only VT4 P07.4 fixture-lane rollback drill.

The drill creates one deterministic internal fixture Case, snapshots its
canonical SQLite/object audit surface, then starts a second application with
the FIN 0.1 fixture lane explicitly unavailable.  It proves the new lane is
fail-closed while the legacy browser shell stays reachable, and that disabling
the lane does not delete or alter the original canonical audit records.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence
from uuid import UUID


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
for import_root in (REPO_ROOT, SRC_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from fastapi.testclient import TestClient

from apps.workbench.backend.app import create_app
from apps.workbench.backend.application.case_service import (
    CasePrincipal,
    CaseService,
    CreateCaseDraft,
)
from sec_agent.canonical_runtime.store import OBJECT_TABLES


SCRIPT_SCHEMA = "fin_ia_0_1_vt4_rollback_drill_v1_0"
RESULT_STATUS = "fixture_lane_disabled_audit_preserved_not_release_admission"
FIXTURE_TIME = datetime(2026, 7, 18, tzinfo=timezone.utc)
FIXTURE_TENANT = "tenant_vt4_rollback_fixture"
FIXTURE_PROJECT = "project_vt4_rollback_fixture"
FIXTURE_ACTOR = "analyst_vt4_rollback_fixture"
FIXTURE_TRACE = "trace_vt4_rollback_fixture"
FIXTURE_IDEMPOTENCY_KEY = "vt4-p07-4-rollback-drill-case-v1"
ZERO_BOUNDARY_KEYS = (
    "commercial_data_spend",
    "model_calls",
    "network_calls",
    "paid_full_chain",
    "provider_calls",
    "real_business_case_writes",
    "release_admission",
    "tool_invocations",
)


class RollbackDrillError(ValueError):
    """Raised when the bounded rollback drill cannot prove its contract."""


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize all drill artifacts with one stable, portable encoding."""
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RollbackDrillError(f"mapping_required:{label}")
    return value


class _DeterministicUuidFactory:
    """Provide stable UUIDs only while constructing the local fixture Case."""

    def __init__(self) -> None:
        self._counter = 0

    def __call__(self) -> UUID:
        self._counter += 1
        return UUID(int=self._counter)


@contextmanager
def _deterministic_fixture_runtime() -> Iterator[None]:
    """Freeze runtime-generated timestamps/UUIDs without changing product code."""
    import apps.workbench.backend.application.case_service as case_service_module
    import sec_agent.canonical_runtime.facade as facade_module
    import sec_agent.canonical_runtime.store as store_module

    fixed_now = lambda: FIXTURE_TIME
    originals = (
        case_service_module.utc_now,
        facade_module.utc_now,
        facade_module.uuid4,
        store_module.utc_now,
    )
    case_service_module.utc_now = fixed_now
    facade_module.utc_now = fixed_now
    facade_module.uuid4 = _DeterministicUuidFactory()
    store_module.utc_now = fixed_now
    try:
        yield
    finally:
        (
            case_service_module.utc_now,
            facade_module.utc_now,
            facade_module.uuid4,
            store_module.utc_now,
        ) = originals


def _headers() -> dict[str, str]:
    return {
        "X-Fin-Case-Tenant": FIXTURE_TENANT,
        "X-Fin-Case-Project": FIXTURE_PROJECT,
        "X-Fin-Case-Actor": FIXTURE_ACTOR,
        "X-Fin-Case-Permissions": "case:create,case:read",
        "X-Trace-Id": FIXTURE_TRACE,
    }


def _create_payload() -> dict[str, str]:
    return {
        "query": "Internal fixture rollback drill only",
        "as_of": "2026-07-18T00:00:00Z",
        "language": "en",
        "source_policy_ref": "fixture:internal-only",
        "idempotency_key": FIXTURE_IDEMPOTENCY_KEY,
    }


def _principal() -> CasePrincipal:
    return CasePrincipal(
        tenant_id=FIXTURE_TENANT,
        project_id=FIXTURE_PROJECT,
        actor_id=FIXTURE_ACTOR,
        permissions=frozenset({"case:create", "case:read"}),
    )


def _checkpoint_database(db_path: Path) -> None:
    """Materialize the initial WAL before comparing bytes across lane disable."""
    with sqlite3.connect(db_path) as connection:
        connection.execute("pragma wal_checkpoint(truncate)").fetchall()


def _database_snapshot(db_path: Path) -> dict[str, Any]:
    if not db_path.is_file():
        raise RollbackDrillError("canonical_database_missing")

    table_counts: dict[str, int] = {}
    logical_payloads: dict[str, list[Any]] = {}
    try:
        with sqlite3.connect(f"{db_path.as_uri()}?mode=ro", uri=True) as connection:
            for table in OBJECT_TABLES:
                rows = connection.execute(
                    f"select payload_json from {table} order by logical_id, version_no, state_version"
                ).fetchall()
                payloads = [json.loads(str(row[0])) for row in rows]
                table_counts[table] = len(payloads)
                if payloads:
                    logical_payloads[table] = payloads
            event_rows = connection.execute(
                "select payload_json from canonical_events order by sequence_no, event_id"
            ).fetchall()
            idempotency_rows = connection.execute(
                "select scope_key, payload_digest, result_json from canonical_idempotency order by scope_key"
            ).fetchall()
    except (OSError, sqlite3.Error, json.JSONDecodeError) as exc:
        raise RollbackDrillError("canonical_database_snapshot_failed") from exc

    events = [json.loads(str(row[0])) for row in event_rows]
    idempotency = [
        {
            "scope_key": str(row[0]),
            "payload_digest": str(row[1]),
            "result": json.loads(str(row[2])),
        }
        for row in idempotency_rows
    ]
    logical_content = {
        "records": logical_payloads,
        "events": events,
        "idempotency": idempotency,
    }
    return {
        "exists": True,
        "byte_count": db_path.stat().st_size,
        "file_sha256": sha256_bytes(db_path.read_bytes()),
        "logical_content_sha256": canonical_sha256(logical_content),
        "record_count": sum(table_counts.values()),
        "records_by_table": table_counts,
        "event_count": len(events),
        "idempotency_count": len(idempotency),
    }


def _object_snapshot(objects_root: Path) -> dict[str, Any]:
    if not objects_root.is_dir():
        raise RollbackDrillError("canonical_object_root_missing")
    objects: list[dict[str, Any]] = []
    for path in sorted(item for item in objects_root.rglob("*") if item.is_file()):
        raw = path.read_bytes()
        objects.append(
            {
                "path": path.relative_to(objects_root).as_posix(),
                "byte_count": len(raw),
                "sha256": sha256_bytes(raw),
            }
        )
    return {
        "exists": True,
        "object_count": len(objects),
        "byte_count": sum(int(item["byte_count"]) for item in objects),
        "objects": objects,
        "content_sha256": canonical_sha256(objects),
    }


def snapshot_canonical_audit(fixture_root: Path) -> dict[str, Any]:
    """Capture only portable content identity, never the temporary root path."""
    fixture_root = fixture_root.resolve()
    database = _database_snapshot(fixture_root / "canonical.sqlite")
    objects = _object_snapshot(fixture_root / "objects")
    payload = {"database": database, "objects": objects}
    return {**payload, "snapshot_sha256": canonical_sha256(payload)}


def _error_code(response: Any) -> str | None:
    try:
        body = response.json()
    except ValueError:
        return None
    if not isinstance(body, Mapping):
        return None
    error = body.get("error")
    return str(error.get("error_code")) if isinstance(error, Mapping) else None


def _disabled_lane_observation(case_id: str, disabled_store_path: Path) -> dict[str, Any]:
    """Exercise the disabled FIN 0.1 lane without reopening the fixture root."""
    app = create_app(
        store_path=disabled_store_path,
        p02_case_service=CaseService.unavailable("vt4_p07_4_fixture_lane_disabled"),
    )
    with TestClient(app) as client:
        case_read = client.get(f"/api/v1/cases/{case_id}", headers=_headers())
        case_create = client.post("/api/v1/cases", headers=_headers(), json=_create_payload())
        legacy = client.get("/legacy")

    for response in (case_read, case_create):
        if response.status_code not in {403, 503}:
            raise RollbackDrillError(f"fixture_lane_not_fail_closed:{response.status_code}")
        if response.status_code == 403 and _error_code(response) != "operation_not_admitted":
            raise RollbackDrillError("fixture_lane_unavailable_code_invalid")
    if legacy.status_code != 200 or 'id="root"' not in legacy.text:
        raise RollbackDrillError("legacy_fallback_shell_unavailable")

    return {
        "new_lane_case_read": {
            "status": "fail_closed",
            "status_code": case_read.status_code,
            "error_code": _error_code(case_read),
        },
        "new_lane_case_create": {
            "status": "fail_closed",
            "status_code": case_create.status_code,
            "error_code": _error_code(case_create),
            "admitted_writes": 0,
        },
        "legacy_browser_fallback": {
            "status": "available_shell_only",
            "status_code": legacy.status_code,
            "root_mount_present": True,
        },
    }


def _create_fixture_case(fixture_root: Path, repo_root: Path) -> dict[str, Any]:
    with _deterministic_fixture_runtime():
        service = CaseService.for_fixture_root(fixture_root, repo_root=repo_root)
        workspace = service.create_case(
            CreateCaseDraft(
                query="Internal fixture rollback drill only",
                as_of=FIXTURE_TIME,
                language="en",
                source_policy_ref="fixture:internal-only",
                idempotency_key=FIXTURE_IDEMPOTENCY_KEY,
            ),
            _principal(),
            trace_id=FIXTURE_TRACE,
        )
    if workspace.get("planning_checkpoint_state") != "legacy_authority_retained":
        raise RollbackDrillError("legacy_global_authority_not_retained")
    return dict(workspace)


def _zero_boundaries() -> dict[str, int]:
    return {key: 0 for key in ZERO_BOUNDARY_KEYS}


def build_result(*, fixture_root: Path, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Run the bounded drill at a caller-owned temporary local fixture root."""
    fixture_root = fixture_root.resolve()
    repo_root = repo_root.resolve()
    if fixture_root == repo_root or repo_root in fixture_root.parents:
        raise RollbackDrillError("temporary_fixture_root_must_not_be_repository")
    workspace = _create_fixture_case(fixture_root, repo_root)
    _checkpoint_database(fixture_root / "canonical.sqlite")
    before = snapshot_canonical_audit(fixture_root)
    lane = _disabled_lane_observation(workspace["case_id"], fixture_root.parent / "disabled-workbench.sqlite")
    after = snapshot_canonical_audit(fixture_root)
    if before != after:
        raise RollbackDrillError("canonical_audit_not_preserved")

    payload = {
        "schema_version": SCRIPT_SCHEMA,
        "result_id": "REL-PROD-001:VT4:P07.4:fixture-lane-rollback-drill",
        "status": RESULT_STATUS,
        "release_id": "REL-PROD-001",
        "tranche_id": "VT4_P07_4_ROLLBACK_DRILL",
        "fixture_case": {
            "case_id": workspace["case_id"],
            "case_version": workspace["case_version"],
            "summary_version": workspace["summary_version"],
            "planning_checkpoint_state": workspace["planning_checkpoint_state"],
            "case_type": "fixture_internal",
        },
        "lane_disable": lane,
        "authority": {
            "legacy_global_authority": "retained",
            "production_readiness": "not_admitted",
            "fixture_lane": "disabled_fail_closed",
            "legacy_fallback": "available_shell_only",
        },
        "canonical_audit": {
            "before": before,
            "after": after,
            "preserved": True,
            "data_deletion": "forbidden_and_not_observed",
        },
        "local_fixture_actions": {
            "fixture_case_creates": 1,
            "disabled_new_lane_read_attempts": 1,
            "disabled_new_lane_write_attempts": 1,
            "disabled_new_lane_admitted_writes": 0,
            "legacy_browser_route_reads": 1,
        },
        "boundary_counts": _zero_boundaries(),
        "operational_execution": "not_run",
        "rg1_vertical_path": "not_run_separate_authority_required",
        "release_admission": "not_granted",
    }
    return {**payload, "result_sha256": canonical_sha256(payload)}


def write_result(path: Path, result: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(dict(result)) + b"\n")


def verify_result(*, result_path: Path, repo_root: Path = REPO_ROOT) -> dict[str, str]:
    """Fail closed on noncanonical bytes, digest tamper, or fixture-result drift."""
    try:
        raw = result_path.read_bytes()
        result = _mapping(json.loads(raw.decode("utf-8")), "rollback_drill_result")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RollbackDrillError(f"result_read_failed:{result_path}") from exc
    if raw != canonical_json_bytes(result) + b"\n":
        raise RollbackDrillError("result_not_canonical_json")
    if result.get("result_sha256") != canonical_sha256(
        {key: value for key, value in result.items() if key != "result_sha256"}
    ):
        raise RollbackDrillError("result_digest_invalid")
    with tempfile.TemporaryDirectory(prefix="fin-ia-vt4-rollback-verify-") as temp_dir:
        expected = build_result(fixture_root=Path(temp_dir) / "fixture", repo_root=repo_root)
    if dict(result) != expected:
        raise RollbackDrillError("result_or_fixture_drift")
    return {"status": "pass", "result_sha256": str(result["result_sha256"])}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="mode", required=True)
    run = commands.add_parser("run")
    run.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    run.add_argument("--output", type=Path, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    verify.add_argument("--result", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.mode == "run":
            with tempfile.TemporaryDirectory(prefix="fin-ia-vt4-rollback-run-") as temp_dir:
                result = build_result(
                    fixture_root=Path(temp_dir) / "fixture",
                    repo_root=args.repo_root,
                )
            write_result(args.output, result)
            response: Mapping[str, Any] = {
                "status": "pass",
                "result_path": str(args.output),
                "result_sha256": result["result_sha256"],
            }
        else:
            response = verify_result(result_path=args.result, repo_root=args.repo_root)
    except RollbackDrillError as exc:
        print(canonical_json_bytes({"status": "fail_closed", "error": str(exc)}).decode("utf-8"))
        return 2
    print(canonical_json_bytes(dict(response)).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
