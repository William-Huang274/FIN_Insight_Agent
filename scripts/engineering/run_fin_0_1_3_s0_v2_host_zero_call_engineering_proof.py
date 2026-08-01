from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
BASE_RUNNER_PATH = ROOT / (
    "scripts/engineering/run_fin_0_1_3_s0_t03_host_zero_call_proof.py"
)
DEFAULT_EXECUTION_MANIFEST = ROOT / (
    "configs/releases/fin_ia_0_1_3_s0_v2_host_zero_call_engineering_"
    "proof_execution_manifest_v1_0.json"
)
EXECUTION_SCHEMA = "fin_ia_0_1_3_s0_v2_host_zero_call_proof_execution_v1_0"
VERIFICATION_SCHEMA = (
    "fin_ia_0_1_3_s0_v2_host_zero_call_engineering_proof_verification_v1_0"
)
EXPECTED_SCOPE = (
    "FIN-0.1.3-S0-REFERENCE-ROLE-TAXONOMY-AND-CURRENT-RUNTIME-HOST-"
    "ZERO-CALL-ENGINEERING-PROOF"
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
        "fin_ia_0_1_3_s0_t03_host_proof_base",
        BASE_RUNNER_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("base_host_proof_runner_load_failed")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BASE = _load_base_runner()


def _manifest_memberships(
    manifest: Mapping[str, Any], nodeid: str
) -> list[dict[str, Any]]:
    normalized_nodeid = nodeid.replace("\\", "/")
    node_path = normalized_nodeid.split("::", 1)[0]
    rows: list[dict[str, Any]] = []
    for suite in manifest["suites"]:
        if not suite["selected"]:
            continue
        matched = False
        for raw_item in suite["test_paths"]:
            item = str(raw_item).replace("\\", "/")
            if "::" in item:
                matched = normalized_nodeid == item or normalized_nodeid.startswith(
                    item + "["
                )
            else:
                matched = node_path == item
            if matched:
                break
        if matched:
            rows.append(
                {
                    "suite_id": suite["suite_id"],
                    "proof_class": suite["proof_class"],
                    "gates_current_release": bool(suite["gates_current_release"]),
                }
            )
    if not rows:
        raise BASE.HostProofError(f"test_without_manifest_membership:{nodeid}")
    return rows


def _validate_execution_manifest(
    manifest: Mapping[str, Any], manifest_path: Path
) -> tuple[dict[str, Any], Path]:
    required = {
        "schema_version",
        "execution_id",
        "status",
        "run_scope",
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
        raise BASE.HostProofError("execution_manifest_top_level_invalid")
    if manifest["schema_version"] != EXECUTION_SCHEMA:
        raise BASE.HostProofError("execution_manifest_schema_invalid")
    if manifest["status"] != "ready_unexecuted":
        raise BASE.HostProofError("execution_manifest_status_invalid")
    if manifest["run_scope"] != EXPECTED_SCOPE:
        raise BASE.HostProofError("execution_manifest_scope_invalid")

    authority = manifest["authority"]
    expected_authority = {
        "v2_host_zero_call_engineering_proof_authorized": True,
        "maximum_host_proof_runs": 1,
        "host_proof_runs_consumed_before_execution": 0,
        "formal_two_disposable_proof_authorized": False,
        "old_T03_rerun_or_reinterpretation_authorized": False,
        "shared_runtime_or_contract_repair_during_proof_authorized": False,
        "model_provider_credential_network_source_external_tool_authorized": False,
        "admission_business_run_or_business_artifact_authorized": False,
        "S1_S2_release_or_FIN_0_1_4_authorized": False,
    }
    if not isinstance(authority, Mapping) or any(
        authority.get(key) != value for key, value in expected_authority.items()
    ):
        raise BASE.HostProofError("execution_manifest_authority_invalid")

    budgets = manifest["budgets"]
    expected_budgets = {
        "v2_implementation_host_formal_maximum": [1, 1, 1],
        "v2_observed_before_execution": [1, 0, 0],
        "v2_host_engineering_proof_runs_maximum": 1,
        "v2_host_engineering_proof_runs_consumed_before_execution": 0,
        "formal_two_disposable_packages_created_or_executed": 0,
        "automatic_retries_replacements_or_second_host_runs": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "credential_reads_or_probes": 0,
        "network_source_or_external_tool_calls": 0,
        "new_admissions": 0,
        "business_runs": 0,
        "business_artifacts": 0,
    }
    if not isinstance(budgets, Mapping) or any(
        budgets.get(key) != value for key, value in expected_budgets.items()
    ):
        raise BASE.HostProofError("execution_manifest_budget_invalid")

    for binding in manifest["source_bindings"]:
        if not isinstance(binding, Mapping) or set(binding) != {
            "role",
            "ref",
            "sha256",
        }:
            raise BASE.HostProofError("execution_manifest_source_binding_invalid")
        path = ROOT / str(binding["ref"])
        if not path.is_file() or BASE._sha256_file(path) != str(binding["sha256"]):
            raise BASE.HostProofError(
                f"execution_manifest_source_binding_drift:{binding.get('role')}"
            )

    active_path = ROOT / str(manifest["active_suite_manifest_ref"])
    active = BASE._load_json(active_path)
    BASE.validate_active_test_suite_manifest(active)
    if active.get("status") != (
        "frozen_ready_for_single_authorized_v2_host_zero_call_engineering_proof"
    ):
        raise BASE.HostProofError("active_suite_manifest_status_invalid")
    plugin_path = ROOT / str(manifest["capture_plugin_ref"])
    if not plugin_path.is_file():
        raise BASE.HostProofError("execution_manifest_capture_plugin_missing")
    if not manifest_path.resolve().is_relative_to(ROOT):
        raise BASE.HostProofError("execution_manifest_must_be_repository_owned")
    return active, plugin_path


def _inventory_evidence(compiled: Any, store: Any) -> dict[str, Any]:
    paths = [path.as_posix() for path in compiled.paths]
    forbidden = [
        value
        for value in paths
        if value == ".git"
        or value.startswith(".git/")
        or value == ".codex_runtime"
        or value.startswith(".codex_runtime/")
    ]
    if forbidden:
        raise BASE.HostProofError("compiled_inventory_contains_forbidden_path")
    if compiled.explicit_allowlist_paths:
        raise BASE.HostProofError(
            "compiled_inventory_contains_nontracked_allowlist_path"
        )
    report = compiled.reference_role_report
    if report is None:
        raise BASE.HostProofError("reference_role_report_missing")
    report_value = report.as_dict()
    role_counts = report_value.get("role_counts")
    if (
        report_value.get("unknown_count") != 0
        or not isinstance(role_counts, Mapping)
        or set(role_counts) != {*EXPECTED_ROLES, "unknown"}
    ):
        raise BASE.HostProofError("reference_role_report_not_all_known")
    if len(str(report_value.get("observation_digest", ""))) != 64:
        raise BASE.HostProofError("reference_role_observation_digest_invalid")
    payload = {
        "schema_version": "fin_ia_s0_v2_host_compiled_repository_inventory_v1_0",
        "paths": paths,
        "tracked_paths": list(compiled.tracked_paths),
        "explicit_allowlist_paths": list(compiled.explicit_allowlist_paths),
        "recursive_reference_paths": list(compiled.recursive_reference_paths),
        "reference_role_report": report_value,
    }
    return {
        **compiled.as_dict(),
        "forbidden_path_count": len(forbidden),
        "ignored_or_untracked_path_count": len(compiled.explicit_allowlist_paths),
        "paths_ref": store.put_json(payload),
    }


BASE.EXECUTION_SCHEMA = EXECUTION_SCHEMA
BASE.VERIFICATION_SCHEMA = VERIFICATION_SCHEMA
BASE.EXPECTED_SCOPE = EXPECTED_SCOPE
BASE.DEFAULT_EXECUTION_MANIFEST = DEFAULT_EXECUTION_MANIFEST
BASE._memberships = _manifest_memberships
BASE._validate_execution_manifest = _validate_execution_manifest
BASE._inventory_evidence = _inventory_evidence


def _contract_only(execution_manifest_path: Path) -> int:
    execution = BASE._load_json(execution_manifest_path)
    active, capture = _validate_execution_manifest(
        execution,
        execution_manifest_path,
    )
    result = {
        "status": "pass",
        "run_scope": execution["run_scope"],
        "active_suite_manifest_ref": execution["active_suite_manifest_ref"],
        "selected_test_paths": list(BASE._selected_test_paths(active)),
        "capture_plugin_ref": capture.relative_to(ROOT).as_posix(),
        "proof_matrix_executed": False,
        "host_proof_runs_consumed": 0,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the single authorized FIN 0.1.3 S0 v2 host zero-call "
            "engineering proof."
        )
    )
    parser.add_argument(
        "--execution-manifest",
        type=Path,
        default=DEFAULT_EXECUTION_MANIFEST,
    )
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--contract-only", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    execution_manifest_path = args.execution_manifest.resolve()
    if args.contract_only and args.validate_only:
        raise BASE.HostProofError("only_one_validation_mode_allowed")
    if args.contract_only:
        if args.output_root is not None:
            raise BASE.HostProofError("contract_only_does_not_accept_output_root")
        return _contract_only(execution_manifest_path)
    if args.validate_only:
        if args.output_root is not None:
            raise BASE.HostProofError("validate_only_does_not_accept_output_root")
        return BASE._validate_only(execution_manifest_path)
    if args.output_root is None:
        raise BASE.HostProofError("output_root_required_for_execution")
    return BASE._execute(
        execution_manifest_path=execution_manifest_path,
        output_root=args.output_root.resolve(),
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BASE.HostProofError as exc:
        print(json.dumps({"status": "failed_pre_execution", "error": exc.code}))
        raise SystemExit(2)
