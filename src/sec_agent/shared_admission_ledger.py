from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sqlite3
from typing import Any

from sec_agent.canonical_runtime.models import canonical_digest


LEDGER_SCHEMA = "fin_ia_shared_admission_consumption_ledger_v1_0"
_DIGEST = re.compile(r"[0-9a-f]{64}")


class SharedAdmissionLedgerError(RuntimeError):
    """Typed fail-closed error at the shared admission boundary."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _nonblank(value: str, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SharedAdmissionLedgerError(code)
    return value.strip()


def _digest(value: str, code: str) -> str:
    candidate = _nonblank(value, code).lower()
    if not _DIGEST.fullmatch(candidate):
        raise SharedAdmissionLedgerError(code)
    return candidate


@dataclass(frozen=True)
class AdmissionConsumptionReceipt:
    admission_digest: str
    admission_id: str
    scope: str
    run_id: str
    attempt_id: str
    runtime_identity: str
    state: str
    reserved_at: str
    reservation_digest: str
    terminal_status: str | None
    terminal_phase: str | None
    terminal_code: str | None
    terminal_result_digest: str | None
    finalized_at: str | None
    receipt_digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": LEDGER_SCHEMA,
            "admission_digest": self.admission_digest,
            "admission_id": self.admission_id,
            "scope": self.scope,
            "run_id": self.run_id,
            "attempt_id": self.attempt_id,
            "runtime_identity": self.runtime_identity,
            "state": self.state,
            "reserved_at": self.reserved_at,
            "reservation_digest": self.reservation_digest,
            "terminal_status": self.terminal_status,
            "terminal_phase": self.terminal_phase,
            "terminal_code": self.terminal_code,
            "terminal_result_digest": self.terminal_result_digest,
            "finalized_at": self.finalized_at,
            "receipt_digest": self.receipt_digest,
        }


class SharedAdmissionConsumptionLedger:
    """Repository-independent, crash-safe exact-once admission authority.

    The caller must place this SQLite file outside disposable per-attempt runtime
    roots. A durable reservation is itself consumption: after a crash the same
    admission stays blocked until a separate, audited disposition is made.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            isolation_level=None,
            timeout=30.0,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA synchronous = FULL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS admission_consumptions (
                    admission_digest TEXT PRIMARY KEY,
                    admission_id TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    attempt_id TEXT NOT NULL,
                    runtime_identity TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN ('reserved', 'terminal')),
                    reserved_at TEXT NOT NULL,
                    reservation_digest TEXT NOT NULL,
                    terminal_status TEXT,
                    terminal_phase TEXT,
                    terminal_code TEXT,
                    terminal_result_digest TEXT,
                    finalized_at TEXT,
                    receipt_digest TEXT NOT NULL
                )
                """
            )

    def reserve(
        self,
        *,
        admission_digest: str,
        admission_id: str,
        scope: str,
        run_id: str,
        attempt_id: str,
        runtime_identity: str,
        reserved_at: str,
    ) -> AdmissionConsumptionReceipt:
        digest = _digest(
            admission_digest,
            "shared_admission_digest_invalid",
        )
        reservation = {
            "schema_version": LEDGER_SCHEMA,
            "admission_digest": digest,
            "admission_id": _nonblank(
                admission_id, "shared_admission_id_invalid"
            ),
            "scope": _nonblank(scope, "shared_admission_scope_invalid"),
            "run_id": _nonblank(run_id, "shared_admission_run_id_invalid"),
            "attempt_id": _nonblank(
                attempt_id, "shared_admission_attempt_id_invalid"
            ),
            "runtime_identity": _nonblank(
                runtime_identity,
                "shared_admission_runtime_identity_invalid",
            ),
            "state": "reserved",
            "reserved_at": _nonblank(
                reserved_at, "shared_admission_reserved_at_invalid"
            ),
        }
        reservation_digest = canonical_digest(reservation)
        receipt_payload = {
            **reservation,
            "reservation_digest": reservation_digest,
            "terminal_status": None,
            "terminal_phase": None,
            "terminal_code": None,
            "terminal_result_digest": None,
            "finalized_at": None,
        }
        receipt_digest = canonical_digest(receipt_payload)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT state FROM admission_consumptions WHERE admission_digest = ?",
                (digest,),
            ).fetchone()
            if existing is not None:
                connection.rollback()
                raise SharedAdmissionLedgerError(
                    "shared_admission_already_consumed:"
                    + str(existing["state"])
                )
            connection.execute(
                """
                INSERT INTO admission_consumptions (
                    admission_digest, admission_id, scope, run_id, attempt_id,
                    runtime_identity, state, reserved_at, reservation_digest,
                    terminal_status, terminal_phase, terminal_code,
                    terminal_result_digest, finalized_at, receipt_digest
                ) VALUES (?, ?, ?, ?, ?, ?, 'reserved', ?, ?, NULL, NULL, NULL, NULL, NULL, ?)
                """,
                (
                    digest,
                    reservation["admission_id"],
                    reservation["scope"],
                    reservation["run_id"],
                    reservation["attempt_id"],
                    reservation["runtime_identity"],
                    reservation["reserved_at"],
                    reservation_digest,
                    receipt_digest,
                ),
            )
            connection.commit()
        except SharedAdmissionLedgerError:
            raise
        except sqlite3.Error as exc:
            connection.rollback()
            raise SharedAdmissionLedgerError(
                "shared_admission_reservation_store_failure"
            ) from exc
        finally:
            connection.close()
        return self.read(digest)

    def finalize(
        self,
        *,
        admission_digest: str,
        run_id: str,
        attempt_id: str,
        terminal_status: str,
        terminal_phase: str,
        terminal_code: str,
        terminal_result_digest: str,
        finalized_at: str,
    ) -> AdmissionConsumptionReceipt:
        digest = _digest(admission_digest, "shared_admission_digest_invalid")
        run = _nonblank(run_id, "shared_admission_run_id_invalid")
        attempt = _nonblank(
            attempt_id, "shared_admission_attempt_id_invalid"
        )
        terminal_digest = _digest(
            terminal_result_digest,
            "shared_admission_terminal_result_digest_invalid",
        )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM admission_consumptions WHERE admission_digest = ?",
                (digest,),
            ).fetchone()
            if row is None:
                connection.rollback()
                raise SharedAdmissionLedgerError(
                    "shared_admission_reservation_missing"
                )
            if row["state"] != "reserved":
                connection.rollback()
                raise SharedAdmissionLedgerError(
                    "shared_admission_terminal_already_recorded"
                )
            if row["run_id"] != run or row["attempt_id"] != attempt:
                connection.rollback()
                raise SharedAdmissionLedgerError(
                    "shared_admission_execution_binding_mismatch"
                )
            receipt_payload = {
                "schema_version": LEDGER_SCHEMA,
                "admission_digest": digest,
                "admission_id": row["admission_id"],
                "scope": row["scope"],
                "run_id": run,
                "attempt_id": attempt,
                "runtime_identity": row["runtime_identity"],
                "state": "terminal",
                "reserved_at": row["reserved_at"],
                "reservation_digest": row["reservation_digest"],
                "terminal_status": _nonblank(
                    terminal_status,
                    "shared_admission_terminal_status_invalid",
                ),
                "terminal_phase": _nonblank(
                    terminal_phase,
                    "shared_admission_terminal_phase_invalid",
                ),
                "terminal_code": _nonblank(
                    terminal_code,
                    "shared_admission_terminal_code_invalid",
                ),
                "terminal_result_digest": terminal_digest,
                "finalized_at": _nonblank(
                    finalized_at,
                    "shared_admission_finalized_at_invalid",
                ),
            }
            receipt_digest = canonical_digest(receipt_payload)
            connection.execute(
                """
                UPDATE admission_consumptions
                SET state = 'terminal', terminal_status = ?, terminal_phase = ?,
                    terminal_code = ?, terminal_result_digest = ?, finalized_at = ?,
                    receipt_digest = ?
                WHERE admission_digest = ? AND state = 'reserved'
                """,
                (
                    receipt_payload["terminal_status"],
                    receipt_payload["terminal_phase"],
                    receipt_payload["terminal_code"],
                    terminal_digest,
                    receipt_payload["finalized_at"],
                    receipt_digest,
                    digest,
                ),
            )
            connection.commit()
        except SharedAdmissionLedgerError:
            raise
        except sqlite3.Error as exc:
            connection.rollback()
            raise SharedAdmissionLedgerError(
                "shared_admission_terminal_store_failure"
            ) from exc
        finally:
            connection.close()
        return self.read(digest)

    def read(self, admission_digest: str) -> AdmissionConsumptionReceipt:
        digest = _digest(admission_digest, "shared_admission_digest_invalid")
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM admission_consumptions WHERE admission_digest = ?",
                    (digest,),
                ).fetchone()
        except sqlite3.Error as exc:
            raise SharedAdmissionLedgerError(
                "shared_admission_receipt_read_failure"
            ) from exc
        if row is None:
            raise SharedAdmissionLedgerError(
                "shared_admission_receipt_missing"
            )
        receipt = AdmissionConsumptionReceipt(
            admission_digest=row["admission_digest"],
            admission_id=row["admission_id"],
            scope=row["scope"],
            run_id=row["run_id"],
            attempt_id=row["attempt_id"],
            runtime_identity=row["runtime_identity"],
            state=row["state"],
            reserved_at=row["reserved_at"],
            reservation_digest=row["reservation_digest"],
            terminal_status=row["terminal_status"],
            terminal_phase=row["terminal_phase"],
            terminal_code=row["terminal_code"],
            terminal_result_digest=row["terminal_result_digest"],
            finalized_at=row["finalized_at"],
            receipt_digest=row["receipt_digest"],
        )
        payload = receipt.as_dict()
        expected = canonical_digest(
            {key: value for key, value in payload.items() if key != "receipt_digest"}
        )
        if receipt.receipt_digest != expected:
            raise SharedAdmissionLedgerError(
                "shared_admission_receipt_digest_mismatch"
            )
        return receipt
