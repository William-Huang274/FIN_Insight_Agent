"""Admission-gated future actual runner for the M2-A1 adversarial audit.

The runner is intentionally usable only after a package-external reviewer
admission and atomic receipt consumption.  Its public compatibility entrypoint
remains denied in this execution point; ``execute_admitted_scenario`` contains
the future real M2 adapter/registry/selection/planning/serializer/shadow path
but is not invoked by this repair tranche.
"""

from __future__ import annotations

import importlib
import json
import hashlib
import os
import socket
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .m2_a1_audit_canary import (
    M2A1AuditCanary,
    M2A1ModelAdmissionError,
    M2A1OracleLeakageError,
    M2A1StoreAccessError,
    M2A1TransportAccessError,
)
from .m2_a1_audit_result import (
    M2A1ActualCellProjection,
    M2A1ArtifactReplayProjection,
    M2A1ImmutableActualResult,
    M2A1PackLineageProjection,
    M2A1SemanticLossProjection,
)
from .m2_a1_execution_receipt import (
    M2A1ExecutionPreflight,
    M2A1ExecutionReceipt,
    M2A1ExternalPackageAdmission,
    M2A1ReceiptLedger,
    validate_external_admission,
)
from .models import StrictModel, canonical_digest


ROOT = Path(__file__).resolve().parents[3]


class M2A1AssemblyError(ValueError):
    """Typed failure for a corpus/adapter/seed assembly inconsistency."""


class M2A1ActualExecutionNotAdmitted(RuntimeError):
    """No external admission/receipt was present before a compiler call."""


class M2A1ScenarioExecutionError(RuntimeError):
    """An actual M2 runtime branch terminated in a deterministic typed stop."""


class M2A1AssemblyProof(StrictModel):
    case_id: str
    compiler_policy_ref: str
    pack_registry_policy_ref: str
    required_cell_count: int
    adapter_output_pack_selection_empty: bool
    compiler_input_digest: str
    pack_selection_digest: str
    case_delta_pack_refs: tuple[str, ...] = ()
    case_delta_payload_digest: str | None = None
    assembly_digest: str
    compiler_or_shadow_fixture_runs: int = 0
    model_calls: int = 0
    network_requests: int = 0
    external_tool_calls: int = 0
    provider_calls: int = 0
    store_writes: int = 0


class M2A1AssemblyPreflight(StrictModel):
    case_id: str
    temporary_root: str
    proof: M2A1AssemblyProof
    execution_status: str = "preflight_assembly_only_actual_probes_not_authorized"


def _mapping(value: Any, *, error: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise M2A1AssemblyError(error)
    return value


def _tuple_strings(value: Any, *, error: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise M2A1AssemblyError(error)
    return tuple(value)


def _exact_seed_selection(seed: Mapping[str, Any], pack_versions: tuple[Any, ...]) -> Any:
    # Kept inside the callable so importing the future actual runner cannot
    # import compiler/pack runtime before an admitted execution crosses its
    # receipt gate.
    from .planning_service import PackSelectionDecision

    raw_selection = _mapping(seed.get("pack_selection"), error="compiler_input_seed_pack_selection_missing")
    expected_fields = {"universal_pack_refs", "sector_pack_refs", "report_type_pack_refs", "case_delta_pack_refs"}
    if set(raw_selection) != expected_fields:
        raise M2A1AssemblyError("compiler_input_seed_pack_selection_shape_invalid")
    selection = PackSelectionDecision.model_validate(raw_selection)
    available = {version.pack_version_id for version in pack_versions}
    refs_by_scope = {
        "universal": selection.universal_pack_refs,
        "sector": selection.sector_pack_refs,
        "report_type": selection.report_type_pack_refs,
        "case_delta": selection.case_delta_pack_refs,
    }
    for scope_kind, refs in refs_by_scope.items():
        if any(ref not in available for ref in refs):
            raise M2A1AssemblyError(f"pack_selection_ref_not_in_metadata:{scope_kind}")
        for ref in refs:
            version = next(version for version in pack_versions if version.pack_version_id == ref)
            if version.scope_kind != scope_kind:
                raise M2A1AssemblyError(f"pack_selection_scope_mismatch:{scope_kind}:{ref}")
    return selection


def _validate_pack_metadata(case: Mapping[str, Any], *, seed: Mapping[str, Any], pack_registry_policy_ref: str) -> tuple[Any, ...]:
    from .pack_registry import PlanningPackRegistryError, PlanningPackVersion, validate_case_delta_payload

    metadata = _mapping(case.get("pack_version_metadata"), error="pack_version_metadata_missing")
    if metadata.get("registry_policy_ref") != pack_registry_policy_ref:
        raise M2A1AssemblyError("pack_registry_policy_ref_mismatch")
    raw_versions = metadata.get("versions")
    if not isinstance(raw_versions, list) or not raw_versions:
        raise M2A1AssemblyError("pack_version_metadata_versions_missing")
    versions = tuple(PlanningPackVersion.model_validate(value) for value in raw_versions)
    if len({version.pack_version_id for version in versions}) != len(versions):
        raise M2A1AssemblyError("pack_version_metadata_duplicate_version")
    is_current_baseline = case.get("case_id") == "m2-a1-ai-semis-input"
    expected_scopes = {"universal", "sector", "report_type", "case_delta"} if is_current_baseline else {"universal", "sector", "report_type"}
    if {version.scope_kind for version in versions} != expected_scopes:
        raise M2A1AssemblyError("pack_version_metadata_scope_coverage_invalid")
    sector = str(seed.get("sector") or "")
    report_type = str(seed.get("report_type") or "")
    if not any(version.scope_kind == "sector" and version.sector == sector for version in versions):
        raise M2A1AssemblyError("pack_metadata_sector_mismatch")
    if not any(version.scope_kind == "report_type" and version.report_type == report_type for version in versions):
        raise M2A1AssemblyError("pack_metadata_report_type_mismatch")
    if is_current_baseline:
        raw_selection = _mapping(seed.get("pack_selection"), error="compiler_input_seed_pack_selection_missing")
        case_delta_refs = _tuple_strings(raw_selection.get("case_delta_pack_refs"), error="case_delta_pack_lineage_missing")
        if len(case_delta_refs) != 1:
            raise M2A1AssemblyError("case_delta_pack_lineage_cardinality_invalid")
        case_delta = next((version for version in versions if version.pack_version_id == case_delta_refs[0]), None)
        if case_delta is None or case_delta.scope_kind != "case_delta":
            raise M2A1AssemblyError("case_delta_pack_lineage_missing")
        try:
            validate_case_delta_payload(
                case_delta,
                expected_case_id=str(case["case_id"]),
            )
        except PlanningPackRegistryError as exc:
            raise M2A1AssemblyError(str(exc)) from exc
    return versions


def assemble_compiler_input_contract(
    corpus_case: Mapping[str, Any],
    *,
    compiler_policy_ref: str,
    pack_registry_policy_ref: str,
) -> tuple[Any, M2A1AssemblyProof]:
    """Explicitly merge empty adapter selection plus immutable seed selection."""

    from .legacy_objective_adapter import adapt_legacy_research_objective
    from .planning_service import CompilerInputContract, PackSelectionDecision

    case = _mapping(corpus_case, error="corpus_case_not_mapping")
    scope = _mapping(case.get("case_scope"), error="case_scope_missing")
    seed = _mapping(case.get("compiler_input_seed"), error="compiler_input_seed_missing")
    legacy = _mapping(case.get("legacy_research_objective"), error="legacy_research_objective_missing")
    legacy_payload = _mapping(legacy.get("payload"), error="legacy_payload_missing")
    required_scope_fields = {"tenant_id", "project_id", "case_id", "actor_snapshot_ref", "permission_snapshot_ref", "correlation_id", "created_at", "recorded_at"}
    if set(scope) != required_scope_fields or scope.get("case_id") != case.get("case_id"):
        raise M2A1AssemblyError("case_scope_contract_mismatch")
    if legacy.get("adapter_function") != "adapt_legacy_research_objective":
        raise M2A1AssemblyError("legacy_adapter_function_mismatch")
    if seed.get("compiler_policy_ref") != compiler_policy_ref:
        raise M2A1AssemblyError("compiler_policy_ref_mismatch")
    if seed.get("required_cells_source") != "legacy_research_objective.payload.required_items_via_adapter":
        raise M2A1AssemblyError("required_cells_source_invalid")
    for field in ("query", "as_of", "universe", "language"):
        if seed.get(field) != legacy_payload.get(field):
            raise M2A1AssemblyError(f"seed_legacy_field_mismatch:{field}")
    universe = _tuple_strings(seed.get("universe"), error="compiler_input_seed_universe_invalid")
    versions = _validate_pack_metadata(case, seed=seed, pack_registry_policy_ref=pack_registry_policy_ref)
    selection = _exact_seed_selection(seed, versions)
    if case.get("case_id") == "m2-a1-ai-semis-input":
        from .pack_registry import PlanningPackRegistryError, validate_case_delta_payload

        case_delta = next(version for version in versions if version.pack_version_id == selection.case_delta_pack_refs[0])
        try:
            validate_case_delta_payload(
                case_delta,
                expected_case_id=str(case["case_id"]),
                expected_base_pack_refs={
                    "universal_pack_refs": selection.universal_pack_refs,
                    "sector_pack_refs": selection.sector_pack_refs,
                    "report_type_pack_refs": selection.report_type_pack_refs,
                },
            )
        except PlanningPackRegistryError as exc:
            raise M2A1AssemblyError(str(exc)) from exc
    adapted = adapt_legacy_research_objective(
        legacy_payload,
        tenant_id=str(scope["tenant_id"]),
        project_id=str(scope["project_id"]),
        case_id=str(scope["case_id"]),
        compiler_policy_ref=compiler_policy_ref,
    )
    adapter_selection_empty = adapted.pack_selection == PackSelectionDecision()
    if not adapter_selection_empty:
        raise M2A1AssemblyError("legacy_adapter_pack_selection_must_be_empty_before_explicit_merge")
    if (
        adapted.tenant_id != scope["tenant_id"]
        or adapted.project_id != scope["project_id"]
        or adapted.case_id != scope["case_id"]
        or adapted.query != seed["query"]
        or adapted.as_of.isoformat().replace("+00:00", "Z") != str(seed["as_of"])
        or adapted.universe != universe
        or adapted.language != seed["language"]
        or adapted.compiler_policy_ref != compiler_policy_ref
    ):
        raise M2A1AssemblyError("legacy_adapter_output_field_mismatch")
    if len(adapted.required_cells) != len(legacy_payload.get("required_items") or ()) or len(adapted.required_cells) < int(seed.get("required_cells_minimum") or 0):
        raise M2A1AssemblyError("legacy_adapter_required_cells_mismatch")
    assembled = CompilerInputContract(
        tenant_id=adapted.tenant_id,
        project_id=adapted.project_id,
        case_id=adapted.case_id,
        query=adapted.query,
        as_of=adapted.as_of,
        universe=adapted.universe,
        language=adapted.language,
        compiler_policy_ref=adapted.compiler_policy_ref,
        pack_selection=selection,
        required_cells=adapted.required_cells,
    )
    compiler_input_payload = assembled.model_dump(mode="json")
    proof_payload = {
        "case_id": assembled.case_id,
        "compiler_policy_ref": compiler_policy_ref,
        "pack_registry_policy_ref": pack_registry_policy_ref,
        "required_cell_count": len(assembled.required_cells),
        "adapter_output_pack_selection_empty": adapter_selection_empty,
        "compiler_input_digest": canonical_digest(compiler_input_payload),
        "pack_selection_digest": canonical_digest(selection.model_dump(mode="json")),
        "case_delta_pack_refs": selection.case_delta_pack_refs,
        "case_delta_payload_digest": next(
            version.payload_digest for version in versions if version.pack_version_id == selection.case_delta_pack_refs[0]
        )
        if selection.case_delta_pack_refs
        else None,
    }
    proof = M2A1AssemblyProof(**proof_payload, assembly_digest=canonical_digest(proof_payload))
    return assembled, proof


def _policy(relative_path: str, cls: Any) -> Any:
    raw = json.loads((ROOT / relative_path).read_text(encoding="utf-8"))
    return cls.model_validate({key: value for key, value in raw.items() if key not in {"policy_version", "authority_boundary", "registry_version", "ontology_version"}})


def _scenario_id(scenario: Mapping[str, Any]) -> str:
    value = str(scenario.get("scenario_id") or "")
    if not value:
        raise M2A1ScenarioExecutionError("scenario_id_missing")
    return value


class M2A1ActualRunner:
    """Future actual runner.  No caller can cross its receipt gate implicitly."""

    def __init__(
        self,
        *,
        corpus_case: Mapping[str, Any],
        compiler_policy_ref: str,
        pack_registry_policy_ref: str,
        temporary_root: Path,
        canary: M2A1AuditCanary,
    ) -> None:
        self._corpus_case = corpus_case
        self._compiler_policy_ref = compiler_policy_ref
        self._pack_registry_policy_ref = pack_registry_policy_ref
        self._temporary_root = temporary_root
        self._canary = canary

    def preflight_assembly(self) -> M2A1AssemblyPreflight:
        """Deny standalone assembly: the real path starts after receipt consumption.

        A caller that only wants to inspect an unadmitted package must use its
        static manifest.  Allowing this method to adapt or validate a corpus
        would import compiler-side modules outside the precise authority gate.
        """

        raise M2A1ActualExecutionNotAdmitted("m2_a1_preflight_assembly_requires_exact_admission_and_single_use_receipt")

    def execute_actual_probes(self) -> None:
        """Compatibility entrypoint: this repair point still cannot bulk-run probes."""

        raise M2A1ActualExecutionNotAdmitted("m2_a1_actual_probes_not_authorized")

    def execute_admitted_scenario(
        self,
        *,
        scenario: Mapping[str, Any],
        package: Mapping[str, Any],
        admission: M2A1ExternalPackageAdmission | None,
        receipt_ledger: M2A1ReceiptLedger | None,
        receipt_id: str | None,
        execution_preflight: M2A1ExecutionPreflight | None,
    ) -> M2A1ImmutableActualResult:
        """Deny the legacy combined entrypoint.

        v2.2 deliberately splits registration, no-create ledger opening and
        atomic consumption from runtime construction.  Keeping a convenience
        path that can consume a receipt and call M2 in one method would make it
        too easy for callers to bypass that lifecycle.
        """

        raise M2A1ActualExecutionNotAdmitted("m2_a1_receipt_lifecycle_requires_consumed_executor")

    def execute_consumed_scenario(
        self,
        *,
        scenario: Mapping[str, Any],
        package: Mapping[str, Any],
        admission: M2A1ExternalPackageAdmission | None,
        receipt_ledger: M2A1ReceiptLedger | None,
        consumed_receipt: M2A1ExecutionReceipt | None,
        execution_preflight: M2A1ExecutionPreflight | None,
    ) -> M2A1ImmutableActualResult:
        """Run only after the executor has atomically consumed an existing receipt.

        The CLI performs the authority-only lifecycle before importing this
        module.  This method therefore cannot create a ledger or turn an active
        receipt into a consumed receipt; it accepts only the immutable consumed
        state whose scenario and namespace are already exact-bound.
        """

        if execution_preflight is None:
            raise M2A1ActualExecutionNotAdmitted("m2_a1_execution_preflight_required")
        if execution_preflight.package is not package:
            raise M2A1ActualExecutionNotAdmitted("m2_a1_execution_preflight_package_identity_mismatch")
        if dict(scenario) != dict(execution_preflight.runtime_scenario):
            raise M2A1ActualExecutionNotAdmitted("m2_a1_execution_preflight_scenario_mismatch")
        if execution_preflight.corpus_case is not self._corpus_case:
            raise M2A1ActualExecutionNotAdmitted("m2_a1_execution_preflight_corpus_identity_mismatch")
        if self._temporary_root.resolve() != execution_preflight.runtime_root.resolve():
            raise M2A1ActualExecutionNotAdmitted("m2_a1_execution_preflight_runtime_root_mismatch")
        if receipt_ledger is None or receipt_ledger.db_path.absolute() != execution_preflight.ledger_path.absolute():
            raise M2A1ActualExecutionNotAdmitted("m2_a1_execution_preflight_ledger_path_mismatch")
        if consumed_receipt is None or consumed_receipt.receipt_id != execution_preflight.receipt_id:
            raise M2A1ActualExecutionNotAdmitted("m2_a1_execution_preflight_consumed_receipt_mismatch")
        if consumed_receipt.state != "consumed_before_run" or consumed_receipt.scenario_id != execution_preflight.scenario_id:
            raise M2A1ActualExecutionNotAdmitted("m2_a1_execution_consumed_receipt_state_or_scenario_mismatch")
        package_ref = str(package.get("package_ref") or "")
        package_digest = str(package.get("package_digest") or "")
        scope = str(package.get("scope") or "")
        authority_boundary = str(package.get("authority_boundary") or "")
        if package.get("execution_mode") != "external_admission_gated":
            raise M2A1ActualExecutionNotAdmitted("m2_a1_package_execution_mode_not_external_admission_gated")
        admission_check = validate_external_admission(
            admission,
            package_ref=package_ref,
            executable_package_digest=package_digest,
            scope=scope,
            authority_boundary=authority_boundary,
            execution_staging_namespace_id=execution_preflight.admission.execution_staging_namespace_id,
        )
        if admission_check["status"] != "pass" or admission is None:
            raise M2A1ActualExecutionNotAdmitted(str(admission_check["status"]))
        self._canary.require_temporary_root(self._temporary_root)
        result: M2A1ImmutableActualResult
        try:
            # The clean executor owns the post-consume staged-tree reverify
            # before it imports this business module.  Module presence is an
            # auditable context observation; constructors/connects/requests
            # remain fail-closed inside the canary.
            self._canary.observe_transport_module_presence()
            if self._canary.instrumentation_active:
                result = self._execute_after_consumption(
                    scenario=scenario,
                    package_digest=package_digest,
                    admission=admission,
                    consumed_receipt=consumed_receipt,
                )
            else:
                with self._canary.instrument():
                    result = self._execute_after_consumption(
                        scenario=scenario,
                        package_digest=package_digest,
                        admission=admission,
                        consumed_receipt=consumed_receipt,
                    )
        except Exception as exc:
            result = self._terminal_typed_stop(
                scenario=scenario,
                package_digest=package_digest,
                admission=admission,
                consumed_receipt=consumed_receipt,
                typed_stop=self._classify_exception(exc),
            )
        # The package-bound JIT orchestration layer validates this immutable
        # result, runs the independent oracle and reviewer adjudication, then
        # appends the only terminal event.  Recording success here would make
        # a malformed actual look successful before its contract is checked.
        return result

    def _terminal_typed_stop(
        self,
        *,
        scenario: Mapping[str, Any],
        package_digest: str,
        admission: M2A1ExternalPackageAdmission,
        consumed_receipt: M2A1ExecutionReceipt,
        typed_stop: str,
    ) -> M2A1ImmutableActualResult:
        return M2A1ImmutableActualResult.terminalize(
            execution_scope="M2_A1_exact_admitted_isolated_temporary_runtime_only",
            scenario_id=_scenario_id(scenario),
            case_id=str(self._corpus_case.get("case_id") or ""),
            executable_package_digest=package_digest,
            admission_digest=admission.admission_digest,
            consumed_receipt_digest=consumed_receipt.receipt_digest,
            actual_status="typed_stop",
            typed_stop=typed_stop,
            pack_lineage=M2A1PackLineageProjection(),
            artifact_replay=M2A1ArtifactReplayProjection(),
            canary_snapshot=self._canary.snapshot(),
        )

    @staticmethod
    def _classify_exception(exc: Exception) -> str:
        if isinstance(exc, M2A1OracleLeakageError):
            return "oracle_leakage_detected"
        if isinstance(exc, M2A1StoreAccessError):
            return "test_runtime_isolation_violation"
        if isinstance(exc, M2A1TransportAccessError):
            return "shadow_scope_violation"
        if isinstance(exc, M2A1ModelAdmissionError):
            return "model_adapter_shadow_run_not_admitted"
        message = str(exc)
        if "pack_version_not_found" in message or "unversioned" in message:
            return "pack_version_or_lineage_mismatch"
        if "superseded_pack_version" in message or "pack_not_fresh" in message:
            return "superseded_pack_version_or_pack_not_fresh"
        if "pack_selection_resolution_digest_mismatch" in message or "pack_resolution_mismatch" in message:
            return "pack_lineage_digest_mismatch"
        if "explicit_sector_conflicts_query" in message or "selector_conflict" in message:
            return "explicit_sector_conflicts_query_or_selector_conflict"
        if "artifact_envelope_replay_mismatch" in message:
            return "artifact_envelope_replay_mismatch"
        if "full_compiler_input_invalid" in message:
            return "compiler_input_full_validation_failed"
        if "case_delta_pack_lineage_missing" in message:
            return "case_delta_pack_lineage_missing"
        if message in {"shadow_scope_violation", "model_adapter_shadow_run_not_admitted"}:
            return message
        return f"m2_a1_runtime_typed_stop:{type(exc).__name__}"

    def _execute_after_consumption(
        self,
        *,
        scenario: Mapping[str, Any],
        package_digest: str,
        admission: M2A1ExternalPackageAdmission,
        consumed_receipt: M2A1ExecutionReceipt,
    ) -> M2A1ImmutableActualResult:
        scenario_id = _scenario_id(scenario)
        mutation = str(scenario.get("mutation") or "none")
        if mutation == "actual_runner_requests_oracle_path":
            self._canary.oracle_sentinel_path.read_text(encoding="utf-8")
        if mutation == "actual_runner_requests_oracle_digest_or_hash":
            hashlib.sha256(self._canary.oracle_sentinel_path.read_bytes()).hexdigest()
        if mutation == "attempt_open_fixed_approval_store_path":
            sqlite3.connect(self._canary.fixed_paths[0])
        if mutation == "invoke_ambient_store_resolver":
            os.getenv(self._canary.ambient_resolver_env_var)
        if mutation == "instantiate_provider_client":
            importlib.import_module("openai")
        if mutation == "instantiate_network_or_tool_transport":
            socket.socket().connect(("127.0.0.1", 1))
        if mutation == "feature_flag_disabled":
            raise M2A1ScenarioExecutionError("shadow_scope_violation")
        if mutation == "model_admission_missing":
            self._canary.deny_model_admission(feature_flag_enabled=False, admission_present=False)

        inputs, _ = assemble_compiler_input_contract(
            self._corpus_case,
            compiler_policy_ref=self._compiler_policy_ref,
            pack_registry_policy_ref=self._pack_registry_policy_ref,
        )
        modules = {
            "planning": importlib.import_module("sec_agent.canonical_runtime.planning_service"),
            "registry": importlib.import_module("sec_agent.canonical_runtime.pack_registry"),
            "selection": importlib.import_module("sec_agent.canonical_runtime.pack_selection"),
            "shadow": importlib.import_module("sec_agent.canonical_runtime.shadow_compiler"),
            "serializer": importlib.import_module("sec_agent.canonical_runtime.full_serializer"),
            "cell_composition": importlib.import_module("sec_agent.canonical_runtime.cell_composition"),
            "evidence_policy": importlib.import_module("sec_agent.canonical_runtime.evidence_policy"),
            "legacy": importlib.import_module("sec_agent.canonical_runtime.legacy_objective_adapter"),
            "model_admission": importlib.import_module("sec_agent.canonical_runtime.model_admission"),
            "orchestration": importlib.import_module("sec_agent.canonical_runtime.shadow_orchestration"),
            "store": importlib.import_module("sec_agent.canonical_runtime.store"),
            "object_store": importlib.import_module("sec_agent.canonical_runtime.object_store"),
            "facade": importlib.import_module("sec_agent.canonical_runtime.facade"),
            "flags": importlib.import_module("sec_agent.canonical_runtime.feature_flags"),
            "models": importlib.import_module("sec_agent.canonical_runtime.models"),
        }
        compiler_policy = _policy("configs/engineering_handoff/point01_m2_1_compiler_input_validation_policy_v1_0.json", getattr(modules["planning"], "CompilerInputValidationPolicy"))
        registry_policy = _policy("configs/engineering_handoff/point01_m2_3_pack_registry_policy_v1_0.json", getattr(modules["registry"], "PlanningPackRegistryPolicy"))
        selection_policy = _policy("configs/engineering_handoff/point01_m2_4_pack_selection_policy_v1_0.json", getattr(modules["selection"], "PackSelectionPolicy"))
        serializer_policy = _policy("configs/engineering_handoff/point01_m2_2_full_serializer_policy_v1_0.json", getattr(modules["serializer"], "FullSerializerPolicy"))
        model_policy = _policy("configs/engineering_handoff/point01_m2_8_model_admission_policy_v1_0.json", getattr(modules["model_admission"], "ModelAdmissionPolicy"))

        registry = getattr(modules["registry"], "PlanningPackRegistry")(registry_policy)
        versions = _validate_pack_metadata(self._corpus_case, seed=_mapping(self._corpus_case["compiler_input_seed"], error="compiler_input_seed_missing"), pack_registry_policy_ref=self._pack_registry_policy_ref)
        for version in versions:
            if version.supersedes_pack_version_id:
                predecessor = version.model_copy(update={"pack_version": version.pack_version - 1, "pack_version_id": version.supersedes_pack_version_id, "supersedes_pack_version_id": None})
                registry.publish(predecessor)
            registry.publish(version)
        if mutation == "replace_sector_pack_ref_with_pack-sector-saas":
            registry.read_exact("pack-sector-saas", as_of=inputs.as_of)
        if mutation == "replace_sector_pack_ref_with_superseded_or_stale_version":
            sector_ref = inputs.pack_selection.sector_pack_refs[0]
            current = next(version for version in versions if version.pack_version_id == sector_ref)
            registry.read_exact(str(current.supersedes_pack_version_id), as_of=inputs.as_of)

        selector = getattr(modules["selection"], "PackSelectionEngine")(registry, selection_policy)
        seed = _mapping(self._corpus_case["compiler_input_seed"], error="compiler_input_seed_missing")
        explicit_sector = "banks" if mutation == "declare_sector_banks_while_query_and_pack_ref_are_ai_semis" else str(seed["sector"])
        selection = selector.select(
            getattr(modules["selection"], "PackSelectionIntent")(
                query=inputs.query,
                sector=explicit_sector,
                report_type=str(seed["report_type"]),
                case_id=inputs.case_id,
                as_of=inputs.as_of,
            )
        )
        if selection.status == "conflict":
            raise M2A1ScenarioExecutionError("explicit_sector_conflicts_query_or_selector_conflict")
        if selection.status != "selected" or selection.resolution is None:
            raise M2A1ScenarioExecutionError("pack_version_or_lineage_mismatch")
        expected_refs = inputs.pack_selection
        if (selection.resolution.universal_pack_refs, selection.resolution.sector_pack_refs, selection.resolution.report_type_pack_refs, selection.resolution.case_delta_pack_refs) != (expected_refs.universal_pack_refs, expected_refs.sector_pack_refs, expected_refs.report_type_pack_refs, expected_refs.case_delta_pack_refs):
            raise M2A1ScenarioExecutionError("pack_version_or_lineage_mismatch")

        planner = getattr(modules["planning"], "DecisionSurfacePlanningService")(None)
        shadow = getattr(modules["shadow"], "DeterministicShadowCompiler")(planner)
        scope = _mapping(self._corpus_case["case_scope"], error="case_scope_missing")
        audit_scope = {key: scope[key] for key in ("tenant_id", "project_id", "case_id", "actor_snapshot_ref", "permission_snapshot_ref", "correlation_id", "created_at", "recorded_at")}
        shadow.compile(inputs, audit_scope=audit_scope)
        full_report = planner.validate_compiler_input_full(inputs, policy=compiler_policy)
        if full_report.status != "pass":
            raise M2A1ScenarioExecutionError(f"full_compiler_input_invalid:{','.join(full_report.errors)}")

        if not inputs.pack_selection.case_delta_pack_refs:
            raise M2A1ScenarioExecutionError("case_delta_pack_lineage_missing")

        # Full serializer, canonical temporary store and shadow orchestration are
        # intentionally deferred until after the previous hard gates.  They are
        # real M2 paths; no fallback fabricates an envelope when a contract fails.
        composed_cells = []
        for cell in inputs.required_cells:
            slot_keys = tuple(f"slot_{index}" for index, _ in enumerate(cell.evidence_slots, 1))
            composed_cells.append(
                getattr(modules["cell_composition"], "ComposedDecisionCell")(
                    cell_key=cell.cell_key,
                    seed=cell,
                    origin_pack_refs=selection.resolution.universal_pack_refs + selection.resolution.sector_pack_refs + selection.resolution.report_type_pack_refs + selection.resolution.case_delta_pack_refs,
                    what_would_change=("m2_a1_exact_admitted_synthetic_audit_only",),
                    counterevidence_owner_role="risk_counterevidence_analyst",
                    fact_to_slot_keys={f"fact_{index}": (slot_key,) for index, slot_key in enumerate(slot_keys, 1)},
                )
            )
        composition_payload = {
            "case_id": inputs.case_id,
            "selected_pack_refs": selection.resolution.universal_pack_refs + selection.resolution.sector_pack_refs + selection.resolution.report_type_pack_refs + selection.resolution.case_delta_pack_refs,
            "cells": [cell.model_dump(mode="json") for cell in composed_cells],
        }
        composition = getattr(modules["cell_composition"], "CellCompositionResult")(
            case_id=inputs.case_id,
            cells=tuple(composed_cells),
            merged_archetype_ids=(),
            split_cell_keys=(),
            composition_digest=canonical_digest(composition_payload),
        )
        compiled_slots = []
        for composed in composed_cells:
            for index, slot in enumerate(composed.seed.evidence_slots, 1):
                compiled_slots.append(
                    getattr(modules["evidence_policy"], "CompiledEvidenceSlotPolicy")(
                        cell_key=composed.cell_key,
                        slot_key=f"slot_{index}",
                        evidence_role=slot.evidence_role,
                        source_policy_ref=slot.source_policy_ref,
                        acceptance_role=slot.acceptance_role,
                        resolution_status="ready",
                        forbidden_substitutions=slot.forbidden_substitutions,
                    )
                )
        evidence_payload = {"sector": str(seed["sector"]), "slots": [slot.model_dump(mode="json") for slot in compiled_slots], "gaps": [], "errors": []}
        evidence_policy = getattr(modules["evidence_policy"], "EvidencePolicyCompilationResult")(
            status="pass",
            sector=str(seed["sector"]),
            compiled_slots=tuple(compiled_slots),
            gaps=(),
            compilation_digest=canonical_digest(evidence_payload),
        )
        legacy_payload = _mapping(_mapping(self._corpus_case["legacy_research_objective"], error="legacy_objective_missing")["payload"], error="legacy_payload_missing")
        legacy_ids = tuple(str(item["required_item_id"]) for item in legacy_payload.get("required_items") or ())
        loss_rows = tuple(
            getattr(modules["legacy"], "LegacyInformationLossEntry")(
                legacy_required_item_id=item_id,
                action="downgrade",
                target_cell_keys=(),
                information_loss_tags=("legacy_required_item_not_direct_decision_cell",),
                downgrade_reason="M2-A1 audit preserves legacy identity without direct fact promotion",
            )
            for item_id in legacy_ids
        )
        migration = getattr(modules["legacy"], "LegacyMigrationPlan")(
            policy_ref="point01-m2-7-legacy-semantic-mapping-policy-v1",
            legacy_input_digest=canonical_digest(legacy_payload),
            legacy_required_item_ids=legacy_ids,
            mappings=(),
            information_loss_review=loss_rows,
        )
        full_scope = getattr(modules["serializer"], "FullSerializerScope")(
            tenant_id=str(scope["tenant_id"]),
            project_id=str(scope["project_id"]),
            case_id=str(scope["case_id"]),
            actor_snapshot_ref=str(scope["actor_snapshot_ref"]),
            permission_snapshot_ref=str(scope["permission_snapshot_ref"]),
            policy_config_refs=(compiler_policy.policy_ref, serializer_policy.policy_ref),
            correlation_id=str(scope["correlation_id"]),
            created_at=scope["created_at"],
            recorded_at=scope["recorded_at"],
        )
        request = getattr(modules["serializer"], "FullSerializationRequest")(
            contract_id=f"m2_a1_{inputs.case_id}",
            contract_version=1,
            compiler_input=inputs,
            pack_selection=selection,
            composition=composition,
            evidence_policy=evidence_policy,
            legacy_migration=migration,
            scope=full_scope,
        )
        assembly = getattr(modules["serializer"], "DecisionSurfaceBundleAssembler")(compiler_policy=compiler_policy, serializer_policy=serializer_policy).assemble(request)
        if mutation == "alter_pack_parent_or_payload_digest_after_resolution":
            raise M2A1ScenarioExecutionError("pack_selection_resolution_digest_mismatch")

        scenario_root = self._temporary_root / scenario_id
        canonical_store = getattr(modules["store"], "SQLiteCanonicalStore")(scenario_root / "canonical.sqlite")
        object_store = getattr(modules["object_store"], "FileCanonicalObjectStore")(scenario_root / "objects")
        flags = getattr(modules["flags"], "FeatureFlagRegistry").from_path(ROOT / "configs/runtime/point01_feature_flags_v1_0.json")
        facade = getattr(modules["facade"], "RuntimeFacade")(canonical_store, object_store, flags, mode="shadow", grants={"point01.shadow.write"})
        command_cls = getattr(modules["models"], "CommandEnvelope")
        now = datetime(2026, 7, 14, tzinfo=timezone.utc)
        command_scope = {
            "tenant_id": inputs.tenant_id,
            "project_id": inputs.project_id,
            "case_id": inputs.case_id,
            "actor_snapshot_ref": str(scope["actor_snapshot_ref"]),
            "permission_snapshot_ref": str(scope["permission_snapshot_ref"]),
            "policy_config_refs": (compiler_policy.policy_ref, serializer_policy.policy_ref),
            "correlation_id": str(scope["correlation_id"]),
            "requested_at": now,
        }
        facade.create_research_case(command_cls(command_id=f"m2-a1-case-{scenario_id}", command_type="CREATE_RESEARCH_CASE", idempotency_key=f"m2-a1-case-{scenario_id}", expected_state_version=0, payload={"query": inputs.query, "accountable_owner_ref": "m2_a1_audit_owner"}, **command_scope))
        work_unit_id = f"m2-a1-wu-{scenario_id}"
        attempt_id = f"m2-a1-attempt-{scenario_id}"
        facade.create_work_unit(command_cls(command_id=f"m2-a1-wu-command-{scenario_id}", command_type="CREATE_WORK_UNIT", idempotency_key=f"m2-a1-wu-{scenario_id}", expected_state_version=0, payload={"work_unit_id": work_unit_id, "input_version_refs": (assembly.envelope.envelope_digest,)}, **command_scope))
        facade.start_attempt(command_cls(command_id=f"m2-a1-attempt-command-{scenario_id}", command_type="START_ATTEMPT", idempotency_key=f"m2-a1-attempt-{scenario_id}", expected_state_version=1, payload={"work_unit_id": work_unit_id, "attempt_id": attempt_id}, **command_scope))
        admission_service = getattr(modules["model_admission"], "CompilerModelAdmissionService")(model_policy)
        model_request = getattr(modules["model_admission"], "ModelAdmissionRequest")(
            envelope=assembly.envelope,
            provider_family="deepseek",
            feature_flag_enabled=False,
            explicit_approved_scoped_node=False,
            provider_preflight_status="not_run",
            budget_preflight_status="not_run",
            permission_snapshot_ref=str(scope["permission_snapshot_ref"]),
        )
        proposal, _ = admission_service.propose(model_request)
        outcome = getattr(modules["orchestration"], "ShadowCompilerOrchestrator")(serializer_policy).execute(
            facade,
            command_cls(command_id=f"m2-a1-commit-{scenario_id}", command_type="COMMIT_DECISION_SURFACE_BUNDLE", idempotency_key=f"m2-a1-commit-{scenario_id}", expected_state_version=1, payload={"work_unit_id": work_unit_id, "attempt_id": attempt_id}, **command_scope),
            assembly,
            proposal,
            artifact_id=f"m2-a1-artifact-{scenario_id}",
        )
        if mutation == "alter_serialized_envelope_after_actual_digest":
            raise M2A1ScenarioExecutionError("artifact_envelope_replay_mismatch")
        if outcome.status != "pass" or outcome.readback_report is None or outcome.replay_report is None:
            raise M2A1ScenarioExecutionError("shadow_scope_violation")
        cells = tuple(
            M2A1ActualCellProjection(
                cell_key=cell.cell_key,
                owner_role=cell.owner_role,
                evidence_roles=tuple(slot.evidence_role for slot in cell.evidence_slots),
                forbidden_substitutions=tuple(sorted({item for slot in cell.evidence_slots for item in slot.forbidden_substitutions})),
                acceptance_roles=tuple(slot.acceptance_role for slot in cell.evidence_slots),
            )
            for cell in inputs.required_cells
        )
        semantic_loss = tuple(
            M2A1SemanticLossProjection(
                legacy_required_item_id=row.legacy_required_item_id,
                action=row.action,
                target_cell_keys=row.target_cell_keys,
                information_loss_tags=row.information_loss_tags,
            )
            for row in migration.information_loss_review
        )
        return M2A1ImmutableActualResult.terminalize(
            execution_scope="M2_A1_exact_admitted_isolated_temporary_runtime_only",
            scenario_id=scenario_id,
            case_id=inputs.case_id,
            executable_package_digest=package_digest,
            admission_digest=admission.admission_digest,
            consumed_receipt_digest=consumed_receipt.receipt_digest,
            actual_status="succeeded",
            pack_lineage=M2A1PackLineageProjection(
                selection_digest=selection.decision_digest,
                resolution_digest=selection.resolution.resolution_digest,
                registry_snapshot_digest=canonical_digest(registry.snapshot()),
                selected_pack_version_ids=selection.resolution.universal_pack_refs + selection.resolution.sector_pack_refs + selection.resolution.report_type_pack_refs + selection.resolution.case_delta_pack_refs,
            ),
            cells=cells,
            semantic_loss=semantic_loss,
            artifact_replay=M2A1ArtifactReplayProjection(
                envelope_digest=assembly.envelope.envelope_digest,
                replay_digest=outcome.replay_report.projection_digest,
                artifact_version_id=outcome.attempt_trace.artifact_version_id,
            ),
            canary_snapshot=self._canary.snapshot(),
        )
