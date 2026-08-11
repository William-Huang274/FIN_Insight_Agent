from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Callable, Mapping, Sequence


REPOSITORY_REFERENCE_PROOF_POLICY_SOURCE_SCHEMA = (
    "fin_ia_repository_reference_proof_policy_source_v3_0"
)
REPOSITORY_REFERENCE_PROOF_POLICY_BINDING_SCHEMA = (
    "fin_ia_repository_reference_proof_policy_binding_v3_0"
)
ELIGIBILITY_PAYLOAD_SCHEMA = (
    "fin_ia_0_1_3_s0_v3_pre_consumption_eligibility_payload_v1_0"
)
ELIGIBILITY_ATTESTATION_SCHEMA = (
    "fin_ia_0_1_3_s0_v3_pre_consumption_eligibility_attestation_v1_0"
)
HOST_AUTHORITY_SCHEMA = (
    "fin_ia_0_1_3_s0_v3_host_zero_call_authority_v1_0"
)

PROOF_POLICY_CONSUMERS = (
    "active_suite_manifest_binding",
    "eligibility_compiler",
    "host_execution_recompute",
    "manifest_validator",
    "shared_repository_compiler",
)

_BINDING_FIELDS = frozenset(
    {"schema_version", "policy_ref", "policy_sha256"}
)
_SOURCE_FIELDS = frozenset(
    {
        "schema_version",
        "policy_id",
        "policy_version",
        "status",
        "consumers",
        "tracked_repository_paths_allowed",
        "explicit_allowlist",
        "reference_role_registry_ref",
        "reference_role_registry_sha256",
        "forbidden_prefixes",
        "untracked_or_ignored_reference_behavior",
        "unknown_reference_behavior",
        "unknown_reference_reporting",
        "traversal_or_symlink_escape_behavior",
        "semantic_or_external_reference_behavior",
        "policy_canonical_digest",
    }
)
_BOUNDARY_VALUES = {
    "tracked_repository_paths_allowed": True,
    "untracked_or_ignored_reference_behavior": "fail_closed",
    "unknown_reference_behavior": "fail_closed",
    "unknown_reference_reporting": "collect_all_typed_envelope",
    "traversal_or_symlink_escape_behavior": "fail_closed",
    "semantic_or_external_reference_behavior": "observe_not_package",
}


class ProofControlPlaneError(RuntimeError):
    """Stable failure at the proof policy or consumption boundary."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProofControlPlaneError(f"proof_policy_duplicate_json_key:{key}")
        result[key] = value
    return result


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_strict_object,
        )
    except ProofControlPlaneError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProofControlPlaneError(
            f"proof_policy_json_read_failed:{path.as_posix()}"
        ) from exc
    if not isinstance(value, dict):
        raise ProofControlPlaneError("proof_policy_json_object_required")
    return value


def _safe_repository_file(repository_root: Path, value: str) -> Path:
    relative = Path(value)
    if not value.strip() or relative.is_absolute() or ".." in relative.parts:
        raise ProofControlPlaneError("proof_policy_path_outside_repository")
    repository_root = repository_root.resolve()
    resolved = (repository_root / relative).resolve()
    try:
        resolved.relative_to(repository_root)
    except ValueError as exc:
        raise ProofControlPlaneError(
            "proof_policy_path_outside_repository"
        ) from exc
    if not resolved.is_file():
        raise ProofControlPlaneError("proof_policy_file_missing")
    return Path(*relative.parts)


@dataclass(frozen=True)
class RepositoryReferenceProofPolicy:
    source_ref: str
    source_sha256: str
    canonical_digest: str
    reference_role_registry_ref: str
    reference_role_registry_sha256: str
    compiler_policy: Mapping[str, Any]

    def package_paths(self) -> tuple[Path, ...]:
        return (
            Path(self.source_ref),
            Path(self.reference_role_registry_ref),
        )


@dataclass(frozen=True)
class V3CompiledRepositoryInventory:
    """Immutable v2 compiler result plus its v3 policy-source binding."""

    base_inventory: Any
    policy: RepositoryReferenceProofPolicy

    def __getattr__(self, name: str) -> Any:
        return getattr(self.base_inventory, name)

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.base_inventory.as_dict(),
            "repository_reference_policy": {
                "ref": self.policy.source_ref,
                "sha256": self.policy.source_sha256,
                "canonical_digest": self.policy.canonical_digest,
            },
        }


def load_repository_reference_proof_policy(
    repository_root: Path,
    binding: Mapping[str, Any],
) -> RepositoryReferenceProofPolicy:
    if set(binding) != _BINDING_FIELDS:
        raise ProofControlPlaneError("proof_policy_binding_surface_invalid")
    if (
        binding.get("schema_version")
        != REPOSITORY_REFERENCE_PROOF_POLICY_BINDING_SCHEMA
    ):
        raise ProofControlPlaneError("proof_policy_binding_schema_invalid")

    source_ref = str(binding.get("policy_ref", "")).strip().replace("\\", "/")
    source_digest = str(binding.get("policy_sha256", "")).strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", source_digest):
        raise ProofControlPlaneError("proof_policy_binding_digest_invalid")
    source_path = _safe_repository_file(repository_root, source_ref)
    if sha256_file(repository_root / source_path) != source_digest:
        raise ProofControlPlaneError("proof_policy_binding_digest_drift")

    source = _load_json(repository_root / source_path)
    if set(source) != _SOURCE_FIELDS:
        raise ProofControlPlaneError("proof_policy_source_surface_invalid")
    if (
        source.get("schema_version")
        != REPOSITORY_REFERENCE_PROOF_POLICY_SOURCE_SCHEMA
    ):
        raise ProofControlPlaneError("proof_policy_source_schema_invalid")
    if source.get("policy_id") != "fin_0_1_3.S0.repository_reference_proof_policy":
        raise ProofControlPlaneError("proof_policy_source_id_invalid")
    if source.get("policy_version") != "v3":
        raise ProofControlPlaneError("proof_policy_source_version_invalid")
    if source.get("status") != "single_source_typed_fail_closed":
        raise ProofControlPlaneError("proof_policy_source_status_invalid")
    if source.get("consumers") != list(PROOF_POLICY_CONSUMERS):
        raise ProofControlPlaneError("proof_policy_consumer_order_invalid")
    if any(source.get(key) != value for key, value in _BOUNDARY_VALUES.items()):
        raise ProofControlPlaneError("proof_policy_boundary_invalid")

    forbidden = source.get("forbidden_prefixes")
    if (
        not isinstance(forbidden, list)
        or forbidden != sorted(set(forbidden))
        or not {".codex_runtime", ".git"}.issubset(forbidden)
    ):
        raise ProofControlPlaneError("proof_policy_forbidden_prefixes_invalid")
    allowlist = source.get("explicit_allowlist")
    if not isinstance(allowlist, list):
        raise ProofControlPlaneError("proof_policy_allowlist_invalid")

    registry_ref = str(
        source.get("reference_role_registry_ref", "")
    ).strip().replace("\\", "/")
    registry_digest = str(
        source.get("reference_role_registry_sha256", "")
    ).strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", registry_digest):
        raise ProofControlPlaneError("proof_policy_registry_digest_invalid")
    registry_path = _safe_repository_file(repository_root, registry_ref)
    if sha256_file(repository_root / registry_path) != registry_digest:
        raise ProofControlPlaneError("proof_policy_registry_digest_drift")

    canonical_source = {
        key: value
        for key, value in source.items()
        if key != "policy_canonical_digest"
    }
    canonical_digest = sha256_bytes(canonical_bytes(canonical_source))
    if source.get("policy_canonical_digest") != canonical_digest:
        raise ProofControlPlaneError("proof_policy_canonical_digest_drift")

    compiler_fields = {
        "schema_version",
        "tracked_repository_paths_allowed",
        "explicit_allowlist",
        "reference_role_registry_ref",
        "forbidden_prefixes",
        "untracked_or_ignored_reference_behavior",
        "unknown_reference_behavior",
        "unknown_reference_reporting",
        "traversal_or_symlink_escape_behavior",
        "semantic_or_external_reference_behavior",
    }
    return RepositoryReferenceProofPolicy(
        source_ref=source_path.as_posix(),
        source_sha256=source_digest,
        canonical_digest=canonical_digest,
        reference_role_registry_ref=registry_path.as_posix(),
        reference_role_registry_sha256=registry_digest,
        compiler_policy={key: source[key] for key in compiler_fields},
    )


def compile_v3_repository_inventory(
    repository_root: Path,
    manifest: Mapping[str, Any],
    *,
    legacy_compile: Callable[[Path, Mapping[str, Any]], Any],
) -> V3CompiledRepositoryInventory:
    """Compile v3 through the immutable v2 compiler without editing v2 code.

    The versioned v3 source is validated first and deterministically projected
    into the v2 compiler surface. The policy source itself is added to the
    tracked closure; the referenced role registry remains admitted by the
    immutable v2 compiler's policy-contract path handling.
    """

    package = manifest.get("hermetic_package_policy")
    if not isinstance(package, Mapping):
        raise ProofControlPlaneError("proof_policy_manifest_package_missing")
    binding = package.get("repository_reference_policy")
    if not isinstance(binding, Mapping):
        raise ProofControlPlaneError("proof_policy_manifest_binding_missing")
    policy = load_repository_reference_proof_policy(repository_root, binding)

    adapted = deepcopy(dict(manifest))
    adapted_package = deepcopy(dict(package))
    compiler_policy = dict(policy.compiler_policy)
    compiler_policy["schema_version"] = (
        "fin_ia_hermetic_repository_reference_policy_v2_0"
    )
    compiler_policy.pop("unknown_reference_reporting", None)
    adapted_package["repository_reference_policy"] = compiler_policy
    seed_paths = [str(value) for value in adapted_package.get("repository_seed_paths", [])]
    if policy.source_ref not in seed_paths:
        seed_paths.append(policy.source_ref)
    adapted_package["repository_seed_paths"] = seed_paths
    adapted["hermetic_package_policy"] = adapted_package

    compiled = legacy_compile(repository_root, adapted)
    compiled_paths = {path.as_posix() for path in compiled.paths}
    required_paths = {policy.source_ref, policy.reference_role_registry_ref}
    if not required_paths.issubset(compiled_paths):
        raise ProofControlPlaneError("proof_policy_compiled_closure_incomplete")
    return V3CompiledRepositoryInventory(compiled, policy)


def _require_sha(value: Any, code: str) -> str:
    normalized = str(value).strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", normalized):
        raise ProofControlPlaneError(code)
    return normalized


def build_eligibility_payload(
    *,
    execution_manifest_ref: str,
    execution_manifest_sha256: str,
    active_suite_manifest_ref: str,
    active_suite_manifest_sha256: str,
    source_bindings: Sequence[Mapping[str, Any]],
    policy: RepositoryReferenceProofPolicy,
    git_state: Mapping[str, Any],
    project_os_preflight: Mapping[str, Any],
    tracked_snapshot: Mapping[str, Any],
    compiled_inventory: Mapping[str, Any],
    selected_test_paths: Sequence[str],
) -> dict[str, Any]:
    if (
        git_state.get("clean") is not True
        or git_state.get("synced") is not True
        or git_state.get("head") != git_state.get("upstream_head")
        or int(git_state.get("status_bytes", -1)) != 0
    ):
        raise ProofControlPlaneError("eligibility_git_state_invalid")
    head = _require_sha(git_state.get("head"), "eligibility_git_head_invalid")
    if (
        project_os_preflight.get("status") != "pass"
        or int(project_os_preflight.get("open_full_chain_blocker_count", -1))
        != 0
    ):
        raise ProofControlPlaneError("eligibility_project_os_preflight_invalid")

    normalized_bindings: list[dict[str, str]] = []
    for row in source_bindings:
        if not isinstance(row, Mapping) or set(row) != {"role", "ref", "sha256"}:
            raise ProofControlPlaneError("eligibility_source_binding_invalid")
        normalized_bindings.append(
            {
                "role": str(row["role"]),
                "ref": str(row["ref"]).replace("\\", "/"),
                "sha256": _require_sha(
                    row["sha256"], "eligibility_source_binding_digest_invalid"
                ),
            }
        )
    if (
        normalized_bindings
        != sorted(normalized_bindings, key=lambda row: (row["role"], row["ref"]))
        or len({row["role"] for row in normalized_bindings})
        != len(normalized_bindings)
    ):
        raise ProofControlPlaneError("eligibility_source_binding_order_invalid")

    test_paths = [str(value).replace("\\", "/") for value in selected_test_paths]
    if test_paths != sorted(set(test_paths)) or not test_paths:
        raise ProofControlPlaneError("eligibility_selected_test_paths_invalid")

    reference_report = compiled_inventory.get("reference_role_report")
    if (
        not isinstance(reference_report, Mapping)
        or int(reference_report.get("unknown_count", -1)) != 0
    ):
        raise ProofControlPlaneError("eligibility_reference_role_report_invalid")

    payload = {
        "schema_version": ELIGIBILITY_PAYLOAD_SCHEMA,
        "consumption_boundary": (
            "before_host_execution_started_marker_and_import_sweep"
        ),
        "git": {
            "head": head,
            "branch": str(git_state.get("branch", "")),
            "upstream_head": head,
            "status_sha256": _require_sha(
                git_state.get("status_sha256"),
                "eligibility_git_status_digest_invalid",
            ),
            "status_bytes": 0,
        },
        "execution_manifest": {
            "ref": execution_manifest_ref.replace("\\", "/"),
            "sha256": _require_sha(
                execution_manifest_sha256,
                "eligibility_execution_manifest_digest_invalid",
            ),
        },
        "active_suite_manifest": {
            "ref": active_suite_manifest_ref.replace("\\", "/"),
            "sha256": _require_sha(
                active_suite_manifest_sha256,
                "eligibility_active_manifest_digest_invalid",
            ),
        },
        "source_bindings": normalized_bindings,
        "source_bindings_digest": sha256_bytes(
            canonical_bytes(normalized_bindings)
        ),
        "proof_policy": {
            "ref": policy.source_ref,
            "sha256": policy.source_sha256,
            "canonical_digest": policy.canonical_digest,
            "unknown_reference_behavior": "fail_closed",
            "unknown_reference_reporting": "collect_all_typed_envelope",
        },
        "project_os_preflight": {
            "status": "pass",
            "open_full_chain_blocker_count": 0,
        },
        "tracked_snapshot": {
            "file_count": int(tracked_snapshot.get("file_count", -1)),
            "canonical_sha256": _require_sha(
                tracked_snapshot.get("canonical_sha256"),
                "eligibility_tracked_snapshot_digest_invalid",
            ),
        },
        "compiled_inventory": {
            "path_count": int(compiled_inventory.get("path_count", -1)),
            "tracked_path_count": int(
                compiled_inventory.get("tracked_path_count", -1)
            ),
            "explicit_allowlist_path_count": int(
                compiled_inventory.get("explicit_allowlist_path_count", -1)
            ),
            "closure_digest": _require_sha(
                compiled_inventory.get("closure_digest"),
                "eligibility_inventory_digest_invalid",
            ),
            "reference_observation_digest": _require_sha(
                reference_report.get("observation_digest"),
                "eligibility_reference_observation_digest_invalid",
            ),
            "unknown_reference_count": 0,
        },
        "selected_test_paths_digest": sha256_bytes(canonical_bytes(test_paths)),
        "host_budget_consumed": False,
    }
    if (
        payload["tracked_snapshot"]["file_count"] <= 0
        or payload["compiled_inventory"]["path_count"] <= 0
        or payload["compiled_inventory"]["tracked_path_count"] <= 0
        or payload["compiled_inventory"]["explicit_allowlist_path_count"] != 0
    ):
        raise ProofControlPlaneError("eligibility_inventory_counts_invalid")
    return payload


def build_eligibility_attestation(
    payload: Mapping[str, Any],
    *,
    evidence_refs: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    if payload.get("schema_version") != ELIGIBILITY_PAYLOAD_SCHEMA:
        raise ProofControlPlaneError("eligibility_payload_schema_invalid")
    return {
        "schema_version": ELIGIBILITY_ATTESTATION_SCHEMA,
        "status": "pass_non_consuming",
        "attestation_digest": sha256_bytes(canonical_bytes(payload)),
        "payload": dict(payload),
        "evidence_refs": dict(evidence_refs),
        "eligibility_attestations_consumed": 1,
        "host_proof_runs_consumed": 0,
        "business_promotable": False,
    }


def validate_eligibility_attestation(
    attestation: Mapping[str, Any],
    *,
    recomputed_payload: Mapping[str, Any],
) -> str:
    required = {
        "schema_version",
        "status",
        "attestation_digest",
        "payload",
        "evidence_refs",
        "eligibility_attestations_consumed",
        "host_proof_runs_consumed",
        "business_promotable",
    }
    if set(attestation) != required:
        raise ProofControlPlaneError("eligibility_attestation_surface_invalid")
    if attestation.get("schema_version") != ELIGIBILITY_ATTESTATION_SCHEMA:
        raise ProofControlPlaneError("eligibility_attestation_schema_invalid")
    if (
        attestation.get("status") != "pass_non_consuming"
        or attestation.get("eligibility_attestations_consumed") != 1
        or attestation.get("host_proof_runs_consumed") != 0
        or attestation.get("business_promotable") is not False
    ):
        raise ProofControlPlaneError("eligibility_attestation_boundary_invalid")
    expected_digest = sha256_bytes(canonical_bytes(recomputed_payload))
    if (
        attestation.get("payload") != dict(recomputed_payload)
        or attestation.get("attestation_digest") != expected_digest
    ):
        raise ProofControlPlaneError("eligibility_attestation_recompute_drift")
    return expected_digest


def validate_host_authority(
    authority: Mapping[str, Any],
    *,
    host_scope: str,
    eligibility_file_sha256: str,
    eligibility_attestation_digest: str,
) -> None:
    required = {
        "schema_version",
        "status",
        "host_scope",
        "eligibility_file_sha256",
        "eligibility_attestation_digest",
        "maximum_host_proof_runs",
        "formal_proof_authorized",
        "model_provider_network_business_authorized",
        "automatic_retry_replacement_or_v4_authorized",
    }
    if set(authority) != required:
        raise ProofControlPlaneError("host_authority_surface_invalid")
    if authority.get("schema_version") != HOST_AUTHORITY_SCHEMA:
        raise ProofControlPlaneError("host_authority_schema_invalid")
    if (
        authority.get("status") != "authorized_for_one_matching_v3_host_run"
        or authority.get("host_scope") != host_scope
        or authority.get("eligibility_file_sha256")
        != eligibility_file_sha256
        or authority.get("eligibility_attestation_digest")
        != eligibility_attestation_digest
        or authority.get("maximum_host_proof_runs") != 1
        or authority.get("formal_proof_authorized") is not False
        or authority.get("model_provider_network_business_authorized")
        is not False
        or authority.get("automatic_retry_replacement_or_v4_authorized")
        is not False
    ):
        raise ProofControlPlaneError("host_authority_boundary_invalid")
