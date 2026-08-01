from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest

from sec_agent.hermetic_test_runner import (
    HermeticTestRunnerError,
    compile_repository_inventory as legacy_compile_repository_inventory,
)
from sec_agent.proof_control_plane import (
    ELIGIBILITY_ATTESTATION_SCHEMA,
    HOST_AUTHORITY_SCHEMA,
    PROOF_POLICY_CONSUMERS,
    ProofControlPlaneError,
    REPOSITORY_REFERENCE_PROOF_POLICY_BINDING_SCHEMA,
    build_eligibility_attestation,
    build_eligibility_payload,
    canonical_bytes,
    compile_v3_repository_inventory,
    load_repository_reference_proof_policy,
    sha256_bytes,
    sha256_file,
    validate_eligibility_attestation,
    validate_host_authority,
)
from sec_agent.runtime_contract_governance import (
    validate_active_test_suite_manifest,
)


ROOT = Path(__file__).resolve().parents[2]
POLICY_REF = (
    "configs/runtime/fin_ia_0_1_3_repository_reference_proof_policy_v3_0.json"
)
REGISTRY_REF = "configs/runtime/fin_ia_0_1_3_reference_role_registry_v1_1.json"
RUNNER_REF = "scripts/engineering/run_fin_0_1_3_s0_v3_proof_control_plane.py"
ACTIVE_REF = (
    "configs/releases/fin_ia_0_1_3_s0_active_test_suite_manifest_v1_3.json"
)
PROJECTION_REF = "configs/runtime/fin_ia_0_1_3_current_program_projection_v1_9.json"
NEXT = (
    "FIN-0.1.3-S0-EXIT-CONTRACT-V3-CLEAN-HEAD-EXACT-BOUNDARY-"
    "ELIGIBILITY-ATTESTATION-AUTHORITY-DECISION"
)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _git(repository: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repository,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _policy_binding(repository: Path, policy_ref: str) -> dict[str, str]:
    return {
        "schema_version": REPOSITORY_REFERENCE_PROOF_POLICY_BINDING_SCHEMA,
        "policy_ref": policy_ref,
        "policy_sha256": sha256_file(repository / policy_ref),
    }


def _policy_document(repository: Path, policy_ref: str) -> dict[str, Any]:
    return json.loads((repository / policy_ref).read_text(encoding="utf-8"))


def _compile_v3(repository: Path, manifest: dict[str, Any]) -> Any:
    return compile_v3_repository_inventory(
        repository,
        manifest,
        legacy_compile=legacy_compile_repository_inventory,
    )


def _seal_policy(repository: Path, policy_ref: str, value: dict[str, Any]) -> None:
    canonical = {key: item for key, item in value.items() if key != "policy_canonical_digest"}
    value["policy_canonical_digest"] = sha256_bytes(canonical_bytes(canonical))
    _write_json(repository / policy_ref, value)


def _minimal_repository(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init", "--quiet")
    (repository / "runner.py").write_text("RUNNER = True\n", encoding="utf-8")
    (repository / "tests").mkdir()
    (repository / "tests/pass.py").write_text(
        "def test_pass():\n    assert True\n", encoding="utf-8"
    )
    (repository / "configs/runtime").mkdir(parents=True)
    policy_ref = "configs/runtime/policy.json"
    registry_ref = "configs/runtime/reference_roles.json"
    (repository / registry_ref).write_bytes((ROOT / REGISTRY_REF).read_bytes())
    policy = _policy_document(ROOT, POLICY_REF)
    policy["reference_role_registry_ref"] = registry_ref
    policy["reference_role_registry_sha256"] = sha256_file(repository / registry_ref)
    _seal_policy(repository, policy_ref, policy)
    manifest = {
        "suites": [
            {
                "selected": True,
                "test_paths": ["tests/pass.py"],
            }
        ],
        "hermetic_package_policy": {
            "required_runner_files": ["runner.py"],
            "repository_seed_paths": [],
            "repository_prefixes": [],
            "repository_reference_policy": _policy_binding(repository, policy_ref),
        },
    }
    _git(repository, "add", ".")
    _git(
        repository,
        "-c",
        "user.name=FIN Test",
        "-c",
        "user.email=fin-test@example.invalid",
        "commit",
        "--quiet",
        "-m",
        "fixture",
    )
    return repository, manifest


def _fake_payload_inputs(policy: Any) -> dict[str, Any]:
    hex_a = "a" * 64
    hex_b = "b" * 64
    return {
        "execution_manifest_ref": "configs/releases/execution.json",
        "execution_manifest_sha256": hex_a,
        "active_suite_manifest_ref": "configs/releases/active.json",
        "active_suite_manifest_sha256": hex_b,
        "source_bindings": [
            {"role": "a", "ref": "a.json", "sha256": hex_a},
            {"role": "b", "ref": "b.json", "sha256": hex_b},
        ],
        "policy": policy,
        "git_state": {
            "head": hex_a,
            "branch": "codex/test",
            "upstream_head": hex_a,
            "clean": True,
            "synced": True,
            "status_sha256": hashlib.sha256(b"").hexdigest(),
            "status_bytes": 0,
        },
        "project_os_preflight": {
            "status": "pass",
            "open_full_chain_blocker_count": 0,
        },
        "tracked_snapshot": {"file_count": 3, "canonical_sha256": hex_a},
        "compiled_inventory": {
            "path_count": 3,
            "tracked_path_count": 3,
            "explicit_allowlist_path_count": 0,
            "closure_digest": hex_b,
            "reference_role_report": {
                "unknown_count": 0,
                "observation_digest": hex_a,
            },
        },
        "selected_test_paths": ["tests/a.py", "tests/b.py"],
    }


def test_policy_source_has_one_ordered_consumer_contract_and_split_semantics() -> None:
    binding = _policy_binding(ROOT, POLICY_REF)
    policy = load_repository_reference_proof_policy(ROOT, binding)
    raw = _policy_document(ROOT, POLICY_REF)

    assert raw["consumers"] == list(PROOF_POLICY_CONSUMERS)
    assert raw["unknown_reference_behavior"] == "fail_closed"
    assert raw["unknown_reference_reporting"] == "collect_all_typed_envelope"
    assert policy.source_ref == POLICY_REF
    assert policy.reference_role_registry_ref == REGISTRY_REF
    assert policy.compiler_policy["unknown_reference_behavior"] == "fail_closed"
    assert policy.compiler_policy["unknown_reference_reporting"] == "collect_all_typed_envelope"


def test_v3_binding_enters_compiled_closure_and_preserves_six_role_report(
    tmp_path: Path,
) -> None:
    repository, manifest = _minimal_repository(tmp_path)
    compiled = _compile_v3(repository, manifest)
    report = compiled.reference_role_report
    policy = compiled.as_dict()["repository_reference_policy"]

    assert policy["ref"] == "configs/runtime/policy.json"
    assert policy["sha256"] == sha256_file(repository / "configs/runtime/policy.json")
    assert Path("configs/runtime/policy.json") in compiled.paths
    assert Path("configs/runtime/reference_roles.json") in compiled.paths
    assert report is not None
    assert report.unknowns == ()
    assert set(report.as_dict()["role_counts"]) == {
        "repository_resource",
        "package_relative_audit",
        "external_content",
        "restricted_runtime_audit",
        "model_run_report",
        "semantic_followup",
        "unknown",
    }


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("binding_digest", "proof_policy_binding_digest_drift"),
        ("extra_field", "proof_policy_source_surface_invalid"),
        ("behavior", "proof_policy_boundary_invalid"),
        ("reporting", "proof_policy_boundary_invalid"),
        ("consumer_order", "proof_policy_consumer_order_invalid"),
        ("canonical_digest", "proof_policy_canonical_digest_drift"),
        ("registry_digest", "proof_policy_registry_digest_drift"),
    ],
)
def test_policy_schema_digest_order_and_value_mutations_fail_closed(
    tmp_path: Path,
    mutation: str,
    error: str,
) -> None:
    repository, manifest = _minimal_repository(tmp_path)
    policy_ref = "configs/runtime/policy.json"
    policy = _policy_document(repository, policy_ref)
    if mutation == "binding_digest":
        manifest["hermetic_package_policy"]["repository_reference_policy"][
            "policy_sha256"
        ] = "0" * 64
    elif mutation == "extra_field":
        policy["unowned"] = True
        _seal_policy(repository, policy_ref, policy)
        manifest["hermetic_package_policy"]["repository_reference_policy"] = _policy_binding(repository, policy_ref)
    elif mutation == "behavior":
        policy["unknown_reference_behavior"] = "collect_all_fail_closed"
        _seal_policy(repository, policy_ref, policy)
        manifest["hermetic_package_policy"]["repository_reference_policy"] = _policy_binding(repository, policy_ref)
    elif mutation == "reporting":
        policy["unknown_reference_reporting"] = "first_only"
        _seal_policy(repository, policy_ref, policy)
        manifest["hermetic_package_policy"]["repository_reference_policy"] = _policy_binding(repository, policy_ref)
    elif mutation == "consumer_order":
        policy["consumers"] = list(reversed(policy["consumers"]))
        _seal_policy(repository, policy_ref, policy)
        manifest["hermetic_package_policy"]["repository_reference_policy"] = _policy_binding(repository, policy_ref)
    elif mutation == "canonical_digest":
        policy["policy_canonical_digest"] = "0" * 64
        _write_json(repository / policy_ref, policy)
        manifest["hermetic_package_policy"]["repository_reference_policy"] = _policy_binding(repository, policy_ref)
    elif mutation == "registry_digest":
        policy["reference_role_registry_sha256"] = "0" * 64
        _seal_policy(repository, policy_ref, policy)
        manifest["hermetic_package_policy"]["repository_reference_policy"] = _policy_binding(repository, policy_ref)

    with pytest.raises((HermeticTestRunnerError, ProofControlPlaneError), match=error):
        _compile_v3(repository, manifest)


def test_eligibility_payload_attestation_and_host_authority_are_digest_bound() -> None:
    policy = load_repository_reference_proof_policy(
        ROOT,
        _policy_binding(ROOT, POLICY_REF),
    )
    payload = build_eligibility_payload(**_fake_payload_inputs(policy))
    ref = {"sha256": "c" * 64, "bytes": 1, "ref": "objects/c"}
    attestation = build_eligibility_attestation(
        payload,
        evidence_refs={"tracked_snapshot": ref},
    )

    digest = validate_eligibility_attestation(
        attestation,
        recomputed_payload=payload,
    )
    assert attestation["schema_version"] == ELIGIBILITY_ATTESTATION_SCHEMA
    assert attestation["host_proof_runs_consumed"] == 0
    assert payload["consumption_boundary"] == (
        "before_host_execution_started_marker_and_import_sweep"
    )

    drifted = deepcopy(payload)
    drifted["compiled_inventory"]["closure_digest"] = "d" * 64
    with pytest.raises(
        ProofControlPlaneError,
        match="eligibility_attestation_recompute_drift",
    ):
        validate_eligibility_attestation(
            attestation,
            recomputed_payload=drifted,
        )

    authority = {
        "schema_version": HOST_AUTHORITY_SCHEMA,
        "status": "authorized_for_one_matching_v3_host_run",
        "host_scope": "scope",
        "eligibility_file_sha256": "e" * 64,
        "eligibility_attestation_digest": digest,
        "maximum_host_proof_runs": 1,
        "formal_proof_authorized": False,
        "model_provider_network_business_authorized": False,
        "automatic_retry_replacement_or_v4_authorized": False,
    }
    validate_host_authority(
        authority,
        host_scope="scope",
        eligibility_file_sha256="e" * 64,
        eligibility_attestation_digest=digest,
    )
    authority["maximum_host_proof_runs"] = 2
    with pytest.raises(ProofControlPlaneError, match="host_authority_boundary_invalid"):
        validate_host_authority(
            authority,
            host_scope="scope",
            eligibility_file_sha256="e" * 64,
            eligibility_attestation_digest=digest,
        )


def test_host_path_recomputes_matching_eligibility_before_base_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = importlib.util.spec_from_file_location("fin_v3_runner_test", ROOT / RUNNER_REF)
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = runner
    spec.loader.exec_module(runner)

    policy = load_repository_reference_proof_policy(
        ROOT,
        _policy_binding(ROOT, POLICY_REF),
    )
    payload = build_eligibility_payload(**_fake_payload_inputs(policy))
    attestation = build_eligibility_attestation(payload, evidence_refs={})
    eligibility_path = tmp_path / "eligibility.json"
    _write_json(eligibility_path, attestation)
    authority = {
        "schema_version": HOST_AUTHORITY_SCHEMA,
        "status": "authorized_for_one_matching_v3_host_run",
        "host_scope": runner.HOST_SCOPE,
        "eligibility_file_sha256": sha256_file(eligibility_path),
        "eligibility_attestation_digest": attestation["attestation_digest"],
        "maximum_host_proof_runs": 1,
        "formal_proof_authorized": False,
        "model_provider_network_business_authorized": False,
        "automatic_retry_replacement_or_v4_authorized": False,
    }
    authority_path = tmp_path / "authority.json"
    _write_json(authority_path, authority)
    execution_path = ROOT / "configs/releases/placeholder_v3_execution.json"
    events: list[str] = []

    monkeypatch.setattr(runner.BASE, "_load_json", lambda path: json.loads(path.read_text(encoding="utf-8")) if path in {eligibility_path, authority_path} else {})
    monkeypatch.setattr(
        runner,
        "_boundary_payload",
        lambda **kwargs: (events.append("recompute") or payload, {}),
    )
    monkeypatch.setattr(
        runner.BASE,
        "_execute",
        lambda **kwargs: events.append("execution_started") or 0,
    )

    assert runner._host(
        execution_manifest_path=execution_path,
        eligibility_path=eligibility_path,
        host_authority_path=authority_path,
        output_root=tmp_path / "host",
    ) == 0
    assert events == ["recompute", "execution_started"]


def test_current_v3_manifest_projection_and_product_boundary() -> None:
    active = json.loads((ROOT / ACTIVE_REF).read_text(encoding="utf-8"))
    projection = json.loads((ROOT / PROJECTION_REF).read_text(encoding="utf-8"))
    policy = active["hermetic_package_policy"]["repository_reference_policy"]

    assert policy == _policy_binding(ROOT, POLICY_REF)
    assert active["fixed_budget"]["v3_implementation_eligibility_host_formal"] == [
        1,
        0,
        0,
        0,
    ]
    assert active["next_action_on_implementation_pass"] == NEXT
    assert projection["expectations"]["current_next_action"] == NEXT
    assert projection["expectations"][
        "v3_implementation_eligibility_host_formal_observed"
    ] == [1, 0, 0, 0]
    assert projection["expectations"]["FIN_0_1_3_S1_entry_authorized"] is False
    assert projection["expectations"]["FIN_0_1_release_qualified"] is False


def test_current_v3_manifest_projection_and_repository_inventory_compile() -> None:
    active = json.loads((ROOT / ACTIVE_REF).read_text(encoding="utf-8"))

    validate_active_test_suite_manifest(active)
    spec = importlib.util.spec_from_file_location(
        "fin_v3_runner_current_compile_test", ROOT / RUNNER_REF
    )
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = runner
    spec.loader.exec_module(runner)
    assert runner._validate_current_projection_v3(ROOT, PROJECTION_REF) == Path(
        PROJECTION_REF
    )

    compiled = runner._compile_repository_inventory_v3(ROOT, active)
    report = compiled.reference_role_report
    policy = compiled.as_dict()["repository_reference_policy"]
    assert policy["ref"] == POLICY_REF
    assert policy["sha256"] == sha256_file(ROOT / POLICY_REF)
    assert compiled.explicit_allowlist_paths == ()
    assert report is not None
    assert report.unknowns == ()
    assert report.as_dict()["unknown_count"] == 0
