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
import sysconfig
import tempfile
from typing import Any, Iterable, Mapping, Sequence

from sec_agent.runtime_contract_governance import (
    ContractGovernanceError,
    validate_active_test_suite_manifest,
)
from sec_agent.runtime_resource_registry import (
    RuntimeResourceRegistryError,
    load_runtime_resource_registry,
)
from sec_agent.reference_role_registry import (
    ReferenceRoleRegistry,
    ReferenceRoleRegistryError,
    ReferenceRoleReport,
    collect_reference_roles,
    iter_reference_strings,
    load_reference_role_registry,
)
from sec_agent.test_execution_contract import (
    CompiledTestExecutionContract,
    TestDependencyBundle,
    TestExecutionContractError,
    load_test_execution_contract_registry,
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
TYPED_SEMANTIC_PARITY_SCHEMA = (
    "fin_ia_0_1_3_typed_environment_semantic_parity_v1_0"
)
REPOSITORY_REFERENCE_POLICY_SCHEMA = (
    "fin_ia_hermetic_repository_reference_policy_v1_0"
)
REPOSITORY_REFERENCE_POLICY_V2_SCHEMA = (
    "fin_ia_hermetic_repository_reference_policy_v2_0"
)
LEGACY_PROGRAM_EVENT_PROJECTION_SCHEMA = (
    "fin_ia_0_1_2_current_program_projection_v1_0"
)
CURRENT_PROGRAM_PROJECTION_SCHEMA = "fin_ia_current_program_projection_v2_0"
CURRENT_PROGRAM_LIFECYCLE_STATES = frozenset(
    {"planned", "in_progress", "blocked", "passed"}
)
CLEAN_ENVIRONMENT_AUTHORITY_SCHEMA = (
    "fin_ia_0_1_2_s0_clean_environment_qualification_authority_decision_v1_0"
)
CLEAN_ENVIRONMENT_AUTHORITY_STATUS = (
    "authorize_one_future_clean_environment_qualification_not_executed"
)
CLEAN_ENVIRONMENT_EXECUTION_NEXT = (
    "FIN-0.1.2-S0-FRESH-CLEAN-ENVIRONMENT-QUALIFICATION-EXECUTION-AND-CLOSEOUT"
)

_REPOSITORY_PATH_SUFFIXES = frozenset(
    {
        ".json",
        ".jsonl",
        ".md",
        ".py",
        ".toml",
        ".yaml",
        ".yml",
    }
)
_REPOSITORY_ROOTS = frozenset(
    {
        ".github",
        "apps",
        "configs",
        "docs",
        "scripts",
        "src",
        "tests",
    }
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
    def __init__(
        self,
        code: str,
        *,
        failure_envelope: Mapping[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.failure_envelope = (
            dict(failure_envelope) if failure_envelope is not None else None
        )
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


@dataclass(frozen=True)
class CompiledRepositoryInventory:
    paths: tuple[Path, ...]
    tracked_paths: tuple[str, ...]
    explicit_allowlist_paths: tuple[str, ...]
    recursive_reference_paths: tuple[str, ...]
    semantic_or_external_reference_count: int
    closure_digest: str
    reference_role_report: ReferenceRoleReport | None = None

    def as_dict(self) -> dict[str, Any]:
        output = {
            "schema_version": "fin_ia_hermetic_repository_inventory_closure_v1_0",
            "path_count": len(self.paths),
            "tracked_path_count": len(self.tracked_paths),
            "explicit_allowlist_path_count": len(
                self.explicit_allowlist_paths
            ),
            "recursive_reference_path_count": len(
                self.recursive_reference_paths
            ),
            "semantic_or_external_reference_count": (
                self.semantic_or_external_reference_count
            ),
            "closure_digest": self.closure_digest,
        }
        if self.reference_role_report is not None:
            output["reference_role_report"] = (
                self.reference_role_report.as_dict()
            )
        return output


def _load_test_execution_plan(
    repository_root: Path,
    manifest: Mapping[str, Any],
) -> CompiledTestExecutionContract | None:
    policy = manifest.get("hermetic_package_policy")
    if not isinstance(policy, Mapping):
        raise HermeticTestRunnerError("hermetic_package_policy_missing")
    registry_ref = policy.get("test_execution_contract_registry_ref")
    if registry_ref is None:
        return None
    if not isinstance(registry_ref, str) or not registry_ref.strip():
        raise HermeticTestRunnerError(
            "test_execution_contract_registry_ref_invalid"
        )
    try:
        return load_test_execution_contract_registry(
            repository_root,
            registry_ref,
        )
    except TestExecutionContractError as exc:
        raise HermeticTestRunnerError(exc.code) from exc


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


def _repository_ref_strings(value: Any) -> Iterable[tuple[str, str]]:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if isinstance(item, str) and (key == "ref" or key.endswith("_ref")):
                yield key, item
            else:
                yield from _repository_ref_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _repository_ref_strings(item)


def _validate_projection_binding(
    repository_root: Path,
    field: str,
    binding: Any,
    *,
    allow_role: bool = False,
) -> None:
    required = {"ref", "sha256"}
    if allow_role:
        required.add("binding_role")
    if not isinstance(binding, Mapping) or set(binding) != required:
        raise HermeticTestRunnerError(f"current_projection_{field}_invalid")
    binding_ref = str(binding["ref"])
    binding_sha = str(binding["sha256"])
    binding_path = _safe_relative_path(repository_root, binding_ref)
    if allow_role and not str(binding["binding_role"]).strip():
        raise HermeticTestRunnerError(f"current_projection_{field}_invalid")
    if (
        not re.fullmatch(r"[0-9a-f]{64}", binding_sha)
        or _sha256_file(repository_root / binding_path) != binding_sha
    ):
        raise HermeticTestRunnerError(f"current_projection_{field}_drift")


def _validate_legacy_program_event_projection(
    repository_root: Path,
    projection_path: Path,
    projection: Mapping[str, Any],
) -> Path:
    """Validate a historical projection as an immutable event snapshot.

    Legacy v1 documents may name the backlogs and ledgers that were current
    when the event was recorded. Those mutable files are existence-checked but
    never re-read as today's authority.
    """

    required_top_level = {
        "schema_version",
        "projection_id",
        "recorded_at",
        "status",
        "source_paths",
        "expectations",
    }
    if not required_top_level.issubset(projection):
        raise HermeticTestRunnerError("historical_projection_top_level_invalid")
    if not all(
        isinstance(projection.get(field), str) and str(projection[field]).strip()
        for field in ("projection_id", "recorded_at", "status")
    ):
        raise HermeticTestRunnerError("historical_projection_identity_invalid")
    source_values = projection["source_paths"]
    if not isinstance(source_values, Mapping) or not source_values:
        raise HermeticTestRunnerError("historical_projection_sources_invalid")
    for value in source_values.values():
        if not isinstance(value, str) or not value.strip():
            raise HermeticTestRunnerError("historical_projection_sources_invalid")
        _safe_relative_path(repository_root, value)
    expectations = projection["expectations"]
    if not isinstance(expectations, Mapping):
        raise HermeticTestRunnerError("historical_projection_expectations_invalid")
    for field in ("active_slice", "current_next_action"):
        if (
            not isinstance(expectations.get(field), str)
            or not expectations[field].strip()
        ):
            raise HermeticTestRunnerError("historical_projection_identity_invalid")
    governance = projection.get("package_governance", projection.get("scope_governance"))
    if not isinstance(governance, Mapping) or not governance:
        raise HermeticTestRunnerError("historical_projection_governance_invalid")
    for field, binding in projection.items():
        if field.endswith("_binding"):
            _validate_projection_binding(repository_root, field, binding)
    return projection_path


def _validate_current_program_projection_v2(
    repository_root: Path,
    projection_path: Path,
    projection: Mapping[str, Any],
) -> Path:
    required_top_level = {
        "schema_version",
        "projection_id",
        "recorded_at",
        "status",
        "lifecycle_state",
        "decision_binding",
        "current_truth",
        "source_paths",
        "historical_projection_policy",
        "execution_authority",
    }
    optional_top_level = {"implementation_binding"}
    if set(projection) not in (
        required_top_level,
        required_top_level | optional_top_level,
    ):
        raise HermeticTestRunnerError("current_projection_top_level_invalid")
    if not all(
        isinstance(projection.get(field), str) and str(projection[field]).strip()
        for field in ("projection_id", "recorded_at", "status")
    ):
        raise HermeticTestRunnerError("current_projection_identity_invalid")
    if projection["lifecycle_state"] not in CURRENT_PROGRAM_LIFECYCLE_STATES:
        raise HermeticTestRunnerError("current_projection_lifecycle_state_invalid")
    _validate_projection_binding(
        repository_root,
        "decision_binding",
        projection["decision_binding"],
        allow_role=True,
    )
    if "implementation_binding" in projection:
        _validate_projection_binding(
            repository_root,
            "implementation_binding",
            projection["implementation_binding"],
            allow_role=True,
        )

    truth = projection["current_truth"]
    required_truth = {
        "product_version",
        "stage",
        "active_slice",
        "current_next_action",
        "current_stage_status",
        "open_issue_ids",
        "release_qualified",
    }
    if not isinstance(truth, Mapping) or not required_truth.issubset(truth):
        raise HermeticTestRunnerError("current_projection_truth_invalid")
    if (
        not re.fullmatch(r"FIN(?:_[0-9]+){2,}", str(truth["product_version"]))
        or not re.fullmatch(r"S[0-9]+", str(truth["stage"]))
        or not all(
            isinstance(truth.get(field), str) and str(truth[field]).strip()
            for field in (
                "active_slice",
                "current_next_action",
                "current_stage_status",
            )
        )
        or type(truth["release_qualified"]) is not bool
    ):
        raise HermeticTestRunnerError("current_projection_truth_invalid")
    issue_ids = truth["open_issue_ids"]
    if (
        not isinstance(issue_ids, list)
        or any(not isinstance(item, str) or not item.strip() for item in issue_ids)
        or len(issue_ids) != len(set(issue_ids))
    ):
        raise HermeticTestRunnerError("current_projection_issue_ids_invalid")
    forbidden_truth_fields = {
        "attempt_id",
        "run_id",
        "execution_started",
        "terminal_result",
    }
    if forbidden_truth_fields.intersection(truth):
        raise HermeticTestRunnerError("current_projection_attempt_state_forbidden")

    source_values = projection["source_paths"]
    required_sources = {
        "program_backlog",
        "context_pack",
        "capability_ledger",
        "root_cause_ledger",
    }
    if (
        not isinstance(source_values, Mapping)
        or not required_sources.issubset(source_values)
    ):
        raise HermeticTestRunnerError("current_projection_sources_invalid")
    for value in source_values.values():
        if not isinstance(value, str) or not value.strip():
            raise HermeticTestRunnerError("current_projection_sources_invalid")
        _safe_relative_path(repository_root, value)

    history = projection["historical_projection_policy"]
    required_history = {
        "immutable_event_files_remain_valid_for_historical_facts": True,
        "historical_files_may_own_current_next_or_backlog_tail": False,
        "superseded_projection_deleted_or_rewritten": False,
    }
    if (
        not isinstance(history, Mapping)
        or any(
            history.get(key) is not value
            for key, value in required_history.items()
        )
    ):
        raise HermeticTestRunnerError("current_projection_history_policy_invalid")

    authority = projection["execution_authority"]
    required_authority = {
        "planning_and_read_only_audit_complete",
        "focused_s0_repair_authorized",
        "clean_environment_acceptance_authorized",
        "credential_model_provider_network_business_authorized",
    }
    if (
        not isinstance(authority, Mapping)
        or set(authority) != required_authority
        or any(type(value) is not bool for value in authority.values())
    ):
        raise HermeticTestRunnerError("current_projection_execution_authority_invalid")
    return projection_path


def validate_host_current_program_projection(
    repository_root: Path,
    projection_ref: str,
) -> Path:
    """Validate either today's single current truth or a historical snapshot.

    Current v2 documents are self-contained mutable projections. Legacy v1
    documents are immutable event snapshots and cannot regain authority by
    comparing themselves with today's backlogs or ledger tails.
    """

    repository_root = repository_root.resolve()
    projection_path = _safe_relative_path(repository_root, projection_ref)
    projection = _load_json(repository_root / projection_path)
    schema = projection.get("schema_version")
    if schema == LEGACY_PROGRAM_EVENT_PROJECTION_SCHEMA:
        return _validate_legacy_program_event_projection(
            repository_root,
            projection_path,
            projection,
        )
    if schema == CURRENT_PROGRAM_PROJECTION_SCHEMA:
        return _validate_current_program_projection_v2(
            repository_root,
            projection_path,
            projection,
        )
    raise HermeticTestRunnerError("current_projection_schema_invalid")


def _validate_clean_environment_qualification_authority(
    *,
    repository_root: Path,
    manifest_path: Path,
    manifest: Mapping[str, Any],
    output_root: Path,
) -> dict[str, Any]:
    runner_policy = manifest.get("runner_policy")
    if (
        not isinstance(runner_policy, Mapping)
        or runner_policy.get("manifest_is_clean_environment_authority")
        is not True
    ):
        raise HermeticTestRunnerError(
            "clean_environment_qualification_authority_missing"
        )
    binding = manifest.get(
        "clean_environment_qualification_authority_binding"
    )
    if not isinstance(binding, Mapping) or set(binding) != {"ref", "sha256"}:
        raise HermeticTestRunnerError(
            "clean_environment_qualification_authority_binding_invalid"
        )
    authority_ref = str(binding["ref"])
    authority_path = _safe_relative_path(repository_root, authority_ref)
    authority_sha256 = str(binding["sha256"])
    if (
        not re.fullmatch(r"[0-9a-f]{64}", authority_sha256)
        or _sha256_file(repository_root / authority_path) != authority_sha256
    ):
        raise HermeticTestRunnerError(
            "clean_environment_qualification_authority_binding_drift"
        )
    decision = _load_json(repository_root / authority_path)
    if (
        decision.get("schema_version") != CLEAN_ENVIRONMENT_AUTHORITY_SCHEMA
        or decision.get("status") != CLEAN_ENVIRONMENT_AUTHORITY_STATUS
    ):
        raise HermeticTestRunnerError(
            "clean_environment_qualification_authority_decision_invalid"
        )
    authority = decision.get("authority")
    if (
        not isinstance(authority, Mapping)
        or authority.get("future_clean_environment_qualification_authorized")
        is not True
        or authority.get("qualification_executed_in_this_decision") is not False
        or authority.get("maximum_future_qualification_attempts") != 1
        or authority.get("automatic_retry_or_replacement_attempts") != 0
        or authority.get("credential_model_provider_network_business_authorized")
        is not False
    ):
        raise HermeticTestRunnerError(
            "clean_environment_qualification_authority_scope_invalid"
        )
    execution = decision.get("execution_contract")
    if not isinstance(execution, Mapping):
        raise HermeticTestRunnerError(
            "clean_environment_qualification_execution_contract_invalid"
        )
    manifest_projection = dict(manifest)
    manifest_projection.pop(
        "clean_environment_qualification_authority_binding", None
    )
    if (
        execution.get("manifest_without_authority_binding_sha256")
        != _sha256_bytes(_canonical_bytes(manifest_projection))
    ):
        raise HermeticTestRunnerError(
            "clean_environment_qualification_manifest_projection_drift"
        )
    expected_manifest = _safe_relative_path(
        repository_root,
        str(execution.get("manifest_ref", "")),
    )
    if manifest_path.resolve() != (repository_root / expected_manifest).resolve():
        raise HermeticTestRunnerError(
            "clean_environment_qualification_manifest_mismatch"
        )
    expected_output = Path(str(execution.get("output_root", ""))).resolve()
    if output_root.resolve() != expected_output:
        raise HermeticTestRunnerError(
            "clean_environment_qualification_output_root_mismatch"
        )
    try:
        expected_output.relative_to(repository_root)
    except ValueError:
        pass
    else:
        raise HermeticTestRunnerError(
            "clean_environment_qualification_output_inside_repository"
        )
    expected_failure_root = expected_output.with_name(
        expected_output.name + ".failed"
    )
    expected_staging_root = expected_output.with_name(
        expected_output.name + ".partial"
    )
    if (
        expected_output.exists()
        or expected_failure_root.exists()
        or expected_staging_root.exists()
    ):
        raise HermeticTestRunnerError(
            "clean_environment_qualification_attempt_already_consumed"
        )

    source_bindings = decision.get("source_bindings")
    if not isinstance(source_bindings, list):
        raise HermeticTestRunnerError(
            "clean_environment_qualification_source_bindings_invalid"
        )
    required_roles = {
        "focused_repair_implementation",
        "qualification_runner",
        "hermetic_runner",
        "manifest_governance_validator",
        "attempt_contract",
    }
    observed_roles: set[str] = set()
    for source_binding in source_bindings:
        if not isinstance(source_binding, Mapping) or set(source_binding) != {
            "role",
            "ref",
            "sha256",
        }:
            raise HermeticTestRunnerError(
                "clean_environment_qualification_source_binding_invalid"
            )
        role = str(source_binding["role"])
        source_path = _safe_relative_path(
            repository_root,
            str(source_binding["ref"]),
        )
        digest = str(source_binding["sha256"])
        if (
            role in observed_roles
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or _sha256_file(repository_root / source_path) != digest
        ):
            raise HermeticTestRunnerError(
                "clean_environment_qualification_source_binding_drift"
            )
        observed_roles.add(role)
    if observed_roles != required_roles:
        raise HermeticTestRunnerError(
            "clean_environment_qualification_source_roles_invalid"
        )

    projection_ref = str(execution.get("current_projection_ref", ""))
    validate_host_current_program_projection(repository_root, projection_ref)
    projection = _load_json(
        repository_root / _safe_relative_path(repository_root, projection_ref)
    )
    projection_without_decision_binding = dict(projection)
    projection_without_decision_binding.pop("decision_binding", None)
    if (
        execution.get("current_projection_without_decision_binding_sha256")
        != _sha256_bytes(_canonical_bytes(projection_without_decision_binding))
    ):
        raise HermeticTestRunnerError(
            "clean_environment_qualification_current_projection_drift"
        )
    current_truth = projection.get("current_truth")
    execution_authority = projection.get("execution_authority")
    if (
        not isinstance(current_truth, Mapping)
        or current_truth.get("current_next_action")
        != CLEAN_ENVIRONMENT_EXECUTION_NEXT
        or not isinstance(execution_authority, Mapping)
        or execution_authority.get("clean_environment_acceptance_authorized")
        is not True
    ):
        raise HermeticTestRunnerError(
            "clean_environment_qualification_current_projection_not_authorized"
        )
    attempt_contract_ref = str(execution.get("attempt_contract_ref", ""))
    attempt_contract = _load_json(
        repository_root
        / _safe_relative_path(repository_root, attempt_contract_ref)
    )
    if (
        attempt_contract.get("status")
        != "active_version_neutral_attempt_boundary"
        or attempt_contract.get("transition_rules", {}).get(
            "same_attempt_retry_allowed"
        )
        is not False
        or attempt_contract.get("transition_rules", {}).get(
            "terminal_is_immutable"
        )
        is not True
    ):
        raise HermeticTestRunnerError(
            "clean_environment_qualification_attempt_contract_invalid"
        )

    precondition = decision.get("clean_head_precondition")
    if not isinstance(precondition, Mapping):
        raise HermeticTestRunnerError(
            "clean_environment_qualification_clean_head_precondition_invalid"
        )
    branch = _git_output(
        repository_root, "rev-parse", "--abbrev-ref", "HEAD"
    ).decode("utf-8").strip()
    head = _git_output(repository_root, "rev-parse", "HEAD").decode(
        "ascii"
    ).strip()
    upstream = _git_output(
        repository_root, "rev-parse", "@{u}"
    ).decode("ascii").strip()
    worktree_status = _git_output(
        repository_root, "status", "--porcelain"
    ).decode("utf-8").strip()
    engineering_base_head = str(
        precondition.get("engineering_base_head", "")
    )
    if (
        branch != precondition.get("branch")
        or head != upstream
        or worktree_status
        or not re.fullmatch(r"[0-9a-f]{40}", engineering_base_head)
    ):
        raise HermeticTestRunnerError(
            "clean_environment_qualification_clean_head_precondition_failed"
        )
    _git_output(
        repository_root,
        "merge-base",
        "--is-ancestor",
        engineering_base_head,
        head,
    )
    return {
        "authority_ref": authority_ref,
        "authority_sha256": authority_sha256,
        "decision_id": str(decision.get("decision_id", "")),
        "attempt_id": str(execution.get("attempt_id", "")),
        "output_root": expected_output.as_posix(),
        "git_head": head,
    }


def _repository_relative_path(
    repository_root: Path,
    value: str,
    *,
    missing_code: str,
) -> Path:
    normalized = value.strip().replace("\\", "/")
    candidate = Path(normalized)
    if not normalized or candidate.is_absolute():
        raise HermeticTestRunnerError(
            "hermetic_repository_reference_outside_repository"
        )
    if ".." in candidate.parts:
        raise HermeticTestRunnerError(
            "hermetic_repository_reference_traversal"
        )
    relative = Path(*candidate.parts)
    lexical = repository_root / relative
    resolved = lexical.resolve()
    _assert_resolved_repository_path(repository_root, resolved)
    if not lexical.is_file():
        raise HermeticTestRunnerError(f"{missing_code}:{normalized}")
    return relative


def _assert_resolved_repository_path(
    repository_root: Path,
    resolved: Path,
) -> None:
    try:
        resolved.relative_to(repository_root.resolve())
    except ValueError as exc:
        raise HermeticTestRunnerError(
            "hermetic_repository_reference_symlink_escape"
        ) from exc


def _is_forbidden_repository_path(
    path: str,
    forbidden_prefixes: Sequence[str],
) -> bool:
    normalized = path.replace("\\", "/")
    return any(
        normalized == prefix or normalized.startswith(prefix + "/")
        for prefix in forbidden_prefixes
    )


def _classify_repository_reference(
    key: str,
    value: str,
    *,
    explicit_allowlist: Mapping[str, str],
    non_repository_reference_fields: Mapping[str, str],
) -> str:
    normalized = value.strip().replace("\\", "/")
    if not normalized:
        return "semantic"
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", normalized):
        return "external"
    candidate = Path(normalized)
    if candidate.is_absolute():
        return "external"
    if ".." in candidate.parts:
        return "repository_path"
    if normalized in explicit_allowlist:
        return "repository_path"
    if normalized == "pyproject.toml":
        return "repository_path"
    if candidate.parts and candidate.parts[0] in _REPOSITORY_ROOTS:
        return "repository_path"
    if key in non_repository_reference_fields:
        return "external"
    if key.startswith("repository_") and (
        "/" in normalized
        or candidate.suffix.lower() in _REPOSITORY_PATH_SUFFIXES
    ):
        return "repository_path"
    if "/" in normalized or candidate.suffix.lower() in _REPOSITORY_PATH_SUFFIXES:
        return "unclassified_path_reference"
    return "semantic"


def _repository_reference_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    for suffix in sorted(_REPOSITORY_PATH_SUFFIXES, key=len, reverse=True):
        for delimiter in ("#", ":"):
            marker = suffix + delimiter
            index = normalized.lower().find(marker)
            if index >= 0:
                return normalized[: index + len(suffix)]
    return normalized


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


def _declared_document_repository_paths(
    repository_root: Path,
    roots: Iterable[str],
) -> tuple[Path, ...]:
    """Close typed projection/event bindings without treating every string as a path."""

    admitted: set[Path] = set()
    pending = list(roots)
    while pending:
        value = pending.pop(0)
        relative = _safe_relative_path(repository_root, value)
        if relative in admitted:
            continue
        if not (repository_root / relative).is_file():
            raise HermeticTestRunnerError(
                f"typed_test_dependency_missing:{relative.as_posix()}"
            )
        admitted.add(relative)
        if relative.suffix.lower() != ".json":
            continue
        document = _load_json(repository_root / relative)
        candidate_values: list[str] = []
        for field in ("decision_binding", "implementation_binding"):
            binding = document.get(field)
            if isinstance(binding, Mapping) and isinstance(
                binding.get("ref"), str
            ):
                candidate_values.append(str(binding["ref"]))
        source_paths = document.get("source_paths")
        if isinstance(source_paths, Mapping):
            candidate_values.extend(
                str(item)
                for item in source_paths.values()
                if isinstance(item, str)
            )
        historical_policy = document.get("historical_projection_policy")
        if isinstance(historical_policy, Mapping) and isinstance(
            historical_policy.get("superseded_projection"), str
        ):
            candidate_values.append(
                str(historical_policy["superseded_projection"])
            )
        source_bindings = document.get("source_bindings")
        if isinstance(source_bindings, list):
            candidate_values.extend(
                str(row["ref"])
                for row in source_bindings
                if isinstance(row, Mapping) and isinstance(row.get("ref"), str)
            )
        for candidate in candidate_values:
            normalized = _repository_reference_path(candidate)
            path = Path(normalized.replace("\\", "/"))
            if (
                path.parts
                and path.parts[0] in _REPOSITORY_ROOTS
                and path not in admitted
            ):
                pending.append(path.as_posix())
    return tuple(sorted(admitted, key=lambda item: item.as_posix()))


def _python_module_index(
    tracked: set[str],
    source_roots: Sequence[str],
) -> dict[str, str]:
    index: dict[str, str] = {}
    for raw_root in source_roots:
        root = raw_root.strip().replace("\\", "/").strip("/")
        if not root:
            raise HermeticTestRunnerError(
                "typed_test_python_source_root_invalid"
            )
        for path in tracked:
            if not path.endswith(".py") or not path.startswith(root + "/"):
                continue
            relative = path[len(root) + 1 :]
            stem = relative[:-3]
            if stem.endswith("/__init__"):
                stem = stem[: -len("/__init__")]
            module = stem.replace("/", ".")
            if module:
                index.setdefault(module, path)
            full_module = path[:-3].replace("/", ".")
            if full_module.endswith(".__init__"):
                full_module = full_module[: -len(".__init__")]
            if full_module:
                index.setdefault(full_module, path)
    return index


def _local_import_candidates(
    path: Path,
    *,
    module_names: Sequence[str],
) -> tuple[str, ...]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        raise HermeticTestRunnerError(
            f"typed_test_python_import_parse_failed:{path.as_posix()}"
        ) from exc
    candidates: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            candidates.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            if node.module:
                candidates.add(node.module)
                candidates.update(
                    f"{node.module}.{alias.name}"
                    for alias in node.names
                    if alias.name != "*"
                )
            else:
                candidates.update(
                    alias.name for alias in node.names if alias.name != "*"
                )
    canonical_module = min(module_names, key=len) if module_names else ""
    if canonical_module:
        package = (
            canonical_module
            if path.name == "__init__.py"
            else canonical_module.rpartition(".")[0]
        )
        package_parts = package.split(".") if package else []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.level <= 0:
                continue
            retained = len(package_parts) - (node.level - 1)
            if retained < 0:
                continue
            base_parts = package_parts[:retained]
            if node.module:
                base_parts.extend(node.module.split("."))
            if base_parts:
                base = ".".join(base_parts)
                candidates.add(base)
                candidates.update(
                    f"{base}.{alias.name}"
                    for alias in node.names
                    if alias.name != "*"
                )
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.value.startswith(".")
            ):
                continue
            value = node.value
            level = len(value) - len(value.lstrip("."))
            suffix = value[level:]
            retained = len(package_parts) - (level - 1)
            if retained < 0:
                continue
            resolved_parts = package_parts[:retained]
            if suffix:
                resolved_parts.extend(suffix.split("."))
            if resolved_parts:
                candidates.add(".".join(resolved_parts))
    return tuple(sorted(candidates))


def _python_import_closure(
    repository_root: Path,
    tracked: set[str],
    *,
    seeds: Iterable[str],
    source_roots: Sequence[str],
) -> tuple[Path, ...]:
    index = _python_module_index(tracked, source_roots)
    modules_by_path: dict[str, list[str]] = {}
    for module_name, path in index.items():
        modules_by_path.setdefault(path, []).append(module_name)
    admitted: set[str] = set()
    pending = [str(value).replace("\\", "/") for value in seeds]
    while pending:
        path = pending.pop(0)
        if path in admitted:
            continue
        if path not in tracked or not path.endswith(".py"):
            raise HermeticTestRunnerError(
                f"typed_test_python_seed_invalid:{path}"
            )
        admitted.add(path)
        for candidate in _local_import_candidates(
            repository_root / path,
            module_names=modules_by_path.get(path, ()),
        ):
            resolved = index.get(candidate)
            if resolved is not None and resolved not in admitted:
                pending.append(resolved)
            parts = candidate.split(".")
            for length in range(1, len(parts)):
                parent = index.get(".".join(parts[:length]))
                if parent is not None and parent not in admitted:
                    pending.append(parent)
    return tuple(Path(path) for path in sorted(admitted))


def _bundle_paths(
    repository_root: Path,
    tracked: set[str],
    plan: CompiledTestExecutionContract,
    bundle: TestDependencyBundle,
    *,
    phase: str,
    policy: Mapping[str, Any],
) -> tuple[Path, ...]:
    configuration = bundle.configuration
    resolver = bundle.resolver_type
    if resolver == "python_import_closure":
        source_roots = configuration.get("source_roots")
        if not isinstance(source_roots, list) or not all(
            isinstance(item, str) and item.strip() for item in source_roots
        ):
            raise HermeticTestRunnerError(
                "typed_test_python_source_roots_invalid"
            )
        seeds = [
            row.test_path
            for row in plan.test_modules
            if row.phase == phase and bundle.bundle_id in row.dependency_bundle_ids
        ]
        return _python_import_closure(
            repository_root,
            tracked,
            seeds=seeds,
            source_roots=source_roots,
        )
    if resolver == "runtime_resource_registry_closure":
        registry_ref = configuration.get("registry_ref")
        if not isinstance(registry_ref, str) or not registry_ref.strip():
            raise HermeticTestRunnerError(
                "typed_test_runtime_registry_ref_invalid"
            )
        try:
            paths = set(load_runtime_resource_registry(
                repository_root, registry_ref
            ).package_paths())
        except RuntimeResourceRegistryError as exc:
            raise HermeticTestRunnerError(exc.code) from exc
        policy_fields = configuration.get("policy_contract_fields", [])
        if not isinstance(policy_fields, list) or not all(
            isinstance(item, str) and item.strip()
            for item in policy_fields
        ):
            raise HermeticTestRunnerError(
                "typed_test_runtime_policy_contract_fields_invalid"
            )
        for field in policy_fields:
            value = policy.get(field)
            if not isinstance(value, str) or not value.strip():
                raise HermeticTestRunnerError(
                    f"typed_test_runtime_policy_contract_ref_missing:{field}"
                )
            paths.add(_safe_relative_path(repository_root, value))
        return tuple(sorted(paths, key=lambda item: item.as_posix()))
    if resolver == "reference_role_repository_closure":
        registry_ref = configuration.get("registry_ref")
        if not isinstance(registry_ref, str) or not registry_ref.strip():
            raise HermeticTestRunnerError(
                "typed_test_reference_role_registry_ref_invalid"
            )
        try:
            return load_reference_role_registry(
                repository_root, registry_ref
            ).package_paths()
        except ReferenceRoleRegistryError as exc:
            raise HermeticTestRunnerError(exc.code) from exc
    if resolver == "current_projection_binding_and_source_paths_closure":
        policy_field = configuration.get("policy_field")
        if policy_field != "host_current_program_projection_ref":
            raise HermeticTestRunnerError(
                "typed_test_current_projection_policy_field_invalid"
            )
        projection_ref = policy.get(policy_field)
        if not isinstance(projection_ref, str) or not projection_ref.strip():
            raise HermeticTestRunnerError(
                "typed_test_current_projection_ref_invalid"
            )
        validate_host_current_program_projection(
            repository_root, projection_ref
        )
        return _declared_document_repository_paths(
            repository_root, [projection_ref]
        )
    if resolver == "immutable_event_root_closure":
        roots = configuration.get("roots")
        if not isinstance(roots, list) or not roots or not all(
            isinstance(item, str) and item.strip() for item in roots
        ):
            raise HermeticTestRunnerError(
                "typed_test_immutable_event_roots_invalid"
            )
        return _declared_document_repository_paths(repository_root, roots)
    if resolver == "tracked_fixture_prefix":
        prefix = configuration.get("path")
        suffixes = configuration.get("suffixes")
        if (
            not isinstance(prefix, str)
            or not prefix.strip()
            or not isinstance(suffixes, list)
            or not suffixes
            or not all(isinstance(item, str) and item for item in suffixes)
        ):
            raise HermeticTestRunnerError(
                "typed_test_fixture_prefix_invalid"
            )
        normalized = prefix.strip().replace("\\", "/").rstrip("/")
        return tuple(
            Path(path)
            for path in sorted(
                path
                for path in tracked
                if path.startswith(normalized + "/")
                and any(path.endswith(suffix) for suffix in suffixes)
            )
        )
    raise HermeticTestRunnerError(
        f"typed_test_dependency_resolver_unknown:{resolver}"
    )


def compile_test_dependency_bundles(
    repository_root: Path,
    tracked: set[str],
    plan: CompiledTestExecutionContract,
    *,
    phase: str,
    policy: Mapping[str, Any],
) -> dict[str, tuple[Path, ...]]:
    selected_bundle_ids = {
        bundle_id
        for row in plan.test_modules
        if row.phase == phase
        for bundle_id in row.dependency_bundle_ids
    }
    return {
        bundle.bundle_id: _bundle_paths(
            repository_root,
            tracked,
            plan,
            bundle,
            phase=phase,
            policy=policy,
        )
        for bundle in plan.dependency_bundles
        if bundle.bundle_id in selected_bundle_ids
    }


def _static_string_constants(tree: ast.Module) -> dict[str, str]:
    constants: dict[str, str] = {}
    pending: list[tuple[str, ast.AST]] = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                pending.append((target.id, node.value))
        elif isinstance(node, ast.AnnAssign) and isinstance(
            node.target, ast.Name
        ):
            pending.append((node.target.id, node.value))
    changed = True
    while changed:
        changed = False
        for name, value in pending:
            if name in constants:
                continue
            resolved: str | None = None
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                resolved = value.value
            elif isinstance(value, ast.Name):
                resolved = constants.get(value.id)
            elif isinstance(value, ast.BinOp) and isinstance(value.op, ast.Add):
                left = (
                    value.left.value
                    if isinstance(value.left, ast.Constant)
                    and isinstance(value.left.value, str)
                    else constants.get(value.left.id)
                    if isinstance(value.left, ast.Name)
                    else None
                )
                right = (
                    value.right.value
                    if isinstance(value.right, ast.Constant)
                    and isinstance(value.right.value, str)
                    else constants.get(value.right.id)
                    if isinstance(value.right, ast.Name)
                    else None
                )
                if left is not None and right is not None:
                    resolved = left + right
            if resolved is not None:
                constants[name] = resolved
                changed = True
    return constants


def _constant_string(node: ast.AST, constants: Mapping[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    return None


def _contains_root_name(node: ast.AST) -> bool:
    return any(
        isinstance(value, ast.Name) and value.id == "ROOT"
        for value in ast.walk(node)
    )


def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def _is_typed_test_resource_call(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and _call_name(node) == (
        "repository_test_resource"
    )


def audit_disposable_test_resource_contract(
    repository_root: Path,
    plan: CompiledTestExecutionContract,
    bundle_paths: Mapping[str, Sequence[Path]],
) -> None:
    direct_read_methods = {
        "read_text",
        "read_bytes",
        "open",
        "is_file",
        "exists",
    }
    copy_functions = {"copy", "copy2", "copyfile"}
    module_by_path = plan.module_by_path
    for test_path in plan.test_paths("disposable_current_gate"):
        module = module_by_path[test_path]
        try:
            tree = ast.parse(
                (repository_root / test_path).read_text(encoding="utf-8"),
                filename=test_path,
            )
        except (OSError, SyntaxError) as exc:
            raise HermeticTestRunnerError(
                f"typed_test_resource_static_audit_parse_failed:{test_path}"
            ) from exc
        constants = _static_string_constants(tree)
        declared = set(module.dependency_bundle_ids)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            call_name = _call_name(node)
            if call_name == "repository_test_resource":
                if len(node.args) < 3:
                    raise HermeticTestRunnerError(
                        f"typed_test_resource_helper_shape_invalid:{test_path}"
                    )
                bundle_id = _constant_string(node.args[1], constants)
                if bundle_id is None or bundle_id not in declared:
                    raise HermeticTestRunnerError(
                        f"typed_test_resource_bundle_undeclared:{test_path}"
                    )
                relative = _constant_string(node.args[2], constants)
                if relative is not None:
                    normalized = Path(relative.replace("\\", "/"))
                    admitted = {
                        path.as_posix()
                        for path in bundle_paths.get(bundle_id, ())
                    }
                    if normalized.as_posix() not in admitted:
                        raise HermeticTestRunnerError(
                            "typed_test_resource_not_in_declared_bundle:"
                            f"{test_path}:{normalized.as_posix()}"
                        )
                continue
            direct_node: ast.AST | None = None
            if (
                isinstance(node.func, ast.Attribute)
                and call_name in direct_read_methods
            ):
                direct_node = node.func.value
            elif call_name in copy_functions and node.args:
                direct_node = node.args[0]
            elif call_name == "open" and node.args:
                direct_node = node.args[0]
            if (
                direct_node is not None
                and not _is_typed_test_resource_call(direct_node)
                and _contains_root_name(direct_node)
            ):
                raise HermeticTestRunnerError(
                    f"typed_test_resource_direct_root_read_forbidden:{test_path}"
                )


def _policy_contract_paths(
    repository_root: Path,
    policy: Mapping[str, Any],
) -> tuple[Path, ...]:
    paths: set[Path] = set()
    test_execution_registry_ref = policy.get(
        "test_execution_contract_registry_ref"
    )
    if test_execution_registry_ref is not None:
        if (
            not isinstance(test_execution_registry_ref, str)
            or not test_execution_registry_ref.strip()
        ):
            raise HermeticTestRunnerError(
                "test_execution_contract_registry_ref_invalid"
            )
        paths.add(
            _safe_relative_path(
                repository_root, test_execution_registry_ref
            )
        )
    reference_policy = policy.get("repository_reference_policy")
    if isinstance(reference_policy, Mapping) and reference_policy.get(
        "schema_version"
    ) == REPOSITORY_REFERENCE_POLICY_V2_SCHEMA:
        reference_role_registry_ref = reference_policy.get(
            "reference_role_registry_ref"
        )
        if (
            not isinstance(reference_role_registry_ref, str)
            or not reference_role_registry_ref.strip()
        ):
            raise HermeticTestRunnerError(
                "reference_role_registry_ref_invalid"
            )
        try:
            reference_role_registry = load_reference_role_registry(
                repository_root,
                reference_role_registry_ref,
            )
        except ReferenceRoleRegistryError as exc:
            raise HermeticTestRunnerError(
                exc.code,
                failure_envelope=exc.failure_envelope,
            ) from exc
        paths.update(reference_role_registry.package_paths())
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
    registry_ref = policy.get("runtime_resource_registry_ref")
    if registry_ref is not None:
        if not isinstance(registry_ref, str) or not registry_ref.strip():
            raise HermeticTestRunnerError(
                "runtime_resource_registry_ref_invalid"
            )
        try:
            registry = load_runtime_resource_registry(
                repository_root,
                registry_ref,
            )
        except RuntimeResourceRegistryError as exc:
            raise HermeticTestRunnerError(exc.code) from exc
        paths.update(registry.package_paths())
    parity_ref = policy.get("semantic_parity_contract_ref")
    if parity_ref is not None:
        if not isinstance(parity_ref, str) or not parity_ref.strip():
            raise HermeticTestRunnerError("semantic_parity_contract_ref_invalid")
        paths.add(_safe_relative_path(repository_root, parity_ref))
    projection_ref = policy.get("host_current_program_projection_ref")
    if projection_ref is not None:
        if not isinstance(projection_ref, str) or not projection_ref.strip():
            raise HermeticTestRunnerError(
                "current_projection_ref_invalid"
            )
        validate_host_current_program_projection(
            repository_root,
            projection_ref,
        )
        paths.update(
            _declared_document_repository_paths(
                repository_root,
                [projection_ref],
            )
        )
    return tuple(sorted(paths, key=lambda item: item.as_posix()))


def compile_repository_inventory(
    repository_root: Path,
    manifest: Mapping[str, Any],
) -> CompiledRepositoryInventory:
    repository_root = repository_root.resolve()
    raw = _git_output(repository_root, "ls-files", "-z")
    tracked = {
        item.decode("utf-8").replace("\\", "/")
        for item in raw.split(b"\0")
        if item
    }
    execution_plan = _load_test_execution_plan(repository_root, manifest)
    policy = manifest["hermetic_package_policy"]
    reference_policy = policy.get("repository_reference_policy")
    if not isinstance(reference_policy, Mapping):
        raise HermeticTestRunnerError(
            "hermetic_repository_reference_policy_missing"
        )
    reference_policy_schema = reference_policy.get("schema_version")
    if reference_policy_schema not in {
        REPOSITORY_REFERENCE_POLICY_SCHEMA,
        REPOSITORY_REFERENCE_POLICY_V2_SCHEMA,
    }:
        raise HermeticTestRunnerError(
            "hermetic_repository_reference_policy_schema_invalid"
        )
    required_policy = {
        "tracked_repository_paths_allowed": True,
        "untracked_or_ignored_reference_behavior": "fail_closed",
        "unknown_reference_behavior": "fail_closed",
        "traversal_or_symlink_escape_behavior": "fail_closed",
        "semantic_or_external_reference_behavior": "observe_not_package",
    }
    if any(reference_policy.get(key) != expected for key, expected in required_policy.items()):
        raise HermeticTestRunnerError(
            "hermetic_repository_reference_policy_boundary_invalid"
        )
    forbidden_values = reference_policy.get("forbidden_prefixes")
    if not isinstance(forbidden_values, list) or not all(
        isinstance(item, str) and item.strip()
        for item in forbidden_values
    ):
        raise HermeticTestRunnerError(
            "hermetic_repository_forbidden_prefixes_invalid"
        )
    forbidden_prefixes = tuple(
        sorted(
            {
                item.strip().replace("\\", "/").rstrip("/")
                for item in forbidden_values
            }
        )
    )
    if ".codex_runtime" not in forbidden_prefixes:
        raise HermeticTestRunnerError(
            "hermetic_repository_runtime_prefix_not_forbidden"
        )

    allowlist_rows = reference_policy.get("explicit_allowlist")
    if not isinstance(allowlist_rows, list):
        raise HermeticTestRunnerError(
            "hermetic_repository_explicit_allowlist_invalid"
        )
    explicit_allowlist: dict[str, str] = {}
    for row in allowlist_rows:
        if not isinstance(row, Mapping) or set(row) != {
            "path",
            "sha256",
            "classification",
            "reason",
        }:
            raise HermeticTestRunnerError(
                "hermetic_repository_explicit_allowlist_row_invalid"
            )
        path_value = str(row["path"]).strip().replace("\\", "/")
        digest = str(row["sha256"]).strip().lower()
        if (
            not path_value
            or path_value in explicit_allowlist
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or not str(row["classification"]).strip()
            or not str(row["reason"]).strip()
        ):
            raise HermeticTestRunnerError(
                "hermetic_repository_explicit_allowlist_row_invalid"
            )
        relative = _repository_relative_path(
            repository_root,
            path_value,
            missing_code="hermetic_repository_explicit_allowlist_file_missing",
        )
        normalized = relative.as_posix()
        if _is_forbidden_repository_path(normalized, forbidden_prefixes):
            raise HermeticTestRunnerError(
                f"hermetic_repository_forbidden_path:{normalized}"
            )
        if _sha256_file(repository_root / relative) != digest:
            raise HermeticTestRunnerError(
                "hermetic_repository_explicit_allowlist_digest_mismatch"
            )
        explicit_allowlist[normalized] = digest

    reference_role_registry: ReferenceRoleRegistry | None = None
    non_repository_reference_fields: dict[str, str] = {}
    if reference_policy_schema == REPOSITORY_REFERENCE_POLICY_SCHEMA:
        non_repository_rows = reference_policy.get(
            "non_repository_reference_fields"
        )
        if not isinstance(non_repository_rows, list):
            raise HermeticTestRunnerError(
                "hermetic_non_repository_reference_fields_invalid"
            )
        for row in non_repository_rows:
            if not isinstance(row, Mapping) or set(row) != {
                "field",
                "classification",
                "reason",
            }:
                raise HermeticTestRunnerError(
                    "hermetic_non_repository_reference_field_row_invalid"
                )
            field = str(row["field"]).strip()
            classification = str(row["classification"]).strip()
            reason = str(row["reason"]).strip()
            if (
                not field
                or field in non_repository_reference_fields
                or not classification
                or not reason
            ):
                raise HermeticTestRunnerError(
                    "hermetic_non_repository_reference_field_row_invalid"
                )
            non_repository_reference_fields[field] = classification
    else:
        expected_v2_fields = {
            "schema_version",
            "tracked_repository_paths_allowed",
            "explicit_allowlist",
            "reference_role_registry_ref",
            "forbidden_prefixes",
            "untracked_or_ignored_reference_behavior",
            "unknown_reference_behavior",
            "traversal_or_symlink_escape_behavior",
            "semantic_or_external_reference_behavior",
        }
        if set(reference_policy) != expected_v2_fields:
            raise HermeticTestRunnerError(
                "hermetic_repository_reference_policy_v2_surface_invalid"
            )
        registry_ref = reference_policy.get("reference_role_registry_ref")
        if not isinstance(registry_ref, str) or not registry_ref.strip():
            raise HermeticTestRunnerError(
                "reference_role_registry_ref_invalid"
            )
        try:
            reference_role_registry = load_reference_role_registry(
                repository_root,
                registry_ref,
            )
        except ReferenceRoleRegistryError as exc:
            raise HermeticTestRunnerError(
                exc.code,
                failure_envelope=exc.failure_envelope,
            ) from exc

    sources: dict[str, set[str]] = {}
    pending: list[str] = []

    def admit(value: str, source: str) -> None:
        relative = _repository_relative_path(
            repository_root,
            value,
            missing_code="hermetic_repository_reference_unknown",
        )
        normalized = relative.as_posix()
        if _is_forbidden_repository_path(normalized, forbidden_prefixes):
            raise HermeticTestRunnerError(
                f"hermetic_repository_forbidden_path:{normalized}"
            )
        if normalized not in tracked and normalized not in explicit_allowlist:
            raise HermeticTestRunnerError(
                "hermetic_repository_reference_untracked_or_ignored:"
                f"{normalized}"
            )
        if normalized not in sources:
            sources[normalized] = set()
            pending.append(normalized)
        sources[normalized].add(source)

    for value in policy["required_runner_files"]:
        admit(str(value), "required_runner_file")
    for value in policy.get("repository_seed_paths", []):
        admit(str(value), "repository_seed")
    selected_paths = (
        execution_plan.test_paths("disposable_current_gate")
        if execution_plan is not None
        else _selected_test_paths(manifest)
    )
    selected_disposable_test_paths = set(selected_paths)
    for value in selected_paths:
        admit(value, "selected_test")
    for path in _policy_contract_paths(repository_root, policy):
        if (
            execution_plan is not None
            and path.as_posix().startswith("tests/")
            and path.suffix.lower() == ".py"
            and path.as_posix() not in selected_disposable_test_paths
        ):
            continue
        admit(path.as_posix(), "policy_contract")
    dependency_bundle_paths: dict[str, tuple[Path, ...]] = {}
    if execution_plan is not None:
        dependency_bundle_paths = compile_test_dependency_bundles(
            repository_root,
            tracked,
            execution_plan,
            phase="disposable_current_gate",
            policy=policy,
        )
        audit_disposable_test_resource_contract(
            repository_root,
            execution_plan,
            dependency_bundle_paths,
        )
        for bundle_id, bundle_paths in dependency_bundle_paths.items():
            for path in bundle_paths:
                admit(path.as_posix(), f"typed_test_dependency:{bundle_id}")
    prefix_rows = policy.get("repository_prefixes", [])
    if execution_plan is not None and prefix_rows:
        raise HermeticTestRunnerError(
            "typed_test_dependency_broad_repository_prefix_forbidden"
        )
    for prefix_row in prefix_rows:
        if not isinstance(prefix_row, Mapping):
            raise HermeticTestRunnerError("hermetic_repository_prefix_invalid")
        prefix = str(prefix_row.get("path", "")).strip().replace("\\", "/").rstrip("/")
        suffixes = prefix_row.get("suffixes")
        if not prefix or not isinstance(suffixes, list) or not all(
            isinstance(item, str) for item in suffixes
        ):
            raise HermeticTestRunnerError("hermetic_repository_prefix_incomplete")
        for path in sorted(
            path
            for path in tracked
            if path.startswith(prefix + "/")
            and any(path.endswith(suffix) for suffix in suffixes)
        ):
            admit(path, "tracked_prefix")

    semantic_or_external_reference_count = 0
    reference_documents: list[tuple[str, Mapping[str, Any]]] = []
    while pending:
        value = pending.pop(0)
        relative = _repository_relative_path(
            repository_root,
            value,
            missing_code="hermetic_repository_reference_unknown",
        )
        if relative.suffix.lower() != ".json":
            continue
        document = _load_json(repository_root / relative)
        if reference_role_registry is not None:
            reference_documents.append((relative.as_posix(), document))
            reference_rows = [
                reference_role_registry.classify(
                    document_ref=relative.as_posix(),
                    json_pointer=pointer,
                    field=key,
                    value=ref,
                )
                for key, ref, pointer in iter_reference_strings(document)
            ]
            for observation in reference_rows:
                if observation.role is None:
                    continue
                if observation.role != "repository_resource":
                    semantic_or_external_reference_count += 1
                    continue
                repository_value = _repository_reference_path(
                    observation.value
                )
                if (
                    execution_plan is not None
                    and repository_value.startswith("tests/")
                    and repository_value.endswith(".py")
                    and repository_value
                    not in selected_disposable_test_paths
                ):
                    continue
                admit(repository_value, "recursive_reference")
            continue
        for key, ref in sorted(set(_repository_ref_strings(document))):
            normalized = ref.replace("\\", "/")
            classification = _classify_repository_reference(
                key,
                normalized,
                explicit_allowlist=explicit_allowlist,
                non_repository_reference_fields=(
                    non_repository_reference_fields
                ),
            )
            if classification == "unclassified_path_reference":
                raise HermeticTestRunnerError(
                    "hermetic_repository_reference_classification_missing:"
                    f"{key}:{normalized}"
                )
            if classification != "repository_path":
                semantic_or_external_reference_count += 1
                continue
            repository_value = _repository_reference_path(normalized)
            if (
                execution_plan is not None
                and repository_value.startswith("tests/")
                and repository_value.endswith(".py")
                and repository_value not in selected_disposable_test_paths
            ):
                continue
            admit(repository_value, "recursive_reference")

    reference_role_report: ReferenceRoleReport | None = None
    if reference_role_registry is not None:
        reference_role_report = collect_reference_roles(
            reference_role_registry,
            reference_documents,
        )
        if reference_role_report.unknowns:
            envelope = reference_role_report.failure_envelope()
            raise HermeticTestRunnerError(
                str(envelope["code"]),
                failure_envelope=envelope,
            )

    rows = [
        {
            "path": path,
            "admission": (
                "tracked" if path in tracked else "explicit_allowlist"
            ),
            "sources": sorted(sources[path]),
        }
        for path in sorted(sources)
    ]
    closure_digest = _sha256_bytes(
        json.dumps(
            rows,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    return CompiledRepositoryInventory(
        paths=tuple(Path(row["path"]) for row in rows),
        tracked_paths=tuple(
            row["path"] for row in rows if row["admission"] == "tracked"
        ),
        explicit_allowlist_paths=tuple(
            row["path"]
            for row in rows
            if row["admission"] == "explicit_allowlist"
        ),
        recursive_reference_paths=tuple(
            row["path"]
            for row in rows
            if "recursive_reference" in row["sources"]
        ),
        semantic_or_external_reference_count=(
            semantic_or_external_reference_count
        ),
        closure_digest=closure_digest,
        reference_role_report=reference_role_report,
    )


def discover_repository_paths(
    repository_root: Path,
    manifest: Mapping[str, Any],
) -> tuple[Path, ...]:
    return compile_repository_inventory(repository_root, manifest).paths


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
    distribution_roots: set[str] = set()
    for distribution in importlib.metadata.distributions():
        try:
            root = Path(distribution.locate_file("")).resolve()
        except (OSError, TypeError, ValueError):
            continue
        if root.is_dir():
            distribution_roots.add(str(root))
    sysconfig_paths = sysconfig.get_paths()
    typed_roots = {
        "sys_prefix": str(Path(sys.prefix).resolve()),
        "sys_base_prefix": str(Path(sys.base_prefix).resolve()),
        "purelib_root": str(
            Path(str(sysconfig_paths.get("purelib", sys.prefix))).resolve()
        ),
        "platlib_root": str(
            Path(str(sysconfig_paths.get("platlib", sys.prefix))).resolve()
        ),
        "installed_distribution_roots": sorted(distribution_roots),
    }
    return {
        "python_executable": str(Path(sys.executable).resolve()),
        "python_version": sys.version,
        "site_paths": site_paths,
        "typed_roots": typed_roots,
        "typed_environment_fingerprint": _sha256_bytes(
            _canonical_bytes(typed_roots)
        ),
        "installed_distributions": [
            {"name": name, "version": version}
            for name, version in distributions
        ],
    }


def _environment_root_fingerprint(
    root_id: str,
    absolute_path: str | Sequence[str],
) -> str:
    paths = (
        [absolute_path]
        if isinstance(absolute_path, str)
        else list(absolute_path)
    )
    return _sha256_bytes(
        _canonical_bytes(
            {
                "root_id": root_id,
                "absolute_paths": paths,
            }
        )
    )


def _typed_environment_root_rows(
    *,
    package_root: Path,
    runtime_root: Path,
    disposable_parent: Path,
    python_environment: Mapping[str, Any],
) -> list[dict[str, Any]]:
    frozen = python_environment.get("typed_roots")
    if not isinstance(frozen, Mapping):
        raise HermeticTestRunnerError(
            "typed_environment_frozen_roots_missing"
        )
    values: dict[str, str | list[str]] = {
        "disposable_package_root": str(package_root.resolve()),
        "disposable_repository_root": str(runtime_root.resolve()),
        "disposable_temporary_root": str(disposable_parent.resolve()),
        "sys_prefix": str(frozen.get("sys_prefix", "")),
        "sys_base_prefix": str(frozen.get("sys_base_prefix", "")),
        "purelib_root": str(frozen.get("purelib_root", "")),
        "platlib_root": str(frozen.get("platlib_root", "")),
        "installed_distribution_roots": [
            str(value)
            for value in frozen.get("installed_distribution_roots", [])
        ],
    }
    metadata = {
        "disposable_package_root": (
            "disposable_package",
            "<ENV:DISPOSABLE_PACKAGE_ROOT>",
            "runner.package_root",
        ),
        "disposable_repository_root": (
            "disposable_repository",
            "<ENV:DISPOSABLE_REPOSITORY_ROOT>",
            "runner.materialized_repository_root",
        ),
        "disposable_temporary_root": (
            "disposable_temporary_parent",
            "<ENV:DISPOSABLE_TEMPORARY_ROOT>",
            "runner.temporary_parent",
        ),
        "sys_prefix": (
            "python_prefix",
            "<ENV:PYTHON_PREFIX>",
            "host_frozen_python_environment.sys_prefix",
        ),
        "sys_base_prefix": (
            "python_base_prefix",
            "<ENV:PYTHON_BASE_PREFIX>",
            "host_frozen_python_environment.sys_base_prefix",
        ),
        "purelib_root": (
            "python_purelib",
            "<ENV:PYTHON_PURELIB_ROOT>",
            "host_frozen_python_environment.sysconfig.purelib",
        ),
        "platlib_root": (
            "python_platlib",
            "<ENV:PYTHON_PLATLIB_ROOT>",
            "host_frozen_python_environment.sysconfig.platlib",
        ),
        "installed_distribution_roots": (
            "installed_distribution_roots",
            "<ENV:INSTALLED_DISTRIBUTION_ROOT>",
            "host_frozen_python_environment.importlib_metadata",
        ),
    }
    rows: list[dict[str, Any]] = []
    for root_id, absolute_path in values.items():
        if (
            (isinstance(absolute_path, str) and not absolute_path.strip())
            or (
                isinstance(absolute_path, list)
                and (
                    not absolute_path
                    or absolute_path != sorted(set(absolute_path))
                    or any(not item.strip() for item in absolute_path)
                )
            )
        ):
            raise HermeticTestRunnerError(
                f"typed_environment_root_invalid:{root_id}"
            )
        role, token, source = metadata[root_id]
        rows.append(
            {
                "root_id": root_id,
                "role": role,
                "absolute_path": absolute_path,
                "projection_token": token,
                "source": source,
                "digest_or_environment_fingerprint": (
                    _environment_root_fingerprint(root_id, absolute_path)
                ),
            }
        )
    return rows


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
    execution_plan = _load_test_execution_plan(repository_root, manifest)
    if execution_plan is not None:
        disposable_tests = set(
            execution_plan.test_paths("disposable_current_gate")
        )
        policy_contract_paths = tuple(
            path
            for path in policy_contract_paths
            if not (
                path.as_posix().startswith("tests/")
                and path.suffix.lower() == ".py"
                and path.as_posix() not in disposable_tests
            )
        )
    if repository_paths is None:
        compiled_inventory = compile_repository_inventory(
            repository_root,
            manifest,
        )
        paths = compiled_inventory.paths
    else:
        paths = tuple(
            sorted(
                {
                    _safe_relative_path(repository_root, item.as_posix())
                    for item in repository_paths
                },
                key=lambda item: item.as_posix(),
            )
        )
        explicit_rows = [
            {
                "path": path.as_posix(),
                "admission": "explicit_fixture_inventory",
                "sources": ["explicit_fixture_inventory"],
            }
            for path in paths
        ]
        compiled_inventory = CompiledRepositoryInventory(
            paths=paths,
            tracked_paths=(),
            explicit_allowlist_paths=tuple(
                path.as_posix() for path in paths
            ),
            recursive_reference_paths=(),
            semantic_or_external_reference_count=0,
            closure_digest=_sha256_bytes(
                json.dumps(
                    explicit_rows,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ),
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
    frozen_inventory_rows = [
        {
            "path": row["path"],
            "sha256": row["sha256"],
            "bytes": row["bytes"],
        }
        for row in entries
    ]
    frozen_inventory_digest = _sha256_bytes(
        json.dumps(
            frozen_inventory_rows,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )

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
        "repository_inventory_closure": compiled_inventory.as_dict(),
        "frozen_repository_inventory_digest": frozen_inventory_digest,
        "python_environment": _python_environment_inventory(),
        "repository_files": entries,
        "external_read_only_dependencies": external_entries,
        "credential_environment_names_removed": sorted(_CREDENTIAL_ENV_NAMES),
    }
    authority_binding = manifest.get(
        "clean_environment_qualification_authority_binding"
    )
    if isinstance(authority_binding, Mapping):
        payload["clean_environment_qualification_authority_binding"] = dict(
            authority_binding
        )
    payload["semantic_digest"] = _sha256_bytes(_canonical_bytes(payload))
    _write_json(package_root / "package_manifest.json", payload)
    return payload


def _materialize_package(
    package_root: Path,
    package_manifest: Mapping[str, Any],
    destination: Path,
) -> None:
    rows = package_manifest.get("repository_files")
    if not isinstance(rows, list) or not rows:
        raise HermeticTestRunnerError(
            "hermetic_frozen_inventory_rows_invalid"
        )
    frozen_rows: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise HermeticTestRunnerError(
                "hermetic_frozen_inventory_row_invalid"
            )
        path_value = str(row.get("path", "")).replace("\\", "/")
        relative = Path(path_value)
        if (
            not path_value
            or relative.is_absolute()
            or ".." in relative.parts
            or path_value in seen_paths
            or not isinstance(row.get("sha256"), str)
            or not isinstance(row.get("bytes"), int)
            or not isinstance(row.get("ref"), str)
        ):
            raise HermeticTestRunnerError(
                "hermetic_frozen_inventory_row_invalid"
            )
        seen_paths.add(path_value)
        frozen_rows.append(
            {
                "path": path_value,
                "sha256": row["sha256"],
                "bytes": row["bytes"],
            }
        )
    if [row["path"] for row in frozen_rows] != sorted(seen_paths):
        raise HermeticTestRunnerError(
            "hermetic_frozen_inventory_order_invalid"
        )
    digest = _sha256_bytes(
        json.dumps(
            frozen_rows,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    if digest != package_manifest.get("frozen_repository_inventory_digest"):
        raise HermeticTestRunnerError(
            "hermetic_frozen_inventory_digest_mismatch"
        )
    destination.mkdir(parents=True, exist_ok=False)
    destination_root = destination.resolve()
    for row in rows:
        source = package_root / str(row["ref"])
        target = destination / str(row["path"])
        try:
            target.resolve().relative_to(destination_root)
        except ValueError as exc:
            raise HermeticTestRunnerError(
                "hermetic_materialized_path_escape"
            ) from exc
        if (
            not source.is_file()
            or source.stat().st_size != row["bytes"]
            or _sha256_file(source) != row["sha256"]
        ):
            raise HermeticTestRunnerError(
                "hermetic_package_object_digest_mismatch"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if _sha256_file(target) != row["sha256"]:
            raise HermeticTestRunnerError("hermetic_materialized_file_digest_mismatch")


def _selected_test_paths(
    manifest: Mapping[str, Any],
    execution_plan: CompiledTestExecutionContract | None = None,
    *,
    phase: str | None = None,
) -> tuple[str, ...]:
    if execution_plan is not None:
        return execution_plan.test_paths(phase)
    paths = {
        str(path)
        for suite in manifest["suites"]
        if suite["selected"]
        for path in suite["test_paths"]
    }
    return tuple(sorted(paths))


def _suite_memberships(
    manifest: Mapping[str, Any],
    nodeid: str,
    execution_plan: CompiledTestExecutionContract | None = None,
) -> list[dict[str, Any]]:
    if execution_plan is not None:
        try:
            membership = execution_plan.membership(nodeid)
        except TestExecutionContractError as exc:
            raise HermeticTestRunnerError(exc.code) from exc
        return [
            {
                "suite_id": membership["phase"],
                "proof_class": membership["phase"],
                "gates_current_release": membership[
                    "gates_current_candidate"
                ],
                "execution_location": membership["location"],
                "dependency_bundle_ids": membership[
                    "dependency_bundle_ids"
                ],
            }
        ]
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
    execution_plan: CompiledTestExecutionContract | None = None,
) -> list[dict[str, Any]]:
    results = []
    tests = raw.get("tests")
    if not isinstance(tests, list):
        raise HermeticTestRunnerError("hermetic_raw_test_capture_invalid")
    for row in tests:
        if not isinstance(row, Mapping):
            raise HermeticTestRunnerError("hermetic_raw_test_row_invalid")
        memberships = _suite_memberships(
            manifest,
            str(row["nodeid"]),
            execution_plan,
        )
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
basetemp = Path(sys.argv[5]).resolve()
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
args = [
    *test_paths,
    "-p",
    "no:terminal",
    "--capture=fd",
    "--strict-markers",
    f"--basetemp={basetemp}",
]
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
    execution_plan: CompiledTestExecutionContract | None = None,
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
    pytest_basetemp = disposable_parent / f"pytest_{run_id}"
    selected_test_paths = _selected_test_paths(
        manifest,
        execution_plan,
        phase=(
            "disposable_current_gate"
            if execution_plan is not None
            else None
        ),
    )
    command = [
        sys.executable,
        "-I",
        "-c",
        _BOOTSTRAP,
        str(runtime_root),
        str(plugin_path),
        json.dumps(list(selected_test_paths)),
        json.dumps(package_manifest["python_environment"]["site_paths"]),
        str(pytest_basetemp),
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
    tests = _objectize_raw_capture(
        raw=raw,
        manifest=manifest,
        store=store,
        execution_plan=execution_plan,
    )
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
        "selected_test_paths": list(selected_test_paths),
        "execution_phase": (
            "disposable_current_gate"
            if execution_plan is not None
            else "legacy_combined_active_suite"
        ),
        "pytest_basetemp": str(pytest_basetemp.resolve()),
        "pytest_basetemp_under_disposable_temporary_root": (
            pytest_basetemp.resolve().is_relative_to(
                disposable_parent.resolve()
            )
        ),
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
        "typed_environment_roots": _typed_environment_root_rows(
            package_root=package_root,
            runtime_root=runtime_root,
            disposable_parent=disposable_parent,
            python_environment=package_manifest["python_environment"],
        ),
    }
    _write_json(package_root / "runs" / run_id / "terminal_result.json", result)
    return result


def run_host_phase(
    *,
    run_id: str,
    phase: str,
    repository_root: Path,
    manifest: Mapping[str, Any],
    execution_plan: CompiledTestExecutionContract,
    store: ContentAddressedStore,
    temporary_root: Path,
    python_environment: Mapping[str, Any],
) -> dict[str, Any]:
    selected_test_paths = execution_plan.test_paths(phase)
    if not selected_test_paths:
        return {
            "schema_version": TERMINAL_SCHEMA,
            "run_id": run_id,
            "execution_phase": phase,
            "status": "pass_no_selected_test_modules",
            "pytest_exit_code": 0,
            "captured_session_exit_code": 0,
            "selected_test_paths": [],
            "test_counts": {},
            "tests": [],
            "collection_errors": [],
            "current_gate_all_green": True,
            "gating_failure_nodeids": [],
            "historical_finding_nodeids": [],
            "credential_environment_removed": sorted(_CREDENTIAL_ENV_NAMES),
        }
    phase_root = temporary_root / run_id
    phase_root.mkdir(parents=True, exist_ok=False)
    raw_capture = phase_root / "raw_capture.json"
    pytest_basetemp = phase_root / "pytest_basetemp"
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
        str(repository_root),
        str(plugin_path),
        json.dumps(list(selected_test_paths)),
        json.dumps(python_environment["site_paths"]),
        str(pytest_basetemp),
    ]
    completed = subprocess.run(
        command,
        cwd=repository_root,
        env=env,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    process_stdout = store.put_bytes(completed.stdout)
    process_stderr = store.put_bytes(completed.stderr)
    if not raw_capture.is_file():
        raise HermeticTestRunnerError(
            f"hermetic_host_phase_capture_not_materialized:{phase}"
        )
    raw = _load_json(raw_capture)
    tests = _objectize_raw_capture(
        raw=raw,
        manifest=manifest,
        store=store,
        execution_plan=execution_plan,
    )
    collection_errors = raw.get("collection_errors", [])
    collection_ref = store.put_bytes(
        json.dumps(
            collection_errors,
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
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
        else "pass_non_gating_with_historical_findings"
        if current_gate_all_green
        else "failed_current_gate"
    )
    result = {
        "schema_version": TERMINAL_SCHEMA,
        "run_id": run_id,
        "execution_phase": phase,
        "status": status,
        "pytest_exit_code": int(completed.returncode),
        "captured_session_exit_code": int(raw["session_exit_code"]),
        "selected_test_paths": list(selected_test_paths),
        "pytest_basetemp": str(pytest_basetemp.resolve()),
        "test_counts": dict(sorted(counts.items())),
        "tests": tests,
        "collection_errors": collection_errors,
        "collection_errors_ref": collection_ref.as_dict(),
        "process_stdout": process_stdout.as_dict(),
        "process_stderr": process_stderr.as_dict(),
        "current_gate_all_green": current_gate_all_green,
        "gating_failure_nodeids": [
            row["nodeid"] for row in gating_failures
        ],
        "historical_finding_nodeids": [
            row["nodeid"] for row in historical_findings
        ],
        "credential_environment_removed": sorted(_CREDENTIAL_ENV_NAMES),
    }
    _write_json(store.root / "runs" / run_id / "terminal_result.json", result)
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
    schema = contract["schema_version"]
    if schema not in {SEMANTIC_PARITY_SCHEMA, TYPED_SEMANTIC_PARITY_SCHEMA}:
        raise HermeticTestRunnerError("semantic_parity_contract_schema_invalid")
    expected_status = (
        "raw_preserving_allowlisted_root_normalization"
        if schema == SEMANTIC_PARITY_SCHEMA
        else "raw_preserving_typed_environment_normalization"
    )
    if contract["status"] != expected_status:
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
    if schema == SEMANTIC_PARITY_SCHEMA:
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
        required_rules = {
            "derive_native_and_posix_separator_variants_from_exact_roots": True,
            "replace_longest_exact_literal_first": True,
            "substring_or_fuzzy_path_matching_allowed": False,
            "unknown_absolute_path_behavior": (
                "fail_closed_and_keep_parity_false"
            ),
        }
    else:
        expected_root_ids = [
            "disposable_package_root",
            "disposable_repository_root",
            "disposable_temporary_root",
            "sys_prefix",
            "sys_base_prefix",
            "purelib_root",
            "platlib_root",
            "installed_distribution_roots",
        ]
        allowed_roots = normalization.get("allowed_roots")
        if (
            not isinstance(allowed_roots, list)
            or [row.get("root_id") for row in allowed_roots if isinstance(row, Mapping)]
            != expected_root_ids
            or any(
                not isinstance(row, Mapping)
                or set(row)
                != {
                    "root_id",
                    "role",
                    "projection_token",
                    "source",
                    "cardinality",
                }
                or not all(
                    isinstance(row.get(key), str) and row[key].strip()
                    for key in (
                        "root_id",
                        "role",
                        "projection_token",
                        "source",
                        "cardinality",
                    )
                )
                for row in allowed_roots
            )
            or len({row["projection_token"] for row in allowed_roots})
            != len(allowed_roots)
        ):
            raise HermeticTestRunnerError(
                "semantic_parity_typed_roots_invalid"
            )
        if normalization.get("required_runtime_root_fields") != [
            "root_id",
            "role",
            "absolute_path",
            "projection_token",
            "source",
            "digest_or_environment_fingerprint",
        ]:
            raise HermeticTestRunnerError(
                "semantic_parity_runtime_root_fields_invalid"
            )
        required_rules = {
            "derive_native_and_posix_separator_variants_from_exact_roots": True,
            "replace_longest_exact_literal_first": True,
            "substring_or_fuzzy_path_matching_allowed": False,
            "replace_only_exact_or_descendant_paths": True,
            "Windows_drive_letter_case_insensitive": True,
            "unknown_absolute_path_behavior": (
                "fail_closed_and_keep_parity_false"
            ),
        }
    for key, expected in required_rules.items():
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
    if schema == TYPED_SEMANTIC_PARITY_SCHEMA and projection.get(
        "normalized_content_fields"
    ) != [
        "test.stdout",
        "test.stderr",
        "test.detail",
        "collection_errors",
        "process_stdout",
        "process_stderr",
    ]:
        raise HermeticTestRunnerError(
            "semantic_parity_normalized_field_boundary_invalid"
        )
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
    replacements: list[tuple[str, str]] = []
    if contract["schema_version"] == SEMANTIC_PARITY_SCHEMA:
        expected_root_ids = {str(row["root_id"]) for row in allowed_rows}
        if not isinstance(roots, Mapping) or set(roots) != expected_root_ids:
            raise HermeticTestRunnerError(
                "semantic_parity_runtime_roots_incomplete"
            )
        for row in allowed_rows:
            root_id = str(row["root_id"])
            placeholder = str(row["placeholder"])
            root = str(roots[root_id]).strip()
            if not root:
                raise HermeticTestRunnerError(
                    "semantic_parity_runtime_root_empty"
                )
            variants = {
                root,
                root.replace("\\", "/"),
                root.replace("/", "\\"),
            }
            replacements.extend(
                (variant, placeholder) for variant in variants if variant
            )
        unique_replacements: dict[str, str] = {}
        for literal, placeholder in replacements:
            unique_replacements.setdefault(literal, placeholder)
        for literal, placeholder in sorted(
            unique_replacements.items(),
            key=lambda item: (-len(item[0]), item[0].casefold(), item[0]),
        ):
            normalized = normalized.replace(literal, placeholder)
    else:
        if not isinstance(roots, Sequence) or isinstance(roots, (str, bytes)):
            raise HermeticTestRunnerError(
                "semantic_parity_typed_runtime_roots_invalid"
            )
        contract_by_id = {str(row["root_id"]): row for row in allowed_rows}
        runtime_by_id: dict[str, Mapping[str, Any]] = {}
        required_fields = set(
            contract["normalization"]["required_runtime_root_fields"]
        )
        for raw_row in roots:
            if not isinstance(raw_row, Mapping) or set(raw_row) != required_fields:
                raise HermeticTestRunnerError(
                    "semantic_parity_typed_runtime_root_row_invalid"
                )
            root_id = str(raw_row.get("root_id", ""))
            if root_id in runtime_by_id:
                raise HermeticTestRunnerError(
                    "semantic_parity_typed_runtime_root_duplicate"
                )
            runtime_by_id[root_id] = raw_row
        if set(runtime_by_id) != set(contract_by_id):
            raise HermeticTestRunnerError(
                "semantic_parity_runtime_roots_incomplete"
            )
        for root_id, contract_row in contract_by_id.items():
            runtime_row = runtime_by_id[root_id]
            if any(
                runtime_row.get(key) != contract_row.get(key)
                for key in ("role", "projection_token", "source")
            ):
                raise HermeticTestRunnerError(
                    "semantic_parity_typed_runtime_root_contract_drift"
                )
            path_value = runtime_row["absolute_path"]
            path_values = (
                [path_value]
                if isinstance(path_value, str)
                else list(path_value)
                if isinstance(path_value, list)
                else []
            )
            if (
                not path_values
                or any(not isinstance(item, str) or not item.strip() for item in path_values)
                or path_values != sorted(set(path_values))
                and isinstance(path_value, list)
                or runtime_row["digest_or_environment_fingerprint"]
                != _environment_root_fingerprint(root_id, path_values)
            ):
                raise HermeticTestRunnerError(
                    f"semantic_parity_typed_runtime_root_invalid:{root_id}"
                )
            replacements.extend(
                (item, str(contract_row["projection_token"]))
                for item in path_values
            )
        unique_replacements = {}
        for literal, placeholder in replacements:
            unique_replacements.setdefault(literal, placeholder)
        for literal, placeholder in sorted(
            unique_replacements.items(),
            key=lambda item: (-len(item[0]), item[0].casefold(), item[0]),
        ):
            normalized_literal = literal.replace("\\", "/").rstrip("/")
            posix_absolute = normalized_literal.startswith("/")
            components = normalized_literal.lstrip("/").split("/")
            if not normalized_literal or any(not item for item in components):
                raise HermeticTestRunnerError(
                    "semantic_parity_typed_runtime_root_empty"
                )
            escaped: list[str] = []
            for index, component in enumerate(components):
                if index == 0 and re.fullmatch(r"[A-Za-z]:", component):
                    drive = component[0]
                    escaped.append(f"[{drive.lower()}{drive.upper()}]:")
                else:
                    escaped.append(re.escape(component))
            path_pattern = (
                (r"[\\/]{1,2}" if posix_absolute else "")
                + r"[\\/]{1,2}".join(escaped)
            )
            boundary_pattern = (
                r"(?<![A-Za-z0-9_.-])"
                + path_pattern
                + r"(?P<descendant>(?:[\\/]{1,2}[^\s\"'<>),:\]]*)?)"
                + r"(?=$|[\s\"'<>),:\]])"
            )
            normalized = re.sub(
                boundary_pattern,
                lambda match: placeholder
                + re.sub(
                    r"[\\/]+",
                    "/",
                    str(match.group("descendant") or ""),
                ),
                normalized,
            )
    unknown_scan = re.sub(
        r"[A-Za-z][A-Za-z0-9+.-]*://[^\s\"'<>]+",
        lambda match: "_" * len(match.group(0)),
        normalized,
    )
    unknown_paths: set[str] = set()
    for pattern in contract["normalization"]["unknown_absolute_path_patterns"]:
        unknown_paths.update(
            match.group(0)
            for match in re.finditer(str(pattern), unknown_scan)
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
    roots = (
        result["semantic_normalization_roots"]
        if contract["schema_version"] == SEMANTIC_PARITY_SCHEMA
        else result["typed_environment_roots"]
    )
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
    manifest_path = manifest_path.resolve()
    output_root = output_root.resolve()
    manifest = _load_json(manifest_path)
    try:
        validate_active_test_suite_manifest(manifest)
    except ContractGovernanceError as exc:
        raise HermeticTestRunnerError(f"hermetic_manifest_invalid:{exc.code}") from exc
    execution_plan = _load_test_execution_plan(repository_root, manifest)
    if execution_plan is not None:
        legacy_paths = {
            str(path).replace("\\", "/")
            for suite in manifest["suites"]
            if suite["selected"]
            for path in suite["test_paths"]
        }
        if legacy_paths != set(execution_plan.test_paths()):
            raise HermeticTestRunnerError(
                "test_execution_contract_legacy_manifest_path_drift"
            )
    authority_metadata: dict[str, Any] | None = None
    if repository_paths is None:
        authority_metadata = (
            _validate_clean_environment_qualification_authority(
                repository_root=repository_root,
                manifest_path=manifest_path,
                manifest=manifest,
                output_root=output_root,
            )
        )
    if output_root.exists():
        raise HermeticTestRunnerError("hermetic_output_root_already_exists")
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
            host_preflight = (
                run_host_phase(
                    run_id="host_preflight",
                    phase="host_preflight",
                    repository_root=repository_root,
                    manifest=manifest,
                    execution_plan=execution_plan,
                    store=store,
                    temporary_root=disposable_parent,
                    python_environment=package_manifest[
                        "python_environment"
                    ],
                )
                if execution_plan is not None
                else None
            )
            if host_preflight is not None and not host_preflight[
                "current_gate_all_green"
            ]:
                raise HermeticTestRunnerError(
                    "hermetic_host_preflight_failed"
                )
            run_a = run_disposable_once(
                run_id="disposable_a",
                package_root=staging,
                package_manifest=package_manifest,
                manifest=manifest,
                store=store,
                disposable_parent=disposable_parent,
                execution_plan=execution_plan,
            )
            run_b = run_disposable_once(
                run_id="disposable_b",
                package_root=staging,
                package_manifest=package_manifest,
                manifest=manifest,
                store=store,
                disposable_parent=disposable_parent,
                execution_plan=execution_plan,
            )
            historical_audit = (
                run_host_phase(
                    run_id="historical_audit",
                    phase="historical_audit",
                    repository_root=repository_root,
                    manifest=manifest,
                    execution_plan=execution_plan,
                    store=store,
                    temporary_root=disposable_parent,
                    python_environment=package_manifest[
                        "python_environment"
                    ],
                )
                if execution_plan is not None
                else None
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
        post_run_attestation = {
            "schema_version": "fin_ia_post_run_attestation_v1_0",
            "execution_phase": "post_run_attestation",
            "status": (
                "pass"
                if parity and repository_unchanged
                else "failed"
            ),
            "gates_current_candidate": True,
            "repository_unchanged_during_run": repository_unchanged,
            "two_disposable_semantic_parity": parity,
            "raw_capture_and_content_readback_materialized": True,
        }
        if execution_plan is not None:
            _write_json(
                staging
                / "runs"
                / "contract_compile"
                / "terminal_result.json",
                {
                    "schema_version": (
                        "fin_ia_contract_compile_terminal_result_v1_0"
                    ),
                    "execution_phase": "contract_compile",
                    "status": "pass",
                    "gates_current_candidate": True,
                    "execution_plan": execution_plan.as_dict(),
                },
            )
            _write_json(
                staging
                / "runs"
                / "post_run_attestation"
                / "terminal_result.json",
                post_run_attestation,
            )
        passed = (
            parity
            and repository_unchanged
            and bool(run_a["current_gate_all_green"])
            and bool(run_b["current_gate_all_green"])
            and (
                host_preflight is None
                or bool(host_preflight["current_gate_all_green"])
            )
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
        if execution_plan is not None:
            verification["compiled_test_execution_contract"] = (
                execution_plan.as_dict()
            )
            verification["phase_results"] = {
                "contract_compile": {
                    "status": "pass",
                    "gates_current_candidate": True,
                    "execution_plan_digest": (
                        execution_plan.execution_plan_digest
                    ),
                },
                "host_preflight": host_preflight,
                "disposable_current_gate": {
                    "status": (
                        "pass"
                        if run_a["current_gate_all_green"]
                        and run_b["current_gate_all_green"]
                        else "failed"
                    ),
                    "gates_current_candidate": True,
                    "runs": [run_a, run_b],
                },
                "historical_audit": historical_audit,
                "post_run_attestation": post_run_attestation,
            }
            verification["historical_finding_nodeids"] = (
                []
                if historical_audit is None
                else historical_audit["historical_finding_nodeids"]
            )
        if authority_metadata is not None:
            verification["clean_environment_qualification_authority"] = (
                authority_metadata
            )
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
