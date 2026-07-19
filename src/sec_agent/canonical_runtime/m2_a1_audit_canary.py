"""Runtime instrumentation for the future M2-A1 isolated actual audit.

The canary is not a convention that a caller may ignore.  Its context manager
patches concrete SQLite, object-store, file, import, socket, HTTP and process
constructors for the lifetime of an admitted synthetic run.  It permits only
the caller-provided temporary root and records every blocked attempt before an
external or fixed resource is opened.
"""

from __future__ import annotations

import builtins
import hashlib
import http.client
import importlib
import os
import socket
import sqlite3
import subprocess
import sys
import urllib.request
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping
from unittest.mock import patch


TRANSPORT_MODULE_ROOTS = frozenset({"aiohttp", "anthropic", "deepseek", "httpx", "openai", "requests", "urllib3"})
PROVIDER_MODULE_ROOTS = frozenset({"anthropic", "deepseek", "openai"})


class M2A1OracleLeakageError(RuntimeError):
    pass


class M2A1StoreAccessError(RuntimeError):
    pass


class M2A1TransportAccessError(RuntimeError):
    pass


class M2A1ModelAdmissionError(RuntimeError):
    pass


class M2A1AuditCanary:
    """Fail-closed, constructor-level isolation guard for a temporary audit root."""

    def __init__(
        self,
        *,
        allowed_temporary_roots: tuple[Path, ...],
        fixed_paths: tuple[Path, ...] = (),
        oracle_paths: tuple[Path, ...] = (),
    ) -> None:
        self._allowed_temporary_roots = tuple(path.resolve() for path in allowed_temporary_roots)
        self._fixed_paths = tuple(path.resolve() for path in fixed_paths)
        self._oracle_paths = tuple(path.resolve() for path in oracle_paths)
        self._counts: dict[str, int] = {
            "oracle_path_resolution_attempt_count": 0,
            "oracle_read_attempt_count": 0,
            "oracle_hash_attempt_count": 0,
            "oracle_import_attempt_count": 0,
            "store_open_attempt_count": 0,
            "store_open_success_count": 0,
            "store_read_open_count": 0,
            "store_write_open_count": 0,
            "object_store_constructor_attempt_count": 0,
            "object_store_constructor_success_count": 0,
            "ambient_resolution_attempt_count": 0,
            "provider_constructor_attempt_count": 0,
            "transport_module_loaded_count": 0,
            "preloaded_transport_alias_count": 0,
            # Historical compatibility only: this is a context observation,
            # never a constructor/use/connect attempt.
            "network_transport_constructor_attempt_count": 0,
            "transport_constructor_attempt_count": 0,
            "tool_transport_constructor_attempt_count": 0,
            "network_request_attempt_count": 0,
            "network_request_success_count": 0,
            "socket_connect_attempt_count": 0,
            "http_client_connect_attempt_count": 0,
            "http_connect_attempt_count": 0,
            "preloaded_transport_module_attempt_count": 0,
            "feature_flag_read_count": 0,
            "admission_lookup_count": 0,
            "model_constructor_attempt_count": 0,
        }
        self._events: list[dict[str, Any]] = []
        self._instrumentation_active = False
        self._sqlite_constructor_paths: list[Path] = []
        self._observed_transport_aliases: tuple[str, ...] = ()

    @property
    def fixed_paths(self) -> tuple[Path, ...]:
        """Exact fixed paths that must never be opened by an admitted run."""

        return self._fixed_paths

    @property
    def oracle_sentinel_path(self) -> Path:
        """A guard-only path used to prove the actual runner cannot read its oracle."""

        if not self._oracle_paths:
            raise M2A1OracleLeakageError("oracle_sentinel_not_configured")
        return self._oracle_paths[0]

    @property
    def ambient_resolver_env_var(self) -> str:
        return "FIN_INSIGHT_M2_A1_CANONICAL_STORE"

    @property
    def instrumentation_active(self) -> bool:
        return self._instrumentation_active

    def observe_transport_module_presence(self) -> tuple[str, ...]:
        """Record loaded transport aliases as context, not proof of capability use.

        Module presence can be caused by a host process, a test framework, or a
        harmless local dependency.  Only a concrete constructor, connect, or
        request path is a hard fail.  This keeps the canary from converting an
        import observation into a fabricated network attempt.
        """

        aliases = tuple(
            name
            for name in sorted(sys.modules)
            if name.split(".", 1)[0] in TRANSPORT_MODULE_ROOTS
        )
        self._observed_transport_aliases = aliases
        self._counts["transport_module_loaded_count"] = len(aliases)
        self._counts["preloaded_transport_alias_count"] = len(aliases)
        self._counts["preloaded_transport_module_attempt_count"] = len(aliases)
        if aliases:
            self._record("transport", "module_loaded_context_only", modules=aliases)
        return aliases

    def assert_no_preloaded_transport_or_provider_modules(self) -> tuple[str, ...]:
        """Compatibility alias for legacy callers; module presence no longer raises."""

        return self.observe_transport_module_presence()

    def _record(self, kind: str, operation: str, **details: Any) -> None:
        self._events.append({"kind": kind, "operation": operation, **details})

    def _is_allowed_root(self, candidate: Path) -> bool:
        resolved = candidate.resolve()
        return any(resolved.is_relative_to(root) for root in self._allowed_temporary_roots)

    def _is_fixed(self, candidate: Path) -> bool:
        resolved = candidate.resolve()
        return resolved in self._fixed_paths or ".runtime_control" in resolved.parts

    def _is_oracle(self, candidate: Path) -> bool:
        resolved = candidate.resolve()
        return resolved in self._oracle_paths

    def require_temporary_root(self, candidate: Path) -> None:
        resolved = candidate.resolve()
        if not self._is_allowed_root(resolved) or self._is_fixed(resolved):
            self._record("temporary_root", "validate", category="ambient_or_fixed", path=str(resolved))
            raise M2A1StoreAccessError("test_runtime_isolation_violation")
        self._record("temporary_root", "validate", category="allowed", path=str(resolved))

    def _guard_store_constructor(self, candidate: Path, *, write: bool, constructor: str) -> None:
        resolved = candidate.resolve()
        self._counts["store_open_attempt_count"] += 1
        category = "fixed" if self._is_fixed(resolved) else ("temporary" if self._is_allowed_root(resolved) else "ambient_or_unallowlisted")
        self._record("store", "constructor", constructor=constructor, path=str(resolved), write=write, category=category)
        if category != "temporary":
            raise M2A1StoreAccessError("test_runtime_isolation_violation")
        self._counts["store_open_success_count"] += 1
        if write:
            self._counts["store_write_open_count"] += 1
        else:
            self._counts["store_read_open_count"] += 1

    def _guard_object_store_constructor(self, candidate: Path) -> None:
        resolved = candidate.resolve()
        self._counts["object_store_constructor_attempt_count"] += 1
        category = "fixed" if self._is_fixed(resolved) else ("temporary" if self._is_allowed_root(resolved) else "ambient_or_unallowlisted")
        self._record("object_store", "constructor", path=str(resolved), category=category)
        if category != "temporary":
            raise M2A1StoreAccessError("test_runtime_isolation_violation")
        self._counts["object_store_constructor_success_count"] += 1

    def reject_oracle_path(self, path: str) -> None:
        self._counts["oracle_path_resolution_attempt_count"] += 1
        self._record("oracle", "path_resolution", path=path)
        raise M2A1OracleLeakageError("oracle_leakage_detected")

    def reject_oracle_read(self) -> None:
        self._counts["oracle_read_attempt_count"] += 1
        self._record("oracle", "read")
        raise M2A1OracleLeakageError("oracle_leakage_detected")

    def reject_oracle_hash(self) -> None:
        self._counts["oracle_hash_attempt_count"] += 1
        self._record("oracle", "hash")
        raise M2A1OracleLeakageError("oracle_leakage_detected")

    def reject_oracle_import(self) -> None:
        self._counts["oracle_import_attempt_count"] += 1
        self._record("oracle", "import")
        raise M2A1OracleLeakageError("oracle_leakage_detected")

    def reject_store_open(self, candidate: Path, *, write: bool) -> None:
        self._guard_store_constructor(candidate, write=write, constructor="explicit_negative_probe")

    def reject_ambient_store_resolution(self) -> None:
        self._counts["ambient_resolution_attempt_count"] += 1
        self._record("store", "ambient_resolution")
        raise M2A1StoreAccessError("test_runtime_isolation_violation")

    def reject_transport_constructor(self, *, kind: str) -> None:
        if kind == "provider":
            self._counts["provider_constructor_attempt_count"] += 1
        elif kind == "network":
            self._counts["network_transport_constructor_attempt_count"] += 1
            self._counts["transport_constructor_attempt_count"] += 1
        elif kind == "tool":
            self._counts["tool_transport_constructor_attempt_count"] += 1
        else:
            raise ValueError("transport_kind_invalid")
        self._record("transport", "constructor", transport_kind=kind)
        raise M2A1TransportAccessError("shadow_scope_violation")

    def reject_model_constructor(self, *, feature_flag_enabled: bool, admission_present: bool) -> None:
        self._counts["feature_flag_read_count"] += 1
        self._counts["admission_lookup_count"] += 1
        self._counts["model_constructor_attempt_count"] += 1
        self._record("model", "constructor", feature_flag_enabled=feature_flag_enabled, admission_present=admission_present)
        raise M2A1ModelAdmissionError("model_adapter_shadow_run_not_admitted")

    def deny_model_admission(self, *, feature_flag_enabled: bool, admission_present: bool) -> None:
        """Record a denied admission lookup without constructing a provider/model."""

        self._counts["feature_flag_read_count"] += 1
        self._counts["admission_lookup_count"] += 1
        self._record("model", "admission_denied", feature_flag_enabled=feature_flag_enabled, admission_present=admission_present)
        raise M2A1ModelAdmissionError("model_adapter_shadow_run_not_admitted")

    @contextmanager
    def instrument(self) -> Iterator["M2A1AuditCanary"]:
        """Patch concrete constructors; nested instrumentation is intentionally forbidden."""

        if self._instrumentation_active:
            raise RuntimeError("m2_a1_audit_instrumentation_already_active")
        self._instrumentation_active = True
        from . import object_store as object_store_module
        from . import store as canonical_store_module

        original_sqlite_store_init = canonical_store_module.SQLiteCanonicalStore.__init__
        original_object_store_init = object_store_module.FileCanonicalObjectStore.__init__
        original_sqlite_connect = sqlite3.connect
        original_path_open = Path.open
        original_path_read_text = Path.read_text
        original_path_read_bytes = Path.read_bytes
        original_builtin_open = builtins.open
        original_import = builtins.__import__
        original_import_module = importlib.import_module
        original_socket_connect = socket.create_connection
        original_socket_instance_connect = socket.socket.connect
        original_http_connect = http.client.HTTPConnection.connect
        original_https_connect = http.client.HTTPSConnection.connect
        original_getenv = os.getenv
        original_urlopen = urllib.request.urlopen
        original_popen = subprocess.Popen

        patched_constructor_keys: set[tuple[int, str]] = set()

        def blocked_network_constructor(*args: Any, **kwargs: Any) -> None:
            self.reject_transport_constructor(kind="network")

        def blocked_provider_constructor(*args: Any, **kwargs: Any) -> None:
            self.reject_model_constructor(feature_flag_enabled=False, admission_present=False)

        def patch_constructor(stack: ExitStack, target: Any, attribute: str, replacement: Any) -> None:
            if not callable(getattr(target, attribute, None)):
                return
            key = (id(target), attribute)
            if key in patched_constructor_keys:
                return
            patched_constructor_keys.add(key)
            stack.enter_context(patch.object(target, attribute, replacement))

        def patch_loaded_transport_or_provider_aliases(stack: ExitStack) -> None:
            """Guard optional aliases without importing them for the audit itself."""

            requests_module = sys.modules.get("requests")
            if requests_module is not None:
                session = getattr(requests_module, "Session", None)
                if session is not None:
                    patch_constructor(stack, session, "__init__", blocked_network_constructor)
            urllib3_module = sys.modules.get("urllib3")
            if urllib3_module is not None:
                for attribute in ("PoolManager", "ProxyManager", "HTTPConnectionPool", "HTTPSConnectionPool"):
                    candidate = getattr(urllib3_module, attribute, None)
                    if candidate is not None:
                        patch_constructor(stack, candidate, "__init__", blocked_network_constructor)
            for root in PROVIDER_MODULE_ROOTS:
                provider_module = sys.modules.get(root)
                if provider_module is None:
                    continue
                for attribute in ("OpenAI", "AsyncOpenAI", "AzureOpenAI", "Anthropic", "AsyncAnthropic", "Client"):
                    candidate = getattr(provider_module, attribute, None)
                    key = (id(provider_module), attribute)
                    if callable(candidate) and key not in patched_constructor_keys:
                        patched_constructor_keys.add(key)
                        stack.enter_context(patch.object(provider_module, attribute, blocked_provider_constructor))

        def sqlite_store_init(instance: Any, db_path: str | Path, *args: Any, **kwargs: Any) -> None:
            resolved = Path(db_path).resolve()
            self._guard_store_constructor(resolved, write=True, constructor="SQLiteCanonicalStore")
            self._sqlite_constructor_paths.append(resolved)
            try:
                original_sqlite_store_init(instance, db_path, *args, **kwargs)
            finally:
                self._sqlite_constructor_paths.pop()

        def object_store_init(instance: Any, root: str | Path, *args: Any, **kwargs: Any) -> None:
            self._guard_object_store_constructor(Path(root))
            original_object_store_init(instance, root, *args, **kwargs)

        def sqlite_connect(database: Any, *args: Any, **kwargs: Any) -> Any:
            if isinstance(database, (str, Path)) and database != ":memory:":
                path = Path(str(database).replace("file:", "").split("?", 1)[0]).resolve()
                if self._sqlite_constructor_paths and path == self._sqlite_constructor_paths[-1]:
                    return original_sqlite_connect(database, *args, **kwargs)
                write = not (kwargs.get("uri") and "mode=ro" in str(database))
                self._guard_store_constructor(path, write=write, constructor="sqlite3.connect")
            return original_sqlite_connect(database, *args, **kwargs)

        def oracle_path(candidate: Any) -> Path | None:
            try:
                path = Path(candidate).resolve()
            except (TypeError, OSError):
                return None
            return path if self._is_oracle(path) else None

        def path_open(path: Path, *args: Any, **kwargs: Any) -> Any:
            if oracle_path(path) is not None:
                self.reject_oracle_read()
            if self._is_fixed(path):
                self._guard_store_constructor(path, write=any(flag in str(kwargs.get("mode") or (args[0] if args else "r")) for flag in ("w", "a", "+")), constructor="Path.open")
            return original_path_open(path, *args, **kwargs)

        def path_read_text(path: Path, *args: Any, **kwargs: Any) -> str:
            if oracle_path(path) is not None:
                self.reject_oracle_read()
            if self._is_fixed(path):
                self._guard_store_constructor(path, write=False, constructor="Path.read_text")
            return original_path_read_text(path, *args, **kwargs)

        def path_read_bytes(path: Path, *args: Any, **kwargs: Any) -> bytes:
            if oracle_path(path) is not None:
                self.reject_oracle_hash()
            if self._is_fixed(path):
                self._guard_store_constructor(path, write=False, constructor="Path.read_bytes")
            return original_path_read_bytes(path, *args, **kwargs)

        def builtin_open(file: Any, *args: Any, **kwargs: Any) -> Any:
            if oracle_path(file) is not None:
                self.reject_oracle_read()
            return original_builtin_open(file, *args, **kwargs)

        def guarded_import(name: str, globals: Mapping[str, Any] | None = None, locals: Mapping[str, Any] | None = None, fromlist: tuple[str, ...] = (), level: int = 0) -> Any:
            if name == "sec_agent.canonical_runtime.m2_a1_audit_oracle" or name.endswith(".m2_a1_audit_oracle"):
                self.reject_oracle_import()
            if name.split(".", 1)[0] in PROVIDER_MODULE_ROOTS:
                self.reject_model_constructor(feature_flag_enabled=False, admission_present=False)
            result = original_import(name, globals, locals, fromlist, level)
            patch_loaded_transport_or_provider_aliases(stack)
            return result

        def guarded_import_module(name: str, package: str | None = None) -> Any:
            if name == "sec_agent.canonical_runtime.m2_a1_audit_oracle" or name.endswith(".m2_a1_audit_oracle"):
                self.reject_oracle_import()
            if name.split(".", 1)[0] in PROVIDER_MODULE_ROOTS:
                self.reject_model_constructor(feature_flag_enabled=False, admission_present=False)
            result = original_import_module(name, package)
            patch_loaded_transport_or_provider_aliases(stack)
            return result

        def socket_connect(*args: Any, **kwargs: Any) -> Any:
            self._counts["network_request_attempt_count"] += 1
            self._record("network", "socket_create_connection")
            raise M2A1TransportAccessError("shadow_scope_violation")

        def socket_instance_connect(instance: socket.socket, *args: Any, **kwargs: Any) -> Any:
            self._counts["network_request_attempt_count"] += 1
            self._counts["socket_connect_attempt_count"] += 1
            self._record("network", "socket_socket_connect")
            raise M2A1TransportAccessError("shadow_scope_violation")

        def http_connect(instance: http.client.HTTPConnection, *args: Any, **kwargs: Any) -> Any:
            self._counts["network_request_attempt_count"] += 1
            self._counts["http_client_connect_attempt_count"] += 1
            self._counts["http_connect_attempt_count"] += 1
            self._record("network", "http_client_connect")
            raise M2A1TransportAccessError("shadow_scope_violation")

        def guarded_getenv(key: str, default: Any = None) -> Any:
            if key == self.ambient_resolver_env_var:
                self._counts["ambient_resolution_attempt_count"] += 1
                self._record("store", "ambient_resolution", key=key)
                raise M2A1StoreAccessError("test_runtime_isolation_violation")
            return original_getenv(key, default)

        def urlopen(*args: Any, **kwargs: Any) -> Any:
            self._counts["network_request_attempt_count"] += 1
            self._record("network", "urlopen")
            raise M2A1TransportAccessError("shadow_scope_violation")

        def popen(*args: Any, **kwargs: Any) -> Any:
            self._counts["tool_transport_constructor_attempt_count"] += 1
            self._record("tool", "subprocess_popen")
            raise M2A1TransportAccessError("shadow_scope_violation")

        try:
            with ExitStack() as stack:
                patch_loaded_transport_or_provider_aliases(stack)
                stack.enter_context(patch.object(canonical_store_module.SQLiteCanonicalStore, "__init__", sqlite_store_init))
                stack.enter_context(patch.object(object_store_module.FileCanonicalObjectStore, "__init__", object_store_init))
                stack.enter_context(patch.object(sqlite3, "connect", sqlite_connect))
                stack.enter_context(patch.object(Path, "open", path_open))
                stack.enter_context(patch.object(Path, "read_text", path_read_text))
                stack.enter_context(patch.object(Path, "read_bytes", path_read_bytes))
                stack.enter_context(patch.object(builtins, "open", builtin_open))
                stack.enter_context(patch.object(builtins, "__import__", guarded_import))
                stack.enter_context(patch.object(importlib, "import_module", guarded_import_module))
                stack.enter_context(patch.object(socket, "create_connection", socket_connect))
                stack.enter_context(patch.object(socket.socket, "connect", socket_instance_connect))
                stack.enter_context(patch.object(http.client.HTTPConnection, "connect", http_connect))
                stack.enter_context(patch.object(http.client.HTTPSConnection, "connect", http_connect))
                stack.enter_context(patch.object(os, "getenv", guarded_getenv))
                stack.enter_context(patch.object(urllib.request, "urlopen", urlopen))
                stack.enter_context(patch.object(subprocess, "Popen", popen))
                yield self
        finally:
            self._instrumentation_active = False

    def snapshot(self) -> dict[str, Any]:
        return {
            "counts": dict(self._counts),
            "events": list(self._events),
            "instrumentation_active": self._instrumentation_active,
            "transport_module_loaded": bool(self._observed_transport_aliases),
            "preloaded_transport_aliases": self._observed_transport_aliases,
            "allowed_temporary_roots": tuple(str(path) for path in self._allowed_temporary_roots),
        }
