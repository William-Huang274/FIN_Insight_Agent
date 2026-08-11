from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time
import traceback
from types import ModuleType
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import sec_agent.hermetic_test_runner as HERMETIC  # noqa: E402
from sec_agent.hermetic_test_runner import (  # noqa: E402
    compile_repository_inventory as legacy_compile_repository_inventory,
    validate_host_current_program_projection as legacy_validate_projection,
)
from sec_agent.proof_control_plane import (  # noqa: E402
    ELIGIBILITY_ATTESTATION_SCHEMA,
    ProofControlPlaneError,
    REPOSITORY_REFERENCE_PROOF_POLICY_BINDING_SCHEMA,
    build_eligibility_attestation,
    build_eligibility_payload,
    compile_v3_repository_inventory,
    load_repository_reference_proof_policy,
    sha256_file,
    validate_eligibility_attestation,
    validate_host_authority,
)
from sec_agent.runtime_contract_governance import (  # noqa: E402
    validate_active_test_suite_manifest,
)


BASE_RUNNER_PATH = ROOT / (
    "scripts/engineering/run_fin_0_1_3_s0_t03_host_zero_call_proof.py"
)
EXECUTION_SCHEMA = (
    "fin_ia_0_1_3_s0_v3_eligibility_and_host_execution_manifest_v1_0"
)
VERIFICATION_SCHEMA = (
    "fin_ia_0_1_3_s0_v3_host_zero_call_engineering_proof_verification_v1_0"
)
ELIGIBILITY_SCOPE = (
    "FIN-0.1.3-S0-EXIT-CONTRACT-V3-CLEAN-HEAD-NON-CONSUMING-"
    "EXACT-BOUNDARY-ELIGIBILITY-ATTESTATION"
)
HOST_SCOPE = (
    "FIN-0.1.3-S0-EXIT-CONTRACT-V3-CURRENT-RUNTIME-HOST-ZERO-CALL-"
    "ENGINEERING-PROOF"
)
EXPECTED_ROLES = {
    "repository_resource",
    "package_relative_audit",
    "external_content",
    "restricted_runtime_audit",
    "model_run_report",
    "semantic_followup",
}


def _load_base_runner() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "fin_ia_0_1_3_s0_v3_host_proof_base",
        BASE_RUNNER_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("v3_base_host_proof_runner_load_failed")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BASE = _load_base_runner()
LEGACY_LOAD_JSON = HERMETIC._load_json


def _validate_current_projection_v3(
    repository_root: Path,
    projection_ref: str,
) -> Path:
    projection_path = (repository_root / projection_ref).resolve()
    projection = LEGACY_LOAD_JSON(projection_path)
    if projection.get("status") != (
        "current_FIN_0_1_3_S0_exit_contract_v3_proof_control_plane_"
        "implementation_pass_eligibility_authority_pending"
    ):
        raise HERMETIC.HermeticTestRunnerError(
            "current_v3_projection_status_invalid"
        )

    def compatibility_load(path: Path) -> dict[str, Any]:
        value = LEGACY_LOAD_JSON(path)
        if path.resolve() == projection_path:
            value = dict(value)
            value["status"] = (
                "current_FIN_0_1_3_S0_exit_contract_v2_reference_role_"
                "implementation_pass_host_proof_authority_pending"
            )
        return value

    previous_load = HERMETIC._load_json
    HERMETIC._load_json = compatibility_load
    try:
        return legacy_validate_projection(repository_root, projection_ref)
    finally:
        HERMETIC._load_json = previous_load


def _compile_repository_inventory_v3(
    repository_root: Path,
    manifest: Mapping[str, Any],
) -> Any:
    previous_validator = HERMETIC.validate_host_current_program_projection
    HERMETIC.validate_host_current_program_projection = (
        _validate_current_projection_v3
    )
    try:
        return compile_v3_repository_inventory(
            repository_root,
            manifest,
            legacy_compile=legacy_compile_repository_inventory,
        )
    finally:
        HERMETIC.validate_host_current_program_projection = previous_validator


def _validate_execution_manifest(
    manifest: Mapping[str, Any], manifest_path: Path
) -> tuple[dict[str, Any], Path]:
    required = {
        "schema_version",
        "execution_id",
        "status",
        "eligibility_scope",
        "host_scope",
        "authority",
        "source_bindings",
        "active_suite_manifest_ref",
        "capture_plugin_ref",
        "required_matrix",
        "required_passed_nodeid_fragments",
        "budgets",
        "promotion_boundary",
        "success_and_stop_rules",
    }
    if set(manifest) != required:
        raise BASE.HostProofError("v3_execution_manifest_top_level_invalid")
    if manifest.get("schema_version") != EXECUTION_SCHEMA:
        raise BASE.HostProofError("v3_execution_manifest_schema_invalid")
    if manifest.get("status") != "frozen_ready_for_one_v3_eligibility":
        raise BASE.HostProofError("v3_execution_manifest_status_invalid")
    if (
        manifest.get("eligibility_scope") != ELIGIBILITY_SCOPE
        or manifest.get("host_scope") != HOST_SCOPE
    ):
        raise BASE.HostProofError("v3_execution_manifest_scope_invalid")

    authority = manifest.get("authority")
    expected_authority = {
        "eligibility_attestation_authorized": True,
        "maximum_eligibility_attestations": 1,
        "host_execution_requires_separate_external_authority": True,
        "formal_two_disposable_proof_authorized": False,
        "old_T03_or_v2_rerun_replacement_or_reinterpretation_authorized": False,
        "model_provider_credential_network_source_external_tool_authorized": False,
        "admission_business_run_or_business_artifact_authorized": False,
        "S1_S2_release_FIN_0_1_4_or_exit_contract_v4_authorized": False,
    }
    if not isinstance(authority, Mapping) or authority != expected_authority:
        raise BASE.HostProofError("v3_execution_manifest_authority_invalid")

    budgets = manifest.get("budgets")
    expected_budgets = {
        "v3_implementation_eligibility_host_formal_maximum": [1, 1, 1, 1],
        "v3_observed_before_eligibility": [1, 0, 0, 0],
        "eligibility_attestations_consumed_before_execution": 0,
        "host_proof_runs_consumed_before_execution": 0,
        "formal_two_disposable_packages_created_or_executed": 0,
        "automatic_retries_replacements_repeat_attestations_or_v4": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "credential_reads_or_probes": 0,
        "network_source_or_external_tool_calls": 0,
        "new_admissions": 0,
        "business_runs": 0,
        "business_artifacts": 0,
    }
    if not isinstance(budgets, Mapping) or budgets != expected_budgets:
        raise BASE.HostProofError("v3_execution_manifest_budget_invalid")

    bindings = manifest.get("source_bindings")
    if not isinstance(bindings, list) or not bindings:
        raise BASE.HostProofError("v3_execution_manifest_bindings_missing")
    normalized: list[tuple[str, str]] = []
    for binding in bindings:
        if not isinstance(binding, Mapping) or set(binding) != {
            "role",
            "ref",
            "sha256",
        }:
            raise BASE.HostProofError("v3_execution_manifest_source_binding_invalid")
        role = str(binding["role"])
        ref = str(binding["ref"]).replace("\\", "/")
        normalized.append((role, ref))
        path = ROOT / ref
        if not path.is_file() or BASE._sha256_file(path) != str(binding["sha256"]):
            raise BASE.HostProofError(
                f"v3_execution_manifest_source_binding_drift:{role}"
            )
    if normalized != sorted(normalized) or len(set(normalized)) != len(normalized):
        raise BASE.HostProofError("v3_execution_manifest_source_binding_order_invalid")

    active_path = ROOT / str(manifest["active_suite_manifest_ref"])
    active = BASE._load_json(active_path)
    validate_active_test_suite_manifest(active)
    if active.get("status") != (
        "S0_exit_contract_v3_proof_control_plane_implementation_pass_"
        "eligibility_authority_pending"
    ):
        raise BASE.HostProofError("v3_active_suite_manifest_status_invalid")
    raw_policy = active.get("hermetic_package_policy", {}).get(
        "repository_reference_policy"
    )
    if (
        not isinstance(raw_policy, Mapping)
        or raw_policy.get("schema_version")
        != REPOSITORY_REFERENCE_PROOF_POLICY_BINDING_SCHEMA
    ):
        raise BASE.HostProofError("v3_active_suite_policy_binding_invalid")
    try:
        load_repository_reference_proof_policy(ROOT, raw_policy)
    except ProofControlPlaneError as exc:
        raise BASE.HostProofError(exc.code) from exc

    plugin_path = ROOT / str(manifest["capture_plugin_ref"])
    if not plugin_path.is_file():
        raise BASE.HostProofError("v3_execution_manifest_capture_plugin_missing")
    if not manifest_path.resolve().is_relative_to(ROOT):
        raise BASE.HostProofError("v3_execution_manifest_must_be_repository_owned")
    return active, plugin_path


def _validate_inventory(compiled: Any) -> dict[str, Any]:
    paths = [path.as_posix() for path in compiled.paths]
    forbidden = [
        value
        for value in paths
        if value == ".git"
        or value.startswith(".git/")
        or value == ".codex_runtime"
        or value.startswith(".codex_runtime/")
    ]
    report = compiled.reference_role_report
    if forbidden:
        raise BASE.HostProofError("v3_compiled_inventory_contains_forbidden_path")
    if compiled.explicit_allowlist_paths:
        raise BASE.HostProofError("v3_compiled_inventory_contains_allowlist_path")
    if report is None:
        raise BASE.HostProofError("v3_reference_role_report_missing")
    report_value = report.as_dict()
    if (
        report_value.get("unknown_count") != 0
        or set(report_value.get("role_counts", {})) != {*EXPECTED_ROLES, "unknown"}
    ):
        raise BASE.HostProofError("v3_reference_role_report_not_all_known")
    policy = compiled.as_dict().get("repository_reference_policy")
    if not isinstance(policy, Mapping):
        raise BASE.HostProofError("v3_compiled_inventory_policy_binding_missing")
    return {
        **compiled.as_dict(),
        "forbidden_path_count": 0,
        "ignored_or_untracked_path_count": 0,
        "paths": paths,
    }


def _inventory_evidence(compiled: Any, store: Any) -> dict[str, Any]:
    validated = _validate_inventory(compiled)
    paths = validated.pop("paths")
    payload = {
        "schema_version": "fin_ia_s0_v3_host_compiled_repository_inventory_v1_0",
        "paths": paths,
        "tracked_paths": list(compiled.tracked_paths),
        "explicit_allowlist_paths": list(compiled.explicit_allowlist_paths),
        "recursive_reference_paths": list(compiled.recursive_reference_paths),
        "reference_role_report": compiled.reference_role_report.as_dict(),
        "repository_reference_policy": compiled.as_dict()[
            "repository_reference_policy"
        ],
    }
    return {**validated, "paths_ref": store.put_json(payload)}


def _boundary_payload(
    *,
    execution_manifest_path: Path,
    execution: Mapping[str, Any],
    scope: str,
    store: Any,
) -> tuple[dict[str, Any], dict[str, Mapping[str, Any]]]:
    BASE.EXPECTED_SCOPE = scope
    active, _ = _validate_execution_manifest(execution, execution_manifest_path)
    git_state = BASE._git_state()
    if not git_state["clean"]:
        raise BASE.HostProofError("v3_eligibility_requires_clean_repository")
    if not git_state["synced"]:
        raise BASE.HostProofError("v3_eligibility_requires_synced_upstream")
    preflight = BASE._project_os_preflight(store)
    tracked = BASE._tracked_snapshot(store)
    compiled = _compile_repository_inventory_v3(ROOT, active)
    inventory = _inventory_evidence(compiled, store)
    raw_policy = active["hermetic_package_policy"]["repository_reference_policy"]
    try:
        policy = load_repository_reference_proof_policy(ROOT, raw_policy)
    except ProofControlPlaneError as exc:
        raise BASE.HostProofError(exc.code) from exc
    try:
        payload = build_eligibility_payload(
            execution_manifest_ref=execution_manifest_path.relative_to(ROOT).as_posix(),
            execution_manifest_sha256=BASE._sha256_file(execution_manifest_path),
            active_suite_manifest_ref=str(execution["active_suite_manifest_ref"]),
            active_suite_manifest_sha256=BASE._sha256_file(
                ROOT / str(execution["active_suite_manifest_ref"])
            ),
            source_bindings=execution["source_bindings"],
            policy=policy,
            git_state=git_state,
            project_os_preflight=preflight,
            tracked_snapshot=tracked,
            compiled_inventory=inventory,
            selected_test_paths=BASE._selected_test_paths(active),
        )
    except ProofControlPlaneError as exc:
        raise BASE.HostProofError(exc.code) from exc
    refs = {
        "project_os_stdout": preflight["stdout"],
        "project_os_stderr": preflight["stderr"],
        "tracked_snapshot": tracked["content_ref"],
        "compiled_inventory": inventory["paths_ref"],
    }
    return payload, refs


def _contract_only(execution_manifest_path: Path) -> int:
    execution = BASE._load_json(execution_manifest_path)
    active, capture = _validate_execution_manifest(
        execution,
        execution_manifest_path,
    )
    compiled = _compile_repository_inventory_v3(ROOT, active)
    inventory = _validate_inventory(compiled)
    result = {
        "status": "pass",
        "execution_manifest_ref": execution_manifest_path.relative_to(ROOT).as_posix(),
        "active_suite_manifest_ref": execution["active_suite_manifest_ref"],
        "capture_plugin_ref": capture.relative_to(ROOT).as_posix(),
        "selected_test_paths": list(BASE._selected_test_paths(active)),
        "compiled_inventory_closure_digest": inventory["closure_digest"],
        "proof_policy": inventory["repository_reference_policy"],
        "eligibility_attestation_executed": False,
        "host_proof_runs_consumed": 0,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def _eligibility(
    execution_manifest_path: Path,
    output_root: Path,
) -> int:
    if output_root.exists() or output_root.with_name(output_root.name + ".partial").exists():
        raise BASE.HostProofError("v3_eligibility_output_root_already_exists")
    if output_root.resolve().is_relative_to(ROOT):
        raise BASE.HostProofError("v3_eligibility_output_must_be_outside_repository")
    execution = BASE._load_json(execution_manifest_path)
    staging = output_root.with_name(output_root.name + ".partial")
    staging.mkdir(parents=True)
    store = BASE.ObjectStore(staging)
    result: dict[str, Any]
    try:
        payload, refs = _boundary_payload(
            execution_manifest_path=execution_manifest_path,
            execution=execution,
            scope=ELIGIBILITY_SCOPE,
            store=store,
        )
        try:
            result = build_eligibility_attestation(payload, evidence_refs=refs)
        except ProofControlPlaneError as exc:
            raise BASE.HostProofError(exc.code) from exc
        for ref in BASE._all_refs(result):
            store.assert_readback(ref)
        BASE._write_json(staging / "eligibility.json", result)
        target = output_root
    except BaseException as exc:
        code = exc.code if isinstance(exc, BASE.HostProofError) else f"unexpected_{type(exc).__name__}"
        result = {
            "schema_version": ELIGIBILITY_ATTESTATION_SCHEMA,
            "status": "failed_non_consuming_terminal",
            "error": code,
            "exception_detail": store.put(traceback.format_exc().encode("utf-8")),
            "eligibility_attestations_consumed": 1,
            "host_proof_runs_consumed": 0,
            "business_promotable": False,
        }
        BASE._write_json(staging / "eligibility.json", result)
        target = output_root.with_name(output_root.name + ".failed")
    staging.replace(target)
    print(
        json.dumps(
            {
                "status": result["status"],
                "output_root": target.as_posix(),
                "eligibility_sha256": sha256_file(target / "eligibility.json"),
                "host_proof_runs_consumed": 0,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if result["status"] == "pass_non_consuming" else 1


def _host(
    *,
    execution_manifest_path: Path,
    eligibility_path: Path,
    host_authority_path: Path,
    output_root: Path,
) -> int:
    if eligibility_path.resolve().is_relative_to(ROOT):
        raise BASE.HostProofError("v3_eligibility_evidence_must_be_external")
    if host_authority_path.resolve().is_relative_to(ROOT):
        raise BASE.HostProofError("v3_host_authority_must_be_external")
    execution = BASE._load_json(execution_manifest_path)
    attestation = BASE._load_json(eligibility_path)
    authority = BASE._load_json(host_authority_path)
    with tempfile.TemporaryDirectory(prefix="fin_ia_v3_host_recompute_") as value:
        store = BASE.ObjectStore(Path(value))
        recomputed, _ = _boundary_payload(
            execution_manifest_path=execution_manifest_path,
            execution=execution,
            scope=HOST_SCOPE,
            store=store,
        )
        try:
            attestation_digest = validate_eligibility_attestation(
                attestation,
                recomputed_payload=recomputed,
            )
            validate_host_authority(
                authority,
                host_scope=HOST_SCOPE,
                eligibility_file_sha256=sha256_file(eligibility_path),
                eligibility_attestation_digest=attestation_digest,
            )
        except ProofControlPlaneError as exc:
            raise BASE.HostProofError(exc.code) from exc

    BASE.EXPECTED_SCOPE = HOST_SCOPE
    return BASE._execute(
        execution_manifest_path=execution_manifest_path,
        output_root=output_root,
    )


BASE.EXECUTION_SCHEMA = EXECUTION_SCHEMA
BASE.VERIFICATION_SCHEMA = VERIFICATION_SCHEMA
BASE._validate_execution_manifest = _validate_execution_manifest
BASE._inventory_evidence = _inventory_evidence
BASE.compile_repository_inventory = _compile_repository_inventory_v3


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate or execute the FIN 0.1.3 S0 exit-contract v3 proof "
            "control plane."
        )
    )
    parser.add_argument("--execution-manifest", type=Path, required=True)
    parser.add_argument("--contract-only", action="store_true")
    parser.add_argument("--eligibility-output-root", type=Path)
    parser.add_argument("--host-output-root", type=Path)
    parser.add_argument("--eligibility-ref", type=Path)
    parser.add_argument("--host-authority-ref", type=Path)
    args = parser.parse_args()
    modes = sum(
        [
            int(args.contract_only),
            int(args.eligibility_output_root is not None),
            int(args.host_output_root is not None),
        ]
    )
    if modes != 1:
        raise BASE.HostProofError("v3_exactly_one_mode_required")
    execution_manifest_path = args.execution_manifest.resolve()
    if args.contract_only:
        if args.eligibility_ref is not None or args.host_authority_ref is not None:
            raise BASE.HostProofError("v3_contract_only_extra_input_forbidden")
        return _contract_only(execution_manifest_path)
    if args.eligibility_output_root is not None:
        if args.eligibility_ref is not None or args.host_authority_ref is not None:
            raise BASE.HostProofError("v3_eligibility_extra_input_forbidden")
        return _eligibility(
            execution_manifest_path,
            args.eligibility_output_root.resolve(),
        )
    if args.eligibility_ref is None or args.host_authority_ref is None:
        raise BASE.HostProofError("v3_host_requires_eligibility_and_authority")
    return _host(
        execution_manifest_path=execution_manifest_path,
        eligibility_path=args.eligibility_ref.resolve(),
        host_authority_path=args.host_authority_ref.resolve(),
        output_root=args.host_output_root.resolve(),
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BASE.HostProofError as exc:
        print(json.dumps({"status": "failed_pre_execution", "error": exc.code}))
        raise SystemExit(2)
