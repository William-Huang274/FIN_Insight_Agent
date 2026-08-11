"""v2.10 lifecycle kernel shared by production and synthetic adapters.

The kernel owns the authority-event sequence.  Adapters may only supply an
already-classified authority, an isolated root, and a constrained actual-child
leaf.  In particular, no production callback can replace register/consume,
artifact validation, reviewer adjudication, or terminal recovery.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Literal, Mapping

from .m2_a1_audit_oracle import M2A1OracleEvaluation, evaluate_independent_oracle
from .m2_a1_audit_result import M2A1ImmutableActualResult
from .m2_a1_audit_reviewer_gate import M2A1ReviewerGateResult, review_future_actual
from .m2_a1_execution_receipt import (
    M2A1ConsumptionGrant,
    M2A1ExecutionReceipt,
    M2A1ExternalPackageAdmission,
    M2A1ReceiptAuthorityError,
    M2A1ReceiptLedger,
    SyntheticNonhumanAuthorityV2_10,
    V2_10_ADMISSION_SCHEMA,
    V2_10_RECEIPT_SCHEMA,
    ValidatedAuthorityContext,
)
from .models import canonical_digest


Branch = Literal["happy", "corrupt_actual", "reviewer_fail", "exit_after_consume", "missing_oracle", "oracle_write_oserror", "captured_child_nonzero"]
Leaf = Callable[[Path, M2A1ConsumptionGrant], "ChildExecutionOutcome"]
MaterializeAuthority = Callable[[], None]
MaterializeRuntime = Callable[[M2A1ConsumptionGrant, M2A1ReceiptLedger], None]


@dataclass(frozen=True)
class ChildExecutionOutcome:
    """A child outcome that preserves a nonzero incident before returning.

    The shape deliberately exposes only irreversible digests and a relative
    artifact reference.  Raw child streams never leave the isolated runtime
    root through this contract.
    """

    returncode: int
    incident_envelope_digest: str | None = None
    incident_envelope_ref: str | None = None


class ChildExecutionIncidentPersistenceError(RuntimeError):
    """The original child failure remains fail-closed if forensics cannot persist."""

    def __init__(self, *, returncode: int, cause: Exception) -> None:
        self.returncode = returncode
        self.cause = cause
        super().__init__(f"child_execution_incident_persistence_failed:returncode={returncode}:{type(cause).__name__}")


@dataclass(frozen=True)
class M2A1V210LifecycleAdapter:
    """Narrow adapter surface; the kernel keeps all lifecycle authority."""

    adapter_kind: Literal["production_human", "synthetic_nonhuman_fixture"]
    authority_context: ValidatedAuthorityContext
    package: Mapping[str, Any]
    admission: M2A1ExternalPackageAdmission
    receipt: M2A1ExecutionReceipt
    run_root: Path
    authority_root: Path
    ledger_path: Path
    output_path: Path
    preflight_digest: str
    oracle_case: Mapping[str, Any]
    scenario: Mapping[str, Any]
    materialize_authority: MaterializeAuthority
    materialize_runtime: MaterializeRuntime
    actual_leaf: Leaf


@dataclass(frozen=True)
class M2A1V210CoreResult:
    state: str
    receipt_id: str
    admission: M2A1ExternalPackageAdmission
    receipt: M2A1ExecutionReceipt
    grant: M2A1ConsumptionGrant
    terminal_digest: str | None
    actual: M2A1ImmutableActualResult | None
    oracle: M2A1OracleEvaluation | None
    reviewer: M2A1ReviewerGateResult | None
    ledger_path: Path
    artifact_digests: Mapping[str, str]
    route_trace: tuple[str, ...]
    failure_reason: str | None = None


def _scenario() -> dict[str, Any]:
    return {
        "scenario_id": "p01-synthetic-v2-10-execution-proof",
        "input_ref": "m2-a1-v2-8-synthetic-case",
        "mutation": "none",
        "expected_typed_stop": "none",
        "actual_assertions": [],
    }


def _oracle() -> dict[str, Any]:
    return {
        "oracle_case_id": "m2-a1-v2-10-synthetic-oracle",
        "input_case_ref": "m2-a1-v2-8-synthetic-case",
        "expected_selection": {"required_pack_version_ids": ["synthetic-pack:v1"], "forbidden_pack_version_ids": []},
        "required_cells": [{"cell_key": "synthetic.revenue", "owner_role": "EvidenceOperator", "required_evidence_roles": ["issuer_financial"], "forbidden_evidence_roles": []}],
        "forbidden_cells": [],
        "cell_count_range": {"minimum": 1, "maximum": 1},
        "legacy_semantic_loss_expectations": [{"legacy_required_item_id": "legacy-synthetic", "allowed_actions": ["mapped"], "required_information_loss_tags": ["synthetic"]}],
        "must_not_assert": ["synthetic_forbidden_claim"],
    }


def _fixture_package(package_digest: str) -> dict[str, Any]:
    return {
        "package_ref": "point01-m2-a1-v2-10-synthetic-execution-proof-only",
        "package_digest": package_digest,
        "scope": "M2_A1_v2_10_synthetic_nonhuman_fixture_only",
        "authority_boundary": "temporary_sqlite_no_fixed_store_network_model_tool_provider_or_business_case",
        "execution_mode": "external_admission_gated",
    }


def _fixture_context(authority: SyntheticNonhumanAuthorityV2_10) -> ValidatedAuthorityContext:
    if not authority.verify_digest() or authority.authority_class != "synthetic_nonhuman_fixture":
        raise M2A1ReceiptAuthorityError("synthetic_nonhuman_authority_invalid")
    return ValidatedAuthorityContext(
        authority_class="synthetic_nonhuman_fixture",
        authority_digest=authority.fixture_digest,
        reviewer_identity="synthetic/nonhuman-fixture",
        scenario_id=authority.scenario_id,
        source_ref=authority.fixture_id,
        production=False,
    )


def _issue_synthetic_authority(context: ValidatedAuthorityContext, *, package_digest: str, namespace_id: str, now: datetime) -> tuple[M2A1ExternalPackageAdmission, M2A1ExecutionReceipt]:
    if context.production or context.authority_class != "synthetic_nonhuman_fixture":
        raise M2A1ReceiptAuthorityError("synthetic_adapter_requires_nonhuman_context")
    admission = M2A1ExternalPackageAdmission.create(
        admission_ref="synthetic_nonhuman_fixture_only_v2_10", admission_id=f"{context.source_ref}:admission:v1", admission_version=1,
        reviewer_identity=context.reviewer_identity, package_ref="point01-m2-a1-v2-10-synthetic-execution-proof-only",
        executable_package_digest=package_digest, scope="M2_A1_v2_10_synthetic_nonhuman_fixture_only",
        authority_boundary="temporary_sqlite_no_fixed_store_network_model_tool_provider_or_business_case", execution_staging_namespace_id=namespace_id,
        expires_at=now + timedelta(minutes=10), schema_version=V2_10_ADMISSION_SCHEMA, human_approval_digest=context.authority_digest,
    )
    receipt = M2A1ExecutionReceipt.create(
        receipt_id=f"{context.source_ref}:receipt:v1", receipt_version=1, approval_id=context.source_ref, package_ref=admission.package_ref,
        executable_package_digest=package_digest, scope=admission.scope, admission_digest=admission.admission_digest,
        nonce_sha256=canonical_digest({"fixture": context.authority_digest, "kind": "v2_10_nonce_digest_only"}), expires_at=now + timedelta(minutes=5),
        reviewer_identity=admission.reviewer_identity, execution_staging_namespace_id=namespace_id, scenario_id=context.scenario_id,
        schema_version=V2_10_RECEIPT_SCHEMA, human_approval_digest=context.authority_digest,
    )
    return admission, receipt


def _common(adapter: M2A1V210LifecycleAdapter) -> dict[str, Any]:
    return {
        "package_ref": adapter.admission.package_ref,
        "executable_package_digest": adapter.admission.executable_package_digest,
        "scope": adapter.admission.scope,
        "authority_boundary": adapter.admission.authority_boundary,
        "execution_staging_namespace_id": adapter.admission.execution_staging_namespace_id,
        "scenario_id": adapter.receipt.scenario_id,
        "expected_admission_schema_version": V2_10_ADMISSION_SCHEMA,
        "expected_receipt_schema_version": V2_10_RECEIPT_SCHEMA,
        "expected_human_approval_digest": adapter.authority_context.authority_digest,
    }


def _write_verified(path: Path, value: Mapping[str, Any], *, expected_digest: str, digest_field: str) -> str:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, Mapping) or parsed.get(digest_field) != expected_digest:
        raise OSError(f"v2_10_artifact_readback_digest_mismatch:{path.name}")
    return canonical_digest(parsed)


_INCIDENT_EXCERPT_LIMIT = 512
_SOURCE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SENSITIVE_IDENTIFIER = re.compile(r"(?i)(?:api[_-]?key|token|password|secret|authorization|cookie|user-agent|bearer|proxy)")
_SENSITIVE_LABEL = r"(?:api[_-]?key|token|password|secret|authorization|proxy-authorization|cookie|set-cookie|user-agent)"
_REDACTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)((?:proxy-)?authorization\s*:\s*bearer\s+)[^\s,;]+"), r"\1<redacted>"),
    (re.compile(rf"(?i)([\"']?{_SENSITIVE_LABEL}[\"']?\s*[:=]\s*)(\"(?:\\.|[^\"])*\"|'(?:\\.|[^'])*'|[^\s,;}}\]]+)"), r"\1<redacted>"),
    (re.compile(r"(?i)(bearer\s+)[^\s,;]+"), r"\1<redacted>"),
    (re.compile(r"(?i)([?&](?:api[_-]?key|token|password|secret|authorization|access_token|client_secret)=)[^&#\s]+"), r"\1<redacted>"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]+\b"), "<redacted-key>"),
    (re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"), "<redacted-email>"),
)


class ChildExecutionSourceRefsError(ValueError):
    """Raised before spawning a child when provenance could carry unsafe text."""


@dataclass(frozen=True)
class ChildExecutionSourceRefs:
    """Strict, non-secret provenance allowed in a child incident envelope."""

    attempt_ref: str
    receipt_id: str
    receipt_digest: str
    admission_digest: str
    human_approval_digest: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, str]) -> "ChildExecutionSourceRefs":
        expected = {"attempt_ref", "receipt_id", "receipt_digest", "admission_digest", "human_approval_digest"}
        if set(value) != expected:
            raise ChildExecutionSourceRefsError("child_execution_source_refs_exact_keys_required")
        identifiers = {"attempt_ref": value["attempt_ref"], "receipt_id": value["receipt_id"]}
        for name, item in identifiers.items():
            if not isinstance(item, str) or not _SOURCE_IDENTIFIER.fullmatch(item):
                raise ChildExecutionSourceRefsError(f"child_execution_source_ref_identifier_invalid:{name}")
            if _SENSITIVE_IDENTIFIER.search(item) or "://" in item or "=" in item or "/" in item or "\\" in item:
                raise ChildExecutionSourceRefsError(f"child_execution_source_ref_identifier_forbidden:{name}")
        digests = {key: value[key] for key in expected - {"attempt_ref", "receipt_id"}}
        for name, item in digests.items():
            if not isinstance(item, str) or not re.fullmatch(r"[0-9a-f]{64}", item):
                raise ChildExecutionSourceRefsError(f"child_execution_source_ref_digest_invalid:{name}")
        return cls(**{key: value[key] for key in sorted(expected)})

    def as_mapping(self) -> dict[str, str]:
        return {
            "attempt_ref": self.attempt_ref,
            "receipt_id": self.receipt_id,
            "receipt_digest": self.receipt_digest,
            "admission_digest": self.admission_digest,
            "human_approval_digest": self.human_approval_digest,
        }


def _redacted_excerpt(stream: str | None) -> Mapping[str, Any]:
    """Bounded sanitizer, not a claim of universal secret removal.

    It removes the supported credential/header/query shapes, redacts paths and
    emails, and never persists raw streams.  Unknown unsafe line shapes are
    replaced wholesale rather than risking a value-preserving best effort.
    """

    value = stream or ""
    if not value:
        return {"capture_status": "empty", "raw_length": 0, "excerpt": ""}
    redacted_lines: list[str] = []
    for line in value.splitlines(keepends=True):
        redacted = line
        for pattern, replacement in _REDACTION_PATTERNS:
            redacted = pattern.sub(replacement, redacted)
        # Avoid retaining host-local paths; paths can encode user names or secrets.
        redacted = re.sub(r"(?i)(?:[A-Z]:\\|(?<![:/])/(?!/))[^\s\r\n]+", "<redacted-path>", redacted)
        if _SENSITIVE_IDENTIFIER.search(redacted) and "<redacted>" not in redacted:
            redacted = "<redacted-sensitive-line>\n" if line.endswith(("\n", "\r")) else "<redacted-sensitive-line>"
        redacted_lines.append(redacted)
    redacted = "".join(redacted_lines)
    truncated = len(redacted) > _INCIDENT_EXCERPT_LIMIT
    excerpt = redacted[:_INCIDENT_EXCERPT_LIMIT]
    if truncated:
        excerpt += "<truncated>"
    return {
        "capture_status": "captured_redacted_truncated" if truncated else "captured_redacted",
        "raw_length": len(value),
        "excerpt": excerpt,
    }


def _argv_shape(argv: list[str]) -> Mapping[str, Any]:
    """Hash argument shape, never individual values such as paths or secrets."""

    roles: list[str] = []
    for index, token in enumerate(argv):
        if index == 0:
            roles.append("interpreter")
        elif token == "--":
            roles.append("separator")
        elif token.startswith("--"):
            flag_name = token.split("=", 1)[0]
            roles.append(f"long_flag:{flag_name}")
        elif token.startswith("-"):
            roles.append("short_flag")
        else:
            roles.append("value")
    return {"argument_count": len(argv), "roles": roles}


def capture_child_execution_outcome(
    *,
    argv: list[str],
    incident_path: Path,
    stage: str,
    source_refs: Mapping[str, str],
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    now: datetime | None = None,
) -> ChildExecutionOutcome:
    """Run one child and durably capture a sanitized envelope on nonzero exit.

    This is intentionally the first producer that sees a nonzero child return.
    If persistence fails, the parent receives a typed exception rather than a
    deceptively successful outcome or a swallowed child failure.
    """

    refs = ChildExecutionSourceRefs.from_mapping(source_refs)
    completed = runner(argv, check=False, capture_output=True, text=True)
    if completed.returncode == 0:
        return ChildExecutionOutcome(returncode=0)
    try:
        shape = _argv_shape(argv)
        envelope: dict[str, Any] = {
            "schema_version": "finsight_point01_child_execution_incident_envelope_v1_0",
            "stage": stage,
            "returncode": int(completed.returncode),
            "argv_shape_digest": canonical_digest(shape),
            "stdout_digest": hashlib.sha256((completed.stdout or "").encode("utf-8")).hexdigest(),
            "stderr_digest": hashlib.sha256((completed.stderr or "").encode("utf-8")).hexdigest(),
            "stdout_capture": _redacted_excerpt(completed.stdout),
            "stderr_capture": _redacted_excerpt(completed.stderr),
            "exception_type": None,
            "exception_stage": "child_process_returned_nonzero",
            "created_at": (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(),
            "source_refs": refs.as_mapping(),
        }
        envelope["incident_envelope_digest"] = canonical_digest(envelope)
        incident_path.parent.mkdir(parents=True, exist_ok=True)
        _write_verified(
            incident_path,
            envelope,
            expected_digest=str(envelope["incident_envelope_digest"]),
            digest_field="incident_envelope_digest",
        )
    except Exception as exc:
        raise ChildExecutionIncidentPersistenceError(returncode=int(completed.returncode), cause=exc) from exc
    return ChildExecutionOutcome(
        returncode=int(completed.returncode),
        incident_envelope_digest=str(envelope["incident_envelope_digest"]),
        incident_envelope_ref=incident_path.name,
    )


def _recover_by_known_authority_root(
    adapter: M2A1V210LifecycleAdapter,
    receipt_id: str,
    *,
    incident_envelope_digest: str | None = None,
    incident_envelope_ref: str | None = None,
) -> str | None:
    """Recover without retaining the pre-consume ledger object in memory."""

    try:
        reopened = M2A1ReceiptLedger.open_existing(adapter.ledger_path, approved_authority_root=adapter.authority_root)
        return reopened.recover_consumed_without_terminal(
            receipt_id,
            incident_envelope_digest=incident_envelope_digest,
            incident_envelope_ref=incident_envelope_ref,
        )
    except M2A1ReceiptAuthorityError:
        return None


def _validate_adapter(adapter: M2A1V210LifecycleAdapter) -> None:
    if adapter.adapter_kind == "production_human":
        adapter.authority_context.require_production()
    elif adapter.adapter_kind == "synthetic_nonhuman_fixture":
        if adapter.authority_context.production or adapter.authority_context.authority_class != "synthetic_nonhuman_fixture":
            raise M2A1ReceiptAuthorityError("synthetic_adapter_authority_context_invalid")
    else:  # pragma: no cover - Literal is still defended at runtime
        raise M2A1ReceiptAuthorityError("v2_10_adapter_kind_invalid")
    if adapter.receipt.human_approval_digest != adapter.authority_context.authority_digest or adapter.admission.human_approval_digest != adapter.authority_context.authority_digest:
        raise M2A1ReceiptAuthorityError("v2_10_adapter_authority_lineage_mismatch")


def execute_approved_window_kernel(
    *, adapter: M2A1V210LifecycleAdapter, artifact_writer: Callable[[Path, Mapping[str, Any], str, str], str] | None = None,
) -> M2A1V210CoreResult:
    """The only v2.10 register→terminal lifecycle graph.

    Production and fixture adapters cannot replace this sequence.  They only
    select classified authority/root/leaf dependencies before entry.
    """

    _validate_adapter(adapter)
    writer = artifact_writer or (lambda path, value, digest, field: _write_verified(path, value, expected_digest=digest, digest_field=field))
    trace: list[str] = ["classified_authority"]
    artifacts: dict[str, str] = {}
    ledger: M2A1ReceiptLedger | None = None
    grant: M2A1ConsumptionGrant | None = None
    child_outcome: ChildExecutionOutcome | None = None
    try:
        adapter.materialize_authority()
        trace.append("authority_root_materialized")
        ledger = M2A1ReceiptLedger.create_for_registration(adapter.ledger_path, approved_authority_root=adapter.authority_root)
        ledger.register(adapter.receipt, admission=adapter.admission, **_common(adapter))
        trace.append("REGISTERED")
        grant = ledger.consume_before_run(
            adapter.receipt.receipt_id, admission=adapter.admission,
            preflight_digest=adapter.preflight_digest,
            run_root=adapter.run_root, **_common(adapter),
        )
        trace.append("CONSUMED_BEFORE_RUN")
        adapter.materialize_runtime(grant, ledger)
        trace.append("runtime_materialized")
        # No code below may assume the in-memory ledger survives a child or
        # adapter failure.  Recovery reopens by the known authority root.
        child_outcome = adapter.actual_leaf(adapter.output_path, grant)
        if child_outcome.incident_envelope_digest is not None:
            artifacts["child_execution_incident"] = child_outcome.incident_envelope_digest
            trace.append("child_execution_incident_envelope_persisted")
        if child_outcome.returncode != 0:
            ledger = None
            raise RuntimeError("v2_10_actual_leaf_nonzero_after_consume")
        trace.append("parent_clean_child_leaf_completed")
        actual = M2A1ImmutableActualResult.model_validate(json.loads(adapter.output_path.read_text(encoding="utf-8")))
        state_ledger = M2A1ReceiptLedger.open_existing(adapter.ledger_path, approved_authority_root=adapter.authority_root)
        state = state_ledger.state(adapter.receipt.receipt_id)
        if state is None or not actual.verify_immutable_digest() or actual.executable_package_digest != adapter.admission.executable_package_digest or actual.scenario_id != adapter.receipt.scenario_id or actual.admission_digest != adapter.admission.admission_digest or actual.consumed_receipt_digest != state.get("receipt_digest"):
            raise ValueError("v2_10_actual_binding_invalid")
        artifacts["actual"] = _write_verified(adapter.output_path, actual.model_dump(mode="json"), expected_digest=actual.actual_result_digest, digest_field="actual_result_digest")
        trace.append("actual_validated")
        consumed = state_ledger.verify_consumption_grant(
            grant, admission=adapter.admission, run_root=adapter.run_root,
            preflight_digest=grant.preflight_digest, **_common(adapter),
        )
        if adapter.scenario.get("force_missing_oracle") is True:
            raise StopIteration("v2_10_missing_oracle")
        oracle = evaluate_independent_oracle(actual, adapter.oracle_case, adapter.scenario)
        artifacts["oracle"] = writer(adapter.output_path.parent / "oracle_evaluation.json", oracle.model_dump(mode="json"), oracle.evaluation_digest, "evaluation_digest")
        trace.append("oracle_artifact_verified")
        reviewer = review_future_actual(
            package=adapter.package, actual_results=(actual,), oracle_evaluations=(oracle,), expected_scenario_ids=(adapter.receipt.scenario_id,),
            admission=adapter.admission, consumed_receipt=consumed, receipt_ledger_state=state, receipt_terminal_event_digest=None,
            require_terminal_event=False, expected_human_approval_digest=adapter.authority_context.authority_digest,
        )
        artifacts["reviewer"] = writer(adapter.output_path.parent / "reviewer_gate.json", reviewer.model_dump(mode="json"), reviewer.gate_digest, "gate_digest")
        trace.append("reviewer_artifact_verified")
        if reviewer.status != "pass":
            raise ValueError("v2_10_real_reviewer_fail_closed")
        terminal = state_ledger.record_terminal_event(
            adapter.receipt.receipt_id, terminal_status="succeeded" if actual.actual_status == "succeeded" else "typed_stop",
            actual_result_digest=actual.actual_result_digest, oracle_evaluation_digest=oracle.evaluation_digest,
            reviewer_gate_digest=reviewer.gate_digest, expected_human_approval_digest=adapter.authority_context.authority_digest,
        )
        state_ledger.verify_terminal_event(adapter.receipt.receipt_id, expected_human_approval_digest=adapter.authority_context.authority_digest, expected_actual_result_digest=actual.actual_result_digest, expected_oracle_evaluation_digest=oracle.evaluation_digest, expected_reviewer_gate_digest=reviewer.gate_digest)
        trace.append("TERMINAL_succeeded")
        return M2A1V210CoreResult("succeeded", adapter.receipt.receipt_id, adapter.admission, adapter.receipt, grant, terminal, actual, oracle, reviewer, adapter.ledger_path, artifacts, tuple(trace))
    except Exception as exc:
        terminal = _recover_by_known_authority_root(
            adapter,
            adapter.receipt.receipt_id,
            incident_envelope_digest=child_outcome.incident_envelope_digest if child_outcome else None,
            incident_envelope_ref=child_outcome.incident_envelope_ref if child_outcome else None,
        )
        trace.append("reopen_known_authority_root_outcome_unknown" if terminal else "recovery_unavailable")
        if grant is None:
            raise
        return M2A1V210CoreResult("outcome_unknown", adapter.receipt.receipt_id, adapter.admission, adapter.receipt, grant, terminal, None, None, None, adapter.ledger_path, artifacts, tuple(trace), str(exc))


def _v2_10_synthetic_leaf(parent: Path, *, admission: M2A1ExternalPackageAdmission, receipt: M2A1ExecutionReceipt, branch: Branch) -> Leaf:
    mode = {"happy": "happy", "corrupt_actual": "corrupt", "reviewer_fail": "reviewer_fail", "exit_after_consume": "exit_after_consume", "missing_oracle": "happy", "oracle_write_oserror": "happy"}.get(branch)

    def run(output: Path, grant: M2A1ConsumptionGrant) -> ChildExecutionOutcome:
        if branch == "captured_child_nonzero":
            return capture_child_execution_outcome(
                argv=[sys.executable, "-c", "import sys; print('token=synthetic-secret'); print('contact=fixture@example.test', file=sys.stderr); sys.exit(17)"],
                incident_path=output.parent / "child_execution_incident.json",
                stage="synthetic_deterministic_failed_child_fixture",
                source_refs={
                    "attempt_ref": receipt.scenario_id,
                    "receipt_id": receipt.receipt_id,
                    "receipt_digest": receipt.receipt_digest,
                    "admission_digest": admission.admission_digest,
                    "human_approval_digest": receipt.human_approval_digest,
                },
            )
        if mode is None:  # pragma: no cover - Literal is guarded for runtime callers.
            raise ValueError("v2_10_synthetic_leaf_branch_invalid")
        completed = subprocess.run(
            [sys.executable, str(parent), "--", "--execute-kernel-leaf", "--leaf-kind", "synthetic_fixture", "--output", str(output), "--package-digest", admission.executable_package_digest, "--admission-digest", admission.admission_digest, "--receipt-digest", grant.consumed_receipt_digest, "--scenario-id", receipt.scenario_id, "--mode", mode],
            capture_output=True, text=True, check=False,
        )
        return ChildExecutionOutcome(returncode=completed.returncode)

    return run


def execute_synthetic_nonhuman_v2_10_fixture(
    *, temporary_root: Path, parent: Path, package_digest: str, branch: Branch = "happy", artifact_writer: Callable[[Path, Mapping[str, Any], str, str], str] | None = None,
) -> M2A1V210CoreResult:
    """Run all four branches through the v2.10 kernel and parent/child route."""

    scenario = _scenario()
    if branch == "missing_oracle":
        scenario = {**scenario, "force_missing_oracle": True}
    authority = SyntheticNonhumanAuthorityV2_10.create(package_digest=package_digest, scenario_id=scenario["scenario_id"])
    context = _fixture_context(authority)
    admission, receipt = _issue_synthetic_authority(context, package_digest=package_digest, namespace_id="synthetic_nonhuman_fixture_namespace_v2_10", now=datetime.now(timezone.utc))
    run_root = temporary_root / "v2_10_synthetic_execution_proof_run"
    authority_root = run_root / "authority"

    def materialize_authority() -> None:
        authority_root.mkdir(parents=True, exist_ok=False)

    def materialize_runtime(_grant: M2A1ConsumptionGrant, _ledger: M2A1ReceiptLedger) -> None:
        (run_root / "output").mkdir(parents=True, exist_ok=False)

    adapter = M2A1V210LifecycleAdapter(
        adapter_kind="synthetic_nonhuman_fixture", authority_context=context, package=_fixture_package(package_digest), admission=admission, receipt=receipt,
        run_root=run_root, authority_root=authority_root, ledger_path=authority_root / "m2_a1_execution_receipts.sqlite", output_path=run_root / "output" / "actual.json",
        preflight_digest=canonical_digest({"authority_digest": context.authority_digest, "receipt_digest": receipt.receipt_digest, "stage": "v2_10_kernel_preflight"}),
        oracle_case=_oracle(), scenario=scenario, materialize_authority=materialize_authority, materialize_runtime=materialize_runtime,
        actual_leaf=_v2_10_synthetic_leaf(parent, admission=admission, receipt=receipt, branch=branch),
    )
    return execute_approved_window_kernel(adapter=adapter, artifact_writer=artifact_writer)


def make_production_v2_10_adapter(
    *, authority_context: ValidatedAuthorityContext, package: Mapping[str, Any], admission: M2A1ExternalPackageAdmission,
    receipt: M2A1ExecutionReceipt, preflight: Any, oracle_case: Mapping[str, Any], scenario: Mapping[str, Any], parent: Path,
) -> M2A1V210LifecycleAdapter:
    """Build a production adapter without giving it lifecycle replacement power."""

    authority_context.require_production()

    def materialize_authority() -> None:
        preflight.materialize_authority_for_registration()

    def materialize_runtime(grant: M2A1ConsumptionGrant, ledger: M2A1ReceiptLedger) -> None:
        preflight.reverify_current_execution_tree()
        preflight.verify_consumption_grant_before_runtime(grant, ledger=ledger)
        preflight.materialize_runtime_after_consumption(grant, ledger=ledger)

    def run_leaf(output: Path, grant: M2A1ConsumptionGrant) -> ChildExecutionOutcome:
        admission_path = preflight.authority_root / "admission.json"
        grant_path = preflight.authority_root / "consumption_grant.json"
        admission_path.write_text(json.dumps(admission.model_dump(mode="json"), sort_keys=True) + "\n", encoding="utf-8")
        grant_path.write_text(json.dumps(grant.model_dump(mode="json"), sort_keys=True) + "\n", encoding="utf-8")
        return capture_child_execution_outcome(
            argv=[sys.executable, str(parent), "--", "--execute-kernel-leaf", "--leaf-kind", "production_actual", "--output", str(output), "--admission", str(admission_path), "--grant", str(grant_path), "--receipt-id", receipt.receipt_id, "--scenario-id", receipt.scenario_id, "--human-approval-digest", authority_context.authority_digest],
            incident_path=output.parent / "child_execution_incident.json",
            stage="production_actual_clean_child",
            source_refs={
                "attempt_ref": receipt.scenario_id,
                "receipt_id": receipt.receipt_id,
                "receipt_digest": receipt.receipt_digest,
                "admission_digest": admission.admission_digest,
                "human_approval_digest": authority_context.authority_digest,
            },
        )

    return M2A1V210LifecycleAdapter(
        adapter_kind="production_human", authority_context=authority_context, package=package, admission=admission, receipt=receipt,
        run_root=preflight.run_root, authority_root=preflight.authority_root, ledger_path=preflight.ledger_path, output_path=preflight.output_path,
        preflight_digest=preflight.preflight_digest,
        oracle_case=oracle_case, scenario=scenario, materialize_authority=materialize_authority, materialize_runtime=materialize_runtime, actual_leaf=run_leaf,
    )
