from __future__ import annotations

from enum import Enum
import hashlib
import json
from typing import Any, Mapping


class ContractGovernanceError(ValueError):
    """A stable, machine-readable S0 contract-governance failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ProofClass(str, Enum):
    IMMUTABLE_EVENT = "immutable_event"
    CURRENT_PROJECTION = "current_projection"
    CURRENT_RUNTIME = "current_runtime"
    HISTORICAL_AUDIT = "historical_audit"
    RELEASE_GATE = "release_gate"


RUNTIME_SPEC_SCHEMA = "fin_ia_runtime_contract_family_source_v1_0"
TEST_MANIFEST_SCHEMA = "fin_ia_active_test_suite_manifest_v1_0"

LOCAL_TRUTH_FIELDS = (
    "material_number",
    "reporting_date",
    "case_identity",
    "runtime_id",
    "lineage",
)

REQUIRED_COMPILED_CONSUMERS = (
    "prompt",
    "server_schema",
    "local_validator",
    "fake_provider",
    "selector",
    "renderer",
    "capacity",
    "budget",
    "typed_failure",
    "capture_index",
)

MUTABLE_ASSERTION_SURFACES = frozenset(
    {
        "current_next_action",
        "current_active_slice",
        "latest_ledger_row",
        "cumulative_store_count",
        "living_document_digest",
        "current_code_digest",
        "mutable_backlog_status",
    }
)


def canonical_digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        dict(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _mapping(value: Any, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractGovernanceError(code)
    return value


def _nonempty_string(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractGovernanceError(code)
    return value.strip()


def _string_tuple(value: Any, code: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ContractGovernanceError(code)
    items = tuple(_nonempty_string(item, code) for item in value)
    if not items:
        raise ContractGovernanceError(f"{code}_empty")
    if len(items) != len(set(items)):
        raise ContractGovernanceError(f"{code}_duplicate")
    return items


def validate_runtime_contract_source(source: Mapping[str, Any]) -> None:
    if source.get("schema_version") != RUNTIME_SPEC_SCHEMA:
        raise ContractGovernanceError("runtime_contract_schema_invalid")
    contract_id = _nonempty_string(
        source.get("contract_id"), "runtime_contract_id_missing"
    )
    contract_version = _nonempty_string(
        source.get("contract_version"), "runtime_contract_version_missing"
    )

    truth = _mapping(
        source.get("truth_ownership"), "runtime_truth_ownership_missing"
    )
    for field in LOCAL_TRUTH_FIELDS:
        if truth.get(field) != "local_deterministic":
            raise ContractGovernanceError(
                f"runtime_truth_owner_not_local:{field}"
            )

    provider = _mapping(
        source.get("provider_authority"),
        "runtime_provider_authority_missing",
    )
    if provider.get("surface") != (
        "request_local_aliases_enums_and_bounded_judgment_atoms_only"
    ):
        raise ContractGovernanceError("runtime_provider_surface_too_broad")
    allowed_kinds = set(
        _string_tuple(
            provider.get("allowed_value_kinds"),
            "runtime_provider_allowed_value_kinds_invalid",
        )
    )
    if allowed_kinds != {
        "request_local_alias",
        "closed_enum",
        "bounded_judgment_atom",
    }:
        raise ContractGovernanceError(
            "runtime_provider_allowed_value_kinds_not_closed"
        )
    forbidden_fields = set(
        _string_tuple(
            provider.get("forbidden_direct_fields"),
            "runtime_provider_forbidden_fields_invalid",
        )
    )
    if not set(LOCAL_TRUTH_FIELDS).issubset(forbidden_fields):
        raise ContractGovernanceError(
            "runtime_provider_material_truth_not_forbidden"
        )

    consumers = source.get("compiled_consumers")
    if not isinstance(consumers, list):
        raise ContractGovernanceError("runtime_compiled_consumers_missing")
    consumer_ids: list[str] = []
    for row in consumers:
        item = _mapping(row, "runtime_compiled_consumer_invalid")
        consumer_ids.append(
            _nonempty_string(
                item.get("consumer_id"),
                "runtime_compiled_consumer_id_missing",
            )
        )
        if item.get("contract_id") != contract_id:
            raise ContractGovernanceError(
                "runtime_compiled_consumer_contract_id_drift"
            )
        if item.get("contract_version") != contract_version:
            raise ContractGovernanceError(
                "runtime_compiled_consumer_contract_version_drift"
            )
        _nonempty_string(
            item.get("implementation_owner"),
            "runtime_compiled_consumer_implementation_owner_missing",
        )
    if len(consumer_ids) != len(set(consumer_ids)):
        raise ContractGovernanceError(
            "runtime_compiled_consumer_duplicate"
        )
    if set(consumer_ids) != set(REQUIRED_COMPILED_CONSUMERS):
        raise ContractGovernanceError(
            "runtime_compiled_consumer_surface_incomplete"
        )

    budget = _mapping(
        source.get("budget_contract"), "runtime_budget_contract_missing"
    )
    for field in (
        "provider_candidate_maximum",
        "selected_atom_maximum",
        "provider_output_max_utf8_bytes",
        "local_rendered_max_utf8_bytes",
    ):
        value = budget.get(field)
        if type(value) is not int or value <= 0:
            raise ContractGovernanceError(
                f"runtime_budget_invalid:{field}"
            )
    if budget["selected_atom_maximum"] > budget[
        "provider_candidate_maximum"
    ]:
        raise ContractGovernanceError(
            "runtime_selected_atom_budget_exceeds_candidate_budget"
        )

    failure = _mapping(
        source.get("failure_and_capture"),
        "runtime_failure_capture_contract_missing",
    )
    required_capture = {
        "phase",
        "code",
        "request_capture_ref",
        "assistant_output_capture_ref",
        "terminal_result_ref",
        "stdout_ref",
        "stderr_ref",
    }
    if not required_capture.issubset(
        set(
            _string_tuple(
                failure.get("required_fields"),
                "runtime_failure_capture_fields_invalid",
            )
        )
    ):
        raise ContractGovernanceError(
            "runtime_failure_capture_surface_incomplete"
        )
    if failure.get("failed_output_promotable") is not False:
        raise ContractGovernanceError(
            "runtime_failed_output_promotion_not_forbidden"
        )


def compile_runtime_contract_source(
    source: Mapping[str, Any],
) -> dict[str, Any]:
    """Compile one source into version- and digest-bound consumer envelopes.

    S0 intentionally compiles governance envelopes only. Runtime-family payload
    generation and migration remain separate, explicit gates.
    """

    validate_runtime_contract_source(source)
    source_digest = canonical_digest(source)
    contract_id = str(source["contract_id"])
    contract_version = str(source["contract_version"])
    truth_digest = canonical_digest(
        _mapping(source["truth_ownership"], "runtime_truth_invalid")
    )
    provider_digest = canonical_digest(
        _mapping(source["provider_authority"], "runtime_provider_invalid")
    )
    consumer_rows = {
        str(row["consumer_id"]): row
        for row in source["compiled_consumers"]
    }
    compiled = []
    for consumer_id in REQUIRED_COMPILED_CONSUMERS:
        row = consumer_rows[consumer_id]
        compiled.append(
            {
                "consumer_id": consumer_id,
                "contract_id": contract_id,
                "contract_version": contract_version,
                "source_digest": source_digest,
                "truth_ownership_digest": truth_digest,
                "provider_authority_digest": provider_digest,
                "implementation_owner": row["implementation_owner"],
            }
        )
    return {
        "schema_version": "fin_ia_compiled_runtime_contract_envelope_v1_0",
        "contract_id": contract_id,
        "contract_version": contract_version,
        "source_digest": source_digest,
        "local_truth_fields": list(LOCAL_TRUTH_FIELDS),
        "provider_surface": source["provider_authority"]["surface"],
        "compiled_consumers": compiled,
    }


def validate_active_test_suite_manifest(
    manifest: Mapping[str, Any],
) -> None:
    if manifest.get("schema_version") != TEST_MANIFEST_SCHEMA:
        raise ContractGovernanceError("test_manifest_schema_invalid")
    if manifest.get("historical_failures_are_ignored") is not False:
        raise ContractGovernanceError(
            "test_manifest_historical_failures_must_remain_visible"
        )
    suites = manifest.get("suites")
    if not isinstance(suites, list) or not suites:
        raise ContractGovernanceError("test_manifest_suites_missing")

    seen_ids: set[str] = set()
    selected_by_class = {proof_class: 0 for proof_class in ProofClass}
    for row in suites:
        suite = _mapping(row, "test_manifest_suite_invalid")
        suite_id = _nonempty_string(
            suite.get("suite_id"), "test_manifest_suite_id_missing"
        )
        if suite_id in seen_ids:
            raise ContractGovernanceError("test_manifest_suite_duplicate")
        seen_ids.add(suite_id)
        try:
            proof_class = ProofClass(str(suite.get("proof_class")))
        except ValueError as exc:
            raise ContractGovernanceError(
                "test_manifest_proof_class_invalid"
            ) from exc
        selected = suite.get("selected")
        gates_current_release = suite.get("gates_current_release")
        if type(selected) is not bool or type(gates_current_release) is not bool:
            raise ContractGovernanceError(
                "test_manifest_boolean_contract_invalid"
            )
        if selected:
            selected_by_class[proof_class] += 1
        surfaces = set(
            _string_tuple(
                suite.get("assertion_surfaces"),
                "test_manifest_assertion_surfaces_invalid",
            )
        )
        _string_tuple(
            suite.get("test_paths"), "test_manifest_test_paths_invalid"
        )
        if (
            proof_class is ProofClass.IMMUTABLE_EVENT
            and surfaces.intersection(MUTABLE_ASSERTION_SURFACES)
        ):
            raise ContractGovernanceError(
                "immutable_event_asserts_mutable_projection"
            )
        if (
            proof_class is ProofClass.HISTORICAL_AUDIT
            and gates_current_release
        ):
            raise ContractGovernanceError(
                "historical_audit_cannot_gate_current_release"
            )
        if proof_class in {
            ProofClass.CURRENT_PROJECTION,
            ProofClass.CURRENT_RUNTIME,
            ProofClass.RELEASE_GATE,
        } and selected != gates_current_release:
            raise ContractGovernanceError(
                "current_selected_and_gate_semantics_diverge"
            )

    for proof_class in ProofClass:
        if selected_by_class[proof_class] != 1:
            raise ContractGovernanceError(
                f"test_manifest_selected_suite_count_invalid:{proof_class.value}"
            )

    runner_policy = _mapping(
        manifest.get("runner_policy"), "test_manifest_runner_policy_missing"
    )
    migration_complete = runner_policy.get("runner_migration_completed")
    if type(migration_complete) is not bool:
        raise ContractGovernanceError(
            "test_manifest_runner_migration_boolean_invalid"
        )
    authority_enabled = runner_policy.get(
        "manifest_is_clean_environment_authority", False
    )
    if type(authority_enabled) is not bool:
        raise ContractGovernanceError(
            "test_manifest_clean_environment_authority_boolean_invalid"
        )
    authority_binding = manifest.get(
        "clean_environment_qualification_authority_binding"
    )
    if authority_enabled:
        binding = _mapping(
            authority_binding,
            "test_manifest_clean_environment_authority_binding_missing",
        )
        if set(binding) != {"ref", "sha256"}:
            raise ContractGovernanceError(
                "test_manifest_clean_environment_authority_binding_invalid"
            )
        _nonempty_string(
            binding.get("ref"),
            "test_manifest_clean_environment_authority_ref_missing",
        )
        digest = _nonempty_string(
            binding.get("sha256"),
            "test_manifest_clean_environment_authority_digest_missing",
        )
        if len(digest) != 64 or any(
            character not in "0123456789abcdef" for character in digest
        ):
            raise ContractGovernanceError(
                "test_manifest_clean_environment_authority_digest_invalid"
            )
        if manifest.get("status") != (
            "clean_environment_qualification_authorized_not_executed"
        ):
            raise ContractGovernanceError(
                "test_manifest_clean_environment_authority_status_invalid"
            )
    elif authority_binding is not None:
        raise ContractGovernanceError(
            "test_manifest_unowned_clean_environment_authority_binding"
        )
    if migration_complete:
        package_policy = _mapping(
            manifest.get("hermetic_package_policy"),
            "test_manifest_hermetic_package_policy_missing",
        )
        required_runner_files = set(
            _string_tuple(
                package_policy.get("required_runner_files"),
                "test_manifest_required_runner_files_invalid",
            )
        )
        capture_plugin_path = _nonempty_string(
            package_policy.get("capture_plugin_path"),
            "test_manifest_capture_plugin_path_missing",
        )
        if capture_plugin_path not in required_runner_files:
            raise ContractGovernanceError(
                "test_manifest_capture_plugin_not_packaged"
            )
        bindings = package_policy.get("external_read_only_bindings")
        if not isinstance(bindings, list):
            raise ContractGovernanceError(
                "test_manifest_external_bindings_invalid"
            )
