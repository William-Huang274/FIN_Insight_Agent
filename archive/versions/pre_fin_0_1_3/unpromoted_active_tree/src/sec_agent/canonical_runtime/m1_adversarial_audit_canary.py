"""Runtime access canary for the isolated Point 01 M1-A1 audit.

The guard instruments the concrete SQLite/object-store constructors used by
M1, direct ``sqlite3.connect`` calls, and common transport constructors.  It
allows only explicitly supplied temporary roots and rejects before any fixed,
ambient, or transport access can occur.
"""

from __future__ import annotations

import http.client
import socket
import sqlite3
import urllib.request
from pathlib import Path
from typing import Any, Callable

from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore


class AuditAccessViolation(RuntimeError):
    pass


class AuditTransportViolation(RuntimeError):
    pass


class M1AuditAccessCanary:
    """Patch concrete constructors while an M1-A1 audit process is running."""

    def __init__(self, *, allowed_roots: tuple[Path, ...], fixed_paths: tuple[Path, ...]) -> None:
        self.allowed_roots = tuple(path.resolve() for path in allowed_roots)
        self.fixed_paths = tuple(path.resolve() for path in fixed_paths)
        self.events: list[dict[str, Any]] = []
        self._original_store_init: Callable[..., Any] | None = None
        self._original_object_init: Callable[..., Any] | None = None
        self._original_connect: Callable[..., Any] | None = None
        self._original_http_init: Callable[..., Any] | None = None
        self._original_https_init: Callable[..., Any] | None = None
        self._original_urlopen: Callable[..., Any] | None = None
        self._original_socket_create: Callable[..., Any] | None = None

    def _classify_path(self, value: str | Path) -> tuple[str, Path | None]:
        if str(value) == ":memory:":
            return "allowed_memory", None
        path = Path(value).resolve()
        if path in self.fixed_paths or ".runtime_control" in path.parts:
            return "fixed_forbidden", path
        if any(path.is_relative_to(root) for root in self.allowed_roots):
            return "allowed", path
        return "ambient_or_unallowlisted", path

    def _record_store(self, *, operation: str, value: str | Path, access_mode: str) -> None:
        category, path = self._classify_path(value)
        self.events.append(
            {
                "kind": "store",
                "operation": operation,
                "access_mode": access_mode,
                "category": category,
                "path": str(path) if path is not None else ":memory:",
            }
        )
        if category == "fixed_forbidden":
            raise AuditAccessViolation("audit_fixed_store_path_forbidden")
        if category == "ambient_or_unallowlisted":
            raise AuditAccessViolation("audit_store_path_not_allowlisted")

    def _record_transport(self, operation: str) -> None:
        self.events.append({"kind": "transport", "operation": operation, "category": "forbidden"})
        raise AuditTransportViolation("audit_transport_constructor_forbidden")

    def __enter__(self) -> M1AuditAccessCanary:
        self._original_store_init = SQLiteCanonicalStore.__init__
        self._original_object_init = FileCanonicalObjectStore.__init__
        self._original_connect = sqlite3.connect
        self._original_http_init = http.client.HTTPConnection.__init__
        self._original_https_init = http.client.HTTPSConnection.__init__
        self._original_urlopen = urllib.request.urlopen
        self._original_socket_create = socket.create_connection
        canary = self

        def guarded_store_init(instance: SQLiteCanonicalStore, db_path: str | Path, *args: Any, **kwargs: Any) -> None:
            canary._record_store(operation="SQLiteCanonicalStore.__init__", value=db_path, access_mode="write_capable")
            assert canary._original_store_init is not None
            canary._original_store_init(instance, db_path, *args, **kwargs)

        def guarded_object_init(instance: FileCanonicalObjectStore, root: str | Path) -> None:
            canary._record_store(operation="FileCanonicalObjectStore.__init__", value=root, access_mode="write_capable")
            assert canary._original_object_init is not None
            canary._original_object_init(instance, root)

        def guarded_connect(database: str | Path, *args: Any, **kwargs: Any) -> sqlite3.Connection:
            canary._record_store(operation="sqlite3.connect", value=database, access_mode="read_or_write")
            assert canary._original_connect is not None
            connection = canary._original_connect(database, *args, **kwargs)

            def trace(statement: str) -> None:
                if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "REPLACE")):
                    canary.events.append({"kind": "sqlite_statement", "operation": statement.split(None, 1)[0].upper(), "category": "allowed_temp"})

            connection.set_trace_callback(trace)
            return connection

        def blocked_http(*args: Any, **kwargs: Any) -> None:
            canary._record_transport("http.client.HTTPConnection.__init__")

        def blocked_https(*args: Any, **kwargs: Any) -> None:
            canary._record_transport("http.client.HTTPSConnection.__init__")

        def blocked_urlopen(*args: Any, **kwargs: Any) -> None:
            canary._record_transport("urllib.request.urlopen")

        def blocked_socket(*args: Any, **kwargs: Any) -> None:
            canary._record_transport("socket.create_connection")

        SQLiteCanonicalStore.__init__ = guarded_store_init  # type: ignore[method-assign]
        FileCanonicalObjectStore.__init__ = guarded_object_init  # type: ignore[method-assign]
        sqlite3.connect = guarded_connect  # type: ignore[assignment]
        http.client.HTTPConnection.__init__ = blocked_http  # type: ignore[method-assign]
        http.client.HTTPSConnection.__init__ = blocked_https  # type: ignore[method-assign]
        urllib.request.urlopen = blocked_urlopen  # type: ignore[assignment]
        socket.create_connection = blocked_socket  # type: ignore[assignment]
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        assert self._original_store_init and self._original_object_init and self._original_connect
        assert self._original_http_init and self._original_https_init and self._original_urlopen and self._original_socket_create
        SQLiteCanonicalStore.__init__ = self._original_store_init  # type: ignore[method-assign]
        FileCanonicalObjectStore.__init__ = self._original_object_init  # type: ignore[method-assign]
        sqlite3.connect = self._original_connect  # type: ignore[assignment]
        http.client.HTTPConnection.__init__ = self._original_http_init  # type: ignore[method-assign]
        http.client.HTTPSConnection.__init__ = self._original_https_init  # type: ignore[method-assign]
        urllib.request.urlopen = self._original_urlopen  # type: ignore[assignment]
        socket.create_connection = self._original_socket_create  # type: ignore[assignment]

    def snapshot(self) -> dict[str, int]:
        store_events = [row for row in self.events if row["kind"] == "store"]
        return {
            "store_open_attempt_count": len(store_events),
            "store_read_or_write_open_count": len(store_events),
            "store_write_capable_open_count": sum(1 for row in store_events if row["access_mode"] == "write_capable"),
            "fixed_store_open_attempt_count": sum(1 for row in store_events if row["category"] == "fixed_forbidden"),
            "ambient_store_open_attempt_count": sum(1 for row in store_events if row["category"] == "ambient_or_unallowlisted"),
            "temporary_sqlite_write_statement_count": sum(1 for row in self.events if row["kind"] == "sqlite_statement"),
            "transport_constructor_attempt_count": sum(1 for row in self.events if row["kind"] == "transport"),
        }
